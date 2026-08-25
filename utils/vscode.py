"""VS Code keyboard-focus helpers.

Window focus raises the *window*; the caret stays where it was, which after
`code -n` is the editor, not the integrated terminal where Claude Code runs.
Typing blind then lands in a source file — and worse, `ctrl+shift+v` is an
editor binding, so the paste vanishes and every caller still answers "Typed:".
Every "type into VS Code" path has to move the inner focus first.
"""
import logging
import os
import time

from utils.window import get_active_window_title

logger = logging.getLogger("bot.vscode")

VSCODE_HINT = "Visual Studio Code"
PALETTE_WAIT = 0.35    # palette must be up before the query is typed
TERMINAL_WAIT = 0.35   # ...and the terminal focused before the caller types
# A brand-new terminal has to spawn a shell and print its prompt; keystrokes sent
# into the gap are dropped by the pty, which reads as "the button did nothing".
NEW_TERMINAL_WAIT = float(os.getenv("VSCODE_NEW_TERMINAL_WAIT", "1.6"))


def _palette(command: str):
    """Run a VS Code command through the palette.

    Position-/layout-independent: a fixed click cannot work (the window may be
    moved, resized or split), and a keybinding can be rebound — the palette
    entry is the stable name."""
    import pyautogui
    from handlers.input import type_and_enter

    pyautogui.hotkey("ctrl", "shift", "p")
    time.sleep(PALETTE_WAIT)
    type_and_enter(command)  # waits before Enter
    time.sleep(TERMINAL_WAIT)


def focus_vscode_terminal():
    """Move keyboard focus into the existing integrated terminal."""
    _palette("Terminal: Focus on Terminal View")


def new_vscode_terminal():
    """Open a FRESH integrated terminal and leave the caret in it.

    "Focus on Terminal View" lands in whatever terminal was last active — which,
    if it already runs Claude Code, turns `claude` into a chat message to that
    session instead of starting one. A new terminal is always a shell prompt, and
    it also covers a just-opened window that has no terminal at all."""
    _palette("Terminal: Create New Terminal")
    time.sleep(NEW_TERMINAL_WAIT)  # shell prompt must be up before anyone types


def focus_terminal_if_active(new: bool = False) -> tuple[bool, str]:
    """Put the caret in a VS Code integrated terminal when VS Code is foreground.

    `new=True` opens a fresh terminal instead of reusing the active one.
    Returns (focused, message). A non-VS-Code foreground is not an error — the
    caller still types — but it is always reported, never swallowed: typing that
    answers "Typed:" while the text goes to a window that ate it is exactly the
    failure this helper exists to end."""
    title = get_active_window_title()
    if VSCODE_HINT not in title:
        logger.info("terminal focus skipped, active window is %r", title or "(none)")
        return False, f"active window is not VS Code ({title or 'none'})"
    what = "new terminal" if new else "terminal"
    try:
        new_vscode_terminal() if new else focus_vscode_terminal()
        logger.info("%s focused in %r", what, title)
        return True, f"{what} focused in {title}"
    except Exception as e:
        logger.warning("%s focus failed in %r: %s", what, title, e)
        return False, f"{what} focus failed: {e}"
