**Q1 answered 2026-11-08 (D59): A.** Report by default, create on `--create`, at two moments only: with a new `NEXT.md`, and at a wrap after one ask. **Q2 answered 2026-11-08 (D60): A.** Look for the known rationale names and create `docs/decisions.md` only when none exists. The search stays on those names. **Q3 answered 2026-11-08 (D61): A.** Create `BACKLOG.md` with the set, and the same question says the next sync will import the open issues. **Q4 answered 2026-11-08 (D62): A.** B32 and B37 wait until stage 1 has landed and the member repos are backfilled. Q1 to Q4 are answered. Stage 1 can be built from this brief. Stage 2 (the rule and README text) stays attended, because it edits shared files.

# B35 — every tracked project gets the full file set, blank if need be: groom brief

Backlog: `BACKLOG.md` B35 (issue #33), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-08 against `origin/main` at `82c19bd`. Every file:line
below was read at that commit.

Two open groom briefs depend on this one: B32's Q1 (open PR #162: what a cross-project post does
when the target has no `INBOX.md`) and B37 (blocked on B35 in its own entry).

## The ask, as filed

Only `NEXT.md` is guaranteed in a member project; `INBOX.md`, `BACKLOG.md`, `CHANGELOG.md` and the
rationale record appear lazily. Absence then means two things: a missing `NEXT.md` means *not in
the system* (correct), a missing `INBOX.md` in a member means *nobody wrote one yet*. The set:
`NEXT.md`, `INBOX.md`, `BACKLOG.md`, `CHANGELOG.md`, the rationale record, header only. **Blank
means blank** (B15: example bullets in a legacy inbox were counted as four phantom items). Opt-in
does not change.

Two enforcement questions were left open: (1) a new project appears, and (2) a fresh install on an
existing tree. Build: `tools/ensure_project_files.py`, idempotent, same shape as
`ensure_mistakes_file.py`, run only where `NEXT.md` exists; document the set in `rules/CLAUDE.md`
and `README.md`. A multi-repo bootstrap: one repo at a time, explicit pathspecs, report each.

## What exists today, with evidence

| Piece | Where | What it means for B35 |
|---|---|---|
| The idempotent create-if-absent pattern | `plugins/cairn/hooks/ensure_mistakes_file.py:19-24` (design rules), `:57-67` `ensure()`: exists means do nothing; else write the header, return one report line; never raise | The shape to copy. But it writes under `~/.claude`, not inside a git working tree, so it never dirties anything. A project file does (see the first finding). |
| Who calls it | `session_orientation.py:982` (`ensure_mistakes_file.ensure()` at every session start) | A session-start call is fine for a file outside any repo. The same call for project files would be a hook writing into every member repo. |
| How `NEXT.md` gets created | `plugins/cairn/rules/CLAUDE.md:169-181`: offer once at a natural stop, "never create the file unasked", and if yes, write `NEXT.md` | The one moment a human has just said yes to joining. B35's "whoever writes `NEXT.md` writes all five" would hang off this paragraph. |
| How `BACKLOG.md` gets created today | `skills/wrap/SKILL.md:478-481`: "No `BACKLOG.md` in this project yet? Create it ... write an empty one (`sh "<root>/hooks/run.sh" backlog_file.py` documents the shape) and run `sync_backlog.py --pull`" | **Doc drift:** `backlog_file.py`'s `__main__` (`:703-711`) prints `summary_lines()`, which returns `[]` for a missing file (`:582-583`). So that command prints nothing in exactly the project the step is about. The real blank shape is `render([], project)` (`:611-637`): the H1, a `<!-- next-id: 0 -->` marker and a fixed paragraph. |
| Missing `INBOX.md` | `session_orientation.py:554-571` `_inbox_items` reads it via `_read` (empty for a missing file); `wrap_receipt.py:766-768` reports `inbox` as `n/a` "no INBOX.md in this project" | Both already cope with absence. A blank `INBOX.md` changes the receipt's step from `n/a` to a measured state, which is the point. |
| Missing `CHANGELOG.md` | `backlog_file.py:263-283` `_changelog_unreadable_reason`: `"missing"` when there is no readable file, `"unparseable"` when the file reads but has no dated heading (`_CHANGELOG_DATE_RE`, `:257`) | **A header-only `CHANGELOG.md` turns "missing" into "unparseable"**, which `:265-269` says names the wrong problem ("a real file in an unrecognised heading shape", B83). See the second finding. `changelog_status()` itself stays `no-changelog` either way (`:313`), so closing items is unaffected. |
| Missing `BACKLOG.md` | `sync_backlog.py:711-713` skips the sync with one line; `backlog_file.summary_lines` is silent (`:582-583`) | A blank `BACKLOG.md` arms the sync. On a repo with an issue host, the next wrap's sync appends every open issue not in the file as an `inbound` item (`sync_backlog.py:19`). It never closes or deletes anything (`:31-32`). See Q3. |
| The rationale record has no fixed name | `rules/CLAUDE.md` ("`docs/decisions.md`, or whatever the project already calls it (this plugin keeps two, as `skills/*/references/incidents.md`)") | A tool cannot know the name. Creating `docs/decisions.md` in a project that already keeps its reasons elsewhere makes two records. See Q2. |

