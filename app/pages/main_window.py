# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget,
)
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QKeyEvent

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
        super().__init__()
        self.setWindowTitle("提词器")
        self.setMinimumSize(960, 540)
        self.resize(1280, 720)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._home = HomePage()
        self._prompter = PrompterPage()
        self._editor = EditorPage()

        self._stack.addWidget(self._home)
        self._stack.addWidget(self._prompter)
        self._stack.addWidget(self._editor)

        self._resizing = False
        self._editing_from_prompter = False
        self._edit_scroll_ratio = 0.0

        self._connect_signals()

    def _connect_signals(self):
        self._home.navigate_to_prompter.connect(self._on_navigate_to_prompter)
        self._home.navigate_to_editor.connect(self._on_navigate_to_editor)

        self._prompter.back_to_home.connect(self._on_back_to_home)
        self._prompter.completed.connect(self._on_prompter_completed)
        self._prompter.edit_current_manuscript.connect(self._on_edit_current)

        self._editor.saved.connect(self._on_editor_saved)
        self._editor.cancelled.connect(self._on_editor_cancelled)

    def _on_navigate_to_prompter(self, manuscript_id: int):
        manuscript = get_manuscript(manuscript_id)
        if not manuscript:
            return
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
        if key == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        if key == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
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
        try:
            self._prompter._save_settings()
        except Exception:
            pass
        if self._prompter._mirror_window:
            self._prompter._mirror_window.close()
        if self._prompter._control_panel:
            self._prompter._control_panel.close()
        event.accept()
