import asyncio
import ctypes
import logging
import threading
import time
import pyautogui
from telegram import Update
from telegram.ext import ContextTypes
from config import (
    TYPE_ENTER_DELAY, TYPE_PASTE_HOTKEY, TYPE_TERMINAL_HINTS,
    TYPE_TERMINAL_PASTE_HOTKEY, TYPE_TERMINAL_PROCS,
)
from utils.auth import auth_required, rate_limit
from utils.window import (
    focus_window, get_active_window_process, get_active_window_title,
)

logger = logging.getLogger("bot.input")
_input_lock = threading.Lock()

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

def _stuck_modifiers() -> list[str]:
    """Modifier keys Windows still believes are held down.

    Every typing path ends in Ctrl+V, so one modifier left down by an earlier
    hotkey (Auto = Shift+Tab x3, an Alt tap from force_foreground) silently turns
    the paste into Ctrl+Shift+V / Ctrl+Alt+V and nothing arrives.
    """
    held = []
    for name, vk in (("ctrl", 0x11), ("shift", 0x10), ("alt", 0x12),
                     ("winleft", 0x5B), ("winright", 0x5C)):
        if _u32.GetAsyncKeyState(vk) & 0x8000:
            held.append(name)
    return held


# Virtual-key codes, so a keystroke never depends on the active layout.
# pyautogui maps a character to a key with VkKeyScanW, which asks the CURRENT
# keyboard layout: under Russian (0x419) VkKeyScanW('v') is -1 and pyautogui
# silently sends nothing. ctrl+shift+v then delivers Ctrl and Shift and no V, so
# the paste never happens; ctrl+shift+p never opens the command palette; and
# pyautogui.write drops every latin letter while digits and '-' still arrive
# (measured 2026-08-31: "echo TGBOT-MARKER-42" reached a console as "--42").
# A VK code is the same number in every layout, so this table is the fix.
_VK = {
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "menu": 0x12,
    "win": 0x5B, "winleft": 0x5B, "winright": 0x5C,
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
}
_VK.update({c: 0x41 + i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")})
_VK.update({str(d): 0x30 + d for d in range(10)})
_VK.update({f"f{i}": 0x6F + i for i in range(1, 13)})
# Keys on the extended part of the keyboard need the flag, or Windows delivers
# the numpad twin instead (an arrow becomes a digit under NumLock).
_VK_EXTENDED = {0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x26, 0x28, 0x25, 0x27}
_KEYEVENTF_EXTENDEDKEY, _KEYEVENTF_KEYUP = 0x0001, 0x0002


def press_keys(*names: str) -> bool:
    """Press a key or combo by virtual-key code. True if it was sent that way.

    Falls back to pyautogui for anything not in the table — better a
    layout-dependent keystroke than none.
    """
    codes = [_VK.get(str(n).strip().lower()) for n in names]
    if not codes or any(c is None for c in codes):
        logger.debug("no VK for %s, falling back to pyautogui", names)
        if len(names) > 1:
            pyautogui.hotkey(*names)
        else:
            pyautogui.press(names[0])
        return False
    for c in codes:
        _u32.keybd_event(c, 0, _KEYEVENTF_EXTENDEDKEY if c in _VK_EXTENDED else 0, 0)
    for c in reversed(codes):
        flags = _KEYEVENTF_KEYUP | (_KEYEVENTF_EXTENDEDKEY if c in _VK_EXTENDED else 0)
        _u32.keybd_event(c, 0, flags, 0)
    return True


def paste_hotkey_for(title: str, proc: str = "") -> tuple[str, ...]:
    """Which paste keystroke this window actually honours.

    Claude Code binds Ctrl+V to "paste image from clipboard", so inside a terminal
    running it a text Ctrl+V does nothing at all — the key arrives (the command
    palette opens on Ctrl+Shift+P), the clipboard holds the text, and the prompt
    stays empty. Ctrl+Shift+V is the terminal's own paste and works there. Plain
    apps (Notepad, browsers) get Ctrl+V, since Ctrl+Shift+V means nothing to them.

    The verdict comes from the owning PROCESS first. A terminal retitles itself to
    the program inside it, so Claude Code in Windows Terminal is called
    '✳ Claude Code' and matches no title hint — which is how a paste into the
    one target this bot exists for went back to being a silent no-op. Titles stay
    as a fallback for when the process name is unavailable.
    """
    if (proc or "").lower() in TYPE_TERMINAL_PROCS:
        combo = TYPE_TERMINAL_PASTE_HOTKEY
    else:
        low = (title or "").lower()
        terminal = any(hint in low for hint in TYPE_TERMINAL_HINTS)
        combo = TYPE_TERMINAL_PASTE_HOTKEY if terminal else TYPE_PASTE_HOTKEY
    return tuple(part.strip() for part in combo.split("+") if part.strip())


def _type_text(text: str, paste_keys: tuple[str, ...] | None = None) -> tuple[str, str]:
    """Type text via clipboard paste — instant, reliable, supports any language.

    Returns (title, process) of the window that actually received it. The caller
    aimed at nothing: whatever is foreground gets the text, and on a busy desktop
    that is not always what the operator was looking at. Reporting the real target
    is what turns a lost message into a visible one.
    """
    with _input_lock:
        held = _stuck_modifiers()
        if held:
            logger.warning("Releasing stuck modifiers before paste: %s", held)
            for key in held:
                pyautogui.keyUp(key)
        title = get_active_window_title()
        proc = get_active_window_process()
        # paste_keys overrides the window rule for a control that is neither: the
        # VS Code command palette lives in a window titled "Visual Studio Code", so
        # the rule hands it ctrl+shift+v — which the quick input does not honour.
        # The command name then never arrives and the palette hop silently no-ops.
        keys = paste_keys or paste_hotkey_for(title, proc)
        logger.debug("Typing %d chars into '%s' [%s] via %s",
                     len(text), title, proc or "?", "+".join(keys))
        _set_clipboard(text)
        press_keys(*keys)
        time.sleep(0.1)
        return title, proc


def type_and_enter(text: str, enter: bool = True,
                   paste_keys: tuple[str, ...] | None = None) -> tuple[str, str]:
    """Paste text, then submit it. The ONLY place these two are sequenced.

    The wait between them is the whole point: Claude Code (and any TUI doing
    bracketed-paste detection) swallows an Enter that arrives while the paste is
    still being assembled, turning submit into a newline. The result is text
    stranded in the input box while every caller reports "Typed: ...".
    """
    target = _type_text(text, paste_keys)
    if enter:
        time.sleep(TYPE_ENTER_DELAY)
        press_keys("enter")
    return target

@auth_required
@rate_limit(1.0)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Type plain text into active window and press Enter."""
    text = update.message.text
    logger.debug("Typing text: %s", text)
    try:
        await asyncio.to_thread(type_and_enter, text)
        await update.message.reply_text(f"Typed: {text}")
        await asyncio.sleep(2)
        from handlers.screen import _grab_to_jpeg
        buf = await asyncio.to_thread(_grab_to_jpeg)
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
        def _do_keys():
            with _input_lock:
                for _ in range(repeat):
                    press_keys(*parts)
        await asyncio.to_thread(_do_keys)
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
        await asyncio.to_thread(type_and_enter, text)
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
        await asyncio.to_thread(pyautogui.click, x, y)
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
    success, msg = await asyncio.to_thread(focus_window, title)
    await update.message.reply_text(msg)
