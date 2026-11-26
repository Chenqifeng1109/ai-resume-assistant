"""简历版本查询与删除业务。"""

import json
import os
import uuid

from config import DATA_DIR
from core.workspace_context import get_active_data_dir
from core.file_security import resolve_file_in_directory
from core.runtime_state import add_log
from modules.db_client import get_connection
from modules.resume_version_repository import (
    activate_resume_version,
    delete_resume_version,
    get_resume_version,
    list_resume_versions,
)


def list_versions(resume_filename: str) -> dict:
    try:
        versions = list_resume_versions(resume_filename)
    except ValueError as error:
        return {"ok": False, "error": str(error), "error_code": "INVALID_INPUT"}
    if not versions:
        return {
            "ok": False,
            "error": "简历或版本记录不存在",
            "error_code": "NOT_FOUND",
        }
    return {"ok": True, "versions": versions, "count": len(versions)}


def version_detail(resume_filename: str, version_id: str) -> dict:
    try:
        version = get_resume_version(resume_filename, version_id)
    except ValueError as error:
        return {"ok": False, "error": str(error), "error_code": "INVALID_INPUT"}
    if version is None:
        return {
            "ok": False,
            "error": "简历版本不存在",
            "error_code": "NOT_FOUND",
        }
    return {"ok": True, "version": version}


def current_version(resume_filename: str) -> dict:
    try:
        version = get_resume_version(resume_filename, current=True)
    except ValueError as error:
        return {"ok": False, "error": str(error), "error_code": "INVALID_INPUT"}
    if version is None:
        return {
            "ok": False,
            "error": "当前简历版本不存在",
            "error_code": "NOT_FOUND",
        }
    return {"ok": True, "version": version}


def activate_version(resume_filename: str, version_id: str) -> dict:
    """用户确认后切换当前版本，并同步 SQLite 与兼容 JSON 文件。"""
    connection = get_connection()
    original_file_content = None
    resume_path = ""
    temp_path = ""
    file_replaced = False
    try:
        connection.execute("BEGIN")
        target_version = get_resume_version(
            resume_filename,
            version_id,
            connection=connection,
        )
        if target_version is None:
            connection.rollback()
            return {
                "ok": False,
                "error": "简历版本不存在",
                "error_code": "NOT_FOUND",
            }

        activated = activate_resume_version(
            resume_filename,
            version_id,
            connection=connection,
        )
        if not activated.get("activated"):
            connection.rollback()
            return {
                "ok": False,
                "error": "简历版本不存在",
                "error_code": "NOT_FOUND",
            }

        stored_row = connection.execute(
            "SELECT parsed_data FROM resumes WHERE filename = ?",
            (resume_filename,),
        ).fetchone()
        if stored_row is None:
            connection.rollback()
            return {
                "ok": False,
                "error": "简历不存在",
                "error_code": "NOT_FOUND",
            }

        stored_profile = json.loads(stored_row["parsed_data"])
        profile = dict(target_version["content"])
        history = stored_profile.get("optimization_history", [])
        if isinstance(history, list):
            profile["optimization_history"] = history
        original_profile = stored_profile.get("original_profile")
        if isinstance(original_profile, dict):
            profile["original_profile"] = original_profile
        if target_version["version_type"] == "optimized":
            profile["active_optimization"] = {
                key: value
                for key, value in target_version.items()
                if key not in {"content", "id", "resume_filename", "is_current"}
            }
        else:
            profile.pop("active_optimization", None)

        serialized_profile = json.dumps(profile, ensure_ascii=False, indent=2)
        connection.execute(
            "UPDATE resumes SET parsed_data = ? WHERE filename = ?",
            (serialized_profile, resume_filename),
        )

        resolved_resume = resolve_file_in_directory(get_active_data_dir(DATA_DIR), resume_filename, {".json"})
        if resolved_resume and os.path.exists(resolved_resume[1]):
            resume_path = resolved_resume[1]
            with open(resume_path, "r", encoding="utf-8") as source:
                original_file_content = source.read()
            temp_path = f"{resume_path}.{uuid.uuid4().hex}.tmp"
            with open(temp_path, "w", encoding="utf-8") as output:
                output.write(serialized_profile)
            os.replace(temp_path, resume_path)
            file_replaced = True

        connection.commit()
        add_log(f"已切换当前简历版本: {version_id}", "success")
        return {"ok": True, "version": target_version}
    except ValueError as error:
        connection.rollback()
        return {"ok": False, "error": str(error), "error_code": "INVALID_INPUT"}
    except Exception:
        connection.rollback()
        if file_replaced and original_file_content is not None:
            restore_path = f"{resume_path}.{uuid.uuid4().hex}.restore"
            with open(restore_path, "w", encoding="utf-8") as restore:
                restore.write(original_file_content)
            os.replace(restore_path, resume_path)
        elif temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        return {
            "ok": False,
            "error": "当前简历版本切换失败，原版本未改变",
            "error_code": "INTERNAL_ERROR",
        }
    finally:
        connection.close()


