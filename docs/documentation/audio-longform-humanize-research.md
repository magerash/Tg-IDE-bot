# Research: Long Audio Recording + Transcript Humanization

Date: 2026-07-22 · Status: research for review, no implementation yet

## Problem (user report)
1. Recording has hidden limit — long speech gets cut, tail of prompt never appears
2. Raw speech transcript is messy: repetitions ("speak speak"), fillers, false starts — needs transform into clean human text
3. User wants longer audio + longer text handling (not max, but comfortable long-form)

## Current Limits Audit (our code, v0.12.0)

| Limit | Value | Where | Effect |
|-------|-------|-------|--------|
| Web mic hard stop | **120s** | `toggleMic()` `_recTimer` | **Root cause of cut speech** — recording silently stops at 2 min, user keeps talking, rest lost |
| No recording timer UI | — | — | User can't see limit approaching or that recording stopped |
| Upload size | 25MB | `utils/stt.py MAX_AUDIO_SIZE` | WAV 16kHz mono = 32KB/s → ~13 min fits |
| TG voice download | 20MB | Telegram Bot API limit | ~long voice OK (ogg/opus ~1MB/min) |
| TG transcript reply | 4096 chars | `edit_text` in `audio.py` | Long transcript → edit fails → **prompt not appears** (second cut cause) |
| Groq audio file | 25MB free tier | Groq docs | matches ours |

## Whisper / Groq Facts
- [Groq speech-to-text docs](https://console.groq.com/docs/speech-to-text): free tier 25MB/file (dev tier 100MB), formats flac/mp3/mp4/m4a/ogg/wav/webm
- `whisper-large-v3-turbo`: fast (~0.5-1s for minutes of audio), auto language (RU/EN), no explicit duration cap below file-size cap
- Our 16kHz mono WAV: 32KB/s → 25MB ≈ 13 min ceiling; **10 min (600s) safe recording cap**
- Whisper hallucinates on silence ("Thank you.") — already mitigated with peak detector v0.12.0

## Humanizer Skill
- User's referenced skill not found on this machine (searched `~/.claude/skills`, plugins, all projects). Closest public: [Aboudjem/humanizer-skill](https://github.com/Aboudjem/humanizer-skill) — 53 AI-writing patterns, 0-100 AI-tell score, 5 voice profiles (Casual/Professional/Technical/Warm/Blunt)
- Its principles transferable to speech-cleanup prompt: kill fillers and false starts, vary sentence length (burstiness), concrete wording, active voice
- For our use case (raw dictation → clean prompt text) the needed transform differs slightly from de-AI-ifying: remove speech artifacts (repetitions, "эээ/um", self-corrections — keep LAST version of corrected phrase), preserve technical terms, file paths, command names verbatim, keep language mix (RU/EN) as spoken, output ready-to-send prompt

## Audio-to-Text Skill
- No local skill found. Our `utils/stt.py` + `/api/stt` already implement it (v0.12.0). Could later be packaged as a Claude Code skill, out of scope here.

## LLM Engine Options for Humanize Step

| Engine | Cost | Speed | Notes |
|--------|------|-------|-------|
| **Groq `llama-3.3-70b-versatile`** ✅ | Free: 30 RPM, 1K req/day, 12K TPM, 100K tokens/day ([limits](https://tokenmix.ai/blog/groq-free-tier-limits-2026)) | ~1s | Same API key as STT — zero new setup. 1K/day ≫ daily dictation needs |
| `claude -p` (local CLI) | Subscription | 10-30s | Best quality, slow — bad for dictation flow |
| Anthropic API | Paid per token | ~2s | New key + billing — unnecessary |

10 min speech ≈ 1500 words ≈ 2K tokens — fits Groq TPM easily.

## Sources
- [Groq Speech-to-Text docs](https://console.groq.com/docs/speech-to-text)
- [Whisper Large v3 Turbo on Groq](https://console.groq.com/docs/model/whisper-large-v3-turbo)
- [Groq ASR 100MB dev tier blog](https://groq.com/blog/largest-most-capable-asr-model-now-faster-on-groqcloud)
- [Groq free tier limits 2026](https://tokenmix.ai/blog/groq-free-tier-limits-2026)
- [Groq pricing overview](https://www.eesel.ai/blog/groq-pricing)
- [Aboudjem/humanizer-skill](https://github.com/Aboudjem/humanizer-skill)
- [anthropics/skills repo](https://github.com/anthropics/skills)
