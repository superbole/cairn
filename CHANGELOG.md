# CHANGELOG — cairn

Finished work, newest first, one entry per plugin version. `NEXT.md` is the queue and holds no
history; this file holds the history and no queue.

## 2026-09-23 — v1.60.0: the new guard had a hole in the only case it was written for

**`staged_review_guard` shipped an hour earlier with seven passing tests and would have caught
nothing.** It resolved the repository from the SESSION's cwd, honouring `git -C <path>` but not
`cd <path> && git …` — and `cd` is the ordinary shape for touching a second repo. So a commit into
any repo other than the session's own was evaluated against the session's repo, found "nothing
staged", and allowed. **The defect that prompted the guard was a commit into `workspace` from a
`bsr-tools` session**, reached by exactly that `cd`, so the guard was blind to its own motivating
incident.

**It passed its tests because they were written the same way the code was.** Every case ran with
`cwd` set to the target repo, which is the one arrangement that hides the bug. It was found within
minutes of a real session loading it, by running it against live `cd`-style commands rather than
against a fixture — the first thing `NEXT.md` W1 asked for, and the reason that watch existed.

**Also fixed: the guard fired on any command that merely CONTAINED the words.** Matching was
against raw command text, so a heredoc, a `grep` pattern or a JSON test payload mentioning the two
verbs was refused — which made the guard's own test script unrunnable, and then blocked the commit
of this very changelog entry. Git verbs now only count at a command position (start of string, or
after `;`, `&&`, `||`, `|`, a newline, `then` or `do`).

**Known and accepted:** bootstrapping a fresh repo (`git init && git add . && git commit`) is still refused,
because it is genuinely a stage-and-commit in one call. The workaround is to split it, and no
exception was added — a carve-out written by the session that wrote the rule is how guards rot.

**The lesson is about the test, not the code.** A hook cannot be exercised by the session that
writes it, so "tested" meant "tested as a standalone script against payloads I invented". That is
weaker evidence than it reads as, and the gap between the two was a whole class of commit.
## 2026-09-23 — v1.59.0: the `NEXT.md` re-read rule was never about `NEXT.md`

**`/cairn:wrap` has always said "RE-READ `NEXT.md` FROM DISK FIRST, never from your context",** and
the reason it gives — several sessions run at once, so your copy can be hours stale — is a fact
about the SESSION, not about that file. It was only ever enforced on one file.

**So a session obeyed it perfectly and was wrong about everything else.** 2026-09-23: it re-read
`NEXT.md` at every wrap, then told the user `MR !5` was open and still needed merging. It had been
merged hours earlier by another machine. One `glab mr view` would have said so. The same session
described a queue from a branch that had been superseded, and a second machine independently
reported a two-week-old `QUEUE.md` as current.

**The rule now covers any external state a session asserts** — an MR or PR, an issue, a branch, a
remote, what another machine pushed — with the tell to watch for: you are about to describe
something from memory *because you did the work earlier and remember the answer*.

**Rejected: a boundary on session length.** The obvious reading of that incident is that the
session ran too long and should have been forced to stop after its first `CAIRN SET` — a
`PostToolUse` hook refusing to let a wrapped session keep working. It was proposed and the user
rejected it, correctly: nearly everything of value that day was found *after* a wrap and *because*
context had accumulated — an unauthenticated-API-surface record, a backlog item, a `glab` install,
the MR itself, and this plugin's two newest rules. A boundary would have cut each of those at the
seam and called it hygiene. **Duration was never the defect; asserting stale state was**, and the
two are easy to confuse because they co-occur. His question, which settled it: *"would those issues
have been raised or found in a new session?"*
## 2026-09-23 — v1.58.0: a pathspec is not a review

**`git add <file>` obeyed the rule and committed someone else's work anyway.** The rule said
*"stage with explicit pathspecs, never `git add .`"*, and a session on 2026-09-23 did exactly that
— `git add INBOX.md` — sweeping in six bullets the nightly divergence scan had appended to that
file, under a commit message describing only the one line the session wrote.

**The rule governs FILES and assumes a named file is entirely yours.** That is false for anything a
background process appends to: a capture inbox, a generated report, a scan log. No wording about
pathspecs could have caught it, so the rule now requires reading `git diff -- <path>` **before**
staging, forbids staging and committing in one shell call, and says plainly that a `--cached
--stat` count you cannot account for is a defect rather than a curiosity.

**The check already existed and was skipped, which is why this also ships a hook.**
`git diff --cached --stat` printed *"7 insertions"* for a one-line change; it was read, noted as
odd, and committed regardless. `hooks/staged_review_guard.py` (`PreToolUse`, `Bash`) makes the
existing check non-optional rather than adding a new one. It refuses two shapes: a command that
stages *and* commits, and a `git commit` where nothing has read the staged diff since it was
staged. `--stat` does not count as reading it — that was the actual failure. Refusals name the
staged paths and say to commit foreign changes separately or unstage them.

**Failure posture is allow.** Unparseable input, no repo, no readable state dir, any exception:
exit 0. The stage-and-commit check deliberately runs *before* any state lookup, so it still fires
when the state dir cannot be read — the moment a guard is most likely to be silently doing nothing.
A `--amend` with an empty index passes; a 15-minute TTL keeps a stale read from authorising a much
later commit.

**What it does NOT do: anything about the remote.** It cannot tell you `origin` has moved, or that
you are committing onto a merged branch. That gap is real and is tracked separately — the
orientation's divergence banner compares against `@{u}`, so a merged, abandoned branch reads as
perfectly in sync while the default branch has moved on.
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
