**Stage 1 (forensic fields in the baseline, and a read-only list of the baselines that do exist when this session has none) is AFK-ready as written below: it changes no verdict. Stage 2 (adopting a baseline after a resume) needs the reviewer's decision on Q1 to Q4 and is not AFK.**

# B11 — a baseline keyed only by session id does not survive a crash-and-resume: groom brief

Backlog: `BACKLOG.md` B11 (issue #9), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-06`.
Written by the scheduled firing on 2026-11-14 against `origin/main` at `4a95fe8`. Every file:line
below was read at that commit.

**Prior decisions:** D21 (provenance from git's reflog AND the content hash; re-stamping after a
pull rejected), D26 (`UNKNOWN` is its own verdict), D36 (the archive guard judges only roots with
this session's own baseline), D38 (no usable baseline is `UNKNOWN`, tested first; a lazy stamp
inside `--record` rejected; it names B11 as "the prevention that makes this rare"). Also the
reverted machine-global stamp cited at `plugins/cairn/hooks/wrap_receipt.py:62-64` and
`reentry_state.py:136-151` (the predecessor repo's B72, not this repo's B72): two concurrent
sessions must never read each other's state.

## The ask, as filed

Half shipped: `CAIRN UNKNOWN` (v1.57.0) is the honest token for a session with no baseline. What
remains is (2): a crashed-and-resumed session should still get a real verdict. Candidates in the
entry: key the baseline by project plus a wall-clock window, or, finding none for this id, adopt
the most recent one whose head is an ancestor of HEAD and say so in the table. Never adopt
silently. Never stamp late. An unexplained anomaly: 25 minutes before the failing wrap, `--check`
from the same shell found a baseline; later the shell's id had none.

Related: B6 (`/clear` gives a new id and no stamp: same mechanism, different trigger), B83 (Cursor:
key on `CURSOR_CONVERSATION_ID`, Queue item 5), B10 (shipped: `UNKNOWN` before everything else).

## What exists today, with evidence

| Piece | Where | What it means for B11 |
|---|---|---|
| The stamp | `wrap_receipt.py:280-332` `stamp_baseline(root, session="", force=False)`: writes `wrap_baseline/<session>.json` = `{schema: 2, at, head, files}` under `state_dir(root)`; write-once per id (`:315-316`) | One file per id. The body records nothing about WHICH event stamped it or what id the hook payload carried, so a stranded file cannot be traced afterwards. That is why the anomaly was "not chased": there was nothing on disk to chase it with. |
| The id the stamp uses | `wrap_receipt.py:256-270` `session_id()`: `CLAUDE_CODE_SESSION_ID`, else `CLAUDE_SESSION_ID`, from the process ENVIRONMENT; `""` inside Cursor | The hook stamps under the hook process's env id. |
| The id the hook was told | `session_orientation.py:943`: `_SESSION_ID = event["session_id"]` from the SessionStart payload | Read, used for the open-item check (`:743`), and **not** passed to the stamp: `:1028` calls `wrap_receipt.stamp_baseline(root)` with no session, so the env id wins. If the env id and the payload id ever differ, the stamp goes under one and nothing records the other. Not measured either way. |
| When the stamp runs | `hooks/hooks.json:5` matcher `startup|resume`; `session_orientation.py:947` returns True for `None`, `startup`, `resume` | A **resume does stamp**. Write-once protects a resume under the SAME id. A resume under a NEW id stamps a fresh baseline at the resume moment, which is a mid-session snapshot: work done before the crash then reads as unchanged since "session start". That is the late stamp the entry says cannot be done, reached by the normal path. Whether a resume keeps or changes the id is not measured in this repo. |
| The read | `wrap_receipt.py:419-431` `baseline()`: only `<this id>.json`, never another session's | Correct for the concurrency constraint. Means a stranded file is invisible to the receipt. |
| Validity | `wrap_receipt.py:434-455` `_usable()`: needs `files` and a positive `at` | An adopted baseline would pass through the same gate. |
| Pruning | `wrap_receipt.py:246-253`, `BASELINE_TTL_DAYS = 7` (`:157`) | The stranded files from the incident (13 at the time) live a week, so a candidate list has material to show. |
| The verdict | `wrap_receipt.py:1010-1047`: no usable baseline returns `UNKNOWN` first | Unchanged by stage 1. |
| The printed note | `wrap_receipt.py:1189-1195`: "SessionStart never ran for it here (a --resume or a crash-restart)" | Partly wrong: SessionStart DOES run on `resume` (`hooks.json:5`). What fails is that it stamped under an id this shell does not carry, or (if the resumed id is new) stamped too late. Stage 1 fixes the wording. |
| A per-session record that already exists | `reentry_state.py:133-172` `_stamp_session_root()`: `_sessions/<id>.json` = `{root, at}` on every hook call | A second place that keys on the env id. Not a baseline; noted because Q2's lineage idea could reuse its directory. |

## Stage 1: make the failure traceable (AFK)

Fields line to paste under a new entry (or under B11 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: `plugins/cairn/hooks/wrap_receipt.py`, `plugins/cairn/hooks/session_orientation.py`,
`plugins/cairn/tools/test_wrap_receipt.py`. A payload change: the routine version bump goes to the
attended pass. No verdict changes, no new file written anywhere new.

1. `stamp_baseline(root, session="", force=False, meta=None)`. When `meta` is a dict, merge these
   keys into the body, each cut to 256 characters; a value that is not a string is dropped, never
   coerced, and no other key is accepted (so `meta` can never overwrite `files`, `at` or `head`): `source` (the SessionStart
   `source`), `payload_session` (the payload's `session_id`), `env_session` (what `session_id()`
   returned), `transcript` (the payload's `transcript_path`). Bump `BASELINE_SCHEMA` to 3. Readers
   ignore unknown keys already (`_usable()` reads only `files` and `at`), so schema-2 files keep
   working. `--stamp-baseline` passes `meta={"source": "manual"}`.
2. `session_orientation._is_reentry_moment()` also stashes `source` and `transcript_path` in two
   new module globals beside `_SESSION_ID`. `main()` at `:1028` passes
   `meta={"source": ..., "payload_session": _SESSION_ID, "env_session": wrap_receipt.session_id(),
   "transcript": ...}`. The stamp still goes under the env id, exactly as today. Do not change the
   key in stage 1: which id to key on is Q1.
3. A read-only `candidates(root, session)` in `wrap_receipt.py`: every `*.json` in this root's
   `wrap_baseline/` other than this session's, newest `at` first, at most 5, each as
   `{id, at, head, source, payload_session}` (missing keys as `""`). Never raises; `[]` on any error.
   Reach the directory through `_baseline_dir(root)` as `baseline()` does; that call can create an
   empty `wrap_baseline/` (as `baseline()` already can), and nothing else may be written. Shown only
   when this process has a session id: a plain terminal has no "this session" to compare against,
   and its note already says to run from inside a session.
4. In `_print_receipt`, inside the existing `if body.get("session"):` branch of the no-baseline note
   (`:1189-1195`): replace "or SessionStart never ran for it here (a --resume or a crash-restart)"
   with "or SessionStart stamped this project under a different session id (a --resume or a
   crash-restart can do that)". Then, when `body["candidates"]` is non-empty, print
   `  Baselines that DO exist for this project (not used: they belong to other session ids):`
   and one line each: `    <id[:12]>  stamped <YYYY-MM-DD HH:MM>  source <source or ?>  head <head[:8]>`.
   `--check` and `record()` both put `candidates` in the body only when the baseline is missing.
   The receipt JSON keeps them too (forensics). The verdict, the token and the exit code are unchanged.

Tests (fixtures only: a temp `CLAUDE_CONFIG_DIR`, a temp git repo, env ids set per test; never the
real `~/.claude/`):

1. `stamp_baseline(..., meta={...})` writes `schema: 3` and the four keys; a 300-character value is
   cut to 256; a non-string value is dropped; `meta={"files": "x", "at": "y"}` leaves `files` and
   `at` as the stamp computed them.
2. Without `meta`, the body has no `source` key and still passes `_usable()`.
3. A schema-2 fixture (no meta keys) is still read and measured as before.
4. `candidates()` lists other ids newest first, caps at 5, excludes this session's own file, and
   returns `[]` for a missing directory and for a corrupt JSON file among good ones (the good ones
   still listed).
5. `--check` with env id A and only a baseline for id B: verdict `UNKNOWN`, exit 1 (as today), and
   the output names B's id prefix and its `source`.
6. `--check` with a baseline for this id: no candidate lines printed, even when other ids exist.
7. The no-baseline note no longer contains "never ran".
8. Orientation: run `session_orientation.main()` with a payload `{"source": "resume",
   "session_id": "P", "transcript_path": "<tmp>/t.jsonl"}` and env id `E`: the baseline file is
   `E.json`, and it carries `payload_session: "P"`, `env_session: "E"`, `source: "resume"`. Feed the
   payload the way `test_item_open.py:70` already feeds `session_orientation` a SessionStart
   payload (`subprocess.run(..., input=json.dumps(...))`).
9. `--stamp-baseline` writes `source: "manual"`.

Done: those tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, and the
suite's "no leak into the real state dir" line still prints.

What stage 1 buys: the next crash-and-resume leaves a file that answers the entry's anomaly (did the
env id and payload id differ, and did the resume stamp a new id), and the receipt shows the person
running the wrap which baselines exist instead of only saying one is missing.

## Questions for the reviewer (stage 2, adoption)

### Q1. Which id should the stamp key on?

- **A. Keep the env id (today), and stamp a second file under the payload id when the two differ.**
  Both are session-start snapshots taken at the same instant, so neither is a late stamp. Costs a
  second small file in the rare case.
- **B. Switch to the payload id.** The shell that runs `--record` sees only the env id, so this
  breaks every ordinary wrap unless the two always agree.
- **C. Decide after stage 1's data.** Two weeks of forensic fields say whether they ever differ.

Recommendation: **C, then A if they ever differ.** It costs nothing to wait, and stage 1 is the only
way to know.

### Q2. A resume under a new id: how does the new id find its predecessor?

- **A. Lineage from the transcript.** At SessionStart(`resume`), read the first lines of
  `transcript_path`: if the resumed transcript carries the earlier session's id (unmeasured here;
  a probe is the first step), copy that id's baseline to the new id with an `inherited_from` key.
  This copies the ORIGINAL snapshot, so it is not a late stamp, and it is exact: no other session
  can be in that transcript.
