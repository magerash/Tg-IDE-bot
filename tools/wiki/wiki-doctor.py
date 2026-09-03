#!/usr/bin/env python3
"""wiki-doctor.py — the checks the update regulation otherwise trusts to discipline.

Every check here exists because the failure it catches actually happened in the project
this method was extracted from. None of them is clever; all of them are things a person
was supposed to do by hand, forgot once, and then kept forgetting.

    python3 wiki-doctor.py              # the current directory
    python3 wiki-doctor.py <dir>        # another repo
    python3 wiki-doctor.py --fix        # rewrite the mechanical things (counts blocks)
    python3 wiki-doctor.py --strict     # warnings become failures
    python3 wiki-doctor.py --list       # print what each check does, and exit

FAIL vs WARN, and why the line is where it is:

  FAIL  the wiki says something untrue, or an id no longer resolves. A reader acting on
        it is misled. Exit code 1.
  WARN  the writing is thin — a chunk with no Verification section, a decision nobody
        ever cited. Nothing is false; something is missing. Exit code 0, unless --strict.

The checks adapt to the tier: a Core project has one ledger file and no cards, and the
checks that need `ASSUMPTIONS.md` or `rows/` simply do not run rather than complaining
about a tier you did not ask for.

Python 3 stdlib only. No network, no config file, no third-party imports.
"""

import os
import re
import sys

CHECKS = [
    ("counts", "the counts block in the entry point matches the ledgers and the board"),
    ("budget", "the entry point is under the line budget it declares"),
    ("codemap", "every path named in the code map exists"),
    ("ids", "every D-/A-/B- citation resolves; no duplicates; nothing defined and never cited"),
    ("board", "row ids unique; no done rows in the working tables; parallel rows name their lanes"),
    ("cards", "every open board row has a card, and every card has a row (Full tier)"),
    ("sessions", "every chunk is indexed, every folder numbered once, chunks carry the required headings"),
    ("specs", "no spec claims built while its board row says not started"),
    ("manifest", "every starter template has a manifest row and vice versa (the kit itself)"),
    ("agentlayer", "skills, agents and rules parse, fit their budgets, and carry no unfilled placeholder"),
]

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", "dist", "build"}
SOURCE_EXT = (".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java",
              ".c", ".h", ".cpp", ".sh", ".sql", ".html", ".css", ".toml", ".yaml", ".yml")

ENTRY = re.compile(r"^##\s+~*\s*(D|A|B)-0*(\d+)", re.M)
FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CITE = re.compile(r"(?<![\w-])(D|A|B)-(\d{1,4})(?![\w-])")
BUDGET = re.compile(r"budget[^.\n]*?(\d+)\s*lines", re.I)
COUNTS = re.compile(r"(<!--\s*counts:begin\s*-->)(.*?)(<!--\s*counts:end\s*-->)", re.S)
CHUNK = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
SESSION_DIR = re.compile(r"^(\d+)-(.+)$")
CARD = re.compile(r"^(\d+)-.+\.md$")
PATHISH = re.compile(r"`([^`\s]+)`")
REQUIRED_HEADINGS = ["## What was done", "## Verification", "## Next"]
EXPECTED_HEADINGS = ["## How it works", "## Decisions"]


class Report:
    def __init__(self):
        self.items = []

    def fail(self, check, where, message):
        self.items.append(("FAIL", check, where, message))

    def warn(self, check, where, message):
        self.items.append(("WARN", check, where, message))

    @property
    def failures(self):
        return [i for i in self.items if i[0] == "FAIL"]

    @property
    def warnings(self):
        return [i for i in self.items if i[0] == "WARN"]


def read(path):
    # utf-8-sig, not utf-8: a byte-order mark is invisible in an editor and turns the first
    # line of a file into something that matches nothing. A Windows editor writes one by
    # default, and the failure it produces — "this file has no frontmatter", about a file
    # whose frontmatter you are looking at — costs an hour the first time.
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def rel(root, path):
    # Forward slashes, always. Paths from this function are compared against paths written
    # in documents — MANIFEST.md rows, code-map lines — and those are written the one way
    # that reads the same on every machine. On Windows os.path.relpath returns backslashes,
    # and every such comparison silently fails.
    return os.path.relpath(path, root).replace(os.sep, "/")


