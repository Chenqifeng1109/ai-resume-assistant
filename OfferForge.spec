# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

wv_datas, wv_binaries, wv_hidden = collect_all("webview")
cl_datas, cl_binaries, cl_hidden = collect_all("clr_loader")
pn_datas, pn_binaries, pn_hidden = collect_all("pythonnet")

bundled_browser_datas = []
_pw_root = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
if _pw_root.is_dir():
    for _dir in sorted(_pw_root.glob("chromium_headless_shell-*"), reverse=True):
        if _dir.is_dir():
            bundled_browser_datas.append((str(_dir), f"playwright_browsers/{_dir.name}"))
            break

hidden_imports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "multipart",
    "python_multipart",
    "sqlite3",
    "clr",
    "app",
    "config",
]
hidden_imports += collect_submodules("core")
hidden_imports += collect_submodules("routers")
hidden_imports += collect_submodules("services")
hidden_imports += collect_submodules("modules")
hidden_imports += wv_hidden + cl_hidden + pn_hidden

a = Analysis(
    ["desktop_launcher.py"],
    pathex=["."],
    binaries=wv_binaries + cl_binaries + pn_binaries,
    datas=[
        ("frontend/dist", "frontend/dist"),
        ("static", "static"),
    ] + wv_datas + cl_datas + pn_datas + bundled_browser_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "numpy",
        "pytest",
        "IPython",
        "jupyter",
        "notebook",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OfferForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 无黑框 CMD 窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="static/offerforge.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OfferForge",
)
