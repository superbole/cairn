# BACKLOG — cairn
<!-- next-id: 2 -->

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

## B2. A wrap from a session rooted outside the project can never earn a receipt
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-14`

`wrap_receipt.py --record` keys its baseline to the session id AND the project the session started
in. A session started in a parent directory (here `~/Projects`, which is not a repo) that does all
its work in a project below or beside it gets `? no session baseline` for `next_rewrite`,
`changelog` and `commit` — the three REQUIRED steps — and therefore `CAIRN OPEN`, however
completely the wrap ran.

Observed 2026-09-14: receipt `9274cfbf13da` read `CAIRN OPEN` on a wrap that had written a 19-line
CHANGELOG entry, re-sorted the Queue, committed `e415fb2` and pushed to `0 0`. The `marker` step
measured `ran` in the same receipt, so the tool could see the repo perfectly well — only the
baseline was missing.

**Already ruled out:** the marker is not the gap (it read `ran`); `CLAUDE_PROJECT_DIR` was set
correctly on the invocation (the earlier run without it failed differently, reporting the parent);
and this is not the `--held` case, since the push was intentional and succeeded.

**Why it matters:** the tool's own note calls this "a wrong place to stand, not a failure", which
is accurate and is the problem — an `OPEN` that means *you stood in the wrong place* is
indistinguishable from an `OPEN` that means *you skipped the changelog*. Training the reader to
discount `OPEN` defeats the verdict, which is the cry-wolf failure `docs/decisions.md` D23 names.

Worth deciding whether the receipt should refuse to record at all from a foreign root (a fourth
verdict, or a hard error naming the directory), rather than emitting a verdict it cannot support.
