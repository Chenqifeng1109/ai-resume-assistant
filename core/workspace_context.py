"""浏览器会话级物理数据隔离上下文（基于 ContextVar + 独立子目录与 SQLite）。

每个访客浏览器持有一枚随机 128-bit HttpOnly Cookie（of_workspace_id），
后端将本次请求及派生的后台线程自动路由到 data/workspaces/<ws_id>/，
实现不同电脑/不同浏览器间 100% 物理隔离、初次进入即空白、上传后仅本机持久可见。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
import os
import re
import secrets
import shutil
import time

from config import DATA_DIR, RESUMES_DIR

WORKSPACE_COOKIE_NAME = "of_workspace_id"
_WORKSPACE_ID_RE = re.compile(r"^[a-f0-9]{24,48}$")
_WORKSPACE_ID: ContextVar[str | None] = ContextVar("offerforge_workspace_id", default=None)
_WORKSPACE_BASE_DIR: ContextVar[str | None] = ContextVar("offerforge_workspace_base_dir", default=None)


def is_valid_workspace_id(value: str | None) -> bool:
    return isinstance(value, str) and bool(_WORKSPACE_ID_RE.match(value))


def generate_workspace_id() -> str:
    return secrets.token_hex(16)


def get_workspace_id() -> str | None:
    return _WORKSPACE_ID.get()


def set_workspace_id(workspace_id: str | None, base_data_dir: str | None = None) -> tuple[Token, Token]:
    t1 = _WORKSPACE_ID.set(workspace_id)
    t2 = _WORKSPACE_BASE_DIR.set(base_data_dir)
    return t1, t2


def reset_workspace_id(tokens: tuple[Token, Token]) -> None:
    t1, t2 = tokens
    _WORKSPACE_ID.reset(t1)
    _WORKSPACE_BASE_DIR.reset(t2)


def _workspace_root(workspace_id: str, base_data_dir: str | None = None) -> str:
    root_data = base_data_dir or _WORKSPACE_BASE_DIR.get() or DATA_DIR
    return os.path.join(root_data, "workspaces", workspace_id)


def get_active_data_dir(default_dir: str | None = None) -> str:
    ws_id = _WORKSPACE_ID.get()
    if ws_id and is_valid_workspace_id(ws_id):
        path = os.path.join(_workspace_root(ws_id), "data")
        os.makedirs(path, exist_ok=True)
        return path
    return default_dir or DATA_DIR


def get_active_resumes_dir(default_dir: str | None = None) -> str:
    ws_id = _WORKSPACE_ID.get()
    if ws_id and is_valid_workspace_id(ws_id):
        path = os.path.join(_workspace_root(ws_id), "resumes")
        os.makedirs(path, exist_ok=True)
        return path
    return default_dir or RESUMES_DIR


def get_active_photos_dir(default_data_dir: str | None = None) -> str:
    ws_id = _WORKSPACE_ID.get()
    if ws_id and is_valid_workspace_id(ws_id):
        path = os.path.join(_workspace_root(ws_id), "photos")
        os.makedirs(path, exist_ok=True)
        return path
    base = default_data_dir or DATA_DIR
    return os.path.join(os.path.dirname(os.path.abspath(base)), "photos")


def get_active_db_path(default_db_path: str | None = None) -> str:
    ws_id = _WORKSPACE_ID.get()
    if ws_id and is_valid_workspace_id(ws_id):
        return os.path.join(get_active_data_dir(), "offerforge.db")
    return default_db_path or os.path.join(DATA_DIR, "offerforge.db")


def touch_workspace(workspace_id: str, base_data_dir: str | None = None) -> None:
    if not is_valid_workspace_id(workspace_id):
        return
    ws_root = _workspace_root(workspace_id, base_data_dir)
    os.makedirs(os.path.join(ws_root, "data"), exist_ok=True)
    os.makedirs(os.path.join(ws_root, "resumes"), exist_ok=True)
    os.makedirs(os.path.join(ws_root, "photos"), exist_ok=True)
    marker = os.path.join(ws_root, ".last_seen")
    try:
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(str(int(time.time())))
    except OSError:
        pass


def prune_stale_workspaces(max_age_days: int = 14, base_data_dir: str | None = None) -> int:
    """安全清理超过指定天数未活跃的访客隔间，绝不触碰根目录 data/。"""
    if max_age_days <= 0:
        return 0
    ws_parent = os.path.join(base_data_dir or DATA_DIR, "workspaces")
    if not os.path.isdir(ws_parent):
        return 0
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for name in os.listdir(ws_parent):
        if not is_valid_workspace_id(name):
            continue
        ws_path = os.path.join(ws_parent, name)
        if not os.path.isdir(ws_path):
            continue
        marker = os.path.join(ws_path, ".last_seen")
        try:
            mtime = os.path.getmtime(marker) if os.path.exists(marker) else os.path.getmtime(ws_path)
            if mtime < cutoff:
                shutil.rmtree(ws_path, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed
