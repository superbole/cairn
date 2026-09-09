#!/usr/bin/env python3
"""Test for `validate_next.py` (B36), against throwaway fixtures only.

    python plugins/cairn/tools/test_validate_next.py

WHY FIXTURES, NOT THE REAL PORTFOLIO
-------------------------------------
`validate_next.py` was written and tuned against real `NEXT.md` files under `~/Projects` (see the
dossier for the actual, pasted output) -- that is where the two regressions below were CAUGHT,
not where they are guarded. A test that read those files would be non-deterministic (today's
result depends on whatever anyone last wrote in nine other repos) and would stop protecting
anything the day someone fixes those files by hand. So every case here builds its own throwaway
`NEXT.md` under a temp directory.

TWO REAL REGRESSIONS THIS FILE EXISTS TO PIN DOWN
---------------------------------------------------
1. `session_orientation._split_next` truncates the Queue at `MAX_NEXT_LINES` (24) for its own,
   correct reason (SessionStart shows one screen) -- and this repo's own 5-item Queue runs past
   that, so calling it unmodified silently validated only the first two items. Section 3 below
   pins the fix (`_split_next_full`, which lifts the cap for the duration of one call).
2. `backlog_file._ATTEND_RE`'s tail assertion requires `·` or end-of-line after the mode --
   true almost everywhere, false in `workspace`'s own `NEXT.md`, whose "portfolio meta" queue
   lines put `` `HITL/Auto` — brief: ... `` right after the mode with an em-dash, no `·`.
   Unmodified, this reported "missing attendance/mode" on all five of that file's real, correct
   items. Section 4 pins the em-dash fix.

Also covers the missing-field/contradiction findings themselves (the actual point of B36), the
`check after` must-be-last rule, and that an unrecognised flag stops in argparse rather than
falling through to checking the default project (the same regression class `test_sync_flags.py`
and `test_check_exits.py` already guard -- see `tools/test_sync_flags.py`'s own docstring for the
incident).

SECTIONS 14-20 (B79 / B81) -- added by the lane-C validate/banner pass, 2026-09-06
------------------------------------------------------------------------------------
14-15 pin `check_duplicate_ids` (B79): two entries sharing a `Wn` or `Dn` are reported by name,
never silently merged or resolved. 16-20 pin B81's addition to `session_orientation.py`'s
`_divergence_warning` -- the banner now names NEXT.md/BACKLOG.md/CHANGELOG.md specifically when
the commits making up a divergence touch one of them, using real throwaway git fixtures (a bare
`origin` plus clones, same pattern as `test_repo_sweep.py`/`test_empty_queue_diverged.py`; no
network, no real checkout). This file is the only place lane C could unit-test that change --
`test_empty_queue_diverged.py`, the existing integration test for the same function, belongs to a
different lane in this batch -- so it exercises `session_orientation._divergence_warning` and
`._numbering_hazard_files` directly via `vn.so`, per the batch's own hard rule to prove the
changed path fails soft: a missing root (19), a root that exists but is not a git repository at
all -- the practical Windows stand-in for "unreadable", since simulating a permission-denied file
is not reliable on this machine (19), and a repo with no `origin` at all (18).
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_next as vn                              # noqa: E402


def _git(cwd, *args):
    r = subprocess.run(("git", *args), cwd=cwd, capture_output=True, text=True,
                       env={"GIT_TERMINAL_PROMPT": "0", **os.environ})
    if r.returncode != 0:
        raise RuntimeError(f"git {args} failed in {cwd}: {r.stderr}")
    return r.stdout.strip()


def _make_bare(base, name):
    p = base / name
    _git(base, "init", "--bare", "-q", str(p))
    # Force the branch name regardless of this machine's `init.defaultBranch` -- same reasoning
    # as `test_repo_sweep.py`'s own helper: left to ambient config, a clone of the still-empty
    # bare repo can pick a different default branch than the one later pushes create.
    _git(p, "symbolic-ref", "HEAD", "refs/heads/main")
    return p


def _make_clone(base, origin, name):
    p = base / name
    _git(base, "clone", "-q", str(origin), str(p))
    _git(p, "config", "user.email", "t@t.com")
    _git(p, "config", "user.name", "t")
    return p


def _commit_and_push(repo, fname, content="x"):
    (repo / fname).write_text(content, encoding="utf-8")
    _git(repo, "add", fname)
    _git(repo, "commit", "-q", "-m", f"add {fname}")
    _git(repo, "push", "-q", "origin", "HEAD:main")

fails = []


def check(label, got, want):
    ok = got == want
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def exits(label, fn, code):
    try:
        fn()
    except SystemExit as e:
        check(label, e.code, code)
        return
    check(label, "no SystemExit", code)


def write(body: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="validate-next-"))
    (tmp / "NEXT.md").write_text(body, encoding="utf-8")
    return tmp


def problems_only(lines):
    """Drop the header line `validate()` returns; keep just the `  - ...` findings."""
    return [ln[4:] for ln in lines if ln.startswith("  - ")]


print("1. no NEXT.md here -- nothing to check, and that is success, not a gap")
tmp_empty = Path(tempfile.mkdtemp(prefix="validate-next-empty-"))
ok, lines, counts = vn.validate(tmp_empty)
check("ok", ok, True)
check("says so", "nothing to check" in lines[0], True)
check("no counts for a file that doesn't exist", counts, {})

print("\n2. a clean file, real convention on both lists (queue bare, watch backticked)")
CLEAN = """# NEXT — fixture

