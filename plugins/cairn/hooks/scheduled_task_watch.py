#!/usr/bin/env python3
"""ONE reporter for two incidents that share a shape: a scheduled process that ran
unattended and left no way to tell "it worked silently" apart from "it never really ran".

    python scheduled_task_watch.py --start  --task-id ID [--sha SHA]   # a scheduled task's FIRST act
    python scheduled_task_watch.py --finish --task-id ID               # its LAST act
    python scheduled_task_watch.py --check                             # what would print at session start

B89 -- A SCHEDULED RUN STUCK ON A PERMISSION PROMPT LOOKS LIKE "NOTHING TO DO"
-------------------------------------------------------------------------------
Measured 2026-09-06: an 05:00 lane-batch cloud-agent task fired into a
session left in `Manual` permission mode and sat for four and a half hours on a dialog asking
permission to run one `sed` that reads a backlog entry. It only completed at 09:55 because a
human woke up and clicked. Until then, the observable state on disk -- no new commits, no
dossier, no handover section -- was BIT-FOR-BIT IDENTICAL to "the run fired, found no eligible
AFK work, and correctly stopped early" (`docs/running-a-batch.md` names that as the design
working). Two opposite outcomes, one appearance.

The fix is a heartbeat, written by the task itself, before anything else it does and after the
last thing it does: `record_start()`/`record_finish()` below, driven by the `--start`/`--finish`
CLI so a scheduled task's own prompt can call this file directly (`$CLAUDE_PLUGIN_ROOT` is set
in a normal session the same way it is for `wrap_receipt.py --check`, per `rules/CLAUDE.md`).
`stalled_runs()` then answers the one question nothing could answer before: is a run in flight
right now, and since when. **Wiring the actual `--start`/`--finish` calls into the scheduled
task's own prompt template (`docs/running-a-batch.md` or wherever such a prompt is authored) is
OUT OF SCOPE for this file** -- this lane owns `hooks/`, not `docs/`; see the dossier this
change shipped with.

EXTENDED SCOPE, DELIBERATELY KEPT AS ONE ITEM: a reader of `~/.claude/scheduled-tasks/` (armed
tasks) and a reader of `~/.claude/reentry-state/` (started-but-unfinished ones) are the SAME
question -- "what did a scheduler start that nobody is watching" -- asked at two different
moments (before it fires, while it is running). Splitting them would be "a partition with
nobody on the other side of it" (B89's own brief, arguing against exactly that split).

WHAT `armed_summary()` CANNOT SAY, AND WHY (checked, not assumed)
-------------------------------------------------------------------
Confirmed against Claude Code's own docs before writing this (2026-09-08): the cron schedule,
enabled/disabled state, and one-shot-vs-recurring flag for a task created via
`create_scheduled_task` / `/schedule` are **server-side only**. The single local artifact is
`~/.claude/scheduled-tasks/<id>/SKILL.md` -- a cached copy of the PROMPT, nothing else. No JSON
sidecar, no sqlite db, no master list exists anywhere under `~/.claude/`. So this module reports
that a task's prompt is cached HERE, and its name/description, and refuses to guess a "when" --
inventing one from the directory name (the one example on this machine happens to be suffixed
`-0500`, which is a coincidence of ONE instance, not a documented contract) or from an mtime is
exactly the class of inference `STALE_WATCH_DAYS`'s own comment in `session_orientation.py`
already rejected once (B44): claim only the true thing, point at where the real answer lives
(`/schedule list`).

THE SAME REASONING RULES OUT "SPENT" DETECTION. The brief asks for a third state -- a completed
one-shot task, left as residue -- but nothing on disk marks a task directory as "done and
disabled" versus "still armed"; Claude Code's own docs describe an explicit, MANUAL "also delete
files on disk" step, not an automatic one. Telling the two apart from a directory's mere
presence would be a guess with the user's cleanup decision riding on it. **Not implemented here
on purpose** -- see the dossier.

"DUE BUT NEVER STARTED" IS THE SAME LIMIT, ONE STEP FURTHER. The module docstring for B89 itself
imagines the line *"a scheduled run was due 05:00 and has not started"* -- but that requires
knowing the schedule, which is confirmed above to not exist locally. `stalled_runs()` can only
ever answer "started, not finished", never "never started at all". Reported instead of quietly
producing a half-true line.

B114 -- `reentry-sync.ps1` REPORTED SUCCESS WHILE DOING NOTHING FOR A DAY
---------------------------------------------------------------------------
Found 2026-09-07: the daily `ReentryPluginSync` task ran `claude plugin update reentry@reentry`
after a rename, and `claude plugin` exits 0 on an unknown slug -- so the script's own
exception-only error handling logged "plugin OK" while the log underneath said `Plugin "reentry"
not found`. Already half-fixed: the script (versioned in a private repo, not this one) now
writes one line to `~/.claude/scripts/reentry-sync.status`, either `<timestamp> ok` or
`<timestamp> FAILED: plugin,config`. Nothing read that file until `_sync_status()` below.

The file's mere EXISTENCE is the "registered on this machine" gate the brief asks for: a machine
that has never run the sync task has no `reentry-sync.status` to read, so `_sync_status()`
returns None -- total silence -- rather than a warning about a task that machine does not have.
Same anti-wallpaper shape as `dirty_tree_warning.uses_wrap_ritual()` gating on `.last_wrap`.

NEVER RAISES, same contract as every module `session_orientation.py` imports: `armed_summary()`
and `alerts()` degrade to `None` / `[]` on any read failure, never an exception. Only the
`--start`/`--finish` CLI writes anything, and only to files under this module's own heartbeat
directory -- nothing here ever touches `NEXT.md`, `BACKLOG.md`, or any project file.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

HEARTBEAT_SUBDIR = "_scheduled_tasks"      # under reentry-state/ -- see docstring below

SYNC_STATUS_REL = Path("scripts") / "reentry-sync.status"
SYNC_STALE_DAYS = 2          # B114's own number: "older than ~2 days"

# A FINISHED heartbeat older than this is pruned so the directory does not grow forever. A
# STARTED one is NEVER pruned by age -- see stalled_runs()'s docstring for why duration must
# never be the thing that hides a stalled run (the 2026-09-06 incident ran 4.5 hours and was
# still exactly the case this exists to catch).
HEARTBEAT_TTL_DAYS = 30

# `~/.claude/scheduled-tasks/<id>/SKILL.md` frontmatter -- the same `---\n...\n---` shape every
# skill in this plugin uses. Read tolerantly: a hand-edited or partially-written file degrades
# to "no name/description found", never a crash.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FIELD_RE = re.compile(r'^([A-Za-z_]+):\s*(.*)$')

_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$")


def _config_dir(override: str | Path | None = None) -> Path:
    """`~/.claude`, or `$CLAUDE_CONFIG_DIR` -- identical resolution to every other module in
    this plugin (`machine_identity._config_dir`, `settings_drift._config_dir`, ...). Kept as a
    local copy rather than imported: this file must stay importable even if a sibling module
    is missing, the same defensive-import contract `session_orientation.py` uses for all of
    its layers.
    """
    if override:
        return Path(override).expanduser()
    env = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(env).expanduser() if env else Path.home() / ".claude"


# --- B89, half 1: ARMED -- what this machine has a local copy of ------------------------------

def _registered_tasks(config_dir: str | Path | None = None) -> list[dict]:
    """Every `~/.claude/scheduled-tasks/<id>/` this machine holds, as
    `{"task_id", "name", "description"}`. `name`/`description` come from the SKILL.md
    frontmatter when present, falling back to the directory name -- never raises, never
    guesses a schedule (see module docstring for why that is not this function's business).
    """
    base = _config_dir(config_dir) / "scheduled-tasks"
    out: list[dict] = []
    try:
        entries = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError:
        return []
    for entry in entries:
        name, description = entry.name, ""
        try:
            text = (entry / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        m = _FRONTMATTER_RE.match(text) if text else None
        if m:
            for line in m.group(1).splitlines():
                fm = _FIELD_RE.match(line.strip())
                if not fm:
                    continue
                key, val = fm.group(1).lower(), fm.group(2).strip().strip("\"'")
                if key == "name" and val:
                    name = val
                elif key == "description":
                    description = val
        out.append({"task_id": entry.name, "name": name, "description": description})
    return out


def armed_summary(config_dir: str | Path | None = None) -> str | None:
    """ONE line naming every scheduled task this machine has a local copy of, or None when
    there are none -- silence is correct in the overwhelmingly common case (no scheduled
    tasks at all), same as every other check in this plugin.

    Deliberately makes NO claim about timing, enabled state, or one-shot vs recurring -- see
    the module docstring for the confirmed reason those cannot be read from local files.
    """
    tasks = _registered_tasks(config_dir)
    if not tasks:
        return None
    names = ", ".join(f"`{t['name']}`" for t in tasks)
    noun = "task is" if len(tasks) == 1 else "tasks are"
    return (f"{len(tasks)} scheduled {noun} registered on this machine: {names} -- schedule, "
            f"enabled state and one-shot/recurring status live server-side, not on disk, so "
            f"exact timing cannot be shown here; ask me to run `/schedule list` for that.")


# --- B89, half 2: STARTED AND NEVER FINISHED -- the heartbeat ---------------------------------

def _sanitize_task_id(task_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in task_id.strip())[:128] or "task"


def _heartbeat_dir(config_dir: str | Path | None = None) -> Path | None:
    """`~/.claude/reentry-state/_scheduled_tasks/` -- GLOBAL, not per-project, because a
    scheduled task is a fact about the MACHINE, the same reasoning `machine_identity.py` and
    `MACHINES.md` already use. Named with a leading underscore for the same reason
    `reentry_state.py`'s own `_sessions` subdir is: nothing a real project's `state_dir()` slug
    produces can ever collide with it (those are always `<name>-<10 hex>`), so a task id that
    happened to look like a project slug can never be misread as one. None when unwritable --
    every caller degrades to "nothing to report", never a crash.
    """
    base = _config_dir(config_dir) / "reentry-state" / HEARTBEAT_SUBDIR
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return base


def _heartbeat_path(task_id: str, config_dir: str | Path | None = None) -> Path | None:
    directory = _heartbeat_dir(config_dir)
    if directory is None:
        return None
    return directory / f"{_sanitize_task_id(task_id)}.json"


def record_start(task_id: str, sha: str | None = None,
                  config_dir: str | Path | None = None) -> bool:
    """The scheduled task's FIRST act, before anything else it does. Best-effort, like every
    write in this plugin: returns whether the stamp was written, never raises.
    """
    path = _heartbeat_path(task_id, config_dir)
    if path is None:
        return False
    try:
        path.write_text(json.dumps({
            "task_id": task_id, "status": "started",
            "started_at": time.time(), "sha": sha, "finished_at": None,
        }), encoding="utf-8")
        return True
    except OSError:
        return False


def record_finish(task_id: str, config_dir: str | Path | None = None) -> bool:
    """The scheduled task's LAST act. Reads back whatever `record_start` wrote so
    `started_at`/`sha` survive into the finished record; a task that calls `--finish` without
    ever having called `--start` (should not happen, but nothing here trusts that) still gets a
    valid finished record rather than an error.
    """
    path = _heartbeat_path(task_id, config_dir)
    if path is None:
        return False
    payload = {"task_id": task_id, "status": "started", "started_at": None, "sha": None}
    try:
        payload.update(json.loads(path.read_text(encoding="utf-8", errors="replace")))
    except Exception:
        pass                      # no prior --start, or an unreadable record -- finish anyway
    payload["status"] = "finished"
    payload["finished_at"] = time.time()
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
        return True
    except OSError:
        return False


def _prune_finished(directory: Path) -> None:
    """Drop FINISHED heartbeats older than `HEARTBEAT_TTL_DAYS`. A STARTED one is untouched
    here regardless of age -- pruning it would silently turn "still running after a very long
    time" into "nothing to report", which is precisely the failure this file exists to remove.
    """
    cutoff = time.time() - HEARTBEAT_TTL_DAYS * 86400
    try:
        for p in directory.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if isinstance(data, dict) and data.get("status") == "finished":
                try:
                    if p.stat().st_mtime < cutoff:
                        p.unlink()
                except OSError:
                    pass
    except OSError:
        pass


def stalled_runs(config_dir: str | Path | None = None) -> list[dict]:
    """Every heartbeat still marked `started` with no `finished_at` -- a run that began and has
    not (yet, or ever) said it is done. NEVER aged out: see `_prune_finished`'s docstring.
    """
    directory = _heartbeat_dir(config_dir)
    if directory is None:
        return []
    _prune_finished(directory)
    out: list[dict] = []
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("status") == "started" and not data.get("finished_at"):
            out.append(data)
    return out


def _fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def _stalled_lines(config_dir: str | Path | None = None) -> list[str]:
    lines: list[str] = []
    for run in stalled_runs(config_dir):
        task_id = run.get("task_id") or "unknown task"
        sha = run.get("sha")
        started_at = run.get("started_at")
        if isinstance(started_at, (int, float)):
            when = datetime.fromtimestamp(started_at).strftime("%Y-%m-%d %H:%M")
            elapsed = _fmt_elapsed(time.time() - started_at)
            sha_note = f" on sha `{sha}`" if sha else ""
            lines.append(
                f"a scheduled run (`{task_id}`) started {when}{sha_note} and has not finished "
                f"-- {elapsed} and counting. If it is sitting on a permission prompt, that is "
                f"exactly what this line exists to catch: nobody is there to click it.")
        else:
            lines.append(
                f"a scheduled run (`{task_id}`) is marked started, with no recorded start "
                f"time, and has not finished -- check it by hand.")
    return lines


# --- B114: the sync-status reader --------------------------------------------------------------

def _sync_status(config_dir: str | Path | None = None) -> str | None:
    """One line when `reentry-sync.status` says FAILED or is older than `SYNC_STALE_DAYS`;
    None otherwise -- including when the file is simply absent, which means this machine has
    no `ReentryPluginSync` task writing it. That absence IS the "registered on this machine"
    gate: a machine that never runs the sync task stays silent about it, exactly like every
    other opt-in check in this plugin.
    """
    path = _config_dir(config_dir) / SYNC_STATUS_REL
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    text = text.lstrip("﻿").strip()          # the real file on this machine carries a BOM
    if not text:
        return (f"`{path}` exists but is empty -- the sync task may be mid-write, or broke "
                f"before it could log anything.")
    m = _TIMESTAMP_RE.match(text)
    if not m:
        return f"`{path}` does not parse as `<timestamp> ok|FAILED: ...` -- got: {text!r}"
    stamp, rest = m.groups()
    try:
        when = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return f"`{path}` has an unparseable timestamp -- got: {stamp!r}"
    age_days = (datetime.now() - when).total_seconds() / 86400
    log_path = path.parent / "reentry-sync.log"
    if not rest.lower().startswith("ok"):
        return (f"reentry-sync last reported FAILED at {stamp} ({rest}) -- nothing has synced "
                f"since. See `{log_path}`.")
    if age_days > SYNC_STALE_DAYS:
        return (f"reentry-sync last reported ok {age_days:.1f} day(s) ago ({stamp}) and has "
                f"not reported since -- the daily task may have stopped running. See "
                f"`{log_path}`.")
    return None


# --- the combined reporter ----------------------------------------------------------------------

def alerts(config_dir: str | Path | None = None) -> list[str]:
    """Everything worth a warning line right now -- a stalled scheduled run, and/or a failed or
    stale sync status. Empty list is the common case. Never raises: a broken read anywhere in
    here degrades to fewer lines, never an exception reaching `session_orientation.py`.
    """
    out: list[str] = []
    try:
        out.extend(_stalled_lines(config_dir))
    except Exception:
        pass
    try:
        sync = _sync_status(config_dir)
    except Exception:
        sync = None
    if sync:
        out.append(sync)
    return out


def _cli(argv: list[str]) -> int:
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    def _opt(name: str) -> str | None:
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return None

    usage = ("usage: scheduled_task_watch.py --start --task-id ID [--sha SHA] | "
             "--finish --task-id ID | --check")
    if not argv:
        print(usage)
        return 2
    if argv[0] == "--start":
        task_id = _opt("--task-id")
        if not task_id:
            print(usage)
            return 2
        ok = record_start(task_id, sha=_opt("--sha"))
        print("heartbeat: started" if ok else "heartbeat: could not write (no writable state dir)")
        return 0 if ok else 1
    if argv[0] == "--finish":
        task_id = _opt("--task-id")
        if not task_id:
            print(usage)
            return 2
        ok = record_finish(task_id)
        print("heartbeat: finished" if ok else "heartbeat: could not write (no writable state dir)")
        return 0 if ok else 1
    if argv[0] == "--check":
        armed = armed_summary()
        found = alerts()
        if armed:
            print(armed)
        for ln in found:
            print(f"! {ln}")
        if not armed and not found:
            print("nothing to report")
        return 0
    print(usage)
    return 2


if __name__ == "__main__":
    import sys
    try:
        raise SystemExit(_cli(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:                                     # pragma: no cover
        print(f"scheduled_task_watch: could not run ({exc}) -- treat as no information")
        raise SystemExit(0)
