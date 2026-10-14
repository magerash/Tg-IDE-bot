"""Extra web API endpoints: window focus, project folders, Claude CLI, scheduling."""
import asyncio
import logging
import os
import subprocess
import time

from utils import project
from utils.window import focus_window_exact, get_active_window_title, list_windows

logger = logging.getLogger("bot.web_extra")


async def api_windows(request):
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        titles = await asyncio.to_thread(list_windows)
        active = await asyncio.to_thread(get_active_window_title)
        return _json({"ok": True, "windows": titles, "active": active})
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
        logger.debug("web /api/focus %r -> ok=%s (%s)", title, ok, msg)
        # "gone" distinguishes "no such window any more" (drop it from the
        # client's recents) from "found but activation blocked" (keep it).
        # Kept next to the producer so the message string is coupled in one place.
        return _json({"ok": ok, "msg": msg, "gone": msg.startswith("Window gone")})
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
    """POST {image: base64, paste: bool} — save image to a temp PNG and type its PATH
    into the focused window. Target is Claude Code in a VS Code terminal: a terminal
    cannot receive a pasted image via Ctrl+V, but Claude Code attaches an image file
    when its path appears in the prompt. So we type the path (no Enter); the caller
    types the user's text + Enter next."""
    import base64
    import io
    import os
    import tempfile

    from PIL import Image

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

        # save as PNG in a stable temp dir
        out_dir = os.path.join(tempfile.gettempdir(), "tgbot_paste")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"img_{int(time.time() * 1000)}.png")
        await asyncio.to_thread(lambda: Image.open(io.BytesIO(raw)).save(path, "PNG"))

        if data.get("paste", True):
            from handlers.input import _type_text
            from utils.uploads import path_token
            await asyncio.to_thread(_type_text, path_token(path))
        logger.debug("web /api/paste: %d bytes -> %s (typed path=%s)",
                     len(raw), path, data.get("paste", True))
        return _json({"ok": True, "path": path, "msg": f"Image path typed ({len(raw) // 1024}KB)"})
    except Exception as e:
        logger.error("web /api/paste error: %s", e)
        return _err(str(e), 500)


