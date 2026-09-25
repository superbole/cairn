# Brief — with no baseline, the receipt must say "cannot tell", not a confident `[SKIP]` (B10)

`Opus 5` · effort `high` · `AFK/Auto` · from `BACKLOG.md` B10. Written 2026-09-26 by the overnight
batch's bookkeeping.

**Commit locally, then stop. The push and `tools/sync_backlog.py` wait for the user.**

## Read first

- The backlog entry: `sed -n '/^## B10\./,/^## B[0-9]/p' BACKLOG.md`. It names the defect (in
  `tracked_step`: `_changed_by_session` returns `False` where `_changed` returns `None`), the three-part
  fix, and two rejected options with their costs. **It says to re-check against v1.57.0 first. Do that
  against HEAD, not v1.57.0.** Reproduce the false `[SKIP]` with a fixture before changing anything.
- `docs/decisions.md` D36 (v1.63.0). The new `hooks/archive_guard.py` imports `wrap_receipt.verdict()`
  and deliberately skips any root with no baseline for the session. That is where B10's false `OPEN`
  would otherwise have blocked an archive. This fix makes `--check` agree with the guard's reasoning,
  so **`tools/test_archive_guard.py` must still pass unchanged**. Its section 4 asserts that
  `--check alone would say OPEN here (stale marker, no baseline)`. If your fix changes that verdict to
  `UNKNOWN`, that assertion is the one to update, and the dossier must say so. Don't change what the
  guard decides.

## The fix (decided in the entry)

1. `_changed_by_session` returns `None` when attribution can see nothing (`paths` empty and `_changed`
   is `None`).
2. Gate the measuring branch on a baseline that actually loaded, not on `have_base`.
3. A receipt with no baseline says so **once, at the top**, and the verdict is `CAIRN UNKNOWN`, not six
   plausible negatives.

**Ask of the fix: does it reintroduce its own bug one level up?** The dangerous direction is the one
the entry rejects: anything that makes a no-baseline session read **`SET`** (a lazy stamp inside
`--record` compares the tree to itself and is all green). `UNKNOWN` is the only honest answer.

## Verification

- `tools/test_wrap_receipt.py`: a `--resume`-shaped fixture (no SessionStart stamp, real edits to
  `NEXT.md` and `CHANGELOG.md`, a commit) reads `UNKNOWN` with one top line, never `[SKIP] … byte-identical`.
  Also pin that a genuine idle session with a real baseline still reads `[SKIP]`.
- `tools/test_archive_guard.py` passes.
- `python plugins/cairn/tools/run_tests.py --timeout=300`, output pasted in full.
- Run `wrap_receipt.py --check` read-only on this repo and paste it.
- Version bump, CHANGELOG entry, `docs/decisions.md` row, and close B10.

## Report, then stop

Changed files, test output, and anything decided. End the turn. The push waits for the user.
