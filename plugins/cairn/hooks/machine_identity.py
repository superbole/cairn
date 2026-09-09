#!/usr/bin/env python3
"""Name the MACHINE this session is running on.

Origin: 2026-08-31, on `ORG-LAPTOP2`. The Queue's top two items both carried `· **run on LAPTOP2**`, and
the session relayed them as "not this machine" — then had to be corrected by the user asking "what
machine do you think you are on?". Nothing in the agent's context named the host: it carries the
cwd, the platform (`win32`), the OS version and the git branch, but never the machine. So the gap
got filled with an assumption, and the assumption was invisible to both of them.

Same root cause as the two-distinct-repos-sharing-one-name confusion recorded the same day in
`briefs/next-md-required-for-membership.md` — a machine-specific fact that only a human could
check, in a file synced across three machines.

A planning doc in another repo already specified this mechanism (hostname -> id table, with
a "self-identify against it" step) but it is documentation enforced by a prompt line, nothing reads
it, and it lives in a repo this plugin cannot depend on.

Prints the RAW hostname and nothing else. No mapping, no comparison against `run on` annotations,
no warning. Every machine's id is currently recoverable from its hostname -- `ORG-LAPTOP1` and
`ORG-LAPTOP2` contain theirs, `WORKSTATION` is its own -- so the annotation the failure turned on is
matchable unaided, and printing the fact is the whole fix.

Comparing them was deliberately a SEPARATE item — B28, done here, 2026-09-05. The hard part was
never the string match, it was the silence boundary: an unrecognised hostname, or an annotation
naming a machine nothing knows about, must produce nothing at all. A check that fires wrongly warns
on every session about items that are correctly placed, which is worse than the annotation going
unchecked -- `item_open.py`'s standard is that every ambiguity resolves to SILENCE. That standard
shapes every function below: `_own_id()` and `mismatch_warning()` return None the instant either
side of the comparison is not a KNOWN id, never a guess.

WHERE THE MAPPING LIVES -- the design question the brief for B28 named directly.
That planning doc already had one, but it is prose enforced by a rule nobody
reads mechanically, and it lives in a repo this plugin cannot depend on (not every project that
uses `reentry` is a checkout beside the others). Three places were considered:

  * A `machines:` block in each project's `NEXT.md` -- rejected. The mapping (which hostname is
    LAPTOP1) is a fact about the FLEET, constant across every project; putting it in NEXT.md means
    retyping the same three rows in every one of the ~9 tracked projects, and it drifts the moment
    one copy is edited and the others are not -- exactly the failure B63 and B65 already describe
    for other per-repo copies of one global fact.
  * An optional per-project file -- same objection, one file instead of one heading.
  * A GLOBAL file, one per machine, outside every repo -- chosen. `~/.claude/MACHINES.md`, same
    shape and same reasoning as `CREDENTIALS.md` and `MISTAKES.md` next to it: "used across every
    project on a machine, not scoped to one repo." `ensure_file()` below creates it empty (a
    generic template, no real hostnames baked into the shipped plugin -- see D1 in this repo's own
    NEXT.md on de-personalising the payload) the first time a session runs anywhere on a machine
    that doesn't have one yet; the user fills in the real rows once, by hand, and every project on
    that machine reads the same copy from then on.

Not scoped to this plugin's own source repo (unlike `version_drift`): a `run on` annotation can appear in any
project's `NEXT.md`. It is scoped by CALL SITE instead — `session_orientation.py` calls
`mismatch_warning()` only on the path that already prints a queue. A project with no `NEXT.md`
stays bit-for-bit silent, which is the property that makes this hook safe to run in every repo.
"""
import os
import platform
import re
from pathlib import Path

# The table lives next to CREDENTIALS.md and MISTAKES.md -- global, one per machine, not
# scoped to a project. Same override as ensure_credentials_file.py's `_config_dir()`.
MACHINES_FILENAME = "MACHINES.md"

_HEADER = """# Machines

One row per machine the user actually uses, so a `run on <id>` annotation in any project's
`NEXT.md` can be checked against the machine a session is really running on. Global, one file,
same reasoning as `CREDENTIALS.md` and `MISTAKES.md`: used across every project on this machine,
not scoped to one repo.

Fill in real rows below -- one per machine, `id` is whatever short form `NEXT.md` annotations use
(`LAPTOP1`, `LAPTOP2`, ...). Leave a machine out and annotations naming it are silently never checked,
same as leaving this whole file empty; that is the safe failure, not a bug to work around.

| Hostname | Id |
|---|---|
| `<hostname substring, e.g. ORG-LAPTOP1>` | `<id used in NEXT.md, e.g. LAPTOP1>` |

---
"""

# One markdown table row: `| cell | cell |`. Matches the header/example row too -- callers
# filter those out by content, not by position, so a hand-edited file that reorders things
# still parses.
_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")

