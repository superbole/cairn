# Running under Cursor — read this before the rules below

The rules below are cairn's **Claude Code** rules, carried into Cursor unchanged: one source,
two harnesses, no second copy to drift. Everywhere they name something Claude Code has and
Cursor does not, read it through the table in this section. **This section is the only
Cursor-specific text cairn ships.** When a rule and this table disagree about a Cursor fact,
the table wins; about anything else, the rule wins.

## At the start of every chat

In a project that has a `NEXT.md`, **before your first reply**: if cairn's orientation is not
already in your context — a `[to the agent]` tier line, or a `WHERE YOU LEFT OFF` block —
invoke the **`cairn-orient`** skill, then follow the tier it prints. Once per chat, never again:
text that reappears later is a summary refilling your context, not a new chat.

Then read `~/.claude/reentry-profile.md` if it exists. It is the user half of these rules, and
Cursor rules cannot import it the way the Claude Code copy does with its `@` line.

## The table

| Where the rules say | Under Cursor |
|---|---|
| `sh "<root>/hooks/run.sh" <file> [args]` | `python "<root>/hooks/<file>" [args]`, or `python "<root>/tools/<name>.py" [args]` for a `tools/…` argument. Use `python3` where `python` is missing (Linux, macOS). Cursor's shell on Windows has no `sh`. |
| `<root>` (the plugin root) | three directories above the folder a `cairn-*` skill's `SKILL.md` is in. |
| `/cairn:next`, `/cairn:wrap` | the `cairn-next` and `cairn-wrap` skills. |
| `set_session_title(session_id: "self")` | the `cursor-app-control.rename_chat` tool, at the same two points: **when an item starts** (a placeholder `<project> · <item title>`) and **at the wrap** (the final title). If the tool is not available, print the title in a fenced block for the user to paste. Say in one line what you renamed it to, either way. |
| `archive_session(session_id: "self")` | Cursor has no archive tool. At the point the wrap would archive, rename the chat to **`Done · <project> · <subject>`** instead — only when the receipt does **not** read `CAIRN OPEN`, the same condition the Claude archive guard enforces. An `AFK` item stopped before its push reads `OPEN`, so it never gets the prefix. |
| `list_sessions` / the junk-title sweep | skip it. |
| `CAIRN UNKNOWN` from `wrap_receipt.py` | expected under Cursor for now: the receipt keys its baseline by a session id that Cursor does not give the shell. Relay it exactly as the rules say — never as `OPEN`, never upgraded to `SET`. |
| model tier (`Opus`, `Sonnet`) | pick the current model of that family in Cursor's model picker. `Auto` or a non-Anthropic model (Grok, Composer, GPT, …) is **not on the scale**: do not call it above or below; name it and ask before starting. |
| effort `high` / `medium` | `high` = that model's thinking or Max variant; `medium` = the standard one. |
| permission mode (Shift+Tab: `Auto`, `Plan`, …) | Cursor's own modes: `Plan` ↔ Plan, everything else ↔ Agent. The user sets it, as in Claude Code. |
| an `AFK` item | runs in **Claude Code**, not here: the unattended safeguards (scheduled runs, allow/deny rules, the held push) exist only there. If one is started in Cursor, say so in one line before starting. |
| `hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}` | `cursor/hooks.json`, `${CURSOR_PLUGIN_ROOT}`. |

What cairn cannot do in Cursor yet, and how to test whether a Cursor update changed that, is
listed in `<root>/cursor/gaps.md`. The orientation says when Cursor has changed.
