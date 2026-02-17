# TG-IDE-Bot v0.4.0

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
| `/status` | Bot uptime & system info |
| `/help` | List all commands |
| Plain text | Typed into active window + Enter |

## Changelog

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
