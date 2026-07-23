"""Project picker: /project — show current project, tap to switch."""
import asyncio
import logging

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from utils import project
from utils.auth import auth_required, rate_limit

logger = logging.getLogger("bot.project")

_cache: list[str] = []


def _keyboard(folders: list[str]) -> InlineKeyboardMarkup:
    cur = project.get_name().lower()
    rows = [[Btn(("✅ " if f.lower() == cur else "") + f, callback_data=f"pj:{i}")]
            for i, f in enumerate(folders)]
    return InlineKeyboardMarkup(rows)


@auth_required
@rate_limit(1.0)
async def project_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/project [name] — show current project or switch by name."""
    global _cache
    folders = await asyncio.to_thread(project.list_projects)
    query = " ".join(context.args).lower().strip() if context.args else ""
    logger.debug("/project called: '%s'", query)

    if query:
        matches = [f for f in folders if query in f.lower()]
        exact = [f for f in matches if f.lower() == query]
        if exact:
            matches = exact
        if len(matches) == 1:
            project.set_by_name(matches[0])
            await update.message.reply_text(f"Project: {matches[0]}\n{project.get_dir()}")
            return
        folders = matches or folders

    if not folders:
        await update.message.reply_text("No projects found.")
        return
    _cache = folders[:30]
    await update.message.reply_text(
        f"Current: {project.get_name()}\nTap to switch:",
        reply_markup=_keyboard(_cache),
    )


async def project_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pj:N — switch current project."""
    query = update.callback_query
    user = query.from_user
    if user is None or user.id != ALLOWED_USER_ID:
        await query.answer("Unauthorized", show_alert=True)
        return

    idx_s = query.data.removeprefix("pj:")
    idx = int(idx_s) if idx_s.isdigit() else -1
    if not (0 <= idx < len(_cache)):
        await query.answer("Stale list — run /project again", show_alert=True)
        return

    project.set_by_name(_cache[idx])
    logger.debug("project_callback: switched to %s", _cache[idx])
    await query.answer(f"Project: {_cache[idx]}")
    try:
        await query.edit_message_text(
            f"Current: {project.get_name()}\nTap to switch:",
            reply_markup=_keyboard(_cache),
        )
    except Exception:
        pass  # message unchanged (tapped already-current project)
