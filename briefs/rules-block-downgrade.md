# Refuse to downgrade a newer rules block

`Opus 5` · effort `high` · `AFK/Auto` · from `BACKLOG.md` B63

**Commit locally, then stop. The push and `tools/sync_backlog.py` both wait for the user.**

## Why this is queued above B59

B59 (queue item 2) edits call sites in `plugins/cairn/rules/CLAUDE.md`. That will be the first
release since v1.59.0 in which the rules **body** changes. Until then this defect has been
harmless, because every version wrote an identical body. Once B59 ships, any machine where an older
installer still runs puts the old rules back, silently, every session. So land this first.

## What is wrong

Seen 2026-09-25 on NB1. The orientation printed *"Updated the cairn rules block in
`~/.claude/CLAUDE.md`: v1.62.0 → v1.60.0"*, which is a rollback reported as an update. The full
evidence is in `BACKLOG.md` B63: the backup filenames and mtimes show that a v1.62.0 installer and a
v1.60.0 installer both ran on the same day. **Which process ran v1.62.0 is unconfirmed. Don't chase
it.** The fix doesn't depend on the answer.

The defect is in `_install_block()` in `plugins/cairn/hooks/install_rules.py`. It returns early
only if the installed version equals this plugin's version and the block body matches. On any other
mismatch it writes, and it never checks which direction the change goes.

## The fix

1. **Add a shared version-comparison helper**, so versions aren't parsed in two places.
   `version_drift.py` already reads the installed and repo versions. Put the comparison where both
   modules can import it (`version_drift.py`, or a small new module both import), and make
   `install_rules.py` use it.
2. **In `_install_block()`, after `_find_block()` returns an installed version:** if the installed
   version is **newer** than `_plugin_version()`, write nothing and back up nothing. Return one
   `[to the agent]` line that names both versions, says the newer block was kept, and tells the user
   to update the plugin (`claude plugin update cairn@superbole`, then restart). Return
   `in_context=True`, because the file still holds rules the session has already read.
3. **Keep the wording in the same voice as the MalformedBlock refusal**, so that B26 (queue item 3)
   can later make every rules-block message consistent.
4. **Leave the equal-version and older-version paths unchanged.** An unparseable version on either
   side falls through to today's behaviour: a version string that can't be read is no evidence of a
   downgrade.

## What was ruled out, and why

- **Newest content wins, decided by diffing the bodies.** A body can't say which of two versions is
  newer. The version marker can.
- **A rules block per process.** Impossible, because `~/.claude/CLAUDE.md` is one file.

## Verification

- Add cases to `plugins/cairn/tools/test_install_rules.py`:
  - a newer installed block with an older plugin: file byte-identical, no backup written, exactly
    one report line naming both versions;
  - an older installed block with a newer plugin: still upgrades, as today;
  - an unparseable installed version: today's behaviour.
- The new "newer block" case must fail against v1.62.0.
- Run the full suite and paste its real output in the report.
- Bump the plugin version and add a CHANGELOG entry and a `docs/decisions.md` row. The row names
  the two rejected options above.

## Report, then stop

List the changed files, paste the test output, and note anything decided on the user's behalf. Then
end the turn. The push waits for the user.
