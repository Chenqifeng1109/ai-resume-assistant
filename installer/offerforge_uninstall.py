"""OfferForge 3.0 Windows 独立卸载程序（无黑框窗口，支持图形向导与静默卸载）。"""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import threading
import winreg
from pathlib import Path

APP_NAME = "OfferForge 3.0"
APP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OfferForge3"
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OfferForge"
USER_DATA_DIRS = {"data", "resumes", "logs"}
USER_DATA_FILES = {".env"}


def _enable_hidpi() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _read_installed_dir() -> Path:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY) as key:
            val, _ = winreg.QueryValueEx(key, "InstallLocation")
            if val and Path(val).exists():
                return Path(val)
    except OSError:
        pass
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "OfferForge.exe").exists():
            return exe_dir
    return DEFAULT_DIR


def _kill_running_app() -> None:
    if os.name != "nt":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["taskkill", "/IM", "OfferForge.exe", "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        check=False,
    )


def _remove_shortcuts() -> None:
    desktop_candidates = [
        Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop",
        Path(os.environ.get("OneDrive", "")) / "Desktop" if os.environ.get("OneDrive") else None,
    ]
    for desk in desktop_candidates:
        if desk and desk.is_dir():
            for name in ("OfferForge 3.0.lnk", "OfferForge.lnk"):
                p = desk / name
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "OfferForge 3.0"
    if start_menu.exists():
        shutil.rmtree(start_menu, ignore_errors=True)


def _remove_registry() -> None:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, APP_KEY)
    except OSError:
        pass


