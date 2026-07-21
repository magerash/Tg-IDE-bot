"""Current project state shared by /git, /build, /apk, /code, panel and web."""
import logging
import os

from config import GIT_DIR, PROJECTS_ROOT

logger = logging.getLogger("bot.project")

# GIT_DIR falls back to PROJECT_DIR in config; env override respected
_current_dir: str = GIT_DIR


def get_dir() -> str:
    """Absolute path of the current project."""
    return _current_dir


def get_name() -> str:
    """Folder name of the current project."""
    return os.path.basename(_current_dir.rstrip("\\/"))


def set_dir(path: str) -> str:
    """Set current project to an arbitrary directory."""
    global _current_dir
    _current_dir = os.path.abspath(path)
    logger.debug("Current project set: %s", _current_dir)
    return _current_dir


def set_by_name(folder: str) -> str:
    """Set current project to a folder under PROJECTS_ROOT."""
    return set_dir(os.path.join(PROJECTS_ROOT, folder))


def list_projects() -> list[str]:
    """List subfolders of PROJECTS_ROOT."""
    try:
        return sorted(
            d for d in os.listdir(PROJECTS_ROOT)
            if os.path.isdir(os.path.join(PROJECTS_ROOT, d)) and not d.startswith(".")
        )
    except OSError as e:
        logger.error("PROJECTS_ROOT listing error: %s", e)
        return []


def project_of(path: str) -> str:
    """Project folder name a path belongs to, or 'other'."""
    root = os.path.abspath(PROJECTS_ROOT)
    p = os.path.abspath(path)
    if os.path.normcase(p).startswith(os.path.normcase(root) + os.sep):
        return p[len(root) + 1:].split(os.sep)[0]
    return "other"
