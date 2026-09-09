"""Test for `check_exits.py` (B42 stage 1), against throwaway fixtures only.

    python plugins/cairn/tools/test_check_exits.py

WHY THIS MUST NEVER TOUCH ~/.claude/reentry-state
----------------------------------------------------
That directory is real operator history -- the user's actual dirty-exit records across every
project on this machine. A test that reads or writes it would be non-deterministic (today's
result depends on whatever they happened to leave dirty) and, worse, a bug in a future edit could
turn a "read-only reporting" test into one that corrupts live state. So every case here builds
its own `reentry-state/` tree under a temp directory and points `check_exits.state_base()` at it
via `CLAUDE_CONFIG_DIR` -- the same override every other tool and test in this plugin honours
(`reentry_state.state_dir`, `check_repos.known_roots`, `test_repo_recorder.py`). Nothing here
imports `Path.home()`.

Covers the two identity-resolution paths named in `check_exits.py`'s docstring (a project with a
`last_exit.json` resolves by its `root` field; a project with only `stop-*.json` falls back to
stripping the directory's hash suffix), the "most recent record only" flagging rule, `--all`'s
full listing, and that an unrecognised flag stops in argparse rather than falling through to the
default report (issue #18 -- the same regression class `test_sync_flags.py` guards).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="check-exits-"))
CFG = TMP / "cfg"
os.environ["CLAUDE_CONFIG_DIR"] = str(CFG)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_exits as ce                               # noqa: E402

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


def write(rel, payload):
    p = CFG / "reentry-state" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")


NOW = 1_800_000_000.0   # fixed epoch so ages are deterministic


print("1. an empty state dir is reported, not an error")
check("no records", ce.render(ce.collect(ce.state_base()), False),
      "No exit records found under %s -- either nothing has run dirty_tree_warning.py yet, "
      "or this is a machine with no history." % ce.state_base())

print("\n2. a project with last_exit.json resolves identity from its `root` field")
write("workspace-a76a7ef7e6/last_exit.json", {
    "root": r"C:\Users\Example\Projects\workspace", "at": NOW - 4 * 3600,
    "reason": "other", "dirty": 2, "paths": ["a.txt", "b.txt"], "unwrapped": 0,
    "wrap_ritual": True,
})
records = ce.collect(ce.state_base())
check("one record found", len(records), 1)
check("name from root, not the slug", records[0]["project"], "workspace")
check("full root kept", records[0]["root"], r"C:\Users\Example\Projects\workspace")
check("dirty count from the authoritative field", records[0]["dirty"], 2)
check("flagged (dirty)", ce._flagged(records[0]), True)

print("\n3. a project with ONLY stop-*.json falls back to stripping the hash suffix")
write("example-project-8d6cb99077/stop-unknown.json",
      {"paths": ["ACTIVITY.md", "INBOX.md", "QUEUE.md", "WAITING.md"], "unwrapped": 0,
       "at": NOW - 8 * 86400})
records = ce.collect(ce.state_base())
oct_rec = [r for r in records if r["session"] == "unknown"][0]
check("name recovered from the directory name", oct_rec["project"], "example-project")
check("root unknown -- only last_exit carries it", oct_rec["root"], None)
check("dirty count is len(paths) for a stop record", oct_rec["dirty"], 4)
check("session id parsed from the filename", oct_rec["session"], "unknown")

print("\n4. a project with an unwrapped commit and a CLEAN tree still flags")
write("agent-reentry-bcd9988b4e/last_exit.json", {
    "root": r"C:\Users\Example\Projects\agent-reentry", "at": NOW - 3600,
    "reason": "other", "dirty": 0, "paths": [], "unwrapped": 3, "wrap_ritual": True,
})
records = ce.collect(ce.state_base())
ar = [r for r in records if r["project"] == "agent-reentry"][0]
check("dirty is zero", ar["dirty"], 0)
check("still flagged, on unwrapped alone", ce._flagged(ar), True)

print("\n5. a clean project never appears in the flagged (default) report")
write("clean-proj-1111111111/last_exit.json", {
    "root": r"C:\Users\Example\Projects\clean-proj", "at": NOW - 60,
    "reason": "other", "dirty": 0, "paths": [], "unwrapped": 0, "wrap_ritual": True,
})
records = ce.collect(ce.state_base())
out = ce.render(records, False)
check("says 3 of N flagged", "ended dirty or unwrapped" in out, True)
check("workspace is named", "workspace" in out, True)
check("example-project is named", "example-project" in out, True)
check("agent-reentry is named", "agent-reentry" in out, True)
check("clean-proj is NOT named in the flagged report", "clean-proj" in out, False)
check("caveat about snapshots is present", "snapshots from when" in out, True)

print("\n6. --all lists every record, clean ones included, and states the rate")
out_all = ce.render(records, True)
check("clean-proj DOES appear under --all", "clean-proj" in out_all, True)
check("rate line present", "record(s), newest first" in out_all, True)
n_total = len(records)
n_flagged = sum(1 for r in records if ce._flagged(r))
check("counts match what was written", (n_total, n_flagged), (4, 3))

print("\n7. a project's most recent record wins -- an EARLIER dirty stop does not leak through "
      "once a later, clean last_exit supersedes it")
write("fixed-later-2222222222/stop-s1.json",
      {"paths": ["oops.txt"], "unwrapped": 0, "at": NOW - 7200})
write("fixed-later-2222222222/last_exit.json", {
    "root": r"C:\Users\Example\Projects\fixed-later", "at": NOW - 60,
    "reason": "other", "dirty": 0, "paths": [], "unwrapped": 0, "wrap_ritual": True,
})
records = ce.collect(ce.state_base())
latest = ce.latest_per_project(records)
fl = [r for r in latest if r["project"] == "fixed-later"]
check("exactly one entry survives dedup", len(fl), 1)
check("the LATER, clean record is the one kept", fl[0]["source"], "last_exit")
check("not flagged -- it was fixed since", ce._flagged(fl[0]), False)

print("\n8. a malformed record is skipped, not fatal")
p = CFG / "reentry-state" / "junk-3333333333"
p.mkdir(parents=True, exist_ok=True)
(p / "last_exit.json").write_text("not json{", encoding="utf-8")
(p / "stop-broken.json").write_text(json.dumps({"paths": []}), encoding="utf-8")  # no "at"
records2 = ce.collect(ce.state_base())
check("junk project contributes no record", any(r["project"] == "junk" for r in records2), False)
check("everything else still there", len(records2) >= n_total, True)

print("\n9. --help and an unrecognised flag stop in argparse -- never fall through to a report")
exits("--help exits 0", lambda: ce.main(["--help"]), 0)
exits("-h exits 0", lambda: ce.main(["-h"]), 0)
exits("--bogus-flag exits 2", lambda: ce.main(["--bogus-flag"]), 2)
exits("a bare positional exits 2 (none are accepted)", lambda: ce.main(["workspace"]), 2)

print("\n10. --json emits one dict per record; main() always returns 0 on a clean run")
check("main() with --all returns 0", ce.main(["--all"]), 0)
check("main() with --json returns 0", ce.main(["--json"]), 0)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
