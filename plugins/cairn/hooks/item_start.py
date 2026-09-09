#!/usr/bin/env python3
"""UserPromptSubmit hook — stamp the open-item marker when they start a queue item.

WHY A HOOK AND NOT A SKILL STEP
-------------------------------
The obvious place is `/cairn:next` step 7, which already renames the session when an
item starts. It is the wrong place to put the *only* copy. This marker exists to catch
sessions that went off-script and ended without a wrap — and an agent that skipped the
wrap is precisely the agent that would have skipped a "stamp the marker" instruction too.
Same reasoning the relay tier is computed in a hook rather than judged by the agent
(`session_orientation.py`, 2026-08-25): the mechanism has to work when the agent does not.

So the primary writer is deterministic and reads only what they typed. The skill keeps a
one-line fallback for the case this regex cannot see — an item started by conversation
rather than by "do 3" — via `python hooks/item_start.py --item N`.

PRINTS NOTHING, EVER. `UserPromptSubmit` stdout on exit 0 is appended to the agent's
context, so any output here would be a per-turn tax on every prompt in every project.
The marker is read at the next `SessionStart` and nowhere else.

NARROW BY DESIGN. Only the documented invocation shape is recognised, anchored at both
ends, and only for a number that is really in `## Queue` (`item_open.stamp` re-checks).
A false marker is the one way this mechanism can invent a warning about work that never
happened, so "do 3 of those" and a bare "3" answering a question are both left alone.
Missing a real start costs nothing beyond the status quo; inventing one costs trust.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reentry_state import project_root                            # noqa: E402
import item_open                                                  # noqa: E402

# "do 1", "do item 2", "let's start #3", "please do 4." — and nothing else.
_START_RE = re.compile(
    r"^\s*(?:please\s+)?(?:let'?s\s+|lets\s+|can\s+you\s+|could\s+you\s+)?"
    r"(?:do|start|begin|run|take|tackle)\s+(?:on\s+)?(?:item\s*|number\s*|#)?"
    r"(\d{1,2})\s*(?:please)?\s*[.!]?\s*$",
    re.IGNORECASE,
)


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    m = _START_RE.match(str(event.get("prompt") or ""))
    if not m:
        return 0
    item_open.stamp(project_root(), int(m.group(1)),
                    str(event.get("session_id") or ""))
    return 0


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--item":
            # The skill's fallback, for an item started without them typing "do N".
            marker = item_open.stamp(project_root(), int(sys.argv[2]))
            print("marked open: item %s" % marker["item"] if marker else
                  "not marked — no such item in the Queue")
            sys.exit(0)
        sys.exit(main())
    except Exception:
        sys.exit(0)                      # never break a turn over a breadcrumb
