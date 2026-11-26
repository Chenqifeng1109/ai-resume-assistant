import os
import sqlite3
import tempfile
import unittest

from modules.db_client import init_db
from modules.job_repository import list_job_batches


class DatabaseSchemaTests(unittest.TestCase):
    def test_job_batches_use_filename_as_stable_tiebreaker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "ordering.db")
            init_db(db_path)
            connection = sqlite3.connect(db_path)
            try:
                for number in (1, 2):
                    connection.execute(
                        """
                        INSERT INTO job_batches (
                            batch_id, profile_data, keywords, collected_at,
                            resume_name, auto_scored, scored_at, job_count, payload
                        ) VALUES (?, '{}', '["python"]', ?, '', 0, '', 1, '{}')
                        """,
                        (
                            f"jobs_20260717_00000{number}.json",
                            "2026-07-17 00:00:00",
                        ),
                    )
                connection.commit()
            finally:
                connection.close()

            result = list_job_batches(db_path)

            self.assertEqual(
                [item["batch_id"] for item in result],
                [
                    "jobs_20260717_000002.json",
                    "jobs_20260717_000001.json",
                ],
            )

    def test_fresh_database_has_current_tables_and_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "fresh.db")

            init_db(db_path)
            init_db(db_path)

            connection = sqlite3.connect(db_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertTrue(
                    {
                        "resumes", "jobs", "deliveries", "job_batches",
                        "job_collection_tasks",
                    }
                    <= tables
                )

                job_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(jobs)")
                }
                self.assertTrue({"batch_id", "keywords"} <= job_columns)

                delivery_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(deliveries)")
                }
                self.assertIn("notes", delivery_columns)

                batch_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(job_batches)")
                }
                self.assertTrue(
                    {
                        "batch_id",
                        "profile_data",
                        "keywords",
                        "resume_name",
                        "job_count",
                        "payload",
                    }
                    <= batch_columns
                )

                task_columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(job_collection_tasks)"
                    )
                }
                self.assertTrue(
                    {
                        "task_id", "status", "stage", "progress_message",
                        "progress_percent", "jobs_count", "request_data",
                        "error_code", "error_message", "cancel_requested",
                        "deadline_at",
                    }
                    <= task_columns
                )
            finally:
                connection.close()

    def test_old_database_is_upgraded_without_losing_jobs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "legacy.db")
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT UNIQUE NOT NULL,
                        platform TEXT NOT NULL,
                        title TEXT NOT NULL,
                        company TEXT NOT NULL,
                        salary TEXT,
                        location TEXT,
                        url TEXT,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE deliveries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        resume_filename TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        match_score INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO jobs (job_id, platform, title, company)
                    VALUES ('legacy-1', 'legacy', 'title', 'company')
                    """
                )
                connection.commit()
            finally:
                connection.close()

            init_db(db_path)

            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
                    1,
                )
                job_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(jobs)")
                }
                self.assertTrue({"batch_id", "keywords"} <= job_columns)
                delivery_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(deliveries)")
                }
                self.assertIn("notes", delivery_columns)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
