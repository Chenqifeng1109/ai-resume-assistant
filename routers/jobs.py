from fastapi import APIRouter, Form, Request, HTTPException
from pydantic import BaseModel, Field, StrictBool
from urllib.parse import urlsplit
from fastapi.concurrency import run_in_threadpool

from core.api_responses import UnifiedAPIRoute
from modules.job_repository import (
    aggregate_job_tracking_board,
    list_job_batches,
    load_job_batch,
    update_job_tracking,
)
from modules.job_query_planner import suggest_related_queries
from modules.job_sources import build_official_search_handoff, list_source_capabilities
from services.job_session_management import get_session_status, clear_session
from services.job_login import login_manager
from services.job_collection import (
    cancel_scrape as cancel_scrape_service,
    get_scrape_status as get_scrape_status_service,
    parse_wechat_recruitment_post,
    start_scrape as start_scrape_service,
)
from services.job_intent import (
    JobIntentConfirmRequest,
    JobIntentExtractRequest,
    JobIntentResponse,
    confirm_job_intent as confirm_job_intent_service,
    extract_job_intent as extract_job_intent_service,
)


router = APIRouter(
    prefix="/api/jobs",
    tags=["jobs"],
    route_class=UnifiedAPIRoute,
)


@router.post(
    "/intent/extract",
    response_model=JobIntentResponse,
    response_model_exclude_none=True,
)
async def extract_job_intent(request: JobIntentExtractRequest):
    """把自然语言求职意向整理成待确认字段。"""
    return await run_in_threadpool(
        extract_job_intent_service,
        request.intent_text,
    )


@router.post(
    "/intent/confirm",
    response_model=JobIntentResponse,
    response_model_exclude_none=True,
)
async def confirm_job_intent(request: JobIntentConfirmRequest):
    """校验用户修改后的岗位采集条件并标记为已确认。"""
    return confirm_job_intent_service(request)


@router.post("/scrape")
async def start_scrape(
    platforms: str = Form("51job"),
    resume_file: str = Form(""),
    salary_range: str = Form(""),
    target_position: str = Form(""),
    target_city: str = Form(""),
    restrictions: str = Form(""),
    related_keywords: str = Form(""),
):
    """接收岗位采集请求，并交给采集 Service 后台执行。"""
    return await start_scrape_service(
        platforms,
        resume_file,
        salary_range,
        target_position,
        target_city,
        restrictions,
        related_keywords,
    )


@router.get("/scrape/status")
async def get_scrape_status(task_id: str = ""):
    """返回当前岗位采集任务的共享状态。"""
    return await get_scrape_status_service(task_id)


class CancelScrapeRequest(BaseModel):
    confirmed: StrictBool


@router.post("/scrape/{task_id}/cancel")
async def cancel_scrape(task_id: str, request: CancelScrapeRequest):
    """请求采集器在下一个安全检查点停止。"""
    return await cancel_scrape_service(task_id, request.confirmed)


class JobQueryPreviewRequest(BaseModel):
    position: str = Field(min_length=2, max_length=100)
    jd_text: str = Field(default="", max_length=5000)
    max_related: int = Field(default=4, ge=0, le=4)


@router.post("/queries/preview")
async def preview_related_queries(request: JobQueryPreviewRequest):
    """只生成候选关联词，不会自动启动岗位采集。"""
    return {
        "ok": True,
        **suggest_related_queries(
            request.position,
            request.jd_text,
            request.max_related,
        ),
    }


class WechatPostParseRequest(BaseModel):
    text: str = Field(min_length=20, max_length=15000)
    article_url: str = Field(default="", max_length=1000)
    resume_file: str = Field(default="", max_length=260)


@router.post("/wechat/parse")
async def parse_wechat_post(request: WechatPostParseRequest):
    """将微信公众号官方招聘推文通过 AI 拆解为结构化岗位批次并入库。"""
    result = await run_in_threadpool(
        parse_wechat_recruitment_post,
        request.text,
        request.article_url,
        request.resume_file,
    )
    if not result.get("ok"):
        raise HTTPException(400 if result.get("error_code") == "INVALID_INPUT" else 502, result.get("error", "解析失败"))
    return result


