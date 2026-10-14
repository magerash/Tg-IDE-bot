# Panel — Inline Keyboard Control Panel

## Quick Reference
- Command: `/panel`
- File: `handlers/panel.py` (~210 lines)
- Callback pattern: `^p:` via `CallbackQueryHandler`

## Overview
Inline keyboard with button grid for one-tap access to common commands. No external hosting needed — pure Telegram API.

## Button Layout
```
[Screen] [Window]
[Git Status] [Git Log] [Git Diff]
[Build] [Build APK] [APK] [Status]
[Enter] [Esc] [Ctrl+C] [Tab]
[Shift+Tab] [Bksp×30] [Auto (Sh+Tab×3)] [Click 250,1000]
[/clear] [/caveman] [Ultrathink]
[/plan] [/hae:release-plan] [/hae:twin]
[Let's finish (LF)] [LF CB] [LF NB] [/model]
```
Web UI mirrors buttons + gray `.hint` note: "LF = let's finish · CB = commit to current branch · NB = commit + new branch".

## Type Presets
`_TYPE_PRESETS` dict maps callback → text; single handler types text + Enter into focused window.
Callbacks listed in `_TYPE_NO_ENTER` skip the Enter and leave the cursor in the field (trailing
space in the text) so you can keep typing — used for keywords/prefixes, not standalone commands.
Same presets mirrored in web UI (`web/index.html` Type Text panel, `doTypePreset(text, enter=true)`).
| Callback | Types | Enter |
|----------|-------|-------|
| `type_finish` | `let's finish` | ✅ |
| `type_finish_cur` | `let's finish. current branch` | ✅ |
| `type_finish_new` | `let's finish. new branch` | ✅ |
| `type_clear` | `/clear` | ✅ |
| `type_caveman` | `/caveman` | ✅ |
| `type_ultra` | `Ultrathink ` | ❌ keyword, not a slash command — prefixes your prompt |
| `type_plan` | `/plan` | ✅ |
| `type_rplan` | `/hae:release-plan` | ✅ |
| `type_twin` | `/hae:twin ` | ❌ takes an argument |
| `type_model` | `/model` | ✅ |

## Key Functions

### `panel_cmd(update, context)`
- Decorated: `@auth_required`
- Sends "Control Panel" message with `InlineKeyboardMarkup`

### `panel_callback(update, context)`
- Handles `CallbackQuery` with `p:` prefix
- Auth: manual `ALLOWED_USER_ID` check (decorators don't apply to callbacks)
- Rate limit: 2s cooldown per command via `_cooldowns` dict
- Dispatches to command logic, sends responses via `bot.send_*`

## Callback Data Format
`p:{command}` — e.g. `p:screen`, `p:git_status`, `p:key_enter`

## Reused Imports
| Source | What |
|--------|------|
| `handlers/screen.py` | `_grab_to_jpeg()` |
| `handlers/files.py` | `_find_apks()` |
| `handlers/git.py` | `_git_dir` (lazy import) |
| `utils/window.py` | `get_active_window_rect()` |
| `utils/chunks.py` | `send_long_text_to_chat()` |

## Registration in bot.py
```python
from handlers.panel import panel_cmd, panel_callback
app.add_handler(CommandHandler("panel", panel_cmd))
app.add_handler(CallbackQueryHandler(panel_callback, pattern="^p:"))
```

## Async Operations (v0.8.0+)
All subprocess calls in panel_callback use `await asyncio.to_thread(subprocess.run, ...)`.
Build/Build APK buttons wrapped in try/except for TimeoutExpired.

## Mini App buttons (v0.19.0)
`build_keyboard(chat_type)` prepends a `web_app` row — **🖥 Dashboard** (`miniapp_url()`) and
**✨ Refine** (`refine_url()`) — to `_BASE_ROWS`. Built per message, never once at import, because
the row depends on where the message is going:

- **Private chats only.** Telegram rejects `web_app` inline buttons anywhere else with
  `BUTTON_TYPE_INVALID` and fails the **whole message** — an unguarded row would take `/panel` down
  in any group the bot sits in. `@auth_required` checks the *user*, not the chat.
- Empty or non-HTTPS `WEBAPP_URL` → no buttons rather than a broken panel.
- Guarded by `test_panel_web_app_buttons_private_only`, which also asserts the base rows survive.

The chat menu button is untouched — Telegram allows exactly one and it stays on the dashboard.

## Related
- `utils/chunks.py` — `send_long_text_to_chat(bot, chat_id, text)` added for callback use
- `handlers/web.py` — Web dashboard with same commands via REST API
- `refinement-view.md` — the second Mini App surface reached from this panel
- See: `phase2-screen-input.md`, `phase3-file-delivery.md`, `git-handler.md`
