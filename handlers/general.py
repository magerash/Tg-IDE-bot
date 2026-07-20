import logging
import platform
import time
from telegram import Update
from telegram.ext import ContextTypes
from config import VERSION
from utils.auth import auth_required

logger = logging.getLogger("bot.general")
_start_time = time.time()

HELP_TEXT = (
    f"TG-IDE-Bot v{VERSION}\n\n"
    "Screen:\n/screen — Screenshot\n/window — Active window\n/crop — Crop region\n\n"
    "Input:\n/key <k> [N] — Key + repeat\n/type <text> — Type /commands\n"
    "/click x y — Mouse click\n/focus <title> — Focus window\n"
    "/win — List windows, tap to focus\n/code [folder] — Open project in VSCode\n\n"
    "Files:\n/build [dir] — Gradle build\n/build apk — Build + send APK\n"
    "/apk [filter] — Send APK\n/file <path> — Send file\n\n"
    "Tools:\n/sh <cmd> — Shell\n/claude <prompt> — Ask Claude\n"
    "/git — status/log/diff/branch/commit/push/pull/cd\n"
    "/panel — Control panel\n/status — Bot info\n/help — This message\n\n"
    "Plain text → typed + auto-screenshot"
)


@auth_required
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("/start from user %s", update.effective_user.id)
    await update.message.reply_text(f"Welcome! Bot is online.\n\n{HELP_TEXT}")


@auth_required
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("/help called")
    await update.message.reply_text(HELP_TEXT)


@auth_required
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status — bot uptime, version, system info."""
    logger.debug("/status called")
    uptime = int(time.time() - _start_time)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    await update.message.reply_text(
        f"TG-IDE-Bot v{VERSION}\nUptime: {h}h {m}m {s}s\n"
        f"OS: {platform.system()} {platform.release()}\nPython: {platform.python_version()}"
    )
