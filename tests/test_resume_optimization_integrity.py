import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.db_client import init_db
from modules import resume_parser
from modules.resume_optimization_guard import (
    merge_grounded_optimization,
    normalize_capability_decisions,
    validated_capability_analysis,
)
from services import resume_documents, resume_optimization


def sample_profile():
    return {
        "name": "测试用户",
        "phone": "13800000000",
        "email": "test@example.com",
        "desired_position": "产品助理",
        "desired_salary": "8K-10K",
        "summary": "协助完成2次产品测试。",
        "education": [
            {"school": "测试学院", "major": "电子商务", "degree": "大专", "year": "2026"}
        ],
        "work_experience": [
            {
                "company": "原公司",
                "position": "运营实习生",
                "duration": "2025.01-2025.06",
                "description": "协助整理5份周报。",
            }
        ],
        "project_experience": [
            {
                "name": "原项目",
                "role": "成员",
                "duration": "2025.07",
                "description": "完成3项测试。",
            }
        ],
        "practical_experience": [
            {"organization": "实践组", "role": "成员", "duration": "2025", "description": "整理资料。"}
        ],
        "campus_experience": [
            {"organization": "学生会", "role": "干事", "duration": "2024", "description": "协助活动。"}
        ],
        "research_experience": [
            {"name": "课程研究", "role": "学生", "duration": "2025", "description": "完成记录。"}
        ],
        "skills": ["Python", "FastAPI"],
        "awards": [{"name": "实践奖", "level": "校级", "year": "2025", "description": ""}],
        "certificates": [{"name": "Python二级", "level": "二级", "year": "2025", "issuer": "考试中心"}],
        "language_skills": [{"language": "普通话", "level": "熟练", "certificate": ""}],
        "interests": ["跑步"],
        "raw_text": "协助完成2次产品测试。协助整理5份周报。完成3项测试。",
        "quality_warnings": [],
    }


class FakeDeepSeekClient:
    last_user_message = ""
    last_temperature = None

    def chat(self, system_prompt, user_message, temperature, **kwargs):
        FakeDeepSeekClient.last_user_message = user_message
        FakeDeepSeekClient.last_temperature = temperature
        return json.dumps(
            {
                "job_analysis": "产品助理岗位分析",
                "capability_analysis": {
                    "direct_matches": [
                        {
                            "capability": "产品测试",
                            "source_evidence": "协助完成2次产品测试。",
                            "target_relevance": "能够支持产品验证工作",
                        }
                    ],
                    "transferable_matches": [],
                    "gaps": [
                        {
                            "capability": "金融知识",
                            "jd_evidence": "负责金融产品需求分析",
                            "action": "先学习基础课程",
                            "priority": "medium",
                        }
                    ],
                },
                "optimized_summary": "主导完成99次产品测试。",
                "summary_evidence": ["协助完成2次产品测试。"],
                "optimized_work_experience": [
                    {
                        "company": "虚构公司",
                        "position": "负责人",
                        "duration": "2030",
                        "description": "主导完成99份周报。",
                        "evidence": ["协助整理5份周报。"],
                    }
                ],
                "optimized_project_experience": [
                    {"name": "原项目", "role": "成员", "duration": "2025.07", "description": "完成3项测试。"},
                    {"name": "新增项目", "role": "负责人", "duration": "2026", "description": "虚构内容"},
                ],
                "optimized_practical_experience": [
                    {"organization": "错误组织", "role": "负责人", "duration": "2030", "description": "更清楚地整理资料。"}
                ],
                "optimized_campus_experience": [],
                "optimized_research_experience": [],
                "enhanced_skills": ["Python", "不存在的新技能"],
                "suggestions": ["可以学习新技能"],
            },
            ensure_ascii=False,
        )