## Queue

1. **First item** — Opus 5 · high · HITL/Plan
   Brief: none.
2. **Second item** — Sonnet 5 · medium · AFK/Auto

## Watching

**W1. A watch** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-01` · check after `2026-09-01`

---
footer line, ignored
"""
ok, lines, counts = vn.validate(write(CLEAN))
check("clean file: ok", ok, True)
check("clean file: 2 queue items counted", counts["queue_items"], 2)
check("clean file: 1 watch counted", counts["watches"], 1)
check("clean file: no problems", counts["problems"], 0)

print("\n3. B36's own defect -- a queue item and a watch with NO attendance/mode field at all")
MISSING_ATTEND = """# NEXT — fixture

## Queue

1. **No mode here** — Sonnet 5 · medium

## Watching

**W1. No mode either** — `Opus 5` · effort `high` · added `2026-08-01` · check after `2026-09-01`
"""
ok, lines, counts = vn.validate(write(MISSING_ATTEND))
problems = problems_only(lines)
check("not ok", ok, False)
check("queue item flagged missing attendance/mode",
      any("Queue item 1" in p and "missing attendance/mode" in p for p in problems), True)
check("watch flagged missing attendance/mode",
      any("Watch W1" in p and "missing attendance/mode" in p for p in problems), True)
check("queue item's model/effort are NOT flagged -- they really are present",
      any("Queue item 1" in p and "missing model" in p for p in problems), False)

print("\n4. missing model, missing effort, each reported on its own")
MISSING_MODEL_EFFORT = """# NEXT — fixture

## Queue

1. **No model** — high · HITL/Auto
2. **No effort** — Opus 5 · HITL/Auto
"""
ok, lines, counts = vn.validate(write(MISSING_MODEL_EFFORT))
problems = problems_only(lines)
check("item 1 missing model", any("Queue item 1" in p and "missing model" in p for p in problems), True)
check("item 2 missing effort", any("Queue item 2" in p and "missing effort" in p for p in problems), True)
check("item 1 does not ALSO claim missing effort (it has one)",
      any("Queue item 1" in p and "missing effort" in p for p in problems), False)

print("\n5. the two forbidden contradictions, queue and watch")
CONTRADICTIONS = """# NEXT — fixture

## Queue

1. **Backwards A** — Opus 5 · high · AFK/Plan
2. **Backwards B** — Sonnet 5 · medium · HITL/Bypass

## Watching

**W1. Backwards C** — `Opus 5` · effort `high` · `AFK/Plan` · added `2026-08-01` · check after `2026-09-01`
"""
ok, lines, counts = vn.validate(write(CONTRADICTIONS))
problems = problems_only(lines)
check("AFK/Plan flagged on item 1", any("Queue item 1" in p and "AFK/Plan" in p for p in problems), True)
check("HITL/Bypass flagged on item 2", any("Queue item 2" in p and "HITL/Bypass" in p for p in problems), True)
check("AFK/Plan flagged on the watch", any("Watch W1" in p and "AFK/Plan" in p for p in problems), True)

print("\n6. a watch missing `added`, and one with no parseable `check after`")
WATCH_GAPS = """# NEXT — fixture

## Watching

**W1. No added date** — `Opus 5` · effort `high` · `AFK/Auto` · check after `2026-09-01`
**W2. No check after** — `Opus 5` · effort `high` · `AFK/Auto` · added `2026-08-01`
"""
ok, lines, counts = vn.validate(write(WATCH_GAPS))
problems = problems_only(lines)
check("W1 missing added", any("Watch W1" in p and "missing `added`" in p for p in problems), True)
check("W2 no parseable check after",
      any("Watch W2" in p and "no parseable" in p for p in problems), True)

print("\n7. `check after` must be LAST -- flagged when added comes after it instead")
CHECK_AFTER_ORDER = """# NEXT — fixture

## Watching

**W1. Out of order** — `Opus 5` · effort `high` · `AFK/Auto` · check after `2026-09-01` · added `2026-08-01`
"""
ok, lines, counts = vn.validate(write(CHECK_AFTER_ORDER))
problems = problems_only(lines)
check("flagged as out of order", any("not the LAST field" in p for p in problems), True)

print("\n8. an unrecognised mode is a DIFFERENT complaint from a missing one")
BAD_MODE = """# NEXT — fixture

## Queue

1. **Weird mode** — Opus 5 · high · HITL/Sometimes
"""
ok, lines, counts = vn.validate(write(BAD_MODE))
problems = problems_only(lines)
check("flagged as not recognised, not as missing",
      any("not one of Auto/Manual/Accept Edits/Plan/Bypass" in p for p in problems), True)
check("not ALSO reported as missing", any("missing attendance/mode" in p for p in problems), False)

print("\n9. REGRESSION -- the Queue truncation cap must not hide items past line 24")
many = ["# NEXT — fixture", "", "## Queue", ""]
for i in range(1, 11):
    many.append(f"{i}. **Item {i}** — Sonnet 5 · medium · AFK/Auto")
    many.append(f"   Brief: some note that pads this out on its own continuation line, item {i}.")
    many.append(f"   A second continuation line, so ten items alone clear the old 24-line cap.")
MANY_ITEMS = "\n".join(many) + "\n"
ok, lines, counts = vn.validate(write(MANY_ITEMS))
check("all ten items were actually counted, not truncated at MAX_NEXT_LINES",
      counts["queue_items"], 10)
check("and the file is clean (every one of the ten really is well-formed)", ok, True)

print("\n10. REGRESSION -- workspace's em-dash-after-mode queue convention is NOT a false positive")
EM_DASH_STYLE = """# NEXT — fixture (portfolio meta style)

## Queue

1. **project-x** — some context here — `Sonnet 5` · effort `medium` · `HITL/Auto` — brief: `BACKLOG.md` item 7
"""
ok, lines, counts = vn.validate(write(EM_DASH_STYLE))
check("no false 'missing attendance/mode' on the em-dash-after-mode style", ok, True)
check("one queue item counted", counts["queue_items"], 1)

print("\n11. --json emits parseable structure with the same verdict")
import json                                             # noqa: E402
import io                                                # noqa: E402
import contextlib                                        # noqa: E402

clean_root = write(CLEAN)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = vn.main(["--json", str(clean_root)])
check("exit 0", rc, 0)
payload = json.loads(buf.getvalue())
check("json ok true", payload["ok"], True)
check("json counts present", payload["queue_items"], 2)

print("\n12. a NEXT.md path handed in directly resolves to its own parent directory")
next_file = clean_root / "NEXT.md"
check("path-to-file resolves like path-to-dir",
      vn._resolve_root(str(next_file)) == vn._resolve_root(str(clean_root)), True)

print("\n13. --help and an unknown flag stop in argparse, before checking anything")
exits("--help exits 0", lambda: vn.main(["--help"]), 0)
exits("-h exits 0", lambda: vn.main(["-h"]), 0)
exits("--bogus-flag exits 2", lambda: vn.main(["--bogus-flag"]), 2)

print("\n14. B79 -- duplicate Wn/Dn ids are reported, naming both titles, never silently merged")
DUPLICATE_IDS = """# NEXT — fixture

## Queue

## Decisions

**D1. First answer needed** — answer: `ask the spec` · added `2026-08-09`
**D1. Second, different, question** — answer: `here` · added `2026-08-20`

## Watching

**W1. First watch** — `Opus 5` · effort `high` · `AFK/Auto` · added `2026-08-01` · check after `2026-09-01`
**W1. Second watch, different trigger** — `Sonnet 5` · effort `medium` · `HITL/Auto` · added `2026-08-05` · check after `2026-09-10`
**W2. Unique, not fighting with anything** — `Opus 5` · effort `high` · `AFK/Auto` · added `2026-08-01` · check after `2026-09-01`
"""
ok, lines, counts = vn.validate(write(DUPLICATE_IDS))
problems = problems_only(lines)
check("not ok", ok, False)
check("W1 duplicate reported once, naming both titles",
      any(p.startswith("Watch id W1 used 2 times") and "First watch" in p and "Second watch" in p
          for p in problems), True)
check("D1 duplicate reported once, naming both titles",
      any(p.startswith("Decision id D1 used 2 times") and "First answer needed" in p
          and "Second, different, question" in p for p in problems), True)
check("W2, the non-duplicate, is not reported as fighting over anything",
      any(p.startswith("Watch id W2") for p in problems), False)
check("counts still count all 2 decisions and 3 watches -- duplicates are reported, not dropped",
      (counts["decisions"], counts["watches"]), (2, 3))

print("\n15. B79 -- no duplicates is still a clean file (regression: the new check adds no noise)")
ok, lines, counts = vn.validate(write(CLEAN))
check("clean file, no decisions at all: still ok", ok, True)
check("clean file: 0 decisions counted, not an error", counts["decisions"], 0)
check("clean-file message now also says no id was used twice",
      "no Wn/Dn used twice" in lines[0], True)

print("\n16. B81 -- the divergence banner names the file when it is among the diverging commits")
tmp16 = Path(tempfile.mkdtemp(prefix="validate-next-hazard-"))
origin16 = _make_bare(tmp16, "origin.git")
behind16 = _make_clone(tmp16, origin16, "behind")
_commit_and_push(behind16, "NEXT.md", "# NEXT — fixture\n\n## Queue\n")
# Advance origin without `behind16` knowing, via a separate pushing clone -- same technique as
# `test_repo_sweep.py`'s `behind_two` and `test_empty_queue_diverged.py`'s `_pusher`. This push
# is the one that touches NEXT.md a second time, which is the hazard.
pusher16 = _make_clone(tmp16, origin16, "_pusher")
_commit_and_push(pusher16, "NEXT.md",
                 "# NEXT — fixture\n\n## Queue\n\n1. **New item** — Sonnet 5 · medium · AFK/Auto\n")
msg16 = vn.so._divergence_warning(behind16)
check("banner fires (behind origin)", msg16 is not None and "BEHIND origin" in msg16, True)
check("banner names NEXT.md specifically", "NEXT.md" in (msg16 or ""), True)
check("banner states the meaning, near-verbatim from the B81 brief",
      "published items or watches you cannot see" in (msg16 or ""), True)

print("\n17. B81 -- ordinary divergence that never touches a numbering file stays plain")
tmp17 = Path(tempfile.mkdtemp(prefix="validate-next-nohazard-"))
origin17 = _make_bare(tmp17, "origin.git")
behind17 = _make_clone(tmp17, origin17, "behind")
_commit_and_push(behind17, "seed.txt")
pusher17 = _make_clone(tmp17, origin17, "_pusher")
_commit_and_push(pusher17, "unrelated.txt")
msg17 = vn.so._divergence_warning(behind17)
check("banner fires (behind origin)", msg17 is not None and "BEHIND origin" in msg17, True)
check("no numbering-hazard sentence when nothing touched NEXT/BACKLOG/CHANGELOG",
      "published items or watches you cannot see" in (msg17 or ""), False)

print("\n18. B81 -- no git remote at all: no crash, plain None, the pre-existing contract")
local_only18 = Path(tempfile.mkdtemp(prefix="validate-next-noremote-"))
_git(local_only18, "init", "-q", "-b", "main")
_git(local_only18, "config", "user.email", "t@t.com")
_git(local_only18, "config", "user.name", "t")
(local_only18 / "f.txt").write_text("x", encoding="utf-8")
_git(local_only18, "add", "f.txt")
_git(local_only18, "commit", "-q", "-m", "init")
msg18 = vn.so._divergence_warning(local_only18)
check("no remote -> None, not a crash", msg18, None)

print("\n19. B81 -- _numbering_hazard_files never raises against a broken/missing root")
missing19 = Path(tempfile.mkdtemp(prefix="validate-next-missing-")) / "does_not_exist"
not_a_repo19 = Path(tempfile.mkdtemp(prefix="validate-next-notrepo-"))   # exists, no .git at all
raised = False
try:
    hazard_missing = vn.so._numbering_hazard_files(missing19, "main", 1, 0)
    hazard_notrepo = vn.so._numbering_hazard_files(not_a_repo19, "main", 1, 0)
except Exception:
    raised = True
    hazard_missing = hazard_notrepo = None
check("never raises against a nonexistent cwd or a real dir that is not a git repo at all",
      raised, False)
check("nonexistent cwd reports no hazard rather than guessing", hazard_missing, set())
check("no-git-repo-at-all reports no hazard rather than guessing", hazard_notrepo, set())

print("\n20. B81 -- with nothing to compare (both zero), no git is even invoked")
hazard20 = vn.so._numbering_hazard_files(Path(r"C:\definitely\not\a\real\path"), "main", 0, 0)
check("behind=ahead=0 short-circuits to empty set", hazard20, set())

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
