import ctypes
import hashlib
import io
import json
import os
import re
import time
import zipfile
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import config as app_config
from core.api_responses import UnifiedAPIRoute
from core.security_middleware import _is_direct_local_request
from core.workspace_context import get_active_data_dir


_PROVIDER_LABELS = {
    "zhipu": "智谱清言 (GLM)",
    "deepseek": "DeepSeek 官方",
    "siliconflow": "硅基流动 (SiliconFlow)",
    "gemini": "Google Gemini",
    "aliyun": "阿里百炼 (通义千问)",
    "dashscope": "阿里百炼 (通义千问)",
}


def _read_windows_clipboard_text() -> str:
    """0ms 纯本地读取 Windows 剪贴板 Unicode 文本（不启子进程、不联网）。"""
    if os.name != "nt":
        return ""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    cf_unicodetext = 13
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(cf_unicodetext)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr) or ""
        finally:
            kernel32.GlobalUnlock(handle)
    except Exception:
        return ""
    finally:
        user32.CloseClipboard()


_JD_DUTY_TERMS = ("岗位职责", "工作职责", "职位描述", "工作内容", "主要职责", "职责描述", "岗位描述")
_JD_REQ_TERMS = ("任职要求", "任职资格", "职位要求", "岗位要求", "加分项", "优先考虑", "能力要求")
_JD_META_PATTERNS = (
    re.compile(r"(本科及以上|统招本科|大专及以上|硕士及以上|博士及以上|985|211)"),
    re.compile(r"(\d+\s*[-~至]\s*\d+\s*年|\d+\s*年以上|应届生|校招|实习生)"),
    re.compile(r"(\d+(?:\.\d+)?\s*[-~]\s*\d+(?:\.\d+)?\s*[kKwW万]|\d+薪)"),
)
_CODE_NOISE_PATTERNS = (
    re.compile(r"(?m)^\s*(import |from |def |class |function |const |let |var |SELECT |CREATE TABLE )"),
    re.compile(r"https?://\S+$"),
)


def detect_clipboard_jd(raw_text: str) -> dict:
    """三层纯本地规则门禁判断剪贴板文本是否为岗位 JD（防日常复制误报）。"""
    text = str(raw_text or "").strip()
    if len(text) < 80 or len(text) > 8000:
        return {"is_jd": False}
    if text.startswith("{") and text.endswith("}"):
        return {"is_jd": False}
    if any(p.search(text) for p in _CODE_NOISE_PATTERNS):
        if sum(1 for ch in text if ch in "{};") > 12:
            return {"is_jd": False}
        if re.fullmatch(r"https?://\S+", text):
            return {"is_jd": False}

    signals = []
    if any(term in text for term in _JD_DUTY_TERMS):
        signals.append("岗位职责")
    if any(term in text for term in _JD_REQ_TERMS):
        signals.append("任职要求")
    if any(p.search(text) for p in _JD_META_PATTERNS):
        signals.append("招聘条件")

    if len(signals) < 2:
        return {"is_jd": False}

    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    preview = (first_line[:52] + ("..." if len(first_line) > 52 else "")) or text[:52]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return {
        "is_jd": True,
        "hash": digest,
        "preview": preview,
        "signals": signals,
        "text": text,
    }


def _mask_api_key(raw: str) -> str:
    val = str(raw or "").strip()
    if not val:
        return ""
    if len(val) <= 8:
        return "*" * len(val)
    return f"{val[:4]}...{val[-4:]}"