def walk(root, exts):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(exts):
                yield os.path.join(base, name)


# ---------------------------------------------------------------- layout discovery

class Wiki:
    """Where things are in this repo, and which tier it is running."""

    def __init__(self, root):
        self.root = root
        self.docs = os.path.join(root, "docs")
        self.entry = self._first("README.md")
        self.codemap = self._first("code-map.md")
        self.roadmap = self._first("ROADMAP.md", "plans/ROADMAP.md")
        self.sessions = os.path.join(self.docs, "sessions")
        self.rows = self._dir("rows", "plans/rows")
        self.specs = self._dir("specs")
        self.ledgers = [p for p in (self._first("DECISIONS.md"),
                                    self._first("ASSUMPTIONS.md"),
                                    self._first("BLOCKERS.md")) if p]

    def _first(self, *names):
        for name in names:
            path = os.path.join(self.docs, name)
            if os.path.isfile(path):
                return path
        return None

    def _dir(self, *names):
        for name in names:
            path = os.path.join(self.docs, name)
            if os.path.isdir(path):
                return path
        return None

    @property
    def ok(self):
        return os.path.isdir(self.docs) and self.entry


# ---------------------------------------------------------------- parsing helpers

def ledger_entries(wiki):
    """{'D': {1: path, 2: path}, ...} plus a list of duplicate (kind, num, path)."""
    found, dupes = {"D": {}, "A": {}, "B": {}}, []
    for path in wiki.ledgers:
        for kind, num in ENTRY.findall(read(path)):
            num = int(num)
            if num in found[kind]:
                dupes.append((kind, num, path))
            else:
                found[kind][num] = path
    return found, dupes


