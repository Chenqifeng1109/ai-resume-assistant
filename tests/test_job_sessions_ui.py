"""Offline UI acceptance against the production build; no real sessions touched."""
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect


@unittest.skip("网站会话管理面板已按用户决策从前端步骤4移除")
class JobSessionsUITests(unittest.TestCase):
    def test_fold_refresh_cancel_clear_and_conflict(self):
        dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
        if not dist.joinpath("index.html").exists():
            self.skipTest("Build frontend before UI acceptance")
        calls = []
        mode = {"conflict": True, "task": None, "storage": "saved", "opens": 0}

        def respond(route):
            url = urlsplit(route.request.url)
            path = url.path
            if path.endswith("/session/login"):
                mode["opens"] += 1
                mode["task"] = {"task_id": "virtual", "running": True, "stage": "waiting", "message": "请手动登录"}
                route.fulfill(json={"ok": True, "task": mode["task"]})
            elif path.endswith("/session/action"):
                mode["storage"] = "saved"
                self.assertEqual(route.request.post_data_json, {"task_id": "virtual", "action": "save"})
                mode["task"] = {"task_id": "virtual", "running": False, "stage": "saved", "message": "虚拟会话已保存，状态待确认"}
                route.fulfill(json={"ok": True})
            elif path.endswith("/session/clear"):
                if not mode["conflict"]:
                    mode["storage"] = "missing"
                calls.append(route.request.post_data_json)
                route.fulfill(status=409 if mode["conflict"] else 200, json={
                    "ok": not mode["conflict"], "error": "采集正在进行，请结束后再清除会话",
                    "storage_status": "missing", "message": "已清除本地会话",
                })
            elif path.endswith("/session"):
                route.fulfill(json={"ok": True, "storage_status": mode["storage"], "auth_status": "unknown", "login_task": mode["task"]})
            elif path == "/api/jobs/sources":
                route.fulfill(json={"ok": True, "sources": [
                    {"code": "51job", "name": "前程无忧", "can_attempt_search": True},
                    {"code": "boss", "name": "BOSS直聘", "can_attempt_search": False, "access_mode": "manual_assist"},
                    {"code": "liepin", "name": "猎聘", "can_attempt_search": False},
                ]})
            elif path.startswith("/api/"):
                route.fulfill(json={"ok": True, "resumes": [], "files": [], "steps": [], "data": {}})
            elif url.hostname == "offerforge.test":
                file = dist / (path.lstrip("/") or "index.html")
                if file.is_file() and file.resolve().is_relative_to(dist):
                    mime = "application/javascript" if file.suffix == ".js" else "text/css" if file.suffix == ".css" else "text/html"
                    route.fulfill(body=file.read_bytes(), content_type=mime + "; charset=utf-8")
                else:
                    route.fulfill(status=404)
            else:
                route.fulfill(body="", content_type="application/javascript")

        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel="msedge", headless=True)
            try:
                page = browser.new_page()
                page.route("**/*", respond)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto("http://offerforge.test/")
                page.get_by_text("岗位采集", exact=True).first.click()
                summary = page.locator("summary").filter(has_text="网站会话管理")
                expect(summary).to_be_visible()
                expect(page.get_by_role("button", name="刷新会话状态")).to_have_count(0)
                summary.click()
                expect(page.get_by_text("已保存本地会话 · 当前登录有效性待检查")).to_be_visible()
                expect(page.get_by_text("人工辅助搜索", exact=True)).to_be_visible()
                expect(page.get_by_text("尚未接入采集")).to_be_visible()
                expect(page.get_by_role("button", name="使用已保存会话打开网站")).to_be_visible()
                button = page.get_by_role("button", name="清除本地会话", exact=True)
                page.once("dialog", lambda dialog: dialog.dismiss())
                button.click()
                self.assertEqual(calls, [])
                page.once("dialog", lambda dialog: dialog.accept())
                button.click()
                expect(page.get_by_role("status")).to_contain_text("采集正在进行")
                mode["conflict"] = False
                page.once("dialog", lambda dialog: dialog.accept())
                button.click()
                expect(page.get_by_text("尚未保存本地会话")).to_be_visible()
                expect(button).to_be_disabled()
                self.assertEqual(calls, [{"confirmed": True}, {"confirmed": True}])
                page.get_by_role("button", name="打开网站登录").click()
                expect(page.get_by_text("请手动登录", exact=True)).to_be_visible()
                expect(button).to_be_disabled()
                page.get_by_role("button", name="已操作，保存会话").click()
                expect(page.get_by_text("虚拟会话已保存，状态待确认")).to_be_visible()
                page.get_by_role("button", name="刷新会话状态").click()
                reopen = page.get_by_role("button", name="使用已保存会话打开网站")
                expect(reopen).to_be_enabled()
                reopen.click()
                expect(reopen).to_be_disabled()
                self.assertEqual(mode["opens"], 2)
                self.assertEqual(errors, [])
            finally:
                browser.close()
