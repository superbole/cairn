# BACKLOG — cairn
<!-- next-id: 2 -->

Everything worth doing that is NOT in `NEXT.md`'s Queue. Unbounded and unordered —
the ordering that matters lives in the Queue, which is capped at 5 and refilled from here.

Items marked `queued` are on the Queue right now and stay listed here until the work lands.
Where the repo has GitHub Issues, `tools/sync_backlog.py` mirrors this file to them; the
file is the writer and Issues is the copy that survives a lost machine.

## B2. A wrap from a session rooted outside the project can never earn a receipt
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-14` · issue `#2` · closed `2026-09-18`
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

**Closed in v1.57.0.** Two halves: `CAIRN UNKNOWN`, a fourth verdict, so "could not be measured"
stops sharing a token with "measured not to have run"; and `stamp_child_baselines()`, which makes
a parent-directory session stamp a real baseline for each opted-in child, so the observed shape
earns `CAIRN SET` rather than the backstop. Rationale and the rejected options in
`docs/decisions.md` D26. The sibling case (rooted in project A, working in project B) is
deliberately NOT covered and falls to `UNKNOWN` — covering it would put the cost on every
ordinary session.
