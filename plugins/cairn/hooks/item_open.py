#!/usr/bin/env python3
"""The open-item marker — a record that a session STARTED a queue item.

WHY THIS EXISTS
---------------
`.claude/.last_wrap` records that a session *wrapped*. Nothing anywhere recorded that a
session *started an item*, so the plugin's own worst failure was invisible: a session
runs `/cairn:next`, starts item 3, does half the work, and ends without a wrap.
`NEXT.md` still shows item 3 queued — byte-identical to an item nobody has ever touched
— and the half-done work exists only in that session's transcript. Reached by the one
path the system did not watch (issue #2).

This module owns the marker: writing it, resolving it, and deciding when an unresolved
one is worth saying out loud. `item_start.py` (UserPromptSubmit) writes it;
`session_orientation.py` reads it into the existing "did not finish cleanly" block.

WHERE THE STATE LIVES
---------------------
`state_dir()` — under the user's Claude config dir, OUTSIDE the repo. Same reasoning as
every other file there (see `reentry_state.py`): a marker written by CODE into the repo
makes `git status` dirty, and a dirty-tree warner that dirties the tree warns about
itself forever. `.last_wrap` is repo-local only because a documented, human-runnable
shell step writes it. This one is not.

THE CRY-WOLF BOUNDARY  (the decision this module exists to encode, 2026-08-28)
-----------------------------------------------------------------------------
A warning that fires whenever they deliberately changes their mind is worse than no warning:
it trains them to skip the box, and that box also carries uncommitted files. So the
resolution rules are deliberately generous and every ambiguity resolves to SILENCE.

  * **Must an orphan survive a session boundary?** Yes, by construction. The marker is
    only ever *read* at `SessionStart`, so anything found there was written by an earlier
    session. Changing their mind inside one session just overwrites the marker; that is not
    an orphan and is never reported. (The session id is stored anyway, so a `resume`
    re-firing `SessionStart` in the same session cannot report itself.)

  * **Does a commit touching the item's files count as "closed enough"?** No — and this
    is the one place we are deliberately strict. The QUEUE is the authority on whether an
    item is open, not the diff. Commits that leave the item queued are exactly the
    half-done case worth catching. What counts is the item leaving `## Queue`, by any
    route: a wrap, a hand edit, another session closing it.

  * **What clears the marker besides a wrap?** Three things, all passive — nothing here
    asks an agent to remember a step, because the sessions that produce orphans are
    precisely the ones that went off-script:
      1. the item's title no longer appears in `## Queue` (closed by any route);
      2. `.claude/.last_wrap` is newer than the marker (a wrap ran after the item opened);
      3. a later item start overwrites it.
    Title matching is loose, and a title we cannot find is treated as CLOSED, never as
    open. A reworded title therefore goes quiet rather than nagging.

  * **How often does an unresolved orphan speak?** Once in full, then one line. The full
    block is what transfers the fact into their attention at the moment they can act; a
    second identical block at the next start is alarm fatigue. But going fully silent
    would delete the fact, so it degrades to a single line for as long as it is real. It
    still dies the instant the item leaves the queue or a wrap runs.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

from reentry_state import WRAP_MARKER_REL, state_dir

MARKER_NAME = "item_open.json"

# `1. **Title** — Opus 5 · high · AFK/Auto`, tolerating the bolded-number variant that
# `_QUEUE_ITEM_RE` in the orientation also tolerates.
_ITEM_RE = re.compile(r"^\s*\*{0,2}(\d+)\.\s*\*{0,2}(.+?)(?:\*\*|\s+—|\s+--|$)")


def _norm(title: str) -> str:
    """Loose identity for a queue title: case, punctuation and spacing are all noise."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def queue_items(root: Path) -> list[tuple[int, str]]:
    """(number, title) for every numbered line in `## Queue`. Empty on any failure."""
    try:
        lines = (root / "NEXT.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[tuple[int, str]] = []
    section = None
    for ln in lines:
        stripped = ln.strip()
        if stripped == "---":
            section = "footer"
            continue
        if stripped.startswith("## "):
            low = stripped.lower()
            section = ("watching" if "watching" in low else
                       "decisions" if "decision" in low else "queue")
            continue
        if section != "queue":
            continue
        m = _ITEM_RE.match(ln)
        if m:
            out.append((int(m.group(1)), m.group(2).strip().rstrip("*").strip()))
    return out


def _path(root: Path) -> Path | None:
    directory = state_dir(root)
    return None if directory is None else directory / MARKER_NAME


def read(root: Path) -> dict | None:
    path = _path(root)
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def clear(root: Path) -> None:
    path = _path(root)
    if path is None:
        return
    try:
        path.unlink()
    except OSError:
        pass


def stamp(root: Path, number: int, session: str = "") -> dict | None:
    """Record that item `number` just started. Returns the marker, or None.

    Refuses to write for a number that is not actually in the Queue — a false marker is
    the only way this mechanism can invent a warning about work that never happened.
    """
    title = next((t for n, t in queue_items(root) if n == number), None)
    if title is None:
        return None
    path = _path(root)
    if path is None:
        return None
    marker = {"item": number, "title": title, "at": time.time(),
              "session": str(session or "")[:64], "reported": None}
    try:
        path.write_text(json.dumps(marker), encoding="utf-8")
    except OSError:
        return None
    return marker


def _resolved(root: Path, marker: dict) -> bool:
    """True when the item this marker names is no longer open. Ambiguity → True."""
    wrap = root / WRAP_MARKER_REL
    try:
        if wrap.stat().st_mtime >= float(marker.get("at") or 0):
            return True                  # a wrap ran after the item was opened
    except (OSError, TypeError, ValueError):
        pass                             # no marker / unreadable — fall through to title
    wanted = _norm(str(marker.get("title") or ""))
    if not wanted:
        return True
    return not any(_norm(t) == wanted for _n, t in queue_items(root))


def orphan(root: Path, session: str = "") -> tuple[dict, bool] | None:
    """(marker, is_first_report) for a still-open item from an EARLIER session.

    None when there is nothing to say — which is the overwhelmingly common case. Clears
    the marker as a side effect whenever it turns out to be resolved, so a stale one can
    never accumulate.
    """
    marker = read(root)
    if marker is None:
        return None
    if session and str(marker.get("session") or "") == str(session):
        return None                      # a `resume` re-firing inside the same session
    if _resolved(root, marker):
        clear(root)
        return None
    return marker, not marker.get("reported")


def mark_reported(root: Path) -> None:
    """Downgrade this orphan to one line from here on. Never re-upgrades."""
    marker = read(root)
    if marker is None or marker.get("reported"):
        return
    marker["reported"] = time.time()
    path = _path(root)
    if path is None:
        return
    try:
        path.write_text(json.dumps(marker), encoding="utf-8")
    except OSError:
        pass


def describe(marker: dict, first: bool) -> list[str]:
    """The lines the orientation folds into its existing left-behind block."""
    def _when(key: str) -> str:
        try:
            return datetime.fromtimestamp(float(marker[key])).strftime("%Y-%m-%d")
        except Exception:
            return "an earlier session"

    number = marker.get("item", "?")
    title = marker.get("title", "")
    if not first:
        return ['Item %s "%s" is STILL open since %s (first flagged %s).'
                % (number, title, _when("at"), _when("reported"))]
    return [
        'Item %s "%s" was started %s and never closed.' % (number, title, _when("at")),
        "     It is still queued as if untouched, so any half-done work exists only in "
        "that session's transcript — check that before starting it again.",
    ]
