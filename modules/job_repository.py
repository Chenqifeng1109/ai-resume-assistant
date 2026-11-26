"""岗位批次的统一 SQLite 仓库与旧 JSON 导入工具。"""

from datetime import datetime
import hashlib
import json
import os

from config import DATA_DIR
from core.file_security import resolve_file_in_directory, validate_filename
from modules.db_client import get_connection, init_db


def _validate_batch_id(batch_id: str) -> str:
    safe_batch_id = validate_filename(batch_id, {".json"})
    if safe_batch_id is None or not safe_batch_id.startswith("jobs_"):
        raise ValueError("岗位批次文件名不安全")
    return safe_batch_id


def _validate_batch_lookup(batch_id: str) -> str:
    safe_batch_id = validate_filename(batch_id)
    if safe_batch_id is None:
        raise ValueError("岗位批次文件名不安全")
    return safe_batch_id


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_sha256(payload: dict) -> str:
    """计算与空格、缩进和键顺序无关的岗位批次内容哈希。"""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _build_record(batch_id: str, payload: dict) -> dict:
    safe_batch_id = _validate_batch_id(batch_id)
    if not isinstance(payload, dict):
        raise ValueError("岗位批次必须是JSON对象")

    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
        raise ValueError("岗位批次的jobs必须是对象列表")

    profile = payload.get("profile", {})
    keywords = payload.get("keywords", [])
    if not isinstance(profile, dict):
        raise ValueError("岗位批次的profile必须是JSON对象")
    if not isinstance(keywords, list):
        raise ValueError("岗位批次的keywords必须是JSON列表")

    return {
        "batch_id": safe_batch_id,
        "profile_data": _canonical_json(profile),
        "keywords": _canonical_json(keywords),
        "collected_at": str(payload.get("collected_at", "")),
        "resume_name": str(payload.get("resume_name", "")),
        "auto_scored": 1 if payload.get("auto_scored") else 0,
        "scored_at": str(payload.get("scored_at", "")),
        "job_count": len(jobs),
        "payload": _canonical_json(payload),
    }


def _upsert_record(connection, record: dict) -> dict:
    existing = connection.execute(
        """
        SELECT profile_data, keywords, collected_at, resume_name,
               auto_scored, scored_at, job_count, payload
        FROM job_batches
        WHERE batch_id = ?
        """,
        (record["batch_id"],),
    ).fetchone()
    comparable_fields = (
        "profile_data",
        "keywords",
        "collected_at",
        "resume_name",
        "auto_scored",
        "scored_at",
        "job_count",
        "payload",
    )
    if existing is not None and all(
        existing[field] == record[field] for field in comparable_fields
    ):
        return {
            "batch_id": record["batch_id"],
            "job_count": record["job_count"],
            "created": False,
            "changed": False,
            "sha256": payload_sha256(json.loads(record["payload"])),
        }

    connection.execute(
        """
        INSERT INTO job_batches (
            batch_id, profile_data, keywords, collected_at, resume_name,
            auto_scored, scored_at, job_count, payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(batch_id) DO UPDATE SET
            profile_data = excluded.profile_data,
            keywords = excluded.keywords,
            collected_at = excluded.collected_at,
            resume_name = excluded.resume_name,
            auto_scored = excluded.auto_scored,
            scored_at = excluded.scored_at,
            job_count = excluded.job_count,
            payload = excluded.payload,
            updated_at = CURRENT_TIMESTAMP
        """,
        tuple(record[field] for field in ("batch_id", *comparable_fields)),
    )
    return {
        "batch_id": record["batch_id"],
        "job_count": record["job_count"],
        "created": existing is None,
        "changed": existing is not None,
        "sha256": payload_sha256(json.loads(record["payload"])),
    }


