#!/usr/bin/env python3
# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#

__version__ = "1.05"

import sys
import io
import os

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


def load_stylesheet(app: QApplication) -> str | None:
    qss_path = os.path.join(os.path.dirname(__file__), "app", "styles", "theme.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            return f.read()
    return None


def main():
    init_database()

    app = QApplication(sys.argv)
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
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
