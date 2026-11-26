"""Offline browser fixtures; all page requests are intercepted locally."""
import html
import json
import unittest
from unittest.mock import patch

from modules.job_scraper import CityFilterError, JobScraper


def card(city, identity):
    payload = html.escape(json.dumps({
        "jobTitle": "演示岗位", "jobId": identity,
        "jobArea": city, "jobSalary": "6-8k",
    }, ensure_ascii=False), quote=True)
    return f'<div class="joblist-item"><div sensorsdata="{payload}"></div></div>'


class OfflineCityBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise unittest.SkipTest("Playwright is unavailable") from error
        cls.runtime = sync_playwright().start()
        try:
            try:
                cls.browser = cls.runtime.chromium.launch(channel="msedge", headless=True)
            except Exception:
                cls.browser = cls.runtime.chromium.launch(headless=True)
        except Exception as error:
            cls.runtime.stop()
            raise unittest.SkipTest("No installed test browser") from error

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def run_fixture(self, markup):
        context = self.browser.new_context(service_workers="block")
        self.addCleanup(context.close)
        context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=markup))
        scraper = JobScraper()
        scraper.page = context.new_page()
        scraper.set_profile({"target_city": "广州", "desired_position": "测试"})
        scraper.salary_range = ""
        wait = scraper._wait_for_city_results
        with patch.object(scraper, "random_delay"), patch.object(
            scraper, "_wait_for_city_results", side_effect=lambda keyword: wait(keyword, timeout_ms=800)
        ):
            return scraper.search_all(["51前程无忧"], pages=1)

    def test_delayed_guangzhou_replaces_default_yunfu(self):
        later = json.dumps(card("广州·天河区", "gz"), ensure_ascii=False)
        markup = card("云浮", "yf") + f'<script>setTimeout(() => document.body.innerHTML = {later}, 300)</script>'
        jobs = self.run_fixture(markup)
        self.assertEqual([job["job_id"] for job in jobs], ["gz"])

    def test_yunfu_never_becomes_success(self):
        with self.assertRaisesRegex(CityFilterError, "城市筛选未生效"):
            self.run_fixture(card("云浮", "yf"))

    def test_login_page_is_unverified_not_empty_success(self):
        with self.assertRaisesRegex(CityFilterError, "无法确认"):
            self.run_fixture("<html><body>请先登录</body></html>")

    def test_mixed_cards_only_return_guangzhou(self):
        jobs = self.run_fixture(card("云浮", "yf") + card("广州-天河区", "gz"))
        self.assertEqual([job["job_id"] for job in jobs], ["gz"])


if __name__ == "__main__":
    unittest.main()
