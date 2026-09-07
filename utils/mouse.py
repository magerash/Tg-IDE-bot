"""Remote mouse — the wheel, the buttons, and drag.

**Every mouse event in this project goes through this module**, enforced by
`test_every_click_path_uses_the_mouse_module`. With `pyautogui.PAUSE` at 0
(`handlers/input.py`), a bare `pyautogui.click(x, y)` fires the button before the
target window has processed the move; the settles here replaced that blanket
delay, and a caller that goes straight to pyautogui skips them. `D-019`

Three Windows facts drive this module:

1. `mouse_event(MOUSEEVENTF_WHEEL, ...)` ignores the x/y it is handed: Windows
   routes the wheel by *cursor position*, so the cursor must be parked first.
2. `dwData` counts raw wheel units and a notch is WHEEL_DELTA (120), which
   pyautogui passes straight through: `scroll(3)` is 3/120 of a notch.
3. A double click is not an API call — Windows merges two down/up pairs arriving
   within `GetDoubleClickTime` (500ms default). Which is why it can never be two
   HTTP requests: one round trip through this tunnel is ~133ms.
"""
import ctypes
import logging
import time

import pyautogui

from config import (
    MOUSE_CLICK_HOLD, MOUSE_DOUBLE_GAP, MOUSE_DRAG_HOLD, MOUSE_DRAG_STEP_DELAY,
    MOUSE_DRAG_STEPS, MOUSE_MOVE_SETTLE,
)
from utils.window import get_active_window_rect

logger = logging.getLogger("bot.mouse")

WHEEL_DELTA = 120        # one physical notch
MAX_NOTCHES = 30         # a full-throttle hold shouldn't be able to fling a page
SETTLE = 0.03            # let the wheel message leave the queue before moving back

BUTTONS = ("left", "right", "middle")


def double_click_time() -> float:
    """Windows' own double-click window, in seconds. User-configurable: a machine
    set to 200ms would turn every double click into two singles."""
    try:
        return max(0.05, ctypes.windll.user32.GetDoubleClickTime() / 1000.0)
    except Exception:                                   # not Windows, or no user32
        return 0.5


def _button(name: str) -> str:
    """Absent means left (clients omit it). A *wrong* name is an error, never a
    silent left click — that is a context menu that never opened."""
    b = (name or "").strip().lower()
    if not b:
        return "left"
    if b not in BUTTONS:
        raise ValueError(f"button must be one of {BUTTONS}, got {name!r}")
    return b


def click_at(x, y, button: str = "left", double: bool = False) -> dict:
    """Move, let the move land, then click. The only click path in this project.

    MOUSE_MOVE_SETTLE is what PAUSE used to pay for: the window must process
    WM_MOUSEMOVE before the button goes down, or the click lands on a control that
    has not registered the hover — menus open on the move, not the click.

    `double` sends two down/up pairs, the gap clamped to 40% of the OS window —
    never two requests, because that deadline is one the network cannot meet.
    """
    b = _button(button)
    x, y = int(x), int(y)
    pyautogui.moveTo(x, y)
    time.sleep(MOUSE_MOVE_SETTLE)

    gap = min(MOUSE_DOUBLE_GAP, double_click_time() * 0.4)
    for i in range(2 if double else 1):
        pyautogui.mouseDown(button=b)
        time.sleep(MOUSE_CLICK_HOLD)
        pyautogui.mouseUp(button=b)
        if double and i == 0:
            time.sleep(gap)
    logger.debug("click: %s%s at (%d, %d)", b, " double" if double else "", x, y)
    return {"clicked": [x, y], "button": b, "double": bool(double)}


def drag(x1, y1, x2, y2, button: str = "left", steps: int = 0) -> dict:
    """Press at (x1,y1), move to (x2,y2) in steps, release.

    Interpolated on purpose: controls recognise a drag from the stream of
    WM_MOUSEMOVE between press and release, so a single jump drags nothing.

    **The release is in a `finally`.** A held button that never comes up wedges the
    desktop — every move becomes a selection — and the phone cannot see it. `D-018`
    """
    b = _button(button)
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    n = max(1, min(int(steps or MOUSE_DRAG_STEPS), 60))

    pyautogui.moveTo(x1, y1)
    time.sleep(MOUSE_MOVE_SETTLE)
    pyautogui.mouseDown(button=b)
    try:
        time.sleep(MOUSE_DRAG_HOLD)     # a press and a move in the same tick is a click
        for i in range(1, n + 1):
            pyautogui.moveTo(x1 + (x2 - x1) * i // n, y1 + (y2 - y1) * i // n)
            time.sleep(MOUSE_DRAG_STEP_DELAY)
        time.sleep(MOUSE_MOVE_SETTLE)   # let the last move land before the release
    finally:
        pyautogui.mouseUp(button=b)
    logger.debug("drag: %s (%d,%d) -> (%d,%d) in %d steps", b, x1, y1, x2, y2, n)
    return {"from": [x1, y1], "to": [x2, y2], "button": b, "steps": n}


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
        # Windows routes the wheel by the CURSOR POSITION at the moment the event
        # is injected. Until PAUSE was set to 0 this gap came for free; without it
        # the wheel can be stamped with the position the cursor has not left yet,
        # and the scroll goes to the window the operator was looking at before.
        time.sleep(MOUSE_MOVE_SETTLE)
    pyautogui.scroll(n * WHEEL_DELTA)
    if point and restore:
        time.sleep(SETTLE)   # the wheel is already stamped; the cursor may go back
        pyautogui.moveTo(origin[0], origin[1])
    logger.debug("scroll: %+d notches at %s (restore=%s)", n, point, restore)
    return {"notches": n, "at": list(point) if point else None}
