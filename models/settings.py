"""应用设置数据模型

管理所有用户配置项，包括下载目录、并发数、主题等。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ThemeMode(Enum):
    """主题模式枚举"""
    LIGHT = "浅色"
    DARK = "深色"
    SYSTEM = "跟随系统"


@dataclass
class Settings:
    """应用设置数据模型

    包含所有可配置的应用设置项，支持 JSON 序列化与反序列化。
    """
    # ========== 下载设置 ==========
    download_dir: str = ""  # 下载保存目录，空字符串表示使用默认目录

    # ========== 并发设置 ==========
    max_workers: int = 4  # 最大并发下载数 (1-32)

    # ========== 格式设置 ==========
    default_video_format: str = "best"  # 默认视频格式
    default_audio_format: str = "mp3"  # 默认音频格式
    default_subtitle_lang: str = "zh"  # 默认字幕语言
    default_subtitle_format: str = "srt"  # 默认字幕格式
    auto_subtitle: bool = True  # 是否自动下载字幕
    auto_merge: bool = True  # 是否自动合并音视频

    # ========== 外观设置 ==========
    theme: ThemeMode = ThemeMode.DARK  # 主题模式

    # ========== 高级设置 ==========
    ffmpeg_path: str = ""  # FFmpeg 可执行文件路径，空字符串表示自动检测
    cookies_from_browser: str = "auto"  # 浏览器名称（或逗号分隔列表），"auto"=自动尝试所有，留空=不使用
    cookies_file: str = ""  # Cookie 文件路径（Netscape 格式），优先于 cookies_from_browser
    proxy: str = ""  # 代理服务器地址
    max_retries: int = 3  # 失败重试次数
    rate_limit: str = ""  # 下载限速，如 "1M", "500K"，空字符串表示不限速

    # ========== 界面设置 ==========
    window_width: int = 1200
    window_height: int = 800
    window_x: int = -1  # -1 表示居中
    window_y: int = -1

    # ========== 其他设置 ==========
    language: str = "zh_CN"  # 界面语言
    check_update: bool = True  # 启动时检查更新
    minimize_to_tray: bool = False  # 关闭时最小化到系统托盘

    def to_dict(self) -> dict:
        """将设置序列化为字典"""
        return {
            "download_dir": self.download_dir,
            "max_workers": self.max_workers,
            "default_video_format": self.default_video_format,
            "default_audio_format": self.default_audio_format,
            "default_subtitle_lang": self.default_subtitle_lang,
            "default_subtitle_format": self.default_subtitle_format,
            "auto_subtitle": self.auto_subtitle,
            "auto_merge": self.auto_merge,
            "theme": self.theme.name,
            "ffmpeg_path": self.ffmpeg_path,
            "cookies_from_browser": self.cookies_from_browser,
            "cookies_file": self.cookies_file,
            "proxy": self.proxy,
            "max_retries": self.max_retries,
            "rate_limit": self.rate_limit,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "window_x": self.window_x,
            "window_y": self.window_y,
            "language": self.language,
            "check_update": self.check_update,
            "minimize_to_tray": self.minimize_to_tray,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        """从字典反序列化创建设置对象"""
        settings = cls()

        # 简单字段映射
        str_fields = [
            "download_dir", "default_video_format", "default_audio_format",
            "default_subtitle_lang", "default_subtitle_format",
            "ffmpeg_path", "cookies_from_browser", "cookies_file", "proxy", "rate_limit", "language",
        ]
        for field_name in str_fields:
            if field_name in data:
                setattr(settings, field_name, data[field_name])

        int_fields = ["max_workers", "max_retries", "window_width",
                       "window_height", "window_x", "window_y"]
        for field_name in int_fields:
            if field_name in data:
                setattr(settings, field_name, int(data[field_name]))

        bool_fields = ["auto_subtitle", "auto_merge", "check_update", "minimize_to_tray"]
        for field_name in bool_fields:
            if field_name in data:
                setattr(settings, field_name, bool(data[field_name]))

        # 主题枚举
        if "theme" in data:
            try:
                settings.theme = ThemeMode[data["theme"]]
            except (KeyError, ValueError):
                settings.theme = ThemeMode.DARK

        return settings
