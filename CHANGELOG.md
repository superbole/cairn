# CHANGELOG — cairn

Finished work, newest first, one entry per plugin version. `NEXT.md` is the queue and holds no
history; this file holds the history and no queue.

## 2026-09-26 — W5: overnight wave 1 reviewed and pushed; wave 2 never ran

No version bump. This is the review of v1.63.0 below.
- **Wave 1 reviewed against its diffs.** Lanes A (B63+B26), B (B59), C (B64) and the bookkeeping
  commit all hold. Re-verified on NB1: `run_tests.py` 33/33 pass. `check_install.py` shows the
  block digest line. `run.sh` refuses `../` and non-`hooks/`/`tools/` paths. `archive_guard.py`
  agrees with `wrap_receipt --check` (`NOT DUE`, so it allows). `session_orientation --check` is OK.
  Pushed, and the backlog synced.
- **Wave 2 (05:00) failed on its first model call** with `ECONNREFUSED`. NB1's API traffic goes
  through a proxy reachable only on VPN, and the VPN had dropped. It did no work. The machine-specific
  half is the `workspace` hub's W11.
- **Queued B70 (the October token plan) as item 1.** Its full brief is in the private config store,
  because the first public versions carried personal schedule detail. Those versions are still in
  public history (commits `5d2cd6a`–`cfec2f7`, and #68's edit history); whether to purge them is D37.
  Purging means a force-push and deleting the issue, both his to do or approve.
- **Sync bug found:** B71's `## 1.` sub-headings were parsed as items and filed as #70 and #71 (now
  closed as not planned). Repaired by hand; the fix is B72.
- **Filed B69**, the backlog item wave 2 was meant to file. Scheduled tasks start in Manual; fix it
  with allow and deny rules in `.claude/settings.json`. It now also asks for a network preflight
  in `running-a-batch.md`.

## 2026-09-26 — v1.63.0: rules blocks never roll back, skill commands resolve, the archive is guarded

Overnight lane batch, wave 1: four items in three lanes, each committed separately and **not pushed**.
Dossiers are in `docs/review/lane-{a,b,c}-2026-09-26.md`, and the handover is
`docs/review/overnight-handover-2026-09-26.md`.

- **B63 (D33).** When the installed rules block is newer, `install_rules` refuses: it writes nothing,
  keeps no backup, and prints one line naming both versions and the update command. The version parser
  is shared through `version_drift.compare_versions`. `check_install.py` flags a newer block, where a
  restart no longer resyncs. This only protects machines once they run v1.63.0; an older installer
  still downgrades.
- **B26 (D34).** The change line now reports `+A −R ~C lines`, up to three touched headings, and the
  exact `git diff --no-index` against the backup. The silent path computes nothing. `check_install.py`
  prints a digest of the installed block.
- **B59 (D35).** 20 call sites in the skills and rules now use `sh "<root>/hooks/run.sh" …`, where
  `<root>` is two directories above the skill's base directory. `run.sh` also runs `tools/…` files.
  The always-loaded rules grew by about 189 bytes (bytes/4, since tiktoken is absent).
- **B64 (D36).** A new `PreToolUse` `archive_guard.py` refuses an agent's self-archive while the
  verdict is `CAIRN OPEN`, including commits made after a `SET`. It fails open on everything else. It
  does not see a sidebar archive.

**Verified.** Full suite 33/33 with no state-dir leak. On a scratch copy of the live `CLAUDE.md`, a
same-version edit printed the summary, the re-run was silent, and a `v9.9.9` block was refused with
the file byte-identical and no backup. Lane B ran the rewritten lines with `CLAUDE_PLUGIN_ROOT` unset
in Git Bash and WSL Ubuntu, where there is no `python`. Filed: B66 (two remedies are wrong after B63),
B67 (`next-id` has two readings), and B68 (the old command form in docs).

## 2026-09-25 — D29 and D30 answered; B63 filed and queued first

No version change and no code change. This entry covers two commits from a session that didn't wrap.

- **D29: backlog ids are integers only.** An item that is split takes the next `next-id` and names
  its parent in its body. **D30: one D-number sequence per repo**, shared by open and answered
  decisions. Both rows are in `docs/decisions.md`. Both entries left `NEXT.md`'s Decisions list, and
  B16's open questions now carry the answers.
- **B63 filed.** On NB1 a v1.60.0 installer rewrote a v1.62.0 rules block, and the hook reported it
  as an update. `_install_block` never checks which direction a change goes. `next-id` also moved
  from 62 to 64, because filing B62 had left it behind.
- **This wrap queued B63 as item 1**, with a brief at `briefs/rules-block-downgrade.md`. The
  downgrade is harmless only while the rules body is unchanged, and B59 (now item 2) changes it.

## 2026-09-25 — v1.62.0: `install_rules` can no longer eat the user's own text

Queue item 1, B25. Before this fix, the managed block in `~/.claude/CLAUDE.md` started at the
first `<!-- reentry:begin` found anywhere in the file. A note above the block that quoted the
marker therefore became the block's start, and the next update silently replaced everything from
there to the real END. The only backup was one rolling copy, overwritten on every update.

