"""封面下载器模块

负责下载 YouTube 视频封面/缩略图，
支持 JPG 和 PNG 格式，可自定义输出路径。
"""

import logging
import os
from pathlib import Path
from typing import Optional

import requests
import yt_dlp

from ..utils.user_agents import get_headers

logger = logging.getLogger(__name__)


class ThumbnailDownloader:
    """封面图下载器

    负责下载 YouTube 视频的缩略图/封面图，
    支持从 yt-dlp 提取或直接 HTTP 下载。
    """

    # YouTube 缩略图质量后缀
    QUALITY_SUFFIXES = [
        "maxresdefault",  # 最高分辨率 (1280x720)
        "sddefault",      # 标准分辨率 (640x480)
        "hqdefault",      # 高质量 (480x360)
        "mqdefault",      # 中等质量 (320x180)
        "default",        # 默认 (120x90)
    ]

    def __init__(self) -> None:
        """初始化封面下载器"""
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

    def download_thumbnail(
        self,
        url: str,
        output_dir: str,
        output_format: str = "jpg",
        output_filename: str = "",
    ) -> Optional[str]:
        """下载视频封面图

        Args:
            url: YouTube 视频 URL
            output_dir: 输出目录
            output_format: 图片格式 (jpg 或 png)
            output_filename: 输出文件名（不含扩展名），为空则使用视频标题

        Returns:
            下载成功的图片文件路径，失败返回 None
        """
        try:
            # 获取视频信息
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    logger.error("无法获取视频信息用于封面下载")
                    return None

                thumbnail_url = info.get("thumbnail", "")
                video_title = info.get("title", "video")

            if not thumbnail_url:
                logger.error(f"未找到封面图 URL: {url}")
                return None

            # 确保输出目录存在
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # 确定输出文件名
            if not output_filename:
                safe_title = self._sanitize_filename(video_title)
                output_filename = f"{safe_title}_cover"

            output_path = Path(output_dir) / f"{output_filename}.{output_format}"

            # 下载封面图
            return self._download_image(thumbnail_url, str(output_path))

        except Exception as e:
            logger.error(f"封面下载失败: {e}")
            return None

    def download_thumbnail_hq(
        self,
        video_id: str,
        output_path: str,
    ) -> Optional[str]:
        """下载高质量封面（使用 video_id）

        直接通过 YouTube 图片服务器下载最高质量封面。

        Args:
            video_id: YouTube 视频 ID (11 位字符)
            output_path: 输出文件完整路径

        Returns:
            下载成功的文件路径，失败返回 None
        """
        # 尝试从高到低质量下载
        for quality in self.QUALITY_SUFFIXES:
            thumbnail_url = (
                f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
            )

            result = self._download_image(thumbnail_url, output_path)
            if result:
                return result

        logger.error(f"所有质量的封面图均下载失败: {video_id}")
        return None

    def _download_image(self, image_url: str, output_path: str) -> Optional[str]:
        """通过 HTTP 下载图片

        Args:
            image_url: 图片 URL
            output_path: 输出文件完整路径

        Returns:
            下载成功的文件路径，失败返回 None
        """
        try:
            response = requests.get(
                image_url, timeout=30, headers=get_headers()
            )
            response.raise_for_status()

            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(response.content)

            file_size = os.path.getsize(output_path)
            if file_size < 1000:  # 文件太小，可能不是有效图片
                logger.warning(f"封面图文件可能无效 (大小: {file_size} bytes)")
                os.remove(output_path)
                return None

            logger.info(f"封面下载成功: {output_path} ({file_size} bytes)")
            return output_path

        except requests.RequestException as e:
            logger.debug(f"封面下载 HTTP 错误 {image_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"封面下载异常: {e}")
            return None

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """清理文件名"""
        import re
        illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
        sanitized = re.sub(illegal_chars, "_", filename)
        sanitized = sanitized.strip(". ")
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized or "video"
