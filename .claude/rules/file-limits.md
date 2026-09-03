---
paths:
  - "handlers/*.py"
  - "utils/*.py"
  - "bot.py"
  - "config.py"
  - "web/*"
---

# File limits

A cap is a smell with a prescribed remedy, not a fault. Crossing one means the file has
started doing a second job; the remedy names which job to move out.

The table is read by `tools/wiki/hook_caps.py`, so the columns are fixed: a name, a glob the
file must match, the budget, and the remedy. The hook warns, it never blocks — whether a
file has really taken on a second job is a judgement, and the hook is not the one making it.

| Kind | Glob | Max lines | When it is exceeded |
|---|---|---|---|
| Entry point | bot.py | 120 | it wires handlers and starts two loops; routing tables and anything that *does* work move to `handlers/` |
| Config | config.py | 160 | env parsing only. A value that needs logic to derive belongs to the module that consumes it |
| Handler | handlers/*.py | 200 | split by surface, not by size — `web.py` owns screen/input/system routes, `web_extra.py` the rest. A handler that grew a helper nobody else calls is fine; one that grew a second *feature* is not |
| Util | utils/*.py | 150 | one concept per file. `window.py` finds windows, `winfocus.py` activates them, `vscode.py` drives the palette — the split is why the terminal-focus fix landed in one place |
| Tests | tests/*.py | 1500 | split by feature, as `test_refine.py` was split out of `test_web.py`. Tests are allowed to be long; they are not allowed to be unnavigable |
| Web page | web/*.html | 2400 | shared code goes to `web/common.js`. **Anything that calls a system endpoint stays in `index.html`** — that boundary is the refine view's isolation and a test enforces it |

These numbers were **raised** from the v0.1.0 caps (handler 150, utils 100, entry 100,
config 50), which had been untrue for months — see `D-015` for why a cap nobody believes is
worse than a cap that is merely generous.

## Known breaches, on the record

`handlers/web.py` (605) and `handlers/web_extra.py` (404) are over the 200-line handler
budget and have been for several versions. That is a real smell with a known remedy — the
route groups inside them are already separable — and it is [row 5](../../docs/ROADMAP.md)
on the board rather than a silent exception. The hook will say so on every edit, which is
the point: a cap you have quietly stopped believing in is worse than no cap.

## Structure rules the caps exist to protect

**Each handler owns one surface.** Telegram command handlers do not import web handlers, and
neither reaches into the other's helpers. Shared behaviour moves to `utils/`.

**Anything that touches the keyboard goes through `handlers/input.py`.** `type_and_enter()`
is the single sequencer for paste-then-Enter; the scheduler, the panel presets, the voice
path and `/api/type` all call it rather than reimplementing the delay. A second copy of that
sequence is a bug that will only appear on one surface.

**Auth is a decorator on every handler, no exceptions** — `utils/auth.py` for Telegram,
`_check_auth`/`_check_auth_refine` for the web. A route added without one is the whole
security model gone, which is why a test counts them.
