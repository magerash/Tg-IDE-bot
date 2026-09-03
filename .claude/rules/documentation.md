# Documentation

**Read the document that owns the area before you change the area; update it in the same
change.** The ownership table is in [docs/README.md](../../docs/README.md). A change that
lands without its document is a change the next session has to re-derive from the diff.

**A fact lives in exactly one place; everything else cites it by id.** Decisions `D-nnn`,
assumptions `A-nnn`, blockers `B-n`. Restating a decision creates a second copy that will
disagree with the first, and there is no way to tell which one is lying.

**Numbers in prose are written by a script, not by hand.** Counts, totals and sizes live
inside `<!-- counts -->` markers that `wiki-doctor.py --fix` regenerates. An index once
claimed 48 decisions while the ledger held 110.

**The always-loaded files point at knowledge; they do not carry it.** `AGENTS.md` and this
directory are read every session. The wiki is read on demand. A rule copied up here is a
rule that goes stale up here.

**The index is a document with an owner.** If the entry point stops listing what exists,
retrieval silently returns the wrong set and nobody sees an error.

**Changelog entries are professional and minimal.** They are read far more often than they
are written.

**This project releases as `versioned`.** `VERSION` in `config.py` is bumped and a dated
entry written to [docs/changelog.md](../../docs/changelog.md) and `README.md` **only** when
the operator says `Let's finish` — never mid-session, because a version that describes
unfinished work is worse than no version. The commit subject carries the changelog line; the
full format is in [git-protocol.md](git-protocol.md).

`v0.0.x` small changes and fixes · `v0.x.0` new features · `v1.0.0` first stable, not yet
reached.

**One more owner, specific to this repo:** every feature also has a file in
[docs/chunks/features/](../../docs/chunks/features/), and it is updated in the same change.
Those files predate the wiki and stay canonical for *how a feature behaves*; the synthesis
documents own *how the project stands*.
