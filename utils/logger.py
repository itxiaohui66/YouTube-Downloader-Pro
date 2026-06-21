"""日志系统模块

提供统一的日志记录功能，支持控制台输出和文件滚动存储。
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 默认日志目录和文件
DEFAULT_LOG_DIR = Path.home() / ".youtube_downloader_pro" / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "app.log"

# 日志文件大小限制 (5 MB)
MAX_LOG_SIZE = 5 * 1024 * 1024
# 备份日志文件数量
BACKUP_COUNT = 3


def setup_logging(
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """配置日志系统

    Args:
        log_file: 日志文件路径，为 None 时使用默认路径
        level: 日志级别
        console: 是否输出到控制台

    Returns:
        根日志记录器
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除已有处理器
    root_logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    # 控制台处理器
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 文件处理器
    if log_file is None:
        log_file = DEFAULT_LOG_FILE

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except (PermissionError, OSError):
        # 无法创建日志文件时，至少保留控制台输出
        pass

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器

    Args:
        name: 日志记录器名称，通常使用 __name__

    Returns:
        Logger 实例
    """
    return logging.getLogger(name)
