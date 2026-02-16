import logging
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import auth_required
from utils.chunks import send_long_text

logger = logging.getLogger("bot.shell")


@auth_required
async def sh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/sh <command> — run shell command, return stdout."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /sh <command>")
        return

    cmd = " ".join(args)
    logger.debug("/sh called: %s", cmd)

    try:
        proc = subprocess.run(
            cmd, shell=True,
            capture_output=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        output = proc.stdout + proc.stderr
        if not output.strip():
            output = f"(no output, exit code {proc.returncode})"

        await send_long_text(update, output)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Command timed out (60s limit).")
    except Exception as e:
        logger.error("/sh error: %s", e)
        await update.message.reply_text(f"Shell error: {e}")
