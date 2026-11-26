import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from modules.job_repository import aggregate_job_tracking_board, save_job_batch
from services.delivery_service import generate_greeting


class PreDesktopPolishTests(unittest.TestCase):
    def test_tracking_board_aggregates_across_batches(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "board.db")
            save_job_batch(
                "jobs_20261126_010000.json",
                {
                    "collected_at": "2026-11-26 01:00:00",
                    "jobs": [
                        {"job_id": "j1", "title": "AI产品经理", "company": "腾讯", "status": "interview", "tracking_note": "周五一面", "match_score": 88},
                        {"job_id": "j2", "title": "AI产品运营", "company": "美团", "status": "sent", "tracking_note": "官网已投", "match_score": 82},
                    ],
                },
                db_path,
            )
            save_job_batch(
                "jobs_20261126_020000.json",
                {
                    "collected_at": "2026-11-26 02:00:00",
                    "jobs": [
                        {"job_id": "j3", "title": "数据分析", "company": "网易", "status": "unsent", "match_score": 70},
                        {"job_id": "j4", "title": "产品助理", "company": "京东", "status": "rejected", "match_score": 65},
                    ],
                },
                db_path,
            )
            board = aggregate_job_tracking_board(db_path)
            self.assertTrue(board["ok"])
            self.assertEqual(board["summary"]["total"], 4)
            self.assertEqual(board["summary"]["applied"], 3)
            self.assertEqual(board["summary"]["interview"], 1)
            self.assertEqual(board["summary"]["interview_rate"], 33.3)
            # Interview items sorted first
            self.assertEqual(board["items"][0]["status"], "interview")

    def test_four_scene_copy_center_and_json_unwrap(self):
        captured = {}

        class FakeClient:
            def chat(self, **kwargs):
                captured["user_message"] = kwargs.get("user_message", "")
                return '{"greeting":"邮件主题：应聘AI产品经理 - 测试者\\n\\n您好，非常期待加入贵司。"}'

        with tempfile.TemporaryDirectory() as td:
            rf = "resume_copy.json"
            with open(os.path.join(td, rf), "w", encoding="utf-8") as f:
                json.dump({"name": "测试者", "desired_position": "AI产品经理", "skills": ["SQL"]}, f, ensure_ascii=False)
            with (
                patch("services.delivery_service.DATA_DIR", td),
                patch("services.delivery_service.DeepSeekClient", return_value=FakeClient()),
            ):
                res = generate_greeting(
                    resume_file=rf,
                    direction="腾讯 AI产品经理",
                    scene="cover_letter",
                    tone="concise",
                )
            self.assertTrue(res["ok"])
            self.assertIn("邮件主题", res["greeting"])
            self.assertNotIn('{"greeting"', res["greeting"])
            self.assertIn("大厂干练风", captured["user_message"])

    def test_llm_config_masks_keys_and_blocks_remote_write(self):
        client = TestClient(app)
        read_resp = client.get("/api/system/llm-config")
        self.assertEqual(read_resp.status_code, 200)
        body = read_resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(isinstance(body["presets"], list) and len(body["presets"]) >= 3)

        # Remote forwarded request must be rejected with 403 even without demo token gate
        with patch.dict(os.environ, {"OFFERFORGE_DEMO_TOKEN": "", "DEMO_ACCESS_TOKEN": ""}, clear=False):
            remote_write = client.post(
                "/api/system/llm-config",
                headers={"cf-connecting-ip": "203.0.113.9"},
                json={"provider": "zhipu", "model": "glm-4.7", "api_key": "fake-key"},
            )
        self.assertEqual(remote_write.status_code, 403)
        self.assertEqual(remote_write.json()["error_code"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
