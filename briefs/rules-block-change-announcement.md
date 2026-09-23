# Say what changed in the rules block, not just `vX → vY`

`Sonnet 5` · effort `medium` · `AFK/Auto` · from `BACKLOG.md` B26

Migrated 2026-09-23 from the private source repo, where it was B101: the code half of finding **S1**
of the 2026-09-06 security review. Decision recorded as **D9** in
[docs/decisions.md](../docs/decisions.md). **Line numbers below are from v1.45.0 — re-locate them
before editing.**

**Do B25 first.** It fixes how the block's boundaries are found, and this item's diff summary is
computed from those boundaries.

## What is wrong

`hooks/install_rules.py` runs from `session_orientation.py` at every SessionStart, writes
`rules/CLAUDE.md` from whatever plugin checkout is installed into `~/.claude/CLAUDE.md` between its
markers, and on a change prints exactly one line:

```
[to the agent] Updated the cairn rules block in <target>: v1.44.0 → v1.45.0. The version in
YOUR context is the old one until the next session.
```

It never says what changed. Marketplace auto-update is what makes this sharp — one machine reached
v1.45.0 that way, unattended — so a version published to the marketplace becomes a **silent,
persistent, machine-wide change to the model's standing instructions in every project**, applied
before the user reads anything.

The file handling itself is careful. This is the plugin's largest lever having the least ceremony
around it.

## What was decided, and what was ruled out

**Announce; do not gate.** D9's rejected options and their costs are in the row — in short: a
`SessionStart` hook cannot prompt, "never fail a session" forbids blocking, and holding the old
block would leave machines silently on stale rules, which is the exact drift the rules layer was
built to kill.

So this item does **not** add a confirmation, a hold, or a signature check. It makes the change
legible after the fact and cheap to inspect.

## The fix

**1. A bounded summary of what moved, on the change line.** Both strings are already in hand at the
decision point (`install_rules.py:232-234`):

```python
start, end, installed = found
if installed == version and existing[start:end] == block:
    return None, True               # the common case — silent, unchanged
```

`existing[start:end]` is the outgoing block and `block` is the incoming one. Report a count —
lines added / removed / changed — and **the exact command to see the full diff**, which is what
makes the summary trustworthy rather than a claim. The user has the backup path (`_backup()`, and
B25 gives it the outgoing version in its name), so a real `diff` against it is one command.

Keep it to **one or two lines**. The rules payload's own budget reasoning applies: this fires once
per version change, not per session, but the change line already competes with everything else in
the SessionStart block.

**2. Say when a section the agent must obey changed.** A bare line count does not distinguish a
typo fix from a new rule. If it is cheap, name the changed `##` headings; if it is not, say so
plainly rather than implying the count is meaningful. Do not invent a semantic classifier.

**3. `check_install.py` gains a comparable block checksum.** It reports the three versions that can
disagree and **never any content**, so today it cannot answer "is the block on this machine the one
the repo ships?" for two machines on the same version string. Add a short digest of the installed
block beside the version. **Reuse `wrap_receipt._digest()`** — the payload imports no `hashlib`
elsewhere. This is the on-demand half: zero session cost, and it answers the question the change
line cannot answer retrospectively.

**Note the existing trigger is broader than the version.** `install_rules.py` rewrites when the
version differs **or** the rendered bytes differ, so an edit to `rules/CLAUDE.md` under the same
version already rewrites and prints `v1.45.0 → v1.45.0`. The summary makes that line informative
instead of confusing — worth a test.

## Cost, and how to state it

The silent path must stay bit-for-bit silent: the `installed == version and existing[start:end] ==
block` early return is the common case and nothing may be computed before it. Measure the change
line's cost with `tools/measure_context.py` rather than asserting it — **no bare constants** (and
see B23 if `tiktoken` is missing).

## Verification

- Tests: a version change prints a summary with a nonzero count; an identical block stays silent and
  writes no backup; a same-version content edit prints the summary; the summary is bounded when the
  block changes wholesale.
- `python plugins/cairn/tools/run_tests.py`.
- `python plugins/cairn/tools/check_install.py` on this machine — the new digest line renders, and
  the exit code semantics (`OK`/`STALE`/`UNKNOWN`, exit 1 on mismatch) are unchanged.
- `python plugins/cairn/tools/measure_context.py <a project root>` before and after, to state the
  cost with a real number.
- A version bump touching `plugin.json` **requires a `README.md` check in the same commit** — and a
  `SKILL.md` rule change requires an `incidents.md` check. Neither applies if this ships without a
  rules-text change, but say so explicitly rather than skipping silently.

## Where it stops

`AFK` — fully specified. **Commit locally and stop before the push.**
