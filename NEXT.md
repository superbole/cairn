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

1. **Team install for colleagues who use Claude Code only** — Opus 5 · high · HITL/Plan
   Brief: [briefs/claude-team-install.md](briefs/claude-team-install.md)
   He knows several Claude-Code-only colleagues and no Cursor-only ones (2026-09-28), so this replaced B81, which stays in the backlog. Stops at the plan. Backlog B86. Stays first: it is the item that serves the aim.

2. **Purge personal schedule detail from public history** — Opus 5 · high · HITL/Auto
   Brief: [briefs/purge-public-history.md](briefs/purge-public-history.md)
   Was W8. The window closes 2026-10-01. Stop and warn before the force-push of `main`. Backlog B93.

3. **When the checkout is behind, orient from origin's `NEXT.md`, and never start an item on a stale base** — Opus 5 · high · HITL/Plan
   Brief: `BACKLOG.md` B87
   Found 2026-09-28: 50 behind, and the orientation printed a stale queue under the warning. Agreed in chat. An item that exists only on origin is declined until he pulls (D46).

## Watching

**W2. The empty-Queue backlog offer (v1.18.0) fires in a genuinely NEW session** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-28` · check after `the next new session in a project whose Queue is empty`

**W3. The orphan warning (v1.20.0) fires on a real abandoned item** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-28` · check after `a session that starts an item and ends without a wrap, on v1.20.0 or later`

**W4. Does an install work on a machine that has never seen the private source repo?** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-09` · check after `someone installs from superbole/cairn on a machine that has never had the private repo`
The real dogfooding test, and no current machine can run it — every one has had the private repo, so
all could pass while a stranger fails. When it fires, check: does the orientation print, does
`install_rules` write the managed block, and does the plugin stay silent in a project with no `NEXT.md`.

**W5. The first unattended cairn firing (F1, on NB5) ran as specified** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-26` · check after `2026-09-30`
F1 is NB5's local scheduled task, 2026-09-29 20:00 (B70's plan, in the private store). Cloud routines are
unavailable on this account, because its GitHub access is blocked. Check: the task's Runs list shows
success, with no stall on a permission prompt; each item became one `afk/<date>-<nn>-<Bnn>-<slug>` PR off
`origin/main` that touches no shared file; the PR notification reached the phone; and nothing reached
`main`. Also read the usage page against Monday's dry-run delta, and adjust the firings per week if needed.
The first real `afk/` run (NB1, 2026-09-27, reviewed as W7) showed: a firing can stall for hours on a
permission prompt (B84); a README-only item is its own PR; the leak detector false-failed three PRs until
B75 merged; bookkeeping stays in the attended session.

**W6. Review and merge the unattended `afk/` PRs, then catch the bookkeeping up** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-26` · check after `2026-10-20`
Every NB5 cairn firing leaves PRs on `superbole/cairn`. Read each dossier against its diff
(`docs/running-a-batch.md`, "The review surface"), merge or close each one, then do one bookkeeping pass
(CHANGELOG, version bump, `BACKLOG.md` closes, the Queue) and run `tools/sync_backlog.py`. Any lane-0
bookkeeping PRs already merged cover part of this, so read `git log` first.

---

`cairn` — session re-entry for people who cannot hold state between sessions.
Aim: a stranger installs from this repo and orients in their own project with no manual setup.
Backlog: [BACKLOG.md](BACKLOG.md). Finished work: [CHANGELOG.md](CHANGELOG.md).
Reasons: [docs/decisions.md](docs/decisions.md). Guide: [docs/guide.md](docs/guide.md).
