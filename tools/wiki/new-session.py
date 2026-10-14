#!/usr/bin/env python3
"""new-session.py — open a session, or add a chunk, without racing anybody for the number.

    python3 new-session.py "the cache lied about tenants"    # new session folder + chunk
    python3 new-session.py --chunk "the second fix"          # chunk in the newest session
    python3 new-session.py --chunk --in 7 "a third thing"    # chunk in session 7
    python3 new-session.py --date 2026-08-01 "backdated"     # for writing up yesterday

Why this is a script and not an instruction.

Claiming a session number is a read-then-write, and with two agents in one checkout the
gap between the two is real. In the project this method came from, session numbers 16 and
33/34/44 tell the story: one number used twice, three claimed and abandoned, all inside a
week of parallel work. A number that means two things breaks every citation to it, and the
citations are the point.

So the claim here IS the directory creation — `os.mkdir` fails if the name is taken, which
makes the check and the claim one atomic operation instead of two. Losing the race costs a
retry with the next number, not a collision.

It also writes both index rows, because the index row is regulation step 4 and it is the
step people skip when they are in a hurry — which is exactly when the chunk matters most.

Python 3 stdlib only.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys

CHUNK_TEMPLATE = """# {date} — {topic}

## What was done

<!-- The change, in the domain's words. A table of file → what it now does works well. -->

## How it works

<!-- The mechanism, so the next reader does not have to re-derive it from the diff. -->

## Decisions (and why)

<!-- Cite the D-/A-/B- ids written this session, one line each. Do not restate them. -->

## Verification

<!-- What you ran and what it said. For a planning session this is not empty — it is:
     every cited path exists, every id resolves, the checkers are clean. -->

```bash
python3 tools/wiki/check-links.py && python3 tools/wiki/wiki-doctor.py
```

## Next

<!-- What you would do first if you sat down again tomorrow. Be specific: "row 4" is
     useful, "continue" is not. This is the heading the next session actually reads. -->
"""

FOLDER_README = """# Session {num:02d} — {topic}

**{date}.** {{one or two sentences: what this episode of work was.}}

| Date | Chunk | Topic |
|---|---|---|
| {date} | [{chunk}]({chunk}) | {topic} |

