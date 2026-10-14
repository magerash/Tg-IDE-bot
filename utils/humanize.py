"""Clean raw speech transcripts into prompt-ready text via Groq LLM."""
import logging
import re

import aiohttp

from config import (
    GROQ_API_KEY, HUMANIZE_FALLBACKS, HUMANIZE_MAX_TOKENS, HUMANIZE_MODEL,
    HUMANIZE_REASONING,
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


def _reasoning_for(model: str, spec: str = HUMANIZE_REASONING) -> str | None:
    """Reasoning effort for one model. `spec` is a bare value for every model or
    comma-separated `prefix=value` pairs (first prefix match wins); "off" or an
    empty value means: send no reasoning_effort at all."""
    spec = spec.strip()
    if "=" not in spec:
        value = spec
    else:
        value = ""
        for part in spec.split(","):
            prefix, _, val = part.partition("=")
            if prefix.strip() and model.startswith(prefix.strip()):
                value = val.strip()
                break
    return None if value.lower() in ("", "off") else value


def _max_tokens(text: str) -> int:
    """Output budget from the input length. Russian tokenises at ~2.5 chars per
    token (measured: 289 prompt tokens for ~600 chars), so `len(text)` tokens is
    ~2.5x the input — room for the expanding styles — capped under the OTPM limit."""
    return max(256, min(HUMANIZE_MAX_TOKENS, len(text) + 256))


def _strip_reasoning(text: str) -> str:
    out = _THINK_RE.sub("", text)
    out = _OPEN_THINK_RE.sub("", out)  # unterminated block = truncated thinking
    return out.strip()


async def _call(session, model: str, system: str, text: str,
                reasoning: str | None) -> str:
    max_tokens = _max_tokens(text)
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
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
        choice = body["choices"][0]
        # A reply cut at the budget is not a reply: it would be typed into a
        # terminal as if it were whole, and nothing on the phone could tell.
        if choice.get("finish_reason") == "length":
            raise RuntimeError(
                f"output truncated at {max_tokens} tokens (HUMANIZE_MAX_TOKENS)")
        return (choice["message"].get("content") or "").strip()


async def chat(system: str, text: str) -> str:
    """Run text through the Groq model fallback chain with the given system prompt.
    Raises when every model fails — callers fall back to the original text, but
    must say so: a silent fallback looks exactly like "AI does nothing".
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
            reasoning = _reasoning_for(model)
            logger.debug("LLM request: %d chars, model=%s, reasoning=%s, max_tokens=%d",
                         len(text), model, reasoning, _max_tokens(text))
            try:
                out = await _call(session, model, system, text, reasoning)
            except RuntimeError as e:
                # A model that rejects reasoning_effort is worth one retry without it
                if "reasoning" in str(e).lower():
                    try:
                        out = await _call(session, model, system, text, None)
                    except Exception as e2:
                        errors.append(f"{model} -> {e2}")
                        continue
                else:
                    errors.append(f"{model} -> {e}")
                    logger.warning("LLM model %s failed: %s", model, e)
                    continue
            except Exception as e:
                errors.append(f"{model} -> {e}")
                continue

            out = _strip_reasoning(out)
            if not out:
                errors.append(f"{model} -> empty after stripping reasoning")
                continue
            if model != HUMANIZE_MODEL:
                logger.warning("LLM fell back to %s (primary %s unavailable)",
                               model, HUMANIZE_MODEL)
            logger.debug("LLM result: %d -> %d chars via %s",
                         len(text), len(out), model)
            return out

    raise RuntimeError("Humanize failed: " + "; ".join(errors))


async def humanize(text: str) -> str:
    """Return cleaned transcript. Raises when every model fails."""
    return await chat(_SYSTEM, text)
