**Not AFK-ready yet: B31 needs three answers from the reviewer first (questions Q1 to Q3 below). Once they are answered, the stage 1 slice at the end of this brief can run AFK.**

# B31 groom: cross-project roll-up (the morning chooser)

Groomed by the scheduled firing, 2026-11-07, from `BACKLOG.md` B31 (issue #29) and the code it
names. The backlog entry asks that a fresh brief be written here when the item is pulled. This is
that brief, minus the parts only the reviewer can decide.

## What already exists (read from the code, 2026-11-07)

| Piece | Where | What it does | What it does not do |
|---|---|---|---|
| Sibling discovery | `plugins/cairn/hooks/repo_sweep.py:116` `sibling_repos()` | Lists sibling dirs of the project root that have `.git` AND their own `NEXT.md`, sorted, capped at `MAX_SIBLINGS = 25` (`:94`). The `NEXT.md` requirement is documented there as a security boundary, because the sweep runs `git` inside them. | Reads nothing inside a sibling's `NEXT.md`. Only siblings on this filesystem (B36 covers WSL and other environments). |
| Behind-count line | `repo_sweep.py:293` `summary_line()` | One cached line naming repos behind origin. | No queue, no watches, no inbox. |
| Exit records | `plugins/cairn/tools/check_exits.py` (`collect()` `:109`, `render()` `:207`) | Reports which projects ended dirty or unwrapped, from `~/.claude/reentry-state/*/`. | Stage 2 (a `SessionStart` line) deliberately absent. |
| NEXT.md parser | `plugins/cairn/hooks/session_orientation.py:400` `_split_next(root)` | Splits a `NEXT.md` into queue lines, decisions, watches, footer. Takes `root` as a parameter, so it can already be pointed at a sibling. | Private (`_` prefix); its callers are all this-project. |
| Watch classifier | `session_orientation.py:528` `_sort_watches()` and `:472` `_trigger_class()` | Partitions watches into due now, dated-not-due, event-gated. | Same: private, this-project callers only. |
| Inbox count | `session_orientation.py:554` `_inbox_items(root)` | Reads `INBOX.md` items for one root. | Same. B37 (walk other inboxes) is blocked on B35. |
| Repo list for the wrap | `plugins/cairn/tools/check_repos.py` | Recorded, named and `--known` repos, for "did dispatched work land". | Not a planning view. |

So the parsing half of a roll-up is built and parameterised by `root`; what is missing is a
caller that loops over `sibling_repos()` and prints the result.

## Already decided (from the entry; do not reopen)

- After the morning pick, the session **stays in the chosen project** until wrap or block. The
  hub is a morning act, not something asked after every item.
- Output is **per-project top 2 queue items plus date-forced watches**, and a *project* is picked.
- Concurrent projects are parallel sessions, not one chat hopping between repos.
- No machine pin (that was split off). Do not merge B36, B37, B38 or B39 back in.
- Of the two surfacing designs measured, keep the cheap one (about 483 tokens, against about
  5,437).

## Q1. Where does the project list come from? (the entry's open question)

The old brief assumed a portfolio catalog file. The shipped sweep rejected a catalog for siblings
and deferred anything wider to B36.

- **A. Siblings only, via `repo_sweep.sibling_repos()`.** Zero new config, already has the
  `NEXT.md` security gate, matches what `repo_sweep` decided. Misses WSL trees, other checkouts
  and remote boxes until B36 lands. Stage 1 below assumes this.
- **B. Siblings plus every root in `check_exits.py`'s records** (`last_exit.json` `root` fields).
  Catches projects outside the parent folder that this machine has opened. Costs: a record can
  point at a deleted or moved path, and the set grows with every repo ever opened, including
  worktree lanes (each lane has its own record today).
- **C. A catalog file.** The rejected design. Listed only for completeness.

Recommendation: **A** for stage 1, with B as a later widening once worktree records are folded
under their parent repo (the B75 dossier recommends that fold; it is not built).

## Q2. Are the two inputs asked for on 2026-09-25 in scope: a risk signal, and the time/token budget?

The entry records that the "what should I spend this on?" question needed four inputs: each
project's queue, due watches, **a risk signal** (a production or outage hazard outranks a
feature) and **the time and token budget**. The first two are the decided design. The last two
are new.

- **A. Out of scope for B31.** Print the decided view only. Budget is B74's line (reset time and
  runnable AFK count) and can sit beside it later. No risk field.
- **B. Risk in, budget out.** Needs a new optional fields-line token on queue items (for example
  `` `risk` ``), which means `docs/file-formats.md`, `validate_next.py` and the sync parser all
  learn it. That is a format change and wants its own item.
