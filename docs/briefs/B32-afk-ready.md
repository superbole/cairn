**Not AFK-ready: B32 needs the reviewer's decision (Q1 to Q4 below). The stage 1 slice at the end becomes AFK once Q1 and Q2 are answered.**

# B32 — a finding about another project goes to that project's `INBOX.md`: groom brief

Backlog: `BACKLOG.md` B32 (issue #30), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-07 against `origin/main` at `955e504`. Every file:line
below was read at that commit.

## The ask, as filed

A session working in project A finds something that belongs to project B. Today it can carry the
finding in chat (lost when the session ends) or edit B's files (the concurrent-rewrite hazard). The
entry's design: the foreign session **appends one bullet** to B's `INBOX.md`, never `NEXT.md` or
`BACKLOG.md`; B's next session surfaces it with no new mechanism. It names three builds:

1. `tools/inbox_post.py --project <name|path> --note "..."`: append atomically, commit with an
   explicit pathspec, push, one-line report, an `--issue` fallback when B is not cloned here.
2. A rule: `MISTAKES.md` is a pattern log, not a delivery mechanism; log it AND post it.
3. A wrap step that cross-references the repos a session touched against the posts it made.

It says it depends on B35 (every project has an `INBOX.md`) and B56 (issue-host writes verified).

## What exists today, with evidence

| Piece | Where | What it means for B32 |
|---|---|---|
| Inbox reader | `plugins/cairn/hooks/session_orientation.py:554-571` (`_inbox_items`) | Any line matching `fence_scan.BULLET_RE` (`fence_scan.py:58`, `^\s*[-*]\s+\S`) outside a fence is an item. The entry's bullet shape `- [from <project> · <machine> · YYYY-MM-DD] ...` already matches, so the receiving side needs **no code**. Shown at `session_orientation.py:1538-1548`, capped at `MAX_INBOX_ITEMS = 12` (`:161`). |
| Wrap empties the inbox | `plugins/cairn/skills/wrap/SKILL.md:412-414` (step 8) | A posted bullet is triaged like any other capture. No change needed. |
| No tool posts to another repo | Glob `plugins/cairn/tools/*inbox*`: no files | Build (1) is entirely new. |
| No rule names where a cross-repo finding goes | `plugins/cairn/rules/CLAUDE.md:158-161` says no project is tracked from a hub on another's behalf, and says nothing about where a finding for another repo goes | B99 (`BACKLOG.md`, AFK, on the scheduled firing's skip list) proposes exactly that rule: "a finding that belongs to another repo goes into THAT repo's `INBOX.md`". Build (2) overlaps it. |
| Precedent for INBOX as the seam | `docs/decisions.md` D20 (line 29: external pullers write `INBOX.md` bullets, "the integration costs zero code here") and D42 (line 50: a cross-repo finding was sent to the hub's `INBOX.md`) | The design is already practised by hand; B32 mechanises it. |
| Append-only is assumed safe | `BACKLOG.md` B34: "`INBOX.md` is append-only and does not race"; B33: "A foreign session may only append (B32 depends on this being a rule)" | B33's rule is still unwritten, so B32's safety rests on a rule that does not exist yet. |
| A foreign append was once committed under the wrong message | `plugins/cairn/hooks/staged_review_guard.py:4-10` | A scheduled task appended six bullets to an `INBOX.md`; the owner session committed them with `git add INBOX.md` under a message describing one line. A tool that commits in B's repo must not create the mirror image: committing the owner's uncommitted edits to `INBOX.md` under the foreign post's message. |
| Helpers a tool can reuse | `plugins/cairn/hooks/reentry_state.py:267` `toplevel()`, `:340` `git()`, `:379` `dirty_paths()` | Enough to resolve B's root, check its state and commit, without new git plumbing. |
| Machine name for the provenance | `plugins/cairn/hooks/machine_identity.py:91` `hostname()`, `:172` `_own_id()` | `_own_id` gives the `MACHINES.md` id when one is declared. The bullet should use that id, falling back to `hostname()` only when no table exists. |

`staged_review_guard.py` is a `PreToolUse` hook on the agent's own Bash calls. A Python tool that
runs `git commit` in a subprocess is **not** seen by it, so the tool has to enforce its own
"only my line" check.

## Questions for the reviewer

### Q1. What happens when B has no `INBOX.md`? (This is the B35 dependency.)

- **A. Create `INBOX.md` in B, but only if B has a `NEXT.md`.** B is in the system; an inbox is the
  one file it can safely gain. A repo without `NEXT.md` is outside the system and gets nothing
  (refuse, and say so), matching "a project without one gets total silence".
- **B. Refuse whenever `INBOX.md` is missing,** and tell the caller to use the issue fallback.
- **C. Wait for B35** (every tracked project gets the full file set) before building anything.

Recommendation: **A**. It removes the B35 dependency for the one file B32 needs, and keeps the
"no `NEXT.md` means not in the system" line. B35 is `HITL/Plan` and broader; waiting on it blocks
this for no gain.

### Q2. Commit and push in B from a foreign session: what are the refusals?

The entry says push at once, because an unpushed append is invisible on the other machine. The
risk is B's own session running at the same time.

- **A. Append, commit only `INBOX.md`, push; refuse first if any of these holds:** `INBOX.md` in B
  already has uncommitted changes (they are the owner's, and would be swept into this commit);
  anything is already staged in B; B's branch is behind its upstream after a fetch (never pull
  unasked); B is mid-merge or mid-rebase; B's checkout is not on its default branch (a bullet
  committed to a feature branch is invisible to B's next session on `main`). On a refusal, write nothing and print the bullet so the
  caller can carry it another way. After commit, check `git diff --name-only HEAD~1 HEAD` is
  exactly `INBOX.md` before pushing.
- **B. Append only; never commit.** B's owner commits it. Simple and race-free on one disk, but
  invisible on every other machine until then, which is the failure the entry names.
- **C. Commit, but never push.**

Recommendation: **A**. The refusals cover the `staged_review_guard.py` incident in reverse and the
"never pull unasked" rule, and a refused post still leaves the caller with the exact text.

### Q3. Where does the rule (build 2) live: B32 or B99?

- **A. B99 carries the rule** (`rules/CLAUDE.md`: a finding for another repo goes to that repo's
  `INBOX.md`, plus "`MISTAKES.md` is a pattern log, not a delivery mechanism"). B32 is only the tool
  and points at the rule.
- **B. B32 carries both** and B99 closes as a duplicate.

Recommendation: **A**. B99 is already a one-line rule change; folding it into a tool PR mixes an
always-loaded rule edit (which needs an `incidents.md` check) with new code.

### Q4. Are the `--issue` fallback and the wrap cross-check (build 3) in stage 1?

- **A. Neither.** Stage 1 is the local post only. The `--issue` fallback is stage 2, GitHub first
  (`issue_host.py` create is proven), GitLab after B56. The wrap cross-check is stage 3, once there
  is a post log to check against.
- **B. Include `--issue` for GitHub only.**

Recommendation: **A**. The fallback needs a project-name to remote mapping that does not exist
yet (B is by definition not cloned here), and B56 is unproven for GitLab writes.

## Stage 1 slice (if Q1 = A, Q2 = A, Q4 = A)

Fields line to paste under a new entry (or under B32 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: new `plugins/cairn/tools/inbox_post.py`, new `plugins/cairn/tools/test_inbox_post.py`.
Nothing else: no hook, no skill, no rule (the rule is B99's under Q3 = A).

Interface:

```
python plugins/cairn/tools/inbox_post.py --project <path> --note "<what> -- <why> -> <evidence>" [--dry-run]
```

- `--project` takes a path in stage 1. Resolving a bare name (`--project inflow`) needs a search
  root, which is B36's territory; leave it out.
- Resolve B with `toplevel()`. Refuse if it is the current session's own repo (that is an ordinary
  capture, not a foreign post).
- Bullet: `- [from <this repo's folder name> · <machine id> · <YYYY-MM-DD>] <note>`. The note is
  one line: refuse a newline in it.
- Append with a trailing newline, adding one first if the file does not end with one. Create the
  file only under Q1 = A's condition.
- Apply Q2 = A's refusals before writing anything. Commit with an explicit pathspec and a message
  naming the source repo, verify the commit touched only `INBOX.md`, push to the current branch's
  upstream with no flags. A push failure is reported in one line, and the commit stays (it is
  still the owner's to push).
- `--dry-run` prints the bullet, the target file and which refusals passed, and writes nothing.
- One line of output on success: `posted to <B>/INBOX.md (<short sha>), pushed`.

Tests (fixtures only: throwaway git repos with a bare-repo remote under a temp dir, a temp
`CLAUDE_CONFIG_DIR`):

1. B has `NEXT.md` and `INBOX.md`: the bullet is appended, committed alone, and pushed to the bare
   remote (read it back from the remote).
2. B has `NEXT.md`, no `INBOX.md`: the file is created with one bullet.
3. B has no `NEXT.md`: refused, nothing written.
4. B's `INBOX.md` has uncommitted edits: refused, the edits are untouched.
5. Something is staged in B: refused, the index is untouched.
6. B is behind its upstream: refused, no pull happened.
7. B is checked out on a branch other than its default: refused.
8. Push fails (remote removed): the commit stays, the output says it was not pushed, exit non-zero.
9. `--project` is the current repo: refused.
10. A note with a newline: refused.
11. `--dry-run`: nothing written, nothing committed.
12. The posted bullet is read back by `session_orientation._inbox_items()` as one item, so the two
    ends stay in agreement.

Done: the twelve tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, and
the test leaves nothing in the real state dir.

## Out of scope for stage 1

- The rule text (B99, Q3).
- `--issue` and the GitLab path (B56).
- The wrap cross-check (build 3).
- Name resolution for `--project` (B36).
- B33's broader concurrency rules; this slice only needs its own refusals.
