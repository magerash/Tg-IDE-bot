# Environment — the machine, the procedures, and what goes wrong

Everything about the world *outside* the source code: versions, binaries, ports, commands,
and the failure modes that have actually happened.

**This is the layer that rots silently.** The code tells you when it is wrong — it fails to
import, the test goes red. The environment does not: it quietly describes a machine nobody
has any more. So every fact here was established by **running something**, and each one is
dated.

**An environment document that was never re-run is a guess with a date on it.**

---

## Run it

```bash
python bot.py
```

Or, and this is the one the operator actually uses:

```bat
start_bot.bat
```

which starts the hidden tunnel keeper first and then the bot inside a 5-second restart loop.
A shortcut to it lives in the Startup folder, so everything comes up after a reboot. It is
safe to run twice — the keeper self-guards and `utils/singleton.py` kills a stale bot.

| | |
|---|---|
| the app | Telegram bot answers `/status`; dashboard on `http://localhost:8080`, publicly on `:8443` through the tunnel |
| the tests | `python -m pytest tests/ -q` — **94 passed** in ~4s (2026-09-02) |
| the wiki | `python tools/wiki/check-links.py && python tools/wiki/wiki-doctor.py` — both must be clean |

**A fresh checkout needs** `pip install -r requirements.txt` and a `.env` carrying at least
`BOT_TOKEN`, `ALLOWED_USER_ID`, `WEB_TOKEN`; `WEBAPP_URL` and `GROQ_API_KEY` unlock the Mini
App button and the voice/AI features respectively. Nothing else — no build step, no database,
no service to register. The tests run without any of it: `BOT_TOKEN` is `None` in CI and the
code is written to tolerate that (an empty secret mints an empty scope token and validates
nothing, `D-010`).

## Machine facts — verified 2026-09-02

| | |
|---|---|
| Platform | Windows 11 Pro, 10.0.26200, x64 — **Windows-only by design**: `pygetwindow`, the Win32 focus chain and the clipboard calls have no portable equivalent |
| Python | 3.14.3, system-wide at `C:\Python314`, user packages under `%APPDATA%\Python\Python314` |
| pytest | 9.0.3 |
| OpenSSH | 9.7p1 — the tunnel is stock Windows ssh, not PuTTY |
| gh | 2.97.0 |
| Node | v24.13.1 — **present but unused by this project**; the web pages are hand-written, no build step, no `package.json` |
| Shell | PowerShell is the operator's; the repo also ships `start_bot_git_bash.sh` |
| **A virtualenv** | **absent** — packages are installed user-wide. Consequence: `python` on PATH is the only interpreter, and a package upgrade is global |
| **A CI runner** | **absent** — the tests are run locally, by hand or by an agent, before a commit |
| **A linter or formatter** | **absent** — no black, no ruff, no pre-commit. Style is by imitation |

**Ports.** `8080` bot (aiohttp, local) → `18080` on the VPS (reverse SSH) → `8443` public via
Caddy. Real hostnames and addresses are in the gitignored topology file — see
[documentation/README-vps.md](documentation/README-vps.md) and `B-1`.

## Failure modes that have actually happened

One row every time something confuses somebody for more than ten minutes. The **symptom** is
written as the reader will experience it, not as it was eventually understood.

| Symptom | Cause | Fix |
|---|---|---|
| Bot restart-loops at startup, `httpx.ConnectTimeout` to `api.telegram.org:443` every 5s | the network path to Telegram is down or filtered — **not** auth, not the token | wait, or fix the link. Confirm with `curl -o /dev/null -w "%{http_code}" https://api.telegram.org/` — a 302 means the path is fine. Observed 2026-09-02 01:00, self-cleared by 01:02 |
| Bot answers `Typed: …` and nothing appears in the terminal | the caret is not where you think. Window focused ≠ control focused (`D-008`), or the paste key is wrong for the target (`D-006`, `D-007`) | the toast now names it. Check the foreground window really is VS Code and that the terminal, not the editor, has focus |
| Text arrives glued to the previous message, or sits in the box unsent | Enter landed inside the bracketed-paste window (`D-005`) | never press Enter outside `type_and_enter()`; raise `TYPE_ENTER_DELAY` if a slow machine needs it |
| Typing does nothing at all, on every surface, for no visible reason | the target window's keyboard layout is Russian and `VkKeyScanW` returns `-1` (`D-012`) | fixed in v0.21.0 — typing goes out as virtual-key codes. Check the layout via `/api/layout` if it recurs |
| Mini App is slow on the phone, instant on the PC | the phone's VPN hairpins bot traffic through the VPS that *is* the VPN server (`D-004`) | exclude the VPS **address** from the VPN's split tunnel on the phone; re-check after every VPS migration, because Amnezia matches by address, not hostname |
| Public URL 502s right after "Restart Bot" | Caddy holds pooled upstream connections through the ssh tunnel and `os.execv` kills them | retry; it self-clears. If it does not, the tunnel is down |
| Public URL 502s and stays down | `TgBotTunnel` is not running, or two keepers are fighting over remote `:18080` — the loser dies on `ExitOnForwardFailure` and retries every 5s | `taskkill /IM ssh.exe`, then `start_tunnel_vps.ps1`; the keeper is single-instance since v0.16.1 |
| Bot will not start, port 8080 already in use | a zombie instance still holds it (`D-002`) | `utils/singleton.py` handles it now. If it recurs, `netstat -ano \| findstr :8080` and check the pid is really python (`A-003`) |
| The Mini App shows old UI against a new bot | Telegram's webview caches the page per URL and ignores no-cache headers | `CLIENT_VERSION` vs `/api/status` triggers a one-shot `?v=` reload; the menu-button URL is version-stamped |
| Voice recognition works, the AI cleanup does not | the model was retired upstream (`D-013`) | the fallback chain covers it and the toast names the failure; change `HUMANIZE_MODEL` if the whole chain is gone |
| `taskkill` or `tasklist` times out for no reason | process **creation** on this box sometimes hangs (`B-2`) | do not spawn a process to solve it — that is the bug. Use an in-process API |

## What is not here

- **The VPS, the tunnel topology and the VPN** — [documentation/README-vps.md](documentation/README-vps.md),
  and the real file, gitignored, beside it.
- **What each feature does** — [chunks/features/](chunks/features/).
- **Why any of it is shaped this way** — [DECISIONS.md](DECISIONS.md).
- **Credentials** — `.env`, never in this repository, never in a doc.

---

## Keeping it current

Regulation step 3: if a version, a path, a port, a command or a procedure changed — or you
hit a failure mode nobody had written down — this file changes in the same commit.

**Corrections are marked, not silently applied.** When something here turns out to be wrong,
quote what it used to say before you replace it — `⚠️ Corrected YYYY-MM-DD: this used to say
X, which was wrong because Y`. A procedure that changed for a reason is a procedure somebody
will otherwise change back.

**Standing dirt, so nobody rediscovers it as news:** `bot.log` is **3.0GB** as of
2026-09-02 (2.7GB at v0.17.0, 2.9GB at v0.19.1). `httpcore` and `telegram.ext` log every poll
at DEBUG and nothing rotates. That is [row 3](ROADMAP.md).
