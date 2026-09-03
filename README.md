# TG-IDE-Bot v0.21.0

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
| `/win` | List open windows, tap to focus |
| `/code [name]` | Open project in new VSCode window + set current |
| `/project [name]` | Show/switch current project (git, build, apk follow it) |
| `/status` | Bot uptime & system info |
| `/help` | List all commands |
| Plain text | Typed into active window + Enter |

## Web Dashboard
Set `WEB_TOKEN` (+ optionally `WEBAPP_URL` for Telegram Mini App) in `.env`, then open `http://localhost:8080`.
Panels: screen (click-to-click remote, zoomable viewer, ▲/▼ scroll arrows), keys, actions, windows focus, projects (VSCode), type presets, Claude, shell.

## Restart & Operations

### Remote path
```
phone → https://bot.magerash.com:8443 → Caddy (VPS) → 127.0.0.1:18080 (VPS)
      → reverse SSH tunnel → 127.0.0.1:8080 (this PC) → aiohttp / bot.py
```

`<vps>` below is **`vpn.magerash.com`** — the tunnel targets the hostname, never
a raw IP. The address behind it changed once already (`45.150.33.106` → filtered
by RF DPI → `213.165.40.182`), so a migration is a Cloudflare edit plus a tunnel
restart, with no code change. Details:
[`docs/documentation/README-vps.md`](docs/documentation/README-vps.md) (the file itself is gitignored).
ssh resolves per connection, so a DNS change only takes effect after the ssh
process is restarted.

**`start_bot.bat` is the single entry point** — it starts the tunnel keeper, then the bot.
Run it after a reboot (or put it in `shell:startup`) and the whole path comes up.
Safe to run twice: the keeper refuses to start a second instance and
`utils/singleton.py` kills stale bots.

| Piece | How it runs |
|-------|-------------|
| Bot | `start_bot.bat` step 2 — `python bot.py` in a 5s auto-restart loop |
| Tunnel | `start_bot.bat` step 1 → `wscript.exe start_tunnel_hidden.vbs` → hidden `start_tunnel_vps.ps1` → `ssh -N -R 18080:127.0.0.1:8080 root@<vps>`, reconnects every 5s. Scheduled task **`TgBotTunnel`** may also start it — the keeper's single-instance guard makes that harmless |
| Watchdog | `utils/tunnel.py` — bot checks every 60s; if no `ssh.exe`, runs `schtasks /run /tn TgBotTunnel`, or the `.vbs` directly when the task isn't registered |

"Restart Bot" from the dashboard/Telegram re-execs python inside the same process
(`os.execv`), so it never falls out of the batch loop and never touches the tunnel.

### Restart the bot
```powershell
# graceful: dashboard → Actions → "Restart Bot"  (POST /api/restart, os.execv)

# from a shell — the batch loop respawns it in 5s
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $_.CommandLine -match 'bot\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# cold start (no loop running) — also brings the tunnel up
Start-Process cmd.exe -ArgumentList "/c","C:\Projects\Tg-IDE-bot\start_bot.bat" -WorkingDirectory "C:\Projects\Tg-IDE-bot"
```

### Restart the tunnel
```powershell
# 1. kill keeper(s) + ssh   — $PID guard matters, see gotcha below
$pat = 'start_' + 'tunnel_' + 'vps'
Get-CimInstance Win32_Process -Filter "Name like 'powershell%'" |
  Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match "-File.*$pat" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Get-Process ssh -ErrorAction SilentlyContinue | Stop-Process -Force

# 2. start exactly one keeper
schtasks /run /tn TgBotTunnel
```

### Verify (bottom-up — first failing step is the culprit)
```bash
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/            # bot alive          → 200
ssh root@<vps> "ss -lptn 'sport = :18080'"                              # tunnel bound       → LISTEN
ssh root@<vps> "curl -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18080/"  # tunnel usable → 200
curl -k -o /dev/null -w "%{http_code}\n" https://bot.magerash.com:8443/ # Caddy + public     → 200
```

