#!/usr/bin/env python3
"""Create `~/.claude/MISTAKES.md` if it doesn't exist yet. Global, one file, plugin-installed.

WHY THIS EXISTS
---------------
The user asked (2026-08-27) for a running log of mistakes -- theirs, the agent's, and the reentry
system's own process failures -- so that recurring ones can eventually be spotted and designed
against, instead of re-discovered and re-corrected session after session. `feedback` memories
already capture one-off corrections; this is the append-only log they get pulled from when a
pattern is worth building something to prevent. It is a log, not an analysis mechanism -- no
categorisation or review step yet, by design (2026-08-27).

It has to be GLOBAL, not per-project, same reasoning as install_rules.py: the goal is to see
patterns across every project the user touches, not just one. So it lives at `~/.claude/MISTAKES.md`
next to the generated CLAUDE.md, and this hook's only job is to make sure the file exists with its
header -- it never rewrites content, unlike install_rules.py's managed block. `/cairn:wrap`
appends to it; this hook just guarantees the file and header are there on a fresh machine.

DESIGN RULES (same as install_rules.py)
----------------------------------------
  - NEVER fail the session. Every path returns quietly; the caller wraps this in try/except too.
  - Idempotent. File already exists -> do nothing, print nothing, touch nothing. Existing content
    (including anything the user or a wrap appended) is NEVER touched by this hook.
  - Say what it did, in ONE line, only on the one run that creates the file.
"""
import os
import sys
from pathlib import Path

HEADER = """# Mistakes

A running log across every project, appended to at `/cairn:wrap` time. Not a blame ledger --
the point is to notice what keeps happening so it can eventually be fixed systematically instead
of re-corrected each time. One entry per mistake caught; newest first.

Categories: **agent** (something the agent did that needed correcting), **user** (a misstep
on their side, logged the same way, no judgement -- just pattern data), **process** (the reentry
system itself failed to prevent something -- distinct from either party's error).

```
## YYYY-MM-DD -- <project> -- <category>

What happened, what it should have been instead, in a sentence or two.
```

---
"""


def _config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def ensure() -> str | None:
    """Create `~/.claude/MISTAKES.md` with its header if absent. Returns a report line or None."""
    target = _config_dir() / "MISTAKES.md"
    if target.exists():
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(HEADER, encoding="utf-8", newline="\n")
    except Exception:
        return None
    return f"[to the agent] Created {target} -- this machine had none. /cairn:wrap appends to it."


if __name__ == "__main__":
    line = ensure()
    if line:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(line)
