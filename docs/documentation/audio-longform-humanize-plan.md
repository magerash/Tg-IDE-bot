# Plan: Long Audio + Humanize Pipeline

Date: 2026-07-22 · Status: awaiting user approval · Research: `audio-longform-humanize-research.md`

## Goal
Speak long-form (up to 10 min), lose nothing, get clean prompt-ready text instead of raw rambling transcript.

## Pipeline
```
speech ──► STT (Groq Whisper) ──► raw transcript ──► Humanize (Groq llama-3.3-70b) ──► clean text
                                        │                                                  │
                                        └── kept for History / fallback ──────────────────┘
```

## Changes

### 1. Longer recording (fixes cut speech)
| What | From → To |
|------|-----------|
| Web mic hard stop | 120s → **600s (10 min)** |
| Recording timer UI | none → **mm:ss ticking on mic button** (red, replaces stop icon text), turns orange at 9:00 |
| Auto-stop behavior | silent → toast "Max 10 min reached, transcribing..." |
| TG long transcript reply | `edit_text` (4096 fail) → `send_long_text` fallback |

WAV stays 16kHz mono: 10 min = 19.2MB < 25MB Groq cap.
Long WAV encode: `blobToWav` loop OK up to 10 min (~9.6M samples, <1s encode).

### 2. Humanize step (new `utils/humanize.py`, ≤100 lines)
- `async humanize(text: str) -> str` — Groq chat completions, `llama-3.3-70b-versatile`, same `GROQ_API_KEY`
- System prompt (humanizer-skill principles adapted for dictation):
  - remove fillers, repetitions, false starts; self-correction → keep last version
  - preserve verbatim: technical terms, file paths, commands, names, numbers
  - keep spoken language mix (RU/EN), keep meaning and order, no new content
  - output plain text ready to paste as prompt, no preamble/quotes
- Config: `HUMANIZE_MODEL = "llama-3.3-70b-versatile"` (env-overridable), `HUMANIZE = True` default
- Errors → fall back to raw transcript, log warning (never block dictation)

### 3. Web UI
- Mic flow: record → STT → **humanize → cleaned text into Type field**
- Toggle chip next to mic: **✨ Human ON/OFF** (persisted in localStorage) — OFF = raw like today
- History: cleaned text saved; raw kept in tooltip/entry suffix? → minimal: save cleaned only, toast shows "raw 812 → clean 512 chars"
- `/api/stt` response extended: `{ok, text, raw}` — server does STT + optional humanize (`?humanize=1` query or body flag)

### 4. Telegram
- Voice message → STT → humanize → reply cleaned transcript + existing buttons (Type / Type+Enter / Claude)
- New button **📝 Raw** on transcript message — swaps to raw transcript (stored in `_last` alongside)
- Long texts: `send_long_text` instead of `edit_text`

### 5. Files touched
| File | Change |
|------|--------|
| `utils/humanize.py` | NEW — Groq LLM call |
| `utils/stt.py` | no change |
| `handlers/audio.py` | humanize call, Raw button, long-text fallback |
| `handlers/web_extra.py` | `/api/stt` humanize flag + raw in response |
| `web/index.html` | 600s cap, timer UI, Human toggle, insert cleaned |
| `config.py` | `HUMANIZE_MODEL`, `HUMANIZE_DEFAULT` |
| `tests/test_web.py` | +humanize-off passthrough test |
| chunk `audio-to-text.md` | update |

## Cost / Limits Check
- Groq free: STT unlimited-ish for personal use; LLM 1K req/day, 100K tokens/day → ~50 long dictations/day headroom
- Latency added by humanize: ~1s (llama-3.3-70b on Groq)

## Out of Scope (later if wanted)
- Packaging STT as reusable Claude Code skill
- Chunked >13 min audio (split upload)
- Streaming partial transcripts while recording

## Steps (on approval)
1. `utils/humanize.py` + config
2. Web: 600s + timer + toggle + flow
3. TG: humanize + Raw button + long-text fallback
4. Test + chunk update
