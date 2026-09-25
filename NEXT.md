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

1. **Stop `install_rules` deleting the user's own text in `~/.claude/CLAUDE.md`** — Opus 5 · high · AFK/Auto
   Brief: [briefs/install-rules-marker-safety.md](briefs/install-rules-marker-safety.md)
   The marker match is a bare prefix search, and the backup is one rolling copy, so on any
   installer's machine the managed block can silently swallow text written above it, with no way
   back after two updates. Backlog B25. Placed above the Cursor item because installs are the aim.
   It commits locally and stops before the push.

2. **Make the skills' `python "$CLAUDE_PLUGIN_ROOT/…"` calls actually resolve** — Opus 5 · high · AFK/Auto
   Brief: [briefs/skill-python-calls.md](briefs/skill-python-calls.md)
   17 call sites in `skills/` and `rules/` name bare `python` (fails on Linux) and a variable that
   was measured unset in the agent's shell (wrong everywhere). v1.61.0 fixed the hooks only. Backlog
   B59. Above Cursor because a Linux wrap is the aim line. It commits locally and stops before the push.

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
