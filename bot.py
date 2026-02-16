import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, VERSION
from utils.auth import auth_required
from handlers.screen import screen_cmd, window_cmd
from handlers.input import text_handler, key_cmd, type_cmd, click_cmd, focus_cmd
from handlers.files import build_cmd, apk_cmd, file_cmd
from handlers.shell import sh_cmd
from handlers.claude import claude_cmd

logger = logging.getLogger("bot.main")

HELP_TEXT = (
    f"TG-IDE-Bot v{VERSION}\n\n"
    "Commands:\n"
    "/screen  — Screenshot of PC screen\n"
    "/window  — Capture active window\n"
    "/key <k> — Send special key (ctrl+c, enter)\n"
    "/type <text> — Type text literally (/commands)\n"
    "/click x y — Mouse click at coordinates\n"
    "/focus <title> — Focus a window\n"
    "/build   — Run gradle build\n"
    "/apk     — Send latest APK\n"
    "/file <path> — Send any file\n"
    "/sh <cmd> — Run shell command\n"
    "/claude <prompt> — Ask Claude\n"
    "/help    — This message\n\n"
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


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set. Create .env file from .env.example")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("screen", screen_cmd))
    app.add_handler(CommandHandler("window", window_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("type", type_cmd))
    app.add_handler(CommandHandler("click", click_cmd))
    app.add_handler(CommandHandler("focus", focus_cmd))
    app.add_handler(CommandHandler("build", build_cmd))
    app.add_handler(CommandHandler("apk", apk_cmd))
    app.add_handler(CommandHandler("file", file_cmd))
    app.add_handler(CommandHandler("sh", sh_cmd))
    app.add_handler(CommandHandler("claude", claude_cmd))

    # Plain text → input handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("Bot started (v%s)", VERSION)
    app.run_polling()


if __name__ == "__main__":
    main()
