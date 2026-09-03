# Verification

**Nothing is reported as verified without running something and quoting the output.** Not
"tests pass" — the command and what it printed. A green light wired to nothing is worse than
no light, because somebody acts on it.

**If you could not run the instrument, say so in the same sentence as the claim.** "The
handler should now return 404; I could not run the suite because the database was not up" is
useful. "Fixed" is not.

**"It looks better" is not an acceptance criterion.** A criterion is good if two people who
disagree about whether it was met can settle it without arguing about taste. If a claim you
keep wanting to make has no instrument behind it, that gap is a roadmap row.

**Never compare against a number from an earlier session.** Re-derive the baseline in the
same run, on the same machine, or the comparison measures the afternoon.

This project's instruments:

```bash
python -m pytest tests/ -q          # 94 passed as of 2026-09-02
```

There is **no CI and no linter** — see [docs/environment.md](../../docs/environment.md). That
command run locally is the entire safety net, which is the argument for running it before
every claim rather than at the end of a session.

Three of those tests are invariants rather than behaviour, and they are the ones that matter
when a refactor looks harmless: every `/api/*` handler checks auth, no path pairs
`_type_text` with its own Enter (`D-005`), and the VS Code terminal-focus sequence exists in
exactly one file (`D-008`). If one of those goes red, the fix is not to update the test.

Before any commit, both checkers:

```bash
python tools/wiki/check-links.py && python tools/wiki/wiki-doctor.py
```

This is also enforced by a hook, so a failing checker denies the commit rather than
disappointing somebody later. The rule stays written down because the hook can be absent —
in a fresh clone, in CI, in another agent — and the rule cannot.
