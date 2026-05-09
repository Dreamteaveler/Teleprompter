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
            if has_formulas:
                reply = QMessageBox.question(
                    self, "检测到公式",
                    "该文档含有公式，是否将其转换为 LaTeX 格式以正确渲染？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    html_content, _ = import_docx_file(filepath, formula_mode="latex")
            if html_content:
                html_content = self._strip_images(html_content)
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
                content = self._strip_images(content)
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
        body = re.sub(r'<img[^>]*/?>', '', body, flags=re.DOTALL)
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

        body_only = html_content
        body_only = re.sub(r'<style[^>]*>.*?</style>', '', body_only, flags=re.DOTALL | re.IGNORECASE)
        body_only = re.sub(r'<script[^>]*>.*?</script>', '', body_only, flags=re.DOTALL | re.IGNORECASE)
        body_only = re.sub(r'<head[^>]*>.*?</head>', '', body_only, flags=re.DOTALL | re.IGNORECASE)
        body_only = re.sub(r'<meta[^>]*>', '', body_only, flags=re.IGNORECASE)
        body_only = re.sub(r'<link[^>]*>', '', body_only, flags=re.IGNORECASE)
        body_only = re.sub(r'<xml[^>]*>.*?</xml>', '', body_only, flags=re.DOTALL | re.IGNORECASE)
        body_only = re.sub(r'<!--\[if\s+gte\s+mso\s+9\].*?<!\[endif\]-->', '', body_only, flags=re.DOTALL | re.IGNORECASE)

        tex_in_text = bool(re.search(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', plain_text))
        tex_in_text = tex_in_text or bool(re.search(r'\$\$[\s\S]*?\$\$', plain_text))
        tex_in_html = bool(re.search(r'\$\$[\s\S]*?\$\$', body_only))
        tex_in_html = tex_in_html or bool(re.search(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', body_only))
        mjx_in_html = bool(re.search(r'<mjx-container', body_only, re.IGNORECASE))
        omml_in_html = bool(re.search(r'<m:oMath[>\s]|<m:oMathPara[>\s]', body_only, re.IGNORECASE))

        unicode_count = 0
        _UMAP = {
            'Α': 1, 'Β': 1, 'Γ': 1, 'Δ': 1, 'Ε': 1, 'Ζ': 1, 'Η': 1, 'Θ': 1,
            'Ι': 1, 'Κ': 1, 'Λ': 1, 'Μ': 1, 'Ν': 1, 'Ξ': 1, 'Ο': 1, 'Π': 1,
            'Ρ': 1, 'Σ': 1, 'Τ': 1, 'Υ': 1, 'Φ': 1, 'Χ': 1, 'Ψ': 1, 'Ω': 1,
            'α': 1, 'β': 1, 'γ': 1, 'δ': 1, 'ε': 1, 'ζ': 1, 'η': 1, 'θ': 1,
            'ι': 1, 'κ': 1, 'λ': 1, 'μ': 1, 'ν': 1, 'ξ': 1, 'π': 1, 'ρ': 1,
            'σ': 1, 'τ': 1, 'υ': 1, 'φ': 1, 'χ': 1, 'ψ': 1, 'ω': 1,
            '→': 1, '←': 1, '⇒': 1, '⇐': 1, '⇌': 1, '·': 1, '×': 1, '÷': 1,
            '±': 1, '∫': 1, '∞': 1, '∂': 1, '∇': 1, '≤': 1, '≥': 1, '≠': 1,
            '≈': 1, '≡': 1, '∈': 1, '⊂': 1, '∪': 1, '∩': 1, '∀': 1, '∃': 1,
            '⊕': 1, '⊗': 1, '∑': 1, '∏': 1,
            '²': 1, '³': 1, '₁': 1, '₂': 1, '₃': 1, '°': 1,
        }
        for ch in plain_text:
            if ch in _UMAP:
                unicode_count += 1
                if unicode_count >= 3:
                    break
        unicode_math_in_text = unicode_count >= 3

        has_formula = tex_in_text or tex_in_html or mjx_in_html or omml_in_html or unicode_math_in_text
        if not has_formula:
            return False

        reply = QMessageBox.question(
            self, "检测到公式",
            "检测到文本中包含公式。请使用 Word 导入功能以确保公式正确渲染。\n\n"
            "• 选择「是」：自动打开 Word 导入界面\n"
            "• 选择「否」：跳过，以纯文本形式粘贴",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            QTimer.singleShot(100, self._import_word)
        return True

    def _on_cancel(self):
        self.cancelled.emit()

    def _apply_chinese_formatting(self):
        doc = self._content_edit.document()
        text = doc.toPlainText()
        if not text:
            return

        ranges = []
        start = None
        for i, ch in enumerate(text):
            if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf' or '\uf900' <= ch <= '\ufaff':
                if start is None:
                    start = i
            else:
                if start is not None:
                    ranges.append((start, i))
                    start = None
        if start is not None:
            ranges.append((start, len(text)))

        if not ranges:
            return

        saved_cursor = self._content_edit.textCursor()
        saved_pos = saved_cursor.position()

        cursor = QTextCursor(doc)
        fmt = QTextCharFormat()
        fmt.setFontFamilies(["黑体"])
        fmt.setFontWeight(QFont.Weight.Bold)

        for start_pos, end_pos in ranges:
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(fmt)

        saved_cursor.setPosition(saved_pos)
        self._content_edit.setTextCursor(saved_cursor)
