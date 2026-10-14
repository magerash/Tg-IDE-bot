# Phase 2 — Screen Capture & Input

## Quick Reference
| File | Purpose |
|------|---------|
| `handlers/screen.py` | `/screen` full monitor, `/window` active window |
| `handlers/input.py` | Text typing, `/key`, `/type`, `/click`, `/focus` |
| `utils/window.py` | `focus_window()`, `get_active_window_rect()` |
| `config.py` | `SCREENSHOT_QUALITY`, `SCREENSHOT_COOLDOWN`, `TYPING_INTERVAL` |

## Overview
Screen capture via `mss` + `Pillow` (JPEG), keyboard/mouse via `pyautogui`, text input via Win32 clipboard API + Ctrl+V, window management via `pygetwindow`.

## Key Functions

### `handlers/screen.py`
- `screen_cmd()` — captures full primary monitor, sends as JPEG photo
- `window_cmd()` — captures active window bounds, sends as JPEG photo
- `_grab_to_jpeg(region)` — mss grab → PIL Image → JPEG BytesIO
- `_check_cooldown()` — enforces `SCREENSHOT_COOLDOWN` between captures

### `handlers/input.py`
- `_set_clipboard(text)` — Win32 API clipboard (no focus steal)
- `_type_text(text)` — clipboard paste via Ctrl+V; logs the target window, releases stuck modifiers first
- `_stuck_modifiers()` — Ctrl/Shift/Alt/Win Windows still believes are held
- `type_and_enter(text, enter=True)` — **the only place paste and Enter are sequenced** (see below)
- `text_handler()` — pastes plain text + Enter
- `type_cmd()` — `/type <text>` for text starting with `/`
- `key_cmd()` — `/key enter`, `/key ctrl+c`, `/key backspace 30` (repeat support)
- `click_cmd()` — `/click x y`
- `focus_cmd()` — `/focus <title>`

### `utils/window.py`
- `focus_window(title)` — partial match, minimize/restore workaround for Windows
- `focus_window_exact(title)` — exact title match (used by `/win` picker)
- `list_windows(limit=30)` — visible window titles, deduplicated
- `get_active_window_rect()` → `(left, top, width, height)` or `None`
- See `window-management.md` for `/win` + `/code`

## Config Values
| Setting | Default | Purpose |
|---------|---------|---------|
| `SCREENSHOT_QUALITY` | 70 | JPEG compression % |
| `SCREENSHOT_COOLDOWN` | 2 | Min seconds between screenshots |
| `TYPING_INTERVAL` | 0.02 | Delay between keystrokes |
| `TYPE_ENTER_DELAY` | 0.45 | Gap between the paste and the Enter that submits it |

## Ctrl+V is not the paste key in a Claude Code terminal (v0.17.1)
Symptom: identical to "nothing typed" — bot answers `Typed: ...`, prompt stays empty.

Claude Code binds **Ctrl+V to "paste image from clipboard"**, so a text Ctrl+V
does nothing at all in a terminal running it. Everything else is fine, which is
what makes it confusing: the key *is* delivered (Ctrl+Shift+P opens the command
palette), the clipboard *does* hold the text, the window *is* foreground.

Proven by elimination against the live window — the order worth repeating:
1. Elevated target? No — all VS Code windows were one non-elevated pid (UIPI out).
2. Focus? `focus_window_exact` → `ok=True`, window really foreground.
3. Clipboard? `Get-Clipboard` returned all 310 chars.
4. Keys arriving? `Ctrl+Shift+P` opened the palette. **Yes.**
5. `pyautogui.write` → `> TYPED-999` appeared; Ctrl+V → nothing. Paste alone.
6. `Ctrl+Shift+V` → `> CSV-111` ✅. `Shift+Insert` → nothing.

`paste_hotkey_for(title, proc)` picks the key from the target window:
terminal → **Ctrl+Shift+V**; anything else → **Ctrl+V**. Plain apps must not get
Ctrl+Shift+V — Notepad has no such binding and would receive nothing.
Config: `TYPE_PASTE_HOTKEY`, `TYPE_TERMINAL_PASTE_HOTKEY`, `TYPE_TERMINAL_HINTS`,
`TYPE_TERMINAL_PROCS`.

## The keyboard layout ate every keystroke (v0.21.0) — read this FIRST

