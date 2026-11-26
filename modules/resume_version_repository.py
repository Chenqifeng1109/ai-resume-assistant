"""简历版本的 SQLite 持久化与历史数据迁移。"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime

from core.file_security import validate_filename


VERSION_TYPES = {"original", "optimized"}
SOURCE_STATUSES = {"confirmed", "legacy_unverified"}
VERSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
RESERVED_VERSION_IDS = {".", "..", "current"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_resume_filename(filename: str) -> str:
    safe_filename = validate_filename(filename, {".json"})
    if safe_filename is None:
        raise ValueError("简历文件名不安全")
    return safe_filename


def _safe_version_id(version_id: str) -> str:
    raw_value = str(version_id or "")
    normalized = raw_value.strip()
    if (
        raw_value != normalized
        or
        not VERSION_ID_PATTERN.fullmatch(normalized)
        or normalized.casefold() in RESERVED_VERSION_IDS
    ):
        raise ValueError("版本编号不安全")
    return normalized


def _snapshot(profile: dict) -> dict:
    snapshot = dict(profile) if isinstance(profile, dict) else {}
    for field in (
        "original_profile",
        "optimization_history",
        "active_optimization",
        "_optimization_meta",
    ):
        snapshot.pop(field, None)
    return snapshot


def original_version_id(filename: str) -> str:
    safe_filename = _safe_resume_filename(filename)
    digest = hashlib.sha256(safe_filename.encode("utf-8")).hexdigest()[:20]
    return f"original-{digest}"


def _has_global_version_id_unique(connection) -> bool:
    """识别早期表结构中错误的 version_id 全局唯一约束。"""
    for index_row in connection.execute("PRAGMA index_list(resume_versions)"):
        if not index_row[2]:
            continue
        index_name = str(index_row[1]).replace("'", "''")
        index_columns = [
            row[2]
            for row in connection.execute(f"PRAGMA index_info('{index_name}')")
        ]
        if index_columns == ["version_id"]:
            return True
    return False


def _rebuild_legacy_resume_version_table(connection) -> None:
    """把旧的全局版本编号约束迁移为“每份简历内唯一”。"""
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(resume_versions)")
    }
    source_status_expression = (
        "COALESCE(source_status, 'confirmed')"
        if "source_status" in columns
        else "'confirmed'"
    )
    connection.execute("DROP TABLE IF EXISTS resume_versions_v2_migration")
    connection.execute(
        """
        CREATE TABLE resume_versions_v2_migration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id TEXT NOT NULL,
            resume_filename TEXT NOT NULL,
            version_type TEXT NOT NULL CHECK(version_type IN ('original', 'optimized')),
            source_status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK(source_status IN ('confirmed', 'legacy_unverified')),
            optimization_mode TEXT NOT NULL DEFAULT 'original',
            prompt_version TEXT NOT NULL DEFAULT '',
            target TEXT NOT NULL DEFAULT '',
            content_json TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 0 CHECK(is_current IN (0, 1)),
            created_at TEXT NOT NULL,
            FOREIGN KEY(resume_filename) REFERENCES resumes(filename),
            UNIQUE(resume_filename, version_id)
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO resume_versions_v2_migration (
            id, version_id, resume_filename, version_type, source_status,
            optimization_mode, prompt_version, target, content_json,
            is_current, created_at
        )
        SELECT
            id, version_id, resume_filename, version_type,
            {source_status_expression}, optimization_mode, prompt_version,
            target, content_json, is_current, created_at
        FROM resume_versions
        ORDER BY id
        """
    )
    connection.execute("DROP TABLE resume_versions")
    connection.execute(
        "ALTER TABLE resume_versions_v2_migration RENAME TO resume_versions"
    )


def ensure_resume_version_schema(connection) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id TEXT NOT NULL,
            resume_filename TEXT NOT NULL,
            version_type TEXT NOT NULL CHECK(version_type IN ('original', 'optimized')),
            source_status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK(source_status IN ('confirmed', 'legacy_unverified')),
            optimization_mode TEXT NOT NULL DEFAULT 'original',
            prompt_version TEXT NOT NULL DEFAULT '',
            target TEXT NOT NULL DEFAULT '',
            content_json TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 0 CHECK(is_current IN (0, 1)),
            created_at TEXT NOT NULL,
            FOREIGN KEY(resume_filename) REFERENCES resumes(filename),
            UNIQUE(resume_filename, version_id)
        )
        """
    )
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(resume_versions)")
    }
    if "source_status" not in columns:
        connection.execute(
            "ALTER TABLE resume_versions ADD COLUMN source_status "
            "TEXT NOT NULL DEFAULT 'confirmed'"
        )
    if _has_global_version_id_unique(connection):
        _rebuild_legacy_resume_version_table(connection)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_resume_versions_filename_created "
        "ON resume_versions(resume_filename, created_at DESC, id DESC)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_resume_versions_original "
        "ON resume_versions(resume_filename) WHERE version_type = 'original'"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_resume_versions_current "
        "ON resume_versions(resume_filename) WHERE is_current = 1"
    )


