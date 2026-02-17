import logging
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import auth_required, rate_limit
from utils.chunks import send_long_text

logger = logging.getLogger("bot.shell")


@auth_required
@rate_limit(5.0)
async def sh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/sh <command> — run shell command, return stdout."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /sh <command>")
        return

    cmd = " ".join(args)
    logger.debug("/sh called: %s", cmd)

    # Auto-detect PowerShell syntax and route accordingly
    ps_markers = ("ForEach-Object", "Get-", "Select-", "Where-Object",
                  "Measure-Object", "$_", "Write-", "Invoke-", "Set-")
    if any(m in cmd for m in ps_markers):
        run_cmd = ["powershell", "-NoProfile", "-Command", cmd]
        use_shell = False
    else:
        run_cmd = cmd
        use_shell = True

    try:
        proc = subprocess.run(
            run_cmd, shell=use_shell,
            capture_output=True, timeout=60,
        )
        raw = proc.stdout + proc.stderr
        try:
            output = raw.decode("utf-8")
        except UnicodeDecodeError:
            output = raw.decode("cp866", errors="replace")
        if not output.strip():
            output = f"(no output, exit code {proc.returncode})"

        await send_long_text(update, output)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Command timed out (60s limit).")
    except Exception as e:
        logger.error("/sh error: %s", e)
        await update.message.reply_text(f"Shell error: {e}")
