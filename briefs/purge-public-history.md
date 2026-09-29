# Purge personal schedule detail from public history

`Opus 5` · effort `high` · `HITL/Auto` · from `BACKLOG.md` B93

Was W8. W7 is wrapped, so this can start. The window closes 2026-10-01.

## Why

Answered 2026-09-29 (`docs/decisions.md` D37): purge after W7 and before 2026-10-01. The working tree is already the stub (`briefs/token-plan-2026-10.md`, commit `c83fb58`). Issue #68 is closed and its current body does not carry the schedule detail. The commits in `5d2cd6a`–`cfec2f7` are still on `origin/main`. Leaving them reachable was rejected, because `git show` still returns the original text.

## Read first

- `docs/decisions.md` D37.
- `briefs/token-plan-2026-10.md`. Do not reconstruct the removed text from git history into a file, an issue, or the chat.
- `git log --oneline 5d2cd6a^..cfec2f7`. Read each commit. One of them is a backlog sync (`7b2ab2f`). Keep a commit that has none of the schedule text.
- Issue #68. The current body and the edit history are different stores.

## Where it stops

`HITL/Auto`. Do the local rewrite and show which commits it drops and what that does to every later commit on `main`. Then stop and warn, in the reply, before any force-push of `main`. Wait for an explicit yes. Do not take that yes from this brief.

Issue #68's edit history is the same kind of step: name the call that deletes it, say what it deletes, and stop before running it.
