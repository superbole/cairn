# `install_rules` can delete the user's own text, and one rolling backup cannot recover it

`Opus 5` · effort `high` · `AFK/Auto` · from `BACKLOG.md` B25

Migrated 2026-09-23 from the private source repo, where it was B104, found during the 2026-09-06
security review's decision pass (its "N1"). Verified in the code, not inferred. **Line numbers below
are from v1.45.0 — re-locate them before editing.**

This is the highest-consequence defect in the payload that is not a security finding: silent data
loss in `~/.claude/CLAUDE.md`, the one file the plugin promises to touch only between its markers.

## What is wrong

Two independent problems that compound.

**1. The marker match is a bare substring search for a prefix.**

```python
BEGIN = "<!-- reentry:begin"        # install_rules.py:49 — NO closing -->
END   = "<!-- reentry:end -->"      # :50

start = text.find(BEGIN)            # :134 — first occurrence ANYWHERE in the file
end   = text.find(END, start)       # :136
...
_write(target, existing[:start] + block + existing[end:])   # :238
```

So if any text **above** the managed block contains the literal `<!-- reentry:begin`, `start` lands
in the user's own writing and everything from there down to the real `END` — their text included —
is replaced by the new block. No warning, no diff, no error.

This is not far-fetched. The installed rules explicitly invite machine-local notes **outside** the
markers, and the block prepends itself on a file that has none (`:220-226`), so the user's own
material naturally lives above and below. Anyone documenting the mechanism in their own notes writes
that string.

The refuse guard at `:190-195` covers the **shipped body** containing a marker. It never checks the
**target file**.

**2. The backup is one rolling copy.**

`_backup()` (`:71-76`) returns a fixed name, `CLAUDE.md.bak-reentry-install`, and `shutil.copy2`
overwrites it on every modifying run (`:224`, `:237`). Two updates in a row destroy the
pre-first-update state — and marketplace auto-update means two updates in a row happen without
anyone acting. So the recovery path for problem 1 is gone by the time anyone notices.

## The fix

**Marker matching — make it structural, not a substring.** All three conditions, not one:

- Anchor `BEGIN` to the **start of a line**.
- Require the comment to **close on that line** (`-->`).
- Require a **version token** in the header — `_find_block` already parses one (`:143-147`) and
  currently tolerates its absence, returning `version = ""`.

A candidate that fails any of these is not the managed block. If a `BEGIN`-looking line exists but
no valid block is found, **refuse and say so** rather than falling through to the "no block →
prepend" path at `:218-230` — prepending a second block into a file that already has a malformed one
is its own mess.

**Backup — name it with the outgoing version.** `CLAUDE.md.bak-reentry-install-v1.44.0`, or the
same with a short digest. The outgoing version is already in hand at `:232` as `installed`. Keep the
current fixed name working (or migrate it) so an existing backup is not orphaned. Decide and record
whether old backups are pruned; unbounded files in `~/.claude` is a real cost, and "never prune" is
a defensible answer if it is written down.

**Reusable helper:** `wrap_receipt._digest()` is the payload's only sha256 helper. The payload
imports no `hashlib` or `difflib` anywhere else — do not add a dependency for this.

**Interaction with B28:** B28 migrates the `reentry:begin` marker itself to a new name. Whichever
lands second must keep both parsers structural; do not let the migration reintroduce a bare prefix
match.

## Why `Opus 5` / `high`

The mechanical change is small; the judgement is not. This file writes always-loaded instruction
text on every machine, its failure mode is silent, and its guard rails are the thing being edited. A
wrong edit here is discovered on every machine at once, and the backup semantics are exactly what
you would be relying on to undo it. Read `install_rules.py` in full before touching it.

## Interaction with B26

B26 adds the "say what changed" announcement to the same function. **Land this one first** — B26's
diff summary is computed from `existing[start:end]` versus `block`, so it inherits whatever
`_find_block` returns. If the block boundaries can be wrong, the diff summary is confidently wrong
too.

## Verification

- New cases in whatever covers `install_rules` today (check `tools/run_tests.py`'s file list; if
  there is no `test_install_rules.py`, this item creates one — the module has no direct test file
  and that is part of why this survived):
  - user text above the block containing `<!-- reentry:begin` → user text intact, block replaced
    correctly;
  - a `BEGIN` prefix with no `-->` on the line → not treated as a block;
  - a block with no version token → refused, not silently rewritten;
  - two consecutive updates → both backups recoverable;
  - the existing idempotency case (second run silent, no backup churn) still green.
- `python plugins/cairn/tools/run_tests.py`.
- By hand on a **copy** of `~/.claude/CLAUDE.md` in the scratchpad, never the live file.

## Where it stops

`AFK` — fully specified. **Commit locally and stop before the push.** Report the real test output,
and say explicitly whether a `test_install_rules.py` had to be created.
