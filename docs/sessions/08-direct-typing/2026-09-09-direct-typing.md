# 2026-09-09 — Direct typing: the phone's own keyboard, straight through

## What was done

Row 17, all four phases of the plan in
[analysis/remote-control-architecture.md](../../analysis/remote-control-architecture.md) §20,
plus the experiment the row was gated on. **The phone types into the PC's focused window,
character by character, with no `type…` field and no Enter** — which is what the operator
actually asked for.

- **E2 passed** (§18): a `KEYEVENTF_UNICODE` keystroke reaches `✳ Claude Code` in Windows
  Terminal **byte-exact at 52.0 cps**, Cyrillic and astral emoji included. The criterion was
  ≥10 cps.
- **Server:** `type_unicode()` in `handlers/input.py`, `POST /api/chars` in `handlers/web.py`,
  `same_window_id()` in `utils/window.py`, `TYPE_CHARS_MAX` in `config.py`.
- **Client:** a typing mode in `web/index.html` — a password-field sink, `beforeinput` as the
  primary signal, composition edges only, an ordered queue chained through one request at a
  time, and a `Keyboard: ON/OFF` toggle on both surfaces.
- **Confirmed on hardware**, which is the part `D-023` exists to insist on: 25 characters from
  a Vivo V2419A on Android 16 through the tunnel into VS Code, **zero short deliveries**.

## How it works

**Two input paths that never merge, and now the code says so at both doors.** A
`KEYEVENTF_UNICODE` key carries no virtual-key code, so a synthetic Ctrl has nothing to
combine with — a helper taking "a string, possibly with modifiers" is the bug waiting to be
written. `type_unicode()` refuses every control character by name; Enter and Backspace leave
the client as named keys through `/api/key` and `press_keys`. `D-025`.

**`sizeof(INPUT)` must be 40 on x64.** The union's largest member is `MOUSEINPUT` (32 bytes);
a union declared with `KEYBDINPUT` alone is 32, and Windows then rejects **every** call with
`ERROR_INVALID_PARAMETER` (87) and sends nothing at all. E2 failed exactly this way before it
succeeded, and a test now pins the size. `press_keys` never met this because it uses the
legacy `keybd_event`.

**`expect` guards the target; it does not focus it.** E2 measured a verified focus going stale
— `force_foreground()` returned `True` honestly, and 800 ms later a different window held the
foreground and 62 characters went into an unrelated editor. Focusing per batch would re-run
that race on every batch. So the client states which window it believes it is typing into and
a mismatch **refuses and types nothing**. `D-026`.

**The guard's first version was inert against the only target that matters.** It compared
`tail_key()` values, and `tail_key` returns `''` for a single-segment title — which
`✳ Claude Code` is. Two empty strings compare equal, so it waved everything through. The fix
is `same_window_id()`, the server-side twin of the client's `_sameWinId`: exact match, or a
**non-empty** shared tail. `D-009`.

**The sink is a password field, on purpose.** Chrome-for-Android ignores `autocomplete` and
`spellcheck` on a text field, and iOS autocorrect rewrites words that were already committed —
here those characters are already inside a terminal on the PC and a keystroke cannot be
un-sent. The suggestion layer is defeated at the field rather than handled after the fact,
which is what xterm.js's own maintainers propose. It is also never `display:none`: an
unfocusable field raises no keyboard, and the mode would look simply dead. `D-027`.

**`keydown` cannot carry the character on a phone** and that is normative, not a bug — UI
Events *requires* `keyCode: 229` while a soft keyboard composes, which on Android is nearly
every letter. `beforeinput` + `inputType` is the primary signal; `insertCompositionText` is
skipped and the committed word is taken at `compositionend`.

## Decisions (and why)

`D-025` two paths, enforced at both doors · `D-026` the target is guarded, never re-focused ·
`D-027` the typing surface is a password field · `D-028` the chain is the batcher.

`D-028` is the one that changed shape after measurement — see below.

## Verification

```
python -m pytest tests/ -q                        114 passed  (103 before)
python tools/wiki/check-links.py                  0 broken
python tools/wiki/wiki-doctor.py                  10 checks · 0 failures · 0 warnings
```

