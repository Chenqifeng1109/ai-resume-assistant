"""Production-build browser acceptance for job collection polling."""
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


class JobScrapeProgressUITests(unittest.TestCase):
    def test_running_success_and_failure_states_finish_without_sticking(self):
        dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
        mode = {
            "started": False, "polls": 0, "fail": False, "hold": False, "cancelled": False,
            "completed": False, "scrape_body": "",
        }

        def respond(route):
            url = urlsplit(route.request.url)
            path = url.path
            if path == "/api/resumes/list":
                route.fulfill(json={"resumes": [{
                    "filename": "virtual.json", "name": "模拟用户",
                    "position": "AI产品助理", "desired_salary": "8k-10k",
                }]})
            elif path == "/api/jobs/intent/confirm":
                route.fulfill(json={"ok": True, "intent": {
                    "position": "AI产品助理", "city": "广州",
                    "salary_min": 8000, "salary_max": 10000, "restrictions": [],
                }})
            elif path == "/api/jobs/queries/preview":
                route.fulfill(json={"ok": True, "primary": "AI产品助理", "max_related": 4, "related": [
                    {"query": "AI产品运营", "reason": "与目标岗位属于同一岗位族"},
                    {"query": "产品助理", "reason": "JD出现：用户研究、需求分析"},
                ]})
            elif path == "/api/jobs/sources/search-handoff":
                self.assertEqual(route.request.post_data_json, {
                    "source": "boss", "position": "AI产品助理", "city": "广州",
                })
                route.fulfill(json={
                    "ok": True, "source": "boss", "source_name": "BOSS直聘",
                    "official_url": "https://www.zhipin.com/guangzhou/",
                    "search_term": "AI产品助理", "target_city": "广州",
                    "city_entry_verified": True,
                    "message": "已生成广州官方入口，请在BOSS直聘页面搜索“AI产品助理”",
                })
            elif path == "/api/jobs/scrape" and route.request.method == "POST":
                mode["scrape_body"] = route.request.post_data or ""
                mode.update(started=True, polls=0, completed=False)
                route.fulfill(json={"ok": True, "message": "采集任务已启动", "task_id": "JOB-virtual001"})
            elif path == "/api/jobs/scrape/JOB-virtual001/cancel":
                mode["cancelled"] = True
                route.fulfill(json={"ok": True, "task_id": "JOB-virtual001", "status": "cancelling", "running": True, "progress": "正在安全停止采集，请稍候", "progress_percent": 30, "jobs_count": 0})
            elif path == "/api/jobs/scrape/status":
                if not mode["started"]:
                    route.fulfill(json={"running": False, "progress": "", "jobs_count": 0, "last_run": ""})
                elif mode["polls"] == 0:
                    mode["polls"] += 1
                    route.fulfill(json={"running": True, "progress": "正在搜索51前程无忧", "jobs_count": 0, "last_run": ""})
                elif mode["cancelled"]:
                    mode.update(started=False, cancelled=False, hold=False)
                    route.fulfill(json={"task_id": "JOB-virtual001", "status": "cancelled", "running": False, "progress": "岗位采集已由用户取消", "progress_percent": 30, "jobs_count": 0, "last_run": "18:30:00"})
                elif mode["hold"]:
                    route.fulfill(json={"task_id": "JOB-virtual001", "status": "running", "running": True, "progress": "正在搜索51前程无忧", "jobs_count": 0, "last_run": ""})
                elif mode["fail"]:
                    mode["started"] = False
                    route.fulfill(json={"running": False, "progress": "出错: 模拟页面结构变化", "jobs_count": 0, "last_run": "18:30:00"})
                else:
                    mode.update(started=False, completed=True)
                    route.fulfill(json={"running": False, "progress": "完成，共 2 个岗位", "jobs_count": 2, "last_run": "18:30:00"})
            elif path == "/api/jobs/list":
                files = [{"filename": "new.json", "keywords": ["AI产品助理"], "count": 2}] if mode["completed"] else []
                route.fulfill(json={"ok": True, "files": files})
            elif path == "/api/jobs/detail/new.json":
                route.fulfill(json={"ok": True, "data": {"jobs": [
                    {"job_id": "1", "title": "AI产品助理", "company": "甲公司", "location": "广州", "salary": "8k", "relation_type": "primary"},
                    {"job_id": "2", "title": "AI运营", "company": "乙公司", "location": "广州", "salary": "9k", "relation_type": "related"},
                ]}})
            elif path.startswith("/api/jobs/sources"):
                if path == "/api/jobs/sources":
                    route.fulfill(json={"ok": True, "sources": []})
                else:
                    route.fulfill(json={"ok": True, "storage_status": "missing"})
            elif path.startswith("/api/"):
                route.fulfill(json={"ok": True, "files": [], "data": {}})
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
                console_errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                page.on("dialog", lambda dialog: dialog.accept())
                page.goto("http://offerforge.test/")
                page.get_by_text("岗位采集", exact=True).first.click()
                resume_select = page.locator("select").first
                resume_select.select_option("virtual.json")
                page.get_by_placeholder("目标城市（必填）").fill("广州")
                page.get_by_role("button", name="确认采集条件").click()
                expect(page.get_by_text("求职意向已确认，可以启动岗位采集")).to_be_visible()

                page.get_by_role("button", name="启动采集").click()
                progress = page.get_by_role("progressbar", name="岗位采集处理中")
                expect(progress).to_be_visible()
                expect(page.get_by_role("button", name="采集中")).to_be_disabled()
                expect(page.get_by_text("正在搜索51前程无忧", exact=True)).to_be_visible()
                expect(page.get_by_text("岗位采集完成，共 2 个岗位", exact=True)).to_be_visible(timeout=5000)
                expect(progress).to_have_count(0)
                expect(page.get_by_text("AI产品助理主岗位", exact=True)).to_be_visible()
                expect(page.get_by_text("主岗位", exact=True)).to_be_visible()
                expect(page.get_by_text("关联岗位", exact=True)).to_be_visible()

                mode["hold"] = True
                page.get_by_role("button", name="启动采集").click()
                expect(progress).to_be_visible()
                page.reload()
                page.get_by_text("岗位采集", exact=True).first.click()
                expect(page.get_by_text("检测到未结束的岗位采集，已恢复状态跟踪", exact=True)).to_be_visible()
                expect(progress).to_be_visible()
                page.get_by_role("button", name="停止采集").click()
                expect(page.get_by_text("岗位采集已由用户取消", exact=True)).to_be_visible(timeout=5000)
                expect(progress).to_have_count(0)

                mode["fail"] = True
                page.locator("select").first.select_option("virtual.json")
                page.get_by_placeholder("目标城市（必填）").fill("广州")
                page.get_by_role("button", name="确认采集条件").click()
                page.get_by_role("button", name="启动采集").click()
                expect(progress).to_be_visible()
                expect(page.get_by_text("出错: 模拟页面结构变化", exact=True)).to_be_visible(timeout=5000)
                expect(progress).to_have_count(0)
                expect(page.get_by_role("button", name="启动采集")).to_be_enabled()
                self.assertEqual(errors, [])
                self.assertEqual(console_errors, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
