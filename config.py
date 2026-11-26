# ============================================
# config.py — 项目全局配置
# 大白话：所有设置都在这里改，不用到处找
# ============================================
import os
import sys

from dotenv import load_dotenv

# --- 文件夹路径（必须在 load_dotenv 之前确定，确保 exe 从快捷方式启动也能找到同级 .env）---
# 支持 PyInstaller 打包后的路径
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)  # exe 所在目录（存放 .env / data / resumes / logs）
    RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)  # 只读打包资源目录（frontend/dist、static）
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 项目根目录
    RESOURCE_DIR = BASE_DIR

# 加载 .env 文件里的配置（API Key 等）
load_dotenv(os.path.join(BASE_DIR, ".env"))

# --- 通用多引擎大模型配置（兼容 智谱 / 硅基流动 / Gemini / 阿里百炼 / DeepSeek / 自定义 OpenAI 兼容接口）---
LLM_PROVIDER_PRESETS = {
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model": "glm-4.7",
        "fallback_model": "glm-5-turbo",
        "key_env": "ZHIPU_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-3.8-flash",
        "key_env": "GEMINI_API_KEY",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
        "key_env": "SILICONFLOW_API_KEY",
    },
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "key_env": "DASHSCOPE_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower() or "auto"
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "").strip()
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", os.getenv("DEEPSEEK_TIMEOUT", "60")) or 60)

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "").strip()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()

# --- DeepSeek API（保留原有变量名以完全向后兼容） ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")   # 你的 API 密钥
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")  # 模型名称

# --- 运行期数据目录 ---
RUNTIME_DIR = os.getenv("OFFERFORGE_RUNTIME_DIR") or (os.path.join("/tmp", "offerforge") if os.getenv("VERCEL") else BASE_DIR)
DATA_DIR = os.path.join(RUNTIME_DIR, "data")             # 数据库存放处
LOGS_DIR = os.path.join(RUNTIME_DIR, "logs")             # 日志存放处
RESUMES_DIR = os.path.join(RUNTIME_DIR, "resumes")       # 简历文件存放处

# --- 旧版岗位 JSON 兼容开关 ---
# 默认只写 SQLite；需要临时回退时在 .env 中设为 1 并重启服务。
WRITE_LEGACY_JOB_JSON = os.getenv(
    "OFFERFORGE_WRITE_LEGACY_JOB_JSON",
    "0",
).strip().lower() in {"1", "true", "yes", "on"}

# --- 投递策略 ---
MATCH_THRESHOLD = 60       # 匹配度低于60分的岗位不投
MAX_DAILY_DELIVERIES = 50  # 每天最多投50个（防止封号）
COOLDOWN_DAYS = 30         # 同一公司30天内不重复投
MIN_DELAY_SEC = 3          # 每次操作最少间隔3秒
MAX_DELAY_SEC = 8          # 每次操作最多间隔8秒（模拟真人）

# --- 日志配置 ---
LOG_LEVEL = "INFO"         # DEBUG=详细日志 / INFO=普通 / WARNING=只警告
