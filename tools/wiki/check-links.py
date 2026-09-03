#!/usr/bin/env python3
"""check-links.py — relative links in the wiki that resolve to nothing.

The fix for a dead link was never the expensive part. Telling a dead link from a link
*template* was — which is why hand-rolled versions of this script get written, used once
and thrown away, and the same class of breakage comes back two commits later.

What it reports:

  BROKEN     a link in prose whose target does not exist. Exit code 1.
  template   a link *shape*: inside a fenced block, or carrying a {{placeholder}} or an
             ellipsis. A template's links are correct relative to the document it
             GENERATES, not to the file it is written in. Counted, never complained
             about — a checker that cries about all ten is a checker somebody stops
             running, and a checker nobody runs is worth less than no checker at all.

Four traps, all of them paid for by somebody already:

  * Targets resolve against the file that contains them, and existence is checked across
    the WHOLE repo. A wiki links `../src/*.py` constantly, and a docs-only walk calls
    every one of them broken.
  * A fenced block may open with more backticks than it contains (````markdown wrapping
    ```markdown), so a closing fence must match the opening marker's character *and* be
    at least as long.
  * `](x)` inside an inline code span is prose about a link, not a link.
  * `.tmpl` files are skipped on purpose. They are not markdown yet.

Usage:  python3 check-links.py                # the current directory, quiet unless broken
        python3 check-links.py <dir>          # another tree
        python3 check-links.py --list         # also list the templates it skipped
        python3 check-links.py --anchors      # also report #fragment misses (never fails)

`--anchors` is a *report*, not a gate, and it never changes the exit code. A wiki writes
`[D-nnn](DECISIONS.md#d-nnn)` against a heading a renderer would slug as
`#d-nnn--the-whole-title`, so enforcing fragments would fail hundreds of citations that
work perfectly well for every reader the repo actually has. The slug here approximates
GitHub's for the same reason: it informs, it does not gate.

Python 3 stdlib only. No network, no config, no build step.
"""

import os
import re
import sys
from urllib.parse import unquote

# ](target) or ](<target with spaces>), with an optional "title" or 'title'.
INLINE = re.compile(r"""\]\(\s*(?:<([^>]*)>|([^\s)]*))\s*(?:"[^"]*"|'[^']*')?\s*\)""")
# [label]: target — a reference definition, at most three spaces of indent.
REFDEF = re.compile(r"""^ {0,3}\[[^\]]+\]:\s*(?:<([^>]*)>|(\S+))""")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CODESPAN = re.compile(r"(`+).*?\1")
SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*:", re.I)
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.*?)\s*#*\s*$")

PLACEHOLDERS = ("{{", "…")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", "dist", "build"}


def scrub_code(line):
    """Blank out inline code spans, keeping every column where it was."""
    return CODESPAN.sub(lambda m: " " * len(m.group(0)), line)


def slug(text):
    """Approximate a renderer's heading slug. Informational only — see --anchors above."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [text](url) -> text
    t = t.replace("`", "").replace("*", "").replace("~", "").replace("_", "")
    t = re.sub(r"[^\w\- ]", "", t.lower(), flags=re.UNICODE)
    return t.strip().replace(" ", "-")


def read_lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def headings(path):
    """The slugs a #fragment could name in this file."""
    out, fence = set(), None
    for raw in read_lines(path):
        m = FENCE.match(raw)
        if m:
            tok = m.group(1)
            if fence is None:
                fence = tok
            elif tok[0] == fence[0] and len(tok) >= len(fence):
                fence = None
            continue
        if fence is None:
            h = HEADING.match(raw)
            if h:
                out.add(slug(h.group(1)))
    return out


def links(path):
    """Yield (line_no, target, is_template) for every link in one markdown file."""
    fence = None
    for n, raw in enumerate(read_lines(path), 1):
        m = FENCE.match(raw)
        if m:
            tok = m.group(1)
            if fence is None:
                fence = tok
            elif tok[0] == fence[0] and len(tok) >= len(fence):
                fence = None
            continue

        # Inside a fence everything is code, so there is nothing to scrub; outside it,
        # a code span is prose about a link rather than a link.
        line = raw if fence is not None else scrub_code(raw)

        found = [(g1 or g2) for g1, g2 in INLINE.findall(line)]
        ref = REFDEF.match(line)
        if ref:
            found.append(ref.group(1) or ref.group(2))

        for target in found:
            target = (target or "").strip()
            if target:
                yield n, target, fence is not None or any(p in target for p in PLACEHOLDERS)


def ignored_dirs(root):
    """Directory names this repo already ignores, from bare `name/` lines in .gitignore.

    A directory git does not track is not this repo's documentation — most often it holds
    files copied in from somewhere else, whose relative links resolve against the repo they
    came from. Reporting those as broken trains people to skim the broken list, which is
    the one habit this checker cannot survive.
    """
    names = set()
    path = os.path.join(root, ".gitignore")
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith(("#", "!")) or not line.endswith("/"):
                    continue
                bare = line.rstrip("/")
                if bare and "*" not in bare and "?" not in bare:
                    names.add(os.path.basename(bare))
    except OSError:
        pass
    return names


def walk(root):
    skip = SKIP_DIRS | ignored_dirs(root)
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        for name in sorted(files):
            if name.endswith(".md"):
                yield os.path.join(base, name)


def check(root, want_anchors=False):
    broken, templates, anchors, total, frags, files = [], [], [], 0, 0, 0

    for path in walk(root):
        files += 1
        rel = os.path.relpath(path, root)
        for n, target, is_template in links(path):
            total += 1
            if is_template:
                templates.append((rel, n, target))
                continue
            if SCHEME.match(target):  # http:, https:, mailto:
                continue

            frag = ""
            if "#" in target:
                target, frag = target.split("#", 1)
            filepart = unquote(target)

            resolved = path if not filepart else os.path.normpath(
                os.path.join(os.path.dirname(path), filepart))
            if filepart and not os.path.exists(resolved):
                broken.append((rel, n, (target + "#" + frag) if frag else target))
                continue

            if frag and resolved.endswith(".md"):
                frags += 1
                if want_anchors and slug(unquote(frag)) not in headings(resolved):
                    anchors.append((rel, n, os.path.relpath(resolved, root) + "#" + frag))

    return broken, templates, anchors, total, frags, files


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    root = os.path.abspath(args[0]) if args else os.getcwd()

    if not os.path.isdir(root):
        print("not a directory: %s" % root)
        return 2

    broken, templates, anchors, total, frags, files = check(root, "--anchors" in flags)

    for rel, n, target in broken:
        print("BROKEN  %s:%d  ->  %s" % (rel, n, target))
    if "--list" in flags:
        for rel, n, target in templates:
            print("template %s:%d  ->  %s" % (rel, n, target))
    if "--anchors" in flags:
        for rel, n, target in anchors:
            print("anchor?  %s:%d  ->  %s" % (rel, n, target))
        print("%d of %d #fragment(s) name no heading — reported, not enforced"
              % (len(anchors), frags))

    print("%d link%s in %d markdown file%s: %d broken, %d template%s skipped"
          % (total, "" if total == 1 else "s", files, "" if files == 1 else "s",
             len(broken), len(templates), "" if len(templates) == 1 else "s"))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
