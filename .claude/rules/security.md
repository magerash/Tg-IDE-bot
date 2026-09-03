# Security

**Secrets never live in code and never enter a commit.** Tokens, keys and passwords come from
the environment or a secret store. Anything that identifies infrastructure — a host, a
project id, an internal address — is configuration, not source, and it does not belong in a
document either.

**Say so before staging, not after.** If a file about to go in should probably not, name it
while the fix is still `git restore`.

**A new persisted entity carries its access policy in the same change that creates it.**
A table without a policy is readable by whoever asks first, and the gap is invisible until
somebody finds it.

**Destructive operations are confirmed, and the dangerous ones are denied by configuration.**
`.claude/settings.json` carries the deny list. Discipline is not a control: it works until
the one session where it does not.

**Environments do not cross.** What goes to testers is validated on the development channel
first, and the two are visually distinct at runtime, so nobody reports a bug against a build
they were not looking at.

**Validate what comes in from outside** — request payloads, uploaded files, scraped pages,
model output that will be executed or interpolated.
