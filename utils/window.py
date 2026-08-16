import logging
import pygetwindow as gw

from utils.winfocus import force_foreground

logger = logging.getLogger("bot.window")


def _activate_window(win) -> bool:
    """Activate window via Win32 foreground chain; returns real success."""
    return force_foreground(win._hWnd)


def focus_window(title: str) -> tuple[bool, str]:
    """Find window by partial title match and activate it."""
    try:
        matches = gw.getWindowsWithTitle(title)
        if not matches:
            logger.debug("No windows matching '%s'", title)
            return False, f"No window found matching '{title}'"

        win = matches[0]
        ok = _activate_window(win)
        logger.debug("Focused window: %s (ok=%s)", win.title, ok)
        if ok:
            return True, f"Focused: {win.title}"
        return False, f"Focus blocked: {win.title} (admin window?)"
    except Exception as e:
        logger.error("focus_window error: %s", e)
        return False, f"Focus failed: {e}"


def list_windows(limit: int = 30) -> list[str]:
    """Return titles of visible windows (non-empty, deduplicated)."""
    titles: list[str] = []
    seen: set[str] = set()
    try:
        for w in gw.getAllWindows():
            title = (w.title or "").strip()
            if not title or title in seen or not w.visible:
                continue
            seen.add(title)
            titles.append(title)
            if len(titles) >= limit:
                break
    except Exception as e:
        logger.error("list_windows error: %s", e)
    logger.debug("list_windows: %d windows", len(titles))
    return titles


def tail_key(title: str) -> str:
    """Stable part of a retitling window: last two ' - ' segments, lowercased.

    VS Code puts the open file FIRST ('config.py - Tg-IDE-bot - Visual Studio
    Code'), so two titles of the same window share no prefix and neither contains
    the other. Their tail ('Tg-IDE-bot - Visual Studio Code') does not move.
    Returns '' for single-segment titles, which must never match.
    """
    parts = [p.strip() for p in (title or "").split(" - ") if p.strip()]
    return " - ".join(parts[-2:]).lower() if len(parts) >= 2 else ""


def focus_window_exact(title: str) -> tuple[bool, str]:
    """Focus window by exact title; fuzzy fallback for titles that changed since listing."""
    try:
        windows = [w for w in gw.getAllWindows() if (w.title or "").strip()]
        target = next((w for w in windows if w.title == title), None)
        if target is None:
            # Title changed since /win list (VSCode retitles per open file etc.) —
            # match by containment / shared prefix / tail key
            t = title.lower()
            key = tail_key(title)
            target = next(
                (w for w in windows
                 if t in w.title.lower() or w.title.lower() in t
                 or w.title.lower()[:25] == t[:25]
                 or (key and tail_key(w.title) == key)),
                None,
            )
        if target is None:
            return False, f"Window gone: '{title}'"

        ok = _activate_window(target)
        logger.debug("Focused window (exact): %s (ok=%s)", target.title, ok)
        if ok:
            return True, f"Focused: {target.title}"
        return False, f"Focus blocked: {target.title} (admin window?)"
    except Exception as e:
        logger.error("focus_window_exact error: %s", e)
        return False, f"Focus failed: {e}"


def get_active_window_title() -> str:
    """Return title of the currently focused window ('' if none)."""
    try:
        win = gw.getActiveWindow()
        title = (win.title or "").strip() if win else ""
        logger.debug("Active window title: %s", title)
        return title
    except Exception as e:
        logger.error("get_active_window_title error: %s", e)
        return ""


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
