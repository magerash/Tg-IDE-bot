import logging
import os
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from config import GIT_DIR
from utils.auth import auth_required, rate_limit
from utils.chunks import send_long_text

logger = logging.getLogger("bot.git")

_git_dir: str = GIT_DIR


@auth_required
@rate_limit(3.0)
async def git_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/git [subcommand] — run git commands in working directory."""
    global _git_dir
    args = list(context.args or [])
    logger.debug("/git called: %s", args)

    # /git cd — switch or show working directory
    if args and args[0] == "cd":
        if len(args) < 2:
            await update.message.reply_text(f"Git dir: {_git_dir}")
            return
        new_dir = " ".join(args[1:])
        if not os.path.isdir(new_dir):
            await update.message.reply_text(f"Not a directory: {new_dir}")
            return
        _git_dir = os.path.abspath(new_dir)
        logger.debug("Git dir changed to: %s", _git_dir)
        await update.message.reply_text(f"Git dir: {_git_dir}")
        return

    # Smart defaults
    if not args:
        args = ["status"]
    elif args[0] == "log" and len(args) == 1:
        args = ["log", "--oneline", "-20"]
    elif args[0] == "diff" and len(args) == 1:
        args = ["diff", "--stat"]

    # Fix commit -m: join everything after -m as one message
    if "commit" in args and "-m" in args:
        m_idx = args.index("-m")
        if m_idx + 1 < len(args):
            msg_parts = args[m_idx + 1:]
            args = args[:m_idx + 1] + [" ".join(msg_parts)]

    cmd = ["git"] + args
    logger.debug("Running: %s in %s", cmd, _git_dir)

    try:
        proc = subprocess.run(
            cmd, cwd=_git_dir,
            capture_output=True, timeout=60,
        )
        raw = proc.stdout + proc.stderr
        try:
            output = raw.decode("utf-8")
        except UnicodeDecodeError:
            output = raw.decode("cp866", errors="replace")
        if not output.strip():
            output = f"(no output, exit code {proc.returncode})"

        header = f"[{_git_dir}]\n"
        await send_long_text(update, header + output)
    except FileNotFoundError:
        logger.error("git not found in PATH")
        await update.message.reply_text("Error: git not found in PATH.")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Git command timed out (60s limit).")
    except Exception as e:
        logger.error("/git error: %s", e)
        await update.message.reply_text(f"Git error: {e}")