### 502 troubleshooting
| Symptom | Cause | Fix |
|---------|-------|-----|
| Local `:8080` refuses | Bot down | Restart bot (above) |
| `remote port forwarding failed for listen port 18080` in `ssh -v` | Local ssh was killed hard; VPS `sshd-session` still holds the port | `ssh root@<vps> "ss -lptn 'sport = :18080'"` → `kill <pid>`, then restart tunnel |
| Tunnel LISTENs, VPS-local curl to `:18080` works, public still 502 | Caddy upstream port wrong | `/etc/caddy/Caddyfile` must read `reverse_proxy 127.0.0.1:18080` (**not** `:8080` — that's this PC's port, not the VPS's). Then `systemctl reload caddy` |
| Several `ssh.exe` / keepers alive, tunnel flaps | Watchdog ran `schtasks /run` while a keeper existed — each run spawns another keeper, and they fight over remote port 18080 | Kill all, start one (above) |

**Gotcha:** when matching processes by command line, exclude your own shell (`$_.ProcessId -ne $PID`) — a `Where-Object { $_.CommandLine -match 'start_tunnel_vps' }` filter matches the very command that contains that string, so the kill loop terminates your own session and inflates keeper counts by one.

## Changelog

### v0.21.0 2026-09-03
- **Documentation is in git for the first time.** `materials/` (31 files, 160KB of feature chunks) was gitignored, so none of it reached a clone. Moved to **`docs/`** and adopted onto the `llm-wiki-kit` template — preflight, update regulation, code map, roadmap, and a decisions ledger recovered from 20 versions of changelog. `CLAUDE.md` goes 527 → 97 lines and imports the new tracked `AGENTS.md`
- The VPS/VPN topology file stays **gitignored on purpose** — this repo is public and that file maps the machine the bot types into. See `docs/documentation/README-vps.md`
- **📎 Attachments** — send a document to the bot or upload from the Mini App; its **path** is typed into the terminal, so Claude Code reads the file itself. Whole file, instantly, at any size — instead of a wall of clipboard text
- **⌨ A Russian keyboard layout no longer eats every keystroke.** `pyautogui` resolves characters through the *active* layout, where `VkKeyScanW('v')` returns `-1` and the key is never sent. Typing now goes out as virtual-key codes; the layout is readable and switchable from the bottom bar
- **Terminal detection by process, not window title** — a terminal wears the name of whatever runs inside it, so `WindowsTerminal.exe` showing `✳ Claude Code` matched no hint and the v0.17.1 silent paste no-op came back on an untested surface
- **📱 The scroll arrows were never missing — they were invisible.** A dark 42%-opaque pill with no border on a dark VS Code screenshot, with `:hover` (which never fires on touch) as the only contrast state. Now a light hairline ring, a stronger fill, and 44px targets on a phone. Two unreported bugs fixed alongside: the held state was **white on white** in night theme, and the answer field scrolled away with the keys
- **The bottom bar folds** — a caret at the far left, same accordion idiom as the Windows/Projects panels, ~36px of screen returned. Phone compaction shrinks inline padding and gaps while holding every touch target's height
- Tests 74 → **94**, with the new assertions mutation-tested; both wiki checkers now gate each commit

### v0.20.0 2026-08-25
- **Typing lands in the terminal now.** v0.19.1 diagnosed it: window focus raises the *window*, the inner keyboard focus stays put, and after `code -n` that is the editor — where `ctrl+shift+v` is an editor binding and the paste vanishes while the bot reports `Typed:`. `POST /api/type` accepts `terminal: true` and moves the caret into the VS Code integrated terminal first
- `utils/vscode.py` holds the command-palette sequence, once. The scheduler's private copy was deleted and it imports the shared helper; a test fails if a second copy appears. The outcome is echoed back (`terminal`, `terminal_msg`) and a non-VS-Code foreground is a loud toast, not a silent success — the text is still typed either way
- **Claude Code launcher** — one orange button in the Actions rail, the quick-keys bar and the zoomed viewer. Types `claude` + Enter into a **fresh** terminal: focusing the last active one hands `claude` to a session already running Claude Code as a chat message. `VSCODE_NEW_TERMINAL_WAIT` (1.6s) waits for the shell prompt, since keystrokes sent before it are dropped by the pty
- **Freeform answer field replaces the `1` / `2` buttons** (bar + viewer) — Enter sends text + Enter, so `3`, `yes` or a path are answerable too; `Tab` added beside `Sh+Tab`, tinted apart
- **Viewer project row** — project select + 🖥 Focus + Open + Claude: pick a project, focus or open its VS Code window, start a session, without leaving the zoomed screenshot. Shares `_selectedProject(selId)` and `loadFolders()` with the dashboard panel. The viewer's gesture guard now exempts `INPUT`/`SELECT`/`OPTION` as well as `BUTTON`, or a tap on the field would pan the image and dismiss the viewer
- **Compact viewer controls on phones and short landscape windows** (`max-width:620px`, `max-height:520px`): 32px pills, one row per group, select and field shrink to fit. At desktop sizing the two rows wrapped into four and covered half the screenshot
- Tests 68 → **74**

### v0.19.1 2026-08-24
- **`/refine` uses the whole window.** On a 2000px screen the view was a 640px column stranded in the middle with the text scrolling inside 400px of it while the rest of the page sat empty. The wrap goes to `max-width:1180px` and, above 760px, both panes are sized from the viewport (`calc(100vh - 300px)`, min 340px) instead of from their content
- The fix needed the JS as well as the CSS: `autoGrow` writes an **inline** height capped at 400px, and an inline height beats a stylesheet rule — it silently undid the fit on every keystroke, every Improve, every transcription. `autoGrow` is now wrapped on this page and clears the inline height on wide screens, keeping the original growth behaviour for the stacked phone layout
- Reading measure is capped **inside** the preview (`.md-body>* {max-width:78ch}`) rather than on the pane, so long-form text stays comfortable to read while the panel still fills the window
- **Char/word counter** next to Copy — routed through the wrapped `autoGrow`, so every programmatic write (Improve, transcription, history refill, Clear) updates it for free, not just typing
- Diagnosed but not code: **typing lands where the inner keyboard focus is.** `focus_window_exact` raises the *window* only. With VS Code focused but the caret in the editor rather than the integrated terminal — or Claude Desktop foreground with its chat box unfocused — `ctrl+shift+v` / `ctrl+v` hits a different control and the text vanishes while the bot still reports `Typed:`. Clipboard write, keystroke injection and paste key were each proven working against a live window. `utils/scheduler.py` already solves this with a command-palette "Terminal: Focus on Terminal View" step; `/api/type` and `text_handler` do not use it yet
- Tests 67 → **68**

### v0.19.0 2026-08-24
- **Split-view Mini App**: text refinement now has its own page, **`/refine`** — mic → speech-to-text, AI cleanup, ✨ Improve, Twin, markdown preview and a **📋 Copy** button, with no screen, keys, shell, git or restart anywhere on it. Text leaves that view through the clipboard only; there is deliberately no Type button, because typing into a focused window is remote control and Copy is not
- **The split is enforced on the server, not just hidden in the UI.** The refine page runs on a 12h scope-limited token minted by `POST /api/scope`; only `/api/status`, `/api/stt` and `/api/improve` accept it, and all 24 system endpoints answer 401. Two tests keep it that way, so "this view can't type to your PC" cannot quietly regress the next time a button is added
- Where the boundary really is: inside Telegram, `initData` is readable by any script on the page, so this defends against the page's own code and narrows the browser flow — it is not a sandbox against the operator. Written up in `docs/chunks/features/refinement-view.md`
- **Reach it** from the `✨ Refine` link in the dashboard header, or the `🖥 Dashboard` / `✨ Refine` buttons now on the first row of `/panel` (private chats only — Telegram rejects Mini App buttons in groups and fails the whole message)
- **`web/common.js`**: ~460 lines shared by both pages (`api()`, toasts, theme, History, markdown, the mic→WAV→Whisper stack, Improve) extracted out of `index.html`, which drops 2332 → 1889 lines. One copy of each hard-won bug fix instead of two
- **Security fix in the markdown preview** (shared by both views): HTML-escaping now covers quotes, and link targets are restricted to `http(s)`/`mailto`/relative — a `[x](javascript:…)` link previously rendered as a live link that would run script with the page's credentials
- **Copy** uses the async clipboard API with an `execCommand` fallback for Telegram's Android webview, which refuses the former. An empty field never clobbers the clipboard, and very large text is selected rather than copied
- Fixes: markdown preview went stale after voice transcription; the stale-client reload flag is now per page; `improve.py` logged a misleading "twin profile missing" warning on any non-Russian input
- Tests 43 → **67**

### v0.18.0 2026-08-20
- **Improve text (AI)**: ✨ Improve button on the dashboard Type field — rewrites rough text via LLM in a chosen style (Structured / Detailed / Concise / →EN). Never auto-sends; the original is saved to History as a `draft` entry first. Optional **Twin** toggle injects the HAE operator profile so output matches your own prompt style; Russian input stays Russian (deterministic language hint — instructions alone lost to a 6KB English persona)
- **Quick-keys bar**: fixed bottom row — ← → Enter Sh+Tab 1 2 — for answering Claude Code question prompts from anywhere, with a recently-tapped-keys trail. Same keys also inside the zoomed screenshot viewer
- **Mobile layout**: Screen first, then Windows, then Projects; Windows/Projects fold as accordions (state persisted)
- **Fix: zombie instance could hold the web port through an endless crash loop.** Singleton guard rewritten on psutil API kills — the old `taskkill`/powershell subprocesses timed out on every restart when process creation on the box hung, while an in-process kill worked instantly
- **Favicon**: rounded-square Telegram-blue "TG" tile (SVG + PNG + ICO + apple-touch)
- Tests 36 → 43

### v0.17.1 2026-08-17
- **Fix: typing still landed nowhere in a Claude Code terminal.** Claude Code binds Ctrl+V to "paste image from clipboard", so a text paste is a silent no-op — key delivered, clipboard correct, prompt empty. The paste key is now chosen from the target window: terminals (VS Code, PowerShell, git bash, Windows Terminal) get **Ctrl+Shift+V**, ordinary apps keep Ctrl+V. Tunable via `TYPE_PASTE_HOTKEY` / `TYPE_TERMINAL_PASTE_HOTKEY` / `TYPE_TERMINAL_HINTS`
- **Fix: voice cleanup stopped improving transcripts.** Groq retired `llama-3.3-70b-versatile` (404 on an existing key, whole Llama family gone); Whisper was unaffected, so recognition kept working and only the cleanup died. Model is now `qwen/qwen3.6-27b` with `openai/gpt-oss-20b` as fallback — same free Groq key, only the model string changed
- Reasoning output is suppressed and stripped — an unguarded qwen3.6 returned 7196 chars of `<think>…` for a 483-char transcript, which would have been typed into Claude Code verbatim
- A failed cleanup is now visible instead of silently returning raw text: `/api/stt` reports `humanized` + `humanize_error`, the dashboard toasts it, and Telegram appends `⚠ AI cleanup failed`
- Tests 33 → 36

### v0.17.0 2026-08-17
- **Fix: typing from the bot stopped submitting.** Text was pasted, then Enter was pressed 0.1s later — Claude Code buffers a bracketed paste and folds an Enter arriving inside that window into the paste as a newline, so the message sat unsent in the input box while the bot reported `Typed: ...`. Affected every surface at once (Telegram chat, Mini App, panel presets, voice, scheduled messages) because all four shared that delay
- `type_and_enter()` is now the single place paste and Enter are sequenced, with `TYPE_ENTER_DELAY` (default 0.45s) between them. Raise it in `.env` if a message still hangs unsent
- A modifier left down by an earlier hotkey (Auto = Shift+Tab ×3) is released before pasting — otherwise Ctrl+V silently becomes Ctrl+Shift+V
- **Scroll arrows on the live view** — ▲/▼ on the right edge of the screenshot and in the zoom viewer, hold to keep scrolling (`POST /api/scroll`). Windows routes the wheel by cursor position, so the server parks the cursor over the target window, scrolls, and restores it; in Window mode the arrows follow the frame you are looking at
- Failed window focus is now logged with the requested title and the live window list (it used to log successes only)
- Tests 28 → 33

### v0.16.7 2026-08-16
- **Zoomed screenshot no longer closes itself on Android.** Two independent causes, both fixed: Telegram treats a vertical drag inside a Mini App as "dismiss", which is exactly the pan gesture — startup now calls `disableVerticalSwipes()` (Bot API 7.7+, ignored by older clients)
- The viewer's own backdrop-close was firing on taps that landed on the image: `setPointerCapture()` retargets every later pointer event to `#lightbox`, so `pointerup` could not tell image from backdrop. That decision moved to `pointerdown`, the only event with a truthful target
- Pinch tails and multi-finger gestures can't be read as a close tap (`_lb.multi`, "other fingers still down" guard); a gesture stolen by the OS now arrives as `pointercancel` instead of leaving a stale finger that wedged pan/pinch
- Telegram BackButton is shown while the viewer is open — hardware back closes the viewer, not the whole Mini App
- **Current window now always appears in the quick-pick chips and lights up green.** VS Code puts the open file first in its title, so two titles of the same window share no prefix and neither contains the other — the chip looked dead. Windows are now identified by their tail (last two `" - "` segments, `tail_key()`), matched the same way on client and server
- Retitled entries merge into one chip instead of one-per-open-file, recents ties break by recency, and the focused window is pinned first — even when it was focused outside the dashboard
- Tests 25 → 28

### v0.16.6 2026-08-09
- **Tunnel moved off the raw IP.** `start_tunnel_vps.ps1` now targets `root@vpn.magerash.com`. The VPS address changed once already (`45.150.33.106` silently dropped by RF DPI → `213.165.40.182`), and pinning it in the repo meant an infrastructure event became a code change. A future migration is one Cloudflare edit plus a tunnel restart
- ssh resolves per connection, so a DNS change only lands on reconnect — kill `ssh.exe` and let the keeper redial. The A-record must stay DNS-only/grey: Cloudflare's proxy is HTTP-only and would kill ssh along with the VPN's UDP
- Recovered the live tunnel: stale keeper still held the old IP in memory, and a leftover `sshd-session` on the VPS squatted on `:18080`, so every reconnect died on `ExitOnForwardFailure`. Verified end to end — 71KB frame in 0.50s through the tunnel (~140KB/s)
- Docs: `vps-architecture.md` → **v1.3** — names table with verified resolutions, domain endpoint marked live and extended to the ssh tunnel, split-tunnel address updated, "if the address is filtered again" runbook. `plane.magerash.com` is now the only name still on the filtered IP
- Split-tunnel note corrected throughout: Amnezia excludes by **address, not hostname**, so the exclusion list does not follow DNS and must be re-checked after every migration
- No behavior change in the bot itself

### v0.16.5 2026-08-06
- Recent window/project chips are validated against the live list — a chip for a closed window no longer sits there looking tappable. Matching mirrors the server's focus logic (exact → containment → 25-char prefix) so VS Code retitling itself per open file doesn't hide a working chip
- Storage survives the filter: close a window and reopen it and its chip comes back with its frequency. Entries unused for 30 days are dropped
- `/api/focus` returns a `gone` flag; a chip is retired only when the window truly no longer exists, not when activation is merely blocked
- Tests 23 → 25

### v0.16.4 2026-08-06
- **Root cause of the slow Mini App: the phone's VPN.** The VPN server is the same VPS the bot's domain resolves to, so with the VPN on the phone tunnels bot traffic *to the VPS through the VPS*. The PC is unaffected because WireGuard auto-excludes its own endpoint IP; Android WireGuard protects only its own socket, so other traffic to that IP still enters the tunnel. **Fix: exclude the VPS address (`213.165.40.182`) from the VPN on the phone** (Amnezia split tunneling, which matches by address, not hostname) — no privacy cost, since the destination *is* the VPN server
- Ruled out first: server (40ms/frame), PC→VPS (46 Mbit/s), VPS shaping (none), hairpin/DNS/NAT (the VPN container fetches the dashboard fine), MTU (client 1280 changed nothing, `awg0` is a correct 1420). Frames degrade 2s → 18s within a session while clicks stay instant — carrier policing of the UDP flow, not a size cliff
- Frame abort 20s → 45s: aborting an 18s frame throws away transferred bytes and turns "slow" into "never updates"
- Default resolution 1920 → **Fit** (adaptive); fixed sizes never adapt to a bad link. Lightbox still pulls ≥1920
- Adaptive sizing corrects in proportion to the overshoot and converges in one step instead of minutes

### v0.16.3 2026-08-05
- Investigated the "Mini App never updates" report against the access log: server renders a frame in 40ms, PC→VPS measures 46 Mbit/s, VPS has no shaping — but the phone's own throughput fell from ~194KB/s (July 23: 17,358 frames at a 1s cadence) to ~20–40KB/s in August, same device and tunnel. Not a code regression; the fix is to need far fewer bytes
- **`POST /api/frame`** — binary WebP transport: no base64 (−25%), WebP instead of JPEG (−37%), `204` with no body when the screen is unchanged, metadata in `X-Rect`/`X-Hash`/`X-Mode` headers. Through the tunnel: 1280px **109KB → 50KB**; **1920px now costs 82KB, less than the old 1280px** — sharper *and* faster. Old JSON endpoints kept for cached clients
- Adaptive sizing in `Fit` mode: frames that don't fit the Auto tick shrink automatically (floor 480px) and grow back when the link allows. Explicit 1280/1920/Full are never overridden
- Auto-refresh pauses while the tab/webview is hidden — a background dashboard was pulling 1.2GB/day through the tunnel and starving the phone
- Status line now shows throughput: `Window updated · 430ms · 50KB · 116KB/s`
- Tests 20 → 23

### v0.16.2 2026-08-05
- Fix: `fetch()` has no timeout — a request stranded by a dropped tunnel hung forever and (with v0.16.1's single-flight queue) wedged the live view permanently. This is why the Mini App stopped updating while the browser looked fine. All API calls now carry an abort deadline (20s default, unbounded only for `/api/sh` `/api/claude` `/api/build` and repeat-key runs), plus a 30s stuck-queue reset
- Screen panel: **transfer resolution selector** — `Fit` / `1280` / `1920` (default) / `Full`, persisted; JPEG quality scales with it. v0.16.1's 1280@q55 was a visible downgrade
- Lightbox pulls ≥1920 immediately on open (zoom view is for reading fine text)
- Fix: `max_w=0` (the Full setting) was treated as "not supplied" and capped back to the default
- Defaults raised for clients that send no preference: `WEB_SCREEN_MAX_W` 1280→1920, `WEB_SCREEN_QUALITY` 55→70
- Fix: stale Mini App — Telegram's webview caches the page per URL and ignores no-cache headers. The menu-button URL is version-stamped and the page reloads itself once as `?v=<server version>` when its `CLIENT_VERSION` doesn't match the bot
- Expired Mini App session (initData is valid 24h) now says so instead of "Invalid token"
- Tests 16 → 20

### v0.16.1 2026-08-05
- Live view: single-flight capture queue — one frame request in flight, extras coalesce into one pending run; Auto is a `setTimeout` chain measured from completion, not `setInterval`. Fixes clicks taking ~15s to appear (or never) as blind post-click refreshes + auto ticks piled up in the reverse-SSH pipe
- Live view: lightbox no longer runs a second refresh loop — its Auto pill drives the shared loop (was doubling frame requests while open)
- Frames: downscale + softer JPEG (`WEB_SCREEN_MAX_W` 1280, `WEB_SCREEN_QUALITY` 55); client requests only the pixels the view shows (container × DPR, 1920 in lightbox). 250KB → ~40KB per frame, 0.44s through the tunnel
- Frames: `hash` round trip — server replies `{same:true}` (~80 bytes) when pixels are unchanged; status line reports real cost (`Screen updated · 430ms · 40KB`)
- Ops: `start_bot.bat` is now the single entry point — starts the hidden tunnel keeper, then the bot restart loop. Safe to run twice; dashboard/Telegram "Restart Bot" (`os.execv`) unaffected
- Ops: `start_tunnel_vps.ps1` single-instance guard — two keepers meant two ssh clients fighting over remote port 18080, the loser retrying every 5s (tunnel flap). Watchdog falls back to the `.vbs` when the `TgBotTunnel` task isn't registered instead of self-disabling
- Web mobile: reorder to Windows → Projects → Screen → Type Text (context pickers first, screen adjacent to input); current window/project tinted green in the recents lists
- Panel + Web: `Ultrathink` preset types `Ultrathink ` without Enter (keyword, not a slash command)
- Docs: README "Restart & Operations" runbook; tests 14 → 16

### v0.16.0 2026-07-26
- Web: Windows/Projects moved into the side rails (left = Windows + Keys, right = Projects + Actions); rails stay compact + sticky-locked while the center scrolls
- Web mobile: `display:contents` reflow restores the old top→bottom order (Screen → Windows → Projects → Keys → Type → …)
- Auto mode: `Auto` key (web + TG panel) sends Shift+Tab ×3 with 1s gaps to cycle Claude Code modes; `/api/key` gains `interval`
- Image paste: saves a temp PNG and types its file path into the terminal (Claude Code attaches it) — terminals can't accept a Ctrl+V image
- Web: Enter sends / Shift+Enter newline restored; screen Auto button green while running, Keys Auto button gray

### v0.15.1 2026-07-23
- Panel + Web: `/model` quick-type button (after LF NB) — types `/model` + Enter
- Web: `continue` quick-type button in Type Text section (green)
- Web: color-coded Keys rail — Enter, Sh+Tab green; Esc red (`--warn` vars + `.btn-warn-soft` added)

### v0.15.0 2026-07-23
- Scheduled messages: queue text to type into a window at a set time (e.g. after a Claude Code limit reset) — `Scheduled` panel with reset-time quick buttons, live list + cancel; persistent, survives restart; TG notify on fire
- Scheduler: focus-settle + VS Code integrated-terminal focus (types into the Claude terminal, not the editor)
- Web: night theme toggle (🌙/☀ header, persisted); fix: zoomed lightbox now auto-refreshes the live frame
- New: `utils/scheduler.py`, `/api/schedule` `/api/schedules` `/api/unschedule`, `SCHEDULE_*` config

### v0.14.1 2026-07-23
- Web: `1` `2` `3` fast-answer keys in Keys rail (type digit+Enter for numbered prompts)
- Web: Screen controls moved below the screenshot (closer to input); `/ultrathink` → `Ultrathink`
- Web: removed `Click 250,1000` from Actions (screenshot Click-mode replaces it)

### v0.14.0 2026-07-22
- Claude Code metrics: live web card — model + effort tags, context %, 5-hour & weekly limit blocks with reset countdowns
- Reads local `~/.claude` state (OMC usage cache + session transcripts); metrics follow the selected project
- ↻ refresh button + 30s auto-poll; `/api/ccmetrics`, `utils/ccmetrics.py`, `CC_*` config
- Fix: oversized textarea resize grip → subtle default handle

### v0.13.0 2026-07-22
- Humanize: raw dictation → clean prompt text via Groq LLM; TG Raw/Clean toggle, web AI: ON/OFF toggle
- Recording: 10 min cap with ticking timer; fix 1MB body limit that killed long uploads
- Remote double-click (tap-delay pattern) on screen + zoomed viewer; double-tap-zoom close bug fixed
- Screen: auto-capture + Auto 3s on login (Window mode default), viewer inherits Auto
- Windows/Projects: current-window tag + top-3 recent one-tap chips
- Type panel: big center record button, AI/Type on sides; auto-grow inputs; visible resize grip

### v0.12.0 2026-07-22
- Audio-to-text: TG voice message → Groq Whisper transcript + action buttons (Type / Type+Enter / Claude)
- Web: mic button in Type panel — record → WAV re-encode (Web Audio) → `/api/stt` → text into Type field
- Web: silence detector with mic device label (skips API call, shows diagnostic toast)
- Web UI: mobile Keys chips above Type Text, Actions below; mic SVG icon; Type+mic column on mobile; inputs min-height 84px
- Web: Screenshot/Window buttons highlight instantly on click (optimistic, capture confirms)
- New modules: `utils/stt.py`, `handlers/audio.py`; config `GROQ_API_KEY`, `STT_MODEL`

### v0.11.4 2026-07-21
- Panel + Web: `/plan`, `/hae:release-plan`, `/twin` quick-type buttons
- Web: Keys/Actions rails top-align with Type Text panel; History panel moved below Type Text

### v0.11.3 2026-07-21
- Panel + Web: finish buttons compacted — "Let's finish (LF)", "LF CB", "LF NB"; gray hint note under web presets

### v0.11.2 2026-07-21
- Panel + Web: `/clear`, `/caveman`, `/ultrathink` quick-type buttons (typed into focused window + Enter)
- Panel + Web: renamed finish buttons — "Let's finish (LF)", "LF on current branch (CB)", "LF and go new branch (NB)"
- Panel: type presets unified into `_TYPE_PRESETS` dict (single handler)

### v0.11.1 2026-07-21
- Web UI: Auto/Click buttons show active state in green/red on main screen

### v0.11.0 2026-07-21
- Web UI: multi-row inputs (Type/Claude/Shell), paste compose with text-block and image chips, History panel
- Screen: auto-refresh interval selector, lightbox Auto/seconds pills, active-mode highlight
- Fix: capture race guard, one-click lag, token wipe on empty login
- Focus: Win32 activation chain — works on all windows, fuzzy title fallback
- Ops: single-instance guard (port crash loop fix), windowless tunnel launcher

### v0.10.0 2026-07-21
- Web UI: compact layout — sticky Keys/Actions side rails, fluid width, Windows+Projects side by side, mobile chip rows
- Web: "Restart Bot" action with reconnect polling; persistent action status field in Actions rail
- Fix: macOS Telegram Mini App red screen (skip hex color calls on macOS platform)
- Fix: dashboard HTML served with no-cache headers
- Ops: tunnel watchdog — bot auto-restarts TgBotTunnel task if SSH tunnel dies

### v0.9.0 2026-07-21
- Project switching: `/project` command + shared current-project state — git, build, APK, panel and web all follow it
- `/code` opens project in new VSCode window (`code -n`) and sets it current; no longer replaces active window
- Build: friendly error when no `gradlew.bat`, output prefixed with project name; `/apk list` grouped by project
- Web UI: Windows and Projects panels redesigned as dropdowns with action buttons; current project in status bar; auto-load after login
- Web API: `/api/project` GET/POST; client hardened against non-JSON error replies
- Autotests: `tests/test_web.py` (pytest) — API smoke + HTML/JS consistency checks
- Docs: tunnel troubleshooting (502 = TgBotTunnel down)

### v0.8.0 2026-07-21
- Web dashboard: aiohttp server + Telegram Mini App (WEB_TOKEN / initData auth), tunnel scripts
- Web UI: light minimal theme, panels — screen, keys, actions, type presets, shell, git, build/APK, Claude
- Web UI: Windows focus + Projects (VSCode) panels, click-on-image remote clicks with resolution mapping, zoomable lightbox viewer
- New commands: `/win` — list & focus windows, `/code` — open project folder in VSCode

### v0.7.8 2026-04-07
- Panel: added "Click 500" button, renamed "Let's finish" → "Let's finish (F)"

### v0.7.7 2026-04-07
- Panel: added "F-cur bra" and "F-new bra" quick-type buttons for finish workflows
- Docs: added Git Workflow (current branch / new branch) to CLAUDE.md

### v0.7.6 2026-03-02
- Build: `gradlew clean` before `assembleDebug` to prevent cache issues
- Panel: Build and Build APK buttons also run clean before build

### v0.7.5 2026-02-23
- Fix: build+APK now filters for debug APK after build

### v0.7.4 2026-02-21
- Panel: added "Let's finish" quick-type button

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