class ResumeOptimizationIntegrityTests(unittest.TestCase):
    def test_new_parse_keeps_immutable_original_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resume_path = Path(temp_dir, "resume.txt")
            resume_path.write_text("姓名：测试用户\n技能：Python", encoding="utf-8")
            parsed = sample_profile()
            with patch.object(resume_parser, "extract_resume_info", return_value=parsed):
                result = resume_parser.parse_resume(str(resume_path))

        self.assertEqual(result["original_profile"]["name"], "测试用户")
        self.assertEqual(result["original_profile"]["raw_text"], "姓名：测试用户\n技能：Python")
        self.assertEqual(result["optimization_history"], [])

    def test_optimizer_uses_full_source_and_blocks_new_facts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "resume_test.json"
            Path(temp_dir, filename).write_text(
                json.dumps(sample_profile(), ensure_ascii=False),
                encoding="utf-8",
            )
            with (
                patch.object(resume_optimization, "DATA_DIR", temp_dir),
                patch.object(resume_optimization, "DeepSeekClient", FakeDeepSeekClient),
            ):
                result = resume_optimization.optimize_resume(
                    filename,
                    "金融产品助理",
                    job_description="负责金融产品需求分析、数据整理和产品测试。",
                )

        self.assertTrue(result["ok"])
        self.assertIn("project_experience", FakeDeepSeekClient.last_user_message)
        self.assertIn("awards", FakeDeepSeekClient.last_user_message)
        self.assertIn("目标岗位JD", FakeDeepSeekClient.last_user_message)
        self.assertEqual(FakeDeepSeekClient.last_temperature, 0.3)
        optimized = result["optimized_resume"]
        self.assertEqual(optimized["summary"], "协助完成2次产品测试。")
        self.assertEqual(optimized["work_experience"][0]["company"], "原公司")
        self.assertEqual(optimized["work_experience"][0]["description"], "协助整理5份周报。")
        self.assertEqual(len(optimized["project_experience"]), 1)
        self.assertEqual(optimized["skills"], ["Python", "FastAPI"])
        self.assertEqual(len(optimized["awards"]), 1)
        self.assertTrue(result["resume_diff"]["has_changes"])
        self.assertIn("desired_position", {item["field"] for item in result["resume_diff"]["changes"]})
        self.assertNotIn("raw_text", {item["field"] for item in result["resume_diff"]["changes"]})
        self.assertEqual(result["capability_analysis"]["direct_matches"][0]["capability"], "产品测试")
        self.assertTrue(any(item["code"] == "UNSUPPORTED_SKILLS_REMOVED" for item in result["optimization_warnings"]))

    def test_optimizer_uses_original_snapshot_instead_of_active_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "resume_test.json"
            original = sample_profile()
            active = dict(original)
            active["summary"] = "这是已经被旧版AI改写的活动版本"
            active["skills"] = ["虚构技能"]
            active["original_profile"] = original
            active["optimization_history"] = []
            Path(temp_dir, filename).write_text(
                json.dumps(active, ensure_ascii=False),
                encoding="utf-8",
            )
            with (
                patch.object(resume_optimization, "DATA_DIR", temp_dir),
                patch.object(resume_optimization, "DeepSeekClient", FakeDeepSeekClient),
            ):
                result = resume_optimization.optimize_resume(
                    filename,
                    "金融产品助理",
                    job_description="负责产品测试、数据整理与金融产品需求分析。",
                )

        self.assertTrue(result["ok"])
        self.assertNotIn("已经被旧版AI改写", FakeDeepSeekClient.last_user_message)
        self.assertNotIn("虚构技能", FakeDeepSeekClient.last_user_message)
        self.assertTrue(result["source_snapshot_available"])
        self.assertEqual(result["optimized_resume"]["skills"], ["Python", "FastAPI"])

    def test_broad_industry_requires_specific_role_or_jd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "resume_test.json"
            Path(temp_dir, filename).write_text(
                json.dumps(sample_profile(), ensure_ascii=False),
                encoding="utf-8",
            )
            with (
                patch.object(resume_optimization, "DATA_DIR", temp_dir),
                patch.object(resume_optimization, "DeepSeekClient", FakeDeepSeekClient),
            ):
                result = resume_optimization.optimize_resume(filename, "金融行业")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_INPUT")
        self.assertIn("具体岗位", result["error"])

    def test_evidence_backed_transfer_rewrite_is_kept(self):
        source = sample_profile()
        merged, warnings = merge_grounded_optimization(
            source,
            {
                "optimized_summary": "具备产品测试和资料整理经验，可迁移到金融产品支持工作。",
                "summary_evidence": ["协助完成2次产品测试。"],
                "optimized_work_experience": [
                    {
                        "description": "协助整理5份周报，形成可用于业务复盘的信息整理习惯。",
                        "evidence": ["协助整理5份周报。"],
                    }
                ],
                "enhanced_skills": ["FastAPI", "Python"],
            },
            "金融产品助理",
        )

        self.assertIn("金融产品支持", merged["summary"])
        self.assertIn("业务复盘", merged["work_experience"][0]["description"])
        self.assertEqual(merged["skills"], ["FastAPI", "Python"])
        self.assertFalse(any(item["code"] == "OPTIMIZATION_EVIDENCE_MISSING" for item in warnings))

    def test_gap_suggestions_need_real_jd_evidence_and_stay_outside_resume(self):
        profile = sample_profile()
        analysis = validated_capability_analysis(
            {
                "capability_analysis": {
                    "gaps": [
                        {
                            "capability": "风险识别",
                            "jd_evidence": "需要具备风险识别能力",
                            "action": "如有真实课程或项目经历，可补充相关内容。",
                            "priority": "high",
                        },
                        {
                            "capability": "虚构能力",
                            "jd_evidence": "JD中不存在的内容",
                            "action": "不应展示。",
                        },
                    ]
                }
            },
            profile,
            "岗位要求：需要具备风险识别能力，并完成数据整理。",
        )

        self.assertEqual(len(analysis["gaps"]), 1)
        gap = analysis["gaps"][0]
        self.assertEqual(gap["jd_evidence"], "需要具备风险识别能力")
        self.assertEqual(gap["resume_status"], "简历未体现该能力，不代表你不具备。")
        self.assertEqual(gap["write_condition"], "仅在用户确认真实经历后，才允许写入正式简历。")
        self.assertEqual(gap["priority"], "high")
        self.assertTrue(gap["suggestion_id"])
        self.assertEqual(gap["decision"], "pending")
        self.assertEqual(gap["confirmed_content"], "")
        self.assertNotIn("风险识别", profile["skills"])

    def test_capability_decisions_require_real_confirmed_content(self):
        analysis = {
            "direct_matches": [],
            "transferable_matches": [],
            "gaps": [
                {
                    "suggestion_id": "gap-risk",
                    "capability": "风险识别",
                    "jd_evidence": "需要具备风险识别能力",
                    "decision": "accepted",
                    "confirmed_content": "",
                }
            ],
        }

        _, error = normalize_capability_decisions(analysis)
        self.assertIn("缺少真实经历说明", error)

        analysis["gaps"][0]["confirmed_content"] = "在课程作业中整理并复核风险清单。"
        normalized, error = normalize_capability_decisions(analysis)
        self.assertIsNone(error)
        self.assertEqual(normalized["gaps"][0]["decision"], "accepted")
        self.assertEqual(
            normalized["gaps"][0]["confirmed_content"],
            "在课程作业中整理并复核风险清单。",
        )

        analysis["gaps"][0]["decision"] = "rejected"
        normalized, error = normalize_capability_decisions(analysis)
        self.assertIsNone(error)
        self.assertEqual(normalized["gaps"][0]["confirmed_content"], "")

    def test_merge_preserves_identity_and_all_optional_sections(self):
        source = sample_profile()
        merged, warnings = merge_grounded_optimization(
            source,
            {
                "optimized_summary": "更清楚地说明产品测试经验。",
                "optimized_work_experience": [
                    {
                        "company": "另一家公司",
                        "position": "经理",
                        "duration": "2030",
                        "description": "更清楚地表达周报整理工作。",
                    }
                ],
                "enhanced_skills": ["Python", "Go"],
            },
            "AI产品助理",
        )
        self.assertEqual(merged["work_experience"][0]["company"], "原公司")
        self.assertEqual(merged["work_experience"][0]["position"], "运营实习生")
        self.assertEqual(merged["skills"], ["Python", "FastAPI"])
        for field in ("project_experience", "practical_experience", "campus_experience", "research_experience", "awards", "certificates", "language_skills", "interests"):
            self.assertEqual(merged[field], source[field])
        self.assertTrue(any(item["code"] == "UNSUPPORTED_SKILLS_REMOVED" for item in warnings))

    def test_overwrite_updates_json_and_sqlite_without_losing_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            init_db(db_path)
            filename = "resume_test.json"
            source = sample_profile()
            Path(temp_dir, filename).write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            connection = sqlite3.connect(db_path)
            connection.execute(
                "INSERT INTO resumes (filename, name, phone, email, parsed_data) VALUES (?, ?, ?, ?, ?)",
                (filename, source["name"], source["phone"], source["email"], json.dumps(source, ensure_ascii=False)),
            )
            connection.commit()
            connection.close()

            candidate = dict(source)
            candidate["summary"] = "更清楚地说明产品测试经验。"
            with patch.object(resume_documents, "DATA_DIR", temp_dir):
                result = resume_documents.overwrite_resume(
                    resume_file=filename,
                    target="AI产品助理",
                    optimized_resume=json.dumps(candidate, ensure_ascii=False),
                    db_path=db_path,
                )

            self.assertTrue(result["ok"])
            json_profile = json.loads(Path(temp_dir, filename).read_text(encoding="utf-8"))
            connection = sqlite3.connect(db_path)
            db_profile = json.loads(connection.execute("SELECT parsed_data FROM resumes WHERE filename = ?", (filename,)).fetchone()[0])
            connection.close()
            self.assertEqual(json_profile, db_profile)
            self.assertEqual(len(json_profile["project_experience"]), 1)
            self.assertEqual(len(json_profile["awards"]), 1)
            self.assertEqual(len(json_profile["certificates"]), 1)
            self.assertEqual(json_profile["original_profile"]["summary"], source["summary"])
            self.assertEqual(len(json_profile["optimization_history"]), 1)
            self.assertEqual(json_profile["active_optimization"]["target"], "AI产品助理")

    def test_overwrite_persists_decisions_without_writing_gap_as_resume_fact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            init_db(db_path)
            filename = "resume_d13.json"
            source = sample_profile()
            Path(temp_dir, filename).write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            connection = sqlite3.connect(db_path)
            connection.execute(
                "INSERT INTO resumes (filename, name, phone, email, parsed_data) VALUES (?, ?, ?, ?, ?)",
                (filename, source["name"], source["phone"], source["email"], json.dumps(source, ensure_ascii=False)),
            )
            connection.commit()
            connection.close()

            candidate = dict(source)
            candidate["_optimization_meta"] = {
                "version_id": "d13-version",
                "target": "AI产品助理",
                "job_description": "需要风险识别和SQL能力",
                "capability_analysis": {
                    "direct_matches": [],
                    "transferable_matches": [],
                    "gaps": [
                        {
                            "suggestion_id": "risk-gap",
                            "capability": "风险识别",
                            "decision": "accepted",
                            "confirmed_content": "在课程作业中整理并复核风险清单。",
                        },
                        {
                            "suggestion_id": "sql-gap",
                            "capability": "SQL",
                            "decision": "rejected",
                            "confirmed_content": "这段内容不应保存",
                        },
                    ],
                },
            }

            invalid_candidate = json.loads(json.dumps(candidate, ensure_ascii=False))
            invalid_candidate["_optimization_meta"]["capability_analysis"]["gaps"][0]["confirmed_content"] = ""
            with patch.object(resume_documents, "DATA_DIR", temp_dir):
                invalid_result = resume_documents.overwrite_resume(
                    resume_file=filename,
                    target="AI产品助理",
                    optimized_resume=json.dumps(invalid_candidate, ensure_ascii=False),
                    db_path=db_path,
                )
            self.assertFalse(invalid_result["ok"])
            self.assertEqual(invalid_result["error_code"], "CONFIRMATION_REQUIRED")
            self.assertEqual(
                json.loads(Path(temp_dir, filename).read_text(encoding="utf-8")),
                source,
            )

            with patch.object(resume_documents, "DATA_DIR", temp_dir):
                result = resume_documents.overwrite_resume(
                    resume_file=filename,
                    target="AI产品助理",
                    optimized_resume=json.dumps(candidate, ensure_ascii=False),
                    db_path=db_path,
                )

            self.assertTrue(result["ok"])
            json_profile = json.loads(Path(temp_dir, filename).read_text(encoding="utf-8"))
            connection = sqlite3.connect(db_path)
            db_profile = json.loads(connection.execute("SELECT parsed_data FROM resumes WHERE filename = ?", (filename,)).fetchone()[0])
            connection.close()
            self.assertEqual(json_profile, db_profile)
            saved_gaps = json_profile["optimization_history"][-1]["capability_analysis"]["gaps"]
            writer_inputs = json_profile["optimization_history"][-1]["resume_writer_inputs"]
            self.assertEqual(saved_gaps[0]["decision"], "accepted")
            self.assertEqual(saved_gaps[0]["confirmed_content"], "在课程作业中整理并复核风险清单。")
            self.assertEqual(saved_gaps[1]["decision"], "rejected")
            self.assertEqual(saved_gaps[1]["confirmed_content"], "")
            self.assertEqual(len(writer_inputs), 1)
            self.assertEqual(writer_inputs[0]["suggestion_id"], "risk-gap")
            self.assertEqual(writer_inputs[0]["confirmed_content"], "在课程作业中整理并复核风险清单。")
            self.assertNotIn("风险识别", json_profile["skills"])
            self.assertNotIn("SQL", json_profile["skills"])

    def test_export_and_template_render_every_nonempty_section(self):
        profile = sample_profile()
        response = resume_documents._build_export_response(profile)
        exported_html = response.body.decode("utf-8")
        for heading in ("工作经验", "教育背景", "期望薪资", "项目经历", "个人实践", "校园经历", "科研经历", "获奖荣誉", "证书资质", "语言能力", "兴趣爱好", "技能"):
            self.assertIn(heading, exported_html)

        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "resume_test.json"
            Path(temp_dir, filename).write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
            with patch.object(resume_documents, "DATA_DIR", temp_dir):
                template_response = resume_documents.resume_template(filename, "classic")
        template_html = template_response.body.decode("utf-8")
        for heading in ("项目经历", "个人实践", "校园经历", "科研经历", "获奖荣誉", "证书资质", "语言能力", "兴趣爱好"):
            self.assertIn(heading, template_html)

    def test_empty_sections_stay_hidden(self):
        profile = sample_profile()
        profile["research_experience"] = []
        profile["awards"] = []
        response = resume_documents._build_export_response(profile)
        exported_html = response.body.decode("utf-8")
        self.assertNotIn("科研经历", exported_html)
        self.assertNotIn("获奖荣誉", exported_html)

    def test_frontend_switch_keeps_optimization_result(self):
        source = Path("frontend/src/components/AIAssistant.jsx").read_text(encoding="utf-8")
        switch_line = next(line for line in source.splitlines() if "const switchStep" in line)
        self.assertNotIn("setOptResult(null)", switch_line)
        self.assertIn("/api/resume/export-optimized", source)
        self.assertIn('fd.append("optimized_resume"', source)
        self.assertIn('fd.append("job_description"', source)
        self.assertIn("保存优化版本", source)
        self.assertIn("接受并补充真实经历", source)
        self.assertIn("确认接受真实内容", source)
        self.assertIn("不采用", source)
        self.assertIn("确认进度：已接受", source)
        self.assertIn("capability_analysis: updatedAnalysis", source)
        self.assertIn("查看本次优化前后对比", source)
        self.assertIn("resumeDiffOpen", source)
        self.assertIn("optResult.resume_diff", source)
        self.assertIn("order: 3", source)


if __name__ == "__main__":
    unittest.main()
