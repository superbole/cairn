# BACKLOG — cairn
<!-- next-id: 103 -->

Everything worth doing that is NOT in `NEXT.md`'s Queue. Unbounded and unordered —
the ordering that matters lives in the Queue, which is capped at 5 and refilled from here.

Items marked `queued` are on the Queue right now and stay listed here until the work lands.
Where the repo has GitHub Issues, `tools/sync_backlog.py` mirrors this file to them; the
file is the writer and Issues is the copy that survives a lost machine.

## B11. A baseline keyed only by session id does not survive a crash-and-resume
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-06` · issue `#9`
Was `agent-reentry` B106 (migrated 2026-09-23). **Half of it shipped:** v1.57.0's `CAIRN UNKNOWN` is
the "distinct token for blindness" this item asked for. The fix that remains is (2) below.

**Found live 2026-09-06.** Every wrap step ran and pushed; `--record` printed `CAIRN OPEN` three
times with `next_rewrite`, `changelog` and `commit` all reading *"no session baseline"*.
`wrap_receipt.baseline()` reads `wrap_baseline/<session_id>.json`; `session_id()` reads
`CLAUDE_CODE_SESSION_ID` first and resolved to an id for which **no file was ever stamped**. The
directory held 13 files, three created *during* the wrap under other ids, all carrying the correct
session-start head. **Reproducer (from the operator):** the session errored mid-run, was retried
several times, then Claude was closed and reopened — each attempt stamped its own baseline, and the
survivor came up with an id none of them wrote. **The failure is correlated with the need**: a
crashed-and-resumed session is exactly the one whose wrap most needs a trustworthy verdict.

**The remaining fix — survive a resume.** Candidates: key the baseline by project + wall-clock
window rather than id; or, finding none for this id, adopt the most recent one **whose head is an
ancestor of HEAD** and say in the table that it was inherited. **Never adopt silently** — a marker
shared across sessions has been reverted once already as worse than none.

**Unexplained anomaly to start from:** ~25 minutes earlier, `--check` from the *same shell* found a
baseline. Later `session_id()` resolved to an id with no file. `_prune()` only deletes past 7 days,
and `stamp_baseline()` writes only under its own id — so either `CLAUDE_CODE_SESSION_ID` changed
value inside one shell, or something stamped under ids that shell never reported. Not chased.
**Cannot be done:** stamping a baseline late — it hashes current files as "session start" and turns
an honest "cannot tell" into a false `skipped` or a false `NOT DUE`.
**Related:** B10, B6 (`/clear` gives a new id and no stamp — the same mechanism, a different trigger).

## B12. `sync_backlog.py` silently DROPS a fields-line token it cannot parse, and reports success
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-09` · issue `#10`
Was `agent-reentry` B141 (migrated 2026-09-23). **Caused real data loss, invisibly.** Four new items
were written with ASCII hyphens as field separators instead of the middot `·` the parser splits on.
The sync rewrote the file, could not see `AFK/Auto`/`HITL/Auto` as a field, and emitted a canonical
fields line **without it** — then printed `8 change(s)` and exited 0.

Before: `` `Sonnet 5` - effort `medium` - `AFK/Auto` - added `2026-09-09` ``
After:  `` `Sonnet 5` · effort `medium` · added `2026-09-09` · issue `#131` ``

Attendance/mode is required on every item; an item without it reads as unclassified and the next
wrap cannot know a value was ever there. **The tool already has the right pattern and does not apply
it here:** an unparseable item HEADING gets `backlog sync REFUSED`, no host call, nothing touched
(added after 13 headings / 206 lines came one write from being lost in another repo, 2026-09-03). A
fields line gets best-effort parse and silent normalisation.
**Fix: normalise on READ, refuse on LOSS.** Accept `-`, `—` and `·` when parsing; before writing,
compare tokens to be emitted against tokens read, and if a recognised field would disappear, refuse
and name the item. A rewrite that loses a field must never be reported as a change count.

## B13. `sync_backlog.py` filed an issue without writing its number back, then re-imported it as a phantom
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-09` · issue `#11`
Was `agent-reentry` B136 (migrated 2026-09-23). **Found live, and it corrupted the file it synced.**
(1) An item with no `issue` field was synced: `· filed #129`. (2) **The number never reached the
file** — a later exact-match `Edit` of the fields line would have failed had `· issue #129` been
appended. (3) The work was done and the item marked `closed`. (4) The next sync printed `· dropped
(closed, never synced)` — **dropping the row without closing #129**. (5) In the same run it saw an
open issue absent from the file and `· pulled #129 into` a new id — re-importing the item's own issue
as new work, with the pre-fix body and a mangled fields line.
**Net: an OPEN issue for shipped work, the closure record deleted, and a phantom live item.** Every
printed line was accurate about what it did; none revealed that file and host had diverged.

**Conditional, and that is measured:** in the repair run the next item's number *did* land on disk.
The run that lost it did nothing but file (no close, no pull); runs where it survived also rewrote
the file for another reason. **Suspect a file-only path that skips the write, or a writeback
overwritten by a later `render()`.** Reproduce with a fixture: fresh item, one sync whose only action
is a file, assert the `issue` field is on disk.
**The `closed, never synced` branch needs its own fix regardless:** "never filed" and "filed, number
lost" have identical file signatures and the drop is only safe for the first. Match by title against
open issues before dropping, or refuse and say so. **Also:** the orphan-pointer check exempts lines
carrying `closed|shipped|dropped`, and the lines it flagged said **`fixed`** — a closing word it does
not know (same narrow-vocabulary shape as B15).

## B16. A malformed decision id is INVISIBLE, and nothing warns
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-08` · issue `#14`
Was `agent-reentry` B130 (migrated 2026-09-23). **Live incident:** a session in another project wrote
*"one decision is yours before I build anything (D-a in the brief)"*. The parser is
`_DECISION_START_RE = ^\*\*D\d`, so `**D-a.**` and `**Da.**` match nothing — verified against the
module. The row never appears in the orientation's decisions block, `validate_next.py` never checks
it (no missing `answer:`/`added`/duplicate check), and the user is told a decision is blocking the
work and then **never shown it again** — a thing to remember wearing the appearance of being tracked.

**Cause:** the numbering vacuum in `## Decisions` D30 — no stated rule for where an open decision's
number comes from, so an agent fearing a collision reaches for a non-integer label.
**Fix, two halves; the second matters more:** (1) say the rule (an open decision takes the next
integer from the rationale record's counter — D30's recommendation); (2) **warn on the near-miss**:
`validate_next.py` reports lines under `## Decisions` matching `^\*\*D(?!\d)` and under `## Watching`
matching `^\*\*W(?!\d)`, by line number. Without (2), fixing (1) changes nothing for the next agent
that invents a label. Consider whether B16/B17/B18 are one "did this file parse the way you think?"
report rather than three warnings.

