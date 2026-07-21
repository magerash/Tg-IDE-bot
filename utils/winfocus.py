"""Reliable Win32 window activation — SetForegroundWindow with unlock workarounds."""
import ctypes
import logging
import time

logger = logging.getLogger("bot.winfocus")

_u32 = ctypes.windll.user32
_k32 = ctypes.windll.kernel32

SW_MINIMIZE = 6
SW_RESTORE = 9
SW_MAXIMIZE = 3
VK_MENU = 0x12  # Alt
KEYEVENTF_KEYUP = 0x0002


def _is_foreground(hwnd: int) -> bool:
    return _u32.GetForegroundWindow() == hwnd


def force_foreground(hwnd: int) -> bool:
    """Bring hwnd to foreground. Three attempts: Alt-tap, AttachThreadInput, min/restore."""
    try:
        was_zoomed = bool(_u32.IsZoomed(hwnd))
        if _u32.IsIconic(hwnd):
            _u32.ShowWindow(hwnd, SW_RESTORE)

        # 1. Alt tap releases the OS foreground-change lock for this process
        _u32.keybd_event(VK_MENU, 0, 0, 0)
        _u32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        _u32.SetForegroundWindow(hwnd)
        _u32.BringWindowToTop(hwnd)
        time.sleep(0.15)
        if _is_foreground(hwnd):
            return True

        # 2. AttachThreadInput to the current foreground thread, then switch
        fg = _u32.GetForegroundWindow()
        if fg:
            cur_tid = _k32.GetCurrentThreadId()
            fg_tid = _u32.GetWindowThreadProcessId(fg, None)
            if fg_tid and fg_tid != cur_tid:
                _u32.AttachThreadInput(fg_tid, cur_tid, True)
                try:
                    _u32.SetForegroundWindow(hwnd)
                    _u32.BringWindowToTop(hwnd)
                finally:
                    _u32.AttachThreadInput(fg_tid, cur_tid, False)
                time.sleep(0.15)
                if _is_foreground(hwnd):
                    return True

        # 3. Minimize/restore forces Windows to hand over focus; re-maximize if needed
        _u32.ShowWindow(hwnd, SW_MINIMIZE)
        time.sleep(0.1)
        _u32.ShowWindow(hwnd, SW_MAXIMIZE if was_zoomed else SW_RESTORE)
        time.sleep(0.15)
        ok = _is_foreground(hwnd)
        if not ok:
            logger.warning("force_foreground failed for hwnd %s (elevated window?)", hwnd)
        return ok
    except Exception as e:
        logger.error("force_foreground error: %s", e)
        return False
