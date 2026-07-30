#!/usr/bin/env python3
# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#

__version__ = "1.12"

import sys
import io
import os
import logging
from datetime import datetime

os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='surrogateescape')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='surrogateescape')

# ── 消除 WebEngine GPU 进程窗口闪烁 ──
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer"
os.environ["QSG_RENDER_LOOP"] = "basic"

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
LOG_PATH = os.path.join(DESKTOP, "teleprompter_debug.log")
LOG_FORMAT = '%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s'
LOG_DATE = '%H:%M:%S'

logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt=LOG_DATE,
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8', mode='w'),
        logging.StreamHandler(sys.stderr),
    ],
)

logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

_window_log = logging.getLogger("teleprompter.windows")


def _install_window_monitor(app: 'QApplication'):
    """全局事件过滤器：记录所有顶层窗口的 show/hide/close/activate 事件"""
    from PyQt6.QtCore import QEvent, QObject

    class WindowMonitor(QObject):
        def eventFilter(self, obj, event):
            t = event.type()
            if t == QEvent.Type.Show:
                _window_log.info(f"窗口 Show: {obj.__class__.__name__} title='{getattr(obj, 'windowTitle', lambda: '')()}'")
            elif t == QEvent.Type.Hide:
                _window_log.info(f"窗口 Hide: {obj.__class__.__name__}")
            elif t == QEvent.Type.Close:
                _window_log.info(f"窗口 Close: {obj.__class__.__name__}")
            elif t == QEvent.Type.WindowActivate:
                _window_log.info(f"窗口 Activate: {obj.__class__.__name__}")
            elif t == QEvent.Type.WindowDeactivate:
                _window_log.info(f"窗口 Deactivate: {obj.__class__.__name__}")
            return False

    monitor = WindowMonitor()
    app.installEventFilter(monitor)
    return monitor

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
    _install_window_monitor(app)
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

    # 后台预加载 WebEngine（窗口显示后 500ms 触发）
    from PyQt6.QtCore import QTimer as _QTimer
    _QTimer.singleShot(500, window._ensure_prompter)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
