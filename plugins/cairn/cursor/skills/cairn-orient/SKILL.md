---
name: cairn-orient
description: >-
  cairn session start. Use at the START of every chat in a project that has a NEXT.md, before
  your first reply, unless cairn's orientation (a "[to the agent]" tier line or a "WHERE YOU
  LEFT OFF" block) is already in your context. Once per chat.
---

# cairn-orient — the session start Claude Code gets from a hook

`<root>` is the cairn plugin root: three directories above the folder this `SKILL.md` is in
(this file is `<root>/cursor/skills/cairn-orient/SKILL.md`).

1. From the project root, run:

   ```
   python "<root>/hooks/session_orientation.py" --harness cursor --no-stdin
   ```

   `python3` where `python` is missing (Linux, macOS). `--no-stdin` matters: without it the
   script waits for a hook payload that is not coming.

2. It prints a `[to the agent]` line naming a tier — `RELAY FIRST`, `ANSWER FIRST, THEN RELAY`,
   `ANSWER FIRST, THEN ONE LINE` or `STAY QUIET`. **Follow it literally.** Relay the queue as the
   numbered list it describes, the file's own numbers, never prose.

3. Printing nothing is a real answer: the project has no `NEXT.md`, or nothing is live. Say
   nothing about it.

Once per chat. If the orientation is already in your context — Cursor's `sessionStart` hook may
have put it there — do not run this again.
