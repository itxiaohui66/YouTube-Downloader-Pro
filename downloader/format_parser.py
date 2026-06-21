"""视频格式解析模块

使用 yt-dlp 提取视频信息，解析所有可用的视频/音频格式，
并输出结构化的格式数据供 UI 展示和下载选择。
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import yt_dlp

from ..models.task import VideoInfo, VideoFormat, SubtitleInfo
from ..utils.user_agents import get_random_ua

logger = logging.getLogger(__name__)

# 自动回退的浏览器列表（按优先级）
_DEFAULT_FALLBACK_BROWSERS = ["chrome", "firefox", "edge", "brave", "opera"]


def _is_cookie_error(msg: str) -> bool:
    """判断错误是否为 Cookie 相关（可回退到下一个浏览器）

    Args:
        msg: 错误消息

    Returns:
        True 表示可以尝试下一个浏览器
    """
    msg_lower = msg.lower()
    return (
        "sign in to confirm" in msg_lower
        or "failed to load cookies" in msg_lower
        or "could not copy" in msg_lower
        or "cookie" in msg_lower
    )


def _parse_browser_list(raw: str) -> List[str]:
    """解析逗号分隔的浏览器列表

    Args:
        raw: 如 "chrome,firefox,edge" 或 "auto"

    Returns:
        浏览器名称列表
    """
    if not raw or not raw.strip():
        return []
    stripped = raw.strip()
    if stripped == "auto":
        return list(_DEFAULT_FALLBACK_BROWSERS)
    browsers = [b.strip() for b in stripped.split(",") if b.strip()]
    return browsers or []


class FormatParser:
    """视频格式解析器

    负责通过 yt-dlp 提取视频元数据和可用格式列表，
    支持视频信息获取、格式过滤和字幕列表获取。

    Cookie 回退机制：当配置的浏览器 Cookie 读取失败时，
    自动尝试列表中的下一个浏览器，直到成功或全部失败。
    """

    # 视频分辨率优先级 (从低到高)
    RESOLUTION_ORDER = [
        "144p", "240p", "360p", "480p", "720p",
        "1080p", "1440p", "2160p", "4320p",
    ]

    # 音频格式代码映射
    AUDIO_FORMAT_MAP = {
        "mp3": {"ext": "mp3", "acodec": "mp3", "preference": 1},
        "m4a": {"ext": "m4a", "acodec": "mp4a", "preference": 2},
        "aac": {"ext": "aac", "acodec": "aac", "preference": 3},
        "opus": {"ext": "opus", "acodec": "opus", "preference": 4},
    }

    def __init__(self, cookies_from_browser: str = "", cookies_file: str = "") -> None:
        """初始化格式解析器

        Args:
            cookies_from_browser: 浏览器名称（或逗号分隔的多个名称），如 "chrome,firefox"
            cookies_file: Cookie 文件路径（Netscape 格式），优先于浏览器 Cookie
        """
        self._cookies_file = cookies_file
        self._browsers = _parse_browser_list(cookies_from_browser)

        # 基础选项（不含 Cookie 配置，每次 _build_ydl_opts 时动态添加）
        self._base_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "ignoreerrors": True,
            "socket_timeout": 30,
            "http_headers": {"User-Agent": get_random_ua()},
            # 跳过播放列表 tab 的认证检查（video URL 带 ?list= 时触发）
            "extractor_args": {"youtubetab": {"skip": ["authcheck"]}},
            # 启用 Node.js 作为 JS 运行时 + 远程挑战求解器（解析现代 YouTube 页面）
            "js_runtimes": {"node": {}, "deno": {}},
            "remote_components": ["ejs:github"],
        }

        self._last_error: str = ""

    def _build_ydl_opts(self, browser_idx: int = -1) -> Dict[str, Any]:
        """构建 yt-dlp 选项（包含 Cookie 配置）

        Args:
            browser_idx: 浏览器列表索引，-1 表示仅使用 cookies_file

        Returns:
            yt-dlp 选项字典
        """
        opts = self._base_opts.copy()
        # 每次构建都刷新 User-Agent
        opts["http_headers"] = {"User-Agent": get_random_ua()}

        # Cookie 文件优先
        if self._cookies_file and Path(self._cookies_file).exists():
            opts["cookiefile"] = self._cookies_file
        elif 0 <= browser_idx < len(self._browsers):
            browser = self._browsers[browser_idx]
            opts["cookiesfrombrowser"] = (browser,)
        return opts

    def _try_extract_info(self, url: str):
        """调用 yt-dlp extract_info，Cookie 失败时自动回退到下一个浏览器

        回退流程：
        1. 优先使用 cookies_file（如果存在）
        2. 依次尝试浏览器列表中的每个浏览器
        3. 遇到 Cookie 相关错误时自动跳到下一个浏览器
        4. 成功后缓存工作浏览器，后续调用直接使用
        5. 全部失败则抛出最后一个错误

        Args:
            url: YouTube URL

        Returns:
            yt-dlp info dict

        Raises:
            RuntimeError: 所有浏览器都失败
        """
        errors: List[str] = []

        # 第一步：尝试 cookies_file
        if self._cookies_file and Path(self._cookies_file).exists():
            try:
                opts = self._build_ydl_opts(browser_idx=-1)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)
            except Exception as e:
                msg = str(e)
                logger.warning(f"Cookie 文件模式失败: {msg[:100]}")
                errors.append(f"cookies_file: {msg[:120]}")
                # 非 Cookie 错误也不 raise，继续回退到浏览器或无 Cookie 模式

        # 第二步：依次尝试浏览器列表
        for idx, browser in enumerate(self._browsers):
            try:
                opts = self._build_ydl_opts(browser_idx=idx)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info is not None:
                        logger.info(f"Cookie 来源: {browser}")
                        return info
            except Exception as e:
                msg = str(e)
                logger.warning(
                    f"浏览器 {browser} Cookie 失败，尝试下一个: {msg[:100]}"
                )
                errors.append(f"{browser}: {msg[:120]}")
                if not _is_cookie_error(msg) or idx + 1 >= len(self._browsers):
                    break  # 非 Cookie 错误或已是最后一个浏览器，跳出循环

        # 第三步（最终回退）：不使用任何 Cookie 直接请求
        logger.warning(
            "Cookie 来源均失败或有错误，尝试无 Cookie 模式（可能触发 YouTube 验证）"
        )
        try:
            opts = self._base_opts.copy()
            opts["http_headers"] = {"User-Agent": get_random_ua()}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            msg = str(e)
            errors.append(f"no_cookies: {msg[:120]}")
            error_summary = "; ".join(errors)
            raise RuntimeError(f"所有方式均失败: {error_summary}")

    def fetch_video_info(self, url: str) -> Optional[VideoInfo]:
        """获取视频基本信息

        Args:
            url: YouTube 视频 URL

        Returns:
            VideoInfo 对象，失败返回 None（可通过 last_error 获取错误详情）
        """
        try:
            info = self._try_extract_info(url)

            if info is None:
                msg = f"无法获取视频信息: {url}"
                logger.error(msg)
                self._last_error = msg
                return None

            return VideoInfo(
                title=info.get("title", "未知标题"),
                author=info.get("uploader", info.get("channel", "未知作者")),
                duration=info.get("duration", 0) or 0,
                upload_date=str(info.get("upload_date", "")) if info.get("upload_date") else "",
                thumbnail_url=info.get("thumbnail", ""),
                description=info.get("description", "") or "",
                webpage_url=info.get("webpage_url", url),
                view_count=info.get("view_count", 0) or 0,
                like_count=info.get("like_count", 0) or 0,
            )

        except Exception as e:
            msg = str(e)
            logger.error(f"获取视频信息异常: {msg}")
            self._last_error = self._format_error(msg)
            return None

    @property
    def last_error(self) -> str:
        """获取最后一次错误的详细信息"""
        return self._last_error

    @staticmethod
    def _format_error(msg: str) -> str:
        """格式化 yt-dlp 错误信息为用户友好的提示

        Args:
            msg: 原始错误信息

        Returns:
            格式化后的错误信息
        """
        if "Sign in to confirm" in msg:
            return (
                "YouTube 要求验证身份。\n\n"
                "解决方法：\n"
                "  1. 设置 → 高级 → Cookie 文件 → 选择 cookies.txt\n"
                "     (推荐：使用浏览器扩展 Get cookies.txt LOCALLY 导出)\n"
                "  2. 设置 → 高级 → 浏览器 Cookie → 选择浏览器\n"
                "     (注意：Chrome/Edge 运行时可能被锁定，请先关闭浏览器)\n\n"
                "详见 yt-dlp 文档: https://git.io/JUwuq"
            )
        if "failed to load cookies" in msg.lower():
            return (
                f"无法读取浏览器 Cookie（已自动尝试多个浏览器）。\n\n"
                f"可能原因：所有浏览器均在运行中导致数据库被锁定。\n\n"
                f"解决方法：\n"
                f"  1. 关闭浏览器后重试\n"
                f"  2. 使用 Cookie 文件方式：设置 → 高级 → Cookie 文件\n"
                f"     (推荐：使用浏览器扩展 Get cookies.txt LOCALLY 导出)\n\n"
                f"原始错误: {msg[:200]}"
            )
        if "所有方式均失败" in msg:
            return (
                "所有 Cookie 来源和无 Cookie 模式均失败。\n\n"
                "建议：\n"
                "  1. 使用 Cookie 文件（最可靠）：\n"
                "     设置 → 高级 → Cookie 文件 → 浏览...\n"
                "     (浏览器扩展 Get cookies.txt LOCALLY 导出)\n"
                "  2. 在设置中关闭 Cookie 功能：\n"
                "     设置 → 高级 → 浏览器 Cookie → 选择「不使用」\n"
                "     （部分视频可能仍可下载）\n\n"
                f"详情: {msg[:200]}"
            )
        return msg[:500]

    def fetch_formats(self, url: str) -> List[VideoFormat]:
        """获取视频所有可用格式

        提取所有视频和音频格式，去重并排序。

        Args:
            url: YouTube 视频 URL

        Returns:
            VideoFormat 列表
        """
        all_formats: List[VideoFormat] = []
        seen_formats: Dict[str, set] = {
            "video": set(),
            "audio": set(),
        }

        try:
            info = self._try_extract_info(url)

            if info is None or "formats" not in info:
                return all_formats

            formats = info["formats"]

            for fmt in formats:
                if fmt is None:
                    continue

                video_format = self._parse_single_format(fmt)

                if video_format and self._is_unique_format(
                    video_format, seen_formats
                ):
                    all_formats.append(video_format)

            # 按分辨率排序
            all_formats.sort(key=lambda f: self._sort_key(f))
            logger.info(f"解析到 {len(all_formats)} 个可用格式")

        except Exception as e:
            logger.error(f"获取格式列表异常: {e}")

        return all_formats

    def fetch_audio_formats(self, url: str) -> List[VideoFormat]:
        """获取仅音频格式列表

        提取纯音频格式，适合只需要音频的用户。

        Args:
            url: YouTube 视频 URL

        Returns:
            仅包含音频的 VideoFormat 列表
        """
        all_formats = self.fetch_formats(url)
        return [f for f in all_formats if f.is_audio_only]

    def fetch_video_only_formats(self, url: str) -> List[VideoFormat]:
        """获取仅视频格式列表（不含音频）

        提取只有视频流的格式，适合需要手动合并高清视频的场景。

        Args:
            url: YouTube 视频 URL

        Returns:
            仅包含视频的 VideoFormat 列表
        """
        all_formats = self.fetch_formats(url)
        return [f for f in all_formats if f.has_video and not f.has_audio]

    def fetch_combined_formats(self, url: str) -> List[VideoFormat]:
        """获取音视频合并格式列表

        提取同时包含音频和视频的格式，可直接下载无需合并。

        Args:
            url: YouTube 视频 URL

        Returns:
            包含音视频的 VideoFormat 列表
        """
        all_formats = self.fetch_formats(url)
        return [f for f in all_formats if f.has_video and f.has_audio]

    def fetch_subtitles(self, url: str) -> List[SubtitleInfo]:
        """获取可用字幕列表

        Args:
            url: YouTube 视频 URL

        Returns:
            SubtitleInfo 列表
        """
        subtitles: List[SubtitleInfo] = []

        # 语言名称映射
        language_names = {
            "zh": "中文", "zh-Hans": "中文(简体)", "zh-Hant": "中文(繁体)",
            "en": "English", "ja": "日本語", "ko": "한국어",
            "fr": "Français", "de": "Deutsch", "es": "Español",
            "ru": "Русский", "pt": "Português", "ar": "العربية",
            "th": "ไทย", "vi": "Tiếng Việt", "id": "Bahasa Indonesia",
        }

        try:
            info = self._try_extract_info(url)

            if info is None:
                return subtitles

            # 自动字幕
            auto_subs = info.get("automatic_captions", {}) or {}
            for lang_code, subs in auto_subs.items():
                for sub in subs:
                    if sub.get("ext") in ("vtt", "srt", "ttml"):
                        subtitles.append(SubtitleInfo(
                            language=lang_code,
                            language_name=language_names.get(
                                lang_code, lang_code
                            ),
                            is_auto=True,
                            ext=sub.get("ext", "vtt"),
                            url=sub.get("url", ""),
                        ))

            # 手动字幕 (官方字幕)
            manual_subs = info.get("subtitles", {}) or {}
            for lang_code, subs in manual_subs.items():
                for sub in subs:
                    if sub.get("ext") in ("vtt", "srt", "ttml"):
                        subtitles.append(SubtitleInfo(
                            language=lang_code,
                            language_name=language_names.get(
                                lang_code, lang_code
                            ),
                            is_auto=False,
                            ext=sub.get("ext", "vtt"),
                            url=sub.get("url", ""),
                        ))

            logger.info(f"解析到 {len(subtitles)} 个字幕")

        except Exception as e:
            logger.error(f"获取字幕列表异常: {e}")

        return subtitles

    def _parse_single_format(self, fmt: dict) -> Optional[VideoFormat]:
        """解析单个格式条目

        Args:
            fmt: yt-dlp 返回的格式字典

        Returns:
            VideoFormat 对象，无法解析时返回 None
        """
        try:
            # 基本信息
            format_id = fmt.get("format_id", "")
            ext = fmt.get("ext", "")
            resolution = fmt.get("resolution", "") or ""
            fps = fmt.get("fps") or 0
            file_size = fmt.get("filesize") or fmt.get("filesize_approx") or 0

            # 编码信息
            vcodec = fmt.get("vcodec", "") or ""
            acodec = fmt.get("acodec", "") or ""

            # 判断类型
            has_video = vcodec != "none" and vcodec != ""
            has_audio = acodec != "none" and acodec != ""
            is_audio_only = not has_video and has_audio

            # 比特率
            tbr = fmt.get("tbr") or 0.0
            vbr = fmt.get("vbr") or 0.0
            abr = fmt.get("abr") or 0.0

            # 格式备注
            note = fmt.get("format_note", "") or ""

            # 如果不是视频也不是音频，跳过
            if not has_video and not has_audio:
                return None

            return VideoFormat(
                format_id=format_id,
                ext=ext,
                resolution=resolution,
                video_codec=vcodec.split(".")[0] if vcodec else "",
                audio_codec=acodec.split(".")[0] if acodec else "",
                fps=int(fps) if fps else 0,
                file_size=int(file_size) if file_size else 0,
                tbr=float(tbr),
                vbr=float(vbr),
                abr=float(abr),
                has_video=has_video,
                has_audio=has_audio,
                is_audio_only=is_audio_only,
                note=note,
            )

        except Exception as e:
            logger.debug(f"解析格式条目失败: {e}")
            return None

    def _is_unique_format(self, fmt: VideoFormat, seen: Dict[str, set]) -> bool:
        """检查格式是否唯一（去重）

        按分辨率和扩展名组合去重，避免显示重复格式。

        Args:
            fmt: 待检查的格式
            seen: 已见过的格式记录

        Returns:
            是否为新的唯一格式
        """
        if fmt.is_audio_only:
            key = f"audio_{fmt.ext}_{fmt.audio_codec}"
            category = "audio"
        else:
            key = f"video_{fmt.resolution}_{fmt.ext}_{fmt.video_codec}"
            category = "video"

        if key in seen[category]:
            return False

        seen[category].add(key)
        return True

    def _sort_key(self, fmt: VideoFormat) -> tuple:
        """生成格式排序键值

        音频格式排在视频格式之后，视频按分辨率升序排列。

        Args:
            fmt: 视频格式

        Returns:
            排序元组 (是否音频, 分辨率数值)
        """
        is_audio = 1 if fmt.is_audio_only else 0

        # 解析分辨率
        resolution_int = 0
        if fmt.resolution:
            try:
                resolution_int = int(fmt.resolution.lower().replace("p", ""))
            except ValueError:
                pass

        return (is_audio, resolution_int)

    def get_best_video_format(self, formats: List[VideoFormat]) -> Optional[VideoFormat]:
        """获取最佳视频格式（带音频的最高分辨率）

        Args:
            formats: 可用格式列表

        Returns:
            最佳 VideoFormat，无可用格式时返回 None
        """
        combined = self.fetch_combined_formats_from_list(formats)
        if combined:
            return combined[-1]  # 已排序，最后一个为最高分辨率
        return None

    def get_best_audio_format(self, formats: List[VideoFormat]) -> Optional[VideoFormat]:
        """获取最佳音频格式

        Args:
            formats: 可用格式列表

        Returns:
            最佳音频 VideoFormat，无可用格式时返回 None
        """
        audio_formats = [f for f in formats if f.is_audio_only]
        if not audio_formats:
            return None
        # 按比特率排序，返回最高质量
        audio_formats.sort(key=lambda f: f.abr, reverse=True)
        return audio_formats[0]

    @staticmethod
    def fetch_combined_formats_from_list(
        formats: List[VideoFormat]
    ) -> List[VideoFormat]:
        """从已有格式列表中筛选合并格式（静态方法）

        Args:
            formats: 格式列表

        Returns:
            同时包含音视频的格式
        """
        return [f for f in formats if f.has_video and f.has_audio]
