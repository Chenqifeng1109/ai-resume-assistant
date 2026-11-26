"""岗位采集任务的 SQLite 状态仓库。"""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.workspace_context import get_active_db_path
from modules.db_client import DB_PATH, get_connection, init_db


def _resolve_db_path(db_path=None):
    return db_path or get_active_db_path(DB_PATH)


ACTIVE_STATUSES = {"queued", "running", "cancelling"}
DEFAULT_TIMEOUT_SECONDS = 600


def _now():
    return datetime.now(timezone.utc).isoformat()


def _decode(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def create_task(request_data, db_path=None, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    target_db = _resolve_db_path(db_path)
    init_db(target_db)
    task_id = f"JOB-{uuid4().hex[:12]}"
    created_at = _now()
    timeout_seconds = max(30, min(int(timeout_seconds), 1800))
    deadline_at = (datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)).isoformat()
    connection = get_connection(target_db)
    try:
        connection.execute(
            """
            INSERT INTO job_collection_tasks (
                task_id, status, stage, progress_message, progress_percent,
                jobs_count, request_data, deadline_at, created_at, updated_at
            ) VALUES (?, 'queued', 'queued', '等待后台开始采集', 0, 0, ?, ?, ?, ?)
            """,
            (
                task_id,
                json.dumps(request_data, ensure_ascii=False),
                deadline_at,
                created_at,
                created_at,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return get_task(task_id, target_db)


def update_task(task_id, db_path=None, **changes):
    allowed = {
        "status", "stage", "progress_message", "progress_percent", "jobs_count",
        "result_data", "error_code", "error_message", "cancel_requested",
        "deadline_at",
    }
    assignments = []
    values = []
    for key, value in changes.items():
        if key not in allowed:
            continue
        if key == "result_data" and isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        assignments.append(f"{key} = ?")
        values.append(value)
    if not assignments:
        return get_task(task_id, db_path)
    assignments.append("updated_at = ?")
    values.extend([_now(), task_id])
    connection = get_connection(_resolve_db_path(db_path))
    try:
        connection.execute(
            f"UPDATE job_collection_tasks SET {', '.join(assignments)} WHERE task_id = ?",
            values,
        )
        connection.commit()
    finally:
        connection.close()
    return get_task(task_id, db_path)


def get_task(task_id, db_path=None):
    connection = get_connection(_resolve_db_path(db_path))
    try:
        row = connection.execute(
            "SELECT * FROM job_collection_tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    task = dict(row)
    task["request_data"] = _decode(task.get("request_data"), {})
    task["result_data"] = _decode(task.get("result_data"), None)
    return task


def latest_task(db_path=None):
    target_db = _resolve_db_path(db_path)
    init_db(target_db)
    connection = get_connection(target_db)
    try:
        row = connection.execute(
            "SELECT task_id FROM job_collection_tasks ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    return get_task(row["task_id"], target_db) if row else None


def request_cancel(task_id, db_path=None):
    task = get_task(task_id, db_path)
    if task is None:
        return None
    if task["status"] not in ACTIVE_STATUSES:
        return task
    return update_task(
        task_id,
        db_path,
        status="cancelling",
        stage="cancelling",
        progress_message="正在安全停止采集，请稍候",
        cancel_requested=1,
    )


def get_stop_reason(task_id, db_path=None):
    task = get_task(task_id, db_path)
    if task is None:
        return "cancelled"
    if task.get("cancel_requested"):
        return "cancelled"
    deadline_text = task.get("deadline_at")
    if deadline_text:
        try:
            deadline = datetime.fromisoformat(deadline_text)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= deadline:
                return "timed_out"
        except ValueError:
            return "timed_out"
    return None


def recover_interrupted_tasks(db_path=None):
    target_db = _resolve_db_path(db_path)
    init_db(target_db)
    updated_at = _now()
    connection = get_connection(target_db)
    try:
        cursor = connection.execute(
            """
            UPDATE job_collection_tasks
            SET status = 'interrupted', stage = 'interrupted',
                progress_message = '服务已重启，原采集任务已中断，请重新启动采集',
                error_code = 'WORKER_INTERRUPTED',
                error_message = '服务重启时任务仍未结束',
                updated_at = ?
            WHERE status IN ('queued', 'running', 'cancelling')
            """,
            (updated_at,),
        )
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


def public_status(task):
    if not task:
        return None
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "stage": task["stage"],
        "running": task["status"] in ACTIVE_STATUSES,
        "progress": task["progress_message"],
        "progress_percent": task["progress_percent"],
        "jobs_count": task["jobs_count"],
        "last_run": task["updated_at"],
        "error_code": task.get("error_code"),
        "error_message": task.get("error_message"),
        "cancel_requested": bool(task.get("cancel_requested")),
        "deadline_at": task.get("deadline_at"),
        "result": task.get("result_data"),
    }
