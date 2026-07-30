# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
import re


def clean_imported_html(html: str) -> str:
    html = _strip_underline_tags(html)
    html = _strip_color_from_all_styles(html)
    html = _unwrap_empty_spans(html)
    html = _remove_empty_style_attrs(html)
    return html


def _strip_underline_tags(html: str) -> str:
    return re.sub(r'</?u>', '', html, flags=re.IGNORECASE)


def _strip_color_from_all_styles(html: str) -> str:
    return re.sub(
        r'style\s*=\s*"([^"]*)"',
        lambda m: _replace_style_attr(m.group(0)),
        html,
        flags=re.IGNORECASE,
    )


def _replace_style_attr(style_attr: str) -> str:
    inner = re.sub(r'^style\s*=\s*"', '', style_attr, flags=re.IGNORECASE)
    inner = re.sub(r'"$', '', inner)

    inner = re.sub(r'\bcolor\s*:\s*[^;"]*;?', '', inner)
    inner = re.sub(r'\bbackground-color\s*:\s*[^;"]*;?', '', inner)
    inner = re.sub(r'\bbackground\s*:\s*[^;"]*;?', '', inner)
    inner = re.sub(r'\bfont-family\s*:\s*[^;"]*;?', '', inner)
    inner = re.sub(r'\bfont-size\s*:\s*[^;"]*;?', '', inner)
    inner = re.sub(r'\bfont-weight\s*:\s*[^;"]*;?', '', inner)
    inner = re.sub(r'\bfont-style\s*:\s*[^;"]*;?', '', inner)

    inner = re.sub(r';\s*;+', ';', inner)
    inner = re.sub(r'^\s*;+\s*', '', inner)
    inner = inner.strip()
    inner = re.sub(r'\s+', ' ', inner)

    if inner:
        return f'style="{inner}"'
    return ''


def _unwrap_empty_spans(html: str) -> str:
    html = re.sub(
        r'<span(?!\s+class\s*=\s*"formula")[^>]*>(.*?)</span>',
        r'\1',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return html


def _remove_empty_style_attrs(html: str) -> str:
    html = re.sub(r'''\s*style\s*=\s*"\s*"''', '', html, flags=re.IGNORECASE)
    html = re.sub(r"\s*style\s*=\s*'\s*'", '', html, flags=re.IGNORECASE)
    html = re.sub(r'"\s+>', '">', html)
    html = re.sub(r'<([a-zA-Z][a-zA-Z0-9]*)\s+>', r'<\1>', html)
    return html
