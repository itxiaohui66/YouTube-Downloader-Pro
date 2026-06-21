# YouTube Downloader Pro

一个基于 PySide6 + yt-dlp 的跨平台桌面 YouTube 视频下载工具，支持视频、播放列表、字幕和封面下载，内置 FFmpeg 音视频合并。

<p align="center">
  <b>🎬 视频下载 · 📋 播放列表 · 💬 字幕 · 🖼️ 封面 · 🔗 自动合并</b>
</p>

---

## ✨ 功能特性

- **单视频下载** — 支持多种分辨率/格式选择，从 144p 到 8K
- **播放列表批量下载** — 自动解析播放列表，支持选择性下载
- **字幕下载** — 支持手动/自动字幕，多种语言，可导出 SRT/VTT 格式
- **封面下载** — 自动下载视频封面，多级清晰度回退（maxresdefault → default）
- **音视频合并** — 自动调用 FFmpeg 将分离视频/音频流合并为高质量 MP4
- **Cookie 认证** — 支持导入浏览器 cookies.txt 或自动读取浏览器 cookie
- **多线程下载** — 可配置 1-32 个并行下载，线程池管理
- **主题切换** — 内置暗色/亮色主题，支持跟随系统
- **暂停/取消** — 单个任务支持暂停恢复和取消操作
- **反检测** — 50 个真实浏览器 User-Agent 轮换，模拟浏览器请求头
- **格式智能分类** — 自动区分合并流、纯视频、纯音频，UI 清晰展示

## 📋 系统要求

- **操作系统**: Windows / macOS / Linux
- **Python**: 3.9+
- **外部工具**: [FFmpeg](https://ffmpeg.org/download.html)（可选，用于音视频合并）

## 🚀 快速开始

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 FFmpeg（推荐）

- **Windows**: 下载 [gyan.dev FFmpeg](https://www.gyan.dev/ffmpeg/builds/) essentials 版本，将 `ffmpeg.exe` 加入 PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg` (Debian/Ubuntu) 或 `sudo dnf install ffmpeg` (Fedora)

也可以启动应用后通过 **帮助 → 检查 FFmpeg 状态** 自动下载安装。

### 3. 运行应用

```bash
python main.py
```

### 4. （可选）配置 Cookie

如果遇到 YouTube 反爬验证，可配置 Cookie 绕过：

1. 安装浏览器扩展 [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. 导出 `cookies.txt` 并在应用设置中指定路径

## 📦 打包为 EXE

```bash
# 使用 spec 文件打包
pyinstaller "YouTube Downloader Pro.spec"

# 或使用命令行
pyinstaller --onefile --windowed --name "YouTube Downloader Pro" main.py
```

输出文件位于 `dist/YouTube Downloader Pro.exe`。

## 📁 项目结构

```
youtube_downloader/
├── main.py                          # 应用入口，初始化日志/配置/窗口
├── requirements.txt                 # Python 依赖清单
├── YouTube Downloader Pro.spec      # PyInstaller 打包配置
├── __init__.py
│
├── ui/                              # 用户界面层
│   ├── main_window.py               # 主窗口（~1860 行），QStackedWidget 三页面
│   ├── settings_window.py           # 设置对话框（通用/格式/高级/外观）
│   ├── about_window.py              # 关于窗口
│   ├── theme.py                     # 暗色/亮色 QSS 主题
│   └── widgets/                     # 可复用组件（预留）
│
├── downloader/                      # 下载引擎层
│   ├── video_downloader.py          # yt-dlp 封装，独立实例保证线程安全
│   ├── download_queue.py            # ThreadPoolExecutor 队列管理器
│   ├── format_parser.py             # 视频信息/格式/字幕提取
│   ├── playlist_downloader.py       # 播放列表解析
│   ├── subtitle_downloader.py       # 字幕下载（yt-dlp / HTTP 直连）
│   ├── thumbnail_downloader.py      # 封面下载（多级清晰度回退）
│   ├── ffmpeg_merger.py             # FFmpeg 子进程合并音视频
│   └── ffmpeg_installer.py          # FFmpeg 自动下载安装
│
├── models/                          # 数据模型层
│   ├── task.py                      # DownloadTask, VideoInfo, VideoFormat 等
│   └── settings.py                  # Settings 数据类，ThemeMode 枚举
│
├── config/                          # 配置管理层
│   └── settings_manager.py          # 单例 SettingsManager，原子写入
│
└── utils/                           # 工具层
    ├── logger.py                    # RotatingFileHandler 日志系统
    ├── validators.py                # YouTube URL 正则验证
    └── user_agents.py               # 50 个真实 UA 轮换池
```

## 🧵 线程模型

| 线程类型 | 实现方式 | 说明 |
|---------|---------|------|
| 主线程 | Qt 事件循环 | 所有 UI 更新 |
| 下载线程 | `ThreadPoolExecutor` | 1-32 个工作线程，每个任务独立 `VideoDownloader` 实例 |
| 信息获取 | `QThread` 子类 | 格式解析、播放列表获取 |
| 队列监控 | `threading.Thread` 守护线程 | 每秒轮询检测全部完成 |
| UI 刷新 | `QTimer` 500ms | 主线程定时器轮询进度 |

## ⚙️ 配置说明

配置文件存储在 `~/.youtube_downloader_pro/settings.json`，支持以下设置：

- **下载目录** — 自定义保存路径
- **并行下载数** — 1-32 个并发任务
- **主题模式** — 暗色 / 亮色 / 跟随系统
- **Cookie 配置** — cookies.txt 路径或浏览器自动提取
- **FFmpeg 路径** — 自定义 FFmpeg 可执行文件路径
- **字幕语言** — 默认下载语言
- **自动合并** — 启用/禁用 FFmpeg 音视频合并

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 ≥ 6.5.0 |
| 下载引擎 | yt-dlp ≥ 2024.1.1 |
| HTTP 请求 | requests ≥ 2.28.0 |
| 音视频处理 | FFmpeg |
| 打包工具 | PyInstaller |
| 主题检测 | darkdetect（可选） |

## 📝 开发笔记

- 无单元测试框架（待添加）
- UI 文本为中文（zh_CN）
- 配置采用原子写入（先写 `.tmp` 再重命名），防止写入中断导致配置损坏
- 日志轮转：单文件 5 MB，保留 3 个备份
- 每个下载任务创建独立 `VideoDownloader` 实例，避免多线程状态交叉
- `_active_downloaders` 字典受 `threading.Lock` 保护

## 📄 许可证

本项目仅供个人学习和研究使用。请遵守 YouTube 服务条款，尊重版权。

## 🔗 开发者

- 网站：[https://www.itxiaohui.top/](https://www.itxiaohui.top/)

## 🤝 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 强大的 YouTube 下载核心库
- [FFmpeg](https://ffmpeg.org/) — 音视频处理利器
- [PySide6](https://wiki.qt.io/Qt_for_Python) — Qt for Python 官方绑定
