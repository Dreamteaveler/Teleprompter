# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit,
    QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QTextCharFormat, QFont, QTextCursor,
)

import re
import html as html_module

from app.database import create_manuscript, update_manuscript
from app.models import Manuscript
from app.docx_importer import import_docx_file
from app.image_utils import compress_images_in_html


class FormulaAwareTextEdit(QTextEdit):
    formula_paste_handler = None
    post_paste_handler = None

    def insertFromMimeData(self, source):
        if self.formula_paste_handler:
            if self.formula_paste_handler(source):
                return
        super().insertFromMimeData(source)
        if self.post_paste_handler:
            self.post_paste_handler()


class EditorPage(QWidget):
    saved = pyqtSignal(int)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_id: int | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        back_btn = QPushButton("← 返回")
        back_btn.setObjectName("ghostButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self._on_cancel)
        header.addWidget(back_btn)

        header.addWidget(QLabel("标题："))
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("输入稿件标题...")
        self._title_input.setObjectName("titleInput")
        header.addWidget(self._title_input, 1)

        import_btn = QPushButton("📄 导入 Word")
        import_btn.setObjectName("ghostButton")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_word)
        header.addWidget(import_btn)

        save_btn = QPushButton("💾 保存")
        save_btn.setObjectName("accentButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        header.addWidget(save_btn)

        layout.addLayout(header)

        self._content_edit = FormulaAwareTextEdit()
        self._content_edit.setObjectName("contentEdit")
        self._content_edit.setPlaceholderText(
            "在此输入您的提词稿件内容...\n\n"
            "• 支持 Ctrl+V 粘贴图片\n"
            "• 支持复制表格、公式截图等富文本内容\n"
            "• 中文字体自动应用黑体加粗，西文自动应用 Times New Roman"
        )
        self._content_edit.setAcceptRichText(True)
        self._content_edit.formula_paste_handler = self._handle_formula_paste_mime
        self._content_edit.post_paste_handler = self._apply_chinese_formatting
        layout.addWidget(self._content_edit, 1)

    def _import_word(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入 Word 文档", "", "Word 文档 (*.docx)"
        )
        if not filepath:
            return
        try:
            html_content, has_formulas = import_docx_file(filepath)
            if not html_content:
                QMessageBox.warning(self, "导入失败", "无法读取文档内容。")
                return

            has_images = bool(re.search(r'<img[^>]*>', html_content, re.IGNORECASE))
            if has_formulas or has_images:
                reply = QMessageBox.question(
                    self, "转换提示",
                    "检测到图片或公式，是否转换格式以保证正确渲染？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                if has_formulas:
                    html_content, _ = import_docx_file(filepath, formula_mode="latex")

            self._content_edit.setHtml(html_content)
            self._apply_chinese_formatting()
            title = filepath.split("/")[-1].split("\\")[-1].replace(".docx", "")
            self._title_input.setText(title)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法导入 Word 文档：\n{e}")

    def load_manuscript(self, manuscript: Manuscript | None):
        self._editing_id = manuscript.id if manuscript else None
        if manuscript:
            self._title_input.setText(manuscript.title)
            content = manuscript.content
            is_html = "<" in content and ">" in content and (
                "<html>" in content.lower() or "<body>" in content.lower()
                or "<p>" in content.lower() or "<div>" in content.lower()
                or "<table>" in content.lower() or "<img" in content.lower()
            )
            if is_html:
                self._content_edit.setHtml(content)
            else:
                self._content_edit.setPlainText(content)
            self._apply_chinese_formatting()
        else:
            self._title_input.clear()
            self._content_edit.clear()
        self._content_edit.setFocus()

    def _save(self):
        title = self._title_input.text().strip()
        content = self._content_edit.toHtml().strip()
        content = self._normalize_html_content(content)
        if not title:
            self._title_input.setFocus()
            return
        try:
            if self._editing_id:
                update_manuscript(self._editing_id, title, content)
                saved_id = self._editing_id
            else:
                ms = create_manuscript(title, content)
                saved_id = ms.id
            self.saved.emit(saved_id)
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"无法保存稿件：\n{e}")

    def _normalize_html_content(self, html: str) -> str:
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
        if body_match:
            body = body_match.group(1)
        else:
            body = html
        body = re.sub(r'<!DOCTYPE[^>]*>', '', body, flags=re.DOTALL)
        body = re.sub(r'<html[^>]*>', '', body, flags=re.DOTALL)
        body = re.sub(r'</html>', '', body, flags=re.DOTALL)
        body = re.sub(r'<head[^>]*>.*?</head>', '', body, flags=re.DOTALL)
        body = html_module.unescape(body.strip())
        body = self._clean_html_noise(body)
        body = self._convert_formula_images(body)
        body = compress_images_in_html(body)
        return body

    @staticmethod
    def _clean_html_noise(html: str) -> str:
        """清除 Qt QTextEdit 产生的冗余样式，不动 span 标签。"""
        html = re.sub(r'<meta[^>]*>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        def _clean_attrs(attrs):
            attrs = re.sub(r'margin-top\s*:\s*\d+px\s*;?', '', attrs)
            attrs = re.sub(r'margin-bottom\s*:\s*\d+px\s*;?', '', attrs)
            attrs = re.sub(r'margin-left\s*:\s*\d+px\s*;?', '', attrs)
            attrs = re.sub(r'margin-right\s*:\s*\d+px\s*;?', '', attrs)
            attrs = re.sub(r'-qt-block-indent\s*:\s*\d+\s*;?', '', attrs)
            attrs = re.sub(r'text-indent\s*:\s*\d+px\s*;?', '', attrs)
            attrs = re.sub(r'white-space\s*:\s*pre-wrap\s*;?', '', attrs)
            attrs = re.sub(r'\s*style\s*=\s*"\s*"', '', attrs)
            attrs = re.sub(r"\s*style\s*=\s*'\s*'", '', attrs)
            return attrs

        html = re.sub(r'<p([^>]*)>', lambda m: '<p' + _clean_attrs(m.group(1)) + '>', html, flags=re.IGNORECASE)
        html = re.sub(r'<li([^>]*)>', lambda m: '<li' + _clean_attrs(m.group(1)) + '>', html, flags=re.IGNORECASE)
        html = re.sub(r'\n{3,}', '\n\n', html)
        return html

    @staticmethod
    def _convert_formula_images(html: str) -> str:
        html = re.sub(
            r'<img[^>]*class="formula"[^>]*data-latex="([^"]*)"[^>]*/?>',
            r'$\1$',
            html, flags=re.DOTALL,
        )
        html = re.sub(
            r'<img[^>]*class="formula"[^>]*alt="([^"]*)"[^>]*/?>',
            r'$\1$',
            html, flags=re.DOTALL,
        )
        return html

    def _strip_images(self, html: str) -> str:
        html = self._convert_formula_images(html)
        return re.sub(r'<img[^>]*/?>', '', html, flags=re.DOTALL)

    def _handle_formula_paste_mime(self, mime) -> bool:
        if not mime:
            return False

        has_text = mime.hasText()
        has_html = mime.hasHtml()
        plain_text = mime.text() if has_text else ""
        html_content = mime.html() if has_html else ""

        has_images = bool(re.search(r'<img[^>]*>', html_content, re.IGNORECASE))
        has_images = has_images or bool(re.search(r'data:image/', html_content))

        tex_in_text = bool(re.search(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', plain_text))
        tex_in_text = tex_in_text or bool(re.search(r'\$\$[\s\S]*?\$\$', plain_text))
        tex_in_html = bool(re.search(r'\$\$[\s\S]*?\$\$', html_content))
        tex_in_html = tex_in_html or bool(re.search(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', html_content))
        mjx_in_html = bool(re.search(r'<mjx-container', html_content, re.IGNORECASE))
        omml_in_html = bool(re.search(r'<m:oMath[>\s]|<m:oMathPara[>\s]', html_content, re.IGNORECASE))

        unicode_math = False
        count = 0
        _MATH_RANGES = [
            (0x0370, 0x03FF), (0x1F00, 0x1FFF),
            (0x2200, 0x22FF), (0x2A00, 0x2AFF),
            (0x27C0, 0x27EF), (0x2980, 0x29FF),
            (0x2070, 0x209F), (0x00B0, 0x00B0),
            (0x00B1, 0x00B1), (0x00D7, 0x00D7),
            (0x00F7, 0x00F7), (0x00B7, 0x00B7),
            (0x2190, 0x21FF), (0x2300, 0x23FF),
        ]
        for ch in plain_text:
            cp = ord(ch)
            if any(lo <= cp <= hi for lo, hi in _MATH_RANGES):
                count += 1
                if count >= 3:
                    unicode_math = True
                    break
            elif cp < 128:
                count = 0

        has_formula = tex_in_text or tex_in_html or mjx_in_html or omml_in_html or unicode_math
        if not has_images and not has_formula:
            return False

        msg = "检测到图片或公式，是否转换格式以保证正确渲染？"
        reply = QMessageBox.question(
            self, "转换提示",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            return False
        return True

    def _on_cancel(self):
        self.cancelled.emit()

    def _apply_chinese_formatting(self):
        doc = self._content_edit.document()
        text = doc.toPlainText()
        if not text:
            return

        def _is_cjk(ch):
            cp = ord(ch)
            return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                    0xF900 <= cp <= 0xFAFF or 0x3000 <= cp <= 0x303F or
                    0xFF00 <= cp <= 0xFFEF)

        def _is_latin(ch):
            cp = ord(ch)
            return (0x41 <= cp <= 0x5A or 0x61 <= cp <= 0x7A or
                    0xC0 <= cp <= 0x24F)

        formula_ranges = []
        i = 0
        while i < len(text):
            if i + 1 < len(text) and text[i:i + 2] == '$$':
                start = i
                i += 2
                while i + 1 < len(text):
                    if text[i:i + 2] == '$$':
                        i += 2
                        formula_ranges.append((start, i))
                        break
                    i += 1
                else:
                    i = start + 1
            elif text[i] == '$':
                start = i
                i += 1
                while i < len(text):
                    if text[i] == '$':
                        i += 1
                        formula_ranges.append((start, i))
                        break
                    i += 1
                else:
                    i = start + 1
            else:
                i += 1

        is_in_formula = [False] * len(text)
        for s, e in formula_ranges:
            for j in range(s, e):
                is_in_formula[j] = True

        cjk_ranges = []
        latin_ranges = []
        current_type = None
        start = None

        for i, ch in enumerate(text):
            if is_in_formula[i]:
                if start is not None:
                    if current_type == "cjk":
                        cjk_ranges.append((start, i))
                    elif current_type == "latin":
                        latin_ranges.append((start, i))
                    start = None
                    current_type = None
                continue

            if _is_cjk(ch):
                if current_type != "cjk":
                    if start is not None and current_type == "latin":
                        latin_ranges.append((start, i))
                    start = i
                    current_type = "cjk"
            elif _is_latin(ch):
                if current_type != "latin":
                    if start is not None and current_type == "cjk":
                        cjk_ranges.append((start, i))
                    start = i
                    current_type = "latin"
            else:
                if start is not None:
                    if current_type == "cjk":
                        cjk_ranges.append((start, i))
                    elif current_type == "latin":
                        latin_ranges.append((start, i))
                    start = None
                    current_type = None

        if start is not None:
            if current_type == "cjk":
                cjk_ranges.append((start, len(text)))
            elif current_type == "latin":
                latin_ranges.append((start, len(text)))

        if not cjk_ranges and not latin_ranges:
            return

        saved_cursor = self._content_edit.textCursor()
        saved_pos = saved_cursor.position()
        cursor = QTextCursor(doc)

        cjk_fmt = QTextCharFormat()
        cjk_fmt.setFontFamilies(["黑体"])
        cjk_fmt.setFontWeight(QFont.Weight.Bold)

        latin_fmt = QTextCharFormat()
        latin_fmt.setFontFamilies(["Times New Roman"])

        for start_pos, end_pos in cjk_ranges:
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(cjk_fmt)

        for start_pos, end_pos in latin_ranges:
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(latin_fmt)

        saved_cursor.setPosition(saved_pos)
        self._content_edit.setTextCursor(saved_cursor)
