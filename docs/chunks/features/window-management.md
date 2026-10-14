# Window Management — /win + /code

## Quick Reference
| File | Purpose |
|------|---------|
| `handlers/windows.py` | `/win` window list picker, `/code` VSCode folder switcher |
| `handlers/web_extra.py` | Same features over web API: `/api/windows`, `/api/focus`, `/api/folders`, `/api/code` |
| `utils/window.py` | `list_windows()`, `focus_window_exact()`, `focus_window()` |
| `config.py` | `PROJECTS_ROOT` (default `C:\Projects`, env override) |

## Overview
Solves "can't pick window/folder by name": VSCode titles start with the open file
(`file.py - Folder - Visual Studio Code`), so blind `/focus` substring match is unreliable.

- `/win` — lists all visible windows as inline buttons; tap → focus by exact title.
- `/code [folder]` — bypasses window titles entirely: fuzzy-matches folder under
  `PROJECTS_ROOT`, runs `code -n "<path>"` (NEW VSCode window — does not replace the
  currently open project) and sets it as current project (`utils/project.py`).
  No args or ambiguous → inline button picker.

## Key Functions
- `win_cmd()` — caches titles in `_win_cache`, buttons carry index (`w:f:N`)
- `code_cmd()` — fuzzy match: substring, exact-match preferred; single hit opens directly
- `windows_callback()` — handles `w:f:N` (focus) and `w:c:N` (open folder); auth-checked
- `_open_in_vscode(folder)` — `subprocess.Popen('code -n "<path>"', shell=True)` + `project.set_by_name(folder)`
- `list_windows(limit=30)` — visible, non-empty, deduplicated titles
- `focus_window_exact(title)` — exact match, fuzzy fallback (contains / 25-char prefix).
  Returns `(ok, msg)`; `msg` starts with `"Window gone: "` when nothing matched, which
  `/api/focus` surfaces as a `gone: true` flag so the dashboard can retire a dead
  recents chip (but keep one that merely failed to activate). The dashboard's
  `_matchesLive()` mirrors this matcher — change one, change both, or recent-window
  chips get hidden while focus would still work (see `web-dashboard.md`)
  for titles that changed since listing; honest ok/blocked result
- `utils/winfocus.py:force_foreground(hwnd)` — reliable activation chain: Alt-tap unlock →
  `SetForegroundWindow` → `AttachThreadInput` fallback → minimize/restore (re-maximizes if
  was zoomed) → verified via `GetForegroundWindow`. pygetwindow `.activate()` alone fails
  when caller isn't foreground; old min/restore trick broke maximized/UWP windows.
  Elevated (admin) windows still unfocusable without admin — reported as "Focus blocked"

## Code Patterns
```python
# callback_data limited to 64 bytes → store titles in module cache, pass index
_win_cache = list_windows()
Btn(f"{i+1}. {t[:48]}", callback_data=f"w:f:{i}")
# stale index after new /win call → "Stale list" alert
```

## Commands
| Command | Handler | Status |
|---------|---------|--------|
| `/win` | `windows.py:win_cmd` | Working |
| `/code [folder]` | `windows.py:code_cmd` | Working |

## Related
- `phase2-screen-input.md` — `/focus`, input simulation
- `panel.md` — inline keyboard patterns
