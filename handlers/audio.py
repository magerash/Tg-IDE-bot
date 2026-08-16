"""Voice message → text: transcribe TG voice/audio, humanize, act via buttons."""
import asyncio
import logging
import subprocess

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID, HUMANIZE_DEFAULT
from utils.auth import auth_required, rate_limit
from utils.chunks import send_long_text_to_chat
from utils.stt import STTError, transcribe

logger = logging.getLogger("bot.audio")

# Last transcript per chat — inline buttons act on it (callback data max 64B)
# {chat_id: {"clean": str, "raw": str, "showing": "clean"|"raw"}}
_last: dict[int, dict] = {}

_DISPLAY_CAP = 3900  # headroom under TG 4096 message limit


def _kb(showing: str, has_clean: bool) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton("⌨ Type", callback_data="a:type"),
        InlineKeyboardButton("⌨ Type+Enter", callback_data="a:enter"),
        InlineKeyboardButton("🤖 Claude", callback_data="a:claude"),
    ]
    rows = [row]
    if has_clean:
        toggle = (InlineKeyboardButton("📝 Raw", callback_data="a:raw")
                  if showing == "clean" else
                  InlineKeyboardButton("✨ Clean", callback_data="a:clean"))
        rows.append([toggle])
    return InlineKeyboardMarkup(rows)


def _display(text: str) -> str:
    return text if len(text) <= _DISPLAY_CAP else text[:_DISPLAY_CAP] + "…"


@auth_required
@rate_limit(2.0)
async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Voice/audio → download → Whisper → humanize → transcript + buttons."""
    msg = update.message
    media = msg.voice or msg.audio
    if not media:
        return
    logger.debug("Voice received: %ss, %s bytes", media.duration, media.file_size)
    try:
        tg_file = await context.bot.get_file(media.file_id)
        data = bytes(await tg_file.download_as_bytearray())
        note = await msg.reply_text("🎙 Transcribing...")
        raw = await transcribe(data, "voice.ogg")
        if not raw:
            await note.edit_text("🎙 (empty transcript)")
            return

        clean = raw
        if HUMANIZE_DEFAULT:
            from utils.humanize import humanize
            try:
                await note.edit_text("🎙 ✨ Cleaning transcript...")
                clean = await humanize(raw)
            except Exception as e:
                logger.warning("humanize failed, using raw: %s", e)

        has_clean = clean != raw
        _last[msg.chat_id] = {"clean": clean, "raw": raw, "showing": "clean"}
        await note.edit_text(f"🎙 {_display(clean)}", reply_markup=_kb("clean", has_clean))
        if len(clean) > _DISPLAY_CAP:  # full text for copy/reading
            await send_long_text_to_chat(context.bot, msg.chat_id, clean)
    except STTError as e:
        logger.error("audio_handler STT error: %s", e)
        await msg.reply_text(f"STT failed: {e}")
    except Exception as e:
        logger.error("audio_handler error: %s", e)
        await msg.reply_text(f"Audio failed: {e}")


async def audio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a:* buttons — act on stored transcript for this chat."""
    query = update.callback_query
    if update.effective_user is None or update.effective_user.id != ALLOWED_USER_ID:
        await query.answer("Unauthorized")
        return
    action = query.data.split(":", 1)[1]
    chat_id = query.message.chat_id
    entry = _last.get(chat_id)
    if not entry:
        await query.answer("No transcript stored")
        return

    if action in ("raw", "clean"):  # toggle displayed variant
        entry["showing"] = action
        await query.answer(action)
        has_clean = entry["clean"] != entry["raw"]
        icon = "🎙" if action == "clean" else "📝"
        await query.message.edit_text(
            f"{icon} {_display(entry[action])}", reply_markup=_kb(action, has_clean))
        return

    text = entry[entry["showing"]]
    await query.answer(action)
    logger.debug("audio_callback %s: %s", action, text[:80])
    try:
        if action in ("type", "enter"):
            from handlers.input import type_and_enter
            await asyncio.to_thread(type_and_enter, text, action == "enter")
            await context.bot.send_message(chat_id, f"Typed: {text[:200]}")
        elif action == "claude":
            await context.bot.send_message(chat_id, "🤖 Running Claude...")
            proc = await asyncio.to_thread(
                subprocess.run, ["claude", "-p", text],
                capture_output=True, timeout=300,
                encoding="utf-8", errors="replace",
            )
            out = proc.stdout.strip() or proc.stderr.strip() or "(no response)"
            await send_long_text_to_chat(context.bot, chat_id, out)
    except Exception as e:
        logger.error("audio_callback error: %s", e)
        await context.bot.send_message(chat_id, f"Action failed: {e}")
