"""Windows clipboard image support: put PNG/JPEG bytes as CF_DIB for Ctrl+V paste."""
import ctypes
import io
import logging

from PIL import Image

logger = logging.getLogger("bot.clipimg")

CF_DIB = 8
GMEM_MOVEABLE = 0x0002


def set_clipboard_image(data: bytes) -> bool:
    """Convert image bytes to DIB and place on the Windows clipboard."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "BMP")
    dib = buf.getvalue()[14:]  # strip BITMAPFILEHEADER — clipboard wants raw DIB

    k32 = ctypes.windll.kernel32
    u32 = ctypes.windll.user32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    if not u32.OpenClipboard(None):
        logger.error("OpenClipboard failed")
        return False
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(GMEM_MOVEABLE, len(dib))
        if not h:
            logger.error("GlobalAlloc failed (%d bytes)", len(dib))
            return False
        p = k32.GlobalLock(h)
        if not p:
            logger.error("GlobalLock failed")
            return False
        ctypes.memmove(p, dib, len(dib))
        k32.GlobalUnlock(h)
        ok = bool(u32.SetClipboardData(CF_DIB, h))
        if not ok:
            logger.error("SetClipboardData failed")
        else:
            logger.debug("Clipboard image set: %dx%d, %d bytes DIB", img.width, img.height, len(dib))
        return ok
    finally:
        u32.CloseClipboard()
