import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import platform
import subprocess
import sys
import time

from aiohttp import web

from config import (
    ALLOWED_USER_ID, BOT_TOKEN, MAX_FILE_SIZE,
    VERSION, WEB_SCREEN_MAX_W, WEB_SCREEN_QUALITY, WEB_TOKEN, WEBAPP_URL,
)
from handlers.files import _find_apks
from utils import project
from handlers.screen import _grab_frame, _grab_to_jpeg
from utils.webauth import check_token, validate_init_data
from utils.window import get_active_window_rect

logger = logging.getLogger("bot.web")

_start_time = time.time()


def _check_auth(request):
    """Validate Telegram Mini App initData or bearer token (timing-safe)."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data and validate_init_data(init_data, BOT_TOKEN) == ALLOWED_USER_ID:
        return True
    auth = request.headers.get("Authorization", "")
    bearer = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else ""
    return check_token(bearer, request.query.get("token", ""), WEB_TOKEN)


def _json(data, status=200):
    return web.json_response(data, status=status)


def _err(msg, status=400):
    return _json({"ok": False, "error": msg}, status=status)


# --- API Endpoints ---

async def _frame_opts(request):
    """Live-view frame size/quality/last-hash — request override, else config defaults."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    # max_w 0 means "native, no downscale" — a real choice, not a missing value,
    # so `or` would silently turn the Full setting back into the default cap.
    raw_w = data.get("max_w")
    max_w = WEB_SCREEN_MAX_W if raw_w is None else int(raw_w)
    quality = int(data.get("quality") or WEB_SCREEN_QUALITY)
    return min(max(max_w, 0), 3840), max(20, min(95, quality)), str(data.get("hash") or "")


def _frame_reply(buf, rect, prev_hash):
    """Frame response. If the JPEG is byte-identical to what the client already
    shows, reply {'same': True} (~80 bytes) instead of re-sending ~80KB — an
    idle screen then costs nothing on the tunnel, so clicks get the bandwidth."""
    raw = buf.getvalue()
    digest = hashlib.md5(raw).hexdigest()
    if prev_hash and prev_hash == digest:
        return _json({"ok": True, "same": True, "hash": digest, "rect": rect})
    return _json({"ok": True, "image": base64.b64encode(raw).decode(),
                  "hash": digest, "rect": rect})


async def api_frame(request):
    """Live-view frame as raw bytes — the transport the dashboard actually uses.

    Two wins over the JSON endpoints below, which stay for older clients:
      * binary, not base64 — base64 inflates every frame by 33%
      * WebP when the client supports it — ~37% smaller than JPEG at equal quality
    A 1280px frame that costs 114KB as base64 JPEG costs 52KB here.

    Unchanged screen → 204 with no body at all. Metadata rides in headers so the
    body stays pure image bytes: X-Rect (l,t,w,h), X-Hash, X-Mode.
    """
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    mode = "window" if data.get("mode") == "window" else "screen"
    fmt = "WEBP" if str(data.get("fmt", "")).lower() == "webp" else "JPEG"
    raw_w = data.get("max_w")
    max_w = min(max(WEB_SCREEN_MAX_W if raw_w is None else int(raw_w), 0), 3840)
    quality = max(20, min(95, int(data.get("quality") or WEB_SCREEN_QUALITY)))
    prev_hash = str(data.get("hash") or "")

    try:
        if mode == "window":
            rect = await asyncio.to_thread(get_active_window_rect)
            if not rect:
                return _err("No active window")
            left, top, w, h = rect
            if w <= 0 or h <= 0:
                return _err("Invalid window dimensions")
            region = {"left": left, "top": top, "width": w, "height": h}
        else:
            import pyautogui
            sw, sh = pyautogui.size()
            rect, region = (0, 0, sw, sh), None

        payload = await asyncio.to_thread(_grab_frame, region, max_w, quality, fmt)
        digest = hashlib.md5(payload).hexdigest()
        headers = {
            "X-Rect": ",".join(str(v) for v in rect),
            "X-Hash": digest,
            "X-Mode": mode,
            "Cache-Control": "no-store",
        }
        if prev_hash and prev_hash == digest:
            return web.Response(status=204, headers=headers)
        return web.Response(
            body=payload, status=200, headers=headers,
            content_type="image/webp" if fmt == "WEBP" else "image/jpeg",
        )
    except Exception as e:
        logger.error("web /api/frame error: %s", e)
        return _err(str(e), 500)