async def api_upload(request):
    """POST raw file bytes + X-Filename → save on the PC and type the PATH.

    Same trick as /api/paste, generalised: a terminal cannot take a pasted
    document, but Claude Code reads a file whose path is in the prompt. So a 40KB
    markdown arrives whole and instantly instead of being pushed through the
    clipboard as text — which is slow, hits bracketed paste, and truncates.

    Raw body, not multipart: api() speaks JSON, so a binary needs its own fetch
    either way, and /api/stt already proved the shape. The name rides in a header
    URL-encoded — a raw UTF-8 header value is mangled by the time it lands here.

    X-Type-Path: 0 saves the file and returns the path without typing anything.
    Plain _check_auth on purpose: typing into a focused window is remote control,
    which the refine-scoped token must never reach.
    """
    from urllib.parse import unquote

    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        from utils.uploads import MAX_UPLOAD, path_token, save_upload
        data = await request.read()
        if not data:
            return _err("Empty upload")
        if len(data) > MAX_UPLOAD:
            return _err(f"File too large ({MAX_UPLOAD // (1024 * 1024)}MB limit)", 413)
        name = unquote(request.headers.get("X-Filename", "") or "")
        path = await asyncio.to_thread(save_upload, data, name)
        typed = request.headers.get("X-Type-Path", "1") != "0"
        if typed:
            from handlers.input import _type_text
            await asyncio.to_thread(_type_text, path_token(path))
        kb = max(1, len(data) // 1024)
        logger.info("web /api/upload: %r %dKB -> %s (typed=%s)",
                    name, kb, path, typed)
        return _json({"ok": True, "path": path, "name": os.path.basename(path),
                      "size": len(data),
                      "msg": f"{os.path.basename(path)} ({kb}KB) — path typed"
                             if typed else f"{os.path.basename(path)} saved"})
    except Exception as e:
        logger.error("web /api/upload error: %s", e)
        return _err(str(e), 500)


async def api_stt(request):
    """POST raw audio body (webm/ogg/wav) → Groq Whisper → {text, raw}.
    ?humanize=1 also cleans the transcript via LLM (falls back to raw on error)."""
    # Refine-scoped tokens reach this one — it is a text-refinement endpoint.
    from handlers.web import _check_auth_refine, _err, _json
    if not _check_auth_refine(request):
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
            raw = await transcribe(data, f"mic.{ext}")
        except STTError as e:
            return _err(str(e))

        text = raw
        wanted = raw and request.query.get("humanize") == "1"
        err = None
        if wanted:
            from utils.humanize import humanize
            try:
                text = await humanize(raw)
            except Exception as e:
                # Reported, not swallowed: a silent fallback is indistinguishable
                # from "the AI button does nothing" (Groq retiring a model looked
                # exactly like that for a day).
                err = str(e)[:300]
                logger.error("humanize failed, returning raw: %s", e)
        return _json({"ok": True, "text": text, "raw": raw,
                      "humanized": bool(wanted and err is None),
                      "humanize_error": err})
    except Exception as e:
        logger.error("web /api/stt error: %s", e)
        return _err(str(e), 500)


async def api_improve(request):
    """POST {text, style, twin} → {improved, twin_used, style}. Rewrites typed text
    into a better prompt; never auto-sends — the client shows it for review.
    LLM failure is a loud 502: the client keeps the original text and toasts."""
    # Refine-scoped tokens reach this one — it is a text-refinement endpoint.
    from handlers.web import _check_auth_refine, _err, _json
    if not _check_auth_refine(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        text = (data.get("text") or "").strip()
        if not text:
            return _err("No text")
        style = data.get("style") or "structured"
        twin = bool(data.get("twin"))
        from utils.improve import improve
        try:
            improved, twin_used = await improve(text, style, twin)
        except Exception as e:
            logger.error("improve failed: %s", e)
            return _err(str(e)[:300], 502)
        return _json({"ok": True, "improved": improved, "style": style,
                      "twin_used": twin_used,
                      "twin_missing": twin and not twin_used})
    except Exception as e:
        logger.error("web /api/improve error: %s", e)
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


async def api_ccmetrics(request):
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        from utils import ccmetrics
        pdir = project.get_dir()  # metrics follow the dashboard's selected project
        m = await asyncio.to_thread(ccmetrics.collect, pdir)
        return _json({"ok": True, "metrics": m})
    except Exception as e:
        logger.error("web /api/ccmetrics error: %s", e)
        return _err(str(e), 500)


async def api_schedule(request):
    """Create a scheduled message. Target window defaults to the currently
    focused window (refocused before typing at fire time)."""
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        text = data.get("text", "").strip()
        if not text:
            return _err("Missing 'text'")
        try:
            when = int(float(data.get("when")))
        except (TypeError, ValueError):
            return _err("Missing or bad 'when' (epoch seconds)")
        if when < int(time.time()) - 5:
            return _err("Time is in the past")

        window = data.get("window")
        if window is None:
            try:
                window = await asyncio.to_thread(get_active_window_title)
            except Exception:
                window = None

        from utils import scheduler
        job = await scheduler.add_job(
            text, when, data.get("enter", True), window, data.get("terminal", True)
        )
        return _json({"ok": True, "job": job})
    except Exception as e:
        logger.error("web /api/schedule error: %s", e)
        return _err(str(e), 500)


async def api_schedules(request):
    """List pending scheduled messages."""
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        from utils import scheduler
        jobs = await scheduler.list_jobs()
        return _json({"ok": True, "jobs": jobs, "now": int(time.time())})
    except Exception as e:
        logger.error("web /api/schedules error: %s", e)
        return _err(str(e), 500)


async def api_unschedule(request):
    """Cancel a scheduled message by id."""
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        data = await request.json()
        from utils import scheduler
        removed = await scheduler.remove_job(data.get("id", ""))
        return _json({"ok": removed})
    except Exception as e:
        logger.error("web /api/unschedule error: %s", e)
        return _err(str(e), 500)


async def api_layout(request):
    """GET: layout of the foreground window. POST: switch it.

    The layout belongs to the window that will receive the typing, not to the
    bot, so both read and write target the foreground window. POST with no
    `lang` cycles to the next installed one — one tap on a phone.
    """
    from handlers.web import _check_auth, _err, _json
    if not _check_auth(request):
        return _err("Unauthorized", 401)
    try:
        from utils import layout
        if request.method == "GET":
            return _json({"ok": True, **await asyncio.to_thread(layout.current)})
        data = await request.json() if request.can_read_body else {}
        lang = data.get("lang")
        ok, msg = await asyncio.to_thread(layout.switch,
                                          int(lang) if lang not in (None, "") else None)
        # The new state ships with the verdict: a UI that re-reads it in a second
        # request can show a layout that already changed again.
        return _json({"ok": ok, "msg": msg, **await asyncio.to_thread(layout.current)})
    except Exception as e:
        logger.error("web /api/layout error: %s", e)
        return _err(str(e), 500)


def register_extra_routes(app):
    app.router.add_get("/api/layout", api_layout)
    app.router.add_post("/api/layout", api_layout)
    app.router.add_get("/api/ccmetrics", api_ccmetrics)
    app.router.add_post("/api/schedule", api_schedule)
    app.router.add_get("/api/schedules", api_schedules)
    app.router.add_post("/api/unschedule", api_unschedule)
    app.router.add_get("/api/windows", api_windows)
    app.router.add_post("/api/focus", api_focus)
    app.router.add_get("/api/folders", api_folders)
    app.router.add_post("/api/code", api_code)
    app.router.add_get("/api/project", api_project)
    app.router.add_post("/api/project", api_project)
    app.router.add_post("/api/paste", api_paste)
    app.router.add_post("/api/upload", api_upload)
    app.router.add_post("/api/stt", api_stt)
    app.router.add_post("/api/improve", api_improve)
    app.router.add_post("/api/claude", api_claude)
