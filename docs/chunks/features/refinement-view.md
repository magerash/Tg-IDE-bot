# Refinement view (`/refine`) — split-view Mini App

## Quick Reference

| | |
|---|---|
| Route | `GET /refine` → `web/refine.html` (no-cache, same contract as `/`) |
| Files | `web/refine.html`, `web/common.js` (shared with the dashboard) |
| Auth | 12h **refine-scoped token**, `sessionStorage['tg_scope_refine']` |
| Reaches | `/api/status`, `/api/stt`, `/api/improve`, `/api/scope` — **nothing else** |
| Entry points | header `✨ Refine` link on the dashboard; `/panel` → ✨ Refine button; direct URL |
| Tools | mic → STT, AI cleanup toggle, ✨ Improve (4 styles), Twin, markdown, **Copy** |
| Tests | `tests/test_refine.py` (24) |

## Overview

The dashboard mixes two jobs: remote control of the PC (24 of 27 API routes — keystrokes, mouse, shell,
git, build, restart) and text refinement (`/api/stt` + `/api/improve`). Refinement is what gets used from a
phone and it needs none of the risk, so it got its own page.

**Text leaves this view through the clipboard only.** There is no Type button — that was a deliberate
product decision, not an oversight. Typing into a focused window is remote control; Copy is not.

The split is enforced on the **server**, not just in the markup: the page runs on a scope-limited credential
and `_check_auth_refine()` is called by exactly three handlers. Everything else refuses it with 401.

## Scoped-token protocol

```
POST /api/scope {"scope":"refine"}   ← requires FULL auth (initData or WEB_TOKEN)
  → {"ok":true, "token":"refine.<exp>.<hmac>", "ttl":43200, "scope":"refine"}
```

- `utils/webauth.py`: `make_scoped_token(secret, scope, ttl)` / `verify_scoped_token(token, secret, scope)`.
- Key is **derived** (`HMAC(b"tgide-scope-v1", secret)`) so scope tokens never share key material with the
  initData check, which HMACs the same bot token under a different construction.
- **The scope is inside the MAC** (`HMAC(key, f"{scope}.{exp}")`). Signing the expiry alone would let anyone
  rewrite the prefix and promote the token.
- Secret is `BOT_TOKEN or WEB_TOKEN`. **Empty secret mints `""` and validates nothing** — `BOT_TOKEN` is
  `os.getenv(...)` with no default and is `None` in CI, so this is not theoretical.
- TTL **12h**: shorter than `INIT_DATA_MAX_AGE` (24h) so a scope can never outlive the credential that minted
  it, long enough that a webview suspended by a phone call doesn't 401 mid-dictation.
- Read from the `Authorization` header **only, never `?token=`** — the query form lands in every proxy and
  tunnel access log.
- **No revocation list.** Rotating `BOT_TOKEN`/`WEB_TOKEN` invalidates every outstanding scoped token. That
  is the escape hatch.
- `/api/scope` requires *full* auth, so a refine token cannot mint another — otherwise the 12h life is
  unbounded.

Client side (`refine.html`): `_mintScope()` → `sessionStorage` (never `localStorage`, which is where the
permanent `tg_bot_token` lives), `_ensureScope()` refreshes when <5 min remain, and the `api()` wrapper
retries **exactly once** on a 401. Never more — an unbounded refresh loop through the tunnel is precisely the
wedge `API_TIMEOUT` was added to prevent. `sttUpload()` is wrapped the same way, because `toggleMic()` calls it
directly and bypasses `api()` — and without its own `_ensureScope()` guard a failed mint would upload the
recording with **no auth header at all**, which reads to the user as "the mic button does nothing".

### What the scoped token buys — and what it does not

**It does not sandbox the page.** Inside the Telegram webview, `Telegram.WebApp.initData` is readable by any
script on the page and **is a full credential**. No page-side design stops an operator with devtools from
re-authing as themselves and calling `/api/sh`. That is Telegram's Mini App model. The acceptance criterion
"inaccessible even via API calls" cannot be met against the authenticated operator in that environment, and
any claim otherwise is a UI promise, not a boundary.

What it *does* buy, all four real:

1. **Defence against this page's own code.** Every handler here is an inline-`onclick` global in a script
   shared with the dashboard. If `refine.html` or `common.js` ever grows a mistyped path or a copy-pasted
   handler, the request carries a refine credential and the *server* refuses. Server-side scope is the only
   mechanism that survives a client-side mistake.
2. **"No typing to the PC" becomes a CI-tested invariant** (`test_scoped_token_rejected_by_system_routes`,
   `test_every_api_handler_checks_auth`) instead of something that regresses silently the next time someone
   adds a button.
3. **Browser mode is genuinely narrowed.** Open `/refine` in a phone browser and that flow carries only the
   scoped token — it really cannot type, shell, or restart. There the boundary is the whole thing.
