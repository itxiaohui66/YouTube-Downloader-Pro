"""输入验证模块

提供 YouTube URL 格式验证和文件路径验证功能。
"""

import re
from pathlib import Path
from typing import Tuple


# YouTube URL 正则表达式模式
YOUTUBE_PATTERNS = [
    # 标准视频 URL: https://www.youtube.com/watch?v=VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
    # 短链接: https://youtu.be/VIDEO_ID
    r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
    # 嵌入: https://www.youtube.com/embed/VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    # Shorts: https://www.youtube.com/shorts/VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    # 移动版: https://m.youtube.com/watch?v=VIDEO_ID
    r"(?:https?://)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
]

# 播放列表 URL 模式
PLAYLIST_PATTERNS = [
    # 标准播放列表: https://www.youtube.com/playlist?list=PLAYLIST_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)",
    # 带视频的播放列表: https://www.youtube.com/watch?v=X&list=Y
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*list=([a-zA-Z0-9_-]+)",
]


def validate_youtube_url(url: str) -> Tuple[bool, str, bool]:
    """验证 YouTube URL 是否有效

    Args:
        url: 待验证的 URL

    Returns:
        (是否有效, 视频/播放列表ID, 是否为播放列表) 元组
        无效时返回 (False, "", False)
    """
    if not url or not url.strip():
        return False, "", False

    url = url.strip()

    # 检查是否为播放列表
    for pattern in PLAYLIST_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return True, match.group(1), True

    # 检查是否为视频
    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return True, match.group(1), False

    return False, "", False


def is_valid_video_url(url: str) -> bool:
    """检查是否为有效的 YouTube 视频 URL

    Args:
        url: 待检查的 URL

    Returns:
        是否有效
    """
    valid, _, is_playlist = validate_youtube_url(url)
    return valid and not is_playlist


def is_valid_playlist_url(url: str) -> bool:
    """检查是否为有效的 YouTube 播放列表 URL

    Args:
        url: 待检查的 URL

    Returns:
        是否有效
    """
    valid, _, is_playlist = validate_youtube_url(url)
    return valid and is_playlist


def validate_directory(path: str) -> Tuple[bool, str]:
    """验证目录路径是否可用

    Args:
        path: 目录路径

    Returns:
        (是否有效, 错误信息) 元组
    """
    if not path:
        return False, "目录路径不能为空"

    try:
        dir_path = Path(path)
        if dir_path.exists() and not dir_path.is_dir():
            return False, f"路径已存在但不是目录: {path}"
        return True, ""
    except (OSError, ValueError) as e:
        return False, f"路径无效: {str(e)}"


def clean_video_url(url: str) -> str:
    """清理视频 URL，移除播放列表和多余参数

    将带 ?list= 或 &list= 的视频 URL 净化，
    同时移除 &t= (时间戳) 和 &feature= 等无关参数，
    保留核心的 ?v= 部分。

    Args:
        url: 原始 YouTube URL

    Returns:
        清理后的 URL
    """
    import re

    # 对于 youtu.be 短链接：移除 ?list=... 及之后的所有参数
    # https://youtu.be/VIDEO_ID?list=...&t=... → https://youtu.be/VIDEO_ID
    short_match = re.match(
        r"(https?://youtu\.be/[a-zA-Z0-9_-]{11})", url
    )
    if short_match:
        return short_match.group(1)

    # 对于标准 youtube.com/watch?v= 链接：保留 v= 参数，移除 list/t/feature 等
    watch_match = re.match(
        r"(https?://(?:www\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]{11})", url
    )
    if watch_match:
        return watch_match.group(1)

    # 其他格式（embed, shorts 等）：原样返回
    return url


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    # Windows 和跨平台非法字符
    illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(illegal_chars, "_", filename)

    # 移除开头和结尾的空格及点
    sanitized = sanitized.strip(". ")

    # 限制文件名长度 (保留扩展名)
    if len(sanitized) > 200:
        # 尝试保留扩展名
        stem = Path(sanitized).stem
        suffix = Path(sanitized).suffix
        max_stem = 200 - len(suffix)
        sanitized = stem[:max_stem] + suffix

    # 空文件名使用默认值
    if not sanitized:
        sanitized = "video"

    return sanitized
