# Git protocol

**No git operations on your own initiative** — not after a feature, not to "save work".
The operator decides when work is committed.

The exception is the three commands below. They **are** the authorization: they mean run the
steps, not print them back to be pasted. Ask only about a choice inside them (the branch
name).

| Said | Means |
|---|---|
| `Let's finish` / `LF` | close the iteration — the update regulation in [docs/README.md](../../docs/README.md). Touches no git. |
| `CB` / `current branch` | commit every change, message grammar per `docs/commits.md` (or the regulation in the entry point, at Core tier); push; report ready. |
| `NB` / `new branch` | both `CB` steps, then cut the next branch, then tell the operator to type `/clear`. |
| `Night work` | ask **all** questions and permissions up front, then plan to finish without interruption. |

**Raise a questionable file before staging, not after.** A local settings file, a document
belonging to another project, a generated artefact — say so while it is still cheap. After
the commit it is a second commit and a conversation.

**Branch names carry the iteration number**: the current number plus one, then a hyphen and
one word for the next piece of work — `7-panel` → `8-search`. The sequence is the audit
trail, and it removes a naming decision from the end of a long session.

`/clear` at the end of `NB` is the one step of the four that cannot be run for the operator.
Say it explicitly; do not assume it happened.