**19 mutations, all red.** Every new assertion was broken deliberately rather than trusted —
the refusals removed, the union shrunk to 32, the surrogate pair split across two calls, the
guard disabled, the auth check deleted, `beforeinput` fed composition text, Enter turned into
a character, the pump put on a `setInterval`, the sink made a text field, `display:none` added,
the caps drifted apart. One mutation **survived** and was a bad mutation rather than a gap: it
renamed `api_chars` instead of removing its auth check, which left the check in the body the
test scans. Replaced with one that deletes the check; both tests then went red.

**Live, against the running bot** (restarted through its own `/api/restart`):

| Call | Result |
|---|---|
| unauthenticated | `401` |
| `expect` a window that is not foreground | `refused: foreground`, `sent: 0`, names the real one |
| a control character | `400 control characters refused: U+000A` |
| 600 characters | `400 600 characters exceeds TYPE_CHARS_MAX (512)` |

**Rendered before shipping**, at a true 390 px viewport (an iframe — `--window-size` does not
give one). The control row is two visual lines, `Fit 71 · Click: OFF 71 · Keyboard: OFF 97` in
346 px with no wrap and no horizontal overflow; the viewer's row is 374 px in 390, `nowrap`.
The `⌨` in the viewer is `U+2328 KEYBOARD` and renders as a real glyph — checked, because
v0.22.0 shipped a caret that was a raw control byte and no test saw it. The file has **zero**
raw control bytes.

**The measurement that changed a default.** `TYPE_BATCH_MS` shipped at 70 ms on a sound
argument (chained HTTPS over a tunnel, ~133 ms warm round trip, so a request per character
would load the single pipe `D-011` protects). The first device session says it never fired:

```
unicode requests : 25        chars per request: {1: 25}
short deliveries : 0         gap between requests: min 143ms  median 367ms
                             implied typing rate: 1.6 chars/sec
```

**Every request carried exactly one character**, because the shortest gap between two thumb
keystrokes was 143 ms and nothing ever arrived inside a 70 ms window. The window coalesced
nothing and delayed everything, so it is now **0** — and what actually does the batching is the
chain itself: keystrokes arriving while a request is in flight merge into the next one, which
makes batch size a function of the link. `D-028`.

## After it shipped, the same day

**Backspace did nothing from an iPad, and neither did Tab, the arrows or any Ctrl combo.**
`D-029`. The log settled it first, as with `D-023` and `D-024`: **zero** `backspace` requests in
the server's whole history, so the keystroke never left the client.

Two causes. The sink shipped **empty**, and an empty field with the caret at 0 has nothing to
delete — so the engine reports no deletion at all and the correct `deleteContentBackward`
branch simply never ran. And `beforeinput` has **no `inputType` for a named key**, so Tab, the
arrows, Delete, Home/End and every combo could only ever have arrived as a `keydown` — where
the handler had a Backspace branch that was a comment and nothing else.

The claim in the code that Backspace "reports itself through `deleteContentBackward` on every
keyboard tested" was **written without a keyboard having been tested**. That is the honest
lesson of the day: the suite was green over a dead key because the test checked that the branch
existed, not that anything could reach it.

Tests 114 → **117**, nine more mutations. One survived and exposed a weak assertion of exactly
the kind v0.22.1 hit — `preventDefault` was asserted to appear *somewhere in the handler*, which
a version that dropped it from the branch that matters still satisfied. Re-scoped to the branch.

## Next

- **E6's phone half is still open** — a *predicted* Cyrillic word goes through composition, and
  only the edges are reliable. The desktop half passed with E2; this needs the phone with
  prediction on. It is the last thing between this row and "no caveats".
- **The `é` question is unresolved and now cheap.** `e`+`U+0301` came back as `U+00E9` in both
  E2 runs. The same rewrite in a shell input line and a TUI buffer points at the copy-paste
  path they share rather than at either reader, but that is not proof.
  `tools/experiments/e2_readback.py` settles it by reading the line in-process — it was written
  and never run, because the target window was never focused.
- **Row 19** — a targeted `/api/type` should re-check after the settle and refuse, the same
  rule `/api/chars` was born with.
- **`web/index.html` is now ~3000 lines against a 2400 budget**, which makes row 14 (extract
  the viewer) more overdue than it was.
