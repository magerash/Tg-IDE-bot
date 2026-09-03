# Changelog

The released history of Tg-IDE-bot, version by version, newest first. Lifted verbatim out of
`CLAUDE.md` on 2026-09-02 (`D-001`), where it had grown to 330 of that file's 527 lines — an
instruction file that is two thirds history gets followed less reliably than a short one, and
history is what a wiki is for.

**This file is the record of what shipped.** What is *unreleased* is
[ROADMAP.md](ROADMAP.md); why any of it is shaped this way is [DECISIONS.md](DECISIONS.md);
how a single feature behaves is [chunks/features/](chunks/features/).

**Versioning.** `v0.0.x` small changes and fixes · `v0.x.0` new features · `v1.0.0` first
stable, not yet reached. A version is bumped only on the operator's "Let's finish" — see
[../AGENTS.md](../AGENTS.md).

---

## Current Version
- **Version**: v0.21.0
- **VersionCode**: 44
- **Last Updated**: 2026-09-03

### Changelog v0.21.0 2026-09-03
- **The project's documentation is in git for the first time.** 31 files and 160KB of feature chunks lived in `materials/`, which was in `.gitignore`, beside a 527-line `CLAUDE.md` that was also gitignored and carried 20 versions of changelog — none of it in a clone. `materials/` → **`docs/`**, adopted onto the `llm-wiki-kit` template: preflight, update regulation, document map, `code-map.md` (44 verified paths + two deep slices), `ROADMAP.md`, and a `DECISIONS.md` ledger whose `D-002`–`D-014` were **recovered** from the changelog and the code rather than invented. `CLAUDE.md` drops 527 → 97 lines and imports the new tracked `AGENTS.md`; this changelog is what moved out of it (`D-001`)
- One file stays deliberately gitignored: `docs/imported/vps-architecture.md`, which maps the VPS, the VPN subnets and the operator's other services. **This repository is public.** `docs/documentation/README-vps.md` is the tracked stub. Related finding, on the record as `B-1`: `README.md`, `start_tunnel_vps.ps1` and commit `e039070`'s *message* have named the tunnel host and both VPS addresses since 2026-07-21 — withholding one file limits the detail, it does not un-publish the host
- **📎 Attachments from the phone** — send a document to the bot, or upload from the Mini App, and its **path** is typed into the terminal (`utils/uploads.py`, `handlers/upload.py`, `POST /api/upload`). Claude Code cannot take a pasted document any more than a pasted image, but it *reads a file whose path is in the prompt* — so the file arrives whole and instantly, whatever its size, instead of being pushed through the clipboard as a wall of text bracketed paste has to survive. One module for both entry points; the per-chat store exists because `callback_data` caps at 64 bytes and a Windows path does not fit
- **⌨ Typing survived a Russian keyboard layout** (`utils/layout.py`, `GET/POST /api/layout`). `pyautogui` resolves a character through the **active** layout, so under Russian `VkKeyScanW('v')` returns `-1` and the key is simply never sent — every typing path broke, invisibly, because of a setting in the target window that a phone cannot see. Typing now goes out as virtual-key codes and no longer cares; the operator still does, so the layout is readable and switchable from a pill in the bottom bar (`D-012`)
- **Terminal-ness is decided by the process, not the window title** (`TYPE_TERMINAL_PROCS`). A terminal wears the name of whatever runs inside it, so `WindowsTerminal.exe` showing `✳ Claude Code` matched no title hint, took the `Ctrl+V` branch, and v0.17.1's silent no-op came back on a surface that had never been tested. The executable does not change when the program inside it does; the title list stays as a fallback (`D-007`)
- **📱 The scroll arrows were never missing — they were invisible.** Reported as "nothing at all" at the right edge of the screenshot on a phone. Ruled out first: no `@media` block touches the pad, no JS hides it, it is not clipped — and the device was proven **not** stale, because the access log shows it calling `/api/layout`, an endpoint that only exists in the current client. What was left was `rgba(20,19,17,.42)`, no border, no shadow, a 15px glyph, and `:hover` — which never fires on touch — as the only rule raising the contrast. A dark pill on a dark VS Code screenshot
- Fixed with a **light hairline ring**, not a theme-aware fill: these float over the *screenshot*, so the page theme cannot tell you whether the pixels behind them are a black terminal or a white document (`D-016`). Fill `.42` → `.78`, a shadow, a 17px/600 glyph, and **44px** targets on a phone — they *grow* while everything else shrinks. Two unreported bugs fixed in the same six lines: `:active` was `var(--accent)`, which in night theme is `#ece9e4` against `color:#fff`, so **the held state of a hold-to-scroll was white on white**; and `:hover` being the only contrast state meant a touch device saw none
- **The bottom quick-keys bar folds.** `#qk-toggle`, a caret at the far left — the one slot the phone block already empties. Reuses `.panel.acc` wholesale: pseudo-element caret, the `acc_` localStorage namespace, expanded by default. Collapsed is a ~24px sliver, not a disappearance, so the way back is where the way out was; **~36px of clearance returned**. The class goes on `<body>`, not the bar, because the two things that must follow the fold — the bottom clearance and `#toast` — are not descendants of it, and it is a class rather than a `--qk-h` variable because `62px` is the expanded height in two places a test pins byte-for-byte
- **Phone compaction, under one rule: horizontal is the scarce axis.** Every overflowing row on this page scrolls or wraps sideways, never down — so at ≤560px *inline* padding and gaps shrink (`.panel` 14→11, `.btn` inline 14→10, `.btn-sm` 11→8, chips 12→9, gaps 6→5) while the **tappable height of every control is held**: nothing vertical below 6px, `#mic-btn` keeps 46px. A test fails on any two-value padding in that block with a vertical under 6px
- `#qk-type` left `.qk-btns` to become its sibling. It was the last child of the row that scrolls at ≤560px, so **the answer field scrolled away with the keys** — the exact opposite of what the comment beside that rule had claimed for two versions
- **Tests 74 → 94**, and the 12 new assertions were **mutation-tested** rather than trusted: eight deliberate reverts, eight failures. That also caught `test_quick_keys_bar_at_bottom` *passing while measuring the wrong span* — its regex swallowed `#main`'s closing tag once the field moved. `check-links.py` and `wiki-doctor.py` now gate every commit through a hook
- Known and unfixed, on the board: `bot.log` is **3.0GB** with nothing rotating (row 3); the stale-client reload retries the *same* `?v=` URL every time, so a cached webview welds its own escape hatch shut (row 9); `env(safe-area-inset-bottom)` is unhandled, so the bar sits under the home indicator on a notched iPhone

