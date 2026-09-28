# Team install for colleagues who use Claude Code only

`Opus 5` · effort `high` · `HITL/Plan` · from `BACKLOG.md` B86

## Why

The footer's aim is that a stranger installs cairn from this repo and orients in their own project
with no manual setup. The user knows several colleagues who use only Claude Code (2026-09-28), and
none who use only Cursor, so this is the team install that matters now. B81, the Cursor-only
version, stays in the backlog.

One person can install cairn today by adding the marketplace and the plugin (README). What has
never been checked is handing it to a *team*: a way to install it once for everyone, and what a colleague
who is not the maintainer actually gets on first run.

## Read first

- `README.md`, the install section and the table of what the plugin writes.
- `docs/guide.md`, "Shipping a change", for how updates reach an install.
- `BACKLOG.md` B61 (auto-update is off by default for this marketplace) and W4 (an install on a
  machine that has never seen the private source repo).

## What to find out (the plan answers these; nothing here is verified)

1. **Team distribution routes in Claude Code.** Check the current docs (code.claude.com) for what
   exists: project `.claude/settings.json` entries that declare a marketplace and enable a plugin,
   org-managed settings, or anything else. Say which route needs an admin and which a colleague can
   take alone. Do not rely on memory for setting names; read them.
2. **First run for a colleague.** What they see on first install: the managed block in
   `~/.claude/CLAUDE.md`, the seeded profile template, the global files, the SessionStart
   orientation in a project with no `NEXT.md` (it should be silent). Check that in code.
3. **What assumes the maintainer.** `MACHINES.md`, `REENTRY_PROFILE_SOURCE`, the private-names
   list, and the issue host defaults. Are any of them noise or errors for a colleague?
4. **Updates.** With auto-update off by default, how does a team stay on a current version? Link B61.
5. **Windows prerequisites.** Git for Windows (B60) and the hook interpreter. What does a colleague
   see if one is missing?

## Where it stops

`HITL/Plan`. It stops with a plan that answers 1–5, says which answers were verified and how, and
proposes the README change and any code change. It does not install anything on a colleague's
machine. The user approves the plan, then the build runs and pushes.
