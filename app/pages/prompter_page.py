# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
import re
import html as html_module
import markdown

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

from app.database import get_setting, set_setting
from app.models import Manuscript
from app.paths import mathjax_url, mathjax_base_url, load_template
from app.pages.mirror_window import MirrorWindow
from app.pages.control_panel import ControlPanel
from app.pages.playback_mixin import PlaybackMixin
from app.pages.mirror_sync_mixin import MirrorSyncMixin
from app.shortcut_manager import ShortcutManager

# 模板在首次使用时加载并缓存
_HTML_TEMPLATE: str | None = None


def _get_html_template() -> str:
    global _HTML_TEMPLATE
    if _HTML_TEMPLATE is None:
        _HTML_TEMPLATE = load_template("prompter.html")
    return _HTML_TEMPLATE


class PrompterPage(PlaybackMixin, MirrorSyncMixin, QWidget):
    back_to_home = pyqtSignal()
    completed = pyqtSignal()
    edit_current_manuscript = pyqtSignal(int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manuscript: Manuscript | None = None
        self._is_playing = False
        self._scroll_position = 0.0
        self._scroll_height = 1
        self._start_time = 0.0
        self._pixels_per_second = 0.0
        self._page_ready = False
        self._reading_line_y = 0
        self._pending_scroll_ratio: float | None = None
        self._mirror_scale: float = 1.0
        self._mirror_reading_line_y: float = 0.0
        self._auto_resume: bool = False
        self._sync_pending: bool = False
        self._sync_version: int = 0
        self._accumulated_scroll: float = 0.0

        self._mirror_window: MirrorWindow | None = None
        self._is_mirror_open = False
        self._shortcut_mgr: ShortcutManager | None = None
        self._control_panel: ControlPanel | None = None

        self._load_settings()
        self._init_ui()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

        self._progress_timer = QTimer(self)
        self._progress_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._progress_timer.timeout.connect(self._poll_progress)
        self._progress_timer.setInterval(200)

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._scroll_timer.timeout.connect(self._tick_scroll)
        self._scroll_direction = 0
        self._scroll_key_start = 0.0
        self._tick_frame = 0
        self._last_tick_time = 0.0

        self._sync_timer = QTimer(self)
        self._sync_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._sync_timer.timeout.connect(self._tick_sync_mirror)
        self._sync_timer.setInterval(16)

        self._resync_debounce_timer = QTimer(self)
        self._resync_debounce_timer.setSingleShot(True)
        self._resync_debounce_timer.setInterval(300)
        self._resync_debounce_timer.timeout.connect(lambda: self._sync_mirror_if_open())

    def _load_settings(self):
        self._font_size = int(get_setting("font_size", "120"))
        self._wpm = int(get_setting("wpm", "30"))
        self._line_spacing = float(get_setting("line_spacing", "1.2"))
        self._mirror_mode = get_setting("mirror_mode", "false") == "true"
        self._margin = int(get_setting("horizontal_margin", "5"))
        self._horizontal_flip = get_setting("horizontal_flip", "true") == "true"
        self._vertical_flip = get_setting("vertical_flip", "false") == "true"
        self._reading_line_visible = get_setting("reading_line_visible", "true") == "true"
        self._reading_line_opacity = float(get_setting("reading_line_opacity", "1.0"))

    def _save_settings(self):
        set_setting("font_size", str(self._font_size))
        set_setting("wpm", str(self._wpm))
        set_setting("line_spacing", str(self._line_spacing))
        set_setting("mirror_mode", "true" if self._mirror_mode else "false")
        set_setting("horizontal_margin", str(self._margin))
        set_setting("horizontal_flip", "true" if self._horizontal_flip else "false")
        set_setting("vertical_flip", "true" if self._vertical_flip else "false")
        set_setting("reading_line_visible", "true" if self._reading_line_visible else "false")
        set_setting("reading_line_opacity", str(self._reading_line_opacity))

    def _init_ui(self):
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._view = QWebEngineView()
        self._view.setObjectName("prompterWebView")
        self._view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, False)
        self._view.loadFinished.connect(self._on_page_loaded)
        self._view.setStyleSheet("background-color: #0d0d0d;")

        layout.addWidget(self._view, 0, 0, 1, 1)
        self._is_fullscreen = False

        self._init_control_panel()

    def _build_html(self, text: str, scale: float = 1.0, vflip: bool = False) -> str:
        if not text or not text.strip():
            body = "<p style='color:#555;'>（空稿件）</p>"
        else:
            stripped = text.strip()
            if '<' in stripped and '>' in stripped:
                body = self._extract_body(stripped)
            else:
                body = self._plain_to_html(stripped)

        body = html_module.unescape(body)
        body = re.sub(
            r'<img[^>]*class="formula"[^>]*data-latex="([^"]*)"[^>]*/?>',
            r'$\1$',
            body, flags=re.DOTALL,
        )
        body = re.sub(
            r'<img[^>]*class="formula"[^>]*alt="([^"]*)"[^>]*/?>',
            r'$\1$',
            body, flags=re.DOTALL,
        )

        fs = int(self._font_size * scale)
        lh = self._line_spacing
        pt = int(fs * 0.3)
        pb = int(fs * 1.5)
        if vflip:
            pt, pb = pb, pt
        px = int(fs * (0.5 + self._margin / 5.0))
        rlh = int(fs * self._line_spacing * 3)

        html = _get_html_template()
        html = html.replace("__MATHJAX__", mathjax_url())
        html = html.replace("__FS__", str(fs))
        html = html.replace("__LH__", str(lh))
        html = html.replace("__PT__", str(pt))
        html = html.replace("__PB__", str(pb))
        html = html.replace("__PX__", str(px))
        html = html.replace("__RLH__", str(rlh))
        html = html.replace("__RL_OPACITY__", str(self._reading_line_opacity))
        html = html.replace("__BODY__", body)
        return html

    def _extract_body(self, html: str) -> str:
        if '<body' in html:
            match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
            if match:
                body = match.group(1)
            else:
                body = html
        else:
            body = html
        body = re.sub(r'<!DOCTYPE[^>]*>', '', body, flags=re.DOTALL)
        body = re.sub(r'<html[^>]*>', '', body, flags=re.DOTALL)
        body = re.sub(r'</html>', '', body, flags=re.DOTALL)
        body = re.sub(r'<head[^>]*>.*?</head>', '', body, flags=re.DOTALL)
        body = re.sub(r'background(?:-color)?\s*:\s*#[0-9a-fA-F]+;?', '', body)
        body = re.sub(r'\bcolor\s*:\s*[^;"]+;?', '', body)
        body = re.sub(r'font-size\s*:\s*[^;"]+;?', '', body)
        return body.strip()

    def _plain_to_html(self, text: str) -> str:
        math_blocks = {}

        def _save_math(m):
            key = f"\x00MATH{len(math_blocks)}\x00"
            math_blocks[key] = m.group(0)
            return key

        text = re.sub(r'\$\$[\s\S]*?\$\$', _save_math, text)
        text = re.sub(r'\$(.+?)\$', _save_math, text)

        html = markdown.markdown(
            text,
            extensions=['extra', 'nl2br'],
            output_format='html5'
        )

        for key, math_block in math_blocks.items():
            html = html.replace(key, math_block)

        return html

    def _on_page_loaded(self, ok: bool):
        if not ok:
            self._page_ready = False
            return
        self._page_ready = True
        self._refresh_scroll_height()
        self._update_reading_line()
        if self._pending_scroll_ratio is not None:
            ratio = self._pending_scroll_ratio
            self._pending_scroll_ratio = None
            self._view.page().runJavaScript(
                f"var d=document.documentElement;"
                f"var maxY=d.scrollHeight-window.innerHeight;"
                f"var target=maxY*{ratio};"
                f"window.scrollTo(0,Math.max(0,target));"
            )
        self._start_sync_timer()
        if self._auto_resume:
            self._auto_resume = False
            self._play()

    def _refresh_scroll_height(self):
        self._view.page().runJavaScript(
            "Math.max(document.documentElement.scrollHeight, window.innerHeight)",
            self._on_scroll_height
        )

    def _on_scroll_height(self, height):
        self._scroll_height = max(int(height) if height is not None else 1, 1)

    def _load_content(self, text: str, keep_scroll: bool = False):
        if keep_scroll:
            self._pending_scroll_ratio = self._scroll_position / max(1, self._scroll_height)
        else:
            self._pending_scroll_ratio = None
        self._page_ready = False
        html = self._build_html(text)
        self._view.setHtml(html, mathjax_base_url())

    def load_manuscript(self, manuscript: Manuscript):
        self._manuscript = manuscript
        self._load_content(manuscript.content)
        if self._is_mirror_open:
            self._sync_mirror_content(keep_scroll=False)
        self._scroll_position = 0.0
        self._start_time = 0.0
        self._pixels_per_second = 0.0
        self._is_playing = False
        self._timer.stop()

    def _on_font_changed(self, value: int):
        self._font_size = value
        if self._manuscript:
            was_playing = self._is_playing
            if was_playing:
                self._auto_resume = True
            self._pause()
            self._load_content(self._manuscript.content, keep_scroll=True)
        self._save_settings()
        QTimer.singleShot(150, lambda: self._sync_mirror_if_open(keep_scroll=True))

    def _on_line_spacing_changed(self, value: int):
        self._line_spacing = value / 10.0
        self._save_settings()
        if self._manuscript:
            was_playing = self._is_playing
            if was_playing:
                self._auto_resume = True
            self._pause()
            self._load_content(self._manuscript.content, keep_scroll=True)
            QTimer.singleShot(150, lambda: self._sync_mirror_if_open(keep_scroll=True))

    def _on_margin_changed(self, value: int):
        self._margin = value
        self._save_settings()
        if self._manuscript:
            was_playing = self._is_playing
            if was_playing:
                self._auto_resume = True
            self._pause()
            self._load_content(self._manuscript.content, keep_scroll=True)
            QTimer.singleShot(150, lambda: self._sync_mirror_if_open(keep_scroll=True))

    def _init_control_panel(self):
        if self._control_panel is None:
            self._control_panel = ControlPanel()
            self._control_panel.back_requested.connect(self._on_back)
            self._control_panel.play_pause_requested.connect(self._toggle_play)
            self._control_panel.reset_requested.connect(self._reset_scroll)
            self._control_panel.font_size_changed.connect(self._on_font_changed)
            self._control_panel.line_spacing_changed.connect(self._on_line_spacing_changed)
            self._control_panel.speed_changed.connect(self._on_speed_changed)
            self._control_panel.margin_changed.connect(self._on_margin_changed)
            self._control_panel.mirror_toggled.connect(self._toggle_mirror)
            self._control_panel.reading_line_toggled.connect(self._toggle_reading_line)
            self._control_panel.reading_line_opacity_changed.connect(self._on_reading_line_opacity_changed)
            self._control_panel.edit_requested.connect(self._on_edit_requested)
            self._control_panel.horizontal_flip_toggled.connect(self._on_horizontal_flip_toggled)
            self._control_panel.vertical_flip_toggled.connect(self._on_vertical_flip_toggled)

        if self._shortcut_mgr is not None and self._control_panel is not None:
            self._shortcut_mgr.add_allowed_window(self._control_panel)

        self._control_panel.set_font_size(self._font_size)
        self._control_panel.set_line_spacing(self._line_spacing)
        self._control_panel.set_speed(self._wpm)
        self._control_panel.set_margin(self._margin)
        self._control_panel.set_horizontal_flip(self._horizontal_flip)
        self._control_panel.set_vertical_flip(self._vertical_flip)
        self._control_panel.set_reading_line_opacity(self._reading_line_opacity)

    def _poll_progress(self):
        if not self._page_ready or self._scroll_height <= 1:
            return
        if self._control_panel is None or not self._control_panel.isVisible():
            return
        self._view.page().runJavaScript(
            "window.pageYOffset",
            lambda y: self._update_progress(float(y) if y is not None else 0.0)
        )

    def _update_progress(self, scroll_y: float):
        self._scroll_position = scroll_y
        if self._scroll_height <= 1:
            return
        pct = min(100, scroll_y / self._scroll_height * 100)
        if self._control_panel:
            self._control_panel.set_progress(pct)

    def _show_control_panel(self):
        self._init_control_panel()
        if self._control_panel is not None:
            self._control_panel.set_font_size(self._font_size)
            self._control_panel.set_line_spacing(self._line_spacing)
            self._control_panel.set_speed(self._wpm)
            self._control_panel.set_margin(self._margin)
            self._control_panel.set_mirror_state(self._is_mirror_open)
            self._control_panel.set_reading_line_state(self._reading_line_visible)
            self._control_panel.set_reading_line_opacity(self._reading_line_opacity)
            self._control_panel.set_horizontal_flip(self._horizontal_flip)
            self._control_panel.set_vertical_flip(self._vertical_flip)
            self._control_panel.show()
            self._control_panel.raise_()
            QTimer.singleShot(0, lambda: self._control_panel.set_playing(self._is_playing))

    def _toggle_control_panel(self):
        self._init_control_panel()
        if self._control_panel is None:
            return
        if self._control_panel.isVisible():
            self._control_panel.hide()
        else:
            self._control_panel.set_font_size(self._font_size)
            self._control_panel.set_line_spacing(self._line_spacing)
            self._control_panel.set_speed(self._wpm)
            self._control_panel.set_margin(self._margin)
            self._control_panel.set_mirror_state(self._is_mirror_open)
            self._control_panel.set_reading_line_state(self._reading_line_visible)
            self._control_panel.set_reading_line_opacity(self._reading_line_opacity)
            self._control_panel.set_horizontal_flip(self._horizontal_flip)
            self._control_panel.set_vertical_flip(self._vertical_flip)
            self._control_panel.show()
            self._control_panel.raise_()
            QTimer.singleShot(0, lambda: self._control_panel.set_playing(self._is_playing))

    def _update_reading_line(self):
        if not self._page_ready:
            return
        self._reading_line_y = self._view.height() // 4
        self._mirror_reading_line_y = self._reading_line_y * self._mirror_scale
        rlh = int(self._font_size * self._line_spacing * 3)
        display = "block" if self._reading_line_visible else "none"
        self._view.page().runJavaScript(
            'var rl=document.getElementById("rl");'
            'if(rl){'
            '  rl.style.top="' + str(self._reading_line_y) + 'px";'
            '  rl.style.height="' + str(rlh) + 'px";'
            '  rl.style.display="'+display+'";'
            '  window._readingLineTop=' + str(self._reading_line_y) + ';'
            '}'
        )

    def _toggle_fullscreen(self):
        win = self.window()
        win._resizing = True
        try:
            if self._is_fullscreen:
                win.showNormal()
            else:
                win.showFullScreen()
        finally:
            self._is_fullscreen = not self._is_fullscreen
            self._update_reading_line()
            QTimer.singleShot(400, lambda: setattr(win, '_resizing', False))
            QTimer.singleShot(600, lambda: self._sync_mirror_if_open())

    def _exit_fullscreen(self):
        if self._is_fullscreen:
            win = self.window()
            win._resizing = True
            win.showNormal()
            self._is_fullscreen = False
            QTimer.singleShot(400, lambda: setattr(win, '_resizing', False))
        else:
            self._on_back()

    def _toggle_reading_line(self):
        self._reading_line_visible = not self._reading_line_visible
        self._save_settings()
        self._update_reading_line()
        if self._control_panel:
            self._control_panel.set_reading_line_state(self._reading_line_visible)
        if self._is_mirror_open and self._mirror_window:
            self._mirror_window.set_reading_line_visibility(self._reading_line_visible)

    def _on_reading_line_opacity_changed(self, opacity: float):
        self._reading_line_opacity = opacity
        self._save_settings()
        color = f"rgba(219,157,22,{opacity})"
        self._view.page().runJavaScript(
            'var rl=document.getElementById("rl");if(rl){rl.style.borderColor="' + color + '";}'
        )
        if self._is_mirror_open and self._mirror_window:
            self._mirror_window.set_reading_line_opacity(opacity)

    def _on_edit_requested(self):
        if not self._manuscript:
            return
        ratio = self._scroll_position / max(1, self._scroll_height)
        self._pause()
        self.edit_current_manuscript.emit(self._manuscript.id, ratio)

    def _on_back(self):
        self._pause()
        self._close_mirror(remember=False)
        # 离开提词器前先退出全屏，避免其他页面也被全屏
        if self._is_fullscreen:
            win = self.window()
            win._resizing = True
            win.showNormal()
            self._is_fullscreen = False
            QTimer.singleShot(400, lambda: setattr(win, '_resizing', False))
        self.back_to_home.emit()

    def showEvent(self, event):
        super().showEvent(event)
        if self._shortcut_mgr is None and self.window() is not None:
            self._shortcut_mgr = ShortcutManager(self.window(), self._view)
            self._shortcut_mgr.set_shortcuts({
                Qt.Key.Key_Space: self._toggle_play,
                Qt.Key.Key_F1: self._toggle_control_panel,
                Qt.Key.Key_F2: self._toggle_reading_line,
                Qt.Key.Key_F11: self._toggle_fullscreen,
                Qt.Key.Key_Escape: self._exit_fullscreen,
                Qt.Key.Key_Up: self._start_scroll_up,
                Qt.Key.Key_Down: self._start_scroll_down,
                Qt.Key.Key_R: self._reset_scroll,
                Qt.Key.Key_M: self._toggle_mirror,
                Qt.Key.Key_Plus: self._speed_up,
                Qt.Key.Key_Equal: self._speed_up,
                Qt.Key.Key_Minus: self._speed_down,
            })
            self._shortcut_mgr.set_release_shortcuts({
                Qt.Key.Key_Up: self._stop_scroll,
                Qt.Key.Key_Down: self._stop_scroll,
            })
            self._shortcut_mgr.set_double_click_handler(self._toggle_fullscreen)
        if self._shortcut_mgr is not None:
            self._shortcut_mgr.install()

        self._init_control_panel()
        if self._control_panel is not None:
            self._control_panel.set_font_size(self._font_size)
            self._control_panel.set_line_spacing(self._line_spacing)
            self._control_panel.set_speed(self._wpm)
            self._control_panel.set_margin(self._margin)
            self._control_panel.set_mirror_state(self._is_mirror_open)
            self._control_panel.set_reading_line_state(self._reading_line_visible)
            self._control_panel.set_reading_line_opacity(self._reading_line_opacity)
            self._control_panel.set_horizontal_flip(self._horizontal_flip)
            self._control_panel.set_vertical_flip(self._vertical_flip)
            self._control_panel.show()
            self._control_panel.raise_()
            QTimer.singleShot(0, lambda: self._control_panel.set_playing(self._is_playing))
        self._progress_timer.start()
        self._start_sync_timer()
        if self._mirror_mode and not self._is_mirror_open:
            QTimer.singleShot(400, self._open_mirror)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._shortcut_mgr is not None:
            self._shortcut_mgr.uninstall()
        self._stop_scroll()
        self._stop_sync_timer()
        if self._control_panel is not None:
            self._control_panel.hide()
        self._progress_timer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_reading_line()
        self._update_mirror_scale()
        self._resync_debounce_timer.start()

