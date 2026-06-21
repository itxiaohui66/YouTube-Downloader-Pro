"""下载器模块

提供视频下载、播放列表解析、字幕下载、封面下载、
FFmpeg 合并、FFmpeg 自动安装和队列管理等核心下载功能。
"""

from .format_parser import FormatParser
from .ffmpeg_merger import FFmpegMerger
from .ffmpeg_installer import FFmpegInstaller, auto_install_ffmpeg
from .video_downloader import VideoDownloader
from .playlist_downloader import PlaylistDownloader
from .subtitle_downloader import SubtitleDownloader
from .thumbnail_downloader import ThumbnailDownloader
from .download_queue import DownloadQueue

__all__ = [
    "FormatParser",
    "FFmpegMerger",
    "FFmpegInstaller",
    "auto_install_ffmpeg",
    "VideoDownloader",
    "PlaylistDownloader",
    "SubtitleDownloader",
    "ThumbnailDownloader",
    "DownloadQueue",
]
