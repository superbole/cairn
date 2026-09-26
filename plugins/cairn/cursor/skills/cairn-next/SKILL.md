---
name: cairn-next
description: >-
  cairn's /next for Cursor. Show where this project was left off (the NEXT.md Queue, due watches,
  un-triaged INBOX.md items) and start an item. Use when the user types /cairn-next or /next,
  says "do 1" (or 2, 3...), asks "where were we?" or "what's next?".
---

# cairn-next

`<root>` is the cairn plugin root: three directories above the folder this `SKILL.md` is in
(this file is `<root>/cursor/skills/cairn-next/SKILL.md`).

**Read `<root>/skills/next/SKILL.md` and follow it.** That is the one copy of the procedure,
shared with Claude Code. Do not follow a copy of it from anywhere else. A hand-written `next`
skill in `~/.cursor/skills/` predates cairn's Cursor adapter.

Read it through the table in cairn's Cursor rule, under **Running under Cursor**:

- Its "base directory" is `<root>/skills/next`, so the `<root>` it defines is this one.
- Its `sh "<root>/hooks/run.sh" …` lines run with `python` instead.
- Step 0 (the junk-title sweep) is skipped.
- Step 7 (name the chat) uses `rename_chat`.
