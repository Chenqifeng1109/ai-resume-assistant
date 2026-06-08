# ============================================
# modules/deepseek_client.py — DeepSeek API 调用模块
# 大白话：这个文件负责和 DeepSeek 大模型对话
# 所有需要 AI 思考的地方都通过它
# ============================================
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, LOGS_DIR
import os
import json
from datetime import datetime


class DeepSeekClient:
    """DeepSeek 大模型客户端 — 封装所有 AI 调用"""

    def __init__(self):
        """初始化：连上 DeepSeek 服务器"""
        if not DEEPSEEK_API_KEY:
            raise ValueError("❌ 没找到 API Key！请检查 .env 文件")
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"  # DeepSeek 的 API 地址
        )
        self.model = DEEPSEEK_MODEL
        self.log_file = os.path.join(LOGS_DIR, "deepseek_calls.log")

    def _log(self, role: str, content: str, tokens: int = 0):
        """记日志：每次对话都写下来，方便查阅"""
        os.makedirs(LOGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {role} (tokens: {tokens})\n{content[:200]}...\n\n")

    def chat(self, system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=4096  # 一次最多返回4000多字
            )
            reply = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            self._log("AI回复", reply, tokens)
            return reply
        except Exception as e:
            error_msg = f"❌ DeepSeek 调用失败: {e}"
            self._log("ERROR", error_msg)
            return error_msg

    def chat_json(self, system_prompt: str, user_message: str) -> dict:
        """
        调用 DeepSeek 并要求它返回 JSON 格式
        大白话：让 AI 输出结构化的数据，方便程序处理
        """
        full_prompt = f"{system_prompt}\n\n请只返回 JSON 格式，不要包含其他文字。"
        raw = self.chat(full_prompt, user_message, temperature=0.3)
        # 尝试提取 JSON（AI 有时会在前后加废话）
        try:
            # 找第一个 { 到最后一个 }
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
            return {"raw": raw, "error": "无法解析为JSON"}
        except json.JSONDecodeError:
            return {"raw": raw, "error": "JSON解析失败"}


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