### Finding 1: creating files is a write into someone's working tree

Every created file is untracked until committed. At the next `Stop`, `dirty_tree_warning.py`
reports uncommitted changes, and the wrap's step 1 has to sort them. So any path that creates the
set silently (a `SessionStart` hook, a tool run from the orientation) makes every member repo dirty
on the next session, in a session that may be about something else entirely. That rules out the
`ensure_mistakes_file.py` call site, even though its shape is right. Creation has to happen where a
commit is about to happen anyway, or where the human has just asked.

### Finding 2: "blank" is not neutral for `CHANGELOG.md`

`_changelog_unreadable_reason()` (`backlog_file.py:260-283`) tells "no file" from "a file whose
headings this parser cannot read", and the second is the message for a malformed changelog. A
header-only changelog is neither. Without a change there, every project the tool backfills reports
its changelog as `unparseable` until its first dated entry. Stage 1 should add a third reason,
`"empty"` (the file reads, and has no `##`-to-`####` heading at all), and the sync's message for it
(`sync_backlog.py:370-375`, which today prints the B83 "HAS a CHANGELOG.md, but no heading in it
matches" line for `"unparseable"`) should say there are no entries yet. That touches
`backlog_file.py`, which no open afk/ PR touches today.

### Finding 3: a blank `CHANGELOG.md` created in a wrap would pass the receipt's changelog step

The receipt's changelog step (`wrap_receipt.py:729-732`) is `tracked_step`, which calls
`_changed_by_session` (`:565-583`). For a file absent at session start, `_changed` (`:460-476`)
returns True as soon as the file exists, and a new untracked file is in this tree's dirty set, so
the step reads `ran`: "CHANGELOG.md written here this session". Under Q1 A (ii), the wrap that
creates the blank set would therefore tick the **required** changelog step with no entry in it.
Stage 1 must close that: when `_changelog_unreadable_reason()` says `"empty"`, the changelog step
is not `ran`, whatever the hash says.

## Questions for the reviewer

### Q1. When are the files created? (the entry's question 1 and 2)

- **A. Report by default, create on `--create`, and call it at two moments only.** (i) Right after
  a session writes a new `NEXT.md` (the rules paragraph at `rules/CLAUDE.md:179-181` gains "then
  run `ensure_project_files.py --create` and commit all of them together"). (ii) In `/cairn:wrap`,
  as a report line: "this project is missing `INBOX.md`, `CHANGELOG.md`: create them in this
  wrap's commit?" asked once, like the archive offer, and the answer stays with the human. A fresh
  install on an existing tree is then backfilled one repo at a time, at that repo's next wrap.
- **B. Create at `SessionStart` in any project with `NEXT.md`.** Fully automatic, but it is a hook
  writing into every member repo, which dirties trees (finding 1) and breaks "never create the
  file unasked".
- **C. Create in the wrap without asking.** Lands in a commit, so no dirty tree. But a work repo's
  wrap would add files its colleagues did not expect, with no human choice.

Recommendation: **A**. It keeps every write next to a commit and a human, and needs no new hook.

### Q2. The rationale record

- **A. Recognise known names, create only if none is found.** Look for `docs/decisions.md`,
  `DECISIONS.md`, `docs/adr/` (any file in it), `docs/decisions/` and `**/references/incidents.md`.
  If one exists, report it as the record and create nothing. If none, create `docs/decisions.md`
  with a header and an empty table (`| D | Decision | Rejected option and its cost |`).
- **B. Leave the rationale record out of the tool.** Report "no rationale record found" and let
  the human create it. The set is then four files, not five.
- **C. A declaration** (a line in `NEXT.md` or `MACHINES.md` naming the file). Exact, but one more
  thing to set.

Recommendation: **A**, with the list of known names in the tool's docstring so a new name is a
one-line change.

### Q3. A blank `BACKLOG.md` in a repo with an issue host

Creating it arms the sync: the next wrap pulls every open issue into it as `inbound`. That is the
documented seeding route (`skills/wrap/SKILL.md:478-481`), but on a repo whose issues were never
meant as this person's backlog (a shared work repo, say) it imports someone else's list.

- **A. Create it, and say so in the report line:** "the next wrap's sync will import N open issues
  as inbound items". The count comes from the session-start issues cache if it exists, otherwise the
  line says "any open issues".
- **B. Do not create `BACKLOG.md` when the repo has an issue host**; report it as missing and point
  at `sync_backlog.py --pull --dry-run`.
- **C. Create it with no warning.**

Recommendation: **A**. It keeps the set uniform, which is the entry's point, and the import is
already the intended route; it just stops being a surprise. The tool reads no network.

### Q4. Does B35 also unblock B32 and B37 as written?

B32's groom brief (open PR #162) recommends that a cross-project post creates `INBOX.md` in the
target only if the target has `NEXT.md`, which removes its dependency on B35 for the inbox alone.
B37 (walk other projects' inboxes, not built yet) is read-only by its entry, so it could treat a
missing inbox as zero items, the way `_inbox_items()` already does for this project
(`session_orientation.py:382-385` returns no lines for a missing file).

- **A. Yes for both, once stage 1 lands and members are backfilled.** Note under B37: "unblocked
  by B35 stage 1; a missing `INBOX.md` in a member now means the member was never backfilled".
- **B. Neither waits on B35 any more** (B32's own rule covers its case; B37 can treat absence as
  zero today).

Recommendation: **B** for B37 (read-only, so absence can read as zero), **A** for the
wording in B32 if its Q1 is answered differently from its recommendation.

## Stage 1 slice: the report-first tool (if Q1 = A, and Q2, Q3 answered)

Fields line to paste under a new entry (or under B35 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: new `plugins/cairn/tools/ensure_project_files.py`, new
`plugins/cairn/tools/test_ensure_project_files.py`, `plugins/cairn/hooks/backlog_file.py` (the
`"empty"` reason from finding 2, and the sync's message for it in `plugins/cairn/tools/sync_backlog.py`),
`plugins/cairn/hooks/wrap_receipt.py` (finding 3: an `"empty"` changelog never counts as the step;
its test goes in `plugins/cairn/tools/test_wrap_receipt.py`),
and `plugins/cairn/skills/wrap/SKILL.md` (fix the `backlog_file.py documents the shape` line at
`:480` to name the new tool, and add the Q1 A (ii) report line). A payload change: routine version
bump at the attended pass.

- `ensure_project_files.py [--root PATH] [--create]`. Root resolution: `--root`, else the git
  toplevel of the current directory. **Not** the session's stamped project (B9's lesson).
- Refuses, exit 0 with one line, when the root has no `NEXT.md`: opt-in stays with `NEXT.md`.
- Default: print one line per file, `present`, `missing`, or (rationale record) `found as <path>`.
  Exit 0. Writes nothing.
- `--create`: write each missing file, never touch an existing one (an existing empty file is
  present). Print one line per created path, and finish with the exact `git add <paths>` line for
  the caller to run, never running git itself.
- Blank contents. `INBOX.md`: an H1 and one prose sentence, **no bullet and no fenced bullet**
  (B15). `BACKLOG.md`: `backlog_file.render([], <root name>)`, never a hand-written copy.
  `CHANGELOG.md`: an H1 and one prose sentence, **no dated heading**. Rationale record: per Q2.
- Line endings `\n`, UTF-8, no BOM, same as `ensure_mistakes_file.py:64`.

Tests (fixtures only: temp directories, throwaway git repos where git matters, never the real
`~/.claude/`):

1. No `NEXT.md`: refuses, creates nothing, even with `--create`.
2. `NEXT.md` only, no `--create`: four `missing` lines, nothing written.
3. `NEXT.md` only, `--create`: the four files exist; a second run creates nothing and prints all
   `present`.
4. An existing `INBOX.md` with content is byte-identical after `--create`.
5. The created `INBOX.md` gives `_inbox_items()` zero items and no unclosed fence.
6. The created `BACKLOG.md` parses with `backlog_file.parse()` to no items, `summary_lines()` is
   silent, and `unparsed_headings()` is empty (so a sync is not refused).
7. The created `CHANGELOG.md`: `_changelog_unreadable_reason()` returns `"empty"`, not
   `"unparseable"`; a file with a real non-date heading still returns `"unparseable"`; a missing
   file still returns `"missing"`.
8. Rationale record: with `docs/adr/0001-x.md` present, nothing is created and the line names it;
   with none present, `docs/decisions.md` is created (or per Q2's answer).
9. The final `git add` line names exactly the created paths, relative, forward slashes.
10. A root inside a subdirectory of a repo resolves to the toplevel.
11. A read-only directory: reports the failure for that file, carries on with the others, exit 0.
12. Receipt (in `test_wrap_receipt.py`, fixtures only): a baseline with no `CHANGELOG.md`, then the
    tool's blank `CHANGELOG.md` created: the `changelog` step is not `ran`. The same, then a dated
    entry added: the step is `ran`.

Done: the tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, and nothing is
left in the real state dir.

## Stage 2: the rule and README text (attended)

`rules/CLAUDE.md` (the plugin source, never the installed copy): after `:179-181`, one sentence
saying a new member gets the full set and how. `README.md`: the set, in the opt-in section. Both are
shared or payload files, so this is the attended pass's. Before editing the rules file, read
`skills/wrap/references/incidents.md` and `skills/next/references/incidents.md` as its header
requires, and measure with `tools/measure_context.py` before and after.

## Out of scope

- The multi-repo backfill itself. Under Q1 A it happens one repo at a time, at each repo's wrap.
- B36 (the cross-environment sweep) and B37 (the inbox walk).
- Any hook that writes project files.

## Side note for the attended pass

Code comments cite "B35" for an unrelated subject: `hooks/archive_offer.py:34` ("B35 — NONE COVERS
TWO OPPOSITE STATES") and `tools/test_archive_offer.py:10` are about the archive offer's `pending()`
state, which is not this entry. They predate the 2026-09-23 migration, when this entry was
renumbered from `agent-reentry` B57, so those comments use the old repo's numbering. A reader
following "B35" from that code lands here. Not changed by this brief.
