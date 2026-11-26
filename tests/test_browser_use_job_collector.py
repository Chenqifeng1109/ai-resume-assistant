import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.browser_use_job_collector import (
    BrowserUseCollectionError,
    _agent_failure_message,
    _classify_failure,
    _extract_liepin_cards,
    normalize_jobs,
)


class BrowserUseJobCollectorTests(unittest.TestCase):
    def test_normalizes_verified_city_and_source_domain(self):
        jobs = normalize_jobs({"jobs": [{
            "title": "AI产品助理",
            "company": "示例公司",
            "location": "广州-天河区",
            "salary": "8-12k",
            "url": "https://www.liepin.com/job/123.html",
            "description": "协助AI产品需求分析",
            "tags": ["Python", "需求分析"],
        }]}, "liepin", "广州", ["AI产品助理"], 12)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["source"], "猎聘")
        self.assertEqual(jobs[0]["keyword"], "AI产品助理")
        self.assertTrue(jobs[0]["job_id"].startswith("liepin-"))

    def test_rejects_wrong_city_foreign_domain_and_duplicates(self):
        valid = {
            "title": "产品助理", "company": "甲", "location": "广州市",
            "url": "https://www.liepin.com/job/ok.html",
        }
        jobs = normalize_jobs({"jobs": [
            valid,
            dict(valid),
            {**valid, "location": "深圳"},
            {**valid, "url": "https://example.com/job/1"},
            {"title": "缺少字段"},
        ]}, "liepin", "广州", ["产品助理"], 12)
        self.assertEqual(len(jobs), 1)

    def test_rejects_unknown_source_and_non_list_result(self):
        with self.assertRaises(ValueError):
            normalize_jobs({"jobs": []}, "unknown", "广州", ["产品"], 10)
        with self.assertRaises(ValueError):
            normalize_jobs({"jobs": {}}, "liepin", "广州", ["产品"], 10)

    def test_model_balance_error_is_translated_for_user(self):
        message = _agent_failure_message([None, "402: Insufficient Balance"])
        self.assertIn("AI API余额不足", message)

    def test_browser_failures_have_distinct_codes(self):
        self.assertEqual(_classify_failure("captcha required")[0], "CAPTCHA_REQUIRED")
        self.assertEqual(_classify_failure("需要登录才能继续")[0], "LOGIN_REQUIRED")
        self.assertEqual(_classify_failure("403 access denied")[0], "ACCESS_RESTRICTED")
        self.assertEqual(_classify_failure("402 Insufficient Balance")[0], "MODEL_BALANCE_INSUFFICIENT")

    def test_collection_error_preserves_machine_code(self):
        error = BrowserUseCollectionError("CITY_RESULT_MISMATCH", "城市错误")
        self.assertEqual(error.code, "CITY_RESULT_MISMATCH")

    def test_deterministic_card_extraction_reads_cdp_value(self):
        expected = [{
            "title": "AI产品助理",
            "company": "示例公司",
            "location": "广州-天河",
            "url": "https://www.liepin.com/job/123.html",
        }]

        class FakeRuntime:
            async def evaluate(self, params, session_id):
                self.params = params
                self.session_id = session_id
                return {"result": {"value": expected}}

        class FakeSend:
            def __init__(self):
                self.Runtime = FakeRuntime()

        class FakeClient:
            def __init__(self):
                self.send = FakeSend()

        class FakeSession:
            session_id = "session-1"
            cdp_client = FakeClient()

        class FakeBrowser:
            async def get_or_create_cdp_session(self, target_id=None, focus=False):
                self.request = (target_id, focus)
                return FakeSession()

        browser = FakeBrowser()
        result = asyncio.run(_extract_liepin_cards(browser, 6))

        self.assertEqual(result, expected)
        self.assertEqual(browser.request, (None, False))

    def test_adapter_reports_progress_and_rejects_cross_city_worker_result(self):
        progress_events = []

        class FakeProcess:
            returncode = 0

            def __init__(self, command, **_kwargs):
                result_path = Path(command[-2])
                progress_path = Path(command[-1])
                result_path.write_text('{"ok":true,"data":{"jobs":[{"title":"AI产品助理","company":"甲","location":"深圳","url":"https://www.liepin.com/job/1.html"}]}}', encoding="utf-8")
                progress_path.write_text('{"stage":"browser_collecting","message":"正在读取公开岗位","percent":50}', encoding="utf-8")

            def poll(self):
                return self.returncode

        with patch("modules.browser_use_job_collector.subprocess.Popen", FakeProcess):
            from modules.browser_use_job_collector import collect_jobs

            with self.assertRaises(BrowserUseCollectionError) as captured:
                collect_jobs(
                    "liepin", ["AI产品助理"], "广州", progress_callback=lambda *event: progress_events.append(event)
                )
        self.assertEqual(captured.exception.code, "CITY_RESULT_MISMATCH")
        self.assertEqual(progress_events[0][0], "browser_starting")


if __name__ == "__main__":
    unittest.main()
