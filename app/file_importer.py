# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
import os
import re
import logging
from pathlib import Path

from app.docx_importer import import_docx_file
from app.html_cleaner import clean_imported_html

logger = logging.getLogger("teleprompter.file_importer")

SUPPORTED_EXTENSIONS = (".docx", ".txt", ".md", ".markdown")


def import_file(filepath: str, auto_confirm_formulas: bool = False) -> tuple[str, str, bool]:
    ext = Path(filepath).suffix.lower()
    logger.info(f"[import_file] 开始导入: {filepath}, 格式={ext}, auto_confirm={auto_confirm_formulas}")
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}")
    if ext == ".docx":
        title, html, needs = _import_docx(filepath, auto_confirm_formulas)
    elif ext in (".txt", ".md", ".markdown"):
        title, html, needs = _import_text(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")
    logger.info(f"[import_file] 导入完成: title={title}, html长度={len(html)}, needs_confirm={needs}")
    return title, html, needs


def _import_docx(filepath: str, auto_confirm_formulas: bool) -> tuple[str, str, bool]:
    html_content, has_formulas = import_docx_file(filepath)
    if not html_content:
        raise ValueError("无法读取文档内容。")

    has_images = bool(re.search(r'<img[^>]*>', html_content, re.IGNORECASE))
    needs_confirm = has_formulas or has_images

    if needs_confirm and auto_confirm_formulas and has_formulas:
        html_content, _ = import_docx_file(filepath, formula_mode="latex")

    logger.info(f"[_import_docx] 调用 clean_imported_html, html长度={len(html_content)}")
    html_content = clean_imported_html(html_content)
    logger.info(f"[_import_docx] 清洗后 html长度={len(html_content)}")
    title = _file_title(filepath, ".docx")
    return title, html_content, needs_confirm


def _import_text(filepath: str) -> tuple[str, str, bool]:
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    ext = Path(filepath).suffix.lower()
    if ext in (".md", ".markdown"):
        try:
            import markdown
            md = markdown.Markdown(extensions=["extra", "nl2br"])
            html_body = md.convert(raw)
        except ImportError:
            html_body = _plain_to_html(raw)
    else:
        html_body = _plain_to_html(raw)

    html_body = clean_imported_html(html_body)
    title = _file_title(filepath, ext)
    return title, html_body, False


def _file_title(filepath: str, ext: str) -> str:
    basename = os.path.basename(filepath)
    if basename.lower().endswith(ext.lower()):
        basename = basename[:-len(ext)]
    return basename


def _plain_to_html(text: str) -> str:
    lines = text.strip().splitlines()
    paragraphs = [f"<p>{_escape_html(line)}</p>" for line in lines if line.strip()]
    return "\n".join(paragraphs) if paragraphs else f"<p>{_escape_html(text.strip())}</p>"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
