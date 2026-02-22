import glob
import logging
import os
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from config import APK_SEARCH_DIRS, APK_GLOB, BUILD_CMD, MAX_FILE_SIZE, PROJECT_DIR
from utils.auth import auth_required, rate_limit

logger = logging.getLogger("bot.files")


def _find_apks(filter_str: str | None = None) -> list[str]:
    """Find APKs across search dirs, optionally filtered by name substring."""
    all_apks = []
    for search_dir in APK_SEARCH_DIRS:
        pattern = os.path.join(search_dir, APK_GLOB)
        all_apks.extend(glob.glob(pattern, recursive=True))

    if filter_str:
        all_apks = [a for a in all_apks if filter_str.lower() in os.path.basename(a).lower()]

    all_apks.sort(key=os.path.getmtime, reverse=True)
    return all_apks


async def _send_apk(update: Update):
    """Find and send latest debug APK after successful build."""
    apks = _find_apks("debug")
    if not apks:
        await update.message.reply_text("Build done but no APK found.")
        return
    apk_path = apks[0]
    size = os.path.getsize(apk_path)
    if size > MAX_FILE_SIZE:
        await update.message.reply_text(f"APK too large: {size // 1024 // 1024}MB (limit 50MB)")
        return
    name = os.path.basename(apk_path)
    with open(apk_path, "rb") as f:
        await update.message.reply_document(document=f, filename=name, caption=f"{name} ({size // 1024}KB)")


@auth_required
@rate_limit(60.0)
async def build_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/build [apk] [dir] — run gradle build. 'apk' sends APK after build."""
    args = list(context.args or [])
    send_apk = False
    if args and args[0].lower() == "apk":
        send_apk = True
        args.pop(0)

    cwd = " ".join(args) if args else (PROJECT_DIR or None)
    logger.debug("/build called, cwd=%s, send_apk=%s", cwd, send_apk)

    gradlew = os.path.join(cwd, "gradlew.bat") if cwd else "gradlew.bat"
    cmd = [gradlew, "assembleDebug"]
    await update.message.reply_text("Building...")
    try:
        proc = subprocess.run(
            cmd, cwd=cwd,
            capture_output=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
            tail = lines[-1] if lines else ""
            await update.message.reply_text(f"Build SUCCESS\n{tail}")
            if send_apk:
                await _send_apk(update)
        else:
            stderr = proc.stderr[-1500:] if len(proc.stderr) > 1500 else proc.stderr
            msg = f"Build FAILED (code {proc.returncode})\n{stderr}"
            if len(msg) > 4000:
                msg = msg[:4000] + "\n...(truncated)"
            await update.message.reply_text(msg)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Build timed out (5 min limit).")
    except Exception as e:
        logger.error("/build error: %s", e)
        await update.message.reply_text(f"Build failed: {e}")


@auth_required
@rate_limit(3.0)
async def apk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/apk [filter] — send latest APK. Filter: debug, release, list."""
    args = context.args
    filter_str = args[0].lower() if args else None
    logger.debug("/apk called, filter=%s", filter_str)

    # /apk list — show available APKs
    if filter_str == "list":
        apks = _find_apks()
        if not apks:
            await update.message.reply_text("No APKs found.")
            return
        lines = []
        for a in apks[:10]:
            size = os.path.getsize(a) // 1024
            lines.append(f"  {os.path.basename(a)} ({size}KB)")
        await update.message.reply_text("APKs found:\n" + "\n".join(lines))
        return

    await update.message.reply_text("Searching for APK...")
    apks = _find_apks(filter_str)
    if not apks:
        msg = f"No APK matching '{filter_str}'." if filter_str else "No APK found."
        await update.message.reply_text(msg + "\nTry: /apk list")
        return

    apk_path = apks[0]  # latest by mtime
    size = os.path.getsize(apk_path)
    if size > MAX_FILE_SIZE:
        await update.message.reply_text(f"APK too large: {size // 1024 // 1024}MB (limit 50MB)")
        return

    try:
        with open(apk_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(apk_path),
                caption=f"{os.path.basename(apk_path)} ({size // 1024}KB)",
            )
        logger.debug("Sent APK: %s", apk_path)
    except Exception as e:
        logger.error("/apk send error: %s", e)
        await update.message.reply_text(f"Failed to send APK: {e}")


@auth_required
@rate_limit(3.0)
async def file_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/file <path> — send any file by path."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /file <path>")
        return

    path = " ".join(args)
    logger.debug("/file called: %s", path)

    if not os.path.isfile(path):
        await update.message.reply_text(f"File not found: {path}")
        return

    size = os.path.getsize(path)
    if size > MAX_FILE_SIZE:
        await update.message.reply_text(f"File too large: {size // 1024 // 1024}MB (limit 50MB)")
        return

    try:
        with open(path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(path),
                caption=f"{os.path.basename(path)} ({size // 1024}KB)",
            )
        logger.debug("Sent file: %s", path)
    except Exception as e:
        logger.error("/file send error: %s", e)
        await update.message.reply_text(f"Failed to send file: {e}")
