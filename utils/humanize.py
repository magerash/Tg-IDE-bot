"""Clean raw speech transcripts into prompt-ready text via Groq LLM."""
import logging
import re

import aiohttp

from config import (
    GROQ_API_KEY, HUMANIZE_FALLBACKS, HUMANIZE_MODEL, HUMANIZE_REASONING,
)

logger = logging.getLogger("bot.humanize")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# A model that ignores the reasoning setting can still emit its thinking inline.
# That text would be pasted into Claude Code verbatim, so strip it defensively.
_THINK_RE = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)
_OPEN_THINK_RE = re.compile(r"<(think|thinking|reasoning)>.*", re.S | re.I)

_SYSTEM = (
    "You clean up raw speech-to-text dictation into ready-to-use text.\n"
    "Rules:\n"
    "- Remove filler words, hesitations, repetitions and false starts.\n"
    "- When the speaker corrects themselves, keep only the final version.\n"
    "- Preserve verbatim: technical terms, file paths, commands, code, names, numbers.\n"
    "- Keep the speaker's language(s) exactly as spoken (Russian stays Russian, "
    "English stays English, mixed stays mixed).\n"
    "- Keep the meaning, intent and order. Never add new content or your own ideas.\n"
    "- Vary sentence length naturally; concrete wording; active voice.\n"
    "- Output ONLY the cleaned text — no preamble, no quotes, no commentary."
)


def _strip_reasoning(text: str) -> str:
    out = _THINK_RE.sub("", text)
    out = _OPEN_THINK_RE.sub("", out)  # unterminated block = truncated thinking
    return out.strip()


async def _call(session, model: str, text: str, reasoning: str | None) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
    }
    if reasoning:
        payload["reasoning_effort"] = reasoning
    async with session.post(
        GROQ_CHAT_URL, json=payload,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
    ) as resp:
        body = await resp.json(content_type=None)
        if resp.status != 200:
            msg = body.get("error", {}).get("message", str(body))[:300]
            raise RuntimeError(f"{resp.status}: {msg}")
        return (body["choices"][0]["message"].get("content") or "").strip()


async def humanize(text: str) -> str:
    """Return cleaned transcript. Raises when every model fails — caller falls back
    to raw, but must say so: a silent fallback looks exactly like "AI does nothing".
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    if not text.strip():
        return text

    models = [HUMANIZE_MODEL] + [m for m in HUMANIZE_FALLBACKS if m != HUMANIZE_MODEL]
    errors = []
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in models:
            logger.debug("Humanize request: %d chars, model=%s", len(text), model)
            try:
                out = await _call(session, model, text, HUMANIZE_REASONING)
            except RuntimeError as e:
                # A model that rejects reasoning_effort is worth one retry without it
                if "reasoning" in str(e).lower():
                    try:
                        out = await _call(session, model, text, None)
                    except Exception as e2:
                        errors.append(f"{model} -> {e2}")
                        continue
                else:
                    errors.append(f"{model} -> {e}")
                    logger.warning("Humanize model %s failed: %s", model, e)
                    continue
            except Exception as e:
                errors.append(f"{model} -> {e}")
                continue

            out = _strip_reasoning(out)
            if not out:
                errors.append(f"{model} -> empty after stripping reasoning")
                continue
            if model != HUMANIZE_MODEL:
                logger.warning("Humanize fell back to %s (primary %s unavailable)",
                               model, HUMANIZE_MODEL)
            logger.debug("Humanize result: %d -> %d chars via %s",
                         len(text), len(out), model)
            return out

    raise RuntimeError("Humanize failed: " + "; ".join(errors))
