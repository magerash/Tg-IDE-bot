# Git Handler

## Quick Reference
```
/git                    → git status (default)
/git log                → git log --oneline -20
/git diff               → git diff --stat
/git <any git command>  → pass-through to git CLI
/git commit -m message  → auto-joins words after -m
/git cd <path>          → switch working directory
/git cd                 → show current directory
```

## Overview
Pass-through git CLI handler in `handlers/git.py`. Runs `git` as a subprocess (list form, no shell) in a configurable working directory. Same encoding strategy as `/sh` (UTF-8 + cp866 fallback).

## Key Functions
- `git_cmd` — main handler, `@auth_required` + `@rate_limit(3.0)`

## Config
- Working directory = current project (`utils/project.py`, see `project-switching.md`)
- Initial value: `GIT_DIR` in `config.py` (falls back to `PROJECT_DIR`)
- `/git cd <path>` switches the shared current project; `/project` also switches it

## Code Patterns
- **No shell=True** — `["git"] + args` list form for security
- **Smart defaults** — bare `/git` → status, `/git log` → oneline -20, `/git diff` → stat
- **Commit -m fix** — detects `-m` flag and joins remaining args as single message string
- **Encoding** — UTF-8 strict, cp866 fallback (Russian Windows compat)
- **Header** — every response prefixed with `[project_name] working_dir`
- **Timeout** — 60s (interactive git commands will fail)

## Related
- `handlers/shell.py` — similar pattern (shell pass-through)
- `utils/auth.py` — `auth_required`, `rate_limit` decorators
- `utils/chunks.py` — `send_long_text` for large output
