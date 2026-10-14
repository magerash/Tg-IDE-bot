# Audio-to-Text Plan (branch feature)

## Goal
Speak instead of type. Two entry points:
1. **Telegram** — send voice message → bot transcribes → text with action buttons (Type into focused window / Claude / plain text)
2. **Web UI** — mic button → record → transcribe → text lands in Type field (editable before send)

## Environment Constraints (checked 2026-07-21)
- Python 3.14.3 — `faster-whisper`/`ctranslate2` wheels not reliable on 3.14
- No ffmpeg installed — can't convert OGG/opus locally without adding it
- No NVIDIA GPU — local Whisper = slow CPU inference

→ **Cloud STT API is the right call.**

## Engine Options

| Engine | Cost | Formats | RU/EN | Notes |
|--------|------|---------|-------|-------|
| **Groq (whisper-large-v3-turbo)** ✅ | Free tier, generous | ogg, opus, webm, wav, mp3 native | Excellent | No ffmpeg needed; TG `.oga` + browser `webm` both accepted; fast (~1s) |
| OpenAI (whisper-1) | $0.006/min | no ogg — needs conversion | Excellent | Paid + needs ffmpeg for TG voice |
| Local vosk | Free | PCM only → needs ffmpeg | OK | Lower accuracy, model download |
| Local whisper.cpp | Free | wav → needs ffmpeg | Good | CPU-slow, setup heavy |

**Chosen: Groq.** Free key at console.groq.com → `GROQ_API_KEY` in `.env`.

## Architecture

```
TG voice msg ──► handlers/audio.py ──► utils/stt.py ──► Groq API
                     │                                      │
                     ▼                                      ▼
             transcript + inline buttons              text (auto lang ru/en)
             [⌨ Type] [⌨ Type+Enter] [🤖 Claude]

Web mic btn ──► MediaRecorder (webm/opus) ──► POST /api/stt ──► utils/stt.py
                                                    │
                                                    ▼
                                          text → Type textarea
```

## New/Changed Files

| File | Change | Limit |
|------|--------|-------|
| `utils/stt.py` | NEW — `async transcribe(data: bytes, filename: str) -> str` via Groq REST (aiohttp client, 60s timeout, DebugLogger) | ≤100 |
| `handlers/audio.py` | NEW — voice/audio message handler: download file → transcribe → reply transcript + inline buttons; callback handlers reuse input.py typing | ≤150 |
| `handlers/web_extra.py` | `/api/stt` POST endpoint (auth via webauth, multipart/raw body, size cap 25MB) | — |
| `web/index.html` | Mic button in Type panel: toggle record (red while recording), MediaRecorder → blob → api → insert into textarea; history entry type `stt` | — |
| `config.py` | `GROQ_API_KEY`, `STT_MODEL = "whisper-large-v3-turbo"` | — |
| `.env` | `GROQ_API_KEY=...` (user provides) | — |
| `bot.py` | register MessageHandler(filters.VOICE \| filters.AUDIO) + callbacks | — |
| `tests/test_web.py` | +test: /api/stt rejects unauthenticated | — |

## Behavior Details
- Language: auto-detect (RU/EN mix expected)
- TG: transcript sent as quoted text; buttons act on last transcript (store per-chat)
- Web: mic permission asked once; recording max 120s guard; while recording button pulses red
- Errors: no key → friendly "GROQ_API_KEY not set" message; API fail → error text, log full response
- Auth: `ALLOWED_USER_ID` on TG handler; `WEB_TOKEN`/initData on /api/stt
- Rate limit: same decorator as other handlers

## Steps
1. `utils/stt.py` + config + .env key
2. `handlers/audio.py` + bot.py routing — test via TG voice
3. `/api/stt` endpoint + test
4. Web mic UI + history integration
5. Chunk doc `docs/chunks/features/audio-to-text.md`, version bump on "let's finish"

## Open Question
- Groq key: user must create (free) at console.groq.com → paste into .env
