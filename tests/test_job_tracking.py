import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from core.workspace_context import set_workspace_id, reset_workspace_id
from modules.job_repository import load_job_batch, save_job_batch, update_job_tracking
from services.job_matching import batch_score_jobs_json


class FakeScoringClient:
    def chat_json(self, system_prompt, user_message):
        return {
            "results": [
                {"index": 0, "score": 88, "brief": "高匹配度，项目经验贴合"},
                {"index": 1, "score": 74, "brief": "技能匹配良好"},
            ]
        }


class JobTrackingPersistenceTests(unittest.TestCase):
    def _seed_batch(self, db_path: str, batch_id: str = "jobs_20261126_010000.json") -> str:
        save_job_batch(
            batch_id,
            {
                "profile": {"desired_position": "Python后端工程师"},
                "keywords": ["Python后端"],
                "count": 2,
                "collected_at": "2026-11-26 01:00:00",
                "jobs": [
                    {
                        "job_id": "jd-job-101",
                        "title": "Python后端开发工程师",
                        "company": "京东科技",
                        "salary": "18-28K",
                        "location": "北京市",
                        "source": "jd",
                        "url": "https://zhaopin.jd.com/web/job/job_info_list/3",
                    },
                    {
                        "job_id": "",
                        "title": "AI应用研发工程师",
                        "company": "百度在线",
                        "salary": "22-35K",
                        "location": "北京市",
                        "source": "baidu",
                        "url": "https://talent.baidu.com/jobs/social-list",
                    },
                ],
            },
            db_path,
        )
        return batch_id

    def test_repository_update_and_fallback_by_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tracking.db")
            batch_id = self._seed_batch(db_path)

            res1 = update_job_tracking(
                batch_id,
                job_id="jd-job-101",
                job_index=0,
                status="interview",
                note="周四 15:00 腾讯会议一面",
                db_path=db_path,
            )
            self.assertTrue(res1["ok"])
            self.assertEqual(res1["status"], "interview")
            self.assertEqual(res1["tracking_note"], "周四 15:00 腾讯会议一面")
            self.assertTrue(res1["tracked_at"])

            # Fallback to job_index when job_id is empty
            res2 = update_job_tracking(
                batch_id,
                job_id="",
                job_index=1,
                status="sent",
                note="官网内推码已填",
                db_path=db_path,
            )
            self.assertTrue(res2["ok"])
            self.assertEqual(res2["job_index"], 1)
            self.assertEqual(res2["status"], "sent")

            reloaded = load_job_batch(batch_id, db_path)
            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded["jobs"][0]["status"], "interview")
            self.assertEqual(reloaded["jobs"][0]["tracking_note"], "周四 15:00 腾讯会议一面")
            self.assertEqual(reloaded["jobs"][1]["status"], "sent")
            self.assertEqual(reloaded["jobs"][1]["tracking_note"], "官网内推码已填")

    def test_rescore_preserves_tracking_status_and_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = os.path.join(temp_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "offerforge.db")
            batch_id = self._seed_batch(db_path)

            update_job_tracking(
                batch_id,
                job_id="jd-job-101",
                job_index=0,
                status="interview",
                note="HR电话沟通完毕，等技术一面",
                db_path=db_path,
            )

            resume_file = "candidate.json"
            with open(os.path.join(data_dir, resume_file), "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "name": "测试候选人",
                        "desired_position": "Python后端开发工程师",
                        "skills": ["Python", "FastAPI", "SQLite"],
                        "work_experience": [],
                        "education": [],
                    },
                    handle,
                    ensure_ascii=False,
                )

            with (
                patch("modules.db_client.DB_PATH", db_path),
                patch("services.job_matching.DATA_DIR", data_dir),
                patch(
                    "services.job_matching.quick_match",
                    side_effect=lambda profile, jd_text: {
                        "ok": True,
                        "score": 88 if "京东" in jd_text else 74,
                        "brief": "高匹配度，项目经验贴合",
                        "reasons": ["Python", "FastAPI"],
                    },
                ),
            ):
                scored = batch_score_jobs_json(
                    {
                        "jobs_file": batch_id,
                        "resume_file": resume_file,
                        "force_rescore": True,
                    }
                )

            self.assertTrue(scored["ok"])
            reloaded = load_job_batch(batch_id, db_path)
            jd_job = next(item for item in reloaded["jobs"] if item.get("job_id") == "jd-job-101")
            self.assertEqual(jd_job["match_score"], 88)
            self.assertEqual(jd_job["status"], "interview")
            self.assertEqual(jd_job["tracking_note"], "HR电话沟通完毕，等技术一面")
            self.assertTrue(jd_job["tracked_at"])

    def test_api_validation_and_browser_workspace_isolation(self):
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

                # Trigger workspace cookies for Browser A and Browser B
                r_a = client_a.get("/api/jobs/list")
                r_b = client_b.get("/api/jobs/list")
                self.assertEqual(r_a.status_code, 200)
                self.assertEqual(r_b.status_code, 200)
                ws_a = client_a.cookies.get("of_workspace_id")
                ws_b = client_b.cookies.get("of_workspace_id")
                self.assertTrue(ws_a)
                self.assertTrue(ws_b)
                self.assertNotEqual(ws_a, ws_b)

                # Seed batch inside Browser A's isolated workspace SQLite
                tokens = set_workspace_id(ws_a, base_data_dir=temp_dir)
                try:
                    batch_id = self._seed_batch(
                        os.path.join(temp_dir, "workspaces", ws_a, "data", "offerforge.db")
                    )
                finally:
                    reset_workspace_id(tokens)

                # Browser A updates tracking via HTTP endpoint
                track_resp = client_a.post(
                    "/api/jobs/track",
                    json={
                        "batch_id": batch_id,
                        "job_id": "jd-job-101",
                        "job_index": 0,
                        "status": "sent",
                        "note": "已投递京东官网",
                    },
                )
                self.assertEqual(track_resp.status_code, 200)
                track_body = track_resp.json()
                self.assertTrue(track_body["ok"])
                self.assertEqual(track_body["status"], "sent")

                detail_a = client_a.get(f"/api/jobs/detail/{batch_id}").json()
                self.assertTrue(detail_a["ok"])
                self.assertEqual(detail_a["data"]["jobs"][0]["status"], "sent")
                self.assertEqual(detail_a["data"]["jobs"][0]["tracking_note"], "已投递京东官网")

                # Browser B cannot read or mutate Browser A's batch
                detail_b = client_b.get(f"/api/jobs/detail/{batch_id}").json()
                self.assertFalse(detail_b["ok"])
                mutate_b = client_b.post(
                    "/api/jobs/track",
                    json={
                        "batch_id": batch_id,
                        "job_id": "jd-job-101",
                        "job_index": 0,
                        "status": "rejected",
                        "note": "跨浏览器篡改尝试",
                    },
                )
                self.assertEqual(mutate_b.status_code, 404)

                # Validation error checks on Browser A
                bad_status = client_a.post(
                    "/api/jobs/track",
                    json={
                        "batch_id": batch_id,
                        "job_id": "jd-job-101",
                        "job_index": 0,
                        "status": "hired_invalid",
                    },
                )
                self.assertEqual(bad_status.status_code, 400)
                self.assertEqual(bad_status.json()["error_code"], "INVALID_INPUT")

                bad_batch = client_a.post(
                    "/api/jobs/track",
                    json={
                        "batch_id": "../evil_batch.json",
                        "job_index": 0,
                        "status": "sent",
                    },
                )
                self.assertEqual(bad_batch.status_code, 400)
                self.assertEqual(bad_batch.json()["error_code"], "INVALID_INPUT")

                missing_job = client_a.post(
                    "/api/jobs/track",
                    json={
                        "batch_id": batch_id,
                        "job_id": "non-existent-id",
                        "job_index": 99,
                        "status": "sent",
                    },
                )
                self.assertEqual(missing_job.status_code, 404)
                self.assertEqual(missing_job.json()["error_code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
