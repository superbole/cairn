#!/usr/bin/env python3
"""Create `~/.claude/CREDENTIALS.md` if it doesn't exist yet. Global, one file, plugin-installed.

WHY THIS EXISTS
---------------
Found the hard way (2026-09-01, LAPTOP1): a GitLab PAT leaked into a chat transcript via a careless
`grep -n` on the file storing it in plaintext. Fixing the leak led to a bigger question -- the PAT
was shared across an unknown number of machines and servers, and nothing tracked where, so there
was no way to know the leak's full blast radius. `CREDENTIALS.md` is the fix: a per-secret record
of which machine holds it, how it's stored, and when it expires, so a rotation is a checklist read
off a file instead of a memory test.

It has to be GLOBAL, not per-project, same reasoning as `ensure_mistakes_file.py`: a credential is
used across every project on a machine, not scoped to one repo. Sits next to `MISTAKES.md` and the
generated `CLAUDE.md`.

DESIGN RULES (same as ensure_mistakes_file.py)
------------------------------------------------
  - NEVER fail the session. Every path returns quietly; the caller wraps this in try/except too.
  - Idempotent. File already exists -> do nothing, print nothing, touch nothing. Existing content
    is NEVER touched by this hook.
  - Say what it did, in ONE line, only on the one run that creates the file.
  - NEVER write a real secret value into the header or anywhere else this hook touches.
"""
import os
import sys
from pathlib import Path

HEADER = """# Credentials

Global, one file, same reasoning as `MISTAKES.md`: a credential (a PAT, an SSH key) is used across
every project on a machine, not scoped to one repo.

**Never stores a value** -- names, locations, and expiry only. The point is that the next rotation
is a checklist read off this file, not a memory test. Update it whenever a credential is created,
moved, or revoked; don't wait for a wrap.

**One secret, one named token, one machine.** Prefer a separate credential per machine over one
shared everywhere -- a leak on one machine then means revoking one credential, not chasing every
host that might have a copy. Naming convention: `<machine>-<purpose>-<expiry-date>`.

```
## <purpose> (<system>)

| Name | Machine | Stored via | Expires | Status |
|---|---|---|---|---|
| `<name>` | `<machine>` | (e.g. Git Credential Manager, SSH agent -- never a plaintext file) | `YYYY-MM-DD` | active / revoked -- why |
```

**Never grep, cat, or log a file that might contain a secret without a flag that hides the
value** -- `grep -c`/`grep -l` to confirm existence or location, never bare `grep -n`/`-p`/`cat` on
a secret-shaped file (`.env`, a shell rc file, anything storing a token). A leaked PAT is what
started this file.

---
"""


def _config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def ensure() -> str | None:
    """Create `~/.claude/CREDENTIALS.md` with its header if absent. Returns a report line or None."""
    target = _config_dir() / "CREDENTIALS.md"
    if target.exists():
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(HEADER, encoding="utf-8", newline="\n")
    except Exception:
        return None
    return f"[to the agent] Created {target} -- this machine had none. Update it whenever a credential changes."


if __name__ == "__main__":
    line = ensure()
    if line:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(line)
