"""播放列表下载器模块

负责解析 YouTube 播放列表，获取所有视频条目信息，
支持单个或批量下载。
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import yt_dlp

from ..models.task import VideoInfo
from ..utils.user_agents import get_random_ua
from .format_parser import (
    FormatParser, _is_cookie_error, _parse_browser_list,
)

logger = logging.getLogger(__name__)


class PlaylistDownloader:
    """播放列表下载器

    负责解析 YouTube 播放列表 URL，提取所有视频条目的基本信息。
    实际下载通过 VideoDownloader 执行。

    Cookie 回退机制：当配置的浏览器 Cookie 读取失败时，
    自动尝试列表中的下一个浏览器。
    """

    def __init__(self, cookies_from_browser: str = "", cookies_file: str = "") -> None:
        """初始化播放列表下载器

        Args:
            cookies_from_browser: 浏览器名称（或逗号分隔的多个），如 "chrome,firefox"
            cookies_file: Cookie 文件路径（Netscape 格式），优先于浏览器 Cookie
        """
        self._cookies_file = cookies_file
        self._browsers = _parse_browser_list(cookies_from_browser)

        self._base_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "ignoreerrors": True,
            "socket_timeout": 30,
            "http_headers": {"User-Agent": get_random_ua()},
        }

        self._last_error: str = ""

    def _build_ydl_opts(self, browser_idx: int = -1) -> Dict[str, Any]:
        """构建 yt-dlp 选项（包含 Cookie 配置）"""
        opts = self._base_opts.copy()
        opts["http_headers"] = {"User-Agent": get_random_ua()}

        if self._cookies_file and Path(self._cookies_file).exists():
            opts["cookiefile"] = self._cookies_file
        elif 0 <= browser_idx < len(self._browsers):
            browser = self._browsers[browser_idx]
            opts["cookiesfrombrowser"] = (browser,)
        return opts

    def _try_extract_info(self, url: str, extra_opts: Dict[str, Any] | None = None):
        """调用 yt-dlp extract_info，Cookie 失败时自动回退

        Args:
            url: YouTube URL
            extra_opts: 额外的 yt-dlp 选项

        Returns:
            yt-dlp info dict

        Raises:
            RuntimeError: 所有方式都失败
        """
        errors: List[str] = []

        def _call_with_opts(opts, use_base=False):
            if use_base:
                merged = self._base_opts.copy()
                merged["http_headers"] = {"User-Agent": get_random_ua()}
            else:
                merged = opts.copy()
            if extra_opts:
                merged.update(extra_opts)
            with yt_dlp.YoutubeDL(merged) as ydl:
                return ydl.extract_info(url, download=False)

        # 第一步：cookies_file
        if self._cookies_file and Path(self._cookies_file).exists():
            try:
                return _call_with_opts(self._build_ydl_opts(browser_idx=-1))
            except Exception as e:
                msg = str(e)
                logger.warning(f"Cookie 文件模式失败: {msg[:100]}")
                errors.append(f"cookies_file: {msg[:120]}")
                # 非 Cookie 错误也不 raise，继续回退

        # 第二步：依次尝试每个浏览器
        for idx, browser in enumerate(self._browsers):
            try:
                info = _call_with_opts(self._build_ydl_opts(browser_idx=idx))
                if info is not None:
                    logger.info(f"播放列表 Cookie 来源: {browser}")
                    return info
            except Exception as e:
                msg = str(e)
                logger.warning(
                    f"浏览器 {browser} Cookie 失败: {msg[:100]}"
                )
                errors.append(f"{browser}: {msg[:120]}")
                if not _is_cookie_error(msg) or idx + 1 >= len(self._browsers):
                    break  # 非 Cookie 错误或已是最后一个浏览器

        # 第三步（最终回退）：不使用任何 Cookie 直接请求
        logger.warning(
            "Cookie 来源均失败或有错误，尝试无 Cookie 模式"
        )
        try:
            return _call_with_opts(None, use_base=True)
        except Exception as e:
            msg = str(e)
            errors.append(f"no_cookies: {msg[:120]}")
            error_summary = "; ".join(errors)
            raise RuntimeError(f"所有方式均失败: {error_summary}")

    def fetch_playlist_info(
        self, url: str, max_videos: int = 0
    ) -> List[VideoInfo]:
        """获取播放列表中的所有视频信息

        Args:
            url: 播放列表 URL
            max_videos: 最大获取视频数，0 表示不限制

        Returns:
            VideoInfo 列表，包含播放列表中每个视频的基本信息
        """
        videos: List[VideoInfo] = []

        try:
            extra = {}
            if max_videos > 0:
                extra["playlist_items"] = f"1-{max_videos}"

            info = self._try_extract_info(url, extra_opts=extra)

            if info is None:
                logger.error(f"无法获取播放列表信息: {url}")
                return videos

            # 获取播放列表标题
            playlist_title = info.get("title", "未命名播放列表")
            logger.info(f"播放列表: {playlist_title}")

            # 提取所有视频条目
            entries = info.get("entries") or []

            # 如果 flat 提取为空，尝试完整提取
            if not entries:
                logger.info("flat 提取为空，尝试完整提取...")
                extra["extract_flat"] = False
                info2 = self._try_extract_info(url, extra_opts=extra)
                if info2:
                    entries = info2.get("entries") or []

            for entry in entries:
                if entry is None:
                    continue

                video_url = entry.get("webpage_url") or entry.get("url") or ""
                if not video_url and entry.get("id"):
                    video_url = f"https://www.youtube.com/watch?v={entry['id']}"

                video_info = VideoInfo(
                    title=entry.get("title", "未知标题"),
                    author=entry.get("uploader", entry.get("channel", "未知作者")),
                    duration=entry.get("duration", 0) or 0,
                    upload_date=str(entry.get("upload_date", "")) if entry.get("upload_date") else "",
                    thumbnail_url=entry.get("thumbnail") or entry.get("thumbnails", [{}])[0].get("url", ""),
                    description=entry.get("description", "") or "",
                    webpage_url=video_url,
                )
                videos.append(video_info)

            logger.info(f"播放列表解析完成，共 {len(videos)} 个视频")
            return videos

        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            logger.error(f"yt-dlp 播放列表解析错误: {msg}")
            self._last_error = FormatParser._format_error(msg)
            return videos
        except Exception as e:
            msg = str(e)
            logger.error(f"播放列表解析异常: {msg}")
            self._last_error = FormatParser._format_error(msg)
            return videos

    @property
    def last_error(self) -> str:
        """获取最后一次错误的详细信息"""
        return self._last_error

    def fetch_playlist_title(self, url: str) -> str:
        """仅获取播放列表标题

        Args:
            url: 播放列表 URL

        Returns:
            播放列表标题，失败返回空字符串
        """
        try:
            info = self._try_extract_info(url)
            return info.get("title", "未命名播放列表") if info else ""
        except Exception as e:
            logger.error(f"获取播放列表标题失败: {e}")
            return ""
