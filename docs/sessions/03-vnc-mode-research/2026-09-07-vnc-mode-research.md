# 2026-09-07 — vnc mode research

## What was done

Row 10. A research iteration for an "interactive VNC mode" — remote screen with real mouse
and keyboard from the phone. **No code was written and no remote input was fired**, because a
test click would have landed on the operator's live desktop.

The output is one document: [analysis/vnc-mode-research.md](../../analysis/vnc-mode-research.md).

| File | What it now holds |
|---|---|
| `docs/analysis/vnc-mode-research.md` | the pack: what already ships, what is measurably missing, four routes, a named stack, six open experiments |
| `docs/ROADMAP.md` | row 10 (this), and what it produced |
| `docs/environment.md` | three machine facts found while measuring |

## How it works

**The finding that reframed the brief.** The request read as "build screen streaming, click
mapping, key passthrough, special keys, 2-second refresh". All five already ship in the Mini
App. What is actually missing is four verbs — **right click, drag, a keystroke path that
skips the clipboard, and partial-frame transfer** — plus one latency tax nobody had noticed.

**Everything is measured on this machine, today, with the command recorded.** The three
numbers that decide the routes:

1. **0 of 5 consecutive whole frames were byte-identical** on a live desktop, so the
   `X-Hash` → `204 Not Modified` dedup in `/api/frame` never fires in practice — a blinking
   caret invalidates the frame. Yet only **2.3 %** of 64-px tiles change per 2-second step.
   A packed strip of the changed tiles is **4.9 KB against a 50.5 KB full frame**. The union
   bounding box is a trap and costs 31 KB for the same 2.3 %.
2. **`pyautogui.PAUSE` is 0.1 s and nothing in this repo overrides it** —
   `moveRel(0,0)` measured at 100.5 ms versus 0.1 ms with `PAUSE = 0`. Every remote click
   therefore sleeps ~200 ms, `scroll_at` ~300 ms, on top of a **~133 ms warm tunnel round
   trip**. This is the cheapest available latency win and it is one line.
3. **The tunnel is not the bottleneck people assume**: 133 ms warm for a control call,
   ~345 ms for a 51 KB frame. `A-002`'s 20–40 KB/s phone is the constraint, and at that rate
   a full frame does not fit in 2 seconds while a tile strip does — which is what makes the
   diff transport a feasibility question rather than a polish one.

**Three external passes ran in parallel** and two of them changed a decision:

- The Telegram chat surface **can never report where a photo was tapped** — no update type
  carries coordinates. The brief's "double click on the image in Telegram" is not a design
  choice; on the chat surface it is impossible, and on the Mini App it is already solved.
- `SendInput` with `KEYEVENTF_UNICODE` carries the character itself through `VK_PACKET` and
  never consults the keyboard layout — the mechanism that makes the v0.21.0 layout bug class
  impossible by construction. **With the caveat that shapes the design:** a synthetic Ctrl
  does not combine with it, so character injection and hotkey injection must stay two paths.
- No maintained Python package exposes DXGI's `GetFrameDirtyRects`. That, plus the 15 ms
  numpy diff measured here, closes the "use a real VNC / Desktop Duplication" route.

**The operator's ruling, mid-session:** right click is a **two-finger tap**, not a double
click. That is also the industry gesture (Moonlight, Microsoft's RD client in pointer mode)
and the double tap was already spent twice — on the remote double click and on the viewer's
fit↔3× zoom. The obstacle is specific and written down: the lightbox sets `_lb.multi` on the
second pointer and `pointerup` returns early, so a two-finger tap is *deliberately* swallowed
to stop a pinch tail reading as a tap. The flag has to be split in two, and the 2-pointer
move branch needs the same 3-px threshold the 1-pointer branch already has.

## Decisions (and why)

None. This session wrote no `D-`/`A-`/`B-` entries on purpose — nothing was chosen, and a
decision entry for work that has not been built is a claim the code cannot back. The routes
are ranked in the pack; the choice between them is the operator's, and `Route D` is proposed
for the roadmap's **Explicitly not doing** table with its revisit trigger.

The existing ids the pack leans on: `D-005` (Enter after paste), `D-006`/`D-007` (the paste
key and terminal-ness), `D-010` (auth on every `/api/*`), `D-011` (chain, never
`setInterval`), `D-016` (contrast over a screenshot), `A-002` (the phone's throughput).

## Verification

The suite, before and after — nothing in `*.py` or `web/` was touched, so this is a baseline,
not a proof of a change:

```
python -m pytest tests/ -q
94 passed in 3.94s
```

Both checkers clean (`wiki-doctor.py --fix` regenerated the counts block after row 10 was
added):

```
python tools/wiki/check-links.py   ->  164 links in 51 markdown files: 0 broken
python tools/wiki/wiki-doctor.py   ->  10 checks · 0 failures · 0 warnings
```

Every measurement in the pack carries the command that produced it, in its appendix, so the
next session re-derives the baseline in its own run rather than trusting today's afternoon.

## Next

**Route A, and only Route A** — `docs/analysis/vnc-mode-research.md` §5. Right click by
two-finger tap, drag, `button` on `/api/click`, `PAUSE = 0` with deliberate sleeps. It is the
smallest change with the largest effect and it needs no new dependency.

Three things to do before the first line of it:

1. Call `disableVerticalSwipes()` — Telegram's swipe-down-to-close will eat a vertical drag
   otherwise, and that reads as "the app closes at random".
2. Run **E1** from §6: re-measure the phone's real throughput. `A-002` is an assumption two
   versions old, and it decides whether Route B is feasibility or polish.
3. Read §2.1 before touching `web/index.html:1430–1500`. That code has a bug history — a
   pinch that closed the viewer, a tap that panned — and every rule in it was written after
   something broke.
