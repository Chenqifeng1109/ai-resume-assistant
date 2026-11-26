"""Metadata-only session operations for the local desktop application."""
from modules.job_sessions import BrowserSessionStore, DOMAINS
from core.runtime_state import SCRAPER_STATUS
from services.job_login import login_manager


def get_session_status(source):
    if source not in DOMAINS:
        return {"ok": False, "error": "招聘来源不存在", "error_code": "NOT_FOUND"}
    return {"ok": True, "source": source, **BrowserSessionStore().status(source),
            "login_task": login_manager.snapshot(source)}


def clear_session(source, confirmed):
    if source not in DOMAINS:
        return {"ok": False, "error": "招聘来源不存在", "error_code": "NOT_FOUND"}
    if confirmed is not True:
        return {"ok": False, "error": "请确认清除该网站的本地会话", "error_code": "INVALID_INPUT"}
    if SCRAPER_STATUS.get("running") or login_manager.active():
        return {"ok": False, "error": "采集正在进行，请结束后再清除会话", "error_code": "CONFLICT"}
    try:
        BrowserSessionStore().clear(source)
        login_manager.forget(source)
    except OSError:
        return {"ok": False, "error": "本地会话清除失败，请稍后重试", "error_code": "INTERNAL_ERROR"}
    return {"ok": True, "source": source, "storage_status": "missing", "auth_status": "unknown",
            "message": "已清除本地会话；这不等于注销网站账号或撤销其他设备登录"}
