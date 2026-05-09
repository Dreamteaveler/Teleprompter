# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
import sys
import os
import time
import re
import html as html_module
import markdown
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

from app.database import get_setting, set_setting
from app.models import Manuscript
from app.pages.mirror_window import MirrorWindow
from app.pages.control_panel import ControlPanel
from app.shortcut_manager import ShortcutManager

# ----------------------------------------------------------------
# 1. 已删除 SPEED_PRESETS 预设速度列表
# ----------------------------------------------------------------


def _mathjax_url() -> str:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    js_path = os.path.join(base, "app", "mathjax", "tex-chtml.js")
    return Path(js_path).as_uri()


def _mathjax_base_url() -> QUrl:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mathjax_dir = os.path.join(base, "app", "mathjax")
    return QUrl.fromLocalFile(mathjax_dir)

_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body {
    background:#0d0d0d;
    color:#f2f2f2;
    width:100%;
    font-size:__FS__px;
    line-height:__LH__;
    padding:__PT__px __PX__px __PB__px __PX__px;
    overflow-x: hidden;
    overflow-y: scroll;
    user-select: none;
    -webkit-user-select: none;
}
.content p{margin:0.5em 0;}
.content h1,.content h2,.content h3{margin:0.6em 0 0.3em;font-weight:700;}
.content h1{font-size:1.4em;}
.content h2{font-size:1.2em;}
.content h3{font-size:1.05em;}
.content sup{vertical-align:super;font-size:0.92em;}
.content sub{vertical-align:sub;font-size:0.92em;}
.content strong{font-weight:700;color:#FFD966;}
.content em{font-style:italic;}
.content blockquote{border-left:3px solid #DB9D16;margin:0.5em 0;padding:0.3em 1em;color:#bbb;}
.content code{background:#1a1a1a;padding:2px 6px;border-radius:4px;font-family:monospace;}
.content pre{background:#1a1a1a;padding:12px 16px;border-radius:6px;overflow-x:auto;}
.content ul,.content ol{margin:0.4em 0;padding-left:1.5em;}
.content li{margin:0.2em 0;}
mjx-container{font-size:1.05em;}
img{max-width:100%;height:auto;display:block;margin:4px 0;}
table{border-collapse:collapse;width:100%;margin:8px 0;}
td,th{border:1px solid #2e2e2e;padding:6px 10px;}
#rl{position:fixed;left:2%;right:2%;height:__RLH__px;border:8px dashed rgba(219,157,22,1);border-radius:8px;background:transparent;pointer-events:auto;cursor:ns-resize;display:none;z-index:100;box-sizing:border-box;}
</style>
<script>
MathJax = {
    tex: {
        inlineMath: [['$', '$']],
        displayMath: [['$$', '$$']],
        processEscapes: true,
        processEnvironments: true
    },
    options: {
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
    }
};
</script>
<script id="MathJax-script" async src="__MATHJAX__"></script>
</head>
<body>
<div class="content">__BODY__</div>
<div id="rl"></div>
<script>
// ── 引导框拖拽 ──
// window._readingLineTop：视口相对 Y（px），水平翻转不影响 Y 轴。
// 16ms 同步定时器读取此值，×_mirror_scale 后推送到镜像。
(function(){
  var rl=document.getElementById('rl');
  var dragging=false,startY=0,startTop=0;
  window._readingLineTop = window.innerHeight / 3;
  rl.addEventListener('mousedown',function(e){
    dragging=true;startY=e.clientY;startTop=parseInt(rl.style.top)||(window.innerHeight/3);
    rl.style.cursor='grabbing';e.preventDefault();
  });
  document.addEventListener('mousemove',function(e){
    if(!dragging)return;
    var newTop=Math.max(0,Math.min(window.innerHeight-rl.offsetHeight,startTop+e.clientY-startY));
    rl.style.top=newTop+'px';
    window._readingLineTop = newTop;
  });
  document.addEventListener('mouseup',function(){
    if(dragging){
      dragging=false;
      rl.style.cursor='ns-resize';
      window._readingLineTop = parseInt(rl.style.top)||(window.innerHeight/3);
    }
  });
  window.getReadingLineTop = function(){
    return window._readingLineTop || (window.innerHeight / 3);
  };
})();
</script>
<script>
(function() {
  function scaleFormulas() {
    var content = document.querySelector('.content');
    if (!content) return;
    var maxWidth = content.getBoundingClientRect().width;
    if (maxWidth <= 0) return;
    document.querySelectorAll('mjx-container').forEach(function(mjx) {
      mjx.style.fontSize = '';
      var w = mjx.getBoundingClientRect().width;
      if (mjx.getAttribute('display') === 'true') {
        var innerMath = mjx.querySelector('mjx-math');
        if (innerMath) w = innerMath.getBoundingClientRect().width;
      }
      if (w > maxWidth + 1) {
        var cs = getComputedStyle(mjx);
        var currentFs = parseFloat(cs.fontSize);
        var parentFs = parseFloat(getComputedStyle(mjx.parentElement).fontSize);
        var ratio = parentFs > 0 ? currentFs / parentFs : 1;
        mjx.style.fontSize = (maxWidth / w * 100 * ratio).toFixed(1) + '%';
      }
    });
  }

  function init() {
    if (window.MathJax && MathJax.startup && MathJax.startup.promise) {
      MathJax.startup.promise.then(function() {
        requestAnimationFrame(function() {
          requestAnimationFrame(scaleFormulas);
        });
        window.addEventListener('resize', function() {
          clearTimeout(window._mjxScaleTimer);
          window._mjxScaleTimer = setTimeout(scaleFormulas, 200);
        });
      });
    } else {
      setTimeout(init, 100);
    }
  }

  init();
})();
</script>
</body></html>"""


class PrompterPage(QWidget):
    back_to_home = pyqtSignal()
    completed = pyqtSignal()

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

    def _save_settings(self):
        set_setting("font_size", str(self._font_size))
        set_setting("wpm", str(self._wpm))
        set_setting("line_spacing", str(self._line_spacing))
        set_setting("mirror_mode", "true" if self._mirror_mode else "false")
        set_setting("horizontal_margin", str(self._margin))
        set_setting("horizontal_flip", "true" if self._horizontal_flip else "false")
        set_setting("vertical_flip", "true" if self._vertical_flip else "false")

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

    def _build_html(self, text: str, scale: float = 1.0) -> str:
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
        body = re.sub(r'<img[^>]*/?>', '', body, flags=re.DOTALL)

        fs = int(self._font_size * scale)
        lh = self._line_spacing
        pt = int(fs * 0.3)
        pb = int(fs * 1.5)
        px = int(fs * (0.5 + self._margin / 5.0))
        rlh = int(fs * self._line_spacing * 3)

        html = _HTML_TEMPLATE
        html = html.replace("__MATHJAX__", _mathjax_url())
        html = html.replace("__FS__", str(fs))
        html = html.replace("__LH__", str(lh))
        html = html.replace("__PT__", str(pt))
        html = html.replace("__PB__", str(pb))
        html = html.replace("__PX__", str(px))
        html = html.replace("__RLH__", str(rlh))
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
        body = re.sub(r'\bcolor\s*:\s*(?:#000(?:000)?|black)\s*;?', '', body)
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
        self._view.setHtml(html, _mathjax_base_url())

    def load_manuscript(self, manuscript: Manuscript):
        self._manuscript = manuscript
        self._load_content(manuscript.content)
        if self._is_mirror_open:
            self._sync_mirror_content()
        self._scroll_position = 0.0
        self._start_time = 0.0
        self._pixels_per_second = 0.0
        self._is_playing = False
        self._timer.stop()

    # ═══════════════════════════════════════════════════════════════
    #  镜像同步核心原则（SOLID）
    #
    #  1. _sync_timer (16ms) 是唯一滚动+引导框同步入口。
    #     _tick / _tick_scroll 绝不直接调用 sync_scroll。
    #     所有滚动（播放/键盘/滚轮）都通过 16ms 定时器统一
    #     从 JS 读取主窗口 scrollY 和引导框 Y，乘以 _mirror_scale 后
    #     推送到镜像窗口。
    #
    #  2. _sync_mirror_content() 重建整个镜像 HTML（字号/行距/
    #     边距变化时调用）。内部重新计算 _mirror_scale。
    #
    #  3. 引导框（Reading Line）独立于文字滚动层：
    #     position:fixed，不随文字 scroll 移动。
    #     镜像侧：#rl 是 body 的直接子元素，.flip-wrapper
    #     的 transform 只包裹 .content，#rl 不受影响。
    #     主窗口拖拽引导框 → JS 更新 window._readingLineTop →
    #     _tick_sync_mirror 读取并 ×_mirror_scale 推送到镜像。
    #
    #  4. 任何窗口 resize → _resync_debounce_timer(300ms) →
    #     _sync_mirror_if_open() 重建 HTML + 重新计算缩放。
    # ═══════════════════════════════════════════════════════════════

    def _sync_mirror_content(self, keep_scroll: bool = False):
        if not self._mirror_window or not self._manuscript:
            return
        main_w = max(100, self._view.width())
        mirror_w = self._mirror_window.view_width()
        self._mirror_scale = mirror_w / main_w
        self._mirror_reading_line_y = self._reading_line_y * self._mirror_scale
        html = self._build_html(self._manuscript.content, scale=self._mirror_scale)
        scroll_y = self._scroll_position * self._mirror_scale if keep_scroll else 0.0
        self._mirror_window.set_content(html, scroll_y, self._mirror_reading_line_y)

    def _sync_mirror_if_open(self, keep_scroll: bool = False):
        if self._is_mirror_open and self._mirror_window:
            self._sync_mirror_content(keep_scroll)

    def _open_mirror(self):
        if self._mirror_window is None:
            self._mirror_window = MirrorWindow()
            self._mirror_window.destroyed.connect(self._on_mirror_closed)
            self._mirror_window.resized.connect(self._resync_debounce_timer.start)
        self._mirror_window.set_flip(self._horizontal_flip, self._vertical_flip)
        self._mirror_window.showNormal()
        self._is_mirror_open = True
        self._mirror_mode = True
        self._save_settings()
        if self._manuscript:
            self._sync_mirror_content()
        self._start_sync_timer()
        if self._control_panel:
            self._control_panel.set_mirror_state(True)

    def _close_mirror(self):
        self._is_mirror_open = False
        self._mirror_mode = False
        self._save_settings()
        self._stop_sync_timer()
        if self._mirror_window:
            self._mirror_window.close()
        if self._control_panel:
            self._control_panel.set_mirror_state(False)

    def _on_mirror_closed(self):
        self._mirror_window = None
        self._is_mirror_open = False
        self._mirror_mode = False
        self._save_settings()
        self._stop_sync_timer()
        if self._control_panel:
            self._control_panel.set_mirror_state(False)

    def _toggle_play(self):
        if self._is_playing:
            self._pause()
        else:
            self._play()

    def _play(self):
        if not self._manuscript or not self._manuscript.content.strip():
            return
        self._is_playing = True
        self._tick_frame = 0
        self._refresh_scroll_height()
        self._last_tick_time = time.monotonic()
        chars_per_minute = self._wpm * 2.5
        self._pixels_per_second = chars_per_minute / 60.0 * self._font_size * 0.6
        self._timer.start(16)
        if self._control_panel:
            QTimer.singleShot(0, lambda: self._control_panel.set_playing(True))

    def _pause(self):
        self._is_playing = False
        self._timer.stop()
        if self._control_panel:
            QTimer.singleShot(0, lambda: self._control_panel.set_playing(False))

    def _tick(self):
        if not self._manuscript or not self._is_playing or not self._page_ready:
            self._pause()
            return
        now = time.monotonic()
        elapsed = now - self._last_tick_time
        self._last_tick_time = now
        delta = elapsed * self._pixels_per_second
        self._view.page().runJavaScript(f"window.scrollBy(0, {delta});")

        self._tick_frame += 1

        if self._tick_frame % 30 == 0:
            self._refresh_scroll_height()
            self._view.page().runJavaScript(
                "document.documentElement.scrollHeight - window.innerHeight",
                lambda max_y: self._check_completion(max_y) if max_y is not None else None
            )

    def _check_completion(self, max_y: float):
        if max_y <= 1:
            self._pause()
            self.completed.emit()

    def _reset_scroll(self):
        self._scroll_position = 0.0
        self._last_tick_time = time.monotonic()
        self._pause()
        self._view.page().runJavaScript("window.scrollTo(0, 0);")
        if self._is_mirror_open and self._mirror_window and self._mirror_scale > 0:
            self._mirror_window.sync_scroll(0.0)
            rlh = int(self._font_size * self._line_spacing * 3 * self._mirror_scale)
            self._mirror_window.set_reading_line(self._mirror_reading_line_y, rlh)

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

    def _on_speed_changed(self, value: int):
        self._wpm = value
        self._save_settings()
        if self._is_playing:
            self._pause()
            self._play()
        if self._control_panel:
            self._control_panel.set_speed(value)

    def _speed_up(self):
        new_wpm = min(400, self._wpm + 5)
        self._wpm = new_wpm
        self._save_settings()
        if self._is_playing:
            self._pause()
            self._play()
        if self._control_panel:
            self._control_panel.set_speed(new_wpm)

    def _speed_down(self):
        new_wpm = max(0, self._wpm - 5)
        self._wpm = new_wpm
        self._save_settings()
        if self._is_playing:
            self._pause()
            self._play()
        if self._control_panel:
            self._control_panel.set_speed(new_wpm)

    # ----------------------------------------------------------------
    # 3. 已删除 _apply_speed_preset 方法
    # ----------------------------------------------------------------

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

    def _on_horizontal_flip_toggled(self, enabled: bool):
        self._horizontal_flip = enabled
        if enabled:
            self._vertical_flip = False
        self._save_settings()
        if self._is_mirror_open and self._mirror_window:
            self._mirror_window.set_flip(self._horizontal_flip, self._vertical_flip)

    def _on_vertical_flip_toggled(self, enabled: bool):
        self._vertical_flip = enabled
        if enabled:
            self._horizontal_flip = False
        self._save_settings()
        if self._is_mirror_open and self._mirror_window:
            self._mirror_window.set_flip(self._horizontal_flip, self._vertical_flip)

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
            self._control_panel.horizontal_flip_toggled.connect(self._on_horizontal_flip_toggled)
            self._control_panel.vertical_flip_toggled.connect(self._on_vertical_flip_toggled)

        self._control_panel.set_font_size(self._font_size)
        self._control_panel.set_line_spacing(self._line_spacing)
        self._control_panel.set_speed(self._wpm)
        self._control_panel.set_margin(self._margin)
        self._control_panel.set_horizontal_flip(self._horizontal_flip)
        self._control_panel.set_vertical_flip(self._vertical_flip)

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

    def _toggle_mirror(self):
        if self._is_mirror_open:
            self._close_mirror()
        else:
            self._open_mirror()

    def _show_control_panel(self):
        self._init_control_panel()
        if self._control_panel is not None:
            self._control_panel.set_font_size(self._font_size)
            self._control_panel.set_line_spacing(self._line_spacing)
            self._control_panel.set_speed(self._wpm)
            self._control_panel.set_margin(self._margin)
            self._control_panel.set_mirror_state(self._is_mirror_open)
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
        self._view.page().runJavaScript(
            'var rl=document.getElementById("rl");'
            'if(rl){'
            '  rl.style.top="' + str(self._reading_line_y) + 'px";'
            '  rl.style.height="' + str(rlh) + 'px";'
            '  rl.style.display="block";'
            '  window._readingLineTop=' + str(self._reading_line_y) + ';'
            '}'
        )

    def _start_scroll_up(self):
        self._scroll_direction = -1
        self._scroll_key_start = time.monotonic()
        self._scroll_timer.start(16)

    def _start_scroll_down(self):
        self._scroll_direction = 1
        self._scroll_key_start = time.monotonic()
        self._scroll_timer.start(16)

    def _stop_scroll(self):
        self._scroll_direction = 0
        self._scroll_timer.stop()

    def _tick_scroll(self):
        if self._scroll_direction == 0:
            self._scroll_timer.stop()
            return
        elapsed = time.monotonic() - self._scroll_key_start
        speed = self._compute_scroll_speed(elapsed)
        delta = speed * self._scroll_direction
        self._view.page().runJavaScript(
            f"window.scrollBy(0, {delta});"
            "window.pageYOffset",
            lambda y: self._on_scroll_tick_position(
                float(y) if y is not None else self._scroll_position
            )
        )

    def _on_scroll_tick_position(self, y):
        self._scroll_position = y

    def _compute_scroll_speed(self, elapsed_seconds: float) -> float:
        base = self._font_size * 0.15
        acceleration = elapsed_seconds * elapsed_seconds * self._font_size * 0.6
        max_speed = 200
        return min(max_speed, base + acceleration)

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

    def _on_back(self):
        self._pause()
        self._close_mirror()
        self.back_to_home.emit()

    def showEvent(self, event):
        super().showEvent(event)
        if self._shortcut_mgr is None and self.window() is not None:
            self._shortcut_mgr = ShortcutManager(self.window(), self._view)
            self._shortcut_mgr.set_shortcuts({
                Qt.Key.Key_Space: self._toggle_play,
                Qt.Key.Key_F1: self._toggle_control_panel,
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
            self._control_panel.set_horizontal_flip(self._horizontal_flip)
            self._control_panel.set_vertical_flip(self._vertical_flip)
            self._control_panel.show()
            self._control_panel.raise_()
            QTimer.singleShot(0, lambda: self._control_panel.set_playing(self._is_playing))
        self._progress_timer.start()
        self._start_sync_timer()

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
        self._resync_debounce_timer.start()

    def _start_sync_timer(self):
        if self._is_mirror_open:
            self._sync_timer.start()

    def _stop_sync_timer(self):
        self._sync_timer.stop()

    # ── 滚动 + 引导框同步（16ms 定时器） ─────────────────
    #  镜像侧：.flip-wrapper 的 transform 只包裹 .content，
    #  #rl 是 body 的直接子元素，position:fixed 相对真实视口，
    #  不受 transform 影响。Y 轴坐标与主屏幕一致。
    def _tick_sync_mirror(self):
        if not self._is_mirror_open or not self._mirror_window:
            self._sync_timer.stop()
            return
        if not self._page_ready:
            return
        self._view.page().runJavaScript(
            "[window.pageYOffset, window.getReadingLineTop ? window.getReadingLineTop() : (window.innerHeight/3), (document.getElementById('rl')||{}).offsetHeight||0]",
            lambda result: self._on_sync_position(result)
        )

    #  ── 纯坐标缩放，无额外变换 ──
    #  scroll_y × scale → 保证不同分辨率每行文字对齐
    #  rl_y × scale    → 引导框位置等比缩放
    #  rl_h × scale    → 引导框高度等比缩放
    def _on_sync_position(self, result):
        if result is None:
            return
        scroll_y = float(result[0]) if result[0] is not None else self._scroll_position
        rl_y = float(result[1]) if len(result) > 1 and result[1] is not None else 0
        rl_h = float(result[2]) if len(result) > 2 and result[2] is not None else 0
        self._scroll_position = scroll_y
        if self._mirror_window and self._mirror_scale > 0:
            self._mirror_window.sync_scroll(scroll_y * self._mirror_scale)
            self._mirror_window.set_reading_line(rl_y * self._mirror_scale, rl_h * self._mirror_scale)
