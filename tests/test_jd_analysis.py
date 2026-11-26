import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.jd_analysis import analyze_jd


def _fake_response(payload):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(payload, ensure_ascii=False)
                )
            )
        ]
    )


class JDAnalysisTests(unittest.TestCase):
    def _analyze(self, jd_text, payload):
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _fake_response(payload)
        with patch("modules.jd_analysis.client", fake_client):
            result = analyze_jd(jd_text)
        return result, fake_client

    def test_analysis_keeps_evidence_and_computes_line_numbers(self):
        jd_text = "\n".join(
            [
                "招聘AI产品助理",
                "负责整理AI产品需求",
                "熟悉Kimi、Claude和SQL",
                "具备良好的沟通能力",
                "大专及以上学历",
                "有RAG项目经验者优先",
            ]
        )
        payload = {
            "job_title": {"value": "AI产品助理", "evidence": "招聘AI产品助理"},
            "responsibilities": [
                {"value": "整理AI产品需求", "evidence": "负责整理AI产品需求"}
            ],
            "hard_skills": [
                {"value": "Kimi", "evidence": "熟悉Kimi、Claude和SQL"},
                {"value": "Claude", "evidence": "熟悉Kimi、Claude和SQL"},
                {"value": "SQL", "evidence": "熟悉Kimi、Claude和SQL"},
            ],
            "soft_skills": [
                {"value": "沟通能力", "evidence": "具备良好的沟通能力"}
            ],
            "keywords": [
                {"value": "AI产品助理", "evidence": "招聘AI产品助理"}
            ],
            "hard_thresholds": [
                {
                    "value": "大专及以上学历",
                    "evidence": "大专及以上学历",
                    "required": True,
                }
            ],
            "preferred_qualifications": [
                {
                    "value": "RAG项目经验",
                    "evidence": "有RAG项目经验者优先",
                    "required": False,
                }
            ],
        }

        result, fake_client = self._analyze(jd_text, payload)

        self.assertTrue(result["ok"])
        analysis = result["analysis"]
        self.assertEqual(analysis["job_title"]["line_number"], 1)
        self.assertEqual(
            [item["value"] for item in analysis["hard_skills"]],
            ["Kimi", "Claude", "SQL"],
        )
        self.assertEqual(analysis["hard_skills"][0]["line_number"], 3)
        self.assertTrue(analysis["hard_thresholds"][0]["required"])
        self.assertFalse(analysis["preferred_qualifications"][0]["required"])
        self.assertEqual(analysis["quality_status"], "evidence_checked")
        messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")

    def test_preferred_word_moves_requirement_out_of_hard_thresholds(self):
        jd_text = "有Dify使用经验者加分"
        payload = {
            "hard_thresholds": [
                {
                    "value": "Dify使用经验",
                    "evidence": "有Dify使用经验者加分",
                    "required": True,
                }
            ]
        }

        result, _ = self._analyze(jd_text, payload)

        self.assertEqual(result["analysis"]["hard_thresholds"], [])
        preferred = result["analysis"]["preferred_qualifications"]
        self.assertEqual(preferred[0]["value"], "Dify使用经验")
        self.assertFalse(preferred[0]["required"])

    def test_value_without_source_evidence_is_removed_with_warning(self):
        jd_text = "熟悉Excel"
        payload = {
            "hard_skills": [
                {"value": "Excel", "evidence": "熟悉Excel"},
                {"value": "Python", "evidence": "熟悉Python"},
            ]
        }

        result, _ = self._analyze(jd_text, payload)

        self.assertEqual(
            [item["value"] for item in result["analysis"]["hard_skills"]],
            ["Excel"],
        )
        self.assertEqual(result["analysis"]["quality_status"], "needs_review")
        self.assertEqual(
            result["analysis"]["quality_warnings"][0]["code"],
            "JD_EVIDENCE_NOT_FOUND",
        )

    def test_requirement_cannot_add_years_missing_from_evidence(self):
        jd_text = "有直播运营经验者优先"
        payload = {
            "preferred_qualifications": [
                {
                    "value": "3年直播运营经验",
                    "evidence": "有直播运营经验者优先",
                    "required": False,
                }
            ]
        }

        result, _ = self._analyze(jd_text, payload)

        self.assertEqual(result["analysis"]["preferred_qualifications"], [])
        self.assertEqual(
            result["analysis"]["quality_warnings"][0]["code"],
            "JD_VALUE_NOT_SUPPORTED",
        )

    def test_invalid_ai_json_returns_upstream_error(self):
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))]
        )

        with patch("modules.jd_analysis.client", fake_client):
            result = analyze_jd("这是一段长度足够的岗位描述原文")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "UPSTREAM_ERROR")


if __name__ == "__main__":
    unittest.main()
