"""Voice message → text: transcribe TG voice/audio, act on result via buttons."""
import asyncio
import logging
import subprocess

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from utils.auth import auth_required, rate_limit
from utils.chunks import send_long_text_to_chat
from utils.stt import STTError, transcribe

logger = logging.getLogger("bot.audio")

# Last transcript per chat — inline buttons act on it (callback data max 64B)
_last: dict[int, str] = {}

_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("⌨ Type", callback_data="a:type"),
    InlineKeyboardButton("⌨ Type+Enter", callback_data="a:enter"),
    InlineKeyboardButton("🤖 Claude", callback_data="a:claude"),
]])


@auth_required
@rate_limit(2.0)
async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Voice/audio message → download → Groq Whisper → transcript + action buttons."""
    msg = update.message
    media = msg.voice or msg.audio
    if not media:
        return
    logger.debug("Voice received: %ss, %s bytes", media.duration, media.file_size)
    try:
        tg_file = await context.bot.get_file(media.file_id)
        data = bytes(await tg_file.download_as_bytearray())
        note = await msg.reply_text("🎙 Transcribing...")
        text = await transcribe(data, "voice.ogg")
        if not text:
            await note.edit_text("🎙 (empty transcript)")
            return
        _last[msg.chat_id] = text
        await note.edit_text(f"🎙 {text}", reply_markup=_KB)
    except STTError as e:
        logger.error("audio_handler STT error: %s", e)
        await msg.reply_text(f"STT failed: {e}")
    except Exception as e:
        logger.error("audio_handler error: %s", e)
        await msg.reply_text(f"Audio failed: {e}")


async def audio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a:* buttons — act on last transcript for this chat."""
    query = update.callback_query
    if update.effective_user is None or update.effective_user.id != ALLOWED_USER_ID:
        await query.answer("Unauthorized")
        return
    action = query.data.split(":", 1)[1]
    chat_id = query.message.chat_id
    text = _last.get(chat_id, "")
    if not text:
        await query.answer("No transcript stored")
        return
    await query.answer(action)
    logger.debug("audio_callback %s: %s", action, text[:80])
    try:
        if action in ("type", "enter"):
            import pyautogui
            from handlers.input import _type_text
            await asyncio.to_thread(_type_text, text)
            if action == "enter":
                await asyncio.to_thread(pyautogui.press, "enter")
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