def save_resume_version(
    resume_filename: str,
    version_id: str,
    version_type: str,
    content: dict,
    *,
    source_status: str | None = None,
    optimization_mode: str = "original",
    prompt_version: str = "",
    target: str = "",
    created_at: str = "",
    is_current: bool = False,
    connection=None,
    db_path: str | None = None,
) -> dict:
    safe_filename = _safe_resume_filename(resume_filename)
    safe_version_id = _safe_version_id(version_id)
    if version_type not in VERSION_TYPES:
        raise ValueError("版本类型无效")
    if source_status is not None and source_status not in SOURCE_STATUSES:
        raise ValueError("版本来源状态无效")
    if not isinstance(content, dict) or not content:
        raise ValueError("版本内容必须是非空字典")

    owns_connection = connection is None
    if owns_connection:
        from modules.db_client import get_connection

        connection = get_connection(db_path)

    ensure_resume_version_schema(connection)
    serialized_content = json.dumps(content, ensure_ascii=False, sort_keys=True)
    normalized_source_status = source_status or "confirmed"
    normalized_mode = str(optimization_mode or "original")
    normalized_prompt_version = str(prompt_version or "")
    normalized_target = str(target or "")
    normalized_created_at = str(created_at or "")
    try:
        parent = connection.execute(
            "SELECT 1 FROM resumes WHERE filename = ?",
            (safe_filename,),
        ).fetchone()
        if parent is None:
            raise ValueError("所属简历不存在，不能创建孤立版本")

        existing = connection.execute(
            """
            SELECT version_type, source_status, optimization_mode,
                   prompt_version, target, content_json, created_at
            FROM resume_versions
            WHERE resume_filename = ? AND version_id = ?
            """,
            (safe_filename, safe_version_id),
        ).fetchone()
        if existing is not None:
            immutable_values_match = (
                existing["version_type"] == version_type
                and existing["content_json"] == serialized_content
                and existing["optimization_mode"] == normalized_mode
                and existing["prompt_version"] == normalized_prompt_version
                and existing["target"] == normalized_target
                and (
                    source_status is None
                    or existing["source_status"] == normalized_source_status
                )
                and (
                    not normalized_created_at
                    or existing["created_at"] == normalized_created_at
                )
            )
            if not immutable_values_match:
                raise ValueError("版本编号已存在且内容或元数据不一致")
            if is_current:
                connection.execute(
                    "UPDATE resume_versions SET is_current = 0 WHERE resume_filename = ?",
                    (safe_filename,),
                )
                connection.execute(
                    """
                    UPDATE resume_versions SET is_current = 1
                    WHERE resume_filename = ? AND version_id = ?
                    """,
                    (safe_filename, safe_version_id),
                )
        else:
            if is_current:
                connection.execute(
                    "UPDATE resume_versions SET is_current = 0 WHERE resume_filename = ?",
                    (safe_filename,),
                )
            connection.execute(
                """
                INSERT INTO resume_versions (
                    version_id, resume_filename, version_type, source_status,
                    optimization_mode, prompt_version, target, content_json,
                    is_current, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    safe_version_id,
                    safe_filename,
                    version_type,
                    normalized_source_status,
                    normalized_mode,
                    normalized_prompt_version,
                    normalized_target,
                    serialized_content,
                    1 if is_current else 0,
                    normalized_created_at or _now(),
                ),
            )
        if owns_connection:
            connection.commit()
        return get_resume_version(
            safe_filename,
            safe_version_id,
            connection=connection,
        )
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def save_original_version(
    resume_filename: str,
    profile: dict,
    *,
    created_at: str = "",
    is_current: bool = True,
    source_status: str | None = None,
    connection=None,
    db_path: str | None = None,
) -> dict:
    return save_resume_version(
        resume_filename,
        original_version_id(resume_filename),
        "original",
        _snapshot(profile),
        source_status=source_status,
        optimization_mode="original",
        target=str(profile.get("desired_position", "")),
        created_at=created_at or str(profile.get("parsed_at", "")),
        is_current=is_current,
        connection=connection,
        db_path=db_path,
    )


def save_optimized_version(
    resume_filename: str,
    version: dict,
    *,
    connection=None,
    db_path: str | None = None,
) -> dict:
    profile = version.get("profile") if isinstance(version, dict) else None
    if not isinstance(profile, dict):
        raise ValueError("优化版本缺少完整简历内容")
    return save_resume_version(
        resume_filename,
        str(version.get("version_id", "")),
        "optimized",
        _snapshot(profile),
        source_status="confirmed",
        optimization_mode=str(version.get("optimization_mode", "role_targeted")),
        prompt_version=str(version.get("prompt_version", "")),
        target=str(version.get("target", "")),
        created_at=str(version.get("created_at", "")),
        is_current=True,
        connection=connection,
        db_path=db_path,
    )


def migrate_embedded_resume_versions(connection) -> int:
    """把旧 parsed_data 中的版本历史无损复制到独立表；已有记录时跳过。"""
    ensure_resume_version_schema(connection)
    try:
        rows = connection.execute(
            "SELECT filename, parsed_data, created_at FROM resumes"
        ).fetchall()
    except Exception:
        return 0

    migrated = 0
    for row in rows:
        filename, parsed_data, database_created_at = row
        existing_count = connection.execute(
            "SELECT COUNT(*) FROM resume_versions WHERE resume_filename = ?",
            (filename,),
        ).fetchone()[0]
        if existing_count:
            continue
        try:
            stored_profile = json.loads(parsed_data)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(stored_profile, dict):
            continue

        original = stored_profile.get("original_profile")
        has_confirmed_original = isinstance(original, dict) and bool(original)
        if not has_confirmed_original:
            original = _snapshot(stored_profile)
        history = [
            item
            for item in stored_profile.get("optimization_history", [])
            if isinstance(item, dict) and isinstance(item.get("profile"), dict)
        ]
        active = stored_profile.get("active_optimization", {})
        active_version_id = (
            str(active.get("version_id", "")) if isinstance(active, dict) else ""
        )
        history_ids = [str(item.get("version_id", "")) for item in history]
        current_history_id = (
            active_version_id
            if active_version_id in history_ids
            else (history_ids[-1] if history_ids else "")
        )

        save_original_version(
            filename,
            original,
            created_at=str(original.get("parsed_at", "") or database_created_at or ""),
            is_current=not history,
            source_status=(
                "confirmed" if has_confirmed_original else "legacy_unverified"
            ),
            connection=connection,
        )
        migrated += 1
        for index, item in enumerate(history):
            version_id = str(item.get("version_id", "")).strip()
            if not VERSION_ID_PATTERN.fullmatch(version_id):
                seed = json.dumps(item, ensure_ascii=False, sort_keys=True)
                version_id = "legacy-" + hashlib.sha256(
                    f"{filename}:{index}:{seed}".encode("utf-8")
                ).hexdigest()[:20]
            migrated_version = dict(item)
            migrated_version["version_id"] = version_id
            migrated_version.setdefault(
                "optimization_mode",
                "jd_targeted" if str(item.get("job_description", "")).strip() else "role_targeted",
            )
            migrated_version.setdefault("prompt_version", "")
            save_resume_version(
                filename,
                version_id,
                "optimized",
                _snapshot(item["profile"]),
                optimization_mode=migrated_version["optimization_mode"],
                prompt_version=migrated_version["prompt_version"],
                target=str(item.get("target", "")),
                created_at=str(item.get("created_at", "") or database_created_at or ""),
                is_current=version_id == current_history_id,
                connection=connection,
            )
            migrated += 1
    return migrated


def _row_to_version(row, include_content: bool) -> dict:
    data = {
        "id": row["id"],
        "version_id": row["version_id"],
        "resume_filename": row["resume_filename"],
        "version_type": row["version_type"],
        "source_status": row["source_status"],
        "optimization_mode": row["optimization_mode"],
        "prompt_version": row["prompt_version"],
        "target": row["target"],
        "is_current": bool(row["is_current"]),
        "created_at": row["created_at"],
    }
    if include_content:
        data["content"] = json.loads(row["content_json"])
    return data


def list_resume_versions(resume_filename: str, db_path: str | None = None) -> list[dict]:
    safe_filename = _safe_resume_filename(resume_filename)
    from modules.db_client import get_connection

    connection = get_connection(db_path)
    try:
        migrate_embedded_resume_versions(connection)
        connection.commit()
        rows = connection.execute(
            """
            SELECT * FROM resume_versions
            WHERE resume_filename = ?
            ORDER BY created_at DESC, id DESC
            """,
            (safe_filename,),
        ).fetchall()
        return [_row_to_version(row, False) for row in rows]
    finally:
        connection.close()


def get_resume_version(
    resume_filename: str,
    version_id: str | None = None,
    *,
    current: bool = False,
    connection=None,
    db_path: str | None = None,
) -> dict | None:
    safe_filename = _safe_resume_filename(resume_filename)
    if not current:
        version_id = _safe_version_id(version_id)

    owns_connection = connection is None
    if owns_connection:
        from modules.db_client import get_connection

        connection = get_connection(db_path)
        migrate_embedded_resume_versions(connection)
        connection.commit()
    try:
        if current:
            row = connection.execute(
                """
                SELECT * FROM resume_versions
                WHERE resume_filename = ? AND is_current = 1
                """,
                (safe_filename,),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT * FROM resume_versions
                WHERE resume_filename = ? AND version_id = ?
                """,
                (safe_filename, version_id),
            ).fetchone()
        return _row_to_version(row, True) if row else None
    finally:
        if owns_connection:
            connection.close()


