# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for 提词器 (Teleprompter) v1.09
# 生成单个可执行文件

import os
from pathlib import Path

# ── 项目根目录 ──
ROOT = Path(SPECPATH)  # spec 文件所在目录

# ── 数据文件收集 ──
datas = [
    # 样式表
    (str(ROOT / "app" / "styles" / "theme.qss"), "app/styles"),
    # 提词器 HTML 模板
    (str(ROOT / "app" / "templates" / "prompter.html"), "app/templates"),
    # MathJax 完整库（公式渲染必需）
    (str(ROOT / "app" / "mathjax"), "app/mathjax"),
    # 应用图标
    (str(ROOT / "text.ico"), "."),
]

# license/notice 可选
for fname in ("LICENSE", "NOTICE"):
    p = ROOT / fname
    if p.exists():
        datas.append((str(p), "."))

# ── 隐藏导入 ──
# PyQt6-WebEngine 相关
hiddenimports = [
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebChannel",
    # 常用 Qt 模块（可能自动发现但显式声明更稳）
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtSvg",
]

# ── 排除不需要的模块（减小体积） ──
excludes = [
    "tkinter",
    "unittest",
    "test",
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "IPython",
    "jupyter",
    "notebook",
    "setuptools",
    "pip",
    "wheel",
    "pkg_resources",
    "xlsxwriter",
    "openpyxl",
    "html5lib",
    "bs4",
    "beautifulsoup4",
    "cryptography",
    "bcrypt",
    "paramiko",
    "sqlalchemy",
    "alembic",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="提词器1.09",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI 应用，不显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "text.ico"),
)
