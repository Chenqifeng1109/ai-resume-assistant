import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from modules.db_client import init_db
from modules.job_repository import load_job_batch
from modules.job_scraper import JobScraper
from services.job_collection import _auto_batch_score


class FixedDateTime:
    @classmethod
    def now(cls):
        return datetime(2026, 7, 17, 12, 34, 56)


def make_scraper(jobs):
    scraper = JobScraper(headless=True)
    scraper.profile = {"name": "candidate", "desired_position": "python"}
    scraper.keywords = ["python", "fastapi"]
    scraper.jobs = jobs
    return scraper


class JobCollectionStorageTests(unittest.TestCase):
    def test_save_jobs_uses_repository_without_json_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "collection.db")
            jobs = [
                {
                    "job_id": "job-1",
                    "source": "test",
                    "title": "python developer",
                    "company": "company-1",
                    "salary": "10k-15k",
                    "location": "guangzhou",
                    "url": "https://example.com/1",
                    "tags": ["python"],
                },
                {
                    "job_id": "job-2",
                    "source": "test",
                    "title": "backend developer",
                    "company": "company-2",
                    "salary": "12k-18k",
                    "location": "guangzhou",
                    "url": "https://example.com/2",
                    "tags": ["fastapi"],
                },
            ]
            scraper = make_scraper(jobs)

            with patch("modules.job_scraper.datetime", FixedDateTime):
                json_path, payload = scraper.save_jobs(
                    temp_dir,
                    db_path,
                    include_payload=True,
                )

            batch_id = os.path.basename(json_path)
            self.assertFalse(os.path.exists(json_path))
            self.assertEqual(load_job_batch(batch_id, db_path), payload)

            connection = sqlite3.connect(db_path)
            try:
                rows = connection.execute(
                    """
                    SELECT job_id, batch_id, keywords
                    FROM jobs
                    ORDER BY job_id
                    """
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual(
                rows,
                [
                    ("job-1", batch_id, "python,fastapi"),
                    ("job-2", batch_id, "python,fastapi"),
                ],
            )

    def test_save_jobs_legacy_switch_writes_matching_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "collection.db")
            scraper = make_scraper(
                [
                    {
                        "job_id": "job-1",
                        "source": "test",
                        "title": "python developer",
                        "company": "company",
                    }
                ]
            )

            with patch("modules.job_scraper.datetime", FixedDateTime):
                json_path = scraper.save_jobs(
                    temp_dir,
                    db_path,
                    write_legacy_json=True,
                )

            with open(json_path, "r", encoding="utf-8") as source:
                json_payload = json.load(source)
            self.assertEqual(
                load_job_batch(os.path.basename(json_path), db_path),
                json_payload,
            )

    def test_missing_job_id_rolls_back_before_json_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "collection.db")
            init_db(db_path)
            scraper = make_scraper(
                [{"title": "missing identifier", "company": "company"}]
            )

            with patch("modules.job_scraper.datetime", FixedDateTime):
                with self.assertRaises(ValueError):
                    scraper.save_jobs(temp_dir, db_path)

            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM job_batches"
                    ).fetchone()[0],
                    0,
                )
            finally:
                connection.close()
            self.assertEqual(
                [name for name in os.listdir(temp_dir) if name.startswith("jobs_")],
                [],
            )

    def test_auto_score_default_preserves_json_and_legacy_switch_updates_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "collection.db")
            scraper = make_scraper(
                [
                    {
                        "job_id": "job-1",
                        "source": "test",
                        "title": "python developer",
                        "company": "company",
                        "tags": ["python"],
                    }
                ]
            )
            with patch("modules.job_scraper.datetime", FixedDateTime):
                json_path, jobs_data = scraper.save_jobs(
                    temp_dir,
                    db_path,
                    include_payload=True,
                )

            # 默认关闭兼容写入时，历史JSON即使存在也不能被改动。
            with open(json_path, "w", encoding="utf-8") as target:
                target.write("not valid json")

            score_result = {
                "ok": True,
                "overall_score": 92,
                "skill_match": 95,
                "experience_match": 88,
                "education_match": 90,
                "verdict": "strong match",
                "strengths": ["python"],
                "weaknesses": ["experience"],
                "suggestions": ["add metrics"],
            }
            with patch(
                "modules.jd_matcher.match_resume_to_jd",
                return_value=score_result,
            ):
                _auto_batch_score(
                    scraper.profile,
                    json_path,
                    jobs_data,
                    data_dir=temp_dir,
                    db_path=db_path,
                )

            stored = load_job_batch(os.path.basename(json_path), db_path)
            with open(json_path, "r", encoding="utf-8") as source:
                self.assertEqual(source.read(), "not valid json")
            self.assertTrue(stored["auto_scored"])
            self.assertEqual(stored["resume_name"], "candidate")
            self.assertEqual(stored["jobs"][0]["match_score"], 92)

            # 显式打开兼容开关时，仍能恢复旧版JSON同步行为。
            with patch(
                "modules.jd_matcher.match_resume_to_jd",
                return_value=score_result,
            ):
                _auto_batch_score(
                    scraper.profile,
                    json_path,
                    jobs_data,
                    data_dir=temp_dir,
                    db_path=db_path,
                    write_legacy_json=True,
                )

            with open(json_path, "r", encoding="utf-8") as source:
                scored_json = json.load(source)
            self.assertEqual(
                load_job_batch(os.path.basename(json_path), db_path),
                scored_json,
            )


if __name__ == "__main__":
    unittest.main()
