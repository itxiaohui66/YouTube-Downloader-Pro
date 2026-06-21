"""FFmpeg 自动安装模块

当系统未检测到 FFmpeg 时，自动从官方源下载 Windows 版本
并解压到本地目录，无需用户手动配置。
"""

import logging
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


# FFmpeg Windows 构建下载地址（gyan.dev 稳定版）
FFMPEG_DOWNLOAD_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)

# 备用下载地址（BtbN 构建）
FFMPEG_DOWNLOAD_URL_BACKUP = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)

# 默认安装目录
DEFAULT_INSTALL_DIR = Path.home() / ".youtube_downloader_pro" / "ffmpeg"


class FFmpegInstaller:
    """FFmpeg 自动安装器

    负责下载、解压和配置 FFmpeg。
    支持进度回调和取消操作。
    """

    def __init__(self, install_dir: Optional[Path] = None) -> None:
        """初始化安装器

        Args:
            install_dir: 安装目录，默认为用户目录下的 .youtube_downloader_pro/ffmpeg
        """
        self._install_dir = install_dir or DEFAULT_INSTALL_DIR
        self._cancel_flag = False
        self._progress_callback: Optional[Callable[[str, float], None]] = None

    @property
    def install_dir(self) -> Path:
        """获取安装目录"""
        return self._install_dir

    @property
    def ffmpeg_exe_path(self) -> Path:
        """获取安装后的 ffmpeg.exe 路径"""
        return self._install_dir / "bin" / "ffmpeg.exe"

    def is_installed(self) -> bool:
        """检查 FFmpeg 是否已在本地安装目录中

        Returns:
            已安装返回 True
        """
        return self.ffmpeg_exe_path.exists()

    def set_progress_callback(
        self, callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """设置进度回调

        Args:
            callback: 回调函数，接收 (状态描述, 百分比 0-100)
        """
        self._progress_callback = callback

    def cancel(self) -> None:
        """取消安装"""
        self._cancel_flag = True

    def install(self) -> bool:
        """执行自动安装

        下载 FFmpeg 压缩包，解压到安装目录，
        并验证安装结果。

        Returns:
            安装成功返回 True
        """
        self._cancel_flag = False

        try:
            # 确保安装目录存在
            self._install_dir.mkdir(parents=True, exist_ok=True)

            # 步骤 1：下载
            zip_path = self._download()
            if not zip_path:
                return False

            # 步骤 2：解压
            if not self._extract(zip_path):
                return False

            # 步骤 3：验证
            if not self._verify():
                return False

            # 步骤 4：清理
            self._cleanup(zip_path)

            self._report_progress("FFmpeg 安装完成！", 100.0)
            logger.info(f"FFmpeg 安装成功: {self.ffmpeg_exe_path}")
            return True

        except Exception as e:
            logger.error(f"FFmpeg 安装失败: {e}")
            self._report_progress(f"安装失败: {str(e)}", 0.0)
            return False

    def _download(self) -> Optional[Path]:
        """下载 FFmpeg 压缩包

        Returns:
            下载的压缩包路径，失败返回 None
        """
        self._report_progress("正在下载 FFmpeg...", 5.0)

        zip_path = self._install_dir / "ffmpeg_temp.zip"

        # 尝试主下载地址
        urls = [FFMPEG_DOWNLOAD_URL, FFMPEG_DOWNLOAD_URL_BACKUP]

        for url in urls:
            try:
                logger.info(f"下载 FFmpeg: {url}")
                self._report_progress(f"正在下载 FFmpeg... (这可能需要几分钟)", 10.0)

                # 使用 urllib 下载，支持进度回调
                def _progress_hook(block_count, block_size, total_size):
                    if self._cancel_flag:
                        raise InterruptedError("用户取消安装")

                    if total_size > 0:
                        percent = 10.0 + (block_count * block_size / total_size) * 60.0
                        downloaded = block_count * block_size
                        self._report_progress(
                            f"正在下载 FFmpeg... ({downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB)",
                            min(percent, 70.0),
                        )

                urllib.request.urlretrieve(
                    url, str(zip_path), reporthook=_progress_hook
                )

                if zip_path.exists() and zip_path.stat().st_size > 100000:
                    logger.info(f"FFmpeg 下载完成 ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
                    return zip_path
                else:
                    logger.warning("下载文件太小，尝试备用地址")
                    zip_path.unlink(missing_ok=True)

            except InterruptedError:
                logger.info("用户取消 FFmpeg 下载")
                zip_path.unlink(missing_ok=True)
                return None
            except Exception as e:
                logger.warning(f"下载地址失败 {url}: {e}")
                zip_path.unlink(missing_ok=True)
                continue

        logger.error("所有下载地址均失败")
        self._report_progress("下载失败，请检查网络连接", 0.0)
        return None

    def _extract(self, zip_path: Path) -> bool:
        """解压 FFmpeg 压缩包

        解压后重命名内部目录，使 ffmpeg.exe 位于 bin/ 子目录下。

        Args:
            zip_path: 压缩包路径

        Returns:
            解压成功返回 True
        """
        self._report_progress("正在解压 FFmpeg...", 75.0)

        try:
            with zipfile.ZipFile(str(zip_path), "r") as zf:
                # 获取压缩包内顶层目录名
                names = zf.namelist()
                top_dirs = set()
                for name in names:
                    parts = name.split("/")
                    if parts[0]:
                        top_dirs.add(parts[0])

                # 解压到临时目录
                extract_dir = self._install_dir / "_extract_temp"
                if extract_dir.exists():
                    shutil.rmtree(str(extract_dir))
                extract_dir.mkdir(parents=True, exist_ok=True)

                self._report_progress("正在解压 FFmpeg... (文件较多，请稍候)", 80.0)
                zf.extractall(str(extract_dir))

            # 查找 bin/ffmpeg.exe
            ffmpeg_exe = None
            for root, dirs, files in os.walk(str(extract_dir)):
                if "ffmpeg.exe" in files:
                    ffmpeg_exe = Path(root) / "ffmpeg.exe"
                    break

            if ffmpeg_exe is None:
                logger.error("解压后未找到 ffmpeg.exe")
                return False

            # 移动文件到标准位置
            bin_dir = self._install_dir / "bin"
            if bin_dir.exists():
                shutil.rmtree(str(bin_dir))
            bin_dir.mkdir(parents=True, exist_ok=True)

            # 复制 bin 目录下所有文件
            ffmpeg_bin_dir = ffmpeg_exe.parent
            for item in ffmpeg_bin_dir.iterdir():
                dest = bin_dir / item.name
                if item.is_file():
                    shutil.copy2(str(item), str(dest))
                elif item.is_dir():
                    if dest.exists():
                        shutil.rmtree(str(dest))
                    shutil.copytree(str(item), str(dest))

            # 清理临时目录
            shutil.rmtree(str(extract_dir))

            self._report_progress("解压完成", 90.0)
            logger.info(f"FFmpeg 解压完成: {bin_dir}")
            return True

        except zipfile.BadZipFile:
            logger.error("FFmpeg 压缩包损坏")
            return False
        except Exception as e:
            logger.error(f"解压 FFmpeg 失败: {e}")
            return False

    def _verify(self) -> bool:
        """验证安装结果

        Returns:
            FFmpeg 可正常执行为 True
        """
        self._report_progress("正在验证 FFmpeg 安装...", 95.0)

        ffmpeg_exe = str(self.ffmpeg_exe_path)
        try:
            result = subprocess.run(
                [ffmpeg_exe, "-version"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt"
                    else 0
                ),
            )
            if result.returncode == 0:
                version_line = result.stdout.split("\n")[0] if result.stdout else "OK"
                logger.info(f"FFmpeg 验证成功: {version_line}")
                return True
            return False
        except Exception as e:
            logger.error(f"FFmpeg 验证失败: {e}")
            return False

    def _cleanup(self, zip_path: Path) -> None:
        """清理临时文件

        Args:
            zip_path: 下载的压缩包路径
        """
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _report_progress(self, message: str, percent: float) -> None:
        """报告安装进度

        Args:
            message: 状态描述
            percent: 进度百分比 (0-100)
        """
        if self._progress_callback:
            self._progress_callback(message, percent)


def auto_install_ffmpeg(
    progress_callback: Optional[Callable[[str, float], None]] = None,
    install_dir: Optional[Path] = None,
) -> Optional[str]:
    """自动安装 FFmpeg 的便捷函数

    Args:
        progress_callback: 进度回调 (状态消息, 百分比)
        install_dir: 安装目录，默认自动选择

    Returns:
        安装成功返回 ffmpeg.exe 路径，失败返回 None
    """
    installer = FFmpegInstaller(install_dir)
    installer.set_progress_callback(progress_callback)

    if installer.is_installed():
        logger.info("FFmpeg 已安装，跳过下载")
        return str(installer.ffmpeg_exe_path)

    if installer.install():
        return str(installer.ffmpeg_exe_path)

    return None