4. **Blast radius on leak.** A scoped token in a screenshot or a log is a text-refinement token with hours to
   live. `WEB_TOKEN` in the same place is a permanent remote shell.

**Design consequences that make (1) real:**

- The page reads `initData` through `_fullCred()` inside `_mintScope()` and never assigns it to a
  page-lifetime variable. `index.html` keeps one in `const TG`; refine sets
  `window.NO_AMBIENT_AUTH = true` **before** loading `common.js` so that global is `null` here.
- `common.js`'s `api()` and `sttUpload()` both take their credential from the `_authHeaders()` hook.
  Without it initData wins in Telegram mode and the narrowing is fiction — this was a real defect caught in
  review, not a hypothetical.

**Be precise about what is still reachable.** `localStorage['tg_bot_token']` and `window.Telegram.WebApp`
are *same-origin browser state*. Any script executing on this origin can read them, on any page, and no
token design fences that off — it is not something `refine.html` can revoke. That is why the markdown
renderer is treated as security-relevant here (below): script execution in the preview is the one realistic
path from "text in a field" to "full credential in hand", and it is the escalation the scoped token cannot
stop. Guarding the renderer is what keeps (1) meaningful.

## Layout

Single column, `max-width:1180px`, one media query at 760px — none of the dashboard's
rail/`display:contents` machinery, which is what makes its mobile layout fragile.

**The wrap was 640px until v0.19.1** and that was wrong for this view: on a 2000px window the page was a
phone-width column stranded in the middle, the text scrolling inside 400px of it while the rest sat empty.
This is a document editor, so it gets the window. Above 760px both panes are sized from the **viewport**
(`height:calc(100vh - 300px)`, `min-height:340px`), not from their content.

- **CSS was only half the fix.** `autoGrow` (in `common.js`) writes an *inline* height capped at 400px, and
  an inline height beats a stylesheet rule — it undid the fit on every keystroke, every Improve, every
  transcription. `autoGrow` is wrapped on this page: on wide screens it clears `el.style.height` and returns;
  on the stacked phone layout it calls through unchanged. `resize` re-fits. Locked by
  `test_refine_uses_the_whole_window_on_a_wide_screen`, which asserts the inline-height clear as well as the
  two CSS values — the CSS alone passing would be a false green.
- **Reading measure is capped inside the pane** (`.md-body>* {max-width:78ch}`), never on the pane itself.
  Capping the pane is how you get the stranded column back.
- **Char/word counter** (`#char-count`) sits beside Copy and is driven from the wrapped `autoGrow`, so every
  programmatic write — Improve, transcription, history refill, Clear — updates it. Wiring it to the `input`
  event instead would have missed all four, the same trap the v0.19.0 markdown-preview staleness fix hit.

```
[data-status]                 ← load-bearing, see below
Type panel
  AI: ON | mic
  Twin | style | ✨ Improve | MD
  textarea  +  .md-body preview     (side by side ≥760px when MD is on)
  📋 Copy | Clear
  hint: "Nothing is typed to your PC. Text leaves this view only via Copy."
History panel
```

- **Controls above the field** so the thumb reaches mic/Improve without scrolling past a tall textarea.
- **Copy below the field** — terminal action, read the result first, and far from the mic where a mis-tap
  would cost a recording.
- **`<div class="action-status" data-status>` is not decoration.** `sttUpload()` reports upload progress
  through `setStatus()`; with no `[data-status]` in the DOM a 19MB WAV over a phone tunnel is 30 seconds of
  silent spinner.

### Deliberately absent — each is a system path in disguise

| Not here | Why |
|---|---|
| Type button, 11 presets | `doTypePreset` → `/api/type` |
| `#attach-row`, image paste, Alt+V | `/api/paste` saves a PNG and **types its path** |
| Blocks toggle | exists only to shape what gets *typed* |
| Quick-keys bar, Keys/Actions | `/api/key` |
| Screen, lightbox, scroll pads | `/api/frame`, `/api/scroll` |
| Shell, Claude, git, build, restart | obvious |
| Windows, Projects, Scheduled, CC metrics | focus / project switch / scheduled keystrokes |
| `alignRails()` | does `.observe(document.querySelector('.center'))` — a TypeError there kills every statement after it in the same script |

Enforced by `test_refine_page_has_no_system_endpoints` (scans refine.html **and** common.js for literal
endpoint strings) and `test_common_js_has_no_dashboard_only_code` (catches the ones carrying no `/api/`
string). **Do not add anything to this page that calls a system endpoint** — put it in `index.html`.

## Copy button

Order matters more than the code:

1. **The clipboard write is the first async thing in the handler.** Any prior `await` drops transient user
   activation and Telegram's Android webview then silently refuses — the classic "works on desktop, does
   nothing on my phone". `test_copy_button_exists_with_fallback` regexes for an `await` before the write.
