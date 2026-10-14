# 2026-09-08 — The hold never fired once, and the log said so

## What was done

Row 16. v0.22.0 shipped a right click on press-and-hold. The operator tested it and reported
it did not work. **It had never worked** — not once, on any device.

| File | What changed |
|---|---|
| `web/index.html` | the live view sends the right click **from the hold timer**, with pointer capture, `touch-action:none` while armed, and a hold slop of its own |
| `tests/test_input.py` | `test_a_hold_is_not_cancelled_by_a_resting_finger` — eight mutations behind it |

## How it works

**The log settled it before any guessing.** One session: 566 frames, 31 clicks — **every one
`left`** — two drags, one `/api/type`, and zero 4xx/5xx. Not a single `button: right` request
in the server's history. So the failure was entirely client-side and before the request: the
gesture was being cancelled, not mis-sent.

Three causes, all the same shape — *the hold was cancelled before it could be recognised*:

1. **It was cancelled by the tap threshold.** `TAP_MOVE_PX` is 8px from the landing point on
   the live view, and the viewer armed against the 3px *pan* threshold. A finger resting on
   glass for 350ms clears both every time. A hold now has `HOLD_SLOP_PX` (14px), measured
   from where the finger landed rather than per move event — accumulated drift is what should
   count, and one jumpy sample should not.
2. **The webview claims the gesture.** With the default `touch-action` a resting finger on
   the live image is a candidate page scroll, and the browser answers with `pointercancel` —
   no error, no `pointerup`, nothing logged anywhere. While Click is armed that image is a
   control surface and now gets `touch-action: none`, which the viewer always had.
3. **Completion depended on `pointerup` arriving at the same element.** Without pointer
   capture, a finger that drifts off the image releases somewhere else.

The deeper fix is to stop needing the release: **the live view sends the right click from the
timer** (`D-023`), anchored where the finger landed, with the haptic arriving while the finger
is still down — what every OS long press does. The release only swallows the synthetic click.
The viewer keeps arm-then-decide, because a drag lives there and its target is where the
finger *ends up*.

## Decisions (and why)

- `D-023` — the hold fires at 350ms on the live view; supersedes the release-decides half of
  `D-020` **for that surface only**, and says why the viewer keeps the old shape.

## Verification

```
python -m pytest tests/ -q
103 passed
```

Eight mutations, all red: the slop back at the tap threshold, the timer gated on the tap flag,
the `touch-action` guard dropped, pointer capture dropped, the hold sending nothing until
release, the following click left unsuppressed, and the viewer's two regressions.

Two of the assertions had to be tightened after mutations **survived** them — an earlier form
checked that `g.slid` appeared *somewhere* in the handler, which a version reading the wrong
flag still satisfied. And once more a rule fired on its own explanation: the code names the
flag it deliberately does not use, so the scan strips comments first.

**Still not confirmed on hardware.** Every earlier claim about this gesture was also green in
the suite. What will settle it is one line in `bot.log` — `bot.mouse: click: right at (x, y)`
— and it has never appeared.

## Next

Two things are open and neither is a bug:

- **Direct typing** — the operator's actual ask: a mode where the phone's keyboard types
  through to the PC live, no `type…` field, no Enter. That is **Route C** in
  [analysis/vnc-mode-research.md](../../analysis/vnc-mode-research.md) and it is not built.
  It needs `SendInput` + `KEYEVENTF_UNICODE` (layout-proof by construction), a hidden focused
  input on the client with ~120ms batching, and experiment **E2** first — whether Claude Code
  in Windows Terminal accepts a synthesized `WM_CHAR` at speed. E2 fires keystrokes into the
  live desktop, so it waits for the operator to be at the machine.
- Row 14: `web/index.html` is over its cap and the viewer is the file to extract.
