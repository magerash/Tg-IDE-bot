import asyncio
import io
import logging
import mss
from PIL import Image
from telegram import Update
from telegram.ext import ContextTypes
from config import SCREENSHOT_QUALITY
from utils.auth import auth_required, rate_limit
from utils.window import get_active_window_rect

logger = logging.getLogger("bot.screen")

_crop_region = None  # {"left": x, "top": y, "width": w, "height": h}


def _grab_frame(
    region: dict | None = None,
    max_w: int = 0,
    quality: int | None = None,
    fmt: str = "JPEG",
) -> bytes:
    """Capture screen region (or full monitor) and encode it.

    max_w > 0 downscales to that width (web live view — smaller frames keep
    short auto-refresh intervals achievable over a thin link).

    fmt="WEBP" is ~37% smaller than JPEG at the same quality for ~22ms more
    encode time — a trade worth making on every byte-constrained path.
    `method=2` is the sweet spot; the default (4) triples encode time for ~2%.
    """
    with mss.mss() as sct:
        if region:
            raw = sct.grab(region)
        else:
            raw = sct.grab(sct.monitors[1])  # primary monitor

    img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
    if max_w and img.width > max_w:
        img = img.resize((max_w, max(1, round(img.height * max_w / img.width))),
                         Image.BILINEAR)
        logger.debug("_grab_frame downscaled %dx%d -> %dx%d",
                     raw.width, raw.height, img.width, img.height)
    buf = io.BytesIO()
    fmt = fmt.upper()
    opts = {"quality": quality or SCREENSHOT_QUALITY}
    if fmt == "WEBP":
        opts["method"] = 2
    img.save(buf, format=fmt, **opts)
    return buf.getvalue()


def _grab_to_jpeg(
    region: dict | None = None,
    max_w: int = 0,
    quality: int | None = None,
) -> io.BytesIO:
    """JPEG BytesIO for the Telegram photo paths (send_photo needs a file-like)."""
    buf = io.BytesIO(_grab_frame(region, max_w, quality, "JPEG"))
    buf.name = "screenshot.jpg"
    return buf


@auth_required
@rate_limit(2.0)
async def screen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/screen — capture full monitor (or crop region if set)."""
    logger.debug("/screen called")
    try:
        buf = await asyncio.to_thread(_grab_to_jpeg, _crop_region)
        await update.message.reply_photo(photo=buf)
        logger.debug("/screen sent successfully")
    except Exception as e:
        logger.error("/screen error: %s", e)
        await update.message.reply_text(f"Screenshot failed: {e}")


@auth_required
@rate_limit(2.0)
async def window_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/window — capture active window only."""
    logger.debug("/window called")
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
        buf = await asyncio.to_thread(_grab_to_jpeg, region)
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