def _update_env_file_vars(env_path: str, updates: dict[str, str]) -> None:
    existing = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    text = existing
    for key, value in updates.items():
        clean_val = str(value).replace("\r", "").replace("\n", "").strip()
        pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
        if pattern.search(text):
            text = pattern.sub(f"{key}={clean_val}", text)
        else:
            sep = "" if (not text or text.endswith("\n")) else "\n"
            text = f"{text}{sep}{key}={clean_val}\n"
    with open(env_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class LlmConfigUpdateRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    model: str = Field(default="", max_length=120)
    api_key: str = Field(default="", max_length=300)


def create_system_router(
    *,
    steps: list[dict],
    stats: dict,
    data_dir: str,
    add_log: Callable[[str, str], None],
) -> APIRouter:
    """创建系统状态与流程步骤路由。"""
    router = APIRouter(tags=["system"], route_class=UnifiedAPIRoute)

    @router.get("/api/status")
    async def get_status():
        active_data_dir = get_active_data_dir(data_dir)
        parsed_count = 0
        if os.path.exists(active_data_dir):
            parsed_count = len(
                [
                    filename
                    for filename in os.listdir(active_data_dir)
                    if filename.startswith("resume_") and filename.endswith(".json")
                ]
            )

        deliveries_count = stats.get("deliveries", 0)
        history_path = os.path.join(active_data_dir, "deliver_history.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as file:
                    history = json.load(file)
                deliveries_count = len(history) if isinstance(history, dict) else 0
            except (OSError, json.JSONDecodeError):
                deliveries_count = 0
        else:
            deliveries_count = 0

        local_stats = dict(stats)
        local_stats["resumes"] = parsed_count
        local_stats["deliveries"] = deliveries_count
        return {"steps": steps, "stats": local_stats}

    @router.post("/api/steps/{step_id}/start")
    async def start_step(step_id: int):
        for step in steps:
            if step["id"] == step_id:
                step["status"] = "in_progress"
                add_log(f"开始步骤: {step['name']}", "info")
                return {"ok": True, "step": step}
        return {"ok": False, "error": "步骤不存在"}

    @router.post("/api/steps/{step_id}/complete")
    async def complete_step(step_id: int):
        for step in steps:
            if step["id"] == step_id:
                step["status"] = "done"
                add_log(f"完成步骤: {step['name']}", "success")
                return {"ok": True, "step": step}
        return {"ok": False, "error": "步骤不存在"}

    @router.get("/api/system/llm-config")
    async def read_llm_config():
        """返回当前模型引擎配置摘要（绝不回显明文 API Key）。"""
        active_provider = os.getenv("LLM_PROVIDER", app_config.LLM_PROVIDER).strip().lower()
        presets = []
        for code, meta in app_config.LLM_PROVIDER_PRESETS.items():
            key_env = meta["key_env"]
            raw_key = os.getenv(key_env, "").strip()
            presets.append(
                {
                    "code": code,
                    "label": _PROVIDER_LABELS.get(code, code),
                    "default_model": meta["model"],
                    "key_env": key_env,
                    "has_key": bool(raw_key),
                    "masked_key": _mask_api_key(raw_key),
                }
            )
        if active_provider not in app_config.LLM_PROVIDER_PRESETS:
            configured = next((p["code"] for p in presets if p["has_key"]), "zhipu")
            active_provider = configured
        active_meta = app_config.LLM_PROVIDER_PRESETS[active_provider]
        current_model = os.getenv("LLM_MODEL", "").strip() or active_meta["model"]
        return {
            "ok": True,
            "provider": active_provider,
            "model": current_model,
            "presets": presets,
        }

    @router.post("/api/system/llm-config")
    async def save_llm_config(body: LlmConfigUpdateRequest, request: Request):
        """仅允许本机修改模型引擎与 API Key，并实时生效 + 持久化到 .env。"""
        if not _is_direct_local_request(request):
            return {
                "ok": False,
                "error": "安全保护：模型与 API Key 设置仅允许本机修改",
                "error_code": "FORBIDDEN",
            }
        provider = body.provider.strip().lower()
        if provider == "auto":
            provider = "zhipu"
        if provider not in app_config.LLM_PROVIDER_PRESETS:
            return {
                "ok": False,
                "error": "不支持的模型厂商",
                "error_code": "INVALID_INPUT",
                "field": "provider",
            }
        preset = app_config.LLM_PROVIDER_PRESETS[provider]
        model_name = body.model.strip() or preset["model"]
        env_updates = {
            "LLM_PROVIDER": provider,
            "LLM_MODEL": model_name,
        }
        key_env = preset["key_env"]
        clean_key = body.api_key.strip()
        if clean_key:
            env_updates[key_env] = clean_key

        env_path = os.path.join(app_config.BASE_DIR, ".env")
        _update_env_file_vars(env_path, env_updates)

        for k, v in env_updates.items():
            os.environ[k] = v
        app_config.LLM_PROVIDER = provider
        app_config.LLM_BASE_URL = preset["base_url"]
        app_config.LLM_MODEL = model_name
        app_config.LLM_FALLBACK_MODEL = preset.get("fallback_model", "")
        effective_key = os.getenv(key_env, "").strip()
        if effective_key:
            app_config.LLM_API_KEY = effective_key
            app_config.DEEPSEEK_API_KEY = effective_key
        app_config.DEEPSEEK_BASE_URL = app_config.LLM_BASE_URL
        app_config.DEEPSEEK_MODEL = app_config.LLM_MODEL

        add_log(f"已更新本地模型配置: {provider} / {model_name}", "success")
        return {
            "ok": True,
            "provider": provider,
            "model": model_name,
            "has_key": bool(effective_key),
            "masked_key": _mask_api_key(effective_key),
        }

    @router.post("/api/system/llm-test")
    async def test_llm_connection(request: Request):
        """测试当前生效的大模型 API Key 连通性与响应延迟（仅限本机）。"""
        if not _is_direct_local_request(request):
            return {"ok": False, "error": "安全保护：仅允许本机测试模型连通性", "error_code": "FORBIDDEN"}

        def _ping():
            from modules.deepseek_client import (
                classify_llm_exception,
                create_openai_client,
                resolve_llm_config,
            )

            cfg = resolve_llm_config()
            t0 = time.perf_counter()
            try:
                client = create_openai_client(timeout=18.0)
                resp = client.chat.completions.create(
                    model=cfg["model"],
                    messages=[{"role": "user", "content": "Reply OK"}],
                    max_tokens=8,
                    temperature=0,
                )
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                reply = ""
                if getattr(resp, "choices", None):
                    reply = str(getattr(resp.choices[0].message, "content", "") or "").strip()
                return {
                    "ok": True,
                    "provider": cfg["provider"],
                    "model": cfg["model"],
                    "latency_ms": elapsed_ms,
                    "reply": reply[:40],
                }
            except Exception as exc:
                code, msg = classify_llm_exception(exc)
                return {"ok": False, "error_code": code, "error": msg}

        return await run_in_threadpool(_ping)

    @router.get("/api/system/desktop-info")
    async def desktop_info(request: Request):
        """返回 PC 桌面端本地目录、数据库与日志概览（仅限本机）。"""
        if not _is_direct_local_request(request):
            return {"ok": False, "error": "仅限本机访问", "error_code": "FORBIDDEN"}
        exports_dir = os.path.join(app_config.RESUMES_DIR, "exports")
        db_file = os.path.join(app_config.DATA_DIR, "offerforge.db")
        log_file = os.path.join(app_config.LOGS_DIR, "desktop.log")
        db_kb = round(os.path.getsize(db_file) / 1024, 1) if os.path.isfile(db_file) else 0.0
        log_kb = round(os.path.getsize(log_file) / 1024, 1) if os.path.isfile(log_file) else 0.0
        return {
            "ok": True,
            "version": "OfferForge 3.0 Desktop",
            "base_dir": app_config.BASE_DIR,
            "data_dir": app_config.DATA_DIR,
            "resumes_dir": app_config.RESUMES_DIR,
            "exports_dir": exports_dir,
            "logs_dir": app_config.LOGS_DIR,
            "db_size_kb": db_kb,
            "log_size_kb": log_kb,
        }

    class OpenFolderRequest(BaseModel):
        target: str = Field(..., min_length=1, max_length=32)

    @router.post("/api/system/open-folder")
    async def open_local_folder(body: OpenFolderRequest, request: Request):
        """在 Windows 资源管理器中打开白名单内的本地数据目录（仅限本机）。"""
        if not _is_direct_local_request(request):
            return {"ok": False, "error": "仅限本机操作", "error_code": "FORBIDDEN"}
        mapping = {
            "data": app_config.DATA_DIR,
            "resumes": app_config.RESUMES_DIR,
            "exports": os.path.join(app_config.RESUMES_DIR, "exports"),
            "logs": app_config.LOGS_DIR,
        }
        folder = mapping.get(body.target.strip().lower())
        if not folder:
            return {"ok": False, "error": "不支持的目录类型", "error_code": "INVALID_INPUT"}
        os.makedirs(folder, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder)
        return {"ok": True, "path": folder}

    @router.get("/api/system/backup-zip")
    async def download_local_backup(request: Request):
        """一键打包备份本地数据库与简历目录（自动排除 .env 密钥防泄露，仅限本机）。"""
        if not _is_direct_local_request(request):
            return {"ok": False, "error": "仅限本机导出备份", "error_code": "FORBIDDEN"}

        def _build_zip() -> bytes:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for label, root_dir in (("data", app_config.DATA_DIR), ("resumes", app_config.RESUMES_DIR)):
                    if not os.path.isdir(root_dir):
                        continue
                    for r, dirs, files in os.walk(root_dir):
                        dirs[:] = [d for d in dirs if d not in {"webview2_profile", "desktop_app_profile", "__pycache__"}]
                        for fname in files:
                            if fname == ".env":
                                continue
                            fpath = os.path.join(r, fname)
                            rel = os.path.relpath(fpath, root_dir).replace("\\", "/")
                            try:
                                zf.write(fpath, f"{label}/{rel}")
                            except OSError:
                                pass
            return buf.getvalue()

        payload = await run_in_threadpool(_build_zip)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        headers = {"Content-Disposition": f'attachment; filename="OfferForge_Backup_{stamp}.zip"'}
        return StreamingResponse(io.BytesIO(payload), media_type="application/zip", headers=headers)

    @router.post("/api/system/clear-logs")
    async def clear_desktop_logs(request: Request):
        """清理本地桌面运行日志（仅限本机）。"""
        if not _is_direct_local_request(request):
            return {"ok": False, "error": "仅限本机操作", "error_code": "FORBIDDEN"}
        log_file = os.path.join(app_config.LOGS_DIR, "desktop.log")
        if os.path.isfile(log_file):
            try:
                with open(log_file, "w", encoding="utf-8") as handle:
                    handle.write("")
            except OSError:
                pass
        return {"ok": True, "message": "本地运行日志已清空"}

    @router.get("/api/system/clipboard-jd")
    async def check_clipboard_jd(request: Request):
        """PC 桌面端专属：窗口聚焦时 0ms 本地检测剪贴板是否为岗位 JD（绝不联网）。"""
        if not _is_direct_local_request(request):
            return {"ok": True, "is_jd": False}
        raw = _read_windows_clipboard_text()
        result = detect_clipboard_jd(raw)
        return {"ok": True, **result}

    return router
