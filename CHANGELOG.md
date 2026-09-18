# CHANGELOG — cairn

Finished work, newest first, one entry per plugin version. `NEXT.md` is the queue and holds no
history; this file holds the history and no queue.

## 2026-09-18 — v1.57.0: a wrap receipt can no longer cry wolf about where you stood

**`CAIRN UNKNOWN`, a fourth verdict.** `verdict()` returned `OPEN` for two opposite states: a
required step measured *not to have run*, and one that *could not be measured*. Receipt
`9274cfbf13da` (2026-09-14) read `CAIRN OPEN` on a wrap that had written a 19-line CHANGELOG entry,
rewritten `NEXT.md`, committed `e415fb2` and pushed to `0 0` — the same token a skipped changelog
produces. `skipped` is now tested before `unverifiable`, so a wrap that is both still reads `OPEN`
and `UNKNOWN` cannot become a soft landing for an incomplete one. `UNKNOWN` records a receipt with
a real, verifiable id; refusing to record was rejected, because the id is the whole reason the
token is evidence.

**And the cause is prevented, not just reported.** `SessionStart` in a directory with no `NEXT.md`
— a parent folder full of repos, the shape this was filed on — now stamps a session-start baseline
for each immediate child that is a git repo carrying its own `NEXT.md`, so a wrap of that child
earns the same verdict it would have from inside it. Same opt-in gate, and same security boundary,
as `repo_sweep.sibling_repos()`: a clone with no `NEXT.md` is never reached. Measured on the real
`~/Projects`: 12 opted-in children, 881 ms, paid only by a session start that prints no orientation
anyway. An ordinary session in a real project still stamps exactly one baseline and pays nothing.
Siblings are deliberately not covered — that would put the cost on every session — and fall to
`UNKNOWN`.

**The printed note named the wrong cause.** It asserted *"the baseline is keyed to the session id,
which a plain terminal does not have"* for every missing baseline, which is false of an in-session
wrap run from a parent directory and sent the reader after the wrong remedy. It now reads the
session id and distinguishes the two.

Closes `BACKLOG.md` B2 (issue `#2`), queue item 2. Rationale in `docs/decisions.md` D26; the
incident record is in `plugins/cairn/skills/wrap/references/incidents.md`. `rules/CLAUDE.md`,
`skills/wrap/SKILL.md`, `docs/guide.md` and `docs/design-notes.md` all state the fourth verdict and
that `UNKNOWN` must never be relayed as `OPEN`. 29/29 test files pass; the new section 11 of
`test_wrap_receipt.py` fails against the pre-fix code, verified.

## 2026-09-16 — `.gitattributes` normalizes line endings to LF

Added `.gitattributes` (`* text=auto eol=lf`) so a WSL checkout of this Windows-authored repo
stops reading all 87 tracked files as modified. `git add --renormalize .` staged nothing — the
index already held LF throughout, so the fix is the rule going forward, not a rewrite of history.
No `.bat`/`.ps1`/`.cmd` files are tracked here, so no CRLF exception was needed. Unblocks a
Linux-side commit for item 1 (the hook interpreter fix).

## 2026-09-14 — two defects found installing v1.56.0 on a second machine

First install of the published plugin into a Linux environment (`SBOLE-NB5`, WSL). It failed
silently, and nothing in the plugin could say so.

**The interpreter.** All five hooks in `hooks.json` invoke bare `python`, which stock
Ubuntu/Debian does not have, so every hook fails to start. `session_orientation.py` never runs and
none of the five global files are written — while `claude plugin list` reports the plugin enabled
and the skills load normally. The plugin cannot self-report it: the hook that would warn is the
hook that cannot run. `python3` is not the fix; no interpreter name is common to all three
platforms. Queued; brief in `briefs/cross-platform-hook-interpreter.md`.

**Line endings.** No `.gitattributes` and `core.autocrlf` unset, so the Windows checkout read from
WSL shows 87 files and 25,751 changed lines — all CRLF, no content. `git status` cannot tell real
work from noise there. Queued; brief in `briefs/gitattributes-eol-normalization.md`.

Neither is fixed here. `SBOLE-NB5` carries a local `python -> python3` symlink as a workaround
only; `B1`/`W1` carry the same for `SBOLE-NB1` after its first pull. `DeepThought` has no WSL and
is unaffected. No plugin code changed, so no version bump.

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
