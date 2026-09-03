# VPS / tunnel / VPN topology — held back on purpose

The real document is `docs/imported/vps-architecture.md`. It is **on disk and
gitignored**, and this stub is what a clone gets instead.

## Why

This repository is public. That file is not a description of the bot — it is a map of the
machine the bot types into: the VPS address behind the tunnel, the VPN subnets, the
container names, the ports, and the operator's *other* services on the same host. The bot's
whole purpose is remote keyboard and shell access to a personal PC, so the topology doc and
the threat model are the same document read twice.

What is already public is public — see the honest note below. Withholding this file stops
the exposure growing, it does not undo it.

## What it covers, so you know whether you need it

- the name → address table, with the date each resolution was last verified
- Caddy, the reverse SSH tunnel, and which port each end owns
- the AmneziaWG VPN, and the hairpin that made the Mini App crawl on the phone
  (`D-004` — the VPN server *is* the VPS the bot's hostname resolves to)
- the runbook for "the address got filtered again"

The **reasoning** from all of that is in the wiki and is not secret: see
[../chunks/features/web-dashboard.md](../chunks/features/web-dashboard.md) for the tunnel
section and the VPN hairpin diagnosis, and [../environment.md](../environment.md) for the
failure modes.

## Getting the real file

It is an imported copy, not an original. Sync it by replacing the file wholesale from its
source of truth — never by editing both:

```
C:/Projects/Pryatki/docs/infra/vps-architecture.md
```

Editing the copy is how the trimmed derivative that used to live here drifted out of date.

## Honest note — this is a partial measure

`README.md` and `start_tunnel_vps.ps1` are tracked and already name the tunnel hostname and
both VPS addresses, and commit `e039070` (v0.16.6, 2026-08-09) carries the address change in
the **commit message**. Git history keeps all of it. Withholding one file lowers the detail
that is public; it does not make the host unlisted. Row 4 of
[../ROADMAP.md](../ROADMAP.md) is the open question of what, if anything, to do about that.
