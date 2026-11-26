import unittest

import httpx
from fastapi import APIRouter, FastAPI

from app import app
from core.api_responses import (
    UnifiedAPIRoute,
    build_error_response,
    register_api_exception_handlers,
)


class ApiErrorMappingTests(unittest.TestCase):
    def test_running_task_uses_409_conflict(self):
        response = build_error_response(
            {"ok": False, "error": "采集任务正在进行中"}
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn(b'"error_code":"CONFLICT"', response.body)

    def test_ai_failure_uses_502_upstream_error(self):
        response = build_error_response(
            {"ok": False, "error": "AI调用失败: timeout"}
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn(b'"error_code":"UPSTREAM_ERROR"', response.body)


class ApiContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        self.client = httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_success_response_stays_200(self):
        response = await self.client.get("/api/status")

        self.assertEqual(response.status_code, 200)
        self.assertIn("steps", response.json())

    async def test_invalid_input_uses_400_contract(self):
        response = await self.client.post(
            "/api/jobs/batch-score",
            data={"jobs_file": "missing.json", "threshold": "101"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_INPUT")
        self.assertEqual(response.json()["field"], "threshold")

    async def test_missing_resource_uses_404_contract(self):
        response = await self.client.get("/api/jobs/detail/not-a-real-batch")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "NOT_FOUND")

    async def test_framework_validation_uses_422_contract(self):
        response = await self.client.post("/api/deliver/update_status", data={})
        body = response.json()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["error_code"], "REQUEST_VALIDATION_ERROR")
        self.assertEqual(body["field"], "delivery_id")
        self.assertNotIn("input", body["details"][0])

    async def test_unknown_api_uses_404_contract(self):
        response = await self.client.get("/api/not-a-route")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "NOT_FOUND")

    async def test_unhandled_exception_hides_internal_detail(self):
        test_app = FastAPI()
        register_api_exception_handlers(test_app)
        router = APIRouter(route_class=UnifiedAPIRoute)

        @router.get("/api/crash")
        async def crash():
            raise RuntimeError("private database detail")

        test_app.include_router(router)
        transport = httpx.ASGITransport(
            app=test_app,
            raise_app_exceptions=False,
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            with self.assertLogs("core.api_responses", level="ERROR"):
                response = await client.get("/api/crash")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error_code"], "INTERNAL_ERROR")
        self.assertNotIn("private database detail", response.text)


if __name__ == "__main__":
    unittest.main()