Now the header must be a whole line with a version that closes on the same line, and the END
marker must be a whole line too. The installer refuses, and says so every session, on a
lookalike with no real block, two real headers, or a header with no END. The header is now one
line, `<!-- reentry:begin vX -->`. The legacy three-line header is still recognised, so installed
machines update. Backups are `CLAUDE.md.bak-reentry-install-v<outgoing>-<digest>`, one per
distinct state and never pruned. The old fixed-name backup is left alone. D32 records the
rejected options.

**Verified.** New `test_install_rules.py` (the module had no test file): 47 checks, all pass,
and it fails against v1.61.0 on the B25 case. Full suite: 31/31, no state-dir leak. By hand, on a
scratch copy of the live `CLAUDE.md` with a lookalike prepended: user text kept, the text below
the block byte-identical, the backup equal to the original, and the second run silent. The first
full-suite run caught the header pattern being stricter than the brief (it refused a one-line
header with words before `-->`); that was fixed.

## 2026-09-25 — v1.61.0: the hooks find Python on Linux

Queue item 1. Every hook in `hooks.json` ran bare `python`, which stock Ubuntu/Debian doesn't
have. A Linux install showed the plugin as enabled, and no hook ever started. All six commands
now go through a new POSIX shim, `hooks/run.sh`. It picks `$CAIRN_PYTHON`, then on Windows
`python`/`py -3`/`python3` (the old behaviour first), and elsewhere `python3`/`python`. When it
finds none, it says so: the first time the plugin can report that. D31 records why, and what was
rejected.

**Verified.** `test_hook_launcher.py` passes 23/23 against fake interpreters, covering interpreter
choice, pass-through of args, stdin and exit code 2, the no-Python warning, and a guard that
every `hooks.json` command routes through `run.sh`. On stock Ubuntu 24.04 (WSL on NB1, no
`python`), the old command exits 127. The new one wrote all five global files into a throwaway
HOME. On Windows the orientation output is byte-identical, and PostToolUse costs +68 ms (472 to
540 ms). `measure_context.py` now runs hooks in Git Bash/`sh` rather than cmd.exe, which couldn't
start the new command. The README states the Python and Git-for-Windows prerequisites.

Full suite: 28/30 on the first run. `test_payload_clean` caught a machine name in the new files,
and `test_git_encoding` caught a v1.60.0 defect, `staged_review_guard._run` decoding git output
with the locale codec. Both were fixed here and re-run individually, and both pass.

Not fixed: skills still say bare `python` (B59). Native Windows without Git Bash stops running
hooks (B60, the accepted cost).

## 2026-09-23 — the private backlog triaged in; the private source repo frozen

Queue item 2. All 60 items in the private repo's backlog were read in full, and each was closed there
with a pointer to where it went. **48 migrated here as B10–B57**, rewritten to drop employer,
server, machine and medical names while keeping every measurement. Two more (the old B139 and B133)
were the same defect as B9 and were merged into it. Five were closed as shipped, answered, done or
superseded; five that are about the operator's own setup went to `workspace` `INBOX.md`; and one
(the Graphify test) went to `bsr-tools` `INBOX.md`. The first keyword estimate was 25 migrate / 30
stay. Reading the items showed most private names were in the evidence, not the subject.

The private queue's Cursor adapter is now queue item 2 (B57). Its 640-line requirements report is in
`docs/cursor-adapter-requirements.md`, pseudonymised, with two stale rows fixed. Three publishable
briefs came across cleaned (B25, B26, B27). New here: decisions D29 and D30 (id rules), watches
W2–W4 (original `added` dates kept), and `docs/decisions.md` D27 (copied) and D28 (this copy is
now the writer). The sync filed #8–#57. All 60 private issues are closed, the private `NEXT.md` is
empty and frozen, and **this machine's clone is deleted** after an ask. It was checked `0 0`, with
no stashes and only disposable ignored files. The NB1 and DeepThought clones are `workspace` W9 and
W6. Private-name check: a scanner run over the added lines, fed the private-names file, found 0 hits
after one fix. It caught 8 of 8 on a control file first.

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

**VERIFIED LIVE, same day, on a restarted session running v1.60.0** — six shapes, each a real Bash
call through Claude Code's own `PreToolUse` plumbing rather than a fixture:

| shape | result |
|---|---|
| fresh-repo bootstrap, stage + commit in one call | refused (by design) |
| `cd <repo> && git commit`, staged but diff unread | **refused, and it named the staged path** |
| `git diff --cached` | allowed |
| commit after reading the diff | allowed, commit landed |
| prose merely mentioning the two verbs | allowed |
| `--stat` read, then commit | **refused** |

The second row is the v1.60.0 fix and the fifth is the false positive, both confirmed against the
live hook. The last row is the original 2026-09-23 defect's exact shape: a `--stat` glanced at and
a commit made anyway. It is now impossible. `NEXT.md` W1 is closed.

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
