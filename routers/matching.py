from fastapi import APIRouter, Form
from starlette.concurrency import run_in_threadpool

from core.api_responses import UnifiedAPIRoute
from services.job_matching import (
    batch_match_jd as batch_match_jd_service,
    batch_score_jobs as batch_score_jobs_service,
    batch_score_jobs_json as batch_score_jobs_json_service,
    match_jd as match_jd_service,
)


router = APIRouter(tags=["matching"], route_class=UnifiedAPIRoute)


@router.post("/api/jd/match")
async def match_jd(
    resume_file: str = Form(""),
    jd_text: str = Form(""),
    restrictions: str = Form(""),
):
    """接收单条JD匹配请求，并在线程池中执行评分与限制条件避坑核查。"""
    return await run_in_threadpool(match_jd_service, resume_file, jd_text, restrictions)


@router.post("/api/jobs/batch-score")
async def batch_score_jobs(
    jobs_file: str = Form(""),
    resume_file: str = Form(""),
    threshold: int = Form(70),
):
    """接收岗位批量评分表单，并在线程池中执行评分。"""
    return await run_in_threadpool(
        batch_score_jobs_service,
        jobs_file,
        resume_file,
        threshold,
    )


@router.post("/api/jobs/batch-score-json")
async def batch_score_jobs_json(data: dict):
    """接收JSON格式的岗位批量评分请求。"""
    return await run_in_threadpool(batch_score_jobs_json_service, data)


@router.post("/api/jd/batch-match")
async def batch_match_jd(
    resume_file: str = Form(""),
    jd_text: str = Form(""),
):
    """接收快速JD匹配请求，并在线程池中执行评分。"""
    return await run_in_threadpool(batch_match_jd_service, resume_file, jd_text)
