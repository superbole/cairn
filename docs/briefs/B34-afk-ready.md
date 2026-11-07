**Not AFK-ready: B34 needs the reviewer's decision (Q1 to Q3 below), and Q1 starts with a measurement only an attended session can make. Slice A becomes AFK once Q1 and Q2 are answered; slice B (the fetch) once Q3 is.**

# B34 — make concurrency safety mechanical: hash at read, check before rewrite: groom brief

Backlog: `BACKLOG.md` B34 (issue #32), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-08 against `origin/main` at `82c19bd`. Every file:line
below was read at that commit. B33 (open groom PR #163) is the rules half; this is the mechanical half.

## The ask, as filed

A second session can change `NEXT.md`, `BACKLOG.md` or `CHANGELOG.md` while this one works, and a
wholesale rewrite from a stale copy deletes the other's edits and looks correct. "Re-read from disk"
is an instruction to the party most likely to be wrong. Mechanism:

1. At `SessionStart`, store the sha256 of the three files in this session's `state_dir()`;
   `wrap_receipt.py` already stamps these, so reuse it and add no state.
2. Before any wrap rewrite, re-hash and compare. Different: name the file and what changed, and hold
   the rewrite until it is re-read.
3. The wrap fetches before it rewrites, offering `--ff-only`, never pulling unasked.

Known blind spot: local hashes see a sibling on the same disk only; two sessions in a worktree and the
main checkout collided on ids with identical hashes. "Stamp the allocation, not only the bytes." A hash,
not a lock. Three files only; `INBOX.md` is append-only.

## What exists today, with evidence

| Piece | Where | What it means for B34 |
|---|---|---|
| The session-start hashes | `plugins/cairn/hooks/wrap_receipt.py:178` (`TRACKED = ("NEXT.md", "CHANGELOG.md", "BACKLOG.md", "INBOX.md")`), `:273-277` `_digest` (sha256, first 16 hex), `:280-332` `stamp_baseline` | Part (1) is already built: one write per session, at start (`:315` declines a second stamp). No new state is needed for the start snapshot. |
| What the receipt does with them | `wrap_receipt.py:460-476` `_changed`: True when the file's hash now differs from the start | **The receipt reads "differs from session start" as evidence that THIS session did the step** (a rewritten `NEXT.md`, a `CHANGELOG.md` entry). Part (2) as filed would read the same fact as evidence that ANOTHER session did. See the main finding. |
| The wrap writes these files itself, in order | `skills/wrap/SKILL.md` step 2 at `:76` (`CHANGELOG.md`), step 7 at `:245-256` (`NEXT.md`, "RE-READ IT FROM DISK FIRST ... edit only the parts you are changing ... prove it with `git diff`"), step 8a at `:416` (`BACKLOG.md`) | By the time the wrap rewrites `NEXT.md`, `CHANGELOG.md` already differs from the start snapshot by the wrap's own hand, and a session that worked an item has often edited `BACKLOG.md` or `NEXT.md` mid-session. |
| Which tool calls a hook sees today | `plugins/cairn/hooks/hooks.json:14-35` (PreToolUse: `Bash`, the archive tool), `:47-57` (PostToolUse: `Edit|Write|NotebookEdit|Bash|PowerShell`, `repo_recorder.py`) | No hook sees a `Read`, and none runs before an `Edit`/`Write`. A "hash at last read" needs both. |
| The only fetch | `plugins/cairn/hooks/session_orientation.py:654` (`git fetch origin <branch>` at session start, 8 s timeout, `:163`) | Part (3) does not exist: the wrap never fetches before step 7. Step 5 (`SKILL.md:135`) reports the ahead/behind count only after the commit. |
| The id-allocation half | `BACKLOG.md` B110 ("Refuse to file an item whose id was already spent") and B87 (Queue 2: orient from origin's `NEXT.md` when behind, never start an item on a stale base) | The entry's blind spot is not a hashing problem; it is these two. |

### The main finding: "differs from session start" cannot tell whose edit it was

The entry says to compare against the `SessionStart` hash. But the session itself edits these files
before the rewrite: the wrap writes `CHANGELOG.md` at step 2 (before step 7) and `BACKLOG.md` at
step 8a (after it), and a session that worked an item has
usually touched `BACKLOG.md` or `NEXT.md` already. Every one of those reads as "changed since start",
so a check built as filed fires on almost every wrap and is learned as noise. That is the opposite of
what the receipt does with the same hashes (`_changed` treats a difference as this session's own work).

What part (2) needs is not "the hash at session start" but **"the hash when this session last read or
wrote the file"**. That is a different snapshot, updated through the session, and it is the one piece
of new state B34 cannot avoid unless the harness already keeps it (Q1).

## Questions for the reviewer

### Q1. Does Claude Code's own read-state tracking already do part (2)? (measure first)

Claude Code's `Edit` and `Write` tools track what the session has read: their own tool descriptions
say `Edit` fails on a file not read in the conversation, and `Write` fails to overwrite an existing
file not read. **Neither description says what happens when the file changed on disk after that read,
and this firing did not measure it** (an unattended run cannot set up a second writer safely). That
case, for `Write` above all (the wholesale-rewrite tool), is the whole of part (2).

The measurement, about ten minutes, attended: in a scratch repo, `Read` a file, change it from a
terminal, then ask the session to `Write` it whole and separately to `Edit` it. Record both outcomes in
`docs/decisions.md`.

- **A. Both refuse.** Part (2) is already mechanical for Claude Code's file tools. What is left is
  writes the harness cannot see: a shell rewrite (`python`, `sed`, PowerShell `Set-Content`) and
  Cursor. Recommend narrowing B34 to those, or closing part (2) with a decision row.
- **B. `Edit` refuses, `Write` does not.** Build slice A, guarding `Write` on the three files.
- **C. Neither refuses.** Build slice A for both.

Recommendation: **measure before building anything.** If A, the cheapest mechanical win left is a
`staged_review_guard`-style refusal of a shell command that writes one of the three files, which is
a different, smaller item.

### Q2. If slice A is built: block, or warn?

- **A. Block** (`PreToolUse` deny, naming the file), the entry's "hold the rewrite until it is
  re-read". A re-`Read` clears it. A stored digest can say *that* the file changed, not *what*
  changed; the re-`Read` the message asks for is what shows it. Saying what changed would mean
  storing a copy of each file per session, which the entry's "add no state" argues against.
- **B. Warn** and let the write proceed. Cheaper to get wrong, but the entry's whole point is that an
  instruction to the wrong party does not work, and a warning is an instruction.

Recommendation: **A**, scoped to the three files and failing open on any error (an unreadable state
file, a missing hash): a hook fault must never block a write. That matches "fails open" in the entry.

### Q3. Part (3), the fetch before the rewrite: here, or in B87?

B87 (Queue 2, HITL/Plan) is already planning "when the checkout is behind, orient from origin and never
start an item on a stale base". A fetch at wrap time is the same question asked at the other end of
the session.

- **A. Fold into B87's plan.** One design for "behind origin", both ends.
- **B. Build here as slice B.** A short step in `/cairn:wrap` before step 7: `git fetch origin`; if
  `NEXT.md`, `BACKLOG.md` or `CHANGELOG.md` differ between `HEAD` and the upstream, say which and
  offer `git pull --ff-only`; never pull unasked. Skill text only, no code.

Recommendation: **A**, and note under B87 that the wrap needs the same check. It avoids two
half-designs of one rule.

## Slice A: the last-seen guard (if Q1 is B or C)

Fields line to paste under a new entry (or under B34 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: new `plugins/cairn/hooks/rewrite_guard.py`, new `plugins/cairn/tools/test_rewrite_guard.py`,
and `plugins/cairn/hooks/hooks.json` (a payload change: routine version bump at the attended pass).

- **Record.** A `PostToolUse` entry matching `Read|Edit|Write` runs `rewrite_guard.py --seen`: when the
  tool's `file_path` resolves to `NEXT.md`, `BACKLOG.md` or `CHANGELOG.md` at the project root, write
  its current `_digest` (import `wrap_receipt._digest`, never re-implement) into
  `<state_dir>/_seen/<session-id>.json` as `{name: digest}`. Any other path: exit 0 at once, before
  any hashing, so the cost on ordinary reads is one process start.
- **Check.** A `PreToolUse` entry matching `Edit|Write` runs `rewrite_guard.py --check`: for one of the
  three files, if a seen digest exists and the file's digest now differs, deny with a message naming
  the file and saying to `Read` it again. No seen digest (never read this session): allow; the
  harness's own "read before edit" covers that.
- **Fail open.** No session id, no state dir, an unreadable or torn seen file, a hashing error: allow,
  exit 0, print nothing. Cursor (no session id, `wrap_receipt.session_id()` returns "" there): allow.
- Prune `_seen/` on the same TTL as the baselines (`wrap_receipt._prune`).
- Accepted: the session's own shell write to one of the three files (a `python` or `sed` step) does
  not update the seen digest, so its next `Edit`/`Write` is denied until it re-reads. That is the
  safe direction, and costs one `Read`.

Tests (fixtures only: a temp `CLAUDE_CONFIG_DIR`, a throwaway git repo, the session id set and
restored in `finally`, the hook run as a subprocess with stdin closed):

1. `Read` of `NEXT.md` records its digest; `Read` of `README.md` records nothing.
2. `Write` of `NEXT.md` after a `Read`, file unchanged: allowed.
3. `Write` of `NEXT.md` after a `Read`, file changed on disk since: denied, message names `NEXT.md`.
4. As 3, then a fresh `Read`: the next `Write` is allowed.
5. The session's own `Edit` updates the seen digest, so its next `Edit` is allowed (no self-conflict).
6. `CHANGELOG.md` and `BACKLOG.md` behave as `NEXT.md`; `INBOX.md` is never checked.
7. A path to `NEXT.md` in a subdirectory, or in another repo: not checked.
8. No session id: allowed, nothing written.
9. A torn seen file: allowed, no exception.
10. A Windows path with backslashes and a different drive-letter case resolves to the same file.
11. CRLF-only change (same text, different line endings): denied, because the bytes differ. Say so in
    the message, since that change is usually a tool, not a session.

Done: the tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, nothing is left
in the real state dir.

## Slice B: the fetch before the rewrite (only if Q3 is B)

`Sonnet 5` · effort `medium` · `AFK/Auto`. File: `plugins/cairn/skills/wrap/SKILL.md`, a short step
before step 7, as described in Q3 B. Skill text, so a payload change and the routine bump.

## Out of scope

- The id-allocation blind spot: B110 (refuse a spent id) and B87 (stale base). Hashes cannot see it.
- B33's rule text and live-session line (open groom PR #163).
- Any lock (the entry rules it out).
- `INBOX.md` (append-only, per the entry).
