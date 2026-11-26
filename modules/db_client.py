# ============================================
# modules/db_client.py — 数据库管理中心（咱们的“大文件柜”）
# 大白话：负责连接 SQLite 数据库，并管理所有的数据抽屉（表结构）
# ============================================

import sqlite3
import os
import json
from config import DATA_DIR
from core.workspace_context import get_active_db_path

# 告诉电脑，我们的“大文件柜”放在哪，叫什么名字
DB_PATH = os.path.join(DATA_DIR, "offerforge.db")

def get_connection(db_path=None):
    """
    获取数据库连接
    大白话：拿到打开文件柜的“钥匙”
    """
    target_path = db_path or get_active_db_path(DB_PATH)
    # 确保数据库所在文件夹存在
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    # 连接数据库文件（如果文件不存在，它会自动帮你建一个）
    conn = sqlite3.connect(target_path)
    # 把返回的结果变成类似字典的形式，方便我们用字段名拿数据
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cursor, table_name, column_name, definition):
    """为旧数据库补充缺失字段，重复执行也不会重复添加。"""
    columns = {
        row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )


def init_db(db_path=None):
    """
    初始化数据库表结构
    大白话：在这个新柜子里，钉上项目需要的所有“抽屉”
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # ---------------------------------------------
    # 抽屉 1：【简历库】(resumes)
    # 存放 AI 解析后的简历信息
    # ---------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- 自动编号 (比如 1, 2, 3...)
            filename TEXT UNIQUE NOT NULL,        -- 文件名 (不能重复)
            name TEXT,                            -- 候选人姓名
            phone TEXT,                           -- 电话
            email TEXT,                           -- 邮箱
            parsed_data TEXT,                     -- AI解析出的完整JSON文本 (为了方便我们暂时整块存起来)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- 存入时间
        )
    ''')

    # ---------------------------------------------
    # 抽屉 2：【岗位库】(jobs)
    # 存放爬虫抓下来的岗位列表
    # ---------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,          -- 岗位在招聘平台上的唯一ID (比如 51job_123456)
            platform TEXT NOT NULL,               -- 平台名称 (51job/boss/liepin)
            title TEXT NOT NULL,                  -- 岗位名称
            company TEXT NOT NULL,                -- 公司名称
            salary TEXT,                          -- 薪资范围
            location TEXT,                        -- 工作地点
            url TEXT,                             -- 岗位详情链接
            description TEXT,                     -- 岗位JD详情
            batch_id TEXT,                        -- 所属采集批次
            keywords TEXT,                        -- 本批次搜索关键词
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 兼容已经存在的旧数据库：CREATE TABLE 不会自动给旧表补字段。
    _ensure_column(cursor, "jobs", "batch_id", "TEXT")
    _ensure_column(cursor, "jobs", "keywords", "TEXT")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id)"
    )

    # ---------------------------------------------
    # 抽屉 3：【投递记录库】(deliveries)
    # 记录哪份简历投了哪个岗位，以及目前的进度
    # ---------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,                 -- 投递了哪个岗位
            resume_filename TEXT NOT NULL,        -- 用了哪份简历
            status TEXT DEFAULT 'pending',        -- 投递状态：待投递/已投递/有回复
            match_score INTEGER,                  -- AI 打的匹配分数
            notes TEXT,                           -- 投递备注
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id),
            FOREIGN KEY(resume_filename) REFERENCES resumes(filename)
        )
    ''')

    _ensure_column(cursor, "deliveries", "notes", "TEXT")

    # ---------------------------------------------
    # 抽屉 4：【岗位批次快照】(job_batches)
    # 保存一整个采集批次及其 AI 评分，下一阶段用于替代兼容 JSON 文件。
    # ---------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_batches (
            batch_id TEXT PRIMARY KEY,
            profile_data TEXT,
            keywords TEXT,
            collected_at TEXT,
            resume_name TEXT,
            auto_scored INTEGER NOT NULL DEFAULT 0,
            scored_at TEXT,
            job_count INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # AI简历优化任务：保存执行阶段、中间结果和失败原因，支持刷新后恢复。
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resume_optimization_tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            request_data TEXT NOT NULL DEFAULT '{}',
            raw_response TEXT,
            result_data TEXT,
            error_code TEXT,
            error_message TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_resume_optimization_tasks_updated_at "
        "ON resume_optimization_tasks(updated_at)"
    )

    # 岗位采集任务：即使页面刷新或服务重启，仍保留阶段与失败原因。
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_collection_tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress_message TEXT NOT NULL DEFAULT '',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            jobs_count INTEGER NOT NULL DEFAULT 0,
            request_data TEXT NOT NULL DEFAULT '{}',
            result_data TEXT,
            error_code TEXT,
            error_message TEXT,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            deadline_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_collection_tasks_updated_at "
        "ON job_collection_tasks(updated_at)"
    )
    _ensure_column(cursor, "job_collection_tasks", "cancel_requested", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(cursor, "job_collection_tasks", "deadline_at", "TEXT")

    # 简历版本档案：独立保存原始底稿和每次确认后的优化版本。
    from modules.resume_version_repository import (
        ensure_resume_version_schema,
        migrate_embedded_resume_versions,
    )

    ensure_resume_version_schema(conn)
    migrate_embedded_resume_versions(conn)

    # 关上抽屉，把刚才的操作保存下来（commit）
    conn.commit()
    conn.close()
    return get_active_db_path(DB_PATH) if db_path is None else db_path

# 当别人直接运行这个脚本时，执行初始化
if __name__ == "__main__":
    init_db()
    print("[成功] 数据库结构初始化完成。")
