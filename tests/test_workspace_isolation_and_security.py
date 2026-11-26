"""浏览器会话级物理数据隔离 + 网络安全门禁 + 防刷限流 + JSON 自动修复回归测试。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as app_module
from core import workspace_context
from core.security_middleware import RATE_LIMITER, WORKSPACE_COOKIE_NAME
from modules.db_client import init_db
from modules.deepseek_client import DeepSeekClient


class WorkspaceIsolationAndSecurityTests(unittest.TestCase):
    def setUp(self):
        RATE_LIMITER.reset()

    def test_two_browsers_are_completely_isolated_and_start_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_data = os.path.join(tmpdir, "data")
            root_resumes = os.path.join(tmpdir, "resumes")
            os.makedirs(root_data, exist_ok=True)
            os.makedirs(root_resumes, exist_ok=True)
            root_db = os.path.join(root_data, "offerforge.db")
            init_db(root_db)

            # 在宿主机根库放一份个人简历，模拟用户本地原简历
            import sqlite3

            owner_profile = {
                "name": "宿主机主人简历",
                "phone": "13899990000",
                "email": "owner@example.com",
                "desired_position": "架构师",
                "summary": "个人隐私简历",
                "skills": ["Python"],
            }
            conn = sqlite3.connect(root_db)
            conn.execute(
                "INSERT INTO resumes (filename, name, phone, email, parsed_data) VALUES (?, ?, ?, ?, ?)",
                ("resume_owner.json", owner_profile["name"], owner_profile["phone"], owner_profile["email"], json.dumps(owner_profile, ensure_ascii=False)),
            )
            conn.commit()
            conn.close()

            def _fake_parse(file_path):
                base = os.path.basename(file_path)
                person = "访客甲" if "alice" in base else "访客乙"
                return {
                    "name": person,
                    "phone": "13800001111",
                    "email": f"{person}@example.com",
                    "desired_position": "产品经理" if person == "访客甲" else "后端开发",
                    "summary": f"{person}的专属简历",
                    "skills": ["Python"],
                    "work_experience": [],
                    "education": [],
                    "parsed_at": "2026-11-24 10:00:00",
                    "source_file": base,
                }

            with (
                patch.object(workspace_context, "DATA_DIR", root_data),
                patch.object(workspace_context, "RESUMES_DIR", root_resumes),
                patch("modules.db_client.DB_PATH", root_db),
                patch("routers.resumes.DATA_DIR", root_data),
                patch("routers.resumes.RESUMES_DIR", root_resumes),
                patch("routers.resumes.parse_resume", side_effect=_fake_parse),
                patch.dict(os.environ, {"OFFERFORGE_DEMO_TOKEN": "", "OFFERFORGE_PUBLIC_MODE": "0"}, clear=False),
            ):
                client_a = TestClient(app_module.app)
                client_b = TestClient(app_module.app)

                # 1. 访客 A 首次进入：拿到专属 Cookie，列表为空，看不到宿主机主人的简历
                res_a0 = client_a.get("/api/resumes/list", headers={"X-OfferForge-Isolate": "1"})
                self.assertEqual(res_a0.status_code, 200)
                self.assertEqual(res_a0.json()["resumes"], [])
                ws_a = res_a0.cookies.get(WORKSPACE_COOKIE_NAME)
                self.assertTrue(ws_a)
                # 校验安全响应头存在
                self.assertEqual(res_a0.headers.get("x-content-type-options"), "nosniff")
                self.assertEqual(res_a0.headers.get("x-frame-options"), "SAMEORIGIN")

                # 2. 访客 A 上传自己的简历
                up_a = client_a.post(
                    "/api/resumes/upload",
                    files={"file": ("alice.txt", "访客甲的个人简历内容测试文本".encode("utf-8"), "text/plain")},
                )
                self.assertEqual(up_a.status_code, 200)
                self.assertTrue(up_a.json()["ok"])

                list_a1 = client_a.get("/api/resumes/list").json()["resumes"]
                self.assertEqual(len(list_a1), 1)
                self.assertEqual(list_a1[0]["name"], "访客甲")
                alice_filename = list_a1[0]["filename"]

                # 3. 访客 B 首次进入：拿到不同 Cookie，初始为空，既看不到宿主机主人，也看不到访客甲
                res_b0 = client_b.get("/api/resumes/list", headers={"X-OfferForge-Isolate": "1"})
                ws_b = res_b0.cookies.get(WORKSPACE_COOKIE_NAME)
                self.assertTrue(ws_b)
                self.assertNotEqual(ws_a, ws_b)
                self.assertEqual(res_b0.json()["resumes"], [])

                # 访客 B 即使直接猜文件名也读不到访客甲和宿主机主人的简历
                self.assertFalse(client_b.get(f"/api/resumes/detail/{alice_filename}").json()["ok"])
                self.assertFalse(client_b.get("/api/resumes/detail/resume_owner.json").json()["ok"])

                # 4. 访客 B 上传自己的简历后，双方始终各自只看到自己
                up_b = client_b.post(
                    "/api/resumes/upload",
                    files={"file": ("bob.txt", "访客乙的个人简历内容测试文本".encode("utf-8"), "text/plain")},
                )
                self.assertTrue(up_b.json()["ok"])
                list_b1 = client_b.get("/api/resumes/list").json()["resumes"]
                list_a2 = client_a.get("/api/resumes/list").json()["resumes"]
                self.assertEqual([r["name"] for r in list_b1], ["访客乙"])
                self.assertEqual([r["name"] for r in list_a2], ["访客甲"])

    def test_public_access_token_gate_and_public_mode_restrictions_and_rate_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_data = os.path.join(tmpdir, "data")
            os.makedirs(root_data, exist_ok=True)
            ext_headers = {"X-Forwarded-For": "203.0.113.42"}

            with (
                patch.object(workspace_context, "DATA_DIR", root_data),
                patch.dict(
                    os.environ,
                    {
                        "OFFERFORGE_DEMO_TOKEN": "secret-demo-998",
                        "OFFERFORGE_PUBLIC_MODE": "1",
                        "OFFERFORGE_AI_RATE_LIMIT_PER_MIN": "2",
                    },
                    clear=False,
                ),
            ):
                client = TestClient(app_module.app)

                # 1. 外网无口令被 401 拦截
                st0 = client.get("/api/auth/status", headers=ext_headers).json()
                self.assertTrue(st0["requires_token"])
                self.assertFalse(st0["unlocked"])
                blocked = client.get("/api/resumes/list", headers=ext_headers)
                self.assertEqual(blocked.status_code, 401)
                self.assertEqual(blocked.json()["error_code"], "ACCESS_TOKEN_REQUIRED")

                # 2. 错误口令被拒，正确口令解锁并下发 Cookie
                bad = client.post("/api/auth/unlock", json={"token": "wrong"}, headers=ext_headers)
                self.assertEqual(bad.status_code, 401)
                good = client.post("/api/auth/unlock", json={"token": "secret-demo-998"}, headers=ext_headers)
                self.assertEqual(good.status_code, 200)
                self.assertTrue(good.json()["unlocked"])

                # 解锁后外网可正常访问隔离工作区
                ok_list = client.get("/api/resumes/list", headers=ext_headers)
                self.assertEqual(ok_list.status_code, 200)

                # 3. 公网模式禁止宿主机桌面浏览器操作路由与 51job 浏览器采集
                sess_block = client.get("/api/jobs/sessions", headers=ext_headers)
                self.assertEqual(sess_block.status_code, 403)
                self.assertEqual(sess_block.json()["error_code"], "PUBLIC_MODE_RESTRICTED")

                deliver_block = client.post("/api/deliver/start", headers=ext_headers)
                self.assertEqual(deliver_block.status_code, 403)

                scrape_51 = client.post(
                    "/api/jobs/scrape",
                    data={"platforms": "51job", "resume_file": "r.json", "target_city": "杭州", "target_position": "后端"},
                    headers=ext_headers,
                )
                self.assertEqual(scrape_51.json().get("error_code"), "PUBLIC_MODE_RESTRICTED")

                # 4. 单 IP AI 接口限流生效（每分钟 2 次，第 3 次返回 429）
                rl_headers = {**ext_headers, "X-OfferForge-Test-RateLimit": "1"}
                for _ in range(2):
                    r = client.post("/api/jobs/intent/extract", json={"intent_text": ""}, headers=rl_headers)
                    self.assertNotEqual(r.status_code, 429)
                r3 = client.post("/api/jobs/intent/extract", json={"intent_text": ""}, headers=rl_headers)
                self.assertEqual(r3.status_code, 429)
                self.assertEqual(r3.json()["error_code"], "RATE_LIMITED")

    def test_chat_json_repairs_trailing_comma_and_retries_once_on_broken_json(self):
        client = DeepSeekClient.__new__(DeepSeekClient)
        # 1. 尾逗号直接修复，不触发重试
        calls = []

        def _fake_chat_trailing(sys_p, usr_m, temperature=0.3):
            calls.append(temperature)
            return '{"ok": true, "items": ["a", "b",],}'

        client.chat = _fake_chat_trailing
        parsed = client.chat_json("sys", "usr")
        self.assertEqual(parsed, {"ok": True, "items": ["a", "b"]})
        self.assertEqual(len(calls), 1)

        # 2. 首次输出截断破损 JSON，自动以低温度重试一次并成功
        replies = ['{"target_position": "AI工程师", "optimized_summary": "截断了...', '{"target_position": "AI工程师", "optimized_summary": "完整闭合"}']

        def _fake_chat_retry(sys_p, usr_m, temperature=0.3):
            return replies.pop(0)

        client.chat = _fake_chat_retry
        parsed2 = client.chat_json("sys", "usr")
        self.assertEqual(parsed2["target_position"], "AI工程师")
        self.assertEqual(parsed2["optimized_summary"], "完整闭合")


if __name__ == "__main__":
    unittest.main()
