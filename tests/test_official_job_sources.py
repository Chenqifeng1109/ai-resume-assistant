"""权威官方开放招聘源（国聘、国家24365、美团）适配器与调度集成测试。"""

import json
import unittest
from unittest.mock import patch

from modules.job_sources import list_source_capabilities, resolve_sources
from modules.official_job_sources import (
    OFFICIAL_ADAPTERS,
    OfficialSourceError,
    collect_official_jobs,
    list_official_source_codes,
)


class _FakeHttpResponse:
    def __init__(self, payload):
        self._bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._bytes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeOpener:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def open(self, req, timeout=None):
        self.calls.append((req.full_url, timeout))
        if not self._responses:
            return _FakeHttpResponse({})
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return _FakeHttpResponse(next_item)


class OfficialJobSourcesTests(unittest.TestCase):
    def test_registry_and_job_sources_expose_three_official_sources(self):
        self.assertEqual(
            list_official_source_codes(),
            (
                "sasac",
                "ncss",
                "iguopin",
                "nowcoder",
                "meituan",
                "tencent",
                "netease",
                "jd",
                "baidu",
                "mihoyo",
                "iflytek",
                "wuxiapptec",
                "mindray",
                "mengniu",
                "vivo",
            ),
        )
        resolved = resolve_sources(["国聘", "24365", "美团"])
        self.assertEqual([item.code for item in resolved], ["iguopin", "ncss", "meituan"])

        caps = {item["code"]: item for item in list_source_capabilities()}
        for code in ("iguopin", "ncss", "meituan"):
            self.assertTrue(caps[code]["can_attempt_search"])
            self.assertEqual(caps[code]["access_mode"], "official_http")
            self.assertEqual(caps[code]["session_status"], "not_required")
            self.assertTrue(caps[code]["official_entry"].startswith("https://"))

    def test_iguopin_parses_fields_and_filters_wrong_city(self):
        opener = _FakeOpener(
            [
                {
                    "code": 200,
                    "data": {
                        "list": [
                            {
                                "job_id": "ig_101",
                                "job_name": "财务分析专员",
                                "company_name": "中国某央企集团",
                                "district_list": [{"area_cn": "广州市"}],
                                "min_wage": 10000,
                                "max_wage": 15000,
                                "education_cn": "本科",
                                "experience_cn": "1-3年",
                                "recruitment_type_cn": "社会招聘",
                                "contents": "<p>负责月度财务报表分析</p><br/>熟练使用Excel",
                            },
                            {
                                "job_id": "ig_102",
                                "job_name": "财务分析专员",
                                "company_name": "异地分公司",
                                "district_list": [{"area_cn": "上海市"}],
                                "contents": "仅限上海",
                            },
                        ]
                    },
                }
            ]
        )
        jobs = collect_official_jobs("iguopin", ["财务"], "广州", opener=opener)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], "iguopin_ig_101")
        self.assertEqual(jobs[0]["salary"], "10.0k-15.0k")
        self.assertIn("负责月度财务报表分析", jobs[0]["description"])
        self.assertNotIn("<p>", jobs[0]["description"])
        self.assertEqual(jobs[0]["url"], "https://www.iguopin.com/job/detail?id=ig_101")

    def test_ncss_parses_salary_and_filters_city(self):
        opener = _FakeOpener(
            [
                {
                    "flag": True,
                    "data": {
                        "list": [
                            {
                                "jobId": "nc_201",
                                "jobName": "客户运营专员",
                                "recName": "中邮消费金融有限公司",
                                "areaCodeName": "广州市",
                                "lowMonthPay": 10.0,
                                "highMonthPay": 15.0,
                                "degreeName": "本科及以上",
                                "major": "金融 市场营销",
                                "recProperty": "国有企业",
                                "recScale": "1000人以上",
                            },
                            {
                                "jobId": "nc_202",
                                "jobName": "客户运营专员",
                                "recName": "异地公司",
                                "areaCodeName": "北京市",
                            },
                        ]
                    },
                }
            ]
        )
        jobs = collect_official_jobs("ncss", ["运营"], "广州", opener=opener)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], "ncss_nc_201")
        self.assertEqual(jobs[0]["salary"], "10k-15k")
        self.assertIn("国有企业", jobs[0]["description"])
        self.assertEqual(jobs[0]["url"], "https://www.ncss.cn/student/jobs/nc_201/detail.html")

    def test_meituan_parses_multi_city_and_deduplicates(self):
        item = {
            "jobUnionId": "mt_301",
            "name": "零售运营经理",
            "cityList": [{"name": "北京市"}, {"name": "广州市"}],
            "department": [{"name": "小象超市"}],
            "jobFamily": "运营类",
            "jobDuty": "负责广州大区商品运营与增长",
            "jobRequirement": "3年以上零售运营经验",
        }
        opener = _FakeOpener(
            [
                {"data": {"list": [item, item]}},
            ]
        )
        jobs = collect_official_jobs("meituan", ["运营"], "广州", opener=opener)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "美团 · 小象超市")
        self.assertIn("广州市", jobs[0]["location"])
        self.assertIn("【岗位职责】", jobs[0]["description"])

    def test_stop_check_aborts_before_network_call(self):
        opener = _FakeOpener([])
        with self.assertRaises(OfficialSourceError) as ctx:
            collect_official_jobs(
                "meituan",
                ["产品经理"],
                "广州",
                stop_check=lambda: "cancelled",
                opener=opener,
            )
        self.assertEqual(ctx.exception.code, "cancelled")
        self.assertEqual(len(opener.calls), 0)

    def test_timeout_error_is_classified(self):
        opener = _FakeOpener([TimeoutError("timed out")])
        with self.assertRaises(OfficialSourceError) as ctx:
            collect_official_jobs("iguopin", ["产品经理"], "广州", opener=opener)
        self.assertEqual(ctx.exception.code, "TIMEOUT")
        self.assertIn("超时", ctx.exception.message)


    def test_rank_and_filter_jobs_by_relevance_prioritizes_primary_and_drops_noise(self):
        from modules.official_job_sources import rank_and_filter_jobs_by_relevance

        jobs = [
            {"job_id": "1", "title": "前台行政专员", "description": "负责接待与考勤"},
            {"job_id": "2", "title": "物业电工维修", "description": "负责大楼电路检修"},
            {"job_id": "3", "title": "Python服务端开发工程师", "description": "负责FastAPI微服务"},
            {"job_id": "4", "title": "高级后端开发工程师", "description": "负责高并发系统架构"},
            {"job_id": "5", "title": "Java后端研发", "description": "负责订单中心"},
            {"job_id": "6", "title": "Go后端开发", "description": "负责网关"},
            {"job_id": "7", "title": "系统研发工程师", "description": "后端平台建设"},
            {"job_id": "8", "title": "后端开发实习生", "description": "协助接口开发"},
            {"job_id": "9", "title": "服务端架构师", "description": "高可用系统"},
            {"job_id": "10", "title": "Python开发工程师", "description": "接口研发"},
        ]
        ranked = rank_and_filter_jobs_by_relevance(
            jobs, ["后端开发", "Python开发", "服务端开发"], min_keep=8
        )
        titles = [j["title"] for j in ranked]
        self.assertEqual(len(ranked), 8)
        self.assertNotIn("前台行政专员", titles)
        self.assertNotIn("物业电工维修", titles)
        self.assertIn("后端开发", ranked[0]["title"])
        self.assertEqual(ranked[0]["keyword_tier"], "primary")
        self.assertEqual(ranked[0]["relevance_level"], "high")


    def test_new_bigtech_adapters_parse_city_and_official_urls(self):
        from modules.official_job_sources import JdAdapter, NetEaseAdapter, TencentAdapter

        # Tencent
        t_adapter = TencentAdapter()
        self.assertEqual(t_adapter.meta.category, "company_official")
        t_job = t_adapter.parse_item(
            {
                "PostId": "2109972739128471552",
                "RecruitPostName": "AI协作工具高级产品经理",
                "LocationName": "北京",
                "BGName": "CSIG",
                "ProductName": "腾讯文档",
                "CategoryName": "产品",
                "Responsibility": "负责AI产品规划与落地",
                "RequireWorkYearsName": "三年以上工作经验",
                "PostURL": "http://careers.tencent.com/jobdesc.html?postId=2109972739128471552",
            },
            "产品",
            "北京",
            "primary",
        )
        self.assertIsNotNone(t_job)
        self.assertEqual(t_job["source"], "tencent")
        self.assertEqual(t_job["url"], "https://careers.tencent.com/jobdesc.html?postId=2109972739128471552")
        self.assertIsNone(t_adapter.parse_item({"RecruitPostName": "产品", "LocationName": "深圳"}, "产品", "北京", "primary"))

        # NetEase
        n_adapter = NetEaseAdapter()
        self.assertEqual(n_adapter.meta.category, "company_official")
        n_job = n_adapter.parse_item(
            {
                "id": 77770,
                "name": "AI策略产品经理",
                "workPlaceNameList": ["北京市"],
                "firstDepName": "云音乐事业部",
                "description": "负责音乐推荐策略",
                "requirement": "熟悉SQL与数据分析",
                "reqEducationName": "本科",
            },
            "产品",
            "北京",
            "primary",
        )
        self.assertIsNotNone(n_job)
        self.assertEqual(n_job["source"], "netease")
        self.assertEqual(n_job["url"], "https://hr.163.com/job-detail.html?id=77770")
        self.assertIn("熟悉SQL", n_job["description"])

        # JD
        j_adapter = JdAdapter()
        self.assertEqual(j_adapter.meta.category, "company_official")
        j_job = j_adapter.parse_item(
            {
                "id": 183917,
                "positionId": 227954,
                "positionName": "产品运营经理",
                "positionDeptName": "京东零售",
                "workCity": "北京市",
                "workContent": "负责核心频道促活与留存",
                "qualification": "3年以上运营经验",
                "jobType": "运营类",
                "formatPublishTime": "2026-11-23",
            },
            "产品运营",
            "北京",
            "primary",
        )
        self.assertIsNotNone(j_job)
        self.assertEqual(j_job["source"], "jd")
        self.assertEqual(j_job["url"], "https://zhaopin.jd.com/web/job/job_info_list/3?positionId=227954")
        self.assertIn("京东零售", j_job["company"])


    def test_sasac_nowcoder_baidu_mihoyo_and_beisen_adapters(self):
        from modules.official_job_sources import (
            BaiduAdapter,
            MihoyoAdapter,
            NowcoderAdapter,
            OFFICIAL_ADAPTERS,
            SasacAdapter,
        )

        # SASAC
        sasac = SasacAdapter()
        s_job = sasac.parse_item(
            {"title": "国务院国资委委属单位2026年面向社会公开招聘公告", "url": "http://www.sasac.gov.cn/c1/content.html", "posted_at": "2026-07-31"},
            "产品",
            "北京",
            "primary",
        )
        self.assertEqual(s_job["source"], "sasac")
        self.assertEqual(s_job["location"], "全国")

        # Nowcoder
        nc = NowcoderAdapter()
        nc_job = nc.parse_item(
            {
                "data": {
                    "id": 340673,
                    "jobName": "初级产品经理",
                    "jobCityList": ["北京"],
                    "salaryMin": 22,
                    "salaryMax": 28,
                    "salaryMonth": 15,
                    "recommendInternCompany": {"companyName": "示例科技", "industryTagNameList": ["互联网"]},
                    "ext": '{"infos": "负责需求分析", "requirements": "熟悉SQL"}',
                }
            },
            "产品",
            "北京",
            "primary",
        )
        self.assertEqual(nc_job["salary"], "22-28K·15薪")
        self.assertEqual(nc_job["url"], "https://www.nowcoder.com/jobs/detail/340673")

        # Baidu
        bd = BaiduAdapter()
        bd_job = bd.parse_item(
            {"name": "AI产品经理", "workPlace": "北京市", "bgShortName": "MEG", "postId": "abc-1", "workContent": "负责大模型产品"},
            "产品",
            "北京",
            "primary",
        )
        self.assertEqual(bd_job["source"], "baidu")
        self.assertIn("talent.baidu.com", bd_job["url"])

        # miHoYo
        mh = MihoyoAdapter()
        mh_job = mh.parse_item(
            {"id": "5629", "title": "系统策划", "addressDetailList": [{"addressDetail": "上海"}], "competencyType": "策划"},
            "策划",
            "上海",
            "primary",
        )
        self.assertEqual(mh_job["source"], "mihoyo")
        self.assertEqual(mh_job["url"], "https://jobs.mihoyo.com/#/position/5629")

        # Beisen (iFlytek)
        xf = OFFICIAL_ADAPTERS["iflytek"]
        xf_job = xf.parse_item(
            {"JobAdId": 190876166, "JobAdName": "AI产品经理-北京", "LocNames": ["北京市"], "Duty": "负责大模型落地", "Require": "3年经验"},
            "产品",
            "北京",
            "primary",
        )
        self.assertEqual(xf_job["source"], "iflytek")
        self.assertEqual(xf_job["url"], "https://iflytek.zhiye.com/zpdetail/190876166")

    def test_sasac_preserved_and_server_side_city_filters_work(self):
        from modules.official_job_sources import (
            BaiduAdapter,
            IguopinAdapter,
            JdAdapter,
            NcssAdapter,
            NowcoderAdapter,
            is_province_level_match,
            rank_and_filter_jobs_by_relevance,
        )

        # 1. Unrelated SASAC announcements must be filtered out instead of polluting targeted searches
        strong_jobs = [
            {"job_id": f"s_{i}", "source": "nowcoder", "title": f"Python后端开发工程师{i}", "description": "高并发服务"}
            for i in range(10)
        ]
        sasac_jobs = [
            {"job_id": f"sa_{i}", "source": "sasac", "title": f"中国航空器材集团2026年公开招聘公告{i}", "description": "官方央企招聘"}
            for i in range(6)
        ]
        ranked = rank_and_filter_jobs_by_relevance(strong_jobs + sasac_jobs, ["后端开发"], min_keep=8)
        sasac_kept = [j for j in ranked if j.get("source") == "sasac"]
        self.assertEqual(len(sasac_kept), 0)
        self.assertEqual(ranked[0]["source"], "nowcoder")

        # 2. Province-level matching accepts same province only, rejects other cities/provinces
        self.assertTrue(is_province_level_match("广东", "广州"))
        self.assertTrue(is_province_level_match("广东省", "深圳"))
        self.assertTrue(is_province_level_match("浙江", "杭州"))
        self.assertFalse(is_province_level_match("深圳市", "广州"))
        self.assertFalse(is_province_level_match("北京市", "广州"))

        # 3. Capture exact HTTP payloads for server-side city parameters
        captured = []

        class _InspectOpener:
            def __init__(self, resp_payload):
                self._resp = resp_payload

            def open(self, req, timeout=None):
                body = req.data.decode("utf-8", errors="replace") if req.data else ""
                captured.append((req.full_url, body))
                return _FakeHttpResponse(self._resp)

        # iguopin sends hierarchical district code for 杭州
        IguopinAdapter().fetch_raw_items("产品", "杭州", 1, 15, _InspectOpener({"data": {"list": []}}), 5)
        self.assertIn("000000.330000.330100", captured[-1][1])

        # ncss sends areaCode=330100 for 杭州 and accepts province-level areaCodeName="浙江"
        NcssAdapter().fetch_raw_items("产品", "杭州", 1, 15, _InspectOpener({"data": {"list": []}}), 5)
        self.assertIn("areaCode=330100", captured[-1][0])
        ncss_job = NcssAdapter().parse_item(
            {"jobId": "hz1", "jobName": "产品运营", "recName": "浙企集团", "areaCodeName": "浙江"},
            "产品",
            "杭州",
            "primary",
        )
        self.assertIsNotNone(ncss_job)
        self.assertEqual(ncss_job["location"], "浙江·杭州")

        # jd sends 2-digit province code ["51"] for 成都 and accepts workCity="四川省"
        JdAdapter().fetch_raw_items("运营", "成都", 1, 15, _InspectOpener([]), 5)
        self.assertIn("workCityJson=%5B%2251%22%5D", captured[-1][1])
        jd_job = JdAdapter().parse_item(
            {"id": 9, "positionName": "零售运营", "workCity": "四川省"},
            "运营",
            "成都",
            "primary",
        )
        self.assertIsNotNone(jd_job)
        self.assertIn("成都同省", jd_job["location"])

        # nowcoder sends jobCity=["成都"]
        NowcoderAdapter().fetch_raw_items("Java", "成都", 1, 15, _InspectOpener({"code": 0, "data": {"datas": []}}), 5)
        self.assertIn('"jobCity": ["成都"]', captured[-1][1])

        # baidu sends city + keyword
        BaiduAdapter().fetch_raw_items("算法", "武汉", 1, 15, _InspectOpener({"status": "ok", "data": {"list": [{"name": "x"}]}}), 5)
        self.assertIn("%E6%AD%A6%E6%B1%89", captured[-1][1])

        # meituan sends plural "keywords" and multi-city location matching works
        from modules.official_job_sources import MeituanAdapter, official_location_matches_city

        MeituanAdapter().fetch_raw_items("产品运营", "深圳", 1, 15, _InspectOpener({"data": {"list": []}}), 5)
        self.assertIn('"keywords": "产品运营"', captured[-1][1])
        self.assertTrue(official_location_matches_city("北京市 / 上海市 / 深圳市", "深圳"))
        self.assertTrue(official_location_matches_city("广东·深圳", "深圳"))
        self.assertTrue(official_location_matches_city("广东省（深圳同省）", "深圳"))
        self.assertFalse(official_location_matches_city("北京市 / 上海市 / 杭州市", "深圳"))


if __name__ == "__main__":
    unittest.main()
