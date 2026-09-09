#!/usr/bin/env python3
"""Stop + SessionEnd hook — notice when work is at risk of being left behind.

Two things get lost between sessions, and neither announces itself:

  1. **Uncommitted changes.** Measured in atlas on 2026-08-06: a session ran its
     wrap and committed at 20:45, then kept working for 14 more minutes and produced a
     NEXT.md item plus two triaged INBOX findings that were never committed. They sat
     in the working tree for two days and were recovered by accident.
  2. **Commits with no wrap.** Nothing else detects this at all. A clean tree looks
     exactly like a finished session, so the wrap-only steps — NEXT.md, the briefs, doc
     timestamps, the memory pass — get skipped silently. That check is the reason this
     hook exists; coverage of (1) is a bonus.

WHY THIS IS NOT THE OLD `session_end_dirty_check.py`
-----------------------------------------------------
That file was named for `SessionEnd` and wired to `Stop`. `Stop` fires **once per
turn**, not at session end (confirmed in the hooks reference: "When Claude finishes
responding", cadence "once per turn"), and the user confirmed the symptom on 2026-08-21:
*"I definitely see that message repeatedly through a dirty session."* A warning repeated
after every turn is not a warning, it is wallpaper — the hook warned at 07:18 on
2026-08-20 and that session still ended with five uncommitted files, which blocked a
deploy two hours later. Porting that unchanged into every project would have multiplied
a non-intervention, not fixed one.

So the shape here is three-part, and only the first part lives in this file's `Stop`
branch:

  Stop        warn ONLY when the state got worse than the last thing we warned about
              (a new dirty path appeared, or the unwrapped-commit count went up).
              Being told once is information; being told every turn is noise.
  SessionEnd  leave a breadcrumb on disk. It CANNOT speak: the hooks reference is
              explicit that SessionEnd has no `systemMessage` support and its "output
              and exit code are largely ignored… useful for cleanup operations only".
              Shipping an invisible warning would have been indistinguishable from
              shipping nothing.
  SessionStart  the actual intervention, in `session_orientation.py`: the next session
              opens with what the last one left behind, where they are already reading.

NEVER BLOCKS. A Stop hook that traps a session is worse than a dirty tree, and it would
fight the very system this plugin runs: a session that cannot end is a session with no
NEXT.md to resume from. Always exits 0, never uses `decision: block`.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reentry_state import (                                    # noqa: E402
    dirty_paths, last_commit_is_wrap_shaped, project_root, state_dir,
    unwrapped_commits, uses_wrap_ritual, wrap_command,
)

MAX_LISTED = 20
STOP_STATE_TTL_DAYS = 7      # prune per-session fingerprints older than this


def _read_event() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def _prune(directory: Path) -> None:
    cutoff = time.time() - STOP_STATE_TTL_DAYS * 86400
    try:
        for old in directory.glob("stop-*.json"):
            if old.stat().st_mtime < cutoff:
                old.unlink()
    except OSError:
        pass


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(path: Path, payload: dict) -> None:
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def _handle_stop(root: Path, event: dict) -> str | None:
    """The warning text, or None to stay silent."""
    changes = dirty_paths(root)
    if changes is None:
        return None                       # not a repo, or git unavailable
    unwrapped = unwrapped_commits(root) or 0
    paths = sorted(ln[3:].strip() for ln in changes)

    directory = state_dir(root)
    session = str(event.get("session_id") or "unknown").replace("/", "-")[:64]
    seen: dict = {}
    statefile = None
    if directory is not None:
        _prune(directory)
        statefile = directory / f"stop-{session}.json"
        seen = _load(statefile)

    # "Worse than last time", not "different from last time". Committing 3 of 5 files
    # shrinks the set and must NOT re-warn — that is the nagging this rewrite exists to
    # kill. A path that disappears is dropped from the record, so if it comes back it
    # counts as new again.
    warned_paths = set(seen.get("paths") or [])
    warned_count = int(seen.get("unwrapped") or 0)
    worse = bool(set(paths) - warned_paths) or unwrapped > warned_count

    if statefile is not None:
        _save(statefile, {"paths": paths, "unwrapped": unwrapped, "at": time.time()})
    if not worse:
        return None
    # No state directory at all means no memory between turns, and a hook with no memory
    # is the wallpaper this replaced. Better to say nothing than to nag blindly.
    if statefile is None:
        return None

    lines: list[str] = []
    if changes:
        noun = "change" if len(changes) == 1 else "changes"
        lines.append(f"{len(changes)} uncommitted {noun} in the working tree:")
        for ln in changes[:MAX_LISTED]:
            lines.append("  " + ln)
        if len(changes) > MAX_LISTED:
            lines.append("  ... and %d more" % (len(changes) - MAX_LISTED))
        if last_commit_is_wrap_shaped(root):
            lines.append("The last commit on this branch is a wrap (possibly from an "
                         "earlier session) -- this is unwrapped work produced since then. "
                         "Ask me to commit it before you close this session.")
        else:
            lines.append("Ask me to commit these before you close this session.")

    if unwrapped:
        if lines:
            lines.append("")
        noun = "commit" if unwrapped == 1 else "commits"
        lines.append(
            f"{unwrapped} {noun} since the last wrap. The tree is safe, but the wrap is "
            f"what updates NEXT.md, the briefs and memory -- run {wrap_command(root)} "
            f"before you close, or ask me what is still outstanding."
        )
    return "\n".join(lines) or None


def _handle_session_end(root: Path, event: dict) -> None:
    """Record what this session left behind. Prints nothing: SessionEnd cannot speak.

    The next session's orientation reads this and leads with it. That also makes the
    mechanism falsifiable — the breadcrumb is evidence the hook ran, at a moment when
    nothing on screen could have proved it. A mechanism that leaves no evidence it ran
    gets reported as broken and cannot be defended without re-reading the code.
    """
    directory = state_dir(root)
    if directory is None:
        return
    changes = dirty_paths(root)
    _save(directory / "last_exit.json", {
        # The state dir is keyed by a HASH of the path, so nothing could map back from a
        # state directory to the project it describes. `tools/check_repos.py --known`
        # needs exactly that (v1.24.0): the set of repos they actually works in, so a
        # multi-repo wrap can check them without being told each one by name.
        "root": str(root.resolve()),
        "at": time.time(),
        "reason": event.get("reason") or "other",
        "dirty": len(changes) if changes else 0,
        "paths": sorted(ln[3:].strip() for ln in (changes or []))[:MAX_LISTED],
        "unwrapped": unwrapped_commits(root) or 0,
        "wrap_ritual": uses_wrap_ritual(root),
    })


def main() -> int:
    event = _read_event()
    root = project_root()
    if event.get("hook_event_name") == "SessionEnd":
        _handle_session_end(root, event)
        return 0
    message = _handle_stop(root, event)
    if message:
        print(json.dumps({"systemMessage": message}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)                       # never break a session over a warning
