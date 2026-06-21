# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件 — YouTube Downloader Pro
===================================================
输出: Windows 单文件 EXE
用法: pyinstaller "YouTube Downloader Pro.spec"
      或: pyinstaller --onefile --windowed --name "YouTube Downloader Pro" main.py
"""

import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

a = Analysis(
    # 入口脚本
    ['main.py'],

    # 打包参数
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # 资源文件 (如有图标等资源，在此添加)
        # ('resources/icons/*', 'resources/icons'),
    ],
    hiddenimports=[
        # yt-dlp 需要的隐藏导入
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',
        'yt_dlp.utils',
        # PySide6 完整导入
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        # 项目模块
        'youtube_downloader',
        'youtube_downloader.ui',
        'youtube_downloader.downloader',
        'youtube_downloader.models',
        'youtube_downloader.config',
        'youtube_downloader.utils',
        # 其他
        'requests',
        'json',
        'logging',
        'uuid',
        'threading',
        'queue',
        'concurrent.futures',
        'pathlib',
        're',
        'os',
        'sys',
        'subprocess',
        'shutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库以减小体积
        'tkinter',
        'unittest',
        'test',
        'setuptools',
        'pip',
        'wheel',
        'pkg_resources',
    ],
    noarchive=False,
    optimize=2,  # 字节码优化级别
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    # 基本信息
    name='YouTube Downloader Pro',
    # 图标 (如有 ico 文件在此指定)
    # icon=str(PROJECT_ROOT / 'resources' / 'icons' / 'app.ico'),
    # 单文件输出
    onefile=True,
    # 无控制台窗口 (Windows GUI 应用)
    console=False,
    # 其他选项
    debug=False,
    strip=True,       # 移除调试信息
    upx=True,         # 使用 UPX 压缩
    runtime_tmpdir=None,
    # 版本信息
    version='1.0.0',
    # Windows 特定
    uac_admin=False,
    # 嵌入 manifest
    embed_manifest=True,
)

# 清理临时文件
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTube Downloader Pro',
)
