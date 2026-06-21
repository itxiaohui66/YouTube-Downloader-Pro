# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Downloader Pro — a PySide6 desktop GUI application for downloading YouTube videos, playlists, subtitles, and thumbnails. Built on yt-dlp with FFmpeg integration for high-quality video/audio merging. Chinese-language UI (zh_CN).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Package to Windows EXE
pyinstaller "YouTube Downloader Pro.spec"
# Or: pyinstaller --onefile --windowed --name "YouTube Downloader Pro" main.py
```

There are no tests or linting scripts in this project.

## Architecture

The application follows a layered architecture with clear separation between UI, download logic, data models, and configuration:

### Entry Point (`main.py`)
- Initializes crash dump handler (faulthandler), logging system, QApplication
- Checks critical dependencies (yt-dlp, PySide6, requests)
- Loads settings via singleton `SettingsManager`, pre-applies theme stylesheet before window creation to avoid render races
- Creates and shows `MainWindow`, then enters the Qt event loop

### UI Layer (`ui/`)
- **`main_window.py`** — The central hub (~1860 lines). Uses `QStackedWidget` with three pages: empty state, video info + format selection, and playlist table. Contains the inline batch-download dialog. Progress display is refreshed by a 500ms `QTimer` polling the download queue rather than per-event signals, avoiding UI thread congestion.
- **`settings_window.py`** — Modal QDialog with tabbed settings (general/format/advanced/appearance). Saves via `SettingsManager.save()`.
- **`theme.py`** — Dark and light QSS stylesheets applied at the `QApplication` level (not per-widget) to avoid render races. Theme is selected before window construction in `main.py`.
- **`widgets/`** — Placeholder package for reusable components (currently empty).

### Downloader Layer (`downloader/`)
- **`video_downloader.py`** — Wraps yt-dlp's `YoutubeDL`. Each download task creates an **independent `VideoDownloader` instance** to avoid threading races. Supports pause (busy-wait loop), cancel (raises `DownloadCancelled`), and progress hooks. Builds yt-dlp options from `DownloadTask` config.
- **`download_queue.py`** — `ThreadPoolExecutor`-based queue manager with 1-32 configurable workers. Provides callback hooks for task lifecycle events (started/completed/failed/all_completed). Callbacks are scheduled to the main thread via `QTimer.singleShot(0, ...)` in `MainWindow._setup_connections()`. Monitors completion via a daemon thread.
- **`format_parser.py`** — Extracts video metadata, available formats (deduplicated by resolution+codec), and subtitle lists from yt-dlp. Formats are categorized as combined (video+audio), video-only, or audio-only; UI display name is built from multiple fields.
- **`playlist_downloader.py`** — Extracts playlist entries with flat extraction first, falling back to full extraction if empty.
- **`subtitle_downloader.py`** — Downloads subtitles via yt-dlp or direct HTTP request (for pre-resolved URLs).
- **`thumbnail_downloader.py`** — Downloads thumbnails from yt-dlp metadata or directly from `img.youtube.com` with quality fallback chain (maxresdefault → sddefault → hqdefault → mqdefault → default).
- **`ffmpeg_merger.py`** — Calls FFmpeg as a subprocess to merge separate video/audio streams. Auto-detects FFmpeg from PATH, bundled directory, or common install locations. `ffmpeg_path` property setter re-validates availability.
- **`ffmpeg_installer.py`** — Downloads FFmpeg essentials build from gyan.dev (with BtbN fallback), extracts to `~/.youtube_downloader_pro/ffmpeg/bin/`, and verifies the binary.

### Data Models (`models/`)
- **`task.py`** — `DownloadTask` (the central task object with all download config), `VideoInfo`, `VideoFormat` (with `display_name` property for UI combos), `DownloadProgress` (bytes, speed, ETA with human-readable formatting), `SubtitleInfo`, and enums `TaskStatus`/`DownloadType`. All are `@dataclass` with sensible defaults.
- **`settings.py`** — `Settings` dataclass with `to_dict()`/`from_dict()` for JSON persistence. Enum `ThemeMode` (LIGHT/DARK/SYSTEM).

### Configuration (`config/`)
- **`settings_manager.py`** — Singleton `SettingsManager` via module-level `_settings_manager` variable. Writes atomically (write to `.tmp`, then rename) to prevent corruption. Lazy-loads settings on first access. Config stored at `~/.youtube_downloader_pro/settings.json`.

### Cookie Authentication
YouTube may require authentication (bot detection). The app supports two methods, with cookies file taking priority:

1. **Cookie file** (recommended) — Netscape-format `cookies.txt` exported via browser extensions like "Get cookies.txt LOCALLY". More reliable because it doesn't depend on browser database access.
2. **Auto browser cookies** (default) — The `cookies_from_browser` setting accepts comma-separated browser names or `"auto"` (tries chrome→firefox→edge→brave→opera in order). On cookie-related errors (locked DB, bot detection), `FormatParser` and `PlaylistDownloader` automatically retry with the next browser via `_try_extract_info()`. The `_is_cookie_error()` helper identifies retryable errors.

### Utilities (`utils/`)
- **`logger.py`** — `RotatingFileHandler`-based logging (5 MB per file, 3 backups). Logs go to `~/.youtube_downloader_pro/logs/app.log`. Console output is optional.
- **`validators.py`** — Regex-based YouTube URL validation supporting 5 video URL patterns and 2 playlist URL patterns. Also provides `sanitize_filename()` for cross-platform safe filenames.
- **`user_agents.py`** — Pool of 50 real browser User-Agent strings (Chrome/Firefox/Edge/Safari/Opera/Brave/Vivaldi/Arc across Windows/macOS/Linux) rotated randomly per request for anti-detection. `get_headers()` returns a full set of browser-like HTTP headers.

### Threading Model
- **Main thread**: Qt event loop and all UI updates
- **Download workers**: `ThreadPoolExecutor` threads, configurable 1-32, each running an isolated `VideoDownloader`
- **Info fetching**: `QThread` subclasses (`FetchInfoWorker`, `FormatFetchThread`, `ParseThread`) with Qt signals for result delivery
- **Queue monitor**: Daemon `threading.Thread` polling every 1s for all-complete detection
- **UI refresh**: `QTimer` on main thread (500ms interval), started with a 1-second delay after `showEvent` to avoid render pipeline races
- **Thread safety**: `_active_downloaders` dict protected by `threading.Lock`; per-task `VideoDownloader` instances prevent cross-task interference

### FFmpeg Handling
- FFmpeg auto-detection searches: PATH → `~/.youtube_downloader_pro/ffmpeg/bin/` → project `FFmpeg/` directory → common Windows install paths
- When FFmpeg is unavailable, the format dropdown separates combined formats (usable) from video-only formats (marked with ⚠ warning)
- The "auto-merge" checkbox is disabled when FFmpeg is absent
- Users can trigger auto-install from Help → Check FFmpeg Status menu, or manually configure the path in Settings

### Download Flow (single video)
1. User pastes URL → clicks "获取信息" → `FetchInfoWorker` (QThread) calls `FormatParser`
2. On success: `_on_info_ready` populates video info card, format combos; switches stack to video page
3. User selects format/options → clicks "下载" → `_start_single_download` creates `DownloadTask`, adds to `DownloadQueue`
4. `_ensure_queue_running` starts the pool if idle, calling `_execute_download` per task
5. `_execute_download` creates a fresh `VideoDownloader`, sets progress hook, runs download, then optionally downloads subtitles and thumbnail
6. UI refreshes every 500ms via `_refresh_progress_display` timer, reading `task.progress` directly
