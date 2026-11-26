import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from reportlab.pdfgen import canvas

import modules.resume_parser as resume_parser
from modules.resume_schema import validate_resume_payload


class ResumeD7BaselineTests(unittest.TestCase):
    def test_01_standard_txt_preserves_raw_text(self):
        resume_text = (
            "陈晨\n"
            "电话：13800138000 | 邮箱：chenchen@example.com\n"
            "求职意向\nAI产品助理\n"
            "专业技能\nPython、SQL"
        )
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "standard.txt"
            file_path.write_text(resume_text, encoding="utf-8")

            with patch.object(
                resume_parser,
                "extract_resume_info",
                return_value={
                    "name": "陈晨",
                    "phone": "13800138000",
                    "email": "chenchen@example.com",
                    "desired_position": "AI产品助理",
                    "skills": ["Python", "SQL"],
                },
            ):
                result = resume_parser.parse_resume(str(file_path))

        self.assertEqual(result["raw_text"], resume_text)
        self.assertEqual(result["source_file"], "standard.txt")

    def test_02_alias_headings_map_to_standard_modules(self):
        resume_text = (
            "求职目标\nAI产品助理\n"
            "实习经验\n某科技公司 产品实习生\n"
            "项目案例\n智能问答助手\n"
            "所获荣誉\n校级一等奖"
        )

        normalized = resume_parser.normalize_resume_section_headings(resume_text)

        self.assertIn("[简历模块:desired_position；原标题:求职目标]", normalized)
        self.assertIn("[简历模块:work_experience；原标题:实习经验]", normalized)
        self.assertIn("[简历模块:project_experience；原标题:项目案例]", normalized)
        self.assertIn("[简历模块:awards；原标题:所获荣誉]", normalized)

    def test_03_headingless_txt_keeps_original_content(self):
        resume_text = (
            "李青，广州，联系电话13800138001。\n"
            "2025年在某公司担任运营实习生，负责整理用户反馈。"
        )

        normalized = resume_parser.normalize_resume_section_headings(resume_text)

        self.assertEqual(normalized, resume_text)
        self.assertNotIn("[简历模块:", normalized)

    def test_04_docx_paragraph_layout_is_readable(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "paragraph-layout.docx"
            document = Document()
            document.add_heading("个人信息", level=1)
            document.add_paragraph("姓名：周岚")
            document.add_heading("教育背景", level=1)
            document.add_paragraph("示例学院 大数据技术")
            document.save(file_path)

            text = resume_parser.read_docx(str(file_path))

        self.assertIn("姓名：周岚", text)
        self.assertIn("示例学院 大数据技术", text)

    def test_05_docx_table_layout_is_readable(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "table-layout.docx"
            document = Document()
            table = document.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "姓名"
            table.cell(0, 1).text = "林川"
            table.cell(1, 0).text = "项目经历"
            table.cell(1, 1).text = "校园招聘数据看板"
            document.save(file_path)

            text = resume_parser.read_docx(str(file_path))

        self.assertIn("姓名", text)
        self.assertIn("林川", text)
        self.assertIn("校园招聘数据看板", text)

    def test_06_multipage_pdf_combines_all_pages(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "multipage.pdf"
            pdf = canvas.Canvas(str(file_path))
            pdf.drawString(72, 720, "Name: Demo Candidate")
            pdf.showPage()
            pdf.drawString(72, 720, "Project: Offer Analysis")
            pdf.save()

            text = resume_parser.read_pdf(str(file_path))

        self.assertIn("Name: Demo Candidate", text)
        self.assertIn("Project: Offer Analysis", text)

    def test_07_missing_optional_sections_become_empty_lists(self):
        result = validate_resume_payload(
            {
                "name": "许宁",
                "phone": "13800138002",
                "email": "",
                "desired_position": "产品助理",
                "skills": ["需求分析"],
            }
        )

        self.assertEqual(result["awards"], [])
        self.assertEqual(result["certificates"], [])
        self.assertEqual(result["practical_experience"], [])
        self.assertEqual(result["quality_status"], "complete")

    def test_08_missing_critical_fields_create_review_warnings(self):
        result = validate_resume_payload(
            {
                "name": "",
                "phone": "",
                "email": "",
                "desired_position": "",
                "skills": [],
            }
        )

        warning_codes = {item["code"] for item in result["quality_warnings"]}
        self.assertEqual(result["quality_status"], "needs_review")
        self.assertEqual(
            warning_codes,
            {
                "MISSING_NAME",
                "MISSING_CONTACT",
                "MISSING_DESIRED_POSITION",
                "MISSING_SKILLS",
            },
        )

    def test_09_empty_txt_stops_before_ai_call(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "empty.txt"
            file_path.write_text(" \n\t", encoding="utf-8")

            with patch.object(resume_parser, "extract_resume_info") as extract_info:
                result = resume_parser.parse_resume(str(file_path))

        self.assertEqual(result, {"error": "简历文件内容为空"})
        extract_info.assert_not_called()

    def test_10_damaged_docx_returns_read_error(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "damaged.docx"
            file_path.write_bytes(b"not-a-valid-docx")

            result = resume_parser.parse_resume(str(file_path))

        self.assertIn("error", result)
        self.assertTrue(result["error"].startswith("<Word文件读取失败:"))


if __name__ == "__main__":
    unittest.main()
