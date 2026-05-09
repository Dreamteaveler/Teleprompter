# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.database import list_manuscripts, search_manuscripts, delete_manuscript, create_manuscript
from app.models import Manuscript
from app.docx_importer import import_docx_file


CARD_WIDTH = 240
CARD_HEIGHT = 160


class ManuscriptCard(QFrame):
    clicked = pyqtSignal(int)
    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)
    play_clicked = pyqtSignal(int)

    def __init__(self, manuscript: Manuscript, parent=None):
        super().__init__(parent)
        self._manuscript = manuscript
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        icon = QLabel("📄")
        icon.setFont(QFont("Segoe UI Emoji", 14))
        top_row.addWidget(icon)
        top_row.addStretch()

        action_btn_style = (
            "QPushButton { background: transparent; border: none; color: #555; padding: 2px 6px; font-size: 11px; }"
            "QPushButton:hover { color: #f2f2f2; }"
        )

        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet(action_btn_style)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._manuscript.id))
        top_row.addWidget(edit_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet(
            action_btn_style + "QPushButton:hover { color: #ef4444; }"
        )
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._manuscript.id))
        top_row.addWidget(delete_btn)

        layout.addLayout(top_row)

        title_label = QLabel(manuscript.title if manuscript.title else "未命名稿件")
        title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f2f2f2;")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(36)
        layout.addWidget(title_label)

        preview = manuscript.plain_text_preview(60)
        preview_label = QLabel(preview)
        preview_label.setObjectName("mutedLabel")
        preview_label.setWordWrap(True)
        preview_label.setStyleSheet("color: #9e9e9e; font-size: 11px; line-height: 1.4;")
        layout.addWidget(preview_label, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        date_label = QLabel(manuscript.formatted_date())
        date_label.setStyleSheet("color: #9e9e9e; font-size: 10px;")
        footer.addWidget(date_label)
        footer.addStretch()
        time_label = QLabel(manuscript.estimated_read_time())
        time_label.setStyleSheet("color: #555; font-size: 10px;")
        footer.addWidget(time_label)
        layout.addLayout(footer)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.setStyleSheet("""QFrame#card {
            border-color: rgba(219, 157, 22, 0.5);
            background-color: #171717;
            border-radius: 12px;
        }""")

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.setStyleSheet("""QFrame#card {
            background-color: #141414;
            border: 1px solid #2e2e2e;
            border-radius: 12px;
        }""")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self._manuscript.id)


class HomePage(QWidget):
    navigate_to_prompter = pyqtSignal(int)
    navigate_to_editor = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manuscripts: list[Manuscript] = []
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ─── 顶部导航栏 ──────────────────────
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)

        logo = QLabel("提词器")
        logo.setStyleSheet("font-size: 18px; font-weight: 700; color: #f2f2f2;")
        header_layout.addWidget(logo)

        header_layout.addStretch()

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchField")
        self._search_input.setPlaceholderText("🔍 搜索稿件...")
        self._search_input.setFixedWidth(260)
        self._search_input.setFixedHeight(36)
        self._search_input.textChanged.connect(self._on_search)
        header_layout.addWidget(self._search_input)

        import_btn = QPushButton("📄 导入 Word")
        import_btn.setObjectName("ghostButton")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_word)
        header_layout.addWidget(import_btn)

        new_btn = QPushButton("+ 新建稿件")
        new_btn.setObjectName("accentButton")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(lambda: self.navigate_to_editor.emit(None))
        header_layout.addWidget(new_btn)

        layout.addWidget(header)

        # ─── 主内容区域 ──────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(40, 24, 40, 24)
        self._scroll_layout.setSpacing(16)

        # 标题栏
        self._count_label = QLabel("全部稿件")
        self._count_label.setObjectName("sectionTitle")
        self._scroll_layout.addWidget(self._count_label)

        # 卡片网格容器
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.addWidget(self._cards_widget)
        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def _import_word(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入 Word 文档", "", "Word 文档 (*.docx)"
        )
        if not filepath:
            return
        reply = QMessageBox.information(
            self, "提示",
            "导入的文档中如包含图片，将不会被加载显示。",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Ok,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return
        try:
            html_content, has_formulas = import_docx_file(filepath)
            title = filepath.split("/")[-1].split("\\")[-1].replace(".docx", "")
            if has_formulas:
                reply = QMessageBox.question(
                    self, "检测到公式",
                    "该文档含有公式，是否将其转换为 LaTeX 格式以正确渲染？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    html_content, _ = import_docx_file(filepath, formula_mode="latex")
            import re
            html_content = re.sub(r'<img[^>]*/?>', '', html_content, flags=re.DOTALL)
            manuscript = create_manuscript(title, html_content)
            self.navigate_to_editor.emit(manuscript)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法导入 Word 文档：\n{e}")

    def _on_search(self, text: str):
        if text.strip():
            self._manuscripts = search_manuscripts(text.strip())
        else:
            self._manuscripts = list_manuscripts()
        self._render_cards()

    def _refresh(self):
        self._manuscripts = list_manuscripts()
        self._render_cards()

    def _render_cards(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        count = len(self._manuscripts)
        self._count_label.setText(f"全部稿件（共 {count} 条）")

        if count == 0:
            empty = QWidget()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.setSpacing(16)

            icon = QLabel("📄")
            icon.setFont(QFont("Segoe UI Emoji", 48))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(icon)

            msg = QLabel("暂无稿件\n点击右上角「新建稿件」开始创作")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setObjectName("mutedLabel")
            msg.setStyleSheet("font-size: 15px; line-height: 1.8;")
            empty_layout.addWidget(msg)

            self._cards_layout.addWidget(empty)
            return

        row_layout = None
        card_spacing = 12
        available_width = self.width() - 80
        if available_width <= 100:
            available_width = 1100
        row_width = 0

        for ms in self._manuscripts:
            if row_layout is None or row_width + CARD_WIDTH > available_width:
                if row_layout is not None:
                    row_layout.addStretch()
                row_layout = QHBoxLayout()
                row_layout.setSpacing(card_spacing)
                row_layout.setContentsMargins(0, 0, 0, 0)
                self._cards_layout.addLayout(row_layout)
                row_width = 0

            card = ManuscriptCard(ms)
            card.play_clicked.connect(self.navigate_to_prompter.emit)
            card.edit_clicked.connect(lambda mid: self.navigate_to_editor.emit(
                next((m for m in self._manuscripts if m.id == mid), None)
            ))
            card.delete_clicked.connect(self._confirm_delete)
            row_layout.addWidget(card)
            row_width += CARD_WIDTH + card_spacing

        if row_layout is not None:
            row_layout.addStretch()
        self._cards_layout.addStretch()

    def _confirm_delete(self, manuscript_id: int):
        ms = next((m for m in self._manuscripts if m.id == manuscript_id), None)
        if not ms:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除稿件「{ms.title or '未命名'}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_manuscript(manuscript_id)
            self._refresh()

    def refresh(self):
        self._search_input.clear()
        self._refresh()