Symptom: nothing the bot types arrives, on **every** surface at once, while focus,
clipboard, logs and HTTP all report success. Looks exactly like a code regression
right after a release. It is not.

`pyautogui` turns a character into a key with `VkKeyScanW`, which asks the
**active keyboard layout**. Under Russian (`0x419`) there is no latin `v`, so
`VkKeyScanW('v')` returns `-1` and pyautogui sends **nothing at all**:

- `ctrl+shift+v` delivers Ctrl and Shift with no V -> no paste, ever
- `ctrl+shift+p` never opens the command palette -> `_palette()` no-ops, the
  terminal is never focused, and the caller's text goes to the editor while the
  API answers `terminal focused`
- `pyautogui.write` drops every letter

Measured 2026-08-31 against a live console: `echo TGBOT-MARKER-42` arrived as
`--42` — digits and `-` exist in the Russian layout, the letters do not. One
layout switch by the operator makes the whole bot mute.

Fix: `press_keys(*names)` in `handlers/input.py` sends **virtual-key codes**
(`_VK`), which are the same number in every layout — down in order, up in
reverse, `KEYEVENTF_EXTENDEDKEY` for arrows/Insert/Delete so NumLock cannot turn
an arrow into a digit. Unknown names fall back to pyautogui (a layout-dependent
keystroke beats none). Every caller routes through it: `_type_text`,
`type_and_enter`, `/api/key`, panel keys, `_palette`. `test_keys_do_not_depend_on_
the_keyboard_layout` fails if any of them goes back to `pyautogui.hotkey/press`.

Diagnostic that settles it in one command — if this prints `-1`, the layout is
the problem and no amount of window/paste-key work will help:

```python
import ctypes; print(ctypes.windll.user32.VkKeyScanW(ord("v")))
```

**The process decides, not the title (v0.21.0).** A terminal wears the name of
whatever runs inside it. Claude Code retitles Windows Terminal to `✳ Claude Code`,
which matches no title hint, so the title-only rule sent Ctrl+V — the exact key
Claude Code swallows as "paste image". The v0.17.1 bug came straight back through
a different door, for the one target this bot exists to type into. The executable
never changes, so `get_active_window_process()` (foreground HWND → pid → psutil
name) is asked first and `TYPE_TERMINAL_PROCS` decides; titles stay as a fallback
for when the process cannot be read. `claude.exe` (Claude Desktop) is a GUI app
and must stay on Ctrl+V — a `claude` substring rule would break it.

The debug line names both: `Typing 38 chars into '✳ Claude Code' [windowsterminal.exe] via ctrl+shift+v`.

**Nothing in the type path picks a target** — the foreground window gets the text.
Measured 2026-08-31: `focus_window_exact('✳ Claude Code')` returned `ok=True` and
held for 3s in one trial, while in the next the foreground was `Claude` (Claude
Desktop, which grabs focus on its own) 700ms later. So `/api/type` now returns
`window` + `proc` and the dashboard toast reads `Sent to '<window>': …` — a message
eaten by an app that stole focus must be distinguishable from one that arrived.

## The window is not the target (diagnosed v0.19.1) — "typing does nothing"
Symptom, identical to both bugs below: bot answers `Typed: …`, prompt stays empty,
every surface affected (TG chat, Mini App, presets). Ruled out one at a time
against the live box, in this order — repeat this, do not re-derive it:

1. Bot alive? `getUpdates` 200, no webhook, `pending_update_count: 0`, and
   `bot.input: Typing N chars into '<window>' via <key>` present per attempt. **Yes.**
2. Clipboard written? Read it straight after a send — it held the sent text. **Yes.**
3. Keystrokes injected at all? `pyautogui.write` into the foreground window put its
   marker on screen. **Yes.**
4. Paste key honoured? Markers pasted with `ctrl+shift+v` **appeared spliced into the
   live prompt line**. Also yes — so nothing in the chain below is broken.

What is missing is the last hop: **`focus_window_exact` raises the window, never the
control inside it.** VS Code foreground with the caret in the editor rather than the
integrated terminal → `Ctrl+Shift+V` is a VS Code *editor* binding and the text is
gone; Claude Desktop foreground with its chat box unfocused → same. The keystroke is
delivered correctly and consumed by the wrong control, and every caller still reports
success, which is what makes it read as "the bot is dead".

