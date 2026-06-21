"""FFmpeg 音视频合并模块

负责调用 FFmpeg 进行音视频流合并，支持进度回调和错误处理。
"""

import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class FFmpegMerger:
    """FFmpeg 合并器

    负责将分离的视频流和音频流合并为单个文件，
    支持自动检测 FFmpeg 安装路径和进度回调。
    """

    def __init__(self, ffmpeg_path: str = "") -> None:
        """初始化合并器

        Args:
            ffmpeg_path: FFmpeg 可执行文件路径，为空时自动检测
        """
        self._ffmpeg_path = ffmpeg_path or self._auto_detect_ffmpeg()
        self._available = self._check_ffmpeg()

    @property
    def is_available(self) -> bool:
        """FFmpeg 是否可用"""
        return self._available

    @property
    def ffmpeg_path(self) -> str:
        """获取 FFmpeg 路径"""
        return self._ffmpeg_path

    @ffmpeg_path.setter
    def ffmpeg_path(self, path: str) -> None:
        """设置 FFmpeg 路径并重新检测"""
        self._ffmpeg_path = path
        self._available = self._check_ffmpeg()

    def _auto_detect_ffmpeg(self) -> str:
        """自动检测系统 FFmpeg 安装

        按以下顺序查找:
        1. 环境变量 PATH
        2. 应用自带安装目录 (~/.youtube_downloader_pro/ffmpeg)
        3. 项目目录下的 FFmpeg 文件夹
        4. Windows 常见安装目录
        5. 系统 PATH 搜索

        Returns:
            FFmpeg 可执行文件路径，未找到返回 "ffmpeg"
        """
        # 1. 检查 PATH 中是否存在
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        if shutil.which("ffmpeg.exe"):
            return "ffmpeg.exe"

        # 2. 应用自带安装目录
        app_ffmpeg = Path.home() / ".youtube_downloader_pro" / "ffmpeg" / "bin" / "ffmpeg.exe"
        if app_ffmpeg.exists():
            return str(app_ffmpeg)

        # 3. 项目目录下的 FFmpeg 文件夹（用户可能手动放置）
        project_root = Path(__file__).parent.parent  # youtube_downloader/
        for candidate in [
            project_root / "FFmpeg" / "bin" / "ffmpeg.exe",
            project_root / "ffmpeg" / "bin" / "ffmpeg.exe",
            project_root / "FFmpeg" / "ffmpeg.exe",
            project_root.parent / "FFmpeg" / "bin" / "ffmpeg.exe",
        ]:
            if candidate.exists():
                return str(candidate)

        # 4. Windows 常见安装目录
        common_paths = [
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe"),
            Path.home() / "ffmpeg/bin/ffmpeg.exe",
            Path.home() / "AppData/Local/ffmpeg/bin/ffmpeg.exe",
        ]
        for path in common_paths:
            if path.exists():
                return str(path)

        return "ffmpeg"

    def _check_ffmpeg(self) -> bool:
        """检查 FFmpeg 是否可用

        Returns:
            FFmpeg 可用返回 True
        """
        try:
            result = subprocess.run(
                [self._ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt"
                    else 0
                ),
            )
            if result.returncode == 0:
                logger.debug(f"FFmpeg 检测成功: {self._ffmpeg_path}")
                return True
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
            logger.debug(f"FFmpeg 不可用: {self._ffmpeg_path}")
            return False

    def merge(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """合并视频和音频文件

        使用 FFmpeg 将视频流和音频流合并为单个 MP4 文件。

        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_path: 输出文件路径
            progress_callback: 进度回调函数，接收状态描述字符串

        Returns:
            合并成功返回 True，失败返回 False
        """
        if not self._available:
            logger.error("FFmpeg 不可用，无法合并")
            if progress_callback:
                progress_callback("FFmpeg 不可用，请先安装 FFmpeg")
            return False

        # 验证输入文件存在
        if not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            return False

        if not os.path.exists(audio_path):
            logger.error(f"音频文件不存在: {audio_path}")
            return False

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback("正在合并音视频...")

        # 构建 FFmpeg 命令
        cmd = [
            self._ffmpeg_path,
            "-i", video_path,  # 输入：视频文件
            "-i", audio_path,  # 输入：音频文件
            "-c:v", "copy",    # 复制视频流（不重新编码）
            "-c:a", "aac",     # 音频编码为 AAC
            "-b:a", "192k",    # 音频比特率 192kbps
            "-movflags", "+faststart",  # 支持流媒体快速启动
            "-y",              # 覆盖输出文件
            output_path,
        ]

        logger.info(f"执行 FFmpeg 命令: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt"
                    else 0
                ),
            )

            # 等待完成（超时 30 分钟）
            stdout, stderr = process.communicate(timeout=1800)

            if process.returncode == 0:
                if progress_callback:
                    progress_callback("合并完成")

                # 验证输出文件
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"合并成功: {output_path}")
                    return True
                else:
                    logger.error("合并后输出文件无效")
                    return False
            else:
                logger.error(f"FFmpeg 合并失败 (返回码 {process.returncode}):\n{stderr[:500]}")
                if progress_callback:
                    progress_callback(f"合并失败: FFmpeg 返回错误码 {process.returncode}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg 合并超时 (30分钟)")
            process.kill()
            if progress_callback:
                progress_callback("合并超时")
            return False
        except Exception as e:
            logger.error(f"FFmpeg 合并异常: {e}")
            if progress_callback:
                progress_callback(f"合并失败: {str(e)}")
            return False

    @staticmethod
    def clean_temp_files(*paths: str) -> None:
        """清理临时文件

        Args:
            *paths: 要删除的文件路径列表
        """
        for path in paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"已删除临时文件: {path}")
            except (PermissionError, OSError) as e:
                logger.warning(f"删除临时文件失败 {path}: {e}")
