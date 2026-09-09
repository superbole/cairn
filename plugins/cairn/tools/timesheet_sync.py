#!/usr/bin/env python3
"""Copy THIS machine's session transcripts into a synced folder the other machine can read.

THE DESTINATION IS PERMANENT AND IS NEVER PRUNED.
-------------------------------------------------
This copies IN, one direction, and deletes nothing at the far end -- not stale files, not files
whose source has since been removed, not anything. Whatever your session transcripts contain
ends up at the destination you name and stays there until you remove it by hand. Transcripts are
the full text of your sessions, so choose a destination on that basis: a folder that syncs to a
cloud account is a copy of your work in that account, indefinitely.

One-shot and manual by design -- nothing schedules this, and it runs only when you run it.

    python plugins/cairn/tools/timesheet_sync.py
    python plugins/cairn/tools/timesheet_sync.py --machine LAPTOP1
    python plugins/cairn/tools/timesheet_sync.py --onedrive-path "D:\\OneDrive - example-corp.com"

WHY THIS EXISTS (B66). `timesheet.py --projects PATH` already merges a second machine's session
transcripts into one timesheet -- it has since before this file existed -- but PATH has to be
REACHABLE, and LAPTOP1 and LAPTOP2 never have been. Direct SSH was attempted and fully reversed the same
session (generated a keypair, installed OpenSSH Server, opened firewall port 22 -- see BACKLOG.md
B66 for the full sequence): three failures in a row pointed at a network-level block between the
VPN client subnet and the office Wi-Fi subnet that neither machine's local firewall or `sshd`
config can fix. Re-attempting SSH/firewall/network configuration is explicitly out of scope for
this transport -- that route is closed.

Both machines already run OneDrive, so this needs no new port, no new credential, and no change
to either machine's network configuration. The mechanism:

  1. Run this script on a machine. It copies THAT machine's own `~/.claude/projects` into a
     machine-named folder under OneDrive (`<OneDrive root>/ReentryTimesheetSync/<machine>/
     projects`). It never reads or writes anything on the OTHER machine.
  2. OneDrive's own background sync -- already running, not something this script starts --
     carries the copy to the other side.
  3. Run `timesheet.py --projects <the OTHER machine's synced folder>` on either machine to get
     the merged total. `timesheet.py` reports how old that copy is (see its `source_freshness`)
     rather than presenting it as current -- the whole reason B66 exists is a transport that
     silently reported the wrong machine's data, and a stale-but-unlabelled synced copy is the
     same defect one level up.

MANUAL, NOT SCHEDULED -- ON PURPOSE. A background task that copies on a timer fails silently
between runs and this repo reverted a machine-global background mechanism for exactly that
reason on 2026-09-05 (see `run_tests.py`'s B70/B73/B74 notes for the class of failure). Running
this by hand right before pulling a combined timesheet means the copy is only ever as old as the
moment it was asked for, and that age is always visible afterwards.

WHAT THIS DOES NOT DO. It never writes to `~/.claude` -- only reads from it (`--projects` in
`timesheet.py` is the read side; this script is the write-into-OneDrive side, and the two never
touch the same directory in the same direction). It opens no socket, deletes nothing at the
destination (a project removed locally does not vanish from a copy that a merge may be reading on
the other side mid-flight), and asks for no credential.

ONEDRIVE ACCOUNT CHOICE. A the organisation machine typically has both a business account
(`OneDriveCommercial`, folder name `OneDrive - example-corp.com`) and a personal one
(`OneDriveConsumer`, folder name `OneDrive`). The business one is preferred by default since
that's the account both work laptops actually share; override with `--onedrive-path` if that
guess is wrong on a given machine -- confirm the real path by hand once (see
`docs/review/timesheet.md`) rather than assuming the default matches.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path

SYNC_SUBDIR = "ReentryTimesheetSync"


def onedrive_root(explicit: str | None) -> Path | None:
    """Where OneDrive keeps its synced files on THIS machine, business account preferred.

    Checked in this order: an explicit override, then `OneDriveCommercial`, then the generic
    `OneDrive` (set to whichever account last signed in), then `OneDriveConsumer`. None of these
    are guaranteed to exist -- a machine where OneDrive was never signed in has none of them --
    which is why this returns `None` rather than a guessed path.
    """
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    for var in ("OneDriveCommercial", "OneDrive", "OneDriveConsumer"):
        val = os.environ.get(var)
        if val and Path(val).is_dir():
            return Path(val)
    return None


def machine_name(explicit: str | None) -> str:
    """This machine's label in the synced folder. `COMPUTERNAME` is what Windows itself calls
    it; `platform.node()` is the cross-platform fallback if that is ever unset."""
    return explicit or os.environ.get("COMPUTERNAME") or platform.node() or "unknown-machine"


def projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    return Path(base) / "projects"


def _needs_copy(src: Path, dst: Path) -> bool:
    """True unless `dst` already matches `src`'s size and mtime.

    Skips untouched transcripts on a repeat run instead of re-copying an entire `projects`
    directory every time -- a real timesheet-review session may run this several times in a row.
    A finished transcript file is never edited in place once complete, so this is not the classic
    mtime-only sync hazard (a rewritten-same-size file silently passing as unchanged): a LIVE
    transcript's size keeps growing as it is appended to, and the size check alone catches that.
    """
    if not dst.exists():
        return True
    s, d = src.stat(), dst.stat()
    return s.st_size != d.st_size or int(s.st_mtime) > int(d.st_mtime)


def sync(source: Path, dest: Path) -> tuple[int, int, int]:
    """Copy every `*/*.jsonl` under `source` into `dest`, mirroring the two-level project-dir
    layout. Returns (files copied, files skipped as unchanged, bytes copied).

    Never DELETES anything already at `dest` -- a project directory removed locally should not
    make the synced copy vanish out from under a merge that may be reading it on the other
    machine at the same moment. `dest` only ever grows or gets fresher; a stale entry there is
    surfaced by `timesheet.py`'s staleness note, not silently pruned here.
    """
    copied = skipped = total_bytes = 0
    for f in sorted(source.glob("*/*.jsonl")):
        rel = f.relative_to(source)
        target = dest / rel
        if _needs_copy(f, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            copied += 1
            total_bytes += f.stat().st_size
        else:
            skipped += 1
    return copied, skipped, total_bytes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--onedrive-path", metavar="PATH",
                     help="override OneDrive root (default: autodetect from "
                          "OneDriveCommercial / OneDrive / OneDriveConsumer)")
    ap.add_argument("--machine", metavar="NAME",
                     help="this machine's name in the synced folder (default: COMPUTERNAME)")
    args = ap.parse_args(argv)

    root = onedrive_root(args.onedrive_path)
    if root is None:
        print("Could not find a OneDrive folder on this machine. Pass --onedrive-path, or "
              "confirm OneDrive is signed in here -- OneDriveCommercial, OneDrive and "
              "OneDriveConsumer are all unset or missing.", file=sys.stderr)
        return 1

    name = machine_name(args.machine)
    source = projects_dir()
    if not source.is_dir():
        print("No projects directory at %s -- nothing to sync." % source, file=sys.stderr)
        return 1

    dest = root / SYNC_SUBDIR / name / "projects"
    dest.mkdir(parents=True, exist_ok=True)
    copied, skipped, total_bytes = sync(source, dest)

    print("Synced %s" % source)
    print("    -> %s" % dest)
    print("  %d file(s) copied (%.2f MB), %d unchanged"
          % (copied, total_bytes / 1e6, skipped))
    print("\nOnce OneDrive has finished syncing that folder to the other machine, run there:")
    print('  python plugins/cairn/tools/timesheet.py --projects "%s"' % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
