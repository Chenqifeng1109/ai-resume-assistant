import json
import os
import threading

from typing import Any

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from config import DATA_DIR, RESUMES_DIR
from core.api_responses import UnifiedAPIRoute
from core.file_security import resolve_file_in_directory, validate_filename
from core.runtime_state import add_log
from core.workspace_context import get_active_data_dir, get_active_resumes_dir
from modules.db_client import get_connection
from modules.resume_parser import list_resumes, parse_resume, save_parsed_result
from services.resume_documents import update_resume_manual as update_resume_manual_service
from services.resume_versions import (
    activate_version as activate_version_service,
    current_version as current_version_service,
    delete_version as delete_version_service,
    list_versions as list_versions_service,
    version_detail as version_detail_service,
)


router = APIRouter(
    prefix="/api/resumes",
    tags=["resumes"],
    route_class=UnifiedAPIRoute,
)
ALLOWED_RESUME_EXTENSIONS = {".docx", ".pdf", ".txt"}
MAX_RESUME_SIZE = 10 * 1024 * 1024
# Serialize upload transactions so replacing a same-name source cannot race.
_UPLOAD_LOCK = threading.Lock()


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """上传简历文件，解析后写入 SQLite 和兼容 JSON 文件。"""
    original_filename = file.filename or ""
    safe_filename = validate_filename(original_filename)
    if safe_filename is None:
        await file.close()
        return {"ok": False, "error": "文件名不安全"}

    extension = os.path.splitext(safe_filename)[1].lower()
    if extension not in ALLOWED_RESUME_EXTENSIONS:
        await file.close()
        return {"ok": False, "error": "仅支持 DOCX、PDF 和 TXT 简历"}

    try:
        content = await file.read(MAX_RESUME_SIZE + 1)
    finally:
        await file.close()
    if not content:
        return {"ok": False, "error": "上传文件为空"}
    if len(content) > MAX_RESUME_SIZE:
        return {"ok": False, "error": "简历文件不能超过 10MB"}

    add_log(f"收到简历文件: {safe_filename}", "info")
    response = await run_in_threadpool(_process_upload, safe_filename, content)
    if response.get("ok"):
        add_log(f"简历解析成功: {response['data'].get('name', '未知')}", "success")
    else:
        add_log(f"简历处理失败: {response.get('error', '未知错误')}", "error")
    return response


def _process_upload(safe_filename: str, content: bytes):
    with _UPLOAD_LOCK:
        return _store_upload(safe_filename, content)


def _store_upload(safe_filename: str, content: bytes):
    """Run source-file writes, parsing and persistence off the event loop."""
    active_resumes_dir = get_active_resumes_dir(RESUMES_DIR)
    os.makedirs(active_resumes_dir, exist_ok=True)
    resolved_upload = resolve_file_in_directory(
        active_resumes_dir,
        safe_filename,
        ALLOWED_RESUME_EXTENSIONS,
    )
    if resolved_upload is None:
        return {"ok": False, "error": "文件名不安全"}

    _, file_path = resolved_upload
    previous_upload_content = None
    if os.path.exists(file_path):
        with open(file_path, "rb") as previous_upload:
            previous_upload_content = previous_upload.read()
    with open(file_path, "wb") as uploaded_file:
        uploaded_file.write(content)

    def restore_uploaded_file():
        if previous_upload_content is None:
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        with open(file_path, "wb") as previous_upload:
            previous_upload.write(previous_upload_content)

    try:
        result = parse_resume(file_path)
    except Exception:
        try:
            restore_uploaded_file()
        except OSError:
            pass
        return {
            "ok": False,
            "error": "简历解析服务异常，请稍后重试",
            "error_code": "INTERNAL_ERROR",
        }
    if "error" in result:
        try:
            restore_uploaded_file()
        except OSError:
            pass
        error_code = result.get("error_code", "RESUME_PARSE_FAILED")
        response = {
            "ok": False,
            "error": result["error"],
            "error_code": error_code,
        }
        if result.get("validation_errors"):
            response["details"] = result["validation_errors"]
        return response

    try:
        json_path = save_parsed_result(result)
    except Exception:
        try:
            restore_uploaded_file()
        except OSError:
            pass
        return {
            "ok": False,
            "error": "简历保存失败，请稍后重试",
            "error_code": "INTERNAL_ERROR",
        }
    return {"ok": True, "data": result, "saved_to": json_path}


@router.get("/files")
async def get_resume_files():
    """列出原始简历文件夹中的文件。"""
    files = list_resumes()
    return {"files": files, "count": len(files)}


@router.get("/list")
async def list_parsed_resumes():
    """从 SQLite 数据库获取所有已解析简历。"""
    resumes = []
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM resumes ORDER BY created_at DESC")
        rows = cursor.fetchall()
        for row in rows:
            data = json.loads(row["parsed_data"])
            resumes.append(
                {
                    "filename": row["filename"],
                    "name": data.get("name", "未知"),
                    "position": data.get("desired_position", ""),
                    "desired_salary": data.get("desired_salary", ""),
                    "skills": data.get("skills", [])[:5],
                    "parsed_at": data.get("parsed_at", ""),
                    "summary": data.get("summary", "")[:80],
                }
            )
        connection.close()
    except Exception as error:
        print(f"读取数据库失败: {error}")
    return {"resumes": resumes, "count": len(resumes)}


