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
expansion, or heredoc BODIES (a heredoc's literal text can contain a path-shaped string that
was never a filesystem target). **State the asymmetry plainly: a false
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

RELATIVE PATHS (B82). Seen live 2026-09-26: `Add-Content ..\\cursor-v1-other\\y.txt ...` fired
the hook and recorded nothing, because only absolute-shaped tokens were tried. Cursor's agent
writes relative paths by default; Claude's does it less, but both harnesses had the hole. A
token that LOOKS like a relative path (`..\\x`, `../x`, `./x`, `x/y`) is now joined onto the
command's working directory -- the payload's `cwd`, or the project root when that is empty --
and onto every `cd` target earlier in the same command, then put through the same git
re-check as everything else. A bare word with no separator (`notes.txt`) is not tried: it
names the working directory itself, which is the project's own tree in every ordinary case,
and that is not a foreign write. Things that are path-shaped but are not paths (`origin/main`,
`HEAD:a/b`, `$HOME/x`, a URL, a flag) either are refused by shape below or resolve into the
project and are dropped by `record()`'s own-project check. Same asymmetry as above: a read-only
`git -C ../other log` is recorded too, exactly as a read-only `cd ../other` already was.

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
import harness                                                    # noqa: E402

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
#
# B82: each shape must START a token. Before, `/x` was matched in the middle of `../x`,
# `$HOME/x` and every `origin/main`, so sixty such words used up `MAX_CANDIDATES` before
# a real absolute target later in the same command was reached. `~/x` is its own shape
# now (`record()` expands it); it used to be matched as `/x`, a different path.
_PATH_RE = re.compile(r'(?:(?<![\w])[A-Za-z]:[\\/][^\s"\'<>|&;]+)'
                      r'|(?:(?<![\w.~$%}\-/])/[^\s"\'<>|&;]+)'
                      r'|(?:(?<![\w.])~[\\/][^\s"\'<>|&;]+)')

# A token roughly as the shell splits it (B82): a quoted run, or a run of anything that is
# not whitespace, a command separator or a redirect.
_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|[^\s;&|<>()]+')

# Already absolute (a drive, a root, a home) -- `_PATH_RE` above has those.
_ABSOLUTE_RE = re.compile(r'^(?:[A-Za-z]:|[\\/~])')

# Characters that mean "not a literal relative path": a colon (`HEAD:a/b`, `host:x/y`, a
# URL), an unexpanded variable (`$x`, `%x%`, `` `x ``), or a git `@{u}`-style ref.
_NOT_A_PATH = set(':$%`{')


def _strip_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _relative_shape(token: str) -> str | None:
    """`token` as a relative path with `/` separators, or None if it does not look like one.

    Needs a separator: a bare `notes.txt` names the working directory, which is the project's
    own tree and not a foreign write (B82's "ruled out")."""
    token = _strip_quotes(token)
    if "=" in token:                     # `--out=../x`, `-Path=..\x`, `VAR=../x`
        token = _strip_quotes(token.rsplit("=", 1)[1])
    if not token or token.startswith("-") or _ABSOLUTE_RE.match(token):
        return None
    if "/" not in token and "\\" not in token:
        return None
    if any(ch in _NOT_A_PATH for ch in token):
        return None
    return token.replace("\\", "/")


def _base(cwd) -> Path | None:
    try:
        return Path(str(cwd)).expanduser() if cwd else None
    except Exception:
        return None


def bash_candidate_paths(command: str, cwd=None) -> list[str]:
    """Best-effort path-shaped tokens in a shell command line. See module docstring --
    this is a regex, not a shell parser, and is meant to be over-inclusive: every caller
    here re-checks each candidate against real git state before recording.

    With `cwd` (B82), relative tokens are joined onto it and onto each `cd` target in the
    command, in order, so `cd ..\\a; Add-Content b\\y.txt` tries `<cwd>/../a/b/y.txt` too.
    Without it, only absolute shapes are returned and a `cd` target comes back as written."""
    if not command:
        return []
    text = command[:MAX_COMMAND_CHARS]
    base = _base(cwd)
    found: list[str] = []
    dirs: list[Path] = [] if base is None else [base]
    current = base
    cd_starts: set[int] = set()
    for m in _CD_RE.finditer(text):
        cd_starts.add(m.start("path"))
        target = _strip_quotes(m.group("path"))
        if _ABSOLUTE_RE.match(target):
            current = _base(target)
        elif current is not None and not any(ch in _NOT_A_PATH for ch in target):
            current = current / target.replace("\\", "/")
        else:
            found.append(target)
            if len(found) >= MAX_CANDIDATES:
                return found
            continue
        if current is None:
            continue
        found.append(str(current))
        if current not in dirs:
            dirs.append(current)
        if len(found) >= MAX_CANDIDATES:
            return found
    for m in _PATH_RE.finditer(text):
        found.append(m.group(0))
        if len(found) >= MAX_CANDIDATES:
            return found
    # Relative tokens get their own cap, so a command full of `origin/main`-shaped words
    # cannot crowd out the absolute ones above.
    relative = 0
    if dirs:
        for m in _TOKEN_RE.finditer(text):
            if m.start() in cd_starts:       # already walked as a `cd` target above
                continue
            rel = _relative_shape(m.group(0))
            if rel is None:
                continue
            for d in dirs:
                found.append(str(d / rel))
                relative += 1
                if relative >= MAX_CANDIDATES:
                    return found
    return found


def main() -> int:
    try:
        # Cursor's `afterFileEdit` / `afterShellExecution` carry a bare `file_path` / `command`;
        # `harness.normalise` reshapes them into the `tool_input` read below (B57). Shell writes
        # are recorded under Cursor too, not only file edits.
        event = harness.read_event()
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
                # Relative tokens resolve against the shell's directory; Cursor sends an
                # empty `cwd` that `harness.normalise` fills, and the project root is the
                # last resort (B82).
                cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else ""
                for candidate in bash_candidate_paths(command, cwd or root):
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
