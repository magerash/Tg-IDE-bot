# Project Switching — /project + shared current-project state

## Quick Reference
| File | Purpose |
|------|---------|
| `utils/project.py` | Shared state: `get_dir()`, `get_name()`, `set_dir()`, `set_by_name()`, `list_projects()`, `project_of(path)` |
| `handlers/project.py` | `/project [name]` — show current, inline picker to switch (callback `pj:N`) |
| `handlers/web_extra.py` | `/api/project` GET (current) / POST `{folder}` (switch), `/api/folders` returns `current` |
| `web/index.html` | Projects panel: dropdown + "Set Current" / "Open VSCode" buttons; Windows panel: dropdown + "Focus"; both auto-load after auth; status bar shows current project |

## Overview
One "current project" shared by all project-scoped features. Solves: git/build/apk were
hardcoded to `PROJECT_DIR` (My habits) — now they follow the current project.

Consumers of `utils.project`:
- `/git` — runs in `project.get_dir()`; `/git cd <path>` switches it; header `[name] dir`
- `/build`, `/build apk` — build in current project; gradlew.bat existence check with
  friendly "use /project to switch" error; output prefixed `[name]`
- `/apk` — searches current project dir first, then `APK_SEARCH_DIRS`; `/apk list`
  grouped by project (via `project_of()`)
- `/code` — opens NEW VSCode window (`code -n`) AND sets current project
- `/panel` — git/build buttons use current project
- `/status` + `/api/status` — show current project
- Web: `/api/git`, `/api/build` use current project

## Key Functions
- `project.get_dir()` / `get_name()` — current abs path / folder basename
- `project.set_by_name(folder)` — folder under `PROJECTS_ROOT`
- `project.set_dir(path)` — arbitrary abs path (used by `/git cd`)
- `project.project_of(path)` — which PROJECTS_ROOT subfolder a path belongs to, else "other"
- Initial value: `GIT_DIR` from config (env override, falls back to `PROJECT_DIR`)

## Code Patterns
```python
from utils import project
cwd = project.get_dir()            # never import PROJECT_DIR directly for cwd
header = f"[{project.get_name()}]"  # prefix outputs for clarity
```
- Module-level state (single-user bot) — same pattern as `_git_dir` before
- Inline picker caches folder list, callback carries index (`pj:N`), stale-list alert
- ✅ marker on current project in picker; `edit_message_text` refreshes markers

## Commands
| Command | Handler | Status |
|---------|---------|--------|
| `/project` | `project.py:project_cmd` | Picker with current marked |
| `/project <name>` | `project.py:project_cmd` | Fuzzy switch |

## Related
- `git-handler.md`, `phase3-file-delivery.md`, `window-management.md`, `web-dashboard.md`
