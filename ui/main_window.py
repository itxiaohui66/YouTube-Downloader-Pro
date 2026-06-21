"""主窗口

应用的主界面，包含 URL 输入、视频信息展示、格式选择、
下载选项、进度列表、播放列表管理等所有核心 UI 交互。
"""

import logging
import os
import re
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QFrame,
    QStackedWidget, QScrollArea, QGroupBox, QFormLayout,
    QStatusBar, QMenuBar, QMenu, QMessageBox, QSplitter,
    QAbstractItemView, QStyle, QApplication, QSizePolicy,
    QGridLayout,
)
from PySide6.QtCore import (
    Qt, Signal, Slot, QThread, QUrl, QTimer, QSize,
)
from PySide6.QtGui import (
    QAction, QFont, QIcon, QPixmap, QDesktopServices,
    QPalette, QColor,
)

from ..models.task import (
    DownloadTask, VideoInfo, VideoFormat, DownloadProgress,
    TaskStatus, DownloadType,
)
from ..models.settings import Settings, ThemeMode
from ..config.settings_manager import get_settings_manager, get_settings
from ..downloader.format_parser import FormatParser
from ..downloader.video_downloader import VideoDownloader
from ..downloader.playlist_downloader import PlaylistDownloader
from ..downloader.subtitle_downloader import SubtitleDownloader
from ..downloader.thumbnail_downloader import ThumbnailDownloader
from ..downloader.ffmpeg_merger import FFmpegMerger
from ..downloader.ffmpeg_installer import FFmpegInstaller
from ..downloader.download_queue import DownloadQueue
from ..utils.validators import validate_youtube_url, sanitize_filename, clean_video_url
from ..utils.logger import get_logger

from .settings_window import SettingsWindow
from .about_window import AboutWindow
from .theme import get_theme_stylesheet

logger = get_logger(__name__)


