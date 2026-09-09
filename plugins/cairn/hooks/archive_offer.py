#!/usr/bin/env python3
"""The archive-offer marker — remembers an unanswered archive question within a session.

WHY THIS EXISTS
---------------
Wrap step 10 asks whether to archive, once, right after the wrap. If they decline (or the
conversation moves on without a clear answer), the wrap is still correctly reported later
as "no wrap needed" — but nothing reconnected THAT verdict to the archive offer, because
the offer and the verdict were computed independently. Caught 2026-08-28: they wrapped, kept
working, and the later "no wrap needed" dropped the archive question on the floor. See
`skills/wrap/references/incidents.md`.

Not: always offering to archive on a clean tree — step 10's gate (only ask if they asked to
wrap, or agreed when it was suggested) stays exactly as strict. This only carries an
offer they already earned forward to the next verdict in the SAME session, so a long
conversation or a compaction doesn't silently lose it the way conversation memory can.

WHERE THE STATE LIVES
----------------------
`state_dir()`, outside the repo — same reasoning as `item_open.py`: a marker written by
code into the repo makes `git status` dirty, and this marker's whole job is to survive
being checked by a hand that is also checking git status. It does not need a session id
like `item_open.py`'s does; it is only ever read back by the same session that wrote it,
within one conversation, so there is nothing to disambiguate against a later session.

WHAT CLEARS THE `--stamp` (declined-and-outstanding) MARKER
-------------------------------------------------------------
Only two things, both meaning the offer is no longer outstanding: they say yes (the
session archives, so there is no "later" for that marker to matter to), or a subsequent
wrap's own step 10 asks again and overwrites it (accepted or declined). It is NOT cleared
by HEAD moving on its own — `pending()` checks that itself, so a marker whose HEAD no
longer matches just reads as stale rather than needing an explicit clear.

B35 — "NONE" COVERS TWO OPPOSITE STATES, AND WHY `pending()` IS NOT WHAT'S WRONG
---------------------------------------------------------------------------------
`--check` printed `NONE` both when the offer was made and accepted (nothing outstanding —
correct) and when it was *never made at all* (also outstanding, reported as fine). Caught
2026-08-31: a wrap done by hand skipped step 10 entirely; `--check` said `NONE` and that
silence was read as "the archive question was settled".

**Weighed and rejected: changing what `pending()` computes.** `pending()` answers one
question only — "is there a DECLINED offer still relevant to the CURRENT head" — and a
cleared marker and a never-created one are genuinely the same answer to THAT question:
nothing to carry forward. Redefining it to also mean "was the question ever asked" would
make it answer two questions with one return value, which is the exact failure this file
exists to prevent one level up (the wrap verdict). So `pending()` is unchanged, and every
existing caller of it keeps its exact contract.

**What's actually missing is a second, independent fact: was the offer asked at all for
this HEAD** — regardless of the answer. `stamp()`/`clear()` are only ever called once the
answer is already known (decline / accept), so neither can supply that fact; a THIRD
marker, written unconditionally at ask-time, is the only way to. Added here as
`stamp_asked()` / `--stamp-asked`, deliberately NOT reusing `MARKER_NAME` — `clear()`
(called on accept) must keep deleting only the declined-and-outstanding marker, never this
one, or an accepted offer would look identical to `NEVER_ASKED` on the very next check.

**Gated behind ever having been used, so an unmigrated project's `--check` is untouched.**
`skills/wrap/SKILL.md` step 10 does not call `--stamp-asked` today — wiring that in is a
one-line addition to step 10 (call it unconditionally, right when the question is asked,
before the answer is known) that belongs to whoever owns that file, not to this one. Until
that call exists, `_asked_path(root)` never gets written, and `--check` prints exactly the
same `NONE` it always has — `NEVER_ASKED` only appears once the mechanism has actually
recorded at least one ask in this project, so today's behaviour for every project that has
not been wired up is BYTE IDENTICAL to before this change.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reentry_state import git, project_root, state_dir            # noqa: E402

MARKER_NAME = "archive_offer.json"

# A SEPARATE file from MARKER_NAME (B35) -- it records "the question was asked",
# independent of the answer, and must never be touched by clear() (which only means
# "they said yes, the DECLINED marker above is moot"). See the B35 note in the module
# docstring for why these cannot be the same file.
ASKED_MARKER_NAME = "archive_offer_asked.json"


def _path(root: Path) -> Path | None:
    directory = state_dir(root)
    return None if directory is None else directory / MARKER_NAME


def _asked_path(root: Path) -> Path | None:
    directory = state_dir(root)
    return None if directory is None else directory / ASKED_MARKER_NAME


def stamp(root: Path, head: str) -> None:
    """Record that the archive offer at `head` was asked and not accepted."""
    path = _path(root)
    if path is None:
        return
    try:
        path.write_text(json.dumps({"head": head, "at": time.time()}), encoding="utf-8")
    except OSError:
        pass


def clear(root: Path) -> None:
    path = _path(root)
    if path is None:
        return
    try:
        path.unlink()
    except OSError:
        pass


def pending(root: Path) -> str | None:
    """The HEAD sha an unanswered offer was made at, if HEAD hasn't moved since. None
    otherwise — no marker, an unreadable one, or one superseded by new commits."""
    path = _path(root)
    if path is None:
        return None
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    head = marker.get("head") if isinstance(marker, dict) else None
    if not head:
        return None
    current = git(root, "rev-parse", "HEAD")
    return head if current and current == head else None


def stamp_asked(root: Path, head: str) -> None:
    """Record that step 10 ASKED the archive question at `head`, regardless of the
    answer (B35). Call this once, unconditionally, at ask-time -- before the answer is
    known. Never call it in place of `stamp()`/`clear()`; it answers a different
    question ("was this asked at all") and both markers are read independently."""
    path = _asked_path(root)
    if path is None:
        return
    try:
        path.write_text(json.dumps({"head": head, "at": time.time()}), encoding="utf-8")
    except OSError:
        pass


def asked_marker_used(root: Path) -> bool:
    """Whether `stamp_asked()` has EVER been called for this project. Gates the
    NEVER_ASKED distinction so a project whose wrap skill doesn't call `--stamp-asked`
    yet sees exactly today's `NONE` behaviour -- see the B35 note above."""
    path = _asked_path(root)
    return path is not None and path.is_file()


