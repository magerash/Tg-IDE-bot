import logging
import time
import pygetwindow as gw

logger = logging.getLogger("bot.window")


def _activate_window(win):
    """Activate window with minimize/restore fallback for Windows."""
    try:
        win.activate()
    except Exception:
        # Windows blocks .activate() when caller isn't foreground —
        # minimize+restore forces the OS to bring it forward
        if win.isMinimized:
            win.restore()
        else:
            win.minimize()
            time.sleep(0.1)
            win.restore()


def focus_window(title: str) -> tuple[bool, str]:
    """Find window by partial title match and activate it."""
    try:
        matches = gw.getWindowsWithTitle(title)
        if not matches:
            logger.debug("No windows matching '%s'", title)
            return False, f"No window found matching '{title}'"

        win = matches[0]
        _activate_window(win)
        time.sleep(0.3)
        logger.debug("Focused window: %s", win.title)
        return True, f"Focused: {win.title}"
    except Exception as e:
        logger.error("focus_window error: %s", e)
        return False, f"Focus failed: {e}"


def get_active_window_rect() -> tuple[int, int, int, int] | None:
    """Return (left, top, width, height) of active window, or None."""
    try:
        win = gw.getActiveWindow()
        if win is None:
            logger.debug("No active window found")
            return None
        rect = (win.left, win.top, win.width, win.height)
        logger.debug("Active window rect: %s (%s)", rect, win.title)
        return rect
    except Exception as e:
        logger.error("get_active_window_rect error: %s", e)
        return None
