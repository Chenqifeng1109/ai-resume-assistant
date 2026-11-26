import unittest
from unittest.mock import MagicMock, patch

from modules.job_scraper import CollectionStopped, JobScraper
from services import job_collection


class JobScraperCancellationTests(unittest.TestCase):
    def test_cancel_stops_before_first_keyword_navigation(self):
        scraper = JobScraper(headless=True)
        scraper.page = MagicMock()
        scraper.keywords = ["数据运营"]
        scraper.location = "广州"
        scraper.stop_check = lambda: "cancelled"

        with self.assertRaises(CollectionStopped) as raised:
            scraper.search_51job(pages=2)

        self.assertEqual(raised.exception.reason, "cancelled")
        scraper.page.goto.assert_not_called()

    def test_worker_records_cancelled_instead_of_failed_or_completed(self):
        state = {
            "running": True,
            "status": "running",
            "progress_percent": 30,
            "jobs_count": 0,
        }
        fake_scraper = MagicMock()
        fake_scraper.search_all.side_effect = CollectionStopped("cancelled")
        with patch.object(job_collection, "SCRAPER_STATUS", state), patch.object(
            job_collection, "JobScraper", return_value=fake_scraper
        ), patch.object(job_collection, "update_task") as update_task:
            job_collection._run_scrape_sync(
                {}, ["数据运营"], ["51job"], task_id="JOB-test-cancel"
            )

        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(state["progress"], "岗位采集已由用户取消")
        fake_scraper.close.assert_called_once()
        self.assertEqual(update_task.call_args.kwargs["error_code"], "USER_CANCELLED")


if __name__ == "__main__":
    unittest.main()
