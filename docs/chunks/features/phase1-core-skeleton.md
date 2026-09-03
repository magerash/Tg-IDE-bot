# Phase 1 — Core Bot Skeleton

## Quick Reference
| File | Purpose |
|------|---------|
| `bot.py` | Entry point, command routing, polling |
| `config.py` | Loads `.env`, exposes settings, configures logging |
| `utils/auth.py` | `auth_required` decorator |
| `handlers/screen.py` | `/screen` stub |
| `handlers/input.py` | `/key` stub + text echo |
| `handlers/files.py` | `/apk`, `/file` stubs |

## Overview
Minimal working Telegram bot skeleton with:
- `.env`-based config (`python-dotenv`)
- Auth decorator checking `ALLOWED_USER_ID` on every handler
- Stub handlers returning placeholder text for Phase 2+ features
- Dual logging (file `bot.log` + console), DEBUG level

## Key Functions

### `config.py`
- Loads `.env` via `load_dotenv()`
- Exports: `BOT_TOKEN`, `ALLOWED_USER_ID`, `VERSION`, `LOG_FILE`, `logger`

### `utils/auth.py` → `auth_required(func)`
- Decorator wrapping async handler
- Rejects non-matching user IDs with "Unauthorized."
- Logs warning on unauthorized attempts

### `bot.py` → `main()`
- Builds `Application` with token
- Registers handlers: `/start`, `/help`, `/screen`, `/key`, `/apk`, `/file`, text
- Starts polling

## Code Patterns
```python
# Auth decorator usage
from utils.auth import auth_required

@auth_required
async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Response")
```

## Commands (all stubs except /start, /help)
| Command | Handler | Status |
|---------|---------|--------|
| `/start` | `bot.py:start_cmd` | Working |
| `/help` | `bot.py:help_cmd` | Working |
| `/screen` | `handlers/screen.py:screen_cmd` | Stub |
| `/key` | `handlers/input.py:key_cmd` | Stub |
| `/apk` | `handlers/files.py:apk_cmd` | Stub |
| `/file` | `handlers/files.py:file_cmd` | Stub |
| plain text | `handlers/input.py:text_handler` | Echo stub |
