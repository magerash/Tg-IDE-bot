"""Document sent to the bot in chat → saved on the PC → its PATH typed on demand.

The phone's own "attach file" is the shortest path from a note to a Claude Code
session: send it, tap Type+Enter. Mirrors handlers/audio.py — same shape, same
buttons, same rule that the stored item lives per chat because callback_data is
capped at 64 bytes and a Windows path does not fit in it.
"""
import asyncio
import logging
import subprocess

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from utils.auth import auth_required, rate_limit
from utils.chunks import send_long_text_to_chat
from utils.uploads import save_upload

logger = logging.getLogger("bot.upload")

# {chat_id: {"path": str, "name": str}} — buttons act on the last file per chat
_last: dict[int, dict] = {}

# Telegram's own limit on what a bot may DOWNLOAD. Not ours to raise, so say it
# out loud instead of failing with a bare API error.
TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024


def _kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⌨ Type", callback_data="f:type"),
        InlineKeyboardButton("⌨ Type+Enter", callback_data="f:enter"),
        InlineKeyboardButton("🤖 Claude", callback_data="f:claude"),
    ]])


@auth_required
@rate_limit(2.0)
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Any document → save under %TEMP%/tgbot_upload, offer to type its path."""
    msg = update.message
    doc = msg.document
    if not doc:
        return
    size = doc.file_size or 0
    logger.debug("Document received: %r %s bytes", doc.file_name, size)
    if size > TG_DOWNLOAD_LIMIT:
        await msg.reply_text(
            f"📎 {doc.file_name} is {size // (1024 * 1024)}MB — Telegram lets a bot "
            f"download at most {TG_DOWNLOAD_LIMIT // (1024 * 1024)}MB. "
            "Use the Mini App 📎 button instead.")
        return
    try:
        note = await msg.reply_text("📎 Saving...")
        tg_file = await context.bot.get_file(doc.file_id)
        data = bytes(await tg_file.download_as_bytearray())
        path = await asyncio.to_thread(save_upload, data, doc.file_name or "")
        _last[msg.chat_id] = {"path": path, "name": doc.file_name or path}
        await note.edit_text(
            f"📎 {doc.file_name} ({max(1, len(data) // 1024)}KB)\n<code>{path}</code>",
            parse_mode="HTML", reply_markup=_kb())
    except Exception as e:
        logger.error("document_handler error: %s", e)
        await msg.reply_text(f"Attach failed: {e}")


async def document_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """f:* buttons — type the stored path, or hand it to claude -p."""
    query = update.callback_query
    if update.effective_user is None or update.effective_user.id != ALLOWED_USER_ID:
        await query.answer("Unauthorized")
        return
    action = query.data.split(":", 1)[1]
    chat_id = query.message.chat_id
    entry = _last.get(chat_id)
    if not entry:
        await query.answer("No file stored")
        return
    path, name = entry["path"], entry["name"]
    await query.answer(action)
    try:
        if action in ("type", "enter"):
            # type_and_enter is the ONLY place paste and Enter are sequenced —
            # an Enter of our own would land inside the paste and become a newline.
            from handlers.input import type_and_enter
            from utils.uploads import path_token
            await asyncio.to_thread(type_and_enter, path_token(path).rstrip(),
                                    action == "enter")
            await context.bot.send_message(chat_id, f"Typed path: {name}")
        elif action == "claude":
            await context.bot.send_message(chat_id, "🤖 Running Claude...")
            proc = await asyncio.to_thread(
                subprocess.run, ["claude", "-p", path],
                capture_output=True, timeout=300,
                encoding="utf-8", errors="replace",
            )
            out = proc.stdout.strip() or proc.stderr.strip() or "(no response)"
            await send_long_text_to_chat(context.bot, chat_id, out)
    except Exception as e:
        logger.error("document_callback error: %s", e)
        await context.bot.send_message(chat_id, f"Action failed: {e}")
