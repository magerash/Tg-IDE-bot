"""Improve typed text into a better prompt via Groq LLM (+ optional twin persona)."""
import logging
import os
import re

from config import HAE_PROFILE_DIR
from utils.humanize import chat

logger = logging.getLogger("bot.improve")

_COMMON = (
    "\nRules:\n"
    "- Preserve verbatim: technical terms, file paths, commands, code, names, numbers.\n"
    "- Keep the author's meaning and intent. Never add your own ideas or invent scope.\n"
    "- Output ONLY the rewritten text — no preamble, no quotes, no commentary."
)

STYLES = {
    "structured": (
        "You rewrite rough notes into a clear, well-structured prompt for a coding "
        "agent. State the goal first, then context, then constraints. Keep the "
        "author's language(s) exactly as written (Russian stays Russian, English "
        "stays English, mixed stays mixed)." + _COMMON
    ),
    "detailed": (
        "You expand rough notes into a detailed task spec for a coding agent: goal, "
        "explicit steps, acceptance criteria, and edge cases — all derived strictly "
        "from what the text says or implies. Keep the author's language(s) exactly "
        "as written." + _COMMON
    ),
    "concise": (
        "You tighten verbose text into its shortest clear form. Keep every technical "
        "detail and the author's language(s) exactly as written; drop only "
        "repetition and filler." + _COMMON
    ),
    "translate": (
        "You rewrite the text as a clear English prompt for a coding agent. "
        "Translate Russian or mixed input into natural technical English." + _COMMON
    ),
}

_TWIN_HEADER = (
    "Operator profile — background on the person whose text you will rewrite. "
    "Use it ONLY to match how they structure and phrase things. Never quote or "
    "copy sentences from this profile into the output, and never turn its "
    "principles into tasks, constraints or requirements of the rewritten text:\n"
)
_TWIN_FOOTER = (
    "\n\n--- End of profile. The profile being in English does NOT set the "
    "output language — the language rule in the instructions below wins. "
    "Your actual instructions: ---\n\n"
)

_twin_cache = {"key": None, "text": None}

_CYRILLIC = re.compile(r"[а-яё]", re.I)
_LETTERS = re.compile(r"[a-zа-яё]", re.I)


def _lang_hint(text: str) -> str | None:
    """Explicit output-language line for mostly-Russian input. Instructions alone
    lose: a 6KB English twin persona reliably drags qwen3.6 into English."""
    letters = _LETTERS.findall(text)
    if letters and len(_CYRILLIC.findall(text)) / len(letters) > 0.5:
        return ("\n\nOutput language: Russian — the input is Russian. "
                "Keep code, commands and technical terms as written.")
    return None


def _twin_context() -> str | None:
    """persona.md + principles.md from the HAE profile dir, cached by mtime.
    None when the profile is missing/empty — twin is unavailable, not an error."""
    key = []
    for name in ("persona.md", "principles.md"):
        try:
            key.append((name, os.path.getmtime(os.path.join(HAE_PROFILE_DIR, name))))
        except OSError:
            pass
    key = tuple(key)
    if key and _twin_cache["key"] == key:
        return _twin_cache["text"]
    parts = []
    for name, _ in key:
        try:
            with open(os.path.join(HAE_PROFILE_DIR, name), encoding="utf-8") as f:
                text = f.read().strip()
        except OSError:
            continue
        if text:
            parts.append(text)
    result = "\n\n".join(parts) or None
    _twin_cache.update(key=key, text=result)
    return result


async def improve(text: str, style: str, twin: bool = False) -> tuple[str, bool]:
    """Return (improved_text, twin_used). Raises when every model fails —
    caller keeps the original text but must report the failure loudly."""
    system = STYLES.get(style) or STYLES["structured"]
    twin_used = False
    if twin:
        ctx = _twin_context()
        if ctx:
            # Profile FIRST, style rules LAST — the recency-weighted small model
            # otherwise answers in the persona's English and copies its
            # principles into the output as fake "constraints".
            system = _TWIN_HEADER + ctx + _TWIN_FOOTER + system
            twin_used = True
        else:
            logger.warning("Improve: twin requested but profile empty/missing at %s",
                           HAE_PROFILE_DIR)
    if style != "translate":
        hint = _lang_hint(text)
        if hint:
            system += hint
    out = await chat(system, text)
    logger.debug("Improve(%s, twin=%s): %d -> %d chars",
                 style, twin_used, len(text), len(out))
    return out, twin_used
