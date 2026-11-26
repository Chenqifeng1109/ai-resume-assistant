import json
import os
import sqlite3
import tempfile
import unittest

from modules.db_client import init_db
from modules.job_repository import (
    import_legacy_job_batches,
    load_job_batch,
    payload_sha256,
    save_job_batch,
)


def make_payload(job_id: str, score: int = 88) -> dict:
    return {
        "profile": {"name": "candidate", "desired_position": "python"},
        "keywords": ["python", "fastapi"],
        "count": 1,
        "collected_at": "2026-07-17T00:00:00",
        "resume_name": "candidate",
        "auto_scored": True,
        "scored_at": "2026-07-17T00:01:00",
        "jobs": [
            {
                "job_id": job_id,
                "title": "developer",
                "company": "company",
                "match_score": score,
                "strengths": ["python"],
                "weaknesses": ["experience"],
            }
        ],
    }


class JobRepositoryTests(unittest.TestCase):
    def test_save_load_and_update_preserve_complete_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "repository.db")
            payload = make_payload("job-1")

            first = save_job_batch("jobs_20260717_000001.json", payload, db_path)
            second = save_job_batch("jobs_20260717_000001.json", payload, db_path)

            self.assertTrue(first["created"])
            self.assertFalse(first["changed"])
            self.assertFalse(second["created"])
            self.assertFalse(second["changed"])
            self.assertEqual(
                load_job_batch("jobs_20260717_000001.json", db_path),
                payload,
            )
            self.assertEqual(first["sha256"], payload_sha256(payload))

            changed_payload = make_payload("job-1", score=93)
            changed = save_job_batch(
                "jobs_20260717_000001.json",
                changed_payload,
                db_path,
            )
            self.assertFalse(changed["created"])
            self.assertTrue(changed["changed"])
            self.assertEqual(
                load_job_batch("jobs_20260717_000001.json", db_path),
                changed_payload,
            )

    def test_import_is_atomic_and_repeatable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "migration.db")
            init_db(db_path)
            first_path = os.path.join(temp_dir, "jobs_20260717_000001.json")
            second_path = os.path.join(temp_dir, "jobs_20260717_000002.json")
            with open(first_path, "w", encoding="utf-8") as target:
                json.dump(make_payload("job-1"), target, ensure_ascii=False)
            with open(second_path, "w", encoding="utf-8") as target:
                target.write("{broken")

            with self.assertRaises(json.JSONDecodeError):
                import_legacy_job_batches(temp_dir, db_path)

            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM job_batches"
                    ).fetchone()[0],
                    0,
                )
            finally:
                connection.close()

            with open(second_path, "w", encoding="utf-8") as target:
                json.dump(make_payload("job-2", score=91), target, ensure_ascii=False)

            first_import = import_legacy_job_batches(temp_dir, db_path)
            second_import = import_legacy_job_batches(temp_dir, db_path)

            self.assertEqual(len(first_import), 2)
            self.assertTrue(all(item["created"] for item in first_import))
            self.assertTrue(
                all(
                    not item["created"] and not item["changed"]
                    for item in second_import
                )
            )
            self.assertEqual(
                load_job_batch("jobs_20260717_000002.json", db_path),
                make_payload("job-2", score=91),
            )

    def test_rejects_unsafe_or_non_batch_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "repository.db")
            payload = make_payload("job-1")
            for batch_id in ("../jobs_bad.json", "other.json", "jobs_bad.txt"):
                with self.subTest(batch_id=batch_id):
                    with self.assertRaises(ValueError):
                        save_job_batch(batch_id, payload, db_path)

    def test_load_distinguishes_missing_and_unsafe_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "repository.db")

            self.assertIsNone(load_job_batch("not-a-real-batch", db_path))
            with self.assertRaises(ValueError):
                load_job_batch("../jobs_bad.json", db_path)


if __name__ == "__main__":
    unittest.main()
