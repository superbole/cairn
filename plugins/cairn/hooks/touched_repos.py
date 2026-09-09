#!/usr/bin/env python3
"""The record of which git trees a session actually WROTE to.

WHY THIS EXISTS
---------------
`tools/check_repos.py` (v1.24.0) asks, at every wrap, whether work landed in the other
repos a session dispatched into. It removed the dependency on the agent remembering to
*check*. It did not remove the second one: the agent still had to *name* the repos, and a
wrap that names seven of eight reports "all clean" for the seven and says nothing at all
about the eighth. On 2026-08-25 exactly that gap put a finished-looking CHANGELOG entry
in this repo while all eight target trees were still dirty (issue #1).

So the naming stops being a memory task. `repo_recorder.py` (PostToolUse) resolves every
written file to its git toplevel and appends the ones OUTSIDE the session's own project
here; `check_repos.py` reads them with no arguments. The agent's list becomes an addition
to the record rather than the whole input.

MEASURED, NOT ASSUMED  (2026-08-29, B3 -- re-measure before quoting these as current)
------------------------------------------------------------------------------------
  * `PostToolUse` fires for SUBAGENT tool calls, carrying `agent_id`/`agent_type` and the
    parent's `session_id`. Verified with a real headless dispatch, not read off docs -- so
    a fan-out is visible here, which is the entire case this was built for.
  * `cwd` in the payload is the PARENT project's, never the written file's tree. Resolving
    `tool_input.file_path` is the only correct method; `cwd` silently answers for the
    wrong repo.
  * Walking parents for a `.git` entry costs nothing over the process spawn (51 ms);
    shelling out to `git rev-parse --show-toplevel` costs 80 ms. Hence `toplevel()` below.

WHERE THE STATE LIVES, AND WHY THIS SHAPE  (the open question in the brief, decided here)
----------------------------------------------------------------------------------------
`state_dir(project_root())` -- under the user's Claude config dir, keyed by the session's
own project, OUTSIDE the repo. Same reasoning as every other file there: a recorder that
wrote into the repo would dirty the tree that the dirty-tree warner watches, so the
plugin would end up warning about itself (`reentry_state.py`).

The file is a **JSONL append log**, not a JSON object rewritten in place. Three reasons,
in order of weight:

  1. **Concurrency.** the user runs several agents at once, and two sessions in the same
     project share one state dir. A read-modify-write of a JSON object loses whichever
     write lands second, silently -- the same class of bug as the wrap that named 7 of 8
     repos. A short `open(..., "a")` write interleaves whole lines rather than corrupting
     the file, and a torn line is skipped by the reader instead of destroying it.
  2. **It is append-only by nature.** "This tree was written to" is a fact that never
     needs revising, only ageing out.
  3. **Cost.** Rejected alternative: one file per session, which needs no dedupe read at
     all. Dropped because `check_repos.py` runs from a Bash step in the wrap and has no
     reliable way to learn its own session id, so it would have to guess which file is
     "this session" -- and guessing is the thing this item exists to remove.

READING: THE WINDOW IS "SINCE THE LAST WRAP", NOT "THIS SESSION"
----------------------------------------------------------------
`touched()` defaults to everything recorded since `.claude/.last_wrap` was written. That
is deliberately WIDER than the current session: a previous session that wrote into a
sibling repo and then ended without wrapping is exactly the failure this plugin exists to
catch, and scoping the read to one session id would hide it. Where there is no wrap
marker at all, entries simply age out after `MAX_AGE_DAYS`.

NEVER RAISES. Every function returns an empty/None value on any failure. The writer runs
inside a `PostToolUse` hook, and a recorder that breaks `Edit` is worse than no recorder.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from reentry_state import MAX_WALK, WRAP_MARKER_REL, state_dir, toplevel  # noqa: F401

RECORD_NAME = "touched_repos.jsonl"

# A retention window, not a measurement. Long enough that a repo written to before a
# holiday weekend is still reported; short enough that the file cannot become an
# ever-growing list of everywhere they have ever worked. Only matters in a project that has
# never wrapped -- once `.last_wrap` exists it, not this, sets the window.
MAX_AGE_DAYS = 30

# Compaction threshold. One line per (repo, session) pair, so this is hundreds of
# fan-outs, not weeks. Rewriting is the only non-atomic operation here, hence rare.
COMPACT_ABOVE_LINES = 500

# `toplevel()` and `MAX_WALK` moved to `reentry_state.py` at v1.29.0 and are re-exported
# above, unchanged. They had to: `dirty_paths`/`unwrapped_commits` there needed the parent
# walk, and this module already imports that one, so importing back would be a cycle.
# `touched_repos.toplevel` still resolves, which is what `record()` below and any external
# caller use.


def _path(root: Path) -> Path | None:
    directory = state_dir(root)
    return None if directory is None else directory / RECORD_NAME


def _same(a: Path, b: Path) -> bool:
    """Path equality that survives Windows' case-insensitive filesystem."""
    try:
        return str(a.resolve()).lower() == str(b.resolve()).lower()
    except Exception:
        return False


