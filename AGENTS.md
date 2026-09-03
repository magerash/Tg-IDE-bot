# Tg-IDE-bot

A Telegram bot that runs **on the operator's Windows PC** and hands it to a phone: live
screen, mouse, keyboard, shell, git, builds, file delivery, and a Mini App dashboard served
through a reverse SSH tunnel. The one architectural fact that explains most of the rest —
**the bot has no UI of its own on the PC; it drives whatever window already has focus.**
Every hard bug in this project's history is a variation of *the keystroke arrived somewhere
else than you thought*, so anything that types, focuses or pastes is treated as a contract,
not a convenience. Python 3.14, python-telegram-bot v20 polling + aiohttp on `:8080`,
pyautogui/mss/pygetwindow for the machine, pytest for the proof.

**Canonical knowledge is the wiki in `docs/`. Read [docs/README.md](docs/README.md) before
starting** — it carries the preflight, the update regulation, the document map and the
"concept → where to look" index.

<!--
This file is the single source of the repo's rules, and every agent reads it. CLAUDE.md at
the root imports it with @AGENTS.md, so there is one text and not two copies. CLAUDE.md is
gitignored (operator-local); THIS file is the tracked one. Do not paste these rules
elsewhere — point at this file. Keep it under ~200 lines.
-->

## The rules of this repo

- **Mark the roadmap when you start, not only when you finish.** Set the row you are about
  to work on in [docs/ROADMAP.md](docs/ROADMAP.md) to `▶` **before the first edit**, one row
  at a time; when you stop, set the status that is true — `✅` finished and verifiable, `⏸`
  **with what remains and where it is**, never back to `☐`.
- **Read the feature's chunk before you touch the feature.** `docs/chunks/features/` is
  where the scar tissue is written down. Update or create the chunk after the change —
  this rule predates the wiki and is why the project's history is recoverable at all.
- **After every feature or iteration, follow the "Update regulation" in
  [docs/README.md](docs/README.md)**: a session chunk under `docs/sessions/NN-slug/`,
  synthesis into the documents the change touched, then the index rows and the checkers.
- **If anything about the machine or the procedure changed, update
  [docs/environment.md](docs/environment.md)** — a version, a path, a port, a command, or a
  failure mode you hit that nobody had written down.
- **Cite ids, don't restate.** `D-nnn`, `A-nnn`, `B-n` are numbered in
  [docs/DECISIONS.md](docs/DECISIONS.md), appended and never rewritten.
- **Design is minimalistic and compact.** Both surfaces are read on a phone held one-handed;
  a control that costs a row of screenshot has to earn it.
- **Never commit or push unless the operator says "Current branch" or "New branch".** Those
  two words are the authorization, and they carry a defined procedure — see
  [.claude/rules/git-protocol.md](.claude/rules/git-protocol.md). Version and changelog are
  **not** touched until "Let's finish".
- **Measure, don't guess.** `python -m pytest tests/ -q` is the instrument, 94 tests today.
  Every claim about latency, frame size or throughput in this wiki came from a number
  someone actually read off a live run — keep it that way, and if there is no instrument
  for a claim you keep wanting to make, that gap is a roadmap row.

## Run and verify

```bash
python bot.py                      # or start_bot.bat — tunnel keeper, then an auto-restart loop
```

```bash
python -m pytest tests/ -q         # 94 passed
```

Then, before you commit:

```bash
python tools/wiki/check-links.py && python tools/wiki/wiki-doctor.py
```

## Load-bearing facts

Each of these cost somebody a debugging session. They are the reason the typing path looks
over-engineered; it is not, it is exactly as engineered as the failures required.

- **A paste key is a property of the target window, not a constant.** Claude Code binds
  `Ctrl+V` to *paste image from clipboard*, so a text paste into it is a silent no-op — the
  keystroke arrives, the clipboard is right, nothing appears. Terminals get
  `Ctrl+Shift+V`; `paste_hotkey_for(title)` in `handlers/input.py` decides. `D-006`
- **Terminal-ness is decided by the process, not the title.** A terminal renames itself to
  whatever runs inside it, so `WindowsTerminal.exe` showing `✳ Claude Code` matches no title
  hint. `TYPE_TERMINAL_PROCS` is the real test; `TYPE_TERMINAL_HINTS` is the fallback.
  `D-007`
- **Enter must not follow a paste immediately.** Claude Code buffers a bracketed paste, and
  an Enter arriving inside that window is folded into the block as a literal newline instead
  of submitting. `TYPE_ENTER_DELAY` (0.45s) is the gap and
  **`type_and_enter()` is the only place allowed to sequence paste-then-Enter** — a caller
  that presses its own Enter reintroduces the bug on one surface only. `D-005`
- **Focusing a window is not focusing the control inside it.** `focus_window_exact` raises
  the window; the caret stays where it was, which after `code -n` is the editor. The VS Code
  integrated terminal is reached through the command palette, and that sequence lives in
  exactly one file, `utils/vscode.py` — a second copy is how one surface silently goes back
  to typing into the editor. A test fails if one appears. `D-008`
- **A window title is not an identity.** VS Code puts the open file first, so two titles of
  one window can share no prefix. `tail_key()` (last two `" - "` segments) matches them, and
  the client's `_sameWin` mirrors `focus_window_exact` on purpose — when one side changes,
  both do, and a test enforces it. `D-009`
- **Every `/api/*` handler checks auth, and a scoped `refine.*` token must reach exactly
  three of them.** `_check_auth_refine` is a separate function rather than a keyword
  argument so a bad merge fails *closed* instead of quietly opening a shell route. Two tests
  pin the coverage and the count. `D-010`
- **The whole dashboard rides one reverse-SSH pipe.** Anything that fires a request on a
  timer must chain from the previous request's *completion*, never `setInterval` — a fixed
  interval piles up in that single pipe and the live view stops updating. `D-011`
