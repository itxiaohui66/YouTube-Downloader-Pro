"""关于窗口

显示应用信息、功能列表和开发者信息。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices, QPixmap, QIcon


class AboutWindow(QDialog):
    """关于窗口

    以对话框形式展示 YouTube Downloader Pro 的
    应用信息、功能特性和开发者信息。
    """

    APP_NAME = "YouTube Downloader Pro"
    APP_VERSION = "v1.0.0"
    APP_DESCRIPTION = (
        "一个基于 Python、yt-dlp 和 FFmpeg 开发的\n"
        "YouTube 视频下载工具。"
    )

    FEATURES = [
        "单视频下载 — 支持多种清晰度选择",
        "播放列表下载 — 批量解析与选择性下载",
        "高清视频自动合并 — 自动调用 FFmpeg 合并音视频流",
        "字幕下载 — 支持自动字幕与官方字幕（SRT/VTT）",
        "封面下载 — 高质量封面图保存",
        "多线程下载 — 可配置 1-32 线程并发",
        "下载队列管理 — 暂停/恢复/取消/重试",
        "深色/浅色主题切换",
    ]

    DEVELOPER = "xiaohui"
    DEVELOPER_WEBSITE = "https://www.itxiaohui.top"
    GITHUB_URL = "https://github.com/xiaohui/youtube-downloader-pro"

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化关于窗口

        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle(f"关于 - {self.APP_NAME}")
        self.setFixedSize(500, 620)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """构建 UI 布局"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # ---------- 应用图标和名称 ----------
        title_label = QLabel(self.APP_NAME)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 版本号
        version_label = QLabel(self.APP_VERSION)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(version_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # ---------- 应用描述 ----------
        desc_label = QLabel(self.APP_DESCRIPTION)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(desc_label)

        # ---------- 功能列表 ----------
        features_label = QLabel("✨ 功能特性")
        features_font = QFont()
        features_font.setPointSize(14)
        features_font.setBold(True)
        features_label.setFont(features_font)
        layout.addWidget(features_label)

        for feature in self.FEATURES:
            feat_label = QLabel(f"  • {feature}")
            feat_label.setStyleSheet("font-size: 12px; color: #555;")
            feat_label.setWordWrap(True)
            layout.addWidget(feat_label)

        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line2)

        # ---------- 开发者信息 ----------
        dev_label = QLabel(f"👨‍💻 开发者: {self.DEVELOPER}")
        dev_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(dev_label)

        # 网站链接
        website_layout = QHBoxLayout()
        website_label = QLabel(f"🌐 网站: ")
        website_label.setStyleSheet("font-size: 13px;")
        website_link = QPushButton(self.DEVELOPER_WEBSITE)
        website_link.setFlat(True)
        website_link.setCursor(Qt.CursorShape.PointingHandCursor)
        website_link.setStyleSheet(
            "QPushButton { color: #2196F3; font-size: 13px; border: none; text-decoration: underline; }"
            "QPushButton:hover { color: #1976D2; }"
        )
        website_link.clicked.connect(lambda: self._open_url(self.DEVELOPER_WEBSITE))
        website_layout.addWidget(website_label)
        website_layout.addWidget(website_link)
        website_layout.addStretch()
        layout.addLayout(website_layout)

        # GitHub 链接
        github_layout = QHBoxLayout()
        github_label = QLabel("📦 GitHub: ")
        github_label.setStyleSheet("font-size: 13px;")
        github_link = QPushButton(self.GITHUB_URL)
        github_link.setFlat(True)
        github_link.setCursor(Qt.CursorShape.PointingHandCursor)
        github_link.setStyleSheet(
            "QPushButton { color: #2196F3; font-size: 13px; border: none; text-decoration: underline; }"
            "QPushButton:hover { color: #1976D2; }"
        )
        github_link.clicked.connect(lambda: self._open_url(self.GITHUB_URL))
        github_layout.addWidget(github_label)
        github_layout.addWidget(github_link)
        github_layout.addStretch()
        layout.addLayout(github_layout)

        layout.addStretch()

        # ---------- 关闭按钮 ----------
        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(100, 36)
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _open_url(self, url: str) -> None:
        """在系统浏览器中打开 URL

        Args:
            url: 要打开的网址
        """
        QDesktopServices.openUrl(QUrl(url))