### Changelog v0.20.0 2026-08-25
- **Typing now lands in the terminal, not wherever the caret happened to be.** v0.19.1 diagnosed it and stopped; this ships the fix. `focus_window_exact` raises the *window* — the inner keyboard focus stays put, and after `code -n` that is the editor, where `ctrl+shift+v` is an editor binding and the paste vanishes while the bot answers `Typed:`. `POST /api/type` takes `terminal: true` and moves the caret into the VS Code integrated terminal first
- **`utils/vscode.py`** — the command-palette sequence (`ctrl+shift+p` → command name → waits) now lives in exactly one file. `utils/scheduler.py` had a private `_focus_vscode_terminal()`; it was deleted and the scheduler imports the shared one. `test_terminal_focus_lives_in_one_place` fails if a second copy appears — a divergent copy is how one surface silently keeps typing into the editor
- The result is **reported, never swallowed**: `focus_terminal_if_active()` returns `(focused, message)`, `/api/type` echoes them as `terminal` / `terminal_msg`, and a non-VS-Code foreground gives a loud red toast (`Typed "claude", but active window is not VS Code (…)`) instead of a cheerful success. Typing still happens — a wrong-window guess must not eat the text
- **✨ Claude Code launcher** — one orange button (`--claude` brand `#d97757`, both palettes) in the Actions rail, the bottom quick-keys bar and the zoomed viewer. Types `claude` + Enter into a **fresh** terminal (`new_terminal: true`): "Focus on Terminal View" lands in the last active terminal, and if that already runs Claude Code the word `claude` arrives as a chat message to that session instead of starting one (observed live). A new terminal is always a shell prompt, and it also covers a just-opened window with no terminal at all. `VSCODE_NEW_TERMINAL_WAIT` (1.6s) lets the shell print its prompt — keystrokes sent into that gap are dropped by the pty and read as "the button did nothing"
- **Freeform answer field replaces the `1` / `2` digit buttons** (bottom bar + viewer): Enter sends text + Enter into the focused window. The two taps the buttons covered still work by typing them; everything they could not answer — `3`, `yes`, a path — now works too. The recently-tapped trail shows a truncated echo, so the field feeds the same history the keys do
- **`Tab` joins the key rows**, tinted apart from `Sh+Tab` (Enter and Sh+Tab are green pills in the viewer, Tab plain) — two keys one character apart with opposite meanings must not look alike
- **Viewer project row** (`#lb-proj-row`): project select + 🖥 Focus + Open + Claude. Pick a project, focus or open its VS Code window, start a session — the whole flow without leaving the zoomed screenshot. `doFocusProj` targets `'<folder> - Visual Studio Code'`, matched server-side by containment so it still hits the window after VS Code prefixes the open file to the title. `_selectedProject(selId)` / `doCodeSel(selId)` take the select id, so the dashboard panel and the viewer share one code path and one `loadFolders()`
- **Gesture guard extended to form controls** — `_lbCtl(el)` exempts `BUTTON` / `INPUT` / `SELECT` / `OPTION` from the viewer's pointer handling. Button-only (the v0.16.7 rule) would have made a tap on the new field start a pan and dismiss the viewer mid-typing, since `#lightbox` sets `touch-action:none; user-select:none`
- **Viewer controls stay compact on a phone** — both rows float *over* the picture, so every pixel they take is screenshot lost. At desktop sizing (38px pills, 8px gaps) each row wrapped in two on a 360px screen: four rows covering half the view. `@media(max-width:620px),(max-height:520px)` gives 32px pills, 6px gaps, `flex-wrap:nowrap`, buttons pinned at `flex:0 0 auto` while the select and the field absorb the leftover width (`flex:1 1 auto; min-width:0` — without `min-width:0` a flex item refuses to shrink below its content and the row overflows the viewport instead). 🖥 Focus drops its label, the icon carries it. Short landscape windows get the same treatment, where height is the scarce axis
- Tests 68 → **74**

### Changelog v0.19.1 2026-08-24
- **`/refine` uses the whole window** — on a 2000px screen it was a 640px column stranded in the middle with the text scrolling inside 400px of it while the rest of the page sat empty. Wrap goes `max-width:640px` → **1180px**, and above 760px both panes are sized from the viewport (`calc(100vh - 300px)`, min 340px) instead of from their content
- CSS alone would not have fixed it: `autoGrow` writes an **inline** height capped at 400px and an inline height beats a stylesheet rule, so it silently undid the fit on every keystroke, Improve and transcription. `autoGrow` is wrapped on this page — clears the inline height when `matchMedia('(min-width:760px)')` matches, keeps the original growth for the stacked phone layout, and re-fits on `resize`
- Reading measure capped **inside** the preview (`.md-body>* {max-width:78ch}`), not on the pane — long-form text stays comfortable while the panel still fills the window
- **Char/word counter** beside Copy, fed through the wrapped `autoGrow`, so every programmatic write (Improve, transcription, history refill, Clear) updates it, not only typing
- Diagnosed live, no code change: **typing lands wherever the inner keyboard focus is.** `focus_window_exact` raises the *window*; it never focuses the control. VS Code focused with the caret in the editor instead of the integrated terminal → `ctrl+shift+v` is an editor binding and the text disappears; Claude Desktop foreground with its chat box unfocused → same. Proven working in isolation against live windows: clipboard write (`Test message` present after a send), keystroke injection (`pyautogui.write` landed), and both paste keys (markers spliced into the live prompt line). The bot still answers `Typed:` in every failing case, which is what made it look dead. `utils/scheduler.py` already carries the missing step (command palette → "Terminal: Focus on Terminal View" + `SCHEDULE_FOCUS_SETTLE`); `/api/type` and `text_handler` do not call it
- Known, untouched: `bot.log` at **2.9GB** (DEBUG on `httpcore`/`telegram.ext`, still needs rotation + per-library levels); `bot.tunnel` watchdog `tasklist` timing out after 15s every 75s — process creation on the box hangs, same class as the v0.18.0 zombie incident
- Tests 67 → **68**

