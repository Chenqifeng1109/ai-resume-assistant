import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.resume_parser import save_parsed_result
from modules.resume_schema import validate_resume_payload


def valid_resume_payload():
    return {
        "name": "张三",
        "phone": "13800138000",
        "email": "",
        "desired_position": "AI产品助理",
        "skills": ["Python"],
    }


class ResumeSchemaTests(unittest.TestCase):
    def test_valid_payload_gets_defaults_without_quality_warning(self):
        result = validate_resume_payload(valid_resume_payload())

        self.assertEqual(result["quality_status"], "complete")
        self.assertEqual(result["quality_warnings"], [])
        self.assertEqual(result["awards"], [])
        self.assertEqual(result["work_experience"], [])

    def test_missing_none_and_wrong_list_values_are_normalized(self):
        payload = valid_resume_payload()
        payload["awards"] = None
        payload["certificates"] = "无"

        result = validate_resume_payload(payload)

        self.assertEqual(result["awards"], [])
        self.assertEqual(result["certificates"], [])
        self.assertEqual(result["quality_status"], "needs_review")
        self.assertEqual(
            [item["field"] for item in result["quality_warnings"]],
            ["certificates"],
        )
        self.assertEqual(
            result["quality_warnings"][0]["code"],
            "AI_FIELD_TYPE_NORMALIZED",
        )

    def test_missing_critical_fields_create_specific_warnings(self):
        result = validate_resume_payload(
            {
                "name": "   ",
                "phone": "",
                "email": "",
                "desired_position": "",
                "skills": [],
            }
        )

        self.assertEqual(result["quality_status"], "needs_review")
        self.assertEqual(
            {item["code"] for item in result["quality_warnings"]},
            {
                "MISSING_NAME",
                "MISSING_CONTACT",
                "MISSING_DESIRED_POSITION",
                "MISSING_SKILLS",
            },
        )

    def test_invalid_nested_item_returns_chinese_field_error(self):
        payload = valid_resume_payload()
        payload["work_experience"] = [
            {
                "company": "示例公司",
                "position": ["错误类型"],
            }
        ]

        result = validate_resume_payload(payload)

        self.assertEqual(result["error_code"], "RESUME_SCHEMA_INVALID")
        self.assertIn("工作/实习经历 > 第1项 > 职位", result["error"])
        self.assertEqual(
            result["validation_errors"][0]["type"],
            "string_type",
        )
        self.assertNotIn("input", result["validation_errors"][0])

    def test_non_object_ai_result_returns_stable_error(self):
        result = validate_resume_payload("not-json-object")

        self.assertEqual(result["error_code"], "RESUME_SCHEMA_INVALID")
        self.assertIn("最外层必须是结构化对象", result["error"])

    def test_validated_quality_result_is_preserved_in_sqlite(self):
        result = validate_resume_payload(
            {
                "name": "张三",
                "phone": "",
                "email": "",
                "desired_position": "AI产品助理",
                "skills": ["Python"],
            }
        )
        result.update(
            {
                "parsed_at": "2026-07-27 03:00:00",
                "source_file": "resume.txt",
                "raw_text": "姓名：张三",
            }
        )

        with tempfile.TemporaryDirectory() as root:
            database_path = Path(root) / "offerforge-test.db"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE resumes (
                    filename TEXT PRIMARY KEY,
                    name TEXT,
                    phone TEXT,
                    email TEXT,
                    parsed_data TEXT
                )
                """
            )
            connection.close()

            with patch(
                "modules.db_client.get_connection",
                side_effect=lambda: sqlite3.connect(database_path),
            ):
                save_parsed_result(result, root)

            connection = sqlite3.connect(database_path)
            stored_json = connection.execute(
                "SELECT parsed_data FROM resumes"
            ).fetchone()[0]
            connection.close()
            stored = json.loads(stored_json)

        self.assertEqual(stored["quality_status"], "needs_review")
        self.assertEqual(
            stored["quality_warnings"][0]["code"],
            "MISSING_CONTACT",
        )


if __name__ == "__main__":
    unittest.main()
