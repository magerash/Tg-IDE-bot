# 2026-09-02 — the wiki, from the code rather than from memory

The first chunk. It is written about the bootstrap itself, because a session that produced
documents and decisions is a session, and starting the log with an empty folder teaches the
next person that paperwork sessions do not count.

The project was not undocumented — it was documented *invisibly*. 31 files and 160KB of
feature chunks lived in `materials/`, which was in `.gitignore`, next to a 527-line
`CLAUDE.md` that was also gitignored and carried 20 versions of changelog. None of it was in
a clone. This session moved that body of work into `docs/`, put it in git, and wrote the
synthesis layer the kit expects on top of it.

## What was done

| Document | What went into it |
|---|---|
| [../../README.md](../../README.md) | the preflight (four checks plus one specific to this project: read the feature's chunk first), the update regulation, the document map, a concept index phrased as the questions people actually arrive with, the session table |
| [../../code-map.md](../../code-map.md) | 44 paths, each verified with `test -e`, plus two deep slices — *text from a phone to a terminal prompt* and *a frame from the PC to the phone* |
| [../../DECISIONS.md](../../DECISIONS.md) | **14 decisions, 3 assumptions, 2 blockers** — `D-002`–`D-014` recovered from the changelog, the code and its comments, dated by the version that shipped them |
| [../../ROADMAP.md](../../ROADMAP.md) | 7 rows — 2 in Now, 2 in Next, 2 in Later, 1 Done — plus four entries in *Explicitly not doing*, each with its revisit trigger |
| [../../environment.md](../../environment.md) | the run commands, the machine facts including four deliberate **absences**, and **12 failure modes** that had already cost somebody time |
| [../../changelog.md](../../changelog.md) | 20 versions lifted out of `CLAUDE.md`, which drops from 527 lines to a pointer |

Structural changes alongside the writing:

- `materials/` → `docs/`, and out of `.gitignore` (`D-001`). Path references rewritten in 8
  files.
- `AGENTS.md` is now the tracked rules file; `CLAUDE.md` imports it with `@AGENTS.md` and
  stays gitignored, which it already was.
- Three local agents were retired to `.wiki-adopt/retired/` — the kit's `wiki-researcher`,
  `wiki-verifier` and `wiki-planner` do their jobs. Nothing was deleted.
- `.claude/rules/file-limits.md` written with this project's real caps, and
  `tools/wiki/hook_caps.py` copied in — the scaffold wired the hook at `core` tier without
  shipping the script, so the hook was pointing at a file that did not exist.

## How it works

The context window is RAM and `docs/` is disk. Each session leaves a dated chunk; the
standing documents are the compiled summary of all of them. Facts are addressable — `D-001`,
`A-001`, `B-1` — and cited by id rather than restated, so no fact exists in two places to
disagree with itself.

This project keeps **two documentation layers**, and the distinction is worth stating because
it is not the kit's default. `docs/chunks/features/` predates the wiki and stays canonical
for *how one feature behaves*; the new synthesis documents own *how the project stands*. The
rule when they disagree is the same as for sessions: the chunk wins about behaviour, the
synthesis wins about state.

Nothing here depends on a particular tool: it is markdown in git, and `grep` is the index.

## Decisions (and why)

- `D-001` — the wiki moved to `docs/` **and into git**, minus the VPS topology file, which
  stays ignored because this repository is public.
- `D-002`–`D-014` were not made this session; they were **recovered**. The most valuable
  outcome of the bootstrap is that the reasoning behind the typing path — six hand-offs,
  five separate failures, each fixed in a different version — is now readable in one place
  instead of being distributed across changelog entries nobody greps.
- `B-1` is the finding this session did not expect: the tunnel hostname, both VPS addresses
  and the port are **already public** in tracked files and in a commit message, and have
  been since 2026-07-21. Withholding one file limits the detail; it does not un-publish the
  host. That is now [row 4](../../ROADMAP.md), owned by the operator.

## Verification

A documentation-only change: no source file was touched, so the code is exactly as it was.

```bash
python -m pytest tests/ -q          # 94 passed in 3.81s — before and after
python tools/wiki/check-links.py    # 0 broken
python tools/wiki/wiki-doctor.py    # clean
```

Every path in the code map exists; every id cited resolves; the session table names this
chunk. The 94 figure is the state the wiki was written against, and it includes the
uncommitted v0.21.0 work sitting in the tree — which is itself the point of preflight check
1: the working tree is ahead of the wiki, and now it is written down.

## Next

**Row 2** — ship v0.21.0. The code is green and the chunk is written; it needs the operator's
"Let's finish" to take the version bump, the changelog entry and the commit. Nothing else in
the tree is blocking it.

Then **row 3**, `bot.log` rotation. It is 3.0GB, it has been listed as "known, untouched" in
two consecutive changelogs, and it is now the oldest unaddressed item on the board. Adding
`logging.handlers.RotatingFileHandler` and setting `httpcore`/`telegram.ext` to WARNING is
under an hour of work, which is the argument for doing it before it becomes four.

Do **not** start row 5 (splitting the web handlers) in the same session as row 2 — `web.py`
is where the v0.21.0 routes live, and a split on top of an uncommitted feature makes both
unreviewable.