def _schedule_self_delete(target_dir: Path, self_exe: Path) -> None:
    """当卸载程序位于安装目录内运行时，退出后延时删除自身与空目录。"""
    if os.name != "nt":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = f'ping 127.0.0.1 -n 3 > nul & del /f /q "{self_exe}" & rmdir "{target_dir}"'
    subprocess.Popen(
        ["cmd.exe", "/c", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def perform_uninstall(
    install_dir: Path,
    remove_user_data: bool = False,
    remove_shortcuts: bool = True,
    remove_registry: bool = True,
    progress_cb=None,
) -> tuple[bool, str]:
    def step(pct: int, msg: str) -> None:
        if callable(progress_cb):
            progress_cb(pct, msg)

    install_dir = install_dir.resolve()
    step(10, "正在关闭正在运行的 OfferForge...")
    _kill_running_app()

    if remove_shortcuts:
        step(25, "正在清理桌面与开始菜单快捷方式...")
        _remove_shortcuts()

    if remove_registry:
        step(40, "正在清理 Windows 卸载注册表项...")
        _remove_registry()

    if not install_dir.exists():
        step(100, "卸载完成（未发现残留安装目录）")
        return True, "未检测到已安装目录，已清理残留快捷方式与注册表。"

    self_exe = Path(sys.executable).resolve() if getattr(sys, "frozen", False) else None
    running_inside = bool(self_exe and install_dir in self_exe.parents)

    step(55, "正在移除程序文件...")
    entries = list(install_dir.iterdir())
    total = max(len(entries), 1)
    for idx, entry in enumerate(entries, start=1):
        name = entry.name
        if not remove_user_data and (name in USER_DATA_DIRS or name in USER_DATA_FILES):
            continue
        if running_inside and self_exe and entry.resolve() == self_exe:
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
        except OSError:
            pass
        step(55 + int(40 * idx / total), f"正在移除: {name}")

    if running_inside and self_exe:
        _schedule_self_delete(install_dir, self_exe)
    else:
        try:
            if remove_user_data and install_dir.exists():
                shutil.rmtree(install_dir, ignore_errors=True)
            elif install_dir.exists() and not any(install_dir.iterdir()):
                install_dir.rmdir()
        except OSError:
            pass

    step(100, "OfferForge 3.0 卸载完成！")
    if remove_user_data:
        return True, f"已彻底卸载 {APP_NAME} 并清理所有本地数据。"
    return True, f"已卸载 {APP_NAME} 程序文件（保留了 {install_dir} 中的个人简历与数据）。"


def run_gui(initial_dir: Path) -> int:
    _enable_hidpi()
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(f"卸载 {APP_NAME}")
    root.geometry("500x330")
    root.resizable(False, False)
    root.configure(bg="#F8FAFC")

    try:
        icon_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent / "static")) / "offerforge.ico"
        if icon_path.exists():
            root.iconbitmap(default=str(icon_path))
    except Exception:
        pass

    header = tk.Frame(root, bg="#1E293B", height=64)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text=f"卸载 {APP_NAME}", fg="#FFFFFF", bg="#1E293B", font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w", padx=20, pady=(12, 0))
    tk.Label(header, text="安全移除桌面程序、快捷方式与系统注册项", fg="#CBD5E1", bg="#1E293B", font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=20)

    body = tk.Frame(root, bg="#F8FAFC", padx=20, pady=16)
    body.pack(fill="both", expand=True)

    tk.Label(body, text="检测到的安装目录：", bg="#F8FAFC", fg="#334155", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
    dir_row = tk.Frame(body, bg="#F8FAFC")
    dir_row.pack(fill="x", pady=(4, 12))
    dir_var = tk.StringVar(value=str(initial_dir))
    dir_entry = ttk.Entry(dir_row, textvariable=dir_var)
    dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def browse():
        chosen = filedialog.askdirectory(initialdir=dir_var.get() or str(DEFAULT_DIR))
        if chosen:
            dir_var.set(chosen)

    ttk.Button(dir_row, text="浏览...", command=browse).pack(side="right")

    remove_data_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        body,
        text="同时删除个人数据（简历、岗位数据库与 .env 密钥配置）",
        variable=remove_data_var,
        bg="#F8FAFC",
        fg="#475569",
        activebackground="#F8FAFC",
        font=("Microsoft YaHei UI", 9),
    ).pack(anchor="w", pady=(0, 12))

    status_var = tk.StringVar(value="点击「开始卸载」将关闭 OfferForge 并移除程序文件。")
    tk.Label(body, textvariable=status_var, bg="#F8FAFC", fg="#64748B", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(0, 6))

    pbar = ttk.Progressbar(body, orient="horizontal", mode="determinate", maximum=100)
    pbar.pack(fill="x", pady=(0, 14))

    btn_row = tk.Frame(body, bg="#F8FAFC")
    btn_row.pack(fill="x")

    uninstall_btn = ttk.Button(btn_row, text="开始卸载")
    close_btn = ttk.Button(btn_row, text="取消", command=root.destroy)
    close_btn.pack(side="right")
    uninstall_btn.pack(side="right", padx=(0, 8))

    def start_uninstall():
        target = Path(dir_var.get().strip())
        if not str(target):
            messagebox.showwarning("提示", "请选择有效的安装目录。")
            return
        if not messagebox.askyesno("确认卸载", f"确定要卸载 {APP_NAME} 吗？\n目标目录：{target}"):
            return
        uninstall_btn.config(state="disabled")
        close_btn.config(state="disabled")

        def worker():
            ok, msg = perform_uninstall(
                target,
                remove_user_data=remove_data_var.get(),
                progress_cb=lambda pct, text: root.after(0, lambda: (pbar.config(value=pct), status_var.set(text))),
            )

            def finish():
                close_btn.config(text="完成", state="normal")
                if ok:
                    messagebox.showinfo("卸载完成", msg)
                    root.destroy()
                else:
                    messagebox.showerror("卸载失败", msg)

            root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    uninstall_btn.config(command=start_uninstall)
    root.mainloop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OfferForge 3.0 Uninstaller")
    parser.add_argument("--silent", action="store_true", help="静默卸载（无弹窗）")
    parser.add_argument("--dir", dest="target_dir", default="", help="指定卸载目录")
    parser.add_argument("--remove-data", action="store_true", help="同时删除个人数据")
    parser.add_argument("--no-shortcuts", action="store_true", help="跳过快捷方式清理")
    parser.add_argument("--no-registry", action="store_true", help="跳过注册表清理")
    args = parser.parse_args()

    target = Path(args.target_dir) if args.target_dir else _read_installed_dir()
    if args.silent:
        ok, msg = perform_uninstall(
            target,
            remove_user_data=args.remove_data,
            remove_shortcuts=not args.no_shortcuts,
            remove_registry=not args.no_registry,
        )
        print(msg)
        return 0 if ok else 1
    return run_gui(target)


if __name__ == "__main__":
    sys.exit(main())
