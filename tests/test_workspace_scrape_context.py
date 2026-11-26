import os
import tempfile
import unittest
from unittest.mock import patch

from core.workspace_context import get_workspace_id, reset_workspace_id, set_workspace_id
from modules.job_collection_tasks import create_task, get_task
from services.job_collection import _run_scrape_sync


class WorkspaceScrapeThreadContextTests(unittest.TestCase):
    def test_multi_source_threadpool_preserves_workspace_context_and_stop_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ws_id = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
            observed = []

            def fake_collect_official_jobs(code, keywords, city, max_jobs=12, stop_check=None, progress_callback=None):
                stop_reason = stop_check() if stop_check else "NO_STOP_CHECK"
                observed.append((code, get_workspace_id(), stop_reason))
                return [
                    {
                        "job_id": f"{code}-1",
                        "title": "AI产品专员",
                        "company": f"{code}公司",
                        "location": "深圳",
                        "salary": "8-12K",
                        "source": code,
                        "url": f"https://example.com/{code}/1",
                        "description": "负责AI产品需求分析与迭代",
                    }
                ]

            tokens = set_workspace_id(ws_id, base_data_dir=temp_dir)
            try:
                with (
                    patch("core.workspace_context.DATA_DIR", temp_dir),
                    patch("services.job_collection.collect_official_jobs", side_effect=fake_collect_official_jobs),
                ):
                    task = create_task({"platforms": "meituan,jd", "city": "深圳"})
                    task_id = task["task_id"]
                    _run_scrape_sync(
                        profile={"name": "测试者", "desired_position": "AI产品专员", "desired_city": "深圳"},
                        keywords=["AI产品专员"],
                        platforms=["meituan", "jd"],
                        salary_range="6k-12k",
                        task_id=task_id,
                    )
                    final_task = get_task(task_id)
            finally:
                reset_workspace_id(tokens)

            self.assertEqual(len(observed), 2)
            for code, worker_ws, stop_reason in observed:
                self.assertEqual(worker_ws, ws_id, f"worker for {code} lost workspace ContextVar")
                self.assertIsNone(stop_reason, f"worker for {code} falsely saw stop_reason={stop_reason}")
            self.assertIsNotNone(final_task)
            self.assertEqual(final_task["status"], "completed")
            self.assertEqual(final_task["jobs_count"], 2)


if __name__ == "__main__":
    unittest.main()
