**Not AFK-ready: B33 needs the reviewer's decision (Q1 to Q4 below). Stage 1 (the "another session is live here" line) becomes AFK once Q2 and Q3 are answered; stage 2 (the rule text) once Q1 is.**

# B33 — several sessions at once: the concurrency rules are implicit: groom brief

Backlog: `BACKLOG.md` B33 (issue #31), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-07 against `origin/main` at `955e504`. Every file:line
below was read at that commit.

## The ask, as filed

Sessions running at once in one repo coordinate through nothing. The entry lists the rules that
are still unwritten and three builds:

- **One writing working tree per repo**; a second writer takes a worktree or a separate clone. A
  branch is not isolation (`git checkout -b` does not isolate uncommitted files).
- **A foreign session may only append** (B32 depends on this).
- **The handoff is a wrap boundary:** wrap, fetch, push, cut the worktree from `origin/main`, hand
  over, end the session. A "donor stops writing" hold was rejected: a hold is state somebody has
  to remember.
- **When isolation fires:** the tree is dirty, another session is known live, or `git worktree
  list` already shows a second checkout.
- Subagent `isolation: worktree` is a different mechanism, not this rule.

Builds: (1) write these into `rules/CLAUDE.md` and `/cairn:wrap`; (2) a cheap "is another session
live here?" marker at `SessionStart`, warn never block; (3) feed it into B31. **Do not build a
lock.** B34 is the mechanical half (hash at read, check before rewrite) and is not in this brief.

## What exists today, with evidence

| Piece | Where | What it means for B33 |
|---|---|---|
| The only concurrency rule written | `plugins/cairn/rules/CLAUDE.md:257-262` ("ALWAYS re-read `NEXT.md` from disk ... Several agents may be running at once"), repeated in `skills/wrap/SKILL.md:247-256` (step 7) | Covers stale `NEXT.md` rewrites only. Nothing on one writer per tree, append-only foreign writes, or the handoff. |
| Wrap separates other sessions' files | `skills/wrap/SKILL.md:43-45` (step 1: "never stage another session's work") | Tells the agent to sort files, not how to avoid sharing the tree. |
| "A branch is not isolation" is already recorded as a correction | `skills/next/references/incidents.md:513-515` | The claim "a second writer needs a branch or a worktree" was retracted there; the rule text never followed. |
| **A per-session liveness stamp already exists** | `plugins/cairn/hooks/reentry_state.py:79` (`SESSION_ROOT_SUBDIR = "_sessions"`), `:133-172` (`_stamp_session_root`), `:200-213` (`_resolve_project_root` stamps on every resolve from `CLAUDE_PROJECT_DIR`) | Each session writes `~/.claude/reentry-state/_sessions/<session-id>.json` = `{"root": ..., "at": <epoch>}`, rewritten on every hook call that resolves the root. The docstring (`:153-158`) says that is every `Stop` (once per turn) and every `PostToolUse` write. So "another session active here recently" is: another file in that folder, different id, same working tree, `at` within a window. **No new state is needed** for build (2). Not re-measured by this firing: that hooks really have `CLAUDE_CODE_SESSION_ID` set (the docstring at `:92-98` confirms it for `Bash` steps). |
| Stamp blind spots | `reentry_state.py:105-106` (no session id inside Cursor), `:207-213` (stamped only when `CLAUDE_PROJECT_DIR` is set), `:86` (7-day TTL, a growth bound only) | A Cursor chat and a bare terminal never stamp, so they are invisible to the marker. Warn-only makes a miss cost nothing new. |
| Working-tree identity | `reentry_state.py:267` `toplevel()` | Compare two stamps by toplevel: a session opened in a subdirectory is the same tree; a worktree has its own toplevel and is correctly a different tree. |
| Where an orientation warning goes | `plugins/cairn/hooks/session_orientation.py:1110-1124` (machine mismatch, `_left_behind_warning`, `_divergence_warning`, each in its own try, "never block"), relay tier computed just below (`:1134`) | The new line sits beside these, with the same never-fail wrapping. |
| The scheduled firing shares the checkout | `BACKLOG.md` B120 | A firing is a Claude Code session too, so it stamps. The marker would show an attended session that a firing is running in the same tree, which is B120's detection half. |
| No lock anywhere | Grep of `plugins/cairn/**/*.py` for `lock` (case-insensitive): only `repo_sweep.py:56`, `:110`, `:204`, all about git's own lock contention | Consistent with the entry's "do not build a lock". |

## Questions for the reviewer

### Q1. Where does the rule text (build 1) live?

`rules/CLAUDE.md` is loaded into every session in every project, so every line there has a
standing cost (B24 tracks that budget).

- **A. Split by when it is needed.** `rules/CLAUDE.md` gets one short paragraph after the
  re-read rule (`:257-262`): one writing tree per repo; a branch is not isolation; a foreign
  session only appends to another project's `INBOX.md`. The handoff procedure goes in
  `/cairn:wrap` as a short "handing over to a second writer" step, since a handoff starts with a
  wrap. The `isolation: worktree` distinction goes in `docs/running-a-batch.md`, where subagent
  fan-outs are described.
- **B. All of it in `rules/CLAUDE.md`.** One place, but the handoff detail is read every session
  and needed rarely.
- **C. Skills only.** No always-loaded cost, but a session that never runs `/cairn:wrap` never
  sees it, which is the reason the rules file exists (its header says so).

Recommendation: **A**. Proposed paragraph for `rules/CLAUDE.md`, to be measured with
`tools/measure_context.py` before and after:

> **One writing working tree per repo.** A second session that will edit files takes a worktree
> cut from `origin/main` or a separate clone; a branch is not isolation, because uncommitted files
> are shared by every branch of one tree. A session in one project writes to another project only
> by appending a bullet to that project's `INBOX.md`. Take a worktree when the tree is dirty,
> another session is known to be live in it, or `git worktree list` already shows a second
> checkout. Handing work to a second writer is a wrap boundary: wrap, fetch, push, cut the
> worktree from `origin/main`, hand over, end the session.

### Q2. What does the live-session marker (build 2) read?

- **A. The existing `_sessions/*.json` stamps.** Another stamp, different id, same toplevel, `at`
  within the window. No new state, no new write path.
- **B. A new marker file per project in `state_dir()`.** Needs its own write on every turn and its
  own cleanup, and duplicates A.
- **C. `git worktree list` only.** Shows a second checkout exists, not that anyone is in it.

Recommendation: **A**, with C's output as a separate, quieter fact only if Q3 wants it. Known
false positive: after a crash and resume, the dead session's stamp is recent and reads as live
(B11 records a retried and reopened session stamping under a new id each time). The wording below says "was active", not "is running",
for that reason.

**A larger false positive, from a clean end (added by the scheduled review).** Nothing marks a
stamp as ended: `SessionEnd` runs only `dirty_tree_warning.py` (`plugins/cairn/hooks/hooks.json:70-78`),
and `_stamp_session_root` only ever writes `{"root", "at"}`. So a session that closed normally a
few minutes ago reads exactly like a live one. The commonest sequence there is, closing one
session and opening the next in the same tree, would show the line on the new session's first
reply every time it happens inside the window. That includes an attended session opened shortly
after a scheduled firing finished. Q3 has to answer this before the tier is chosen.

### Q3. The window, the wording, and the relay tier

- Window: **30 minutes** recommended. A stamp is rewritten every turn, so an attended session
  that has gone quiet for longer than that is treated as not live. A longer window raises the
  crash-and-resume false positive.
- Wording (recommended): `another session was active in this working tree <N> min ago. Two
  writers in one tree overwrite each other: take a worktree or a separate clone for this one.`
  With more than one, name the count and the most recent age. Never name the other session's id.
- Relay tier: **recommend it raises the tier to `RELAY FIRST`**, like the divergence banner,
  because starting work in a tree someone else is writing is the time-sensitive hazard. The
  alternative is an informational line that leaves the tier alone. The cost of `RELAY FIRST`: both
  false positives from Q2 (crash-and-resume, and the far commoner clean end) then lead the first
  reply for up to the window, and a warning that fires on a dead session teaches the reader to
  skip it.
- Telling a clean end from a live session (needed if the tier is `RELAY FIRST`):
  - **i. Mark the stamp ended at `SessionEnd`.** A new `SessionEnd` entry (or a line in the existing
    one) writes `"ended": <epoch>` into this session's own `_sessions/<id>.json`; `others_live`
    skips a stamp with `ended` set. Costs a write path in `reentry_state.py`'s stamp code (busy in
    open PR #157 while it is open) and a `hooks.json` change. A crash still leaves no `ended`, so
    crash-and-resume remains.
  - **ii. Keep the line informational** (no tier change) and accept both false positives.
  - **iii. Shorten the window** (for example 10 minutes). Narrows the clean-end case but also
    misses a live session that has been quiet for longer.
  - Recommendation: **i** if `RELAY FIRST` is chosen, otherwise **ii**. If i, stage 1 gains the
    `SessionEnd` write and test 13 below.

### Q4. Build (3), feeding B31

Recommend **defer** to B31's stage 2. B31's own brief (open groom PR #156) has no live-session
input yet; the helper in stage 1 below is the piece B31 would call.

## Stage 1 slice: the live-session line (if Q2 = A and Q3 is answered)

Fields line to paste under a new entry (or under B33 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: new `plugins/cairn/hooks/live_sessions.py`, new `plugins/cairn/tools/test_live_sessions.py`,
and a few lines in `plugins/cairn/hooks/session_orientation.py` beside `_divergence_warning`.
**A new module rather than a function in `reentry_state.py`**, because `reentry_state.py` is
changed by open PR #157; a new file cannot conflict with it.

- `others_live(root, *, window_s=1800, now=None) -> list[float]`: ages in seconds of other
  sessions' stamps whose root's `toplevel()` equals `toplevel(root)` (falling back to the resolved
  path when either is not in a git repo), excluding this session's own id, `at` within
  `window_s`. Reads the folder `reentry_state._session_root_dir()` returns. Never raises: a torn
  file, a missing path, an unreadable folder are each skipped. An `at` in the future (a clock
  change) counts as age 0, not as negative.
- Known false positive, accepted: a session whose `CLAUDE_PROJECT_DIR` is the main checkout but
  which works inside a worktree by changing directory stamps the main checkout's root, so it reads
  as live in the main tree.
- `warning_line(root, ...) -> str | None`: the Q3 wording, or None.
- In `session_orientation.main()`, compute it in its own `try` beside `diverged` (`:1121-1124`),
  print it in the same block as the other git banners, and apply Q3's relay-tier answer.
- Read-only: the module never writes or deletes a stamp. Pruning stays `reentry_state`'s.

Tests (fixtures only: a temp `CLAUDE_CONFIG_DIR`, real throwaway git repos under a temp dir, the
session-id variables set and restored in `finally`):

1. No other stamps: no line.
2. Another stamp, same root, 5 minutes old: one line, naming 5 min.
3. Another stamp, same root, 2 hours old: no line.
4. Another stamp whose root is a subdirectory of the same repo: a line.
5. Another stamp for a `git worktree add` checkout of the same repo: no line (different tree).
6. A stamp with this session's own id: ignored.
7. A torn JSON file and a stamp whose root no longer exists: ignored, no exception.
8. Two other live stamps: the line names the count and the most recent age.
9. `root` not in a git repo: compared by resolved path, same answers as 2 and 3.
10. Orientation integration: the line is printed, the hook still exits 0, and the tier follows
    Q3's answer.
11. No session id in the environment (a bare terminal): the function still works and excludes
    nothing.
12. A stamp whose `at` is 60 seconds in the future: counted as live, age 0.
13. Only if Q3 picks i: another stamp, same root, 5 minutes old, with `ended` set: no line; and
    running the `SessionEnd` hook in a fixture session sets `ended` in that session's own stamp only.

Done: the twelve tests (thirteen under Q3 i) pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, and
nothing is left in the real state dir.

## Stage 2 slice: the rule text (if Q1 = A)

`Sonnet 5` · effort `medium` · `AFK/Auto`. Files: `plugins/cairn/rules/CLAUDE.md` (the Q1 paragraph, in
the plugin source, never the installed copy), `plugins/cairn/skills/wrap/SKILL.md` (a short handover step), and
`docs/running-a-batch.md` (one line on `isolation: worktree`). Before editing the rules file, read
`skills/wrap/references/incidents.md` and `skills/next/references/incidents.md` as its header
requires. Measure with `tools/measure_context.py` before and after and put both numbers in the
dossier. A rules change is a payload change, so it needs the routine version bump at the attended
pass.

## Out of scope

- B34 (hash at read, check before rewrite).
- B120's fix for scheduled firings (a dedicated clone or a re-check before commit). Stage 1 only
  makes the shared tree visible; a firing prompt that aborts when another session is live is a
  separate change to the task prompt.
- Any lock (the entry rules it out).
- Cursor and bare-terminal sessions, which do not stamp.
