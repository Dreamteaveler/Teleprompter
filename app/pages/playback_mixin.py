# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
"""播放控制逻辑 Mixin，由 PrompterPage 继承使用。"""
import time

from PyQt6.QtCore import QTimer


class PlaybackMixin:
    """提供自动滚动播放/暂停/速度控制功能。

    要求宿主类具有以下属性：
    - _manuscript, _is_playing, _page_ready
    - _tick_frame, _last_tick_time, _pixels_per_second
    - _wpm, _font_size, _scroll_position, _scroll_height
    - _timer (QTimer), _view (QWebEngineView)
    - _control_panel, _auto_resume
    - _save_settings(), _refresh_scroll_height(), _load_content()
    - _sync_mirror_if_open()
    """

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
                "[document.documentElement.scrollHeight - window.innerHeight, window.pageYOffset]",
                lambda r: self._check_completion(r) if r is not None else None
            )

    def _check_completion(self, result):
        if not isinstance(result, list) or len(result) < 2:
            return
        max_y = float(result[0]) if result[0] is not None else 0
        current_y = float(result[1]) if result[1] is not None else 0
        # 内容不足一屏，或已滚动到底部（留 2px 容差）
        if max_y <= 1 or (max_y > 1 and current_y >= max_y - 2):
            self._pause()
            self.completed.emit()

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

    def _reset_scroll(self):
        self._scroll_position = 0.0
        self._last_tick_time = time.monotonic()
        self._pause()
        self._view.page().runJavaScript("window.scrollTo(0, 0);")
        if self._is_mirror_open and self._mirror_window and self._mirror_scale > 0:
            self._mirror_window.sync_scroll(0.0)
            rlh = int(self._font_size * self._line_spacing * 3 * self._mirror_scale)
            self._mirror_window.set_reading_line(self._mirror_reading_line_y, rlh)

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