@router.get("/sources")
async def get_job_sources():
    return {"ok": True, "sources": list_source_capabilities()}


class OfficialSearchHandoffRequest(BaseModel):
    source: str = Field(min_length=2, max_length=20)
    position: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=1, max_length=30)


@router.post("/sources/search-handoff")
async def create_official_search_handoff(request: OfficialSearchHandoffRequest):
    """Create an official-site handoff without automated scraping or session access."""
    try:
        return {"ok": True, **build_official_search_handoff(
            request.source.strip().lower(), request.position, request.city,
        )}
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


class ClearSessionRequest(BaseModel):
    confirmed: StrictBool


class LoginActionRequest(BaseModel):
    task_id: str
    action: str


def _require_local_session_request(request):
    if not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "会话管理仅允许本机访问")
    if request.url.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        raise HTTPException(403, "会话管理不支持此主机")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.url.netloc:
        raise HTTPException(403, "禁止跨站操作会话")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "禁止跨站操作会话")


@router.get("/sources/{source}/session")
async def read_job_session(source: str, request: Request):
    _require_local_session_request(request)
    return await run_in_threadpool(get_session_status, source)


@router.post("/sources/{source}/session/clear")
async def clear_job_session(source: str, body: ClearSessionRequest, request: Request):
    _require_local_session_request(request)
    # Keep the running check and unlink in this loop turn; start_scrape uses the same loop.
    return clear_session(source, body.confirmed)


@router.post("/sources/{source}/session/login")
async def start_job_login(source: str, request: Request):
    _require_local_session_request(request)
    return login_manager.start(source)


@router.post("/sources/{source}/session/check")
async def check_job_login(source: str, request: Request):
    _require_local_session_request(request)
    return login_manager.start(source, check_only=True)


@router.post("/sources/{source}/session/action")
async def act_job_login(source: str, body: LoginActionRequest, request: Request):
    _require_local_session_request(request)
    task = login_manager.snapshot(source)
    if not task or task["task_id"] != body.task_id:
        raise HTTPException(404, "登录任务不存在")
    return login_manager.action(body.task_id, body.action)


@router.get("/list")
async def list_collected_jobs():
    """按采集批次列出 SQLite 中的岗位历史。"""
    try:
        files = []
        for batch in list_job_batches():
            keywords_text = ",".join(str(item) for item in batch["keywords"])
            files.append(
                {
                    "filename": batch["batch_id"],
                    "collected_at": batch["collected_at"],
                    "count": batch["job_count"],
                    "keywords": [keywords_text]
                    if keywords_text
                    else ["未命名采集"],
                    "profile_name": "",
                }
            )
        return {"files": files, "count": len(files)}
    except Exception as error:
        return {"files": [], "count": 0, "error": str(error)}


@router.get("/detail/{filename}")
async def get_job_detail(filename: str):
    """读取某一采集批次中的完整岗位数据。"""
    try:
        data = load_job_batch(filename)
        if data is None:
            return {"ok": False, "error": "批次不存在或无数据"}
        return {"ok": True, "data": data}
    except Exception as error:
        return {"ok": False, "error": str(error)}


class JobTrackRequest(BaseModel):
    batch_id: str = Field(min_length=6, max_length=260)
    job_id: str = Field(default="", max_length=200)
    job_index: int = Field(default=-1, ge=-1, le=5000)
    status: str = Field(default="unsent", max_length=30)
    note: str = Field(default="", max_length=1000)


@router.post("/track")
async def track_job_status(request: JobTrackRequest):
    """持久化更新单个岗位的投递状态与面试备注。"""
    return await run_in_threadpool(
        update_job_tracking,
        request.batch_id,
        job_id=request.job_id,
        job_index=request.job_index,
        status=request.status,
        note=request.note,
    )


@router.get("/tracking-board")
async def get_job_tracking_board():
    """跨批次汇总求职投递漏斗统计与跟进清单。"""
    return await run_in_threadpool(aggregate_job_tracking_board)
