"""Windows clipboard image support: put an image on the clipboard for Ctrl+V paste.

Sets TWO formats in one session so any target recognises it:
  - CF_DIB (legacy bitmap) — Paint, classic Win32 apps
  - registered "PNG" format — Claude Code, Electron/VS Code, modern apps
Legacy CF_DIB alone was not recognised by Claude Code's image paste → image dropped.
"""
import ctypes
import io
import logging

from PIL import Image

logger = logging.getLogger("bot.clipimg")

CF_DIB = 8
GMEM_MOVEABLE = 0x0002


def _alloc_global(data: bytes):
    """Copy bytes into a moveable global buffer, return the HGLOBAL handle."""
    k32 = ctypes.windll.kernel32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        logger.error("GlobalAlloc failed (%d bytes)", len(data))
        return None
    p = k32.GlobalLock(h)
    if not p:
        logger.error("GlobalLock failed")
        return None
    ctypes.memmove(p, data, len(data))
    k32.GlobalUnlock(h)
    return h


def set_clipboard_image(data: bytes) -> bool:
    """Convert image bytes to DIB + PNG and place both on the Windows clipboard."""
    img = Image.open(io.BytesIO(data))

    # DIB (BMP minus the 14-byte BITMAPFILEHEADER) — clipboard wants raw DIB
    bbuf = io.BytesIO()
    img.convert("RGB").save(bbuf, "BMP")
    dib = bbuf.getvalue()[14:]

    # PNG (preserve alpha if present) — the format modern apps actually read
    pbuf = io.BytesIO()
    img.save(pbuf, "PNG")
    png = pbuf.getvalue()

    u32 = ctypes.windll.user32
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    u32.RegisterClipboardFormatW.restype = ctypes.c_uint

    png_fmt = u32.RegisterClipboardFormatW("PNG")

    if not u32.OpenClipboard(None):
        logger.error("OpenClipboard failed")
        return False
    try:
        u32.EmptyClipboard()
        set_any = False
        for fmt, blob in ((CF_DIB, dib), (png_fmt, png)):
            if not fmt:
                continue
            h = _alloc_global(blob)
            if h and u32.SetClipboardData(fmt, h):
                set_any = True
            else:
                logger.error("SetClipboardData failed for format %d", fmt)
        if set_any:
            logger.debug("Clipboard image set: %dx%d (DIB %dB + PNG %dB)",
                         img.width, img.height, len(dib), len(png))
        return set_any
    finally:
        u32.CloseClipboard()
