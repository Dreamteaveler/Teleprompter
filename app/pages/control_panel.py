# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal


class ControlPanel(QWidget):
    back_requested = pyqtSignal()
    play_pause_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    font_size_changed = pyqtSignal(int)
    line_spacing_changed = pyqtSignal(int)
    speed_changed = pyqtSignal(int)
    margin_changed = pyqtSignal(int)
    mirror_toggled = pyqtSignal()
    reading_line_toggled = pyqtSignal()
    horizontal_flip_toggled = pyqtSignal(bool)
    vertical_flip_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("控制面板")
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMinimumWidth(280)
        self.resize(300, 560)

        self._is_playing = False
        self._dragging = False
        self._drag_pos = None

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0d0d;
                color: #f2f2f2;
                font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
                font-size: 13px;
            }
            QPushButton {
                background-color: #141414;
                color: #f2f2f2;
                border: 1px solid #2e2e2e;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1f1f1f;
                border-color: #DB9D16;
                color: #DB9D16;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton#playBtn {
                background-color: #DB9D16;
                color: #000000;
                border: none;
                font-weight: 700;
                font-size: 14px;
                padding: 10px;
                border-radius: 10px;
            }
            QPushButton#playBtn:hover {
                background-color: #c48d14;
            }
            QPushButton#pauseBtn {
                background-color: rgba(219, 157, 22, 0.15);
                color: #DB9D16;
                border: 1px solid rgba(219, 157, 22, 0.3);
                font-weight: 700;
                font-size: 14px;
                padding: 10px;
                border-radius: 10px;
            }
            QPushButton#pauseBtn:hover {
                background-color: rgba(219, 157, 22, 0.25);
            }
            QSlider::groove:horizontal {
                background: #2e2e2e;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #DB9D16;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #c48d14;
            }
            QSlider::sub-page:horizontal {
                background: #DB9D16;
                border-radius: 2px;
            }
            QProgressBar {
                background-color: #2e2e2e;
                border: none;
                border-radius: 6px;
                height: 8px;
                text-align: center;
                font-size: 10px;
                color: #f2f2f2;
            }
            QProgressBar::chunk {
                background-color: #DB9D16;
                border-radius: 6px;
            }
            QLabel#valueLabel {
                color: #DB9D16;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#sectionLabel {
                color: #9e9e9e;
                font-size: 11px;
            }
            QLabel#titleLabel {
                font-size: 14px;
                font-weight: 700;
                color: #f2f2f2;
            }
            QLabel#hintLabel {
                color: #555555;
                font-size: 10px;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        frame = QFrame()
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # ─── Title Bar (draggable) ──────────────────
        title_bar = QHBoxLayout()
        title_bar.addStretch()
        title = QLabel("控制面板")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f2f2f2;")
        title_bar.addWidget(title)
        title_bar.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.08); border: 1px solid #444; color: #bbb; font-size: 20px; font-weight: 600; border-radius: 10px; }"
            "QPushButton:hover { color: #fff; background: rgba(220,60,60,0.2); border-color: rgba(220,60,60,0.5); }"
        )
        close_btn.clicked.connect(self.hide)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        # ─── Back / Reset row ───────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        back_btn = QPushButton("← 返回")
        back_btn.clicked.connect(self.back_requested.emit)
        btn_row.addWidget(back_btn)

        reset_btn = QPushButton("↺ 重置")
        reset_btn.clicked.connect(self.reset_requested.emit)
        btn_row.addWidget(reset_btn)

        layout.addLayout(btn_row)

        # ─── Play / Pause button ────────────────────
        self._play_btn = QPushButton("▶ 播放  (空格)")
        self._play_btn.setObjectName("playBtn")
        self._play_btn.clicked.connect(self.play_pause_requested.emit)
        layout.addWidget(self._play_btn)

        # ─── Margin ─────────────────────────────────
        self._margin_label = QLabel("5")
        layout.addLayout(self._make_section_row(
            "页边距", "%", self._margin_label
        ))
        self._margin_slider = QSlider(Qt.Orientation.Horizontal)
        self._margin_slider.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._margin_slider.setRange(0, 40)
        self._margin_slider.setValue(5)
        self._margin_slider.valueChanged.connect(self._on_margin_changed)
        layout.addWidget(self._margin_slider)

        # ─── Font Size ──────────────────────────────
        self._font_size_label = QLabel("120")
        layout.addLayout(self._make_section_row(
            "字号", "px", self._font_size_label
        ))
        self._font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._font_size_slider.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._font_size_slider.setRange(50, 250)
        self._font_size_slider.setValue(120)
        self._font_size_slider.valueChanged.connect(self._on_font_size_changed)
        layout.addWidget(self._font_size_slider)

        # ─── Line Spacing ───────────────────────────
        self._line_spacing_label = QLabel("1.2")
        layout.addLayout(self._make_section_row(
            "行距", "", self._line_spacing_label
        ))
        self._line_spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self._line_spacing_slider.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._line_spacing_slider.setRange(10, 30)
        self._line_spacing_slider.setValue(12)
        self._line_spacing_slider.valueChanged.connect(self._on_line_spacing_changed)
        layout.addWidget(self._line_spacing_slider)

        # ─── Speed ──────────────────────────────────
        self._speed_label = QLabel("30")
        layout.addLayout(self._make_section_row(
            "播放速度", "WPM", self._speed_label
        ))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._speed_slider.setRange(0, 400)
        self._speed_slider.setValue(30)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        layout.addWidget(self._speed_slider)

        # ─── Reading Line Toggle ────────────────────
        reading_line_layout = QHBoxLayout()
        reading_line_title = QLabel("引导框")
        reading_line_title.setObjectName("sectionLabel")
        reading_line_layout.addWidget(reading_line_title)
        reading_line_layout.addStretch()
        self._reading_line_label = QLabel("已开启")
        self._reading_line_label.setObjectName("valueLabel")
        reading_line_layout.addWidget(self._reading_line_label)
        layout.addLayout(reading_line_layout)

        self._reading_line_btn = QPushButton("关闭引导框")
        self._reading_line_btn.clicked.connect(self.reading_line_toggled.emit)
        layout.addWidget(self._reading_line_btn)

        # ─── Mirror Toggle ──────────────────────────
        mirror_layout = QHBoxLayout()
        mirror_title = QLabel("镜像模式")
        mirror_title.setObjectName("sectionLabel")
        mirror_layout.addWidget(mirror_title)
        mirror_layout.addStretch()
        self._mirror_label = QLabel("已关闭")
        self._mirror_label.setObjectName("valueLabel")
        mirror_layout.addWidget(self._mirror_label)
        layout.addLayout(mirror_layout)

        self._mirror_btn = QPushButton("开启镜像")
        self._mirror_btn.clicked.connect(self.mirror_toggled.emit)
        layout.addWidget(self._mirror_btn)

        # ─── Flip Toggles ───────────────────────────
        flip_row = QHBoxLayout()
        flip_row.setSpacing(8)

        self._hflip_btn = QPushButton("水平翻转: 开")
        self._hflip_btn.setCheckable(True)
        self._hflip_btn.setChecked(True)
        self._hflip_btn.clicked.connect(self._on_hflip_toggled)
        flip_row.addWidget(self._hflip_btn)

        self._vflip_btn = QPushButton("垂直翻转: 关")
        self._vflip_btn.setCheckable(True)
        self._vflip_btn.setChecked(False)
        self._vflip_btn.clicked.connect(self._on_vflip_toggled)
        flip_row.addWidget(self._vflip_btn)

        layout.addLayout(flip_row)

        # ─── Progress Bar ───────────────────────────
        progress_layout = QHBoxLayout()
        progress_title = QLabel("播放进度")
        progress_title.setObjectName("sectionLabel")
        progress_layout.addWidget(progress_title)
        progress_layout.addStretch()
        self._progress_label = QLabel("0%")
        self._progress_label.setObjectName("valueLabel")
        progress_layout.addWidget(self._progress_label)
        layout.addLayout(progress_layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        # ─── Hint ───────────────────────────────────
        hint1 = QLabel("空格播放 · ↑↓长按变速滚动 · +/- 调速")
        hint1.setObjectName("hintLabel")
        hint1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint1)

        hint2 = QLabel("R 重置 · M 镜像 · F2 引导框 · F1 隐藏面板")
        hint2.setObjectName("hintLabel")
        hint2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint2)

        layout.addStretch()

    def _make_section_row(self, title_text, unit, value_label):
        row = QHBoxLayout()
        section = QLabel(title_text)
        section.setObjectName("sectionLabel")
        row.addWidget(section)
        row.addStretch()
        value_label.setObjectName("valueLabel")
        row.addWidget(value_label)
        if unit:
            row.addWidget(QLabel(unit))
        return row

    def _on_margin_changed(self, value):
        self._margin_label.setText(str(value))
        self.margin_changed.emit(value)

    def _on_font_size_changed(self, value):
        self._font_size_label.setText(str(value))
        self.font_size_changed.emit(value)

    def _on_line_spacing_changed(self, value):
        text = f"{value / 10:.1f}"
        self._line_spacing_label.setText(text)
        self.line_spacing_changed.emit(value)

    def _on_speed_changed(self, value):
        self._speed_label.setText(str(value))
        self.speed_changed.emit(value)

    def set_playing(self, playing: bool):
        self._is_playing = playing
        if playing:
            self._play_btn.setText("⏸ 暂停  (空格)")
            self._play_btn.setStyleSheet(
                "background-color: rgba(219, 157, 22, 0.15); color: #DB9D16;"
                "border: 1px solid rgba(219, 157, 22, 0.3); font-weight: 700;"
                "font-size: 14px; padding: 10px; border-radius: 10px;"
            )
        else:
            self._play_btn.setText("▶ 播放  (空格)")
            self._play_btn.setStyleSheet(
                "background-color: #DB9D16; color: #000000; border: none;"
                "font-weight: 700; font-size: 14px; padding: 10px; border-radius: 10px;"
            )

    def set_progress(self, percent: float):
        pct = max(0, min(100, int(percent)))
        self._progress_bar.setValue(pct)
        self._progress_label.setText(f"{pct}%")

    def set_font_size(self, value: int):
        self._font_size_slider.blockSignals(True)
        self._font_size_slider.setValue(value)
        self._font_size_label.setText(str(value))
        self._font_size_slider.blockSignals(False)

    def set_line_spacing(self, value: float):
        ival = int(value * 10)
        self._line_spacing_slider.blockSignals(True)
        self._line_spacing_slider.setValue(ival)
        self._line_spacing_label.setText(f"{ival / 10:.1f}")
        self._line_spacing_slider.blockSignals(False)

    def set_speed(self, value: int):
        self._speed_slider.blockSignals(True)
        self._speed_slider.setValue(value)
        self._speed_label.setText(str(value))
        self._speed_slider.blockSignals(False)

    def set_margin(self, value: int):
        self._margin_slider.blockSignals(True)
        self._margin_slider.setValue(value)
        self._margin_label.setText(str(value))
        self._margin_slider.blockSignals(False)

    def set_mirror_state(self, active: bool):
        if active:
            self._mirror_label.setText("已开启")
            self._mirror_btn.setText("关闭镜像")
        else:
            self._mirror_label.setText("已关闭")
            self._mirror_btn.setText("开启镜像")

    def set_reading_line_state(self, active: bool):
        if active:
            self._reading_line_label.setText("已开启")
            self._reading_line_btn.setText("关闭引导框")
        else:
            self._reading_line_label.setText("已关闭")
            self._reading_line_btn.setText("开启引导框")

    def _on_hflip_toggled(self, checked: bool):
        if checked:
            self._hflip_btn.setText("水平翻转: 开")
            self._vflip_btn.blockSignals(True)
            self._vflip_btn.setChecked(False)
            self._vflip_btn.setText("垂直翻转: 关")
            self._vflip_btn.blockSignals(False)
        else:
            self._hflip_btn.setText("水平翻转: 关")
        self.horizontal_flip_toggled.emit(checked)

    def _on_vflip_toggled(self, checked: bool):
        if checked:
            self._vflip_btn.setText("垂直翻转: 开")
            self._hflip_btn.blockSignals(True)
            self._hflip_btn.setChecked(False)
            self._hflip_btn.setText("水平翻转: 关")
            self._hflip_btn.blockSignals(False)
        else:
            self._vflip_btn.setText("垂直翻转: 关")
        self.vertical_flip_toggled.emit(checked)

    def set_horizontal_flip(self, enabled: bool):
        self._hflip_btn.blockSignals(True)
        self._hflip_btn.setChecked(enabled)
        self._hflip_btn.setText("水平翻转: 开" if enabled else "水平翻转: 关")
        self._hflip_btn.blockSignals(False)

    def set_vertical_flip(self, enabled: bool):
        self._vflip_btn.blockSignals(True)
        self._vflip_btn.setChecked(enabled)
        self._vflip_btn.setText("垂直翻转: 开" if enabled else "垂直翻转: 关")
        self._vflip_btn.blockSignals(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._drag_pos = None
        event.accept()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
