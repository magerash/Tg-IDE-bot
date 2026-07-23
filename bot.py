import asyncio
import html
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters, ContextTypes,
)
from config import BOT_TOKEN, VERSION, WEB_PORT, WEB_TOKEN, WEBAPP_URL
from handlers.general import start_cmd, help_cmd, status_cmd
from handlers.screen import screen_cmd, window_cmd, crop_cmd
from handlers.input import text_handler, key_cmd, type_cmd, click_cmd, focus_cmd
from handlers.files import build_cmd, apk_cmd, file_cmd
from handlers.shell import sh_cmd
from handlers.claude import claude_cmd
from handlers.git import git_cmd
from handlers.panel import panel_cmd, panel_callback
from handlers.windows import win_cmd, code_cmd, windows_callback
from handlers.project import project_cmd, project_callback

logger = logging.getLogger("bot.main")

_COMMANDS = [
    ("start", start_cmd), ("help", help_cmd), ("status", status_cmd),
    ("screen", screen_cmd), ("window", window_cmd), ("crop", crop_cmd),
    ("key", key_cmd), ("type", type_cmd), ("click", click_cmd), ("focus", focus_cmd),
    ("build", build_cmd), ("apk", apk_cmd), ("file", file_cmd),
    ("sh", sh_cmd), ("claude", claude_cmd), ("git", git_cmd), ("panel", panel_cmd),
    ("win", win_cmd), ("code", code_cmd), ("project", project_cmd),
]


def _build_tg_app():
    app = Application.builder().token(BOT_TOKEN).build()
    for cmd, fn in _COMMANDS:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^p:"))
    app.add_handler(CallbackQueryHandler(windows_callback, pattern="^w:"))
    app.add_handler(CallbackQueryHandler(project_callback, pattern="^pj:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Unhandled exception:", exc_info=context.error)
        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    update.effective_chat.id,
                    f"Bot error: {html.escape(str(context.error))}"[:4000],
                )
            except Exception:
                pass

    app.add_error_handler(error_handler)
    return app


async def run():
    """Run Telegram bot + web dashboard concurrently."""
    tg_app = _build_tg_app()
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    logger.info("Telegram bot started (v%s)", VERSION)

    runner = None
    if WEB_TOKEN or WEBAPP_URL:
        from handlers.web import create_web_app, setup_menu_button
        runner = web.AppRunner(create_web_app())
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", WEB_PORT).start()
        logger.info("Web dashboard on http://0.0.0.0:%d", WEB_PORT)
        await setup_menu_button(tg_app.bot)
        if WEBAPP_URL:
            from utils.tunnel import tunnel_watchdog
            asyncio.create_task(tunnel_watchdog())
    else:
        logger.info("WEB_TOKEN/WEBAPP_URL not set — web dashboard disabled")

    try:
        await asyncio.Event().wait()
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        if runner:
            await runner.cleanup()


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set. Create .env file from .env.example")
        return
    asyncio.run(run())


if __name__ == "__main__":
    main()
