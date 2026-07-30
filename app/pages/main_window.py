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
import logging
import os

from app.database import get_manuscript
from app.pages.home_page import HomePage
from app.pages.prompter_page import PrompterPage
from app.pages.editor_page import EditorPage

logger = logging.getLogger("teleprompter.window")

ASPECT_RATIO = 16.0 / 9.0


class MainWindow(QMainWindow):
    PAGE_HOME = 0
    PAGE_PROMPTER = 1
    PAGE_EDITOR = 2

    def __init__(self):
        super().__init__()
        logger.debug("MainWindow.__init__ 开始")
        self.setWindowTitle("提词器")
        self.setMinimumSize(960, 540)
        self.resize(1280, 720)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._home = HomePage()
        self._editor = EditorPage()
        self._prompter = None
        self._prompter_created = False

        self._stack.addWidget(self._home)
        self._stack.addWidget(self._editor)
        logger.debug("MainWindow 基础页面已添加 (home+editor)")

        self._resizing = False
        self._editing_from_prompter = False
        self._edit_scroll_ratio = 0.0

        self._connect_signals()
        logger.debug("MainWindow.__init__ 完成")

    def _connect_signals(self):
        self._home.navigate_to_prompter.connect(self._on_navigate_to_prompter)
        self._home.navigate_to_editor.connect(self._on_navigate_to_editor)

        self._editor.saved.connect(self._on_editor_saved)
        self._editor.cancelled.connect(self._on_editor_cancelled)

    def _ensure_prompter(self):
        if not self._prompter_created:
            logger.debug("_ensure_prompter: 开始创建 PrompterPage (WebEngine)...")
            self.setUpdatesEnabled(False)
            self._prompter = PrompterPage()
            logger.debug("_ensure_prompter: PrompterPage 对象已创建, 连接信号...")
            self._prompter.hide()
            self._stack.insertWidget(self.PAGE_PROMPTER, self._prompter)
            self._prompter.back_to_home.connect(self._on_back_to_home)
            self._prompter.completed.connect(self._on_prompter_completed)
            self._prompter.edit_current_manuscript.connect(self._on_edit_current)
            self._prompter_created = True
            self.setUpdatesEnabled(True)
            logger.debug("_ensure_prompter: PrompterPage 创建完成并已隐藏")

    def _on_navigate_to_prompter(self, manuscript_id: int):
        logger.debug(f"导航到提词器: manuscript_id={manuscript_id}")
        manuscript = get_manuscript(manuscript_id)
        if not manuscript:
            logger.warning(f"导航到提词器失败: 稿件不存在 id={manuscript_id}")
            return
        self.setUpdatesEnabled(False)
        self._resizing = True  # 禁止 resizeEvent 触发 16:9 调整
        self._ensure_prompter()
        self._prompter.load_manuscript(manuscript)
        self._stack.setCurrentIndex(self.PAGE_PROMPTER)
        self.setUpdatesEnabled(True)
        self._resizing = False
        logger.debug("已切换到提词器页面")

    def _on_navigate_to_editor(self, manuscript):
        logger.debug(f"导航到编辑器: manuscript={'None(新建)' if manuscript is None else manuscript.id}")
        self._editor.load_manuscript(manuscript)
        self._stack.setCurrentIndex(self.PAGE_EDITOR)

    def _on_back_to_home(self):
        logger.debug("返回主页")
        self.setUpdatesEnabled(False)
        self._stack.setCurrentIndex(self.PAGE_HOME)
        self._home.refresh()
        self.setUpdatesEnabled(True)

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
        logger.debug("closeEvent 触发")
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
            logger.debug("用户取消退出")
            event.ignore()
            return
        logger.debug("用户确认退出, 开始清理...")
        if self._prompter:
            try:
                self._prompter._save_settings()
                logger.debug("提词器设置已保存")
            except Exception as e:
                logger.error(f"保存设置异常: {e}")
            if self._prompter._mirror_window:
                logger.debug("关闭镜像窗口...")
                self._prompter._mirror_window.hide()
                self._prompter._mirror_window.close()
            if self._prompter._control_panel:
                logger.debug("关闭控制面板...")
                self._prompter._control_panel.hide()
                self._prompter._control_panel.close()
        self.hide()
        logger.debug("主窗口已隐藏, 接受退出")
        # 从 __main__ 模块获取事件列表（python main.py 时模块名是 __main__）
        import sys as _sys
        m = _sys.modules.get('__main__')
        events = getattr(m, '_WINDOW_EVENTS', []) if m else []
        path = os.path.join(os.path.expanduser("~"), "Desktop", "teleprompter_windows.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"total: {len(events)}\n")
            f.write("\n".join(events) + "\n")
        print(f"[monitor] wrote {len(events)} events to desktop", file=_sys.stderr)
        event.accept()
