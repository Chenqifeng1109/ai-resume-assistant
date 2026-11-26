import asyncio
from datetime import datetime


STEPS = [
    {"id": 1, "name": "简历解析", "icon": "file-text", "status": "done", "detail": "上传/解析/删除"},
    {"id": 2, "name": "智能优化简历", "icon": "sparkles", "status": "done", "detail": "AI 智能优化"},
    {"id": 3, "name": "简历模板", "icon": "layout", "status": "done", "detail": "6套模板+证件照"},
    {"id": 4, "name": "岗位采集", "icon": "search", "status": "done", "detail": "51前程无忧/采集历史"},
    {"id": 5, "name": "JD 匹配度评分", "icon": "target", "status": "done", "detail": "AI 打分"},
    {"id": 6, "name": "精准简历优化", "icon": "sparkles", "status": "done", "detail": "JD定向优化"},
    {"id": 7, "name": "自动打招呼", "icon": "send", "status": "done", "detail": "半自动投递"},
]

STATS = {
    "resumes": 0,
    "jobs_found": 0,
    "deliveries": 0,
    "replies": 0,
    "interviews": 0,
    "uptime": datetime.now().strftime("%H:%M:%S"),
}

connected_clients = set()
log_buffer = []
SCRAPER_STATUS = {
    "running": False,
    "progress": "",
    "jobs_count": 0,
    "last_run": "",
}
_WORKSPACE_SCRAPER_STATUS: dict[str, dict] = {}


def get_scraper_status(default_status: dict | None = None) -> dict:
    """按当前请求所属浏览器隔间返回独立的采集运行状态；无隔间时返回默认状态。"""
    from core.workspace_context import get_workspace_id

    ws_id = get_workspace_id()
    if not ws_id:
        return SCRAPER_STATUS if default_status is None else default_status
    state = _WORKSPACE_SCRAPER_STATUS.get(ws_id)
    if state is None:
        state = {
            "running": False,
            "progress": "",
            "jobs_count": 0,
            "last_run": "",
        }
        _WORKSPACE_SCRAPER_STATUS[ws_id] = state
    return state


def add_log(message: str, level: str = "info") -> None:
    """记录一条内存日志，并推送给当前已连接的 WebSocket 客户端。"""
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "msg": message,
    }
    log_buffer.append(entry)
    if len(log_buffer) > 100:
        log_buffer.pop(0)

    for websocket in list(connected_clients):
        try:
            asyncio.ensure_future(
                websocket.send_json({"type": "log", "data": entry})
            )
        except Exception:
            connected_clients.discard(websocket)
