import io
import logging
from telegram import Update

logger = logging.getLogger("bot.chunks")

TG_MSG_LIMIT = 4096


async def send_long_text(update: Update, text: str):
    """Send text, splitting into chunks or as .txt file if too long."""
    if len(text) <= TG_MSG_LIMIT:
        await update.message.reply_text(text)
        return

    # If very long, send as file
    if len(text) > TG_MSG_LIMIT * 3:
        buf = io.BytesIO(text.encode("utf-8"))
        buf.name = "output.txt"
        await update.message.reply_document(document=buf, caption=f"Output ({len(text)} chars)")
        return

    # Split into chunks
    for i in range(0, len(text), TG_MSG_LIMIT):
        chunk = text[i:i + TG_MSG_LIMIT]
        await update.message.reply_text(chunk)
