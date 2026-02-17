import asyncio
import ctypes
import logging
import time
import pyautogui
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import auth_required, rate_limit
from utils.window import focus_window

logger = logging.getLogger("bot.input")

pyautogui.FAILSAFE = False

# Fix 64-bit pointer truncation for clipboard Win32 calls
_k32 = ctypes.windll.kernel32
_u32 = ctypes.windll.user32
_vp = ctypes.c_void_p
_k32.GlobalAlloc.restype = _k32.GlobalLock.restype = _vp
_k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_k32.GlobalLock.argtypes = _k32.GlobalUnlock.argtypes = _k32.GlobalFree.argtypes = [_vp]
_u32.SetClipboardData.restype = _vp
_u32.SetClipboardData.argtypes = [ctypes.c_uint, _vp]

def _set_clipboard(text: str):
    """Set clipboard text via Win32 API — 64-bit safe with error checks."""
    if not _u32.OpenClipboard(0):
        raise OSError("OpenClipboard failed")
    try:
        _u32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = _k32.GlobalAlloc(0x0002, len(data))
        if not h_mem:
            raise OSError("GlobalAlloc failed")
        p_mem = _k32.GlobalLock(h_mem)
        if not p_mem:
            _k32.GlobalFree(h_mem)
            raise OSError("GlobalLock failed")
        ctypes.memmove(p_mem, data, len(data))
        _k32.GlobalUnlock(h_mem)
        _u32.SetClipboardData(13, h_mem)
    finally:
        _u32.CloseClipboard()

def _type_text(text: str):
    """Type text via clipboard paste — instant, reliable, supports any language."""
    _set_clipboard(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.1)

@auth_required
@rate_limit(1.0)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Type plain text into active window and press Enter."""
    text = update.message.text
    logger.debug("Typing text: %s", text)
    try:
        _type_text(text)
        pyautogui.press("enter")
        await update.message.reply_text(f"Typed: {text}")
        await asyncio.sleep(2)
        from handlers.screen import _grab_to_jpeg
        buf = _grab_to_jpeg()
        await update.message.reply_photo(photo=buf)
    except Exception as e:
        logger.error("text_handler error: %s", e)
        await update.message.reply_text(f"Typing failed: {e}")

@auth_required
@rate_limit(1.0)
async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/key <key> — send special key or combo (e.g. ctrl+c, enter, tab)."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /key <key> [N]\n"
            "Singles: enter tab space esc backspace up down left right\n"
            "Combos: ctrl+c ctrl+v alt+tab\nRepeat: /key backspace 30"
        )
        return

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
@rate_limit(1.0)
async def type_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/type <text> — type text literally (for text starting with /)."""
    if not context.args:
        await update.message.reply_text("Usage: /type <text>\nTypes text + Enter.")
        return
    text = " ".join(context.args)
    logger.debug("/type called: %s", text)
    try:
        _type_text(text)
        pyautogui.press("enter")
        await update.message.reply_text(f"Typed: {text}")
    except Exception as e:
        logger.error("/type error: %s", e)
        await update.message.reply_text(f"Typing failed: {e}")

@auth_required
@rate_limit(1.0)
async def click_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/click x y — mouse click at coordinates."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /click <x> <y>")
        return
    try:
        x, y = int(context.args[0]), int(context.args[1])
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
@rate_limit(1.0)
async def focus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/focus <title> — focus a window by partial title match."""
    if not context.args:
        await update.message.reply_text("Usage: /focus <window title>")
        return
    title = " ".join(context.args)
    logger.debug("/focus called: %s", title)
    success, msg = focus_window(title)
    await update.message.reply_text(msg)
