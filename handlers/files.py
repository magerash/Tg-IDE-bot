import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import auth_required

logger = logging.getLogger("bot.files")


@auth_required
async def apk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stub: /apk — will send latest APK in Phase 3."""
    logger.debug("/apk called (stub)")
    await update.message.reply_text("APK delivery not implemented yet (Phase 3)")


@auth_required
async def file_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stub: /file <path> — will send file in Phase 3."""
    logger.debug("/file called (stub)")
    await update.message.reply_text("File delivery not implemented yet (Phase 3)")
