# 提词器 (Teleprompter) v1.08

专业桌面提词软件，适用于视频录制、直播、演讲、教学场景。支持稿件编辑、Word导入、公式渲染、自动滚动播放、镜像输出。

## 功能特性

- 稿件管理：创建、搜索、导入 Word(.docx)、删除
- 富文本编辑：Markdown 语法、LaTeX 公式 ( $...$ / $$...$$ )，从 Word 直接粘贴公式自动转换
- 提词播放：自动滚动（WPM 速率可控）、手动键盘滚动（t²·⁵ 加速曲线）
- 镜像模式：第二屏幕输出，水平/垂直翻转，状态自动记忆
- 控制面板：浮动参数调节（字号 50-250px、行距、速度、边距、引导框）
- 视线引导框：可拖拽定位，F2 快捷键开关
- 快捷键全覆盖：空格播放、↑↓滚动、+/-调速、R重置、M镜像、F11全屏

## 安装运行

### 源码运行
```
pip install -r requirements.txt
python main.py
```

### 打包版本
下载 [Releases](https://github.com/Dreamteaveler/Teleprompter/releases) 中的 `提词器1.08.zip`，解压出来后双击运行（无需安装 Python）

## 技术栈
Python 3.12 · PyQt6 · PyQt6-WebEngine · MathJax 3 · SQLite · python-docx · Pillow · Markdown · lxml

## 快捷键

| 按键 | 功能 |
|------|------|
| 空格 | 播放/暂停 |
| ↑ ↓ | 手动滚动（长按加速） |
| + / - | 调速（步进 2 WPM） |
| R | 重置滚动位置 |
| M | 镜像模式开关 |
| F1 | 控制面板 |
| F2 | 引导框开关 |
| F11 | 全屏 |
| Esc | 退出全屏 |

## 许可证

本项目基于 [飞书妙搭平台飓风提词器](https://www.feishu.cn)（Apache-2.0 许可）的源代码重新实现，修改后按 **GPL-3.0-or-later** 分发。

任何人都可以自由使用、修改和分发，但必须以相同的 GPL-3.0 协议开源，不得用于闭源商业产品。

## 致谢

感谢 [影视飓风](https://www.ysfxmedia.com) 团队的开源贡献。
