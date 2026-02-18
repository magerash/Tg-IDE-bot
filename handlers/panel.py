import logging
import os
import platform
import subprocess
import time

import pyautogui
from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID, MAX_FILE_SIZE, PROJECT_DIR, VERSION
from handlers.files import _find_apks
from handlers.screen import _grab_to_jpeg
from utils.auth import auth_required
from utils.chunks import send_long_text_to_chat
from utils.window import get_active_window_rect

logger = logging.getLogger("bot.panel")

_start_time = time.time()
_cooldowns: dict[str, float] = {}
COOLDOWN_SEC = 2.0

KEYBOARD = InlineKeyboardMarkup([
    [Btn("Screen", callback_data="p:screen"), Btn("Window", callback_data="p:window")],
    [Btn("Git Status", callback_data="p:git_status"), Btn("Git Log", callback_data="p:git_log"), Btn("Git Diff", callback_data="p:git_diff")],
    [Btn("Build", callback_data="p:build"), Btn("APK", callback_data="p:apk"), Btn("Status", callback_data="p:status")],
    [Btn("Enter", callback_data="p:key_enter"), Btn("Esc", callback_data="p:key_esc"), Btn("Ctrl+C", callback_data="p:key_ctrlc"), Btn("Tab", callback_data="p:key_tab")],
])

_GIT_ARGS = {"status": ["status"], "log": ["log", "--oneline", "-20"], "diff": ["diff", "--stat"]}
_KEY_MAP = {"enter": "enter", "esc": "escape", "ctrlc": ("ctrl", "c"), "tab": "tab"}


@auth_required
async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/panel — show inline keyboard control panel."""
    logger.debug("/panel called")
    await update.message.reply_text("Control Panel", reply_markup=KEYBOARD)


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    user = query.from_user
    if user is None or user.id != ALLOWED_USER_ID:
        await query.answer("Unauthorized", show_alert=True)
        return

    cmd = query.data.removeprefix("p:")
    now = time.time()
    if now - _cooldowns.get(cmd, 0.0) < COOLDOWN_SEC:
        await query.answer("Cooldown...")
        return
    _cooldowns[cmd] = now

    chat_id = query.message.chat_id
    bot = context.bot
    logger.debug("Panel callback: %s", cmd)

    try:
        if cmd == "screen":
            await query.answer("Capturing...")
            await bot.send_photo(chat_id, photo=_grab_to_jpeg())

        elif cmd == "window":
            await query.answer("Capturing...")
            rect = get_active_window_rect()
            if not rect:
                await bot.send_message(chat_id, "No active window detected.")
                return
            left, top, w, h = rect
            if w <= 0 or h <= 0:
                await bot.send_message(chat_id, "Invalid window dimensions.")
                return
            buf = _grab_to_jpeg({"left": left, "top": top, "width": w, "height": h})
            await bot.send_photo(chat_id, photo=buf)

        elif cmd.startswith("git_"):
            await query.answer("Running git...")
            from handlers.git import _git_dir
            git_args = _GIT_ARGS.get(cmd.removeprefix("git_"), ["status"])
            proc = subprocess.run(
                ["git"] + git_args, cwd=_git_dir, capture_output=True, timeout=60,
            )
            raw = proc.stdout + proc.stderr
            try:
                output = raw.decode("utf-8")
            except UnicodeDecodeError:
                output = raw.decode("cp866", errors="replace")
            await send_long_text_to_chat(bot, chat_id, f"[{_git_dir}]\n{output or '(empty)'}")

        elif cmd == "build":
            await query.answer("Building...")
            cwd = PROJECT_DIR or None
            gradlew = os.path.join(cwd, "gradlew.bat") if cwd else "gradlew.bat"
            await bot.send_message(chat_id, f"Building in: {cwd}")
            proc = subprocess.run(
                [gradlew, "assembleDebug"], cwd=cwd,
                capture_output=True, timeout=300, encoding="utf-8", errors="replace",
            )
            out = proc.stdout[-3000:] if len(proc.stdout) > 3000 else proc.stdout
            status = "SUCCESS" if proc.returncode == 0 else "FAILED"
            msg = f"Build {status}\n\n{out}"
            if proc.returncode != 0:
                msg += f"\n{proc.stderr[-1000:]}"
            await bot.send_message(chat_id, msg[:4000])

        elif cmd == "apk":
            await query.answer("Searching APK...")
            apks = _find_apks()
            if not apks:
                await bot.send_message(chat_id, "No APK found.")
                return
            apk_path, size = apks[0], os.path.getsize(apks[0])
            if size > MAX_FILE_SIZE:
                await bot.send_message(chat_id, f"APK too large: {size // 1024 // 1024}MB")
                return
            name = os.path.basename(apk_path)
            with open(apk_path, "rb") as f:
                await bot.send_document(chat_id, document=f, filename=name, caption=f"{name} ({size // 1024}KB)")

        elif cmd == "status":
            await query.answer()
            uptime = int(time.time() - _start_time)
            h, rem = divmod(uptime, 3600)
            m, s = divmod(rem, 60)
            await bot.send_message(chat_id,
                f"TG-IDE-Bot v{VERSION}\nUptime: {h}h {m}m {s}s\n"
                f"OS: {platform.system()} {platform.release()}\nPython: {platform.python_version()}")

        elif cmd.startswith("key_"):
            k = _KEY_MAP.get(cmd.removeprefix("key_"))
            if isinstance(k, tuple):
                pyautogui.hotkey(*k)
            elif k:
                pyautogui.press(k)
            await query.answer(f"Pressed {cmd.removeprefix('key_')}")

        else:
            await query.answer(f"Unknown: {cmd}", show_alert=True)

    except Exception as e:
        logger.error("Panel %s error: %s", cmd, e)
        await query.answer(f"Error: {e}", show_alert=True)
