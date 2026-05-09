# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget,
)
from PyQt6.QtCore import QSize

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

        self._connect_signals()

    def _connect_signals(self):
        self._home.navigate_to_prompter.connect(self._on_navigate_to_prompter)
        self._home.navigate_to_editor.connect(self._on_navigate_to_editor)

        self._prompter.back_to_home.connect(self._on_back_to_home)
        self._prompter.completed.connect(self._on_prompter_completed)

        self._editor.saved.connect(self._on_editor_saved)
        self._editor.cancelled.connect(self._on_back_to_home)

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

    def _on_editor_saved(self, manuscript_id: int):
        self._on_back_to_home()

    def _on_prompter_completed(self):
        self._stack.setCurrentIndex(self.PAGE_HOME)
        self._home.refresh()

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
