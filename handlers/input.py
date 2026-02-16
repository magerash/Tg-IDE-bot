import logging
import pyautogui
from telegram import Update
from telegram.ext import ContextTypes
from config import TYPING_INTERVAL
from utils.auth import auth_required
from utils.window import focus_window

logger = logging.getLogger("bot.input")

pyautogui.FAILSAFE = False


def _set_clipboard(text: str):
    """Set clipboard text via Win32 API — no window creation, no focus steal."""
    import ctypes
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard(0)
    user32.EmptyClipboard()
    data = text.encode("utf-16-le") + b"\x00\x00"
    h_mem = kernel32.GlobalAlloc(0x0002, len(data))
    p_mem = kernel32.GlobalLock(h_mem)
    ctypes.memmove(p_mem, data, len(data))
    kernel32.GlobalUnlock(h_mem)
    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    user32.CloseClipboard()


def _type_text(text: str):
    """Type text via clipboard paste — instant, reliable, supports any language."""
    _set_clipboard(text)
    pyautogui.hotkey("ctrl", "v")
    import time
    time.sleep(0.1)


@auth_required
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Type plain text into active window and press Enter."""
    text = update.message.text
    logger.debug("Typing text: %s", text)
    try:
        _type_text(text)
        pyautogui.press("enter")
        await update.message.reply_text(f"Typed: {text}")
    except Exception as e:
        logger.error("text_handler error: %s", e)
        await update.message.reply_text(f"Typing failed: {e}")


@auth_required
async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/key <key> — send special key or combo (e.g. ctrl+c, enter, tab)."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /key <key>\n\n"
            "Singles: enter, tab, space, esc, backspace, delete, "
            "up, down, left, right, home, end, pageup, pagedown, "
            "insert, f1-f12, y, n\n\n"
            "Combos: ctrl+c, ctrl+v, ctrl+z, shift+tab, "
            "alt+tab, ctrl+shift+esc, ctrl+a\n\n"
            "Repeat: /key backspace 30"
        )
        return

    # Parse repeat count: last arg may be a number
    repeat = 1
    if len(args) >= 2 and args[-1].isdigit():
        repeat = min(int(args[-1]), 200)
        key_str = " ".join(args[:-1]).lower().strip()
    else:
        key_str = " ".join(args).lower().strip()
    logger.debug("/key called: %s x%d", key_str, repeat)

    try:
        parts = key_str.split("+")
        for _ in range(repeat):
            if len(parts) > 1:
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(parts[0])
        label = f"Pressed: {key_str}" + (f" x{repeat}" if repeat > 1 else "")
        await update.message.reply_text(label)
    except Exception as e:
        logger.error("/key error: %s", e)
        await update.message.reply_text(f"Key press failed: {e}")


@auth_required
async def type_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/type <text> — type text literally (for text starting with /)."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /type <text>\nTypes text + Enter. Use for /commands in terminal.")
        return

    text = " ".join(args)
    logger.debug("/type called: %s", text)
    try:
        _type_text(text)
        pyautogui.press("enter")
        await update.message.reply_text(f"Typed: {text}")
    except Exception as e:
        logger.error("/type error: %s", e)
        await update.message.reply_text(f"Typing failed: {e}")


@auth_required
async def click_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/click x y — mouse click at coordinates."""
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Usage: /click <x> <y>")
        return

    try:
        x, y = int(args[0]), int(args[1])
    except ValueError:
        await update.message.reply_text("Coordinates must be integers.")
        return

    logger.debug("/click at (%d, %d)", x, y)
    try:
        pyautogui.click(x, y)
        await update.message.reply_text(f"Clicked: ({x}, {y})")
    except Exception as e:
        logger.error("/click error: %s", e)
        await update.message.reply_text(f"Click failed: {e}")


@auth_required
async def focus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/focus <title> — focus a window by partial title match."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /focus <window title>")
        return

    title = " ".join(args)
    logger.debug("/focus called: %s", title)
    success, msg = focus_window(title)
    await update.message.reply_text(msg)