def delete_resume_version(
    resume_filename: str,
    version_id: str,
    db_path: str | None = None,
    *,
    connection=None,
) -> dict:
    safe_filename = _safe_resume_filename(resume_filename)
    safe_version_id = _safe_version_id(version_id)
    owns_connection = connection is None
    if owns_connection:
        from modules.db_client import get_connection

        connection = get_connection(db_path)
    try:
        migrate_embedded_resume_versions(connection)
        row = connection.execute(
            """
            SELECT version_type, is_current FROM resume_versions
            WHERE resume_filename = ? AND version_id = ?
            """,
            (safe_filename, safe_version_id),
        ).fetchone()
        if row is None:
            if owns_connection:
                connection.commit()
            return {"deleted": False, "reason": "not_found"}
        if row["version_type"] == "original":
            if owns_connection:
                connection.commit()
            return {"deleted": False, "reason": "original"}
        if row["is_current"]:
            if owns_connection:
                connection.commit()
            return {"deleted": False, "reason": "current"}
        connection.execute(
            "DELETE FROM resume_versions WHERE resume_filename = ? AND version_id = ?",
            (safe_filename, safe_version_id),
        )
        if owns_connection:
            connection.commit()
        return {"deleted": True, "version_id": safe_version_id}
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def activate_resume_version(
    resume_filename: str,
    version_id: str,
    db_path: str | None = None,
    *,
    connection=None,
) -> dict:
    """将指定历史快照设为当前版本；调用方可把它放进更大的事务。"""
    safe_filename = _safe_resume_filename(resume_filename)
    safe_version_id = _safe_version_id(version_id)
    owns_connection = connection is None
    if owns_connection:
        from modules.db_client import get_connection

        connection = get_connection(db_path)
    try:
        migrate_embedded_resume_versions(connection)
        row = connection.execute(
            """
            SELECT * FROM resume_versions
            WHERE resume_filename = ? AND version_id = ?
            """,
            (safe_filename, safe_version_id),
        ).fetchone()
        if row is None:
            if owns_connection:
                connection.commit()
            return {"activated": False, "reason": "not_found"}

        connection.execute(
            "UPDATE resume_versions SET is_current = 0 WHERE resume_filename = ?",
            (safe_filename,),
        )
        connection.execute(
            """
            UPDATE resume_versions SET is_current = 1
            WHERE resume_filename = ? AND version_id = ?
            """,
            (safe_filename, safe_version_id),
        )
        if owns_connection:
            connection.commit()
        return {"activated": True, "version": _row_to_version(row, True)}
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()
