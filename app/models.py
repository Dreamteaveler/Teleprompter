# @license
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件进行了修改。
# 本项目基于影视飓风提词器（Apache-2.0 许可）的源代码重新实现。
#
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Manuscript:
    id: int = 0
    title: str = ""
    content: str = ""
    cover_image: str = ""
    status: str = "draft"
    created_at: str = ""
    updated_at: str = ""

    def formatted_date(self) -> str:
        try:
            dt = datetime.fromisoformat(self.updated_at)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return ""

    def plain_text_preview(self, max_len: int = 150) -> str:
        text = self.content
        if "<" in text and ">" in text:
            import re
            text = re.sub(r"<[^>]+>", "", text)
            text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.strip()
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text if text else "(空内容)"

    def estimated_read_time(self) -> str:
        char_count = len(self.content)
        if char_count == 0:
            return "0 秒"
        minutes = char_count // 300
        seconds = (char_count % 300) // 5
        if minutes == 0:
            return f"{seconds} 秒"
        if seconds == 0:
            return f"{minutes} 分"
        return f"{minutes} 分 {seconds} 秒"
