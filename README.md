# 提词器 (Teleprompter) v1.12

专业桌面提词软件，适用于视频录制、直播、演讲、教学场景。支持稿件编辑、Word导入、公式渲染、自动滚动播放、镜像输出。

## 功能特性

- 稿件管理：创建、搜索、导入 Word(.docx)、删除
- 富文本编辑：Markdown 语法、LaTeX 公式，编辑区字号独立调节
- 提词播放：自动滚动（WPM 可控）、键盘变速滚动（t^2.5 加速曲线）、预估剩余时间
- 镜像模式：第二屏幕输出，多分辨率像素级同步（setZoomFactor），自动弹到副屏
- 控制面板：浮动紧凑面板，参数调节（字号/行距/速度/边距/引导框透明度/主镜像全屏）
- 视线引导框：可拖拽定位，透明度 0-100%，F2 快捷键开关
- 提词中编辑：控制面板"编辑"按钮直接修改稿件，保持全屏/镜像，保存后恢复进度
- 快捷键全覆盖：空格播放、↑↓滚动、+/-调速、R重置、M镜像、F11全屏
- 焦点无感：鼠标在控制面板上快捷键仍生效，滚轮转发主屏
- 退出确认：关闭前弹出确认对话框，防止误退

## 安装运行

### 源码运行
```
pip install -r requirements.txt
python main.py
```

### 打包版本
- **单文件版**：下载 `Teleprompter-v1.12-Single.zip`，解压后双击 exe 运行
- **便携版**：下载 `Teleprompter-v1.12-Portable.zip`，解压后运行文件夹内 `提词器.exe`

均无需安装 Python 环境。下载地址：[Releases](https://github.com/Dreamteaveler/Teleprompter/releases)

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