def save_collected_job_batch(
    batch_id: str,
    payload: dict,
    db_path: str | None = None,
) -> dict:
    """在一个事务中更新岗位索引和完整批次快照。"""
    record = _build_record(batch_id, payload)
    keywords_text = ",".join(str(item) for item in payload.get("keywords", []))
    indexed_jobs = []
    for job in payload["jobs"]:
        job_id = str(job.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("岗位缺少job_id")
        indexed_jobs.append(
            (
                job_id,
                str(job.get("source", "")),
                str(job.get("title", "")),
                str(job.get("company", "")),
                str(job.get("salary", "")),
                str(job.get("location", "")),
                str(job.get("url", "")),
                str(job.get("description", "")),
                record["batch_id"],
                keywords_text,
            )
        )

    init_db(db_path)
    connection = get_connection(db_path)
    try:
        for indexed_job in indexed_jobs:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, platform, title, company, salary, location,
                    url, description, batch_id, keywords
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    platform = excluded.platform,
                    title = excluded.title,
                    company = excluded.company,
                    salary = excluded.salary,
                    location = excluded.location,
                    url = excluded.url,
                    description = excluded.description,
                    batch_id = excluded.batch_id,
                    keywords = excluded.keywords,
                    created_at = CURRENT_TIMESTAMP
                """,
                indexed_job,
            )
        result = _upsert_record(connection, record)
        connection.commit()
        result["indexed_jobs"] = len(indexed_jobs)
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_job_batch(batch_id: str, payload: dict, db_path: str | None = None) -> dict:
    """把一个完整岗位批次写入 SQLite，内容相同时不重复写。"""
    record = _build_record(batch_id, payload)
    init_db(db_path)
    connection = get_connection(db_path)
    try:
        result = _upsert_record(connection, record)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def load_job_batch(batch_id: str, db_path: str | None = None) -> dict | None:
    """按批次文件名从 SQLite 读取完整岗位快照。"""
    safe_batch_id = _validate_batch_lookup(batch_id)
    init_db(db_path)
    connection = get_connection(db_path)
    try:
        row = connection.execute(
            "SELECT payload FROM job_batches WHERE batch_id = ?",
            (safe_batch_id,),
        ).fetchone()
        return json.loads(row["payload"]) if row else None
    finally:
        connection.close()


VALID_TRACKING_STATUSES = {"unsent", "sent", "interview", "rejected"}


def update_job_tracking(
    batch_id: str,
    *,
    job_id: str = "",
    job_index: int = -1,
    status: str = "unsent",
    note: str = "",
    db_path: str | None = None,
) -> dict:
    """更新批次内单个岗位的投递状态与跟进备注，并持久化写回 SQLite。"""
    try:
        safe_batch_id = _validate_batch_id(batch_id)
    except ValueError as error:
        return {"ok": False, "error": str(error), "error_code": "INVALID_INPUT", "field": "batch_id"}

    clean_status = str(status or "").strip().lower()
    if clean_status not in VALID_TRACKING_STATUSES:
        return {
            "ok": False,
            "error": "投递状态无效，仅支持 unsent / sent / interview / rejected",
            "error_code": "INVALID_INPUT",
            "field": "status",
        }

    clean_note = str(note or "").strip()
    if len(clean_note) > 1000:
        return {
            "ok": False,
            "error": "跟进备注最多 1000 个字符",
            "error_code": "INVALID_INPUT",
            "field": "note",
        }

    payload = load_job_batch(safe_batch_id, db_path)
    if payload is None:
        return {"ok": False, "error": "批次不存在或无数据", "error_code": "NOT_FOUND"}

    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return {"ok": False, "error": "该批次没有岗位记录", "error_code": "NOT_FOUND"}

    clean_job_id = str(job_id or "").strip()
    target_idx = None

    if 0 <= job_index < len(jobs):
        candidate = jobs[job_index]
        if isinstance(candidate, dict) and (
            not clean_job_id or str(candidate.get("job_id") or "").strip() == clean_job_id
        ):
            target_idx = job_index

    if target_idx is None and clean_job_id:
        for idx, item in enumerate(jobs):
            if isinstance(item, dict) and str(item.get("job_id") or "").strip() == clean_job_id:
                target_idx = idx
                break

    if target_idx is None and 0 <= job_index < len(jobs) and isinstance(jobs[job_index], dict):
        target_idx = job_index

    if target_idx is None:
        return {"ok": False, "error": "未找到对应岗位记录", "error_code": "NOT_FOUND"}

    target_job = jobs[target_idx]
    tracked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_job["status"] = clean_status
    target_job["tracking_note"] = clean_note
    target_job["tracked_at"] = tracked_at

    save_job_batch(safe_batch_id, payload, db_path)

    return {
        "ok": True,
        "batch_id": safe_batch_id,
        "job_index": target_idx,
        "job_id": str(target_job.get("job_id") or ""),
        "status": clean_status,
        "tracking_note": clean_note,
        "tracked_at": tracked_at,
    }


def aggregate_job_tracking_board(db_path: str | None = None) -> dict:
    """跨批次汇总所有岗位的投递漏斗统计与跟进看板列表。"""
    init_db(db_path)
    connection = get_connection(db_path)
    try:
        rows = connection.execute(
            """
            SELECT batch_id, collected_at, payload
            FROM job_batches
            ORDER BY collected_at DESC, batch_id DESC
            """
        ).fetchall()
    finally:
        connection.close()

    counts = {"total": 0, "unsent": 0, "sent": 0, "interview": 0, "rejected": 0}
    items = []
    for row in rows:
        batch_id = row["batch_id"]
        collected_at = row["collected_at"] or ""
        try:
            payload = json.loads(row["payload"]) if row["payload"] else {}
        except (TypeError, json.JSONDecodeError):
            payload = {}
        jobs = payload.get("jobs") if isinstance(payload, dict) else []
        if not isinstance(jobs, list):
            continue
        for idx, job in enumerate(jobs):
            if not isinstance(job, dict):
                continue
            status = str(job.get("status") or "unsent").strip().lower()
            if status not in VALID_TRACKING_STATUSES:
                status = "unsent"
            counts["total"] += 1
            counts[status] += 1
            items.append(
                {
                    "batch_id": batch_id,
                    "collected_at": collected_at,
                    "job_index": idx,
                    "job_id": str(job.get("job_id") or ""),
                    "title": str(job.get("title") or ""),
                    "company": str(job.get("company") or ""),
                    "salary": str(job.get("salary") or "面议"),
                    "location": str(job.get("location") or ""),
                    "source": str(job.get("source") or ""),
                    "url": str(job.get("url") or ""),
                    "match_score": job.get("match_score"),
                    "status": status,
                    "tracking_note": str(job.get("tracking_note") or ""),
                    "tracked_at": str(job.get("tracked_at") or ""),
                }
            )

    applied_total = counts["sent"] + counts["interview"] + counts["rejected"]
    interview_rate = round((counts["interview"] / applied_total) * 100, 1) if applied_total > 0 else 0.0
    status_order = {"interview": 0, "sent": 1, "unsent": 2, "rejected": 3}
    items.sort(
        key=lambda it: (
            status_order.get(it["status"], 9),
            -(it["match_score"] if isinstance(it.get("match_score"), (int, float)) else -1),
        )
    )
    return {
        "ok": True,
        "summary": {
            **counts,
            "applied": applied_total,
            "interview_rate": interview_rate,
        },
        "items": items,
    }


def list_job_batches(db_path: str | None = None) -> list[dict]:
    """按采集时间和批次文件名稳定列出完整岗位批次。"""
    init_db(db_path)
    connection = get_connection(db_path)
    try:
        rows = connection.execute(
            """
            SELECT batch_id, collected_at, job_count, keywords, resume_name
            FROM job_batches
            ORDER BY collected_at DESC, batch_id DESC
            """
        ).fetchall()
        batches = []
        for row in rows:
            keywords = json.loads(row["keywords"])
            if not isinstance(keywords, list):
                raise ValueError("岗位批次的keywords必须是JSON列表")
            batches.append(
                {
                    "batch_id": row["batch_id"],
                    "collected_at": row["collected_at"],
                    "job_count": row["job_count"],
                    "keywords": keywords,
                    "resume_name": row["resume_name"],
                }
            )
        return batches
    finally:
        connection.close()


def import_legacy_job_batches(
    data_dir: str = DATA_DIR,
    db_path: str | None = None,
) -> list[dict]:
    """整批校验并导入旧jobs_*.json；任一文件无效时不写入任何批次。"""
    records = []
    for filename in sorted(os.listdir(data_dir)):
        if not filename.startswith("jobs_") or not filename.endswith(".json"):
            continue
        resolved = resolve_file_in_directory(data_dir, filename, {".json"})
        if resolved is None:
            raise ValueError("岗位批次文件名不安全")
        with open(resolved[1], "r", encoding="utf-8") as source:
            payload = json.load(source)
        records.append(_build_record(filename, payload))

    init_db(db_path)
    connection = get_connection(db_path)
    try:
        results = [_upsert_record(connection, record) for record in records]
        connection.commit()
        return results
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
