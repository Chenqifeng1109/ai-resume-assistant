from fastapi import APIRouter, Form
from starlette.concurrency import run_in_threadpool

from core.api_responses import UnifiedAPIRoute
from services.delivery_service import (
    api_update_deliver_status as update_deliver_status_service,
    generate_greeting as generate_greeting_service,
    get_deliver_history as get_deliver_history_service,
    get_deliver_status as get_deliver_status_service,
    list_deliver_candidates as list_deliver_candidates_service,
    mark_delivered as mark_delivered_service,
    undo_deliver as undo_deliver_service,
)


router = APIRouter(
    prefix="/api/deliver",
    tags=["deliveries"],
    route_class=UnifiedAPIRoute,
)


@router.get("/status")
async def get_deliver_status():
    return await run_in_threadpool(get_deliver_status_service)


@router.get("/history")
async def get_deliver_history():
    return await run_in_threadpool(get_deliver_history_service)


@router.post("/greeting")
async def generate_greeting(
    resume_file: str = Form(""),
    direction: str = Form(""),
    jobs_file: str = Form(""),
    scene: str = Form("greeting"),
    tone: str = Form("professional"),
    target_job: str = Form(""),
):
    return await run_in_threadpool(
        generate_greeting_service,
        resume_file,
        direction,
        jobs_file,
        scene,
        tone,
        target_job,
    )


@router.post("/list")
async def list_deliver_candidates(
    jobs_file: str = Form(""),
    resume_file: str = Form(""),
    threshold: int = Form(70),
):
    return await run_in_threadpool(
        list_deliver_candidates_service,
        jobs_file,
        resume_file,
        threshold,
    )


@router.post("/mark")
async def mark_delivered(
    url: str = Form(""),
    title: str = Form(""),
    company: str = Form(""),
    salary: str = Form(""),
    score: int = Form(0),
    notes: str = Form(""),
):
    return await run_in_threadpool(
        mark_delivered_service,
        url,
        title,
        company,
        salary,
        score,
        notes,
    )


@router.post("/undo")
async def undo_deliver(url: str = Form("")):
    return await run_in_threadpool(undo_deliver_service, url)


@router.post("/update_status")
async def update_deliver_status(
    delivery_id: int = Form(...),
    status: str = Form(...),
):
    return await run_in_threadpool(
        update_deliver_status_service,
        delivery_id,
        status,
    )