### Changelog v0.19.0 2026-08-24
- **Split-view Mini App** — text refinement moved to its own page at **`/refine`**: mic → speech-to-text, AI cleanup, ✨ Improve (4 styles), Twin, markdown preview, **📋 Copy**. No screen, keys, shell, git, build, restart, windows, projects or scheduler. **Text leaves this view through the clipboard only** — there is deliberately no Type button, because typing into a focused window is remote control and Copy is not
- **Isolation is server-enforced, not markup.** `POST /api/scope` (full auth required) mints a 12h `refine.<exp>.<hmac>` bearer; `_check_auth_refine()` is called by exactly three handlers (`api_status`, `api_stt`, `api_improve`) while the other 24 keep plain `_check_auth` and reject it with 401. Deliberately a second function rather than a `refine_ok=` kwarg — the system handlers then get a zero-line diff, and a bad merge that drops it fails *closed* instead of quietly opening a shell route. `test_scoped_token_rejected_by_system_routes` + `test_every_api_handler_checks_auth` pin both the coverage and the count of three
- Token design: the scope is **inside** the MAC (signing the expiry alone would let anyone rewrite the prefix), the key is derived (`HMAC(b"tgide-scope-v1", secret)`) so it never shares material with the initData check, an empty secret mints `""` and validates nothing (`BOT_TOKEN` is `None` in CI), and it is read from the `Authorization` header only — never `?token=`, which lands in every proxy log. TTL 12h: shorter than `INIT_DATA_MAX_AGE` so a scope cannot outlive its minter, long enough that a suspended webview does not 401 mid-dictation
- **Honest limit, written into the chunk:** inside the Telegram webview `Telegram.WebApp.initData` is readable by any script and *is* a full credential, and `localStorage` is same-origin state — no page can fence either off. What the scoped token buys is defence against this page's own code, a CI-tested "no typing to the PC" invariant, a genuinely narrowed browser flow, and hours-not-forever blast radius on a leak
- **`web/common.js`** — ~460 lines shared by both pages (`api()`, toast/status, theme, History, the markdown renderer, the mic→WAV→STT stack, `doImprove`), extracted from `index.html` (2332 → 1889 lines). Each block is scar tissue from a real bug, and a second copy would silently miss the next fix. Shipped as a mechanical cut with all 44 existing tests green before any feature code was written. Rule, test-enforced: **anything calling a system endpoint stays in `index.html`**
- `window.AUTH_HEADERS` decides which credential every request carries — without it `api()` prefers initData and the refine view's scoped token is bypassed inside Telegram, which would have made the whole split fiction. `window.NO_AMBIENT_AUTH` keeps `const TG` null there, so no full credential sits in a page-lifetime global
- **Markdown renderer hardened** (shared, and default-ON in the new view, where the text usually arrives from an LLM rather than the operator's own keystrokes): `_mdEsc` now escapes `"` and `'` — the link rule writes the URL into an `href="…"`, so an unescaped quote closes the attribute and opens an event handler — and `_mdSafeUrl` allows only `http(s)`/`mailto`/relative targets, so `[x](javascript:…)` renders as plain text instead of one-click script execution with this origin's credentials
- **Copy button** — async clipboard API with a hidden-textarea `execCommand` fallback, because Telegram's Android webview refuses the former. The write is the first async statement in the handler: any prior `await` spends the transient user activation and the copy silently no-ops on a phone while working on desktop. An empty field leaves the clipboard untouched, >500k chars selects instead of copying, the caret position is restored, and the toasts name both the size and the path taken
- **Two entry points** — a `✨ Refine` / `🖥 Dashboard` header link on each page, plus `🖥 Dashboard` + `✨ Refine` `web_app` buttons on the first row of `/panel`. The panel keyboard is now built per message (`build_keyboard(chat_type)`): `web_app` inline buttons are private-chat-only and Telegram fails the **whole message** with `BUTTON_TYPE_INVALID` elsewhere, so an unguarded row would take `/panel` down in any group the bot sits in. Empty or non-HTTPS `WEBAPP_URL` → no buttons, not a broken panel
- The markdown preview keeps its own `tg_md_refine` key (default **ON**) — the dashboard field is text about to be typed into a terminal, this one is a document being produced to paste elsewhere, and a shared key would push the dashboard's preset grid below the fold. History stays shared on one `tg_history`, which needed a null guard and a `HISTORY_TARGETS` override so a `shell` row does not throw on a page with a single field
- Fixes: the markdown preview went stale after transcription and history-refill (the `input` event does not fire for programmatic `.value` writes); `tg_reloaded_for` is namespaced per page, or the second surface to load after a version bump dead-ends on "reload failed"; `utils/improve.py` logged "twin profile missing" whenever the input was **not** mostly Cyrillic, and never when a profile was actually absent
- Tests 43 → **67** (`tests/test_refine.py`, 23 new)

### Changelog v0.18.0 2026-08-20
- **Improve text (AI)** — type rough text in the dashboard Type field, tap **✨ Improve**: LLM rewrites it in a chosen style (Structured / Detailed / Concise / →EN), result replaces the field, **never auto-sends** — read, edit, send yourself. Original saved to History as gray `draft` kind *before* the request (survives a dead call; click the row to restore). `POST /api/improve`; `utils/improve.py`; `utils/humanize.py` refactored to expose generic `chat(system, text)` (same Groq fallback chain + reasoning-strip, `humanize()` is a thin wrapper). LLM failure = loud 502 toast, field untouched
- **Twin toggle** — injects the HAE operator profile (`persona.md` + `principles.md` from `HAE_PROFILE_DIR`, default `~/.hae/profile`, mtime-cached) into the improve prompt so output matches the operator's style. Deliberately *not* `twin.ps1` — its exemplar retrieval is decision-oriented and a pwsh subprocess per request is waste; the two profile files carry the style signal. Missing profile → `twin_missing` + toast, improve still runs
- Two prompt-ordering lessons measured against live qwen3.6-27b (locked in `improve-text.md`, don't undo): profile placed after the style rules got `principles.md` copied verbatim into output as fake "Constraints" → profile goes FIRST, instructions LAST; and no instruction survives a 6KB English persona dragging Russian input into English → deterministic `_lang_hint()` (Cyrillic >50% → "Output language: Russian" appended last, skipped for translate)
- **Quick-keys bar** — fixed at the viewport bottom (z-90): ← → Enter Sh+Tab 1 2, the Claude Code question-schema set (arrows/Enter move the option selector, Sh+Tab cycles mode, 1/2 type digit+Enter). Left side shows a recently-tapped trail (cap 8, newest last, RTL-ellipsis so the newest survives overflow, "no keys tapped yet" empty state) fed centrally from `doKey` — Keys-rail and mob-chip presses appear too. Body gets 62px bottom clearance at every breakpoint (the ≤560px media block was silently resetting it); toast raised above the bar
- **Same keys inside the lightbox** (`#lb-keys`, bottom-center, z-201, white-pill style shared with `#lb-controls`) — answer Claude prompts without leaving the zoomed screenshot. Safe by construction: the viewer's pointerdown handler already exempts `BUTTON` targets from pan/backdrop-close
- **Mobile layout** — order now Screen → Windows → Projects → Type (screen is what you look at, windows switch constantly); Windows + Projects are **accordions** (tap title to fold, ▾/▸ caret, per-panel localStorage, collapse is CSS-only so data keeps refreshing underneath)
- **Singleton guard rewritten on psutil** after a live incident: a zombie instance held :8080 through a 40-min crash loop because process *creation* on the box was hanging — `taskkill /F` timed out at 10s and the WMI powershell enumeration at 20s on every restart, while an API-level kill of the same pid worked instantly. Guard now enumerates and kills in-process (zero child processes, `p.wait(5)` because the port frees only when the process is really gone). psutil added to requirements
- **Favicon** — rounded-square Telegram-blue (`#229ED9`) tile with big white "TG"; SVG source + 16/32 PNGs + ICO + apple-touch (Pillow, 4× supersample → LANCZOS). Served via existing `/static/`, plus unauthenticated `/favicon.ico` root route (browsers request it before any auth exists)
- Tests 36 → **43**

### Changelog v0.17.1 2026-08-17
- **Typing was still silent after v0.17.0 — Ctrl+V is not the paste key in a Claude Code terminal.** Claude Code binds Ctrl+V to "paste image from clipboard", so a text paste is a no-op: the keystroke arrives, the clipboard holds the text, the prompt stays empty, and the bot reports `Typed: ...`
- Isolated against the live window rather than guessed. Elevation ruled out (all three VS Code windows are one non-elevated pid, so UIPI is not it); focus verified (`ok=True`, window really foreground); clipboard verified (310 chars readable); key delivery verified (**Ctrl+Shift+P opened the command palette**). Then `pyautogui.write` produced `> TYPED-999` while Ctrl+V produced nothing — paste alone was broken. `Ctrl+Shift+V` → `> CSV-111` ✅, `Shift+Insert` → nothing. Confirmed in the second terminal too (`> CSV-TG-333`), so one rule covers every session
- **`paste_hotkey_for(title)`** picks the keystroke from the target window: terminal-ish titles (`visual studio code`, `powershell`, `git bash`, `windows terminal`, …) → **Ctrl+Shift+V**; everything else (Notepad, browser, Telegram) → Ctrl+V, which is what those apps actually honour. Env-tunable: `TYPE_PASTE_HOTKEY`, `TYPE_TERMINAL_PASTE_HOTKEY`, `TYPE_TERMINAL_HINTS`. The log line names the key used (`… via ctrl+shift+v`). Verified end to end through the bot's own `/api/type`
- **Voice cleanup died because Groq retired the model.** `llama-3.3-70b-versatile` answered normally at 13:18 and returned `404 — does not exist or you do not have access` by 14:25; the whole Llama family disappeared from the key. Whisper was untouched, which is exactly why recognition kept working and only the cleanup stopped
- The old code caught that and returned the raw transcript with a warning in the log — indistinguishable from "the AI button does nothing". **Failure is now loud**: `/api/stt` returns `humanized` + `humanize_error`, the dashboard toasts `AI cleanup failed, raw text: …`, a Telegram voice message appends `⚠ AI cleanup failed`
- **`HUMANIZE_MODEL` → `qwen/qwen3.6-27b`** with `HUMANIZE_FALLBACKS=openai/gpt-oss-20b` — first model that answers wins and the switch is logged, so the next retirement costs quality, not the feature. Still the same free Groq key and endpoint; only the model string changed (`gpt-oss-120b` and `compound-mini` return 403 *blocked at project level* for this key)
- **`HUMANIZE_REASONING=none`** sent as `reasoning_effort`, plus defensive `<think>…</think>` stripping: without it qwen3.6 returned **7196 chars of chain-of-thought** for a 483-char transcript, which would have been pasted into Claude Code verbatim. Chosen over `gpt-oss-20b` on a mixed RU/EN dictation — faster (0.46s vs 0.61s) and it kept the speaker's self-correction
- Tests 33 → **36** (paste key follows the target window; humanize has a fallback chain, strips reasoning and never fails silently; `/api/stt` reports a failed cleanup)

### Changelog v0.17.0 2026-08-17
- **Typing from the bot silently stopped submitting.** Every path — Telegram chat text, Mini App Type, panel presets, voice "Type+Enter", scheduled messages — pasted the text and then pressed Enter **0.1s later**. Claude Code detects bracketed paste and buffers the block; an Enter arriving inside that window is folded into the paste as a literal newline instead of submitting. The message sat in the input box while the bot answered `Typed: ...`
- Diagnosed from the live system, not by reading: bot alive, no webhook, `pending_update_count: 0`, local + public endpoints 200, `_type_text` proven working against Notepad. New `bot.input: Typing N chars into '<window>'` log line caught the real behavior — two `Test` messages arrived at Claude Code glued together as `TestTest` (first Enter eaten, second submitted both), while a third went through. A race, which is why it looked random and hit all surfaces at once
- **`type_and_enter(text, enter=True)`** (`handlers/input.py`) is now the only place paste and Enter are sequenced; `TYPE_ENTER_DELAY` (default **0.45s**, env-tunable) is the gap. `handlers/web.py`, `panel.py`, `audio.py`, `utils/scheduler.py` all route through it — no caller presses Enter itself. `/api/paste` keeps bare `_type_text` on purpose (types an image path, no Enter)
- **`_stuck_modifiers()`** releases a Ctrl/Shift/Alt/Win left down by an earlier hotkey (Auto = Shift+Tab ×3, the Alt tap in `force_foreground`) — one stuck modifier turns the paste into Ctrl+Shift+V and nothing arrives. Logged as a warning when it fires
- **Scroll arrows on the live view** (RustDesk-style): floating ▲/▼ column on the right edge of the screenshot and inside the lightbox, hold to keep scrolling. `utils/mouse.py` + `POST /api/scroll`
- Windows routes the wheel by **cursor position** (`mouse_event` ignores the x/y handed to a WHEEL event), so `scroll_at()` parks the cursor over the target, scrolls, then puts it back where the user left it. Notches are multiplied by `WHEEL_DELTA` (120) — `pyautogui.scroll(3)` is 3/120 of a notch and moves nothing. Clamped to `MAX_NOTCHES` (30) so a stuck hold can't fling a page
- In Window capture mode the client sends the centre of the frame it is showing, so the arrows scroll the window you are **looking at** even if focus moved on; in full-screen mode it sends nothing and the server aims at the active window. Hold-repeat chains from each request's completion, never `setInterval` — a fixed interval would pile up in the single-request tunnel exactly like the v0.16.1 capture bug
- Arrows live in `.screen-wrap`, not `#screen-area` — `capture()` replaces that element's children every frame and would wipe them
- Focus misses were **silent**: `focus_window_exact` logged only successes, so a chip that matched nothing left no trace. It now logs the requested title and the live window list; `/api/focus` logs its verdict
- Tests 28 → **33** (Enter waits for the paste; no path pairs `_type_text` with its own Enter; scroll auth + clamp, cursor-park/notch conversion, arrows wired outside `#screen-area`)
- Known, untouched: `bot.log` reached **2.7GB** — DEBUG on `httpcore`/`telegram.ext` logs every poll. Needs rotation + per-library levels

### Changelog v0.16.7 2026-08-16
- **Zoomed screenshot viewer closed itself while panning on Android** — two independent causes, both fixed
- **Cause 1: Telegram's own dismiss gesture.** A vertical drag inside a Mini App *is* the close gesture, and panning a zoomed image is that drag. `_twa.expand()` does not stop it; startup now calls `_twa.disableVerticalSwipes()` (Bot API 7.7+, try/catch for older clients)
- **Cause 2: pointer capture lies about the target.** `box.setPointerCapture()` retargets every later pointer event to `#lightbox`, so `pointerup`'s `e.target.id === 'lightbox'` was true even for taps that started **on the image** → the backdrop close timer fired mid-gesture. The decision now comes from `pointerdown` (`_lb.onBackdrop`), the only event whose target is truthful
- Gesture guards: `_lb.multi` (second finger landed → pinch tail is never a close tap), `if (_lb.ptrs.size) return` (no verdict while fingers are still down), `pointercancel` handler — an OS-stolen gesture never sends pointerup and used to leave a stale finger in `_lb.ptrs`, wedging pan/pinch at `size === 2`. `openLightbox`/`closeLightbox` reset all gesture state + the close timer
- **Telegram BackButton** shown while the viewer is open (`_tgBack`) — hardware back closes the viewer instead of the whole Mini App
- **Current window missing from the quick-pick chips / never highlighted.** Title is not identity: VS Code puts the open file *first* (`config.py - Tg-IDE-bot - Visual Studio Code` vs `index.html - Tg-IDE-bot - …`), so two titles of one window share no prefix and neither contains the other — the v0.16.5 rules declared the chip dead
- **`tail_key()` / `_tailKey()`** — last two `" - "` segments, lowercased — added as a 4th match rule on both sides (`utils/window.py:focus_window_exact`, `_sameWin()` in the dashboard). Empty for single-segment titles, which must never match
- Two matchers on purpose: `_sameWin` (exact → containment → 25-prefix → tail) = "will focus find it?", mirrors the server; **`_sameWinId`** (exact → tail) = "is this the same window?", drives merge/dedupe/highlight — containment is too loose for identity ("Telegram" is inside "Telegram Web - Google Chrome")
- Highlight compares with `_sameWinId` instead of `===`; `bumpRecent` merges retitled entries into one (counts summed) — a retitling VS Code used to write one entry per open file and fill all 8 slots alone
- Recents ordering ties now break by recency (`_recentOrder`) — frequency-only meant a fresh `n=1` entry lost to eight older `n=1` entries; and the **current window is pinned first**, exempt from the top-6 cut, since it may have been focused outside the dashboard and never bumped
- `test_lightbox_survives_pan_gestures` locks the viewer fixes, including "pointerup must not read `e.target.id === 'lightbox'` again"; `test_tail_key_identifies_a_retitling_window` + `test_current_window_chip_is_pinned_and_highlighted` lock the chips. Tests 25 → **28**
- Deploy note: `index.html` is read per request (no bot restart needed), but the Telegram webview caches hard — `CLIENT_VERSION` 0.16.7 vs the running bot triggers the one-shot `?v=` reload

### Changelog v0.16.6 2026-08-09
- **Reverse tunnel targets a name, not an address.** `start_tunnel_vps.ps1` → `root@vpn.magerash.com` (was `root@45.150.33.106`). The VPS address was silently dropped by RF DPI on 2026-08-07 and replaced by `213.165.40.182`; with the IP pinned in the repo, an infrastructure event forced a code change. The raw IP survives only as a commented fallback for when DNS itself is the broken thing
- **DNS is picked up on reconnect only** — ssh resolves once per connection attempt, so a keeper that is already connected keeps the old address until its ssh dies (`taskkill /IM ssh.exe`, or wait ≤60s for `utils/tunnel.py`). The `vpn` A-record must stay DNS-only/grey cloud: Cloudflare's proxy is HTTP-only and would break ssh exactly as it breaks the VPN's UDP
- **Live recovery, not just an edit.** Tunnel was down: the running keeper still had the old IP parsed in memory, and a leftover `sshd-session` (pid 208543) held VPS `:18080`, so every reconnect died on `ExitOnForwardFailure`. Killed both, restarted via `start_bot.bat`. Verified: local frame 0.09s / 70KB, public frame **0.50s / 71KB ≈ 140KB/s** through the tunnel
- **Phone slowness is not this.** Same path, same frame size, the phone's Telegram webview measured ~8s per 68KB frame (≈8.5KB/s) — 16× worse than the PC. That is the v0.16.4 VPN hairpin returning, because the phone's split-tunnel exclusion still named `45.150.33.106`. **Amnezia excludes by address, not hostname**, so the exclusion does not follow DNS and must be re-checked after every migration
- Docs: `vps-architecture.md` → **v1.3** (names table with resolutions verified 2026-08-09, domain endpoint marked live and extended to the ssh tunnel, diagram/cheat-sheet/checklist updated, "if the address is filtered again" runbook). `plane.magerash.com` is the only name left on the filtered IP and blocks releasing it
- Chunk `web-dashboard.md` + README ops runbook: tunnel host, DNS-reconnect rule, split-tunnel address
- No change to bot behavior; tests 25 unchanged

### Changelog v0.16.5 2026-08-06
- **Recents are validated against reality.** Recent-window/project chips live in localStorage, so they outlived the windows they pointed at — a chip for a closed window looked tappable and did nothing. `renderRecents()` now filters every chip against the live list (`_winList` from `/api/windows`, `_projList` from `/api/folders`)
- `_matchesLive()` mirrors `focus_window_exact()` in `utils/window.py` — exact → containment either way → first-25-chars prefix. Required because VS Code retitles per open file: a chip saved as `Tg-IDE-bot - Visual Studio Code` must still match the live `index.html - Tg-IDE-bot - Visual Studio Code`. `test_recent_validation_mirrors_server_matching` fails if either side drifts
- Storage is **not** pruned on render — close a window and reopen it and the chip returns with its frequency intact. Only the 30-day-unused entries are dropped (`RECENT_MAX_AGE`), so a once-popular dead window can't hold a top-8 slot forever
- `/api/focus` returns a machine-readable `gone` flag (`msg.startswith("Window gone")`, kept next to the producer). A failed focus retires the chip only when the window is really gone — "found but activation blocked (admin window?)" keeps it
- Empty live list (endpoint failed / not loaded yet) disables filtering rather than hiding everything
- Tests 25

### Changelog v0.16.4 2026-08-06
- **Root cause of "Mini App doesn't update": the phone's VPN.** VPN off → works; VPN on → frames crawl. The VPN server *is* the VPS the bot's domain points to, so with the VPN on the phone tunnels bot traffic **to the VPS through the VPS**: phone →AmneziaWG(UDP 36698)→ VPS → Caddy → ssh tunnel → PC, and back the same way. The PC is immune because WireGuard auto-excludes its own endpoint IP (`Find-NetRoute 45.150.33.106` → `Ethernet`, not the AmneziaVPN adapter); Android WireGuard protects only its own socket, so *other* traffic to the endpoint IP still enters the tunnel
- Ruled out by measurement, in order: server (40ms/frame), PC→VPS link (46 Mbit/s), VPS shaping (`tc`: none), hairpin+DNS+NAT (`docker exec amnezia-awg2 wget https://bot.magerash.com:8443/` → serves the page), MTU black hole (client MTU 1280 changed nothing; `awg0` MTU is a correct 1420). Signature in the log is a **draining budget**, not a size cliff: frames start at 2–3s and degrade to 17–18s within one session while `/api/click` stays instant → carrier policing of the sustained UDP flow
- **Fix is routing, not code**: exclude `bot.magerash.com` / `45.150.33.106` from the VPN on the phone (Amnezia split tunneling). Costs nothing in privacy — the destination *is* the VPN server, so the carrier already sees the phone talking to that exact IP
- Frame abort 20s → **45s**: over a policed link a frame legitimately takes ~18s, and aborting throws away bytes already transferred, turning "slow" into "never updates"
- Default transfer resolution **1920 → `Fit`** (adaptive). Fixed sizes never adapt; `Fit` matches the view and auto-shrinks on a bad link. Lightbox still pulls ≥1920 for zooming
- `_adapt` now corrects **in proportion to the overshoot** (`1/√ratio`, clamped 0.4–0.9) after 2 samples instead of stepping 25% after 3 — an 18s frame against a 3s tick converges in one step instead of minutes

### Changelog v0.16.3 2026-08-05
- **Investigated the "Telegram never updates" report against the access log** (`bot.log` keeps user agents). Findings: server-side a frame costs 40ms; PC→VPS link measures 46 Mbit/s up; VPS has no shaping. The phone's own throughput collapsed — 2026-07-23 it pulled **17,358 frames at 1.0s median gap, 194KB each** (≈194KB/s); on 08-01..08-05 the same device on the same tunnel manages ~20–40KB/s. Same phone (Vivo V2419A), same Telegram family (12.8.3→12.9.2). **Not a code regression** — but the app now has to survive a thin link
- **`POST /api/frame` — binary transport** (`api_frame`, `_grab_frame`): raw bytes instead of base64 (−25%) + **WebP** instead of JPEG (−37% at equal quality, `method=2` = 23ms encode). Unchanged screen → **204 with no body**. Metadata in headers (`X-Rect`, `X-Hash`, `X-Mode`). Measured through the tunnel: 1280px frame **109KB → 50KB**; **1920px now costs 82KB — less than the old 1280px did**, so resolution went up and bytes went down at the same time. `/api/screen` + `/api/window` stay for cached older clients
- **Adaptive sizing** (`Fit` mode only): client tracks median round trip; frames that don't fit the Auto tick shrink 25% (floor 480px), cheap ones grow back to view size. Explicit 1280/1920/Full stay exactly as chosen
- **Auto-refresh pauses when the tab/webview is hidden** — a background dashboard was pulling **1.2GB/day** (2026-08-03) through the tunnel, competing with the phone for it. Resumes + captures immediately on `visibilitychange`
- Status line reports throughput too: `Window updated · 430ms · 50KB · 116KB/s` — the number to read when the live view feels slow
- Known transient: right after "Restart Bot" the public URL can 502 once — Caddy holds pooled upstream connections through the ssh tunnel and `os.execv` kills them. Self-clears on retry
- Tests 23 (WebP is really WebP + smaller than JPEG, 204 path, `/api/frame` auth)

### Changelog v0.16.2 2026-08-05
- **`api()` abort deadline** — `fetch()` has no timeout, so a request whose tunnel died mid-flight hung forever; combined with the v0.16.1 single-flight queue that wedged `_capBusy` permanently → Mini App never updated again while the browser (fresh page) looked fine. Default 20s, per-call overrides (`0` = unbounded for `/api/sh`, `/api/claude`, `/api/build`, `/api/key` with intervals; 120s typing; 8s restart)
- Live view: `CAP_STUCK_MS` (30s) queue reset as a backstop, `_capStart` timestamp per flight
- **Transfer resolution selector** in the Screen panel — `Fit` / `1280` / `1920` (default) / `Full`, persisted in localStorage, quality scales with it (65/68/72/80). v0.16.1's 1280@q55 was a visible downgrade from the old full-res frames
- Lightbox always pulls ≥1920 (and immediately on open) — the zoom view exists to read fine text, `Fit` would hand it a thumbnail
- Fix: `_frame_opts` treated `max_w=0` (= native, the Full setting) as missing and re-applied the default cap — `0` is now a real choice
- Config defaults raised for clients that send no preference (old cached UIs): `WEB_SCREEN_MAX_W` 1280→**1920**, `WEB_SCREEN_QUALITY` 55→**70**
- **Stale Mini App self-heal** — Telegram's webview caches the page per URL and ignores no-cache headers, so a phone can run an old UI against a new bot for days. `CLIENT_VERSION` in `index.html` is compared to `/api/status`; on mismatch the page reloads once as `?v=<server>` (sessionStorage guard against loops). Menu button URL is now version-stamped (`miniapp_url()`), index gains `Pragma`/`Expires` headers
- Mini App 401 (initData expires after 24h) now reads "Session expired — close and reopen the Mini App" instead of "Invalid token"
- Tests 20 (`_frame_opts` native/clamp, `miniapp_url` stamping, CLIENT_VERSION == VERSION, long-job timeouts declared)

### Changelog v0.16.1 2026-08-05
- Live view latency: **single-flight capture queue** (`requestCapture()`) — one frame request in flight ever, extras collapse into one pending run; Auto is a `setTimeout` chain measured from **completion** (was `setInterval`). Root cause of "click takes ~15s / never updates": blind post-click refreshes at +500ms/+1600ms stacked on auto ticks in the single reverse-SSH pipe, queue grew unbounded, `_capSeq` dropped late frames
- Live view: lightbox dropped its own refresh timer — the Auto pill drives the one shared loop (open lightbox + Auto was 2× frame requests)
- Frames: `_grab_to_jpeg(max_w, quality)` downscale + `WEB_SCREEN_MAX_W`/`WEB_SCREEN_QUALITY` config; client sends `max_w` = container × DPR (cap 1280, 1920 in lightbox). 250KB → ~40KB; measured 0.44s through the tunnel, click round trip 0.37s
- Frames: `hash` short-circuit — client echoes last frame md5, `_frame_reply()` returns `{same:true}` (~80B) when identical; status shows `Screen updated · 430ms · 40KB` (if ms > Auto interval, that IS the refresh rate)
- Ops: **`start_bot.bat` = one entry point** — hidden tunnel keeper, then bot auto-restart loop; Startup folder now holds `TG-IDE-Bot.lnk` → this bat (old `tg-bot-tunnel.bat` backed up in `docs/`). Web/TG "Restart Bot" (`os.execv`) untouched
- Ops: `start_tunnel_vps.ps1` single-instance guard (exclude `$PID` — own command line matches the pattern). Two keepers = two ssh fighting over remote port 18080, loser dies on `ExitOnForwardFailure` and retries every 5s → flapping tunnel. `utils/tunnel.py` falls back to the `.vbs` when `TgBotTunnel` isn't registered
- Web mobile: order Windows → Projects → Screen → Type Text; active window / current project tinted green (`btn-ok-soft`) in recents lists
- Panel + Web: `Ultrathink` types `Ultrathink ` with no Enter (keyword, not a slash command)
- Tests 16 (`_frame_reply` hash paths, `_grab_to_jpeg` downscale); docs `web-dashboard.md` + README ops runbook

### Changelog v0.16.0 2026-07-26
- Web layout: **Windows/Projects moved into the side rails** — left rail = Windows + Keys, right rail = Projects + Actions (`.rail` now a stacked flex column). Rails stay compact so `position:sticky` **locks** them while the center scrolls; recents render as full-width vertical lists
- Web mobile ≤920px: `.rail,.center{display:contents}` flatten all panels into one column, explicit order restores the old flow — Screen → Windows → Projects → Keys chips → Type Text → History → Scheduled → Actions chips → Claude → Shell (`#screen-panel`/`#win-panel`/`#proj-panel` order −3/−2/−1); `.rail-tools` hidden (mob-tools chips cover Keys/Actions)
- Auto mode: **Auto** key (web Keys rail + TG panel "Auto (Sh+Tab×3)") sends `Shift+Tab` ×3 with 1s gaps to cycle Claude Code modes; `/api/key` gains `interval` (sec between presses, ≤5); web `doKey('shift+tab',3,1)`, panel `p:auto_mode`
- Image paste rewrite: target is Claude Code in a VS Code **terminal**, which can't accept a Ctrl+V image. `/api/paste` now saves a temp PNG (`%TEMP%/tgbot_paste/`) and **types its file path** into the terminal (Claude Code attaches the file); `doType` types each path → waits `IMG_INGEST_MS` (700ms) → types text + Enter (`utils/clipimg.py` kept, unused)
- Web: Enter sends / Shift+Enter = newline restored (removed a `beforeinput` mobile fallback that swallowed Shift+Tab line breaks); `enterkeyhint="send"` kept
- Web: screen `Auto: ON/OFF` green while running (`.btn-ok`); Keys rail `Auto` button plain gray; TG panel `/twin`→`/hae:twin` (no-Enter preset, `_TYPE_NO_ENTER`)
- Docs: `docs/chunks/features/web-dashboard.md`; tests 14

### Changelog v0.15.1 2026-07-23
- Panel + Web: `/model` quick-type button after LF NB — types `/model` + Enter into focused window (`_TYPE_PRESETS["type_model"]`, `doTypePreset('/model')`)
- Web: `continue` quick-type button in Type Text preset row (green `btn-ok-soft`)
- Web: color-coded Keys rail — `Enter` + `Sh+Tab` green (`btn-ok-soft`), `Esc` red (`btn-red-soft`); `KEYS` entries gain optional 5th `cls` field, `renderTools` applies it
- Web: new `--warn`/`--warn-soft` theme vars (light+dark) + `.btn-warn-soft` class (yellow, currently unused after Sh+Tab→green)

### Changelog v0.15.0 2026-07-23
- Scheduled messages: queue text to type into a window at a set time — main use: fire right after a Claude Code limit reset so a session auto-continues (`utils/scheduler.py`, `POST /api/schedule`, `GET /api/schedules`, `POST /api/unschedule`)
- Web: `Scheduled` panel (below History) — message + `datetime-local`, **After 5h reset** / **After weekly reset** quick buttons (from metrics reset times), live list with countdown + ✕ cancel; **VS Code terminal** checkbox
- Scheduler: persistent JSON store (`scheduled_messages.json`, gitignored) survives restart; async poll loop (`SCHEDULE_POLL` 10s) started in `bot.py run()`; fires focus→type→Enter + Telegram notify
- Scheduler fixes: `SCHEDULE_FOCUS_SETTLE` (0.6s) after focus so a non-foreground window comes forward before typing; VS Code integrated-terminal focus via command palette ("Terminal: Focus on Terminal View") — position-independent, so text lands in the Claude terminal not the editor
- Web: night theme toggle (🌙/☀ in header, Warm Mono dark via `[data-theme]`, persisted, no-flash early apply); fixed `.btn:hover`/`.btn-primary` hardcoded colors (`--accent-fg`)
- Fix: zoomed lightbox auto-refresh showed a one-interval-stale frame — fresh frame now pushed from `capture()` onload (zoom/pan preserved)
- Config: `SCHEDULE_FILE`, `SCHEDULE_POLL`, `SCHEDULE_FOCUS_SETTLE`; tests 14 total
- Docs: `docs/chunks/features/scheduled-messages.md`

### Changelog v0.14.1 2026-07-23
- Web: `1` `2` `3` fast-answer keys at front of Keys rail — type digit+Enter (`KEYS` entries gain optional `fn` override); answer numbered prompts in one tap
- Web: Screen capture controls (`.screen-head`) moved **below** the screenshot — closer to Type input for faster tapping; `Screen` panel title kept
- Web + TG panel: `/ultrathink` preset relabeled `Ultrathink` (typed text unchanged)
- Web: removed `Click 250,1000` from Actions rail — screenshot Click-mode (flexible x,y) replaces it

### Changelog v0.14.0 2026-07-22
- Claude Code metrics: live card in web dashboard — active model + effort tags, context usage %, 5-hour & weekly rate-limit blocks with reset countdowns (`utils/ccmetrics.py`, `GET /api/ccmetrics`)
- Sources all local `~/.claude` files: OMC usage cache `.usage-cache-anthropic.json` (5h/weekly) + newest session transcript (model/effort/context tokens); tail-read keeps large transcripts fast
- Metrics follow the dashboard's selected project (path→folder encode); switching project re-fetches; no-session project shows account-wide limits only; ↻ refresh button + 30s auto-poll + 1s reset countdown
- Config: `CC_USAGE_CACHE`, `CC_PROJECTS_DIR`, `CC_CONTEXT_WINDOW` (default 1M-context, set 200000 for standard)
- Fix: oversized textarea resize grip → subtle default handle (matches History), Type/Claude/Shell fields
- Tests 12 total; docs `docs/chunks/features/cc-metrics.md`

### Changelog v0.13.0 2026-07-22
- Humanize: raw transcript → clean prompt via Groq `llama-3.3-70b` (`utils/humanize.py`); TG 📝 Raw/✨ Clean toggle, web monochrome AI: ON/OFF toggle; fallback to raw on any error
- Recording: web mic cap 120s → 10 min, ticking mm:ss timer on button (⚠ last minute); fix: aiohttp `client_max_size` 1MB → 30MB (long uploads died silently); upload status + 3-min abort guard
- Clicks: remote double-click (`/api/click {double}`, `pyautogui.doubleClick`) — tap-delay 280ms pattern on main screen + lightbox Click mode; fix: double-tap zoom no longer closes lightbox (close-timer cancel)
- Screen: lightbox inherits main Auto state on open; entry defaults — auto-capture + Auto 3s ON at login, Window capture mode default, Click OFF
- Windows/Projects: current focused window tag (`/api/windows` returns `active`), top-3 recent chips (frequency, localStorage) for one-tap focus/switch
- Type panel: controls row above input — AI toggle left, big record button center (46px), Type right; auto-grow textareas to content (84→400px); visible diagonal resize grip
- Config: `HUMANIZE_MODEL`, `HUMANIZE_DEFAULT`; tests 11 total
- Docs: `docs/documentation/audio-longform-humanize-research.md` + `-plan.md`

### Changelog v0.12.0 2026-07-22
- Audio-to-text: TG voice message → Groq Whisper (`whisper-large-v3-turbo`) transcript + inline buttons Type / Type+Enter / Claude
- Web: mic button in Type panel — MediaRecorder → WAV re-encode via Web Audio (fixes webm no-duration "Thank you." hallucination) → `/api/stt` → Type field
- Web: silence detector (peak < 0.005 skips API, toast shows mic device label) for mic diagnostics
- Web UI: mobile Keys chips above Type Text, Actions chips below; traditional mic SVG icon; Type+mic one column on mobile (`.input-btns`)
- Web: input textareas min-height 84px (matches stacked button column)
- Web: Screenshot/Window mode buttons highlight instantly on click (optimistic `_syncModeButtons(mode)`)
- New: `utils/stt.py`, `handlers/audio.py`, `/api/stt` endpoint; config `GROQ_API_KEY`, `STT_MODEL`; +1 test (10 total)

### Changelog v0.11.4 2026-07-21
- Panel + Web: new quick-type buttons `/plan`, `/hae:release-plan`, `/twin`
- Web: Keys/Actions rails top-align with Type Text panel (`alignRails()` + ResizeObserver, dynamic screen height safe)
- Web: History panel moved directly below Type Text

### Changelog v0.11.3 2026-07-21
- Panel + Web: finish buttons compacted — "Let's finish (LF)", "LF CB", "LF NB" (one row in TG panel)
- Web: gray hint under presets — "LF = let's finish · CB = commit to current branch · NB = commit + new branch"

### Changelog v0.11.2 2026-07-21
- Panel + Web: `/clear`, `/caveman`, `/ultrathink` quick-type buttons (typed into focused window + Enter)
- Panel + Web: renamed finish buttons — "Let's finish (LF)", "LF on current branch (CB)", "LF and go new branch (NB)"
- Panel: type presets unified into `_TYPE_PRESETS` dict; new rows layout (Click moved up, LF buttons own rows)

### Changelog v0.11.1 2026-07-21
- Web UI: main-screen Auto button solid green while running, Click button solid red while armed (new `.btn-ok` class) — matches lightbox pill states

### Changelog v0.11.0 2026-07-21
- Web UI: Type/Claude/Shell as multi-row textareas (Enter = send, Shift+Enter = new row), all fields resizable
- Paste compose: big text → block chips (rows/chars count), images → thumbnail chips; all sent together on Type
- History panel: sent type/shell/claude/image messages, click to refill input (localStorage, cap 100)
- Screen: auto-refresh interval selector (1–10s), lightbox Auto + seconds pills, active-mode highlight on Screenshot/Window
- Fix: capture race (`_capSeq` guard) — stale captures no longer overwrite newer ones; refresh follows capture mode
- Fix: one-click lag — `await doClick()` before refresh + double refresh (500ms/1600ms)
- Fix: `doAuth()` no longer wipes saved token on empty input
- Focus: reliable Win32 activation chain (`utils/winfocus.py`) + fuzzy title fallback — works on all windows
- Ops: single-instance guard (`utils/singleton.py`) kills duplicate bot processes (port 10048 crash loop fix)
- Ops: tunnel runs via `start_tunnel_hidden.vbs` — zero console window
- New modules: `utils/winfocus.py`, `utils/singleton.py`, `start_tunnel_hidden.vbs`

### Changelog v0.10.0 2026-07-21
- Web UI: compact layout from design handoff — sticky Keys/Actions side rails, fluid center (≤1500px), Windows+Projects side by side, mobile chip rows; `KEYS`/`ACTIONS` arrays as single source for buttons
- Web: "Restart Bot" action (`/api/restart`, `os.execv` self-restart) with reconnect polling
- Web: action status field in Actions rail — last action result + timestamp, fed by all toasts
- Fix: macOS Telegram red screen — skip `setBackgroundColor`/`setHeaderColor` hex calls on `platform === 'macos'`
- Fix: index served with `Cache-Control: no-cache` (webviews always get fresh HTML)
- Ops: tunnel watchdog (`utils/tunnel.py`) — bot restarts TgBotTunnel task if ssh dies (60s check)
- Tests: +restart auth test (9 total)

### Changelog v0.9.0 2026-07-21
- Project switching: `/project` command + shared current-project state (`utils/project.py`) — git, build, APK, panel and web follow it
- `/code` opens project in new VSCode window (`code -n`) and sets it current; no longer replaces active window
- Build: `gradlew.bat` guard with friendly error, output prefixed `[project]`; `/apk list` grouped by project
- Web UI: Windows/Projects panels as dropdowns with action buttons, current project in status bar, auto-load after login
- Web API: `/api/project` GET/POST; client `api()` hardened against non-JSON replies
- Autotests: `tests/test_web.py` (pytest) — API smoke + HTML/JS consistency checks
- Docs: tunnel troubleshooting (502 = TgBotTunnel down) in `web-dashboard.md` chunk
- New modules: `utils/project.py`, `handlers/project.py`, `tests/test_web.py`

### Changelog v0.8.0 2026-07-21
- Web dashboard: aiohttp server + Telegram Mini App (WEB_TOKEN / initData auth), tunnel scripts
- Web UI: light minimal theme (Warm Mono, picked via Claude Design variants), panels — screen, keys, actions, type presets, shell, git, build/APK, Claude
- Web UI: Windows focus + Projects (VSCode) panels, click-on-image remote clicks with resolution mapping, zoomable lightbox viewer
- New commands: `/win` — list & focus windows, `/code` — open project folder in VSCode
- New modules: `handlers/general.py`, `handlers/web.py`, `handlers/web_extra.py`, `handlers/windows.py`, `utils/webauth.py`

### Changelog v0.7.8 2026-04-07
- Panel: added "Click 500" button, renamed "Let's finish" → "Let's finish (F)"

### Changelog v0.7.7 2026-04-07
- Panel: added "F-cur bra" and "F-new bra" quick-type buttons for finish workflows
- Docs: added Git Workflow (current branch / new branch) to CLAUDE.md

### Changelog v0.7.6 2026-03-02
- Build: `gradlew clean` before `assembleDebug` to prevent cache issues
- Panel: Build and Build APK buttons also run clean before build

### Changelog v0.7.5 2026-02-23
- Fix: build+APK now filters for debug APK after build

### Changelog v0.7.4 2026-02-21
- Panel: added "Let's finish" quick-type button

### Changelog v0.7.3 2026-02-21
- Panel: added Shift+Tab, Build APK, Backspace×30 buttons

### Changelog v0.7.2 2026-02-20
- `/build apk` subcommand: build + auto-send APK on success

### Changelog v0.7.1 2026-02-19
- Compact build output: success shows last line only, failure shows stderr only

### Changelog v0.7.0 2026-02-18
- `/panel` command: inline keyboard control panel with button grid
- Buttons: Screen, Window, Git Status/Log/Diff, Build, APK, Status, Enter/Esc/Ctrl+C/Tab
- Auth + rate limiting on callback queries
- `send_long_text_to_chat()` utility for callback responses

### Changelog v0.6.0 2026-02-17
- `/git` command: full git CLI pass-through with smart defaults
- Smart defaults: `/git` → status, `/git log` → oneline -20, `/git diff` → stat
- Runtime working directory switch via `/git cd <path>`
- Auto-join commit messages after `-m` flag
- `GIT_DIR` config with env override

### Changelog v0.5.1 2026-02-17
- Fix: clipboard 64-bit pointer truncation (`_set_clipboard` NULL check + proper `argtypes`)
- Fix: `/sh` encoding — UTF-8 with cp866 fallback for Russian Windows
- Fix: `/sh` auto-detects PowerShell syntax and routes through `powershell -Command`

### Changelog v0.5.0 2026-02-17
- Rate limiting: `@rate_limit(seconds)` decorator on all handlers
- Auto-restart: `start_bot.bat` with 5s retry loop
- Trimmed `bot.py` (91 lines) and `input.py` (149 lines) under limits

### Changelog v0.4.0 2026-02-17
- Crop mode: `/crop x y w h`, `/crop window`, `/crop off`
- `/status` command with uptime, OS, Python info
- Reorganized `/help` by categories

### Changelog v0.3.0 2026-02-17
- File delivery: `/build`, `/apk [debug|release|list]`, `/file <path>`
- Gradle build with configurable `PROJECT_DIR` and 5 min timeout
- APK filter by name (debug/release) and list view
- 50MB file size validation

### Changelog v0.2.0 2026-02-17
- Screen capture: `/screen` (full monitor), `/window` (active window) via mss+Pillow
- Input simulation: text typing via Win32 clipboard paste, `/key` with combos and repeat count
- New commands: `/click x y`, `/focus <title>`, `/type <text>`
- Window management: `utils/window.py` with minimize/restore focus workaround
- Added Pillow dependency, keys reference docs

### v0.1.0 2026-02-16
- Core bot skeleton: auth, command routing, logging
- Stub handlers for all planned commands

### Older changelogs

There are none. v0.1.0 is the first version and it is above; the pointer that used to sit
here named a `changelog.md` that had never been written — this file is it, at last.
