# Sessions

**What actually happened, dated.** One folder per episode of work, numbered in order; one
dated chunk per feature or iteration inside it.

This is the raw-material layer. The synthesis documents are compiled *from* these, and when
the two disagree: **the chunk wins about what happened, the synthesis wins about how things
are now.** That rule is what lets a chunk stay written as it was, forever.

A session folder never carries anything forward-looking. What to build next lives in
[../ROADMAP.md](../ROADMAP.md); why lives in [../DECISIONS.md](../DECISIONS.md).

## Opening a session

```bash
python tools/wiki/new-session.py "what this episode is about"
```

It claims the next free number under a lock — with two agents in one checkout the id space
races, and a session number that means two things breaks every citation to it — then writes
the folder, its README, a dated chunk from the template, and both index rows.

## What a chunk must contain

Three required headings, checked by `wiki-doctor.py`:

| Heading | Job |
|---|---|
| `## What was done` | the change, in the domain's words |
| `## Verification` | what you ran and what it said. For a planning session this is *not* empty — it is: every cited path exists, every id resolves, the checkers are clean |
| `## Next` | what you would do first if you sat down again tomorrow. This is the heading the next session actually reads |

Two more are expected and warned about when missing: `## How it works` (the mechanism, so
the reader does not have to re-derive it) and `## Decisions (and why)` (with the `D-` ids,
cited not restated).

## Archiving

When this folder passes ~50 sessions, fold the closed ones into `ARCHIVE-YYYY.md` — one
line each, pointing at the folder, which stays on disk. The index is what gets long, not
the history. Write the rule down now, while it costs nothing.

---

## The sessions

Newest first.

| # | Session | Dates | What came out of it |
|---|---|---|---|
| 02 | [02 · mobile compaction, visible scroll arrows, foldable bar](02-mobile-compaction-visible-scroll-arrows-foldable/README.md) | 2026-09-02 | mobile compaction, visible scroll arrows, foldable bar |
| 01 | [bootstrap](01-bootstrap/README.md) | 2026-09-02 | this wiki, `docs/` in git, and 14 decisions recovered from 20 versions of changelog |

**Before session 01** there were no session folders. The record of everything from v0.1.0
(2026-02-16) to v0.20.0 (2026-08-25) is [../changelog.md](../changelog.md) and the feature
files in [../chunks/features/](../chunks/features/) — written per feature rather than per
episode, which is why they are deep on behaviour and silent on what a given day was like.
