# BACKLOG — cairn
<!-- next-id: 9 -->

Everything worth doing that is NOT in `NEXT.md`'s Queue. Unbounded and unordered —
the ordering that matters lives in the Queue, which is capped at 5 and refilled from here.

Items marked `queued` are on the Queue right now and stay listed here until the work lands.
Where the repo has GitHub Issues, `tools/sync_backlog.py` mirrors this file to them; the
file is the writer and Issues is the copy that survives a lost machine.

## B8. `/cairn:next` and `/cairn:wrap` should tell the agent to read files with Read, not a shell chain
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-23`
On re-entry, an agent read NEXT.md's Queue, INBOX.md and git state in ONE Bash call:
`cd /c/…/agent-reentry && sed -n '/^## Queue/,/^## Decisions/p' NEXT.md; ls INBOX.md 2>/dev/null && cat INBOX.md; git log --oneline -3; git status -sb | head -3`.
Every piece of it is read-only and auto-allowed on its own, but the chain (a `cd` combined with
`git`, plus `;`, `&&`, a pipe and a redirect) still brought up an **"Allow Claude to run …?"**
prompt. He asked how to stop it (2026-09-23, `agent-reentry` on SBOLE-NB5). A prompt at the very
first step of re-entry is the attention cost this plugin exists to remove.

**Fix:** one line in each skill's Procedure — *read `NEXT.md`, `INBOX.md` and `BACKLOG.md` with the
Read/Grep tools (offset/limit for one section); run each `git` command as its own plain call; never
chain them behind a `cd`.* Consider the same line in `rules/CLAUDE.md` under "How work gets done",
since sessions that never load a skill read these files too.

**Ruled out:**
- **An allowlist rule** — no `permissions.allow` pattern can match an arbitrary compound
  command, and the prompt comes from the `cd`+`git` combination, not from any single command.
  (`agent-reentry` got a read-only MCP allowlist the same day; it doesn't cover this case.)
- **A per-project memory** — saved in `agent-reentry`, but it loads only there.

**Check:** SKILL.md rule changes need an `incidents.md` check in the same commit (this repo's
CLAUDE.md, if carried over from `agent-reentry`).

## B3. "Commits since the last wrap" ignores wraps made on another machine
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-23` · issue `#3`
`reentry_state.unwrapped_commits()` counts `rev-list <.last_wrap>..HEAD`, and `.claude/.last_wrap`
is gitignored — so it only knows wraps made on the machine reading it. A wrap on one machine,
pulled to another, makes the second raise **"THE LAST SESSION DID NOT FINISH CLEANLY — N commits
since the last wrap"** (`session_orientation.py` ~l.709, `dirty_tree_warning.py` ~l.146) about
work that was wrapped properly.

**Observed 2026-09-23, `workspace` on SBOLE-NB5:** 12 commits flagged. NB5's marker said `6b4fdaa`;
NB1 had since wrapped twice (`df5378f`, `323d835`, each with a CHANGELOG entry and a `NEXT.md`
rewrite), and the rest were committed inbox/backlog captures. Reconciling it cost a session's
first round of work and found nothing wrong.

**Proposed fix:** count from the NEWER of the local marker and the newest commit reachable from
HEAD that is wrap-shaped — touches both `CHANGELOG.md` and `NEXT.md`, or subject starts `wrap:`.
`last_commit_is_wrap_shaped()` already sits beside it and only looks at HEAD; generalise it to
"newest such commit" (`git log -1 --format=%H -- CHANGELOG.md` intersected with `NEXT.md`, scoped
by `_scope(root)`).

**Ruled out:**
- **Tracking the marker in git** — every wrap would commit it, and two machines wrapping the same
  day conflict on it. The gitignore is deliberate (`reentry_state.py` docstring).
- **Changing `wrap_receipt.py`** — not needed. The receipt is the verdict and keys to the session
  baseline, not this count; this is only the orientation's nudge. Leave the receipt alone.

**Accepted risk:** a session that commits CHANGELOG + NEXT.md together without running `/cairn:wrap`
reads as wrapped here. That commit IS the substance of a wrap, and the receipt still catches the
missing steps, so the D4 false-wrap failure does not recur through this path.

**Why it matters:** this box also carries uncommitted-file warnings. Firing it on every machine
switch — his normal NB1↔NB5 pattern — trains him to skip it (the cry-wolf boundary, `item_open.py`).

## B4. A merged feature branch reads as in-sync, so the orientation shows a stale NEXT.md silently
`Opus 5` · effort `high` · `HITL/Auto` · added `2026-09-23` · issue `#4`
The divergence banner compares HEAD to `@{u}`. A checkout left on a feature branch after its MR
merged is `0 0` against its own upstream with a clean tree — no banner, no warning — while the
default branch has moved on and rewritten `NEXT.md`. The orientation then relays the branch's copy.

**Observed 2026-09-23, NB5 WSL `bsr-tools`:** sat on `feat/pen-test-headers-53` after MR !5 merged.
`0 0` against `origin/feat/pen-test-headers-53`; `master` was **41** commits behind `origin/master`
by the time it was noticed (3+ at first sighting), and those commits included wraps rewriting
`NEXT.md`. Fixed by hand: `git switch master && git merge --ff-only origin/master`.

