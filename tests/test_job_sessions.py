import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock

from modules.job_sessions import BrowserSessionStore


@unittest.skipUnless(os.name == "nt", "DPAPI requires Windows")
class BrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = BrowserSessionStore(self.temp.name)
        self.state = {"cookies": [
            {"name": "demo", "value": "synthetic-secret-value", "domain": ".51job.com",
             "path": "/", "expires": time.time() + 3600, "httpOnly": True,
             "secure": True, "sameSite": "Lax"},
            {"name": "foreign", "value": "no", "domain": ".liepin.com", "expires": -1},
        ], "origins": [{"origin": "https://we.51job.com", "localStorage": [{"name": "demo", "value": "synthetic"}]}]}

    def test_encrypted_roundtrip_and_domain_isolation(self):
        self.store.save("51job", self.state)
        raw = Path(self.temp.name, "51job.dpapi").read_bytes()
        self.assertNotIn(b"synthetic-secret-value", raw)
        restored = BrowserSessionStore(self.temp.name).load("51job")
        self.assertEqual(len(restored["cookies"]), 1)
        self.assertEqual(restored["cookies"][0]["value"], "synthetic-secret-value")
        self.assertEqual(restored["origins"], self.state["origins"])
        self.assertIsNone(self.store.load("liepin"))

    def test_saved_does_not_prove_authenticated(self):
        self.store.save("51job", self.state, "authenticated")
        status = self.store.status("51job")
        self.assertEqual(status["auth_status"], "unknown")
        self.assertEqual(status["last_observed_auth_status"], "authenticated")
        self.assertNotIn("cookies", status)

    def test_expired_cookie_and_expired_session(self):
        self.state["cookies"][0]["expires"] = time.time() - 60
        self.store.save("51job", self.state)
        self.assertEqual(self.store.load("51job")["cookies"], [])
        self.store.save("51job", self.state, "expired")
        self.assertIsNone(self.store.load("51job"))

    def test_clear_corruption_and_path_validation(self):
        self.store.save("51job", self.state)
        Path(self.temp.name, "51job.dpapi").write_bytes(b"invalid")
        self.assertEqual(self.store.status("51job")["storage_status"], "unreadable")
        self.store.clear("51job")
        self.assertEqual(self.store.status("51job")["storage_status"], "missing")
        with self.assertRaises(ValueError):
            self.store.load("../other")

    def test_scraper_close_saves_before_browser_shutdown(self):
        from modules.job_scraper import JobScraper
        scraper = JobScraper()
        scraper.session_store = self.store
        scraper.context = MagicMock()
        scraper.context.storage_state.return_value = self.state
        scraper.browser = MagicMock()
        scraper.playwright = MagicMock()
        scraper.close()
        self.assertEqual(self.store.load("51job")["cookies"][0]["name"], "demo")
        scraper.browser.close.assert_called_once()
        scraper.playwright.stop.assert_called_once()

    def test_real_browser_context_restores_synthetic_cookie(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel="msedge", headless=True)
            try:
                first = browser.new_context()
                first.add_cookies([self.state["cookies"][0]])
                self.store.save("51job", first.storage_state())
                first.close()
                second = browser.new_context(storage_state=self.store.load("51job"))
                cookies = second.cookies("https://we.51job.com/")
                self.assertEqual(cookies[0]["value"], "synthetic-secret-value")
                second.close()
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