**D29 and D30 answered 2026-09-25** (`docs/decisions.md`): backlog ids stay integers (a split takes
the next id and names its parent), and a repo has one D-number sequence shared by open and answered
decisions, with no prefix. That makes fix (1) concrete: state D30's rule in `rules/CLAUDE.md`'s
`## Decisions` shape (*"an open decision takes the next number after the highest in the rationale
record, and keeps it when answered"*) — a rules-text change, so it needs a version bump. Fix (2)'s
near-miss warning should also catch a letter-suffixed backlog heading (`## B2b.`), which D29 now
says is always a mistake. **Billing codes are not ids** — see B55, whose content stays private.

## B17. A watch trigger has exactly TWO evaluable forms; everything else is prose on a timer
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-08` · issue `#15`
Was `agent-reentry` B129 (migrated 2026-09-23). **Measured across a portfolio 2026-09-08: 3 of 8
watches (38%) carried a trigger the system cannot evaluate.** `check after` understands a
`YYYY-MM-DD` date and `[the] next session on <machine>` (v1.53.1). Anything else never becomes
`DUE NOW`; only the 30-day staleness flag surfaces it, which measures time since `added` — *nobody
has looked*, never *the trigger fired*. One of the three was written hours after the machine-trigger
matcher was fixed, by the same session, and was inert on arrival; the operator caught it in four
words (*"I don't see W7 yet"*).

**Tempting and wrong:** teach the parser more English (`when X ships`) — a wrong guess makes a watch
DUE on the wrong session, worse than silence.
**Build instead:** `validate_next.py` reports per watch whether the trigger is a date, a machine gate,
or **free text that only surfaces on the staleness timer**. Then, for the unexpressible ones:
(1) attach a date floor as the review point (cheapest; applies to W1 and W2 in this repo today);
(2) turn the condition into a check — W1 and W2 are really *pending verifications of shipped
features* and might deserve their own list; (3) mark timer-only explicitly, only with (1).
**Do not** reword inert watches into machine gates — a false `DUE NOW` has repeatedly been judged
worse than silence.

## B18. A short machine id only works as a SUBSTRING of the hostname; `MACHINES.md` is not consulted
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-08` · issue `#16`
Was `agent-reentry` B128 (migrated 2026-09-23). The operator proposed a two-letter id for a machine
whose hostname is one CamelCase word (say `BigDesk` → `BD`). Measured before answering: it **would
silently never fire.** `_is_here()` (`session_orientation.py`) is case-insensitive substring
containment against the live hostname:

    _is_here('BD', 'BigDesk') -> False    _is_here('Big', 'BigDesk') -> True    _is_here('DESK', 'BigDesk') -> True

An unmatched machine trigger falls to the free-text branch and renders as "not actionable yet" on
the very machine where it is due; it validates clean. **`MACHINES.md` exists to map hostname → id
and the watch matcher does not read it** — `machine_identity.check()` loads it in the same function
for the `run on <id>` annotation, so the lookup is adjacent and unused. `_is_here`'s docstring states
the assumption honestly; the short id breaks it.

**Fix:** consult `MACHINES.md` first, fall back to containment (it is populated on one machine only —
see B41 — so lookup-only would break every working trigger elsewhere). Then **warn on an id matching
neither** a `MACHINES.md` row nor the current host. **Rejected:** "just use the substring" (makes the
id a function of hostname spelling; the fix becomes something to remember), and exact match
(`ORG-LAPTOP1` containing `LAPTOP1` is the normal case).

## B19. `check_repos.py` collapses two repos that share a basename, and names only the basename
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-16` · issue `#17`
Was `agent-reentry` B142 (migrated 2026-09-23). Found during a wrap, at the step whose whole job is to
stop a CHANGELOG claiming work landed somewhere it did not. A session wrote to three repos: two under
`~/Projects` (one named `cairn`), and a private config clone *also* named `cairn` under
`~/.claude-private/`, outside the recorder's view. Naming the third explicitly:

    python tools/check_repos.py ~/.claude-private/cairn
    -> 2 repo(s) checked -- all clean and pushed (1 found by the recorder, not named)
         [ok] cairn -- clean, nothing unpushed
         [ok] workspace -- clean, nothing unpushed

**Three roots in, two out**, and the named path was folded into the recorded one. `record["name"]`
is `resolved.name`, so the line reads `[ok] cairn` either way — a clean result on the wrong repo is
indistinguishable from one on the right. Exit 0; the header arithmetic is the only tell and nothing
checks it. **Ruled out:** path format (`--no-recorded` resolves both MSYS and Windows forms
correctly) and `known_roots()`'s dedupe (keys on the full lowered path); the collision is in merging
*named* with *recorded*. **Fix:** dedupe on the resolved absolute path, and print a path whenever two
entries would render identically — the existing `"%s (in %s)"` branch proves it can. Consider always
printing the resolved root. (The wrap that found it verified the third repo by hand.)

## B20. The disclosure checker cannot see gitignored files, and every `.pyc` embeds the username
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-09` · issue `#18`
Was `agent-reentry` B140 (migrated 2026-09-23). Running the tests creates `__pycache__/`, and **every
`.pyc` embeds the absolute path of its source** — verified by reading the bytes (byte 5052 of one
`.pyc` holds `C:\Users\<username>\Projects\...`). That is one of the GENERIC patterns
`test_payload_clean.py` bans, and would be caught instantly in a source file. **But the checker
cannot see it:** `tracked_files()` runs `git ls-files --cached --others --exclude-standard`, so
anything `.gitignore` matches is invisible. The protection is supplied entirely by `.gitignore`, and
nothing checks that `.gitignore` still contains the line.

1. **`.gitignore` is load-bearing for DISCLOSURE, not tidiness**, and no doc says so. The seed got
   it right for another reason (copied with `git ls-files`, fresh `.gitignore` before the first
   `git add`); a directory copy would have left 39 `.pyc` files one `git add .` from publication.
2. **The checker should report ignored files that match a banned pattern** — a count and the
   pattern name, not a scan — so the operator learns the guard is `.gitignore`, not the tool.
**Related:** B30 (a `~` directory in a repo, fixed by trusting the same unchecked file).

## B21. The dangling-pointer warning cannot tell a stale pointer from a historical citation
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-06` · issue `#19`
Was `agent-reentry` B92 (migrated 2026-09-23). **Partially fixed 2026-09-08, 48 → 26 lines, precision
still 0.** `sync_backlog.py` now excludes known-historical paths (`CHANGELOG.md`, `docs/decisions.md`,
`docs/review/**`, `skills/*/references/incidents.md`) and drops lines carrying
`closed`/`shipped`/`dropped`, and deliberately *widened* to `BACKLOG.md`. Measured on the original
case after the change: **26 still reported, 0 real** — 13 `BACKLOG.md` prose cross-references
(`**Related:** Bn`), 10 in a design doc whose subject is the id, 3 in `skills/wrap/SKILL.md`.
Earlier live instances: 0/22, 0/6, then 0/11 minutes later — **the warning grows with how well the
close was documented.**

**The discriminator that would finish it is a shape, not a path list.** A *pointer* is structured —
a markdown link naming the id, a `blocked by Bn` field, a `## Queue` line, `→ Bn`. A *citation* is
the id inside a sentence, after `Related:`, `see`, `same as`, `family as`, or in parentheses. Test
the id's syntactic position — an exact question about the line, not prose-sniffing. Keep the path
exclusions as the belt. **Do not fix this by deleting the citations** — they are the record.

## B22. A NEW decision can contradict an OLD one, and nothing notices
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-08` · issue `#20`
Was `agent-reentry` B127 (migrated 2026-09-23). **Self-inflicted, which makes it better evidence.** An
agent recorded `docs/decisions.md` D22 **without reading D1's cell**; D22 contradicted D1, a brief
was rewritten to match D22, and a backlog item was filed praising the "catch". D22 now stands
superseded by its own correction (see the row). **The gap is the reverse of what was first
described:** not a brief drifting from a decision, but a new decision row contradicting an existing
one, in a project whose central rule is *read the record before deviating from it*.

**Why nothing sees it:** `wrap_receipt.py`'s `briefs` step checks a brief link **resolves**, not that
it agrees; the dangling-pointer scan (B21) finds refs to ids **going away**, not refs that are
**wrong**; `validate_next.py` checks fields in one `NEXT.md`. The whole family is "does the pointer
resolve", never "does the target still say the same thing".
**Candidates, none chosen:** (1) decisions carry their consequences as a list of files, and the
check is that each was touched in the same commit — caught this exactly, but only for files someone
listed; (2) a linked brief must be newer than the newest decision it cites — an mtime standing in for
agreement, **do not build alone**; (3) at wrap, list Queue-linked briefs unchanged since the last
decision row and ASK — report-only, but needs precision discipline (B21) before shipping. Re-read
any mechanism against the correction above: here both files were self-consistent at every step.

## B24. Nothing tracks the always-loaded context budget, and the files have grown since the last trim
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-07` · issue `#22`
**Unblocked 2026-09-26 (B23 closed).** `measure_context.py` runs without `tiktoken`, and it
already did at `init: cairn v1.56.0`. It prints a labelled bytes/4 estimate and exits 0. So the
"real number" below can now be measured on any machine. Re-measure it; don't reuse the
2026-09-07 table, which the files have outgrown.
Was `agent-reentry` B117 (migrated 2026-09-23). Trim work shipped (v1.12.0 trimmed the rules, v1.12.1
an audit tool), then the files kept growing — the expected outcome of a budget nobody owns: every
rule added since was justified individually and none weighed against a ceiling. Measured 2026-09-07:

| File | Bytes | Lines |
|---|---|---|
| `plugins/cairn/rules/CLAUDE.md` | 25,433 | 370 |
| `plugins/cairn/skills/wrap/SKILL.md` | 48,025 | 718 |
| `plugins/cairn/skills/next/SKILL.md` | 14,460 | 224 |

Older trim briefs opened on *"the wrap is 5,113 tokens"* — stale in the direction that matters; do
not revive them. `rules/CLAUDE.md` is paid unconditionally, every session, every machine. No backlog
item held a measurement and no trigger fires when the file grows. **Blocked on B23 for the real
number:** fix it, measure, then decide whether the ceiling is a row in `docs/decisions.md` or a check
in the suite. **Also decide:** is a brief pointer into a *different* repo allowed at all (one such
pointer went dead when that clone was deleted), or must briefs be copied in?

## B27. Third-party text reaches session context unmarked — label at `pull()`, neutralise at the printer
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-06` · issue `#25`
Brief: [briefs/untrusted-text-boundary.md](briefs/untrusted-text-boundary.md)
Was `agent-reentry` B102 (migrated 2026-09-23); decision row **D10**. **Live now: this repo is public
and its issues sync.** File content prints into the same stream as the `[to the agent]` lines the
agent is told to obey, separated only by a two-space indent nothing checks. `sync_backlog.pull()`
writes a remote issue's `title` and `body` verbatim into `BACKLOG.md`, so anyone who can file an issue
has a route in. Wider than first stated: `## Decisions` and `## Watching` have **no entry-count cap**,
a DUE watch's body prints whole, no sink has a per-line cap, `_decision_title`/`_watch_title` fall
back to the whole raw line, and `backlog_file.summary_lines()` never consults `inbound`. Two
chokepoints, not ten print sites: `backlog_file.parse()` and `session_orientation._read()`. **Never
`render()`.** Stops once, on the cap for Decisions/Watching and the DUE body.

## B28. Four on-disk identifiers still say `reentry` after the rename to `cairn`
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-07` · issue `#26`
Was `agent-reentry` B111 (migrated 2026-09-23). D18 renamed the plugin (v1.51.0); four identifiers
naming **live state on every installed machine** were deliberately left:

| Identifier | Refs | What renaming it orphans |
|---|---|---|
| `<!-- reentry:begin -->` / `:end` | 33 | the managed block in every `~/.claude/CLAUDE.md` — a new marker writes a SECOND block and leaves the first loaded forever |
| `~/.claude/reentry-profile.md` | 31 | the profile, the `@`-import line, `.bak-reentry-profile` backups |
| `~/.claude/reentry-state/` | 163 | every wrap marker, exit record, baseline, archive-offer and item-open marker — losing them makes the next session report a false "did not finish cleanly" |
| `~/.claude/reentry-private-names.txt` | 5 | the disclosure check falls to GENERIC-only and reports `PARTIAL`, quietly |

**A migration, not a rename:** write the new name; on startup move old → new when old exists and new
does not; then leave old alone forever. `reentry:begin` is the sharp one — the installer must
*remove* an old-marker block in the pass that writes the new one. **Not part of this:**
`reentry_state.py` (internal module, no on-disk footprint), `CHANGELOG.md` and archived records (the
record of what happened under the old name). Until this lands, `install_rules.py` says *"the cairn
rules block"* while writing `reentry:begin`.
**Since v1.62.0 (B25, D32) the header is a whole-line match** (`_BEGIN_LINE` in `install_rules.py`) —
the new marker's parser must stay one; never reintroduce a prefix search.

## B29. The payload still says `agent-reentry` in prose, in a repo called `cairn`
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-09` · issue `#27`
Was `agent-reentry` B137 (migrated 2026-09-23), which absorbed the still-open half of `agent-reentry`
B125. **A quality problem, not a disclosure one** — the name is published by decision (D1, D25).
Deferred during the seed because a wide editorial pass inside an irreversible commit was the wrong
risk (v1.50.0 records a de-personalising edit that reversed a sentence's meaning). Measured 2026-09-09:

| Where | What |
|---|---|
| `tools/check_install.py` :10, :37, :41, :137 | docstrings and a walk-up comment — **no user-facing string**; an earlier claim of a printed `not in an agent-reentry checkout` was stale |
| `tools/sync_backlog.py:12`, `tools/label_backlog.py:25` | docstring prose citing measurements |
| `tools/test_settings_drift.py:252`, `tools/test_version_drift.py:9` | comments |
| `skills/wrap/SKILL.md:90`, `skills/wrap/references/incidents.md` (×3) | provenance — **LEAVE ALONE** (D15: the measurement is the evidence) |
| ~20 test fixture names | plausible sample data — **LEAVE ALONE** |

**Only the first three rows are in scope.** Say "the plugin's own source repo" where the sentence
means *this project*; keep the name where the sentence is a dated record. **No bare find-and-replace.**
Renaming the old repo's remote is moot — its local clones are being removed and it is frozen.

## B30. The system's shell instructions are POSIX idiom, and a private file landed inside a repo because of it
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-07` · issue `#28`
Was `agent-reentry` B119 (migrated 2026-09-23). **Live incident 2026-09-07, following a watch's step
verbatim** on a Windows machine: `git clone <private-store-url> ~/.claude-private/<repo>`.
**PowerShell expands `~` only for cmdlets and providers, never for arguments to a native
executable**, so git got a literal `~` as a RELATIVE path and created a directory named `~` inside the
current repo — holding the private profile, inside the repo that was about to spawn a public twin,
untracked and one `git add .` from publication. The explicit-pathspec rule caught it by luck. Fixed in
passing: the watch's commands now use `"$env:USERPROFILE\..."` and `~/` is in `.gitignore`.

**Still open, the two things NOT fixed:**
1. **Nothing detects a private file that has landed inside a project.** `check_leak_coverage.py` can
   see the private store (v1.54.0, D23) but deliberately does not look INSIDE the project for one —
   that is a presence question, not coverage, and needs its own vocabulary. Whether
   `test_payload_clean.py`'s public-set walk would have caught it is **unverified** — check first.
   The v1.46.0 containment guard refuses such a path as a SOURCE but says nothing about a file sitting there.
2. **Every command the system hands the user is POSIX** — `rules/CLAUDE.md`, both skills, briefs and
   watches emit `~/...`, `cp`, `rm -rf`, `$VAR`, and on Windows `~`-to-native-exe is silently wrong.
   Sweep every fenced command in the payload, then decide: emit PowerShell-correct paths, state the
   shell per block, or a check grepping for `~` beside a native exe (`git`, `python`, `claude`, `gh`).
**Ruled out:** telling users to run these in bash — a rule about which shell is something to remember.

## B31. Cross-project roll-up: the morning chooser across every opted-in project
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-08-28` · issue `#29`
Was `agent-reentry` B2 (migrated 2026-09-23). Its two briefs stayed in the private repo (they name
the operator's portfolio); **write a fresh brief here when this is pulled**, from what follows.
Asked for from a work laptop: is there a projects-wide `/cairn:next` for planning a work week?

**What is built (measured 2026-09-08) — roughly one slice of four:**
- **Shipped:** `hooks/repo_sweep.py` — sweeps every sibling repo with `.git` AND its own `NEXT.md`,
  one cached behind-count line, capped at 25, reports and never pulls. It answers only *"folders next
  to this one on THIS machine"*.
- **Shipped, stage 1 of 2:** `tools/check_exits.py` — reads `~/.claude/reentry-state/*/` and reports
  which projects ended dirty or unwrapped. Stage 2 (a `SessionStart` one-liner) is deliberately absent.
- **Not built:** anything that reads another project's `NEXT.md` **contents** — no queue extraction,
  no `DUE NOW` count, no inbox count, no foreign `.last_wrap`. `sibling_repos()` tests only existence,
  as a security gate. No portfolio-catalog reader either.

**Decided — do not reopen:** after the morning pick, **stay in the project until wrap or block**
(the operator's own call, 2026-09-04; hub-after-every-item is the morning question asked all day).
The hub is a morning act that prints per-project top-2 plus date-forced watches, and a *project* is
picked. Concurrent projects are parallel sessions, not one chat hopping. Every opted-in project owns
its own `NEXT.md`, so the scraper is total, not best-effort. **No machine pin** — that belonged to
the Cursor half, now B57. **Do not re-merge them.**
**Decomposed separately:** B36 (multi-environment sweep), B37 (walk other inboxes), B38 (evening wrap
driver), B39 (a watch coming due elsewhere while you stay put — the hole "stay" leaves).
**Open when pulled:** the input source — the old brief assumed a portfolio catalog file; the shipped
sweep rejected that for siblings and deferred it to B36. Surfacing measured at ~483 vs ~5,437 tokens
for the two designs considered; keep the cheap one.
**Asked for again 2026-09-25:** with 90 minutes left on a Friday and the weekly token budget half
spent, the user wanted to ask cairn *"what should I spend this on?"* across every project, rather
than an agent reasoning it out ad hoc. The ad-hoc answer needed: each project's Queue, due watches,
a risk signal (an item marked as a production/outage hazard outranks a feature), and the time and
token budget available. The last two are new inputs beyond the per-project top-2 decided above.
**Asked for again 2026-10-01**, as a morning act or on a command: look across every project, raise
the next priority, and flag deadlines. Today's example: a queue item in a sibling repo whose window
closed that same day was seen only because the agent happened to open that repo's `BACKLOG.md` to
file something else. The session-start sweep reported the repo as 3 behind and nothing more. That
is the "date-forced watches" half of the decision above, and it needs to cover queue items with a
stated deadline, not just watches. Related: B95 (the roll-up should print briefs as links).

## B32. A finding about ANOTHER project has nowhere to go — make `INBOX.md` the cross-project mailbox
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#30`
Was `agent-reentry` B54 (migrated 2026-09-23). **Incident:** asked whether it had logged an issue in
another project, a session answered *"No — only logged it in MISTAKES.md"*. Recorded, and recorded
where the owning project will never read. A session in A that finds work for B can only carry it in
chat (the thing this plugin exists to prevent) or rewrite B's files (the concurrent-rewrite hazard).

**Design — `INBOX.md` already is the right file:** a foreign session **appends** one bullet to B's
`INBOX.md` — never `NEXT.md`/`BACKLOG.md`, which their owner rewrites wholesale. B's next session
surfaces it with no new mechanism. One line, provenance, no interpretation:
`- [from <project> · <machine> · YYYY-MM-DD] <what> — <why it matters> → <path or evidence>`.
**Post and move on; never read the target's files** (operator's constraint: *"we must try not to
waste current context"*). **Not an issue by default** — that creates a second writer (BACKLOG.md is
the writer, Issues the copy). **The one case an issue IS right:** the target is not cloned here; then
`gh issue create -R` / `glab`, saying why the normal path was bypassed. **Push the append at once** —
an unpushed append is invisible on the other machine; say so in chat if it fails.
**Build:** (1) `tools/inbox_post.py --project <name|path> --note "..."` — append atomically, commit
with an explicit pathspec, push, one-line report, `--issue` fallback; (2) a rule: `MISTAKES.md` is a
pattern log, not a delivery mechanism — log AND post; (3) a wrap step cross-referencing touched repos
against posts made. **Depends on** B35 (every project has an `INBOX.md`) and B56 (verified writes).

## B33. Several sessions at once — the concurrency rules are implicit
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#31`
Was `agent-reentry` B55 (migrated 2026-09-23). Operator: *"the problem is the cross checking and
messaging in one session about work in another session."* Separate repos fix file conflicts and none
of the coordination; the messaging half is B32. v1.59.0 generalised the re-read rule to all external
state; the rest is still unwritten:
- **One writing working tree per repo**, any number of read-only ones; a second writer takes a
  **worktree or a separate clone**. *A branch is NOT isolation* — `git checkout -b` does not isolate
  uncommitted files; two harnesses shared one tree with a dirty `BACKLOG.md` on 2026-09-04.
- **A foreign session may only append** (B32 depends on this being a rule).
- **The handoff is a wrap boundary:** wrap → fetch → push → cut the worktree from `origin/main` →
  hand over → end the session. The operator rejected a "donor stops writing until done" hold: *a hold
  is state somebody has to remember*. This also kills a second defect: a worktree cut mid-session
  from a local HEAD **19 commits behind origin** inherited a stale base and four items collided on ids.
- **When isolation fires:** the tree is dirty, another session is known live, or `git worktree
  list` already shows a second checkout.
- Subagent `isolation: worktree` is a different mechanism — it pointed agents at the wrong repo once
  (eight dirty trees) — not the independent-session rule.
**Build:** (1) write these into `rules/CLAUDE.md` and `/cairn:wrap`; (2) a cheap "is another session
live here?" marker at `SessionStart`, warn never block; (3) feed it into B31. **Do not build a lock**
— a stale lock on a machine walked away from is worse than the race. **B34 is the mechanical half.**

## B34. Make concurrency safety MECHANICAL — stamp the file hash at read, check it before rewrite
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#32`
Was `agent-reentry` B68 (migrated 2026-09-23). Operator's question: *"can we make it by design?"* — the
honest answer had been **no, the ordering saved it**. A second session appended to the inbox and ran a
full wrap while this one worked; nothing was lost only because this session had already pushed.
Reverse the order and a wholesale `NEXT.md` rewrite from a stale copy deletes the other's edits **and
looks perfectly correct**. *"Re-read from disk before rewriting"* is an instruction to the party most
likely to be wrong; this repo's incident record is agents reasoning past instructions.

**Mechanism:** (1) at `SessionStart`, while it has the bytes, store sha256 of `NEXT.md`,
`BACKLOG.md`, `CHANGELOG.md` in this session's `state_dir()` (`wrap_receipt.py` already stamps these —
reuse, add no state); (2) before any wrap rewrite, re-hash and compare; different → **name the file
and what changed**, and hold the rewrite until it is re-read; (3) the wrap **fetches before it
rewrites**, offering `--ff-only`, never pulling unasked.
**Known blind spot:** local hashes catch a sibling on the same disk only. Two sessions collided four
times across a worktree and the main checkout while every file hashed identical, because each side's
changes were unpushed — a fetch makes *content* current without making *id allocation* safe; stamp
the allocation, not only the bytes. **Why a hash, not a lock:** no lifetime, no cleanup, fails open.
**Scope: three files only**; `INBOX.md` is append-only and does not race.

## B35. Every tracked project gets the FULL file set, blank if need be — not just `NEXT.md`
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#33`
Was `agent-reentry` B57 (migrated 2026-09-23). Operator: *"All projects should get all the .md files
necessary for the plugin to work! Even if those files are blank."* Only `NEXT.md` is guaranteed; the
rest are created lazily. **Why lazy is wrong:** absence carries two meanings — a missing `NEXT.md`
means *not in the system* (correct), a missing `INBOX.md` in a member means *nobody wrote one yet* —
and B32's mailbox turns that into a real failure. **Measured on one laptop 2026-09-04:** Windows tree
12 repos, all have `NEXT.md`, **1** has `INBOX.md`, 5 `BACKLOG.md`, 4 `CHANGELOG.md`; WSL tree 6
repos, all `NEXT.md`, **0** `INBOX.md`, 0 `BACKLOG.md`, 2 `CHANGELOG.md`.

**The set:** `NEXT.md` (membership, unchanged), `INBOX.md`, `BACKLOG.md`, `CHANGELOG.md`, the
rationale record — header only. **Blank means BLANK:** legacy inboxes shipped example bullets and a
scanner counted four phantom items (see B15). **Does not change opt-in.**
**Two enforcement questions, unanswered:** (1) *a new project appears* — no daemon; `SessionStart` is
silent without `NEXT.md` by contract, so creation likely happens **whoever writes `NEXT.md` writes
all five** (a skill-side job — decide, don't assume); (2) *a fresh install on an existing tree* — no
backfill; a report-first tool that lists missing files and creates them only when asked fits the
existing `check_*` / `validate_next.py` pattern. **Build:** `tools/ensure_project_files.py`
(idempotent, same shape as `ensure_mistakes_file.py`), run only where `NEXT.md` exists; document the
set in `rules/CLAUDE.md` and `README.md`. A multi-repo bootstrap is the largest fan-out yet — one repo
at a time, explicit pathspecs, report each.

## B36. The git sweep is per-machine-and-cwd — Windows, WSL and remote checkouts are never swept together
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#34`
Was `agent-reentry` B59 (migrated 2026-09-23). Extends `repo_sweep.py`, which fetches *siblings of
cwd*. The ask is one report over **every clone the user owns**: the Windows tree, the WSL tree, and
checkouts on remote servers. "Siblings of cwd" cannot express that — WSL is not a sibling of Windows
and a server is not on this filesystem. Needs a project list plus a machine list as input, not a
directory listing. Report only: behind / ahead / dirty / **unreachable said as unreachable**, then
offer a pull list; never pull unasked; stop on conflict. **Name the environment, not just the repo** —
one repo on Windows, in WSL and on a server is three rows (B40 is why).

## B37. Nothing ever walks the other projects' `INBOX.md` files
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-04` · issue `#35`
Was `agent-reentry` B60 (migrated 2026-09-23). Orientation counts *this* project's inbox; the morning
ask is "reconcile all the inboxes". **Blocked on B35** — measured 2026-09-04, 1 of 18 repos had an
`INBOX.md`. Report counts and due-looking bullets per project; **read-only** — a foreign session
appends and the owner triages (B32).

## B38. Evening wrap is per-session; there is no driver over the machine
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#36`
Was `agent-reentry` B61 (migrated 2026-09-23). `/cairn:wrap` closes the repo you stand in; the evening
ask is "wrap everything, push, archive, so the other machine tomorrow does not skip a beat" — today N
wraps from a remembered list. Drive it from what this machine touched (`check_repos.py`,
`check_exits.py`): wrapped? clean? pushed? Offer a wrap where not. Don't wrap a repo another agent is
in (B33). Report push failures honestly. Finish with one line naming the remotes the *other* machine
should pull tomorrow — that is B36's input. Weekly half is B53.

## B39. A due watch in another project is invisible while you stay in this one
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#37`
Was `agent-reentry` B64 (migrated 2026-09-23). The hole in "stay in the project until wrap or block"
(B31). A dated watch surfaces as `DUE NOW` only at session start in its own project, so a day inside
project A is a day in which B..N's watches surface nowhere. **Fix in the hub, not the day:** (1) the
evening driver (B38) reports watches that came due today in projects not opened; (2) the morning hub
(B31) prints date-forced watches across projects. **No mid-day interrupt** — it re-creates the
rejected per-session roll-up. **Do not weaken "stay"**; it is the right choice for re-entry cost.

## B40. `state_dir()` hashes the resolved path, so one repo has several separate memories
`Sonnet 5` · effort `medium` · `HITL/Plan` · added `2026-09-04` · issue `#38`
Was `agent-reentry` B63 (migrated 2026-09-23). `state_dir()` keys on `root.resolve()`, so one repo
checked out on Windows, in WSL (`/mnt/c/...` *or* `~/Projects/...`) and on a server is **separate
silos** for wrap markers, item-open markers, dirty-tree breadcrumbs and timesheet rows. Git-tracked
files sync; plugin memory does not — a wrap on Windows does not close the WSL tree, and nothing says
so. **Document it as a constraint first**; aliasing (shaped like `timesheet.py`'s `PROJECT_ALIASES`)
is a later design. **Related:** B3 (wraps on another machine are invisible — the git-side twin of this).

## B41. `~/.claude` content is global by location, local by content, and backed up nowhere
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-05` · issue `#39`
Was `agent-reentry` B77 (migrated 2026-09-23). `~/.claude` is not a git repo, so `CREDENTIALS.md`,
`MISTAKES.md`, `MACHINES.md` and every `projects/*/memory/*.md` exist on exactly one machine,
unversioned. The plugin creates three of them (`ensure_credentials_file.py`,
`ensure_mistakes_file.py`, `MACHINES.md`) **empty** and has no opinion about their contents
travelling. Lose the machine and the credential inventory — whose whole purpose is surviving the
moment something needs rotating — goes with it. **Live symptom:** `MACHINES.md` was populated on one
machine of three, so `run on <machine>` checks (and B18's fix) are inert on the others.
**Why HITL/Plan:** every mechanism is the user's call — a private git repo (needs a credential per
machine), a synced folder (no versioning, conflict copies), or a plugin export into a repo — and the
blast radius includes a credential inventory (names and locations only, never values). The profile
already solved this for one file (D7/D19's private store); decide whether the same store carries the rest.

## B42. Nothing detects a commitment made in chat that never reached disk
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-06` · issue `#40`
Was `agent-reentry` B98 (migrated 2026-09-23). Operator, after catching three in one session: *"How
do we stop this from happening?"* A session about the re-entry system delivered three follow-ups in
chat, wrote none down, and left the FINISHED item at Queue position 1. **Third instance in two days**
(`MISTAKES.md`). The rule is in `rules/CLAUDE.md`, both skills, and printed as an always-on
`[to the agent]` line every session — in context, and broken anyway. A fourth copy is the
intervention that has already failed three times (the D4 shape).

**Shape: a `Stop`-hook detector.** Stop hooks receive `transcript_path`, so the last reply is
readable. Signal: the reply contains future-commitment phrasing **AND** `NEXT.md`/`BACKLOG.md` are
unchanged since session start (reuse `wrap_receipt.py`'s baseline hashes; add no state). Phrases from
real instances: *before you, next session, still needs, outstanding, then run, you should, worth
checking, keep an eye, after the deploy, at some point, we should also, don't forget, remember to*.
Downgrade when the reply cites a `Bn`/`Wn`/`Dn` or a `NEXT.md`/`BACKLOG.md` path. **One line, never
blocks, never fails the verdict** (D5/D6). **Rejected:** a stricter rule (failed 3×); blocking the
Stop (fires on read-only sessions); doing it at wrap (the sessions that lose commitments are the ones
that never wrap); an LLM judge (per-turn model call, non-deterministic, breaks zero-deps).
**Second hole, same plan:** an item STARTED this session with `NEXT.md` unchanged — `item_open.py`
stamps the start but only warns next session, and says "abandoned", not "finished but never cleared".
**Fourth instance, the first measured (2026-09-09):** a committed, pushed CHANGELOG entry claimed a
brief, a backlog id and a closed watch in a *sibling* repo; none existed there, and the sibling was
clean and `0 0`. A cross-repo claim is mechanically checkable — `check_repos.py` checks repos the
session *touched*, and this one was never touched. Parsing the wrap's own entry for `<repo>/<path>`
and `` `<repo>` B<n> `` shapes and stat-ing them is a far smaller job than the general case.

## B43. Nothing detects a good stopping point — the wrap nudge was never mechanised
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-07` · issue `#41`
Was `agent-reentry` B113 (migrated 2026-09-23). Operator: *"the plugin hasn't been doing this for a
while now — suggesting I wrap and start a new session."* **What exists:** `dirty_tree_warning.py` on
`Stop`/`SessionEnd`, once-per-*worsening* (a per-turn warning became wallpaper). **What doesn't:**
searched `hooks/` and `tools/` for `good (point|time) to (stop|end|wrap)`, `suggest.*wrap`, `natural
breakpoint` — **zero hits**; the phrase lives only in prose (`rules/CLAUDE.md`, `skills/wrap/SKILL.md`,
its `incidents.md`). *Uncommitted work* is detected; *a phase completing* is an instruction to
remember — the B42/D4 shape. A phase boundary is not a git fact. **Candidates:** a `Stop` heuristic (a
queue item's brief done, a version bump, a CHANGELOG entry since `.last_wrap`) with the same
anti-wallpaper gate; session age / turns since `.last_wrap`. **Rejected in advance:** a louder skill
sentence. **Read `MISTAKES.md` first** (42 entries at filing) as the evidence of which signal helps.

## B44. The operator wants a hook that blocks closing a session with unwrapped work
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-02` · issue `#42`
Was `agent-reentry` B43 (migrated 2026-09-23). Raised after `dirty_tree_warning.py` warned correctly
mid-session: can the warning become a block? **Read that hook's header first** — *"NEVER BLOCKS. A
Stop hook that traps a session is worse than a dirty tree … a session that cannot end is a session
with no `NEXT.md` to resume from"* — and the incident behind it in `skills/wrap/references/incidents.md`.
**Candidates short of a block:** a louder warning (today's de-dupes to "worse than last time", which
may be too quiet to read as urgent); or use the archive offer as the harder stop, since it is read at
a moment of attention rather than mid-task. Needs a plan: it changes the moment of leaving.

## B45. `MISTAKES.md` is written and never read
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04` · issue `#43`
Was `agent-reentry` B62 (migrated 2026-09-23). The file exists on every machine and `/cairn:wrap`
appends to it; **nothing reviews it**, and its justification is that a recurring pattern gets
*designed against* — which needs a reader. Not a dashboard: a skill or a dated review cadence that
reads the log, clusters repeats, proposes **one** rule or tool change, and writes an `incidents.md`
row if accepted. **Never auto-edit `rules/CLAUDE.md` unasked** — it installs to every machine.

## B46. Narrative accumulates in `NEXT.md` between the Queue and `## Decisions`, where no budget applies
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-07` · issue `#44`
Was `agent-reentry` B108 (migrated 2026-09-23); only the design question migrates — the file it was
found in is frozen. **Measured:** eleven italic paragraph blocks, ~80 lines, every one a dated
narrative of a past session, several already false (a "Queue is at 4" note contradicted by the header
above it; a fix described as new after it shipped). Each block was a reasonable single addition;
nothing removes one, because a wrap edits only what it is changing. **The footer has an 8-line budget
and a truncation marker; this region has neither** — same always-loaded cost, no ceiling.
**Decide:** should `session_orientation.py --check` (or `validate_next.py`) flag it — a line count, or
a date older than N days in a non-footer paragraph — rather than relying on a wrap noticing?

## B47. The wrap cannot tell whether the session's work left the user-facing docs behind
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-06` · issue `#45`
Was `agent-reentry` B93 (migrated 2026-09-23). **Answered by the operator: DETECT and REPORT, offer per
session** — `docs/decisions.md` D5. Three existing rules are prose: `wrap/SKILL.md` step 3a, and two
same-commit rules (version bump → README check; `SKILL.md` rule → `incidents.md` check). The gap is
the change with no version bump, or one that leaves `docs/guide.md` / `docs/design-notes.md` behind.
**Shape, copying `hooks/archive_offer.py`:** diff this session's committed paths against the docs
that claim to explain them; one line per stale doc (*"`docs/guide.md` last changed at v1.42.0; this
session changed `hooks/wrap_receipt.py`"*); update / file it / skip, **skip is first-class and does
not re-nag**; the verdict is unaffected. **Hard part, design before code — which doc covers which
behaviour:** a path→docs map in the project (explicit, travels, one more file); a convention (zero
config, wrong for other projects); recency only (fires constantly). State the check's horizon next
to it: it cannot see a doc that is wrong without being old.

## B48. Nothing knows how much code has shipped since anyone last read it
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-06` · issue `#46`
Was `agent-reentry` B94 (migrated 2026-09-23). **Answered in D6:** code review is **offered at the
COMMIT step with a running total**; security review is trigger-based. B47's pattern does not transfer
— for docs, detection is free and the fix costs; for code, **the detection is the cost** (an agent
pass). Only *"N source files committed, no review ran"* is free. The operator's correction: a
per-session offer where skip leaves no residue means twenty reasonable skips hide thousands of lines.
So: *"committed 312 lines this session · **1,847 lines across 12 sessions unreviewed since
2026-08-24**"* — per-volume, not per-calendar. A lane batch is then a special case, not a second
trigger. **Security:** when a touched file constructs a `subprocess`, reads/writes `CREDENTIALS.md` /
a token, or talks to the issue host, the offer names `/security-review` instead and says which file.
**The marker (last-reviewed sha) must be committed IN the repo**, not in `state_dir()` (B40); a stale
one over-counts, which fails safe. **Open:** what counts as source (Python and hook JSON, not
Markdown)? Threshold, or always shown at the commit offer? Does a partial review reset the whole count?

## B49. A scheduled unattended run that never got going looks identical to one with nothing to do
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-06` · issue `#47`
Was `agent-reentry` B89 (migrated 2026-09-23). **Measured:** a 05:00 batch fired into a session left
in `Manual` mode and sat **four and a half hours** on a permission dialog for a read of one backlog
entry, completing only when a human woke and clicked. The mode half is now written in
`docs/running-a-batch.md` (`AFK/Manual` is a contradiction). **What's missing is any way to find out it
stalled:** no commits, no dossier, no handover is *bit-for-bit identical* to "fired, found no eligible
work, stopped early" — which that doc calls the design working.
**Fix — a heartbeat first:** the task's first act stamps `~/.claude/reentry-state/<task-id>.started`
(wall-clock and sha); its last act marks it `finished`. Orientation can then say *"a scheduled run
started 09:29 and never finished"* or *"was due 05:00 and has not started"*. **Extended by the
operator's question** — one reader of `~/.claude/scheduled-tasks/` at session start reporting
**armed** (what will fire, and when — the one that matters), **spent** (offer deletion at wrap, never
unasked), **started-never-finished**. **Rejected:** inferring from mtimes (a 09:48 mtime, and 09:29
recorded nowhere); the plugin setting the mode (cannot, and should not); a kill timeout (a run blocked
on a prompt is not a run gone wrong); the plugin deleting tasks itself.

## B50. Scheduling an unattended run is hand-built from memory every time — it should be `/cairn:schedule`
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-06` · issue `#48`
Was `agent-reentry` B91 (migrated 2026-09-23). The creation half of B49. The 05:00 batch was a
~60-line prompt restating from memory the push prohibition, the sync prohibition, the lane partition,
the dossier shape, the handover and the `AFK`-only rule — all already on disk — then fired into
`Manual` mode. **The vocabulary lacks this case:** `AFK`/`HITL` describe attendance *during a
session the user started*; a scheduled run is a third thing — nobody present until morning, composing
work met cold. `rules/CLAUDE.md` says nothing about it. **Name the case first.**
**The skill should:** (1) compose a short prompt pointing at `docs/running-a-batch.md`, `NEXT.md`,
`BACKLOG.md`; (2) check what it can and **refuse** — tree clean and pushed, eligible `AFK` items exist,
`NEXT.md` present; (3) state what it cannot check before the user walks away — permission mode (`Auto`
or `Accept Edits`, never `Manual`), app staying open, sleep settings; (4) write B49's heartbeat into
the task; (5) name the handover file and dossier prefix from the scheduled start. **Rejected:**
leaving it as prose (written the same day it failed); a recurring nightly cron (fires with or without
safe work); the skill setting the mode.

## B51. Archiving a review dossier is a multi-file repointing job done by hand
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-06` · issue `#49`
Was `agent-reentry` B90 (migrated 2026-09-23). `docs/running-a-batch.md` makes `docs/review/` an inbox:
once a batch is pushed, dossiers move to `docs/review/archive/`. Done by hand once for twenty-five
files, and every pointer in `NEXT.md`, `BACKLOG.md`, `CHANGELOG.md`, `docs/decisions.md` and both
`incidents.md` had to be rewritten in the same commit — a moved file with a stale pointer is a
dangling pointer made by hand. **Build `tools/archive_reviews.py`:** move non-reference dossiers,
preserving or deriving the `YYYY-MM-DD-HHMM-` prefix; rewrite every `docs/review/<name>` pointer;
report anything left pointing at nothing; `--dry-run` by default. **Only archive what is accepted** —
gate on `0` ahead of origin or explicit shas, never mtimes. **Rejected:** leaving them flat (sorting
says when, not whether anyone owes a read); deleting accepted dossiers (the only record of what an
unattended lane decided).

## B52. `timesheet.py` on a Cursor laptop reports the wrong machine's work, confidently
`Sonnet 5` · effort `medium` · `HITL/Auto` · added `2026-09-04` · issue `#50`
Was `agent-reentry` B65 (migrated 2026-09-23). Verified from a Cursor shell: the script runs (no Claude
Code import), reads `~/.claude/projects/`, and reports the few *Claude Code* sessions there — read as
"this week's work on this laptop", silently wrong where most hours are spent in Cursor. Cursor does
write transcripts, at `~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl`, but the
schema is `{"role": ..., "message": {...}}` — no `type`, no structured `timestamp`, no `cwd`, no
`custom-title`; user turns carry a clock inside the prompt text, assistant turns none.
**Pick one:** a Cursor backend in the reader, agent-gap duration marked `unverified`; or a
`sessionEnd` hook appending `{session_id, cwd, duration_ms, reason}` to a gitignored jsonl (loses
overlap attribution, survives schema change). **Rejected:** a derived ledger beside `NEXT.md` (a
second store that drifts). **Land the guard first:** refuse, or loudly caveat, when a Cursor transcript
tree exists and `~/.claude/projects/` is near-empty. `timesheet.py` also asserts twice that "Cursor
writes no transcript" — false; fix the comments.

## B53. There is no end-of-WEEK driver, so the timesheet is still something to remember
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-05` · issue `#51`
Was `agent-reentry` B78 (migrated 2026-09-23). Operator: *"a global wrap at the end of the work day…
And then also one for the end of the week that then calculates the timesheets automatically."* Daily
half is B38; this is only the weekly half. A driver that runs `timesheet.py` across every
contributing machine, merges, and leaves the result where it will be found on Monday. **Must NOT ship
before B52 and B54** — today it would be confidently wrong on the machine with most hours, and the
cross-machine transport has an unresolved design defect. **HITL/Plan:** it produces a number that is
billed against; what counts as a week, parallel sessions, and where it lands are the user's calls.

## B54. `timesheet_sync.py` copies whole session transcripts where a digest would do
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-07` · issue `#52`
Was `agent-reentry` B120 (migrated 2026-09-23). **Measured 2026-09-07, running the tool's own
documented command:** it copied **35 files, 88.50 MB** of raw `~/.claude/projects/*.jsonl` to a synced
cloud folder on an employer tenant. Case-sensitive `grep -ral -F` over the copies found the user's
personal-profile terms in up to **19 of 35** files and `CREDENTIALS` in 14 — **an earlier `-i` pass
returned a false all-clear on these files and is not a usable check.** Transcripts quote the profile
every session, so the transcript set is a larger disclosure than the profile the rules already keep
off employer infrastructure. **Exposure resolved:** one event, one machine, about an hour; purged
from both machines and BOTH stages of the tenant recycle bin (a first-stage or local delete alone was
not enough). Diagnostic worth keeping: a cloud **placeholder** (`RECALL_ON_DATA_ACCESS | OFFLINE |
REPARSE_POINT | SPARSE_FILE`, 88 MB Length, 24 KB on disk) is evidence of what the cloud still holds,
and `du` on it proves nothing.
**Still the item — the default:** `timesheet.py` needs **timestamps and project names**; the tool
ships entire transcripts because copying a directory was cheapest. **Options:** (1) sync a derived
per-session digest (`sessionId`, project, first/last timestamp) — kills the disclosure; needs a format
and a reader; (2) keep the transport, move the destination; (3) refuse when the destination resolves
inside a corporate sync folder unless overridden. **(1) is what it should have done from the start.**
The tool is not in any daily sync, so nothing re-uploads unattended — until someone follows the docs.

## B55. `timesheet.py` reports by directory name, not by the billing code timesheets are filled in with
`Sonnet 5` · effort `medium` · `HITL/Auto` · added `2026-09-08` · issue `#53`
Was `agent-reentry` B126 (migrated 2026-09-23; the actual codes stay private). Timesheets are filled
in per **project number and activity**; `timesheet.py` already derives per-project hours and handles
renamed directories via `PROJECT_ALIASES`, but reports by **directory name**, so the last step is
manual mapping from memory. **The gap is one mapping, not a feature:** an optional table, directory →
(project code, group, activity), resolved from the user's private config, **absent by default and
silent when absent**, consumed to emit rows in the timesheet's shape. Codes are employer data; the
mechanism ships, the content never does (the D16/profile split). **Not an id:** a billing code is an
attribution axis and changes when funding changes; an item id must never change — two fields.

## B56. GitLab writes: create and close are proven on a 2021 server; update, label and note are not
`Sonnet 5` · effort `medium` · `HITL/Auto` · added `2026-09-03` · issue `#54`
**Measured 2026-09-28 (SBOLE-NB5), and the answer to "check first" below.** `bsr-tools` (WSL, on the
13.12.15 server) has filed and closed issues through `sync_backlog.py` many times — e.g.
`c3ddb98` (close #85, file #86 #87), `02b215d` (#88), `17c81f4` (close #88, file #89), `e73054e`
(close #86, file #90 #91); 40 of its 42 items carry an issue number. So `issue create --yes` and
`issue close` work against the old server. **Still unproven:** `issue update --description-file`,
`issue update --label`, `label create --color '#…'`, and `issue note` on a closed issue.
**The fix is a manufactured test, not waiting for it to happen:** on a throwaway GitLab project (never
`bsr-tools` or another real repo), a scratch `BACKLOG.md` that forces each of the four writes once, then
reads the issue back with `glab api` to check the server did what the argv claimed. `HITL` because it
writes to the employer's host: it stops for him before the first write and says which project.
Was `agent-reentry` B50 (migrated 2026-09-23). **Check first whether it has run since** — a `glab`
backlog sync has reported success in at least one WSL work repo (see B5), which may already be the
evidence. v1.34.0's GitLab backend was verified for **reads** only; every write —
`issue create --yes`, `issue close` + `issue note`, `issue update --description-file`,
`issue update --label`, `label create --color '#…'` — is pinned by `test_issue_host.py` at argv level,
which proves the intended flags and nothing about the server. `glab api version` on the one instance
used returned **13.12.15** (mid-2021) against `glab` 1.116.0, and `personal_access_tokens/self` 404s
there (a 14.x endpoint). Token scope was measured as `api`, so scope is not the risk. **Watch for:**
`--yes` unsupported (would hang, not fail), `issue note` on a closed issue, `#` in label colours. Any
fix belongs in `GitLabHost`, not callers. **Related:** B7 (the same write path failing on WSL + `gh.exe`).

## B9. `sync_backlog.py` and `validate_next.py` answer for the SESSION's repo, not the one they're run in
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-23` · issue `#56`
Seen twice in one session on SBOLE-NB5, 2026-09-23. The session was opened on the private source
repo, and `cairn` was then added as an extra directory:
- `cd …/cairn && python plugins/cairn/tools/validate_next.py` printed **3 watches, 4 decisions**,
  which are the private repo's counts. With the root passed explicitly it printed **0 and 0**,
  which is correct for `cairn`.
- `cd …/cairn && python <plugin>/tools/sync_backlog.py` printed `backlog synced with
  superbole/agent-reentry`. So `cairn`'s B8 has **not** been filed as an issue yet.

Probably the project root comes from the session's project dir (`CLAUDE_PROJECT_DIR` or
equivalent) before `cwd`. Not checked. The private repo filed the validate half as B139. A wrong
repo in a sync is worse than a wrong count: it writes to a different issue host. **Fix direction:**
prefer the git root of `cwd`, and print the root being used on the first line (sync already names
the repo; validate does not).

**Seen again 2026-09-28 (NB5), and it cost a false diagnosis.** A session opened on `cairn` ran the
wrap's sync from `cd …/workspace`. It printed nothing inside a 100 s timeout, and the agent blamed `glab`
as unconfigured, from a stale memory. In fact `glab` was logged in and fast, and `--dry-run` showed the
sync answering for `superbole/cairn`. **Working workaround:** `CLAUDE_PROJECT_DIR='<repo path>'` in front of the
command made it sync that repo to its GitLab host correctly (closed #44, filed #64–#66).

**Merged in 2026-09-23 from `agent-reentry` B139 and B133**, which were the same defect, filed twice:
- **The cause is confirmed, not probable.** `validate_next.py` falls back to `project_root()`, and
  `sync_backlog.py` does `root = project_root() if project_root else Path.cwd()`.
  `reentry_state.project_root()` resolves `CLAUDE_PROJECT_DIR` → this session's stamp → `cwd()`, in
  that order, so **inside a session `cwd` is unreachable and `cd` has no effect at all.** That
  ordering is right for hooks, which must answer for their own project. The defect is that a
  **report tool** inherits it silently.
- **The worse instance was a real sync against the wrong remote:** run from inside a sibling repo, it
  printed `backlog synced with <this repo> (GitHub): ... no changes.` The sibling's three new items
  were never filed, and it was only noticed because someone read the repo name. The workaround,
  `CLAUDE_PROJECT_DIR=<path> python .../sync_backlog.py`, works, but steering a tool by setting an
  internal env var is not an interface.
- **The remedy is already established practice:** v1.35.0 made `check_repos.py` print the root it
  resolved, *"because it can resolve the wrong one when the shell's cwd has drifted"*.
- **Fix:** (1) add `--root PATH` to `sync_backlog.py` (validate already takes a PATH), taking
  precedence over `project_root()`. (2) Every report tool prints the root it used, and where it came
  from: `project_root_source()` already returns `env` / `session-stamp` / `cwd` and nothing prints
  it. (3) **A success line naming a repo the caller didn't ask for is a warning, not a report** —
  that applies when cwd sits inside a different git repo from the resolved root. (4) Audit every
  tool that calls `project_root()` with no argument and prints a verdict: `check_repos.py`,
  `issues_backlog.py`, `validate_next.py`, `measure_context.py`.

## B8. `/cairn:next` and `/cairn:wrap` should tell the agent to read files with Read, not a shell chain
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-23` · issue `#57`
On re-entry, an agent read NEXT.md's Queue, INBOX.md and git state in ONE Bash call:
`cd /c/…/agent-reentry && sed -n '/^## Queue/,/^## Decisions/p' NEXT.md; ls INBOX.md 2>/dev/null && cat INBOX.md; git log --oneline -3; git status -sb | head -3`.
Every piece of it is read-only and auto-allowed on its own, but the chain (a `cd` combined with
`git`, plus `;`, `&&`, a pipe and a redirect) still brought up an **"Allow Claude to run …?"**
prompt. He asked how to stop it (2026-09-23, `agent-reentry` on SBOLE-NB5). A prompt at the very
first step of re-entry is the attention cost this plugin exists to remove.

**Fix:** one line in each skill's Procedure — *read `NEXT.md`, `INBOX.md` and `BACKLOG.md` with the
Read/Grep tools (offset/limit for one section); run each `git` command as its own plain call; never
chain them behind a `cd`.* Consider the same line in `rules/CLAUDE.md` under "How work gets done",
since sessions that never load a skill read these files too.

**Ruled out:**
- **An allowlist rule** — no `permissions.allow` pattern can match an arbitrary compound
  command, and the prompt comes from the `cd`+`git` combination, not from any single command.
  (`agent-reentry` got a read-only MCP allowlist the same day; it doesn't cover this case.)
- **A per-project memory** — saved in `agent-reentry`, but it loads only there.

**Check:** SKILL.md rule changes need an `incidents.md` check in the same commit (this repo's
CLAUDE.md, if carried over from `agent-reentry`).

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

## B7. On WSL with the Windows `gh.exe`, every GitHub issue re-body fails ("cannot find the file")
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-23` · issue `#7`
**Seen 2026-09-23 on NB5 (WSL):** `sync_backlog.py` in `cairn` printed `! B5 — could not update #5:
open /tmp/tmpXXXX.md: The system cannot find the file specified.` On NB5, `~/.local/bin/gh` is a
**symlink to `/mnt/c/Program Files/GitHub CLI/gh.exe`**. `hooks/issue_host.py` `_body_file()`
writes the body with `tempfile.mkstemp()` into WSL's `/tmp` and passes that Linux path to a
Windows exe, which can't open it.

**What is and isn't affected:** `create` passes the body in argv (see the comment near line 632),
so **filing** new issues works (B6 was filed as #6 in the same session). Only `update` (line 477,
re-bodying an existing issue) fails, and it fails every time. The sync reports "file is still
right", so nothing is lost locally, but GitHub issue bodies stop updating on this machine without
anyone noticing. `glab` on NB5 is a native Linux ELF, so GitLab projects (`bsr-tools`) aren't
affected.

**Likely fix:** when the resolved CLI is a `.exe` running under WSL (`/proc/version` contains
`microsoft`), put the temp file somewhere Windows can see (e.g. under `/mnt/c/Users/<u>/AppData/
Local/Temp`) and pass the path converted with `wslpath -w`. Or pass the body in argv, as `create`
already does. The alternative is a native Linux `gh` on NB5, which is machine state for
`workspace`, not a plugin fix.

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

## B62. A machine inbox: show the GitHub issues labelled for THIS machine at session start
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-25` · issue `#62`
**Asked for 2026-09-25**, the durable half of `workspace` D8. One user can have several hubs that no
single machine opens. This user has two repos called `workspace`: a private GitHub one for the personal
machine, and one on the employer's GitLab for the work laptops. So a machine-gated watch filed in the
wrong hub never surfaces where it's needed.
Routing by hand (D8 option 1) fixes each case. This fixes the class.
**Shape:** issues on one GitHub repo, the user's inbox (their private personal hub), labelled
`machine:<id>` with the id from `MACHINES.md`. The orientation lists the open ones for this machine in
every session, whatever project is open, from a cache the detached refresh keeps (no network on the
hot path, same as the inbound-issue cache). Opt-in via an env var beside `REENTRY_PROFILE_SOURCE`, so
a stranger's install is silent. Any machine with `gh` can file into it. On 2026-09-25 a work laptop's `gh` was
already the user's personal account with `repo` scope, so the work laptops can write today.
**Ruled out:** `glab` on the personal machine filing into the employer host (puts an employer token on a
personal machine); a file in `cairn-private` (no phone access, and B112 gave that repo one job on
purpose); a corporate planner such as Microsoft Planner (employer tenant, and not readable by agents there). **Open for the plan:**
how an inbox item is closed (by the machine that acts on it, and with what evidence), and whether it
also lands in that hub's `BACKLOG.md` or stays a session-start line only. `HITL/Plan` because the
design is still open.

## B60. Native Windows without Git for Windows can't run any hook since v1.61.0
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-25` · issue `#60`
Accepted cost of D31. When Git for Windows is absent, Claude Code runs shell-form hooks through
PowerShell (code.claude.com/docs/en/hooks), which can't start `sh "…/run.sh"`. Before v1.61.0
the bare `python "…"` command ran there. The README now lists Git for Windows as a Windows
prerequisite. The bet is that nobody using a git-centric plugin lacks it, and that bet is
**unmeasured**.

Reopen only if someone is actually seen in that configuration. **Options then:** a PowerShell
twin (`run.ps1`) plus a way to pick it. `hooks.json` has no per-platform branch, and the `shell`
field is per hook, not per OS, so that "way" is the whole problem. Or exec-form `args`, if a
future Claude Code adds per-platform commands. Rejected already (D31): a sh/PowerShell polyglot
command string, because of CommandNotFound noise on every PowerShell hook call.

## B67. The `next-id` marker has two readings, and the parser and the people disagree
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-26` · issue `#65`
Found in the 2026-09-26 overnight batch's bookkeeping. `backlog_file.next_id()` returns
`max(parsed, marker, origin) + 1`, so the code reads `<!-- next-id: N -->` as **the highest id already
spent**. The name, and every hand edit, read it as **the next free id**: the 2026-09-25 wrap filed B64
and set the marker to 65 ("next-id moved from 62 to 64, because filing B62 had left it behind" in
`CHANGELOG.md`), after which `next_id()` answered **66**, skipping 65. The direction is the safe one (it
skips, never collides), which is why nothing has failed, but a hand edit made in the other reading
could lower the floor by one. **Decide:** keep the code's semantics and say so where people edit it
(the marker comment `render()` writes, `docs/file-formats.md`, the wrap skill's backlog step), or
rename the marker (`<!-- last-id: N -->`, reading the old spelling on the way in). Either way the
parser keeps accepting the old marker. B65 was never filed; nothing needs renumbering.

## B68. The old `python "$CLAUDE_PLUGIN_ROOT/…"` command form survives outside the skills
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-26` · issue `#66`
B59 (v1.63.0, D35) rewrote every call site in `skills/*/SKILL.md` and `rules/CLAUDE.md`, and
`tools/test_skill_calls.py` pins those two places only. Lane B listed the copies it did not own:
`plugins/cairn/tools/check_repos.py:56-57` (a docstring quoting the old wrap step-1a command),
`docs/design-notes.md:91,112`, and `docs/cursor-adapter-requirements.md:286`. The README's
`check_install.py` row also tells the user to run `python plugins/cairn/tools/check_install.py`,
which fails on stock Linux. Rewrite them to the `sh "<root>/hooks/run.sh" …` form (the README one is
for a human, so `python3`/`py` alternatives are fine there). Leave `skills/*/references/incidents.md`
alone: it quotes history verbatim on purpose. Consider widening `test_skill_calls.py` to `docs/` with
an allow-list for dated evidence.

## B71. Wrap: act on sync_backlog dangling-citation warnings inline; prefer gh/glab for cross-repo backlog items
added `2026-09-26` · issue `#69`
Two related findings from an ai-coach wrap session (2026-09-26), both about how an agent
should behave when cairn-relevant work surfaces from inside a *different* project's session.

### 1. A named, unambiguous sync warning got deferred instead of fixed

`sync_backlog.py` closed ai-coach's B141 and printed:

    backlog: 3 reference(s) elsewhere still name an item this sync is about to drop (B141) —
    they will point at nothing once BACKLOG.md is rewritten; fix them by hand:
      · BACKLOG.md:1319 — ...
      · BACKLOG.md:1709 — ...
      · BACKLOG.md:1724 — ...

The session reported this to the user as a heads-up for later ("doesn't block anything —
a note for whoever next touches those entries") instead of just fixing it. The user pushed
back: *"why didn't you do this automatically?"* — correctly. The warning named exact files,
exact lines, and an unambiguous fix (repoint the citation to the CHANGELOG entry that has
the real narrative). There was no judgement call left to defer.

**Proposed fix:** `skills/wrap/SKILL.md` step 8a (or wherever `sync_backlog.py`'s output is
handled) should say plainly: a dangling-citation warning is fixed in the same wrap turn it is
printed in, not logged as a note — unless the fix is genuinely ambiguous (multiple plausible
targets, or the citation's meaning is unclear), in which case *that* ambiguity is what gets
surfaced, not the mechanical fact that something needs fixing.

### 2. Cross-repo backlog additions should go through gh/glab, not a local edit

The above surfaced a broader question: when a session working in project A notices something
that belongs in project B's (e.g. cairn's own) `BACKLOG.md`, editing B's file locally means a
checkout, a commit, and a push from a session that has no other reason to be in that repo —
and risks exactly the concurrent-edit collision the whole system exists to prevent, just
against the *tooling's own* repo instead of a project repo. This is live right now: cairn is
being edited on NB1 while this finding came from a DeepThought session in ai-coach.

`sync_backlog.py` already has the reconciliation path for this — an issue that exists on the
host but isn't yet in `BACKLOG.md` is pulled in and marked `inbound` on that repo's own next
wrap. So the round-trip already exists; it's just not named as the default.

**Proposed fix:** document in `rules/CLAUDE.md` or `skills/wrap/SKILL.md`: when a session
notices a backlog-worthy item for a DIFFERENT project (including cairn itself) than the one
it is working in, file it via `gh issue create` / `glab issue create` against that repo,
never by editing its `BACKLOG.md`/`NEXT.md` locally. Local edits to a project's own re-entry
files stay reserved for sessions actually working in that project (or, for cairn specifically,
actual plugin development — editing rules/skills/hooks, which needs a real checkout anyway).

This issue itself was filed this way, from the ai-coach session that found it, as a live
instance of the proposed rule.

## B72. An inbound issue whose body has `## N.` headings becomes extra backlog items
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-26` · issue `#72`
**Seen 2026-09-26.** `sync_backlog.py` pulled issue #69 in as B71, and that issue's body has two
sub-headings, `## 1. …` and `## 2. …`. On the next sync, `backlog_file._ITEM_RE`
(`^##\s+B?(\d+)\.\s+(.+?)\s*$`, where the `B` is optional) read them as items **1** and **2**. It
rewrote them as `## B1.` and `## B2.`, gave them fields lines, filed them as issues #70 and #71, and
dropped an indented line from B71's body. That makes three defects: the optional `B` accepts any
numbered `##` heading; a pulled-in body is written into the file without demoting its headings; and
the parser takes an item number from the heading, so it reused **B1** and **B2**, ids spent long ago,
even though `next_id()` exists to stop exactly that. Repaired by hand: B71's sub-headings are now
`###`, and #70 and #71 are closed as not planned. **Fix:** when pulling, demote every `#` heading in
an issue body by two levels, or indent it. Decide whether `B?` can become `B` (check what the
`## 12.` REFUSED guard from 2026-09-03 relies on). If the parser sees a number at or below the
spent floor that isn't already in the file, refuse, don't renumber. Add a test with a body carrying
`## 1.` headings. **Ruled out:** fixing only #69's text, because the next inbound issue with
numbered headings does the same.

## B73. Offer "do N covers N, M" when a queue item can run other queued AFK items as its own lanes
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-26` · issue `#74`
**Requested 2026-09-26**, on seeing the orientation say that queue item 1 (B70) runs items 2 and 3
as background worktree subagents, so one "do 1" covers all three: *"I like this, we should provide
this as an option when it's possible."* Today that only happened because B70's hand-written brief
said so. Nothing in the mechanism detects or offers it.
**Why it matters:** the user does not want parallel sessions, because they have overlapped before.
One attended session that also drives the queued AFK items as lanes uses the tokens that would
otherwise go unspent, without a second session to remember or collide with. It is the
`docs/running-a-batch.md` shape, but attended and started from a single queue pick.
**When it is possible** (all of these must hold, and most are already rules in `running-a-batch.md`):
the extra items are `AFK` (a lane cannot ask the user anything); their owned files are disjoint from
each other and from the lead item; at most four lanes run at once; each lane runs at its own item's
model (`Agent` `model:`) with `isolation: "worktree"`; lanes touch no shared file (`NEXT.md`,
`BACKLOG.md`, `CHANGELOG.md`, `README.md`, `docs/decisions.md`, `plugin.json`), and the lead session
does all the bookkeeping. A `HITL` lead item is fine, and arguably the best case, because the user is
present to review each lane when it reports.
**Design to decide:** (a) the wrap writes it: when refilling the Queue, it checks the AFK items'
briefs for owned files, and if they are disjoint it adds a `with: 2, 3` marker to the lead item. The
orientation prints "do 1 also runs 2 and 3 as lanes". (b) `/cairn:next` works it out at pick time
from the briefs. (a) is recommended: it is decided once, with the whole file in view, and it is
visible before anyone picks. (b) re-derives it on every pick and hides it until then. Either way a
brief has to declare its owned files, which briefs do not do consistently today. Declaring them is
probably the first step.
**Where:** `skills/wrap/SKILL.md` (queue refill, step 7), `skills/next/SKILL.md` (step 6), the
orientation hook's queue rendering, the brief template, and `docs/running-a-batch.md`.
**Ruled out:** a second parallel session per item, because the user has rejected that.

## B74. The orientation should say when the weekly allowance resets, and how much AFK work is runnable
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-26` · issue `#75`
**Decided 2026-09-26 in B70's planning session: file it, don't build it yet.** The weekly allowance
is use-it-or-lose-it, but the only place the reset time lives is the user's profile (prose, in their
private store). So nothing reminds anyone on the day it matters. By the time someone notices unused
budget, the reset has usually passed. The orientation already prints `N runnable AFK`, and it is the
one thing read every session.
**Design:** an optional `resets:` declaration mapping account → weekday + local time (e.g.
`work: Sun 16:00`, `private: Thu 15:00`), plus which account each machine uses. `MACHINES.md` already
maps hostname → machine id, so the account can sit beside it or in the profile. The orientation adds
one line when the reset is less than about 48h away: `work allowance resets in 29h · 24 AFK items
runnable`. **Do not print a percentage used:** `tools/measure_usage.py --window` measures only the
5-hour window, and inventing a weekly figure is the bare-constant failure. If a real weekly source
appears later, add it then. **Silent when undeclared**, the same as every other opt-in, so a stranger's
install is unchanged.
**Where:** `hooks/session_orientation.py` (the line), the reader (MACHINES.md or the profile, which
has to be decided), `docs/file-formats.md`, and the README's opt-in list. **Ruled out:** hard-coding
this user's reset times anywhere in the plugin, since they are personal and the plugin is public.

## B77. Guard `main` against unattended pushes with something stronger than permission patterns
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-26` · issue `#78`
**From B69's lane (v1.64.0), dossier `docs/review/2026-09-26-1225-lane-b69.md` §5.** `.claude/settings.json`
now **asks** before every push that can reach `main`. A local unattended run therefore stalls rather than
pushes. But patterns cannot close everything: quoted or escaped verbs, git aliases, `exec`/`xargs`
wrappers, `GIT_CONFIG_*` injection, globs, and a run writing a script and executing it with an allowed
interpreter. That last one cannot be closed by a pattern or a hook. The `afk/` and `tools/*` allows also
match six push forms and some sync forms by construction, so the `ask` rules are load-bearing. And the
routines docs say a cloud routine runs "without stopping for approval", which may mean `ask` is simply
approved there. The cloud dry run tests that.
**The strongest candidate is GitHub-side:** the routines docs say a routine **refuses to push to a
protected branch**
(https://code.claude.com/docs/en/routines.md#repositories-and-branch-permissions). Routines push as the
user's own GitHub identity, so a ruleset cannot tell a routine from him at GitHub. But the refusal is
the routine's own check, so protecting `main`, while his attended pushes still work through an admin
bypass, may stop routines cold. **Unverified.** Test it on a throwaway repo before relying on it.
Changing a repo setting is his to approve (HITL).
**Also proposed:** a project `PreToolUse` push-guard hook that resolves a push's real destination with
`git push --dry-run --porcelain` and refuses anything that reaches `main`, plus a `pre-push` git hook
(its limit: it is not installed in a fresh cloud clone unless `core.hooksPath` is committed and honoured).
**Ruled out:** `deny` in `settings.json`, because it also refuses his attended wraps (his decision,
2026-09-26).

## B78. Wrap close: print the 'Next: item N …' line in a copy box
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-26` · issue `#73`
Reported 2026-09-26 (captured via a project's INBOX.md, then triaged here).

The wrap close ends with the "what's next" line, e.g. *"Next: item 1 — <title>. Opus 5, effort high, AFK in Auto mode."* The user copied that line by hand from the close to start the next session. They asked for it to be printed in a **copy box**, i.e. a fenced code block, so the desktop app gives it a copy button.

Tension to resolve: step 9 says **do not paste a ready-to-copy prompt into chat** (the 2026-08-09 correction), because everything a prompt would hold is already on disk. This is not that. It is a one-line handle (item number, title, model, effort, attendance/mode), and it is evidently what the user types to re-enter. A likely resolution: fence the one "Next:" line and keep the prose around it.

Touches: `skills/wrap/SKILL.md` step 9, plus the matching incident note in `skills/wrap/references/incidents.md`.

## B79. Review the unattended `afk/` PRs in Cursor's diff view, and say so where the review is queued
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-27` · issue `#79`
**From B57's plan (2026-09-27), D43.** `AFK` items run in Claude Code and each pushes one `afk/…` branch
and PR (D39). Reviewing those is `HITL` work that Cursor does better than a terminal: the whole diff
in the editor, file by file, with inline edits. W6 is exactly this job. **To decide:** whether W6's
brief and the wrap's `afk/` push-stop wording name Cursor as the preferred harness for the review,
and whether `cairn-next` should offer to open the PR's branch. **Not this:** routing `AFK` items to
Cursor, which D43 rejected.

## B80. A cross-model second opinion before a `HITL` merge, on the cheapest non-Anthropic model
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-27` · issue `#80`
**From B57's plan (2026-09-27).** Cursor ships `review` and `review-security` built-in skills and
non-Anthropic models (Grok, Cursor's own Composer, GPT). A review of a Claude-written change by a
different model family catches a different class of mistake. It should use the cheapest such model
on the Pro licence. **Not `Auto`:** it can route to a Claude model, and then the review is not a
second opinion. **Probes first, both unverified:** which models are cheapest on the licence, and
whether `Auto` reports which model it used. **To decide:** where in the wrap, or in the `afk/` PR
review (B79), the step sits, and whether it is offered or required.

## B81. Team install for colleagues who use Cursor only
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-27` · issue `#81`
Brief: [briefs/cursor-team-install.md](briefs/cursor-team-install.md). Pulled to refill the Queue at B57's wrap, 2026-09-27.
**Taken off the Queue 2026-09-28, kept in the backlog.** He knows of no colleague who uses only
Cursor, but several who use only Claude Code, so B86 (the Claude Code team install) took its slot.
Kept on purpose: no such colleague *today* is not a reason to drop the option.
**From B57's plan (2026-09-27).** This is the Cursor half of the aim that "a stranger installs from
this repo and orients in their own project with no manual setup". Cursor has team marketplaces and
account-level installs (cursor.com/docs/plugins). An account-level install lands on every machine
that shares the account, which is right for cairn and wrong for anything machine-specific (the
requirements report, §3). **Unverified:** whether a team marketplace can host a GitHub repository
that is not in the team's organisation, and whether auto-refresh needs the Cursor GitHub App on
`superbole/cairn`. Blocked on nothing; start from `README.md`'s "Using it from Cursor".

## B82. The repo recorder misses a shell write that names its target by a RELATIVE path
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-27` · issue `#82`
**Seen live 2026-09-26**, in the second Cursor test chat. The agent ran `Add-Content
..\cursor-v1-other\y.txt …`. The recorder hook fired, exit 0, and recorded nothing:
`repo_recorder.bash_candidate_paths()` only picks up absolute-path-shaped tokens, and every
candidate is re-checked against real git state, so a relative one is never tried. **Both harnesses
have it;** Cursor only made it visible, because its agent writes relative paths by default. **The
fix to weigh:** resolve relative-looking tokens (`..\x`, `../x`, `x/y`) against the command's working
directory (`cwd`, or the project root when that is empty, which Cursor sends), then apply the same
git re-check. Keep the over-inclusive-then-verify shape the module docstring defends. **Ruled out:**
recording the project's own tree, which is not a foreign write.

## B83. Make the wrap receipt measurable in Cursor (today it reads `CAIRN UNKNOWN`)
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-27` · issue `#83`
**From B57 (v1.65.0), `plugins/cairn/cursor/gaps.md`.** The receipt's baseline is keyed by session id
(B72: never machine-global). Cursor gives hooks a `session_id`, but the agent's shell, where
`wrap_receipt.py --record` runs, has no session variable (checked 2026-09-26). So every Cursor wrap
reads `UNKNOWN`. That is honest, and D38 makes it harmless, but it is blind. Cursor processes also
ignore any inherited Claude session id since v1.65.0, because a Cursor window launched from a Claude
session carries that id. **Candidates:** a `beforeSubmitPrompt` hook stamps `{project → session_id}`
and the receipt adopts it only when exactly one live Cursor session holds that project; or a probe
finds a session variable in a later Cursor. **The constraint to respect:** B72's reverted
machine-global stamp. Two concurrent chats in one project must not share a baseline.

## B84. "Burn tokens": a named `/cairn:burn` that schedules ONE persistent task and survives Manual
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-27` · issue `#91`
**Found 2026-09-27, NB1.** The 03:00 firing (`cairn-lane-batch-2026-09-27-0300`) did fire, and the VPN held.
It stalled on its 6th command at 03:01 and sat until a human approved at 09:44. The command was
`git show origin/main:BACKLOG.md > "$TEMP/bl.md"; sed -n …`. `sed` is not on the allow list, and a
redirect to a file outside the project is not covered either, so in `Manual` it became a prompt. The
next stall was the same shape: `python plugins/cairn/tools/run_tests.py … > "$TEMP/b61-tests.txt"`. The
allow list (D39, B69) is right. The prompt text still let the run write commands outside it. Third
Manual stall in a row (2026-09-06, 2026-09-25, 2026-09-27).
**Three fixes, one item:**
1. **One persistent task, rescheduled, not a new one-shot each night.** The app stores tool approvals
   on the TASK and reapplies them on later runs, and the mode is set per task in the Scheduled
   sidebar. A fresh `taskId` every night throws both away, which is why Auto has to be set again
   every time. Keep `cairn-burn` and move its `fireAt` with `update_scheduled_task`. **Unverified:**
   whether a mode set on a task survives into its next firing. Test it on the first reuse.
2. **The prompt forbids the shapes that miss the allow list:** no `>`/`>>` redirects, no `$VAR`, no
   `sed`/`awk`/`cat` (use Read/Grep/the file tools), no `cd && …` into paths outside the repo. The
   task prompt is where the allowed shapes are named, so name them. Alternatively, add narrowly
   scoped allows (e.g. `Bash(sed -n *)`). Weigh that against D39's point that `*` spans spaces.
3. **A named command and a reminder.** He never knows what to call this. It is a local scheduled task
   (a "routine" is the cloud kind) running `docs/running-a-batch.md`. Name it **the burn**: `/cairn:burn`
   picks the AFK items, creates or reschedules `cairn-burn`, and ends with a preflight checklist he
   acts on while still at the keyboard: set the task to **Auto** in the Scheduled sidebar (first time
   only, if 1 holds); reconnect the VPN (TOTP, see W7); lid open; app open. The SessionStart hook
   already lists registered tasks, so it can also print "a burn is scheduled; is it set to Auto?"
   when `cairn-burn` has a future `fireAt`. Rename the doc's "lane batch" to "burn" where it is
   user-facing.
**Ruled out:** `defaultMode` in the project file (D39: `auto` is ignored there). Push notifications as
the reminder (blocked on the work account). A cloud routine (GitHub blocked on the work account).

## B85. `check_repos.py` reports every pushed `afk/` worktree as "1 unpushed"
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-27` · issue `#92`
**Seen at the 2026-09-27 batch's wrap.** `check_repos.py` flagged all seven `afk/2026-09-27-*` worktrees as
`[!!] … 1 unpushed` (afk-02 as 2), and then said *"Do NOT write a CHANGELOG entry saying this work landed"*.
Every branch was in fact identical to its remote: `git ls-remote origin refs/heads/<branch>` matched each
local HEAD. **Cause:** `docs/running-a-batch.md` and the task prompts create lanes with
`git worktree add … -b afk/… origin/main`, which sets each branch's **upstream to `origin/main`**. So
`@{u}..HEAD` counts the PR's own commits, and a pushed PR branch looks unpushed forever. **Fix, either or both:**
create lane branches with `--no-track` (the push stays `git push origin afk/<branch>`); and in
`check_repos.py`, for an `afk/` branch, compare HEAD with `origin/<same branch>`, not `@{u}`. **Why it
matters:** it's the wrap's gate on the CHANGELOG, so a false `[!!]` there either blocks an honest entry or
teaches the next agent to ignore the gate.

## B86. Team install for colleagues who use Claude Code only
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-28` · issue `#93` · queued
Brief: [briefs/claude-team-install.md](briefs/claude-team-install.md). Took B81's Queue slot 2026-09-28.
**He said, 2026-09-28:** he knows of no colleague who uses only Cursor, but several who use only
Claude Code. One person can already install cairn from the marketplace (README). What is missing is
a way to hand it to a team without walking each person through it, and a check of what a colleague
who is not the maintainer actually gets on first run. B81 (the Cursor-only version) stays in the backlog.

## B87. When the checkout is behind, orient from origin's `NEXT.md`, and never start an item on a stale base
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-28` · issue `#94` · queued
**Found 2026-09-28, SBOLE-NB5.** `main` was 50 commits behind `origin/main`. The banner said so, but the
queue it printed came from the stale local `NEXT.md`: two of its three items had already been replaced
on origin, and a new decision (D37) wasn't shown. The agent had to `git show origin/main:NEXT.md` by
hand to give a true answer. He agreed the fix below ("then the user is never seeing a stale queue").
**Shape:** when HEAD is strictly behind `@{u}` and `NEXT.md` has no uncommitted or unpushed local
change, print the orientation from `git show @{u}:NEXT.md`, labelled *from origin, local is N behind*,
then offer the pull. It's a local read of a ref the detached fetch already updated, so the hot path
still makes no network call. If `NEXT.md` *does* have local changes, show the local file and say
origin differs; don't merge the two.
**The case he asked about, a pull refused and then an item started that exists only on origin:**
the brief is not on disk, the item may already be done on another machine, and any id minted
collides (B33: 19 behind, four items collided). So the agent must not start it on the stale checkout.
**Decided 2026-09-28 (D46): decline until he pulls.** Say in one line that the item exists only on
origin and a pull unblocks it. A worktree off `origin/main` was considered and rejected: he doesn't yet
follow worktree workflows.
**Related:** B4 (a merged feature branch reads as in-sync), B33/B34 (concurrency), B36, B58.

## B88. "Where do I run what?" — an SOP, and a cross-project search that crosses Windows and WSL
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-28` · issue `#95`
**Asked for 2026-09-28:** *"I'm still having issues with knowing where I should be running what
from … This needs a plan session."* The trigger: asked about Planner/Outlook ingestion, the agent searched
only `cairn`, said nothing existed, and was wrong. The flows, the reader (`scripts/propose-queue.ps1`)
and the `inflow` brief all live in `workspace`, on purpose (cairn D20: cairn doesn't grow an
employer-specific Graph client). The layout is correct, and neither he nor an agent can find things in it.
**Two halves, one plan session:**
1. **The SOP.** A short written procedure: which machine, which repo or hub (there are two `workspace`s),
   Windows or WSL, Claude Code or Cursor, for each kind of work. It is his, so it probably belongs with
   the profile or in `workspace`, not in the shipped rules. The plan decides where.
2. **A cairn tool: find which project owns X.** A search over every opted-in project's `NEXT.md`,
   `BACKLOG.md`, `docs/decisions.md` and briefs, across **both** sweep roots. Today the sibling sweep
   is per-cwd and never sees Windows and WSL together (B36). Candidate: `/cairn:find <term>`, and a
   rule that an agent runs it before saying something does not exist.
**Would graphify have helped? Measured, no:** `workspace` B62's graphify test (2026-09-27) had the graph
beat grep on 0 of 3 questions, and it maps code inside one repo, not who owns what across repos.
`workspace` B64 (orientation maps in each repo's `AGENTS.md`) is the code-level half of this problem.
**Would ponytail have helped? No:** github.com/dietrichgebert/ponytail (read 2026-09-28) is a YAGNI
guide that steers an agent toward writing less code, and it works inside one project. It doesn't search
across repos or record who owns what. **Related:** B31 (cross-project roll-up), B36.
**More evidence, 2026-09-29 (NB5).** A Windows desktop session in the `SBole/workspace` hub was used
to change the WSL-homed `bsr-tools`. Read/Edit refused the path (`blockReadsOutsideWorkingDirectories`),
so it edited scratchpad copies and `wsl cp`'d them back: whole-file overwrites, no reviewed diff, and a
CRLF risk. The SOP needs a rule for that moment: **stop and name the session to open; never work
around the boundary.** The hub now says so in its `AGENTS.md` (its `docs/decisions.md`, 2026-09-29).
**One unknown decides the SOP's WSL line.** The desktop-app WSL docs (code.claude.com/docs/en/desktop-wsl,
read 2026-09-29) list plugins as not working there yet. If so, cairn is silent in every desktop WSL
session, and WSL repos should go to `claude` in a WSL terminal instead. Being tested on NB5
(`SBole/workspace` W7, brief section dated 2026-09-29); the result gets written here.
**RESULT, 2026-09-30 (NB5): PASS.** A new desktop-app session with the WSL environment in `bsr-tools`
printed cairn's orientation and queue on "hi" (newest cairn cached in WSL is 1.60.0). Plugins
DO load there, so the docs page is stale or wrong for cairn. The SOP's WSL line is the desktop app's WSL
environment, same as a `claude` terminal in WSL. Not measured: whether the staged-review guard and the wrap
receipt fire there too; only the SessionStart hook was seen.

## B89. An issue-finding scan: a scheduled AFK run that files findings into each project's `INBOX.md`
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-28` · issue `#96`
**Asked for 2026-09-28:** *"I'm struggling to find time to get to everything and a bot that can log
issues sounds wonderful right now!"* 13 of 17 tracked projects (Windows and WSL) have empty or nearly
empty queues. He corrected the reading of that: an empty `NEXT.md` means nothing *has been added
yet*, not that nothing needs doing.
**Shape agreed in chat:** a local scheduled task on NB5 (cloud routines can't reach GitHub or the
work account), running as B84's "burn" so it spends the weekly allowance before the reset. For each
project on an opt-in list he keeps, it reads the code and writes up to N findings as `INBOX.md`
bullets. `INBOX.md` is the existing seam that cairn triages at session start, so no new mechanism is
needed to surface them. It commits locally and doesn't push (AFK). It never files to the issue host
directly, because the file is the writer and the host is the copy.
**Will it find issues nobody has identified? Yes, of the kind a code reviewer finds:** bugs, failing or
missing tests, dead code, committed secrets, stale dependencies, docs that contradict the code,
TODO/FIXME debt, and a first seed backlog for a project that has none. **No, for product-level gaps**
(what users need next); those need him. Each bullet must carry `file:line` evidence and be deduped
against `BACKLOG.md`, `NEXT.md` and `INBOX.md`, or the inbox becomes noise he learns to skip.
**Open for the plan:** reaching WSL projects from a Windows task (B36), the cap per project per run,
which model scans (cost against the allowance), and how a rejected finding stops being re-filed.
**Related:** B84, B74 (the reset and how much AFK work is runnable), B31.

## B90. Auto-mode approvals pile up as one-off exact-command rules, and cairn's command shapes cause most
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-29` · issue `#97`
**Asked 2026-09-28:** why a Windows session in a hub kept stopping for approval on read-only commands
in Auto mode. **Measured in that checkout on NB5, 2026-09-29:** `.claude/settings.local.json` held 23
allow rules, 8 of them one-off compound strings like `Bash(cd "<plugin cache>/1.58.0" && grep -rn ...)`.
Each approval is saved as that exact string, never matches again, and so never reduces a future prompt.
**The shapes that prompted are the ones cairn leads an agent to write:** `cd` into the plugin cache to
read hooks, `git -C` on sibling repos, `git fetch` (writes `.git`, a protected path that still prompts
in Auto mode per code.claude.com/docs/en/permission-modes), `wsl.exe` hops, and `&&`/`;` chains that
mix a fetch with reads. One prompt, `sed -n '/^## Queue/,/^## Decisions/p' NEXT.md | grep ...`, has no
documented cause; the guess (unchecked) is that `sed` can write, so it isn't classed read-only.
**Fix directions for the plan:** (1) rules text: one command per call, absolute paths, no `cd`
outside the working folder, fetch in its own call; (2) a vetted set of pattern allow rules for
cairn's own read-only calls (`git -C * status|log|rev-list|diff`, the `--check` tools) that
`check_settings.py` offers to add; (3) say so when `settings.local.json` is full of one-off compound
rules. **Check B77 first:** any allowlist here must not widen what can push to `main`.
The per-checkout cleanup is `SBole/workspace` B69.

## B91. The leak detector ignores a new state dir for the suite checkout's own slug
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-29` · issue `#99`
Accepted with #88 (B75), not queued. A test that writes the checkout the suite is running in is ignored, because that checkout is a real worktree. Refusing to ignore that slug fails the suite whenever it runs inside a live worktree, which is how a batch re-runs its own lanes. An unrecognised name still fails the run. Do not close this by blaming every real worktree.

## B92. sync_backlog: an interrupted run re-files items it already created, and pull then re-imports the duplicates
added `2026-09-29` · issue `#98`
**Found 2026-09-29 in `ai-coach`.** `tools/sync_backlog.py` was started from the Bash tool. That shell's sandbox made network calls slow, so the call hit its 180s timeout and was stopped. By then it had already created GitHub issues #217 and #218 for B174/B175, but it never wrote `issue #N` back into `BACKLOG.md`. The next run, from PowerShell, saw two items with no issue and filed them again as #219/#220. On a later sync, the pull step imported #217/#218 as new items B177/B178, duplicating both.

**Why it matters:** an interrupted sync duplicates work, and the next wrap re-imports the duplicates as inbound items. Those look like someone else filed them.

**Fix shape:** before filing an item that has no `issue`, search the open issues for an exact title match, or a `Synced from BACKLOG.md (item Bn)` footer, and adopt the match instead of creating a new one. Or write each issue number back to the file right after its create, not in one batch at the end.

Cleanup done by hand: #217/#218 closed as duplicates, B177/B178 removed.

## B94. Map Claude family and effort onto Cursor and Grok model slugs
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-29` · issue `#101`
**Triaged from INBOX.md at the 2026-09-29 wrap; nothing decided yet.** Captured verbatim below. It needs his
call on whether a non-Anthropic row may stand in for a family (D45 says off-scale: name it and ask) or only
records effort, and whether the preamble should name slugs at all (D47: the label is the family). Stops at the plan.

**Map Claude family and effort onto Cursor and Grok.** Captured 2026-09-29. Not decided. D45 still says Cursor `Auto` and any non-Anthropic model (Grok, Composer, GPT) is off the scale: name it and ask, do not call it above or below. D47 says the label is the family, Haiku < Sonnet < Opus < Fable, and effort is separate. The preamble says `high` is that model's thinking or Max variant and `medium` is the standard one, and to pick the current model of the family. It names no slug. The slugs below are the ones this session's subagent list offered on 2026-09-29. The picker may have more. A blank cell means it was not in that list, not that Cursor lacks it. Two Sonnet highs were both listed, so "current of the family" is not one slug.

| Claude label | effort | Cursor slug, Claude | Cursor slug, Grok |
|---|---|---|---|
| Haiku | high | `claude-4.5-haiku-thinking` | `grok-4.7-high` |
| Haiku | medium | | `cursor-grok-4.6-medium` |
| Sonnet | high | `claude-sonnet-5-5-high` and `claude-4.5-sonnet-thinking` | `grok-4.7-high` |
| Sonnet | medium | | `cursor-grok-4.6-medium` |
| Opus | high | `claude-opus-5-thinking-high` | `grok-4.7-high` |
| Opus | medium | `claude-opus-5-5-medium` | `cursor-grok-4.6-medium` |
| Fable | high | `claude-fable-5-1-thinking-high` | `grok-4.7-high` |
| Fable | medium | | `cursor-grok-4.6-medium` |

This chat ran as `grok-4.7-high`. The Grok column is the same two slugs on every row: effort only, not a family. Also in that list and also off the scale: `composer-2.5-fast`, `gemini-3.8-flash-high`, `gpt-5.6-sol-medium`, `muse-spark-1.3-high`. Triage should say whether the preamble names these slugs, and whether a Grok row is allowed to stand in for a Claude family or only records the effort.

## B95. Briefs are not clickable in the orientation relay, and a watch has no brief link at all
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-10-01` · issue `#106`
**Found 2026-10-01** at a session start in the operator's work portfolio hub. He went to click a due
watch's brief to follow its steps and found no link anywhere in the relay. Three separate gaps:

1. **Queue items reference a brief as a code span, not a link.** The hub's `NEXT.md` writes
   `` brief: `BACKLOG.md` B39 ``. `session_orientation.py` echoes the line as written, so the
   orientation shows a code span. The `[to the agent]` line (line 1329) does ask for
   `[brief](link)`, but the agent copied the path as written instead of turning it into a link. That
   is the expected way for it to go wrong, because the rule says "path copied from `NEXT.md`".
   `validate_next.py` accepts the code span, so nothing catches it.
2. **A brief that is a BACKLOG section has no address of its own.** "B39" inside `BACKLOG.md` is a
   heading, not a file. A link to `BACKLOG.md` opens at the top of a long file. A
   `BACKLOG.md:<line>` link works in the desktop app, but a line number written into `NEXT.md`
   goes stale as soon as the file changes. Whether heading anchors (`#b39-…`) work in the app's
   file pane has not been tested.
3. **The watch shape has no brief field.** A watch's steps live inline in `NEXT.md`. The hook prints a
   due watch in full, but the agent shortens it in the relay, and nothing links to the watch's own
   `NEXT.md:<line>`, so the full steps are not one click away. Some watches name a brief file in
   their prose (`docs/briefs/x.md`), also as a code span.

**Fix shape, not decided:** (a) have the hook render any brief path it can resolve as a markdown
link, with a line suffix for a BACKLOG item or a watch, computed at print time so it never goes
stale; (b) let `validate_next.py` warn on a code-span brief reference; (c) add an optional
`→ [brief](path)` to the watch shape, or have the relay always link a due watch to its own
`NEXT.md` line. (a) alone covers most of it, because nobody has to edit a file to get the links.
(d), the operator's suggestion 2026-10-01 and the simplest: make the section labels themselves links.
"DUE NOW" and "Also watching" link to `NEXT.md`'s `## Watching`, "WHERE YOU LEFT OFF" to `## Queue`.
One link per section instead of one per item, and it works without a per-watch brief field. Untested:
whether a `#watching` anchor opens at the heading in the desktop app's file pane. If it doesn't, the
hook can print `NEXT.md:<line of the heading>`, computed at print time.
**Ruled out:** asking agents to write links by hand. That is the rule that failed here.

## B97. `installed_plugins.json` is never compared against the latest PUBLISHED version
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-30` · issue `#108`
**Triaged from INBOX.md at the 2026-10-01 wrap.** Captured verbatim:

(2026-09-30, from a workspace session on NB1) `version_drift.py` never compares the installed plugin against the latest PUBLISHED version: only installed vs this repo's `plugin.json` (cairn repo only) and installed vs the rules block. So a machine with auto-update silently off stays silent. Sheldon wants it added only if it succeeds silently. Proposed, offline, no network in the hook: compare `installed_plugins.json` with `~/.claude/plugins/marketplaces/superbole/plugins/cairn/.claude-plugin/plugin.json`, and flag if the marketplace clone's last fetch (FETCH_HEAD mtime / last commit) is older than a few days. Print nothing when both are fine. On NB1 today both read 1.66.0, clone fetched 2026-09-29 23:03. Auto-update itself proven working on NB1 (workspace W10, closed 2026-09-30). Also see workspace B71 / #69 (sync_backlog.py targets the session's project, not the cwd), which belongs here.

## B98. `sync_backlog.py` run from a sibling repo silently syncs the SESSION's project
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-30` · issue `#109` · queued
**Triaged from INBOX.md at the 2026-10-01 wrap.** Captured verbatim:

(2026-09-30, moved from workspace B71 / workspace issue #69, where it was wrongly parked) **`sync_backlog.py` run from a sibling repo silently syncs the SESSION's project.** From a workspace session, `cd ~/Projects/inflow && sh <root>/hooks/run.sh tools/sync_backlog.py --dry-run` printed `DRY RUN against SBole/workspace`: `main()` uses `reentry_state.project_root()`, which prefers `CLAUDE_PROJECT_DIR`, then the session stamp (B72), and only then the cwd. A real run would have synced workspace's 70-item backlog while the agent believed it was syncing inflow's; the one output line naming the target is easy to skim past. **Worse:** the workaround `CLAUDE_PROJECT_DIR=<repo>` RE-STAMPS the session root (`_resolve_project_root` calls `_stamp_session_root`), so every later cairn tool in the session (`check_repos.py`, `wrap_receipt.py`) resolves to the sibling unless the var is passed again. **Same family:** `staged_review_guard.py` did not count `git -C <repo> diff --cached` as reading the staged diff; only `cd <repo> && git diff --cached` cleared it. Not a glab/GitLab issue: with the var set, the sync targeted and filed correctly. Fix direction: repo-acting tools take the git toplevel of the cwd when it differs from the stamped root (or refuse and name both); an env override must not overwrite the stamp.

## B99. Rule gap: nothing says where a finding for ANOTHER repo goes
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-30` · issue `#110`
**Triaged from INBOX.md at the 2026-10-01 wrap.** Captured verbatim:

(2026-09-30, Sheldon agreed) **Rule gap: nothing says where a finding for ANOTHER repo goes.** `rules/CLAUDE.md` says no project is tracked from a hub on another's behalf, but not how to file a cross-repo finding, so the item above got parked in workspace's own backlog. Proposed rule for `rules/CLAUDE.md` (mechanism, not profile: identical on every machine): a finding that belongs to another repo goes into THAT repo's `INBOX.md` (commit + push there, explicit pathspec), never the current repo's backlog. The profile's machine-gated rule (watch goes to the machine's workspace hub) stays as the one exception. Prefer INBOX over filing an issue directly, because INBOX gets triaged into a full item; see next bullet.

## B100. An issue the OWNER files directly is never triaged
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-30` · issue `#111`
**Triaged from INBOX.md at the 2026-10-01 wrap.** Captured verbatim:

(2026-09-30, Sheldon asked) **An issue the OWNER files directly is never triaged.** `sync_backlog.py --pull` appends any unseen open issue as a bare BACKLOG item (no model/effort/attendance, no brief), and the orientation flags it only when `inbound` (author != owner). Issues he files himself, from his phone say, land silently as unjudged items. They should get INBOX treatment: surfaced at session start as un-triaged captures and triaged into a full item (fields, brief, or a Queue/Watching/Decisions slot), same as an INBOX bullet. Options: pull them into `INBOX.md` instead of BACKLOG, or mark pulled items `untriaged` and have the orientation list them with the inbox.

## B101. Unattended runs: three command shapes the allow list misses, and approvals don't carry over
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-30` · issue `#112`
**Triaged from INBOX.md at the 2026-10-01 wrap.** Captured verbatim:

(2026-09-30, from a workspace session on NB5) **Unattended runs: three command shapes the allow list misses, and approving them doesn't carry over.** In `cairn-afk-firing` runs, `cd .claude/worktrees/<Bnn>`, `git -C <worktree> …` (with pipes to `head`/`wc`) and a `W=…;` compound all prompted. The card offered only "Allow once", with no always option, so a tool approval is NOT stored on the scheduled task for Bash, despite the tool docs, and each unattended run would stall there. Worked around in the task prompt: one branch at a time in the main checkout (`git switch -c afk/… origin/main`), no worktrees. Durable fix for `running-a-batch.md` / `.claude/settings.json` (B84/B90 family): either allow the worktree shapes, or drop worktrees from the unattended section. Also: **a run's own "permission prompts: none" line was wrong** (it hit two), so the summary can't be the detector for stalls; B49's heartbeat is the right half. And **the scheduler's `nextRunAt` already shows the NEXT slot while today's is inside its jitter window** (17:00 + 322 s showed Friday at 17:02), which looks like a skipped run and isn't.

## B102. `sync_backlog.py` drops unknown fields from an item's metadata line on issue write-back
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-30` · issue `#113`
**Triaged from INBOX.md at the 2026-10-01 wrap.** Captured verbatim:

(2026-09-30, from a workspace session on NB5) **`sync_backlog.py` drops unknown fields from an item's metadata line when it writes the issue number back.** workspace B72's line was `… · added `2026-09-30` · **run on NB1**`; after filing #71 it read `… · added `2026-09-30` · issue `#71``, and the machine marker was gone. Harmless there (the title says NB1), but a machine gate living only in that field would be lost silently. Fix: append ` · issue `#n`` to the line as it is, rather than regenerating it from parsed fields; add a test with an unknown trailing field.

## B103. After a history rewrite on origin, the divergence banner invites the pull that undoes it
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-10-01` · issue `#114`
**Triaged from INBOX.md at the 2026-10-01 wrap.** Sibling of B87 (orient from origin when behind). NB1 application: `SBole/workspace` W25. Captured verbatim:

(2026-10-01, NB5 session) **After the B93 purge, every other clone still holds the purged history, and nothing stops it being pushed back.** NB5's `main` showed "49 ahead, 57 behind". `git log --cherry-mark main...origin/main` showed every local commit had a same-subject twin on origin, and `git diff main aff0839` was only the 6 purged lines ("France trip", `plans/2026-10-trip.md`). Fixed on NB5 by `git reset --hard origin/main`; he ran it, because the agent's `reset --hard` is denied. **Per machine:** NB1 and DeepThought must each run the same reset before ANY push from their cairn clone, unless that clone did the purge itself (the B93 CHANGELOG entry doesn't say which machine did). A `git pull` there merges the old history back in, and the next push republishes it. File one watch per hub (NB1 → `SBole/workspace`, DeepThought → `superbole/workspace`); this session couldn't, because reads outside `cairn` are blocked. **Mechanism gap (this repo):** the divergence banner says "sort out git", which reads as "pull". It should spot a history rewrite on origin (local-only commits that all have patch-equivalent or same-subject twins on origin) and say "origin was rewritten: reset to origin/main, do not pull or push", never offer a merge. Related: B87.
