#!/usr/bin/env python3
"""Read the exit records `dirty_tree_warning.py` already writes -- and show them together.

    python plugins/cairn/tools/check_exits.py            # projects that ended dirty/unwrapped
    python plugins/cairn/tools/check_exits.py --all       # every record, so the rate is visible

STAGE 1 OF B42. THE DEFECT IS AGGREGATION, NOT DETECTION
----------------------------------------------------------
`dirty_tree_warning.py` already does the hard part: it fires on every `Stop` and `SessionEnd`,
and it has been writing one `stop-<session-id>.json` per session (and one `last_exit.json` per
project, overwritten) to `~/.claude/reentry-state/<project>/` since 2026-08-26. Measured on
2026-09-03 across nine of those records, spanning three projects:

    2026-08-26  example-project        dirty=4  unwrapped=0   ended dirty
    2026-09-03  workspace      dirty=2  unwrapped=0   ended dirty
    2026-09-03  workspace      dirty=0  unwrapped=1   ended dirty
    (six others clean)

Three of nine sessions ended with uncommitted work or an unwrapped commit, and the hook fired
correctly every single time. The warning still went nowhere anyone was looking: `Stop` speaks to
a session that is ENDING, and the follow-up in `session_orientation.py` speaks to the next
session start in that SAME project -- which may never come, because the next thing opened is a
different repo. Per-project state never reaches the session they are actually sitting in.

This file is the fix's cheap half: read every project's state back and report it together, in
whichever project you happen to have open. **No `git` call, no network, no new capture** -- every
byte here was already written by `dirty_tree_warning.py`, so this cannot be slow and cannot make
a session or a hook fail. `main()` always exits 0 for exactly that reason; the only nonzero exit
is argparse rejecting a flag it does not recognise (issue #18 -- see `test_sync_flags.py`, where
an unrecognised flag falling through to a DEFAULT action, rather than stopping, was the actual
incident).

A record's `paths` are a SNAPSHOT from the moment that session ended, not current truth -- they may
well have committed since. Nothing here re-checks; every rendered line says so, so this reads as
"here is what was left behind, as of when it happened" and not as a live accusation.

STAGE 2 IS NOT HERE ON PURPOSE
-------------------------------
Stage 2 is one line of this at `SessionStart`, in whatever project they open next, e.g.:
    2 other projects ended dirty: workspace (2 files, 4h ago), example-project (4 files, 8d ago)
silent when everything is clean, never naming the project you are standing in (the existing
per-project warning already owns that), one line, two at the absolute most -- see
`briefs/check-exits-aggregation.md`. Building it first would mean guessing at the shape from
imagination instead of from what stage 1 actually finds; the brief is explicit that this is the
wrong order. This file's job stops at making that line designable.

WHERE PROJECT IDENTITY COMES FROM
-----------------------------------
The state directory is named `<slug>-<hash10>` (`reentry_state.state_dir`) -- a sanitised,
32-char-truncated project name plus ten hex characters of a SHA-1 of the resolved root path.
`last_exit.json` carries `root` in full; `stop-*.json` does not, because `Stop` never learned the
project's identity beyond `CLAUDE_PROJECT_DIR`, only its dirty state. So identity resolves in two
steps, cheapest first:

  1. If ANY record in the directory is a `last_exit.json`, its `root` field is authoritative --
     use `Path(root).name` and keep the full path.
  2. Otherwise (a project that has only ever produced `stop-*.json`, e.g. a session that has not
     yet reached `SessionEnd`), strip the trailing `-<10 hex chars>` off the directory name. That
     recovers the exact slug `state_dir()` built UNLESS the real name was truncated to 32 chars or
     had characters folded to `-`, in which case this shows the folded/truncated form -- named
     here rather than silently guessed at, and the caller can tell the two apart because a
     resolved root is only ever printed in case 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Trailing `-<10 hex>` that `state_dir()` appends to every slug. Matched, not re-derived by
# hashing every candidate name -- there is nothing to hash against; a directory holds no list of
# real project names to try.
_HASH_SUFFIX = re.compile(r"^(?P<name>.+)-[0-9a-f]{10}$")

# How many raw paths to show under a flagged project. Mirrors `check_repos.py`'s MAX_LISTED --
# a dirty tree of 40 files does not need 40 lines to make the point.
MAX_LISTED = 8


def state_base() -> Path:
    """`~/.claude/reentry-state`, or its test double. Same override every tool in this plugin
    honours -- see `reentry_state.state_dir` and `check_repos.known_roots`."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    return Path(base) / "reentry-state"


