import json
import os
import tempfile
import unittest
from unittest.mock import patch

from modules.job_repository import save_job_batch
from services.delivery_service import generate_greeting


class FakeDeepSeekClient:
    def __init__(self, captured: dict):
        self.captured = captured

    def chat(self, **kwargs):
        self.captured.update(kwargs)
        return "您好，期待进一步沟通"


class GreetingRepositoryTests(unittest.TestCase):
    def _write_resume(self, temp_dir: str) -> str:
        filename = "resume.json"
        with open(os.path.join(temp_dir, filename), "w", encoding="utf-8") as target:
            json.dump(
                {
                    "name": "candidate",
                    "desired_position": "python developer",
                    "skills": ["python", "fastapi"],
                    "summary": "backend learner",
                },
                target,
                ensure_ascii=False,
            )
        return filename

    def _generate(self, temp_dir: str, db_path: str, jobs_file: str):
        captured = {}
        fake_client = FakeDeepSeekClient(captured)
        with patch(
            "services.delivery_service.DeepSeekClient",
            return_value=fake_client,
        ):
            result = generate_greeting(
                self._write_resume(temp_dir),
                jobs_file=jobs_file,
                data_dir=temp_dir,
                db_path=db_path,
            )
        return result, captured

    def test_greeting_uses_first_eight_repository_jobs_without_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "greeting.db")
            batch_id = "jobs_20260718_000001.json"
            jobs = [
                {
                    "job_id": f"job-{index}",
                    "title": f"role-{index}",
                    "company": "company",
                    "salary": "5-8k",
                }
                for index in range(9)
            ]
            save_job_batch(
                batch_id,
                {
                    "profile": {},
                    "keywords": ["python"],
                    "count": len(jobs),
                    "collected_at": "2026-07-18 00:00:00",
                    "jobs": jobs,
                },
                db_path,
            )

            result, captured = self._generate(temp_dir, db_path, batch_id)

            self.assertTrue(result["ok"])
            self.assertFalse(os.path.exists(os.path.join(temp_dir, batch_id)))
            self.assertIn("role-0", captured["user_message"])
            self.assertIn("role-7", captured["user_message"])
            self.assertNotIn("role-8", captured["user_message"])

    def test_missing_repository_batch_keeps_optional_context_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "greeting.db")

            result, captured = self._generate(
                temp_dir,
                db_path,
                "jobs_20260718_000001.json",
            )

            self.assertTrue(result["ok"])
            self.assertNotIn("[采集到的岗位信息", captured["user_message"])

    def test_unsafe_job_name_is_rejected_before_ai(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "greeting.db")
            resume_file = self._write_resume(temp_dir)

            with patch("services.delivery_service.DeepSeekClient") as client:
                result = generate_greeting(
                    resume_file,
                    jobs_file="../jobs_bad.json",
                    data_dir=temp_dir,
                    db_path=db_path,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "岗位文件名不安全")
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
