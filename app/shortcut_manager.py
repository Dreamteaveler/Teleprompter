# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
import time

from PyQt6.QtCore import QObject, Qt, QEvent
from PyQt6.QtWidgets import QApplication


class ShortcutManager(QObject):
    def __init__(self, window, view=None):
        super().__init__()
        self._window = window
        self._view = view
        self._allowed_windows = {window}
        self._shortcuts = {}
        self._release_shortcuts = {}
        self._double_click_handler = None

        self._press_time = 0.0
        self._last_valid_click_time = 0.0

    def set_shortcuts(self, shortcuts: dict):
        self._shortcuts = shortcuts

    def set_release_shortcuts(self, shortcuts: dict):
        self._release_shortcuts = shortcuts

    def set_double_click_handler(self, handler):
        self._double_click_handler = handler

    def install(self):
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def uninstall(self):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def _is_event_for_this_window(self, obj):
        try:
            return obj.window() in self._allowed_windows
        except Exception:
            return False

    def _event_window(self, obj):
        try:
            return obj.window()
        except Exception:
            return None

    def add_allowed_window(self, win):
        self._allowed_windows.add(win)

    def eventFilter(self, obj, event):
        # ── mouse double-click: main window only ──
        if event.type() == QEvent.Type.MouseButtonPress:
            if self._event_window(obj) is not self._window:
                return False
            self._press_time = time.monotonic()
            return False

        if event.type() == QEvent.Type.MouseButtonRelease:
            if self._event_window(obj) is not self._window:
                return False
            now = time.monotonic()
            if now - self._press_time < 0.3:
                if self._last_valid_click_time > 0 and now - self._last_valid_click_time < 0.5:
                    self._last_valid_click_time = 0.0
                    if self._double_click_handler is not None:
                        self._double_click_handler()
                    return True
                self._last_valid_click_time = now
            return False

        # ── wheel: forward from control panel to main view ──
        if event.type() == QEvent.Type.Wheel:
            win = self._event_window(obj)
            if win is not self._window and win is not None and win in self._allowed_windows:
                delta = event.angleDelta().y()
                if delta != 0 and self._view is not None:
                    try:
                        self._view.page().runJavaScript(
                            f"window.scrollBy(0, {-delta * 0.5});"
                        )
                    except Exception:
                        pass
                return True
            return False

        # ── keyboard: all allowed windows ──
        if event.type() == QEvent.Type.KeyPress:
            if not self._is_event_for_this_window(obj):
                return False
            if event.isAutoRepeat():
                return False
            key = event.key()
            handler = self._shortcuts.get(key)
            if handler is not None:
                handler()
                return True

        if event.type() == QEvent.Type.KeyRelease:
            if not self._is_event_for_this_window(obj):
                return False
            if event.isAutoRepeat():
                return False
            key = event.key()
            handler = self._release_shortcuts.get(key)
            if handler is not None:
                handler()
                return True

        return False
