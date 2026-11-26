import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from modules.job_scraper import CityFilterError, JobScraper, get_metro_code, normalize_city_name
from services import job_collection


class CityGuardTests(unittest.TestCase):
    def setUp(self):
        self.scraper = JobScraper()
        self.scraper.set_profile({"target_city": "广州", "desired_position": "AI & 产品"})
        self.scraper.salary_range = ""
        self.scraper.page = MagicMock()
        self.scraper.random_delay = MagicMock()
        self.scraper._parse_51job_card = lambda card, keyword: card

    def test_platform_display_name_dispatches_to_51job(self):
        with patch.object(self.scraper, "search_51job", return_value=[]) as search:
            self.scraper.search_all(["51前程无忧"], pages=1)
        search.assert_called_once_with(pages=1)

    def test_waits_for_default_city_to_be_replaced(self):
        wrong = [{"job_id": "1", "location": "云浮"}]
        right = [{"job_id": "2", "location": "广州·天河区"}]
        self.scraper.page.query_selector_all.side_effect = [wrong, right, right]
        result = self.scraper.search_51job(pages=1)
        self.assertEqual(result, right)
        self.scraper.page.wait_for_timeout.assert_called_once_with(250)
        query = parse_qs(urlparse(self.scraper.page.goto.call_args.args[0]).query)
        self.assertEqual(query["jobArea"], ["030200"])
        self.assertEqual(query["keyword"], ["AI & 产品"])

    def test_persistent_yunfu_is_error_not_empty_success(self):
        self.scraper.page.query_selector_all.return_value = [{"location": "云浮"}]
        with patch("modules.job_scraper.time.monotonic", side_effect=[0, 20]):
            with self.assertRaisesRegex(CityFilterError, "城市筛选未生效"):
                self.scraper.search_51job(pages=1)

    def test_empty_or_unparseable_page_is_unverified(self):
        for cards in ([], [None], [{"location": ""}]):
            with self.subTest(cards=cards), self.assertRaisesRegex(CityFilterError, "无法确认"):
                self.scraper._require_city_results(cards, "AI")

    def test_unknown_city_does_not_fall_back_to_all_cities(self):
        self.scraper.location = "不存在的城市"
        with self.assertRaisesRegex(CityFilterError, "城市码"):
            self.scraper.search_51job()
        self.scraper.page.goto.assert_not_called()

    def test_city_code_requires_an_explicit_configured_city(self):
        self.assertEqual(normalize_city_name(" 广州市 "), "广州")
        self.assertEqual(get_metro_code("广州市"), "030200")
        self.assertEqual(get_metro_code("深圳"), "040000")
        self.assertEqual(get_metro_code("不在广州"), "000000")
        self.assertEqual(get_metro_code("广州天河"), "000000")

    def test_mixed_results_only_keep_target_city(self):
        self.scraper.page.query_selector_all.return_value = [
            {"job_id": "1", "location": "云浮"},
            {"job_id": "1", "location": "广州市-天河区"},
            {"job_id": "3", "location": "云浮-广州路"},
        ]
        result = self.scraper.search_51job(pages=1)
        self.assertEqual([job["location"] for job in result], ["广州市-天河区"])

    def test_navigation_failure_is_not_zero_jobs(self):
        self.scraper.page.goto.side_effect = TimeoutError()
        with self.assertRaisesRegex(RuntimeError, "页面加载"):
            self.scraper.search_51job()

    def test_worker_stops_without_save_or_scoring_on_city_failure(self):
        state = {"running": True, "progress": "", "jobs_count": 0}
        fake = MagicMock()
        fake.location = "广州"
        fake.search_all.side_effect = CityFilterError("城市筛选未生效")
        with patch.object(job_collection, "JobScraper", return_value=fake), patch.object(
            job_collection, "SCRAPER_STATUS", state
        ), patch.object(job_collection, "add_log"), patch.object(job_collection, "_auto_batch_score") as score:
            job_collection._run_scrape_sync({}, ["AI"], ["51前程无忧"])
        self.assertFalse(state["running"])
        self.assertIn("城市筛选未生效", state["progress"])
        fake.save_jobs.assert_not_called()
        score.assert_not_called()
        fake.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
