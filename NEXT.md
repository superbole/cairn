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
   He knows several Claude-Code-only colleagues and no Cursor-only ones (2026-09-28), so this replaced B81, which stays in the backlog. Stops at the plan. Backlog B86. The item that serves the aim.

2. **When the checkout is behind, orient from origin's `NEXT.md`, and never start an item on a stale base** — Opus 5 · high · HITL/Plan
   Brief: `BACKLOG.md` B87
   Found 2026-09-28: 50 behind, and the orientation printed a stale queue under the warning. Agreed in chat. An item that exists only on origin is declined until he pulls (D46). Do B103 in the same plan: when origin was rewritten, the banner must say reset, not pull.

3. **Repo-acting tools must act on the repo they are run in, not the session's stamped project** — Opus 5 · high · AFK/Auto
   Brief: [briefs/sync-backlog-target-repo.md](briefs/sync-backlog-target-repo.md)
   Pulled at the 2026-10-01 wrap to refill the Queue: run from a sibling repo, `sync_backlog.py` silently syncs the wrong backlog. Commits locally and stops before the push. Backlog B98.

## Watching

**W9. GitHub Support has purged the old commit pages and PR refs** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-10-01` · check after `2026-10-15`
Ticket sent 2026-10-01 (confirmation email received). Check that `https://github.com/superbole/cairn/commit/5d2cd6a` returns 404 and
`git ls-remote origin 'refs/pull/8*/head' 'refs/pull/90/head'` no longer lists PRs #84 to #90 at old commits. If not, it waits on Support's reply in his email. Brief: [briefs/purge-github-residue.md](briefs/purge-github-residue.md).

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
Since 2026-10-02 (D49) a firing takes one new item and first reviews up to 2 open PRs, leaving a
`Scheduled review` comment on each: start from those. It stops itself after 2026-10-20; disable it then. PRs #103,
#104 and #105 (B16, B17, B18) all touch `validate_next.py` `validate()`: the second and third to merge need a
small rebase, and B16's rules-text half plus the version bump are left for the attended pass (see #103).

**W10. The first firing on the rewritten `cairn-afk-firing` prompt ran cleanly** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-10-02` · check after `2026-10-03`
Its first run was 2026-10-02 17:00. Read that firing's Discord post, and on `superbole/cairn` check
for `Scheduled review` comments on open `afk/` PRs and at most one new PR. A missing post, or a run that
never finished, means it stalled on a permission prompt: find which command, then fix
`.claude/settings.json` or the prompt (D49, CHANGELOG 2026-10-02).

**W11. The `claude-inbox-check` task runs cleanly and doesn't fake an unfinished session** — `Opus 5` · effort `high` · `HITL/Auto` · added `2026-10-03` · check after `2026-10-04`
Created 2026-10-03 from `superbole/claude-inbox` #3: every 30 min, in this checkout, it acts on issues whose
newest message starts `From Cairn` (author `superbole`). Two things to check. (1) Do the runs finish? Check
`list_task_runs` and #2's reply. A stalled run means a missing allow rule: he was adding the 4 `Bash` + 4
`PowerShell` `gh issue … -R superbole/claude-inbox` rules himself. (2) Does each quiet run (a session that
starts and ends here with no wrap) set off the "last session did not finish cleanly" warning? If it does,
the real warning gets lost, and that's a cairn hook bug to file in `BACKLOG.md`: scheduled runs should not count.
Found on the first run (2026-10-03 15:31): it stalled on a `grep` of `~/.claude/scheduled-tasks/cairn-afk-firing/SKILL.md`
for #2. That path is outside the checkout, so every request about the AFK prompt will prompt. Suggested fix, his to add:
`Read(//c/Users/SheldonBole/.claude/scheduled-tasks/**)` and `Bash(grep * C:/Users/SheldonBole/.claude/scheduled-tasks/*)`.
Keep edits there behind a prompt. Check whether he added them.

---

`cairn` — session re-entry for people who cannot hold state between sessions.
Aim: a stranger installs from this repo and orients in their own project with no manual setup.
Backlog: [BACKLOG.md](BACKLOG.md). Finished work: [CHANGELOG.md](CHANGELOG.md).
Reasons: [docs/decisions.md](docs/decisions.md). Guide: [docs/guide.md](docs/guide.md).
