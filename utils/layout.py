"""Keyboard layout of the foreground window — read it, and switch it.

Worth its own module because the layout is not cosmetic here: it silently broke
every typing path once (v0.20.1). `pyautogui` resolves a character through the
ACTIVE layout, so under Russian `VkKeyScanW('v')` is -1 and the key is never
sent. Typing now goes out as virtual-key codes and no longer cares — but the
operator still does: what lands in a remote terminal is whatever the target
window's layout produces, and a wrong layout is invisible from a phone.
"""
import ctypes
import logging
import time
from ctypes import wintypes

logger = logging.getLogger("bot.layout")

_u32 = ctypes.windll.user32
_k32 = ctypes.windll.kernel32

WM_INPUTLANGCHANGEREQUEST = 0x0050
_LOCALE_SISO639LANGNAME = 0x0059


def _langid(hkl: int) -> int:
    """The language half of an HKL. The high half is the physical layout."""
    return hkl & 0xFFFF


def _short_name(langid: int) -> str:
    """'ru' -> 'RU'. Falls back to the hex id, which is still a usable label."""
    buf = ctypes.create_unicode_buffer(16)
    if _k32.GetLocaleInfoW(langid, _LOCALE_SISO639LANGNAME, buf, 16):
        return buf.value.upper()
    return f"{langid:#06x}"


def _foreground() -> tuple[int, int]:
    """(hwnd, hkl) of the window that will receive the next keystroke."""
    hwnd = _u32.GetForegroundWindow()
    if not hwnd:
        return 0, 0
    tid = _u32.GetWindowThreadProcessId(hwnd, None)
    return hwnd, _u32.GetKeyboardLayout(tid)


def list_layouts() -> list[dict]:
    """Installed layouts, in the order Windows cycles them."""
    n = _u32.GetKeyboardLayoutList(0, None)
    arr = (ctypes.c_void_p * max(n, 1))()
    _u32.GetKeyboardLayoutList(n, arr)
    out, seen = [], set()
    for h in arr[:n]:
        lang = _langid(int(h or 0))
        if not lang or lang in seen:
            continue
        seen.add(lang)
        out.append({"lang": lang, "name": _short_name(lang), "hkl": int(h)})
    return out


def current() -> dict:
    """Layout of the foreground window plus everything installed."""
    hwnd, hkl = _foreground()
    lang = _langid(hkl)
    title = ""
    if hwnd:
        buf = ctypes.create_unicode_buffer(256)
        _u32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value
    return {
        "lang": lang,
        "name": _short_name(lang) if lang else "?",
        "window": title,
        "layouts": list_layouts(),
    }


def switch(lang: int | None = None) -> tuple[bool, str]:
    """Switch the foreground window's layout. `lang` omitted = next installed one.

    Sent as WM_INPUTLANGCHANGEREQUEST to the foreground window, not by faking
    Alt+Shift: the shortcut is user-configurable (and often disabled), while the
    message is what Windows itself posts. Windows keeps the layout per window, so
    it must go to the window that will receive the typing, not to us.
    """
    hwnd, hkl = _foreground()
    if not hwnd:
        return False, "no foreground window"
    installed = list_layouts()
    if not installed:
        return False, "no layouts installed"

    if lang is None:
        langs = [it["lang"] for it in installed]
        cur = _langid(hkl)
        nxt = langs[(langs.index(cur) + 1) % len(langs)] if cur in langs else langs[0]
        target = next(it for it in installed if it["lang"] == nxt)
    else:
        target = next((it for it in installed if it["lang"] == lang), None)
        if target is None:
            return False, f"layout {lang:#06x} is not installed"

    _u32.PostMessageW(wintypes.HWND(hwnd), WM_INPUTLANGCHANGEREQUEST,
                      wintypes.WPARAM(0), ctypes.c_void_p(target["hkl"]))
    # Verify instead of trusting: PostMessage cannot fail loudly, and a window
    # that ignores the request would leave the UI showing a layout that is not
    # actually active — the one thing this indicator exists to prevent.
    for _ in range(10):
        time.sleep(0.05)
        if _langid(_foreground()[1]) == target["lang"]:
            logger.info("layout -> %s in %r", target["name"], hwnd)
            return True, target["name"]
    logger.warning("layout switch to %s not confirmed", target["name"])
    return False, f"{target['name']} requested, window did not switch"
