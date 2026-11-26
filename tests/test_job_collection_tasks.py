import os
import tempfile
import unittest

from modules.job_collection_tasks import (
    create_task,
    get_stop_reason,
    get_task,
    public_status,
    recover_interrupted_tasks,
    request_cancel,
    update_task,
)


class JobCollectionTaskTests(unittest.TestCase):
    def test_task_progress_and_result_survive_new_database_connection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tasks.db")
            created = create_task(
                {"target_position": "数据运营", "target_city": "广州"},
                db_path,
            )

            update_task(
                created["task_id"],
                db_path,
                status="completed",
                stage="completed",
                progress_message="完成，共 3 个岗位",
                progress_percent=100,
                jobs_count=3,
                result_data={"jobs_count": 3},
            )

            restored = get_task(created["task_id"], db_path)
            status = public_status(restored)
            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["jobs_count"], 3)
            self.assertEqual(status["result"], {"jobs_count": 3})
            self.assertFalse(status["running"])

    def test_startup_recovery_marks_unfinished_tasks_interrupted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tasks.db")
            created = create_task({"target_position": "内容运营"}, db_path)
            update_task(
                created["task_id"],
                db_path,
                status="running",
                stage="collecting",
                progress_message="正在采集",
                progress_percent=30,
            )

            recovered_count = recover_interrupted_tasks(db_path)
            restored = get_task(created["task_id"], db_path)
            self.assertEqual(recovered_count, 1)
            self.assertEqual(restored["status"], "interrupted")
            self.assertEqual(restored["error_code"], "WORKER_INTERRUPTED")
            self.assertIn("重新启动", restored["progress_message"])

    def test_cancel_request_is_persistent_and_visible_to_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tasks.db")
            created = create_task({"target_position": "产品助理"}, db_path)

            cancelling = request_cancel(created["task_id"], db_path)

            self.assertEqual(cancelling["status"], "cancelling")
            self.assertEqual(get_stop_reason(created["task_id"], db_path), "cancelled")
            self.assertTrue(public_status(cancelling)["running"])

    def test_expired_deadline_requests_cooperative_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "tasks.db")
            created = create_task({"target_position": "测试工程师"}, db_path)
            update_task(
                created["task_id"],
                db_path,
                deadline_at="2020-01-01T00:00:00+00:00",
            )

            self.assertEqual(get_stop_reason(created["task_id"], db_path), "timed_out")


if __name__ == "__main__":
    unittest.main()
