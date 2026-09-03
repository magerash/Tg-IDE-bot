"""Files attached from the phone: save to disk, hand back the PATH.

The target is Claude Code in a VS Code terminal. It cannot receive a pasted
document any more than it can receive a pasted image — but it DOES read a file
whose path appears in the prompt. So an attachment is saved on the PC and its
path is typed; the file arrives whole, instantly, whatever its size, instead of
being pushed through the clipboard as a wall of text that bracketed paste has to
survive.

One module for both entry points (Mini App upload + Telegram document): a second
copy is how one surface silently keeps doing it the old way.
"""
import logging
import os
import re
import time

from config import UPLOAD_DIR, UPLOAD_MAX_MB

logger = logging.getLogger("bot.uploads")

MAX_UPLOAD = UPLOAD_MAX_MB * 1024 * 1024

# Everything Windows forbids in a file name, plus control characters. The name
# arrives from a phone over an HTTP header, so it is attacker-shaped input:
# '..\..\autoexec.bat' must end up as 'autoexec.bat', never as a traversal.
_BAD_CHARS = re.compile(r'[\/:*?"<>|\x00-\x1f]+')
_NAME_CAP = 120


def safe_name(name: str) -> str:
    """A bare, writable file name — never a path, never empty."""
    name = _BAD_CHARS.sub("_", os.path.basename(str(name or "")))
    # Leading dots/spaces hide the file (and '..' is the traversal itself);
    # trailing dots/spaces are silently dropped by Windows on create.
    name = name.strip(" .")
    if len(name) > _NAME_CAP:
        stem, ext = os.path.splitext(name)
        name = stem[:_NAME_CAP - len(ext)] + ext
    return name or f"file_{int(time.time() * 1000)}"


def save_upload(data: bytes, name: str) -> str:
    """Write `data` into UPLOAD_DIR under a safe name; return the full path.

    An existing file is never overwritten — the same report.md sent twice is two
    files, because the first one may already be open in the session that asked
    for it.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = safe_name(name)
    path = os.path.join(UPLOAD_DIR, name)
    if os.path.exists(path):
        stem, ext = os.path.splitext(name)
        path = os.path.join(UPLOAD_DIR, f"{stem}_{int(time.time() * 1000)}{ext}")
    with open(path, "wb") as fh:
        fh.write(data)
    logger.debug("upload %r: %d bytes -> %s", name, len(data), path)
    return path


def path_token(path: str) -> str:
    """The exact string typed into the terminal for a saved file.

    Quoted only when the path holds a space (an unquoted one splits into two
    arguments), and always followed by a space so the next token — the user's
    own text — does not fuse onto the file name.
    """
    return f'"{path}" ' if " " in path else f"{path} "