**Fixed in v0.20.0.** The command-palette step the scheduler had all along — focus the
window, wait `SCHEDULE_FOCUS_SETTLE`, then run "Terminal: Focus on Terminal View",
which is position-independent — moved into **`utils/vscode.py`** and is now callable
from anywhere. `POST /api/type {terminal: true}` runs it before typing;
`{new_terminal: true}` opens a fresh terminal instead of reusing the active one (a
reused terminal that already runs Claude Code takes `claude` as a chat message, not a
launch). The scheduler's private `_focus_vscode_terminal()` was deleted, and
`test_terminal_focus_lives_in_one_place` fails if a second copy of the palette string
appears — a divergent copy is how one surface silently goes back to typing into the
editor. `text_handler` (plain Telegram text) still types without the flag: it targets
whatever the operator focused, not necessarily VS Code.

The outcome is always reported: `focus_terminal_if_active()` returns `(focused, msg)`,
`/api/type` echoes `terminal` / `terminal_msg`, and a non-VS-Code foreground gives a red
toast rather than a cheerful `Typed:`. Typing happens either way — a wrong guess about
the foreground window must not eat the text.

Test it in two runs before touching code: click into the terminal prompt, send from the
phone (lands), then click into an editor tab and send again (vanishes). Same window,
same key, opposite result.

## Enter must wait for the paste (v0.17.0) — "typing is broken"
Symptom: bot answers `Typed: ...`, nothing happens in Claude Code. Sometimes it
works. Two messages later both appear **glued together** (`Test` + `Test` →
`TestTest`) as one submit.

Cause: `_type_text` pasted, slept **0.1s**, then pressed Enter. Claude Code (any
TUI doing bracketed-paste detection) buffers the pasted block for a moment and
treats an Enter arriving inside that window as **part of the paste** — a literal
newline, not submit. The text is stranded in the input box; the next successful
Enter submits everything at once. A race, so it looks random.

Rules:
- Never pair `_type_text` with your own `pyautogui.press("enter")`. Call
  `type_and_enter(text, enter)`. `tests/test_web.py` fails the build if a caller
  (`handlers/web.py`, `panel.py`, `audio.py`, `utils/scheduler.py`) does it again.
- `TYPE_ENTER_DELAY` (config, default **0.45s**, env-tunable) is the gap. Raise it
  if messages still pile up unsent.
- `/api/paste` is the one legitimate bare `_type_text` — it types an image path
  with no Enter, and the caller types the user's text afterwards.
- A modifier left down by an earlier hotkey (Auto = Shift+Tab ×3, the Alt tap in
  `force_foreground`) turns Ctrl+V into Ctrl+Shift+V and nothing arrives —
  `_stuck_modifiers()` releases them first and logs a warning when it fires.

Debugging it: `bot.input: Typing N chars into '<window>'` names the window that
received the paste. `focus_window_exact` logs misses with the live window list —
before v0.17.0 it logged only successes, so a chip matching nothing left no trace.

## The mouse (row 11) — buttons, drag, and the delay that was hiding in pyautogui

**Every mouse event goes through `utils/mouse.py`.** `click_at(x, y, button, double)`,
`drag(x1, y1, x2, y2, button, steps)`, `scroll_at(notches, x, y)`. Nothing else may call
`pyautogui.click` / `mouseDown` / `dragTo` — `test_every_click_path_uses_the_mouse_module`
fails if it does, and the test strips comments first so a comment naming the banned call is
still allowed to explain the rule.

### `pyautogui.PAUSE = 0` — read this before adding any mouse code (`D-019`)

pyautogui sleeps `PAUSE` (0.1s) after **every** call it owns. Measured on this machine:

```
moveRel(0,0) with PAUSE=0.1 : 100.5 ms
moveRel(0,0) with PAUSE=0   :   0.1 ms
```

`pyautogui.click(x, y)` is a move plus a click, so a remote click spent **~200ms asleep**
before an event was sent and `scroll_at` ~300ms — against a ~133ms warm tunnel round trip.
It is now `0`, set beside `FAILSAFE` in `handlers/input.py`.

**What the blanket delay was silently paying for**, now explicit in `config.py` and spent in
`utils/mouse.py`:

