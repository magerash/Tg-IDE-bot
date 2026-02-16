import logging
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import auth_required
from utils.chunks import send_long_text

logger = logging.getLogger("bot.claude")


@auth_required
async def claude_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/claude <prompt> — run claude -p query and return text output."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /claude <prompt>")
        return

    prompt = " ".join(args)
    logger.debug("/claude called: %s", prompt)
    await update.message.reply_text("Asking Claude...")

    try:
        proc = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        output = proc.stdout.strip()
        if not output:
            output = proc.stderr.strip() or "(no response)"

        await send_long_text(update, output)
        logger.debug("/claude response sent (%d chars)", len(output))
    except FileNotFoundError:
        await update.message.reply_text("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Claude timed out (2 min limit).")
    except Exception as e:
        logger.error("/claude error: %s", e)
        await update.message.reply_text(f"Claude error: {e}")
