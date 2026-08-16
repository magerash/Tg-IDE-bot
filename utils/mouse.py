"""Remote mouse wheel — scroll the window under a point (RustDesk-style arrows).

Two Windows facts drive this module:

1. `mouse_event(MOUSEEVENTF_WHEEL, ...)` ignores the x/y it is handed unless
   MOUSEEVENTF_MOVE is also set, and Windows routes the wheel message by the
   *cursor position*. So the cursor really has to be parked over the target
   window first — passing coordinates to `pyautogui.scroll(x=, y=)` does nothing.
2. `dwData` counts raw wheel units, and one physical notch is WHEEL_DELTA (120).
   PyAutoGUI passes `clicks` straight through, so `pyautogui.scroll(3)` is 3/120
   of a notch — i.e. nothing moves. Notches must be multiplied by 120.
"""
import logging
import time

import pyautogui

from utils.window import get_active_window_rect

logger = logging.getLogger("bot.mouse")

WHEEL_DELTA = 120        # one physical notch
MAX_NOTCHES = 30         # a full-throttle hold shouldn't be able to fling a page
SETTLE = 0.03            # let the wheel message leave the queue before moving back


def _target_point(x=None, y=None) -> tuple[int, int] | None:
    """Where to park the cursor: explicit point, else centre of the active window."""
    if x is not None and y is not None:
        return int(x), int(y)
    rect = get_active_window_rect()
    if not rect:
        logger.debug("scroll: no active window rect, using current cursor")
        return None
    left, top, w, h = rect
    return left + w // 2, top + h // 2


def scroll_at(notches: int, x=None, y=None, restore: bool = True) -> dict:
    """Scroll `notches` (positive = up) over (x, y) / the active window centre.

    Returns what actually happened, for the caller to log and echo back.
    """
    n = max(-MAX_NOTCHES, min(int(notches), MAX_NOTCHES))
    if n == 0:
        return {"notches": 0, "at": None}

    origin = pyautogui.position()
    point = _target_point(x, y)
    if point:
        pyautogui.moveTo(point[0], point[1])
    pyautogui.scroll(n * WHEEL_DELTA)
    if point and restore:
        # Cursor goes back where the user left it — the wheel message is already
        # stamped with the position it was injected at.
        time.sleep(SETTLE)
        pyautogui.moveTo(origin[0], origin[1])
    logger.debug("scroll: %+d notches at %s (restore=%s)", n, point, restore)
    return {"notches": n, "at": list(point) if point else None}
