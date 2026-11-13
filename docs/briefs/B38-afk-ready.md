**Not AFK-ready: B38 needs the reviewer's decision (Q1 to Q5 below). Stage 1 (a read-only evening report over this machine's projects) becomes AFK once Q1, Q2 and Q5 are answered. Stage 2 (acting on the report) waits on B5 and B33 whatever the answers.**

# B38 — the evening driver over the machine: groom brief

Backlog: `BACKLOG.md` B38 (issue #36), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-13 against `origin/main` at `68c0ba8`. Every file:line
below was read at that commit.

## The ask, as filed

`/cairn:wrap` closes the repo the session stands in. The evening ask is "wrap everything, push,
archive, so the other machine tomorrow does not skip a beat", and today that is N wraps from a
remembered list. The entry asks for a driver built from what this machine touched
(`check_repos.py`, `check_exits.py`) that, per project, answers wrapped? clean? pushed?, offers a
wrap where not, does not wrap a repo another agent is in (B33), reports push failures honestly,
and ends with one line naming the remotes the other machine should pull tomorrow (B36's input).
The weekly half is B53 and is not in this brief.

Related entries: B5 (the receipt cannot verdict a sibling repo), B31 (the morning roll-up, its
mirror image), B33 (concurrency rules; its groom brief proposes the live-session marker this
needs), B36 (the cross-environment sweep that consumes the last line), B39 (watches due elsewhere;
its fix (1) puts a line in this driver), B53 (the weekly half), B122 (pulled commits read as
unwrapped).

## What exists today, with evidence

| Piece | Where | What it means for B38 |
|---|---|---|
| Projects this machine has ended a session in | `plugins/cairn/tools/check_exits.py:109-154` `collect()` reads every `~/.claude/reentry-state/*/last_exit.json` and `stop-*.json`; `:157-172` `latest_per_project()` keeps the newest per project; `:192-193` `_flagged()` = dirty or unwrapped | The "what this machine touched" list already exists, with a timestamp per exit (`at`). No `git` call, so it is cheap. Its `dirty`/`unwrapped` are snapshots from the moment the session ended (`:33-35`), not current state. |
| The same list, as roots | `plugins/cairn/tools/check_repos.py:195-221` `known_roots()` | Only `last_exit.json` roots that still exist. Includes worktree lanes, each with its own record (B31 brief Q1 B). |
| Live per-repo state | `check_repos.py:131-192` `inspect()`: dirty count, unpushed count (`:117-128` `_unpushed`, `None` with a note when there is no upstream), never raises | The clean? and pushed? columns, measured now. Runs `git` in the target. |
| What the exit record says about wrapping | `plugins/cairn/hooks/dirty_tree_warning.py:168-174` writes `root`, `reason`, `unwrapped`, `wrap_ritual` into `last_exit.json` | `unwrapped` is `reentry_state.unwrapped_commits()` (`reentry_state.py:457-475`), which counts every commit since `.claude/.last_wrap`, **including commits that arrived by pull from the other machine**. That is B122's defect, so it cannot be the wrapped? column as is. |
| A per-repo wrap verdict that already handles pulls | `plugins/cairn/hooks/wrap_receipt.py:948-956` `last_receipt(root)`, `:959-968` `receipt_used(root)`, `:1117-1156` `orientation_line(root)` | Reads the project's last recorded receipt (verdict, time, head) and, when HEAD moved, uses the reflog to say whether the new commits were made here or arrived by pull (`:1145-1153`). `None` means either "never used the receipt" or "last receipt SET and HEAD unchanged", so a caller must test `receipt_used()` first. This is the right source for wrapped?. |
| Why the driver cannot wrap another repo for you | `wrap_receipt.py:377-416` `stamp_child_baselines()`; `BACKLOG.md` B5 | A baseline is stamped only at session start, for the session's own project (or its opted-in children when started in a parent folder). A `/cairn:wrap` run from the evening session against a sibling repo therefore reads `CAIRN UNKNOWN`, never `SET`. That is D26's recorded trade-off. |
| The opt-in gate | `wrap_receipt.py:335-374` `_opted_in_children()` and `repo_sweep.sibling_repos()`: a repo must have its own `NEXT.md` before any `git` runs in it | The same security boundary applies to any list this driver walks: git executes the target repo's config. |
| Is another session live in that repo | Nothing built. B33's groom brief (`docs/briefs/B33-afk-ready.md`, stage 1) proposes `hooks/live_sessions.py` reading `~/.claude/reentry-state/_sessions/*.json`; Glob for `plugins/cairn/hooks/live_sessions.py` finds nothing at `68c0ba8` | The "don't wrap a repo another agent is in" check has no source yet. |
| Where a wrap pushes and archives | `plugins/cairn/skills/wrap/SKILL.md` step 5 (`:135`, push with before/after counts), step 5b (`:193`, marker after a successful push), step 10 (`:667`, ask whether to archive, the wrap's final act) | Every write the evening ask names is already a step of the per-repo wrap, and each is attended there. |

## Questions for the reviewer

### Q1. What is the driver: a report, or something that acts?

- **A. A read-only report tool first (stage 1), the acting part later (stage 2).** `tools/evening.py`
  prints one row per project with wrapped? clean? pushed? and the pull line. The evening session
  reads it and the user opens a session in each repo that needs a wrap. No writes, so it can be
  built unattended and run any time.
- **B. A skill (`/cairn:evening`) that loops over the repos and runs the wrap in each from this
  session.** Every wrap reads `CAIRN UNKNOWN` until B5 is solved, so the verdict the rules say to
  trust is unavailable for every repo but one. It also pushes and archives from one session for
  many projects, which no rule covers yet.
- **C. Fold it into `/cairn:wrap` as a final "and the rest of the machine" step.** Grows the one
  skill every session reads, for a question asked once a day.

Recommendation: **A**. Stage 2 is the acting half and is blocked on B5 regardless of the answer.

### Q2. Which projects are on the list, and over what window?

- **A. Exit records from the last 24 hours** (`check_exits.collect()`, keep a project whose newest
  `at` is inside the window), plus the current project, gated on the root still existing and having
  its own `.git` and `NEXT.md` before any `git` runs there. Worktree lanes are shown under their
  parent repo's row (by `git rev-parse --git-common-dir`), not as rows of their own.
- **B. Every exit record ever** (`check_repos.py --known`). Complete, but the list grows with every
  repo ever opened, and old lanes dominate it.
- **C. Siblings of the current project** (`repo_sweep.sibling_repos()`). Matches B31's stage 1
  (D63), but misses a project outside the parent folder that was worked in today, which is exactly
  the one the evening forgets.

Recommendation: **A**, with `--since <hours>` (default 24) so a Friday evening can cover the week.
"Today" by local midnight was considered and rejected: a session that ran past midnight drops off.

### Q3. Does stage 2 wait for B33, or carry its own live-session check?

The entry says do not wrap a repo another agent is in. Nothing can tell that today.

- **A. Stage 2 waits for B33 stage 1** and calls `live_sessions.others_live()`. Stage 1 prints
  nothing about live sessions.
- **B. Stage 1 reads the `_sessions/*.json` stamps itself.** Duplicates B33's helper before it
  exists, and inherits B33 Q2's open false positive (a session that ended cleanly a few minutes ago
  reads as live).

Recommendation: **A**. A report that does not act cannot wrap over anyone, so stage 1 does not need
the check.

### Q4. Archiving

The entry's "wrap everything, push, archive" includes archiving the day's app sessions.
`/cairn:wrap` step 10 asks about archiving the current session only, in that session.

- **A. Out of scope for B38.** Each session's own wrap keeps asking. The report may list, read only,
  how many sessions are still open per project if a session listing is available to a tool (not
  checked by this firing).
- **B. Stage 2 archives every session in every listed project** once its repo is wrapped and pushed.
  Archiving a session the user is still using is the failure, and B33's marker is the only signal
  for that.

Recommendation: **A**.

### Q5. The pull line: how is "pushed today" measured?

- **A. From the remote-tracking reflog, no network.** For each listed repo, a
  `git reflog show --date=unix refs/remotes/origin/<branch>` entry whose message starts
  `update by push` and whose time is inside the window means this machine pushed there today. The
  line names those repos and branches: `pull tomorrow on the other machine: cairn (main), ...`.
- **B. Ahead count went to 0.** Cannot be measured after the fact; it needs a snapshot from earlier
  in the day.
- **C. Fetch every repo and compare.** Network per repo, and it says what is on origin, not what
  this machine put there.

Recommendation: **A**. Known gap: a push made with `--no-track` or to a branch with no
remote-tracking ref leaves no reflog entry; say so in the tool's docstring.

## Stage 1 slice: the evening report (if Q1 = A, Q2 = A, Q5 = A)

Fields line to paste under a new entry (or under B38 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: new `plugins/cairn/tools/evening.py`, new `plugins/cairn/tools/test_evening.py`. No change
to any existing file. A payload change, so it gets the routine version bump at the attended pass.
`docs/guide.md` gains one paragraph naming the tool; if that file is busy or shared at the time,
the text goes in the dossier.

- `evening.py [--since HOURS] [--json]`. Imports, with the same defensive import and one-line exit-0
  fallback as `check_repos.py:99-112`: `check_exits.collect`, `check_exits.latest_per_project`,
  `check_repos.inspect`, `wrap_receipt.receipt_used`, `wrap_receipt.last_receipt`,
  `wrap_receipt.orientation_line`.
- Project list per Q2 A. Before any `git` call in a root: it exists, has `.git`, and has `NEXT.md`.
  A root with no `NEXT.md` (a session started in a parent folder, or a repo not in the system) is
  dropped without a row and counted in one trailing line, `<n> other folder(s) had sessions but no
  NEXT.md`: silence is what "not in the system" means everywhere else, and a row per such folder
  would repeat every evening. A root that no longer exists is a row reading `skipped: gone`. A
  project known only from `stop-*.json` has no root (`check_exits.py:51-62`), so it is a row by its
  slug reading `root unknown (no session has ended there yet)` and nothing runs for it.
- One row per project:
  - wrapped?: `never` when `receipt_used()` is false; otherwise the last receipt's verdict and time,
    plus `orientation_line()`'s text when the verdict is `SET` and the line is not `None` (that is
    what separates "commits made here since the wrap" from "commits pulled since the wrap"). For any
    other verdict, do not use `orientation_line()`'s text: it says "did not record a completed wrap"
    for every verdict other than `SET` and `UNKNOWN`, `NOT DUE` included (`wrap_receipt.py:1142-1144`). Never
    `unwrapped_commits()`, for the B122 reason in the table.
  - clean?: `inspect()["dirty"]`, with up to `MAX_LISTED` paths.
  - pushed?: `inspect()["unpushed"]`, or its note (`no upstream branch`).
  - A row needs a wrap when its last receipt is not `SET`/`NOT DUE`, or `orientation_line()` says
    commits were made here after the wrap, or it is dirty, or it is ahead.
- Footer: the Q5 A pull line, or `nothing pushed from this machine in the last <N>h`.
- Exit 0 always (advisory), like `check_exits.py:269`.
- Read only: never writes a state file, a receipt, a marker or a repo file. Never fetches.

Tests (fixtures only: a temp `CLAUDE_CONFIG_DIR` set before the first import that can touch
`state_dir()`, see `run_tests.py`'s B74 docstring; throwaway git repos with a bare repo as origin;
never the real `~/.claude/`):

1. No exit records: one line saying so, exit 0.
2. Two projects with records inside the window and one outside: two rows, plus the current project.
3. A record whose root is gone is a `skipped: gone` row. A record whose root has `.git` but no
   `NEXT.md` has no row, is counted in the trailing line, and no `git` process runs in it (assert
   with a wrapped `git` helper or by giving the fixture repo a `core.fsmonitor` hook that writes a
   file, which must not appear). A project with only a `stop-*.json` is a `root unknown` row.
4. A project with a `SET` receipt at HEAD, clean and pushed: reads as done, not in "needs a wrap".
5. The same project after a local commit: needs a wrap, and the row carries `orientation_line()`'s
   "HEAD has moved" text.
6. The same project after a fast-forward pull only: not "needs a wrap" (the B122 case), and the row
   says the commits arrived by pull.
7. A project that has never recorded a receipt: wrapped? reads `never`, not `OPEN`. A project
   whose last receipt is `NOT DUE`, clean and pushed: reads as done, with no "did not record a
   completed wrap" text.
8. Dirty, ahead, and no-upstream fixtures each give the right column.
9. A push to the bare origin inside the window: named in the pull line; a push older than the
   window is not.
10. Two worktrees of one repo with records: one row, under the main checkout.
11. `--json` carries the same rows; `--since 1` drops a record from two hours ago.
12. Snapshot every file under the fixture state dir and the fixture repos before and after: nothing
    changed.

Done: those tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, and nothing
is left in the real state dir.

## Stage 2 (not AFK; listed so it is not forgotten)

Offer a wrap per "needs a wrap" row, skipping any repo B33's marker says is live, with honest push
failures. Blocked on B5 (a wrap from here reads `CAIRN UNKNOWN`) and on B33 stage 1. B39's fix (1),
watches that came due today in projects not opened, is a column this report can gain once B31's
stage 1 exposes the watch classifier for a foreign root.

## Out of scope

- B53 (the weekly half, timesheets).
- B36's other environments: this is one machine's report; its pull line is B36's input.
- Archiving (Q4).
- Any `SessionStart` line. The report is run on demand, in the evening.

## Side note for the attended pass

The plugin source cites "B38" for a different subject: `hooks/issue_host.py:206`, `:244`, `:260`,
`tools/check_install.py:207`, `tools/test_check_install.py:62` and `tools/test_issue_host.py:301`,
`:306` all mean the predecessor repo's B38 (finding an installed `gh`/`glab` that is not on PATH),
landed 2026-09-05. A reader following "B38" from those files lands on this entry. Same drift as the
B36 brief's finding 2. Not changed here (not this brief's files); the attended pass can decide
whether to annotate them with the old repo's name.

A possible defect, read from the code and not reproduced: `wrap_receipt.orientation_line()`
(`:1142-1144`) prints "the previous session did not record a completed wrap" for every verdict
other than `SET` and `UNKNOWN`, so a session whose wrap legitimately recorded `NOT DUE` (which
`main()` treats as success, `:1267`) would trigger that line at the next session start. Worth a
backlog entry if a test confirms it.
