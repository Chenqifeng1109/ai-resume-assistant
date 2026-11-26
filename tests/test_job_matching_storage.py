import json
import os
import tempfile
import unittest
from unittest.mock import patch

from modules.job_repository import load_job_batch, save_job_batch
from services.job_matching import batch_score_jobs, batch_score_jobs_json


def make_payload() -> dict:
    return {
        "profile": {},
        "keywords": ["python"],
        "count": 2,
        "collected_at": "2026-07-17 00:00:00",
        "jobs": [
            {"job_id": "job-1", "title": "python developer"},
            {"job_id": "job-2", "title": "fastapi engineer"},
        ],
    }


class JobMatchingStorageTests(unittest.TestCase):
    def _assert_entrypoint_syncs_storage(
        self,
        use_json_entrypoint: bool,
        write_legacy_json: bool = False,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "matching.db")
            batch_id = "jobs_20260717_000001.json"
            json_path = os.path.join(temp_dir, batch_id)
            save_job_batch(batch_id, make_payload(), db_path)

            profile = {"name": "candidate"}
            fake_result = {"ok": True, "score": 86, "brief": "matched"}
            with (
                patch("services.job_matching.load_profile", return_value=profile),
                patch("services.job_matching.quick_match", return_value=fake_result),
            ):
                if use_json_entrypoint:
                    result = batch_score_jobs_json(
                        {"jobs_file": batch_id, "threshold": 80},
                        data_dir=temp_dir,
                        db_path=db_path,
                        write_legacy_json=write_legacy_json,
                    )
                else:
                    result = batch_score_jobs(
                        batch_id,
                        threshold=80,
                        data_dir=temp_dir,
                        db_path=db_path,
                        write_legacy_json=write_legacy_json,
                    )

            self.assertTrue(result["ok"])
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["high_score_count"], 2)
            stored = load_job_batch(batch_id, db_path)
            self.assertEqual(stored["resume_name"], "candidate")
            self.assertTrue(stored["auto_scored"])
            self.assertTrue(
                all(job["match_score"] == 86 for job in stored["jobs"])
            )
            if write_legacy_json:
                with open(json_path, "r", encoding="utf-8") as source:
                    self.assertEqual(stored, json.load(source))
            else:
                self.assertFalse(os.path.exists(json_path))

    def test_form_batch_score_updates_repository_without_json(self):
        self._assert_entrypoint_syncs_storage(use_json_entrypoint=False)

    def test_json_batch_score_updates_repository_without_json(self):
        self._assert_entrypoint_syncs_storage(use_json_entrypoint=True)

    def test_legacy_switch_keeps_repository_and_json_equal(self):
        self._assert_entrypoint_syncs_storage(
            use_json_entrypoint=False,
            write_legacy_json=True,
        )

    def test_missing_repository_batch_does_not_create_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "matching.db")
            batch_id = "jobs_20260717_000001.json"

            result = batch_score_jobs(
                batch_id,
                data_dir=temp_dir,
                db_path=db_path,
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "岗位文件不存在")
            self.assertFalse(os.path.exists(os.path.join(temp_dir, batch_id)))


    def test_json_batch_score_reuses_same_resume_cache_and_rescores_for_new_resume(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "matching.db")
            batch_id = "jobs_20261124_000001.json"
            payload = {
                "profile": {},
                "keywords": ["python"],
                "count": 12,
                "collected_at": "2026-11-24 00:00:00",
                "jobs": [
                    {"job_id": f"job-{i}", "title": f"python engineer {i}", "description": "Python FastAPI SQL"}
                    for i in range(12)
                ],
            }
            save_job_batch(batch_id, payload, db_path)

            profile_a = {"name": "candidate_a"}
            profile_b = {"name": "candidate_b"}
            with (
                patch("services.job_matching.load_profile", return_value=profile_a),
                patch("services.job_matching.quick_match", return_value={"ok": True, "score": 88, "brief": "good"}) as mock_qm,
            ):
                # 首次：只评前 10 条，全部 12 条完整保留
                res1 = batch_score_jobs_json(
                    {"jobs_file": batch_id, "threshold": 70},
                    data_dir=temp_dir,
                    db_path=db_path,
                )
                self.assertTrue(res1["ok"])
                self.assertFalse(res1["cached"])
                self.assertEqual(res1["total"], 12)
                self.assertEqual(mock_qm.call_count, 10)

                # 第二次同简历：直接秒返缓存，不再调用 AI
                res2 = batch_score_jobs_json(
                    {"jobs_file": batch_id, "threshold": 70},
                    data_dir=temp_dir,
                    db_path=db_path,
                )
                self.assertTrue(res2["ok"])
                self.assertTrue(res2["cached"])
                self.assertEqual(res2["total"], 12)
                self.assertEqual(mock_qm.call_count, 10)

            # 切换另一份简历 B：绝不复用 A 的旧分数，必须重新评分
            with (
                patch("services.job_matching.load_profile", return_value=profile_b),
                patch("services.job_matching.quick_match", return_value={"ok": True, "score": 61, "brief": "ok"}) as mock_qm_b,
            ):
                res3 = batch_score_jobs_json(
                    {"jobs_file": batch_id, "threshold": 70},
                    data_dir=temp_dir,
                    db_path=db_path,
                )
                self.assertTrue(res3["ok"])
                self.assertFalse(res3["cached"])
                self.assertEqual(res3["resume_name"], "candidate_b")
                self.assertEqual(mock_qm_b.call_count, 10)


if __name__ == "__main__":
    unittest.main()