2. Feature-check `navigator.clipboard && writeText`, then `try` — it is `undefined` on some Android WebView
   builds and rejects with `NotAllowedError` in Telegram.
3. Fallback: hidden `<textarea>`, `position:fixed;left:-9999px;opacity:0` — **not** `display:none`, which
   iOS refuses to select — `focus/select/setSelectionRange`, `execCommand('copy')`, remove.
4. **Restore the caret** (`selectionStart/End` + focus) or the user loses their place mid-edit.
5. Empty field → error toast, **clipboard untouched**. Clobbering it with `""` is worse than doing nothing.
6. `> 500 000` chars → skip the fallback (`execCommand` on a multi-MB string janks the main thread),
   `el.select()` and say so.
7. `HapticFeedback.notificationOccurred('success')` in a try/catch — on a phone it is the only confirmation
   you get without looking.

Toasts name the size and the path taken, so a bug report is actionable:
`Copied — 1 842 chars` · `Copied (fallback) — 1 842 chars` ·
`Copy blocked by this webview — text selected, long-press to copy` ·
`Too long to copy here (600 001 chars) — text selected, long-press to copy` ·
`Nothing to copy — the field is empty`

## Markdown: rendered *and* editable

Raw textarea = the single editable source of truth; `.md-body` = derived, read-only. That is the only safe
shape here — a contenteditable rendered editor would put user-controlled rendered HTML into an editable
surface, at which point `_mdRender`'s escape-before-inject stops being a guard. Invalid markdown degrades to
paragraphs by construction; the renderer has no error path.

**The renderer is security-relevant, and doubly so here** (default ON, and the text often arrives from an
LLM or a transcript rather than from the operator's own keystrokes). Two guards, both test-pinned by
`test_markdown_preview_cannot_execute_script`:

- `_mdEsc` escapes `& < > " '`. Quotes matter because the link rule drops the URL straight into an
  `href="…"` — without escaping, `[x](https://e.com/")onmouseover="alert(1))` would close the attribute and
  open an event handler.
- `_mdSafeUrl` allows only `http(s)://`, `mailto:` and relative/anchor targets. Anything else —
  `javascript:`, `data:`, `vbscript:` — renders as **plain text**, not a link. A one-click
  `[click](javascript:…)` would otherwise run script with this origin's credentials and walk past every
  boundary above.

**`tg_md_refine`, default ON** — separate from the dashboard's `tg_md` (default OFF). The two fields are
different jobs: one is text about to be typed into a terminal (markdown is noise), the other is a document
being produced to paste elsewhere (rendered *is* the point). With a shared key, turning the preview on here
would push the dashboard's preset grid below the fold.

`window.MD_STORAGE_KEY` / `window.MD_DEFAULT_ON` are read by `common.js` at load, so they must be set in an
inline `<script>` **before** the `common.js` tag.

## History: shared on purpose

One `tg_history`. A draft dictated in refine appearing in the dashboard's History is the feature — same
operator, same day's thinking — and splitting it would stop the dashboard's History being "everything I wrote
today". Two guards make it safe:

- `window.HISTORY_TARGETS` routes **every** kind to `type-input` here (a shell line is still text you might
  want to refine); there is no `#sh-input`/`#claude-input` on this page.
- `renderHistory`'s click handler null-guards the target — without it, clicking a `shell` row throws.

No `copy` history kind: it would double every entry. `Clear` saves the field to History as a `draft` first,
so nothing is lost to a mis-tap.

## Entry points

`handlers/panel.py` builds the keyboard **per message** (`build_keyboard(chat_type)`), not once at import:

```python
[🖥 Dashboard → miniapp_url()]  [✨ Refine → refine_url()]
```

- **Private chats only.** Telegram rejects `web_app` inline buttons elsewhere with `BUTTON_TYPE_INVALID` and
  fails the **whole message** — an unguarded row would take `/panel` down in any group the bot sits in.
  `@auth_required` checks the user, not the chat.
- Empty or non-HTTPS `WEBAPP_URL` → no buttons, not a broken panel.
- `refine_url(base, version)` handles a trailing slash and an existing query:
  `https://x/` → `https://x/refine?v=0.18.0`.
- `setup_menu_button` is untouched — Telegram allows one chat menu button and it stays on the dashboard.

**Header cross-link (`.view-link`).** Each page carries a link to the other, mirroring `.theme-toggle` on
the left. Added the day the split shipped: with `/panel` as the only door, the view was invisible to anyone
who opened the Mini App from the menu button, and unreachable in a browser without typing the URL.
`test_the_two_views_link_to_each_other` keeps both doors open.

## Related

- [`web-dashboard.md`](web-dashboard.md) — the full dashboard and the shared `common.js` contract
- [`improve-text.md`](improve-text.md) — Improve styles, twin profile, prompt ordering
- [`audio-to-text.md`](audio-to-text.md) — mic → WAV → Whisper → humanize
- [`panel.md`](panel.md) — the inline keyboard
