import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from reportlab.pdfgen import canvas

import modules.resume_parser as resume_parser


class ResumeParserReadingTests(unittest.TestCase):
    def test_read_txt_returns_complete_text(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "resume.txt"
            expected_text = "Name: Demo\nSkills: Python"
            file_path.write_text(expected_text, encoding="utf-8")

            self.assertEqual(resume_parser.read_txt(str(file_path)), expected_text)

    def test_read_docx_includes_paragraphs_and_table_cells(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "resume.docx"
            document = Document()
            document.add_paragraph("Name: Demo")
            table = document.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "Company: OfferForge"
            table.cell(0, 1).text = "Role: AI Product Assistant"
            document.save(file_path)

            text = resume_parser.read_docx(str(file_path))

            self.assertIn("Name: Demo", text)
            self.assertIn("Company: OfferForge", text)
            self.assertIn("Role: AI Product Assistant", text)

    def test_read_pdf_combines_text_from_multiple_pages(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "resume.pdf"
            pdf = canvas.Canvas(str(file_path))
            pdf.drawString(72, 720, "Page one: Demo")
            pdf.showPage()
            pdf.drawString(72, 720, "Page two: Python")
            pdf.save()

            text = resume_parser.read_pdf(str(file_path))

            self.assertIn("Page one: Demo", text)
            self.assertIn("Page two: Python", text)

    def test_parse_resume_preserves_raw_text_without_real_ai(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "resume.txt"
            expected_text = "Name: Demo\nSkills: Python"
            file_path.write_text(expected_text, encoding="utf-8")

            with patch.object(
                resume_parser,
                "extract_resume_info",
                return_value={"name": "Demo", "skills": ["Python"]},
            ) as extract_info:
                result = resume_parser.parse_resume(str(file_path))

            self.assertEqual(extract_info.call_args.args[0], expected_text)
            self.assertEqual(result["raw_text"], expected_text)
            self.assertEqual(result["source_file"], "resume.txt")

    def test_empty_pdf_returns_error_before_ai_analysis(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = Path(root) / "empty.pdf"
            pdf = canvas.Canvas(str(file_path))
            pdf.showPage()
            pdf.save()

            with patch.object(resume_parser, "extract_resume_info") as extract_info:
                result = resume_parser.parse_resume(str(file_path))

            self.assertEqual(result, {"error": "简历文件内容为空"})
            extract_info.assert_not_called()

    def test_read_txt_returns_error_marker_for_missing_file(self):
        result = resume_parser.read_txt("D:/missing-resume-for-d2-test.txt")

        self.assertTrue(result.startswith("<TXT文件读取失败:"))


if __name__ == "__main__":
    unittest.main()
