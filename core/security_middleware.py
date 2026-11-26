"""网络安全加固中间件：会话级数据隔离 + 公网演示口令锁 + 单 IP 限流 + 公网高危路由禁用 + 安全响应头。"""

from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import hmac
import os
import threading
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.workspace_context import (
    WORKSPACE_COOKIE_NAME,
    generate_workspace_id,
    get_active_db_path,
    get_workspace_id,
    is_valid_workspace_id,
    reset_workspace_id,
    set_workspace_id,
    touch_workspace,
)
from modules.db_client import init_db

ACCESS_COOKIE_NAME = "of_access_grant"

_AI_RATE_LIMITED_PATHS = {
    "/api/resumes/upload",
    "/api/resume/optimize",
    "/api/resume/optimize/tasks",
    "/api/resume/precision-optimize",
    "/api/resume/precision-recheck",
    "/api/resume/interview-prep",
    "/api/jobs/match",
    "/api/jobs/batch-score",
    "/api/jobs/batch-score-json",
    "/api/jobs/batch-match",
    "/api/jobs/intent/extract",
    "/api/jobs/queries/preview",
    "/api/jobs/wechat/parse",
    "/api/deliver/greeting",
}

_SCRAPE_RATE_LIMITED_PATHS = {
    "/api/jobs/scrape",
}

_PUBLIC_BLOCKED_PREFIXES = (
    "/api/jobs/sessions",
    "/api/deliver/start",
)

_AUTH_EXEMPT_PATHS = {
    "/api/status",
    "/api/auth/status",
    "/api/auth/unlock",
    "/api/auth/logout",
}


