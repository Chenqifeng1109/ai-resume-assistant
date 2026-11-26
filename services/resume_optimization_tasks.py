"""AI简历优化的可恢复任务流程。"""

from modules.resume_optimization_tasks import (
    create_task,
    get_task,
    latest_task,
    reset_task,
    update_task,
)
from services.resume_optimization import optimize_resume


def start_optimization_task(
    resume_file: str,
    target: str,
    extra: str = "",
    job_description: str = "",
    db_path: str | None = None,
    intensity: str = "mild",
) -> dict:
    return create_task(
        {
            "resume_file": resume_file,
            "target": target,
            "extra": extra,
            "job_description": job_description,
            "intensity": intensity,
        },
        db_path,
    )


def run_optimization_task(task_id: str, db_path: str | None = None) -> None:
    task = get_task(task_id, db_path)
    if task is None:
        return

    request_data = task["request_data"]

    def record_progress(stage, progress, **details):
        update_task(
            task_id,
            db_path,
            status="running",
            stage=stage,
            progress=progress,
            attempts=details.get("attempts", task.get("attempts", 0)),
        )

    def record_raw_response(raw_response):
        update_task(
            task_id,
            db_path,
            raw_response=raw_response,
        )

    update_task(
        task_id,
        db_path,
        status="running",
        stage="validating_input",
        progress=5,
        error_code=None,
        error_message=None,
    )
    try:
        result = optimize_resume(
            request_data.get("resume_file", ""),
            request_data.get("target", ""),
            request_data.get("extra", ""),
            request_data.get("job_description", ""),
            intensity=request_data.get("intensity", "mild"),
            progress_callback=record_progress,
            raw_response_callback=record_raw_response,
        )
    except Exception:
        update_task(
            task_id,
            db_path,
            status="failed",
            error_code="INTERNAL_ERROR",
            error_message="服务器处理任务时发生异常",
        )
        return

    if result.get("ok"):
        update_task(
            task_id,
            db_path,
            status="completed",
            stage="completed",
            progress=100,
            result_data=result,
            attempts=result.get("attempts", 1),
        )
        return

    latest_state = get_task(task_id, db_path) or task
    update_task(
        task_id,
        db_path,
        status="failed",
        progress=min(latest_state.get("progress", 0), 95),
        result_data=result,
        error_code=result.get("failure_code") or result.get("error_code") or "INTERNAL_ERROR",
        error_message=result.get("error", "任务执行失败"),
        attempts=result.get("attempts", 0),
    )


def retry_optimization_task(task_id: str, db_path: str | None = None) -> dict | None:
    task = get_task(task_id, db_path)
    if task is None or task["status"] != "failed":
        return None
    return reset_task(task_id, db_path)


def optimization_task(task_id: str, db_path: str | None = None) -> dict | None:
    return get_task(task_id, db_path)


def latest_optimization_task(db_path: str | None = None) -> dict | None:
    return latest_task(db_path)
