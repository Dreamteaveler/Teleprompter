# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt, QUrl, QSize, QTimer, QEvent, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

import re

from app.paths import mathjax_base_url
from app.shortcut_manager import ShortcutManager

ASPECT_RATIO = 16.0 / 9.0

_FLIP_CSS = (
    '<style>'
    '.flip-wrapper{{'
    'transform:scale({sx},{sy});'
    'transform-origin:50% 50%;'
    'width:100%;min-height:100vh;'
    '}}'
    '#rl{{pointer-events:none !important;cursor:default !important;}}'
    '</style>'
)


class MirrorWindow(QMainWindow):
    resized = pyqtSignal()
    fullscreen_changed = pyqtSignal(bool)
    play_pause_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("提词器 - 镜像模式")
        self.setMinimumSize(960, 540)
        self.resize(1280, 720)

        self._shortcut_mgr: ShortcutManager | None = None
        self._pending_scroll_y: float = 0.0
        self._pending_scroll_ratio: float | None = None
        self._page_ready = False
        self._pending_rl_y: float = 0.0
        self._resizing = False
        self._content_html: str = ""
        self._hflip: bool = True
        self._vflip: bool = False
        self._reading_line_visible: bool = True
        self._reading_line_opacity: float = 1.0
        self._mirror_scale: float = 1.0

        self._view = QWebEngineView()
        self._view.page().setBackgroundColor(QColor("#0d0d0d"))
        self._view.setZoomFactor(1.0)
        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, False)
        self._view.loadFinished.connect(self._on_page_loaded)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setCentralWidget(self._view)

    def set_content(self, full_html: str, scroll_y: float = 0.0, rl_y: float = 0.0, scale: float = 1.0, *, scroll_ratio: float | None = None):
        self._content_html = full_html
        self._pending_scroll_y = scroll_y
        self._pending_scroll_ratio = scroll_ratio
        self._pending_rl_y = rl_y
        self._mirror_scale = scale
        self._view.setZoomFactor(scale)
        self._load_html()

    def view_width(self) -> int:
        return max(100, self._view.width())

    def set_flip(self, hflip: bool, vflip: bool, rebuild: bool = True):
        changed = self._hflip != hflip or self._vflip != vflip
        self._hflip = hflip
        self._vflip = vflip
        if rebuild and changed and self._content_html:
            self._rebuild_with_scroll(self._pending_scroll_y)

    def update_scale(self, scale: float):
        self._mirror_scale = scale
        self._view.setZoomFactor(scale)

    def sync_scroll(self, scroll_y: float):
        self._pending_scroll_y = scroll_y
        self._pending_scroll_ratio = None
        self._apply_pending_scroll()

    def sync_scroll_pct(self, ratio: float):
        # 始终保存主屏方向的逻辑比例，翻转仅在应用到DOM时进行一次。
        self._pending_scroll_ratio = max(0.0, min(1.0, ratio))
        self._apply_pending_scroll()

    def _apply_pending_scroll(self):
        if not self._page_ready:
            return
        if self._pending_scroll_ratio is not None:
            ratio = 1.0 - self._pending_scroll_ratio if self._vflip else self._pending_scroll_ratio
            target = f"maxY*{ratio}"
        else:
            target = f"maxY-{self._pending_scroll_y}" if self._vflip else str(self._pending_scroll_y)
        self._view.page().runJavaScript(
            "var maxY=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);"
            + f"var target={target};window.scrollTo(0,Math.max(0,Math.min(maxY,target)));"
        )

    #  ── 引导框同步 ──
    #  #rl 是 body 的直接子元素，position:fixed 相对真实视口。
    #  水平模式：rl.style.top = y（主屏坐标直接使用）
    #  垂直模式：rl.style.top = innerHeight - y - h（内容翻转后对齐）
    def set_reading_line(self, y: float, h: float = 0):
        self._pending_rl_y = y
        display = "block" if self._reading_line_visible else "none"
        if self._vflip:
            js = 'var rl=document.getElementById("rl");if(rl){rl.style.top=(window.innerHeight - ' + str(y) + ' - ' + str(h) + ')+"px";rl.style.display="' + display + '";'
        else:
            js = 'var rl=document.getElementById("rl");if(rl){rl.style.top="' + str(y) + 'px";rl.style.display="' + display + '";'
        if h > 0:
            js += 'rl.style.height="' + str(h) + 'px";'
        js += '}'
        self._view.page().runJavaScript(js)

    def set_reading_line_visibility(self, visible: bool):
        self._reading_line_visible = visible
        display = "block" if visible else "none"
        self._view.page().runJavaScript(
            'var rl=document.getElementById("rl");if(rl){rl.style.display="' + display + '";}'
        )

    def set_reading_line_opacity(self, opacity: float):
        self._reading_line_opacity = opacity
        self._view.page().runJavaScript(
            'var rl=document.getElementById("rl");if(rl){rl.style.borderColor="rgba(219,157,22,' + str(opacity) + ')";}'
        )

    def _load_html(self):
        self._page_ready = False
        html = self._content_html
        sx = -1 if self._hflip else 1
        sy = -1 if self._vflip else 1
        flip_tag = _FLIP_CSS.format(sx=sx, sy=sy)
        html = re.sub(r'(</head>)', flip_tag + r'\1', html)
        html = re.sub(r'(<body[^>]*>)', r'\1<div class="flip-wrapper">', html)
        html = re.sub(r'(<div\s+id="rl"[^>]*>)', r'</div>\1', html)
        self._view.setHtml(html, mathjax_base_url())

    def _rebuild_with_scroll(self, scroll_y: float):
        self._pending_scroll_y = scroll_y
        self._load_html()

    def _on_page_loaded(self, ok: bool):
        self._page_ready = ok
        if not ok:
            return
        self._apply_pending_scroll()
        self.set_reading_line(self._pending_rl_y)

    def _toggle_fullscreen(self):
        self._resizing = True
        try:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        finally:
            self._reinstall_shortcuts()
            self.fullscreen_changed.emit(self.isFullScreen())
            QTimer.singleShot(500, self._on_fullscreen_stable)

    def _on_fullscreen_stable(self):
        self._resizing = False
        if not self.isFullScreen():
            self._resizing = True
            w = self.width()
            h = max(540, int(w / ASPECT_RATIO))
            self.resize(w, h)
            self._resizing = False
        self.resized.emit()

    def _force_resize_to_aspect(self):
        self._resizing = False
        if not self.isFullScreen():
            w = self.width()
            h = max(540, int(w / ASPECT_RATIO))
            self.resize(w, h)
        self.resized.emit()

    def _reinstall_shortcuts(self):
        if self._shortcut_mgr is not None:
            self._shortcut_mgr.install()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self._reinstall_shortcuts()
            self.fullscreen_changed.emit(self.isFullScreen())
        super().changeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._shortcut_mgr is None:
            self._shortcut_mgr = ShortcutManager(self, self._view)
            _noop = lambda: None
            self._shortcut_mgr.set_shortcuts({
                Qt.Key.Key_F11: self._toggle_fullscreen,
                Qt.Key.Key_Space: _noop,
                Qt.Key.Key_F1: _noop,
                Qt.Key.Key_Escape: _noop,
                Qt.Key.Key_Up: _noop,
                Qt.Key.Key_Down: _noop,
                Qt.Key.Key_R: _noop,
                Qt.Key.Key_M: _noop,
                Qt.Key.Key_Plus: _noop,
                Qt.Key.Key_Equal: _noop,
                Qt.Key.Key_Minus: _noop,
            })
            self._shortcut_mgr.set_double_click_handler(self._toggle_fullscreen)
            self._shortcut_mgr.set_keypad_toggle(self.play_pause_requested.emit)
        self._shortcut_mgr.install()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._shortcut_mgr is not None:
            self._shortcut_mgr.uninstall()

    def closeEvent(self, event):
        if self._shortcut_mgr is not None:
            self._shortcut_mgr.uninstall()
        event.accept()

    def resizeEvent(self, event):
        if self._resizing or self.isFullScreen():
            super().resizeEvent(event)
            return
        self._resizing = True
        sz = event.size()
        new_h = max(540, int(sz.width() / ASPECT_RATIO))
        self.resize(QSize(sz.width(), new_h))
        self._resizing = False
        super().resizeEvent(event)
        self.resized.emit()
