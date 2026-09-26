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

1. **Cursor adapter v1 — reconcile the hand-written copy that already exists** — Opus 5 · high · HITL/Plan
   Brief: [briefs/cursor-adapter-reconcile.md](briefs/cursor-adapter-reconcile.md)
   A 102-line pair of Cursor `next`/`wrap` skills, hand-written 2026-09-04 against a pre-rename
   plugin, is installed and has drifted ~14 versions. The question is whether it is regenerated from
   this repo or stays hand-maintained. Backlog B57.

2. **Model labels name the tier, not a version: `Opus 5.5` reads as "no model" today** — Opus 5 · high · AFK/Auto
   Brief: [briefs/model-labels-by-family.md](briefs/model-labels-by-family.md)
   Every model release would otherwise need a plugin release. Backlog B76. It commits locally and stops before the push.

3. **The README says how to turn on auto-update (off by default for this marketplace)** — Sonnet 5 · medium · AFK/Auto
   Brief: [briefs/readme-auto-update.md](briefs/readme-auto-update.md)
   A stranger's install otherwise stays on its first version forever. Backlog B61. It commits locally and stops before the push.

## Decisions

**D37. Purge personal schedule detail from public history (commits `5d2cd6a`–`cfec2f7`, issue #68's edit history)?** — answer: `here` · added `2026-09-26` → the 2026-09-26 CHANGELOG entry

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

**W6. Review and merge the unattended `afk/` PRs, then catch the bookkeeping up** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-26` · check after `2026-10-20`
Every NB5 cairn firing through 2026-10-18 leaves PRs on `superbole/cairn`. Read each dossier against its diff
(`docs/running-a-batch.md`, "The review surface"), merge or close each one, then do one bookkeeping pass
(CHANGELOG, version bump, `BACKLOG.md` closes, the Queue) and run `tools/sync_backlog.py`. Any lane-0
bookkeeping PRs already merged cover part of this, so read `git log` first.

---

`cairn` — session re-entry for people who cannot hold state between sessions.
Aim: a stranger installs from this repo and orients in their own project with no manual setup.
Backlog: [BACKLOG.md](BACKLOG.md). Finished work: [CHANGELOG.md](CHANGELOG.md).
Reasons: [docs/decisions.md](docs/decisions.md). Guide: [docs/guide.md](docs/guide.md).
