# Code map — where everything lives

A path plus what it is *for*. Synthesis, not a file dump: if a reader could get this from
`ls`, it is not earning its line.

**Coverage.** Every Python module, both web pages, and the launch scripts — that is the
whole runtime. Not listed: `__init__.py` (empty), `__pycache__`, and the contents of
`docs/` itself, which [README.md](README.md) maps. Line counts are from 2026-09-02 and
include the uncommitted v0.21.0 work; they drift, the purposes do not. Every path below was
verified with `test -e`; re-verify with `python tools/wiki/wiki-doctor.py`.

---

## Entry and configuration

| Path | Purpose |
|---|---|
| `bot.py` (109) | Wires 20 Telegram commands, 5 callback prefixes and 3 message handlers, then runs **two loops in one process**: PTB polling and the aiohttp app. Also starts the scheduler poll. The error handler reports the exception back into the chat — a bot that dies silently on a phone is indistinguishable from a bot that is ignoring you |
| `config.py` (152) | Every env-tunable value, and — unusually — the *reasons*. The comments on `TYPE_TERMINAL_PROCS`, `TYPE_ENTER_DELAY` and `TYPE_FOCUS_SETTLE` are the failure history in situ, kept there because that is where somebody about to change the number will be looking |
| `start_bot.bat` | The single entry point: hidden tunnel keeper (via `wscript`, because `-WindowStyle Hidden` still flashes a console), then `python bot.py` in a 5-second restart loop. "Restart Bot" re-execs inside this same process (`os.execv`), so it never falls out of the loop |
| `start_tunnel_vps.ps1` · `start_tunnel_hidden.vbs` | Reverse SSH keeper, PC `:8080` → VPS `:18080`. Targets a **hostname, never a raw IP** (`D-003`), and self-guards against a second keeper — two of them fight over the remote port and the loser flaps every 5s |

**Entry points:** `python bot.py`, `start_bot.bat`, `https://<host>:8443` (Mini App).

---

## handlers/ — one surface each

The Telegram side. Every one carries `@auth_required` and `@rate_limit`; a handler without
them is the security model gone.

| Path | Purpose |
|---|---|
| `handlers/input.py` (280) | **The keyboard contract, and the most load-bearing file here.** `type_and_enter()` is the only place allowed to sequence paste-then-Enter (`D-005`); `paste_hotkey_for()` picks `Ctrl+Shift+V` or `Ctrl+V` from the target (`D-006`, `D-007`); `_stuck_modifiers()` releases a Ctrl/Shift/Alt left down by an earlier hotkey, which otherwise turns the next paste into something else entirely |
| `handlers/screen.py` (153) | `/screen`, `/window`, `/crop` — mss capture, Pillow encode, crop region state |
| `handlers/web.py` (605) | The aiohttp app and 18 routes: frame/screen/window, click, scroll, key, type, sh, git, build, status, restart, scope. Owns `_check_auth` and `_check_auth_refine`, and `create_web_app()` with the 30MB body cap that uploads and long dictations both live under. **Over its 200-line budget — `D-015`, [row 5](ROADMAP.md)** |
| `handlers/web_extra.py` (404) | The other 17 routes: windows, focus, folders, code, project, stt, improve, ccmetrics, schedule(s), unschedule, paste, upload, layout. Split from `web.py` by *when it was written*, not by concept, which is why row 5 exists |
| `handlers/panel.py` (275) | The inline-keyboard control panel. `build_keyboard(chat_type)` is rebuilt per message because `web_app` buttons are private-chat-only and Telegram fails the **whole message** elsewhere. `_TYPE_PRESETS` is the single source for the quick-type buttons |
| `handlers/audio.py` (129) | Voice message → Groq Whisper → optional AI cleanup → Type / Type+Enter / Claude buttons |
| `handlers/upload.py` (102) | Document sent in chat → saved → its **path** typed on demand. Deliberately the same shape as `audio.py`, including the per-chat store: `callback_data` is capped at 64 bytes and a Windows path does not fit |
| `handlers/windows.py` (110) | `/win` list-and-focus, `/code` open a project in a new VS Code window |
| `handlers/project.py` (77) | `/project` — the current project that git, build, apk and both UIs follow |
| `handlers/files.py` (185) | `/build`, `/apk`, `/file` — gradle with a `gradlew.bat` guard, APK filtering, the 50MB Telegram ceiling |
| `handlers/shell.py` (52) | `/sh`, with PowerShell-syntax autodetection and a cp866 fallback for a Russian Windows console |
| `handlers/claude.py` (43) | `claude -p` wrapper |
| `handlers/git.py` (75) | Git pass-through with smart defaults (`/git` → status, `/git log` → oneline -20) |
| `handlers/general.py` (53) | `/start`, `/help`, `/status` |

---

## utils/ — one concept each

The split is not cosmetic: it is why the terminal-focus fix (`D-008`) landed in exactly one
place instead of three.

