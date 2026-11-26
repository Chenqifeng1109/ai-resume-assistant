import unittest
from unittest.mock import MagicMock, patch

from services.job_login import LoginManager, observe_login


class LoginFlowTests(unittest.TestCase):
    def make_manager(self):
        store = MagicMock()
        store.load.return_value = None
        store.status.return_value = {"auth_status": "unknown"}
        manager = LoginManager(lambda: store)
        manager.task = {"task_id": "test-task", "source": "51job", "running": True}
        browser = MagicMock()
        page = browser.new_context.return_value.new_page.return_value
        page.is_closed.return_value = False
        page.url = "https://we.51job.com/"
        page.locator.return_value.first.is_visible.return_value = False
        runtime = MagicMock()
        runtime.__enter__.return_value.chromium.launch.return_value = browser
        return manager, store, browser, page, runtime

    def test_unknown_login_is_saved_as_unknown_only_on_confirmation(self):
        manager, store, browser, page, runtime = self.make_manager()
        manager.command = "save"
        with patch("playwright.sync_api.sync_playwright", return_value=runtime):
            manager.run()
        self.assertEqual(manager.snapshot()["stage"], "saved")
        self.assertEqual(manager.snapshot()["auth_status"], "unknown")
        self.assertEqual(store.save.call_args.args[2], "unknown")
        browser.close.assert_called_once()
        self.assertFalse(manager.active())

    def test_cancel_and_timeout_never_save(self):
        for command, timeout in (("cancel", 300), (None, 0)):
            manager, store, browser, page, runtime = self.make_manager()
            manager.command = command
            with patch("playwright.sync_api.sync_playwright", return_value=runtime):
                manager.run(timeout_seconds=timeout)
            store.save.assert_not_called()
            self.assertFalse(manager.active())

    def test_reopen_restores_saved_state_in_visible_browser(self):
        manager, store, browser, page, runtime = self.make_manager()
        saved = {"cookies": [], "origins": []}
        store.load.return_value = saved
        manager.command = "cancel"
        with patch("playwright.sync_api.sync_playwright", return_value=runtime):
            manager.run()
        runtime.__enter__.return_value.chromium.launch.assert_called_once_with(
            channel="msedge", headless=False)
        browser.new_context.assert_called_once_with(storage_state=saved)
        page.goto.assert_called_once_with("https://we.51job.com/", wait_until="domcontentloaded", timeout=30000)
        store.save.assert_not_called()

    def test_check_detects_expiration_without_overwriting_state(self):
        manager, store, browser, page, runtime = self.make_manager()
        store.status.return_value = {"last_observed_auth_status": "authenticated"}
        with patch("playwright.sync_api.sync_playwright", return_value=runtime), patch(
            "services.job_login.observe_login", return_value="anonymous"
        ):
            manager.run(check_only=True)
        self.assertEqual(manager.snapshot()["auth_status"], "expired")
        store.save.assert_not_called()

    def test_browser_failure_releases_busy_state(self):
        manager, store, browser, page, runtime = self.make_manager()
        page.goto.side_effect = TimeoutError("private detail")
        with patch("playwright.sync_api.sync_playwright", return_value=runtime):
            manager.run()
        self.assertEqual(manager.snapshot()["stage"], "failed")
        self.assertNotIn("private detail", str(manager.snapshot()))
        self.assertFalse(manager.active())

    def test_stale_task_and_invalid_actions_rejected(self):
        manager, *_ = self.make_manager()
        self.assertEqual(manager.action("old-task", "save")["error_code"], "NOT_FOUND")
        self.assertEqual(manager.action("test-task", "other")["error_code"], "INVALID_INPUT")

    def test_unimplemented_source_and_parallel_start_rejected(self):
        manager, *_ = self.make_manager()
        self.assertFalse(manager.start("liepin")["ok"])
        self.assertEqual(manager.start("51job")["error_code"], "CONFLICT")

    def test_foreign_domain_cannot_claim_authenticated(self):
        page = MagicMock()
        page.url = "https://51job.com.example.org/"
        page.locator.return_value.first.is_visible.return_value = True
        self.assertEqual(observe_login(page), "unknown")

    def test_real_browser_login_markers(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel="msedge", headless=True)
            try:
                page = browser.new_page()
                page.route("**/*", lambda route: route.fulfill(body="<html></html>", content_type="text/html; charset=utf-8"))
                page.goto("https://we.51job.com/")
                for markup, expected in (
                    ('<a href="/logout">退出登录</a>', "authenticated"),
                    ('<input type="password">', "anonymous"),
                    ('<div>普通岗位页面</div>', "unknown"),
                    ('<a href="/logout" hidden>退出登录</a>', "unknown"),
                ):
                    page.set_content(markup)
                    self.assertEqual(observe_login(page), expected)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
