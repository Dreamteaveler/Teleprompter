# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QMessageBox,
)
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QKeyEvent
import os

from app.database import get_manuscript
from app.pages.home_page import HomePage
from app.pages.prompter_page import PrompterPage
from app.pages.editor_page import EditorPage

ASPECT_RATIO = 16.0 / 9.0


class MainWindow(QMainWindow):
    PAGE_HOME = 0
    PAGE_PROMPTER = 1
    PAGE_EDITOR = 2

    def __init__(self):
        import time as _t
        _t0 = _t.time()
        super().__init__()
        self.setWindowTitle("提词器")
        self.setMinimumSize(960, 540)
        self.resize(1280, 720)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._home = HomePage()
        _t1 = _t.time()
        self._editor = EditorPage()
        self._prompter = None
        self._prompter_created = False

        with open(os.path.expanduser(r"~\Desktop\启动日志.log"), "a", encoding="utf-8") as f:
            f.write(f"  MainWindow-init: {_t.time()-_t0:.1f}s (HomePage:{_t1-_t0:.1f}s EditorPage:{_t.time()-_t1:.1f}s)\n")

        self._stack.addWidget(self._home)
        self._stack.addWidget(self._editor)

        self._resizing = False
        self._editing_from_prompter = False
        self._edit_scroll_ratio = 0.0

        self._connect_signals()

    def _connect_signals(self):
        self._home.navigate_to_prompter.connect(self._on_navigate_to_prompter)
        self._home.navigate_to_editor.connect(self._on_navigate_to_editor)

        self._editor.saved.connect(self._on_editor_saved)
        self._editor.cancelled.connect(self._on_editor_cancelled)

    def _ensure_prompter(self):
        if not self._prompter_created:
            self._prompter = PrompterPage()
            self._stack.insertWidget(self.PAGE_PROMPTER, self._prompter)
            self._prompter.back_to_home.connect(self._on_back_to_home)
            self._prompter.completed.connect(self._on_prompter_completed)
            self._prompter.edit_current_manuscript.connect(self._on_edit_current)
            self._prompter_created = True

    def _on_navigate_to_prompter(self, manuscript_id: int):
        manuscript = get_manuscript(manuscript_id)
        if not manuscript:
            return
        self._ensure_prompter()
        self._prompter.load_manuscript(manuscript)
        self._stack.setCurrentIndex(self.PAGE_PROMPTER)

    def _on_navigate_to_editor(self, manuscript):
        self._editor.load_manuscript(manuscript)
        self._stack.setCurrentIndex(self.PAGE_EDITOR)

    def _on_back_to_home(self):
        self._stack.setCurrentIndex(self.PAGE_HOME)
        self._home.refresh()

    def _on_edit_current(self, manuscript_id: int, scroll_ratio: float):
        manuscript = get_manuscript(manuscript_id)
        if not manuscript:
            return
        self._editing_from_prompter = True
        self._edit_scroll_ratio = scroll_ratio
        self._editor.load_manuscript(manuscript)
        self._stack.setCurrentIndex(self.PAGE_EDITOR)

    def _on_editor_saved(self, manuscript_id: int):
        if self._editing_from_prompter:
            self._editing_from_prompter = False
            manuscript = get_manuscript(manuscript_id)
            if manuscript:
                self._prompter.load_manuscript(manuscript)
            self._stack.setCurrentIndex(self.PAGE_PROMPTER)
            self._restore_prompter_scroll()
        else:
            self._on_back_to_home()

    def _on_editor_cancelled(self):
        if self._editing_from_prompter:
            self._editing_from_prompter = False
            self._stack.setCurrentIndex(self.PAGE_PROMPTER)
        else:
            self._on_back_to_home()

    def _restore_prompter_scroll(self):
        if self._edit_scroll_ratio <= 0:
            return
        self._prompter._pending_scroll_ratio = self._edit_scroll_ratio
        self._prompter._scroll_position = self._edit_scroll_ratio * max(1, self._prompter._scroll_height)

    def _on_prompter_completed(self):
        self._stack.setCurrentIndex(self.PAGE_HOME)
        self._home.refresh()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_F11 and self._prompter:
            self._prompter._toggle_fullscreen()
            return
        if key == Qt.Key.Key_Escape and self.isFullScreen() and self._prompter:
            self._prompter._exit_fullscreen()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        if self._stack.currentIndex() != self.PAGE_PROMPTER or self._resizing or self.isFullScreen():
            super().resizeEvent(event)
            return
        self._resizing = True
        sz = event.size()
        new_h = max(540, int(sz.width() / ASPECT_RATIO))
        self.resize(QSize(sz.width(), new_h))
        self._resizing = False
        super().resizeEvent(event)

    def closeEvent(self, event):
        msg = QMessageBox(
            QMessageBox.Icon.Question,
            "退出确认", "确定要退出提词器吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        msg.setWindowFlags(
            msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        if self._prompter:
            try:
                self._prompter._save_settings()
            except Exception:
                pass
            if self._prompter._mirror_window:
                self._prompter._mirror_window.close()
            if self._prompter._control_panel:
                self._prompter._control_panel.close()
        event.accept()
