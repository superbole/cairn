# Brief — the README says how to turn on auto-update (B61)

`Sonnet 5` · effort `medium` · `AFK/Auto` · from `BACKLOG.md` B61. Written 2026-09-26 at B70's wrap.

**Commit locally, then stop. The push and `tools/sync_backlog.py` wait for the user.**

It serves the aim line (a stranger installs and stays current with no manual setup). Plugin auto-update
is off by default for every non-Anthropic marketplace, and nothing in the README says so.

## Read first
`sed -n '/^## B61\./,/^## B[0-9]/p' BACKLOG.md`. The entry has the doc facts (fetched 2026-09-25), the
env vars that block updates even when auto-update is on, and the NB1 measurement. Re-fetch
`https://code.claude.com/docs/en/plugins/install.md` before writing, so the README quotes current docs,
not the entry's copy.

## Do
Add a short README section next to the install instructions: how to enable auto-update (`/plugin` UI,
or `"autoUpdate": true` on the marketplace entry in `settings.json`), the blocking env vars, and the
manual update command, which is already in `docs/guide.md` "Shipping a change". No code change unless
the entry names one.

## Verification
`python plugins/cairn/tools/run_tests.py --timeout=300` (the payload-clean test covers the README), with
the output pasted. CHANGELOG entry and close B61.

## Report, then stop
Changed files and the test output. End the turn. The push waits for the user.
