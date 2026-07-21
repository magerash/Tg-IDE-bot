# TG-IDE-Bot v0.11.4

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
Panels: screen (click-to-click remote, zoomable viewer), keys, actions, windows focus, projects (VSCode), type presets, Claude, shell.

## Changelog

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
