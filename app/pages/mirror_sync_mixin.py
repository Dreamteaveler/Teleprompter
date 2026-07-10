# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
"""镜像同步逻辑 Mixin，由 PrompterPage 继承使用。"""
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.pages.mirror_window import MirrorWindow


class MirrorSyncMixin:
    """提供镜像窗口的打开/关闭/同步功能。

    要求宿主类具有以下属性：
    - _mirror_window, _is_mirror_open, _mirror_mode
    - _mirror_scale, _mirror_reading_line_y, _reading_line_y
    - _horizontal_flip, _vertical_flip
    - _manuscript, _scroll_position, _font_size, _line_spacing
    - _view (QWebEngineView), _page_ready, _sync_pending
    - _control_panel
    - _sync_timer, _resync_debounce_timer
    - _save_settings(), _build_html()
    """

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
    #  4. 任何窗口 resize → _update_mirror_scale() 立即更新 _mirror_scale，
    #     保证滚动同步缩放比实时正确。_resync_debounce_timer(300ms) 仅在
    #     需要时重建 HTML（字号/行距/边距依赖 scale 时才变化）。
    # ═══════════════════════════════════════════════════════════════

    def _sync_mirror_content(self, keep_scroll: bool = True):
        if not self._mirror_window or not self._manuscript:
            return
        main_w = self._view.width()
        mirror_w = self._mirror_window.view_width()
        if main_w > 100 and mirror_w > 100:
            self._mirror_scale = mirror_w / main_w
        self._mirror_reading_line_y = self._reading_line_y * self._mirror_scale
        html = self._build_html(self._manuscript.content, scale=1.0, vflip=self._vertical_flip)
        scroll_y = self._scroll_position if keep_scroll else 0.0
        self._mirror_window._reading_line_visible = self._reading_line_visible
        self._mirror_window._reading_line_opacity = self._reading_line_opacity
        self._mirror_window.set_content(html, scroll_y, self._mirror_reading_line_y, self._mirror_scale)

    def _sync_mirror_if_open(self, keep_scroll: bool = True):
        if self._is_mirror_open and self._mirror_window:
            self._sync_mirror_content(keep_scroll)

    def _update_mirror_scale(self):
        if not self._mirror_window or not self._is_mirror_open:
            return
        main_w = self._view.width()
        mirror_w = self._mirror_window.view_width()
        if main_w > 100 and mirror_w > 100:
            self._mirror_scale = mirror_w / main_w
        self._mirror_reading_line_y = self._reading_line_y * self._mirror_scale
        self._mirror_window.update_scale(self._mirror_scale)

    def _on_mirror_resized(self):
        self._update_mirror_scale()
        self._resync_debounce_timer.start()

    def _on_mirror_fs_changed(self, active: bool):
        if self._control_panel:
            self._control_panel.set_mirror_fullscreen_state(active)

    def _open_mirror(self):
        if self._mirror_window is None:
            self._mirror_window = MirrorWindow()
            self._mirror_window.destroyed.connect(self._on_mirror_closed)
            self._mirror_window.resized.connect(self._on_mirror_resized)
            self._mirror_window.fullscreen_changed.connect(self._on_mirror_fs_changed)
        self._mirror_window.set_flip(self._horizontal_flip, self._vertical_flip)
        if getattr(self, '_mirror_was_fullscreen', False):
            self._mirror_window.showFullScreen()
            self._mirror_was_fullscreen = False
            fullscreen = True
        else:
            self._mirror_window.showNormal()
            fullscreen = False
            self._position_mirror_on_secondary()
        QTimer.singleShot(200, self._update_mirror_scale)
        self._is_mirror_open = True
        self._mirror_mode = True
        if self._manuscript:
            self._sync_mirror_content(keep_scroll=False)
        self._start_sync_timer()
        if self._control_panel:
            self._control_panel.set_mirror_state(True)
            self._control_panel.set_mirror_fullscreen_state(fullscreen)

    def _position_mirror_on_secondary(self):
        if not self._mirror_window:
            return
        app = QApplication.instance()
        if not app:
            return
        screens = app.screens()
        primary = app.primaryScreen()
        if len(screens) < 2:
            return
        if len(screens) > 2:
            QMessageBox.information(
                self._mirror_window, "多显示器提示",
                "检测到超过2个显示器，请手动调整镜像窗口位置。"
            )
            return
        for screen in screens:
            if screen is not primary:
                geo = screen.availableGeometry()
                self._mirror_window.move(
                    geo.x() + (geo.width() - self._mirror_window.width()) // 2,
                    geo.y() + (geo.height() - self._mirror_window.height()) // 2,
                )
                return

    def _close_mirror(self, remember: bool = True):
        self._is_mirror_open = False
        if remember:
            self._mirror_mode = False
        self._stop_sync_timer()
        if self._mirror_window:
            self._mirror_was_fullscreen = self._mirror_window.isFullScreen()
            if self._mirror_was_fullscreen:
                self._mirror_window.showNormal()
            self._mirror_window.close()
            self._mirror_window.deleteLater()
            self._mirror_window = None
        if self._control_panel:
            self._control_panel.set_mirror_state(False)
            self._control_panel.set_mirror_fullscreen_state(False)

    def _on_mirror_closed(self):
        self._mirror_window = None
        self._is_mirror_open = False
        self._mirror_mode = False
        self._stop_sync_timer()
        if self._control_panel:
            self._control_panel.set_mirror_state(False)

    def _toggle_mirror(self):
        if self._is_mirror_open:
            self._close_mirror()
        else:
            self._open_mirror()

    def _on_horizontal_flip_toggled(self, enabled: bool):
        self._horizontal_flip = enabled
        if enabled:
            self._vertical_flip = False
        if self._is_mirror_open and self._mirror_window:
            self._mirror_window.set_flip(self._horizontal_flip, self._vertical_flip, rebuild=False)
            self._sync_mirror_content()

    def _on_vertical_flip_toggled(self, enabled: bool):
        self._vertical_flip = enabled
        if enabled:
            self._horizontal_flip = False
        if self._is_mirror_open and self._mirror_window:
            self._mirror_window.set_flip(self._horizontal_flip, self._vertical_flip, rebuild=False)
            self._sync_mirror_content()

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
        self._sync_version += 1
        version = self._sync_version
        self._view.page().runJavaScript(
            "[window.pageYOffset, document.documentElement.scrollHeight - window.innerHeight, window.getReadingLineTop ? window.getReadingLineTop() : (window.innerHeight/3), (document.getElementById('rl')||{}).offsetHeight||0]",
            lambda result: self._on_sync_position(result, version)
        )

    #  ── 百分比同步（兼容不同分辨率下的折行差异） ──
    #  主屏百分比 = scrollY / maxY → 镜像 scrollY = 百分比 × mirror_maxY
    #  引导框仍然用像素坐标，CSS transform 方案保证一致性
    def _on_sync_position(self, result, version):
        if version != self._sync_version:
            return
        if result is None:
            return
        scroll_y = float(result[0]) if result[0] is not None else self._scroll_position
        max_y = float(result[1]) if len(result) > 1 and result[1] is not None else 1
        rl_y = float(result[2]) if len(result) > 2 and result[2] is not None else 0
        rl_h = float(result[3]) if len(result) > 3 and result[3] is not None else 0
        self._scroll_position = scroll_y
        self._accumulated_scroll = scroll_y
        if self._mirror_window and max_y > 0:
            ratio = scroll_y / max_y
            self._mirror_window.sync_scroll_pct(ratio)
            self._mirror_window.set_reading_line(rl_y, rl_h)
