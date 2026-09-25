# BACKLOG — cairn
<!-- next-id: 61 -->

Everything worth doing that is NOT in `NEXT.md`'s Queue. Unbounded and unordered —
the ordering that matters lives in the Queue, which is capped at 5 and refilled from here.

Items marked `queued` are on the Queue right now and stay listed here until the work lands.
Where the repo has GitHub Issues, `tools/sync_backlog.py` mirrors this file to them; the
file is the writer and Issues is the copy that survives a lost machine.

## B10. With NO baseline at all, the receipt reports a confident `[SKIP]` instead of "cannot tell"
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-20` · issue `#8`
Was `agent-reentry` B143 (migrated 2026-09-23). **Re-check against v1.57.0 first** — that release
added `CAIRN UNKNOWN` and reordered `verdict()` so `skipped` is tested before `unverifiable`, which
makes this defect *more* consequential, not less: a false `skipped` now always wins.

Found wrapping a project on 2026-09-20. The wrap rewrote `NEXT.md` (37 lines) and `CHANGELOG.md`
(79 lines) and committed both — verifiable with one `git show --stat`. `wrap_receipt.py --record`
printed `[SKIP] next_rewrite  NEXT.md is byte-identical to session start` and `[SKIP] changelog
CHANGELOG.md untouched`, then `CAIRN OPEN`. **There was no baseline**: the session was a `--resume`,
the `SessionStart` stamp never ran for it, and `wrap_baseline/` was created by the `--record` itself.

**The defect is in `tracked_step`, not in the missing stamp.** The two helpers disagree about "no data":
`_changed(root, {}, name)` returns **`None`** (correctly unmeasurable), but `_changed_by_session(...)`
returns `bool(changed and name in paths)` → **`False`**, because `attrib["paths"]` is `[]` rather
than `None` when attribution can see nothing. `False` is not `None`, so the `unverifiable` guard is
skipped and control reaches `put(name, "skipped", idle_detail)` — printing *"byte-identical to
session start"* as a positive claim about a comparison never made. Measured on the live tree:
`paths: []`, `commits: None`, `window: None`.

**Why it matters:** `CAIRN OPEN` is defined as actionable (*"go back and run them, then re-record"*).
Here the only way to clear it is to edit two correct files purely to move a hash. A verdict that
cannot be honestly cleared trains the reader to ignore it.

**Fix:** (1) `_changed_by_session` returns `None` when `paths` is empty AND `_changed` is `None`;
(2) gate the measuring branch on a baseline that actually loaded, not on `have_base`; (3) a receipt
with no baseline says so **once, at the top**, rather than six plausible negatives.
**Rejected:** stamping a baseline lazily inside `--record` (compares the tree to itself, all green —
worse in the dangerous direction); treating no baseline as `NOT DUE` (hides a real wrap).
**Related:** B11 (the same missing baseline, the resume/crash cause), B6 (`/clear`), B5 (siblings).

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

