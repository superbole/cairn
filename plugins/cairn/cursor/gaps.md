# What cairn cannot do in Cursor yet — and how to tell when that changes

Each row names something Claude Code's cairn does that its Cursor half cannot, **as measured on
Cursor 3.19.13 (2026-09-26)**, plus a probe short enough to run when Cursor updates. The
orientation prints one line when Cursor's version or its built-in skills change
(`hooks/cursor_drift.py`). That line is the cue to run these probes. A calendar reminder is not
used.

**A probe that passes becomes a backlog item to use the new capability.** Edit the row here in
the same change, so this file keeps describing today.

| Gap | Why it is a gap | Probe |
|---|---|---|
| **Archiving a chat** | No archive tool is in the agent's tool list, and no built-in skill mentions one. The wrap renames to `Done · …` instead. | List the agent's tools for anything like `archive_chat`, and `ls ~/.cursor/skills-cursor/` for an archive skill. |
| **The junk-title sweep** (`/next` step 0) | There is no tool to list or rename *other* chats. `rename_chat` renames only the current one. | Same listing, for a tool that lists chats or takes a chat id. |
| **Orientation arriving on its own** | Measured 2026-09-26: `sessionStart` did not fire in the first test chat (no request in that chat's hook log), and did fire in the second, returning the orientation as `additional_context`. Whether that text reached the model, and why the first chat got nothing, are both unknown. So the rule also invokes `cairn-orient` whenever the orientation is not in context, and that path relayed correctly both times. | Output → Hooks: search for `Hook step requested: sessionStart` in a new chat. Then ask the agent, before anything runs, what its context says about cairn. |
| **Renaming the chat** | Measured 2026-09-26: an agent in an ordinary chat reported that `rename_chat` was not available to it. The built-in `/rename-chat` skill names it, so it may exist only under that skill. The wrap falls back to a copy block. | Type `/rename-chat test` in a chat. If it renames, the tool exists, and the question is only how the wrap reaches it. |
| **A measurable wrap receipt** | The baseline is keyed by a session id. Cursor gives one to hooks (`session_id`, `conversation_id`), but not to the agent's shell, so `wrap_receipt.py` reads `CAIRN UNKNOWN`. | Run `env` in the agent's shell and look for a chat or conversation id variable. If one is there, key the baseline on it. |
| **Cloud and background agents** | Cursor does not fire `sessionStart` for them, and the user-level plugin does not travel. | Start a background agent in a project with a `NEXT.md`, and check whether its first message relays the queue. |
| **Hours on Cursor-only machines** (B52) | `tools/timesheet.py` reads Claude Code transcripts only. Cursor's transcripts have a different shape. | `sessionEnd` already carries `duration_ms`. The gap is the reader, not Cursor. |
| **Permission-mode names** | Cursor's modes (Agent, Plan, Ask, …) do not map one to one onto Claude Code's. | Compare Cursor's mode list with the table in `cursor/preamble.md`. |
| **Hooks on Windows** | Measured 2026-09-26 on Cursor 3.19.13. Cursor runs hook commands through **Windows PowerShell 5.1**: `\|\|` is a parse error, and the payload arrives behind a UTF-8 byte-order mark (`harness.load_stdin` strips it). `sh` resolved because Cursor puts Git's `usr\bin` on the hook PATH. A Windows machine without Git for Windows would have no `sh`, and every hook would fail open. | Output → Hooks: a `sh` that is "not recognized", or a hook that exits 1. |
| **Hooks run twice on a machine with both harnesses** | Cursor's third-party import also runs Claude Code's installed cairn hooks, from `~/.claude/plugins/cache/…` (Output → Hooks labels them "claude-plugin config"). Both copies detect a Cursor payload, so from v1.65.0 the double run is harmless, just slower. | Output → Hooks: count the hooks run per `stop`. Two, while both are installed, is expected. |
