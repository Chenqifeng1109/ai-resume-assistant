import tempfile
import unittest
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules.job_sessions import BrowserSessionStore
from routers.jobs import router
from services import job_session_management as service


class SessionRouteTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = BrowserSessionStore(directory.name)
        replacement = patch.object(service, "BrowserSessionStore", return_value=self.store)
        replacement.start()
        self.addCleanup(replacement.stop)
        state = patch.object(service, "SCRAPER_STATUS", {"running": False})
        self.state = state.start()
        self.addCleanup(state.stop)
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_metadata_never_exposes_storage_state(self):
        with patch.object(self.store, "status", return_value={"storage_status": "saved", "auth_status": "unknown"}):
            response = self.client.get("/api/jobs/sources/51job/session")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("cookies", response.text)
        self.assertEqual(response.json()["auth_status"], "unknown")

    def test_clear_requires_explicit_boolean_confirmation(self):
        with patch.object(self.store, "clear") as clear:
            for value, code in ((False, 400), ("true", 422), (True, 200)):
                response = self.client.post("/api/jobs/sources/51job/session/clear", json={"confirmed": value})
                self.assertEqual(response.status_code, code)
            clear.assert_called_once_with("51job")

    def test_running_collection_blocks_clear(self):
        self.state["running"] = True
        with patch.object(self.store, "clear") as clear:
            response = self.client.post("/api/jobs/sources/51job/session/clear", json={"confirmed": True})
        self.assertEqual(response.status_code, 409)
        clear.assert_not_called()

    def test_cross_site_and_unknown_source_rejected(self):
        response = self.client.post("/api/jobs/sources/51job/session/clear", json={"confirmed": True}, headers={"Origin": "https://example.com"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/jobs/sources/unknown/session").status_code, 404)

    def test_missing_session_clear_is_idempotent(self):
        for _ in range(2):
            response = self.client.post("/api/jobs/sources/51job/session/clear", json={"confirmed": True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["storage_status"], "missing")


if __name__ == "__main__":
    unittest.main()
