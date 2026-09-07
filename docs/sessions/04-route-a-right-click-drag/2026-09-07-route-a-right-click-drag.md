# 2026-09-07 — Route A: right click, drag, and the end of the blanket PAUSE

## What was done

Row 11 — the first of the routes from
[analysis/vnc-mode-research.md](../../analysis/vnc-mode-research.md), chosen by the operator
straight after the research landed. Four verbs the phone was missing, no new dependency, no
new transport.

| File | What it now does |
|---|---|
| `utils/mouse.py` | **owns every mouse event** — `click_at` (button + double), `drag`, `scroll_at`, `double_click_time()` |
| `handlers/web.py` | `/api/click` takes `button`; **new `POST /api/drag`** |
| `handlers/input.py` | `pyautogui.PAUSE = 0`; `/click` takes an optional button |
| `handlers/panel.py` | its one click goes through the module like everything else |
| `config.py` | six `MOUSE_*` gaps that replace what PAUSE was hiding |
| `web/index.html` | two-finger tap → right click, press-hold → drag, on both the live view and the viewer |
| `tests/test_input.py` | **new file** — six tests, split out when `test_web.py` passed its cap |

## How it works

**Right click is a two-finger tap** (`D-017`). Not the double tap the brief first asked for —
that is spent twice already, on the remote double click and on the viewer's fit↔3× zoom — and
not a long press, which is the gesture users of every other client report as "the PC thinks
the left button is held down", and which is now the *drag* gesture here, where a held button
is what is actually meant.

The interesting part is why it did not already work. The viewer **suppressed it twice**:
`_lb.multi` is set on the second `pointerdown` and `pointerup` returned early on it, so a
pinch tail could not close the viewer; and the two-pointer branch of `pointermove` set
`moved = true` on the first pixel, which two fingers landing together always produce. Both
guards were correct and both had to be made narrower rather than removed — `multi` still
stops the pinch tail, `peak` now counts fingers, and movement needs the pinch **span** to
change by more than `TAP_MOVE_PX`. The tap is anchored at the midpoint of where the fingers
*landed*, kept in a separate `_lb.down` map, because `ptrs` is rewritten on every move and by
release time two fingers have drifted.

On the un-zoomed live view the same gesture needed a pointer machine of its own — `onclick`
cannot see how many fingers were involved — plus a 400ms suppression flag, because the
browser still synthesises a click from the first finger and a right click would otherwise
send a left one too.

**Drag is press-and-hold, then move** — Moonlight's gesture. An immediate finger drag stays
the pan that reaches the rest of a zoomed screenshot, which cannot be given up. Once armed
(haptic + `Drag armed` in the status line) the **view stops panning**: moving the picture
under the gesture would drop the drag where the operator never pointed. A gesture the OS
steals (`pointercancel`) disarms it, or the next release drags from a point nobody remembers.

**On the wire a drag is one request** (`D-018`): `{x, y, to_x, to_y, button}`. A button held
*between* HTTP requests is a button this tunnel can strand — lose the `up` and the desktop is
left with the mouse down, where every movement is a selection, and the phone cannot tell.
`utils.mouse.drag` releases in a `finally`, interpolates the move in 12 steps (a single jump
drags nothing — controls recognise a drag from the `WM_MOUSEMOVE` stream) and holds
`MOUSE_DRAG_HOLD` after the press, because an app that sees press and move in one tick calls
it a click.

**`pyautogui.PAUSE` is off** (`D-019`), and this is the change with the widest blast radius.
It sleeps 0.1s after every call it owns — 100.5ms measured here against 0.1ms with it off —
so a click was ~200ms of sleep and `scroll_at` ~300ms before any event was sent, on top of a
~133ms warm tunnel round trip. Turning it off exposed what it had been paying for, and one of
those was a live regression the same moment: **Windows routes the wheel by the cursor
position at the instant of injection**, so `scroll_at` would have stamped the wheel with a
position the cursor had not reached. That gap is now explicit, as is the settle between a
move and a button. The keyboard paths needed nothing — `press_keys` has always sent its
virtual-key events back-to-back.

Because a caller reaching for `pyautogui.click` skips all of it, every mouse event now goes
through `utils/mouse.py`, enforced the way `D-005` and `D-008` are enforced.

## Decisions (and why)

- `D-017` — right click is a two-finger tap; what the double tap and the long press are
  already spent on, and the two guards that were suppressing the gesture.
- `D-018` — a drag is one request, released in a `finally`; why the protocol-shaped
  `{down|up|move}` API is wrong for this transport.
- `D-019` — PAUSE is off and every gap it hid is named; the wheel-position regression it
  uncovered.

## Verification

```
python -m pytest tests/ -q
100 passed in 4.23s          (94 before this session)
```

The six new tests were **mutation-tested, not trusted**: eleven deliberate reverts — the
`finally` removed, PAUSE put back, the panel calling pyautogui directly, the wheel settle
deleted, the double-click clamp dropped, the 400 turned back into a 500, the pinch branch
marking movement immediately, the click suppression removed, panning restored under an armed
drag, the cancel disarm deleted, and the drag arming taken out of its timer. **All eleven
went red.** The last one was caught only after the assertion was strengthened: the first
version checked that the string `dragTimer` appeared nearby, which a version that armed on
touch still satisfied.

Caps (`.claude/rules/file-limits.md`): `test_web.py` passed 1500 and was split by feature
into `tests/test_input.py`, as `test_refine.py` once was. `config.py` and `utils/mouse.py`
were trimmed back under theirs. `web/index.html` is at 2557 against a 2400 budget and is
recorded as a known breach with its remedy — row 14.

Both checkers clean.

## Next

Row 14 first if anything: `web/index.html` is over its cap and the remedy is real — the
lightbox viewer is a separable file. Doing it in the same session as the gesture work would
have meant refactoring code with a bug history immediately after adding to it.

Then row 12 (**E1** — re-measure the phone's throughput), which is what decides whether
row 13's tile-diff transport is feasibility or polish.

**Not verified on hardware.** Every claim here is from the suite and from reading. A
two-finger tap on a real phone, through the real tunnel, into a real context menu has not
happened yet — and the gestures are the half of this that a test can only describe. Do that
before the next version goes out.
