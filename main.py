"""YouTube Downloader Pro - 应用入口

启动 YouTube 视频下载器桌面应用。
负责初始化日志系统、加载配置、创建主窗口并启动事件循环。
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

# 确保项目根目录在 Python 路径中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from youtube_downloader.utils.logger import setup_logging, get_logger
from youtube_downloader.config.settings_manager import get_settings_manager
from youtube_downloader.ui.main_window import MainWindow

logger: Optional[logging.Logger] = None


def check_dependencies() -> bool:
    """检查关键依赖是否已安装

    Returns:
        所有依赖可用返回 True
    """
    missing = []

    # 检查 yt-dlp
    try:
        import yt_dlp
    except ImportError:
        missing.append("yt-dlp")

    # 检查 PySide6
    try:
        import PySide6
    except ImportError:
        missing.append("PySide6")

    # 检查 requests
    try:
        import requests
    except ImportError:
        missing.append("requests")

    if missing:
        QMessageBox.critical(
            None,
            "缺少依赖",
            f"以下关键依赖未安装:\n\n"
            f"  • {'\n  • '.join(missing)}\n\n"
            f"请运行以下命令安装:\n"
            f"  pip install {' '.join(missing)}"
        )
        return False

    return True


def main() -> int:
    """应用主函数

    初始化应用环境并启动主窗口事件循环。

    Returns:
        应用退出码 (0 表示正常退出)
    """
    global logger

    # ========== 初始化崩溃转储（写入文件，确保崩溃时也有堆栈） ==========
    import faulthandler
    crash_log = Path.home() / ".youtube_downloader_pro" / "logs" / "crash.log"
    crash_log.parent.mkdir(parents=True, exist_ok=True)
    faulthandler.enable(file=open(str(crash_log), "w"), all_threads=True)
    logger_global = logging.getLogger("crash_guard")

    # ========== 初始化日志 ==========
    setup_logging(level=logging.INFO)
    logger = get_logger(__name__)
    logger.info("=" * 50)
    logger.info("YouTube Downloader Pro v1.0.0 启动")
    logger.info(f"Python: {sys.version}")
    logger.info(f"崩溃转储: {crash_log}")
    logger.info("=" * 50)

    # ========== 创建 QApplication ==========
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Downloader Pro")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("itxiaohui")
    app.setOrganizationDomain("itxiaohui.top")

    # 应用图标
    icon_path = Path(__file__).parent / "resources" / "icons" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 高 DPI 支持
    app.setStyle("Fusion")

    # ========== 检查依赖 ==========
    if not check_dependencies():
        return 1

    # ========== 加载设置 ==========
    try:
        settings_manager = get_settings_manager()
        settings = settings_manager.settings
        logger.info(f"配置加载完成 (workers={settings.max_workers})")
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        # 使用默认设置继续

    # ========== 预加载主题（窗口创建前应用，避免渲染竞态） ==========
    try:
        from youtube_downloader.ui.theme import get_theme_stylesheet
        from youtube_downloader.models.settings import ThemeMode
        theme = settings.theme if 'settings' in dir() else ThemeMode.DARK
        is_dark = (theme != ThemeMode.LIGHT)
        app.setStyleSheet(get_theme_stylesheet(is_dark))
        logger.info(f"主题预加载: {'深色' if is_dark else '浅色'}")
    except Exception as e:
        logger.warning(f"主题预加载失败: {e}")

    # ========== 创建并显示主窗口 ==========
    try:
        main_window = MainWindow()
        main_window.show()
        logger.info("主窗口已显示")
    except Exception as e:
        logger.critical(f"创建主窗口失败: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "启动失败",
            f"无法创建应用窗口:\n\n{str(e)}\n\n"
            "请检查日志文件获取详细信息。"
        )
        return 1

    # ========== 进入事件循环 ==========
    exit_code = app.exec()

    # ========== 退出清理 ==========
    logger.info(f"应用退出 (code={exit_code})")

    return exit_code


if __name__ == "__main__":
    # 处理 Windows 平台的多进程问题
    if os.name == "nt":
        import multiprocessing
        multiprocessing.freeze_support()

    sys.exit(main())
