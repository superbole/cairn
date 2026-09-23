# BACKLOG — cairn
<!-- next-id: 5 -->

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

## B3. "Commits since the last wrap" ignores wraps made on another machine
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-23`
`reentry_state.unwrapped_commits()` counts `rev-list <.last_wrap>..HEAD`, and `.claude/.last_wrap`
is gitignored — so it only knows wraps made on the machine reading it. A wrap on one machine,
pulled to another, makes the second raise **"THE LAST SESSION DID NOT FINISH CLEANLY — N commits
since the last wrap"** (`session_orientation.py` ~l.709, `dirty_tree_warning.py` ~l.146) about
work that was wrapped properly.

**Observed 2026-09-23, `workspace` on SBOLE-NB5:** 12 commits flagged. NB5's marker said `6b4fdaa`;
NB1 had since wrapped twice (`df5378f`, `323d835`, each with a CHANGELOG entry and a `NEXT.md`
rewrite), and the rest were committed inbox/backlog captures. Reconciling it cost a session's
first round of work and found nothing wrong.

**Proposed fix:** count from the NEWER of the local marker and the newest commit reachable from
HEAD that is wrap-shaped — touches both `CHANGELOG.md` and `NEXT.md`, or subject starts `wrap:`.
`last_commit_is_wrap_shaped()` already sits beside it and only looks at HEAD; generalise it to
"newest such commit" (`git log -1 --format=%H -- CHANGELOG.md` intersected with `NEXT.md`, scoped
by `_scope(root)`).

**Ruled out:**
- **Tracking the marker in git** — every wrap would commit it, and two machines wrapping the same
  day conflict on it. The gitignore is deliberate (`reentry_state.py` docstring).
- **Changing `wrap_receipt.py`** — not needed. The receipt is the verdict and keys to the session
  baseline, not this count; this is only the orientation's nudge. Leave the receipt alone.

**Accepted risk:** a session that commits CHANGELOG + NEXT.md together without running `/cairn:wrap`
reads as wrapped here. That commit IS the substance of a wrap, and the receipt still catches the
missing steps, so the D4 false-wrap failure does not recur through this path.

**Why it matters:** this box also carries uncommitted-file warnings. Firing it on every machine
switch — his normal NB1↔NB5 pattern — trains him to skip it (the cry-wolf boundary, `item_open.py`).

## B4. A merged feature branch reads as in-sync, so the orientation shows a stale NEXT.md silently
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-23`
The divergence banner compares HEAD to `@{u}`. A checkout left on a feature branch after its MR
merged is `0 0` against its own upstream with a clean tree — no banner, no warning — while the
default branch has moved on and rewritten `NEXT.md`. The orientation then relays the branch's copy.

**Observed 2026-09-23, NB5 WSL `bsr-tools`:** sat on `feat/pen-test-headers-53` after MR !5 merged.
`0 0` against `origin/feat/pen-test-headers-53`; `master` was **41** commits behind `origin/master`
by the time it was noticed (3+ at first sighting), and those commits included wraps rewriting
`NEXT.md`. Fixed by hand: `git switch master && git merge --ff-only origin/master`.

**Candidate fix:** when the current branch is not the default branch, also compare HEAD to
`origin/<default>` (from `git symbolic-ref refs/remotes/<remote>/HEAD`, remote taken from `@{u}` —
several repos' upstream is not `origin`). If HEAD is an ancestor of it (`merge-base --is-ancestor`),
say *"this branch is merged; <default> is N ahead — switch?"*. Offer, never switch unasked.

**Ruled out:** comparing to the default branch always — an unmerged feature branch is legitimately
behind master, and warning on every one would be wallpaper. The ancestor test is what makes it
specific to the merged-and-forgotten case.

## B5. The wrap receipt cannot verdict a sibling repo — hit 3x in one legitimate multi-repo session
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-23`
`wrap_receipt.py --record` against any repo other than the session's own project prints `CAIRN
UNKNOWN` ("no session baseline to compare HEAD against"), even when that repo is clean, committed
and pushed. **This is the case B2's fix deliberately left out** (`docs/decisions.md` D26: *"rooted
in project A, working in project B … falls to UNKNOWN — covering it would put the cost on every
ordinary session"*).

**Observed 2026-09-23:** one session worked across `bsr-tools`, `workspace` and `cairn`; 2 of the 3
repos could only ever read `UNKNOWN`. The same pattern again the same day: a `workspace` session on
NB5 committed to `cairn` and to WSL repos. Cross-repo work is his normal pattern, not an edge case.

**Why it matters:** the rules make the receipt the one thing to trust over English. A mechanism that
cannot answer for most of the repos a session touches pushes the verdict back onto prose — the
failure it exists to prevent.

**Decide before building (hence Plan):** is D26's cost estimate still right given it now fires
routinely? A cheap option to cost: stamp a baseline for a sibling repo lazily, on the first write
the PostToolUse recorder sees there (`touched_repos.py` already records which repos were touched),
so the cost lands only on sessions that actually cross repos. Not related to agent-reentry B143
(no-baseline reads SKIPPED in the session's OWN repo).
