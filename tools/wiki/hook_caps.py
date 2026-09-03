#!/usr/bin/env python3
"""PostToolUse hook: say when a file has grown past the budget its kind declares.

The budget table lives in .claude/rules/file-limits.md, filled by the project. This script
reads it rather than carrying numbers of its own — across the corpus this kit was extracted
from, four projects set a 150-line cap and each meant a different kind of file.

It warns and never blocks. A cap is a smell with a prescribed remedy, and the remedy is a
judgement the operator makes, not one a hook makes for them.
"""

import fnmatch
import json
import os
import re
import sys

RULES_FILE = os.path.join(".claude", "rules", "file-limits.md")
ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$")
PLACEHOLDER = re.compile(r"\{\{.+?\}\}")


def budgets(root):
    """Rows of (kind, glob, max_lines, remedy) from the project's own table."""
    path = os.path.join(root, RULES_FILE)
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = ROW.match(line.strip())
            if not match:
                continue
            cells = [c.strip() for c in match.group("cells").split("|")]
            if len(cells) != 4:
                continue
            kind, glob, limit, remedy = cells
            if PLACEHOLDER.search(line) or set(limit) <= set("- "):
                continue                                   # header rule, or unfilled template
            if not limit.isdigit():
                continue                                   # header row
            out.append((kind, glob, int(limit), remedy))
    return out


def edited_path(data):
    tool_input = data.get("tool_input") or {}
    return tool_input.get("file_path") or tool_input.get("notebook_path") or ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    path = edited_path(data)
    if not path or not os.path.isfile(path):
        return 0

    root = data.get("cwd") or os.getcwd()
    rows = budgets(root)
    if not rows:
        return 0

    try:
        relative = os.path.relpath(path, root)
    except ValueError:                                     # different drive on Windows
        relative = path
    relative = relative.replace(os.sep, "/")

    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = sum(1 for _ in fh)

    for kind, glob, limit, remedy in rows:
        if not fnmatch.fnmatch(relative, glob):
            continue
        if lines <= limit:
            return 0
        json.dump({
            "systemMessage": (
                f"{relative} is {lines} lines; the budget for a {kind} is {limit}. {remedy}"
            )
        }, sys.stdout)
        sys.stdout.write("\n")
        return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
