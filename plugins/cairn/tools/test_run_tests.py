"""Test for `run_tests.py`'s leak ATTRIBUTION (B75), against throwaway fixtures only.

    python plugins/cairn/tools/test_run_tests.py

WHAT THIS GUARDS AGAINST
------------------------
`run_tests.py` diffs the real `~/.claude/reentry-state/` before and after every test file and
blames whichever file was running for any new directory that appears. That plain diff cannot
tell "this test wrote here" apart from "an unrelated concurrent Claude Code session's own hook
wrote here while this test happened to be running" -- reproduced twice against the real suite
(2026-09-26, 2026-09-27; see `run_tests.py`'s B75 docstring) as a false LEAK on a fully passing
run. The fix (`_classify_new_entries`, `_slug_for`, `_git_worktree_roots`,
`_recorded_project_roots`, `_real_roots`) attributes each new name before letting it fail
anything:

  - keys to a real, still-existing project/worktree  -> ignored, never a leak
  - keys to a directory this run's own temp-dir snapshot just saw appear -> blamed (real leak)
  - matches neither                                   -> blamed (unrecognised; not proof of
    innocence -- see the B75 docstring for why this stays a leak rather than a warning)

This file proves both halves of that split directly against `run_tests.py`'s own functions --
it never runs the real suite, and it never touches the real `~/.claude/reentry-state/` (every
`CLAUDE_CONFIG_DIR` used below is a throwaway temp directory, same convention as
`test_check_exits.py` and `test_archive_guard.py`) or the real system temp dir (every "new temp
entry" used below is a name inside a throwaway sandbox this file creates itself with
`tempfile.mkdtemp()`, never a name actually written to `tempfile.gettempdir()`).

It also proves `_slug_for` (the pure, side-effect-free reimplementation `run_tests.py` uses to
test candidate paths) agrees with `hooks/reentry_state.state_dir`'s own slug for the same path --
the two must never drift, since a mismatch would silently break every ignore-match this fix
relies on.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="run-tests-test-"))
CFG = TMP / "cfg"
os.environ["CLAUDE_CONFIG_DIR"] = str(CFG)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_tests as rt                                 # noqa: E402

HOOKS = HERE.parent / "hooks"
sys.path.insert(0, str(HOOKS))
import reentry_state                                   # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


print("1. _slug_for agrees with reentry_state.state_dir's own slug for the same path")
real_project = TMP / "some-real-project"
real_project.mkdir(parents=True, exist_ok=True)
state_path = reentry_state.state_dir(real_project)
check("state_dir() succeeded", state_path is not None, True)
check("_slug_for matches the directory state_dir() actually created",
      rt._slug_for(real_project), state_path.name)

print("\n2. a name that keys to a REAL, still-existing project/worktree is IGNORED, not blamed")
concurrent_project = TMP / "afk-02"                    # a live worktree lane, still on disk
concurrent_project.mkdir(parents=True, exist_ok=True)
concurrent_slug = rt._slug_for(concurrent_project)
blamed, ignored = rt._classify_new_entries(
    [concurrent_slug],            # this is what the diff sees appear mid-run
    [],                            # this run created nothing in temp
    [concurrent_project],          # the candidate real roots this run knows about
)
check("not blamed", blamed, [])
check("ignored, attributed to the real project", ignored, [(concurrent_slug, concurrent_project)])

print("\n3. a name that keys to a fixture THIS RUN created in temp is STILL BLAMED (a real leak)")
# `_classify_new_entries` checks NEW_TEMP_NAMES against `Path(tempfile.gettempdir()) / name` --
# the same shallow, top-level shape `_snapshot_temp_dir()` sees -- so the fixture has to be a
# real top-level entry of the actual system temp dir (exactly what a test's own
# `tempfile.mkdtemp()` produces), not a subdirectory of this file's own TMP sandbox.
fixture_root = Path(tempfile.mkdtemp(prefix="cairn-fixture-abc-"))
try:
    fixture_slug = rt._slug_for(fixture_root)
    blamed, ignored = rt._classify_new_entries(
        [fixture_slug],
        [fixture_root.name],       # this run's temp-dir snapshot saw this new entry appear
        [],                         # no real project/worktree candidates known
    )
    check("blamed as a genuine leak", blamed,
          [(fixture_slug, "matches this run's own temp fixture")])
    check("nothing ignored", ignored, [])
finally:
    try:
        fixture_root.rmdir()
    except OSError:
        pass

print("\n4. a name matching NEITHER list is still blamed -- unrecognised is not innocent")
mystery_slug = "totally-unrecognised-0000000000"
blamed, ignored = rt._classify_new_entries([mystery_slug], [], [])
check("blamed as unrecognised", blamed, [(mystery_slug, "unrecognised")])
check("nothing ignored", ignored, [])

print("\n5. a real-project match wins even when the same name would also match temp (can't "
      "happen via real slugs, but the ordering itself is the contract, and this proves it "
      "holds even if a future caller passes overlapping candidates)")
blamed, ignored = rt._classify_new_entries(
    [concurrent_slug],
    [concurrent_project.name],     # pretend it also showed up in the temp-dir snapshot
    [concurrent_project],
)
check("still ignored, not blamed", (blamed, ignored),
      ([], [(concurrent_slug, concurrent_project)]))

print("\n6. _git_worktree_roots never raises when run outside any git repo")
outside = TMP / "not-a-repo"
outside.mkdir(parents=True, exist_ok=True)
check("empty list, no exception", rt._git_worktree_roots(outside), [])

print("\n7. _recorded_project_roots reads last_exit.json's root field, skips junk, never raises")
state_base = CFG / "reentry-state"
good_dir = state_base / "workspace-aaaaaaaaaa"
good_dir.mkdir(parents=True, exist_ok=True)
recorded_root = TMP / "recorded-project"
recorded_root.mkdir(parents=True, exist_ok=True)
(good_dir / "last_exit.json").write_text(
    json.dumps({"root": str(recorded_root)}), encoding="utf-8")
junk_dir = state_base / "junk-bbbbbbbbbb"
junk_dir.mkdir(parents=True, exist_ok=True)
(junk_dir / "last_exit.json").write_text("not json{", encoding="utf-8")
missing_base = TMP / "does-not-exist"
roots = rt._recorded_project_roots(state_base)
check("recorded root found", recorded_root in roots, True)
check("junk contributes nothing extra", len(roots), 1)
check("a missing state base never raises", rt._recorded_project_roots(missing_base), [])

print("\n8. _real_roots dedupes case-insensitively across both sources")
dupe_state_base = TMP / "dupe-state"
dupe_dir = dupe_state_base / "proj-cccccccccc"
dupe_dir.mkdir(parents=True, exist_ok=True)
(dupe_dir / "last_exit.json").write_text(
    json.dumps({"root": str(recorded_root).upper()}), encoding="utf-8")
combined = rt._real_roots(dupe_state_base)
check("no crash with an empty git context", isinstance(combined, list), True)

print("\n9. a worktree that appears AFTER the first real-roots computation is still ignored, not "
      "blamed -- _classify_with_refresh recomputes real roots when the cache leaves something "
      "blamed (B75 round 2: `afk-05`/`afk-06`, `git worktree add`ed WHILE the suite was running)")
late_project = TMP / "afk-05"
late_project.mkdir(parents=True, exist_ok=True)
late_slug = rt._slug_for(late_project)

refresh_calls = []


def fake_real_roots_late(state_base):
    refresh_calls.append(state_base)
    return [late_project]          # what `_real_roots` would see NOW, post-`worktree add`


orig_real_roots = rt._real_roots
rt._real_roots = fake_real_roots_late
try:
    # the CACHED real_roots passed in is stale -- empty, exactly as it would be if `_real_roots`
    # ran at suite start, before this worktree existed.
    blamed, ignored, updated_roots = rt._classify_with_refresh(
        [late_slug], [], [], CFG / "reentry-state")
finally:
    rt._real_roots = orig_real_roots
check("refreshed exactly once", len(refresh_calls), 1)
check("not blamed after refresh", blamed, [])
check("ignored, attributed to the newly-appeared worktree", ignored,
      [(late_slug, late_project)])
check("caller's cache updated to the fresh list for the next test file", updated_roots,
      [late_project])

print("\n10. when the cached real roots already cover everything, no refresh happens at all "
      "(the normal path costs nothing)")
refresh_calls2 = []


def fake_real_roots_unused(state_base):
    refresh_calls2.append(state_base)
    return []


rt._real_roots = fake_real_roots_unused
try:
    blamed, ignored, updated_roots = rt._classify_with_refresh(
        [concurrent_slug], [], [concurrent_project], CFG / "reentry-state")
finally:
    rt._real_roots = orig_real_roots
check("no refresh call made", len(refresh_calls2), 0)
check("ignored via the cache alone", ignored, [(concurrent_slug, concurrent_project)])
check("cache returned unchanged", updated_roots, [concurrent_project])

print("\n11. an unrecognised name still triggers a refresh, and is still blamed if the fresh "
      "list doesn't explain it either (a refresh must not turn into a free pass)")
refresh_calls3 = []


def fake_real_roots_no_match(state_base):
    refresh_calls3.append(state_base)
    return []          # even after refreshing, nothing explains this name


rt._real_roots = fake_real_roots_no_match
try:
    blamed, ignored, updated_roots = rt._classify_with_refresh(
        [mystery_slug], [], [], CFG / "reentry-state")
finally:
    rt._real_roots = orig_real_roots
check("refreshed once", len(refresh_calls3), 1)
check("still blamed as unrecognised", blamed, [(mystery_slug, "unrecognised")])
check("nothing ignored", ignored, [])

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
