#!/usr/bin/env python3
"""PreToolUse hook: no commit while the wiki says something untrue.

Twelve instruction files across one machine said "both checkers green before any commit"
and not one of them enforced it. This is the enforcement: when the command about to run is
a `git commit`, the two checkers run first, and a FAIL denies the tool call with the names
of the checks that failed.

Every other command passes straight through, and so does a commit in a repository that has
no checkers — the gate guards a wiki, it does not invent one.

The second thing it guards is the message shape of a `versioned` project — one whose rules
say so, or whose docs/changelog.md carries an Open: line. The commit and the changelog entry
are the same artefact there: subject `vX.Y.Z Name of the session's work`, the version copied
from the Open: line, then a body that is a short list. Left to discipline the shape decayed
at both ends — one project's subjects reached 8 098 characters with nothing in the body;
this kit's bodies reached six paragraphs that the operator read as "the same as before". A
message the gate cannot see (an editor, a file it cannot read) passes: the gate guards what
it can read, it does not block on what it cannot.
"""

import json
import os
import re
import subprocess
import sys

# A commit, not a word that contains one. `--dry-run` is a question, not a commit.
COMMIT = re.compile(r"(^|[;&|]\s*)git\s+(-[^\s]+\s+|--\S+\s+)*commit\b")
DRY_RUN = re.compile(r"--dry-run\b")

CHECKERS = (
    ("check-links", ["check-links.py"]),
    ("wiki-doctor", ["wiki-doctor.py"]),
)
TIMEOUT = 120

# The versioned subject: `vX.Y.Z Name`, and the places the version may be copied from.
VERSIONED = re.compile(r"releases as `versioned`")
SUBJECT = re.compile(r"^v\d+\.\d+\.\d+\S*\s+\S")
VERSION_OF = re.compile(r"^(v\d+\.\d+\.\d+\S*)")
OPEN_LINE = re.compile(r"^##\s+Open:\s*`?(v\d+\.\d+\.\d+[^`\s]*)`?", re.M)
ENTRY_LINE = re.compile(r"^###\s+(v\d+\.\d+\.\d+\S*)", re.M)
SUBJECT_MAX = 95
BODY_MAX = 20                     # non-empty body lines; the list of changes, not an essay
TRAILER = re.compile(r"^[A-Za-z][A-Za-z-]+: \S")   # Co-Authored-By:, Signed-off-by:, …
# How a message reaches `git commit` from a shell line: -m/--message inline, -F/--file, or
# `-F -` with a heredoc. Only the first -m is the subject; git joins later ones as paragraphs.
MSG_FLAG = re.compile(r"""(?:^|\s)(?:-m|--message)(?:=|\s+)(?:"((?:[^"\\]|\\.)*)"|'([^']*)'|(\S+))""")
FILE_FLAG = re.compile(r"""(?:^|\s)(?:-F|--file)(?:=|\s+)(?:"([^"]+)"|'([^']+)'|(\S+))""")
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\1\s*$", re.S)


