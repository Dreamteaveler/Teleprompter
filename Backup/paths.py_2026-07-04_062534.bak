# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
"""公共路径解析工具，统一处理 frozen/dev 环境差异。"""
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QUrl


def get_app_root() -> str:
    """返回应用根目录（frozen 时为 _MEIPASS，开发时为项目根）。"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_path(relative_path: str) -> str:
    """解析相对于应用根目录的路径。"""
    return os.path.join(get_app_root(), relative_path)


def mathjax_url() -> str:
    """返回本地 MathJax tex-chtml.js 的 file:// URI。"""
    js_path = os.path.join(get_app_root(), "app", "mathjax", "tex-chtml.js")
    return Path(js_path).as_uri()


def mathjax_base_url() -> QUrl:
    """返回 MathJax 目录的 QUrl（用于 setHtml baseUrl）。"""
    mathjax_dir = os.path.join(get_app_root(), "app", "mathjax")
    return QUrl.fromLocalFile(mathjax_dir)


def template_path(name: str) -> str:
    """返回 app/templates/ 下模板文件的绝对路径。"""
    return os.path.join(get_app_root(), "app", "templates", name)


def load_template(name: str) -> str:
    """加载 app/templates/ 下的模板文件内容。"""
    path = template_path(name)
    with open(path, encoding="utf-8") as f:
        return f.read()