def board_rows(wiki):
    """[(id, state, section, line_no)] from the roadmap's tables."""
    if not wiki.roadmap:
        return []
    rows, section = [], ""
    for n, line in enumerate(read(wiki.roadmap).splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or set(cells[0]) <= set("-: "):
            continue
        if section in ("now", "next", "later"):
            ident, state = cells[0], cells[1]
        elif section == "done":
            ident, state = cells[1], "✅"
        else:
            continue
        m = re.match(r"^\**(\d+)\**$", ident)
        if m:
            rows.append((int(m.group(1)), state, section, n))
    return rows


def chunk_files(wiki):
    """[(session_number, folder, chunk_path)] for every dated chunk."""
    out = []
    if not os.path.isdir(wiki.sessions):
        return out
    for folder in sorted(os.listdir(wiki.sessions)):
        full = os.path.join(wiki.sessions, folder)
        if not os.path.isdir(full):
            continue
        m = SESSION_DIR.match(folder)
        num = int(m.group(1)) if m else None
        for name in sorted(os.listdir(full)):
            if CHUNK.match(name):
                out.append((num, folder, os.path.join(full, name)))
    return out


# ---------------------------------------------------------------- the checks

def check_counts(wiki, rep, fix):
    if not (wiki.ledgers or wiki.roadmap or os.path.isdir(wiki.sessions)):
        return  # not a project wiki — the kit's own docs/ is a manual, not a memory
    text = read(wiki.entry)
    m = COUNTS.search(text)
    if not m:
        rep.warn("counts", rel(wiki.root, wiki.entry),
                 "no <!-- counts:begin --> block. Any total written by hand goes stale — "
                 "the source project's index claimed 48 decisions while its ledger held 110")
        return
    found, _ = ledger_entries(wiki)
    rows = board_rows(wiki)
    open_rows = [r for r in rows if r[2] in ("now", "next", "later")]
    inflight = [r for r in open_rows if "▶" in r[1]]
    chunks = chunk_files(wiki)
    folders = {c[1] for c in chunks}

    parts = ["**%d decision%s**" % (len(found["D"]), "" if len(found["D"]) == 1 else "s")]
    if found["A"]:
        parts.append("%d assumption%s" % (len(found["A"]), "" if len(found["A"]) == 1 else "s"))
    if found["B"]:
        parts.append("%d blocker%s" % (len(found["B"]), "" if len(found["B"]) == 1 else "s"))
    parts.append("**%d open row%s**%s" % (len(open_rows), "" if len(open_rows) == 1 else "s",
                                          " (%d in flight)" % len(inflight) if inflight else ""))
    parts.append("**%d session%s, %d chunk%s**" % (
        len(folders), "" if len(folders) == 1 else "s",
        len(chunks), "" if len(chunks) == 1 else "s"))
    want = "\n" + " · ".join(parts) + "\n*Regenerated by `wiki-doctor.py --fix` — do not edit by hand.*\n"

    if m.group(2).strip() == want.strip():
        return
    if fix:
        with open(wiki.entry, "w", encoding="utf-8") as fh:
            fh.write(text[:m.start(2)] + want + text[m.end(2):])
        print("fixed   counts      %s" % rel(wiki.root, wiki.entry))
    else:
        rep.fail("counts", rel(wiki.root, wiki.entry),
                 "the counts block is out of date — run with --fix. Should read: %s"
                 % " · ".join(parts).replace("**", ""))


def check_budget(wiki, rep, _fix):
    text = read(wiki.entry)
    m = BUDGET.search(text)
    if not m:
        return
    limit, actual = int(m.group(1)), len(text.splitlines())
    if actual > limit:
        rep.fail("budget", rel(wiki.root, wiki.entry),
                 "%d lines, over the %d-line budget this file declares. The entry point is "
                 "read at the start of every session; when it stops fitting in a glance it "
                 "stops being read. Move the session table and the concept index out and "
                 "leave pointers" % (actual, limit))


def check_codemap(wiki, rep, _fix):
    """Every path in the code map exists — the `test -e` pass nobody re-runs by hand.

    The whole difficulty is deciding what is a path. A code map is full of backticked
    things that look like one and are not: `http.server`, `sqlite3.Row`, `app.js`,
    `search.search()`, `/api/search?q=…`. Flagging those makes the check useless, so the
    rule is deliberately narrow — **a directory component, a file extension, and no
    punctuation that belongs to a URL or a call.** A bare filename in prose is a mention;
    `src/pinboard/store.py` is a claim.
    """
    if not wiki.codemap:
        return
    seen, checked = set(), 0
    for token in PATHISH.findall(read(wiki.codemap)):
        token = token.strip().rstrip(".,;:")
        token = re.sub(r":\d+$", "", token)          # path:line is still a path
        if token in seen or "/" not in token or token.startswith("/"):
            continue
        if any(ch in token for ch in "?=()*#…{} ") or "://" in token:
            continue
        if not re.search(r"\.[A-Za-z0-9]{1,8}$", token):
            continue                                  # no extension — too ambiguous to fail on
        seen.add(token)
        checked += 1
        candidates = [os.path.join(wiki.root, token),
                      os.path.join(os.path.dirname(wiki.codemap), token)]
        if not any(os.path.exists(c) for c in candidates):
            rep.fail("codemap", rel(wiki.root, wiki.codemap),
                     "`%s` does not exist, relative to either the repo root or docs/. An "
                     "index with invented paths is worse than no index — a reader trusts "
                     "it and then cannot find the file" % token)
    if not checked:
        rep.warn("codemap", rel(wiki.root, wiki.codemap),
                 "no paths found — the code map has not been filled in yet")


def check_ids(wiki, rep, _fix):
    if not wiki.ledgers:
        return
    found, dupes = ledger_entries(wiki)
    for kind, num, path in dupes:
        rep.fail("ids", rel(wiki.root, path),
                 "%s-%03d is defined twice. Ids are permanent and never reused — two "
                 "entries with one id break every citation to either" % (kind, num))

    cited = {}
    for path in list(walk(wiki.root, (".md",))) + list(walk(wiki.root, SOURCE_EXT)):
        fence = None
        for line in read(path).splitlines():
            # An id inside a fenced block is an example — a sample commit body, a
            # template — exactly as a link inside a fence is a link shape and not a
            # link. Same rule, same reason: a checker that flags every illustration
            # is a checker somebody switches off.
            m = FENCE_LINE.match(line)
            if m:
                tok = m.group(1)
                if fence is None:
                    fence = tok
                elif tok[0] == fence[0] and len(tok) >= len(fence):
                    fence = None
                continue
            if fence is not None or ENTRY.match(line):
                continue                 # the definition itself is not a citation
            for kind, num in CITE.findall(line):
                cited.setdefault((kind, int(num)), set()).add(rel(wiki.root, path))

    for (kind, num), where in sorted(cited.items()):
        if not found.get(kind):
            continue                      # that ledger section does not exist at this tier
        if num not in found[kind]:
            rep.fail("ids", sorted(where)[0],
                     "cites %s-%03d, which no ledger defines. Either the entry was never "
                     "written or the id was mistyped; both leave a reader chasing nothing"
                     % (kind, num))

    for kind in ("D", "A", "B"):
        for num in sorted(found.get(kind, {})):
            if (kind, num) not in cited:
                rep.warn("ids", rel(wiki.root, found[kind][num]),
                         "%s-%03d is defined but never cited anywhere. Either something "
                         "should point at it, or it was written for its own sake"
                         % (kind, num))


def check_board(wiki, rep, _fix):
    rows = board_rows(wiki)
    if not rows:
        return
    seen = {}
    for ident, state, section, line in rows:
        if ident in seen:
            rep.fail("board", "%s:%d" % (rel(wiki.root, wiki.roadmap), line),
                     "row %d appears twice (also line %d). Sessions and commits cite work "
                     "as 'row %d', so an id must never mean two things"
                     % (ident, seen[ident], ident))
        else:
            seen[ident] = line
        if section in ("now", "next", "later") and "✅" in state:
            rep.fail("board", "%s:%d" % (rel(wiki.root, wiki.roadmap), line),
                     "row %d is ✅ but still in %s. The edit that finishes a row moves it "
                     "to Done — otherwise the working tables stop showing only open work"
                     % (ident, section.title()))

    inflight = [(i, s, l) for i, s, _sec, l in rows if "▶" in s]
    if len(inflight) > 1:
        unnamed = [i for i, s, _ in inflight if "lane" not in s.lower()]
        if unnamed:
            rep.warn("board", rel(wiki.root, wiki.roadmap),
                     "%d rows are ▶ at once and row%s %s name%s no lane. Two rows in flight "
                     "is fine when each says what it is not touching; unnamed, it is how two "
                     "sessions edit the same file"
                     % (len(inflight), "" if len(unnamed) == 1 else "s",
                        ", ".join(str(i) for i in unnamed), "s" if len(unnamed) == 1 else ""))


def check_cards(wiki, rep, _fix):
    if not wiki.rows:
        return
    rows = board_rows(wiki)
    open_ids = {i for i, _s, sec, _l in rows if sec in ("now", "next", "later")}
    all_ids = {i for i, _s, _sec, _l in rows}
    cards = {}
    for name in sorted(os.listdir(wiki.rows)):
        m = CARD.match(name)
        if m:
            cards[int(m.group(1))] = name
    for ident in sorted(open_ids - set(cards)):
        rep.warn("cards", rel(wiki.root, wiki.rows),
                 "row %d is on the board with no card. A row without a card puts its story "
                 "back in the board cell, which is what the split exists to prevent" % ident)
    for ident in sorted(set(cards) - all_ids):
        rep.warn("cards", os.path.join(rel(wiki.root, wiki.rows), cards[ident]),
                 "card for row %d, which is not on the board" % ident)


def check_sessions(wiki, rep, _fix):
    if not os.path.isdir(wiki.sessions):
        return
    index = os.path.join(wiki.sessions, "README.md")
    index_text = read(index)
    entry_text = read(wiki.entry)
    if not index_text:
        rep.fail("sessions", rel(wiki.root, wiki.sessions),
                 "no README.md — the session index is where the chunks are found")

    numbers = {}
    for folder in sorted(os.listdir(wiki.sessions)):
        full = os.path.join(wiki.sessions, folder)
        if not os.path.isdir(full):
            continue
        m = SESSION_DIR.match(folder)
        if not m:
            rep.warn("sessions", rel(wiki.root, full),
                     "folder is not named NN-slug, so it cannot be cited as a session number")
            continue
        num = int(m.group(1))
        if num in numbers:
            rep.fail("sessions", rel(wiki.root, full),
                     "session %d is also %s. A session number that means two things breaks "
                     "every citation to it — use new-session.py, which claims the number "
                     "under a lock" % (num, numbers[num]))
        else:
            numbers[num] = folder
        if not os.path.isfile(os.path.join(full, "README.md")):
            rep.warn("sessions", rel(wiki.root, full),
                     "no README.md — a session folder says what the episode was and what "
                     "came out of it, in five lines")

    if numbers:
        gaps = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        if gaps:
            rep.warn("sessions", rel(wiki.root, wiki.sessions),
                     "session number%s %s never used. Usually two agents claimed numbers at "
                     "once and one backed off — harmless, but it means the id space raced"
                     % ("" if len(gaps) == 1 else "s", ", ".join(str(g) for g in gaps)))

    for _num, folder, path in chunk_files(wiki):
        name = os.path.basename(path)
        if name not in index_text and name not in entry_text:
            rep.fail("sessions", rel(wiki.root, path),
                     "not linked from the session index. An unindexed chunk is a chunk the "
                     "next session will not find, which is the whole point of writing it")
        body = read(path)
        for heading in REQUIRED_HEADINGS:
            if heading.lower() not in body.lower():
                rep.warn("sessions", rel(wiki.root, path),
                         "no '%s' section. For a planning session Verification is not empty "
                         "— it is: every cited path exists, every id resolves" % heading)
        for heading in EXPECTED_HEADINGS:
            if heading.lower() not in body.lower():
                rep.warn("sessions", rel(wiki.root, path), "no '%s' section" % heading)


def check_specs(wiki, rep, _fix):
    if not wiki.specs:
        return
    rows = {i: s for i, s, _sec, _l in board_rows(wiki)}
    built = re.compile(r"\b(built|shipped|landed|complete)\b", re.I)
    nearby = re.compile(r"\brows?\s+(\d+)")
    for name in sorted(os.listdir(wiki.specs)):
        if not name.endswith(".md") or name.startswith("_"):
            continue
        path = os.path.join(wiki.specs, name)
        for line in read(path).splitlines():
            if not line.lstrip().startswith("**Status:**"):
                continue
            # A Status line usually reports several stages at once — "S.1 built (row 2),
            # S.2 in flight (row 3), S.3 not started (row 4)". Reading the whole line at
            # once would flag row 4 for a claim made about row 2, so each "built" is
            # matched only against the row reference that follows it closely.
            for m in built.finditer(line):
                if line[max(0, m.start() - 5):m.start()].lower().strip().endswith("not"):
                    continue
                after = nearby.search(line, m.end(), m.end() + 80)
                if not after:
                    continue
                ident = int(after.group(1))
                if rows.get(ident, "").strip() in ("☐", ""):
                    rep.fail("specs", rel(wiki.root, path),
                             "Status says %r of board row %d, which reads not started. One "
                             "of the two is lying, and the expensive one is the board — a "
                             "row reading ☐ invites the next session to build it again"
                             % (m.group(1), ident))
            break


def check_manifest(wiki, rep, _fix):
    manifest = os.path.join(wiki.root, "MANIFEST.md")
    starter = os.path.join(wiki.root, "starter")
    if not (os.path.isfile(manifest) and os.path.isdir(starter)):
        return
    listed = set()
    for line in read(manifest).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for cell in cells:
            m = re.match(r"^`(starter/[^`]+|tools/[^`]+)`$", cell)
            if m:
                listed.add(m.group(1))
                break
    on_disk = set()
    for base, dirs, files in os.walk(starter):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            on_disk.add(rel(wiki.root, os.path.join(base, name)))
    for path in sorted(on_disk - listed):
        rep.fail("manifest", path,
                 "no row in MANIFEST.md, so wiki-init.py will never copy it")
    for path in sorted(listed - on_disk):
        if path.startswith("starter/") and not os.path.exists(os.path.join(wiki.root, path)):
            rep.fail("manifest", "MANIFEST.md", "row points at %s, which does not exist" % path)


# ---------------------------------------------------------------- the agent layer

SKILL_BODY_MAX = 500          # platform guidance: past this, split into references
DESCRIPTION_MAX = 1024        # platform limit on the description field
NAME_OK = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")
WINDOWS_PATH = re.compile(r"`[^`\n]*[A-Za-z0-9_.-]\\[A-Za-z0-9_.-][^`\n]*`")
LOCAL_MD_LINK = re.compile(r"\]\((?!https?:|#)([^)\s]+\.md)\)")


def frontmatter(text):
    """Top-level scalar keys of a YAML frontmatter block, and the body after it.

    Deliberately not a YAML parser: the fields this checks are scalars, and a stdlib-only
    kit does not get to import one. A block key (`paths:` with a list under it) is recorded
    with its indented lines joined, which is all the placeholder check needs.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block, body = lines[1:i], "\n".join(lines[i + 1:])
            break
    else:
        return None, text

    keys, current = {}, None
    for line in block:
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            current = match.group(1)
            keys[current] = match.group(2).strip()
        elif current and line.strip():
            keys[current] = (keys[current] + "\n" + line).strip()
    return keys, body


def check_skill(root, path, rep):
    text = read(path)
    keys, body = frontmatter(text)
    where = rel(root, path)
    if keys is None:
        rep.fail("agentlayer", where, "no YAML frontmatter — Claude cannot index this skill")
        return

    name = keys.get("name", "")
    if name and not NAME_OK.match(name):
        rep.fail("agentlayer", where,
                 "name %r must be lowercase letters, digits and hyphens" % name)
    if "claude" in name.lower() or "anthropic" in name.lower():
        rep.fail("agentlayer", where, "name %r uses a reserved word" % name)

    description = keys.get("description", "").strip().strip('"').strip("'")
    if not description:
        rep.fail("agentlayer", where,
                 "empty description — a skill Claude cannot decide to use is a skill nobody uses")
    elif len(description) > DESCRIPTION_MAX:
        rep.fail("agentlayer", where,
                 "description is %d characters; the limit is %d" % (len(description), DESCRIPTION_MAX))

    lines = len(body.splitlines())
    if lines > SKILL_BODY_MAX:
        rep.fail("agentlayer", where,
                 "body is %d lines; over %d it stops fitting in context — move detail into "
                 "references/ and link them from here" % (lines, SKILL_BODY_MAX))

    if WINDOWS_PATH.search(text):
        rep.fail("agentlayer", where,
                 "a backslash path separator — use forward slashes, they work everywhere")

    # References are read one level deep. A reference that points at another reference gets
    # previewed rather than read, and the second hop silently never arrives.
    skill_dir = os.path.dirname(path)
    for target in LOCAL_MD_LINK.findall(body):
        nested = os.path.normpath(os.path.join(skill_dir, target))
        if not os.path.isfile(nested) or os.path.dirname(nested) == os.path.dirname(skill_dir):
            continue
        for second in LOCAL_MD_LINK.findall(read(nested)):
            if os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(nested), second))):
                rep.warn("agentlayer", rel(root, nested),
                         "links on to %s — references are read one level deep from SKILL.md"
                         % second)
                break


def check_agent(root, path, rep):
    keys, _body = frontmatter(read(path))
    where = rel(root, path)
    if keys is None:
        rep.fail("agentlayer", where, "no YAML frontmatter — this is not a subagent definition")
        return
    for field in ("name", "description"):
        if not keys.get(field, "").strip():
            rep.fail("agentlayer", where, "no %s — the agent cannot be selected without one" % field)
    if not keys.get("tools", "").strip():
        rep.warn("agentlayer", where,
                 "no tools allowlist, so it inherits everything the session has")


def check_agentlayer(wiki, rep, _fix):
    root = wiki.root

    # 1. A consumer project: rules and settings must have no holes left in them.
    for folder, pattern in ((os.path.join(root, ".claude", "rules"), ".md"),
                            (os.path.join(root, ".claude"), "settings.json")):
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(pattern):
                continue
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            text = read(path)
            keys, _body = frontmatter(text) if name.endswith(".md") else (None, text)
            scoped = PLACEHOLDER.findall((keys or {}).get("paths", ""))
            holes = sorted(set(PLACEHOLDER.findall(text)) - set(scoped))
            # A placeholder in the body is a visible hole — somebody reads it and fills it,
            # which is the whole point of writing placeholders through unfilled. A
            # placeholder inside `paths:` is not visible at all: the glob matches nothing,
            # the rule never loads, and the file looks finished.
            if scoped:
                rep.fail("agentlayer", rel(root, path),
                         "unfilled %s inside `paths:` — this rule matches no file and will "
                         "never load. Scaffold with --src-globs / --ui-globs, or write the "
                         "globs in by hand" % ", ".join(sorted(set(scoped))))
            if holes:
                rep.warn("agentlayer", rel(root, path),
                         "unfilled %s" % ", ".join(holes))

    # 2. The kit itself: every shipped skill and agent, and the copies that must not drift.
    plugins = os.path.join(root, "plugins")
    if not os.path.isdir(plugins):
        return

    marketplace = read(os.path.join(root, ".claude-plugin", "marketplace.json"))
    for plugin in sorted(os.listdir(plugins)):
        base = os.path.join(plugins, plugin)
        if not os.path.isdir(base):
            continue
        if not os.path.isfile(os.path.join(base, ".claude-plugin", "plugin.json")):
            rep.fail("agentlayer", rel(root, base), "no .claude-plugin/plugin.json")
        if marketplace and '"%s"' % plugin not in marketplace:
            rep.fail("agentlayer", ".claude-plugin/marketplace.json",
                     "plugin %s is on disk but not in the catalogue, so nobody can install it"
                     % plugin)

        skills = os.path.join(base, "skills")
        if os.path.isdir(skills):
            for skill in sorted(os.listdir(skills)):
                path = os.path.join(skills, skill, "SKILL.md")
                if os.path.isdir(os.path.join(skills, skill)) and not os.path.isfile(path):
                    rep.fail("agentlayer", rel(root, os.path.join(skills, skill)), "no SKILL.md")
                elif os.path.isfile(path):
                    check_skill(root, path, rep)

        agents = os.path.join(base, "agents")
        if os.path.isdir(agents):
            for name in sorted(os.listdir(agents)):
                if name.endswith(".md"):
                    check_agent(root, os.path.join(agents, name), rep)

    # 3. A bundled script that shares a name with one in tools/ is a copy, and a copy that
    #    has drifted is two behaviours with one name. This is the same law as MANIFEST.md:
    #    one place knows, everywhere else matches it.
    for folder in (plugins, os.path.join(root, "example")):
        if not os.path.isdir(folder):
            continue
        for path in walk(folder, (".py",)):
            canonical = os.path.join(root, "tools", os.path.basename(path))
            if os.path.isfile(canonical) and read(path) != read(canonical):
                rep.fail("agentlayer", rel(root, path),
                         "differs from tools/%s — a copy that has drifted is two behaviours "
                         "with one name" % os.path.basename(path))


ALL = {
    "counts": check_counts, "budget": check_budget, "codemap": check_codemap,
    "ids": check_ids, "board": check_board, "cards": check_cards,
    "sessions": check_sessions, "specs": check_specs, "manifest": check_manifest,
    "agentlayer": check_agentlayer,
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    if "--list" in flags:
        for name, what in CHECKS:
            print("%-10s %s" % (name, what))
        return 0

    root = os.path.abspath(args[0]) if args else os.getcwd()
    wiki = Wiki(root)
    if not wiki.ok:
        print("no docs/README.md under %s — is this a wiki?" % root)
        return 2

    rep = Report()
    fix = "--fix" in flags
    for name, _what in CHECKS:
        ALL[name](wiki, rep, fix)

    order = {"FAIL": 0, "WARN": 1}
    for level, check, where, message in sorted(rep.items, key=lambda i: (order[i[0]], i[1], i[2])):
        print("%-6s %-11s %s\n       %s" % (level, check, where, message))

    strict = "--strict" in flags
    bad = len(rep.failures) + (len(rep.warnings) if strict else 0)
    print("\n%d check%s · %d failure%s · %d warning%s%s" % (
        len(CHECKS), "" if len(CHECKS) == 1 else "s",
        len(rep.failures), "" if len(rep.failures) == 1 else "s",
        len(rep.warnings), "" if len(rep.warnings) == 1 else "s",
        " (strict: warnings count)" if strict else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
