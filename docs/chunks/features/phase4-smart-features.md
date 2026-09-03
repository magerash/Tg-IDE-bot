# Phase 4 — Smart Features

## Quick Reference
| File | Purpose |
|------|---------|
| `handlers/shell.py` | `/sh <cmd>` — direct shell execution |
| `handlers/claude.py` | `/claude <prompt>` — claude -p wrapper |
| `utils/chunks.py` | `send_long_text()` — message splitting/file fallback |
| `handlers/input.py` | Auto-screenshot after typing (2s delay) |

## Overview
Shell command execution, Claude CLI integration, message chunking for long output, and auto-screenshot after text input.

## Key Functions

### `handlers/shell.py`
- `sh_cmd()` — runs command via subprocess, 60s timeout, returns stdout+stderr
- Uses `send_long_text()` for long output

### `handlers/claude.py`
- `claude_cmd()` — runs `claude -p <prompt>`, 2 min timeout
- Uses `send_long_text()` for long responses

### `utils/chunks.py`
- `send_long_text(update, text)` — auto-splits:
  - <= 4096 chars: single message
  - <= 12288 chars: split into chunks
  - > 12288 chars: send as .txt file

### `handlers/input.py` (updated)
- `text_handler()` — now auto-sends screenshot 2s after typing

## Commands
| Command | Handler | Status |
|---------|---------|--------|
| `/sh <cmd>` | `shell.py:sh_cmd` | Working |
| `/claude <prompt>` | `claude.py:claude_cmd` | Working |
| auto-screenshot | `input.py:text_handler` | Working |
