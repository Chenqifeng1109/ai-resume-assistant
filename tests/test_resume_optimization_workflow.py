import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from modules.db_client import init_db
from modules.resume_optimization_tasks import create_task, get_task
from services import resume_optimization
from services.resume_optimization_tasks import run_optimization_task
from tests.test_resume_optimization_integrity import FakeDeepSeekClient, sample_profile


class TimeoutThenSuccessClient(FakeDeepSeekClient):
    def __init__(self):
        self.calls = 0

    def chat(self, system_prompt, user_message, temperature, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("request timed out")
        return super().chat(system_prompt, user_message, temperature, **kwargs)


class AuthenticationFailure:
    status_code = 401

    def __init__(self):
        self.calls = 0

    def chat(self, system_prompt, user_message, temperature, **kwargs):
        self.calls += 1
        raise RuntimeError("API key authentication failed")


class InvalidJsonClient:
    def chat(self, system_prompt, user_message, temperature, **kwargs):
        return "这不是JSON"


class ResumeOptimizationWorkflowTests(unittest.TestCase):
    def _write_profile(self, directory):
        filename = "resume_workflow.json"
        Path(directory, filename).write_text(
            json.dumps(sample_profile(), ensure_ascii=False),
            encoding="utf-8",
        )
        return filename

    def test_task_is_persisted_with_request_data(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory, "workflow.db"))
            init_db(db_path)
            task = create_task(
                {"resume_file": "resume.json", "target": "AI产品助理"},
                db_path,
            )
            stored = get_task(task["task_id"], db_path)
            self.assertEqual(stored["status"], "queued")
            self.assertEqual(stored["request_data"]["target"], "AI产品助理")

    def test_transient_timeout_retries_once_then_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = self._write_profile(directory)
            client = TimeoutThenSuccessClient()
            with (
                patch.object(resume_optimization, "DATA_DIR", directory),
                patch.object(resume_optimization, "DeepSeekClient", return_value=client),
            ):
                result = resume_optimization.optimize_resume(
                    filename,
                    "AI产品助理",
                    retry_delay=0,
                )
            self.assertTrue(result["ok"])
            self.assertEqual(client.calls, 2)
            self.assertEqual(result["attempts"], 2)

    def test_authentication_error_does_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = self._write_profile(directory)
            client = AuthenticationFailure()
            with (
                patch.object(resume_optimization, "DATA_DIR", directory),
                patch.object(resume_optimization, "DeepSeekClient", return_value=client),
            ):
                result = resume_optimization.optimize_resume(
                    filename,
                    "AI产品助理",
                    retry_delay=0,
                )
            self.assertFalse(result["ok"])
            self.assertEqual(result["failure_code"], "AI_AUTH_ERROR")
            self.assertEqual(client.calls, 1)

    def test_invalid_json_keeps_raw_response_and_failed_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = self._write_profile(directory)
            db_path = str(Path(directory, "workflow.db"))
            task = create_task(
                {"resume_file": filename, "target": "AI产品助理", "extra": "", "job_description": ""},
                db_path,
            )
            with (
                patch.object(resume_optimization, "DATA_DIR", directory),
                patch.object(resume_optimization, "DeepSeekClient", return_value=InvalidJsonClient()),
            ):
                run_optimization_task(task["task_id"], db_path)
            failed = get_task(task["task_id"], db_path)
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["stage"], "parsing_response")
            self.assertEqual(failed["error_code"], "AI_RESPONSE_INVALID")
            self.assertEqual(failed["raw_response"], "这不是JSON")
            self.assertEqual(failed["request_data"]["resume_file"], filename)

    def test_frontend_uses_task_endpoint_and_restores_saved_task(self):
        source = Path("frontend/src/components/AIAssistant.jsx").read_text(encoding="utf-8")
        self.assertIn("offerforge.resumeOptimizationTaskId", source)
        self.assertIn("/api/resume/optimize/tasks", source)
        self.assertIn("retryOptimizationTask", source)
        self.assertIn("OPTIMIZATION_STAGE_LABELS", source)

    def test_task_route_returns_202_without_waiting_for_result_contract(self):
        queued_task = {
            "ok": True,
            "task_id": "OF-test-task",
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "request_data": {"resume_file": "resume.json", "target": "AI产品助理"},
        }
        with (
            patch("routers.resume_actions.start_optimization_task", return_value=queued_task),
            patch("routers.resume_actions.run_optimization_task") as runner,
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/resume/optimize/tasks",
                data={"resume_file": "resume.json", "target": "AI产品助理"},
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["task_id"], "OF-test-task")
        runner.assert_called_once_with("OF-test-task")


if __name__ == "__main__":
    unittest.main()
