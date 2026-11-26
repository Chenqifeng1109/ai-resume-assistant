import unittest
from unittest.mock import patch

from modules.resume_parser import (
    build_field_evidence,
    extract_resume_info,
    find_value_source,
)


class FakeDeepSeekClient:
    def chat_json(self, system_prompt, analysis_text):
        return {
            "name": "张三",
            "phone": "13800138000",
            "email": "zhang@example.com",
            "desired_position": "AI产品助理",
            "skills": ["Python", "FastAPI"],
        }


class ResumeFieldEvidenceTests(unittest.TestCase):
    def test_extract_resume_info_attaches_evidence_for_five_fields(self):
        raw_text = "\n".join([
            "个人信息",
            "姓名：张三",
            "电话：13800138000",
            "邮箱：zhang@example.com",
            "求职意向：AI产品助理",
            "专业技能",
            "Python、FastAPI",
        ])

        with patch("modules.resume_parser.DeepSeekClient", return_value=FakeDeepSeekClient()):
            result = extract_resume_info(raw_text)

        self.assertEqual(
            set(result["field_evidence"]),
            {"name", "phone", "email", "desired_position", "skills"},
        )
        self.assertEqual(result["field_evidence"]["name"][0]["line_number"], 2)
        self.assertEqual(
            result["field_evidence"]["email"][0]["source_text"],
            "邮箱：zhang@example.com",
        )
        self.assertEqual(
            [item["value"] for item in result["field_evidence"]["skills"]],
            ["Python", "FastAPI"],
        )

    def test_normalized_phone_match_has_lower_confidence(self):
        evidence = build_field_evidence(
            "姓名：李四\n电话：138-0013-8000",
            {"phone": "13800138000"},
        )

        self.assertEqual(evidence["phone"][0]["line_number"], 2)
        self.assertEqual(evidence["phone"][0]["confidence"], 0.9)

    def test_value_not_found_in_raw_text_has_no_evidence(self):
        evidence = build_field_evidence(
            "技能：Python",
            {"skills": ["Python", "Docker"]},
        )

        self.assertEqual(
            [item["value"] for item in evidence["skills"]],
            ["Python"],
        )

    def test_context_slice_does_not_wrap_around_at_first_line(self):
        source = find_value_source("姓名：王五\n邮箱：wang@example.com", "王五")

        self.assertEqual(source["line_number"], 1)
        self.assertEqual(source["context"], ["姓名：王五", "邮箱：wang@example.com"])

    def test_empty_or_unsupported_value_is_ignored(self):
        self.assertIsNone(find_value_source("姓名：王五", ""))
        self.assertEqual(
            build_field_evidence("姓名：王五", {"name": {"value": "王五"}}),
            {},
        )


if __name__ == "__main__":
    unittest.main()