| Path | Purpose |
|---|---|
| `utils/window.py` (147) | Finds a window by title through four rules — exact, containment, 25-char prefix, `tail_key()`. The fourth exists because VS Code retitles per open file (`D-009`). Logs its misses, which it did not always do |
| `utils/winfocus.py` (65) | Actually *activates* it — the Win32 chain that works when `pygetwindow` alone does not |
| `utils/vscode.py` (85) | The command-palette sequence, and **the only copy of it**. `focus_terminal_if_active()` returns `(focused, message)` so a wrong guess is reported rather than swallowed. A test fails if a second copy appears (`D-008`) |
| `utils/layout.py` (114) | Reads and switches the foreground window's keyboard layout. Its own module because the layout silently broke every typing path once: `pyautogui` resolves a character through the *active* layout, so under Russian `VkKeyScanW('v')` is `-1` and the key is never sent (`D-012`) |
| `utils/uploads.py` (69) | Saves an attachment and hands back the **path** — one module for both entry points, because a second copy is how one surface keeps doing it the old way |
| `utils/scheduler.py` (128) | Persistent JSON store + async poll loop; fires focus → type → Enter and notifies. Built for one job: continuing a session the moment a rate limit resets |
| `utils/webauth.py` (104) | Mini App `initData` validation and the scoped `refine.*` token — scope inside the MAC, key derived, header-only (`D-010`) |
| `utils/auth.py` (49) | `@auth_required` and `@rate_limit` |
| `utils/ccmetrics.py` (138) | Reads Claude Code's own local files for model, context use and both rate-limit windows |
| `utils/humanize.py` (113) | Groq chat with a model fallback chain and `<think>` stripping. `chat(system, text)` is the generic entry; `humanize()` a thin wrapper (`D-013`) |
| `utils/improve.py` (119) | The ✨ Improve prompt: profile first, instructions last, deterministic language hint appended (`D-014`) |
| `utils/stt.py` (46) | Groq Whisper |
| `utils/mouse.py` (59) | Remote wheel. Windows routes the wheel by **cursor position**, so it parks the cursor, scrolls, and puts it back |
| `utils/tunnel.py` (60) | Watchdog — restarts the tunnel task when ssh dies |
| `utils/singleton.py` (43) | Kills a stale instance holding `:8080`, in-process via psutil and waiting for real death (`D-002`) |
| `utils/project.py` (54) | Current-project state, shared by every surface |
| `utils/chunks.py` (43) | Splits a message to fit Telegram's 4096-char limit |
| `utils/clipimg.py` (80) | Clipboard image helper. **Kept, unused** — superseded by typing a path |

---

## web/ — the two pages

| Path | Purpose |
|---|---|
| `web/index.html` (2317) | The dashboard: live screen, click and scroll, windows, projects, keys, type, history, scheduler, shell, git, actions. **Anything calling a system endpoint stays in this file** — that rule is the refine view's isolation and a test enforces it |
| `web/refine.html` (464) | `/refine` — mic, cleanup, ✨ Improve, markdown preview, 📋 Copy. No Type button by design: text leaves through the clipboard only (`D-010`) |
| `web/common.js` (511) | The ~460 lines both pages share — `api()`, toasts, theme, History, the hardened markdown renderer, the mic→WAV→STT stack. `window.AUTH_HEADERS` decides which credential every request carries; without it `api()` prefers `initData` and the scoped token is bypassed inside Telegram |

---

## tests/ and tools/

| Path | Purpose |
|---|---|
| `tests/test_web.py` (1397) | 71 of the 94. Beyond the API smoke tests it pins **invariants**: every handler checks auth, no path pairs `_type_text` with its own Enter, the terminal-focus sequence exists once, the client matcher mirrors the server's |
| `tests/test_refine.py` (390) | 23 — the scoped token, and that the system routes reject it |
| `tools/wiki/*.py` | The wiki's own instruments: `check-links.py`, `wiki-doctor.py`, `new-session.py`, and the three hooks wired in `.claude/settings.json` — preflight at session start, guard and commit gate before a shell call, caps after an edit |

---

## Deep slices

### AREA 1 — text from a phone to a terminal prompt

The flow every hard bug in this project lives on. Six hand-offs, each one a place text has
actually been lost.

1. **Arrival** — `text_handler` (`handlers/input.py`), a panel preset, `POST /api/type`, a
   transcript from `handlers/audio.py`, or the scheduler firing. All five converge on one
   function; that convergence is the fix from `D-005`, not an accident of refactoring.
2. **Window** — `focus_window_exact` (`utils/window.py`) matches by four rules and
   `utils/winfocus.py` raises it. Guaranteed at this hand-off: the *window* is foreground.
   **Not** guaranteed: which control inside it has the caret.
3. **Control** — `focus_terminal_if_active` (`utils/vscode.py`) drives the command palette
   to "Terminal: Focus on Terminal View", waits `TYPE_FOCUS_SETTLE`, and **returns whether
   it worked**. `/api/type` echoes that back as a red toast rather than a cheerful `Typed:`.
4. **Modifiers** — `_stuck_modifiers()` releases anything left down. Skipping this turns the
   next paste into a different keystroke entirely.
5. **The paste** — clipboard write, then `paste_hotkey_for(title)`: `Ctrl+Shift+V` for a
   terminal, `Ctrl+V` for an ordinary app. The target is decided by **process** first
   (`TYPE_TERMINAL_PROCS`), title second (`D-007`).
6. **Enter** — after `TYPE_ENTER_DELAY`, never before: inside the bracketed-paste window an
   Enter becomes a newline in the block instead of a submit (`D-005`).

An attachment skips 5 and 6 entirely: `utils/uploads.py` writes the file and the *path* goes
through the same six steps as text, because a path is text and Claude Code opens it.

### AREA 2 — a frame from the PC to the phone

`POST /api/frame` grabs with mss, downscales to the client's requested width, encodes WebP,
and compares an md5 against the hash the client echoed — identical means **204, no body**.
Everything about this path is shaped by one constraint: it is a **single reverse-SSH pipe**.
So the client keeps one request in flight at a time, chains the next from the previous
one's *completion* rather than a timer, pauses entirely when the tab is hidden, and shrinks
the requested width in proportion to how badly the last frame overshot its budget
(`D-011`). The lightbox overrides the width upward, because the zoom view exists to read
fine text.