def _load(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _identity(dirname: str, last_exit: dict | None) -> tuple[str, str | None]:
    """(display name, full root path or None). See the module docstring for the two-step order."""
    root = last_exit.get("root") if last_exit else None
    if isinstance(root, str) and root.strip():
        return Path(root).name or root, root
    m = _HASH_SUFFIX.match(dirname)
    return (m.group("name") if m else dirname), None


def collect(base: Path) -> list[dict]:
    """Every stop-*.json and last_exit.json under `base`, one dict each. Never raises: an
    unreadable directory or a malformed file is skipped, not fatal -- this is read-only reporting
    over a cache other hooks own, and a bad file in it is not this tool's problem to solve."""
    records: list[dict] = []
    try:
        dirs = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError:
        return records

    for d in dirs:
        last_exit = _load(d / "last_exit.json")
        name, root = _identity(d.name, last_exit)

        if last_exit is not None and isinstance(last_exit.get("at"), (int, float)):
            paths = last_exit.get("paths") or []
            records.append({
                "project": name, "root": root, "source": "last_exit",
                "session": None, "at": float(last_exit["at"]),
                # `dirty` is the true count even when `paths` was capped at save time;
                # `len(paths)` is the honest fallback for an older or hand-edited record.
                "dirty": int(last_exit.get("dirty", len(paths)) or 0),
                "unwrapped": int(last_exit.get("unwrapped") or 0),
                "paths": list(paths), "reason": last_exit.get("reason"),
                "wrap_ritual": bool(last_exit.get("wrap_ritual")),
            })

        try:
            stop_files = sorted(d.glob("stop-*.json"))
        except OSError:
            stop_files = []
        for f in stop_files:
            data = _load(f)
            if data is None or not isinstance(data.get("at"), (int, float)):
                continue
            paths = data.get("paths") or []
            session = f.stem[len("stop-"):] or None
            records.append({
                "project": name, "root": root, "source": "stop",
                "session": session, "at": float(data["at"]),
                "dirty": len(paths), "unwrapped": int(data.get("unwrapped") or 0),
                "paths": list(paths), "reason": None, "wrap_ritual": None,
            })

    records.sort(key=lambda r: r["at"], reverse=True)
    return records


def latest_per_project(records: list[dict]) -> list[dict]:
    """One record per project: whichever of its stop-*/last_exit files has the newest `at`.

    This is the "did the project end dirty" question -- it must NOT average or sum across a
    project's history, only ask what its most recent exit looked like. `records` is already
    newest-first, so the first record seen for a project IS its latest.
    """
    seen: set[str] = set()
    latest: list[dict] = []
    for r in records:
        key = r["root"].lower() if r["root"] else r["project"].casefold()
        if key in seen:
            continue
        seen.add(key)
        latest.append(r)
    return latest


def _age(seconds_ago: float) -> str:
    if seconds_ago < 0:
        seconds_ago = 0
    minutes = seconds_ago / 60
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return "%dm ago" % round(minutes)
    hours = minutes / 60
    if hours < 24:
        return "%dh ago" % round(hours)
    days = hours / 24
    if days < 90:
        return "%dd ago" % round(days)
    return "%dmo ago" % round(days / 30)


def _flagged(r: dict) -> bool:
    return bool(r["dirty"]) or bool(r["unwrapped"])


def _describe(r: dict, now: float) -> str:
    bits = []
    if r["dirty"]:
        bits.append("%d uncommitted" % r["dirty"])
    if r["unwrapped"]:
        noun = "commit" if r["unwrapped"] == 1 else "commits"
        bits.append("%d unwrapped %s" % (r["unwrapped"], noun))
    state = ", ".join(bits) or "clean"
    return "%-30s %-32s %s" % (r["project"][:30], state, _age(now - r["at"]))


def render(records: list[dict], show_all: bool) -> str:
    now = time.time()
    if not records:
        return ("No exit records found under %s -- either nothing has run "
                "dirty_tree_warning.py yet, or this is a machine with no history." % state_base())

    lines: list[str] = []
    if show_all:
        n_flagged = sum(1 for r in records if _flagged(r))
        lines.append("%d record(s), newest first -- %d ended dirty or unwrapped"
                     % (len(records), n_flagged))
        lines.append("")
        for r in records:
            marker = "[!!]" if _flagged(r) else "[ok]"
            lines.append("  %s %s  (%s)" % (marker, _describe(r, now), r["source"]))
            if r["root"]:
                lines.append("       %s" % r["root"])
            for p in r["paths"][:MAX_LISTED]:
                lines.append("         " + p)
            if len(r["paths"]) > MAX_LISTED:
                lines.append("         ... and %d more" % (len(r["paths"]) - MAX_LISTED))
        return "\n".join(lines)

    latest = latest_per_project(records)
    flagged = [r for r in latest if _flagged(r)]
    if not flagged:
        return ("%d project(s) checked -- every one's most recent exit was clean. "
                "(--all lists every record, clean ones included.)" % len(latest))

    lines.append("%d of %d project(s) ended dirty or unwrapped, most recently:"
                 % (len(flagged), len(latest)))
    lines.append("")
    for r in flagged:
        lines.append("  [!!] %s" % _describe(r, now))
        if r["root"]:
            lines.append("       %s" % r["root"])
        for p in r["paths"][:MAX_LISTED]:
            lines.append("         " + p)
        if len(r["paths"]) > MAX_LISTED:
            lines.append("         ... and %d more" % (len(r["paths"]) - MAX_LISTED))
    lines.append("")
    lines.append("These are snapshots from when each session ended -- not re-checked against the "
                 "working tree now. They may already have committed. (--all lists every record, "
                 "including clean ones, to see the rate.)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check_exits.py", description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", dest="show_all",
                    help="list every record, newest first, clean ones included -- "
                         "answers 'how bad is it' as a rate")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="machine-readable: every record this tool found")
    args = ap.parse_args(argv)

    records = collect(state_base())
    if args.as_json:
        print(json.dumps(records, indent=2))
        return 0
    print(render(records, args.show_all))
    return 0                                   # reports, never fails -- see the module docstring


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                   # pragma: no cover
        print("check_exits could not run (%s) -- check ~/.claude/reentry-state by hand" % exc)
        sys.exit(0)
