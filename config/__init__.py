"""配置模块

提供应用配置管理的统一入口。
"""

from .settings_manager import (
    SettingsManager,
    get_settings_manager,
    get_settings,
)

__all__ = [
    "SettingsManager",
    "get_settings_manager",
    "get_settings",
]
