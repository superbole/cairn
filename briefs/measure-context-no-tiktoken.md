# Brief — `measure_context.py` must run without `tiktoken` (B23)

`Sonnet 5` · effort `medium` · `AFK/Auto` · from `BACKLOG.md` B23. Written 2026-09-26 by the
overnight batch's bookkeeping.

**Commit locally, then stop. The push and `tools/sync_backlog.py` wait for the user.**

## Why now

The rules file's last rule, and both skills, tell every agent to *measure* with
`tools/measure_context.py` rather than quote a number (since v1.63.0 the call is
`sh "<root>/hooks/run.sh" tools/measure_context.py <project-root>`). On every machine checked so far
`tiktoken` is not installed, so the payload tells agents to run a tool that dies before printing
anything. The 2026-09-26 lanes all had to fall back to hand-made `bytes/4` estimates. The aim is that a
stranger's install works without setup, and this tool is part of that.

Read the backlog entry first: `sed -n '/^## B23\./,/^## B[0-9]/p' BACKLOG.md`.

## The fix (decided in the entry: option (a), with (c) as the documented extra)

1. Guard the `import tiktoken`. When it is missing, fall back to a bytes-based estimate, and **label it
   as an estimate on every line that shows it** (e.g. `~7,334 (est. bytes/4)`), plus one header line
   saying exact counts need `pip install tiktoken`. A fallback that prints the same `~N` as a real
   count is the bug one level up: it turns an estimate back into a quotable constant.
2. Keep the exit code 0 in the fallback. The tool reports; it must not fail a wrap step.
3. Mention the optional `tiktoken` in the tool's docstring and in the README's prerequisites, as the way
   to get exact counts. **No `requirements.txt`**: the plugin has zero Python dependencies, and that is
   worth keeping.
4. Check `tools/measure_usage.py` and anything else that imports `tiktoken` (`grep -rn tiktoken
   plugins/`) for the same unguarded import.

## Verification

- `tools/test_measure_context.py`: add a case that hides `tiktoken` (e.g. by inserting a
  `sys.modules["tiktoken"] = None` shim in a subprocess) and asserts the tool exits 0, prints the
  estimate label, and prints the install hint once.
- Run the real tool on this repo with and without `tiktoken` available, and paste both outputs.
- `python plugins/cairn/tools/run_tests.py --timeout=300`, output pasted in full.
- Version bump, CHANGELOG entry, and close B23 (`closed` on its fields line). Also check B24, which
  this unblocks. Its "real number" can now be measured, so say so in B24's body.

## Report, then stop

Changed files, test output, and anything decided. End the turn. The push waits for the user.
