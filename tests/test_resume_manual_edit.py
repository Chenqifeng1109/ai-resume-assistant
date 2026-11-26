import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from core.workspace_context import reset_workspace_id, set_workspace_id
from modules.db_client import get_connection, init_db
from services.resume_documents import update_resume_manual


class ResumeManualEditTests(unittest.TestCase):
    def _seed_resume(self, data_dir: str, db_path: str, filename: str = "resume_test_01.json") -> dict:
        os.makedirs(data_dir, exist_ok=True)
        initial = {
            "name": "测试候选人",
            "desired_position": "数据分析实习生",
            "desired_salary": "6k-8k",
            "phone": "13800138000",
            "email": "test@example.com",
            "summary": "原始自我介绍",
            "skills": ["Excel", "SQL"],
            "education": [{"school": "测试大学", "major": "统计学", "degree": "本科", "year": "2026"}],
            "work_experience": [
                {"company": "示例科技", "position": "数据实习生", "duration": "2025.06-2025.09", "description": "负责日常报表"}
            ],
            "project_experience": [
                {"name": "用户留存分析", "role": "负责人", "duration": "2025.03-2025.05", "description": "SQL 拆解留存漏斗"}
            ],
            "parsed_at": "2026-11-26 00:00:00",
            "quality_status": "needs_review",
            "quality_warnings": [
                {
                    "code": "MISSING_DESIRED_POSITION",
                    "field": "desired_position",
                    "message": "未识别到求职意向，请检查或补充目标岗位。",
                }
            ],
        }
        filepath = os.path.join(data_dir, filename)
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(initial, handle, ensure_ascii=False, indent=2)

        init_db(db_path)
        conn = get_connection(db_path)
        try:
            conn.execute(
                """
                INSERT INTO resumes (filename, name, phone, email, parsed_data)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    initial["name"],
                    initial["phone"],
                    initial["email"],
                    json.dumps(initial, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return initial

    def test_manual_edit_persists_sqlite_versions_and_json_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = os.path.join(temp_dir, "data")
            db_path = os.path.join(data_dir, "offerforge.db")
            filename = "resume_test_01.json"
            self._seed_resume(data_dir, db_path, filename)

            with patch("services.resume_documents.DATA_DIR", data_dir):
                res = update_resume_manual(
                    filename,
                    {
                        "name": "测试候选人(新)",
                        "desired_position": "Python后端工程师",
                        "desired_salary": "12k-16k",
                        "skills": ["Python", "FastAPI", "Python", "  SQLite "],
                        "summary": "更新后的后端工程自我介绍",
                        "work_experience": [
                            {
                                "company": "示例科技",
                                "position": "Python开发实习生",
                                "duration": "2025.06-2025.09",
                                "description": "独立开发 FastAPI 接口并将查询耗时降低 40%",
                            }
                        ],
                    },
                    db_path=db_path,
                )

            self.assertTrue(res["ok"])
            self.assertIn("name", res["changed_fields"])
            self.assertIn("desired_position", res["changed_fields"])
            self.assertIn("skills", res["changed_fields"])
            self.assertTrue(str(res["version_id"]).startswith("manual-"))
            self.assertEqual(res["data"]["skills"], ["Python", "FastAPI", "SQLite"])
            self.assertEqual(res["data"]["quality_warnings"], [])
            self.assertEqual(res["data"]["quality_status"], "complete")

            # Verify JSON file synced
            with open(os.path.join(data_dir, filename), "r", encoding="utf-8") as handle:
                disk_data = json.load(handle)
            self.assertEqual(disk_data["name"], "测试候选人(新)")
            self.assertEqual(disk_data["original_profile"]["name"], "测试候选人")

            # Verify SQLite resumes & resume_versions synced
            conn = get_connection(db_path)
            try:
                row = conn.execute("SELECT name, parsed_data FROM resumes WHERE filename = ?", (filename,)).fetchone()
                self.assertEqual(row["name"], "测试候选人(新)")
                versions = conn.execute(
                    "SELECT version_id, is_current FROM resume_versions WHERE resume_filename = ?",
                    (filename,),
                ).fetchall()
                self.assertGreaterEqual(len(versions), 2)
                current_ids = [v["version_id"] for v in versions if v["is_current"]]
                self.assertEqual(current_ids, [res["version_id"]])
            finally:
                conn.close()

    def test_put_api_validation_and_browser_workspace_isolation(self):
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
                client_a = TestClient(app)
                client_b = TestClient(app)

                self.assertEqual(client_a.get("/api/resumes/list").status_code, 200)
                self.assertEqual(client_b.get("/api/resumes/list").status_code, 200)
                ws_a = client_a.cookies.get("of_workspace_id")
                ws_b = client_b.cookies.get("of_workspace_id")
                self.assertTrue(ws_a and ws_b and ws_a != ws_b)

                filename = "resume_iso_01.json"
                ws_a_data = os.path.join(temp_dir, "workspaces", ws_a, "data")
                ws_a_db = os.path.join(ws_a_data, "offerforge.db")
                tokens = set_workspace_id(ws_a, base_data_dir=temp_dir)
                try:
                    self._seed_resume(ws_a_data, ws_a_db, filename)
                finally:
                    reset_workspace_id(tokens)

                # Browser A updates successfully
                put_a = client_a.put(
                    f"/api/resumes/{filename}",
                    json={"desired_position": "AI全栈工程师", "desired_salary": "18k-25k"},
                )
                self.assertEqual(put_a.status_code, 200)
                body_a = put_a.json()
                self.assertTrue(body_a["ok"])
                self.assertEqual(body_a["data"]["desired_position"], "AI全栈工程师")

                # Browser A detail reflects update
                detail_a = client_a.get(f"/api/resumes/detail/{filename}").json()
                self.assertTrue(detail_a["ok"])
                self.assertEqual(detail_a["data"]["desired_salary"], "18k-25k")

                # Browser B cannot overwrite Browser A's resume
                put_b = client_b.put(
                    f"/api/resumes/{filename}",
                    json={"desired_position": "恶意篡改"},
                )
                self.assertEqual(put_b.status_code, 404)
                self.assertEqual(put_b.json()["error_code"], "NOT_FOUND")

                # Validation: blank name -> 400 INVALID_INPUT
                bad_name = client_a.put(
                    f"/api/resumes/{filename}",
                    json={"name": "   "},
                )
                self.assertEqual(bad_name.status_code, 400)
                self.assertEqual(bad_name.json()["error_code"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
