"""Speech-to-text via Groq Whisper API (accepts ogg/opus/webm/wav directly)."""
import logging

import aiohttp

from config import GROQ_API_KEY, STT_MODEL

logger = logging.getLogger("bot.stt")

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # Groq per-file limit


class STTError(Exception):
    pass


async def transcribe(data: bytes, filename: str = "voice.ogg") -> str:
    """Send audio bytes to Groq Whisper, return transcript text."""
    if not GROQ_API_KEY:
        raise STTError("GROQ_API_KEY not set — get a free key at console.groq.com and add to .env")
    if len(data) > MAX_AUDIO_SIZE:
        raise STTError(f"Audio too large ({len(data) // 1024 // 1024}MB, limit 25MB)")
    if not data:
        raise STTError("Empty audio")

    form = aiohttp.FormData()
    form.add_field("file", data, filename=filename, content_type="application/octet-stream")
    form.add_field("model", STT_MODEL)
    form.add_field("response_format", "json")

    logger.debug("STT request: %s, %d bytes, model=%s", filename, len(data), STT_MODEL)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            GROQ_URL, data=form,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200:
                msg = body.get("error", {}).get("message", str(body))[:300]
                logger.error("STT API error %d: %s", resp.status, msg)
                raise STTError(f"STT API error {resp.status}: {msg}")
            text = (body.get("text") or "").strip()
            logger.debug("STT result: %d chars", len(text))
            return text
