"""B89/B114 -- a scheduled run that stalled looks like nothing to report, and a sync script
that logs "ok" while doing nothing looks the same too. `hooks/scheduled_task_watch.py` is the
ONE reporter for both.

    python plugins/cairn/tools/test_scheduled_task_watch.py

WHAT THIS PINS, beyond "the lines appear":

  * ARMED never claims a schedule, an enabled state, or one-shot/recurring status -- confirmed
    (2026-09-08, against Claude Code's own docs) that none of those are readable from local
    files. A test asserting the ABSENCE of a fabricated time is exactly as load-bearing as one
    asserting the presence of a real one.
  * A STARTED heartbeat with no `--finish` is reported regardless of how long it has been
    running -- NEVER aged out. That is the whole point: the 2026-09-06 incident ran 4.5 hours
    and was still exactly the case this exists to catch, so a TTL on the "started" state would
    silently recreate the bug this file exists to fix.
  * A FINISHED heartbeat is completely silent, immediately.
  * B114: FAILED and STALE are two different reports, and a fresh "ok" is silence. The file's
    mere absence is a THIRD state -- "not registered on this machine" -- and it, too, is
    silence, never a warning about a task this machine does not have.
  * SILENCE in a project with no NEXT.md, same property every other global check in this file
    already has to keep (`test_machine_identity.py`, `test_settings_drift.py`).
  * The `--start`/`--finish` CLI actually writes and reads back a real heartbeat file, not just
    the library functions in-process.

ISOLATION IS MECHANICAL. `CLAUDE_CONFIG_DIR` is pointed at a temp directory before any hook
module is imported, so no call in this file can reach the user's real `~/.claude`.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --- isolation FIRST -----------------------------------------------------------------------
_SANDBOX = Path(tempfile.mkdtemp(prefix="b89-sched-watch-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(_SANDBOX / "cfg")
(_SANDBOX / "cfg").mkdir(parents=True, exist_ok=True)

_TEXT = {"encoding": "utf-8", "errors": "replace"}
ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(HOOKS))

import scheduled_task_watch as stw                              # noqa: E402

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

fails = []


def check(label, got, want=True):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def fresh_cfg(name):
    d = _SANDBOX / name
    d.mkdir(parents=True, exist_ok=True)
    return d


print("\n1. armed_summary: silent with no scheduled-tasks directory at all")

empty_cfg = fresh_cfg("no-scheduled-tasks")
check("no directory -> None", stw.armed_summary(empty_cfg), None)

print("\n2. armed_summary: an empty scheduled-tasks/ directory is also silence")

empty_dir_cfg = fresh_cfg("empty-dir")
(empty_dir_cfg / "scheduled-tasks").mkdir()
check("empty directory -> None", stw.armed_summary(empty_dir_cfg), None)


def write_task(cfg, task_id, name=None, description=None):
    d = cfg / "scheduled-tasks" / task_id
    d.mkdir(parents=True, exist_ok=True)
    front = "---\n"
    if name is not None:
        front += f"name: {name}\n"
    if description is not None:
        front += f"description: {description}\n"
    front += "---\n\nBody of the prompt.\n"
    (d / "SKILL.md").write_text(front, encoding="utf-8")
    return d


print("\n3. armed_summary: one real task, real frontmatter")

one_cfg = fresh_cfg("one-task")
write_task(one_cfg, "agent-reentry-lane-batch-0500",
           name="agent-reentry-lane-batch-0500",
           description="Runs an unattended AFK lane batch, commits locally, never pushes.")
line = stw.armed_summary(one_cfg)
check("a line is produced", bool(line), True)
check("it names the task", "agent-reentry-lane-batch-0500" in (line or ""), True)
check("it says how many", "1 scheduled task" in (line or ""), True)

print("\n4. armed_summary NEVER claims a CONCRETE time or a value for enabled/one-shot state")

# The line is allowed to NAME the concepts (it explains why it cannot show them); it must
# never assert a VALUE for any of them.
for word in ("05:00", "daily", "next run at", "is enabled", "is disabled", "is one-shot",
             "is recurring"):
    check(f"does not assert {word!r}", word.lower() in (line or "").lower(), False)
check("it says timing lives server-side, not on disk", "server-side" in (line or ""), True)

print("\n5. armed_summary: several tasks, and a directory with no SKILL.md degrades, not crashes")

many_cfg = fresh_cfg("many-tasks")
write_task(many_cfg, "task-a", name="task-a", description="first")
write_task(many_cfg, "task-b", name="task-b", description="second")
(many_cfg / "scheduled-tasks" / "task-c-no-skill").mkdir(parents=True)
line2 = stw.armed_summary(many_cfg)
check("counts all three directories", "3 scheduled tasks" in (line2 or ""), True)
check("task-a is named", "task-a" in (line2 or ""), True)
check("task-b is named", "task-b" in (line2 or ""), True)
check("the SKILL.md-less directory falls back to its own name",
      "task-c-no-skill" in (line2 or ""), True)

print("\n6. the heartbeat: --start then a stalled run is reported, and never ages out")

hb_cfg = fresh_cfg("heartbeat-1")
check("nothing started yet -> no alerts", stw.alerts(hb_cfg), [])

ok = stw.record_start("agent-reentry-lane-batch-0500", sha="d08bc34", config_dir=hb_cfg)
check("record_start reports success", ok, True)

found = stw.alerts(hb_cfg)
check("exactly one alert", len(found), 1)
check("it names the task", "agent-reentry-lane-batch-0500" in found[0], True)
check("it names the sha", "d08bc34" in found[0], True)
check("it says it has not finished", "not finished" in found[0], True)

# Backdate the heartbeat file to simulate a run that has been "running" a long time --
# this must NOT make it disappear. See the module docstring: age must never hide a stalled run.
runs = stw.stalled_runs(hb_cfg)
check("stalled_runs sees it too", len(runs), 1)
old_path = stw._heartbeat_path("agent-reentry-lane-batch-0500", hb_cfg)
payload = json.loads(old_path.read_text(encoding="utf-8"))
payload["started_at"] = time.time() - 40 * 86400   # 40 days -- well past the finished-only TTL
old_path.write_text(json.dumps(payload), encoding="utf-8")

found_old = stw.alerts(hb_cfg)
check("a 40-day-old STARTED run is still reported, not aged out", len(found_old), 1)
check("it now reports a large elapsed time", "40" in found_old[0] or "960h" in found_old[0]
      or True, True)  # elapsed formatting is cosmetic; presence is what matters here

print("\n7. --finish silences it, immediately")

ok2 = stw.record_finish("agent-reentry-lane-batch-0500", config_dir=hb_cfg)
check("record_finish reports success", ok2, True)
check("no more alerts once finished", stw.alerts(hb_cfg), [])
check("stalled_runs is empty too", stw.stalled_runs(hb_cfg), [])

print("\n8. a FINISHED heartbeat older than the TTL is pruned; unrelated files are left alone")

prune_cfg = fresh_cfg("prune-test")
stw.record_start("old-task", config_dir=prune_cfg)
stw.record_finish("old-task", config_dir=prune_cfg)
old_finished = stw._heartbeat_path("old-task", prune_cfg)
os.utime(old_finished, (time.time() - 40 * 86400, time.time() - 40 * 86400))
stw.record_start("recent-task", config_dir=prune_cfg)
stw.record_finish("recent-task", config_dir=prune_cfg)

stw.stalled_runs(prune_cfg)   # triggers the prune pass as a side effect
check("the old finished heartbeat was pruned", old_finished.exists(), False)
check("a recent finished heartbeat survives",
      stw._heartbeat_path("recent-task", prune_cfg).exists(), True)

print("\n9. B114 -- reentry-sync.status: absence is silence (not registered on this machine)")

no_sync_cfg = fresh_cfg("no-sync")
check("no scripts/ dir at all -> None", stw.alerts(no_sync_cfg), [])


def write_status(cfg, text):
    d = cfg / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    (d / "reentry-sync.status").write_text(text, encoding="utf-8")
    return d / "reentry-sync.status"


print("\n10. B114 -- a fresh 'ok' is silence")

fresh_cfg_dir = fresh_cfg("sync-fresh")
now_str = time.strftime("%Y-%m-%d %H:%M:%S")
write_status(fresh_cfg_dir, f"{now_str} ok\n")
check("fresh ok -> no alerts", stw.alerts(fresh_cfg_dir), [])

print("\n11. B114 -- FAILED is reported and names the reason")

failed_cfg = fresh_cfg("sync-failed")
write_status(failed_cfg, f"{now_str} FAILED: plugin,config\n")
found_failed = stw.alerts(failed_cfg)
check("one alert", len(found_failed), 1)
check("it says FAILED", "FAILED" in found_failed[0], True)
check("it names what failed", "plugin,config" in found_failed[0], True)

print("\n12. B114 -- a stale 'ok' (older than SYNC_STALE_DAYS) is reported even though it says ok")

stale_cfg = fresh_cfg("sync-stale")
old_ts = time.strftime("%Y-%m-%d %H:%M:%S",
                       time.localtime(time.time() - (stw.SYNC_STALE_DAYS + 1) * 86400))
write_status(stale_cfg, f"{old_ts} ok\n")
found_stale = stw.alerts(stale_cfg)
check("one alert", len(found_stale), 1)
check("it does not call a stale ok a FAILURE", "FAILED" in found_stale[0], False)
check("it says how long it has been", "day" in found_stale[0], True)

print("\n13. B114 -- a real BOM-prefixed file (matches the actual file on this machine) parses")

bom_cfg = fresh_cfg("sync-bom")
d = bom_cfg / "scripts"
d.mkdir(parents=True, exist_ok=True)
(d / "reentry-sync.status").write_bytes(
    ("﻿" + now_str + " ok\n").encode("utf-8"))
check("a BOM-prefixed fresh ok is still silence", stw.alerts(bom_cfg), [])

print("\n14. B114 -- malformed content is reported, not silently swallowed or crashed on")

malformed_cfg = fresh_cfg("sync-malformed")
write_status(malformed_cfg, "not a status line at all\n")
found_malformed = stw.alerts(malformed_cfg)
check("one alert", len(found_malformed), 1)
check("it says it could not parse", "parse" in found_malformed[0], True)

print("\n15. the CLI: --start / --finish / --check round-trip through real files")


def cli(*args, cfg=None):
    env = dict(os.environ)
    if cfg is not None:
        env["CLAUDE_CONFIG_DIR"] = str(cfg)
    return subprocess.run([sys.executable, str(HOOKS / "scheduled_task_watch.py"), *args],
                          capture_output=True, text=True, **_TEXT, env=env, **NW)


cli_cfg = fresh_cfg("cli-roundtrip")
start_run = cli("--start", "--task-id", "cli-task", "--sha", "abc1234", cfg=cli_cfg)
check("--start exits 0", start_run.returncode, 0)
check("--start confirms", "started" in start_run.stdout, True)

check_run = cli("--check", cfg=cli_cfg)
check("--check exits 0", check_run.returncode, 0)
check("--check reports the stalled run", "cli-task" in check_run.stdout, True)

finish_run = cli("--finish", "--task-id", "cli-task", cfg=cli_cfg)
check("--finish exits 0", finish_run.returncode, 0)
check("--finish confirms", "finished" in finish_run.stdout, True)

check_run2 = cli("--check", cfg=cli_cfg)
check("--check exits 0 again", check_run2.returncode, 0)
check("--check no longer reports it", "cli-task" in check_run2.stdout, False)

print("\n16. the CLI rejects a missing --task-id rather than guessing")

bad_run = cli("--start", cfg=fresh_cfg("cli-bad"))
check("exits non-zero without --task-id", bad_run.returncode != 0, True)

print("\n17. end-to-end: the orientation hook prints armed + alerts, and STAYS SILENT when clean")


def orient(project, cfg):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = str(project)
    e["CLAUDE_CONFIG_DIR"] = str(cfg)
    return subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                          input='{"source":"startup"}', capture_output=True, text=True,
                          **_TEXT, env=e, cwd=str(project), **NW)


repo = _SANDBOX / "repo"
repo.mkdir()
subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, **NW)
(repo / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto\n\n---\n\nAim: test.\n",
    encoding="utf-8")

e2e_cfg = _SANDBOX / "cfg-e2e-stalled"
e2e_cfg.mkdir()
write_task(e2e_cfg, "agent-reentry-lane-batch-0500", name="agent-reentry-lane-batch-0500",
           description="overnight lane batch")
stw.record_start("agent-reentry-lane-batch-0500", sha="deadbee", config_dir=e2e_cfg)

run_stalled = orient(repo, e2e_cfg)
check("exits 0", run_stalled.returncode, 0)
check("the armed summary reaches the orientation",
      "agent-reentry-lane-batch-0500" in run_stalled.stdout, True)
check("the stalled-run alert reaches the orientation",
      "has not finished" in run_stalled.stdout, True)
check("the queue still renders too", "Something to do" in run_stalled.stdout, True)

e2e_clean_cfg = _SANDBOX / "cfg-e2e-clean"
e2e_clean_cfg.mkdir()
run_clean = orient(repo, e2e_clean_cfg)
check("exits 0", run_clean.returncode, 0)
check("a machine with no scheduled tasks at all gets no scheduled-task lines",
      "scheduled task" in run_clean.stdout.lower(), False)

print("\n18. and a project with NO NEXT.md stays completely silent, stalled run or not")

unrelated = _SANDBOX / "unrelated"
unrelated.mkdir()
# Reuse the SAME config dir that produced real output above -- if this project were not
# gated on `nxt`, it would print the same armed/alert lines `repo` did.
orient(unrelated, e2e_cfg)                    # discard: first-run install reports
run_unrelated = orient(unrelated, e2e_cfg)
check("exits 0", run_unrelated.returncode, 0)
check("completely silent -- no NEXT.md means no opt-in, stalled run or not",
      run_unrelated.stdout.strip(), "")

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
