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

1. **Plan the October AFK token spend — due 2026-10-01** — Opus 5 · high · HITL/Auto
   Brief: [briefs/token-plan-2026-10.md](briefs/token-plan-2026-10.md) (a stub; the full brief is private)
   Decides how unattended work uses the weekly allowance over the coming weeks. Items 2 and 3 (B10, B23)
   already ran as its worktree lanes and landed in v1.64.0. Stops at each checkpoint. Backlog B70.

2. **Cursor adapter v1 — reconcile the hand-written copy that already exists** — Opus 5 · high · HITL/Plan
   Brief: [briefs/cursor-adapter-reconcile.md](briefs/cursor-adapter-reconcile.md)
   A 102-line pair of Cursor `next`/`wrap` skills, hand-written 2026-09-04 against a pre-rename
   plugin, is installed and has drifted ~14 versions. The question is whether it is regenerated from
   this repo or stays hand-maintained. Backlog B57.

## Decisions

**D37. Purge personal schedule detail from public history (commits `5d2cd6a`–`cfec2f7`, issue #68's edit history)?** — answer: `here` · added `2026-09-26` → the 2026-09-26 CHANGELOG entry

## Watching

**W2. The empty-Queue backlog offer (v1.18.0) fires in a genuinely NEW session** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-28` · check after `the next new session in a project whose Queue is empty`

**W3. The orphan warning (v1.20.0) fires on a real abandoned item** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-28` · check after `a session that starts an item and ends without a wrap, on v1.20.0 or later`

**W4. Does an install work on a machine that has never seen the private source repo?** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-09` · check after `someone installs from superbole/cairn on a machine that has never had the private repo`
The real dogfooding test, and no current machine can run it — every one has had the private repo, so
all could pass while a stranger fails. When it fires, check: does the orientation print, does
`install_rules` write the managed block, and does the plugin stay silent in a project with no `NEXT.md`.

**W5. The first real cloud firing (F1) ran as specified** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-26` · check after `2026-09-30`
F1 is scheduled for 2026-09-29 20:00 (B70's plan, in the private store). Check: the routine's Runs list
shows success; each item became one `afk/<date>-<nn>-<Bnn>-<slug>` PR off `origin/main` that touches no
shared file; the PR notification reached the phone; and nothing reached `main`. Also read the usage page
and compare it with the dry run's delta. **Blocked on the dry run's own verdict:** if
`git push --dry-run origin main` was NOT blocked in the cloud, F1 must not have run until the push rules
were set back to `deny` (D39).

**W6. Review and merge the unattended `afk/` PRs, then catch the bookkeeping up** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-26` · check after `2026-10-20`
Every cloud firing through 2026-10-18 leaves PRs on `superbole/cairn`. Read each dossier against its diff
(`docs/running-a-batch.md`, "The review surface"), merge or close each one, then do one bookkeeping pass
(CHANGELOG, version bump, `BACKLOG.md` closes, the Queue) and run `tools/sync_backlog.py`. Any lane-0
bookkeeping PRs already merged cover part of this, so read `git log` first.

---

`cairn` — session re-entry for people who cannot hold state between sessions.
Aim: a stranger installs from this repo and orients in their own project with no manual setup.
Backlog: [BACKLOG.md](BACKLOG.md). Finished work: [CHANGELOG.md](CHANGELOG.md).
Reasons: [docs/decisions.md](docs/decisions.md). Guide: [docs/guide.md](docs/guide.md).
