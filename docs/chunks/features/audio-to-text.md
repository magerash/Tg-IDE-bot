# Audio-to-Text (Voice Input + Humanize)

## Quick Reference
| File | Purpose |
|------|---------|
| `utils/stt.py` | `transcribe(bytes, filename)` — Groq Whisper API call |
| `utils/humanize.py` | `humanize(text)` — Groq LLM transcript cleanup |
| `handlers/audio.py` | TG voice/audio handler + `a:*` action buttons + Raw/Clean toggle |
| `handlers/web_extra.py` | `/api/stt` POST endpoint (`?humanize=1` flag, returns `{text, raw}`) |
| `web/common.js` | Mic button logic shared by both surfaces (`toggleMic`, `blobToWav`, `sttUpload`), ✨ Human toggle |
| `web/index.html` · `web/refine.html` | the two pages that mount it — see `refinement-view.md` |
| `config.py` | `GROQ_API_KEY`, `STT_MODEL`, `HUMANIZE_MODEL`, `HUMANIZE_FALLBACKS`, `HUMANIZE_REASONING`, `HUMANIZE_DEFAULT` |

## Overview
Speak instead of type. Two entry points:
1. **Telegram**: send voice message → transcript + inline buttons `⌨ Type` / `⌨ Type+Enter` / `🤖 Claude`
2. **Web UI**: 🎤 button next to Type field → record (red ⏹ while recording) → transcript inserted into Type textarea, editable before send

Engine: **Groq Whisper** (`whisper-large-v3-turbo`), free key at console.groq.com → `GROQ_API_KEY` in `.env`. Chosen because it accepts TG `.oga` (ogg/opus) and browser webm/mp4 natively — no ffmpeg, no GPU, works on Python 3.14. Auto language detect (RU/EN). See `docs/analysis/audio-to-text-plan.md` for engine comparison.

## Key Functions

### `utils/stt.py`
- `transcribe(data, filename)` — aiohttp POST multipart to `api.groq.com/openai/v1/audio/transcriptions`, 60s timeout, 25MB cap
- `STTError` — raised on missing key / size / API errors (friendly messages)

### `utils/humanize.py`
- `humanize(text)` — Groq chat completions (`HUMANIZE_MODEL`, temp 0.2, 30s timeout), tries `HUMANIZE_FALLBACKS` in order when a model is gone, raises only when every model failed
- System prompt: remove fillers/repeats/false starts (keep final version of self-corrections), preserve tech terms/paths/commands verbatim, keep RU/EN mix, no new content, output only cleaned text
- `_strip_reasoning(text)` — drops `<think>…</think>` (and an unterminated tail) in case a model ignores the reasoning setting
- Callers fall back to raw **and must say so** — see below

## Model retirement (v0.17.1) — the failure mode that looks like "AI does nothing"
`llama-3.3-70b-versatile` answered normally at 13:18 on 2026-08-17 and returned
`404 — does not exist or you do not have access` by 14:25; the entire Llama family
had vanished from the key. Whisper was untouched, so **recognition kept working
and only the cleanup died** — the AI toggle stayed ON and the toast still said
"Transcribed", so nothing pointed at the model.

Rules that came out of it:
- **Fallback chain.** `HUMANIZE_MODEL` (`qwen/qwen3.6-27b`) then `HUMANIZE_FALLBACKS`
  (`openai/gpt-oss-20b`). First model that answers wins; falling back logs a warning.
- **Never fail silently.** `/api/stt` returns `humanized` + `humanize_error`; the
  dashboard toasts `AI cleanup failed, raw text: …`; TG appends `⚠ AI cleanup failed`.
- **Suppress reasoning.** `HUMANIZE_REASONING=none` → `reasoning_effort`. Without
  it qwen3.6 returned **7196 chars of `<think>…`** for a 483-char transcript —
  that text would have been typed straight into Claude Code.
- Still the same free Groq key and endpoint; only the model string changed.
  `openai/gpt-oss-120b` and `groq/compound-mini` answer **403 blocked at project
  level** for this key (console.groq.com → project limits to enable).
- Check what a key can actually reach: `GET https://api.groq.com/openai/v1/models`.

### `handlers/audio.py`
- `audio_handler()` — `@auth_required @rate_limit(2.0)`; download → transcribe → humanize (if `HUMANIZE_DEFAULT`) → transcript + keyboard
- Long transcripts: display capped at 3900 chars (TG 4096 limit), full text sent via `send_long_text_to_chat`
- `audio_callback()` — pattern `^a:`; acts on `_last[chat_id]`:
  - `a:type` / `a:enter` — `_type_text` into focused window (+ Enter)
  - `a:claude` — `claude -p <transcript>`, output via `send_long_text_to_chat`
  - `a:raw` / `a:clean` — toggle displayed variant (📝 Raw / ✨ Clean button)
- `_last` — per-chat store `{clean, raw, showing}` (callback data limited to 64B)

### `/api/stt` (web_extra.py)
- POST raw audio bytes, `Content-Type` decides filename ext (webm/ogg/m4a/wav)
- `?humanize=1` → LLM cleanup; on error returns the raw text **plus** `humanize_error`
- Auth via `_check_auth` (initData or bearer), returns `{ok, text, raw, humanized, humanize_error}`

### Web (`index.html`)
- `toggleMic()` — MediaRecorder, mime pick webm/opus → mp4 fallback (iOS webview), **600s (10 min) hard stop** with ticking mm:ss on button (⚠ in last minute), min 1KB blob
- ✨ Human toggle (`human-btn`, green = ON, persisted `tg_humanize`) — adds `?humanize=1` to upload
- `blobToWav(blob)` — decode via Web Audio → OfflineAudioContext resample → mono 16kHz 16-bit WAV. **Required:** Chrome MediaRecorder webm has no duration metadata → Groq decodes as 0s silence → Whisper hallucinates "Thank you."
- Silence detector: `_lastPeak` (max |sample|) computed during WAV encode; peak < 0.005 → skip upload, toast with `_micLabel` (device name) — diagnoses mic permission / wrong device / OS privacy block
- `sttUpload(blob)` — raw POST with auth headers (bypasses JSON `api()` helper)
- Result appended to `type-input`, logged to History as `type`
- Telegram webview may block `getUserMedia` — error toast suggests browser fallback

## Code Patterns
- Voice routing in `bot.py`: `MessageHandler(filters.VOICE | filters.AUDIO, audio_handler)` + `CallbackQueryHandler(audio_callback, pattern="^a:")`
- No key configured → `STTError` with console.groq.com hint (bot stays alive)

## Related
- Input simulation: `phase2-screen-input.md`
- Web dashboard: `web-dashboard.md`
