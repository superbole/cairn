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
   thinner than the actual work. **It also empties the private `NEXT.md` and ends by removing the
   private clone** (the operator asked for this 2026-09-23), so the brief's new last step asks before
   deleting anything.

3. **Cursor adapter v1 — reconcile the hand-written copy that already exists** — Opus 5 · high · HITL/Plan
   Brief: [briefs/cursor-adapter-reconcile.md](briefs/cursor-adapter-reconcile.md)
   A 102-line pair of Cursor `next`/`wrap` skills, hand-written 2026-09-04 against a pre-rename
   plugin, is installed and has drifted ~14 versions. The question is whether it is regenerated from
   this repo or stays hand-maintained. Backlog B57.

## Decisions

**D29. Can a backlog id carry a letter suffix (`## B2b.`)?** — answer: `here` · added `2026-09-05` · → `BACKLOG.md` B16
**D30. One D-number sequence per repo, shared by open and answered decisions?** — answer: `here` · added `2026-09-08` · → `docs/decisions.md` D28, `BACKLOG.md` B16

## Watching

**W2. The empty-Queue backlog offer (v1.18.0) fires in a genuinely NEW session** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-28` · check after `the next new session in a project whose Queue is empty`

**W3. The orphan warning (v1.20.0) fires on a real abandoned item** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-28` · check after `a session that starts an item and ends without a wrap, on v1.20.0 or later`

**W4. Does an install work on a machine that has never seen the private source repo?** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-09` · check after `someone installs from superbole/cairn on a machine that has never had the private repo`
The real dogfooding test, and no current machine can run it — every one has had the private repo, so
all could pass while a stranger fails. When it fires, check: does the orientation print, does
`install_rules` write the managed block, and does the plugin stay silent in a project with no `NEXT.md`.

---

`cairn` — session re-entry for people who cannot hold state between sessions.
Aim: a stranger installs from this repo and orients in their own project with no manual setup.
Backlog: [BACKLOG.md](BACKLOG.md). Finished work: [CHANGELOG.md](CHANGELOG.md).
Reasons: [docs/decisions.md](docs/decisions.md). Guide: [docs/guide.md](docs/guide.md).
