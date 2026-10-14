# Scheduled Messages

Queue text to be typed into a window at a future time — main use: fire a message
right after a Claude Code **limit reset** (from the metrics reset times) so a
session auto-continues unattended. Create, list, and cancel from the web dashboard.

## Quick Reference

| Item | Value |
|------|-------|
| Util | `utils/scheduler.py` |
| Store | `scheduled_messages.json` (project root, gitignored; survives restart) |
| Loop | `run_scheduler_loop(bot)` — started in `bot.py run()`, polls every `SCHEDULE_POLL` (10s) |
| Endpoints | `POST /api/schedule`, `GET /api/schedules`, `POST /api/unschedule` |
| UI | `Scheduled` panel (below History) in `web/index.html` |
| Config | `SCHEDULE_FILE`, `SCHEDULE_POLL` |

## Job shape

```json
{"id":"a1b2c3d4","text":"continue","when":1784732880,"enter":true,
 "window":"My habits - Visual Studio Code","terminal":true,"created":1784730000}
```

- `when` = epoch seconds. `window` = title to refocus before typing (defaults to
  the window focused when the job was created). `enter` appends Enter.
- `terminal` (default true) — for a VS Code target, move focus into the integrated
  terminal before typing (Claude Code runs there; plain window focus lands in the editor).

## Flow

1. **Create** (`api_schedule`) — validates text + `when`; rejects past times;
   captures `get_active_window_title()` as the target if none given; `add_job()`.
2. **Loop** (`run_scheduler_loop`) — every 10s loads store, splits due (`when<=now`)
   vs remaining, saves remaining, then for each due job `_fire_sync()` in a thread:
   `focus_window_exact(window)` (best effort) → `_type_text()` → `pyautogui.press("enter")`.
   Notifies the user over Telegram (`bot.send_message(ALLOWED_USER_ID, …)`).
3. **List / Cancel** — `list_jobs()` sorted by time; `remove_job(id)`.

- Store writes are atomic (`.tmp` + `os.replace`) under an `asyncio.Lock`.
- Fire reuses the same typing path as `/api/type` (`handlers.input._type_text`).

## UI (`web/index.html`)

- Panel: message textarea, `datetime-local` input, **After 5h reset** /
  **After weekly reset** quick buttons (fill time from `_cc5hReset`/`_ccWkReset`
  metrics globals, +1 min), Schedule button, live list with countdown + ✕ cancel.
- `doSchedule()` → POST; `loadSchedules()` renders (called on login + every 30s via
  `refreshStatus`); `schedAtReset()` fills the time; `cancelSchedule()` → unschedule.

## Caveats

- Target window must exist/match at fire time; if focus fails it types into
  whatever is focused (best effort).
- **Focus settle**: `_fire_sync` sleeps `SCHEDULE_FOCUS_SETTLE` (0.6s) after focusing
  before typing — bringing a *non-foreground* window forward is async in Windows, so
  typing immediately pastes into the old foreground window. This was the "fires into
  the currently-focused window but not into a different one" bug.
- **Terminal focus**: `focus_vscode_terminal()` (moved to **`utils/vscode.py`** — the web
  dashboard's Claude launcher and `/api/type {terminal:true}` need the same sequence, and a
  second copy would drift silently) runs the command palette
  (`Ctrl+Shift+P` → "Terminal: Focus on Terminal View" → Enter) — position/layout
  independent, unlike a fixed click. Gated on `terminal` flag + "Visual Studio Code"
  in the window title.
- Reset quick-buttons need metrics loaded first (`loadCCMetrics`). See [[cc-metrics]].

## Tests

`tests/test_web.py` — `test_scheduler_add_list_remove` (round-trip on temp store),
`test_schedule_endpoints` (auth + past-time/missing-when rejection). 14 total.
