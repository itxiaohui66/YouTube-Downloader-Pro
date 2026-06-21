# YouTube Downloader Pro

一个基于 Python、yt-dlp 和 FFmpeg 开发的现代化 YouTube 视频下载工具。

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## ✨ 功能特性

### 核心功能

- 🎬 **单视频下载** — 支持多种清晰度选择，从 144P 到 8K
- 📋 **播放列表下载** — 批量解析播放列表，支持选择性下载
- 🔗 **高清视频自动合并** — 自动下载音视频流并使用 FFmpeg 合并
- 📝 **字幕下载** — 支持自动字幕和官方字幕（SRT/VTT 格式）
- 🖼 **封面下载** — 高质量封面图保存（JPG/PNG）
- ⚡ **多线程下载** — 可配置 1-32 线程并发，充分利用带宽
- 📊 **下载队列管理** — 支持暂停、恢复、取消和失败重试
- 🎨 **深色/浅色主题** — 支持跟随系统主题自动切换

### 特色亮点

- 现代化 PySide6 界面，操作流畅
- 实时下载进度显示（速度、进度条、剩余时间）
- 批量下载设置自由组合（视频/音频/字幕/封面）
- 完整日志系统，方便问题排查
- 自动检测 FFmpeg，无需手动配置

---

## 📸 界面截图

> 截图位置预留 — 请在应用运行后截图替换

```
┌──────────────────────────────────────────────────────┐
│  🔗 [YouTube URL 输入框..................] [获取信息] [下载] │
├──────────────────────────────────────────────────────┤
│  ┌─────────┐                                          │
│  │ 封面图   │  视频标题                                │
│  │         │  👤 作者  ⏱ 时长  📅 上传日期            │
│  └─────────┘                                          │
├──────────────────────────────────────────────────────┤
│  格式选择                                              │
│  🎬 视频格式: [1080p | MP4 | AVC1 | 60FPS | 1.2GB ▾]  │
│  🎵 音频格式: [MP3 192kbps ▾]                         │
├──────────────────────────────────────────────────────┤
│  ☑ 下载字幕 [中文 ▾]  ☐ 下载封面  ☑ 自动合并音视频    │
├──────────────────────────────────────────────────────┤
│  下载队列                                    [暂停] [恢复]│
│  任务 │ 状态 │ 速度 │ 已下载/总大小 │ 进度 │ 操作     │
│  ...  │ 下载中│ 5MB/s│ 45M/300M   │ [=== ]│ [取消]  │
└──────────────────────────────────────────────────────┘
```

---

## 🔧 安装教程

### 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.12 或更高版本 |
| pip | 最新版本 |
| FFmpeg | 用于高清视频音视频合并（可选但推荐） |

### 步骤 1: 克隆项目

```bash
git clone https://github.com/xiaohui/youtube-downloader-pro.git
cd youtube-downloader-pro
```

### 步骤 2: 创建虚拟环境（推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 步骤 3: 安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 4: 运行应用

```bash
python main.py
```

---

## 🎬 FFmpeg 配置教程

高清视频（1080P 及以上）通常音频和视频流分离，需要 FFmpeg 合并。

### Windows 安装

