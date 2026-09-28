# 2026-09-29 — typing from web — click re-targets keyboard, null click

## What was done

Reported: "typing in some case does not work from web". The log, not the code, picked the
cases. Rows 23 and 24 fixed; row 25 opened and parked.

| File | Change |
|---|---|
| `web/index.html` `doClick` | a click the PC confirmed clears `_kbExpect` — Keyboard mode re-targets instead of refusing (`D-031`) |
| `web/index.html` `_mapToScreen` | returns null unless both coordinates are finite |
| `handlers/web.py` `api_click` | missing / null `x`/`y` → **400** `x and y must be numbers`, was a 500 |
| `tests/test_input.py` | two tests, tests 120 → 122 |

## How it works

**The Mac session, 2026-09-28 17:21–17:35, rebuilt from `bot.log`.** Keyboard mode typed into
`Жан`; three clicks later `Вера` was in front; the next batch was refused and the mode switched
itself off. That is `D-026` doing what it was written to do against a window the operator chose
on purpose — `D-031`. (A "Macintosh" user agent may be the iPad, see `environment.md`.)

**The null click.** `JSON.stringify(NaN)` is `null`. `_mapToScreen` divided through the frame's
ratio; with a zero divisor — the viewer's `naturalWidth` before its frame decodes, a zero-size
box — it produced NaN, and every bounds check upstream passes NaN because NaN compares false to
everything. The server's `int(None)` raised `TypeError`, which the route caught as a 500.

**Four `/api/type` sends of the same text, 17:33–17:35, into `Preview ROADMAP.md - GenTree`,
all 200.** Not fixed, because nothing was broken on this side: the text was pasted. GenTree's
Claude Code was mid-turn (tool calls every few seconds from 17:34), so the sends most likely
queued behind that turn and looked like nothing happened. Reading that transcript's content
to confirm it was blocked by the permission classifier and was not pursued.

**Ruled out by experiment:** a Markdown preview (webview) holding focus does *not* break the
palette hop. Reproduced live in a scratch window: plain editor → `REPRO_OK`, preview focused →
`PREVIEW_OK`, both typed into the terminal and ran.

## Decisions (and why)

- `D-031` — a confirmed click re-targets Keyboard mode; an unasked foreground change is still refused.

## Verification

```bash
python -m pytest tests/ -q                                  # 122 passed
python tools/wiki/check-links.py && python tools/wiki/wiki-doctor.py
```

Four mutations, all red: `_mapToScreen` passing non-finite through; the `_kbExpect` reset
removed; the `expect` guard removed; the route catching only `KeyError`. Not confirmed on a
device yet — the bot needs a restart and the client a reload.

## Next

- **`utils/vscode.py:80` says "terminal focused" without checking anything.** It is logged and
  returned after the palette sequence merely *ran*. Every retried `/api/type` burst in the log
  carries it. An instrument (UI Automation's focused element, or the terminal title) would turn
  it into a measurement.
- **Typing into a Claude Code that is showing a select menu** (`AskUserQuestion`): the paste
  does nothing and the Enter that follows **picks the highlighted option**. Seen on GenTree
  2026-09-28. Not yet a row — needs a way to detect the menu, or a decision that `/api/type`
  never sends Enter blind.
- Row 25 — the answer field's Enter guarded by `!e.isComposing`; on Android the last word is
  often still composing. Parked until it fails on the phone; the operator reported it working.
