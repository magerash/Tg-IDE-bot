import logging
import time
import platform
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, VERSION
from utils.auth import auth_required
from handlers.screen import screen_cmd, window_cmd, crop_cmd
from handlers.input import text_handler, key_cmd, type_cmd, click_cmd, focus_cmd
from handlers.files import build_cmd, apk_cmd, file_cmd
from handlers.shell import sh_cmd
from handlers.claude import claude_cmd
from handlers.git import git_cmd
from handlers.panel import panel_cmd, panel_callback

logger = logging.getLogger("bot.main")

_start_time = time.time()

HELP_TEXT = (
    f"TG-IDE-Bot v{VERSION}\n\n"
    "Screen:\n/screen — Screenshot\n/window — Active window\n/crop — Crop region\n\n"
    "Input:\n/key <k> [N] — Key + repeat\n/type <text> — Type /commands\n"
    "/click x y — Mouse click\n/focus <title> — Focus window\n\n"
    "Files:\n/build [dir] — Gradle build\n/apk [filter] — Send APK\n"
    "/file <path> — Send file\n\n"
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
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)

    await update.message.reply_text(
        f"TG-IDE-Bot v{VERSION}\n"
        f"Uptime: {hours}h {minutes}m {seconds}s\n"
        f"OS: {platform.system()} {platform.release()}\n"
        f"Python: {platform.python_version()}"
    )


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set. Create .env file from .env.example")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("screen", screen_cmd))
    app.add_handler(CommandHandler("window", window_cmd))
    app.add_handler(CommandHandler("crop", crop_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("type", type_cmd))
    app.add_handler(CommandHandler("click", click_cmd))
    app.add_handler(CommandHandler("focus", focus_cmd))
    app.add_handler(CommandHandler("build", build_cmd))
    app.add_handler(CommandHandler("apk", apk_cmd))
    app.add_handler(CommandHandler("file", file_cmd))
    app.add_handler(CommandHandler("sh", sh_cmd))
    app.add_handler(CommandHandler("claude", claude_cmd))
    app.add_handler(CommandHandler("git", git_cmd))
    app.add_handler(CommandHandler("panel", panel_cmd))
    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^p:"))

    # Plain text → input handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("Bot started (v%s)", VERSION)
    app.run_polling()


if __name__ == "__main__":
    main()
