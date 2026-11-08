**Not AFK-ready: B44 needs the reviewer's decision (Q1 to Q3 below). One test-only slice at the end is AFK-ready now and does not depend on the answers.**

# B44 — a hook that blocks closing a session with unwrapped work: groom brief

Backlog: `BACKLOG.md` B44 (issue #42), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-02`.
Written by the scheduled firing on 2026-11-07 against `origin/main` at `955e504`. Every file:line
below was read at that commit.

## The ask, as filed

Raised after `dirty_tree_warning.py` warned correctly mid-session: can the warning become a block?
The entry names two candidates short of a block: a louder warning (today's de-dupes to "worse than
last time"), or the archive offer as the harder stop, since it is read at a moment of attention.
It says it needs a plan because it changes the moment of leaving.

## What has changed since it was filed

**The second candidate has largely been built, by a different item.** B64 (D36, v1.63.0, CHANGELOG
entry "B64 (D36)") added `plugins/cairn/hooks/archive_guard.py`, a `PreToolUse` hook on
`mcp__ccd_session_mgmt__archive_session` (`plugins/cairn/hooks/hooks.json:25-34`). It refuses an
agent's self-archive while `wrap_receipt.verdict()` reads `OPEN`, including commits made after a
`SET` (`archive_guard.py:2-21`, decision table at `:23-31`). B44 predates it by three weeks and was
never cross-referenced.

What B64 does not cover, by its own account (`archive_guard.py:44-49`, D36's cost column):

- **The sidebar archive.** No hook fires on it. The next session's "did not finish cleanly" box is
  the only cover.
- **Closing the window or the app without archiving.** Same: nothing fires that can speak.
- **A session whose baseline stamp failed.** It archives unwrapped, with one line.

## What exists today, with evidence

| Piece | Where | What it does |
|---|---|---|
| Stop warning | `hooks/dirty_tree_warning.py:90-148` (`_handle_stop`) | Warns only when the state got worse than the last warning: a new dirty path, or a higher unwrapped-commit count (`:107-118`). Fingerprint per session in `state_dir()/stop-<session>.json`, pruned after 7 days (`:59`, `:66-73`). |
| The no-block rule | `hooks/dirty_tree_warning.py:40-42` | "NEVER BLOCKS. A Stop hook that traps a session is worse than a dirty tree … a session that cannot end is a session with no NEXT.md to resume from." Exits 0, never `decision: block`. |
| Why the de-dupe exists | `hooks/dirty_tree_warning.py:15-24` | `Stop` fires once per turn. A per-turn warning was reported as wallpaper (2026-08-21) and a session still ended with five uncommitted files. |
| SessionEnd breadcrumb | `hooks/dirty_tree_warning.py:151-175` | Writes `last_exit.json`. SessionEnd cannot speak (`:32-36`). |
| Cursor | `hooks/dirty_tree_warning.py:184-190` | Cursor's `stop` submits any output as the next prompt (B57), so Cursor gets the breadcrumb only. Any louder Stop message is Claude Code only. |
| Archive guard | `hooks/archive_guard.py` | Above. Fails open on every error (`:51-55`). |
| Archive offer | `hooks/archive_offer.py:2-16` | Records whether the wrap's step 10 asked about archiving. Blocks nothing. |
| Verdict | `hooks/wrap_receipt.py:1010` `verdict()` | The only source of `SET` / `NOT DUE` / `OPEN` / `UNKNOWN`. No baseline means `UNKNOWN` first (`:1025-1032`). |
| Unwrapped count | `hooks/reentry_state.py:414` `unwrapped_commits()` | `git rev-list <.last_wrap sha>..HEAD`. Per machine (B122). |

**No test exercises `_handle_stop`.** A Grep of `plugins/cairn/**/test_*.py` for `_handle_stop` and
`dirty_tree_warning` finds only `test_cursor_build.py:191` (Cursor `stop` prints nothing) and an
unrelated string in `test_check_exits.py:66`. The "worse than last time" rule, which is the whole
reason the warning is quiet, is untested.

## B122 is in the way of a louder warning

`unwrapped_commits()` counts every commit after this machine's `.last_wrap` sha, including commits
pulled from another machine (B122, `BACKLOG.md`, filed 2026-10-29). The Stop warning's second half
(`dirty_tree_warning.py:139-147`) uses that count. Making that warning louder before B122 is fixed
would make a known false alarm louder. B122 itself says to fix `dirty_tree_warning.py:144` and
`session_orientation.py:790` together.

## Questions for the reviewer

### Q1. Does B64 close B44?

- **A. Close B44 as covered by B64.** The agent path is a hard stop. The sidebar and window-close
  paths cannot be hooked at all, and the next session's box covers them. Record the close as a
  `docs/decisions.md` row pointing at D36.
- **B. Keep B44 open, narrowed to "the warning is too quiet to read as urgent".** Then Q2.
- **C. A real block on `Stop`.** Rejected in the file's own header (`:40-42`) and by the incident
  behind it. Listed only so the rejection is explicit.

Recommendation: **A**, unless the reviewer has seen a session end unwrapped since v1.63.0 by a path
other than the sidebar. If so, that incident decides it, and it should be written into the entry.

### Q2. If B: what does "louder" mean?

- **a. Lead the Stop warning with the verdict token.** On the warn path only (it already fires only
  when things got worse), call `wrap_receipt.verdict()` and open the message with
  `CAIRN OPEN · <missing steps>`, the same token the user sees everywhere else. Cost: verdict's git
  calls, paid only when a warning is about to print. `UNKNOWN` must not be printed as `OPEN` here
  either.
- **b. Re-warn on time.** Repeat the same warning if N minutes passed since the last one. Risks the
  wallpaper the de-dupe was written to kill (`:15-24`).
- **c. Re-warn when the user's message signals leaving** ("thanks", "done for today"). Hooks see the
  prompt on `UserPromptSubmit` (`item_start.py` already runs there), so this is possible, but it is a
  keyword guess and will miss and misfire.

Recommendation: **a**. It changes what the message says, not how often, so it cannot become
wallpaper, and it uses the one verdict that is already trusted.

### Q3. Order against B122?

- **A. B122 first.** Then the count in the message stops including other machines' work.
- **B. Together**, since both touch `dirty_tree_warning.py:139-147`.
- **C. B44 first.**

Recommendation: **A**, or B if one session takes both. Not C: it amplifies B122's false alarm.

## Slice if Q1 = B and Q2 = a

Fields line to paste under a new entry (or under B44 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: `plugins/cairn/hooks/dirty_tree_warning.py`, new `plugins/cairn/tools/test_dirty_tree_warning.py`.

Change: in `_handle_stop`, after `worse` is decided and before the lines are built, compute the
verdict for `root` the way `archive_guard.py` does (import `wrap_receipt`, never parse `--check`
output; see `archive_guard.py:15-21`). If it is `OPEN`, the first line is
`CAIRN OPEN · <missing steps>`. If `UNKNOWN`, `SET`, `NOT DUE` or any error, the message is exactly
what it is today. Never raises, never blocks.

Tests (fixtures only, a temp `CLAUDE_CONFIG_DIR`, throwaway git repos):

1. Verdict `OPEN` and a new dirty path: the first line starts `CAIRN OPEN`.
2. Verdict `UNKNOWN`: the message is byte-identical to today's, no `CAIRN` token.
3. Verdict raises: today's message, exit 0.
4. Not worse than last time: silent, and the verdict is never computed (count the calls).
5. Cursor `stop`: still prints nothing (already pinned in `test_cursor_build.py`; keep it green).

Done: the five tests pass, the full suite passes, and `docs/` or the wrap skill names the new first
line wherever the Stop warning's wording is quoted.

## AFK-ready now, independent of Q1 to Q3: pin the de-dupe

Fields line: `` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

New file `plugins/cairn/tools/test_dirty_tree_warning.py`, tests only, no hook change. Call
`_handle_stop(root, event)` directly with a temp `CLAUDE_CONFIG_DIR` and a throwaway git repo:

1. First call with one dirty file: a warning naming it.
2. Same state again: `None` (not worse).
3. One of two dirty files committed: `None` (smaller is not worse).
4. A new dirty path: a warning.
5. A path that went away and came back: a warning (it was dropped from the record, `:107-110`).
6. Unwrapped count rises (write a `.claude/.last_wrap` naming an older sha, then commit): a warning.
   Commit the marker file itself first, so the dirty-path set does not change and only the count
   can trigger the warning.
7. `state_dir()` returns `None` (monkeypatch `dirty_tree_warning.state_dir`): `None` (no memory
   means silence, `:119-122`).
8. A different `session_id`: warns afresh (fingerprints are per session).

Done: the file passes on its own and in `run_tests.py`, and `no leak into the real state dir`.
`run_tests.py` discovers every `tools/test_*.py` (`run_tests.py:158`), so the name is enough. For
test 6, `.last_wrap` must name a real commit: `unwrapped_commits()` returns `None` for a sha that
`git cat-file -e` cannot find (`reentry_state.py:429-430`).

## Out of scope

- Hooking the sidebar archive or window close: no event exists.
- Changing `archive_guard.py`'s decisions (D36).
- B122's counting fix itself.
