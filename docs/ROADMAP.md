# Roadmap

**The board.** What we are doing, in what order, and where it stands. What to build lives in
the feature's chunk; why lives in [DECISIONS.md](DECISIONS.md); what happened lives in
[sessions/](sessions/README.md). This file carries none of those — it points at them.

**A row is one line.** The Task cell is a name, ≤ 90 characters, no second sentence.

---

## Status

**Now / Next / Later is the *order*. Status is the *state*.** They are orthogonal.

| | Status | Means | Set it when |
|---|---|---|---|
| ▶ | **Play** | in flight — somebody is on this row, this session | **before the first edit** — [step 0 of the regulation](README.md#update-regulation-mandatory). A second `▶` only when each names its lane: `▶ lane A` |
| ⏸ | **Pause** | started, then stopped, work left on the floor | you stop before Done — and the row says **what remains and where it is** |
| ✅ | **Done** | finished *and* verifiable | tests pass, the chunk is written — and the row moves to [Done](#done) **in the same edit** |
| ☐ | *(blank)* | not started | — |

`⊘ dropped` is not a status. A dropped row moves to
[Explicitly not doing](#explicitly-not-doing) **with its revisit trigger**.

---

## Now

| # | State | Task | Size | Blocked by |
|---|---|---|---|---|
| 3 | ☐ | `bot.log` rotation and per-library log levels | ~0.5 d | — |

**Row 3, why it is Now:** `bot.log` reached 2.7GB at v0.17.0 and 2.9GB at v0.19.1 and has
been listed as "known, untouched" in two consecutive changelogs. `httpcore` and
`telegram.ext` log every poll at DEBUG. It is the oldest unaddressed item in the project.

## Next

| # | State | Task | Size | Blocked by |
|---|---|---|---|---|
| 4 | ☐ | Decide what to do about the already-public tunnel topology | ~1 h | the operator — `B-1` |
| 5 | ☐ | Split `handlers/web.py` (605) and `web_extra.py` (404) by concept | ~1 d | — |
| 14 | ☐ | Extract the lightbox viewer from `index.html` (2675 > 2400 cap) | ~0.5 d | — |
| 9 | ☐ | The stale-client escape hatch is welded shut — and unreportable | ~1 h | — |
| 12 | ☐ | Re-measure the phone's real throughput — experiment E1, decides row 13 | ~1 h | needs the phone |

**Row 14, left by row 11:** `web/index.html` reached 2675 lines against a 2400 budget — the
gesture machine, then row 15's regrouping. The remedy is not `common.js` (shared with `/refine`) but a
page-specific viewer file — see [.claude/rules/file-limits.md](../.claude/rules/file-limits.md).
Deliberately not done in the same session: the viewer's pointer code has a bug history and had
just been extended.

**Row 9, found while doing row 8, not fixed there:** two defects that make a stale Mini App
unrecoverable *and* undiagnosable. `_checkStaleClient` reloads with `?v=<version>` — the same
URL every time — so once the webview caches that entry no reload can get past it and "clear
the app cache" is the only way out; append a timestamp. And the one message that would say so
(`— reload failed, clear the app cache`) is written to `[data-status]`, which sits off-screen
on mobile and is overwritten by the next capture within one 3s tick, while `#status-bar`
prints the **server's** version — the single number that is identical however stale the client
is. Not on the critical path today only because the phone was proven current.

## Later

| # | State | Task | Size | Blocked by |
|---|---|---|---|---|
| 6 | ☐ | Root-cause the process-creation hang instead of routing around it | ~0.5 d | needs the machine — `B-2` |
| 7 | ☐ | Confirm or kill `A-002` — is the phone's throughput drop really external? | ~2 h | — |
| 13 | ☐ | Tile-diff frame transport — 51 KB → 5 KB measured, but the client becomes a canvas | ~2 d | row 12 |

---

## Done

**Done rows leave the working tables immediately.** Newest first.

| Landed | # | What | Record |
|---|---|---|---|
| 2026-09-08 | 15 | **Mobile: four controls stay out, the rest folds behind one caret** — `D-021`, `D-022` | [chunk](sessions/05-mobile-control-grouping/2026-09-07-mobile-control-grouping.md) |
| 2026-09-08 | 11 | **Right click by tap or hold, drag, and the blanket `PAUSE` removed** — `D-017`–`D-020` | [chunk](sessions/04-route-a-right-click-drag/2026-09-07-route-a-right-click-drag.md) |
| 2026-09-08 | 10 | **Interactive control ("VNC mode") — researched, not built** | [pack](analysis/vnc-mode-research.md) · [chunk](sessions/03-vnc-mode-research/2026-09-07-vnc-mode-research.md) |
| 2026-09-03 | 2 | **v0.21.0 shipped** — attachments, keyboard layout, terminal-by-process | [changelog](changelog.md) · commit `85e4f9e` |
| 2026-09-02 | 8 | **Mobile: arrows visible, bars compacted, bottom bar folds** — `D-016` | [chunk](sessions/02-mobile-compaction-visible-scroll-arrows-foldable/2026-09-02-mobile-compaction-visible-scroll-arrows-foldable.md) |
| 2026-09-02 | 1 | **The wiki exists, and `docs/` is in git** | [chunk](sessions/01-bootstrap/2026-09-02-wiki-bootstrap.md) |

Everything before 2026-09-02 predates this board. The released record is
[changelog.md](changelog.md) — 20 minor versions, v0.1.0 to v0.20.0.

---

## Explicitly not doing

A closed decision, never a silent backlog. **The revisit column is mandatory.**

| Not doing | Decided, on record | Revisit if |
|---|---|---|
| A Type button in `/refine` | `D-010` — text leaves that view through the clipboard only; the absence is enforced server-side, not by markup | never, while `/refine` is the view you can hand to someone else |
| Rewriting `twin.ps1`'s exemplar retrieval into the Improve prompt | v0.18.0 — its retrieval is decision-oriented and a pwsh subprocess per request is waste; the two profile files carry the style signal | the profile files stop being enough to match the operator's voice |
| Clipboard image paste into Claude Code | v0.16.0 — the target is a terminal and cannot take a pasted image; `utils/clipimg.py` is kept but unused, and a path is typed instead | Claude Code learns to accept an image from a terminal paste |
| A VNC/RFB client, or DXGI Desktop Duplication, for the live view | row 10's research — no maintained Python package exposes `GetFrameDirtyRects`, a local VNC server is a second process, port and auth surface, and the diff it would buy costs 15 ms in numpy | the refresh target drops below ~200 ms, where a 34 ms grab plus a 15 ms diff stops being free |
| A live remote-control view in the Telegram **chat** (not the Mini App) | row 10's research — no Telegram update type carries the coordinates of a tap on a photo, so a chat screenshot can never be a control surface | Telegram ships an update that reports a position on media |
| Pinning one humanize model | `D-013` — pinning is what broke when Groq retired the Llama family mid-day | the fallback chain itself becomes the source of confusion |

---

## Open decisions

Questions that block work and are **not yours to answer**.

| # | Question | Blocks | Owner | Detail |
|---|---|---|---|---|
| 4 | The repo is public and already names the tunnel host, both VPS addresses and the port. Private, rotate, or accept? | row 4 | operator | `B-1` |
| 6 | Is the process-creation hang worth an afternoon with Process Monitor, or do the workarounds stand? | row 6 | operator | `B-2` |

---

## Row ids

**Permanent, never reused, next free integer.** Sessions, commits and code comments cite work
as "row 7", so an id must never mean two things.

```bash
grep -n '^| 7 |' docs/ROADMAP.md   # expect exactly one line, or none
```

`wiki-doctor.py` checks this for every row.
