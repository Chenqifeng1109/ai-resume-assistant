"""AI简历优化任务的 SQLite 持久化。"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from core.workspace_context import get_active_db_path
from modules.db_client import DB_PATH, get_connection, init_db


def _resolve_db_path(db_path=None):
    return db_path or get_active_db_path(DB_PATH)


TERMINAL_STATUSES = {"completed", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def create_task(request_data: dict, db_path: str | None = None) -> dict:
    target_db = _resolve_db_path(db_path)
    init_db(target_db)
    task_id = f"OF-{uuid4().hex[:12]}"
    created_at = _now()
    connection = get_connection(target_db)
    try:
        connection.execute(
            """
            INSERT INTO resume_optimization_tasks (
                task_id, status, stage, progress, request_data,
                created_at, updated_at
            ) VALUES (?, 'queued', 'queued', 0, ?, ?, ?)
            """,
            (
                task_id,
                json.dumps(request_data, ensure_ascii=False),
                created_at,
                created_at,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return get_task(task_id, target_db)


def update_task(task_id: str, db_path: str | None = None, **changes) -> dict | None:
    allowed = {
        "status",
        "stage",
        "progress",
        "raw_response",
        "result_data",
        "error_code",
        "error_message",
        "attempts",
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
    values.append(_now())
    values.append(task_id)
    connection = get_connection(_resolve_db_path(db_path))
    try:
        connection.execute(
            f"UPDATE resume_optimization_tasks SET {', '.join(assignments)} WHERE task_id = ?",
            values,
        )
        connection.commit()
    finally:
        connection.close()
    return get_task(task_id, db_path)


def get_task(task_id: str, db_path: str | None = None) -> dict | None:
    connection = get_connection(_resolve_db_path(db_path))
    try:
        row = connection.execute(
            "SELECT * FROM resume_optimization_tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    task = dict(row)
    task["request_data"] = _decode(task.get("request_data"), {})
    task["result_data"] = _decode(task.get("result_data"), None)
    task["ok"] = True
    return task


def latest_task(db_path: str | None = None) -> dict | None:
    target_db = _resolve_db_path(db_path)
    init_db(target_db)
    connection = get_connection(target_db)
    try:
        row = connection.execute(
            "SELECT task_id FROM resume_optimization_tasks ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    return get_task(row["task_id"], target_db) if row else None


def reset_task(task_id: str, db_path: str | None = None) -> dict | None:
    return update_task(
        task_id,
        db_path,
        status="queued",
        stage="queued",
        progress=0,
        raw_response=None,
        result_data=None,
        error_code=None,
        error_message=None,
        attempts=0,
    )
