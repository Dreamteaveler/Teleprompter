# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QToolButton,
)
from PyQt6.QtCore import Qt, QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QTextDocument, QImage, QPainter, QFont, QPixmap


class FormulaEditor(QDialog):
    def __init__(self, parent=None, latex=""):
        super().__init__(parent)
        self.setWindowTitle("公式编辑器")
        self.setModal(True)
        self.setMinimumSize(520, 320)
        self._result_png_base64 = None
        self._result_latex = None
        self._init_ui()
        if latex:
            self._input.setText(latex)
            self._update_preview()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        sym_layout = QHBoxLayout()
        sym_layout.setSpacing(2)
        symbols = [
            ("π", "\\pi "), ("∞", "\\infty "), ("∑", "\\sum "),
            ("∏", "\\prod "), ("∫", "\\int "), ("√", "\\sqrt{}"),
            ("±", "\\pm "), ("→", "\\rightarrow "), ("α", "\\alpha "),
            ("β", "\\beta "), ("γ", "\\gamma "), ("θ", "\\theta "),
            ("²", "^2"), ("³", "^3"), ("/", "\\frac{}{}"),
        ]
        for label, snippet in symbols:
            btn = QToolButton()
            btn.setText(label)
            btn.setFixedSize(34, 28)
            btn.setObjectName("toolbarBtn")
            btn.clicked.connect(lambda checked, s=snippet: self._insert(s))
            sym_layout.addWidget(btn)
        sym_layout.addStretch()
        layout.addLayout(sym_layout)

        self._input = QLineEdit()
        self._input.setPlaceholderText(
            "输入公式，如: E = mc^2  或  \\frac{a}{b}"
        )
        self._input.textChanged.connect(self._update_preview)
        layout.addWidget(self._input)

        self._preview = QLabel("预览区域")
        self._preview.setMinimumHeight(100)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            "background-color: #111; border: 1px solid #333; border-radius: 6px;"
        )
        layout.addWidget(self._preview, 1)

        btn_lay = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_lay.addStretch()
        btn_lay.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("accentButton")
        ok_btn.clicked.connect(self._on_ok)
        btn_lay.addWidget(ok_btn)
        layout.addLayout(btn_lay)

    def _insert(self, snippet):
        cursor = self._input.cursorPosition()
        text = self._input.text()
        new_text = text[:cursor] + snippet + text[cursor:]
        self._input.setText(new_text)
        self._input.setCursorPosition(cursor + len(snippet))
        self._input.setFocus()

    @staticmethod
    def latex_to_html(latex: str) -> str:
        html = (
            latex.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        greek = {
            "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
            "theta": "θ", "lambda": "λ", "mu": "μ", "sigma": "σ",
            "omega": "ω", "phi": "φ", "pi": "π", "rho": "ρ",
            "epsilon": "ε", "tau": "τ",
        }
        for name, char in greek.items():
            html = html.replace(f"\\{name} ", char)
            html = html.replace(f"\\{name}", char)
        symbols = {
            "\\sum": "∑", "\\prod": "∏", "\\int": "∫", "\\infty": "∞",
            "\\rightarrow": "→", "\\leftarrow": "←", "\\pm": "±",
            "\\times": "×", "\\div": "÷", "\\approx": "≈",
            "\\neq": "≠", "\\leq": "≤", "\\geq": "≥",
            "\\cdot": "·", "\\cdots": "⋯", "\\vdots": "⋮",
        }
        for cmd, char in symbols.items():
            html = html.replace(cmd, char)
        html = re.sub(
            r'\\frac\s*\{([^}]*)\}\s*\{([^}]*)\}',
            r'<sup>\1</sup>⁄<sub>\2</sub>',
            html,
        )
        html = re.sub(r'\\sqrt\s*\{([^}]*)\}', r'√(\1)', html)
        html = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', html)
        html = re.sub(r'_([a-zA-Z0-9])', r'<sub>\1</sub>', html)
        html = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', html)
        html = re.sub(r'\^([a-zA-Z0-9])', r'<sup>\1</sup>', html)
        return html

    @staticmethod
    def render_to_png(latex: str, font_size: int = 28):
        html_math = FormulaEditor.latex_to_html(latex)
        doc = QTextDocument()
        doc.setDefaultFont(QFont("sans-serif", font_size))
        doc.setHtml(
            '<html><body style="color:#ffffff;font-size:%dpx;background:transparent;">%s</body></html>'
            % (font_size, html_math)
        )
        doc.setDocumentMargin(3)
        size = doc.size().toSize()
        if size.width() < 2 or size.height() < 2:
            return None
        img = QImage(
            size.width() + 4, size.height() + 4,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        doc.drawContents(painter)
        painter.end()
        buf_arr = QByteArray()
        buf = QBuffer(buf_arr)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        return buf_arr.toBase64().data().decode()

    def _update_preview(self):
        latex = self._input.text().strip()
        if not latex:
            self._preview.setText("预览区域")
            self._preview.setPixmap(QPixmap())
            return
        b64 = FormulaEditor.render_to_png(latex, 28)
        if b64:
            pix = QPixmap()
            pix.loadFromData(QByteArray.fromBase64(b64.encode()))
            self._preview.setPixmap(pix)
        else:
            self._preview.setText("预览区域")

    def _on_ok(self):
        latex = self._input.text().strip()
        if not latex:
            self.reject()
            return
        self._result_latex = latex
        self.accept()

    def get_result(self):
        return self._result_latex

    @staticmethod
    def wrap_formula(latex: str) -> str:
        return f" ${latex}$ "

    @staticmethod
    def make_img_html(png_base64: str, latex: str, height: int = 48) -> str:
        escaped = latex.replace("&", "&amp;").replace('"', "&quot;")
        return (
            f'<img src="data:image/png;base64,{png_base64}" '
            f'class="formula" data-latex="{escaped}" '
            f'height="{height}" alt="{escaped}">'
        )
