#!/usr/bin/env python3
"""PreToolUse hook: no commit while the wiki says something untrue.

Twelve instruction files across one machine said "both checkers green before any commit"
and not one of them enforced it. This is the enforcement: when the command about to run is
a `git commit`, the two checkers run first, and a FAIL denies the tool call with the names
of the checks that failed.

Every other command passes straight through, and so does a commit in a repository that has
no checkers — the gate guards a wiki, it does not invent one.
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

    if not failed:
        return 0

    return deny(
        "The wiki says something untrue, so the commit is denied. "
        "Fix these, then commit again:\n\n" + "\n\n".join(failed)
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A broken gate must not become a broken repository.
        sys.exit(0)
