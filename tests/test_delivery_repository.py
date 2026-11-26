import os
import tempfile
import unittest
from unittest.mock import patch

from modules.job_repository import save_job_batch
from services.delivery_service import list_deliver_candidates


def make_payload(score: int, resume_name: str = "candidate") -> dict:
    return {
        "profile": {},
        "keywords": ["python"],
        "count": 2,
        "collected_at": "2026-07-18 00:00:00",
        "resume_name": resume_name,
        "auto_scored": True,
        "jobs": [
            {
                "job_id": "job-1",
                "title": "python developer",
                "company": "company",
                "location": "广州",
                "url": "https://example.com/job-1",
                "match_score": score,
            },
            {
                "job_id": "job-2",
                "title": "junior developer",
                "company": "company",
                "location": "广州",
                "url": "https://example.com/job-2",
                "match_score": 60,
            },
        ],
    }


class DeliveryRepositoryTests(unittest.TestCase):
    def _list(self, batch_id: str, temp_dir: str, db_path: str):
        with (
            patch(
                "services.delivery_service.load_profile",
                return_value={"name": "candidate"},
            ),
            patch("services.delivery_service._load_deliver_history", return_value=[]),
        ):
            return list_deliver_candidates(
                batch_id,
                threshold=70,
                data_dir=temp_dir,
                db_path=db_path,
            )

    def test_selected_batch_comes_from_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "delivery.db")
            batch_id = "jobs_20260718_000001.json"
            save_job_batch(batch_id, make_payload(88), db_path)

            result = self._list(batch_id, temp_dir, db_path)

            self.assertTrue(result["ok"])
            self.assertEqual(result["jobs_file"], batch_id)
            self.assertEqual(result["total_jobs"], 2)
            self.assertEqual(result["candidates"], 1)
            self.assertEqual(result["jobs"][0]["match_score"], 88)
            self.assertFalse(os.path.exists(os.path.join(temp_dir, batch_id)))

    def test_missing_selection_falls_back_to_latest_repository_batch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "delivery.db")
            older_id = "jobs_20260718_000001.json"
            newer_id = "jobs_20260718_000002.json"
            save_job_batch(older_id, make_payload(75), db_path)
            save_job_batch(newer_id, make_payload(91), db_path)

            result = self._list("missing.json", temp_dir, db_path)

            self.assertTrue(result["ok"])
            self.assertEqual(result["jobs_file"], newer_id)
            self.assertEqual(result["jobs"][0]["match_score"], 91)

    def test_empty_repository_reports_no_collected_jobs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "delivery.db")

            result = self._list("", temp_dir, db_path)

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "没有找到岗位采集文件")


if __name__ == "__main__":
    unittest.main()
