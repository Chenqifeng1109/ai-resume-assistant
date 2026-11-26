import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from core.workspace_context import reset_workspace_id, set_workspace_id
from modules.db_client import get_connection, init_db
from modules.job_repository import save_job_batch
from modules.restriction_checker import evaluate_restrictions_against_jd
from services.interview_prep import generate_interview_prep


class FakeInterviewClient:
    def __init__(self, captured: dict):
        self.captured = captured

    def chat_json(self, system_prompt, user_message):
        self.captured["system_prompt"] = system_prompt
        self.captured["user_message"] = user_message
        return {
            "target_role": "AI产品专员",
            "overall_strategy": "重点突出需求拆解与数据分析闭环，坦诚补充真实业务指标",
            "questions": [
                {
                    "category": "项目深挖",
                    "question": "你在用户留存分析项目中是如何定位流失关键节点的？",
                    "intent": "考察数据拆解深度与业务洞察力",
                    "star_answer": {
                        "situation": "负责用户留存分析项目",
                        "task": "定位核心流失环节并提出优化方案",
                        "action": "通过 SQL 拆解次日与七日留存漏斗",
                        "result": "输出可行改进建议【请补充你的真实数据】",
                    },
                    "follow_ups": ["如果指标口径不一致你会怎么处理？"],
                }
            ],
            "reverse_questions": [
                "请问团队目前的加班与双休节奏大概是怎样的？",
                "这个岗位前 3 个月最核心的业务目标是什么？",
            ],
        }


class Stage2CompetitivenessTests(unittest.TestCase):
    def test_restriction_traffic_light_evaluator(self):
        jd = (
            "岗位职责：负责AI产品需求分析与迭代。\n"
            "福利待遇：入职即缴五险一金，团队实行大小周排班，需外派驻场客户现场。"
        )
        report = evaluate_restrictions_against_jd(
            "双休\n五险一金\n不接受外包\n不接受长期出差",
            jd,
        )
        by_rule = {item["restriction"]: item for item in report["items"]}
        self.assertEqual(by_rule["双休"]["status"], "red")
        self.assertIn("大小周", by_rule["双休"]["evidence"])
        self.assertEqual(by_rule["五险一金"]["status"], "green")
        self.assertIn("五险一金", by_rule["五险一金"]["evidence"])
        self.assertEqual(by_rule["不接受外包"]["status"], "red")
        self.assertEqual(by_rule["不接受长期出差"]["status"], "yellow")
        self.assertEqual(report["summary"], {"total": 4, "green": 1, "yellow": 1, "red": 2})

    def test_interview_prep_from_job_batch_and_workspace_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("core.workspace_context.DATA_DIR", temp_dir),
                patch.dict(
                    os.environ,
                    {
                        "OFFERFORGE_WORKSPACE_ISOLATION": "always",
                        "OFFERFORGE_PUBLIC_MODE": "0",
                        "OFFERFORGE_DEMO_TOKEN": "",
                    },
                    clear=False,
                ),
            ):
                client = TestClient(app)
                self.assertEqual(client.get("/api/resumes/list").status_code, 200)
                ws_id = client.cookies.get("of_workspace_id")
                self.assertTrue(ws_id)

                ws_data = os.path.join(temp_dir, "workspaces", ws_id, "data")
                os.makedirs(ws_data, exist_ok=True)
                ws_db = os.path.join(ws_data, "offerforge.db")
                resume_file = "resume_stage2.json"
                batch_file = "jobs_20261126_040000.json"

                tokens = set_workspace_id(ws_id, base_data_dir=temp_dir)
                try:
                    profile = {
                        "name": "测试求职者",
                        "desired_position": "AI产品专员",
                        "skills": ["SQL", "原型设计", "数据分析"],
                        "project_experience": [
                            {"name": "用户留存分析", "role": "负责人", "duration": "2025.03-2025.05", "description": "SQL 拆解留存漏斗"}
                        ],
                    }
                    with open(os.path.join(ws_data, resume_file), "w", encoding="utf-8") as handle:
                        json.dump(profile, handle, ensure_ascii=False)
                    init_db(ws_db)
                    conn = get_connection(ws_db)
                    conn.execute(
                        "INSERT INTO resumes (filename, name, phone, email, parsed_data) VALUES (?, ?, ?, ?, ?)",
                        (resume_file, profile["name"], "", "", json.dumps(profile, ensure_ascii=False)),
                    )
                    conn.commit()
                    conn.close()

                    save_job_batch(
                        batch_file,
                        {
                            "keywords": ["AI产品专员"],
                            "restrictions": ["双休", "不接受外包"],
                            "count": 1,
                            "collected_at": "2026-11-26 04:00:00",
                            "jobs": [
                                {
                                    "job_id": "job-ai-1",
                                    "title": "AI产品专员",
                                    "company": "未来智能",
                                    "salary": "10-15K",
                                    "location": "深圳",
                                    "description": "负责大模型应用产品需求文档撰写、数据分析与上线跟进。",
                                }
                            ],
                        },
                        ws_db,
                    )
                finally:
                    reset_workspace_id(tokens)

                captured = {}
                with patch("services.interview_prep.DeepSeekClient", return_value=FakeInterviewClient(captured)):
                    resp = client.post(
                        "/api/resume/interview-prep",
                        data={
                            "resume_file": resume_file,
                            "jobs_file": batch_file,
                            "job_index": "0",
                        },
                    )
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertTrue(body["ok"])
                self.assertEqual(body["target_role"], "AI产品专员")
                self.assertEqual(len(body["questions"]), 1)
                self.assertTrue(body["questions"][0]["standard_answer"])
                self.assertEqual(len(body["reverse_questions"]), 2)
                self.assertIn("双休", captured["user_message"])
                self.assertIn("不接受外包", captured["user_message"])

                # Validation error check: missing resume_file -> 400
                bad = client.post("/api/resume/interview-prep", data={"jd_text": "短期"})
                self.assertEqual(bad.status_code, 400)
                self.assertEqual(bad.json()["error_code"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