async def api_screen(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        max_w, quality, prev_hash = await _frame_opts(request)
        buf = await asyncio.to_thread(_grab_to_jpeg, None, max_w, quality)
        import pyautogui
        sw, sh = pyautogui.size()
        return _frame_reply(buf, [0, 0, sw, sh], prev_hash)
    except Exception as e:
        logger.error("web /api/screen error: %s", e)
        return _err(str(e), 500)


async def api_window(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        rect = await asyncio.to_thread(get_active_window_rect)
        if not rect:
            return _err("No active window")
        left, top, w, h = rect
        if w <= 0 or h <= 0:
            return _err("Invalid window dimensions")
        max_w, quality, prev_hash = await _frame_opts(request)
        buf = await asyncio.to_thread(
            _grab_to_jpeg, {"left": left, "top": top, "width": w, "height": h},
            max_w, quality,
        )
        return _frame_reply(buf, list(rect), prev_hash)
    except Exception as e:
        logger.error("web /api/window error: %s", e)
        return _err(str(e), 500)


async def api_key(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        key_str = data.get("key", "").lower().strip()
        repeat = min(int(data.get("repeat", 1)), 200)
        interval = min(float(data.get("interval", 0)), 5.0)  # sec between presses
        if not key_str:
            return _err("Missing 'key'")

        import time
        import pyautogui
        parts = key_str.split("+")

        def _do():
            for i in range(repeat):
                if len(parts) > 1:
                    pyautogui.hotkey(*parts)
                else:
                    pyautogui.press(parts[0])
                if interval and i < repeat - 1:
                    time.sleep(interval)

        await asyncio.to_thread(_do)
        return _json({"ok": True, "pressed": key_str, "repeat": repeat})
    except Exception as e:
        logger.error("web /api/key error: %s", e)
        return _err(str(e), 500)


async def api_type(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        text = data.get("text", "")
        enter = data.get("enter", True)
        if not text:
            return _err("Missing 'text'")

        from handlers.input import _type_text
        import pyautogui
        await asyncio.to_thread(_type_text, text)
        if enter:
            await asyncio.to_thread(pyautogui.press, "enter")
        return _json({"ok": True, "typed": text})
    except Exception as e:
        logger.error("web /api/type error: %s", e)
        return _err(str(e), 500)


async def api_click(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        x, y = int(data["x"]), int(data["y"])
        double = bool(data.get("double", False))
        import pyautogui
        fn = pyautogui.doubleClick if double else pyautogui.click
        await asyncio.to_thread(fn, x, y)
        return _json({"ok": True, "clicked": [x, y], "double": double})
    except Exception as e:
        logger.error("web /api/click error: %s", e)
        return _err(str(e), 500)


async def api_sh(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        cmd = data.get("cmd", "")
        if not cmd:
            return _err("Missing 'cmd'")
        timeout = min(int(data.get("timeout", 60)), 300)

        proc = await asyncio.to_thread(
            subprocess.run, cmd, shell=True,
            capture_output=True, timeout=timeout,
        )
        raw = proc.stdout + proc.stderr
        try:
            output = raw.decode("utf-8")
        except UnicodeDecodeError:
            output = raw.decode("cp866", errors="replace")
        return _json({"ok": True, "output": output, "code": proc.returncode})
    except subprocess.TimeoutExpired:
        return _err("Command timed out", 408)
    except Exception as e:
        logger.error("web /api/sh error: %s", e)
        return _err(str(e), 500)


async def api_git(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        args = data.get("args", ["status"])
        if isinstance(args, str):
            args = args.split()

        git_dir = project.get_dir()
        proc = await asyncio.to_thread(
            subprocess.run, ["git"] + args, cwd=git_dir,
            capture_output=True, timeout=60,
        )
        raw = proc.stdout + proc.stderr
        try:
            output = raw.decode("utf-8")
        except UnicodeDecodeError:
            output = raw.decode("cp866", errors="replace")
        return _json({"ok": True, "output": output, "cwd": git_dir,
                      "project": project.get_name(), "code": proc.returncode})
    except Exception as e:
        logger.error("web /api/git error: %s", e)
        return _err(str(e), 500)


async def api_status(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    uptime = int(time.time() - _start_time)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    return _json({
        "ok": True,
        "version": VERSION,
        "uptime": f"{h}h {m}m {s}s",
        "uptime_sec": uptime,
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "project": project.get_name(),
        "project_dir": project.get_dir(),
    })


async def api_build(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json() if request.body_exists else {}
        send_apk = data.get("apk", False)
        cwd = data.get("cwd") or project.get_dir()
        gradlew = os.path.join(cwd, "gradlew.bat")
        if not os.path.isfile(gradlew):
            return _err(f"No gradlew.bat in {os.path.basename(cwd)} — switch project first")

        await asyncio.to_thread(
            subprocess.run, [gradlew, "clean"], cwd=cwd,
            capture_output=True, timeout=120, encoding="utf-8", errors="replace",
        )
        proc = await asyncio.to_thread(
            subprocess.run, [gradlew, "assembleDebug"], cwd=cwd,
            capture_output=True, timeout=300, encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
            result = {"ok": True, "status": "SUCCESS", "tail": lines[-1] if lines else ""}
            if send_apk:
                apks = _find_apks("debug", dirs=[cwd])
                if apks:
                    result["apk"] = os.path.basename(apks[0])
                    result["apk_size"] = os.path.getsize(apks[0])
            return _json(result)
        else:
            stderr = proc.stderr[-2000:] if len(proc.stderr) > 2000 else proc.stderr
            return _json({"ok": False, "status": "FAILED", "code": proc.returncode, "stderr": stderr})
    except subprocess.TimeoutExpired:
        return _err("Build timed out", 408)
    except Exception as e:
        logger.error("web /api/build error: %s", e)
        return _err(str(e), 500)


async def api_apk_list(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        filt = request.query.get("filter", None)
        apks = await asyncio.to_thread(_find_apks, filt)
        items = []
        for a in apks[:20]:
            items.append({
                "path": a,
                "name": os.path.basename(a),
                "size": os.path.getsize(a),
            })
        return _json({"ok": True, "apks": items})
    except Exception as e:
        return _err(str(e), 500)


def _do_restart():
    """Replace current process with a fresh bot instance (keeps console/env)."""
    logger.info("Restarting bot via os.execv")
    os.execv(sys.executable, [sys.executable, os.path.abspath(sys.argv[0])])


async def api_restart(request):
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    logger.warning("Restart requested via web")
    # Reply first, then re-exec — 0.7s lets the response flush
    asyncio.get_running_loop().call_later(0.7, _do_restart)
    return _json({"ok": True, "msg": "Restarting bot..."})


async def index_page(request):
    """Serve the web dashboard (no-cache: webviews must always get fresh HTML).

    Telegram's webview treats these headers as advisory, so the page also
    self-checks CLIENT_VERSION against /api/status and reloads with ?v= when
    it finds itself stale — see _checkStaleClient() in index.html.
    """
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "index.html")
    if os.path.isfile(html_path):
        return web.FileResponse(
            html_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return web.Response(text="Dashboard not found", status=404)


def create_web_app():
    """Create and configure the aiohttp web application.
    client_max_size: default 1MB kills long voice WAV uploads (10 min ≈ 19MB)."""
    app = web.Application(client_max_size=30 * 1024 * 1024)

    # API routes
    app.router.add_post("/api/frame", api_frame)
    app.router.add_post("/api/screen", api_screen)
    app.router.add_post("/api/window", api_window)
    app.router.add_post("/api/key", api_key)
    app.router.add_post("/api/type", api_type)
    app.router.add_post("/api/click", api_click)
    app.router.add_post("/api/sh", api_sh)
    app.router.add_post("/api/git", api_git)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/build", api_build)
    app.router.add_get("/api/apks", api_apk_list)
    app.router.add_post("/api/restart", api_restart)

    from handlers.web_extra import register_extra_routes
    register_extra_routes(app)

    # Static dashboard
    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
    if os.path.isdir(web_dir):
        app.router.add_get("/", index_page)
        app.router.add_static("/static/", web_dir, name="static")

    logger.info("Web app created with %d routes", len(app.router.routes()))
    return app


def miniapp_url(base: str = "", version: str = "") -> str:
    """Mini App URL with a version stamp.

    Telegram's webview caches the page per URL and ignores no-cache headers, so
    without this a phone can keep running last month's dashboard against a new
    bot. A new version = a new URL = a guaranteed fresh load.
    """
    base = base or WEBAPP_URL
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}v={version or VERSION}"


async def setup_menu_button(bot):
    """Set the chat menu button to open the Mini App (if WEBAPP_URL configured)."""
    if not WEBAPP_URL:
        return
    from telegram import MenuButtonWebApp, WebAppInfo
    url = miniapp_url()
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Panel", web_app=WebAppInfo(url=url))
        )
        logger.info("Mini App menu button set: %s", url)
    except Exception as e:
        logger.error("Menu button setup failed: %s", e)
