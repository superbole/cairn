#!/usr/bin/env python3
"""PreToolUse(Bash): refuse `git commit` when the staged diff has not been read.

WHY THIS EXISTS (2026-09-23, `workspace`)
-----------------------------------------
The rule in `rules/CLAUDE.md` said "stage with explicit pathspecs, never `git add .`"
and a session obeyed it exactly -- `git add INBOX.md` -- while committing six bullets a
scheduled task had appended to that file, under a message describing only the one line
the session wrote.

The rule governs WHICH FILES you stage. It quietly assumes a named file is entirely
yours, which is false for any file a background process appends to: a capture inbox, a
generated report, a scan log. So a pathspec is not a review, and the rule could not have
caught it.

The signal WAS there and was skipped: `git diff --cached --stat` printed "7 insertions"
for a one-line change. Read, noted as odd, committed anyway. So this guard does not add a
new check -- it makes the existing one non-optional, which is the only part that failed.

WHAT IT DOES NOT DO
-------------------
It says nothing about the REMOTE. Whether `origin` has moved, whether you are about to
commit onto a merged or abandoned branch, whether another machine pushed first -- none of
that is visible here and none of it is this hook's job. `push_check.py` and the
orientation's divergence banner cover their own parts of that; the gap between them is
tracked separately.

FAILURE POSTURE
---------------
Any error, any uncertainty, any unparseable input: exit 0 and allow. A guard that blocks
work because it could not read its own state is worse than the defect it prevents.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ALLOW = 0
BLOCK = 2

# A read is only good for this long. Long enough that a diff read at the top of a turn
# still counts when the commit lands a few tool calls later; short enough that a diff
# read half an hour and several edits ago does not.
READ_TTL_SECONDS = 900


def _run(args, cwd):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


def _repo_root(cwd):
    out = _run(["git", "rev-parse", "--show-toplevel"], cwd)
    return out.strip() or None


# A git verb only counts at a COMMAND POSITION -- start of string, or after a
# separator. Without this the guard fires on any command that merely CONTAINS the
# words, such as a heredoc, a grep pattern or a JSON payload literal, which made its
# own test script unrunnable (2026-09-23).
_AT_CMD = r"(?:^|[\n;|]|&&|\|\||\bthen\b|\bdo\b)\s*"
RE_ADD = re.compile(_AT_CMD + r"git\s+(?:-C\s+\S+\s+)?add\b")
RE_COMMIT = re.compile(_AT_CMD + r"git\s+(?:-C\s+\S+\s+)?commit\b")
RE_DIFF = re.compile(_AT_CMD + r"git\s+(?:-C\s+\S+\s+)?diff\b")
RE_CD = re.compile(_AT_CMD + r"cd\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")
RE_DASH_C = re.compile(r"git\s+(?:--\w[\w-]*\s+)*-C\s+(\"[^\"]+\"|'[^']+'|\S+)")


def _cwd_for(command, hook_cwd):
    """Where the git command will ACTUALLY run.

    `git -C <path>` wins, then the last `cd <path>` in the command, then the session's
    cwd. The `cd` case is not an edge case: `cd <repo> && git commit` is the ordinary
    shape for touching a second repository, and while it was unhandled the guard
    silently evaluated the SESSION's repo instead -- reporting "nothing staged" and
    allowing the commit. That is the exact multi-repo situation the guard was written
    for, so it passed its standalone tests and would have caught nothing in practice
    (found 2026-09-23 by running it against a real session).
    """
    m = RE_DASH_C.search(command)
    if m:
        candidate = m.group(1).strip("\"'")
        if os.path.isdir(candidate):
            return candidate
    last = None
    for m in RE_CD.finditer(command):
        candidate = os.path.expanduser(m.group(1).strip("\"'"))
        if os.path.isdir(candidate):
            last = candidate
    return last or hook_cwd


def _state_path(root):
    try:
        from reentry_state import state_dir
        return Path(state_dir(Path(root))) / "staged_review.json"
    except Exception:
        return None


def _load(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return ALLOW

    if payload.get("tool_name") != "Bash":
        return ALLOW
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "git" not in command:
        return ALLOW

    hook_cwd = payload.get("cwd") or os.getcwd()
    cwd = _cwd_for(command, hook_cwd)
    root = _repo_root(cwd)
    if not root:
        return ALLOW
    now = time.time()

    # Checked BEFORE any state lookup: this shape is wrong on its face and needs no
    # history to judge. It also has to survive a state dir that cannot be read, which is
    # exactly when a guard is most likely to be quietly doing nothing.
    if RE_ADD.search(command) and RE_COMMIT.search(command):
        return _refuse(
            "This command stages and commits in one step, so nothing reads the diff in "
            "between. That is how six lines written by a scheduled task were committed "
            "under a message describing one (2026-09-23).",
            _run(["git", "diff", "--cached", "--name-only"], cwd).split(), command,
        )

    state_file = _state_path(root)
    if state_file is None:
        return ALLOW
    state = _load(state_file)

    # A diff that shows staged content counts as the review. `git show` of a commit does
    # not -- that is reading history, not what is about to become history.
    reads_staged_diff = RE_DIFF.search(command) and "--stat" not in command
    stages = RE_ADD.search(command)
    commits = RE_COMMIT.search(command)

    if stages:
        state["staged_at"] = now
        state.pop("read_at", None)
        _save(state_file, state)
        return ALLOW

    if reads_staged_diff:
        state["read_at"] = now
        _save(state_file, state)
        return ALLOW

    if commits:
        if "--amend" in command and not _run(["git", "diff", "--cached", "--name-only"], cwd).strip():
            return ALLOW
        staged = _run(["git", "diff", "--cached", "--name-only"], cwd).split()
        if not staged:
            return ALLOW
        read_at = state.get("read_at")
        staged_at = state.get("staged_at")
        fresh = read_at and (now - read_at) < READ_TTL_SECONDS
        after_staging = read_at and (not staged_at or read_at >= staged_at)
        if fresh and after_staging:
            state.pop("read_at", None)
            state.pop("staged_at", None)
            _save(state_file, state)
            return ALLOW
        return _refuse(
            "Nothing has read the staged diff since it was staged.",
            staged, command,
        )

    return ALLOW


def _refuse(why, staged, command) -> int:
    listing = "\n".join(f"  - {p}" for p in staged[:20]) or "  (could not list staged paths)"
    more = f"\n  … and {len(staged) - 20} more" if len(staged) > 20 else ""
    sys.stderr.write(
        "BLOCKED by cairn staged_review_guard.\n\n"
        f"{why}\n\n"
        "Staged now:\n" + listing + more + "\n\n"
        "Run `git diff --cached` (without --stat) and READ it, then commit as a separate\n"
        "call. A pathspec is not a review: capture files, generated files and anything a\n"
        "scheduled task appends to can carry lines you did not write. If the diff contains\n"
        "changes that are not yours, commit them separately under their own message, or\n"
        "unstage them — do not fold them into yours.\n"
    )
    return BLOCK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(ALLOW)
