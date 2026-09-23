# BACKLOG — cairn
<!-- next-id: 7 -->

Everything worth doing that is NOT in `NEXT.md`'s Queue. Unbounded and unordered —
the ordering that matters lives in the Queue, which is capped at 5 and refilled from here.

Items marked `queued` are on the Queue right now and stay listed here until the work lands.
Where the repo has GitHub Issues, `tools/sync_backlog.py` mirrors this file to them; the
file is the writer and Issues is the copy that survives a lost machine.

## B3. "Commits since the last wrap" ignores wraps made on another machine
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-23` · issue `#3`
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
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-23` · issue `#4`
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

## B6. `/clear` starts a new session with no baseline, so its wrap reads `CAIRN UNKNOWN`
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-23` · issue `#6`
**Root cause, measured 2026-09-23 on NB5 (CLI, WSL, `bsr-tools`):** `/clear` gives the session a
**new `session_id`** (a new transcript file, `8116a414…`, whose first entry is the `/clear` itself)
but cairn stamps no baseline for it, on two layers:
1. `hooks/hooks.json` — the `SessionStart` matcher is `startup|resume`, so the hook never runs on
   `source: clear`.
2. `hooks/session_orientation.py` `_is_reentry_moment()` — even if it did run, `main()` returns on
   `clear`/`compact` **before** `wrap_receipt.stamp_baseline(root)`.

So every receipt taken after a `/clear` is `CAIRN UNKNOWN`, even when the whole wrap ran (the
`bsr-tools` session this was found in: CHANGELOG, NEXT.md, commit and push all verifiably happened,
receipt `UNKNOWN`, then the next session opened with "did not finish cleanly"). **Not WSL- or
CLI-specific:** it happens anywhere `/clear` is used. The session started from the project dir, so
this is not B5 or the parent-dir case.

**Also wrong:** `skills/wrap/SKILL.md` (the model-switch table) says `/clear` "keeps the session's
identity". The transcript shows a new session id.

**Likely fix (decide in Plan):** add `clear` to the matcher, and in `main()` stamp the baseline for a
`clear` source **silently** (no relay, since the 2026-08-22 incident about relaying the queue
mid-session still applies), then return. `compact` keeps its session id, so it stays excluded. Open
question: should a `clear` also count as a re-entry for relay purposes, since the context really is
empty afterwards?

## B5. The wrap receipt cannot verdict a sibling repo — hit 3x in one legitimate multi-repo session
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-23` · issue `#5`
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

**Same pattern in `tools/sync_backlog.py` (seen 2026-09-23):** run from inside `cairn` during a
`bsr-tools` session, it synced **`bsr-tools`** ("synced with issr/bsr-tools"). It resolves the
project from the session and ignores the cwd, and it has no `--root` flag. Setting
`CLAUDE_PROJECT_DIR=$PWD` works around it. That run wrote nothing, but only because nothing had
changed in bsr-tools.
