# ============================================

# app.py — Web 后端服务器（完整版 v3：加入简历历史管理）

# ============================================

import sys

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))



from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

import json

from config import BASE_DIR, DATA_DIR, RESOURCE_DIR
from core.api_responses import register_api_exception_handlers
from core.security_middleware import (
    OfferForgeSecurityMiddleware,
    create_auth_router,
    is_public_mode,
)
from core.workspace_context import prune_stale_workspaces

from core.runtime_state import (
    STEPS,
    STATS,
    add_log,
    connected_clients,
)
from modules.db_client import init_db
from modules.job_collection_tasks import recover_interrupted_tasks
from routers.deliveries import router as deliveries_router
from routers.jobs import router as jobs_router
from routers.matching import router as matching_router
from routers.resume_actions import router as resume_actions_router
from routers.resumes import router as resumes_router
from routers.system import create_system_router




@asynccontextmanager

async def lifespan(app: FastAPI):

    init_db()

    recover_interrupted_tasks()

    prune_stale_workspaces(max_age_days=14)

    add_log("系统启动", "success")

    yield

    add_log("系统关闭", "warning")



_PUBLIC_MODE_ACTIVE = is_public_mode()
app = FastAPI(
    title="AI 智能简历助手",
    lifespan=lifespan,
    docs_url=None if _PUBLIC_MODE_ACTIVE else "/docs",
    redoc_url=None if _PUBLIC_MODE_ACTIVE else "/redoc",
    openapi_url=None if _PUBLIC_MODE_ACTIVE else "/openapi.json",
)

register_api_exception_handlers(app)

_raw_origins = os.getenv("OFFERFORGE_ALLOWED_ORIGINS", "").strip()
if _raw_origins:
    _cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
elif _PUBLIC_MODE_ACTIVE:
    _cors_origins = ["http://localhost:5000", "http://127.0.0.1:5000"]
else:
    _cors_origins = ["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=None if _PUBLIC_MODE_ACTIVE else r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Access-Token", "X-OfferForge-Isolate"],
)
app.add_middleware(OfferForgeSecurityMiddleware)

# 自定义静态文件服务（禁用缓存，确保前端更新生效）

from starlette.staticfiles import StaticFiles as _StaticFiles

class NoCacheStaticFiles(_StaticFiles):

    async def get_response(self, path: str, scope):

        response = await super().get_response(path, scope)

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

        response.headers["Pragma"] = "no-cache"

        response.headers["Expires"] = "0"

        return response



_static_dir = os.path.join(RESOURCE_DIR, "static")
if not os.path.isdir(_static_dir):
    _static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", NoCacheStaticFiles(directory=_static_dir), name="static")

app.include_router(
    create_system_router(
        steps=STEPS,
        stats=STATS,
        data_dir=DATA_DIR,
        add_log=add_log,
    )
)
app.include_router(create_auth_router())
app.include_router(resumes_router)
app.include_router(resume_actions_router)
app.include_router(deliveries_router)
app.include_router(jobs_router)
app.include_router(matching_router)






























@app.websocket("/ws")

async def websocket_endpoint(ws: WebSocket):
    from core.security_middleware import ACCESS_COOKIE_NAME, _sign_access_token, get_demo_access_token
    import hmac

    required_token = get_demo_access_token()
    if required_token:
        host = (ws.client.host if ws.client else "") or ""
        has_proxy = bool(ws.headers.get("cf-connecting-ip") or ws.headers.get("x-forwarded-for") or ws.headers.get("x-real-ip"))
        is_direct_local = (not has_proxy) and host in {"127.0.0.1", "::1", "localhost", "testclient"}
        if not is_direct_local:
            cookie_val = (ws.cookies.get(ACCESS_COOKIE_NAME) or "").strip()
            expected_sig = _sign_access_token(required_token)
            if not (cookie_val and hmac.compare_digest(cookie_val, expected_sig)):
                await ws.close(code=4401)
                return

    await ws.accept()

    connected_clients.add(ws)

    add_log("新的客户端已连接", "info")

    try:

        while True:

            data = await ws.receive_text()

            msg = json.loads(data)

            if msg.get("type") == "ping":

                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:

        connected_clients.discard(ws)

        add_log("客户端已断开", "info")







# ============================================

# 精准简历优化 - 针对高分岗位定向优化

# ============================================







# --- VITE FRONTEND INTEGRATION ---
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.join(RESOURCE_DIR, "frontend", "dist")
if not os.path.exists(os.path.join(frontend_dist, "index.html")):
    frontend_dist = os.path.join(BASE_DIR, "frontend", "dist")
if os.path.exists(os.path.join(frontend_dist, "assets")):
    try:
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    except Exception as e:
        print("Mount assets failed:", e)

@app.get("/")
async def root():
    index_file = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "Vite build not found. Please run npm run build in frontend directory."}

@app.get("/{catchall:path}")
async def catchall(catchall: str):
    if catchall.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="API route not found")
    index_file = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "Frontend not found"}
# ---------------------------------

if __name__ == "__main__":

    import uvicorn

    print(f"\n{'='*50}")

    print(f"  AI 智能简历助手 Web 控制台")

    print(f"  打开浏览器访问: http://localhost:5000")

    print(f"{'='*50}\n")

    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=False)