**Produced:** {{links to what came out of it — ledger entries, board rows, documents}}
"""


def slugify(text, limit=50):
    slug = re.sub(r"[^\w]+", "-", text.strip().lower(), flags=re.UNICODE).strip("-")
    if len(slug) > limit:
        slug = slug[:limit].rsplit("-", 1)[0] or slug[:limit]
    return slug or "session"


def find_sessions(root):
    for candidate in ("docs/sessions", "sessions"):
        path = os.path.join(root, candidate)
        if os.path.isdir(path):
            return path
    sys.exit("no docs/sessions/ under %s — run this from the repo root" % root)


def existing(sessions):
    """{number: folder_name} for every NN-slug folder."""
    out = {}
    for name in sorted(os.listdir(sessions)):
        m = re.match(r"^(\d+)-(.+)$", name)
        if m and os.path.isdir(os.path.join(sessions, name)):
            out[int(m.group(1))] = name
    return out


def claim(sessions, slug):
    """Create the next free NN-slug directory. The mkdir IS the claim."""
    number = max(existing(sessions) or [0]) + 1
    while number < 1000:
        folder = "%02d-%s" % (number, slug)
        try:
            os.mkdir(os.path.join(sessions, folder))
            return number, folder
        except FileExistsError:
            number += 1          # somebody else got there between our read and our write
    sys.exit("could not claim a session number below 1000 — something is wrong")


def insert_row(path, label, cells_by_header, dry):
    """Insert a row into the first table whose header mentions a session or a chunk.

    Rows go directly under the separator, because every one of these tables is newest
    first and the row you are adding is the newest thing that has happened.
    """
    if not os.path.isfile(path):
        return False
    lines = open(path, encoding="utf-8").read().splitlines()
    for i, line in enumerate(lines[:-1]):
        if not line.startswith("|"):
            continue
        headers = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if not any(h in ("session", "chunk", "#") for h in headers):
            continue
        nxt = lines[i + 1]
        if not (nxt.startswith("|") and set(nxt.replace("|", "")) <= set("-: ")):
            continue
        row = "| " + " | ".join(cells_by_header(h) for h in headers) + " |"
        if not dry:
            lines.insert(i + 2, row)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        print("  %s  %s" % ("would index in" if dry else "indexed in    ", label))
        return True
    print("  no session table found in %s — add the row by hand" % label)
    return False


def main():
    ap = argparse.ArgumentParser(description="Open a session, or add a chunk to one.")
    ap.add_argument("topic", help="what this piece of work is about, in a few words")
    ap.add_argument("--chunk", action="store_true", help="add to an existing session")
    ap.add_argument("--in", dest="session", type=int, help="which session (with --chunk)")
    ap.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--root", default=os.getcwd(), help="repo root, defaults to cwd")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        sys.exit("--date must be YYYY-MM-DD")

    root = os.path.abspath(args.root)
    sessions = find_sessions(root)
    slug = slugify(args.topic)
    have = existing(sessions)

    if args.chunk or args.session:
        number = args.session if args.session else (max(have) if have else None)
        if number not in have:
            sys.exit("session %s does not exist. Sessions: %s"
                     % (number, ", ".join(str(n) for n in sorted(have)) or "none"))
        folder = have[number]
        fresh = False
    elif args.dry_run:
        number, folder, fresh = (max(have or [0]) + 1), "%02d-%s" % (max(have or [0]) + 1, slug), True
    else:
        number, folder = claim(sessions, slug)
        fresh = True

    chunk_name = "%s-%s.md" % (date, slug)
    chunk_path = os.path.join(sessions, folder, chunk_name)
    if os.path.exists(chunk_path):
        sys.exit("%s already exists — pick a different topic, or edit it" % chunk_path)

    print("session %02d  %s" % (number, folder))
    if not args.dry_run:
        with open(chunk_path, "w", encoding="utf-8") as fh:
            fh.write(CHUNK_TEMPLATE.format(date=date, topic=args.topic))
    print("  %s  %s" % ("would write  " if args.dry_run else "wrote        ",
                        os.path.relpath(chunk_path, root)))

    readme = os.path.join(sessions, folder, "README.md")
    if fresh and not os.path.exists(readme):
        if not args.dry_run:
            with open(readme, "w", encoding="utf-8") as fh:
                fh.write(FOLDER_README.format(num=number, topic=args.topic,
                                              date=date, chunk=chunk_name))
        print("  %s  %s" % ("would write  " if args.dry_run else "wrote        ",
                            os.path.relpath(readme, root)))

    def cells(header, prefix=""):
        link = "[%s](%s%s/%s)" % (args.topic, prefix, folder, chunk_name)
        return {
            "#": "%02d" % number,
            "date": date, "dates": date, "landed": date,
            "session": "%02d · %s" % (number, args.topic) if prefix else
                       "[%02d · %s](%s/README.md)" % (number, args.topic, folder),
            "chunk": link, "topic": args.topic,
        }.get(header, args.topic)

    index = os.path.join(sessions, "README.md")
    insert_row(index, os.path.relpath(index, root), lambda h: cells(h), args.dry_run)
    entry = os.path.join(os.path.dirname(sessions), "README.md")
    if os.path.abspath(entry) != os.path.abspath(index):
        insert_row(entry, os.path.relpath(entry, root),
                   lambda h: cells(h, "sessions/"), args.dry_run)

    # A new chunk moves the counts, and a total nobody regenerates is the defect the
    # marker exists to prevent. The tool that changed it is the tool that fixes it.
    doctor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiki-doctor.py")
    if os.path.isfile(doctor) and not args.dry_run:
        subprocess.run([sys.executable, doctor, "--fix", root],
                       check=False, stdout=subprocess.DEVNULL)

    print("\nNow: set your row in the roadmap to ▶ before the first edit, if you have not.")


if __name__ == "__main__":
    main()