@router.get("/detail/{filename}")
async def get_resume_detail(filename: str):
    """从 SQLite 数据库获取某份简历的完整信息。"""
    safe_filename = validate_filename(filename, {".json"})
    if safe_filename is None:
        return {"ok": False, "error": "文件名不安全"}
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT parsed_data FROM resumes WHERE filename = ?", (safe_filename,)
        )
        row = cursor.fetchone()
        connection.close()
        if row:
            return {"ok": True, "data": json.loads(row["parsed_data"])}
        return {"ok": False, "error": "简历在数据库中不存在"}
    except Exception as error:
        return {"ok": False, "error": str(error)}


@router.get("/latest")
async def get_latest_resume():
    """从 SQLite 数据库获取最新的一份简历。"""
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT filename, parsed_data FROM resumes ORDER BY created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        connection.close()
        if row:
            return {
                "ok": True,
                "data": json.loads(row["parsed_data"]),
                "filename": row["filename"],
            }
        return {"ok": False, "error": "数据库中没有简历"}
    except Exception as error:
        return {"ok": False, "error": str(error)}


@router.get("/versions/{filename}")
async def get_resume_versions(filename: str):
    """列出一份简历的版本元数据，不返回大段简历正文。"""
    return await run_in_threadpool(list_versions_service, filename)


@router.get("/versions/{filename}/current")
async def get_current_resume_version(filename: str):
    """读取当前版本及其完整简历快照。"""
    return await run_in_threadpool(current_version_service, filename)


@router.post("/versions/{filename}/{version_id}/activate")
async def activate_resume_version(filename: str, version_id: str):
    """用户确认后，将指定历史版本设为当前简历。"""
    return await run_in_threadpool(
        activate_version_service,
        filename,
        version_id,
    )


@router.get("/versions/{filename}/{version_id}")
async def get_resume_version(filename: str, version_id: str):
    """按版本编号读取完整简历快照。"""
    return await run_in_threadpool(
        version_detail_service,
        filename,
        version_id,
    )


@router.delete("/versions/{filename}/{version_id}")
async def delete_resume_version(filename: str, version_id: str):
    """只允许删除非当前的AI优化历史版本。"""
    return await run_in_threadpool(
        delete_version_service,
        filename,
        version_id,
    )


@router.delete("/delete/{filename}")
async def delete_resume(filename: str):
    """删除 SQLite 记录及其关联的兼容文件。"""
    safe_filename = validate_filename(filename, {".json"})
    if safe_filename is None:
        return {"ok": False, "error": "文件名不安全"}

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT parsed_data FROM resumes WHERE filename = ?", (safe_filename,)
        )
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "error": "简历在数据库中不存在"}

        parsed_data = json.loads(row["parsed_data"])
        source_filename = (
            validate_filename(
                parsed_data.get("source_file", ""),
                ALLOWED_RESUME_EXTENSIONS,
            )
            or ""
        )
        cursor.execute(
            "DELETE FROM resume_versions WHERE resume_filename = ?",
            (safe_filename,),
        )
        cursor.execute("DELETE FROM resumes WHERE filename = ?", (safe_filename,))
        connection.commit()

        cursor.execute("SELECT parsed_data FROM resumes")
        source_still_used = any(
            validate_filename(
                json.loads(other["parsed_data"]).get("source_file", ""),
                ALLOWED_RESUME_EXTENSIONS,
            )
            == source_filename
            for other in cursor.fetchall()
        )
    finally:
        connection.close()

    deleted_files = []
    active_data_dir = get_active_data_dir(DATA_DIR)
    active_resumes_dir = get_active_resumes_dir(RESUMES_DIR)
    resolved_json = resolve_file_in_directory(active_data_dir, safe_filename, {".json"})
    json_path = resolved_json[1] if resolved_json else ""
    if json_path and os.path.exists(json_path):
        os.remove(json_path)
        deleted_files.append(json_path)

    if source_filename and not source_still_used:
        resolved_source = resolve_file_in_directory(
            active_resumes_dir,
            source_filename,
            ALLOWED_RESUME_EXTENSIONS,
        )
        source_path = resolved_source[1] if resolved_source else ""
        if source_path and os.path.exists(source_path):
            os.remove(source_path)
            deleted_files.append(source_path)

    add_log(f"已删除简历: {safe_filename}", "info")
    return {"ok": True, "deleted_files": deleted_files}


class ResumeManualUpdateRequest(BaseModel):
    name: str | None = None
    desired_position: str | None = None
    desired_salary: str | None = None
    phone: str | None = None
    email: str | None = None
    summary: str | None = None
    skills: list[str] | None = None
    education: list[dict[str, Any]] | None = None
    work_experience: list[dict[str, Any]] | None = None
    project_experience: list[dict[str, Any]] | None = None
    practical_experience: list[dict[str, Any]] | None = None
    campus_experience: list[dict[str, Any]] | None = None
    research_experience: list[dict[str, Any]] | None = None


@router.put("/{filename}")
async def update_resume_manual(filename: str, request: ResumeManualUpdateRequest):
    """人工在线微调简历并原子写回 SQLite、版本历史表与兼容 JSON。"""
    payload = request.model_dump(exclude_none=True)
    return await run_in_threadpool(update_resume_manual_service, filename, payload)
