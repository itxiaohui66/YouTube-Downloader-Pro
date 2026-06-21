"""视频下载器模块

使用 yt-dlp 实现 YouTube 视频下载，支持：
- 视频/音频下载
- 下载进度回调
- 多线程安全
- 错误重试机制
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any

import yt_dlp

from ..models.task import DownloadTask, DownloadProgress, TaskStatus
from ..utils.user_agents import get_random_ua
from .ffmpeg_merger import FFmpegMerger

logger = logging.getLogger(__name__)


class VideoDownloader:
    """视频下载器

    封装 yt-dlp 下载逻辑，提供进度回调和状态管理。
    每个下载任务在独立线程中执行。
    """

    def __init__(self, ffmpeg_path: str = "") -> None:
        """初始化视频下载器

        Args:
            ffmpeg_path: FFmpeg 路径，用于合并音视频
        """
        self._ffmpeg_path = ffmpeg_path
        self._merger = FFmpegMerger(ffmpeg_path)
        self._progress_hook: Optional[Callable] = None

        # 下载状态（线程安全）
        self._cancel_flag = threading.Event()
        self._pause_flag = threading.Event()
        self._current_task: Optional[DownloadTask] = None

    @property
    def is_ffmpeg_available(self) -> bool:
        """FFmpeg 是否可用"""
        return self._merger.is_available

    def set_progress_hook(
        self, hook: Optional[Callable[[DownloadProgress, str], None]]
    ) -> None:
        """设置进度回调

        Args:
            hook: 回调函数，接收 DownloadProgress 和状态消息
        """
        self._progress_hook = hook

    def cancel(self) -> None:
        """取消当前下载"""
        self._cancel_flag.set()
        logger.info("下载取消请求已发送")

    def pause(self) -> None:
        """暂停当前下载"""
        self._pause_flag.set()
        logger.info("下载暂停请求已发送")

    def resume(self) -> None:
        """恢复当前下载"""
        self._pause_flag.clear()
        logger.info("下载恢复")

    def download_video(self, task: DownloadTask) -> bool:
        """下载视频

        根据任务配置下载视频/音频，对于需要合并的高清视频自动处理。

        Args:
            task: 下载任务对象

        Returns:
            下载成功返回 True，失败返回 False
        """
        self._cancel_flag.clear()
        self._pause_flag.clear()
        self._current_task = task

        task.status = TaskStatus.DOWNLOADING
        task.started_at = task.created_at  # 使用创建时间作为开始时间

        try:
            # 构建 yt-dlp 选项
            ydl_opts = self._build_ydl_options(task)

            # 执行下载
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([task.url])

            # 检查是否被取消
            if self._cancel_flag.is_set():
                task.status = TaskStatus.CANCELLED
                self._cleanup_partial_download(task)
                return False

            # 设置完成状态
            task.status = TaskStatus.COMPLETED
            task.progress.percent = 100.0
            logger.info(f"下载完成: {task.video_info.title if task.video_info else task.url}")

            return True

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp 下载错误: {e}")
            if self._cancel_flag.is_set():
                task.status = TaskStatus.CANCELLED
            else:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)[:500]
            self._cleanup_partial_download(task)
            return False

        except Exception as e:
            logger.error(f"下载异常: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)[:500]
            self._cleanup_partial_download(task)
            return False

    def download_audio(self, task: DownloadTask) -> bool:
        """仅下载音频

        Args:
            task: 下载任务对象

        Returns:
            下载成功返回 True，失败返回 False
        """
        # 设置为仅音频模式
        task.download_audio = True
        task.download_video = False
        return self.download_video(task)

    def _build_ydl_options(self, task: DownloadTask) -> Dict[str, Any]:
        """构建 yt-dlp 下载选项

        Args:
            task: 下载任务对象

        Returns:
            yt-dlp 选项字典
        """
        # 确定输出目录
        output_dir = task.output_dir or str(
            Path.home() / "Downloads" / "YouTube"
        )

        # 确定输出文件名模板
        filename_template = "%(title)s.%(ext)s"

        # 构建输出路径模板
        outtmpl = str(Path(output_dir) / filename_template)

        options: Dict[str, Any] = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "socket_timeout": 30,
            "retries": 5,
            "fragment_retries": 5,
            "http_headers": {"User-Agent": get_random_ua()},
            "progress_hooks": [self._on_progress],
            "postprocessor_hooks": [self._on_postprocessing],
            # 启用 Node.js 作为 JS 运行时 + 远程挑战求解器
            "js_runtimes": {"node": {}, "deno": {}},
            "remote_components": ["ejs:github"],
        }

        # 格式选择逻辑
        if task.download_audio and not task.download_video:
            # 仅下载音频
            audio_format = task.selected_format
            if audio_format and audio_format.format_id:
                options["format"] = audio_format.format_id
            else:
                options["format"] = "bestaudio/best"

            if self._merger.is_available:
                # FFmpeg 可用：转码为 MP3
                options["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                }]
            else:
                # FFmpeg 不可用：直接下载原始音频格式（不转码）
                logger.warning(
                    "FFmpeg 不可用，音频将保存为原始格式（不转码为 MP3）"
                )

        elif task.selected_format and task.selected_format.format_id:
            # 用户选择的特定格式
            fmt = task.selected_format

            if fmt.has_video and not fmt.has_audio:
                # 仅视频流，需要下载音频流并合并
                if self._merger.is_available:
                    options["format"] = (
                        f"{fmt.format_id}+bestaudio/best"
                    )
                    options["merge_output_format"] = "mp4"
                    # yt-dlp 设置 merge_output_format 后会自动使用 FFmpegMergerPP 合并
                else:
                    # FFmpeg 不可用：完全避免 + 合并语法，仅使用预合并格式
                    # best[height<=X] 选择该分辨率下已包含音频的格式
                    fmt_selector = (
                        f"best[height<={fmt.resolution_int}][ext=mp4]/"
                        f"best[height<={fmt.resolution_int}]/"
                        f"best[ext=mp4]/best"
                    )
                    options["format"] = fmt_selector
                    logger.warning(
                        "FFmpeg 不可用，回退到预合并格式 (≤%sp): %s",
                        fmt.resolution_int, fmt_selector,
                    )
            else:
                # 完整格式（含音频）或纯音频
                options["format"] = fmt.format_id

        else:
            # 默认最佳格式
            if self._merger.is_available:
                # FFmpeg 可用：下载最佳视频+音频流并合并
                options["format"] = (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                )
                options["merge_output_format"] = "mp4"
            else:
                # FFmpeg 不可用：直接下载已合并的最佳格式（通常上限 720p）
                options["format"] = (
                    "best[ext=mp4]/best[ext=webm]/best"
                )
                logger.warning("FFmpeg 不可用，仅下载内置合并格式（最高 720p）")

        # 字幕下载选项
        if task.download_subtitle:
            options["writesubtitles"] = True
            options["writeautomaticsub"] = task.subtitle_auto
            options["subtitleslangs"] = [task.subtitle_language]
            options["subtitlesformat"] = task.subtitle_format

        # 封面下载
        if task.download_thumbnail:
            options["writethumbnail"] = True

        # FFmpeg 路径（如果不为空）
        if self._ffmpeg_path and os.path.exists(self._ffmpeg_path):
            options["ffmpeg_location"] = self._ffmpeg_path

        # Cookie 设置（Cookie 文件优先于浏览器 Cookie）
        if task.extra_data.get("cookies_file"):
            options["cookiefile"] = task.extra_data["cookies_file"]
        elif task.extra_data.get("cookies_from_browser"):
            options["cookiesfrombrowser"] = (
                task.extra_data["cookies_from_browser"],
            )

        # 代理设置
        if task.extra_data.get("proxy"):
            options["proxy"] = task.extra_data["proxy"]

        # 限速设置
        if task.extra_data.get("rate_limit"):
            options["ratelimit"] = task.extra_data["rate_limit"]

        return options

    def _on_progress(self, d: Dict[str, Any]) -> None:
        """yt-dlp 下载进度回调

        Args:
            d: yt-dlp 进度数据字典
        """
        if self._cancel_flag.is_set():
            raise yt_dlp.utils.DownloadCancelled("用户取消下载")

        # 等待暂停恢复
        while self._pause_flag.is_set():
            import time
            time.sleep(0.1)
            if self._cancel_flag.is_set():
                raise yt_dlp.utils.DownloadCancelled("用户取消下载")

        if self._current_task is None or self._progress_hook is None:
            return

        status = d.get("status", "")

        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0) or 0
            total = (
                d.get("total_bytes")
                or d.get("total_bytes_estimate")
                or 0
            )
            speed = d.get("speed") or 0.0
            eta = d.get("eta") or 0

            # 计算百分比
            percent = (downloaded / total * 100) if total > 0 else 0.0

            progress = DownloadProgress(
                downloaded_bytes=downloaded,
                total_bytes=total,
                speed=speed,
                percent=percent,
                eta=eta,
                status="下载中",
            )

            self._current_task.progress = progress
            self._progress_hook(progress, "下载中")

        elif status == "finished":
            # 下载完成，可能还需后处理
            if self._current_task:
                self._current_task.progress.percent = 99.0
                self._progress_hook(
                    self._current_task.progress, "处理中..."
                )

        elif status == "error":
            logger.error("下载出错")

    def _on_postprocessing(self, d: Dict[str, Any]) -> None:
        """yt-dlp 后处理回调（如合并、转码）

        Args:
            d: 后处理数据字典
        """
        if self._current_task is None or self._progress_hook is None:
            return

        postprocessor = d.get("postprocessor", "")
        status = d.get("status", "")

        if postprocessor == "MoveFiles" and status == "started":
            pass
        elif postprocessor == "MoveFiles" and status == "finished":
            self._current_task.progress.percent = 100.0
        elif postprocessor in ("FFmpegMergerPP", "FFmpegMergeVideo") and status == "started":
            self._current_task.status = TaskStatus.MERGING
            self._progress_hook(
                self._current_task.progress, "正在合并音视频..."
            )
        elif postprocessor in ("FFmpegMergerPP", "FFmpegMergeVideo") and status == "finished":
            self._progress_hook(
                self._current_task.progress, "合并完成"
            )

    def _cleanup_partial_download(self, task: DownloadTask) -> None:
        """清理不完整的下载文件

        Args:
            task: 下载任务
        """
        # yt-dlp 通常使用 .part 或 .ytdl 扩展名标记未完成下载
        output_dir = task.output_dir or str(
            Path.home() / "Downloads" / "YouTube"
        )
        try:
            if task.video_info:
                # 尝试清理匹配标题的临时文件
                clean_title = task.video_info.title.replace("/", "_")[:50]
                for ext in [".part", ".ytdl", ".tmp"]:
                    for f in Path(output_dir).glob(f"*{clean_title}*{ext}"):
                        try:
                            f.unlink()
                        except OSError:
                            pass
        except Exception:
            pass
