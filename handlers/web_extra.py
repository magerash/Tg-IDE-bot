"""Extra web API endpoints: window focus, project folders, Claude CLI."""
import asyncio
import logging
import subprocess

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
        from handlers.windows import _list_project_folders
        folders = await asyncio.to_thread(_list_project_folders)
        return _json({"ok": True, "folders": folders})
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
        from handlers.windows import _list_project_folders, _open_in_vscode
        # Membership check keeps shell command safe from arbitrary paths
        folders = await asyncio.to_thread(_list_project_folders)
        if folder not in folders:
            return _err(f"Unknown folder: {folder}")
        ok, msg = await asyncio.to_thread(_open_in_vscode, folder)
        return _json({"ok": ok, "msg": msg})
    except Exception as e:
        logger.error("web /api/code error: %s", e)
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
    app.router.add_post("/api/claude", api_claude)
