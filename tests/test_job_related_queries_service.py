import asyncio
import unittest

from services.job_collection import start_scrape


class JobRelatedQueriesServiceTests(unittest.TestCase):
    def test_rejects_non_list_related_keywords_before_resume_access(self):
        result = asyncio.run(start_scrape(
            target_position="AI产品助理",
            related_keywords='{"query":"AI产品运营"}',
        ))

        self.assertFalse(result["ok"])
        self.assertEqual(result["field"], "related_keywords")

    def test_rejects_more_than_four_related_keywords(self):
        result = asyncio.run(start_scrape(
            target_position="AI产品助理",
            related_keywords='["岗位一","岗位二","岗位三","岗位四","岗位五"]',
        ))

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
