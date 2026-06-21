"""下载任务数据模型

定义下载任务的所有状态、属性和数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid


class TaskStatus(Enum):
    """任务状态枚举"""
    WAITING = "等待中"
    DOWNLOADING = "下载中"
    MERGING = "合并中"
    COMPLETED = "已完成"
    FAILED = "失败"
    PAUSED = "已暂停"
    CANCELLED = "已取消"


class DownloadType(Enum):
    """下载类型枚举"""
    VIDEO = "视频"
    AUDIO = "音频"
    SUBTITLE = "字幕"
    THUMBNAIL = "封面"


@dataclass
class VideoInfo:
    """视频信息数据结构"""
    title: str = ""
    author: str = ""
    duration: int = 0  # 秒
    upload_date: str = ""  # YYYYMMDD 格式
    thumbnail_url: str = ""
    description: str = ""
    webpage_url: str = ""
    view_count: int = 0
    like_count: int = 0

    @property
    def duration_str(self) -> str:
        """格式化时长为 HH:MM:SS"""
        if not self.duration:
            return "未知"
        duration = int(self.duration)  # yt-dlp 可能返回 float
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def upload_date_str(self) -> str:
        """格式化上传日期为 YYYY-MM-DD"""
        if not self.upload_date or len(self.upload_date) != 8:
            return self.upload_date or "未知"
        return f"{self.upload_date[:4]}-{self.upload_date[4:6]}-{self.upload_date[6:8]}"


@dataclass
class VideoFormat:
    """视频格式数据结构"""
    format_id: str = ""
    ext: str = ""  # 文件扩展名，如 mp4, webm
    resolution: str = ""  # 如 1080p
    video_codec: str = ""  # 如 avc1, vp9
    audio_codec: str = ""  # 如 mp4a, opus
    fps: int = 0  # 帧率
    file_size: int = 0  # 字节
    tbr: float = 0.0  # 总比特率 (kbps)
    vbr: float = 0.0  # 视频比特率 (kbps)
    abr: float = 0.0  # 音频比特率 (kbps)
    has_video: bool = True
    has_audio: bool = True
    is_audio_only: bool = False
    note: str = ""  # 格式备注，如 "Premium", "HDR"

    @property
    def resolution_int(self) -> int:
        """获取分辨率高度数值"""
        if not self.resolution:
            return 0
        try:
            return int(self.resolution.lower().replace('p', ''))
        except ValueError:
            return 0

    @property
    def file_size_str(self) -> str:
        """格式化文件大小"""
        if not self.file_size:
            return "未知大小"
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @property
    def display_name(self) -> str:
        """用于 UI 显示的格式名称"""
        parts = []
        # 分辨率/类型
        if self.is_audio_only:
            parts.append(self.ext.upper())
        elif self.resolution:
            parts.append(self.resolution.upper())
        else:
            parts.append(self.ext.upper())

        # 编码
        if self.video_codec:
            parts.append(self.video_codec.upper())
        if self.audio_codec and not self.is_audio_only:
            parts.append(self.audio_codec.upper())

        # 帧率 (仅视频)
        if self.fps and not self.is_audio_only:
            parts.append(f"{self.fps}FPS")

        # 文件大小
        parts.append(self.file_size_str)

        # 备注
        if self.note:
            parts.append(self.note)

        return " | ".join(parts)


@dataclass
class SubtitleInfo:
    """字幕信息数据结构"""
    language: str = ""  # 语言代码，如 zh, en
    language_name: str = ""  # 语言名称，如 中文, English
    is_auto: bool = False  # 是否为自动生成字幕
    ext: str = "vtt"  # 字幕格式
    url: str = ""


@dataclass
class DownloadProgress:
    """下载进度数据结构"""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0  # 字节/秒
    percent: float = 0.0  # 0-100
    eta: int = 0  # 预计剩余秒数
    status: str = ""  # 进度状态描述

    @property
    def speed_str(self) -> str:
        """格式化下载速度"""
        if not self.speed:
            return "计算中..."
        speed = self.speed
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed < 1024:
                return f"{speed:.1f} {unit}"
            speed /= 1024
        return f"{speed:.1f} TB/s"

    @property
    def downloaded_str(self) -> str:
        """格式化已下载大小"""
        size = self.downloaded_bytes
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @property
    def total_str(self) -> str:
        """格式化总大小"""
        if not self.total_bytes:
            return "未知"
        size = self.total_bytes
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @property
    def eta_str(self) -> str:
        """格式化剩余时间"""
        if not self.eta:
            return "计算中..."
        eta = self.eta
        if eta < 60:
            return f"{eta} 秒"
        elif eta < 3600:
            return f"{eta // 60} 分 {eta % 60} 秒"
        else:
            hours = eta // 3600
            minutes = (eta % 3600) // 60
            return f"{hours} 时 {minutes} 分"


@dataclass
class DownloadTask:
    """下载任务数据模型

    封装单个下载任务的所有信息，包括视频信息、格式选择、
    进度跟踪和状态管理。
    """
    # 唯一标识
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # URL 信息
    url: str = ""
    is_playlist: bool = False

    # 视频信息
    video_info: Optional[VideoInfo] = None

    # 下载配置
    selected_format: Optional[VideoFormat] = None
    download_video: bool = True
    download_audio: bool = False
    download_subtitle: bool = False
    download_thumbnail: bool = False
    subtitle_language: str = "zh"  # 字幕语言代码
    subtitle_format: str = "srt"  # 字幕文件格式
    subtitle_auto: bool = True  # 是否使用自动字幕
    thumbnail_format: str = "jpg"  # 封面图格式

    # 输出配置
    output_dir: str = ""
    output_filename: str = ""

    # 状态
    status: TaskStatus = TaskStatus.WAITING
    progress: DownloadProgress = field(default_factory=DownloadProgress)
    error_message: str = ""

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 额外数据
    extra_data: dict = field(default_factory=dict)

    def reset_progress(self) -> None:
        """重置进度信息"""
        self.progress = DownloadProgress()
        self.status = TaskStatus.WAITING
        self.error_message = ""
        self.started_at = None
        self.completed_at = None
