# BACKLOG — cairn
<!-- next-id: 1 -->

Everything worth doing that is NOT in `NEXT.md`'s Queue. Unbounded and unordered —
the ordering that matters lives in the Queue, which is capped at 5 and refilled from here.

Items marked `queued` are on the Queue right now and stay listed here until the work lands.
Where the repo has GitHub Issues, `tools/sync_backlog.py` mirrors this file to them; the
file is the writer and Issues is the copy that survives a lost machine.

## B1. Apply the interpreter workaround on SBOLE-NB1
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-14`

`SBOLE-NB1` is the same Windows + WSL shape as `SBOLE-NB5`, so its WSL side has the same silent
failure: hooks enabled, `claude plugin list` green, and none of the five global files written.
Confirm, then apply the same local workaround until Queue item 1 lands a real fix.

Check `~/.claude/` for `CLAUDE.md`, `reentry-profile.md`, `MISTAKES.md`, `CREDENTIALS.md` and
`MACHINES.md`. If they are missing and `command -v python` is empty, symlink
`~/.local/bin/python -> /usr/bin/python3` and re-run `hooks/session_orientation.py` once; it is
idempotent and prints nothing on a second run. `MACHINES.md` should end up with the same three
rows as `SBOLE-NB5`.

`DeepThought` is personal and has no WSL at present, so it is not affected — revisit only if WSL
is added there.

This is a per-machine workaround, not the fix. The fix is Queue item 1:
[briefs/cross-platform-hook-interpreter.md](briefs/cross-platform-hook-interpreter.md). Tracked as
`W1` in NEXT.md so it triggers on that machine after the first pull.