def read_records(root: Path) -> list[dict]:
    """Every parseable line, oldest first. Unparseable lines are skipped, not fatal."""
    path = _path(root)
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue                     # a torn concurrent append; drop just this line
        if isinstance(rec, dict) and rec.get("repo"):
            out.append(rec)
    return out


def record(root: Path, file_path: str, session: str = "",
           agent: str = "", tool: str = "") -> Path | None:
    """Note that `file_path` was written, if it lives in a repo other than `root`.

    Returns the repo recorded, or None when there is nothing to record -- which is the
    overwhelmingly common case, since most writes land inside the project itself.
    """
    if not file_path:
        return None
    try:
        repo = toplevel(Path(file_path).expanduser())
    except Exception:
        return None
    if repo is None:                     # in no git repo -- nothing a wrap could check
        return None
    if _same(repo, root):                # the session's own project; other hooks see it
        return None

    path = _path(root)
    if path is None:
        return None
    key = str(repo).lower()
    session = str(session or "")[:64]
    for rec in read_records(root):
        if (str(rec.get("repo", "")).lower() == key
                and str(rec.get("session", "")) == session):
            return repo                  # already recorded this session; stay quiet
    line = json.dumps({"repo": str(repo), "session": session,
                       "agent": str(agent or "")[:64], "tool": str(tool or "")[:32],
                       "at": time.time()}, separators=(",", ":"))
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return None
    _compact(root, path)
    return repo


def _compact(root: Path, path: Path) -> None:
    """Rewrite the log without stale lines, but only when it has actually grown."""
    try:
        records = read_records(root)
        if len(records) <= COMPACT_ABOVE_LINES:
            return
        cutoff = time.time() - MAX_AGE_DAYS * 86400
        kept = [r for r in records if float(r.get("at") or 0) >= cutoff]
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in kept),
                       encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass                             # a log we failed to shrink is still a good log


def _wrap_time(root: Path) -> float | None:
    try:
        return (root / WRAP_MARKER_REL).stat().st_mtime
    except OSError:
        return None


def touched(root: Path, since: float | None = None) -> list[Path]:
    """Distinct repos written to since the last wrap (or `since`), first-seen order.

    Only repos that still exist are returned: a path that has been moved or deleted
    cannot be checked, and reporting it would be noise in the one place that has to stay
    worth reading.
    """
    if since is None:
        since = _wrap_time(root)
    cutoff = since if since is not None else time.time() - MAX_AGE_DAYS * 86400
    seen: set[str] = set()
    out: list[Path] = []
    for rec in read_records(root):
        try:
            when = float(rec.get("at") or 0)
        except (TypeError, ValueError):
            continue
        if when < cutoff:
            continue
        repo = Path(str(rec["repo"]))
        key = str(repo).lower()
        if key in seen or not repo.is_dir():
            continue
        seen.add(key)
        out.append(repo)
    return out
