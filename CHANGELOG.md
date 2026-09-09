# CHANGELOG — cairn

Finished work, newest first, one entry per plugin version. `NEXT.md` is the queue and holds no
history; this file holds the history and no queue.

## 2026-09-09 (latest) — v1.56.0: seeded

**This repo begins at v1.56.0, not at v0.1.0, and the history before it is deliberately absent.**
The plugin was built over 150+ commits in a private repo. Sixteen of those commits name an
employer's internal git host and three name personal information, so a public clone or fork
would carry both forever. A `git filter-repo` rewrite was considered and rejected: one missed
string is permanent, and a fresh `git init` is *provably* clean rather than carefully clean. The
full reasoning, including what was rejected, is `docs/decisions.md` D1.

**What that costs, stated plainly:** the reasons behind the design are in `docs/decisions.md` and
the incidents behind individual rules are in `plugins/cairn/skills/*/references/incidents.md`, but
the commit-by-commit record of how it got here is not public and will not become public.

**What arrived:** the plugin payload (`plugins/cairn/`, 74 files), the marketplace manifest,
`README.md`, `LICENSE`, and five documents — `docs/guide.md`, `docs/design-notes.md`,
`docs/file-formats.md`, `docs/running-a-batch.md` and `docs/decisions.md`. Nothing else. The file
list was explicit rather than a wildcard, and the payload was copied by `git ls-files` so no cache
or ignored file could travel.

**Verified before the first commit**, in this directory: `test_payload_clean.py` ALL PASS over both
file sets, with the private pattern list loaded from outside the repo; `run_tests.py` 29/29;
`check_leak_coverage.py` 0 LEAK; `fence_check.py` clean on the three working files.
