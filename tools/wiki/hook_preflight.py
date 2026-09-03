#!/usr/bin/env python3
"""SessionStart hook: print the preflight so the session starts knowing four things.

Wired from .claude/settings.json. Reads the hook payload on stdin, writes plain text on
stdout — Claude Code surfaces a SessionStart hook's stdout as session context.

It never blocks and never fails the session: every check is best-effort, and a missing
wiki simply produces a shorter preflight. A hook that can break the session start is a
hook somebody disables.
"""

import json
import os
import re
import subprocess
import sys

MAX_ROWS = 8          # a board with more than this in flight has a different problem
CHUNKS_SHOWN = 2      # the last two chunks say what was left on the floor


def payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def git(cwd, *args):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_lines(cwd):
    """Branch and dirty-file count, or None outside a repository."""
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return None
    status = git(cwd, "status", "--porcelain") or ""
    dirty = [line for line in status.splitlines() if line.strip()]
    head = f"branch `{branch}`, {len(dirty)} uncommitted file(s)"
    if dirty:
        shown = ", ".join(line[3:] for line in dirty[:5])
        more = "" if len(dirty) <= 5 else f", +{len(dirty) - 5} more"
        head += f" — {shown}{more}"
    return head


WORKING = ("now", "next", "later")


def board_rows(root):
    """Rows marked in progress in a working table.

    Only Now / Next / Later count. The glyph legend at the top of the board is a table
    that contains a ▶ in every copy of the template, and reporting it as work in flight on
    a repository's first day is how a preflight teaches people to ignore preflights.
    """
    path = os.path.join(root, "docs", "ROADMAP.md")
    if not os.path.isfile(path):
        return []
    rows, section = [], ""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            if line.startswith("## "):
                section = line[3:].strip().lower()
                continue
            if section not in WORKING or "▶" not in line:
                continue
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3 or set("".join(cells)) <= set("-: "):
                continue
            rows.append(" · ".join(c for c in cells if c))
    return rows[:MAX_ROWS]


def recent_chunks(root):
    """The most recent session chunks by folder number, then filename."""
    sessions = os.path.join(root, "docs", "sessions")
    if not os.path.isdir(sessions):
        return []
    found = []
    for folder in sorted(os.listdir(sessions)):
        full = os.path.join(sessions, folder)
        if not os.path.isdir(full):
            continue
        number = re.match(r"(\d+)", folder)
        for name in sorted(os.listdir(full)):
            if name.endswith(".md") and name.upper() != "README.MD":
                found.append((int(number.group(1)) if number else 0, folder, name))
    found.sort()
    return [f"docs/sessions/{folder}/{name}" for _, folder, name in found[-CHUNKS_SHOWN:]]


def open_entries(root):
    """Count blockers and assumptions that are still open, wherever the tier put them."""
    counts = {}
    for filename, prefix, label in (
        ("BLOCKERS.md", "B-", "blocker"),
        ("ASSUMPTIONS.md", "A-", "assumption"),
        ("DECISIONS.md", "B-", "blocker"),
    ):
        path = os.path.join(root, "docs", filename)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        ids = set(re.findall(r"^#+\s*(" + prefix + r"\d+)", text, re.MULTILINE))
        superseded = set(re.findall(r"^#+\s*(" + prefix + r"\d+).*SUPERSEDED", text, re.MULTILINE))
        if ids - superseded:
            counts.setdefault(label, set()).update(ids - superseded)
    return {label: len(ids) for label, ids in counts.items()}


def main():
    data = payload()
    root = data.get("cwd") or os.getcwd()

    lines = ["Preflight (docs/README.md), four checks:"]

    tree = git_lines(root)
    lines.append(f"1. Working tree: {tree}" if tree else "1. Working tree: not a git repository")

    rows = board_rows(root)
    if rows:
        lines.append(f"2. Board: {len(rows)} row(s) already in progress —")
        lines.extend(f"   ▶ {row}" for row in rows)
    elif os.path.isfile(os.path.join(root, "docs", "ROADMAP.md")):
        lines.append("2. Board: nothing in progress. Mark your row ▶ before the first edit.")
    else:
        lines.append("2. Board: no docs/ROADMAP.md in this repository.")

    chunks = recent_chunks(root)
    if chunks:
        lines.append("3. Last chunks: " + ", ".join(chunks))
    else:
        lines.append("3. Last chunks: none recorded yet.")

    counts = open_entries(root)
    if counts:
        lines.append("4. Open: " + ", ".join(f"{n} {label}(s)" for label, n in sorted(counts.items())))
    else:
        lines.append("4. Open: no unsuperseded blockers found.")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                      # never break a session start
        print(f"preflight unavailable: {exc}")
        sys.exit(0)