def delete_version(resume_filename: str, version_id: str) -> dict:
    connection = get_connection()
    original_file_content = None
    resume_path = ""
    temp_path = ""
    file_replaced = False
    try:
        connection.execute("BEGIN")
        result = delete_resume_version(
            resume_filename,
            version_id,
            connection=connection,
        )
    except ValueError as error:
        connection.rollback()
        connection.close()
        return {"ok": False, "error": str(error), "error_code": "INVALID_INPUT"}
    except Exception:
        connection.rollback()
        connection.close()
        return {
            "ok": False,
            "error": "版本删除失败",
            "error_code": "INTERNAL_ERROR",
        }
    try:
        if result.get("reason") == "not_found":
            connection.rollback()
            return {
                "ok": False,
                "error": "简历版本不存在",
                "error_code": "NOT_FOUND",
            }
        if result.get("reason") == "original":
            connection.rollback()
            return {
                "ok": False,
                "error": "原始底稿不能删除",
                "error_code": "CONFLICT",
            }
        if result.get("reason") == "current":
            connection.rollback()
            return {
                "ok": False,
                "error": "当前版本不能删除，请先保存新的优化版本",
                "error_code": "CONFLICT",
            }

        row = connection.execute(
            "SELECT parsed_data FROM resumes WHERE filename = ?",
            (resume_filename,),
        ).fetchone()
        if row is not None:
            profile = json.loads(row["parsed_data"])
            history = profile.get("optimization_history", [])
            if isinstance(history, list):
                profile["optimization_history"] = [
                    item
                    for item in history
                    if not isinstance(item, dict)
                    or str(item.get("version_id", "")) != version_id
                ]
            serialized_profile = json.dumps(profile, ensure_ascii=False, indent=2)
            connection.execute(
                "UPDATE resumes SET parsed_data = ? WHERE filename = ?",
                (serialized_profile, resume_filename),
            )

            resolved_resume = resolve_file_in_directory(
                get_active_data_dir(DATA_DIR),
                resume_filename,
                {".json"},
            )
            if resolved_resume and os.path.exists(resolved_resume[1]):
                resume_path = resolved_resume[1]
                with open(resume_path, "r", encoding="utf-8") as source:
                    original_file_content = source.read()
                temp_path = f"{resume_path}.{uuid.uuid4().hex}.tmp"
                with open(temp_path, "w", encoding="utf-8") as output:
                    output.write(serialized_profile)
                os.replace(temp_path, resume_path)
                file_replaced = True

        connection.commit()
        add_log(f"已删除简历历史版本: {version_id}", "info")
        return {"ok": True, "deleted_version_id": version_id}
    except Exception:
        connection.rollback()
        if file_replaced and original_file_content is not None:
            restore_path = f"{resume_path}.{uuid.uuid4().hex}.restore"
            with open(restore_path, "w", encoding="utf-8") as restore:
                restore.write(original_file_content)
            os.replace(restore_path, resume_path)
        elif temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        return {
            "ok": False,
            "error": "版本删除失败",
            "error_code": "INTERNAL_ERROR",
        }
    finally:
        connection.close()
