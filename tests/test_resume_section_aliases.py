import unittest
from unittest.mock import patch

import modules.resume_parser as resume_parser


class ResumeSectionAliasTests(unittest.TestCase):
    def test_common_heading_aliases_are_normalized_to_standard_modules(self):
        resume_text = """个人信息
张三 13800138000
教育背景：
2022-2025 示例大学
实习经历
2024 示例公司 产品实习生
个人实践
2023 社区志愿服务
项目经验
OfferForge
校园经历
学生会宣传部
科研经历
推荐系统研究
专业技能
Python、FastAPI
荣誉奖项
校级一等奖学金
资格证书
CET-6
语言能力
英语六级
兴趣爱好
摄影
个人简介
学习能力强"""

        normalized = resume_parser.normalize_resume_section_headings(resume_text)

        self.assertIn("[简历模块:basic_info；原标题:个人信息]", normalized)
        self.assertIn("[简历模块:education；原标题:教育背景]", normalized)
        self.assertIn("[简历模块:work_experience；原标题:实习经历]", normalized)
        self.assertIn("[简历模块:practical_experience；原标题:个人实践]", normalized)
        self.assertIn("[简历模块:project_experience；原标题:项目经验]", normalized)
        self.assertIn("[简历模块:campus_experience；原标题:校园经历]", normalized)
        self.assertIn("[简历模块:research_experience；原标题:科研经历]", normalized)
        self.assertIn("[简历模块:skills；原标题:专业技能]", normalized)
        self.assertIn("[简历模块:awards；原标题:荣誉奖项]", normalized)
        self.assertIn("[简历模块:certificates；原标题:资格证书]", normalized)
        self.assertIn("[简历模块:language_skills；原标题:语言能力]", normalized)
        self.assertIn("[简历模块:interests；原标题:兴趣爱好]", normalized)
        self.assertIn("[简历模块:summary；原标题:个人简介]", normalized)

    def test_work_and_internship_headings_share_one_module(self):
        for heading in ["工作经历", "工作经验", "实习经历", "实习经验"]:
            with self.subTest(heading=heading):
                normalized = resume_parser.normalize_resume_section_headings(heading)
                self.assertEqual(
                    normalized,
                    f"[简历模块:work_experience；原标题:{heading}]",
                )

    def test_practical_experience_headings_share_one_independent_module(self):
        for heading in ["个人实践", "实践经历", "社会实践", "实训经历", "兼职经历"]:
            with self.subTest(heading=heading):
                normalized = resume_parser.normalize_resume_section_headings(heading)
                self.assertEqual(
                    normalized,
                    f"[简历模块:practical_experience；原标题:{heading}]",
                )

    def test_self_introduction_headings_share_summary_module(self):
        for heading in ["自我介绍", "个人简介", "关于我", "个人陈述", "核心优势"]:
            with self.subTest(heading=heading):
                normalized = resume_parser.normalize_resume_section_headings(heading)
                self.assertEqual(
                    normalized,
                    f"[简历模块:summary；原标题:{heading}]",
                )

    def test_words_inside_normal_sentence_are_not_rewritten(self):
        sentence = "我的实习经历主要负责整理产品需求。"

        normalized = resume_parser.normalize_resume_section_headings(sentence)

        self.assertEqual(normalized, sentence)

    @patch("modules.resume_parser.DeepSeekClient")
    def test_ai_receives_alias_rules_and_normalized_resume(self, client_class):
        client_class.return_value.chat_json.return_value = {"work_experience": []}

        result = resume_parser.extract_resume_info("实习经历\n2024 示例公司")

        system_prompt, resume_text = client_class.return_value.chat_json.call_args.args
        self.assertIn('"实习经历"', system_prompt)
        self.assertIn("work_experience", system_prompt)
        self.assertIn("[简历模块:work_experience；原标题:实习经历]", resume_text)
        self.assertEqual(result["work_experience"], [])
        self.assertEqual(result["practical_experience"], [])
        self.assertEqual(result["awards"], [])
        self.assertEqual(result["certificates"], [])
        self.assertEqual(result["campus_experience"], [])

    @patch("modules.resume_parser.DeepSeekClient")
    def test_missing_optional_modules_become_empty_lists(self, client_class):
        client_class.return_value.chat_json.return_value = {"name": "张三"}

        result = resume_parser.extract_resume_info("张三")

        for field in resume_parser.RESUME_LIST_FIELDS:
            self.assertEqual(result[field], [])


if __name__ == "__main__":
    unittest.main()
