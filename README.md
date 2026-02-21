# TG-IDE-Bot v0.7.3

Telegram bot for remote PC control — screen capture, keyboard/mouse input, file delivery.

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env  # add BOT_TOKEN and ALLOWED_USER_ID
python bot.py
```

## Commands
| Command | Description |
|---------|-------------|
| `/screen` | Screenshot (full or crop region) |
| `/window` | Capture active window |
| `/crop x y w h` | Set crop region for `/screen` |
| `/crop window` | Crop to active window bounds |
| `/crop off` | Reset to full screen |
| `/key <key>` | Send special key (enter, ctrl+c, tab) |
| `/key <key> <N>` | Repeat key N times |
| `/type <text>` | Type text literally (for /commands) |
| `/click x y` | Mouse click at coordinates |
| `/focus <title>` | Focus a window by title |
| `/build [dir]` | Run gradle build |
| `/apk [filter]` | Send latest APK (debug/release/list) |
| `/file <path>` | Send any file |
| `/sh <cmd>` | Run shell command |
| `/claude <prompt>` | Ask Claude |
| `/git [cmd]` | Git CLI (status/log/diff/branch/commit/push/pull/cd) |
| `/panel` | Inline keyboard control panel |
| `/status` | Bot uptime & system info |
| `/help` | List all commands |
| Plain text | Typed into active window + Enter |

## Changelog

### v0.7.3 2026-02-21
- Panel: added Shift+Tab, Build APK, Backspace×30 buttons

### v0.7.2 2026-02-20
- `/build apk` subcommand: build + auto-send APK on success

### v0.7.1 2026-02-19
- Compact build output: success shows last line only, failure shows stderr only

### v0.7.0 2026-02-18
- `/panel` command: inline keyboard control panel with button grid
- Buttons: Screen, Window, Git Status/Log/Diff, Build, APK, Status, key shortcuts
- Auth + rate limiting on callback queries

### v0.6.0 2026-02-17
- `/git` command: full git CLI pass-through with smart defaults
- Runtime working directory switch via `/git cd`
- Auto-join commit messages, `GIT_DIR` config

### v0.5.1 2026-02-17
- Fix: clipboard 64-bit crash on text typing
- Fix: `/sh` Cyrillic encoding (cp866 fallback)
- Fix: `/sh` auto-routes PowerShell commands

### v0.5.0 2026-02-17
- Rate limiting: per-command cooldowns on all handlers (1s–60s)
- Auto-restart: `start_bot.bat` with 5s retry loop
- Trimmed `bot.py` and `input.py` under file limits

### v0.4.0 2026-02-17
- Crop mode: `/crop x y w h`, `/crop window`, `/crop off`
- `/status` command with uptime, OS, Python info
- Reorganized `/help` by categories

### v0.3.0 2026-02-17
- File delivery: `/build`, `/apk` with filters, `/file <path>`
- Gradle build with configurable project dir, 5 min timeout

### v0.2.0 2026-02-17
- Screen capture: `/screen` (full monitor), `/window` (active window)
- Input: text typing via clipboard paste, `/key` with combos and repeat
- New commands: `/click`, `/focus`, `/type`
- Window management with minimize/restore focus workaround

### v0.1.0 2026-02-16
- Core bot skeleton: auth, command routing, logging
- Stub handlers for all planned commands
