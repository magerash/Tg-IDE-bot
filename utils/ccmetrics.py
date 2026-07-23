"""Claude Code live metrics — reads local ~/.claude state to expose the same
numbers the CLI shows in the VS Code terminal: active model + effort, context
usage %, and the 5-hour / weekly rate-limit blocks.

Sources (all local files written by Claude Code / OMC):
  - 5h + weekly limits: OMC usage cache `.usage-cache-anthropic.json`
  - model / effort / context tokens: newest session transcript `.jsonl`
"""
import glob
import json
import logging
import os
import re
import time

from config import CC_USAGE_CACHE, CC_PROJECTS_DIR, CC_CONTEXT_WINDOW

logger = logging.getLogger("bot.ccmetrics")


def _read_usage_cache():
    """5h + weekly limit block from the OMC anthropic usage cache."""
    try:
        with open(CC_USAGE_CACHE, encoding="utf-8") as f:
            d = json.load(f)
        data = d.get("data", {})
        ts = d.get("timestamp")
        return {
            "five_hour_percent": data.get("fiveHourPercent"),
            "five_hour_resets_at": data.get("fiveHourResetsAt"),
            "weekly_percent": data.get("weeklyPercent"),
            "weekly_resets_at": data.get("weeklyResetsAt"),
            "usage_age_sec": int(time.time() - ts / 1000) if ts else None,
            "usage_stale": bool(d.get("error")),
        }
    except FileNotFoundError:
        logger.debug("usage cache not found: %s", CC_USAGE_CACHE)
        return {}
    except Exception as e:
        logger.debug("usage cache read failed: %s", e)
        return {}


def _tail_lines(path, max_bytes=200_000):
    """Read only the tail of a (possibly large) transcript, split into lines."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        return f.read().decode("utf-8", "replace").splitlines()


def _newest_transcript():
    """Path of the most recently written session transcript across all projects."""
    files = glob.glob(os.path.join(CC_PROJECTS_DIR, "*", "*.jsonl"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _project_transcript(project_dir):
    """Newest transcript for a specific project dir (Claude Code encodes the path
    as a folder name, replacing ':' '\\' '/' and spaces with '-')."""
    if not project_dir:
        return None
    folder = re.sub(r"[:\\/ ]", "-", os.path.abspath(project_dir))
    files = glob.glob(os.path.join(CC_PROJECTS_DIR, folder, "*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def _read_session(project_dir=None):
    """Model, effort, context tokens + session identity from the active transcript.
    With project_dir set, reads that project's newest session (no cross-project
    fallback); otherwise the globally most-recent session."""
    path = _project_transcript(project_dir) if project_dir else _newest_transcript()
    if not path:
        return {"session_found": False} if project_dir else {}
    try:
        lines = _tail_lines(path)
    except Exception as e:
        logger.debug("transcript read failed: %s", e)
        return {}

    model = effort = usage = cwd = branch = None
    for ln in reversed(lines):
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if effort is None and o.get("effort"):
            effort = o["effort"]
        if cwd is None and o.get("cwd"):
            cwd = o["cwd"]
        if branch is None and o.get("gitBranch"):
            branch = o["gitBranch"]
        msg = o.get("message")
        if usage is None and isinstance(msg, dict) and msg.get("usage"):
            model = msg.get("model")
            usage = msg["usage"]
        if model and effort and usage and cwd:
            break

    out = {}
    if model:
        out["model"] = model
    if effort:
        out["effort"] = effort
    if cwd:
        out["session_dir"] = cwd
        out["session_project"] = os.path.basename(cwd.rstrip("\\/"))
    if branch:
        out["session_branch"] = branch
    if usage:
        ctx = (usage.get("input_tokens", 0)
               + usage.get("cache_read_input_tokens", 0)
               + usage.get("cache_creation_input_tokens", 0))
        out["context_tokens"] = ctx
        out["context_window"] = CC_CONTEXT_WINDOW
        out["context_percent"] = round(ctx / CC_CONTEXT_WINDOW * 100, 1) if CC_CONTEXT_WINDOW else None
    if path:
        try:
            out["session_age_sec"] = int(time.time() - os.path.getmtime(path))
        except OSError:
            pass
    return out


def collect(project_dir=None):
    """All Claude Code metrics for the /api/ccmetrics endpoint. With project_dir,
    session metrics come from that project's session; limits are always account-wide."""
    m = {}
    m.update(_read_usage_cache())
    m.update(_read_session(project_dir))
    logger.debug("ccmetrics(%s): model=%s effort=%s ctx=%s%% 5h=%s%% wk=%s%%",
                 os.path.basename(project_dir.rstrip("\\/")) if project_dir else "newest",
                 m.get("model"), m.get("effort"), m.get("context_percent"),
                 m.get("five_hour_percent"), m.get("weekly_percent"))
    return m
