import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api_responses import register_api_exception_handlers
from routers.matching import router
from services.job_matching import match_jd


class JDMatchAnalysisIntegrationTests(unittest.TestCase):
    def test_single_match_analyzes_jd_before_scoring(self):
        jd_text = "招聘AI产品助理，负责需求整理，要求熟悉SQL。"
        analysis = {
            "job_title": {
                "value": "AI产品助理",
                "evidence": jd_text,
                "line_number": 1,
            },
            "responsibilities": [],
            "hard_skills": [],
            "soft_skills": [],
            "keywords": [],
            "hard_thresholds": [],
            "preferred_qualifications": [],
            "quality_status": "evidence_checked",
            "quality_warnings": [],
        }
        score_result = {
            "ok": True,
            "overall_score": 80,
            "skill_match": 80,
            "experience_match": 75,
            "education_match": 85,
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "verdict": "值得投递",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            resume_file = "resume_demo.json"
            profile = {"name": "测试用户", "skills": ["SQL"]}
            with open(
                os.path.join(temp_dir, resume_file),
                "w",
                encoding="utf-8",
            ) as target:
                json.dump(profile, target, ensure_ascii=False)

            with (
                patch("services.job_matching.DATA_DIR", temp_dir),
                patch(
                    "services.job_matching.analyze_jd",
                    return_value={"ok": True, "analysis": analysis},
                ) as analyzer,
                patch(
                    "services.job_matching.match_resume_to_jd",
                    return_value=score_result,
                ) as matcher,
            ):
                result = match_jd(resume_file, jd_text)

        analyzer.assert_called_once_with(jd_text)
        matcher.assert_called_once_with(profile, jd_text, analysis)
        self.assertEqual(result["jd_analysis"], analysis)
        self.assertEqual(result["overall_score"], 80)

    def test_analysis_failure_stops_matching(self):
        jd_text = "招聘AI产品助理，负责需求整理，要求熟悉SQL。"
        analysis_error = {
            "ok": False,
            "error": "AI响应解析失败：JD分析结果不是有效JSON。",
            "error_code": "UPSTREAM_ERROR",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            resume_file = "resume_demo.json"
            with open(
                os.path.join(temp_dir, resume_file),
                "w",
                encoding="utf-8",
            ) as target:
                json.dump({"name": "测试用户"}, target, ensure_ascii=False)

            with (
                patch("services.job_matching.DATA_DIR", temp_dir),
                patch(
                    "services.job_matching.analyze_jd",
                    return_value=analysis_error,
                ),
                patch("services.job_matching.match_resume_to_jd") as matcher,
            ):
                result = match_jd(resume_file, jd_text)

        self.assertEqual(result, analysis_error)
        matcher.assert_not_called()


class JDMatchAnalysisRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        register_api_exception_handlers(app)
        app.include_router(router)
        self.client = TestClient(app)

    @patch("routers.matching.match_jd_service")
    def test_match_endpoint_returns_jd_analysis(self, match_service):
        match_service.return_value = {
            "ok": True,
            "overall_score": 80,
            "jd_analysis": {
                "job_title": None,
                "responsibilities": [],
                "hard_skills": [],
                "soft_skills": [],
                "keywords": [],
                "hard_thresholds": [],
                "preferred_qualifications": [],
                "quality_status": "evidence_checked",
                "quality_warnings": [],
            },
        }

        response = self.client.post(
            "/api/jd/match",
            data={"resume_file": "resume_demo.json", "jd_text": "有效岗位描述原文"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("jd_analysis", response.json())

    @patch("routers.matching.match_jd_service")
    def test_match_endpoint_maps_analysis_failure_to_502(self, match_service):
        match_service.return_value = {
            "ok": False,
            "error": "AI响应解析失败：JD分析结果不是有效JSON。",
            "error_code": "UPSTREAM_ERROR",
        }

        response = self.client.post(
            "/api/jd/match",
            data={"resume_file": "resume_demo.json", "jd_text": "有效岗位描述原文"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error_code"], "UPSTREAM_ERROR")


if __name__ == "__main__":
    unittest.main()
