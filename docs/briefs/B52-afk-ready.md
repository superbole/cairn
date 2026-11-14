**Stage 1 (the guard and the two false comments) is AFK-ready as written below; the entry already decided it ("Land the guard first"), and Q1 only picks between the two shapes it names, with a recommendation. Stage 2 (actually counting Cursor hours) needs the reviewer's decision on Q2 and Q3 and is not AFK.**

# B52 — `timesheet.py` on a Cursor laptop reports the wrong machine's work: groom brief

Backlog: `BACKLOG.md` B52 (issue #50), `Sonnet 5` · effort `medium` · `HITL/Auto` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-14 against `origin/main` at `4a95fe8`. Every file:line
below was read at that commit. No Cursor transcript was opened by this firing; the Cursor file shape
is taken from the entry and from `docs/cursor-adapter-requirements.md:338-350`.

**Prior decisions:** none in `docs/decisions.md` (searched for `timesheet`: no match; the Cursor rows
D40 to D45, D55, D57 and D58 are about the adapter, hooks and shared-file writes, not hours). The
entry itself rejects a derived ledger beside `NEXT.md`, and `docs/cursor-adapter-requirements.md:372-373`
rejects the same ledger and "pretending the existing reader will start working". Respect both.

## The ask, as filed

Run from a Cursor shell, `timesheet.py` reads `~/.claude/projects/` and reports the few Claude Code
sessions there, which reads as the week's work on a laptop where most hours are spent in Cursor.
Cursor does write transcripts (`~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl`) in a
schema the reader cannot parse. Pick one of two backends later; **land the guard first** (refuse, or
loudly caveat, when a Cursor transcript tree exists and `~/.claude/projects/` is near-empty), and fix
the two comments that say Cursor writes no transcript.

Related: B53 (the weekly driver must not ship before B52 and B54), B54 (`timesheet_sync.py` copies
whole transcripts), B55 (billing codes), B66 (the OneDrive transport, already built).

## What exists today, with evidence

| Piece | Where | What it means for B52 |
|---|---|---|
| The only root read by default | `plugins/cairn/tools/timesheet.py:108-110` `projects_dir()`: `$CLAUDE_CONFIG_DIR/projects` or `~/.claude/projects`; `:538` `roots = [projects_dir()] + extra_roots` | Nothing looks under `~/.cursor`. A Cursor-only machine gets "No sessions with recorded time" (`:403-407`) or a small Claude-only total, with no hint that hours are missing. |
| A loud-note mechanism already exists | `timesheet.py:292-304` `source_notes()`; printed to stderr always (`:540-544`) and into the report header (`:420-423`) and the empty-report path (`:405-406`) | The guard does not need a new channel: it is one more line in `notes`. stderr keeps it visible under `--csv`, where stdout must stay machine-readable. |
| False comment 1 | `timesheet.py:73-74`: "Cursor writes no Claude Code transcript at all, so the work machines remain out of scope." | Literally true ("no *Claude Code* transcript") and still read as "writes nothing"; `docs/cursor-adapter-requirements.md:351-353` already calls it easy to misread. |
| False comment 2 | `timesheet.py:472`, printed at the foot of every report: "Claude Code on the directories read. Cursor writes no transcript." | This one is plainly false, and it is printed to the user, not just a comment. |
| A Cursor home override already exists | `plugins/cairn/hooks/cursor_drift.py:63-65` `cursor_home()`: `$CAIRN_CURSOR_HOME`, else `~/.cursor` | Reuse the same variable so tests and odd installs set one name. `timesheet.py` imports nothing from `hooks/` today (`:93-101`), so copy the three lines rather than adding a cross-folder import. |
| Tests | `plugins/cairn/tools/test_timesheet.py`: a script with `check()`, `CLAUDE_CONFIG_DIR` pointed at a temp dir before import (`:18-19`) | Stage 1's tests go here, same style. |
| Docs that repeat the claim | `docs/design-notes.md:194-198` (already corrected: "it does write its own"); `docs/cursor-adapter-requirements.md:331-373` (the two build options, in more detail than the entry); `plugins/cairn/skills/next/references/incidents.md:512-513` (kept as calibration, correct as is) | Only `timesheet.py` still states the false version. |

## Q1. Refuse or caveat? (stage 1; has a recommendation, does not block it)

- **A. Caveat, never refuse.** One line in `notes` whenever any Cursor transcript was modified on or
  after the window's start, whatever the Claude Code total. Exit code unchanged.
- **B. Refuse** (non-zero exit) when Cursor transcripts exist and `~/.claude/projects/` is
  near-empty. Needs a threshold for "near-empty", and a machine that uses both harnesses would still
  get a confident, partial total with no warning.
- **C. Caveat only when `~/.claude/projects/` is near-empty** (the entry's literal condition).

Recommendation: **A**. It needs no threshold to tune, it also covers the machine that runs both
harnesses (where the Claude total is real but incomplete), and a refusal would break `--csv`
pipelines and B53's future driver for no gain: the line says exactly what is missing. This is a
judgement made on the reviewer's behalf; flip to C by adding the near-empty test if preferred.

## Stage 1: the guard and the comments (AFK)

Fields line to paste under B52 once this brief is accepted (or under a new entry for stage 1):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: `plugins/cairn/tools/timesheet.py`, `plugins/cairn/tools/test_timesheet.py`. A payload change,
so it gets the routine version bump at the attended pass.

1. In `timesheet.py`, add `cursor_home()` (same body as `cursor_drift.py:63-65`, with a comment
   pointing there) and `cursor_notes(since: date) -> list[str]`:
   - Look under `cursor_home() / "projects" / * / "agent-transcripts"` and count `*.jsonl` files
     found **recursively** (`rglob`) whose mtime, as a local date, is on or after `since`. Recursive,
     because the documented depth (`<uuid>/<uuid>.jsonl`) was observed once and is not an API.
   - No `projects` directory, or a count of 0: return `[]` (silence, as for every opt-in).
   - Otherwise one line, in the existing `  ! ` style:
     `  ! Cursor: <n> conversation(s) under <cursor home>/projects active since <since> -- NOT counted here; this report reads Claude Code transcripts only (B52).`
   - Count by mtime **on or after** `since`, with no upper bound: a transcript last written after the
     window (a conversation continued this week, seen from `--last-week`) still had activity that may
     fall inside it. Over-warning is the safe side; say "active since", never "in this window".
   - Never read file contents. Never raise: an `OSError` on one file skips that file.
2. In `main()`, change `:542` to `notes = source_notes(extra_roots) + cursor_notes(since)`, BEFORE
   the stderr loop at `:543-544`, so the line reaches stderr and the report header exactly as the
   synced-copy notes do, including the empty-report path (`:403-407`).
3. Comment 1 (`:73-74`): "Cursor writes its own transcripts, in a schema this reader cannot parse
   (B52), so Cursor hours are not counted; `cursor_notes()` says so whenever they exist."
4. Comment 2 (`:472`): replace the printed sentence with "Claude Code transcripts only; Cursor hours
   are not counted (B52)."

Tests, in `test_timesheet.py`, fixtures only (set `CAIRN_CURSOR_HOME` to a temp dir; never the real
`~/.cursor` or `~/.claude`):

1. No Cursor home at all: `cursor_notes()` is `[]`.
2. A Cursor `projects` dir with no `.jsonl` anywhere: `[]`.
3. Two transcripts at the documented depth, one modified today and one 30 days ago, `since` = 7 days
   ago: one line, count 1, and it contains `NOT counted`.
4. A transcript modified after `until` of a past window (`since` = 14 days ago, file modified today):
   counted.
5. A transcript at a different depth (`agent-transcripts/<uuid>.jsonl`): counted.
6. A non-`.jsonl` file and a `.jsonl` outside `agent-transcripts`: not counted.
7. `main()` with `sys.argv` set to `--days 7` and the stdout/stderr captured
   (`contextlib.redirect_stdout`/`redirect_stderr`, already imported at `test_timesheet.py:104-105`):
   the Cursor line is on stderr and in the stdout report.
8. The same with `--csv`: the Cursor line is on stderr and **not** on stdout (the CSV stays parseable).
9. The source of `timesheet.py` no longer contains `Cursor writes no` (comment 1 wraps across a line
   break after those words, so pin the shorter phrase to catch both).

Done: those tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, and nothing
is left in the real state dir.

## Q2. Stage 2: which way are Cursor hours counted?

The entry says pick one. Both options are written up in more detail at
`docs/cursor-adapter-requirements.md:359-370`.

- **A. A Cursor backend in the reader.** Parse `role` and take the clock from the
  `<timestamp>...</timestamp>` tag the entry says user turns carry in their text. Assistant turns
  carry no clock, so every agent-terminated gap has no length: either count user-to-user gaps under
  the existing `--idle` cap only (attended time, an undercount of long agent runs, labelled), or fall
  back to file mtime for the last turn only. Keeps per-project overlap attribution. Breaks when the
  prompt-text clock changes, and it is not an API.
- **B. A `sessionEnd` hook** in `plugins/cairn/cursor/hooks.json` appending
  `{session_id, cwd, duration_ms, reason}` to a gitignored jsonl, summed by a thin reporter. Survives a
  schema change; loses overlap attribution; and **unmeasured**: whether `duration_ms` runs from the
  first prompt or from when the chat was opened, so a chat left open overnight may count as one long
  session, which is the failure the `--max-run` cap exists to stop (`timesheet.py:58-64`).
- **C. Neither yet: stage 1's line is enough** until B53 needs a number.

Recommendation: **C until B53 is scheduled, then A**, attended-time-only, with agent time printed as
`unverified`. A is the only option that keeps the overlap figure, which this tool prints in every mode
because it is what reveals two clients billed for one hour (`timesheet.py:44-45`). B's overnight risk
needs one real measurement before it can be weighed. Not decided here: it produces a billed number,
which the entry and B53 both treat as the reviewer's call.

## Q3. Stage 2: how does a Cursor slug become a project?

`~/.cursor/projects/<slug>` names the folder, but the entry says Cursor transcripts carry no `cwd`.
Unverified by this firing how the slug encodes the path. Options: decode the slug if it is a
reversible path encoding (measure on one machine first); or map slugs to projects through the existing
`PROJECT_ALIASES` (`timesheet.py:122`). The answer decides whether a Cursor row and a Claude Code row
for the same repo land under one `project_key()`.

Recommendation: measure one slug on a Cursor machine before choosing; this needs a person at that
machine, so it cannot be done unattended.

## Out of scope

- B53 (the weekly driver), B54 (sync digests), B55 (billing codes).
- Changing how Claude Code sessions are counted.

## Side note for the attended pass

`docs/design-notes.md:194-198` (a public-set file) describes the Cursor gap correctly but will be
one step behind once stage 1 lands: add "and `timesheet.py` says so in every report when Cursor
transcripts exist" to its last sentence in the same PR as stage 1.
