# NEXT — cairn

The plugin's source repo. Its backlog lives here.

Seeded 2026-09-09 at **v1.56.0**. History belongs in [CHANGELOG.md](CHANGELOG.md) and reasons in
[docs/decisions.md](docs/decisions.md) — this file is the queue and holds neither.

**This repo starts almost empty on purpose.** The plugin was developed in a private repo whose
history names an employer's git host and personal information, so publishing that history was
never an option — this repo is a fresh `git init`, and the working files start blank rather than
being carried across. `docs/decisions.md` is the exception: it arrived whole, because a rationale
record is the one thing in a repo that cannot be re-derived from the repo.

## Queue

1. **Fix the hook interpreter so Linux installs work** — Opus 5 · high · HITL/Plan
   Brief: [briefs/cross-platform-hook-interpreter.md](briefs/cross-platform-hook-interpreter.md)
   All five hooks invoke bare `python`, which does not exist on stock Ubuntu/Debian. Every hook
   fails to start, so a Linux installer gets none of the five global files and the plugin cannot
   warn about it — the hook that would report the problem is the hook that cannot run. Found on
   `SBOLE-NB5` 2026-09-11. `python3` is not the fix; it moves the breakage to Windows. First
   because it is the aim line failing: today a stranger on Ubuntu gets silence.

2. **Triage the private backlog into this repo** — Opus 5 · high · HITL/Plan
   Brief: [briefs/triage-private-backlog.md](briefs/triage-private-backlog.md)
   About half the private repo's backlog is plugin-generic and belongs here; the rest names work
   servers, clients and machines and stays where it is. Until this runs, this repo's queue is
   thinner than the actual work.

## Watching

**W1. Verify `staged_review_guard` actually loads and blocks on a real session** — `Sonnet 5` · effort `medium` · `HITL/Auto` · added `2026-09-23` · check after `next Claude Code restart with v1.58.0 installed`
Shipped 2026-09-23 (`adc5ea2`) and tested against seven shapes **as a standalone script** — never
once through Claude Code's own `PreToolUse` plumbing, because a hook cannot be loaded by the
session that writes it. Until that is confirmed, this is a guard nobody has seen fire in anger.
**Do:** reinstall/repoint to v1.58.0, restart, then in a scratch repo run `git add f && git commit`
in one call — it must be refused. Then `git commit` alone with something staged — also refused.
Then `git diff --cached`, then commit — must pass.
**If it misfires, remove the `PreToolUse` block from `hooks.json` first and diagnose after**: this
is the plugin's first blocking hook, and a false positive stops every commit on every machine.



---

`cairn` — session re-entry for people who cannot hold state between sessions.
Aim: a stranger installs from this repo and orients in their own project with no manual setup.
Backlog: [BACKLOG.md](BACKLOG.md). Finished work: [CHANGELOG.md](CHANGELOG.md).
Reasons: [docs/decisions.md](docs/decisions.md). Guide: [docs/guide.md](docs/guide.md).
