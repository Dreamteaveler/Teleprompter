# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
import re


def clean_imported_html(html: str) -> str:
    html = _strip_unwanted_tags(html)
    html = _strip_all_inline_styles(html)
    html = _unwrap_empty_spans(html)
    html = _remove_empty_style_attrs(html)
    html = _clean_tag_spaces(html)
    return html


def _strip_unwanted_tags(html: str) -> str:
    html = re.sub(r'</?u>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'</?s>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'</?strike>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'</?del>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'</?ins>', '', html, flags=re.IGNORECASE)
    return html


def _strip_all_inline_styles(html: str) -> str:
    html = re.sub(
        r'style\s*=\s*"([^"]*)"',
        lambda m: _replace_style_attr(m.group(0)),
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"style\s*=\s*'([^']*)'",
        lambda m: _replace_style_attr_sq(m.group(0)),
        html,
        flags=re.IGNORECASE,
    )
    return html


def _replace_style_attr(style_attr: str) -> str:
    return _clean_style_value(style_attr, '"')


def _replace_style_attr_sq(style_attr: str) -> str:
    return _clean_style_value(style_attr, "'")


def _clean_style_value(style_attr: str, quote: str) -> str:
    inner = re.sub(rf'^style\s*=\s*{quote}', '', style_attr, flags=re.IGNORECASE)
    inner = re.sub(rf'{quote}$', '', inner)

    removals = [
        r'\bcolor\s*:\s*[^;"]*;?',
        r'\bbackground-color\s*:\s*[^;"]*;?',
        r'\bbackground\s*:\s*[^;"]*;?',
        r'\bfont-family\s*:\s*[^;"]*;?',
        r'\bfont-size\s*:\s*[^;"]*;?',
        r'\bfont-weight\s*:\s*[^;"]*;?',
        r'\bfont-style\s*:\s*[^;"]*;?',
        r'\btext-decoration\s*:\s*[^;"]*;?',
        r'\btext-shadow\s*:\s*[^;"]*;?',
        r'\bbox-shadow\s*:\s*[^;"]*;?',
        r'\bopacity\s*:\s*[^;"]*;?',
    ]
    for pat in removals:
        inner = re.sub(pat, '', inner)

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
    return html


def _clean_tag_spaces(html: str) -> str:
    html = re.sub(r'"\s+>', '">', html)
    html = re.sub(r"'\s+>", "'>", html)
    html = re.sub(r'<(\w+)\s+>', r'<\1>', html)
    return html
