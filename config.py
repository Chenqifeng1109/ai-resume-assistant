# ============================================
# config.py — 项目全局配置
# 大白话：所有设置都在这里改，不用到处找
# ============================================
import os
from dotenv import load_dotenv

# 加载 .env 文件里的配置（API Key 等）
load_dotenv()

# --- DeepSeek API ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")   # 你的 API 密钥
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")  # 模型名称

# --- 文件夹路径 ---
# 支持 PyInstaller 打包后的路径
import sys
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)  # exe 所在目录
else:
    import sys as _sys
if getattr(_sys, 'frozen', False):
    BASE_DIR = os.path.dirname(_sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 项目根目录
DATA_DIR = os.path.join(BASE_DIR, "data")               # 数据库存放处
LOGS_DIR = os.path.join(BASE_DIR, "logs")               # 日志存放处
RESUMES_DIR = os.path.join(BASE_DIR, "resumes")         # 简历文件存放处

# --- 投递策略 ---
MATCH_THRESHOLD = 60       # 匹配度低于60分的岗位不投
MAX_DAILY_DELIVERIES = 50  # 每天最多投50个（防止封号）
COOLDOWN_DAYS = 30         # 同一公司30天内不重复投
MIN_DELAY_SEC = 3          # 每次操作最少间隔3秒
MAX_DELAY_SEC = 8          # 每次操作最多间隔8秒（模拟真人）

# --- 日志配置 ---
LOG_LEVEL = "INFO"         # DEBUG=详细日志 / INFO=普通 / WARNING=只警告
