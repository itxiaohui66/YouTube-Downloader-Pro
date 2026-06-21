"""配置管理模块

负责应用设置的持久化存储，支持 JSON 格式的读写操作。
"""

import json
import os
from pathlib import Path
from typing import Optional

from ..models.settings import Settings


class SettingsManager:
    """设置管理器

    负责读取和写入应用配置文件 settings.json，
    提供默认值回退和错误处理机制。
    """

    # 默认配置文件路径
    DEFAULT_CONFIG_DIR = Path.home() / ".youtube_downloader_pro"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "settings.json"

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """初始化设置管理器

        Args:
            config_path: 配置文件路径，为 None 时使用默认路径
        """
        self._config_path = config_path or self.DEFAULT_CONFIG_FILE
        self._settings: Optional[Settings] = None

    @property
    def settings(self) -> Settings:
        """获取当前设置，延迟加载"""
        if self._settings is None:
            self._settings = self.load()
        return self._settings

    def load(self) -> Settings:
        """从配置文件加载设置

        如果文件不存在或损坏，返回默认设置。

        Returns:
            Settings 对象
        """
        if not self._config_path.exists():
            return Settings()

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Settings.from_dict(data)
        except (json.JSONDecodeError, FileNotFoundError, PermissionError):
            # 配置文件损坏或无法读取，使用默认设置
            return Settings()

    def save(self, settings: Optional[Settings] = None) -> bool:
        """保存设置到配置文件

        Args:
            settings: 要保存的设置，为 None 时保存当前设置

        Returns:
            是否保存成功
        """
        if settings is not None:
            self._settings = settings

        if self._settings is None:
            return False

        try:
            # 确保目录存在
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入临时文件后重命名，避免写入中断导致配置损坏
            temp_path = self._config_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._settings.to_dict(), f, ensure_ascii=False, indent=2)

            temp_path.replace(self._config_path)
            return True
        except (PermissionError, OSError):
            return False

    def reset(self) -> Settings:
        """重置为默认设置

        Returns:
            默认的 Settings 对象
        """
        self._settings = Settings()
        return self._settings

    @property
    def config_path(self) -> Path:
        """获取配置文件路径"""
        return self._config_path


# 全局设置管理器单例
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """获取全局设置管理器单例

    Returns:
        SettingsManager 实例
    """
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


def get_settings() -> Settings:
    """获取当前设置（便捷函数）

    Returns:
        当前 Settings 对象
    """
    return get_settings_manager().settings
