import asyncio
import unittest
from unittest.mock import patch

from routers.jobs import get_job_detail, list_collected_jobs


class JobRoutesRepositoryTests(unittest.TestCase):
    def test_list_uses_repository_batch_metadata(self):
        batches = [
            {
                "batch_id": "jobs_20260717_000001.json",
                "collected_at": "2026-07-17 00:00:00",
                "job_count": 2,
                "keywords": ["python", "fastapi"],
                "resume_name": "candidate",
            }
        ]
        with patch("routers.jobs.list_job_batches", return_value=batches):
            result = asyncio.run(list_collected_jobs())

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["files"][0]["count"], 2)
        self.assertEqual(
            result["files"][0]["keywords"],
            ["python,fastapi"],
        )

    def test_detail_returns_complete_repository_snapshot(self):
        payload = {
            "count": 1,
            "jobs": [
                {
                    "job_id": "job-1",
                    "match_score": 92,
                    "strengths": ["python"],
                }
            ],
        }
        with patch("routers.jobs.load_job_batch", return_value=payload):
            result = asyncio.run(get_job_detail("jobs_20260717_000001.json"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], payload)
        self.assertEqual(result["data"]["jobs"][0]["match_score"], 92)

    def test_detail_reports_a_missing_batch(self):
        with patch("routers.jobs.load_job_batch", return_value=None):
            result = asyncio.run(get_job_detail("jobs_20260717_000001.json"))

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "批次不存在或无数据")


if __name__ == "__main__":
    unittest.main()
