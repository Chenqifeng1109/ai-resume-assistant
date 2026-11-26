import unittest

from modules.job_query_planner import suggest_related_queries
from modules.job_scraper import JobScraper


class JobQueryPlannerTests(unittest.TestCase):
    def test_suggestions_are_bounded_explainable_and_do_not_replace_primary(self):
        result = suggest_related_queries(
            "AI产品助理", "负责需求分析、产品原型和数据看板", max_related=20
        )
        self.assertEqual(result["primary"], "AI产品助理")
        self.assertLessEqual(len(result["related"]), 4)
        self.assertNotIn("AI产品助理", [item["query"] for item in result["related"]])
        self.assertTrue(all(item["reason"] for item in result["related"]))

    def test_unknown_role_does_not_invent_related_jobs(self):
        self.assertEqual(suggest_related_queries("古籍修复师")["related"], [])

    def test_cross_query_duplicates_keep_best_copy_and_primary_first(self):
        scraper = JobScraper()
        scraper.keywords = ["AI产品助理", "AI产品运营"]
        scraper.primary_keyword = "AI产品助理"
        jobs = [
            {"job_id": "1", "source": "51前程无忧", "title": "AI产品运营", "company": "甲", "location": "广州", "keyword": "AI产品运营"},
            {"job_id": "2", "source": "51前程无忧", "title": "AI产品助理", "company": "乙", "location": "广州", "keyword": "AI产品助理"},
            {"job_id": "1", "source": "51前程无忧", "title": "AI产品运营", "company": "甲", "location": "广州", "keyword": "AI产品助理"},
        ]
        result = scraper._deduplicate_and_rank(jobs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "AI产品助理")
        self.assertEqual(result[0]["relation_type"], "primary")
        self.assertEqual(result[1]["keyword"], "AI产品助理")

    def test_content_key_deduplicates_jobs_without_source_id(self):
        scraper = JobScraper()
        scraper.keywords = ["内容运营"]
        scraper.primary_keyword = "内容运营"
        duplicate = {"source": "示例", "title": "内容运营", "company": "甲", "location": "广州", "keyword": "内容运营"}
        self.assertEqual(len(scraper._deduplicate_and_rank([duplicate, dict(duplicate)])), 1)


if __name__ == "__main__":
    unittest.main()
