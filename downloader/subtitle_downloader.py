"""字幕下载器模块

支持从 YouTube 下载自动生成字幕和官方手动字幕，
支持多种语言和格式（SRT、VTT）。
"""

import logging
import os
from pathlib import Path
from typing import Optional, List

import yt_dlp
import requests

from ..models.task import SubtitleInfo
from ..utils.user_agents import get_headers

logger = logging.getLogger(__name__)


class SubtitleDownloader:
    """字幕下载器

    负责下载 YouTube 视频的字幕文件，
    支持自动字幕、官方字幕、多种语言和格式。
    """

    # 支持的语言列表
    SUPPORTED_LANGUAGES = {
        "zh": "中文",
        "en": "英文",
        "ja": "日文",
        "ko": "韩文",
        "auto": "自动检测",
    }

    # 支持的格式
    SUPPORTED_FORMATS = ["srt", "vtt"]

    def __init__(self) -> None:
        """初始化字幕下载器"""
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignoreerrors": True,
        }

    def download_subtitle(
        self,
        url: str,
        output_dir: str,
        language: str = "zh",
        subtitle_format: str = "srt",
        auto_subtitle: bool = True,
        output_filename: str = "",
    ) -> Optional[str]:
        """下载字幕文件

        Args:
            url: YouTube 视频 URL
            output_dir: 输出目录
            language: 字幕语言代码
            subtitle_format: 字幕格式 (srt 或 vtt)
            auto_subtitle: 是否使用自动字幕
            output_filename: 输出文件名（不含扩展名），为空则使用视频标题

        Returns:
            下载成功的字幕文件路径，失败返回 None
        """
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # 获取视频信息以确定文件名
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    logger.error("无法获取视频信息用于字幕下载")
                    return None

                video_title = info.get("title", "video")
                safe_title = self._sanitize_filename(video_title)

            # 构建输出文件路径
            if not output_filename:
                output_filename = safe_title

            output_path = Path(output_dir) / f"{output_filename}.{subtitle_format}"

            # 构建字幕下载专用的 yt-dlp 选项
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": auto_subtitle,
                "subtitleslangs": [language],
                "subtitlesformat": subtitle_format,
                "outtmpl": str(Path(output_dir) / f"{output_filename}.%(ext)s"),
                "ignoreerrors": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # 检查字幕文件是否生成
            if output_path.exists():
                logger.info(f"字幕下载成功: {output_path}")
                return str(output_path)

            # 尝试查找其他匹配的字幕文件
            for f in Path(output_dir).glob(f"{output_filename}*.{subtitle_format}"):
                logger.info(f"找到字幕文件: {f}")
                return str(f)

            logger.warning(f"未找到字幕文件: {output_path}")
            return None

        except Exception as e:
            logger.error(f"字幕下载失败: {e}")
            return None

    def download_subtitle_from_url(
        self,
        subtitle_url: str,
        output_path: str,
    ) -> bool:
        """直接从字幕 URL 下载

        用于已获取字幕 URL 的情况。

        Args:
            subtitle_url: 字幕文件 URL
            output_path: 输出文件完整路径

        Returns:
            下载成功返回 True
        """
        try:
            response = requests.get(
                subtitle_url, timeout=30, headers=get_headers()
            )
            response.raise_for_status()

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.info(f"字幕下载成功 (直链): {output_path}")
            return True

        except requests.RequestException as e:
            logger.error(f"直链字幕下载失败: {e}")
            return False

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """清理文件名

        Args:
            filename: 原始文件名

        Returns:
            清理后的文件名
        """
        illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
        import re
        sanitized = re.sub(illegal_chars, "_", filename)
        sanitized = sanitized.strip(". ")
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized or "video"
