import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.browser_use_job_collector import BrowserUseCollectionError, collect_jobs
from modules.job_repository import load_job_batch, save_collected_job_batch
from modules.job_scraper import JobScraper
from services import job_collection


class WaitingProcess:
    returncode = None

    def __init__(self, _command, **_kwargs):
        self.pid = 45678

    def poll(self):
        return self.returncode


class CombinedSourceScraper:
    def __init__(self, db_path):
        self.db_path = db_path
        self.location = "广州"
        self.jobs = []
        self.profile = {}
        self.keywords = []
        self.primary_keyword = ""
        self.stop_check = None
        self.saved_batch_id = "jobs_20260920_030000.json"

    def set_profile(self, profile):
        self.profile = profile

    def _launch_browser(self):
        return None

    def search_all(self, platforms, pages):
        self.asserted_platforms = (platforms, pages)
        return [
            {
                "job_id": "51job-1",
                "source": "51job",
                "title": "AI产品助理",
                "company": "甲公司",
                "location": "广州-天河",
                "url": "https://we.51job.com/job/1",
                "keyword": "AI产品助理",
            },
            {
                "job_id": "51job-1",
                "source": "51job",
                "title": "AI产品助理",
                "company": "甲公司",
                "location": "广州-天河",
                "url": "https://we.51job.com/job/1",
                "keyword": "AI产品助理",
            },
        ]

    def _deduplicate_and_rank(self, jobs):
        return JobScraper._deduplicate_and_rank(self, jobs)

    def _city_matches(self, location):
        return "广州" in location

    def _check_stop(self):
        return None

    def save_jobs(self, include_payload=False):
        payload = {
            "profile": self.profile,
            "keywords": self.keywords,
            "collected_at": "2026-09-20T03:00:00",
            "jobs": self.jobs,
        }
        save_collected_job_batch(self.saved_batch_id, payload, self.db_path)
        result = (os.path.join("data", self.saved_batch_id), payload)
        return result if include_payload else result[0]

    def close(self):
        return None


class BrowserUseCollectionIntegrationTests(unittest.TestCase):
    def test_active_worker_cancellation_stops_owned_process(self):
        process = WaitingProcess(None)

        def stop_process_tree(target):
            self.assertIs(target, process)
            target.returncode = -1

        with patch(
            "modules.browser_use_job_collector.subprocess.Popen", return_value=process
        ), patch(
            "modules.browser_use_job_collector._stop_process_tree", side_effect=stop_process_tree
        ) as stop_worker, patch("modules.browser_use_job_collector.time.sleep"):
            with self.assertRaises(BrowserUseCollectionError) as captured:
                collect_jobs("liepin", ["AI产品助理"], "广州", stop_check=lambda: "cancelled")

        self.assertEqual(captured.exception.code, "USER_CANCELLED")
        stop_worker.assert_called_once_with(process)

    def test_timeout_stops_owned_process_and_returns_timeout_code(self):
        process = WaitingProcess(None)

        def stop_process_tree(target):
            target.returncode = -1

        with patch(
            "modules.browser_use_job_collector.subprocess.Popen", return_value=process
        ), patch(
            "modules.browser_use_job_collector._stop_process_tree", side_effect=stop_process_tree
        ) as stop_worker, patch(
            "modules.browser_use_job_collector.time.monotonic", side_effect=[0, 31]
        ), patch("modules.browser_use_job_collector.time.sleep"):
            with self.assertRaises(BrowserUseCollectionError) as captured:
                collect_jobs("liepin", ["AI产品助理"], "广州", timeout_seconds=30)

        self.assertEqual(captured.exception.code, "BROWSER_TIMEOUT")
        stop_worker.assert_called_once_with(process)

    def test_combined_sources_are_deduplicated_and_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "combined.db")
            fake_scraper = CombinedSourceScraper(db_path)
            state = {
                "running": True,
                "status": "running",
                "progress_percent": 0,
                "jobs_count": 0,
            }
            liepin_job = {
                "job_id": "liepin-2",
                "source": "猎聘",
                "title": "AI产品助理",
                "company": "乙公司",
                "location": "广州-越秀",
                "url": "https://www.liepin.com/job/2.html",
                "keyword": "AI产品助理",
            }

            def set_task(_task_id, stage, message, percent, jobs_count=None, **changes):
                state.update({
                    "stage": stage,
                    "progress": message,
                    "progress_percent": percent,
                    "status": changes.get("status", "running"),
                    "running": changes.get("status", "running") in {"queued", "running"},
                })
                if jobs_count is not None:
                    state["jobs_count"] = jobs_count

            with patch.object(job_collection, "SCRAPER_STATUS", state), patch.object(
                job_collection, "JobScraper", return_value=fake_scraper
            ), patch.object(
                job_collection, "collect_browser_use_jobs", return_value=[liepin_job, dict(liepin_job)]
            ), patch.object(
                job_collection, "_set_scrape_task", side_effect=set_task
            ), patch.object(job_collection, "_auto_batch_score"):
                job_collection._run_scrape_sync(
                    {"name": "测试候选人"},
                    ["AI产品助理"],
                    ["51job", "liepin"],
                    task_id="JOB-combined-test",
                )

            stored = load_job_batch(fake_scraper.saved_batch_id, db_path)
            self.assertEqual(stored["count"] if "count" in stored else len(stored["jobs"]), 2)
            self.assertEqual({job["source"] for job in stored["jobs"]}, {"51job", "猎聘"})
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["jobs_count"], 2)


if __name__ == "__main__":
    unittest.main()