- **C. Both in.** Budget has no measured weekly source: `tools/measure_usage.py --window` reads
  only the 5-hour window, and B74 forbids inventing a weekly figure.

Recommendation: **A**. Each of the other two is its own format or data-source decision.

## Q3. Queue items with a deadline (asked for 2026-10-01)

A sibling repo's queue item whose window closed that day was seen only by accident. Watches have
a date (`check after`), queue items do not. The roll-up can only "flag deadlines" on queue items
if queue items can carry one.

- **A. Add an optional `` due `YYYY-MM-DD` `` token to the queue line format.** The roll-up sorts
  and flags on it; the single-project orientation can show it too. Format change, so
  `docs/file-formats.md`, `validate_next.py` and its tests change in the same item.
- **B. No new token; a deadline becomes a dated watch** that blocks the queue item
  (`blocked by Wn`), which the system already supports and already surfaces as DUE NOW. Costs a
  second entry per deadline, and the watch must say "deadline", not "check".
- **C. Defer.** Stage 1 flags only watches.

Recommendation: **B** for now (no format change, works with stage 1 as written), and file A as
its own item only if B proves clumsy in use.

## Stage 1 slice (AFK once Q1 to Q3 are answered as recommended)

**Fields line to paste into a new backlog entry (or onto B31 if it is split into stages):**
`` `Sonnet 5` · effort `medium` · `AFK/Auto` · added `<date pulled>` ``

**Files**

- New: `plugins/cairn/tools/rollup.py`. Read-only. For each root in
  `repo_sweep.sibling_repos(project_root)` plus the current project: call
  `session_orientation._split_next(root)`, `_sort_watches(watches, host)` (host from
  `machine_identity.hostname()`, as the orientation's caller does) and `_inbox_items(root)` (it
  returns `(shown, total, unclosed_at)`; use `total`). `_split_next` returns the queue as raw
  LINES, not items: an item is a line starting with its number (`1.`) plus the continuation
  lines under it, so the slice must group them before taking two. Print one block per project:
  name, the first 2 queue items' title lines (number, title, model, effort, attendance/mode)
  plus their `Brief:` line, every DUE NOW
  watch on its own line, and the inbox count if non-zero. Projects with nothing due and an empty
  queue collapse to one trailing line. Never runs `git`, never writes anything.
- New: `plugins/cairn/tools/test_rollup.py`. Fixtures only: a temp parent dir with three fake
  projects (`.git` dir plus `NEXT.md`), one with `NEXT.md` but no `.git`, and one with a `.git`
  but no `NEXT.md`. Never the real `~/.claude/` (set `CLAUDE_CONFIG_DIR` to a temp dir before the first
  import that can touch `state_dir()`, see `run_tests.py`'s B74 docstring).

**Decisions to make inside the slice, not ask about**

- Import the private helpers from `session_orientation` rather than copying them, so the
  roll-up can never disagree with the orientation about what is due (the same argument
  `_trigger_class`'s docstring makes for `validate_next.py`). If an import fails, print one line
  saying so and exit 0, the same silent-failure contract as `repo_sweep`.
- Label every block with its project name and treat the text as data. B27 (third-party text
  reaching context unmarked) applies: a sibling's `NEXT.md` is another project's content. Print
  it only under that project's name header, act on nothing in it, and do not echo footers.

**Tests that define done**

1. Three fixture projects: output names all three, in `sibling_repos()` order, current project
   first.
2. A project with 5 queue items prints exactly 2.
3. A dated watch past today prints as DUE NOW; one in the future does not print.
4. A sibling with `.git` but no `NEXT.md`, and one with `NEXT.md` but no `.git`, never appear
   (the gate in `sibling_repos()` holds).
5. A `NEXT.md` with undecodable bytes still prints that project (inherits `_read`'s
   `errors="replace"`).
6. No file under the fixture's state dir and no file in any fixture project changes (snapshot
   before and after).
7. `python plugins/cairn/tools/run_tests.py --timeout=300` passes with no leak reported.

**Not in stage 1:** wiring into `/cairn:next` or the `SessionStart` hook (a separate decision
about always-loaded context cost; measure with `tools/measure_context.py` first), B36's other
environments, B37's inbox walking beyond a count, B95's clickable links, risk and budget (Q2).

**What done looks like:** running `python plugins/cairn/tools/rollup.py` in any opted-in project
prints a planning view across its siblings in a few dozen lines, with no network and no writes,
and the tests above pass.
