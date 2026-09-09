#!/usr/bin/env python3
"""PostToolUse hook -- record every git tree this session wrote to OUTSIDE its own project.

WHY A HOOK AND NOT A WRAP STEP
------------------------------
Same reasoning as `item_start.py`: the wrap already asks the question (step 1a, v1.24.0),
and the sessions that get it wrong are the ones that would have skipped a "remember to
list the repos" instruction too. The 2026-08-25 incident (issue #1) was not a missing
step, it was a step whose input the agent supplied from memory. A recorder that watches
the tool calls has no memory to fail.

WHAT IT MATCHES, AND WHAT THAT MISSES
-------------------------------------
`Edit|Write|NotebookEdit` carry a STRUCTURED file path in `tool_input` -- `file_path` /
`notebook_path` -- and are read exactly as before, unconditionally.

`Bash`/`PowerShell` (B39, this file) are now ALSO matched, but only ever ADDITIVELY and
only ever as a best-effort GUESS, never a replacement for the structured path above:
`bash_candidate_paths()` below is a regex over the raw command text, not a shell parser.
It catches the common shapes -- `cd /some/repo && ...`, a heredoc or `sed -i` naming an
absolute path directly -- and nothing else. It does NOT understand quoting, variable
expansion, heredoc BODIES (a heredoc's literal text can contain a path-shaped string that
was never a filesystem target), or relative paths. **State the asymmetry plainly: a false
positive here costs one extra clean repo listed at the next wrap; a false negative is the
status quo (2026-08-25's actual shape) and is unchanged by this file existing.** Recording
too much is the safe failure mode; recording too little is what B39 was filed over.

Cost is not the reason Bash was excluded before -- at 18.3 file-writing calls a session the
tax is ~0.9 s and matching Bash too only reaches ~3 s (measured 2026-08-29, B3). It was
excluded because nobody had written down what a "cheap enough to be worth false positives"
guess would look like; this is that guess, scoped as narrowly as it usefully can be.

**This still would not have caught the 2026-08-25 incident outright** -- that fan-out's
commands are not on file to check against this heuristic -- but the aggravating case B39
was actually filed over (a session under an output style that routes ALL file work through
Bash, reproduced live 2026-09-05, `docs/review/orchestrator-notes.md`) is exactly the shape
this DOES catch: heredocs and `sed`/`python -c` one-liners overwhelmingly name an absolute
path, because that is what `Read`/`Edit`/`Write` require and what agents default to even
when told to prefer Bash.

PRINTS NOTHING, EVER, AND NEVER FAILS A TOOL CALL. Exit 0 on every path -- a missing key,
an unwritable state dir, a malformed payload, anything. A recorder that breaks `Edit` (or
`Bash`) is worse than no recorder, and there is nothing it could usefully say at this point
anyway: the record is read at the next wrap and nowhere else.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reentry_state import project_root                            # noqa: E402
import touched_repos                                              # noqa: E402

# `file_path` covers Edit/Write; `notebook_path` covers NotebookEdit. `path` is accepted
# because it costs nothing and a future write-shaped tool may use it -- the matcher in
# `hooks.json`, not this tuple, is what decides which tools reach here.
PATH_KEYS = ("file_path", "notebook_path", "path")

# The shell-shaped tools whose `tool_input` carries a `command` string instead of a
# structured path. Matched in `hooks.json` alongside Edit/Write/NotebookEdit (B39).
BASH_TOOLS = ("Bash", "PowerShell")

# Bounds so a huge heredoc body can't turn one PostToolUse event into unbounded regex
# work. Long enough for any realistic single command; the cap is a safety rail, not a
# tuning target.
MAX_COMMAND_CHARS = 20_000
MAX_CANDIDATES = 25

# `cd /some/path && ...` / `cd "/some path" ; ...` -- the single most common shape for
# "the rest of this command operates on a different repo". Anchored on a command
# boundary (start of string, `;`, `&`, `|`, or newline) so it doesn't fire on `cd` as a
# substring of a longer word.
_CD_RE = re.compile(
    r'(?:^|[;&\n]|\|\|)\s*cd\s+(?P<path>"[^"]+"|\'[^\']+\'|[^\s;&|]+)',
    re.IGNORECASE,
)

# An absolute-path-SHAPED token: a Windows drive path (`C:\...` / `C:/...`) or a POSIX
# absolute path (`/...`). This is deliberately just a shape test -- it does not know
# whether the token is really a filesystem argument, a URL, part of a comment, or text
# inside a heredoc body; `record()` below only keeps it if it resolves to something that
# is actually inside a git repo, which filters out the overwhelming majority of noise.
_PATH_RE = re.compile(r'(?:[A-Za-z]:[\\/][^\s"\'<>|&;]+)|(?:/[^\s"\'<>|&;]+)')


def _strip_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def bash_candidate_paths(command: str) -> list[str]:
    """Best-effort absolute-path-shaped tokens in a shell command line. See module
    docstring -- this is a regex, not a shell parser, and is meant to be over-inclusive:
    every caller here re-checks each candidate against real git state before recording."""
    if not command:
        return []
    text = command[:MAX_COMMAND_CHARS]
    found: list[str] = []
    for m in _CD_RE.finditer(text):
        found.append(_strip_quotes(m.group("path")))
        if len(found) >= MAX_CANDIDATES:
            return found
    for m in _PATH_RE.finditer(text):
        found.append(m.group(0))
        if len(found) >= MAX_CANDIDATES:
            break
    return found


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
        if not isinstance(event, dict):
            return 0
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0

        root = project_root()
        session = str(event.get("session_id") or "")
        # `agent_id` is null for the parent's own calls and an id for a subagent's, so a
        # fan-out is distinguishable from ordinary work when reading the log back.
        agent = str(event.get("agent_id") or "")
        tool_name = str(event.get("tool_name") or "")

        target = next((str(tool_input[k]) for k in PATH_KEYS
                       if isinstance(tool_input.get(k), str) and tool_input[k]), None)
        if target:
            touched_repos.record(root, target, session=session, agent=agent, tool=tool_name)

        if tool_name in BASH_TOOLS:
            command = tool_input.get("command")
            if isinstance(command, str) and command:
                for candidate in bash_candidate_paths(command):
                    touched_repos.record(root, candidate, session=session, agent=agent,
                                          tool=tool_name)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
