"""Clean raw speech transcripts into prompt-ready text via Groq LLM."""
import logging

import aiohttp

from config import GROQ_API_KEY, HUMANIZE_MODEL

logger = logging.getLogger("bot.humanize")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

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


async def humanize(text: str) -> str:
    """Return cleaned transcript. Raises on API failure — caller falls back to raw."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    if not text.strip():
        return text

    payload = {
        "model": HUMANIZE_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
    }
    logger.debug("Humanize request: %d chars, model=%s", len(text), HUMANIZE_MODEL)
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            GROQ_CHAT_URL, json=payload,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200:
                msg = body.get("error", {}).get("message", str(body))[:300]
                raise RuntimeError(f"Humanize API error {resp.status}: {msg}")
            out = (body["choices"][0]["message"]["content"] or "").strip()
            logger.debug("Humanize result: %d -> %d chars", len(text), len(out))
            return out or text
