import json
import os
import tempfile
import unittest
from unittest.mock import patch

from modules.job_repository import save_job_batch
from services.resume_precision import precision_optimize


class FakeDeepSeekClient:
    def __init__(self, captured: dict):
        self.captured = captured

    def chat_json(self, system_prompt, user_message):
        self.captured["system_prompt"] = system_prompt
        self.captured["user_message"] = user_message
        return {"target_position": "python developer"}


class ResumePrecisionRepositoryTests(unittest.TestCase):
    def _write_resume(self, temp_dir: str) -> str:
        filename = "resume.json"
        with open(os.path.join(temp_dir, filename), "w", encoding="utf-8") as target:
            json.dump(
                {
                    "name": "candidate",
                    "desired_position": "developer",
                    "summary": "learner",
                    "skills": ["python"],
                    "work_experience": [],
                    "education": [],
                },
                target,
                ensure_ascii=False,
            )
        return filename

    def test_precision_reads_selected_jobs_from_repository_without_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "precision.db")
            batch_id = "jobs_20260718_000001.json"
            jobs = [
                {
                    "job_id": "job-1",
                    "title": "python developer",
                    "company": "company-a",
                    "salary": "8-10k",
                    "location": "广州",
                    "url": "https://example.com/job-1",
                    "match_score": 90,
                    "strengths": ["python"],
                    "weaknesses": ["experience"],
                    "suggestions": ["practice"],
                },
                {
                    "job_id": "job-2",
                    "title": "fastapi developer",
                    "company": "company-b",
                    "salary": "9-12k",
                    "location": "广州",
                    "url": "https://example.com/job-2",
                    "match_score": 88,
                    "strengths": ["fastapi"],
                    "weaknesses": [],
                    "suggestions": [],
                },
            ]
            save_job_batch(
                batch_id,
                {
                    "profile": {},
                    "keywords": ["python"],
                    "count": len(jobs),
                    "collected_at": "2026-07-18 00:00:00",
                    "jobs": jobs,
                },
                db_path,
            )
            captured = {}
            fake_client = FakeDeepSeekClient(captured)
            with (
                patch(
                    "services.resume_precision._fetch_jd_detail",
                    return_value="full jd detail",
                ),
                patch(
                    "services.resume_precision.DeepSeekClient",
                    return_value=fake_client,
                ),
            ):
                result = precision_optimize(
                    self._write_resume(temp_dir),
                    batch_id,
                    "0,1",
                    data_dir=temp_dir,
                    db_path=db_path,
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["jobs_count"], 2)
            self.assertFalse(os.path.exists(os.path.join(temp_dir, batch_id)))
            self.assertIn("python developer", captured["user_message"])
            self.assertIn("fastapi developer", captured["user_message"])
            self.assertIn("full jd detail", captured["user_message"])

    def test_missing_repository_batch_stops_before_network_and_ai(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "precision.db")
            resume_file = self._write_resume(temp_dir)
            with (
                patch("services.resume_precision._fetch_jd_detail") as fetch,
                patch("services.resume_precision.DeepSeekClient") as client,
            ):
                result = precision_optimize(
                    resume_file,
                    "jobs_20260718_000001.json",
                    "0",
                    data_dir=temp_dir,
                    db_path=db_path,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "岗位文件不存在")
            fetch.assert_not_called()
            client.assert_not_called()

    def test_unsafe_job_name_is_rejected_before_network_and_ai(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "precision.db")
            resume_file = self._write_resume(temp_dir)
            with (
                patch("services.resume_precision._fetch_jd_detail") as fetch,
                patch("services.resume_precision.DeepSeekClient") as client,
            ):
                result = precision_optimize(
                    resume_file,
                    "../jobs_bad.json",
                    "0",
                    data_dir=temp_dir,
                    db_path=db_path,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "岗位文件名不安全")
            fetch.assert_not_called()
            client.assert_not_called()

    def test_precision_optimize_overwrite_persists_to_sqlite_and_recheck_compares_scores(self):
        import sqlite3
        from modules.db_client import init_db
        from services import resume_documents
        from services.job_matching import batch_score_jobs_json
        from services.resume_precision import precision_recheck

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "precision_e2e.db")
            init_db(db_path)
            resume_file = "resume_precision_e2e.json"
            base_profile = {
                "name": "林测试",
                "phone": "13800000000",
                "email": "test@example.com",
                "desired_position": "产品实习生",
                "summary": "熟悉需求分析与原型设计，具备数据分析基础。",
                "skills": ["Axure", "SQL", "Python", "需求分析"],
                "work_experience": [
                    {
                        "company": "星云科技",
                        "position": "产品助理",
                        "duration": "2025.06-2025.12",
                        "description": "协助梳理需求文档并跟进研发上线。",
                    }
                ],
                "project_experience": [
                    {
                        "name": "智能客服知识库搭建",
                        "role": "项目负责人",
                        "duration": "2025.09-2025.11",
                        "description": "整理常见问题并搭建检索流程。",
                    }
                ],
                "education": [],
            }
            with open(os.path.join(temp_dir, resume_file), "w", encoding="utf-8") as fh:
                json.dump(base_profile, fh, ensure_ascii=False)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO resumes (filename, name, phone, email, parsed_data) VALUES (?, ?, ?, ?, ?)",
                (resume_file, base_profile["name"], base_profile["phone"], base_profile["email"], json.dumps(base_profile, ensure_ascii=False)),
            )
            conn.commit()
            conn.close()

            batch_id = "jobs_20261124_000001.json"
            save_job_batch(
                batch_id,
                {
                    "profile": {},
                    "keywords": ["AI产品经理"],
                    "count": 1,
                    "collected_at": "2026-11-24 09:00:00",
                    "resume_name": base_profile["name"],
                    "scored_resume_file": resume_file,
                    "auto_scored": True,
                    "jobs": [
                        {
                            "job_id": "j-ai-1",
                            "title": "AI产品助理",
                            "company": "未来智算",
                            "salary": "12k-18k",
                            "location": "杭州",
                            "description": "负责AI知识库产品需求梳理、SQL数据指标分析与跨团队上线推进。",
                            "url": "https://example.com/j-ai-1",
                            "match_score": 72,
                            "match_brief": "基础匹配，缺少针对性表达",
                        }
                    ],
                },
                db_path,
            )

            class _RichFakeClient:
                def chat_json(self, system_prompt, user_message):
                    return {
                        "target_position": "AI产品助理",
                        "optimized_summary": "聚焦AI产品需求分析、SQL指标追踪与知识库产品落地的复合型候选人。",
                        "optimized_work_experience": [
                            {
                                "company": "星云科技",
                                "position": "产品助理",
                                "duration": "2025.06-2025.12",
                                "description": "主导核心需求文档撰写与跨研发排期推进，保障AI相关功能稳定上线。",
                            }
                        ],
                        "optimized_project_experience": [
                            {
                                "name": "智能客服知识库搭建",
                                "role": "项目负责人",
                                "duration": "2025.09-2025.11",
                                "description": "面向AI问答场景搭建结构化知识库检索流程，显著提升高频问题响应清晰度。",
                            }
                        ],
                        "enhanced_skills": ["需求分析", "SQL", "Python", "Axure"],
                        "optimization_notes": "已突出AI知识库与数据分析相关经历。",
                    }

            with patch("services.resume_precision.DeepSeekClient", return_value=_RichFakeClient()):
                opt_res = precision_optimize(
                    resume_file,
                    batch_id,
                    "0",
                    data_dir=temp_dir,
                    db_path=db_path,
                )

            self.assertTrue(opt_res["ok"])
            self.assertIn("optimized_resume", opt_res)
            self.assertEqual(opt_res["selected_jobs"][0]["before_score"], 72)

            with patch.object(resume_documents, "DATA_DIR", temp_dir):
                ov_res = resume_documents.overwrite_resume(
                    resume_file=resume_file,
                    optimized_summary=opt_res["optimized_summary"],
                    optimized_projects=json.dumps(opt_res["optimized_projects"], ensure_ascii=False),
                    optimized_internships=json.dumps(opt_res["optimized_work_experience"], ensure_ascii=False),
                    enhanced_skills=json.dumps(opt_res["enhanced_skills"], ensure_ascii=False),
                    target=opt_res["target_position"],
                    optimized_resume=json.dumps(opt_res["optimized_resume"], ensure_ascii=False),
                    db_path=db_path,
                )

            self.assertTrue(ov_res["ok"])
            for expected_field in ("summary", "desired_position", "work_experience", "project_experience", "skills"):
                self.assertIn(expected_field, ov_res["changed_fields"])

            # Verify SQLite resumes table truly holds the overwritten content
            conn = sqlite3.connect(db_path)
            db_saved = json.loads(
                conn.execute("SELECT parsed_data FROM resumes WHERE filename = ?", (resume_file,)).fetchone()[0]
            )
            conn.close()
            self.assertIn("SQL指标追踪", db_saved["summary"])
            self.assertIn("AI问答场景", db_saved["project_experience"][0]["description"])
            self.assertIn("跨研发排期推进", db_saved["work_experience"][0]["description"])
            self.assertEqual(db_saved["desired_position"], "AI产品助理")

            # Verify precision_recheck uses overwritten resume and returns before/after delta
            seen_profiles = []

            def _fake_match(profile_arg, jd_text_arg):
                seen_profiles.append(profile_arg)
                return {
                    "ok": True,
                    "overall_score": 86,
                    "skill_match": 88,
                    "experience_match": 85,
                    "education_match": 84,
                    "verdict": "覆盖后简历与AI知识库产品JD高度契合",
                    "strengths": ["具备知识库搭建与SQL分析能力"],
                    "weaknesses": ["可补充量化业务指标"],
                    "suggestions": ["补充上线后效果数据"],
                }

            with patch("services.resume_precision.match_resume_to_jd", side_effect=_fake_match):
                recheck_res = precision_recheck(
                    resume_file=resume_file,
                    jobs_file=batch_id,
                    job_indices="0",
                    before_scores=json.dumps({"0": {"before_score": 72, "before_brief": "旧简评"}}),
                    data_dir=temp_dir,
                    db_path=db_path,
                    write_legacy_json=False,
                )

            self.assertTrue(recheck_res["ok"])
            self.assertEqual(recheck_res["avg_before"], 72.0)
            self.assertEqual(recheck_res["avg_after"], 86.0)
            self.assertEqual(recheck_res["avg_delta"], 14.0)
            self.assertEqual(recheck_res["improved_count"], 1)
            self.assertIn("SQL指标追踪", seen_profiles[0]["summary"])

            # Verify batch_score_jobs_json invalidates cache when resume content changes again
            db_saved["summary"] = "再次变更后的全新摘要内容"
            with open(os.path.join(temp_dir, resume_file), "w", encoding="utf-8") as fh:
                json.dump(db_saved, fh, ensure_ascii=False)
            with patch(
                "services.job_matching.quick_match",
                return_value={"ok": True, "score": 91, "brief": "新简历重新打分", "reasons": []},
            ) as mock_qm:
                rescored = batch_score_jobs_json(
                    {"jobs_file": batch_id, "resume_file": resume_file, "threshold": 70},
                    data_dir=temp_dir,
                    db_path=db_path,
                    write_legacy_json=False,
                )
            self.assertTrue(rescored["ok"])
            self.assertFalse(rescored["cached"])
            self.assertEqual(rescored["jobs"][0]["match_score"], 91)
            self.assertEqual(mock_qm.call_count, 1)


if __name__ == "__main__":
    unittest.main()