class FetchInfoWorker(QThread):
    """获取视频信息的后台线程

    在后台获取视频信息和格式列表，避免阻塞 UI。
    """

    # 信号：成功获取 (video_info, formats, subtitles)
    info_ready = Signal(object, list, list)
    # 信号：获取失败 (error_message)
    info_error = Signal(str)
    # 信号：播放列表信息 (playlist_title, videos)
    playlist_ready = Signal(str, list)

    def __init__(self, url: str, cookies: str = "", cookies_file: str = "", parent=None) -> None:
        """初始化信息获取线程

        Args:
            url: YouTube URL
            cookies: 浏览器名称用于 Cookie 读取
            cookies_file: Cookie 文件路径（Netscape 格式）
            parent: 父对象
        """
        super().__init__(parent)
        self._url = url
        self._cookies = cookies
        self._cookies_file = cookies_file
        self._is_playlist = False

    @property
    def is_playlist(self) -> bool:
        """是否为播放列表"""
        return self._is_playlist

    def run(self) -> None:
        """执行线程逻辑"""
        try:
            valid, vid, is_playlist = validate_youtube_url(self._url)

            if not valid:
                self.info_error.emit("无效的 YouTube URL，请检查链接格式。")
                return

            self._is_playlist = is_playlist
            parser = FormatParser(self._cookies, self._cookies_file)

            if is_playlist:
                # 播放列表
                playlist_dl = PlaylistDownloader(self._cookies, self._cookies_file)
                videos = playlist_dl.fetch_playlist_info(self._url)
                title = playlist_dl.fetch_playlist_title(self._url)
                self.playlist_ready.emit(title, videos)
            else:
                # 单个视频 — 清理 URL（移除 ?list= / &t= 等参数）
                clean_url = clean_video_url(self._url)
                info = parser.fetch_video_info(clean_url)
                if info is None:
                    err = parser.last_error or "无法获取视频信息，请检查链接或网络连接。"
                    self.info_error.emit(err)
                    return

                formats = parser.fetch_formats(clean_url)
                subtitles = parser.fetch_subtitles(clean_url)

                self.info_ready.emit(info, formats, subtitles)

        except Exception as e:
            logger.error(f"获取信息失败: {e}")
            self.info_error.emit(f"获取信息时发生错误: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口

    YouTube Downloader Pro 的主界面，
    提供视频下载、播放列表管理和设置入口。
    """

    # 应用信息
    APP_TITLE = "YouTube Downloader Pro"
    APP_VERSION = "v1.0.0"

    def __init__(self) -> None:
        """初始化主窗口"""
        super().__init__()

        # 设置管理器
        self._settings_manager = get_settings_manager()
        self._settings = self._settings_manager.settings

        # 下载器组件
        cookies = self._settings.cookies_from_browser
        cookies_file = self._settings.cookies_file
        self._format_parser = FormatParser(cookies, cookies_file)
        self._video_downloader = VideoDownloader(self._settings.ffmpeg_path)
        self._playlist_downloader = PlaylistDownloader(cookies, cookies_file)
        self._subtitle_downloader = SubtitleDownloader()
        self._thumbnail_downloader = ThumbnailDownloader()
        self._ffmpeg_merger = FFmpegMerger(self._settings.ffmpeg_path)

        # 下载队列
        self._download_queue = DownloadQueue(self._settings.max_workers)
        self._active_downloaders: dict = {}  # task_id -> VideoDownloader
        self._downloaders_lock = threading.Lock()  # 保护 _active_downloaders

        # 当前获取的视频信息
        self._current_info: Optional[VideoInfo] = None
        self._current_formats: List[VideoFormat] = []
        self._current_subtitles = []
        self._playlist_videos: List[VideoInfo] = []

        # 后台线程
        self._fetch_worker: Optional[FetchInfoWorker] = None

        # 进度定时器（延迟到 showEvent 启动，避免初始化竞态崩溃）
        self._progress_timer = QTimer()
        self._progress_timer.setInterval(500)
        self._progress_timer.timeout.connect(self._refresh_progress_display)

        # 构建 UI
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._setup_connections()
        # 主题在 main.py 中通过 app.setStyleSheet() 预加载，此处不重复应用

        # 恢复窗口位置
        self._restore_window_geometry()

        logger.info("主窗口初始化完成")

    # ========== UI 构建 ==========

    def _setup_ui(self) -> None:
        """构建主界面布局"""
        self.setWindowTitle(f"{self.APP_TITLE} {self.APP_VERSION}")
        self.setMinimumSize(1000, 700)

        # 中央组件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # ---------- 顶部：URL 输入区 ----------
        self._create_url_bar(main_layout)

        # ---------- 中间：内容区 (堆叠) ----------
        self._content_stack = QStackedWidget()

        # 页面 0: 空状态
        self._empty_page = self._create_empty_page()
        self._content_stack.addWidget(self._empty_page)

        # 页面 1: 视频信息 + 格式选择 + 选项
        self._video_page = self._create_video_page()
        self._content_stack.addWidget(self._video_page)

        # 页面 2: 播放列表
        self._playlist_page = self._create_playlist_page()
        self._content_stack.addWidget(self._playlist_page)

        main_layout.addWidget(self._content_stack, stretch=1)

        # ---------- 下载设置面板（始终可见，对所有下载模式生效）----------
        self._download_settings = self._create_download_settings()
        main_layout.addWidget(self._download_settings)

        # ---------- 底部：下载进度列表 ----------
        self._create_progress_table(main_layout)

        # 默认显示空状态
        self._content_stack.setCurrentIndex(0)

    def _create_url_bar(self, parent_layout: QVBoxLayout) -> None:
        """创建顶部 URL 输入栏

        Args:
            parent_layout: 父布局
        """
        url_frame = QFrame()
        url_frame.setObjectName("urlBar")
        url_frame.setFixedHeight(56)
        url_layout = QHBoxLayout(url_frame)
        url_layout.setContentsMargins(8, 8, 8, 8)

        # URL 图标
        url_icon = QLabel("🔗")
        url_icon.setFixedWidth(30)
        url_layout.addWidget(url_icon)

        # URL 输入框
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(
            "粘贴 YouTube 视频或播放列表链接...  例如: https://www.youtube.com/watch?v=..."
        )
        self._url_input.setClearButtonEnabled(True)
        self._url_input.returnPressed.connect(self._on_fetch_info)
        url_layout.addWidget(self._url_input)

        # 获取信息按钮
        self._fetch_btn = QPushButton("🔍 获取信息")
        self._fetch_btn.setFixedWidth(110)
        self._fetch_btn.setToolTip("获取视频信息和可用格式")
        self._fetch_btn.clicked.connect(self._on_fetch_info)
        url_layout.addWidget(self._fetch_btn)

        # 下载按钮
        self._download_btn = QPushButton("⬇ 下载")
        self._download_btn.setFixedWidth(90)
        self._download_btn.setEnabled(False)
        self._download_btn.setToolTip("开始下载当前视频")
        self._download_btn.clicked.connect(self._on_start_download)
        url_layout.addWidget(self._download_btn)

        # 批量下载按钮
        self._batch_btn = QPushButton("📦 批量下载")
        self._batch_btn.setFixedWidth(100)
        self._batch_btn.setToolTip("批量添加多个视频链接同时下载")
        self._batch_btn.clicked.connect(self._on_batch_download)
        url_layout.addWidget(self._batch_btn)

        parent_layout.addWidget(url_frame)

    def _create_empty_page(self) -> QWidget:
        """创建空状态引导页

        Returns:
            空状态页面组件
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        icon_label = QLabel("📥")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px;")
        layout.addWidget(icon_label)

        title = QLabel("YouTube Downloader Pro")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        hint = QLabel('在上方粘贴 YouTube 链接，然后点击"获取信息"开始')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(hint)

        layout.addStretch()
        return page

    def _create_video_page(self) -> QWidget:
        """创建视频信息页面

        Returns:
            视频信息页面组件
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        # ===== 视频信息卡片 =====
        info_frame = QFrame()
        info_frame.setObjectName("videoInfoCard")
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 12, 16, 12)

        # 封面图
        self._thumbnail_label = QLabel()
        self._thumbnail_label.setFixedSize(160, 90)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setStyleSheet(
            "background-color: #333; border-radius: 6px; color: #888; font-size: 12px;"
        )
        self._thumbnail_label.setText("封面图")
        info_layout.addWidget(self._thumbnail_label)

        # 视频元数据
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(4)

        self._title_label = QLabel("视频标题")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)
        meta_layout.addWidget(self._title_label)

        meta_grid = QGridLayout()
        meta_grid.setSpacing(4)

        meta_grid.addWidget(QLabel("👤 作者:"), 0, 0)
        self._author_label = QLabel("-")
        meta_grid.addWidget(self._author_label, 0, 1)

        meta_grid.addWidget(QLabel("⏱ 时长:"), 0, 2)
        self._duration_label = QLabel("-")
        meta_grid.addWidget(self._duration_label, 0, 3)

        meta_grid.addWidget(QLabel("📅 上传:"), 1, 0)
        self._upload_date_label = QLabel("-")
        meta_grid.addWidget(self._upload_date_label, 1, 1)

        meta_layout.addLayout(meta_grid)
        info_layout.addLayout(meta_layout, stretch=1)

        layout.addWidget(info_frame)

        return page

    def _create_download_settings(self) -> QWidget:
        """创建下载设置面板（始终可见）

        包含格式选择和下载选项，对所有下载模式（单视频/播放列表/批量）生效。
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ===== 格式选择区 =====
        format_group = QGroupBox("格式选择")
        format_flayout = QFormLayout(format_group)

        # 视频格式
        video_fmt_layout = QHBoxLayout()
        self._video_format_combo = QComboBox()
        self._video_format_combo.setMinimumWidth(400)
        self._video_format_combo.setToolTip("选择视频清晰度和编码格式")
        video_fmt_layout.addWidget(self._video_format_combo)
        video_fmt_layout.addStretch()
        format_flayout.addRow("🎬 视频格式:", video_fmt_layout)

        # 音频格式
        audio_fmt_layout = QHBoxLayout()
        self._audio_format_combo = QComboBox()
        self._audio_format_combo.setMinimumWidth(200)
        self._audio_format_combo.setToolTip("选择纯音频格式（仅下载音频时选择此项）")
        audio_fmt_layout.addWidget(self._audio_format_combo)
        audio_fmt_layout.addStretch()
        format_flayout.addRow("🎵 音频格式:", audio_fmt_layout)

        layout.addWidget(format_group)

        # ===== 下载选项 =====
        options_frame = QFrame()
        options_hlayout = QHBoxLayout(options_frame)
        options_hlayout.setContentsMargins(0, 0, 0, 0)

        self._subtitle_cb = QCheckBox("📝 下载字幕")
        self._subtitle_cb.setChecked(self._settings.auto_subtitle)
        options_hlayout.addWidget(self._subtitle_cb)

        self._sub_lang_combo = QComboBox()
        self._sub_lang_combo.addItems(["中文", "English", "日本語", "한국어"])
        self._sub_lang_combo.setFixedWidth(80)
        options_hlayout.addWidget(self._sub_lang_combo)

        options_hlayout.addSpacing(16)

        self._thumbnail_cb = QCheckBox("🖼 下载封面")
        options_hlayout.addWidget(self._thumbnail_cb)

        options_hlayout.addSpacing(16)

        self._auto_merge_cb = QCheckBox("🔗 自动合并音视频")
        self._auto_merge_cb.setChecked(self._settings.auto_merge)
        self._auto_merge_cb.setToolTip("高清视频自动下载音视频流并使用 FFmpeg 合并")
        options_hlayout.addWidget(self._auto_merge_cb)

        options_hlayout.addStretch()
        layout.addWidget(options_frame)

        return container

    def _create_playlist_page(self) -> QWidget:
        """创建播放列表信息页面

        Returns:
            播放列表页面组件
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        # 播放列表标题
        self._playlist_title_label = QLabel("播放列表")
        pl_font = QFont()
        pl_font.setPointSize(14)
        pl_font.setBold(True)
        self._playlist_title_label.setFont(pl_font)
        layout.addWidget(self._playlist_title_label)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self._select_all_btn = QPushButton("全选")
        self._select_all_btn.setFixedWidth(70)
        self._select_all_btn.clicked.connect(self._on_select_all)
        btn_layout.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("取消全选")
        self._deselect_all_btn.setFixedWidth(80)
        self._deselect_all_btn.clicked.connect(self._on_deselect_all)
        btn_layout.addWidget(self._deselect_all_btn)

        btn_layout.addStretch()

        count_label = QLabel("共 ")
        btn_layout.addWidget(count_label)

        self._playlist_count_label = QLabel("0")
        self._playlist_count_label.setStyleSheet("font-weight: bold;")
        btn_layout.addWidget(self._playlist_count_label)

        btn_layout.addWidget(QLabel(" 个视频"))

        btn_layout.addStretch()

        self._playlist_download_btn = QPushButton("⬇ 下载选中")
        self._playlist_download_btn.setFixedWidth(110)
        self._playlist_download_btn.clicked.connect(self._on_download_selected)
        btn_layout.addWidget(self._playlist_download_btn)

        layout.addLayout(btn_layout)

        # 视频列表表格
        self._playlist_table = QTableWidget()
        self._playlist_table.setColumnCount(5)
        self._playlist_table.setHorizontalHeaderLabels([
            "", "序号", "标题", "作者", "时长",
        ])
        self._playlist_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._playlist_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._playlist_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._playlist_table.setColumnWidth(0, 40)   # 复选框
        self._playlist_table.setColumnWidth(1, 50)   # 序号
        self._playlist_table.setColumnWidth(3, 120)  # 作者
        self._playlist_table.setColumnWidth(4, 80)   # 时长
        self._playlist_table.setAlternatingRowColors(True)

        layout.addWidget(self._playlist_table)

        return page

    def _create_progress_table(self, parent_layout: QVBoxLayout) -> None:
        """创建下载进度列表

        Args:
            parent_layout: 父布局
        """
        progress_group = QGroupBox("下载队列")
        progress_layout = QVBoxLayout(progress_group)

        # 工具栏
        toolbar = QHBoxLayout()

        self._pause_all_btn = QPushButton("⏸ 全部暂停")
        self._pause_all_btn.setFixedWidth(90)
        self._pause_all_btn.clicked.connect(self._on_pause_all)
        toolbar.addWidget(self._pause_all_btn)

        self._resume_all_btn = QPushButton("▶ 全部恢复")
        self._resume_all_btn.setFixedWidth(90)
        self._resume_all_btn.clicked.connect(self._on_resume_all)
        toolbar.addWidget(self._resume_all_btn)

        self._cancel_all_btn = QPushButton("⏹ 全部取消")
        self._cancel_all_btn.setFixedWidth(90)
        self._cancel_all_btn.clicked.connect(self._on_cancel_all)
        toolbar.addWidget(self._cancel_all_btn)

        toolbar.addStretch()

        self._clear_completed_btn = QPushButton("清空已完成")
        self._clear_completed_btn.setFixedWidth(90)
        self._clear_completed_btn.clicked.connect(self._on_clear_completed)
        toolbar.addWidget(self._clear_completed_btn)

        self._retry_failed_btn = QPushButton("重试失败")
        self._retry_failed_btn.setFixedWidth(80)
        self._retry_failed_btn.clicked.connect(self._on_retry_failed)
        toolbar.addWidget(self._retry_failed_btn)

        progress_layout.addLayout(toolbar)

        # 进度表格
        self._progress_table = QTableWidget()
        self._progress_table.setColumnCount(6)
        self._progress_table.setHorizontalHeaderLabels([
            "任务", "状态", "速度", "已下载/总大小", "进度", "操作",
        ])
        self._progress_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._progress_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._progress_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._progress_table.setColumnWidth(1, 80)
        self._progress_table.setColumnWidth(2, 100)
        self._progress_table.setColumnWidth(3, 150)
        self._progress_table.setColumnWidth(4, 160)
        self._progress_table.setColumnWidth(5, 90)
        self._progress_table.setAlternatingRowColors(True)

        progress_layout.addWidget(self._progress_table)

        parent_layout.addWidget(progress_group)

    def _setup_menu_bar(self) -> None:
        """设置菜单栏"""
        menu_bar = self.menuBar()

        # 文件菜单
        file_menu = menu_bar.addMenu("文件(&F)")

        add_url_action = QAction("添加下载链接...", self)
        add_url_action.triggered.connect(
            lambda: self._url_input.setFocus()
        )
        file_menu.addAction(add_url_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tools_menu = menu_bar.addMenu("工具(&T)")

        settings_action = QAction("设置(&S)...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        tools_menu.addSeparator()

        open_dir_action = QAction("打开下载目录...", self)
        open_dir_action.triggered.connect(self._open_download_dir)
        tools_menu.addAction(open_dir_action)

        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助(&H)")

        about_action = QAction("关于(&A)...", self)
        about_action.triggered.connect(self._open_about)
        help_menu.addAction(about_action)

        help_menu.addSeparator()

        ffmpeg_action = QAction("检查 FFmpeg 状态...", self)
        ffmpeg_action.triggered.connect(self._check_ffmpeg_status)
        help_menu.addAction(ffmpeg_action)

    def _setup_status_bar(self) -> None:
        """设置状态栏"""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # 线程数标签
        self._thread_label = QLabel(
            f"线程: {self._settings.max_workers}"
        )
        self._status_bar.addPermanentWidget(self._thread_label)

        # FFmpeg 状态（标签创建，内容在 showEvent 中更新）
        self._ffmpeg_status_label = QLabel()
        self._status_bar.addPermanentWidget(self._ffmpeg_status_label)

        self._status_bar.showMessage("就绪")

    def _setup_connections(self) -> None:
        """设置下载队列的回调连接（所有回调通过 QTimer 调度到主线程）"""
        self._download_queue.set_callbacks(
            on_started=lambda t: QTimer.singleShot(0, lambda: self._on_task_started(t)),
            on_completed=lambda t: QTimer.singleShot(0, lambda: self._on_task_completed(t)),
            on_failed=lambda t: QTimer.singleShot(0, lambda: self._on_task_failed(t)),
            on_all_completed=lambda: QTimer.singleShot(0, self._on_all_completed),
        )

    # ========== 主题 ==========

    def _apply_theme(self) -> None:
        """应用当前主题设置"""
        theme = self._settings.theme

        if theme == ThemeMode.SYSTEM:
            is_dark = True  # 默认深色
            try:
                import darkdetect
                is_dark = darkdetect.isDark()
            except Exception:
                pass
        else:
            is_dark = (theme == ThemeMode.DARK)

        if is_dark:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

    def _apply_dark_theme(self) -> None:
        """应用深色主题"""
        QApplication.instance().setStyleSheet(get_theme_stylesheet(True))

    def _apply_light_theme(self) -> None:
        """应用浅色主题"""
        QApplication.instance().setStyleSheet(get_theme_stylesheet(False))

    # ========== 窗口状态管理 ==========

    def _restore_window_geometry(self) -> None:
        """恢复上次的窗口位置和大小"""
        s = self._settings
        if s.window_width > 0 and s.window_height > 0:
            self.resize(s.window_width, s.window_height)
        if s.window_x >= 0 and s.window_y >= 0:
            self.move(s.window_x, s.window_y)

    def _save_window_geometry(self) -> None:
        """保存当前窗口位置和大小"""
        s = self._settings
        s.window_width = self.width()
        s.window_height = self.height()
        s.window_x = self.x()
        s.window_y = self.y()
        self._settings_manager.save(s)

    # ========== 事件处理 ==========

    def closeEvent(self, event) -> None:
        """窗口关闭事件

        Args:
            event: 关闭事件
        """
        # 停止进度刷新定时器
        self._progress_timer.stop()

        # 保存窗口状态
        self._save_window_geometry()

        # 停止下载队列
        if self._download_queue.is_running:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "下载任务正在进行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                self._progress_timer.start()  # 恢复定时器
                event.ignore()
                return
            self._download_queue.stop()

        event.accept()

    def showEvent(self, event) -> None:
        """窗口显示后延迟启动定时器，避免与渲染管道竞争"""
        super().showEvent(event)

        if not self._progress_timer.isActive():
            # 延迟启动避免与 Qt 渲染竞态 (Python 3.14 兼容)
            QTimer.singleShot(500, self._update_ffmpeg_status_label)
            QTimer.singleShot(1000, self._progress_timer.start)

    # ========== 核心操作 ==========

    def _on_fetch_info(self) -> None:
        """获取视频/播放列表信息"""
        url = self._url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请先输入 YouTube 链接。")
            return

        valid, _, _ = validate_youtube_url(url)
        if not valid:
            QMessageBox.warning(
                self, "无效链接",
                "请检查 YouTube 链接格式是否正确。\n\n"
                "支持的格式:\n"
                "  • https://www.youtube.com/watch?v=...\n"
                "  • https://youtu.be/...\n"
                "  • https://www.youtube.com/playlist?list=..."
            )
            return

        # 禁用按钮，防止重复点击
        self._fetch_btn.setEnabled(False)
        self._download_btn.setEnabled(False)
        self._status_bar.showMessage("正在获取信息...")

        # 启动后台线程获取信息
        self._fetch_worker = FetchInfoWorker(
            url,
            cookies=self._settings.cookies_from_browser,
            cookies_file=self._settings.cookies_file,
        )
        self._fetch_worker.info_ready.connect(self._on_info_ready)
        self._fetch_worker.info_error.connect(self._on_info_error)
        self._fetch_worker.playlist_ready.connect(self._on_playlist_ready)
        self._fetch_worker.start()

    @Slot(object, list, list)
    def _on_info_ready(
        self,
        info: VideoInfo,
        formats: list,
        subtitles: list,
    ) -> None:
        """视频信息获取成功

        Args:
            info: 视频信息
            formats: 可用格式列表
            subtitles: 字幕列表
        """
        self._current_info = info
        self._current_formats = formats
        self._current_subtitles = subtitles

        # 更新 UI
        self._display_video_info(info)
        self._populate_format_combos(formats)

        # 切换到视频页面
        self._content_stack.setCurrentIndex(1)
        self._download_btn.setEnabled(True)
        self._fetch_btn.setEnabled(True)

        self._status_bar.showMessage(f"已获取: {info.title[:50]}...", 5000)
        logger.info(f"视频信息获取成功: {info.title}")

    @Slot(str)
    def _on_info_error(self, error_msg: str) -> None:
        """视频信息获取失败

        Args:
            error_msg: 错误消息
        """
        self._fetch_btn.setEnabled(True)
        self._status_bar.showMessage("获取失败", 3000)
        QMessageBox.critical(self, "获取失败", error_msg)
        logger.error(f"获取信息失败: {error_msg}")

    @Slot(str, list)
    def _on_playlist_ready(self, title: str, videos: list) -> None:
        """播放列表信息获取成功

        Args:
            title: 播放列表标题
            videos: 视频信息列表
        """
        self._playlist_videos = videos

        # 更新播放列表 UI
        self._playlist_title_label.setText(f"📋 {title}")
        self._playlist_count_label.setText(str(len(videos)))

        # 填充播放列表表格
        self._populate_playlist_table(videos)

        # 切换到播放列表页面
        self._content_stack.setCurrentIndex(2)
        self._download_btn.setEnabled(True)
        self._fetch_btn.setEnabled(True)

        # 后台获取第一个视频的可用格式，填充格式选择下拉框
        if videos and videos[0].webpage_url:
            self._fetch_formats_for_playlist(videos[0].webpage_url)

        self._status_bar.showMessage(
            f"播放列表: {title} ({len(videos)} 个视频)", 5000
        )
        logger.info(f"播放列表解析成功: {title} ({len(videos)} 个视频)")

    def _fetch_formats_for_playlist(self, sample_url: str) -> None:
        """后台获取播放列表的可用格式（使用第一个视频采样）

        Args:
            sample_url: 采样视频的 URL
        """
        class FormatFetchThread(QThread):
            formats_ready = Signal(list)

            def __init__(self, url: str, cookies: str = "", cookies_file: str = ""):
                super().__init__()
                self._url = url
                self._cookies = cookies
                self._cookies_file = cookies_file

            def run(self) -> None:
                try:
                    parser = FormatParser(self._cookies, self._cookies_file)
                    formats = parser.fetch_formats(self._url)
                    self.formats_ready.emit(formats)
                except Exception:
                    self.formats_ready.emit([])

        self._format_thread = FormatFetchThread(
            sample_url,
            cookies=self._settings.cookies_from_browser,
            cookies_file=self._settings.cookies_file,
        )
        self._format_thread.formats_ready.connect(self._populate_format_combos)
        self._format_thread.start()

    def _on_start_download(self) -> None:
        """开始下载"""
        current_page = self._content_stack.currentIndex()

        if current_page == 1:
            # 单视频下载
            self._start_single_download()
        elif current_page == 2:
            # 播放列表下载
            self._start_playlist_download()
        else:
            QMessageBox.warning(self, "提示", "请先获取视频信息。")

    def _start_single_download(self) -> None:
        """启动单个视频下载"""
        if not self._current_info:
            return

        # 创建下载任务
        task = DownloadTask(
            url=self._url_input.text().strip(),
            video_info=self._current_info,
        )

        # 获取选择的格式（从 combo 的用户数据中获取）
        selected_fmt = self._video_format_combo.currentData()
        if selected_fmt and isinstance(selected_fmt, VideoFormat):
            task.selected_format = selected_fmt

        # 检查 FFmpeg 是否就绪（纯视频格式需要合并）
        if (
            task.selected_format
            and task.selected_format.has_video
            and not task.selected_format.has_audio
            and not self._ffmpeg_merger.is_available
        ):
            reply = QMessageBox.warning(
                self,
                "FFmpeg 不可用",
                "您选择的视频格式只有视频流，没有音频。\n"
                "合并音频需要 FFmpeg，但当前未安装。\n\n"
                "建议:\n"
                "  1. 选择含音频的合并格式（下拉列表前半部分）\n"
                "  2. 安装 FFmpeg 并在设置中配置\n\n"
                "是否仍要继续？(可能下载失败)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # 下载选项
        task.download_subtitle = self._subtitle_cb.isChecked()
        task.download_thumbnail = self._thumbnail_cb.isChecked()

        if self._subtitle_cb.isChecked():
            lang_map = {0: "zh", 1: "en", 2: "ja", 3: "ko"}
            task.subtitle_language = lang_map.get(
                self._sub_lang_combo.currentIndex(), "zh"
            )

        # 输出目录
        task.output_dir = (
            self._settings.download_dir
            or str(Path.home() / "Downloads" / "YouTube")
        )

        # 代理和限速
        if self._settings.proxy:
            task.extra_data["proxy"] = self._settings.proxy
        if self._settings.rate_limit:
            task.extra_data["rate_limit"] = self._settings.rate_limit
        if self._settings.cookies_file:
            task.extra_data["cookies_file"] = self._settings.cookies_file
        elif self._settings.cookies_from_browser:
            task.extra_data["cookies_from_browser"] = self._settings.cookies_from_browser

        # 添加到下载队列
        self._download_queue.add_task(task)

        # 刷新进度表
        self._refresh_progress_table()

        # 启动队列（如果尚未运行）
        self._ensure_queue_running()

        self._status_bar.showMessage(
            f"已添加下载: {task.video_info.title[:40]}..."
        )

    def _start_playlist_download(self) -> None:
        """启动播放列表批量下载

        使用主窗口当前设置（画质/格式/字幕/封面/音频）应用到所有选中视频。
        """
        selected_videos = self._get_selected_playlist_videos()

        if not selected_videos:
            QMessageBox.warning(self, "提示", "请至少选择一个视频。")
            return

        # 读取主窗口的当前设置
        selected_fmt = self._video_format_combo.currentData()
        is_audio_only = False
        if (selected_fmt and isinstance(selected_fmt, VideoFormat)
                and selected_fmt.is_audio_only):
            is_audio_only = True

        output_dir = (
            self._settings.download_dir
            or str(Path.home() / "Downloads" / "YouTube")
        )

        tasks = []
        for i, video_info in enumerate(selected_videos):
            task = DownloadTask(
                url=video_info.webpage_url,
                video_info=video_info,
                is_playlist=True,
            )

            # 应用主窗口的画质/格式选择
            if selected_fmt and isinstance(selected_fmt, VideoFormat):
                task.selected_format = selected_fmt

            # 应用主窗口的下载选项
            task.download_video = not is_audio_only
            task.download_audio = is_audio_only
            task.download_subtitle = self._subtitle_cb.isChecked()
            task.download_thumbnail = self._thumbnail_cb.isChecked()
            task.subtitle_auto = self._settings.auto_subtitle
            task.subtitle_language = self._settings.default_subtitle_lang
            task.subtitle_format = self._settings.default_subtitle_format
            task.output_dir = output_dir

            if self._settings.proxy:
                task.extra_data["proxy"] = self._settings.proxy
            if self._settings.rate_limit:
                task.extra_data["rate_limit"] = self._settings.rate_limit
            if self._settings.cookies_file:
                task.extra_data["cookies_file"] = self._settings.cookies_file
            elif self._settings.cookies_from_browser:
                task.extra_data["cookies_from_browser"] = self._settings.cookies_from_browser

            tasks.append(task)

        # 批量添加
        self._download_queue.add_tasks(tasks)

        # 刷新进度表
        self._refresh_progress_table()

        # 启动队列
        self._ensure_queue_running()

        self._status_bar.showMessage(
            f"已添加 {len(tasks)} 个下载任务"
        )

    def _on_batch_download(self) -> None:
        """批量下载对话框

        支持两种模式:
        1. 粘贴多个视频 URL（每行一个）
        2. 粘贴播放列表链接，自动解析全部视频

        解析后展示视频列表，支持勾选、配置参数，一键批量下载。
        """
        from PySide6.QtWidgets import (
            QDialog, QTextEdit, QDialogButtonBox, QSpinBox,
        )
        from PySide6.QtCore import QThread, Signal

        # ===== 后台解析线程 =====
        class ParseThread(QThread):
            """后台解析播放列表的线程"""
            result_signal = Signal(list)  # [(url, title, author, duration_str), ...]
            error_signal = Signal(str)

            def __init__(self, raw_text: str, cookies: str = "", cookies_file: str = ""):
                super().__init__()
                self._raw_text = raw_text
                self._cookies = cookies
                self._cookies_file = cookies_file

            def run(self) -> None:
                results = []
                lines = [l.strip() for l in self._raw_text.split("\n") if l.strip()]

                for line in lines:
                    valid, vid, is_playlist = validate_youtube_url(line)
                    if not valid:
                        continue

                    if is_playlist:
                        # 播放列表：解析所有视频
                        try:
                            pl = PlaylistDownloader(self._cookies, self._cookies_file)
                            videos = pl.fetch_playlist_info(line)
                            for v in videos:
                                results.append((
                                    v.webpage_url or f"https://youtu.be/{v.title}",
                                    v.title,
                                    v.author,
                                    v.duration_str,
                                ))
                        except Exception as e:
                            self.error_signal.emit(f"播放列表解析失败: {e}")
                    else:
                        # 单个视频：先获取基本信息
                        try:
                            parser = FormatParser(self._cookies, self._cookies_file)
                            info = parser.fetch_video_info(line)
                            if info:
                                results.append((
                                    line, info.title, info.author, info.duration_str,
                                ))
                            else:
                                results.append((line, "(获取中...)", "", ""))
                        except Exception:
                            results.append((line, "(获取失败)", "", ""))

                self.result_signal.emit(results)

        # ===== 构建对话框 =====
        dialog = QDialog(self)
        dialog.setWindowTitle("批量下载")
        dialog.setMinimumSize(750, 600)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)

        # ---- 输入区 ----
        input_label = QLabel(
            "粘贴视频链接（每行一个）或播放列表链接，然后点击「解析链接」："
        )
        layout.addWidget(input_label)

        text_edit = QTextEdit()
        text_edit.setPlaceholderText(
            "https://www.youtube.com/watch?v=xxxxx\n"
            "https://youtu.be/yyyyy\n"
            "https://www.youtube.com/playlist?list=zzzzz\n"
            "..."
        )
        text_edit.setMaximumHeight(120)
        layout.addWidget(text_edit)

        # ---- 解析按钮 ----
        parse_btn = QPushButton("🔍 解析链接")
        parse_btn.setFixedHeight(34)
        layout.addWidget(parse_btn)

        # ---- 结果表格 ----
        result_table = QTableWidget()
        result_table.setColumnCount(4)
        result_table.setHorizontalHeaderLabels(["", "标题", "作者", "时长"])
        result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        result_table.setColumnWidth(0, 40)
        result_table.setColumnWidth(2, 120)
        result_table.setColumnWidth(3, 70)
        result_table.setAlternatingRowColors(True)
        layout.addWidget(result_table)

        # ---- 表格工具栏 ----
        table_toolbar = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.setFixedWidth(60)
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.setFixedWidth(80)
        count_label = QLabel("共 0 个视频")
        table_toolbar.addWidget(select_all_btn)
        table_toolbar.addWidget(deselect_all_btn)
        table_toolbar.addStretch()
        table_toolbar.addWidget(count_label)
        layout.addLayout(table_toolbar)

        # ---- 下载选项提示（使用主窗口设置） ----
        options_label = QLabel(
            "下载参数使用主窗口设置：画质/格式/字幕/封面/音频等。\n"
            "请先在主窗口选择好格式和选项，再使用批量下载。"
        )
        options_label.setStyleSheet("color: #2196F3; font-size: 12px; padding: 4px;")
        layout.addWidget(options_label)

        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("批量线程数:"))
        thread_spin = QSpinBox()
        thread_spin.setRange(1, 32)
        thread_spin.setValue(self._settings.max_workers)
        thread_spin.setFixedWidth(60)
        thread_layout.addWidget(thread_spin)
        thread_layout.addStretch()
        layout.addLayout(thread_layout)

        # ---- 底部按钮 ----
        btn_layout = QHBoxLayout()
        download_btn = QPushButton("⬇ 开始批量下载")
        download_btn.setEnabled(False)
        download_btn.setFixedHeight(36)
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(36)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(download_btn)
        layout.addLayout(btn_layout)

        # ---- 存储解析结果 ----
        parsed_urls: list = []  # [(url, title, author, duration_str), ...]

        # ---- 信号连接 ----
        def on_parse():
            raw_text = text_edit.toPlainText().strip()
            if not raw_text:
                QMessageBox.warning(dialog, "提示", "请输入至少一个链接。")
                return

            parse_btn.setEnabled(False)
            parse_btn.setText("⏳ 正在解析...")
            result_table.setRowCount(0)
            parsed_urls.clear()

            self._parse_thread = ParseThread(
                raw_text,
                cookies=self._settings.cookies_from_browser,
                cookies_file=self._settings.cookies_file,
            )

            def on_result(results):
                nonlocal parsed_urls
                parsed_urls = results
                result_table.setRowCount(len(results))
                for i, (url, title, author, duration) in enumerate(results):
                    cb = QTableWidgetItem()
                    cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                    cb.setCheckState(Qt.CheckState.Checked)
                    result_table.setItem(i, 0, cb)
                    result_table.setItem(i, 1, QTableWidgetItem(title))
                    result_table.setItem(i, 2, QTableWidgetItem(author))
                    result_table.setItem(i, 3, QTableWidgetItem(duration))
                count_label.setText(f"共 {len(results)} 个视频")
                download_btn.setEnabled(len(results) > 0)
                parse_btn.setEnabled(True)
                parse_btn.setText("🔍 解析链接")

            def on_error(msg):
                parse_btn.setEnabled(True)
                parse_btn.setText("🔍 解析链接")
                QMessageBox.warning(dialog, "解析错误", msg)

            self._parse_thread.result_signal.connect(on_result)
            self._parse_thread.error_signal.connect(on_error)
            self._parse_thread.start()

        parse_btn.clicked.connect(on_parse)

        select_all_btn.clicked.connect(lambda: [
            result_table.item(i, 0).setCheckState(Qt.CheckState.Checked)
            for i in range(result_table.rowCount())
            if result_table.item(i, 0)
        ])
        deselect_all_btn.clicked.connect(lambda: [
            result_table.item(i, 0).setCheckState(Qt.CheckState.Unchecked)
            for i in range(result_table.rowCount())
            if result_table.item(i, 0)
        ])

        close_btn.clicked.connect(dialog.reject)

        def on_download():
            selected = []
            for i in range(result_table.rowCount()):
                cb = result_table.item(i, 0)
                if cb and cb.checkState() == Qt.CheckState.Checked and i < len(parsed_urls):
                    selected.append(parsed_urls[i])

            if not selected:
                QMessageBox.warning(dialog, "提示", "请至少勾选一个视频。")
                return

            # 读取主窗口当前设置
            selected_fmt = self._video_format_combo.currentData()
            is_audio_only = False
            if (selected_fmt and isinstance(selected_fmt, VideoFormat)
                    and selected_fmt.is_audio_only):
                is_audio_only = True

            output_dir = (
                self._settings.download_dir
                or str(Path.home() / "Downloads" / "YouTube")
            )

            tasks = []
            for url, title, author, duration in selected:
                task = DownloadTask(url=url)
                task.video_info = VideoInfo(
                    title=title, author=author, webpage_url=url,
                )

                # 应用主窗口的画质/格式选择
                if selected_fmt and isinstance(selected_fmt, VideoFormat):
                    task.selected_format = selected_fmt

                # 应用主窗口的下载选项
                task.download_video = not is_audio_only
                task.download_audio = is_audio_only
                task.download_subtitle = self._subtitle_cb.isChecked()
                task.download_thumbnail = self._thumbnail_cb.isChecked()
                task.subtitle_auto = self._settings.auto_subtitle
                task.subtitle_language = self._settings.default_subtitle_lang
                task.subtitle_format = self._settings.default_subtitle_format
                task.output_dir = output_dir

                if self._settings.proxy:
                    task.extra_data["proxy"] = self._settings.proxy
                if self._settings.rate_limit:
                    task.extra_data["rate_limit"] = self._settings.rate_limit
                if self._settings.cookies_file:
                    task.extra_data["cookies_file"] = self._settings.cookies_file
                elif self._settings.cookies_from_browser:
                    task.extra_data["cookies_from_browser"] = self._settings.cookies_from_browser
                tasks.append(task)

            # 应用线程数
            self._download_queue.max_workers = thread_spin.value()

            self._download_queue.add_tasks(tasks)
            self._refresh_progress_table()
            self._ensure_queue_running()

            self._status_bar.showMessage(f"已添加 {len(tasks)} 个批量下载任务")
            QMessageBox.information(
                dialog, "批量下载",
                f"已添加 {len(tasks)} 个下载任务到队列！\n\n"
                "可在主窗口下方下载队列中查看进度。"
            )

        download_btn.clicked.connect(on_download)

        dialog.exec()

    def _ensure_queue_running(self) -> None:
        """确保下载队列正在运行"""
        if not self._download_queue.is_running:
            self._download_queue.max_workers = self._settings.max_workers
            self._download_queue.start(self._execute_download)

    def _execute_download(self, task: DownloadTask) -> bool:
        """执行单个下载任务（由队列线程调用）

        每个任务创建独立的 VideoDownloader 实例，避免多线程竞态。

        Args:
            task: 下载任务

        Returns:
            下载是否成功
        """
        # 每个任务使用独立的下载器，避免多线程共享导致竞态
        downloader = VideoDownloader(self._settings.ffmpeg_path)

        # 设置进度回调，让 task.progress 随下载实时更新（UI 定时器读取）
        def update_progress(progress: DownloadProgress, message: str) -> None:
            task.progress = progress

        downloader.set_progress_hook(update_progress)

        with self._downloaders_lock:
            self._active_downloaders[task.task_id] = downloader

        try:
            # 执行下载
            success = downloader.download_video(task)
        finally:
            # 清理
            with self._downloaders_lock:
                self._active_downloaders.pop(task.task_id, None)

        # 下载字幕（字幕下载器是线程安全的，仅做 HTTP 请求）
        if task.download_subtitle and task.video_info:
            output_dir = task.output_dir or str(
                Path.home() / "Downloads" / "YouTube"
            )
            try:
                self._subtitle_downloader.download_subtitle(
                    task.url,
                    output_dir,
                    language=task.subtitle_language,
                    subtitle_format=task.subtitle_format,
                    auto_subtitle=task.subtitle_auto,
                    output_filename=sanitize_filename(task.video_info.title),
                )
            except Exception as e:
                logger.warning(f"字幕下载失败: {e}")

        # 下载封面
        if task.download_thumbnail and task.video_info:
            output_dir = task.output_dir or str(
                Path.home() / "Downloads" / "YouTube"
            )
            try:
                self._thumbnail_downloader.download_thumbnail(
                    task.url,
                    output_dir,
                    output_format=task.thumbnail_format,
                    output_filename=sanitize_filename(task.video_info.title),
                )
            except Exception as e:
                logger.warning(f"封面下载失败: {e}")

        return success

    def _on_download_progress(
        self,
        task: DownloadTask,
        progress: DownloadProgress,
        message: str,
    ) -> None:
        """下载进度回调（在下载线程中调用）

        Args:
            task: 下载任务
            progress: 进度信息
            message: 状态消息
        """
        # 使用信号安全地更新 UI (通过定时器轮询)
        pass  # UI 由 _progress_timer 定期刷新

    # ========== 播放列表操作 ==========

    def _populate_playlist_table(self, videos: List[VideoInfo]) -> None:
        """填充播放列表表格

        Args:
            videos: 视频信息列表
        """
        table = self._playlist_table
        table.setRowCount(len(videos))

        for i, video in enumerate(videos):
            # 复选框
            cb_item = QTableWidgetItem()
            cb_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable |
                Qt.ItemFlag.ItemIsEnabled |
                Qt.ItemFlag.ItemIsSelectable
            )
            cb_item.setCheckState(Qt.CheckState.Checked)
            table.setItem(i, 0, cb_item)

            # 序号
            table.setItem(i, 1, QTableWidgetItem(str(i + 1)))
            # 标题
            table.setItem(i, 2, QTableWidgetItem(video.title))
            # 作者
            table.setItem(i, 3, QTableWidgetItem(video.author))
            # 时长
            table.setItem(i, 4, QTableWidgetItem(video.duration_str))

    def _get_selected_playlist_videos(self) -> List[VideoInfo]:
        """获取播放列表中被勾选的视频

        Returns:
            被选中的视频信息列表
        """
        selected = []
        for i in range(self._playlist_table.rowCount()):
            cb_item = self._playlist_table.item(i, 0)
            if cb_item and cb_item.checkState() == Qt.CheckState.Checked:
                if i < len(self._playlist_videos):
                    selected.append(self._playlist_videos[i])
        return selected

    def _on_select_all(self) -> None:
        """全选播放列表"""
        for i in range(self._playlist_table.rowCount()):
            item = self._playlist_table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _on_deselect_all(self) -> None:
        """取消全选播放列表"""
        for i in range(self._playlist_table.rowCount()):
            item = self._playlist_table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _on_download_selected(self) -> None:
        """下载选中的播放列表视频"""
        self._start_playlist_download()

    # ========== 进度表操作 ==========

    def _refresh_progress_table(self) -> None:
        """刷新进度列表显示"""
        tasks = self._download_queue.get_all_tasks()
        table = self._progress_table
        table.setRowCount(len(tasks))

        for i, task in enumerate(tasks):
            # 任务名称
            title = task.video_info.title if task.video_info else task.url[:50]
            table.setItem(i, 0, QTableWidgetItem(title))

            # 状态
            status_item = QTableWidgetItem(task.status.value)
            if task.status == TaskStatus.COMPLETED:
                status_item.setForeground(QColor("#4CAF50"))
            elif task.status == TaskStatus.FAILED:
                status_item.setForeground(QColor("#F44336"))
            elif task.status in (TaskStatus.DOWNLOADING, TaskStatus.MERGING):
                status_item.setForeground(QColor("#2196F3"))
            elif task.status == TaskStatus.CANCELLED:
                status_item.setForeground(QColor("#FF9800"))
            table.setItem(i, 1, status_item)

            # 速度
            table.setItem(i, 2, QTableWidgetItem(task.progress.speed_str))

            # 已下载/总大小
            size_text = f"{task.progress.downloaded_str} / {task.progress.total_str}"
            table.setItem(i, 3, QTableWidgetItem(size_text))

            # 进度条
            progress_widget = QProgressBar()
            progress_widget.setRange(0, 100)
            progress_widget.setValue(int(task.progress.percent))
            progress_widget.setTextVisible(True)
            progress_widget.setFormat(f"{task.progress.percent:.1f}%")
            table.setCellWidget(i, 4, progress_widget)

            # 操作按钮
            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.MERGING):
                cancel_btn = QPushButton("取消")
                cancel_btn.setFixedSize(60, 24)
                cancel_btn.clicked.connect(
                    lambda checked, tid=task.task_id: self._cancel_single_task(tid)
                )
                table.setCellWidget(i, 5, cancel_btn)
            elif task.status == TaskStatus.FAILED:
                retry_btn = QPushButton("重试")
                retry_btn.setFixedSize(60, 24)
                retry_btn.clicked.connect(
                    lambda checked, tid=task.task_id: self._retry_single_task(tid)
                )
                table.setCellWidget(i, 5, retry_btn)
            elif task.status == TaskStatus.COMPLETED:
                table.setItem(i, 5, QTableWidgetItem("✅"))
            else:
                table.setItem(i, 5, QTableWidgetItem("-"))

    @Slot()
    def _refresh_progress_display(self) -> None:
        """定时刷新进度显示（由 QTimer 触发）"""
        try:
            if self._download_queue.task_count > 0:
                self._refresh_progress_table()
        except Exception:
            pass  # 防止定时器回调异常导致崩溃

    def _cancel_single_task(self, task_id: str) -> None:
        """取消单个任务

        Args:
            task_id: 任务 ID
        """
        # 取消对应的下载器
        downloader = self._active_downloaders.get(task_id)
        if downloader:
            downloader.cancel()
        self._download_queue.cancel_task(task_id)
        self._status_bar.showMessage(f"已取消任务: {task_id}")

    def _retry_single_task(self, task_id: str) -> None:
        """重试单个任务

        Args:
            task_id: 任务 ID
        """
        task = self._download_queue.get_task(task_id)
        if task:
            task.reset_progress()
            self._download_queue.add_task(task)
            self._ensure_queue_running()
            self._status_bar.showMessage(f"正在重试: {task_id}")

    def _on_pause_all(self) -> None:
        """全部暂停"""
        with self._downloaders_lock:
            downloaders = list(self._active_downloaders.values())
        for downloader in downloaders:
            downloader.pause()
        self._status_bar.showMessage("已暂停所有下载")

    def _on_resume_all(self) -> None:
        """全部恢复"""
        with self._downloaders_lock:
            downloaders = list(self._active_downloaders.values())
        for downloader in downloaders:
            downloader.resume()
        self._status_bar.showMessage("已恢复下载")

    def _on_cancel_all(self) -> None:
        """全部取消"""
        reply = QMessageBox.question(
            self,
            "确认取消",
            "确定要取消所有下载任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            with self._downloaders_lock:
                downloaders = list(self._active_downloaders.values())
            for downloader in downloaders:
                downloader.cancel()
            self._download_queue.stop()
            self._refresh_progress_table()
            self._status_bar.showMessage("已取消所有任务")

    def _on_clear_completed(self) -> None:
        """清空已完成的任务"""
        count = self._download_queue.clear_completed()
        self._refresh_progress_table()
        self._status_bar.showMessage(f"已清除 {count} 个已完成任务")

    def _on_retry_failed(self) -> None:
        """重试所有失败的任务"""
        count = self._download_queue.retry_failed(self._execute_download)
        if count > 0:
            self._ensure_queue_running()
            self._status_bar.showMessage(f"正在重试 {count} 个失败任务")
        else:
            self._status_bar.showMessage("没有失败的任务需要重试")

    # ========== 回调 ==========

    def _on_task_started(self, task: DownloadTask) -> None:
        """任务开始回调"""
        pass  # UI 由定时器刷新

    def _on_task_completed(self, task: DownloadTask) -> None:
        """任务完成回调"""
        self._status_bar.showMessage(
            f"✅ 下载完成: {task.video_info.title[:40] if task.video_info else task.task_id}",
            5000,
        )

    def _on_task_failed(self, task: DownloadTask) -> None:
        """任务失败回调"""
        self._status_bar.showMessage(
            f"❌ 下载失败: {task.video_info.title[:40] if task.video_info else task.task_id}",
            8000,
        )

    def _on_all_completed(self) -> None:
        """全部任务完成回调"""
        QMessageBox.information(
            self, "下载完成", "所有下载任务已完成！"
        )
        self._status_bar.showMessage("全部下载任务已完成！")

    # ========== UI 更新辅助方法 ==========

    def _display_video_info(self, info: VideoInfo) -> None:
        """在视频页面显示视频信息

        Args:
            info: 视频信息对象
        """
        self._title_label.setText(info.title)
        self._author_label.setText(info.author)
        self._duration_label.setText(info.duration_str)
        self._upload_date_label.setText(info.upload_date_str)

    def _populate_format_combos(self, formats: List[VideoFormat]) -> None:
        """填充格式下拉框

        FFmpeg 可用时：所有格式可选，视频优先
        FFmpeg 不可用时：优先显示含音频的合并格式，标记纯视频格式

        Args:
            formats: 可用格式列表
        """
        ffmpeg_ok = self._ffmpeg_merger.is_available

        # ===== 视频格式 =====
        self._video_format_combo.clear()

        # 分类
        combined = [f for f in formats if f.has_video and f.has_audio]
        video_only = [f for f in formats if f.has_video and not f.has_audio]

        if ffmpeg_ok:
            # FFmpeg 可用：所有格式自由选择（按分辨率排序）
            all_video = sorted(
                combined + video_only,
                key=lambda f: (f.resolution_int, f.has_audio)
            )
            for fmt in all_video:
                self._video_format_combo.addItem(fmt.display_name, fmt)
        else:
            # FFmpeg 不可用：合并格式优先，纯视频格式标为不可用
            for fmt in combined:
                self._video_format_combo.addItem(fmt.display_name, fmt)

            if video_only:
                # 添加分隔线和标记
                self._video_format_combo.insertSeparator(
                    self._video_format_combo.count()
                )
                for fmt in video_only:
                    label = f"{fmt.display_name} ⚠ (需要 FFmpeg 合并)"
                    self._video_format_combo.addItem(label, fmt)

        # 如果没有任何格式
        if self._video_format_combo.count() == 0:
            for fmt in formats:
                if fmt.has_video:
                    self._video_format_combo.addItem(fmt.display_name, fmt)

        # ===== 音频格式 =====
        self._audio_format_combo.clear()
        audio_formats = [f for f in formats if f.is_audio_only]
        if audio_formats:
            # 按比特率降序排列
            audio_formats.sort(key=lambda f: f.abr, reverse=True)
            for fmt in audio_formats:
                self._audio_format_combo.addItem(fmt.display_name, fmt)
        else:
            self._audio_format_combo.addItem("默认最佳音频")

    # ========== 菜单操作 ==========

    def _open_settings(self) -> None:
        """打开设置窗口"""
        dialog = SettingsWindow(self)
        if dialog.exec():
            # 设置已保存，重新加载
            self._settings = self._settings_manager.settings

            # 更新下载队列配置
            self._download_queue.max_workers = self._settings.max_workers

            # 更新 FFmpeg
            self._video_downloader = VideoDownloader(
                self._settings.ffmpeg_path
            )
            self._ffmpeg_merger.ffmpeg_path = self._settings.ffmpeg_path

            # 重新应用主题
            self._apply_theme()

            # 更新状态栏
            self._thread_label.setText(
                f"线程: {self._settings.max_workers}"
            )
            self._update_ffmpeg_status_label()
            self._status_bar.showMessage("设置已更新", 3000)

    def _open_about(self) -> None:
        """打开关于窗口"""
        dialog = AboutWindow(self)
        dialog.exec()

    def _open_download_dir(self) -> None:
        """打开下载目录"""
        download_dir = (
            self._settings.download_dir
            or str(Path.home() / "Downloads" / "YouTube")
        )
        # 确保目录存在
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(download_dir))

    def _check_ffmpeg_status(self) -> None:
        """检查并显示 FFmpeg 状态，缺失时提供自动安装选项"""
        if self._ffmpeg_merger.is_available:
            QMessageBox.information(
                self,
                "FFmpeg 状态",
                f"FFmpeg 已就绪\n\n路径: {self._ffmpeg_merger.ffmpeg_path}\n\n"
                "高清视频音视频合并功能可用。"
            )
        else:
            reply = QMessageBox.question(
                self,
                "FFmpeg 未检测到",
                "FFmpeg 未检测到\n\n"
                "高清视频 (1080p+) 需要 FFmpeg 合并音视频。\n\n"
                "是否自动下载安装 FFmpeg？\n"
                "(约 30MB，需要网络连接)\n\n"
                "选'否'将手动指定路径。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._auto_install_ffmpeg()

    def _auto_install_ffmpeg(self) -> None:
        """自动下载并安装 FFmpeg

        在后台线程中执行下载安装，通过进度对话框显示状态。
        安装成功后自动更新设置和状态。
        """
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import QThread, Signal
        from pathlib import Path

        class InstallThread(QThread):
            progress_signal = Signal(str, float)
            finished_signal = Signal(bool, str)

            def __init__(self):
                super().__init__()
                self._installer = None

            def run(self) -> None:
                try:
                    install_dir = Path.home() / ".youtube_downloader_pro" / "ffmpeg"
                    self._installer = FFmpegInstaller(install_dir)
                    self._installer.set_progress_callback(
                        lambda msg, pct: self.progress_signal.emit(msg, pct)
                    )
                    success = self._installer.install()
                    if success:
                        self.finished_signal.emit(
                            True, str(self._installer.ffmpeg_exe_path)
                        )
                    else:
                        self.finished_signal.emit(
                            False, "安装失败，请检查网络连接后重试"
                        )
                except Exception as e:
                    self.finished_signal.emit(False, str(e))

            def cancel(self) -> None:
                if self._installer:
                    self._installer.cancel()

        progress_dialog = QProgressDialog(
            "准备安装 FFmpeg...", "取消", 0, 100, self,
        )
        progress_dialog.setWindowTitle("安装 FFmpeg")
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)

        install_thread = InstallThread()
        install_thread.progress_signal.connect(
            lambda msg, pct: (
                progress_dialog.setLabelText(msg),
                progress_dialog.setValue(int(pct)),
            )
        )

        def on_finished(success: bool, result: str) -> None:
            progress_dialog.close()
            if success:
                self._settings.ffmpeg_path = result
                self._settings_manager.save(self._settings)
                self._ffmpeg_merger.ffmpeg_path = result
                self._video_downloader = VideoDownloader(result)
                self._update_ffmpeg_status_label()
                self._status_bar.showMessage(
                    f"FFmpeg 安装成功！路径: {result}", 8000
                )
                QMessageBox.information(
                    self, "安装成功",
                    f"FFmpeg 已成功安装！\n\n路径: {result}\n\n"
                    "现在可以下载高清视频并进行音视频合并了。"
                )
            else:
                self._status_bar.showMessage(
                    f"FFmpeg 安装失败: {result}", 8000
                )
                QMessageBox.warning(
                    self, "安装失败",
                    f"FFmpeg 自动安装失败:\n\n{result}\n\n"
                    "请手动安装 FFmpeg:\n"
                    "https://ffmpeg.org/download.html\n\n"
                    "或在设置中手动指定 FFmpeg 路径。"
                )

        install_thread.finished_signal.connect(on_finished)
        progress_dialog.canceled.connect(install_thread.cancel)
        install_thread.start()

    def _update_ffmpeg_status_label(self) -> None:
        """更新状态栏 FFmpeg 图标和提示"""
        if self._ffmpeg_merger.is_available:
            self._ffmpeg_status_label.setText("FFmpeg ✅")
            self._ffmpeg_status_label.setStyleSheet("color: #4CAF50;")
            self._auto_merge_cb.setEnabled(True)
        else:
            self._ffmpeg_status_label.setText("FFmpeg ❌ (点击安装)")
            self._ffmpeg_status_label.setStyleSheet(
                "color: #F44336; font-weight: bold;"
            )
            self._auto_merge_cb.setChecked(False)
            self._auto_merge_cb.setEnabled(False)
            # 启动时在状态栏提示
            self._status_bar.showMessage(
                "⚠ FFmpeg 未安装 — 高清视频(1080p+)下载受限。点击菜单 帮助→检查 FFmpeg 状态 可自动安装",
                10000,
            )
