# Team install for colleagues who use Cursor only

`Opus 5` · effort `high` · `HITL/Plan` · from `BACKLOG.md` B81

## Why

The footer's aim is that a stranger installs cairn from this repo and orients in their own project
with no manual setup. Since v1.65.0 the repo is also a Cursor plugin (`docs/decisions.md` D40), but
the only install path written down is one person importing the repository in their own Cursor
(README, "Using it from Cursor"). A colleague who uses only Cursor, on a team account, has no
path that does not start with *ask the maintainer what to click*.

## Read first

- `README.md`, "Using it from Cursor", which is the current install text.
- `docs/decisions.md` D40–D44: how the Cursor half is built, and why.
- `plugins/cairn/cursor/gaps.md`: what does not work in Cursor yet. A colleague meets these too.
- `docs/cursor-adapter-requirements.md` §3 (distribution). It warns that an account-level install
  lands on every machine sharing the account: right for cairn, wrong for anything machine-specific.

## What to find out (the plan answers these; nothing here is verified)

1. Can a Cursor **team marketplace** list a plugin from a public GitHub repository the team's
   organisation does not own, or must the repository be imported per user?
   Source: cursor.com/docs/plugins and the team admin settings.
2. Does **auto-refresh** need the Cursor GitHub App installed on `superbole/cairn`? If so, who
   can install it, and is that acceptable for a public repo?
3. What does a **brand-new colleague** see on first install: the rules, the `cairn-orient` run, and
   the drift lines? `cursor_drift` must stay silent on a machine that has never had Claude Code.
   Check that in code before claiming it.
4. Does anything in the Cursor half assume the maintainer's machine, such as `~/.claude/`
   paths, `MACHINES.md` or the profile? `session_orientation.py --harness cursor` creates
   `~/.claude/{MISTAKES,CREDENTIALS,MACHINES}.md` and the profile. Is that right for a Cursor-only
   colleague, or noise?

## Where it stops

`HITL/Plan`. It stops with a plan that answers 1–4, says which answers were verified and how, and
proposes the README change and any code change. It does not install anything on a colleague's
machine. The user approves the plan, then the build runs and pushes.

## Done when

The README gives a Cursor-only colleague an install path with no maintainer step. Any code change
has a test in `tools/test_cursor_build.py`. B81 is marked `closed` in `BACKLOG.md`.
