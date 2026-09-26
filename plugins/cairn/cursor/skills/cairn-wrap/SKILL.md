---
name: cairn-wrap
description: >-
  cairn's /wrap for Cursor. End a session cleanly: CHANGELOG entry, commit, push, rewritten
  NEXT.md, the wrap receipt. Use when the user types /cairn-wrap or /wrap, says to wrap up, end
  the session or "we're done here", and suggest it when a phase completes.
---

# cairn-wrap

`<root>` is the cairn plugin root: three directories above the folder this `SKILL.md` is in
(this file is `<root>/cursor/skills/cairn-wrap/SKILL.md`).

**Read `<root>/skills/wrap/SKILL.md` and follow it, every step.** That is the one copy of the
procedure, shared with Claude Code. Do not follow a copy of it from anywhere else. A
hand-written `wrap` skill in `~/.cursor/skills/` predates cairn's Cursor adapter.

Read it through the table in cairn's Cursor rule, under **Running under Cursor**. The places
it applies:

- Its "base directory" is `<root>/skills/wrap`, so the `<root>` it defines is this one.
- Its `sh "<root>/hooks/run.sh" …` lines run with `python` instead.
- The **receipt** will most likely read `CAIRN UNKNOWN` under Cursor. Quote it and relay it as
  the rules say: not `OPEN`, and never upgraded.
- The **rename** at the close uses `rename_chat`.
- The **archive** step becomes a rename to `Done · <project> · <subject>`, only when the receipt
  is not `CAIRN OPEN`. Say in one line that you did it.
- The `AFK` push-stop applies exactly as written.
