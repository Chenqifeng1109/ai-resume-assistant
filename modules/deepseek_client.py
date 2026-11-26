# ============================================
# modules/deepseek_client.py — DeepSeek API 调用模块
# 大白话：这个文件负责和 DeepSeek 大模型对话
# 所有需要 AI 思考的地方都通过它
# ============================================
from openai import OpenAI
from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    LLM_PROVIDER_PRESETS,
    LOGS_DIR,
)
import os
import json
import re
from datetime import datetime

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_TIMEOUT = float(os.getenv("LLM_TIMEOUT", os.getenv("DEEPSEEK_TIMEOUT", "60")) or 60)
AUTO_PROVIDER_ORDER = ("zhipu", "gemini", "siliconflow", "aliyun", "deepseek")


class DeepSeekCallError(RuntimeError):
    """结构化的大模型调用异常，便于上层区分配置、余额、限流与超时。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _env_or_empty(name: str) -> str:
    val = os.getenv(name)
    return val.strip() if isinstance(val, str) else ""


def _is_zhipu_always_thinking_model(model: str) -> bool:
    """判断是否为智谱强制思考模型（不支持 thinking=disabled）。"""
    lowered = (model or "").strip().lower()
    return lowered == "glm-5" or lowered.startswith(("glm-5.1", "glm-5.2", "glm-5.3", "glm-5.4"))


def _is_zhipu_toggle_thinking_model(model: str) -> bool:
    """判断是否为支持关闭深度思考的智谱模型（如 glm-4.7 / glm-5-turbo / glm-4.5* / glm-4.6*）。"""
    lowered = (model or "").strip().lower()
    return lowered.startswith(("glm-4.5", "glm-4.6", "glm-4.7", "glm-5-turbo"))


def resolve_llm_config() -> dict:
    """动态解析当前激活的大模型引擎配置（支持智谱/Gemini/硅基流动/阿里百炼/DeepSeek/自定义）。"""
    provider = _env_or_empty("LLM_PROVIDER").lower() or "auto"
    generic_key = _env_or_empty("LLM_API_KEY")
    generic_base = _env_or_empty("LLM_BASE_URL")
    generic_model = _env_or_empty("LLM_MODEL")
    timeout_raw = _env_or_empty("LLM_TIMEOUT") or _env_or_empty("DEEPSEEK_TIMEOUT")
    timeout = float(timeout_raw) if timeout_raw else DEFAULT_DEEPSEEK_TIMEOUT

    def _provider_key(code: str) -> str:
        preset = LLM_PROVIDER_PRESETS.get(code)
        if not preset:
            return ""
        key_env = preset["key_env"]
        val = os.getenv(key_env)
        if val is not None:
            return val.strip()
        if code == "deepseek":
            return (DEEPSEEK_API_KEY or "").strip()
        return ""

    selected_provider = provider
    api_key = ""
    base_url = ""
    model = ""
    preset_fallback = ""

    if provider != "auto" and provider in LLM_PROVIDER_PRESETS:
        preset = LLM_PROVIDER_PRESETS[provider]
        api_key = generic_key or _provider_key(provider)
        base_url = generic_base or preset["base_url"]
        model = generic_model or (
            (_env_or_empty("DEEPSEEK_MODEL") or DEEPSEEK_MODEL)
            if provider == "deepseek"
            else preset["model"]
        )
        preset_fallback = preset.get("fallback_model", "")
    elif provider != "auto":
        # 自定义 OpenAI 兼容平台
        selected_provider = provider
        api_key = generic_key or _provider_key("deepseek")
        base_url = generic_base or DEFAULT_DEEPSEEK_BASE_URL
        model = generic_model or (_env_or_empty("DEEPSEEK_MODEL") or DEEPSEEK_MODEL)
    else:
        # auto 模式：优先 LLM_API_KEY，其次按预设顺序检测已配置的厂商密钥
        if generic_key:
            selected_provider = "custom"
            api_key = generic_key
            base_url = generic_base or DEFAULT_DEEPSEEK_BASE_URL
            model = generic_model or (_env_or_empty("DEEPSEEK_MODEL") or DEEPSEEK_MODEL)
        else:
            matched = None
            for code in AUTO_PROVIDER_ORDER:
                candidate_key = _provider_key(code)
                if candidate_key:
                    matched = (code, candidate_key)
                    break
            if matched:
                selected_provider, api_key = matched
                preset = LLM_PROVIDER_PRESETS[selected_provider]
                base_url = generic_base or preset["base_url"]
                model = generic_model or (
                    (_env_or_empty("DEEPSEEK_MODEL") or DEEPSEEK_MODEL)
                    if selected_provider == "deepseek"
                    else preset["model"]
                )
                preset_fallback = preset.get("fallback_model", "")
            else:
                selected_provider = "deepseek"
                api_key = ""
                base_url = generic_base or DEFAULT_DEEPSEEK_BASE_URL
                model = generic_model or (_env_or_empty("DEEPSEEK_MODEL") or DEEPSEEK_MODEL)

    fallback_model = _env_or_empty("LLM_FALLBACK_MODEL") or preset_fallback
    if fallback_model == model:
        fallback_model = ""

    if not timeout_raw and selected_provider == "zhipu" and _is_zhipu_always_thinking_model(model):
        timeout = max(timeout, 120.0)

    return {
        "provider": selected_provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "fallback_model": fallback_model,
        "timeout": timeout,
    }


def resolve_deepseek_api_key() -> str:
    """返回当前激活引擎的 API 密钥（保留原函数名以向后兼容）。"""
    return resolve_llm_config()["api_key"]


def get_active_llm_model() -> str:
    """返回当前激活的大模型名称（如 glm-5.3-flash / gemini-3.8-flash / deepseek-chat）。"""
    return resolve_llm_config()["model"]


def _messages_request_json(messages: list[dict]) -> bool:
    """判断提示词是否明确要求返回 JSON 对象，用于启用智谱原生 JSON Mode 防止引号/逗号破损。"""
    for msg in messages or []:
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if isinstance(content, str) and "json" in content.lower():
            return True
    return False


def build_chat_completion_kwargs(
    *,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    provider: str | None = None,
) -> dict:
    """统一组装 chat.completions.create 参数，自动适配智谱快速直出与始终思考模型。"""
    active_provider = (provider or resolve_llm_config()["provider"] or "").lower()
    effective_max_tokens = max_tokens
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": effective_max_tokens,
    }
    if active_provider == "zhipu":
        if _is_zhipu_always_thinking_model(model):
            effort = _env_or_empty("LLM_THINKING_EFFORT").lower() or "low"
            if effort not in ("low", "high", "max"):
                effort = "low"
            kwargs["max_tokens"] = max(effective_max_tokens, 8192)
            kwargs["extra_body"] = {"thinking": {"type": "enabled", "effort": effort}}
        elif _is_zhipu_toggle_thinking_model(model):
            thinking_mode = _env_or_empty("LLM_THINKING_MODE").lower() or "disabled"
            if thinking_mode == "enabled":
                kwargs["max_tokens"] = max(effective_max_tokens, 8192)
                kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            else:
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            if _messages_request_json(messages):
                kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def _is_valid_json_reply(content: str) -> bool:
    """检查模型返回文本是否包含可解析的 JSON 对象（兼容代码块包裹与尾逗号）。"""
    if not isinstance(content, str) or not content.strip():
        return False
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return False
    candidate = match.group()
    try:
        return isinstance(json.loads(candidate), dict)
    except json.JSONDecodeError:
        try:
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
            return isinstance(json.loads(repaired), dict)
        except json.JSONDecodeError:
            return False


def _extract_response_content(response) -> str | None:
    try:
        choices = getattr(response, "choices", None)
        if not choices:
            return None
        content = getattr(choices[0].message, "content", None)
        return content if isinstance(content, str) else None
    except Exception:
        return None


def create_chat_completion_with_fallback(
    client_obj,
    *,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    provider: str | None = None,
    fallback_model: str | None = None,
):
    """发起 chat completion 请求；遇 429/超时/JSON破损时自动降级到备选模型重试一次。"""
    req_kwargs = build_chat_completion_kwargs(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )
    resolved_fallback = (
        fallback_model
        if fallback_model is not None
        else resolve_llm_config().get("fallback_model", "")
    ).strip()

    def _call_fallback():
        fb_kwargs = build_chat_completion_kwargs(
            model=resolved_fallback,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            provider=provider,
        )
        return client_obj.chat.completions.create(**fb_kwargs)

    try:
        response = client_obj.chat.completions.create(**req_kwargs)
    except Exception as exc:
        code, _ = classify_deepseek_error(exc)
        if code not in ("RATE_LIMITED", "TIMEOUT") or not resolved_fallback or resolved_fallback == model:
            raise
        return _call_fallback()

    if (
        _messages_request_json(messages)
        and resolved_fallback
        and resolved_fallback != model
    ):
        content = _extract_response_content(response)
        if content is not None and not _is_valid_json_reply(content):
            try:
                fb_response = _call_fallback()
                fb_content = _extract_response_content(fb_response)
                if fb_content is not None and _is_valid_json_reply(fb_content):
                    return fb_response
            except Exception:
                return response

    return response


def classify_deepseek_error(exc: Exception) -> tuple[str, str]:
    """将底层异常归类为稳定错误码与用户可读的中文提示。"""
    if isinstance(exc, DeepSeekCallError):
        return exc.code, exc.message

    status_code = getattr(exc, "status_code", None)
    text = str(exc or "")
    lowered = text.lower()
    class_name = exc.__class__.__name__.lower()

    if "api_key" in lowered and ("missing" in lowered or "empty" in lowered or "没找到" in text):
        return "CONFIG_MISSING", "未配置大模型 API 密钥，请先点击右上角「⚙️ 模型设置」填入你的 API Key"
    if status_code == 402 or "insufficient balance" in lowered or "余额不足" in text or "arrearage" in lowered:
        return "INSUFFICIENT_BALANCE", "大模型 API 余额不足（402），请充值或切换其他可用模型引擎"
    if status_code == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return "RATE_LIMITED", "大模型 API 请求过于频繁（429），请稍后重试"
    if status_code in (401, 403) or "invalid api key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        return "AUTH_FAILED", "大模型 API 密钥无效或无权限，请点击右上角「⚙️ 模型设置」检查密钥配置"
    if (
        isinstance(exc, TimeoutError)
        or "timeout" in class_name
        or "timed out" in lowered
        or "timeout" in lowered
    ):
        return "TIMEOUT", "大模型 API 响应超时，请稍后重试"
    return "UPSTREAM_ERROR", f"大模型 API 调用失败: {text[:180]}"


def create_openai_client(timeout: float | None = None) -> OpenAI:
    """按需创建带超时保护的通用 OpenAI 兼容客户端，避免导入期崩溃。"""
    cfg = resolve_llm_config()
    if not cfg["api_key"]:
        raise DeepSeekCallError(
            "CONFIG_MISSING",
            "未配置大模型 API 密钥，请先点击右上角「⚙️ 模型设置」填入你的 API Key",
        )
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        timeout=cfg["timeout"] if timeout is None else timeout,
        max_retries=0,
    )


_INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\ufeff\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_llm_input(text: str) -> str:
    """清洗从招聘网站/微信复制的 JD 或简历中的不可见字符、异常空格与控制符，避免干扰大模型 JSON 输出。"""
    if not isinstance(text, str) or not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u2028", "\n").replace("\u2029", "\n")
    cleaned = cleaned.replace("\u00a0", " ").replace("\u3000", " ")
    cleaned = _INVISIBLE_CHARS_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned


def _repair_unescaped_quotes_in_json(text: str) -> str:
    """状态机修复 JSON 字符串内部的未转义英文双引号与裸换行（如 "负责"AI产品"落地"）。"""
    out: list[str] = []
    in_string = False
    escaped = False
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
            elif ch == "\\":
                out.append(ch)
                escaped = True
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                pass
            elif ch == '"':
                j = i + 1
                while j < n and text[j] in " \t\r\n":
                    j += 1
                if j >= n or text[j] in ",:}]":
                    in_string = False
                    out.append('"')
                else:
                    out.append('\\"')
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
        i += 1
    return "".join(out)


def parse_llm_json_robust(raw_text: str) -> dict:
    """多层容错 JSON 解析器：支持去围栏、去尾逗号、容忍控制符、修复字符串内未转义双引号。"""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("AI返回内容为空")
    cleaned = raw_text.replace("\u2028", "\n").replace("\u2029", "\n").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError("AI返回内容中没有找到JSON对象")
    candidate = cleaned[start:end]

    attempts = [
        candidate,
        re.sub(r",\s*([}\]])", r"\1", candidate),
        re.sub(r",\s*([}\]])", r"\1", _repair_unescaped_quotes_in_json(candidate)),
    ]
    last_exc: Exception | None = None
    for attempt_str in attempts:
        try:
            parsed = json.loads(attempt_str, strict=False)
            if isinstance(parsed, dict):
                return parsed
            last_exc = ValueError("AI返回的JSON顶层必须是对象")
        except json.JSONDecodeError as exc:
            last_exc = exc
            continue
    if last_exc is not None:
        raise last_exc
    raise ValueError("AI返回内容不是有效JSON对象")


class DeepSeekClient:
    """通用多引擎大模型客户端（保留 DeepSeekClient 类名以向后兼容）"""

    def __init__(self):
        """初始化：按当前配置连接大模型服务（智谱 / Gemini / 硅基流动 / 阿里百炼 / DeepSeek）"""
        cfg = resolve_llm_config()
        self.provider = cfg["provider"]
        self.client = create_openai_client()
        self.model = cfg["model"]
        self.fallback_model = cfg.get("fallback_model", "")
        self.log_file = os.path.join(LOGS_DIR, "deepseek_calls.log")

    def _log(self, role: str, content: str, tokens: int = 0):
        """记日志：每次对话都写下来，方便查阅"""
        os.makedirs(LOGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {role} (tokens: {tokens})\n{content[:200]}...\n\n")

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        raise_on_error: bool = False,
    ) -> str:
        """
        调用 DeepSeek 对话
        参数：
          system_prompt: 给 AI 的角色设定（比如"你是一个HR专家"）
          user_message: 你要问的具体问题
          temperature: 创造性程度（0=保守，1=开放）
        返回：
          AI 的回复文字
        """
        try:
            clean_user_message = sanitize_llm_input(user_message)
            response = create_chat_completion_with_fallback(
                self.client,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": clean_user_message},
                ],
                temperature=temperature,
                max_tokens=4096,  # 一次最多返回4000多字；始终思考模型自动扩容至8192
                provider=self.provider,
                fallback_model=getattr(self, "fallback_model", None),
            )
            reply = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else 0
            self._log("AI回复", reply, tokens)
            return reply
        except Exception as e:
            code, friendly = classify_deepseek_error(e)
            error_msg = f"❌ [{code}] {friendly}"
            self._log("ERROR", error_msg)
            if raise_on_error:
                raise
            return error_msg

    def chat_json(self, system_prompt: str, user_message: str, temperature: float = 0.3) -> dict:
        """
        调用大模型并要求它返回严格 JSON 对象（自动修复尾逗号/控制字符，遇破损自动重试一次）。
        """
        full_prompt = f"{system_prompt}\n\n请只返回合法 JSON 对象，不要包含 Markdown 代码块或任何额外解释文字。"

        def _try_parse(raw_text: str) -> dict | None:
            try:
                return parse_llm_json_robust(raw_text)
            except Exception:
                return None

        raw = self.chat(full_prompt, user_message, temperature=temperature)
        parsed = _try_parse(raw)
        if parsed is not None:
            return parsed

        # 偶发 JSON 截断或格式损坏时自动以更低温度重试一次，压低偶发 JSON 解析失败率
        retry_prompt = (
            f"{system_prompt}\n\n"
            "注意：上一次回复不是合法 JSON。请精简措辞并严格返回完整闭合的合法 JSON 对象，不要输出任何额外文字。"
        )
        raw_retry = self.chat(retry_prompt, user_message, temperature=0.1)
        parsed_retry = _try_parse(raw_retry)
        if parsed_retry is not None:
            return parsed_retry
        return {"raw": raw_retry or raw, "error": "JSON解析失败"}


# ============================================
# 测试函数：验证 DeepSeek 是否连接正常
# ============================================
def test_connection():
    """跑一下看看 DeepSeek 能不能用"""
    print("=" * 50)
    print("🧪 正在测试 DeepSeek API 连接...")
    print("=" * 50)
    try:
        client = DeepSeekClient()
        result = client.chat(
            system_prompt="你是一个友好的助手，用中文回答。",
            user_message="你好，请用一句话介绍你自己。"
        )
        print(f"\n✅ 连接成功！DeepSeek 回复：\n{result}")
        print(f"\n📁 日志已保存到：{client.log_file}")
        print("\n🎉 DeepSeek API 接入完成！可以进行下一步了。")
        return True
    except Exception as e:
        print(f"\n❌ 连接失败：{e}")
        return False


if __name__ == "__main__":
    test_connection()