**Candidate fix:** when the current branch is not the default branch, also compare HEAD to
`origin/<default>` (from `git symbolic-ref refs/remotes/<remote>/HEAD`, remote taken from `@{u}` —
several repos' upstream is not `origin`). If HEAD is an ancestor of it (`merge-base --is-ancestor`),
say *"this branch is merged; <default> is N ahead — switch?"*. Offer, never switch unasked.

**Ruled out:** comparing to the default branch always — an unmerged feature branch is legitimately
behind master, and warning on every one would be wallpaper. The ancestor test is what makes it
specific to the merged-and-forgotten case.

## B7. On WSL with the Windows `gh.exe`, every GitHub issue re-body fails ("cannot find the file")
`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-09-23` · issue `#7`
**Seen 2026-09-23 on NB5 (WSL):** `sync_backlog.py` in `cairn` printed `! B5 — could not update #5:
open /tmp/tmpXXXX.md: The system cannot find the file specified.` On NB5, `~/.local/bin/gh` is a
**symlink to `/mnt/c/Program Files/GitHub CLI/gh.exe`**. `hooks/issue_host.py` `_body_file()`
writes the body with `tempfile.mkstemp()` into WSL's `/tmp` and passes that Linux path to a
Windows exe, which can't open it.

**What is and isn't affected:** `create` passes the body in argv (see the comment near line 632),
so **filing** new issues works (B6 was filed as #6 in the same session). Only `update` (line 477,
re-bodying an existing issue) fails, and it fails every time. The sync reports "file is still
right", so nothing is lost locally, but GitHub issue bodies stop updating on this machine without
anyone noticing. `glab` on NB5 is a native Linux ELF, so GitLab projects (`bsr-tools`) aren't
affected.

**Likely fix:** when the resolved CLI is a `.exe` running under WSL (`/proc/version` contains
`microsoft`), put the temp file somewhere Windows can see (e.g. under `/mnt/c/Users/<u>/AppData/
Local/Temp`) and pass the path converted with `wslpath -w`. Or pass the body in argv, as `create`
already does. The alternative is a native Linux `gh` on NB5, which is machine state for
`workspace`, not a plugin fix.

## B6. `/clear` starts a new session with no baseline, so its wrap reads `CAIRN UNKNOWN`
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-23` · issue `#6`
**Root cause, measured 2026-09-23 on NB5 (CLI, WSL, `bsr-tools`):** `/clear` gives the session a
**new `session_id`** (a new transcript file, `8116a414…`, whose first entry is the `/clear` itself)
but cairn stamps no baseline for it, on two layers:
1. `hooks/hooks.json` — the `SessionStart` matcher is `startup|resume`, so the hook never runs on
   `source: clear`.
2. `hooks/session_orientation.py` `_is_reentry_moment()` — even if it did run, `main()` returns on
   `clear`/`compact` **before** `wrap_receipt.stamp_baseline(root)`.

So every receipt taken after a `/clear` is `CAIRN UNKNOWN`, even when the whole wrap ran (the
`bsr-tools` session this was found in: CHANGELOG, NEXT.md, commit and push all verifiably happened,
receipt `UNKNOWN`, then the next session opened with "did not finish cleanly"). **Not WSL- or
CLI-specific:** it happens anywhere `/clear` is used. The session started from the project dir, so
this is not B5 or the parent-dir case.

**Also wrong:** `skills/wrap/SKILL.md` (the model-switch table) says `/clear` "keeps the session's
identity". The transcript shows a new session id.

**Likely fix (decide in Plan):** add `clear` to the matcher, and in `main()` stamp the baseline for a
`clear` source **silently** (no relay, since the 2026-08-22 incident about relaying the queue
mid-session still applies), then return. `compact` keeps its session id, so it stays excluded. Open
question: should a `clear` also count as a re-entry for relay purposes, since the context really is
empty afterwards?

## B5. The wrap receipt cannot verdict a sibling repo — hit 3x in one legitimate multi-repo session
`Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-23` · issue `#5`
`wrap_receipt.py --record` against any repo other than the session's own project prints `CAIRN
UNKNOWN` ("no session baseline to compare HEAD against"), even when that repo is clean, committed
and pushed. **This is the case B2's fix deliberately left out** (`docs/decisions.md` D26: *"rooted
in project A, working in project B … falls to UNKNOWN — covering it would put the cost on every
ordinary session"*).

**Observed 2026-09-23:** one session worked across `bsr-tools`, `workspace` and `cairn`; 2 of the 3
repos could only ever read `UNKNOWN`. The same pattern again the same day: a `workspace` session on
NB5 committed to `cairn` and to WSL repos. Cross-repo work is his normal pattern, not an edge case.

**Why it matters:** the rules make the receipt the one thing to trust over English. A mechanism that
cannot answer for most of the repos a session touches pushes the verdict back onto prose — the
failure it exists to prevent.

**Decide before building (hence Plan):** is D26's cost estimate still right given it now fires
routinely? A cheap option to cost: stamp a baseline for a sibling repo lazily, on the first write
the PostToolUse recorder sees there (`touched_repos.py` already records which repos were touched),
so the cost lands only on sessions that actually cross repos. Not related to agent-reentry B143
(no-baseline reads SKIPPED in the session's OWN repo).

**Same pattern in `tools/sync_backlog.py` (seen 2026-09-23):** run from inside `cairn` during a
`bsr-tools` session, it synced **`bsr-tools`** ("synced with issr/bsr-tools"). It resolves the
project from the session and ignores the cwd, and it has no `--root` flag. Setting
`CLAUDE_PROJECT_DIR=$PWD` works around it. That run wrote nothing, but only because nothing had
changed in bsr-tools.
