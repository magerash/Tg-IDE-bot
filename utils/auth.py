import functools
import logging
import time
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_ID

logger = logging.getLogger("bot.auth")

_cooldowns: dict[str, float] = {}


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


def rate_limit(seconds: float):
    """Decorator: enforce per-command cooldown in seconds."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            key = func.__name__
            now = time.time()
            last = _cooldowns.get(key, 0.0)
            if now - last < seconds:
                remaining = seconds - (now - last)
                logger.debug("Rate limit hit for %s (%.0fs cooldown)", key, seconds)
                await update.message.reply_text(f"Cooldown: wait {remaining:.0f}s")
                return
            _cooldowns[key] = now
            return await func(update, context)

        return wrapper

    return decorator
