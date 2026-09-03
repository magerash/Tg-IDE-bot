# Improve Text (AI rewrite in the Type field)

## Quick Reference

| Piece | Location |
|-------|----------|
| Styles + twin + LLM call | `utils/improve.py` |
| Shared Groq caller | `utils/humanize.py` → `chat(system, text)` |
| Endpoint | `POST /api/improve` (`handlers/web_extra.py::api_improve`) |
| UI | second `.type-controls` row — on **both** surfaces: `web/index.html` and `web/refine.html` (Twin toggle · style select · ✨ Improve) |
| Client JS | `web/common.js` (`doImprove`, twin/style toggles) — shared by both pages |
| Config | `HAE_PROFILE_DIR` (default `~/.hae/profile`); reuses `HUMANIZE_MODEL`/`FALLBACKS`/`REASONING` |
| Tests | `test_improve_endpoint_auth_and_validation`, `test_improve_styles_match_ui_and_twin_is_optional`, `test_improve_never_auto_sends_and_saves_draft_first` |

Related: [audio-to-text.md](audio-to-text.md) (humanizer origin), [web-dashboard.md](web-dashboard.md)

## Overview

User types rough text into the Type field, picks a style, taps **✨ Improve** → LLM
rewrites it, result replaces the field content. **Never auto-sends** — user reads,
edits, sends themselves. The original text is pushed to History as kind `draft`
**before** the request (survives even if the call dies; click the row to restore).

Styles (`STYLES` keys must match `#imp-style` option values — drift-guarded by test):

| Key | What it does |
|-----|--------------|
| `structured` | Goal → context → constraints prompt for a coding agent, keeps input language |
| `detailed` | Expands into spec: steps, acceptance criteria, edge cases — derived only from the text |
| `concise` | Tightens, keeps all technical detail + language |
| `translate` | RU/mixed → clean English prompt |

## Twin (HAE persona injection)

`Twin: ON` toggle (persisted `tg_twin`) injects the operator profile from the HAE
plugin — `persona.md` + `principles.md` read from `HAE_PROFILE_DIR`, cached by mtime
(`_twin_context()`; returns `None` when missing → `twin_missing` in the reply, toast
says "twin profile not found", improve still runs).

Why not `twin.ps1`: the twin composer's exemplar retrieval is decision-oriented
(release scope questions), wrong tool for text rewriting, and a pwsh subprocess per
request is waste. Reading its two profile inputs directly gives the style signal.

### Prompt-ordering lessons (measured against live qwen3.6-27b, do not undo)

- Profile must go **before** the style instructions (`_TWIN_HEADER + ctx +
  _TWIN_FOOTER + style`). With profile last, the model copied `principles.md`
  sentences verbatim into the output as fake "Constraints".
- Instructions alone cannot hold the output language: a 6KB English persona
  dragged Russian input into English through three increasingly explicit
  "keep the language" rules. Fix is deterministic: `_lang_hint()` counts Cyrillic
  letters (>50% → "Output language: Russian" appended last). Skipped for
  `translate`.

## Key Functions

- `improve(text, style, twin) -> (improved, twin_used)` — builds system prompt,
  calls `chat()`; raises when every model fails (loud, like humanize)
- `chat(system, text)` (`utils/humanize.py`) — Groq fallback chain + reasoning-strip,
  extracted from `humanize()` in this feature; `humanize()` is now a thin wrapper
- `doImprove()` (index.html) — history first, spinner on `#imp-btn`, 60s explicit
  `api()` timeout, field replaced + `autoGrow` + focus on success, untouched on error

## Contract

`POST /api/improve` `{text, style, twin}` →
`{ok, improved, style, twin_used, twin_missing}`; empty text → 400, LLM failure →
502 `{error}` (client toasts, keeps original). Same auth guard as `/api/stt`.
