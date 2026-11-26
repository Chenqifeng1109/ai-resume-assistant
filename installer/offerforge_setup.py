"""OfferForge 3.0 Windows 单文件安装向导（无黑框窗口，支持图形向导与静默安装）。"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import threading
import winreg
import zipfile
from pathlib import Path

APP_NAME = "OfferForge 3.0"
APP_VERSION = "3.0.0"
PUBLISHER = "OfferForge Studio"
APP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OfferForge3"
DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OfferForge"


def _enable_hidpi() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _get_payload_zip() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "offerforge_payload.zip"
    return Path(__file__).resolve().parent.parent / "build" / "offerforge_payload.zip"


def _create_shortcut(lnk_path: Path, target_exe: Path, work_dir: Path, icon_path: Path, desc: str) -> None:
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{str(lnk_path)}'); "
        f"$s.TargetPath = '{str(target_exe)}'; "
        f"$s.WorkingDirectory = '{str(work_dir)}'; "
        f"$s.IconLocation = '{str(icon_path)}'; "
        f"$s.Description = '{desc}'; "
        "$s.Save()"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        check=False,
    )


def _register_uninstaller(install_dir: Path) -> None:
    uninstall_exe = install_dir / "Uninstall.exe"
    icon_exe = install_dir / "OfferForge.exe"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon_exe))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}"')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def perform_install(
    install_dir: Path,
    create_desktop_shortcut: bool = True,
    create_start_menu: bool = True,
    register_windows_uninstall: bool = True,
    progress_cb=None,
) -> tuple[bool, str]:
    def step(pct: int, msg: str) -> None:
        if callable(progress_cb):
            progress_cb(pct, msg)

    payload_zip = _get_payload_zip()
    if not payload_zip.exists():
        return False, f"安装包数据损坏：找不到 {payload_zip.name}"

    install_dir = install_dir.resolve()
    step(5, "正在关闭旧版运行实例...")
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/IM", "OfferForge.exe", "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )

    install_dir.mkdir(parents=True, exist_ok=True)
    step(10, "正在解压 OfferForge 3.0 核心引擎...")

    with zipfile.ZipFile(payload_zip, "r") as zf:
        members = zf.infolist()
        total = max(len(members), 1)
        for idx, member in enumerate(members, start=1):
            # 覆盖升级时不破坏用户已有的 .env 和 data/
            rel = member.filename.replace("\\", "/")
            if rel in {".env"} and (install_dir / rel).exists():
                continue
            zf.extract(member, install_dir)
            if idx == total or idx % 20 == 0:
                pct = 10 + int(75 * idx / total)
                step(pct, f"正在安装文件 ({idx}/{total})...")

    app_exe = install_dir / "OfferForge.exe"
    uninstall_exe = install_dir / "Uninstall.exe"
    icon_file = install_dir / "_internal" / "static" / "offerforge.ico"
    if not icon_file.exists():
        icon_file = app_exe

    if create_desktop_shortcut:
        step(88, "正在创建桌面快捷方式...")
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        if desktop.is_dir():
            _create_shortcut(desktop / "OfferForge 3.0.lnk", app_exe, install_dir, icon_file, "OfferForge 3.0 AI 求职工作台")

    if create_start_menu:
        step(92, "正在创建开始菜单快捷方式...")
        start_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "OfferForge 3.0"
        _create_shortcut(start_dir / "OfferForge 3.0.lnk", app_exe, install_dir, icon_file, "启动 OfferForge 3.0")
        if uninstall_exe.exists():
            _create_shortcut(start_dir / "卸载 OfferForge 3.0.lnk", uninstall_exe, install_dir, icon_file, "卸载 OfferForge 3.0")

    if register_windows_uninstall:
        step(96, "正在写入 Windows 应用与卸载信息...")
        _register_uninstaller(install_dir)

    step(100, "OfferForge 3.0 安装完成！")
    return True, f"已成功安装至：{install_dir}"


def run_gui() -> int:
    _enable_hidpi()
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(f"{APP_NAME} 安装向导")
    root.geometry("540x380")
    root.resizable(False, False)
    root.configure(bg="#F8FAFC")

    try:
        icon_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent / "static")) / "offerforge.ico"
        if icon_path.exists():
            root.iconbitmap(default=str(icon_path))
    except Exception:
        pass

    header = tk.Frame(root, bg="#312E81", height=76)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text=f"欢迎安装 {APP_NAME}", fg="#FFFFFF", bg="#312E81", font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", padx=22, pady=(14, 2))
    tk.Label(header, text="AI 简历解析 · 智能润色 · 多源岗位采集 · 模拟面试 · 投递看板（全本地隐私保护）", fg="#C7D2FE", bg="#312E81", font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=22)

    body = tk.Frame(root, bg="#F8FAFC", padx=22, pady=16)
    body.pack(fill="both", expand=True)

    tk.Label(body, text="安装目录（无需管理员权限）：", bg="#F8FAFC", fg="#334155", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
    dir_row = tk.Frame(body, bg="#F8FAFC")
    dir_row.pack(fill="x", pady=(5, 12))
    dir_var = tk.StringVar(value=str(DEFAULT_INSTALL_DIR))
    ttk.Entry(dir_row, textvariable=dir_var).pack(side="left", fill="x", expand=True, padx=(0, 8))

    def browse():
        chosen = filedialog.askdirectory(initialdir=dir_var.get() or str(DEFAULT_INSTALL_DIR))
        if chosen:
            p = Path(chosen)
            dir_var.set(str(p if p.name.lower() == "offerforge" else p / "OfferForge"))

    ttk.Button(dir_row, text="更改目录...", command=browse).pack(side="right")

    desktop_var = tk.BooleanVar(value=True)
    start_var = tk.BooleanVar(value=True)
    launch_var = tk.BooleanVar(value=True)

    tk.Checkbutton(body, text="创建桌面快捷方式", variable=desktop_var, bg="#F8FAFC", fg="#334155", activebackground="#F8FAFC", font=("Microsoft YaHei UI", 9)).pack(anchor="w")
    tk.Checkbutton(body, text="创建开始菜单快捷方式（含卸载入口）", variable=start_var, bg="#F8FAFC", fg="#334155", activebackground="#F8FAFC", font=("Microsoft YaHei UI", 9)).pack(anchor="w")
    tk.Checkbutton(body, text="安装完成后立即启动 OfferForge 3.0", variable=launch_var, bg="#F8FAFC", fg="#334155", activebackground="#F8FAFC", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(0, 12))

    status_var = tk.StringVar(value="准备就绪。安装过程约需 5–10 秒，每个用户均使用自己的本地 API Key。")
    tk.Label(body, textvariable=status_var, bg="#F8FAFC", fg="#64748B", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(0, 6))

    pbar = ttk.Progressbar(body, orient="horizontal", mode="determinate", maximum=100)
    pbar.pack(fill="x", pady=(0, 14))

    btn_row = tk.Frame(body, bg="#F8FAFC")
    btn_row.pack(fill="x")

    install_btn = ttk.Button(btn_row, text="立即安装")
    cancel_btn = ttk.Button(btn_row, text="取消", command=root.destroy)
    cancel_btn.pack(side="right")
    install_btn.pack(side="right", padx=(0, 8))

    def start_install():
        target = Path(dir_var.get().strip())
        if not str(target):
            messagebox.showwarning("提示", "请选择有效的安装目录。")
            return
        install_btn.config(state="disabled")
        cancel_btn.config(state="disabled")

        def worker():
            ok, msg = perform_install(
                target,
                create_desktop_shortcut=desktop_var.get(),
                create_start_menu=start_var.get(),
                register_windows_uninstall=True,
                progress_cb=lambda pct, text: root.after(0, lambda: (pbar.config(value=pct), status_var.set(text))),
            )

            def finish():
                cancel_btn.config(text="关闭", state="normal")
                if ok:
                    if launch_var.get():
                        exe = target / "OfferForge.exe"
                        if exe.exists():
                            subprocess.Popen([str(exe)], cwd=str(target))
                    messagebox.showinfo("安装完成", f"{msg}\n\n首次使用请点击右上角「⚙️ 模型设置」填入你自己的大模型 API Key。")
                    root.destroy()
                else:
                    install_btn.config(state="normal")
                    messagebox.showerror("安装失败", msg)

            root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    install_btn.config(command=start_install)
    root.mainloop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OfferForge 3.0 Setup")
    parser.add_argument("--silent", action="store_true", help="静默安装（无弹窗）")
    parser.add_argument("--dir", dest="target_dir", default="", help="指定安装目录")
    parser.add_argument("--no-shortcuts", action="store_true", help="不创建快捷方式")
    parser.add_argument("--no-registry", action="store_true", help="不写入注册表")
    args = parser.parse_args()

    if args.silent:
        target = Path(args.target_dir) if args.target_dir else DEFAULT_INSTALL_DIR
        ok, msg = perform_install(
            target,
            create_desktop_shortcut=not args.no_shortcuts,
            create_start_menu=not args.no_shortcuts,
            register_windows_uninstall=not args.no_registry,
        )
        print(msg)
        return 0 if ok else 1
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
