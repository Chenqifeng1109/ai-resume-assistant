import contextvars

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from core.api_responses import UnifiedAPIRoute
from services.resume_documents import (
    export_optimized_resume as export_optimized_resume_service,
    export_resume as export_resume_service,
    overwrite_resume as overwrite_resume_service,
    resume_template as resume_template_service,
    upload_photo as upload_photo_service,
)
from services.resume_optimization import optimize_resume as optimize_resume_service
from services.resume_optimization_tasks import (
    latest_optimization_task,
    optimization_task,
    retry_optimization_task,
    run_optimization_task,
    start_optimization_task,
)
from services.resume_precision import (
    precision_optimize as precision_optimize_service,
    precision_recheck as precision_recheck_service,
)
from services.interview_prep import generate_interview_prep as generate_interview_prep_service


router = APIRouter(
    prefix="/api/resume",
    tags=["resume-actions"],
    route_class=UnifiedAPIRoute,
)


@router.post("/optimize")
async def optimize_resume(
    resume_file: str = Form(""),
    target: str = Form(""),
    extra: str = Form(""),
    job_description: str = Form(""),
    intensity: str = Form("balanced"),
):
    """接收优化请求，并在线程池中运行同步 AI 业务。"""
    return await run_in_threadpool(
        optimize_resume_service,
        resume_file,
        target,
        extra,
        job_description,
        None,
        None,
        1.0,
        intensity,
    )


@router.post("/optimize/tasks", status_code=202)
async def create_optimization_task(
    background_tasks: BackgroundTasks,
    resume_file: str = Form(""),
    target: str = Form(""),
    extra: str = Form(""),
    job_description: str = Form(""),
    intensity: str = Form("balanced"),
):
    """创建可恢复的AI优化任务，随后在后台线程中执行。"""
    task = start_optimization_task(
        resume_file,
        target,
        extra,
        job_description,
        intensity=intensity,
    )
    ctx = contextvars.copy_context()
    background_tasks.add_task(ctx.run, run_optimization_task, task["task_id"])
    return task


@router.get("/optimize/tasks/latest")
async def get_latest_optimization_task():
    """返回最近一次任务，用于刷新页面后恢复状态。"""
    task = latest_optimization_task()
    if task is None:
        return {"ok": True, "task": None}
    return task


@router.get("/optimize/tasks/{task_id}")
async def get_optimization_task(task_id: str):
    """查询优化任务的当前阶段。"""
    task = optimization_task(task_id)
    if task is None:
        return {
            "ok": False,
            "error": "优化任务不存在",
            "error_code": "NOT_FOUND",
        }
    return task


@router.post("/optimize/tasks/{task_id}/retry", status_code=202)
async def retry_failed_optimization_task(
    task_id: str,
    background_tasks: BackgroundTasks,
):
    """仅允许对已失败任务重新执行。"""
    task = retry_optimization_task(task_id)
    if task is None:
        return {
            "ok": False,
            "error": "只能重试已失败的优化任务",
            "error_code": "CONFLICT",
        }
    ctx = contextvars.copy_context()
    background_tasks.add_task(ctx.run, run_optimization_task, task_id)
    return task


@router.post("/overwrite")
async def overwrite_resume(
    resume_file: str = Form(""),
    optimized_summary: str = Form(""),
    optimized_projects: str = Form("[]"),
    optimized_internships: str = Form("[]"),
    enhanced_skills: str = Form("[]"),
    target: str = Form(""),
    optimized_resume: str = Form("{}"),
):
    """接收覆盖请求，把文件读写业务交给 Service。"""
    return await run_in_threadpool(
        overwrite_resume_service,
        resume_file,
        optimized_summary,
        optimized_projects,
        optimized_internships,
        enhanced_skills,
        target,
        optimized_resume,
    )


@router.post("/template")
async def resume_template(
    resume_file: str = Form(""),
    template_style: str = Form("classic"),
):
    """接收模板请求，把 HTML 生成业务交给 Service。"""
    return await run_in_threadpool(
        resume_template_service,
        resume_file,
        template_style,
    )


@router.post("/photo")
async def upload_photo(
    resume_file: str = Form(""),
    photo: UploadFile = File(None),
):
    """接收照片上传请求，把文件保存业务交给 Service。"""
    return await upload_photo_service(resume_file, photo)


@router.get("/export/{filename}")
async def export_resume(filename: str):
    """接收导出请求，把 HTML 生成业务交给 Service。"""
    return await run_in_threadpool(export_resume_service, filename)


@router.post("/export-optimized")
async def export_optimized_resume(
    resume_file: str = Form(""),
    optimized_resume: str = Form("{}"),
):
    """导出当前AI优化结果，不覆盖保存的原简历。"""
    return await run_in_threadpool(
        export_optimized_resume_service,
        resume_file,
        optimized_resume,
    )


