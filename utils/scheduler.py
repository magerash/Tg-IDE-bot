"""Scheduled messages — queue text to be typed into a window at a future time
(e.g. right after a Claude Code limit reset, so a session auto-continues).

Persisted to a JSON file so pending jobs survive a bot restart. A single async
loop polls the store and fires due jobs (focus target window → type → Enter).
"""
import asyncio
import json
import logging
import os
import time
import uuid

from config import SCHEDULE_FILE, SCHEDULE_POLL, SCHEDULE_FOCUS_SETTLE, ALLOWED_USER_ID

logger = logging.getLogger("bot.scheduler")

_lock = asyncio.Lock()


def _load():
    try:
        with open(SCHEDULE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(jobs):
    tmp = SCHEDULE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SCHEDULE_FILE)


async def list_jobs():
    async with _lock:
        jobs = _load()
    return sorted(jobs, key=lambda j: j.get("when", 0))


async def add_job(text, when, enter=True, window=None, terminal=True):
    job = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "when": int(when),
        "enter": bool(enter),
        "window": window or None,
        "terminal": bool(terminal),
        "created": int(time.time()),
    }
    async with _lock:
        jobs = _load()
        jobs.append(job)
        _save(jobs)
    logger.info("scheduled %s at %d: %.40s", job["id"], job["when"], text)
    return job


async def remove_job(job_id):
    async with _lock:
        jobs = _load()
        kept = [j for j in jobs if j.get("id") != job_id]
        changed = len(kept) != len(jobs)
        if changed:
            _save(kept)
    logger.info("unscheduled %s (found=%s)", job_id, changed)
    return changed


def _focus_vscode_terminal():
    """Move keyboard focus into the VS Code integrated terminal via the command
    palette. Position-/layout-independent (a fixed click can't work — the window
    may be moved/resized, and raw focus lands in the editor, not the terminal)."""
    import pyautogui
    from handlers.input import _type_text

    pyautogui.hotkey("ctrl", "shift", "p")
    time.sleep(0.35)
    _type_text("Terminal: Focus on Terminal View")
    time.sleep(0.25)
    pyautogui.press("enter")
    time.sleep(0.35)


def _fire_sync(job):
    """Focus the target window (best effort) then type the message + Enter.

    A settle delay after focus is essential: bringing a *non-foreground* window
    forward is async in Windows, so typing immediately would paste into the old
    foreground window. For VS Code targets, also move focus into the integrated
    terminal (where Claude Code runs) — plain window focus lands in the editor."""
    from handlers.input import _type_text
    import pyautogui

    window = job.get("window") or ""
    if window:
        try:
            from utils.window import focus_window_exact
            ok, msg = focus_window_exact(window)
            logger.debug("fire focus %r -> ok=%s (%s)", window, ok, msg)
        except Exception as e:
            logger.warning("focus failed for %r: %s", window, e)
        time.sleep(SCHEDULE_FOCUS_SETTLE)  # let the window actually come forward
        if job.get("terminal", True) and "Visual Studio Code" in window:
            try:
                _focus_vscode_terminal()
            except Exception as e:
                logger.warning("terminal focus failed: %s", e)
    _type_text(job["text"])
    if job.get("enter", True):
        pyautogui.press("enter")


async def run_scheduler_loop(bot=None):
    """Poll the store; fire due jobs. Started once from bot.py run()."""
    logger.info("scheduler loop started (poll %ss)", SCHEDULE_POLL)
    while True:
        try:
            now = int(time.time())
            due = []
            async with _lock:
                jobs = _load()
                remaining = [j for j in jobs if j.get("when", 0) > now]
                due = [j for j in jobs if j.get("when", 0) <= now]
                if due:
                    _save(remaining)
            for j in due:
                try:
                    await asyncio.to_thread(_fire_sync, j)
                    logger.info("fired scheduled %s", j["id"])
                    if bot:
                        try:
                            await bot.send_message(
                                ALLOWED_USER_ID,
                                f"⏰ Sent scheduled message:\n{j['text'][:3500]}",
                            )
                        except Exception as e:
                            logger.warning("scheduled notify failed: %s", e)
                except Exception as e:
                    logger.error("fire failed for %s: %s", j.get("id"), e)
        except Exception as e:
            logger.error("scheduler loop error: %s", e)
        await asyncio.sleep(SCHEDULE_POLL)