- **B. Adopt by ancestry at wrap time** (the entry's candidate): no baseline for this id, so take
  the newest `candidate` whose `head` is an ancestor of HEAD and whose `at` is within N hours.
  Two concurrent sessions in one project share one reflog and one HEAD, so this can adopt the
  other session's snapshot and credit its work, which is the reverted machine-global failure at
  project scope.
- **C. Key by project plus a time window.** Same concurrency failure as B, applied to every session,
  not only resumed ones.
- **D. Do not adopt; stage 1's candidate list is the end state.** `UNKNOWN` stays the verdict, the
  person sees the stranded baseline and can judge.

Recommendation: **A if the probe shows the old id is in the resumed transcript, else D.** B and C
are both the shape D38's row and the B72 revert already refused.

### Q3. If a baseline is adopted, can the verdict still be `SET`?

- **A. Yes, with the table saying `baseline inherited from <id>, stamped <time>`** on the first line,
  and the receipt JSON carrying `inherited_from`. Lineage (Q2 A) is exact, so the measurement is
  as good as an own baseline.
- **B. No: an adopted baseline can reach `OPEN` or `UNKNOWN`, never `SET`.** Safer under Q2 B, and it
  means a resumed session can never earn a clean verdict.

Recommendation: **A under Q2 A; B under Q2 B** (if B is chosen against the recommendation above).

### Q4. One design for B11, B6 and B83?

All three are "the shell's id has no baseline": a resume (B11), a `/clear` (B6, which also needs
`clear` in the matcher), and Cursor (B83, a different id variable). Planning them separately risks
three adoption rules.

- **A. One plan, three triggers**, with Q2's lineage rule as the shared mechanism and B83's
  `CURSOR_CONVERSATION_ID` as a keying change only.
- **B. Separately**, in Queue order (B83 is Queue item 5 today).

Recommendation: **A**, attached to B83's planning session since it is already queued.

## Out of scope

- Any change to `verdict()`'s ordering (D38 stands).
- Stamping a baseline anywhere other than SessionStart or the explicit `--stamp-baseline`.
- The `clear` matcher change (B6) and the Cursor id (B83), except as Q4 names them.

## Side notes for the attended pass

1. The no-baseline note's "SessionStart never ran for it here (a --resume ...)" (`wrap_receipt.py:1193-1194`)
   contradicts `hooks.json:5`, which runs SessionStart on `resume`. Stage 1 step 4 fixes it; if
   stage 1 is not taken, that one sentence is worth fixing on its own.
2. B11's own entry says "`session_id()` reads `CLAUDE_CODE_SESSION_ID` first" without saying it is
   the hook PROCESS environment; the payload id at `session_orientation.py:943` is a second source the
   entry does not mention. Worth one clause in the entry when it is narrowed.
