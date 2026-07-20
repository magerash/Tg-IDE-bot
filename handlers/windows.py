import asyncio
import logging
import os
import subprocess

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID, PROJECTS_ROOT
from utils.auth import auth_required, rate_limit
from utils.window import focus_window_exact, list_windows

logger = logging.getLogger("bot.windows")

# Caches for inline keyboard callbacks (callback_data holds only an index)
_win_cache: list[str] = []
_folder_cache: list[str] = []


@auth_required
@rate_limit(1.0)
async def win_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/win — list open windows, tap to focus."""
    global _win_cache
    logger.debug("/win called")
    _win_cache = await asyncio.to_thread(list_windows)
    if not _win_cache:
        await update.message.reply_text("No windows found.")
        return
    rows = [[Btn(f"{i + 1}. {t[:48]}", callback_data=f"w:f:{i}")]
            for i, t in enumerate(_win_cache)]
    await update.message.reply_text(
        "Open windows — tap to focus:", reply_markup=InlineKeyboardMarkup(rows)
    )


def _list_project_folders() -> list[str]:
    """List subfolders of PROJECTS_ROOT."""
    try:
        return sorted(
            d for d in os.listdir(PROJECTS_ROOT)
            if os.path.isdir(os.path.join(PROJECTS_ROOT, d)) and not d.startswith(".")
        )
    except OSError as e:
        logger.error("PROJECTS_ROOT listing error: %s", e)
        return []


def _open_in_vscode(folder: str) -> tuple[bool, str]:
    """Open/focus a project folder in VSCode via CLI (reuses existing window)."""
    path = os.path.join(PROJECTS_ROOT, folder)
    try:
        subprocess.Popen(f'code -r "{path}"', shell=True)
        logger.debug("VSCode open: %s", path)
        return True, f"VSCode: {folder}"
    except Exception as e:
        logger.error("VSCode open error: %s", e)
        return False, f"VSCode open failed: {e}"


@auth_required
@rate_limit(1.0)
async def code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/code [folder] — open/focus project folder in VSCode by name."""
    global _folder_cache
    folders = await asyncio.to_thread(_list_project_folders)
    if not folders:
        await update.message.reply_text(f"No folders found in {PROJECTS_ROOT}")
        return

    query = " ".join(context.args).lower().strip() if context.args else ""
    logger.debug("/code called: '%s'", query)
    matches = [f for f in folders if query in f.lower()] if query else folders
    exact = [f for f in matches if f.lower() == query]
    if exact:
        matches = exact

    if query and len(matches) == 1:
        _, msg = await asyncio.to_thread(_open_in_vscode, matches[0])
        await update.message.reply_text(msg)
        return

    if not matches:
        matches = folders
        label = f"No match for '{query}'. All folders:"
    else:
        label = "Pick folder:" if query else f"Folders in {PROJECTS_ROOT}:"

    _folder_cache = matches[:30]
    rows = [[Btn(f, callback_data=f"w:c:{i}")] for i, f in enumerate(_folder_cache)]
    await update.message.reply_text(label, reply_markup=InlineKeyboardMarkup(rows))


async def windows_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /win and /code inline keyboard presses (w:f:N / w:c:N)."""
    query = update.callback_query
    user = query.from_user
    if user is None or user.id != ALLOWED_USER_ID:
        await query.answer("Unauthorized", show_alert=True)
        return

    kind, _, idx_s = query.data.removeprefix("w:").partition(":")
    idx = int(idx_s) if idx_s.isdigit() else -1
    logger.debug("windows_callback: %s %d", kind, idx)

    if kind == "f":
        if 0 <= idx < len(_win_cache):
            _, msg = await asyncio.to_thread(focus_window_exact, _win_cache[idx])
            await query.answer(msg[:190])
        else:
            await query.answer("Stale list — run /win again", show_alert=True)
    elif kind == "c":
        if 0 <= idx < len(_folder_cache):
            _, msg = await asyncio.to_thread(_open_in_vscode, _folder_cache[idx])
            await query.answer(msg[:190])
        else:
            await query.answer("Stale list — run /code again", show_alert=True)