@router.post("/precision-optimize")
async def precision_optimize(
    resume_file: str = Form(""),
    jobs_file: str = Form(""),
    job_indices: str = Form(""),
    custom_jd: str = Form(""),
    custom_target: str = Form(""),
    intensity: str = Form("balanced"),
):
    """接收精准优化请求，支持从已采集岗位选择或直接粘贴任意岗位 JD 定向优化。"""
    return await run_in_threadpool(
        precision_optimize_service,
        resume_file,
        jobs_file,
        job_indices,
        None,
        None,
        custom_jd,
        custom_target,
        intensity,
    )


@router.post("/precision-recheck")
async def precision_recheck(
    resume_file: str = Form(""),
    jobs_file: str = Form(""),
    job_indices: str = Form(""),
    before_scores: str = Form("{}"),
):
    """覆盖简历后，用最新简历重新检测与所选目标 JD 的匹配度与关联性变化。"""
    return await run_in_threadpool(
        precision_recheck_service,
        resume_file,
        jobs_file,
        job_indices,
        before_scores,
    )


@router.post("/interview-prep")
async def generate_interview_prep(
    resume_file: str = Form(""),
    jd_text: str = Form(""),
    jobs_file: str = Form(""),
    job_index: int = Form(-1),
    target_position: str = Form(""),
    restrictions: str = Form(""),
    avoid_questions: str = Form("[]"),
    temperature: float = Form(0.72),
    question_count: int = Form(5),
):
    """针对当前简历与目标 JD 一键生成 AI 模拟面试追问与 STAR 参考答法（支持换一批题库与自定义温度/题数）。"""
    return await run_in_threadpool(
        generate_interview_prep_service,
        resume_file,
        jd_text,
        jobs_file,
        job_index,
        target_position,
        restrictions,
        None,
        avoid_questions,
        temperature,
        question_count,
    )


def _export_pdf_direct_sync(resume_file: str, template_style: str, open_folder: bool) -> dict:
    import os
    import re
    import shutil
    import subprocess
    import tempfile
    from datetime import datetime
    from pathlib import Path
    from config import RESUMES_DIR

    rendered = resume_template_service(resume_file, template_style)
    html_content = ""
    if isinstance(rendered, dict):
        if not rendered.get("ok"):
            return rendered
        html_content = str(rendered.get("html") or "")
    elif hasattr(rendered, "body"):
        status = int(getattr(rendered, "status_code", 200) or 200)
        body_bytes = rendered.body if isinstance(rendered.body, (bytes, bytearray)) else str(rendered.body or "").encode("utf-8")
        decoded = body_bytes.decode("utf-8", errors="replace")
        if status >= 400:
            return {"ok": False, "error": decoded[:200] or "模板渲染失败"}
        html_content = decoded
    elif isinstance(rendered, str):
        html_content = rendered
    if not html_content.strip():
        return {"ok": False, "error": "模板渲染内容为空，请先选择有效简历"}

    browser_candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("LocalAppData", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        shutil.which("msedge"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
        shutil.which("chrome"),
    ]
    browser_exe = next((p for p in browser_candidates if p and os.path.isfile(p)), None)
    if not browser_exe:
        return {"ok": False, "error": "未找到本机 Edge/Chrome 渲染引擎，请使用右侧「下载 HTML」或打印另存为 PDF"}

    exports_dir = Path(RESUMES_DIR) / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(resume_file or "resume").stem
    safe_stem = re.sub(r'[\\/:*?"<>|\s]+', "_", stem)[:48] or "resume"
    safe_style = re.sub(r"[^a-zA-Z0-9_-]+", "", template_style or "classic") or "classic"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_pdf = exports_dir / f"{safe_stem}_{safe_style}_{stamp}.pdf"

    with tempfile.TemporaryDirectory(prefix="offerforge_pdf_") as tmp:
        html_file = Path(tmp) / "resume.html"
        profile_dir = Path(tmp) / "edge_pdf_profile"
        html_file.write_text(html_content, encoding="utf-8")
        cmd = [
            browser_exe,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile_dir}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out_pdf}",
            html_file.as_uri(),
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, creationflags=flags)
        if proc.returncode != 0 or not out_pdf.exists() or out_pdf.stat().st_size == 0:
            return {"ok": False, "error": "高清 PDF 直出失败，请改用「导出 PDF / 打印」"}

    if open_folder and os.name == "nt":
        try:
            subprocess.Popen(["explorer.exe", f"/select,{out_pdf}"])
        except OSError:
            pass

    return {
        "ok": True,
        "filename": out_pdf.name,
        "path": str(out_pdf),
        "size_kb": round(out_pdf.stat().st_size / 1024, 1),
    }


@router.post("/export-pdf")
async def export_resume_pdf(
    resume_file: str = Form(""),
    template_style: str = Form("classic"),
    open_folder: bool = Form(True),
):
    """PC 桌面端专属：一键静默直出高清 A4 PDF 到本地 exports 目录并定位文件。"""
    return await run_in_threadpool(_export_pdf_direct_sync, resume_file, template_style, open_folder)