def deny(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.stdout.write("\n")
    return 0


def command_of(data):
    tool_input = data.get("tool_input") or {}
    return tool_input.get("command") or ""


def run_checker(root, script):
    """Return (ok, output). A checker that is not installed is not a failure.

    `tools/wiki/` is where a scaffolded project keeps them. `tools/` is where the kit itself
    keeps them, so the gate guards the repository that ships it too.
    """
    for folder in ("tools/wiki", "tools"):
        path = os.path.join(root, folder.replace("/", os.sep), script)
        if os.path.isfile(path):
            break
    else:
        return True, ""
    try:
        done = subprocess.run(
            [sys.executable, path],
            cwd=root, capture_output=True, text=True, timeout=TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # The gate could not form an opinion. Say so, do not block on it.
        return True, f"({script} could not run: {exc})"
    return done.returncode == 0, (done.stdout or done.stderr or "").strip()


def message_of(command, root):
    """The whole message this command would commit, or None if the gate cannot read it."""
    parts = [next(g for g in m.groups() if g is not None) for m in MSG_FLAG.finditer(command)]
    if parts:
        # git joins several -m values as paragraphs
        return "\n\n".join(p.replace("\\n", "\n") for p in parts)
    m = FILE_FLAG.search(command)
    if not m:
        return None
    path = next(g for g in m.groups() if g is not None)
    if path == "-":
        h = HEREDOC.search(command)
        return h.group(2) if h else None
    if "$" in path:
        return None                   # an unexpanded variable; the gate cannot read it
    full = path if os.path.isabs(path) else os.path.join(root, path)
    try:
        with open(full, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def split_message(text):
    """(subject, body_lines): the first non-empty line, then every later non-empty line
    that is not a trailer such as Co-Authored-By."""
    lines = text.strip().split("\n")
    subject = next((l.strip() for l in lines if l.strip()), "")
    rest = lines[lines.index(next(l for l in lines if l.strip())) + 1:]
    body = [l for l in rest if l.strip() and not TRAILER.match(l.strip())]
    return subject, body


def release_mode(root):
    """`versioned` when the rules say so, or when docs/changelog.md carries an Open: line —
    a changelog with an open version is itself the declaration. Otherwise None."""
    path = os.path.join(root, ".claude", "rules", "documentation.md")
    try:
        with open(path, encoding="utf-8") as fh:
            if VERSIONED.search(fh.read()):
                return "versioned"
    except OSError:
        pass
    open_v, _released = known_versions(root)
    return "versioned" if open_v else None


def known_versions(root):
    """The open version and every released one, from docs/changelog.md. Empty if none."""
    path = os.path.join(root, "docs", "changelog.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None, []
    open_v = OPEN_LINE.search(text)
    return (open_v.group(1) if open_v else None), ENTRY_LINE.findall(text)


def check_body(body):
    """None when the body is a list a person scans, else the reason it is not."""
    if len(body) > BODY_MAX:
        return ("the body is %d lines; the shape is a list of roughly %d at most — one emoji "
                "bullet per change, a Wiki line, a \u2705 instruments line, the ids. The "
                "reasoning belongs in the session chunk, and the commit points at it."
                % (len(body), BODY_MAX))
    return None


def check_subject(root, subject):
    """None when the subject fits the versioned profile, else the reason it does not."""
    shape = ("this project releases as `versioned`, so the subject is "
             "`vX.Y.Z Name of the session's work` — the version copied from the Open: line "
             "of docs/changelog.md — then one line per change in the body.")
    if not SUBJECT.match(subject):
        return "%s\nGot: %r" % (shape, subject)
    if len(subject) > SUBJECT_MAX:
        return ("the subject is %d characters; the limit is %d so `git log --oneline` does "
                "not wrap. The list of changes is the body, not the subject.\nGot: %r"
                % (len(subject), SUBJECT_MAX, subject))
    open_v, released = known_versions(root)
    allowed = [v for v in [open_v] + released if v]
    version = VERSION_OF.match(subject).group(1)
    if allowed and version not in allowed:
        return ("the subject names %s, but docs/changelog.md opens %s (released: %s). "
                "A commit copies the open version; only the release commit carries the "
                "number of the entry it adds. Nothing bumps a version except `Let's finish`."
                % (version, open_v or "nothing", ", ".join(released[:3]) or "none"))
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    command = command_of(data)
    if not command or not COMMIT.search(command) or DRY_RUN.search(command):
        return 0

    root = data.get("cwd") or os.getcwd()
    failed = []
    for name, argv in CHECKERS:
        ok, output = run_checker(root, argv[0])
        if not ok:
            tail = "\n".join(output.splitlines()[-12:])
            failed.append(f"{name}:\n{tail}")

    if release_mode(root) == "versioned":
        message = message_of(command, root)
        if message is not None:
            subject, body = split_message(message)
            reason = check_subject(root, subject)
            if reason:
                failed.append("commit-subject:\n" + reason)
            reason = check_body(body)
            if reason:
                failed.append("commit-body:\n" + reason)

    if not failed:
        return 0

    return deny(
        "The commit is denied — the wiki says something untrue, or the message does not "
        "fit the shape this project declared. Fix these, then commit again:\n\n"
        + "\n\n".join(failed)
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A broken gate must not become a broken repository.
        sys.exit(0)