def asked_at_head(root: Path) -> str | None:
    """The HEAD sha the most recent `stamp_asked()` recorded, if it still matches HEAD.
    None if there is no marker, an unreadable one, or HEAD has moved on since — same
    shape as `pending()`, deliberately."""
    path = _asked_path(root)
    if path is None:
        return None
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    head = marker.get("head") if isinstance(marker, dict) else None
    if not head:
        return None
    current = git(root, "rev-parse", "HEAD")
    return head if current and current == head else None


def main() -> int:
    root = project_root()
    args = sys.argv[1:]
    if not args:
        print("usage: archive_offer.py --stamp | --stamp-asked | --clear | --check")
        return 2
    if args[0] == "--stamp":
        head = git(root, "rev-parse", "HEAD")
        if not head:
            print("not a git repo, or no commits yet — nothing to stamp")
            return 1
        stamp(root, head)
        print(f"archive offer recorded as outstanding at {head[:12]}")
        return 0
    if args[0] == "--stamp-asked":
        head = git(root, "rev-parse", "HEAD")
        if not head:
            print("not a git repo, or no commits yet — nothing to stamp")
            return 1
        stamp_asked(root, head)
        print(f"archive offer recorded as ASKED at {head[:12]} (B35 — answer not yet known)")
        return 0
    if args[0] == "--clear":
        clear(root)
        print("archive offer marker cleared")
        return 0
    if args[0] == "--check":
        head = pending(root)
        if head:
            print(f"PENDING — archive was offered and not accepted at {head[:12]}, "
                  "still HEAD: carry it forward with the next verdict")
        elif not asked_marker_used(root):
            # Unmigrated project (or `--stamp-asked` simply never fired yet): identical
            # to pre-B35 behaviour, on purpose.
            print("NONE — no outstanding archive offer for the current HEAD")
        elif asked_at_head(root):
            print("NONE — archive was asked and resolved at the current HEAD, "
                  "nothing outstanding")
        else:
            print("NEVER_ASKED — no record the archive question was asked for the "
                  "current HEAD (step 10 may have been skipped) — this is NOT "
                  "confirmation the archive question was settled")
        return 0
    print("usage: archive_offer.py --stamp | --stamp-asked | --clear | --check")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