| Gap | Default | Why it exists |
|---|---|---|
| `MOUSE_MOVE_SETTLE` | 0.04 | the window must process `WM_MOUSEMOVE` before the button goes down, or the click lands on a control that has not registered the hover — menus and tooltips open on the *move* |
| `MOUSE_CLICK_HOLD` | 0.02 | down→up; a button never observed down is how a handler decides no drag started |
| `MOUSE_DOUBLE_GAP` | 0.06 | between the two pairs of a double click — clamped to 40% of the machine's real `GetDoubleClickTime` |
| `MOUSE_DRAG_HOLD` | 0.12 | press and move in the same tick is a click, not a drag |
| `MOUSE_DRAG_STEPS` / `_STEP_DELAY` | 12 / 0.012 | a single jump drags nothing — controls read a drag from the `WM_MOUSEMOVE` stream |

**The regression turning PAUSE off would have caused, caught in the same change:** Windows
routes the wheel by the **cursor position at the moment of injection**. `scroll_at` parks the
cursor and then scrolls, and the gap between those two came free from PAUSE. Without an
explicit settle the wheel is stamped with a position the cursor has not reached, and the
scroll goes to the window the operator was looking at *before*. `scroll_at` now sleeps
`MOUSE_MOVE_SETTLE` between them, and the test asserts the order.

The keyboard paths needed nothing: `press_keys` has always sent its virtual-key events
back-to-back with no gap.

### Buttons and double click

`click_at(x, y, button, double)` — `button` is `left` (default), `right` or `middle`. An
**absent** button is left, because clients omit the field; a **wrong** one raises `ValueError`
and `/api/click` answers 400. Never a silent left click: a right click quietly downgraded is a
context menu that did not open, which looks exactly like a dead gesture.

A double click is **not** an API call and **not** two requests. Windows merges two ordinary
down/up pairs if they arrive inside `GetDoubleClickTime` — 500ms by default, and
user-configurable, so `double_click_time()` reads the real value and the gap is clamped to 40%
of it. Two HTTP requests through this tunnel cannot meet that deadline: one warm round trip is
~133ms and the old pyautogui overhead was another ~200ms per click.

### Drag — one request, released in a `finally` (`D-018`)

`POST /api/drag {x, y, to_x, to_y, button, steps}` presses, interpolates, releases.

The protocol-shaped alternative (`/api/mouse {down|up|move}`, which is what RustDesk's
`MouseEvent.mask` encodes) is right for a socket and wrong for this transport. **A button held
between HTTP requests is a button the tunnel can strand**: lose the `up` — dropped connection,
backgrounded webview, phone locking mid-gesture — and the desktop is left with the mouse down,
where every movement is a selection, and nothing on the phone can say so. One request cannot
be half-delivered, and the release is in a `finally` so even a mid-drag exception lifts the
button.

`/click x y [left|right|middle]` in Telegram chat takes the button too.

## Lessons Learned
- Enter pressed too soon after a paste is swallowed by the paste itself (v0.17.0)
- `pyautogui.write()` garbles long text → use clipboard paste instead
- `pygetwindow.activate()` fails on Windows (error 258) → use minimize/restore
- `tkinter` clipboard steals focus → use Win32 API via ctypes directly
- PowerShell `Set-Clipboard` truncates long text in args → avoid

## Code Patterns
```python
# Win32 clipboard (no focus steal)
user32.OpenClipboard(0)
user32.EmptyClipboard()
data = text.encode("utf-16-le") + b"\x00\x00"
h_mem = kernel32.GlobalAlloc(0x0002, len(data))
p_mem = kernel32.GlobalLock(h_mem)
ctypes.memmove(p_mem, data, len(data))
kernel32.GlobalUnlock(h_mem)
user32.SetClipboardData(CF_UNICODETEXT, h_mem)
user32.CloseClipboard()

# Key repeat
/key backspace 30  → last arg is digit → repeat N times (max 200)
```

## Commands
| Command | Handler | Status |
|---------|---------|--------|
| `/screen` | `screen.py:screen_cmd` | Working |
| `/window` | `screen.py:window_cmd` | Working |
| `/key <key> [N]` | `input.py:key_cmd` | Working |
| `/type <text>` | `input.py:type_cmd` | Working |
| `/click x y` | `input.py:click_cmd` | Working |
| `/focus <title>` | `input.py:focus_cmd` | Working |
| plain text | `input.py:text_handler` | Working |

## Dependencies Added
- `Pillow` (JPEG conversion from mss raw pixels)
