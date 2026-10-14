# Phase 5 — Reliability & Polish

## Quick Reference
| File | Purpose |
|------|---------|
| `utils/auth.py` | `auth_required` + `rate_limit(seconds)` decorators |
| `bot.py` | `/status`, `/help`, command routing (91 lines) |
| `handlers/screen.py` | `/crop`, `/screen`, `/window` with 2s rate limit |
| `handlers/input.py` | All input commands with 1s rate limit (149 lines) |
| `handlers/shell.py` | `/sh` with 5s rate limit, cp866 encoding, PowerShell auto-detect |
| `handlers/claude.py` | `/claude` with 10s rate limit |
| `handlers/files.py` | `/build` 60s, `/apk` `/file` 3s rate limits |
| `start_bot.bat` | Auto-restart loop (5s delay between restarts) |
| `config.py` | `SCREENSHOT_COOLDOWN` (legacy, replaced by decorator) |

## Overview
Rate limiting via `@rate_limit(seconds)` decorator on all handlers, auto-restart batch script, categorized help text, `/status` with uptime/OS/Python info, `/crop` for targeted screenshots.

## Key Functions

### `utils/auth.py` — rate_limit decorator
- `rate_limit(seconds)` — decorator enforcing per-command cooldown
- Uses `_cooldowns` dict keyed by function name
- Stack with `@auth_required` (auth first, then rate limit)
- Returns "Cooldown: wait Ns" message when triggered

### `bot.py`
- `status_cmd()` — version, uptime, OS, Python version
- `HELP_TEXT` — compact, organized by category (Screen, Input, Files, Tools)

### `handlers/screen.py` — crop mode
- `crop_cmd()` — `/crop x y w h`, `/crop window`, `/crop off`
- `_crop_region` — global state, used by `/screen` when set

### `handlers/input.py` — clipboard fix
- `_set_clipboard()` uses proper 64-bit `ctypes` argtypes/restype
- NULL checks on `GlobalAlloc`/`GlobalLock` prevent access violations
- `try/finally` ensures `CloseClipboard` always runs

### `handlers/shell.py` — encoding & PowerShell
- Raw bytes decoded: try UTF-8 strictly, fallback to cp866 (Russian OEM)
- Auto-detects PowerShell syntax (`Get-`, `ForEach-Object`, `$_`, etc.)
- Routes PowerShell commands through `powershell -NoProfile -Command`

### `start_bot.bat`
- Loops: runs `python bot.py`, waits 5s on exit, restarts
- User can add to Windows Task Scheduler for auto-start on boot

## Rate Limits
| Command | Cooldown | Handler |
|---------|----------|---------|
| `/screen`, `/window` | 2s | `handlers/screen.py` |
| `/key`, `/type`, `/click`, `/focus`, text | 1s | `handlers/input.py` |
| `/apk`, `/file` | 3s | `handlers/files.py` |
| `/sh` | 5s | `handlers/shell.py` |
| `/claude` | 10s | `handlers/claude.py` |
| `/build` | 60s | `handlers/files.py` |

## Code Pattern
```python
@auth_required
@rate_limit(5.0)
async def handler(update, context):
    ...
```

## Commands
| Command | Handler | Status |
|---------|---------|--------|
| `/status` | `bot.py:status_cmd` | Working |
| `/crop x y w h` | `screen.py:crop_cmd` | Working |
| `/crop window` | `screen.py:crop_cmd` | Working |
| `/crop off` | `screen.py:crop_cmd` | Working |
| `/help` | `bot.py:help_cmd` | Working |
| Rate limiting | `utils/auth.py:rate_limit` | Working |
| Auto-restart | `start_bot.bat` | Working |

## Async Architecture (v0.8.0+)
All blocking operations now run via `asyncio.to_thread()`:
- `subprocess.run()` — shell, build, git, claude handlers
- `pyautogui.*` — key presses, clicks, typing
- `_grab_to_jpeg()` — screenshot capture
- `focus_window()` — window activation

This prevents the event loop from freezing during long operations (builds, shell commands).

### Global Error Handler
`bot.py` registers an `error_handler` that catches unhandled exceptions, logs full tracebacks, and sends error messages to the user's chat.

## File Size Compliance
| File | Lines | Limit |
|------|-------|-------|
| `bot.py` | 90 | 100 |
| `handlers/input.py` | 152 | 150 |
| `utils/auth.py` | 49 | 100 |
