"""PermissionRequest hook: log every permission prompt, change nothing.

Appends one JSON line per prompt to ~/.claude/permission-prompts.jsonl: when, which session, the
tool, and its full input. A scheduled run that stalls on a prompt otherwise leaves no record of
which command asked (W10, W11). Prints nothing and always exits 0, so the dialog appears as usual.
The log lives outside the checkout because cairn-afk-firing aborts on a dirty tree.
"""
import json
import os
import sys
from datetime import datetime, timezone

try:
    event = json.load(sys.stdin)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": event.get("session_id"),
        "cwd": event.get("cwd"),
        "permission_mode": event.get("permission_mode"),
        "tool_name": event.get("tool_name"),
        "tool_input": event.get("tool_input"),
        "transcript_path": event.get("transcript_path"),
    }
    path = os.path.join(os.path.expanduser("~"), ".claude", "permission-prompts.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
except Exception:
    pass
sys.exit(0)
