"""User-driven login in an isolated browser, confined to its worker thread."""
import threading
import time
import uuid
from urllib.parse import urlsplit

from core.runtime_state import SCRAPER_STATUS
from modules.job_sessions import BrowserSessionStore


def observe_login(page):
    host = urlsplit(page.url).hostname or ""
    if host != "51job.com" and not host.endswith(".51job.com"):
        return "unknown"
    # Positive evidence only; a cookie or an avatar alone is not authentication proof.
    for selector in ('a[href*="logout"]', 'button:text-is("退出登录")', 'a:text-is("退出登录")'):
        if page.locator(selector).first.is_visible():
            return "authenticated"
    if page.locator('input[type="password"]').first.is_visible():
        return "anonymous"
    return "unknown"


class LoginManager:
    def __init__(self, store_factory=BrowserSessionStore):
        self.store_factory = store_factory
        self.lock = threading.Lock()
        self.task = None
        self.command = None

    def snapshot(self, source="51job"):
        with self.lock:
            return dict(self.task) if self.task and self.task["source"] == source else None

    def active(self):
        with self.lock:
            return bool(self.task and self.task["running"])

    def forget(self, source):
        with self.lock:
            if self.task and self.task["source"] == source and not self.task["running"]:
                self.task = None

    def update(self, **values):
        with self.lock:
            self.task.update(values)

    def start(self, source, check_only=False):
        if source != "51job":
            return {"ok": False, "error": "该网站尚未接入登录管理", "error_code": "INVALID_INPUT"}
        with self.lock:
            if SCRAPER_STATUS.get("running") or (self.task and self.task["running"]):
                return {"ok": False, "error": "采集或登录操作正在进行", "error_code": "CONFLICT"}
            self.command = None
            self.task = {"task_id": uuid.uuid4().hex, "source": source, "running": True,
                         "stage": "opening", "auth_status": "unknown", "message": "正在打开独立浏览器"}
            result = dict(self.task)
        threading.Thread(target=self.run, args=(check_only,), daemon=True).start()
        return {"ok": True, "task": result}

    def action(self, task_id, action):
        with self.lock:
            if not self.task or self.task["task_id"] != task_id:
                return {"ok": False, "error": "登录任务不存在", "error_code": "NOT_FOUND"}
            if not self.task["running"]:
                return {"ok": False, "error": "登录任务已结束", "error_code": "CONFLICT"}
            if action not in {"save", "cancel"}:
                return {"ok": False, "error": "不支持的登录操作", "error_code": "INVALID_INPUT"}
            self.command = action
        return {"ok": True}

    def run(self, check_only=False, timeout_seconds=300):
        browser = None
        store = self.store_factory()
        try:
            from playwright.sync_api import sync_playwright
            try:
                saved = store.load("51job")
            except (OSError, ValueError, RuntimeError, TypeError, KeyError):
                saved = None
            previous = store.status("51job").get("last_observed_auth_status")
            with sync_playwright() as runtime:
                try:
                    browser = runtime.chromium.launch(channel="msedge", headless=check_only)
                    context = browser.new_context(storage_state=saved)
                    page = context.new_page()
                    page.goto("https://we.51job.com/", wait_until="domcontentloaded", timeout=30000)
                    self.update(stage="waiting", message=(
                        "已加载保存的会话并打开网站，请在独立浏览器查看；若网站要求登录请重新登录。更新会话请点击保存；5分钟后自动关闭"
                        if saved else "请在独立浏览器中手动登录，完成后回到这里点击保存会话；5分钟后自动关闭"))
                    deadline = time.monotonic() + timeout_seconds
                    while not page.is_closed() and time.monotonic() < deadline:
                        page.wait_for_timeout(250)
                        with self.lock:
                            command = self.command
                            self.command = None
                        if command == "cancel":
                            self.update(stage="cancelled", message="已取消，未保存本次会话")
                            return
                        if check_only or command == "save":
                            status = observe_login(page)
                            if status == "anonymous" and previous == "authenticated":
                                status = "expired"
                            if check_only:
                                self.update(stage="checked", auth_status=status, message={
                                    "authenticated": "当前页面检测到登录证据",
                                    "anonymous": "当前页面显示登录表单",
                                    "expired": "先前登录会话已失效，请重新登录",
                                    "unknown": "无法确认登录状态，可打开浏览器手动检查",
                                }[status])
                                return
                            if status in {"anonymous", "expired"}:
                                self.update(auth_status=status, message="仍显示登录表单，请完成登录后再保存")
                                continue
                            store.save("51job", context.storage_state(), status)
                            self.update(stage="saved", auth_status=status, message=(
                                "会话已保存，当前页面检测到登录证据；可点击“使用已保存会话打开网站”重新进入" if status == "authenticated"
                                else "会话已保存，但无法自动确认登录有效性；可点击“使用已保存会话打开网站”手动查看"))
                            return
                    self.update(stage="closed", message="浏览器已关闭或操作超时，未保存本次会话")
                finally:
                    if browser:
                        browser.close()
        except Exception:
            self.update(stage="failed", message="登录浏览器操作失败，请检查浏览器安装和网络后重试")
        finally:
            self.update(running=False, finished_at=time.time())


login_manager = LoginManager()
