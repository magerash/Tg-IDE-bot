# Claude Code Metrics

Live monitor of the running Claude Code CLI — same numbers the VS Code terminal
shows — surfaced in the web dashboard: active **model** + **effort** tags,
**context** usage %, and the **5-hour** / **weekly** rate-limit blocks with reset
countdowns.

## Quick Reference

| Item | Value |
|------|-------|
| Util | `utils/ccmetrics.py` (`collect()`) |
| Endpoint | `GET /api/ccmetrics` → `{ok, metrics}` (auth required) |
| UI | `#cc-metrics` card under the status bar in `web/index.html` |
| Config | `CC_USAGE_CACHE`, `CC_PROJECTS_DIR`, `CC_CONTEXT_WINDOW` |
| Poll | client fetches on login + every 30s; reset countdown ticks 1s |

## Data Sources (all local `~/.claude` files, no network)

| Metric | Source file | Field |
|--------|-------------|-------|
| 5h % + reset | `plugins/oh-my-claudecode/.usage-cache-anthropic.json` | `data.fiveHourPercent`, `data.fiveHourResetsAt` |
| Weekly % + reset | same | `data.weeklyPercent`, `data.weeklyResetsAt` |
| Model | selected project's newest `.jsonl` | last `message.model` |
| Effort | same transcript | top-level `effort` key |
| Context tokens | same transcript | last `message.usage` (input + cache_read + cache_creation) |
| Session id | same transcript | `cwd`, `gitBranch` |

- **Follows the dashboard's selected project** — the endpoint passes
  `project.get_dir()` to `collect()`, which reads that project's newest transcript
  (path encoded as folder: `:` `\` `/` space → `-`, e.g. `C--Projects-My-habits`).
  Switching project in the UI re-fetches metrics. No cross-project fallback: a
  project with no session shows `session_found:false` (model/context blank) while
  the account-wide 5h/weekly limits still render.
- With no project passed, `collect()` uses the **globally newest** transcript.
- Transcripts read via **tail** (`_tail_lines`, last 200 KB) — large files stay fast.
- **Refresh** — ↻ button in the card header (`onclick=loadCCMetrics()`, spin
  animation); also auto-refreshes on login, every 30s, and on project switch.

## Key Functions (`utils/ccmetrics.py`)

- `_read_usage_cache()` — 5h/weekly block + `usage_age_sec` + `usage_stale`
- `_newest_transcript()` — most-recently-modified transcript path (global)
- `_project_transcript(dir)` — newest transcript for one project (path→folder encode)
- `_read_session(project_dir=None)` — model, effort, context tokens/%/window, project+branch
- `collect(project_dir=None)` — merged dict for the endpoint (logs a DEBUG summary line)

Every read is wrapped — missing files return `{}`, never raises.

## Config

```python
CC_USAGE_CACHE   = ~/.claude/plugins/oh-my-claudecode/.usage-cache-anthropic.json
CC_PROJECTS_DIR  = ~/.claude/projects
CC_CONTEXT_WINDOW = 1000000   # 1M-context models; set 200000 for standard
```

## Caveats

- **5h/weekly freshness** — the OMC cache only refreshes while Claude Code runs
  with OMC polling. `usage_age_sec` / `usage_stale` expose staleness.
- **Context window** — model id can't distinguish 200k vs 1M variants, so the
  window is a config constant. Wrong value → wrong % (bar clamps at 100).

## UI (`web/index.html`)

- Card `#cc-metrics`: chip row (model / effort / session·branch) + 3 meters.
- `loadCCMetrics()` renders; `_ccMeter()` colors bar green/amber/red at 70/90%.
- `_ccFmtLeft(iso)` → "resets in 2h 14m"; `_ccTickCountdown()` on 1s interval.

## Tests

`tests/test_web.py::test_ccmetrics_endpoint_and_collect` — collect() returns dict,
endpoint 401 without auth / 200 with. HTML-consistency tests auto-cover new ids +
the `/api/ccmetrics` route.
