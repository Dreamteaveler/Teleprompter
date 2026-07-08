#!/usr/bin/env python3
# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#

__version__ = "1.10"

import sys
import io
import os
import time as _time
import tempfile
from pathlib import Path as _Path

_START_TS = _time.time()
_LOG = _Path(os.path.expanduser(r"~\Desktop\启动日志.log"))

def _boot_log(msg: str):
    try:
        elapsed = _time.time() - _START_TS
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(str(_LOG), "a", encoding="utf-8") as f:
            f.write(f"[{elapsed:6.1f}s] {msg}\n")
    except Exception:
        pass

_boot_log("Python 启动完成, 开始导入 PyQt6...")

os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='surrogateescape')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='surrogateescape')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from app.database import init_database
from app.paths import resolve_path
from app.pages.main_window import MainWindow

_boot_log("PyQt6 导入完成")


def load_stylesheet(app: QApplication) -> str | None:
    qss_path = os.path.join(os.path.dirname(__file__), "app", "styles", "theme.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            return f.read()
    return None


def main():
    init_database()
    _boot_log("数据库初始化完成")

    app = QApplication(sys.argv)
    _boot_log("QApplication 创建完成")
    app.setApplicationName("提词器")
    app.setApplicationDisplayName("提词器")

    icon_path = resolve_path("text.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    stylesheet = load_stylesheet(app)
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow()
    _boot_log("MainWindow 创建完成")
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    _boot_log("窗口已显示")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