1. 访问 [FFmpeg 官网](https://ffmpeg.org/download.html)
2. 下载 Windows 版本（推荐 gyan.dev 或 BtbN 构建版）
3. 解压到 `C:\ffmpeg\`
4. 将 `C:\ffmpeg\bin\` 添加到系统环境变量 PATH
5. 或直接在应用设置中手动指定 `ffmpeg.exe` 路径

### macOS 安装

```bash
brew install ffmpeg
```

### Linux 安装

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch
sudo pacman -S ffmpeg
```

### 验证安装

```bash
ffmpeg -version
```

应用会自动检测 FFmpeg，也可在 **设置 → 高级 → FFmpeg 路径** 中手动指定。

---

## 📖 使用方法

### 下载单个视频

1. 复制 YouTube 视频链接
2. 粘贴到应用顶部输入框
3. 点击 **获取信息** 查看视频详情
4. 选择需要的清晰度和格式
5. 可选勾选字幕、封面下载
6. 点击 **下载**

### 下载播放列表

1. 复制播放列表链接（如 `https://www.youtube.com/playlist?list=xxx`）
2. 粘贴并点击 **获取信息**
3. 在列表中勾选需要下载的视频（支持全选/取消全选）
4. 点击 **下载选中**

### 批量下载设置

在下载选项区域可自由组合：
- ✅ 下载视频 + ✅ 下载字幕 + ✅ 下载封面
- ✅ 仅下载音频（选择音频格式）
- 任意组合

### 下载队列管理

- **暂停/恢复**: 控制下载进程
- **取消**: 取消单个或全部任务
- **重试失败**: 一键重试所有失败任务
- **清空已完成**: 清理已完成的任务记录

---

## 📁 项目结构

```
youtube_downloader/
├── main.py                      # 应用入口
├── __init__.py                  # 包初始化
│
├── ui/                          # UI 层
│   ├── __init__.py
│   ├── main_window.py           # 主窗口
│   ├── settings_window.py       # 设置窗口
│   ├── about_window.py          # 关于窗口
│   └── widgets/                 # 可复用组件
│       └── __init__.py
│
├── downloader/                  # 下载器核心
│   ├── __init__.py
│   ├── video_downloader.py      # 视频下载逻辑
│   ├── playlist_downloader.py   # 播放列表解析
│   ├── subtitle_downloader.py   # 字幕下载
│   ├── thumbnail_downloader.py  # 封面下载
│   ├── ffmpeg_merger.py         # FFmpeg 合并
│   ├── format_parser.py         # 格式解析
│   └── download_queue.py        # 下载队列管理
│
├── models/                      # 数据模型
│   ├── __init__.py
│   ├── task.py                  # 下载任务模型
│   └── settings.py              # 设置模型
│
├── config/                      # 配置管理
│   ├── __init__.py
│   └── settings_manager.py      # 设置持久化
│
├── utils/                       # 工具模块
│   ├── __init__.py
│   ├── logger.py                # 日志系统
│   └── validators.py            # URL 验证
│
├── resources/                   # 资源文件
│   ├── icons/
│   └── images/
│
├── requirements.txt             # 依赖清单
└── README.md                    # 项目文档
```

---

## 📦 打包为 EXE

### 使用 PyInstaller 打包为单文件 EXE

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包
pyinstaller --onefile --windowed --name "YouTube Downloader Pro" main.py
```

或使用提供的 spec 文件：

```bash
pyinstaller "YouTube Downloader Pro.spec"
```

打包后的 EXE 文件位于 `dist/` 目录，用户无需安装 Python 即可运行。

---

## ❓ 常见问题

### Q: 下载失败：`ERROR: Unable to download webpage`

**A:** 这通常是网络问题：
- 检查网络连接是否正常
- 尝试使用代理（设置 → 高级 → 代理服务器）
- yt-dlp 会自动处理大部分 YouTube 变更，保持版本更新

### Q: 高清视频没有声音

**A:** 需要 FFmpeg 合并音视频流：
- 确认 FFmpeg 已安装（状态栏可查看）
- 勾选"自动合并音视频"选项
- yt-dlp 会自动下载音视频流并调用 FFmpeg 合并

### Q: 字幕下载失败

**A:** 
- 检查视频是否有对应语言的字幕
- 尝试切换自动字幕/官方字幕
- 部分视频可能没有特定语言的字幕

### Q: 如何更新 yt-dlp？

```bash
pip install --upgrade yt-dlp
```

### Q: 下载速度慢

**A:**
- 在设置中增加下载线程数
- 检查是否启用了下载限速
- 使用代理服务器可能改善连接

---

## 👨‍💻 开发者

- **开发者:** xiaohui
- **网站:** [https://www.itxiaohui.top](https://www.itxiaohui.top)
- **GitHub:** [https://github.com/xiaohui/youtube-downloader-pro](https://github.com/xiaohui/youtube-downloader-pro)

---

## 📄 许可证

MIT License — 详见 LICENSE 文件

---

## ⚠️ 免责声明

本工具仅供个人学习和研究使用。请遵守 YouTube 服务条款和当地法律法规。下载受版权保护的内容需获得权利人授权。
#   Y o u T u b e - D o w n l o a d e r - P r o  
 