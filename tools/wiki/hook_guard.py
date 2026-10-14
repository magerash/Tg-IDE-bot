#!/usr/bin/env python3
"""PreToolUse hook: deny the handful of commands whose mistake cannot be undone.

Across twenty-one project directories on the machine this kit was extracted from there
were six hundred allow entries in permission files and zero deny entries. Nothing was
denied anywhere. Discipline is not a control: it works until the one session where it
does not, and the commands below are exactly the ones where that session is expensive.

Each pattern names what it refuses and what to do instead, because a denial that does not
say the alternative just gets rephrased until it passes.
"""

import json
import re
import sys

RULES = (
    (r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rR][a-zA-Z]*[fF]|\brm\s+-[a-zA-Z]*[fF][a-zA-Z]*[rR]",
     "recursive force delete",
     "Delete named paths without -rf, or move them aside first."),
    (r"\bRemove-Item\b(?=.*-Recurse)(?=.*-Force)",
     "recursive force delete",
     "Remove named paths, or use -WhatIf first and show the operator the list."),
    (r"\bgit\s+push\b.*(--force(?!-with-lease)|(^|\s)-f(\s|$))",
     "force push",
     "Use --force-with-lease, and only when the operator asked for a rewrite."),
    (r"\bgit\s+reset\s+--hard\b",
     "hard reset",
     "git stash, or git restore the specific paths. A hard reset discards work "
     "that checkpoints do not track."),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f",
     "git clean",
     "List the untracked files first with git clean -n and show them."),
    (r"\bgit\s+checkout\s+--\s+\.",
     "discard every local change",
     "Name the paths to restore instead of the whole tree."),
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b",
     "destructive schema change",
     "Write it as a reviewed migration, not as an ad-hoc statement."),
    (r"\bTRUNCATE\s+TABLE\b",
     "table truncation",
     "Delete the rows the task actually names."),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)",
     "unfiltered DELETE",
     "Add a WHERE clause. An unfiltered DELETE is a truncation with extra steps."),
)

COMPILED = tuple((re.compile(p, re.IGNORECASE), what, instead) for p, what, instead in RULES)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0

    for pattern, what, instead in COMPILED:
        if pattern.search(command):
            json.dump({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Denied: {what}. {instead} "
                        "If this really is what the operator asked for, say so and let them "
                        "run it themselves — this hook is in .claude/settings.json."
                    ),
                }
            }, sys.stdout)
            sys.stdout.write("\n")
            return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
