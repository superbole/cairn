"""Tests for `timesheet.py`'s staleness reporting and `timesheet_sync.py` (B66).

    python plugins/cairn/tools/test_timesheet.py

WHY THIS EXISTS. B66 is "a transport that silently reports the wrong machine's data" -- the fix
is a OneDrive-based transport (`timesheet_sync.py`) plus a staleness note in `timesheet.py` so a
synced-but-stale `--projects` copy can never pass as current by omission. Both halves are asserted
here against throwaway fixtures only; nothing in this file touches the real `~/.claude` or a real
OneDrive folder. `CLAUDE_CONFIG_DIR` is overridden before anything runs, same convention as every
other test in this plugin (`test_check_exits.py`, `test_machine_identity.py`, ...).
"""
import os
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="test-timesheet-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(TMP / "cfg")     # never the real ~/.claude

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import timesheet as ts                                  # noqa: E402
import timesheet_sync as sync_mod                        # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def write_transcript(root: Path, project: str, session_id: str, mtime: float | None = None):
    """One throwaway `*.jsonl` under `root/<project>/<session_id>.jsonl`. Content does not
    matter for the freshness tests -- only that the file exists and carries a specific mtime."""
    p = root / project / (session_id + ".jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"type":"user"}\n', encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


# --- timesheet.py: source_freshness / _age / source_notes -----------------------------------

print("1. source_freshness -- empty vs populated root")
empty_root = TMP / "empty_root"
empty_root.mkdir(parents=True, exist_ok=True)
check("an empty (but existing) root has no freshness", ts.source_freshness(empty_root), None)

missing_root = TMP / "does_not_exist"
check("a root that doesn't exist at all has no freshness",
      ts.source_freshness(missing_root), None)

fresh_root = TMP / "fresh_root"
now = time.time()
older = write_transcript(fresh_root, "proj-a", "sess-old", mtime=now - 3 * 3600)
newer = write_transcript(fresh_root, "proj-b", "sess-new", mtime=now - 300)
got = ts.source_freshness(fresh_root)
check("freshness is the NEWEST transcript's mtime, not the oldest or an average",
      abs(got.timestamp() - (now - 300)) < 2, True)

print("\n2. _age -- formats minutes / hours / days the way the report reads them")
ref = ts.datetime.now().astimezone()
check("under an hour prints minutes", ts._age(ref - ts.timedelta(minutes=5), ref), "5m")
check("hours and minutes below 48h", ts._age(ref - ts.timedelta(hours=3, minutes=7), ref), "3h07m")
check("48h and over collapses to whole days", ts._age(ref - ts.timedelta(hours=50), ref), "2d")
check("a negative delta (clock skew) never prints negative minutes",
      ts._age(ref + ts.timedelta(minutes=5), ref), "0m")

print("\n3. source_notes -- never silent, one line per --projects root, in either direction")
notes_empty = ts.source_notes([empty_root])
check("an existing-but-empty synced root gets a warning, not a blank line",
      len(notes_empty), 1)
check("...and the warning says so in words a non-programmer reads",
      "no transcripts found" in notes_empty[0], True)

notes_fresh = ts.source_notes([fresh_root])
check("a populated synced root gets exactly one note", len(notes_fresh), 1)
check("...and it names its own age", "ago" in notes_fresh[0], True)
# The newer file is ~5 minutes old, the older one ~3 hours -- the note must reflect the NEWEST
# transcript, so its age token must be minutes ("...m ago"), never an hour/day figure from the
# stale sibling. Checked by shape (ends in 'm') rather than an exact minute count, which would
# be brittle against however many seconds this test itself took to reach this line.
age_token = notes_fresh[0].split("newest transcript ")[1].split(" ago")[0]
check("age token is in MINUTES, not hours/days (proves it used the newest file, not the oldest)",
      age_token.endswith("m") and "h" not in age_token and "d" not in age_token, True)

notes_multi = ts.source_notes([empty_root, fresh_root])
check("multiple --projects roots each get their own line", len(notes_multi), 2)

print("\n4. the guard actually fires end to end: a stale --projects copy is never silent")
# Local (default) root is empty; the ONLY data comes from a synced copy that is deliberately
# made to look 10 days old. If this guard regressed, `main()` would print totals with no
# indication the numbers came from a 10-day-old mirror -- exactly the B66 defect one level up.
local_root = ts.projects_dir()
local_root.mkdir(parents=True, exist_ok=True)
stale_root = TMP / "stale_synced_copy"
write_transcript(stale_root, "workspace", "old-session", mtime=now - 10 * 24 * 3600)

import contextlib
import io

buf_out, buf_err = io.StringIO(), io.StringIO()
argv_saved = sys.argv
sys.argv = ["timesheet.py", "--days", "30", "--projects", str(stale_root)]
try:
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        ts.main()
finally:
    sys.argv = argv_saved
combined = buf_out.getvalue() + buf_err.getvalue()
check("the staleness note reaches the user somewhere in stdout+stderr",
      "synced copy" in combined, True)
check("it names the actual age (about 10 days), not a vague 'may be stale'",
      "9d" in combined or "10d" in combined, True)

print("\n5. --projects on a directory that doesn't exist is still reported and skipped "
      "(pre-existing behaviour, re-asserted so the new code path around it didn't break it)")
buf_out2, buf_err2 = io.StringIO(), io.StringIO()
sys.argv = ["timesheet.py", "--days", "7", "--projects", str(TMP / "nope")]
try:
    with contextlib.redirect_stdout(buf_out2), contextlib.redirect_stderr(buf_err2):
        ts.main()
finally:
    sys.argv = argv_saved
check("unreadable --projects path warned on stderr", "is not a readable directory"
      in buf_err2.getvalue(), True)
check("no crash -- and no bogus 'no transcripts found' note for a path that isn't even a dir",
      "no transcripts found" in buf_err2.getvalue(), False)


# --- timesheet_sync.py -----------------------------------------------------------------------

print("\n6. onedrive_root -- explicit override, then env vars in preference order")
check("explicit --onedrive-path wins outright", sync_mod.onedrive_root(str(TMP)), TMP)
check("a non-existent explicit path is rejected, not accepted verbatim",
      sync_mod.onedrive_root(str(TMP / "nope")), None)

saved_env = {k: os.environ.get(k) for k in ("OneDriveCommercial", "OneDrive", "OneDriveConsumer")}
biz = TMP / "biz-onedrive"
personal = TMP / "personal-onedrive"
biz.mkdir(exist_ok=True)
personal.mkdir(exist_ok=True)
try:
    os.environ["OneDriveCommercial"] = str(biz)
    os.environ["OneDrive"] = str(personal)
    os.environ["OneDriveConsumer"] = str(personal)
    check("business account (OneDriveCommercial) preferred when both are present",
          sync_mod.onedrive_root(None), biz)

    del os.environ["OneDriveCommercial"]
    check("falls back to OneDrive when Commercial is absent", sync_mod.onedrive_root(None),
          personal)

    del os.environ["OneDrive"]
    check("falls back to OneDriveConsumer when both others are absent",
          sync_mod.onedrive_root(None), personal)

    del os.environ["OneDriveConsumer"]
    check("no OneDrive var set at all -> None, never a guess", sync_mod.onedrive_root(None), None)
finally:
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print("\n7. machine_name -- explicit, then COMPUTERNAME, never silently blank")
check("explicit --machine wins", sync_mod.machine_name("LAPTOP1"), "LAPTOP1")
saved_cn = os.environ.get("COMPUTERNAME")
os.environ["COMPUTERNAME"] = "ORG-LAPTOP1"
try:
    check("falls back to COMPUTERNAME", sync_mod.machine_name(None), "ORG-LAPTOP1")
finally:
    if saved_cn is None:
        os.environ.pop("COMPUTERNAME", None)
    else:
        os.environ["COMPUTERNAME"] = saved_cn

print("\n8. sync() -- copies new/changed files, skips unchanged, never deletes at dest")
src = TMP / "sync_src"
dst = TMP / "sync_dst"
write_transcript(src, "workspace", "s1")
write_transcript(src, "workspace", "s2")
copied, skipped, nbytes = sync_mod.sync(src, dst)
check("first run copies every file", copied, 2)
check("first run skips nothing (dest was empty)", skipped, 0)
check("mirrors the two-level project-dir layout",
      (dst / "workspace" / "s1.jsonl").exists(), True)

copied2, skipped2, _ = sync_mod.sync(src, dst)
check("second run with no changes copies nothing", copied2, 0)
check("second run skips both unchanged files", skipped2, 2)

# Simulate a live transcript growing (appended to) -- must be re-copied, not skipped on mtime
# alone reading stale, and must NOT require a newer mtime if the size differs.
(src / "workspace" / "s1.jsonl").write_text('{"type":"user"}\nmore appended content\n',
                                            encoding="utf-8")
copied3, skipped3, _ = sync_mod.sync(src, dst)
check("a grown (appended-to) transcript is re-copied, not skipped as unchanged", copied3, 1)
check("the untouched sibling is still skipped", skipped3, 1)

# A project removed from the SOURCE must not remove it from the already-synced DEST -- deleting
# it here would be exactly the "local view silently changes the synced copy underneath a
# concurrent reader" hazard the module docstring calls out.
import shutil as _shutil
_shutil.rmtree(src / "workspace")
(src / "other-proj").mkdir(parents=True, exist_ok=True)
sync_mod.sync(src, dst)
check("removing a project from the SOURCE does not delete it from an already-synced dest",
      (dst / "workspace" / "s1.jsonl").exists(), True)

print("\n9. main() end to end -- writes only under the OneDrive path, never near ~/.claude")
proj_src = ts.projects_dir()             # already pointed at the throwaway CLAUDE_CONFIG_DIR
write_transcript(proj_src, "agent-reentry", "e2e-session")
onedrive_fake = TMP / "e2e-onedrive"
onedrive_fake.mkdir(exist_ok=True)
before = set(TMP.rglob("*"))
rc = sync_mod.main(["--onedrive-path", str(onedrive_fake), "--machine", "TEST-NB"])
check("exits 0", rc, 0)
expected_dest = onedrive_fake / "ReentryTimesheetSync" / "TEST-NB" / "projects"
check("landed under <onedrive>/ReentryTimesheetSync/<machine>/projects",
      (expected_dest / "agent-reentry" / "e2e-session.jsonl").exists(), True)
# The only writes anywhere under TMP should be inside onedrive_fake (plus dirs already made by
# write_transcript into proj_src, which predate this call) -- nothing new appears elsewhere.
after = set(TMP.rglob("*"))
new_paths = after - before
outside_onedrive = [p for p in new_paths if onedrive_fake not in p.parents and p != onedrive_fake]
check("every new path this call created is under the fake OneDrive root",
      outside_onedrive, [])

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
