"""AI 通用多引擎配置、懒加载、无密钥冷启动与错误分类回归测试。"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import modules.deepseek_client as deepseek_client
import modules.jd_matcher as jd_matcher


CLEAN_LLM_ENV = {
    "LLM_PROVIDER": "",
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "",
    "LLM_MODEL": "",
    "ZHIPU_API_KEY": "",
    "GEMINI_API_KEY": "",
    "SILICONFLOW_API_KEY": "",
    "DASHSCOPE_API_KEY": "",
    "DEEPSEEK_API_KEY": "",
}


class _FakeStatusError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class AIClientResilienceTests(unittest.TestCase):
    def test_import_app_without_api_key_does_not_crash(self):
        """模拟 Vercel 无任何大模型密钥环境，导入 app 和 jd_matcher 不得崩溃。"""
        env = dict(os.environ)
        env.update(CLEAN_LLM_ENV)
        env["VERCEL"] = "1"
        root = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import app, modules.jd_matcher, modules.jd_analysis; print('IMPORT_OK')",
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, f"无密钥导入失败: {proc.stderr}")
        self.assertIn("IMPORT_OK", proc.stdout)

    def test_match_and_quick_match_return_config_missing_without_key(self):
        """无密钥时调用匹配函数返回明确 CONFIG_MISSING，而不是未捕获异常。"""
        with patch.dict(os.environ, CLEAN_LLM_ENV, clear=False), patch.object(
            deepseek_client, "DEEPSEEK_API_KEY", ""
        ):
            res1 = jd_matcher.match_resume_to_jd({"name": "测试"}, "招聘Python开发")
            res2 = jd_matcher.quick_match({"name": "测试"}, "招聘Python开发")

        self.assertFalse(res1["ok"])
        self.assertEqual(res1["error_code"], "CONFIG_MISSING")
        self.assertIn("API 密钥", res1["error"])

        self.assertFalse(res2["ok"])
        self.assertEqual(res2["error_code"], "CONFIG_MISSING")
        self.assertIn("API 密钥", res2["error"])

    def test_multi_engine_auto_resolves_zhipu_gemini_and_custom(self):
        """通用多引擎支持自动识别智谱、Gemini 以及自定义覆盖参数。"""
        # 1. 智谱自动识别
        zhipu_env = dict(CLEAN_LLM_ENV, ZHIPU_API_KEY="zp-test-key")
        with patch.dict(os.environ, zhipu_env, clear=False), patch.object(
            deepseek_client, "DEEPSEEK_API_KEY", ""
        ):
            cfg = deepseek_client.resolve_llm_config()
            self.assertEqual(cfg["provider"], "zhipu")
            self.assertEqual(cfg["api_key"], "zp-test-key")
            self.assertEqual(cfg["base_url"], "https://open.bigmodel.cn/api/paas/v4/")
            self.assertEqual(cfg["model"], "glm-4.7")
            self.assertEqual(cfg["fallback_model"], "glm-5-turbo")
            self.assertEqual(deepseek_client.get_active_llm_model(), "glm-4.7")

        # 2. Gemini 显式指定 + 模型覆盖
        gemini_env = dict(
            CLEAN_LLM_ENV,
            LLM_PROVIDER="gemini",
            GEMINI_API_KEY="AIza-test-key",
            LLM_MODEL="gemini-4-argon",
        )
        with patch.dict(os.environ, gemini_env, clear=False):
            cfg = deepseek_client.resolve_llm_config()
            self.assertEqual(cfg["provider"], "gemini")
            self.assertEqual(cfg["api_key"], "AIza-test-key")
            self.assertEqual(
                cfg["base_url"],
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            self.assertEqual(cfg["model"], "gemini-4-argon")

        # 3. 硅基流动自动识别
        sf_env = dict(CLEAN_LLM_ENV, SILICONFLOW_API_KEY="sf-test-key")
        with patch.dict(os.environ, sf_env, clear=False), patch.object(
            deepseek_client, "DEEPSEEK_API_KEY", ""
        ):
            cfg = deepseek_client.resolve_llm_config()
            self.assertEqual(cfg["provider"], "siliconflow")
            self.assertEqual(cfg["base_url"], "https://api.siliconflow.cn/v1")

    def test_classify_deepseek_error_categories(self):
        """准确区分余额不足、限流、超时、鉴权失败与通用上游异常。"""
        code, msg = deepseek_client.classify_deepseek_error(
            _FakeStatusError(402, "Error code: 402 - Insufficient Balance")
        )
        self.assertEqual(code, "INSUFFICIENT_BALANCE")
        self.assertIn("余额不足", msg)

        code, msg = deepseek_client.classify_deepseek_error(
            _FakeStatusError(429, "Too Many Requests")
        )
        self.assertEqual(code, "RATE_LIMITED")
        self.assertIn("频繁", msg)

        code, msg = deepseek_client.classify_deepseek_error(TimeoutError("Request timed out"))
        self.assertEqual(code, "TIMEOUT")
        self.assertIn("超时", msg)

        code, msg = deepseek_client.classify_deepseek_error(
            _FakeStatusError(401, "Invalid API key")
        )
        self.assertEqual(code, "AUTH_FAILED")
        self.assertIn("密钥无效", msg)

    def test_create_openai_client_applies_timeout(self):
        """创建 OpenAI 客户端时必须显式传入 timeout，防止请求无限挂起。"""
        env = dict(CLEAN_LLM_ENV, ZHIPU_API_KEY="zp-test-key")
        with patch.dict(os.environ, env, clear=False), patch.object(
            deepseek_client, "OpenAI"
        ) as mock_openai:
            deepseek_client.create_openai_client(timeout=45.0)
            mock_openai.assert_called_once_with(
                api_key="zp-test-key",
                base_url="https://open.bigmodel.cn/api/paas/v4/",
                timeout=45.0,
                max_retries=0,
            )

    def test_zhipu_glm47_disables_thinking_by_default(self):
        """智谱默认 glm-4.7 与备选 glm-5-turbo 默认关闭深度思考以实现秒级直出。"""
        env = dict(
            CLEAN_LLM_ENV,
            ZHIPU_API_KEY="zp-test-key",
            LLM_TIMEOUT="",
            DEEPSEEK_TIMEOUT="",
            LLM_THINKING_MODE="",
        )
        with patch.dict(os.environ, env, clear=False):
            cfg = deepseek_client.resolve_llm_config()
            self.assertEqual(cfg["model"], "glm-4.7")
            self.assertEqual(cfg["fallback_model"], "glm-5-turbo")
            self.assertEqual(cfg["timeout"], 60.0)
            kw_primary = deepseek_client.build_chat_completion_kwargs(
                model="glm-4.7",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.3,
                max_tokens=1500,
                provider="zhipu",
            )
            self.assertEqual(kw_primary["max_tokens"], 1500)
            self.assertEqual(kw_primary["extra_body"], {"thinking": {"type": "disabled"}})

            self.assertNotIn("response_format", kw_primary)

            kw_json = deepseek_client.build_chat_completion_kwargs(
                model="glm-4.7",
                messages=[{"role": "system", "content": "请只返回JSON格式"}],
                temperature=0.3,
                max_tokens=1500,
                provider="zhipu",
            )
            self.assertEqual(kw_json["response_format"], {"type": "json_object"})

            kw_turbo = deepseek_client.build_chat_completion_kwargs(
                model="glm-5-turbo",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.3,
                max_tokens=1500,
                provider="zhipu",
            )
            self.assertEqual(kw_turbo["extra_body"], {"thinking": {"type": "disabled"}})

    def test_zhipu_glm5_always_thinking_defaults_to_120s_timeout_and_low_thinking(self):
        """显式切回智谱 glm-5.3-flash 始终思考模型时，仍保留 120s 超时、low 思考强度与 8192 预算。"""
        env = dict(
            CLEAN_LLM_ENV,
            ZHIPU_API_KEY="zp-test-key",
            LLM_MODEL="glm-5.3-flash",
            LLM_TIMEOUT="",
            DEEPSEEK_TIMEOUT="",
        )
        with patch.dict(os.environ, env, clear=False):
            cfg = deepseek_client.resolve_llm_config()
            self.assertEqual(cfg["timeout"], 120.0)
            kw = deepseek_client.build_chat_completion_kwargs(
                model=cfg["model"],
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.3,
                max_tokens=1500,
                provider=cfg["provider"],
            )
            self.assertEqual(kw["max_tokens"], 8192)
            self.assertEqual(kw["extra_body"], {"thinking": {"type": "enabled", "effort": "low"}})

    def test_fallback_model_triggers_on_429_and_timeout_only(self):
        """遇 429 限流或超时时自动降级到 glm-5-turbo 重试一次；401 鉴权失败不降级。"""

        class _FakeCompletions:
            def __init__(self, errors_first):
                self.calls = []
                self._errors_first = list(errors_first)

            def create(self, **kwargs):
                self.calls.append(kwargs)
                if self._errors_first:
                    err = self._errors_first.pop(0)
                    if err is not None:
                        raise err
                return {"ok": True, "used_model": kwargs["model"]}

        class _FakeClient:
            def __init__(self, errors_first):
                self.chat = type("Chat", (), {"completions": _FakeCompletions(errors_first)})()

        env = dict(CLEAN_LLM_ENV, ZHIPU_API_KEY="zp-test-key", LLM_FALLBACK_MODEL="")
        with patch.dict(os.environ, env, clear=False):
            # 1) 429 -> 自动降级 glm-5-turbo
            c429 = _FakeClient([_FakeStatusError(429, "Too Many Requests"), None])
            res = deepseek_client.create_chat_completion_with_fallback(
                c429,
                model="glm-4.7",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                max_tokens=500,
                provider="zhipu",
            )
            self.assertEqual(res["used_model"], "glm-5-turbo")
            self.assertEqual([c["model"] for c in c429.chat.completions.calls], ["glm-4.7", "glm-5-turbo"])
            self.assertEqual(c429.chat.completions.calls[1]["extra_body"], {"thinking": {"type": "disabled"}})

            # 2) Timeout -> 自动降级 glm-5-turbo
            cto = _FakeClient([TimeoutError("Request timed out"), None])
            res_to = deepseek_client.create_chat_completion_with_fallback(
                cto,
                model="glm-4.7",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                max_tokens=500,
                provider="zhipu",
            )
            self.assertEqual(res_to["used_model"], "glm-5-turbo")

            # 3) 401 -> 不降级，直接抛出
            c401 = _FakeClient([_FakeStatusError(401, "Invalid API key")])
            with self.assertRaises(_FakeStatusError):
                deepseek_client.create_chat_completion_with_fallback(
                    c401,
                    model="glm-4.7",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.2,
                    max_tokens=500,
                    provider="zhipu",
                )
            self.assertEqual(len(c401.chat.completions.calls), 1)

    def test_fallback_model_triggers_on_malformed_json_reply(self):
        """JSON 请求下主模型返回破损 JSON 时，自动切 glm-5-turbo 重试一次并返回合法结果。"""

        def _fake_resp(text: str):
            msg = type("Msg", (), {"content": text})()
            choice = type("Choice", (), {"message": msg})()
            return type("Resp", (), {"choices": [choice]})()

        class _FakeCompletions:
            def __init__(self, responses):
                self.calls = []
                self._responses = list(responses)

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return self._responses.pop(0)

        class _FakeClient:
            def __init__(self, responses):
                self.chat = type("Chat", (), {"completions": _FakeCompletions(responses)})()

        env = dict(CLEAN_LLM_ENV, ZHIPU_API_KEY="zp-test-key", LLM_FALLBACK_MODEL="")
        with patch.dict(os.environ, env, clear=False):
            c_bad_json = _FakeClient([
                _fake_resp('{"summary": "broken "quote" here"}'),
                _fake_resp('{"summary": "clean valid json"}'),
            ])
            resp = deepseek_client.create_chat_completion_with_fallback(
                c_bad_json,
                model="glm-4.7",
                messages=[{"role": "system", "content": "请只返回JSON格式"}],
                temperature=0.3,
                max_tokens=1500,
                provider="zhipu",
            )
            self.assertEqual([c["model"] for c in c_bad_json.chat.completions.calls], ["glm-4.7", "glm-5-turbo"])
            self.assertIn("clean valid json", resp.choices[0].message.content)


if __name__ == "__main__":
    unittest.main()
