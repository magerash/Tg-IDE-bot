# 2026-09-08 — Architecture study: the answer is the architecture we have

## What was done

Row 18. A structured architecture study for interactive remote control, grounded in this
repository rather than in the technology landscape: three variants compared, a feasibility
matrix, a latency budget, a session model, a threat model, a changes-required table and a
phased MVP. **No production code was written.**

Output: [analysis/remote-control-architecture.md](../../analysis/remote-control-architecture.md)
(694 lines). It **supersedes** [vnc-mode-research.md](../../analysis/vnc-mode-research.md)
(row 10) as the answer to *what to build*; that file keeps a banner saying so and stays as the
record of what was **measured**, because its numbers are cited here rather than re-derived.

The board was rewired so the two do not compete: row 10 is marked superseded in Done, and rows
**12**, **13** and **17** are restated as *inputs* to row 18 rather than independent plans.

## How it works

**The conclusion is a negative one, and that is the value.** The recommended architecture is
the one already running; the study's job was to make the argument for not changing it strong
enough to stop the next person reaching for VNC because the word appeared in the brief.

- **Pure Bot is removed by a fact, not a preference** — no Telegram update type carries the
  coordinates of a tap on a photo. Tens of button zones for two million pixels.
- **Variant C is more moving parts, counted: 5 today, 9 with noVNC, 11–12 with Guacamole** —
  and *neither removes any of the five*, because git, shell, scheduler and upload have no VNC
  equivalent. `guacd` has no supported native-Windows build at all, so Guacamole means Docker
  Desktop or WSL2 under Tomcat and a JVM. RFB's incremental updates and CopyRect solve a
  bandwidth problem that exists at 20–60 fps and not at 0.5–2.
- **The architectural fact under all of it:** the bot runs *on the machine it controls*. There
  is no protocol between controller and desktop, only Win32 in-process. Every remote-desktop
  architecture exists to solve a problem this project does not have.

**Two findings nobody had written down**, both from reading and measuring today:

- **No frame this project has ever sent contained the mouse cursor.** `mss`'s Windows backend
  is one `BitBlt(SRCCOPY | CAPTUREBLT)` and never calls `GetCursorInfo`/`DrawIconEx`. It has
  not hurt because every interaction is absolute, but it removes a relative-cursor mode (the
  most-cited UX finding) and leaves a drag with no feedback about where the grab is.
- **DPI scaling is untested and this machine cannot test it** — logical, physical and
  `pyautogui.size()` all read 2048×1152 here, and the process is `DPI_AWARENESS_UNAWARE`. At
  125 % or 150 % it would be handed virtualised coordinates and the frame would disagree with
  the click. Recorded in [environment.md](../../environment.md).

**And a measurement that changes a default's status:** the same frame at 1280 px is **80.7 KB**
with `BILINEAR` and **114.2 KB** with `LANCZOS` — the downscaler is a ~40 % bandwidth decision,
not a cosmetic one. The code's `BILINEAR` is right for a thin link and should now be a
deliberate choice rather than an inherited one.

**The direct-typing design changed shape because of the external pass.** The naive
`keydown`-and-send cannot work: UI Events *requires* `keyCode: 229` while a soft keyboard is
composing, so on Android that is nearly every letter. `beforeinput` + `inputType` is the
primary signal. Two limits are honest ones that cannot be engineered away — per-keystroke
delivery is impossible *during* composition (only the edges are reliable, so a predicted
Cyrillic word lands when committed), and **iOS autocorrect can rewrite text that has already
been injected, which cannot be un-sent**. The mitigation is to defeat the suggestion layer at
the field (`type="password"`, as xterm.js's own maintainers propose), not to handle the
correction.

Guacamole's phone-keyboard problem — a canvas instead of a real input, so the OS keyboard often
does not appear at all — is independent confirmation of the same design.

## Decisions (and why)

None. Nothing was chosen that the code can back yet, and a `D-` entry for unbuilt work is a
claim with nothing behind it. The study's recommendations become decisions when row 17 lands.

Existing ids it leans on: `D-005`–`D-008` (the typing scars), `D-010` (auth on every handler),
`D-011` (chain, never a fixed interval — and the reason a long-lived WebSocket over the single
tunnel is the wrong load), `D-017`–`D-023` (the gesture work), `A-002` (the phone's throughput).

## Verification

This is a research iteration; the instruments are the ones that apply to documents plus the
measurements taken for §8.

```
python -m pytest tests/ -q                        103 passed
python tools/wiki/check-links.py                  205 links in 60 files, 0 broken
python tools/wiki/wiki-doctor.py                  10 checks · 0 failures · 0 warnings
```

Encode and diff figures at 1280×720 / 1920×1080 / 2560×1440 were measured in one run today and
are in §8 with the resolution they were taken at. The cursor and DPI findings were established
by reading the installed `mss` module and querying the Win32 metrics, not inferred.

**What is cited rather than claimed:** the external passes are labelled Cited / Read /
Observed with URLs, and two gaps are stated rather than filled — TigerVNC's Windows service
behaviour could not be established, and one forum thread could not be fetched (403), so it is
named and not quoted.

## Next

**Experiment E2, and it needs the operator at the machine** — does Claude Code in Windows
Terminal accept a synthesized `WM_CHAR` at typing speed? It fires keystrokes into the live
desktop, which is why it has not been run. E6 (Cyrillic, emoji, composed text) rides with it.

Then row 17 in the order §20 sets out: the unicode injector and its route, then the client
typing mode, then the field UX. Row 13's tile transport stays gated on **E1**, which is one
hour with the phone and is the difference between "feasibility" and "polish".
