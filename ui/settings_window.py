"""设置窗口

提供所有应用配置项的图形化设置界面，
包括下载目录、FFmpeg 配置、并发数、主题等。
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QLineEdit, QFileDialog, QGroupBox,
    QFormLayout, QCheckBox, QFrame, QMessageBox, QWidget,
    QTabWidget, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..models.settings import Settings, ThemeMode
from ..config.settings_manager import get_settings_manager, get_settings
from ..downloader.ffmpeg_merger import FFmpegMerger


class SettingsWindow(QDialog):
    """设置窗口

    以标签页形式组织设置项：
    - 基本设置：下载目录、线程数
    - 格式设置：默认视频/音频格式、字幕选项
    - 高级设置：FFmpeg 路径、代理、限速
    - 外观设置：主题
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化设置窗口

        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(550, 500)
        self.setModal(True)

        # 加载当前设置
        self._settings_manager = get_settings_manager()
        self._settings = self._settings_manager.settings

        # FFmpeg 检测器
        self._ffmpeg_checker = FFmpegMerger(self._settings.ffmpeg_path)

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """构建 UI 布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 标签页
        self._tab_widget = QTabWidget()

        # 创建各个设置页面
        self._tab_widget.addTab(self._create_general_tab(), "📥 基本")
        self._tab_widget.addTab(self._create_format_tab(), "🎬 格式")
        self._tab_widget.addTab(self._create_advanced_tab(), "⚙️ 高级")
        self._tab_widget.addTab(self._create_appearance_tab(), "🎨 外观")

        main_layout.addWidget(self._tab_widget)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("恢复默认")
        reset_btn.setFixedSize(100, 34)
        reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setFixedSize(80, 34)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        """创建基本设置标签页

        Returns:
            基本设置页面组件
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 下载目录组
        dir_group = QGroupBox("下载目录")
        dir_layout = QHBoxLayout(dir_group)

        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("选择视频保存目录...")
        self._dir_edit.setReadOnly(True)
        dir_layout.addWidget(self._dir_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_btn)

        layout.addWidget(dir_group)

        # 默认目录
        default_dir = str(Path.home() / "Downloads" / "YouTube")
        dir_hint = QLabel(f"默认目录: {default_dir}")
        dir_hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(dir_hint)

        # 线程数组
        thread_group = QGroupBox("下载并发数")
        thread_layout = QHBoxLayout(thread_group)

        thread_label = QLabel("同时下载数:")
        thread_layout.addWidget(thread_label)

        self._thread_spin = QSpinBox()
        self._thread_spin.setRange(1, 32)
        self._thread_spin.setValue(4)
        self._thread_spin.setFixedWidth(80)
        self._thread_spin.setToolTip("设置同时下载的最大任务数 (1-32)")
        thread_layout.addWidget(self._thread_spin)

        thread_layout.addStretch()
        layout.addWidget(thread_group)

        # 启动行为组
        behavior_group = QGroupBox("启动行为")
        behavior_layout = QVBoxLayout(behavior_group)

        self._check_update_cb = QCheckBox("启动时检查更新")
        behavior_layout.addWidget(self._check_update_cb)

        self._minimize_tray_cb = QCheckBox("关闭时最小化到系统托盘")
        behavior_layout.addWidget(self._minimize_tray_cb)

        layout.addWidget(behavior_group)

        layout.addStretch()
        return widget

    def _create_format_tab(self) -> QWidget:
        """创建格式设置标签页

        Returns:
            格式设置页面组件
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 默认视频格式
        video_group = QGroupBox("默认视频格式")
        video_layout = QFormLayout(video_group)

        self._video_format_combo = QComboBox()
        self._video_format_combo.addItems([
            "best (最佳质量)",
            "1080p",
            "720p",
            "480p",
            "360p",
        ])
        video_layout.addRow("视频质量:", self._video_format_combo)

        layout.addWidget(video_group)

        # 默认音频格式
        audio_group = QGroupBox("默认音频格式")
        audio_layout = QFormLayout(audio_group)

        self._audio_format_combo = QComboBox()
        self._audio_format_combo.addItems(["MP3", "M4A", "AAC", "Opus"])
        audio_layout.addRow("音频格式:", self._audio_format_combo)

        layout.addWidget(audio_group)

        # 字幕默认设置
        sub_group = QGroupBox("字幕默认设置")
        sub_layout = QFormLayout(sub_group)

        self._sub_lang_combo = QComboBox()
        self._sub_lang_combo.addItems([
            "中文 (zh)", "English (en)", "日本語 (ja)",
            "한국어 (ko)", "自动检测",
        ])
        sub_layout.addRow("默认语言:", self._sub_lang_combo)

        self._sub_format_combo = QComboBox()
        self._sub_format_combo.addItems(["SRT", "VTT"])
        sub_layout.addRow("默认格式:", self._sub_format_combo)

        self._auto_sub_cb = QCheckBox("优先使用自动生成字幕")
        self._auto_sub_cb.setChecked(True)
        sub_layout.addRow("", self._auto_sub_cb)

        layout.addWidget(sub_group)

        # 自动合并
        merge_group = QGroupBox("音视频合并")
        merge_layout = QVBoxLayout(merge_group)

        self._auto_merge_cb = QCheckBox("高清视频自动合并音视频（需要 FFmpeg）")
        self._auto_merge_cb.setChecked(True)
        merge_layout.addWidget(self._auto_merge_cb)

        layout.addWidget(merge_group)

        layout.addStretch()
        return widget

    def _create_advanced_tab(self) -> QWidget:
        """创建高级设置标签页

        Returns:
            高级设置页面组件
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # FFmpeg 配置
        ffmpeg_group = QGroupBox("FFmpeg 配置")
        ffmpeg_layout = QVBoxLayout(ffmpeg_group)

        ffmpeg_form = QFormLayout()

        path_layout = QHBoxLayout()
        self._ffmpeg_edit = QLineEdit()
        self._ffmpeg_edit.setPlaceholderText("自动检测中...")
        self._ffmpeg_edit.setReadOnly(True)
        path_layout.addWidget(self._ffmpeg_edit)

        detect_btn = QPushButton("自动检测")
        detect_btn.setFixedWidth(80)
        detect_btn.clicked.connect(self._detect_ffmpeg)
        path_layout.addWidget(detect_btn)

        browse_ffmpeg_btn = QPushButton("浏览...")
        browse_ffmpeg_btn.setFixedWidth(80)
        browse_ffmpeg_btn.clicked.connect(self._browse_ffmpeg)
        path_layout.addWidget(browse_ffmpeg_btn)

        ffmpeg_form.addRow("FFmpeg 路径:", path_layout)

        self._ffmpeg_status_label = QLabel("状态: 检测中...")
        self._ffmpeg_status_label.setStyleSheet("font-size: 11px;")
        ffmpeg_form.addRow("", self._ffmpeg_status_label)

        ffmpeg_layout.addLayout(ffmpeg_form)
        layout.addWidget(ffmpeg_group)

        # 网络设置
        network_group = QGroupBox("网络设置")
        network_layout = QFormLayout(network_group)

        self._proxy_edit = QLineEdit()
        self._proxy_edit.setPlaceholderText("如: http://127.0.0.1:7890 (留空表示不使用代理)")
        network_layout.addRow("代理服务器:", self._proxy_edit)

        self._cookies_combo = QComboBox()
        self._cookies_combo.addItems([
            "auto (自动尝试 chrome→firefox→edge→brave→opera)",
            "chrome",
            "firefox",
            "edge",
            "brave",
            "opera",
            "不使用",
        ])
        self._cookies_combo.setToolTip(
            "自动读取浏览器 YouTube Cookie。\n"
            "'auto' 模式按顺序尝试多个浏览器，首个成功即使用。\n"
            "注意: Chrome/Edge 运行时可能被锁定，auto 模式会自动回退。"
        )
        network_layout.addRow("浏览器 Cookie:", self._cookies_combo)

        # Cookie 文件选择（比浏览器 Cookie 更可靠）
        cookies_file_layout = QHBoxLayout()
        self._cookies_file_edit = QLineEdit()
        self._cookies_file_edit.setPlaceholderText(
            "选择 YouTube cookies.txt 文件 (Netscape 格式)..."
        )
        self._cookies_file_edit.setReadOnly(True)
        cookies_file_layout.addWidget(self._cookies_file_edit)

        browse_cookies_btn = QPushButton("浏览...")
        browse_cookies_btn.setFixedWidth(80)
        browse_cookies_btn.clicked.connect(self._browse_cookies_file)
        cookies_file_layout.addWidget(browse_cookies_btn)

        clear_cookies_btn = QPushButton("清除")
        clear_cookies_btn.setFixedWidth(60)
        clear_cookies_btn.clicked.connect(lambda: self._cookies_file_edit.clear())
        cookies_file_layout.addWidget(clear_cookies_btn)

        network_layout.addRow("Cookie 文件:", cookies_file_layout)

        cookies_file_hint = QLabel(
            "推荐方式。使用浏览器扩展 (如 Get cookies.txt LOCALLY) 导出，\n"
            "不受浏览器锁定影响。留空则尝试使用上方浏览器 Cookie。"
        )
        cookies_file_hint.setStyleSheet("color: #888; font-size: 11px;")
        network_layout.addRow("", cookies_file_hint)

        self._rate_limit_edit = QLineEdit()
        self._rate_limit_edit.setPlaceholderText("如: 1M, 500K (留空表示不限速)")
        network_layout.addRow("下载限速:", self._rate_limit_edit)

        layout.addWidget(network_group)

        # 重试设置
        retry_group = QGroupBox("重试设置")
        retry_layout = QHBoxLayout(retry_group)

        retry_label = QLabel("失败重试次数:")
        retry_layout.addWidget(retry_label)

        self._retry_spin = QSpinBox()
        self._retry_spin.setRange(0, 10)
        self._retry_spin.setValue(3)
        self._retry_spin.setFixedWidth(80)
        retry_layout.addWidget(self._retry_spin)

        retry_layout.addStretch()
        layout.addWidget(retry_group)

        layout.addStretch()
        return widget

    def _create_appearance_tab(self) -> QWidget:
        """创建外观设置标签页

        Returns:
            外观设置页面组件
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_layout = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems([
            "深色 (Dark)",
            "浅色 (Light)",
            "跟随系统 (System)",
        ])
        theme_layout.addRow("界面主题:", self._theme_combo)

        layout.addWidget(theme_group)

        # 语言设置
        lang_group = QGroupBox("语言设置")
        lang_layout = QFormLayout(lang_group)

        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["简体中文 (zh_CN)"])
        self._lang_combo.setEnabled(False)  # 目前仅支持中文
        lang_layout.addRow("界面语言:", self._lang_combo)

        lang_hint = QLabel("更多语言将在后续版本中添加")
        lang_hint.setStyleSheet("color: #888; font-size: 11px;")
        lang_layout.addRow("", lang_hint)

        layout.addWidget(lang_group)

        layout.addStretch()
        return widget

    def _load_settings(self) -> None:
        """从当前设置加载 UI 控件值"""
        s = self._settings

        # 基本
        if s.download_dir:
            self._dir_edit.setText(s.download_dir)
        self._thread_spin.setValue(s.max_workers)
        self._check_update_cb.setChecked(s.check_update)
        self._minimize_tray_cb.setChecked(s.minimize_to_tray)

        # 格式
        self._auto_sub_cb.setChecked(s.auto_subtitle)
        self._auto_merge_cb.setChecked(s.auto_merge)

        # 高级
        if s.ffmpeg_path:
            self._ffmpeg_edit.setText(s.ffmpeg_path)
        self._proxy_edit.setText(s.proxy)
        # Cookie 浏览器选择
        cookie_index = 0  # 默认 "auto"
        if s.cookies_from_browser == "":
            cookie_index = self._cookies_combo.count() - 1  # "不使用"
        elif s.cookies_from_browser == "auto":
            cookie_index = 0
        else:
            for i in range(self._cookies_combo.count()):
                if self._cookies_combo.itemText(i) == s.cookies_from_browser:
                    cookie_index = i
                    break
        self._cookies_combo.setCurrentIndex(cookie_index)
        self._cookies_file_edit.setText(s.cookies_file)
        self._rate_limit_edit.setText(s.rate_limit)
        self._retry_spin.setValue(s.max_retries)
        self._update_ffmpeg_status()

        # 外观
        theme_map = {
            ThemeMode.DARK: 0,
            ThemeMode.LIGHT: 1,
            ThemeMode.SYSTEM: 2,
        }
        self._theme_combo.setCurrentIndex(theme_map.get(s.theme, 0))

    def _save_settings(self) -> None:
        """保存设置到配置文件"""
        s = self._settings

        # 基本
        s.download_dir = self._dir_edit.text().strip()
        s.max_workers = self._thread_spin.value()
        s.check_update = self._check_update_cb.isChecked()
        s.minimize_to_tray = self._minimize_tray_cb.isChecked()

        # 格式
        s.auto_subtitle = self._auto_sub_cb.isChecked()
        s.auto_merge = self._auto_merge_cb.isChecked()

        # 格式默认值
        video_fmt_map = {
            0: "best", 1: "1080p", 2: "720p", 3: "480p", 4: "360p",
        }
        s.default_video_format = video_fmt_map.get(
            self._video_format_combo.currentIndex(), "best"
        )
        audio_fmt_map = {0: "mp3", 1: "m4a", 2: "aac", 3: "opus"}
        s.default_audio_format = audio_fmt_map.get(
            self._audio_format_combo.currentIndex(), "mp3"
        )
        s.default_subtitle_lang = self._sub_lang_combo.currentText()[:2].lower()
        s.default_subtitle_format = self._sub_format_combo.currentText().lower()

        # 高级
        s.ffmpeg_path = self._ffmpeg_edit.text().strip()
        s.proxy = self._proxy_edit.text().strip()
        # Cookie 浏览器
        cookie_idx = self._cookies_combo.currentIndex()
        cookie_text = self._cookies_combo.currentText()
        if cookie_idx == self._cookies_combo.count() - 1:  # "不使用"
            s.cookies_from_browser = ""
        elif cookie_text.startswith("auto"):
            s.cookies_from_browser = "auto"
        else:
            s.cookies_from_browser = cookie_text
        s.cookies_file = self._cookies_file_edit.text().strip()
        s.rate_limit = self._rate_limit_edit.text().strip()
        s.max_retries = self._retry_spin.value()

        # 外观
        theme_map = {
            0: ThemeMode.DARK,
            1: ThemeMode.LIGHT,
            2: ThemeMode.SYSTEM,
        }
        s.theme = theme_map.get(self._theme_combo.currentIndex(), ThemeMode.DARK)

        # 持久化保存
        if self._settings_manager.save(s):
            QMessageBox.information(self, "设置", "设置已保存！")
            self.accept()
        else:
            QMessageBox.warning(self, "保存失败", "无法保存设置，请检查文件权限。")

    def _reset_settings(self) -> None:
        """重置为默认设置"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要恢复所有设置为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._settings = self._settings_manager.reset()
            self._load_settings()

    def _browse_directory(self) -> None:
        """选择下载目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择下载保存目录",
            self._dir_edit.text() or str(Path.home() / "Downloads"),
        )
        if dir_path:
            self._dir_edit.setText(dir_path)

    def _detect_ffmpeg(self) -> None:
        """自动检测 FFmpeg"""
        merger = FFmpegMerger()
        if merger.is_available:
            self._ffmpeg_edit.setText(merger.ffmpeg_path)
            self._ffmpeg_status_label.setText("✅ 状态: 已检测到 FFmpeg")
            self._ffmpeg_status_label.setStyleSheet(
                "color: #4CAF50; font-size: 11px;"
            )
        else:
            self._ffmpeg_edit.setText("")
            self._ffmpeg_status_label.setText(
                "❌ 状态: 未检测到 FFmpeg，高清视频合并功能不可用"
            )
            self._ffmpeg_status_label.setStyleSheet(
                "color: #F44336; font-size: 11px;"
            )

    def _browse_ffmpeg(self) -> None:
        """手动选择 FFmpeg 可执行文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 FFmpeg 可执行文件",
            "",
            "可执行文件 (ffmpeg.exe ffmpeg);;所有文件 (*.*)",
        )
        if file_path:
            self._ffmpeg_edit.setText(file_path)
            self._ffmpeg_checker.ffmpeg_path = file_path
            self._update_ffmpeg_status()

    def _browse_cookies_file(self) -> None:
        """选择 Cookie 文件（Netscape 格式 txt）"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 YouTube Cookie 文件",
            str(Path.home()),
            "Cookie 文件 (cookies.txt *.txt);;所有文件 (*.*)",
        )
        if file_path:
            self._cookies_file_edit.setText(file_path)

    def _update_ffmpeg_status(self) -> None:
        """更新 FFmpeg 状态显示"""
        if self._ffmpeg_checker.is_available:
            self._ffmpeg_status_label.setText("✅ 状态: FFmpeg 可用")
            self._ffmpeg_status_label.setStyleSheet(
                "color: #4CAF50; font-size: 11px;"
            )
        else:
            self._ffmpeg_status_label.setText(
                "❌ 状态: FFmpeg 不可用，请安装或指定路径"
            )
            self._ffmpeg_status_label.setStyleSheet(
                "color: #F44336; font-size: 11px;"
            )
