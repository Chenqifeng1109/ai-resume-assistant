import tempfile
import unittest
from unittest.mock import patch

import httpx

from app import app


class ResumeUploadQualityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        self.client = httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_upload_returns_quality_warnings_without_rejecting_result(self):
        parsed_result = {
            "name": "",
            "phone": "",
            "email": "",
            "desired_position": "",
            "skills": [],
            "quality_status": "needs_review",
            "quality_warnings": [
                {
                    "code": "MISSING_NAME",
                    "field": "name",
                    "message": "未识别到姓名，请检查简历内容。",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as resume_dir:
            with (
                patch("routers.resumes.RESUMES_DIR", resume_dir),
                patch("routers.resumes.parse_resume", return_value=parsed_result),
                patch(
                    "routers.resumes.save_parsed_result",
                    return_value="temporary-result.json",
                ),
            ):
                response = await self.client.post(
                    "/api/resumes/upload",
                    files={"file": ("resume.txt", b"resume text", "text/plain")},
                )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["quality_status"], "needs_review")
        self.assertEqual(body["data"]["quality_warnings"][0]["field"], "name")

    async def test_upload_exposes_safe_chinese_schema_error_details(self):
        parsed_result = {
            "error": "AI简历解析结果格式异常：技能 > 第2项必须是文本格式。",
            "error_code": "RESUME_SCHEMA_INVALID",
            "validation_errors": [
                {
                    "field": "技能 > 第2项",
                    "message": "技能 > 第2项必须是文本格式",
                    "type": "string_type",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as resume_dir:
            with (
                patch("routers.resumes.RESUMES_DIR", resume_dir),
                patch("routers.resumes.parse_resume", return_value=parsed_result),
            ):
                response = await self.client.post(
                    "/api/resumes/upload",
                    files={"file": ("resume.txt", b"resume text", "text/plain")},
                )

        body = response.json()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["error_code"], "RESUME_SCHEMA_INVALID")
        self.assertEqual(body["details"][0]["field"], "技能 > 第2项")
        self.assertNotIn("input", body["details"][0])


if __name__ == "__main__":
    unittest.main()