## B14. `fence_check.py` with no arguments checks nothing and prints a clean pass
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-09` · issue `#12`
Was `agent-reentry` B138 (migrated 2026-09-23). `fence_check.py` is `for path in sys.argv[1:]` with
**no default file set**. With no arguments it prints `fence check: 0 line(s) inside a fence that a
parser would read as structure` and **exits 0 having read no files** — byte-identical to a pass.
It shipped inside a brief's verification one-liner for two versions, so that pre-publication check
was vacuous every time it ran. (This repo's own brief passes explicit paths and is correct.)

**The fix is a default set, not a docs change.** With no arguments, check `NEXT.md`, `BACKLOG.md`,
`CHANGELOG.md`, and `INBOX.md` when present, and say which; with arguments, keep today's behaviour.
**It must print the file count it actually read** — that line is what makes a vacuous run visible.
Measured: run properly on the four parsed files it is clean; run across public docs it reports 9
hits, all deliberate format examples in `README.md`, `docs/guide.md`, `docs/file-formats.md` which no
line-start parser reads — **so the default set must NOT include docs**, or it cries wolf.

## B15. Bullet counters and `fence_check.py` don't know a bullet inside a fence isn't a bullet
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-09` · issue `#13`
Was `agent-reentry` B132 (migrated 2026-09-23). **Live incident:** an `INBOX.md` intake contract
carried four example bullets inside a fenced code block, and the file was read as **5 un-triaged
items instead of 1**. `wrap_receipt.py:_inbox_bullets()` uses `_BULLET_RE = ^\s*[-*]\s+\S` per line
(it matches `*` too, so "use asterisks" is no workaround). **And `fence_check.py` reported `0
line(s)`** on the broken file — it looks for heading- and `**Dn.`/`**Wn.`-shaped lines only. It is
not wrong about what it checks; it has no idea a bullet is structure to somebody. A check that
reports a clean zero on a broken file is worse than none — it retires the suspicion.

**Fix, preferred order:** (2) make the counters skip fenced regions — fixes every future file at
once, with the same fence tracking `fence_check.py` already has; (1) give `fence_check.py` the bullet
rule, with the list of "structures" defined in one place. Doing (1) without (2) only warns about the
trap. **Do not fix this by telling authors not to write examples** — an intake file with no example
is how the convention gets guessed wrong. (The affected repo worked around it with a table; revisit
when this lands. That repo's own PowerShell scanner has the same shape and is tracked there.)

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

**Detail for `NEXT.md` D29 and D30** (both open, both `answer: here`; migrated from the private
repo's D3 and D5, 2026-09-23):
- **D29 — letter-suffixed ids.** The parser accepts a bare `## 12.` as item 12, but `## 2b.` is
  refused, because `n` is an integer that `next_id()`, the issue mapping and `render()` all key
  off. Either letter-suffixed items are not a thing (the simplest answer, and the one file that used
  them has been normalised), or `n` becomes a string and everything keyed off it changes. **Do not
  let an agent smuggle this into a sync release.** Live cost, 2026-09-08: splitting an item couldn't
  use `a`/`b` and spent a fresh integer id instead. That cost is small, which argues for the simple
  answer.
- **D30 — one sequence per repo.** The real collision was INSIDE one repo, and a prefix wouldn't
  touch it. The private repo's `NEXT.md` open decisions and its `docs/decisions.md` rows used
  separate counters and collided on D4: two decisions, one number. **Recommendation: one sequence
  per repo.** An open decision takes the next number from the rationale record's counter and keeps
  it when answered, so a collision is impossible by construction. D29 and D30 themselves are
  numbered this way (after `docs/decisions.md` D28). **No repo prefix:** cross-repo ambiguity is
  already handled by qualifying (`cairn D30`) whenever more than one project is in play. **Billing
  codes are not ids** — see B55, whose content stays private.

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

## B23. `measure_context.py` hard-fails on any machine without `tiktoken`
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-06` · issue `#21`
Was `agent-reentry` B95 (migrated 2026-09-23). `import tiktoken` is at module level, unguarded; on a
machine without it (`pip show tiktoken` → not found, Python 3.14.0) the tool dies with
`ModuleNotFoundError` before printing anything. **Confirmed on a second machine 2026-09-07.**
`rules/CLAUDE.md`'s last rule says *"Measure with the plugin's `tools/measure_context.py` instead of
quoting"*, so the payload tells every agent to run a tool that cannot run there — leaving only a
stale quote (forbidden) or a bytes fallback. **Ruled out:** PATH/venv; the package is absent and
nothing installs it; README and docstring mention no dependency step.
**Options:** (a) guard the import, fall back to bytes-and-estimate labelled as such; (b) print an
install line and exit non-zero; (c) `requirements.txt` + README step — but the plugin has zero Python
dependencies and that is worth something. **Recommend (a), with (c) as the documented way to get
exact counts.** Blocks B24's real number.

## B24. Nothing tracks the always-loaded context budget, and the files have grown since the last trim
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-07` · issue `#22`
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

## B25. `install_rules` can delete the user's own text, and one rolling backup cannot recover it
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-06` · issue `#23` · queued
Brief: [briefs/install-rules-marker-safety.md](briefs/install-rules-marker-safety.md)
Was `agent-reentry` B104 (migrated 2026-09-23). `BEGIN = "<!-- reentry:begin"` carries **no closing
`-->`**, and `_find_block` takes `text.find(BEGIN)` — the first occurrence anywhere. The rewrite is
`existing[:start] + block + existing[end:]`, so user text **above** the block containing that literal
is deleted down to the real `END`, silently — in the one file whose contract is *"anything outside
the markers is yours"*. The refuse guard checks the shipped body, never the target file. And
`_backup()` is a **single rolling copy**, so two updates (which auto-update produces unattended)
destroy the recoverable state. **Fix:** anchor to a line start, require `-->` and a version token,
refuse rather than prepend when a `BEGIN`-looking line yields no valid block, and name the backup
with the outgoing version. `install_rules.py` has no direct test file; this item creates one.
**Do this before B26.**

## B26. Say what changed in the rules block, not just `vX → vY`
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-06` · issue `#24`
Brief: [briefs/rules-block-change-announcement.md](briefs/rules-block-change-announcement.md)
Was `agent-reentry` B101 (migrated 2026-09-23); decision row **D9**. `install_rules.py` rewrites
always-loaded, machine-wide instruction text at every `SessionStart` where the version or rendered
bytes differ, and prints only `v1.44.0 → v1.45.0`. A marketplace auto-update applied one such change
unattended before anyone read anything. **Announce, do not gate** (a `SessionStart` hook cannot
prompt; holding the old block leaves machines silently stale). A bounded added/removed/changed
summary plus the exact diff command, computed from `existing[start:end]` vs `block`, both already in
hand; the silent path stays bit-for-bit silent. Plus a block digest in `check_install.py`, reusing
`wrap_receipt._digest()`. **Depends on B25** — the summary inherits whatever boundaries it finds.

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

## B56. The GitLab write path has never run against a real server, and one known server is from 2021
`Sonnet 5` · effort `medium` · `HITL/Auto` · added `2026-09-03` · issue `#54`
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

## B57. Cursor adapter v1 — RECONCILE the hand-written copy that already exists
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-08` · issue `#55` · queued
Brief: [briefs/cursor-adapter-reconcile.md](briefs/cursor-adapter-reconcile.md) ·
Requirements: [docs/cursor-adapter-requirements.md](docs/cursor-adapter-requirements.md)
Was `agent-reentry` B123 and its Queue item 1 (migrated 2026-09-23). A hand-authored adapter is already
installed on one work laptop: `~/.cursor/skills/next/SKILL.md` (40 lines) and
`~/.cursor/skills/wrap/SKILL.md` (62 lines), written 2026-09-04, against 224 and 736 lines in the
plugin then. Its header says *"the `reentry` Claude Code plugin"* — pre-D18, ~14 versions of rules
behind. No `hooks.json`, no receipt tool, no backlog sync: a Cursor session can orient but cannot
produce a verdict, sync, or obey any rule added since. **The question is no longer what an adapter
should do — it is whether that pair is regenerated from this repo's source or stays hand-maintained
and drifts again.** Two competing copies is the condition this item exists to prevent. Zero adapter
code exists in `plugins/`. v1 shape, already decided by the requirements report: side-effect hooks in
`.cursor/hooks.json` (schema v1, flat arrays) plus an always-on Cursor rule that runs
`session_orientation.py`; not hook injection (`sessionStart.additional_context` reaching the model is
unverified and reportedly broken). `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PROJECT_DIR` are empty in a
Cursor shell. **Found alongside and NOT this:** `~/.cursor/skills-cursor/` (Cursor's built-ins), and
`AGENTS.md` files across project trees (a separate portfolio convention).

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

## B58. The sibling "behind origin" banner still names a repo whose directory is gone
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-24` · issue `#58`
Seen 2026-09-24 in `workspace` on DeepThought. `agent-reentry` had been archived and deleted from
`~/Projects` that day, yet the next SessionStart printed *"1 sibling repo is behind origin:
agent-reentry (5 behind)"*. The agent relayed that and offered a pull, and the user had to correct
it (*"I thought agent-reentry had just been moved to the recycle bin?"*). The directory really is
gone: `ls ~/Projects` has no `agent-reentry`.

**Cause:** `hooks/repo_sweep.py` works as designed. `summary_line()` reads the JSON cache that the
PREVIOUS session's detached `--refresh` wrote, and never re-checks it. The repo existed when that
cache was written, so the deletion won't show up until one more session has passed.

**Fix:** in `summary_line()`, drop any cached name whose `root.parent / name` no longer exists.
That is one `Path.exists()` per named repo (at most `MAX_NAMED`). It adds no subprocess or network
call, so the "effectively free at session start" contract holds. Add a case to the test that
covers `repo_sweep`.
**Rejected:** refreshing inline at session start. The module docstring says why that can never be
inline: the hook must not do network I/O.
**Why it matters:** a warning about a repo that is not there costs a round trip and trust in the
banner. It is also the one line the agent is told to lead with.
**Second occurrence, 2026-09-25, on a work laptop — and the scope is wider than a gone directory.**
The same banner named the deleted repo AND two siblings that exist, as 1 and 7 behind; a live
`git fetch` + `rev-list` showed both 0/0 (one had been pushed from that machine an hour earlier).
The user called it "the second time today this information is stale." So `exists()` alone is not
enough. Also: (a) print the cache's age on the line (`as of 14:02` / `from last session`), since
the JSON already holds `at`; (b) for each named repo, re-count `HEAD..@{u}` against the LOCAL
remote-tracking ref (one `git rev-list`, no fetch, no network) and drop it when it reads 0. That
keeps the no-network contract and catches the "already pulled/pushed since" case.

## B59. Skills and rules still tell the agent to run bare `python "$CLAUDE_PLUGIN_ROOT/…"`
`Opus 5` · effort `high` · `AFK/Auto` · added `2026-09-25` · queued
Brief: [briefs/skill-python-calls.md](briefs/skill-python-calls.md). Pulled to refill the Queue at the v1.61.0 wrap.
v1.61.0 (D31) moved every HOOK onto `hooks/run.sh`, but the text the agent reads still names
the interpreter directly. There are 17 call sites across `skills/` and `rules/CLAUDE.md`:
`wrap_receipt.py` 4, `archive_offer.py` 3, `measure_context.py` 3, and one each for `backlog_file`,
`issues_backlog`, `item_start`, `session_orientation`, `check_repos`, `label_backlog` and `sync_backlog`
(`grep -rn 'python "' plugins/cairn/skills plugins/cairn/rules`). On stock Ubuntu each one fails
with `python: not found`.

It was left out of the hook fix on purpose. That failure is VISIBLE: it happens in the agent's
own shell, and an agent recovers by trying `python3`. The hook failure was silent, and fixing it
was the aim line. The skill failure still costs a wasted tool call and a moment of doubt at every
wrap on Linux, and the `--record` step is REQUIRED.

**Options:** (a) rewrite them as `sh "$CLAUDE_PLUGIN_ROOT/hooks/run.sh" wrap_receipt.py --check`.
That is longer, and the rules are always loaded, so measure the token cost with
`tools/measure_context.py` before choosing it. (b) Add one line to `rules/CLAUDE.md`: "`python`
below means your Python 3: `python3` on Linux/macOS". Cheap, but it's prose, and prose is what
agents reason past. (c) Both.

**Measured 2026-09-25, and it widens the item:** `$CLAUDE_PLUGIN_ROOT` is **UNSET** in the
agent's Bash tool (NB1, desktop app, `echo ${CLAUDE_PLUGIN_ROOT:-unset}` → `unset`). So every
one of these 17 call sites expands to `python "/hooks/…"` on EVERY platform, not just Linux, and
agents have been silently substituting a path they found some other way. The interpreter name is the
smaller half of this.

## B60. Native Windows without Git for Windows can't run any hook since v1.61.0
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-25`
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
