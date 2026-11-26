"""OfferForge 4 级自动浏览器探测与启动器（供 51job / 猎聘 / PDF 导出共用）。

探测优先级：
1. 系统自带 Microsoft Edge（Win10/11 默认预装）
2. 本机 Google Chrome
3. 本机其他 Chromium 内核浏览器（Brave / 360 极速 / Vivaldi）
4. 内置或本机已安装的 Playwright Chromium 兜底内核
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from config import BASE_DIR, RESOURCE_DIR

DEFAULT_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]


def _find_bundled_chromium_exe() -> str | None:
    """查找随安装包一起内置或本机 ms-playwright 目录中的 Chromium 可执行文件。"""
    roots = [
        Path(RESOURCE_DIR) / "playwright_browsers",
        Path(BASE_DIR) / "playwright_browsers",
        Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in ("**/chrome-headless-shell.exe", "**/headless_shell.exe", "**/chrome.exe"):
            for candidate in sorted(root.glob(pattern), reverse=True):
                if candidate.is_file():
                    return str(candidate)
    return None


def find_chromium_candidates() -> list[tuple[str, str | None, str | None]]:
    """返回 (展示名, playwright_channel, executable_path) 的 4 级探测候选列表。"""
    candidates: list[tuple[str, str | None, str | None]] = []
    pf = os.environ.get("ProgramFiles", "")
    pf86 = os.environ.get("ProgramFiles(x86)", "")
    local_app = os.environ.get("LocalAppData", "")

    # 第 1 级：Microsoft Edge
    edge_paths = [
        os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(local_app, "Microsoft", "Edge", "Application", "msedge.exe"),
        shutil.which("msedge") or "",
    ]
    edge_exe = next((p for p in edge_paths if p and os.path.isfile(p)), None)
    if edge_exe:
        candidates.append(("Microsoft Edge", None, edge_exe))
    else:
        candidates.append(("Microsoft Edge (channel)", "msedge", None))

    # 第 2 级：Google Chrome
    chrome_paths = [
        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local_app, "Google", "Chrome", "Application", "chrome.exe"),
        shutil.which("chrome") or "",
    ]
    chrome_exe = next((p for p in chrome_paths if p and os.path.isfile(p)), None)
    if chrome_exe:
        candidates.append(("Google Chrome", None, chrome_exe))
    else:
        candidates.append(("Google Chrome (channel)", "chrome", None))

    # 第 3 级：其他本机 Chromium 核浏览器（Brave / 360 极速 / Vivaldi）
    other_paths = [
        ("Brave", os.path.join(pf, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")),
        ("Brave", os.path.join(local_app, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")),
        ("360极速浏览器", os.path.join(local_app, "360ChromeX", "Chrome", "Application", "360ChromeX.exe")),
        ("Vivaldi", os.path.join(local_app, "Vivaldi", "Application", "vivaldi.exe")),
    ]
    for label, path in other_paths:
        if path and os.path.isfile(path):
            candidates.append((label, None, path))

    # 第 4 级：内置 / Playwright 自带 Chromium 兜底内核
    bundled = _find_bundled_chromium_exe()
    if bundled:
        candidates.append(("内置 Chromium 内核", None, bundled))
    else:
        candidates.append(("Playwright 默认 Chromium", None, None))

    return candidates


def launch_best_chromium_browser(playwright_instance, headless: bool = True, extra_args: list[str] | None = None):
    """按 4 级探测链依次启动可用 Chromium 浏览器，返回 (browser, label)。"""
    args = list(DEFAULT_BROWSER_ARGS) + list(extra_args or [])
    errors: list[str] = []
    for label, channel, exe_path in find_chromium_candidates():
        kwargs: dict = {"headless": headless, "args": args}
        if exe_path:
            kwargs["executable_path"] = exe_path
        elif channel:
            kwargs["channel"] = channel
        try:
            browser = playwright_instance.chromium.launch(**kwargs)
            return browser, label
        except Exception as exc:
            errors.append(f"{label}: {str(exc)[:80]}")
            continue
    raise RuntimeError(
        "未检测到可用 Chromium 浏览器内核（已依次尝试 Edge/Chrome/其他Chromium/内置内核）；"
        "请安装 Edge 或 Chrome，或继续使用 15 个免登录官方直采渠道。"
    )
