# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QToolButton,
    QFileDialog, QMessageBox, QColorDialog, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt6.QtGui import (
    QTextCharFormat, QFont, QColor, QBrush, QTextCursor,
)

import re
import html as html_module

from app.database import create_manuscript, update_manuscript
from app.models import Manuscript
from app.docx_importer import import_docx_file
from app.formula_editor import FormulaEditor
from app.image_utils import compress_images_in_html

FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
FONT_FAMILIES = [
    "微软雅黑", "宋体", "黑体", "仿宋", "楷体",
    "Arial", "Arial Black", "Comic Sans MS",
    "Courier New", "Georgia", "Impact",
    "Times New Roman", "Trebuchet MS", "Verdana",
]


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
        self._color_click_timer = QTimer(self)
        self._color_click_timer.setSingleShot(True)
        self._color_click_timer.timeout.connect(self._pick_font_color)
        self._bg_click_timer = QTimer(self)
        self._bg_click_timer.setSingleShot(True)
        self._bg_click_timer.timeout.connect(self._pick_bg_color)
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

        tb = QHBoxLayout()
        tb.setSpacing(4)

        self._font_family = QComboBox()
        self._font_family.addItems(FONT_FAMILIES)
        self._font_family.setCurrentText("微软雅黑")
        self._font_family.setFixedWidth(140)
        self._font_family.currentTextChanged.connect(self._on_font_family)
        tb.addWidget(self._font_family)

        self._font_size = QComboBox()
        self._font_size.addItems([str(s) for s in FONT_SIZES])
        self._font_size.setCurrentText("18")
        self._font_size.setFixedWidth(60)
        self._font_size.currentTextChanged.connect(self._on_font_size)
        tb.addWidget(self._font_size)

        tb.addSpacing(8)

        self._bold_btn = QToolButton()
        self._bold_btn.setText("B")
        self._bold_btn.setCheckable(True)
        self._bold_btn.setFixedSize(32, 32)
        self._bold_btn.setObjectName("toolbarBtn")
        bold_font = self._bold_btn.font()
        bold_font.setBold(True)
        bold_font.setPointSize(12)
        self._bold_btn.setFont(bold_font)
        self._bold_btn.setToolTip("粗体 (Ctrl+B)")
        self._bold_btn.clicked.connect(self._toggle_bold)
        tb.addWidget(self._bold_btn)

        self._italic_btn = QToolButton()
        self._italic_btn.setText("I")
        self._italic_btn.setCheckable(True)
        self._italic_btn.setFixedSize(32, 32)
        self._italic_btn.setObjectName("toolbarBtn")
        italic_font = self._italic_btn.font()
        italic_font.setItalic(True)
        italic_font.setPointSize(12)
        self._italic_btn.setFont(italic_font)
        self._italic_btn.setToolTip("斜体 (Ctrl+I)")
        self._italic_btn.clicked.connect(self._toggle_italic)
        tb.addWidget(self._italic_btn)

        self._underline_btn = QToolButton()
        self._underline_btn.setText("U")
        self._underline_btn.setCheckable(True)
        self._underline_btn.setFixedSize(32, 32)
        self._underline_btn.setObjectName("toolbarBtn")
        u_font = self._underline_btn.font()
        u_font.setUnderline(True)
        u_font.setPointSize(12)
        self._underline_btn.setFont(u_font)
        self._underline_btn.setToolTip("下划线 (Ctrl+U)")
        self._underline_btn.clicked.connect(self._toggle_underline)
        tb.addWidget(self._underline_btn)

        tb.addSpacing(4)

        self._sup_btn = QToolButton()
        self._sup_btn.setText("X²")
        self._sup_btn.setCheckable(True)
        self._sup_btn.setFixedSize(32, 32)
        self._sup_btn.setObjectName("toolbarBtn")
        sup_font = self._sup_btn.font()
        sup_font.setPointSize(9)
        self._sup_btn.setFont(sup_font)
        self._sup_btn.setToolTip("上标")
        self._sup_btn.clicked.connect(self._toggle_superscript)
        tb.addWidget(self._sup_btn)

        self._sub_btn = QToolButton()
        self._sub_btn.setText("X₂")
        self._sub_btn.setCheckable(True)
        self._sub_btn.setFixedSize(48, 32)
        self._sub_btn.setObjectName("toolbarBtn")
        sub_font = self._sub_btn.font()
        sub_font.setPointSize(9)
        self._sub_btn.setFont(sub_font)
        self._sub_btn.setToolTip("下标")
        self._sub_btn.clicked.connect(self._toggle_subscript)
        tb.addWidget(self._sub_btn)

        tb.addSpacing(8)

        self._color_btn = QToolButton()
        self._color_btn.setText("A")
        self._color_btn.setFixedSize(32, 32)
        self._color_btn.setObjectName("colorBtn")
        self._color_btn.setToolTip("字体颜色（双击设为黑色）")
        self._color_btn.setAutoRepeat(False)
        self._color_btn.installEventFilter(self)
        tb.addWidget(self._color_btn)

        self._bg_color_btn = QToolButton()
        self._bg_color_btn.setText("背景")
        self._bg_color_btn.setFixedSize(36, 32)
        self._bg_color_btn.setObjectName("colorBtn")
        self._bg_color_btn.setToolTip("底色（双击清除底色）")
        self._bg_color_btn.setAutoRepeat(False)
        self._bg_color_btn.installEventFilter(self)
        tb.addWidget(self._bg_color_btn)

        self._clear_color_btn = QToolButton()
        self._clear_color_btn.setText("无底纹")
        self._clear_color_btn.setFixedSize(48, 32)
        self._clear_color_btn.setObjectName("toolbarBtn")
        self._clear_color_btn.setToolTip("清除底色")
        self._clear_color_btn.clicked.connect(self._clear_bg)
        tb.addWidget(self._clear_color_btn)

        tb.addSpacing(8)

        self._formula_btn = QToolButton()
        self._formula_btn.setText("Σ")
        self._formula_btn.setFixedSize(36, 32)
        self._formula_btn.setObjectName("toolbarBtn")
        f_font = self._formula_btn.font()
        f_font.setPointSize(14)
        self._formula_btn.setFont(f_font)
        self._formula_btn.setToolTip("插入公式")
        self._formula_btn.clicked.connect(self._insert_formula)
        tb.addWidget(self._formula_btn)

        tb.addStretch()
        layout.addLayout(tb)

        self._content_edit = FormulaAwareTextEdit()
        self._content_edit.setObjectName("contentEdit")
        self._content_edit.setPlaceholderText(
            "在此输入您的提词稿件内容...\n\n"
            "• 支持 Ctrl+V 粘贴图片\n"
            "• 支持复制表格、公式截图等富文本内容\n"
            "• 使用上方工具栏设置字体样式"
        )
        self._content_edit.setAcceptRichText(True)
        self._content_edit.cursorPositionChanged.connect(self._sync_toolbar)
        self._content_edit.formula_paste_handler = self._handle_formula_paste_mime
        self._content_edit.post_paste_handler = self._apply_chinese_formatting
        layout.addWidget(self._content_edit, 1)

    def _on_font_family(self, family: str):
        if not family:
            return
        cursor = self._content_edit.textCursor()
        if cursor.hasSelection():
            fmt = QTextCharFormat()
            fmt.setFontFamilies([family])
            cursor.mergeCharFormat(fmt)
            self._content_edit.setTextCursor(cursor)
        else:
            default_fmt = self._content_edit.currentCharFormat()
            default_fmt.setFontFamilies([family])
            self._content_edit.setCurrentCharFormat(default_fmt)

    def _on_font_size(self, size_str: str):
        if not size_str:
            return
        size = int(size_str)
        cursor = self._content_edit.textCursor()
        if cursor.hasSelection():
            fmt = QTextCharFormat()
            fmt.setFontPointSize(size)
            cursor.mergeCharFormat(fmt)
            self._content_edit.setTextCursor(cursor)
        else:
            default_fmt = self._content_edit.currentCharFormat()
            default_fmt.setFontPointSize(size)
            self._content_edit.setCurrentCharFormat(default_fmt)

    def _toggle_bold(self):
        cursor = self._content_edit.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Bold if self._bold_btn.isChecked() else QFont.Weight.Normal
        )
        cursor.mergeCharFormat(fmt)
        self._content_edit.setTextCursor(cursor)
        self._content_edit.setFocus()

    def _toggle_italic(self):
        cursor = self._content_edit.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(self._italic_btn.isChecked())
        cursor.mergeCharFormat(fmt)
        self._content_edit.setTextCursor(cursor)
        self._content_edit.setFocus()

    def _toggle_underline(self):
        cursor = self._content_edit.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self._underline_btn.isChecked())
        cursor.mergeCharFormat(fmt)
        self._content_edit.setTextCursor(cursor)
        self._content_edit.setFocus()

    def _toggle_superscript(self):
        cursor = self._content_edit.textCursor()
        fmt = QTextCharFormat()
        if self._sup_btn.isChecked():
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
        else:
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignNormal)
        cursor.mergeCharFormat(fmt)
        self._content_edit.setTextCursor(cursor)
        if self._sup_btn.isChecked():
            self._sub_btn.setChecked(False)
        self._content_edit.setFocus()

    def _toggle_subscript(self):
        cursor = self._content_edit.textCursor()
        fmt = QTextCharFormat()
        if self._sub_btn.isChecked():
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSubScript)
        else:
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignNormal)
        cursor.mergeCharFormat(fmt)
        self._content_edit.setTextCursor(cursor)
        if self._sub_btn.isChecked():
            self._sup_btn.setChecked(False)
        self._content_edit.setFocus()

    def _pick_font_color(self):
        cursor = self._content_edit.textCursor()
        current = self._content_edit.currentCharFormat().foreground().color()
        color = QColorDialog.getColor(current, self, "选择字体颜色")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            if cursor.hasSelection():
                cursor.mergeCharFormat(fmt)
            else:
                self._content_edit.setCurrentCharFormat(fmt)
            self._color_btn.setStyleSheet(
                f"color: {color.name()}; border-bottom: 2px solid {color.name()};"
            )
        self._content_edit.setFocus()

    def _pick_bg_color(self):
        cursor = self._content_edit.textCursor()
        current = self._content_edit.currentCharFormat().background().color()
        color = QColorDialog.getColor(current, self, "选择底色")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            if cursor.hasSelection():
                cursor.mergeCharFormat(fmt)
            else:
                self._content_edit.setCurrentCharFormat(fmt)
            self._bg_color_btn.setStyleSheet(
                f"background-color: {color.name()}; color: #fff;"
            )
        self._content_edit.setFocus()

    def _clear_bg(self):
        cursor = self._content_edit.textCursor()
        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self._content_edit.setCurrentCharFormat(fmt)
        self._bg_color_btn.setStyleSheet("")
        self._content_edit.setFocus()

    def _set_foreground_black(self):
        cursor = self._content_edit.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(0, 0, 0))
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self._content_edit.setCurrentCharFormat(fmt)
        self._color_btn.setStyleSheet("")
        self._content_edit.setFocus()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if obj is self._color_btn:
                self._color_click_timer.start(300)
                return True
            if obj is self._bg_color_btn:
                self._bg_click_timer.start(300)
                return True
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            if obj is self._color_btn:
                self._color_click_timer.stop()
                self._set_foreground_black()
                return True
            if obj is self._bg_color_btn:
                self._bg_click_timer.stop()
                self._clear_bg()
                return True
        return super().eventFilter(obj, event)

    def _sync_toolbar(self):
        fmt = self._content_edit.currentCharFormat()
        self._bold_btn.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        self._italic_btn.setChecked(fmt.fontItalic())
        self._underline_btn.setChecked(fmt.fontUnderline())
        align = fmt.verticalAlignment()
        self._sup_btn.setChecked(align == QTextCharFormat.VerticalAlignment.AlignSuperScript)
        self._sub_btn.setChecked(align == QTextCharFormat.VerticalAlignment.AlignSubScript)
        families = fmt.fontFamilies()
        if families:
            family = families[0]
            idx = self._font_family.findText(family)
            if idx >= 0:
                self._font_family.blockSignals(True)
                self._font_family.setCurrentIndex(idx)
                self._font_family.blockSignals(False)
        pt = fmt.fontPointSize()
        if pt > 0:
            size_str = str(int(pt))
            idx = self._font_size.findText(size_str)
            if idx >= 0:
                self._font_size.blockSignals(True)
                self._font_size.setCurrentIndex(idx)
                self._font_size.blockSignals(False)
        fg = fmt.foreground().color()
        if fg.isValid() and fg != QColor(0, 0, 0):
            self._color_btn.setStyleSheet(
                f"color: {fg.name()}; border-bottom: 2px solid {fg.name()};"
            )
        else:
            self._color_btn.setStyleSheet("")
        bg = fmt.background().color()
        if bg.isValid():
            self._bg_color_btn.setStyleSheet(
                f"background-color: {bg.name()}; color: #fff;"
            )
        else:
            self._bg_color_btn.setStyleSheet("")

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
                    "您的内容包含图片或公式，需要进行转换以确保正确渲染。\n\n"
                    "• 选择「是」：转换并载入编辑器\n"
                    "• 选择「否」：取消导入",
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

    def _insert_formula(self):
        dialog = FormulaEditor(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            latex = dialog.get_result()
            if latex:
                formula_text = FormulaEditor.wrap_formula(latex)
                cursor = self._content_edit.textCursor()
                cursor.insertText(formula_text)
                self._content_edit.setFocus()

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
        body = self._convert_formula_images(body)
        body = compress_images_in_html(body)
        return body

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

        msg = "您的内容包含图片或公式，需要进行转换以确保正确渲染。"
        reply = QMessageBox.question(
            self, "转换提示",
            msg + "\n\n"
            "• 选择「是」：转换并粘贴到编辑器\n"
            "• 选择「否」：取消粘贴",
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
