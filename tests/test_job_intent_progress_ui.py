from pathlib import Path
import unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect


class IntentProgressUITests(unittest.TestCase):
    def test_pending_success_missing_city_and_failure(self):
        dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
        pending = []
        sent = []

        def respond(route):
            path = urlsplit(route.request.url).path
            if path == "/api/jobs/intent/extract":
                sent.append(route.request.post_data_json)
                pending.append(route)
            elif path.startswith("/api/"):
                route.fulfill(json={"ok": True, "resumes": [], "files": [], "data": {}})
            elif urlsplit(route.request.url).hostname == "offerforge.test":
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
                page.goto("http://offerforge.test/")
                page.get_by_text("岗位采集", exact=True).first.click()
                text = page.get_by_placeholder("用一句话说明求职意向", exact=False)
                text.fill("想在广州找AI产品助理")
                page.get_by_role("button", name="AI识别求职意向").click()
                progress = page.get_by_role("progressbar", name="求职意向识别处理中")
                expect(progress).to_be_visible()
                expect(page.get_by_role("button", name="AI识别中")).to_be_disabled()
                expect(page.get_by_placeholder("目标城市（必填）")).to_be_disabled()
                self.assertIsNone(progress.get_attribute("aria-valuenow"))
                page.wait_for_timeout(1200)
                expect(page.get_by_text("已等待 1 秒")).to_be_visible()
                self.assertEqual(sent, [{"intent_text": "想在广州找AI产品助理"}])
                pending.pop().fulfill(json={"ok": True, "intent": {"position": "AI产品助理", "city": "广州", "missing_fields": []}})
                expect(progress).to_have_count(0)
                expect(page.get_by_placeholder("目标城市（必填）")).to_have_value("广州")
                text.fill("想找AI产品助理")
                page.get_by_role("button", name="AI识别求职意向").click()
                expect(progress).to_be_visible()
                page.wait_for_timeout(100)
                pending.pop().fulfill(json={"ok": True, "intent": {"position": "AI产品助理", "city": "", "missing_fields": ["city", "salary"]}})
                expect(page.get_by_text("AI已整理，尚未提取：目标城市", exact=False)).to_be_visible()
                expect(page.get_by_placeholder("目标城市（必填）")).to_have_value("")
                page.get_by_role("button", name="AI识别求职意向").click()
                expect(progress).to_be_visible()
                page.wait_for_timeout(100)
                pending.pop().fulfill(status=502, json={"ok": False, "error": "模拟AI失败"})
                expect(progress).to_have_count(0)
                expect(page.get_by_role("button", name="AI识别求职意向")).to_be_enabled()
                expect(page.get_by_text("模拟AI失败", exact=True)).to_be_visible()
            finally:
                browser.close()
