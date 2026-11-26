import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.job_sources import (
    build_official_search_handoff,
    list_source_capabilities,
    resolve_sources,
)
from modules.job_scraper import JobScraper
from routers.jobs import router
from services.job_collection import start_scrape


class JobSourceTests(unittest.TestCase):
    def test_aliases_share_one_canonical_source(self):
        result = resolve_sources(["51job", "51前程无忧", "前程无忧", " 51JOB "])
        self.assertEqual([item.code for item in result], ["51job"])

    def test_invalid_or_unimplemented_sources_rejected(self):
        for values in ([], [""], ["unknown"], ["boss"], ["BOSS直聘"], [None]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                resolve_sources(values)

    def test_unimplemented_source_never_launches_browser(self):
        scraper = JobScraper()
        with patch.object(scraper, "_launch_browser") as launch:
            with self.assertRaises(ValueError):
                scraper.search_all(["liepin"])
        launch.assert_not_called()

    def test_capabilities_do_not_claim_login_or_live_verification(self):
        sources = list_source_capabilities()
        self.assertEqual(sources[0]["verification_status"], "simulation_passed")
        self.assertEqual(sources[0]["session_status"], "unknown")
        self.assertEqual(sources[0]["city_configuration_status"], "configured_not_live_verified")
        self.assertFalse(sources[1]["can_attempt_search"])
        self.assertEqual(sources[1]["access_mode"], "manual_assist")
        self.assertEqual(sources[1]["official_entry"], "https://www.zhipin.com/")
        liepin_source = next(s for s in sources if s["code"] == "liepin")
        self.assertTrue(liepin_source["can_attempt_search"])
        self.assertEqual(liepin_source["access_mode"], "browser_use_beta")
        self.assertEqual(liepin_source["verification_status"], "not_verified")
        sources[0]["code"] = "modified"
        self.assertEqual(list_source_capabilities()[0]["code"], "51job")

    def test_source_api_and_rejected_scrape_api(self):
        app = FastAPI()
        app.include_router(router)
        with patch("services.job_collection.SCRAPER_STATUS", {"running": False}), TestClient(app) as client:
            response = client.get("/api/jobs/sources")
            self.assertEqual(response.status_code, 200)
            sources_payload = response.json()["sources"]
            self.assertEqual(len(sources_payload), 19)
            codes = {item["code"] for item in sources_payload}
            for code in ("sasac", "iguopin", "ncss", "nowcoder", "meituan", "tencent", "netease", "jd", "baidu", "mihoyo", "iflytek", "wuxiapptec", "mindray", "mengniu", "vivo", "zhilian"):
                self.assertIn(code, codes)
            resolved = resolve_sources(["国资委", "牛客", "腾讯", "网易", "京东", "百度", "科大讯飞"])
            self.assertEqual([item.code for item in resolved], ["sasac", "nowcoder", "tencent", "netease", "jd", "baidu", "iflytek"])
            response = client.post("/api/jobs/scrape", data={"platforms": "unknown"})
            self.assertEqual(response.status_code, 400)
            self.assertIn("不支持", response.json()["error"])

    def test_boss_handoff_uses_verified_guangzhou_entry_without_scraping(self):
        result = build_official_search_handoff("boss", "AI产品助理", "广州市")
        self.assertEqual(result["official_url"], "https://www.zhipin.com/guangzhou/")
        self.assertTrue(result["city_entry_verified"])
        self.assertEqual(result["search_term"], "AI产品助理")

        fallback = build_official_search_handoff("boss", "AI产品助理", "深圳")
        self.assertEqual(fallback["official_url"], "https://www.zhipin.com/")
        self.assertFalse(fallback["city_entry_verified"])

    def test_boss_handoff_api_validates_and_returns_official_entry(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post("/api/jobs/sources/search-handoff", json={
                "source": "boss", "position": "AI产品助理", "city": "广州",
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["official_url"], "https://www.zhipin.com/guangzhou/")
            rejected = client.post("/api/jobs/sources/search-handoff", json={
                "source": "51job", "position": "AI产品助理", "city": "广州",
            })
            self.assertEqual(rejected.status_code, 400)


class JobCollectionConflictTests(unittest.IsolatedAsyncioTestCase):
    async def test_scrape_and_login_conflicts_have_different_messages(self):
        with patch("services.job_collection.SCRAPER_STATUS", {"running": True}), patch(
            "services.job_collection.login_manager.active", return_value=False
        ):
            result = await start_scrape()
        self.assertEqual(result["error_code"], "CONFLICT")
        self.assertIn("岗位采集任务", result["error"])

        with patch("services.job_collection.SCRAPER_STATUS", {"running": False}), patch(
            "services.job_collection.login_manager.active", return_value=True
        ):
            result = await start_scrape()
        self.assertEqual(result["error_code"], "CONFLICT")
        self.assertIn("保存或取消登录", result["error"])
        self.assertNotIn("采集任务正在进行", result["error"])

    async def test_unsupported_city_is_rejected_before_resume_or_browser_work(self):
        with patch("services.job_collection.SCRAPER_STATUS", {"running": False}), patch(
            "services.job_collection.login_manager.active", return_value=False
        ):
            result = await start_scrape(
                resume_file="missing.json",
                target_position="AI产品助理",
                target_city="火星城",
            )
        self.assertEqual(result["error_code"], "INVALID_INPUT")
        self.assertEqual(result["field"], "target_city")
        self.assertIn("尚未配置城市", result["error"])


if __name__ == "__main__":
    unittest.main()
