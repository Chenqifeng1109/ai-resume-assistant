import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api_responses import register_api_exception_handlers
from routers.jobs import router


class JobIntentRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        register_api_exception_handlers(app)
        app.include_router(router)
        self.client = TestClient(app)

    @patch("routers.jobs.extract_job_intent_service")
    def test_extract_endpoint_returns_draft(self, extract_service):
        extract_service.return_value = {
            "ok": True,
            "intent": {
                "position": "AI产品助理",
                "city": "广州",
                "salary_min": 8000,
                "salary_max": 10000,
                "restrictions": [],
                "status": "needs_confirmation",
                "missing_fields": [],
                "warnings": [],
                "source_text": "广州AI产品助理",
                "confirmed_at": None,
            },
        }

        response = self.client.post(
            "/api/jobs/intent/extract",
            json={"intent_text": "广州AI产品助理"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intent"]["status"], "needs_confirmation")

    def test_confirm_endpoint_returns_confirmed_values(self):
        response = self.client.post(
            "/api/jobs/intent/confirm",
            json={
                "position": "AI产品助理",
                "city": "广州",
                "salary_min": 8000,
                "salary_max": 10000,
                "restrictions": ["不接受长期出差"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intent"]["status"], "confirmed")

    def test_confirm_endpoint_rejects_reversed_salary(self):
        response = self.client.post(
            "/api/jobs/intent/confirm",
            json={
                "position": "数据助理",
                "city": "深圳",
                "salary_min": 12000,
                "salary_max": 8000,
                "restrictions": [],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error_code"], "REQUEST_VALIDATION_ERROR")

    def test_query_preview_returns_bounded_explainable_suggestions(self):
        response = self.client.post(
            "/api/jobs/queries/preview",
            json={
                "position": "AI产品助理",
                "jd_text": "负责用户研究和需求分析",
                "max_related": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["primary"], "AI产品助理")
        self.assertLessEqual(len(data["related"]), 2)
        self.assertTrue(all(item["reason"] for item in data["related"]))

    @patch("routers.jobs.cancel_scrape_service", new_callable=AsyncMock)
    def test_cancel_endpoint_requires_explicit_body_and_forwards_task(self, cancel_service):
        cancel_service.return_value = {
            "ok": True,
            "task_id": "JOB-demo",
            "status": "cancelling",
            "running": True,
        }

        response = self.client.post(
            "/api/jobs/scrape/JOB-demo/cancel",
            json={"confirmed": True},
        )

        self.assertEqual(response.status_code, 200)
        cancel_service.assert_awaited_once_with("JOB-demo", True)

    @patch("routers.jobs.start_scrape_service", new_callable=AsyncMock)
    def test_scrape_endpoint_forwards_confirmed_intent(self, start_service):
        start_service.return_value = {"ok": True, "message": "采集任务已启动"}

        response = self.client.post(
            "/api/jobs/scrape",
            data={
                "platforms": "51前程无忧",
                "resume_file": "resume_demo.json",
                "salary_range": "8k-10k",
                "target_position": "AI产品助理",
                "target_city": "广州",
                "restrictions": "不接受长期出差",
                "related_keywords": '["AI产品运营"]',
            },
        )

        self.assertEqual(response.status_code, 200)
        start_service.assert_awaited_once_with(
            "51前程无忧",
            "resume_demo.json",
            "8k-10k",
            "AI产品助理",
            "广州",
            "不接受长期出差",
            '["AI产品运营"]',
        )


if __name__ == "__main__":
    unittest.main()
