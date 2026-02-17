import io
import logging
import time
import mss
from PIL import Image
from telegram import Update
from telegram.ext import ContextTypes
from config import SCREENSHOT_QUALITY, SCREENSHOT_COOLDOWN
from utils.auth import auth_required
from utils.window import get_active_window_rect

logger = logging.getLogger("bot.screen")

_last_screenshot_time = 0.0
_crop_region = None  # {"left": x, "top": y, "width": w, "height": h}


def _check_cooldown() -> bool:
    """Return True if cooldown has passed, False otherwise."""
    global _last_screenshot_time
    now = time.time()
    if now - _last_screenshot_time < SCREENSHOT_COOLDOWN:
        return False
    _last_screenshot_time = now
    return True


def _grab_to_jpeg(region: dict | None = None) -> io.BytesIO:
    """Capture screen region (or full monitor) and return JPEG BytesIO."""
    with mss.mss() as sct:
        if region:
            raw = sct.grab(region)
        else:
            raw = sct.grab(sct.monitors[1])  # primary monitor

    img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=SCREENSHOT_QUALITY)
    buf.seek(0)
    buf.name = "screenshot.jpg"
    return buf


@auth_required
async def screen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/screen — capture full monitor (or crop region if set)."""
    logger.debug("/screen called")
    if not _check_cooldown():
        await update.message.reply_text(f"Cooldown: wait {SCREENSHOT_COOLDOWN}s between screenshots.")
        return

    try:
        buf = _grab_to_jpeg(_crop_region)
        await update.message.reply_photo(photo=buf)
        logger.debug("/screen sent successfully")
    except Exception as e:
        logger.error("/screen error: %s", e)
        await update.message.reply_text(f"Screenshot failed: {e}")


@auth_required
async def window_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/window — capture active window only."""
    logger.debug("/window called")
    if not _check_cooldown():
        await update.message.reply_text(f"Cooldown: wait {SCREENSHOT_COOLDOWN}s between screenshots.")
        return

    rect = get_active_window_rect()
    if rect is None:
        await update.message.reply_text("No active window detected.")
        return

    left, top, width, height = rect
    if width <= 0 or height <= 0:
        await update.message.reply_text("Active window has invalid dimensions.")
        return

    region = {"left": left, "top": top, "width": width, "height": height}
    try:
        buf = _grab_to_jpeg(region)
        await update.message.reply_photo(photo=buf)
        logger.debug("/window sent successfully (%s)", rect)
    except Exception as e:
        logger.error("/window error: %s", e)
        await update.message.reply_text(f"Window capture failed: {e}")


@auth_required
async def crop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/crop x y w h — set crop region for /screen. /crop off to reset."""
    global _crop_region
    args = context.args

    if not args:
        if _crop_region:
            r = _crop_region
            await update.message.reply_text(
                f"Crop: {r['left']},{r['top']} {r['width']}x{r['height']}\n"
                "/crop off — reset to full screen"
            )
        else:
            await update.message.reply_text(
                "No crop set (full screen).\n"
                "Usage: /crop <x> <y> <w> <h>\n"
                "/crop window — use active window bounds"
            )
        return

    if args[0].lower() == "off":
        _crop_region = None
        logger.debug("Crop region cleared")
        await update.message.reply_text("Crop off — full screen mode.")
        return

    if args[0].lower() == "window":
        rect = get_active_window_rect()
        if rect is None:
            await update.message.reply_text("No active window detected.")
            return
        left, top, width, height = rect
        _crop_region = {"left": left, "top": top, "width": width, "height": height}
        logger.debug("Crop set to window: %s", _crop_region)
        await update.message.reply_text(f"Crop set to window: {left},{top} {width}x{height}")
        return

    if len(args) < 4:
        await update.message.reply_text("Usage: /crop <x> <y> <w> <h>")
        return

    try:
        x, y, w, h = int(args[0]), int(args[1]), int(args[2]), int(args[3])
    except ValueError:
        await update.message.reply_text("All values must be integers.")
        return

    _crop_region = {"left": x, "top": y, "width": w, "height": h}
    logger.debug("Crop set: %s", _crop_region)
    await update.message.reply_text(f"Crop set: {x},{y} {w}x{h}")
