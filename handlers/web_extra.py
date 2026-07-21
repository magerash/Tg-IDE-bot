"""Extra web API endpoints: window focus, project folders, Claude CLI."""
import asyncio
import logging
import subprocess

from utils import project
from utils.window import focus_window_exact, list_windows

logger = logging.getLogger("bot.web_extra")


async def api_windows(request):
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        titles = await asyncio.to_thread(list_windows)
        return _json({"ok": True, "windows": titles})
    except Exception as e:
        logger.error("web /api/windows error: %s", e)
        return _err(str(e), 500)


async def api_focus(request):
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        title = data.get("title", "")
        if not title:
            return _err("Missing 'title'")
        ok, msg = await asyncio.to_thread(focus_window_exact, title)
        return _json({"ok": ok, "msg": msg})
    except Exception as e:
        logger.error("web /api/focus error: %s", e)
        return _err(str(e), 500)


async def api_folders(request):
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        folders = await asyncio.to_thread(project.list_projects)
        return _json({"ok": True, "folders": folders, "current": project.get_name()})
    except Exception as e:
        logger.error("web /api/folders error: %s", e)
        return _err(str(e), 500)


async def api_code(request):
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        folder = data.get("folder", "")
        from handlers.windows import _open_in_vscode
        # Membership check keeps shell command safe from arbitrary paths
        folders = await asyncio.to_thread(project.list_projects)
        if folder not in folders:
            return _err(f"Unknown folder: {folder}")
        ok, msg = await asyncio.to_thread(_open_in_vscode, folder)
        return _json({"ok": ok, "msg": msg, "current": project.get_name()})
    except Exception as e:
        logger.error("web /api/code error: %s", e)
        return _err(str(e), 500)


async def api_project(request):
    """GET — current project; POST {folder} — switch current project (no VSCode)."""
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        if request.method == "GET":
            return _json({"ok": True, "current": project.get_name(), "dir": project.get_dir()})
        data = await request.json()
        folder = data.get("folder", "")
        folders = await asyncio.to_thread(project.list_projects)
        if folder not in folders:
            return _err(f"Unknown folder: {folder}")
        project.set_by_name(folder)
        return _json({"ok": True, "current": project.get_name(), "dir": project.get_dir(),
                      "msg": f"Project: {folder}"})
    except Exception as e:
        logger.error("web /api/project error: %s", e)
        return _err(str(e), 500)


async def api_paste(request):
    """POST {image: base64, paste: bool} — put image on PC clipboard, optionally Ctrl+V it."""
    import base64

    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        b64 = data.get("image", "")
        if not b64:
            return _err("Missing 'image'")
        raw = base64.b64decode(b64)
        if len(raw) > 15 * 1024 * 1024:
            return _err("Image too large (15MB limit)")

        from utils.clipimg import set_clipboard_image
        ok = await asyncio.to_thread(set_clipboard_image, raw)
        if not ok:
            return _err("Clipboard set failed", 500)

        if data.get("paste", True):
            import pyautogui
            await asyncio.to_thread(pyautogui.hotkey, "ctrl", "v")
        logger.debug("web /api/paste: %d bytes, paste=%s", len(raw), data.get("paste", True))
        return _json({"ok": True, "msg": f"Image pasted ({len(raw) // 1024}KB)"})
    except Exception as e:
        logger.error("web /api/paste error: %s", e)
        return _err(str(e), 500)


async def api_stt(request):
    """POST raw audio body (webm/ogg/wav) → Groq Whisper → {text}."""
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        from utils.stt import MAX_AUDIO_SIZE, STTError, transcribe
        data = await request.read()
        if len(data) > MAX_AUDIO_SIZE:
            return _err("Audio too large (25MB limit)", 413)
        ctype = request.headers.get("Content-Type", "audio/webm")
        ext = ("webm" if "webm" in ctype else "ogg" if "ogg" in ctype
               else "m4a" if "mp4" in ctype else "wav")
        try:
            text = await transcribe(data, f"mic.{ext}")
        except STTError as e:
            return _err(str(e))
        return _json({"ok": True, "text": text})
    except Exception as e:
        logger.error("web /api/stt error: %s", e)
        return _err(str(e), 500)


async def api_claude(request):
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return _err("Missing 'prompt'")
        proc = await asyncio.to_thread(
            subprocess.run, ["claude", "-p", prompt],
            capture_output=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
        output = proc.stdout.strip() or proc.stderr.strip() or "(no response)"
        return _json({"ok": True, "output": output})
    except FileNotFoundError:
        return _err("Claude CLI not found")
    except subprocess.TimeoutExpired:
        return _err("Claude timed out (5 min limit)", 408)
    except Exception as e:
        logger.error("web /api/claude error: %s", e)
        return _err(str(e), 500)


def register_extra_routes(app):
    app.router.add_get("/api/windows", api_windows)
    app.router.add_post("/api/focus", api_focus)
    app.router.add_get("/api/folders", api_folders)
    app.router.add_post("/api/code", api_code)
    app.router.add_get("/api/project", api_project)
    app.router.add_post("/api/project", api_project)
    app.router.add_post("/api/paste", api_paste)
    app.router.add_post("/api/stt", api_stt)
    app.router.add_post("/api/claude", api_claude)