# `**run on LAPTOP2**` -- the annotation shape used throughout this repo's own NEXT.md today.
_RUN_ON_RE = re.compile(r"\*\*run on\s+([A-Za-z0-9][\w.-]*)\*\*", re.IGNORECASE)


def hostname() -> str:
    """The raw hostname, stripped; '' if the OS won't say.

    Split out of `check()` (B40, 2026-09-05) so `session_orientation.py` can compare a
    `check after `next session on <id>`` watch trigger against the machine actually running
    this session, without re-parsing the `machine: ` line `check()` prints. Same value,
    same fallible call — `check()` is now a one-line wrapper around this.
    """
    try:
        return (platform.node() or "").strip()
    except Exception:
        return ""


def check() -> str | None:
    """One line naming this machine, or None if the OS won't say."""
    name = hostname()
    return f"machine: {name}" if name else None


def _config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def ensure_file() -> str | None:
    """Create `~/.claude/MACHINES.md` with an empty template if absent. Returns a report line
    the ONE run that creates it, None every other time -- same contract as
    `ensure_credentials_file.ensure()` and `ensure_mistakes_file.ensure()`.
    """
    target = _config_dir() / MACHINES_FILENAME
    if target.exists():
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_HEADER, encoding="utf-8", newline="\n")
    except Exception:
        return None
    return (f"[to the agent] Created {target} -- empty. Fill in this machine's hostname and "
            f"id (and any others the user uses) so `run on <machine>` annotations can be checked.")


def _load_table() -> dict[str, str]:
    """hostname (lowercased) -> id, from `~/.claude/MACHINES.md`.

    Empty on ANY problem -- missing file, unreadable, no real rows yet, a line that doesn't
    parse as a table row. Empty means every downstream check stays silent; that is the
    intended degrade, not an error path to fix.
    """
    try:
        text = (_config_dir() / MACHINES_FILENAME).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    table: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        m = _ROW_RE.match(stripped)
        if not m:
            continue
        # Backticks stripped BEFORE the placeholder check below, not after -- the shipped
        # template's example row is itself backtick-wrapped (`` `<hostname substring>` ``), so
        # checking `startswith("<")` on the raw cell missed it entirely and would have loaded
        # the literal placeholder text as a "known machine". Caught by testing against the
        # actual template text, not a simplified fixture.
        host, mid = m.group(1).strip().strip("`"), m.group(2).strip().strip("`")
        # Skip the header row, the `---` separator row, and the placeholder example row --
        # all three are angle-bracketed or dashed rather than a real hostname/id pair.
        if not host or not mid:
            continue
        if host.lower() in ("hostname",) or mid.lower() in ("id",):
            continue
        if host.startswith("<") or mid.startswith("<") or set(host) == {"-"} or set(mid) == {"-"}:
            continue
        table[host.lower()] = mid
    return table


def _own_id(host: str, table: dict[str, str]) -> str | None:
    """This machine's id per the table, or None if the table doesn't recognise it.

    Exact match first, then substring either direction -- a table row is allowed to be a
    fragment of the real hostname (`ORG-LAPTOP1` contains `LAPTOP1`), the same tolerance the module
    docstring already documents for the annotation itself.
    """
    if not host:
        return None
    low = host.lower()
    if low in table:
        return table[low]
    for row_host, mid in table.items():
        if row_host in low or low in row_host:
            return mid
    return None


def mismatch_warning(nxt_lines: list[str]) -> str | None:
    """A queue item annotated `**run on <X>**` where <X> is a KNOWN machine that is NOT this
    one -- None the instant either half of that is not established.

    Fires ONLY on a positive mismatch between two known ids:
      - no table on this machine (nobody has filled in `~/.claude/MACHINES.md` yet) -> None
      - this machine's own hostname isn't in the table -> None (can't judge from the outside)
      - the annotation names an id the table has never heard of -> that annotation is ignored,
        not treated as a mismatch (someone may be renaming a machine; a stale row elsewhere is
        not evidence this one is wrong)
      - the annotation names a known id that IS this machine -> not a mismatch, no line
    Only the remaining case -- a known id, and it disagrees with this machine's own known id --
    produces a line, and it names every mismatched id in the queue at once rather than one line
    per item, so a project with several `run on` annotations still gets a single warning.
    """
    table = _load_table()
    if not table:
        return None
    my_id = _own_id(hostname(), table)
    if my_id is None:
        return None
    known_ids = {mid.lower() for mid in table.values()}
    mismatched = set()
    for ln in nxt_lines:
        for m in _RUN_ON_RE.finditer(ln):
            target = m.group(1)
            if target.lower() in known_ids and target.lower() != my_id.lower():
                mismatched.add(target)
    if not mismatched:
        return None
    names = ", ".join(sorted(mismatched))
    noun = "item is" if len(mismatched) == 1 else "items are"
    return (f"queue {noun} marked `run on` a different machine ({names}) -- this session is "
            f"on {my_id}.")
