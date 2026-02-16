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
    """/screen — capture full primary monitor and send as photo."""
    logger.debug("/screen called")
    if not _check_cooldown():
        await update.message.reply_text(f"Cooldown: wait {SCREENSHOT_COOLDOWN}s between screenshots.")
        return

    try:
        buf = _grab_to_jpeg()
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
