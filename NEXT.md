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

1. **Finish the purge on GitHub: delete issue #68, ask Support to drop the old commits** — Sonnet 5 · medium · HITL/Auto
   Brief: [briefs/purge-github-residue.md](briefs/purge-github-residue.md)
   Issue #68 is deleted (2026-10-01, confirmed not found). Left: he sends the Support request drafted in the brief; the agent only verifies. First because the old pages stay public until it is done. Backlog B96.

2. **Team install for colleagues who use Claude Code only** — Opus 5 · high · HITL/Plan
   Brief: [briefs/claude-team-install.md](briefs/claude-team-install.md)
   He knows several Claude-Code-only colleagues and no Cursor-only ones (2026-09-28), so this replaced B81, which stays in the backlog. Stops at the plan. Backlog B86. The item that serves the aim.

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

**W6. Review and merge the unattended `afk/` PRs, then catch the bookkeeping up** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-26` · check after `2026-10-20`
Every NB5 cairn firing leaves PRs on `superbole/cairn`. Read each dossier against its diff
(`docs/running-a-batch.md`, "The review surface"), merge or close each one, then do one bookkeeping pass
(CHANGELOG, version bump, `BACKLOG.md` closes, the Queue) and run `tools/sync_backlog.py`. Any lane-0
bookkeeping PRs already merged cover part of this, so read `git log` first.
Firings run Sun/Wed/Fri 17:00 (`cairn-afk-firing`, Scheduled sidebar on NB5); each posts its summary to Discord.
**The summary's "Permission prompts: none" line is not reliable** (2026-09-30 said none after two). PRs #103,
#104 and #105 (B16, B17, B18) all touch `validate_next.py` `validate()`: the second and third to merge need a
small rebase, and B16's rules-text half plus the version bump are left for the attended pass (see #103).

---

`cairn` — session re-entry for people who cannot hold state between sessions.
Aim: a stranger installs from this repo and orients in their own project with no manual setup.
Backlog: [BACKLOG.md](BACKLOG.md). Finished work: [CHANGELOG.md](CHANGELOG.md).
Reasons: [docs/decisions.md](docs/decisions.md). Guide: [docs/guide.md](docs/guide.md).
