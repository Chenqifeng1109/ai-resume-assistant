"""OfferForge 3.0 Windows 原生桌面端启动器（WebView2 纯原生独立窗口，无浏览器关联，无黑框 CMD）。"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _get_resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def _init_windows_identity() -> None:
    """设置独立 AppUserModelID 与高分屏适配，确保任务栏显示专属 OfferForge 原生图标。"""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OfferForge.Studio.3")
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _setup_windowed_stdio(log_dir: Path) -> Path:
    """在 PyInstaller --windowed 模式下 sys.stdout/stderr 为 None，必须重定向到日志文件防崩溃。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "desktop.log"
    try:
        stream = open(log_file, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    except Exception:
        pass
    return log_file


def _show_error_dialog(title: str, message: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x10)
            return
        except Exception:
            pass
    print(f"[{title}] {message}", file=sys.stderr)


def _find_free_port(preferred: int = 5000, max_tries: int = 50) -> int:
    for port in range(preferred, preferred + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _local_http_get(url: str, timeout: float = 2.0) -> tuple[int, str]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as resp:
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def _wait_for_server(port: int, timeout_sec: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout_sec
    url = f"http://127.0.0.1:{port}/api/status"
    while time.monotonic() < deadline:
        try:
            code, _ = _local_http_get(url, timeout=1.5)
            if code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _find_fallback_browser() -> str | None:
    candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("LocalAppData", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        shutil.which("msedge"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
        shutil.which("chrome"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _launch_native_webview(url: str, data_dir: Path, icon_path: Path) -> bool:
    """使用 Windows 原生 WebView2（pywebview）启动纯独立桌面窗口。"""
    try:
        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True

        profile_dir = data_dir / "webview2_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        webview.create_window(
            title="OfferForge 3.0 — AI 求职工作台",
            url=url,
            width=1380,
            height=880,
            min_size=(1024, 680),
            resizable=True,
            text_select=True,
            background_color="#F8FAFC",
        )
        webview.start(
            gui="edgechromium",
            icon=str(icon_path) if icon_path.exists() else None,
            storage_path=str(profile_dir),
            private_mode=False,
        )
        return True
    except Exception:
        print("[Desktop] WebView2 原生窗口启动异常，准备回退：", file=sys.stderr)
        traceback.print_exc()
        return False


def _run_smoke_checks(port: int, log_dir: Path) -> int:
    base = f"http://127.0.0.1:{port}"
    status_code, status_body = _local_http_get(f"{base}/api/status", timeout=5.0)
    index_code, index_html = _local_http_get(f"{base}/", timeout=5.0)
    asset_matches = re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', index_html)
    assets_ok = {}
    for rel in asset_matches:
        c, _ = _local_http_get(f"{base}{rel}", timeout=5.0)
        assets_ok[rel] = c
    webview_ready = False
    try:
        import webview  # noqa: F401
        webview_ready = True
    except Exception:
        webview_ready = False
    ok = (
        status_code == 200
        and index_code == 200
        and webview_ready
        and bool(asset_matches)
        and all(v == 200 for v in assets_ok.values())
    )
    report = {
        "ok": ok,
        "port": port,
        "webview_ready": webview_ready,
        "status_code": status_code,
        "index_code": index_code,
        "assets": assets_ok,
        "status_preview": status_body[:200],
    }
    (log_dir / "smoke_test.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0 if ok else 1


def main() -> int:
    _init_windows_identity()
    base_dir = _get_base_dir()
    resource_dir = _get_resource_dir()
    os.chdir(str(base_dir))
    os.environ.setdefault("OFFERFORGE_PUBLIC_MODE", "0")
    os.environ.setdefault("PYTHONUTF8", "1")

    data_dir = base_dir / "data"
    logs_dir = base_dir / "logs"
    resumes_dir = base_dir / "resumes"
    for d in (data_dir, logs_dir, resumes_dir):
        d.mkdir(parents=True, exist_ok=True)

    log_file = _setup_windowed_stdio(logs_dir)
    smoke_mode = "--smoke-test" in sys.argv[1:]

    try:
        import uvicorn
        from app import app as fastapi_app

        port = _find_free_port(5000)
        server_config = uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_config=None,
            access_log=False,
        )
        server = uvicorn.Server(server_config)
        server.install_signal_handlers = lambda: None

        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        if not _wait_for_server(port, timeout_sec=25.0):
            raise RuntimeError(f"本地引擎在 127.0.0.1:{port} 启动超时，请查看日志：{log_file}")

        if smoke_mode:
            rc = _run_smoke_checks(port, logs_dir)
            server.should_exit = True
            server_thread.join(timeout=5.0)
            return rc

        url = f"http://127.0.0.1:{port}"
        icon_path = resource_dir / "static" / "offerforge.ico"
        if not icon_path.exists():
            icon_path = base_dir / "static" / "offerforge.ico"

        launched_native = _launch_native_webview(url, data_dir, icon_path)
        if launched_native:
            server.should_exit = True
            server_thread.join(timeout=5.0)
            return 0

        # 极端老旧系统缺少 WebView2 Runtime 时的安全兜底
        browser_exe = _find_fallback_browser()
        if browser_exe:
            profile_dir = data_dir / "desktop_app_profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen(
                [
                    browser_exe,
                    f"--app={url}",
                    "--window-size=1380,880",
                    f"--user-data-dir={profile_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            proc.wait()
            server.should_exit = True
            server_thread.join(timeout=5.0)
        else:
            webbrowser.open(url)
            while server_thread.is_alive():
                time.sleep(1.0)
        return 0
    except Exception as exc:
        err_text = f"OfferForge 启动失败：{exc}\n\n详细日志已保存至：\n{log_file}"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n=== DESKTOP LAUNCH ERROR ===\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        if not smoke_mode:
            _show_error_dialog("OfferForge 3.0 启动失败", err_text)
        return 1


if __name__ == "__main__":
    sys.exit(main())
