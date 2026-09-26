#!/usr/bin/env python3
"""Which harness fired this hook, and a Cursor payload reshaped into the Claude one.

WHY THIS EXISTS (B57, v1.65.0)
------------------------------
The same Python runs under two harnesses. Claude Code wires it from `hooks/hooks.json`; Cursor
wires it from `cursor/hooks.json`, which passes `--harness cursor`. The payloads are close but not
the same (cursor.com/docs/hooks, read 2026-09-26):

  - Cursor names events in camelCase (`sessionEnd`, not `SessionEnd`).
  - Only `sessionStart` / `sessionEnd` carry `session_id`; every other event carries
    `conversation_id`, which Cursor documents as the same value.
  - `afterFileEdit` has a top-level `file_path`, and `before/afterShellExecution` a top-level
    `command` -- there is no `tool_name` / `tool_input` pair on either.
  - `postToolUse` names its tools `Shell` and `Write` where Claude says `Bash` and `Edit`.

So every hook reads Claude's shape, and this module is the one place that knows Cursor's. A
Claude payload passes through untouched: `normalise()` changes nothing unless the payload is
Cursor's, which is what keeps the Claude side byte-for-byte what it was.

THE OTHER DIFFERENCE IS WHAT A HOOK MAY PRINT. Claude's `Stop` hook prints a `systemMessage` the
user sees. Cursor's `stop` reads `followup_message` and AUTO-SUBMITS it as the next prompt, so a
warning printed there would start the agent again. A hook that knows it is under Cursor prints
nothing the harness could act on, and writes its side effects instead. `is_cursor()` is how it
knows.

Never raises: every caller is a hook, and a hook that crashes is worse than one that says nothing.
"""
from __future__ import annotations

import json
import sys

CURSOR = "cursor"

# Cursor event -> the Claude event whose code path handles it.
_EVENTS = {
    "sessionStart": "SessionStart",
    "sessionEnd": "SessionEnd",
    "beforeSubmitPrompt": "UserPromptSubmit",
    "preToolUse": "PreToolUse",
    "postToolUse": "PostToolUse",
    "afterFileEdit": "PostToolUse",
    "afterShellExecution": "PostToolUse",
    "beforeShellExecution": "PreToolUse",
    "stop": "Stop",
}

# Cursor tool name -> Claude tool name (cursor.com/docs/reference/third-party-hooks lists the
# same two in the opposite direction).
_TOOLS = {"Shell": "Bash", "Write": "Edit"}

# Keys a Cursor edit tool has been seen to name its file under. Claude's hooks read `file_path`.
_CURSOR_PATH_KEYS = ("file_path", "target_file", "path")


def harness_flag(argv: list[str] | None = None) -> str:
    """The value after `--harness`, or "" when there is none."""
    args = sys.argv if argv is None else argv
    try:
        return str(args[args.index("--harness") + 1]).strip().lower()
    except (ValueError, IndexError):
        return ""


def is_cursor(event: dict | None = None, argv: list[str] | None = None) -> bool:
    """True when this hook is running under Cursor.

    The flag is what `cursor/hooks.json` passes and is authoritative. The payload test is the
    backstop for the one route the flag cannot cover: Cursor's third-party import running this
    plugin's CLAUDE-format hooks, which would pass no flag. Every Cursor payload carries
    `cursor_version`; no Claude payload does.
    """
    if harness_flag(argv) == CURSOR:
        return True
    return isinstance(event, dict) and bool(event.get("cursor_version"))


def normalise(event):
    """`event` in Claude's shape. Returns a new dict; a non-Cursor payload comes back unchanged."""
    if not isinstance(event, dict):
        return {}
    name = str(event.get("hook_event_name") or "")
    if not (event.get("cursor_version") or name in _EVENTS):
        return event
    out = dict(event)
    out["_harness"] = CURSOR
    if name in _EVENTS:
        out["hook_event_name"] = _EVENTS[name]
    if not out.get("session_id") and out.get("conversation_id"):
        out["session_id"] = out["conversation_id"]
    if not out.get("cwd"):
        # Measured 2026-09-26: Cursor sends `cwd: ""` on shell events, and `workspace_roots` in
        # URI form -- `/C:/Users/...` on Windows, which is not a path any tool can open. The
        # first live run fed that to staged_review_guard, which found no repo and allowed the
        # commit it exists to stop. CURSOR_PROJECT_DIR is a real path; prefer it.
        import os
        roots = out.get("workspace_roots")
        root = os.environ.get("CURSOR_PROJECT_DIR", "")
        if not root and isinstance(roots, list) and roots and isinstance(roots[0], str):
            root = roots[0]
        if len(root) > 2 and root[0] == "/" and root[2] == ":":
            root = root[1:]                      # "/C:/x" -> "C:/x"
        if root:
            out["cwd"] = root

    if name == "afterFileEdit":
        out["tool_name"] = "Edit"
        out["tool_input"] = {"file_path": str(event.get("file_path") or "")}
    elif name in ("afterShellExecution", "beforeShellExecution"):
        out["tool_name"] = "Bash"
        out["tool_input"] = {"command": str(event.get("command") or "")}
    elif "tool_name" in event:
        out["tool_name"] = _TOOLS.get(str(event.get("tool_name")), event.get("tool_name"))
        tool_input = event.get("tool_input")
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except Exception:
                tool_input = {}
        if isinstance(tool_input, dict):
            tool_input = dict(tool_input)
            if not tool_input.get("file_path"):
                for key in _CURSOR_PATH_KEYS:
                    if isinstance(tool_input.get(key), str) and tool_input[key]:
                        tool_input["file_path"] = tool_input[key]
                        break
            out["tool_input"] = tool_input
    return out


def load_stdin() -> dict:
    """The hook payload on stdin, as a dict; {} on anything unreadable.

    Read as BYTES and decoded `utf-8-sig`. Measured 2026-09-26 on Cursor 3.19.13 / Windows: Cursor
    runs hook commands through Windows PowerShell 5.1, which prefixes the payload it forwards with
    a UTF-8 byte-order mark. `json.loads(sys.stdin.read())` fails on that, every time, and a hook
    that swallows the error (all of ours do, by design) then acts on `{}` -- which is exactly how
    the imported Claude hooks ran for a whole test chat and recorded nothing.
    """
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        try:
            raw = sys.stdin.read().encode("utf-8")
        except Exception:
            return {}
    try:
        data = json.loads(raw.decode("utf-8-sig") or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def read_event() -> dict:
    """stdin as a Claude-shaped dict; {} on anything unreadable."""
    return normalise(load_stdin())


def in_cursor_process() -> bool:
    """True inside a process Cursor launched (a hook, or the agent's shell).

    Used to IGNORE a Claude Code session id in such a process. Cursor inherits its launcher's
    environment, so a Cursor window opened from a Claude Code session carries that session's
    `CLAUDE_CODE_SESSION_ID` into every hook it runs -- measured 2026-09-26 -- and a hook keying
    state on it would write into the Claude session's files.
    """
    import os
    return bool(os.environ.get("CURSOR_VERSION") or os.environ.get("CURSOR_PROJECT_DIR"))
