# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
import re
import base64
from io import BytesIO

from PIL import Image


def compress_images_in_html(html: str, max_width: int = 800, quality: int = 60) -> str:
    def _compress_src(m):
        b64data = m.group(1)
        try:
            data = base64.b64decode(b64data)
            img = Image.open(BytesIO(data))
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            w, h = img.size
            if w > max_width:
                new_h = int(h * max_width / w)
                img = img.resize((max_width, new_h), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=quality)
            new_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return f'src="data:image/jpeg;base64,{new_b64}"'
        except Exception:
            return m.group(0)

    return re.sub(
        r'src="data:image/[^;]+;base64,([^"]+)"',
        _compress_src,
        html,
    )
