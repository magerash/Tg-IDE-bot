import functools
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_ID

logger = logging.getLogger("bot.auth")


def auth_required(func):
    """Decorator: reject any user except ALLOWED_USER_ID."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None or user.id != ALLOWED_USER_ID:
            uid = user.id if user else "unknown"
            logger.warning("Unauthorized access attempt from user %s", uid)
            await update.message.reply_text("Unauthorized.")
            return
        logger.debug("Auth OK for user %s -> %s", user.id, func.__name__)
        return await func(update, context)

    return wrapper
