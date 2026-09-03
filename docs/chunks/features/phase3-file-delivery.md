# Phase 3 — File Delivery

## Quick Reference
| File | Purpose |
|------|---------|
| `handlers/files.py` | `/build`, `/apk`, `/file <path>` |
| `config.py` | `APK_SEARCH_DIRS`, `APK_GLOB`, `BUILD_CMD`, `MAX_FILE_SIZE` |

## Overview
Gradle build trigger, APK finder (latest by mtime), and arbitrary file sender with size validation (50MB TG limit).

## Key Functions

### `handlers/files.py`
- `build_cmd()` — builds current project (`utils/project.py`), `clean` then `assembleDebug`, 5 min timeout, output prefixed `[project]`; refuses with friendly error if no `gradlew.bat`
- `_send_apk(update, build_dir)` — sends latest **debug** APK from the built project dir only
- `apk_cmd()` — glob search: current project dir first, then `APK_SEARCH_DIRS`, latest by mtime; `/apk list` grouped by project
- `file_cmd()` — `/file <path>` sends any file, validates existence + size
- `_find_latest_apk()` — internal: recursive glob, returns newest APK path

## Config Values
| Setting | Default | Purpose |
|---------|---------|---------|
| `APK_SEARCH_DIRS` | `[home_dir]` | Dirs to search for APKs |
| `APK_GLOB` | `**/*.apk` | Glob pattern for APK search |
| `BUILD_CMD` | `gradlew.bat assembleDebug` | Build command |
| `MAX_FILE_SIZE` | 50MB | Telegram file size limit |

## Commands
| Command | Handler | Status |
|---------|---------|--------|
| `/build [dir]` | `files.py:build_cmd` | Working |
| `/build apk [dir]` | `files.py:build_cmd` | Working — build + send APK |
| `/apk` | `files.py:apk_cmd` | Working |
| `/file <path>` | `files.py:file_cmd` | Working |
