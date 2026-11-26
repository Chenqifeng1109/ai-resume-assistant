import asyncio
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI, UploadFile

from routers import deliveries, resumes
from services.delivery_service import generate_greeting


class GreetingFailureTests(unittest.TestCase):
    def test_success_empty_and_exception_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "resume.json").write_text(
                json.dumps({"name": "test", "skills": []}), encoding="utf-8"
            )
            for answer in ("您好", "", "  ", None, TimeoutError("private detail")):
                with self.subTest(answer=type(answer).__name__):
                    client = MagicMock()
                    if isinstance(answer, Exception):
                        client.chat.side_effect = answer
                    else:
                        client.chat.return_value = answer
                    with patch("services.delivery_service.DeepSeekClient", return_value=client):
                        result = generate_greeting("resume.json", data_dir=directory)
                    self.assertTrue(client.chat.call_args.kwargs["raise_on_error"])
                    self.assertEqual(result["ok"], answer == "您好")
                    if not result["ok"]:
                        self.assertEqual(result["error_code"], "UPSTREAM_ERROR")
                        self.assertNotIn("greeting", result)
                        self.assertNotIn("private detail", str(result))


class UploadRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_endpoint_does_not_block_other_requests(self):
        app = FastAPI()
        app.include_router(resumes.router)

        @app.get("/probe")
        async def probe():
            return {"ok": True}

        started = threading.Event()
        release = threading.Event()
        thread_ids = []

        def parse(path):
            thread_ids.append(threading.get_ident())
            started.set()
            if not release.wait(5):
                raise TimeoutError("test release missing")
            return {"name": "test"}

        def save(result):
            thread_ids.append(threading.get_ident())
            return "test.json"

        with tempfile.TemporaryDirectory() as directory, patch.object(
            resumes, "RESUMES_DIR", directory
        ), patch.object(resumes, "parse_resume", side_effect=parse), patch.object(
            resumes, "save_parsed_result", side_effect=save
        ), patch.object(resumes, "add_log"):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                task = asyncio.create_task(client.post("/api/resumes/upload", files={"file": ("test.txt", b"test")}))
                try:
                    self.assertTrue(await asyncio.to_thread(started.wait, 2))
                    response = await asyncio.wait_for(client.get("/probe"), 1)
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(task.done())
                finally:
                    release.set()
                    upload = await task
                self.assertEqual(upload.status_code, 200)
                self.assertTrue(upload.json()["ok"])
                self.assertEqual(len(thread_ids), 2)
                self.assertTrue(all(value != threading.get_ident() for value in thread_ids))

    async def test_parse_exception_restores_existing_file_and_removes_new_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            resumes, "RESUMES_DIR", directory
        ), patch.object(resumes, "parse_resume", side_effect=RuntimeError("private")), patch.object(
            resumes, "save_parsed_result"
        ) as save, patch.object(resumes, "add_log"):
            existing = Path(directory, "old.txt")
            existing.write_bytes(b"original")
            for filename in ("old.txt", "new.txt"):
                result = await resumes.upload_resume(UploadFile(filename=filename, file=io.BytesIO(b"new")))
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_code"], "INTERNAL_ERROR")
            self.assertEqual(existing.read_bytes(), b"original")
            self.assertFalse(Path(directory, "new.txt").exists())
            save.assert_not_called()

    async def test_oversized_upload_is_rejected_before_parse(self):
        with patch.object(resumes, "MAX_RESUME_SIZE", 3), patch.object(resumes, "parse_resume") as parse:
            file = UploadFile(filename="test.txt", file=io.BytesIO(b"12345"))
            result = await resumes.upload_resume(file)
            self.assertFalse(result["ok"])
            self.assertTrue(file.file.closed)
            parse.assert_not_called()

    async def test_greeting_endpoint_returns_502_for_upstream_failure(self):
        app = FastAPI()
        app.include_router(deliveries.router)
        with patch.object(deliveries, "generate_greeting_service", return_value={
            "ok": False, "error": "AI开场白生成失败", "error_code": "UPSTREAM_ERROR"
        }):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/deliver/greeting", data={"resume_file": "test.json"})
        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()["ok"])


if __name__ == "__main__":
    unittest.main()
