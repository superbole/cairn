# Brief — wrap receipt from a foreign session root

Filed 2026-09-14 as `BACKLOG.md` B2, issue `#2`. Pulled to Queue 2026-09-16.

## The problem

`wrap_receipt.py --record` keys its baseline to the session id AND the project the session
started in. A session started in a parent directory (e.g. `~/Projects`, not itself a repo) that
does all its actual work in a project below or beside it gets `? no session baseline` for
`next_rewrite`, `changelog` and `commit` — the three REQUIRED steps — and therefore reports
`CAIRN OPEN`, however completely the wrap actually ran.

## Evidence

Observed 2026-09-14: receipt `9274cfbf13da` read `CAIRN OPEN` on a wrap that had written a
19-line CHANGELOG entry, re-sorted the Queue, committed `e415fb2` and pushed to `0 0`. The
`marker` step measured `ran` in the same receipt — the tool could see the repo fine — only the
session baseline was missing.

**Already ruled out:**
- The marker is not the gap (it read `ran`).
- `CLAUDE_PROJECT_DIR` was set correctly on the invocation that produced this receipt (an earlier
  run without it failed differently, reporting the parent directory instead).
- Not the `--held` case — the push was intentional and succeeded.

## Why it matters

The tool's own note calls this "a wrong place to stand, not a failure" — accurate, and the
problem: an `OPEN` that means *you stood in the wrong place* is indistinguishable from an `OPEN`
that means *you skipped the changelog*. Training the reader to discount `OPEN` defeats the
verdict — the exact cry-wolf failure `docs/decisions.md` D23 names.

## The decision needed

Whether `wrap_receipt.py` should:
1. Refuse to record at all from a foreign root — a fourth verdict (e.g. `CAIRN UNKNOWN`) or a
   hard error naming the directory the session actually started in, rather than emitting a
   verdict (`OPEN`) it cannot support; or
2. Resolve the session baseline by walking down to whatever project the session's tool calls
   actually touched (same heuristic `check_repos.py` already uses), so a foreign-root session
   still earns a real verdict.

Read `hooks/wrap_receipt.py` and `tools/check_repos.py` before choosing — the fix likely reuses
whatever `check_repos.py` does to resolve "this session's own project" from tool-call history
rather than `CLAUDE_PROJECT_DIR`.

## Done looks like

A wrap run from a parent directory that only touched one child repo produces the same verdict
(`CAIRN SET` / `CAIRN NOT DUE` / `CAIRN OPEN`) it would have produced if the session had started
inside that repo — never a false `OPEN` caused solely by where the session happened to start.