def is_public_mode() -> bool:
    return os.getenv("OFFERFORGE_PUBLIC_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}


def get_demo_access_token() -> str:
    return (
        os.getenv("OFFERFORGE_DEMO_TOKEN", "").strip()
        or os.getenv("DEMO_ACCESS_TOKEN", "").strip()
    )


def get_isolation_mode() -> str:
    mode = os.getenv("OFFERFORGE_WORKSPACE_ISOLATION", "auto").strip().lower()
    return mode if mode in {"auto", "always", "off"} else "auto"


def _get_client_ip(request: Request) -> str:
    cf_ip = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf_ip:
        return cf_ip
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    x_real = (request.headers.get("x-real-ip") or "").strip()
    if x_real:
        return x_real
    return (request.client.host if request.client else "") or "unknown"


def _is_direct_local_request(request: Request) -> bool:
    """仅当直连本机回环且无任何反代转发头时，才视为本机访问。"""
    if request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip"):
        return False
    host = (request.client.host if request.client else "") or ""
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def _is_https_request(request: Request) -> bool:
    proto = (request.headers.get("x-forwarded-proto") or "").strip().lower()
    return proto == "https" or request.url.scheme == "https"


def _sign_access_token(raw_token: str) -> str:
    return hmac.new(raw_token.encode("utf-8"), b"offerforge-access-v1", hashlib.sha256).hexdigest()


def _has_valid_access(request: Request, required_token: str) -> bool:
    if not required_token:
        return True
    if _is_direct_local_request(request) and os.getenv("OFFERFORGE_REQUIRE_TOKEN_LOCAL", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return True
    expected_sig = _sign_access_token(required_token)
    cookie_val = (request.cookies.get(ACCESS_COOKIE_NAME) or "").strip()
    if cookie_val and hmac.compare_digest(cookie_val, expected_sig):
        return True
    header_val = (request.headers.get("x-access-token") or "").strip()
    if header_val and hmac.compare_digest(header_val, required_token):
        return True
    return False


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(self, key: tuple[str, str], limit: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._buckets[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                retry_after = max(1, int(window_seconds - (now - q[0])))
                return False, retry_after
            q.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


RATE_LIMITER = _SlidingWindowLimiter()


def _should_isolate_request(request: Request) -> bool:
    mode = get_isolation_mode()
    if mode == "off":
        return False
    if mode == "always":
        return True
    # auto 模式：所有真实浏览器均自动分配独立隔间；FastAPI TestClient 仅在显式携带隔离头/Cookie/转发头时启用，保证旧单测兼容
    client_host = (request.client.host if request.client else "") or ""
    if client_host != "testclient":
        return True
    if request.cookies.get(WORKSPACE_COOKIE_NAME):
        return True
    if request.headers.get("x-offerforge-isolate") == "1":
        return True
    if request.headers.get("x-forwarded-for") or request.headers.get("cf-connecting-ip"):
        return True
    return False


class OfferForgeSecurityMiddleware(BaseHTTPMiddleware):
    """统一执行：响应安全头、公网口令锁、高危路由拦截、单 IP 限流与浏览器隔间绑定。"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_host = (request.client.host if request.client else "") or ""

        # 1. 公网模式禁用会拉起宿主机桌面浏览器的高危接口
        if is_public_mode() and any(path.startswith(prefix) for prefix in _PUBLIC_BLOCKED_PREFIXES):
            resp = JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": "公网演示模式已禁用本机桌面浏览器自动化与本地会话操作，请使用 15 个纯 HTTP 官方开放源",
                    "error_code": "PUBLIC_MODE_RESTRICTED",
                },
            )
            return _attach_security_headers(resp)

        # 2. 公网演示口令门禁（仅拦截 /api/*，静态前端由前端解锁屏承接）
        required_token = get_demo_access_token()
        if path.startswith("/api/") and path not in _AUTH_EXEMPT_PATHS:
            if not _has_valid_access(request, required_token):
                resp = JSONResponse(
                    status_code=401,
                    content={
                        "ok": False,
                        "error": "需要输入访问口令后才能使用 OfferForge 在线服务",
                        "error_code": "ACCESS_TOKEN_REQUIRED",
                    },
                )
                return _attach_security_headers(resp)

        # 3. 单 IP 防刷限流（保护大模型 API 余额）
        test_rl = request.headers.get("x-offerforge-test-ratelimit") == "1"
        if (client_host != "testclient" or test_rl) and request.method.upper() == "POST":
            client_ip = _get_client_ip(request)
            if path in _AI_RATE_LIMITED_PATHS:
                ai_limit = max(1, int(os.getenv("OFFERFORGE_AI_RATE_LIMIT_PER_MIN", "15") or 15))
                ok, retry_after = RATE_LIMITER.allow((client_ip, "ai_min"), ai_limit, 60.0)
                if not ok:
                    resp = JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                        content={
                            "ok": False,
                            "error": f"AI 接口调用过于频繁，请在 {retry_after} 秒后再试",
                            "error_code": "RATE_LIMITED",
                        },
                    )
                    return _attach_security_headers(resp)
            elif path in _SCRAPE_RATE_LIMITED_PATHS:
                scrape_limit = max(1, int(os.getenv("OFFERFORGE_SCRAPE_RATE_LIMIT_PER_MIN", "6") or 6))
                ok, retry_after = RATE_LIMITER.allow((client_ip, "scrape_min"), scrape_limit, 60.0)
                if not ok:
                    resp = JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                        content={
                            "ok": False,
                            "error": f"岗位采集启动过于频繁，请在 {retry_after} 秒后再试",
                            "error_code": "RATE_LIMITED",
                        },
                    )
                    return _attach_security_headers(resp)

        # 4. 浏览器会话级物理数据隔离
        tokens = None
        new_cookie_ws = None
        if not path.startswith("/assets/") and not path.startswith("/static/") and _should_isolate_request(request):
            raw_ws = (request.cookies.get(WORKSPACE_COOKIE_NAME) or "").strip()
            if is_valid_workspace_id(raw_ws):
                ws_id = raw_ws
            else:
                ws_id = generate_workspace_id()
                new_cookie_ws = ws_id
            tokens = set_workspace_id(ws_id)
            touch_workspace(ws_id)
            init_db(get_active_db_path())

        try:
            response = await call_next(request)
        finally:
            if tokens is not None:
                reset_workspace_id(tokens)

        if new_cookie_ws:
            response.set_cookie(
                key=WORKSPACE_COOKIE_NAME,
                value=new_cookie_ws,
                max_age=30 * 86400,
                httponly=True,
                samesite="lax",
                secure=_is_https_request(request),
                path="/",
            )

        return _attach_security_headers(response)


def _attach_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


def create_auth_router() -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.get("/status")
    async def auth_status(request: Request):
        required_token = get_demo_access_token()
        unlocked = _has_valid_access(request, required_token)
        ws_id = get_workspace_id()
        return {
            "ok": True,
            "requires_token": bool(required_token),
            "unlocked": unlocked,
            "public_mode": is_public_mode(),
            "isolated": bool(ws_id),
            "workspace_tag": ws_id[:8] if ws_id else "local",
        }

    @router.post("/unlock")
    async def auth_unlock(request: Request):
        required_token = get_demo_access_token()
        if not required_token:
            return {"ok": True, "unlocked": True, "message": "当前未启用访问口令"}
        try:
            body = await request.json()
        except Exception:
            body = {}
        supplied = str((body or {}).get("token") or "").strip()
        if not supplied or not hmac.compare_digest(supplied, required_token):
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "访问口令不正确，请重试", "error_code": "INVALID_TOKEN"},
            )
        resp = JSONResponse({"ok": True, "unlocked": True, "message": "口令验证通过"})
        resp.set_cookie(
            key=ACCESS_COOKIE_NAME,
            value=_sign_access_token(required_token),
            max_age=7 * 86400,
            httponly=True,
            samesite="lax",
            secure=_is_https_request(request),
            path="/",
        )
        return resp

    @router.post("/logout")
    async def auth_logout():
        resp = JSONResponse({"ok": True, "unlocked": False})
        resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
        return resp

    return router
