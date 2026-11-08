**Not AFK-ready: B36 needs the reviewer's decision (Q1 to Q4 below). Stage 1 (a read-only, on-demand report over a declared list of local and WSL roots) becomes AFK once Q1, Q2 and Q3 are answered. Remote servers (Q4) stay out of stage 1 whatever the answer.**

# B36 — one git sweep over every environment a project lives in: groom brief

Backlog: `BACKLOG.md` B36 (issue #34), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-08 against `origin/main` at `f3f3cdb`. Every file:line
below was read at that commit.

## The ask, as filed

`repo_sweep.py` fetches *siblings of the current project*. The ask is one report over every clone
the user owns: the Windows tree, the WSL tree, and checkouts on remote servers. "Siblings of cwd"
cannot express that, because WSL is not a sibling of a Windows directory and a server is not on
this filesystem. So the input has to be a project list plus a machine (environment) list, not a
directory listing. Report only: behind / ahead / dirty / **unreachable said as unreachable**, then
offer a pull list; never pull unasked; stop on conflict. **Name the environment, not just the
repo**: one repo on Windows, in WSL and on a server is three rows (B40 is why).

Related entries: B31 (the cross-project morning roll-up, whose open input-source question was
deferred to this entry), B38 (the evening driver, whose last line "remotes the other machine should
pull tomorrow" is named as this entry's input), B40 (state is siloed per resolved path), B88 (the
"where do I run what" search, which needs the same two roots).

## What exists today, with evidence

| Piece | Where | What it means for B36 |
|---|---|---|
| Sibling discovery | `plugins/cairn/hooks/repo_sweep.py:116-156` `sibling_repos()`: siblings of the project root with `.git` AND their own `NEXT.md`, sorted, capped at `MAX_SIBLINGS = 25` (`:94`) | The `NEXT.md` gate is documented at `:119-126` as the **security boundary**: the sweep runs `git` inside each repo, and git executes the target's own config (`core.fsmonitor`, `core.sshCommand`, aliases). Any wider discovery must keep that gate per root, not just per sibling. |
| What one repo reports | `repo_sweep.py:169-193` `_behind()`: behind count only, `None` for every failure | Deliberately one number (`:173-177`). B36 asks for ahead, dirty and unreachable as well, so stage 1 needs its own per-repo probe rather than reusing `_behind()`. |
| Failure is silent | `repo_sweep.py:61-65` | Correct for a session-start line, wrong for B36, which asks for "unreachable said as unreachable". The two contracts differ, which is a reason to build B36 as a separate on-demand tool and leave the session-start line alone (Q3). |
| Cached, never inline | `repo_sweep.py:26-46` (measured ~1 s per repo, ~8.3 s for 8 repos, with no network) and the detached `spawn_refresh()` at `:266-290`, called from `session_orientation.py:1529-1531` | A cross-environment sweep adds a WSL process start per repo at least, so running it at session start is ruled out by the same measurement. An on-demand tool has no such budget. |
| The session-start line | `session_orientation.py:1126-1132` reads `repo_sweep.summary_line(root)` from cache | Unchanged by stage 1 under Q3 A. |
| Projects known to this machine | `plugins/cairn/tools/check_repos.py:195-206` `known_roots()`: every project with a `reentry-state/*/last_exit.json` | A list of roots this machine's Claude Code has *ended a session in*. Partial by construction (`:199`), and a WSL session writes its state under WSL's own home, so the Windows list never contains WSL roots. Useful as a seed, not as the source. |
| Machine names | `plugins/cairn/hooks/machine_identity.py:31-48`, `~/.claude/MACHINES.md`: one global file per machine, hostname to id | The precedent for where fleet-wide facts live: one global file, outside every repo, never in a project's `NEXT.md` (`:36-41` rejects the per-project copy). An environment list is the same kind of fact. |
| Per-path silos | B40 (`state_dir()` keys on `root.resolve()`) | Rows must name the environment because the same repo on Windows and under WSL are different working trees with different state. |
| Nothing reaches WSL today | Grep of `plugins/cairn/**/*.py` for `wsl` (case-insensitive): only comments, `check_leak_coverage.py:49` ("a WSL tree, an SSH box, a second `Projects` root") and `measure_context.py:132` | No code path in the plugin runs anything inside WSL or over SSH. Stage 1 is the first. |

### Finding 1: the stale cross-reference to this entry is "B59"

`repo_sweep.py:21-24` and `check_leak_coverage.py:49-50` both name this work as **B59**, its number
in the predecessor repo before the 2026-09-23 migration (`BACKLOG.md:448`: "Was `agent-reentry`
B59"). `BACKLOG.md` has no `## B59` heading today, and this repo's numbering means any B59 here is a
different item. A reader following "B59" from either file does not land on this entry. Stage 1
should change both comments to B36. Same kind of drift as the B35 groom brief's side note about
`archive_offer.py`.

### Finding 2: `validate_next.py` and `test_validate_next.py` also say "B36", for a different subject

`tools/validate_next.py:7` ("THE INCIDENT THIS EXISTS FOR (B36, filed 2026-08-31)") and
`tools/test_validate_next.py:2`, `:27`, `:150` use the old repo's B36, which was the missing-field
validator, not this sweep. A reader following "B36" from those files lands here. Not changed by
this brief; stage 1 should leave them alone too (they are not its files), and the attended pass can
decide whether to annotate them with the old number.

### Finding 3: reaching WSL from Windows has two shapes, and neither is measured here

From a Windows process, a WSL checkout can be reached either (a) by running Windows `git` against
the `\\wsl.localhost\<distro>\...` path, or (b) by running `wsl.exe -d <distro> -- git -C <path> ...`
so the Linux `git` inside WSL does the work. Not measured by this firing (it runs no command outside
its allow list). Known risks to check in stage 1, stated as unverified:

- (a) Windows `git` on a `\\wsl.localhost` path is commonly refused as "dubious ownership" unless
  `safe.directory` names it, and it reads the repo with Windows line-ending and file-mode settings,
  so `dirty` can be a false positive.
- (b) needs the distro name and runs the WSL user's git config and credentials, which is what the
  WSL session itself would see. That matches "name the environment" and is the more honest probe.
- Either way, if WSL is not running, the first call starts it, which can take seconds.

A WSL install of Claude Code has its own `~/.claude` and its own plugin install (B88 records a
desktop-app WSL session loading cairn, `BACKLOG.md:1247-1251`), so WSL already behaves as a separate
cairn machine, and (b) is consistent with that. Recommendation in Q2.

## Questions for the reviewer

### Q1. Where does the list of environments and roots come from?

- **A. A global `~/.claude/ENVIRONMENTS.md`**, created empty by an `ensure_` helper like
  `MACHINES.md`, with one row per root: environment id, kind (`local`, `wsl`, later `ssh`), and a
  path (plus distro for `wsl`). Each root is swept like a `Projects` parent: every child with `.git`
  and `NEXT.md` is a row. Same reasoning as `machine_identity.py:42-48`: a fleet fact, one file per
  machine, never in a repo, nothing personal shipped in the plugin.
- **B. Extend `MACHINES.md`** with a second table. One file fewer, but it mixes "which machine am I"
  with "which trees do I sweep", and `machine_identity.py`'s row parser (`_ROW_RE`, `:85`) would
  have to learn to tell the tables apart.
- **C. Derive it**: the Windows `known_roots()` plus whatever WSL's own `reentry-state` lists, read
  through the WSL filesystem. Zero setup, but it only knows projects a session has already ended in,
  and it couples this tool to WSL's state layout.

Recommendation: **A**, with C as a one-line hint in the empty template ("these projects have
sessions on this machine: ...") so filling it in is copying, not remembering.

### Q2. How is a WSL root probed?

- **A. `wsl.exe -d <distro> -- git ...`**, the Linux git inside WSL (finding 3 (b)).
- **B. Windows `git` on the `\\wsl.localhost` path** (finding 3 (a)).

Recommendation: **A**. It reports what the WSL session would see, and it avoids the ownership and
line-ending false positives. Stage 1 must measure one real call before the tests are written, and
put the measured time in the tool's docstring, the way `repo_sweep.py:28-35` did.

### Q3. Does this change the session-start line?

- **A. No.** B36 is a new on-demand tool, `tools/sweep_all.py`, run by hand, by `/cairn:wrap` at
  the evening driver (B38) and by the morning roll-up (B31) once they exist. `repo_sweep.py` and its
  cached session-start line stay as they are.
- **B. Yes**: feed the detached refresh from the environment list too, so the cached line covers
  WSL. That puts a WSL start and a fetch per WSL repo into a background process fired from every
  session in every project, and the line then names environments, which grows it.

Recommendation: **A**. The two features have opposite failure contracts (silent at session start,
explicit "unreachable" on demand, finding in the table above), and keeping them apart keeps both
honest.

### Q4. Remote servers

The entry includes "checkouts on remote servers". That means running `git` over SSH on another
host, with a credential, from a tool this plugin ships.

- **A. Leave `ssh` out of stage 1 entirely.** The row kind is reserved in the file format, the tool
  reports an `ssh` row as `not supported yet`, and a later entry designs it.
- **B. Support `ssh` rows in stage 1** with `ssh -o BatchMode=yes <host> git -C <path> ...`.

Recommendation: **A**. An SSH probe raises the credential question (`~/.claude/CREDENTIALS.md`, one
key reused everywhere) and executes on someone else's machine, which is a separate decision. The
unattended firings may not touch a server at all, so B can never be built by one.

## Stage 1 slice: on-demand local + WSL sweep (if Q1 = A, Q2 = A, Q3 = A, Q4 = A)

Fields line to paste under a new entry (or under B36 once narrowed):

`` `Opus 5` · effort `high` · `AFK/Auto` ``

(`Opus`/`high` because the WSL probe needs one measurement and the failure wording is a judgement;
everything else is specified.)

Files: new `plugins/cairn/hooks/ensure_environments_file.py` (copy the `MACHINES.md` pattern:
create-if-absent under `~/.claude`, generic template, never a real path), new
`plugins/cairn/tools/sweep_all.py`, new `plugins/cairn/tools/test_sweep_all.py`, and the two stale
"B59" comments (`hooks/repo_sweep.py:21`, `tools/check_leak_coverage.py:49`). A payload change:
routine version bump at the attended pass. `docs/file-formats.md` gains the file's format; if that
file is shared at the time, the text goes in the dossier instead.

- `sweep_all.py [--fetch] [--json]`. Reads `ENVIRONMENTS.md`. For each `local` root, list children
  with `.git` and `NEXT.md` (reuse `repo_sweep.sibling_repos`' gate: **a child without `NEXT.md` is
  never entered**). For each `wsl` root, do the same listing inside WSL (one `wsl.exe` call per root
  that lists the children and tests for both files), then probe each repo inside WSL.
- One row per (environment, repo): `env`, `repo`, `branch`, `behind`, `ahead`, `dirty` (count of
  porcelain lines), or `unreachable: <one-line reason>`. Never silent about a root it could not
  read: a missing root, WSL not installed, a distro name that does not exist, a timeout, each is a
  row.
- Default reads remote-tracking refs already on disk (no network), like `repo_sweep._local_behind`
  (`:196-215`). `--fetch` runs `git fetch origin <branch>` first, with `GIT_TERMINAL_PROMPT=0` and a
  per-repo timeout, as `_behind()` does (`:184`).
- Ends with a pull list: the `(env, repo)` rows that are behind and clean, with the exact command for
  each environment. **Never runs it.** A row that is behind and also dirty, or behind and also ahead,
  is listed separately as "needs a person", never in the pull list (the entry's "stop on conflict").
- Exit 0 always (advisory), same as `check_repos.py:76-78`.
- `ssh` rows: one line `not supported yet (B36 Q4)`.

Tests (fixtures only: temp directories and throwaway git repos, `CLAUDE_CONFIG_DIR` pointed at a
temp dir, never the real `~/.claude/`; the WSL path is exercised through an injectable runner, so
the suite never needs WSL installed):

1. No `ENVIRONMENTS.md`: one line saying so, exit 0, nothing created by the tool itself.
2. A `local` root with three children: one with `.git`+`NEXT.md`, one `.git` only, one plain dir.
   Only the first is a row; git is never run in the second (assert through the injected runner's
   call log).
3. Behind, ahead, dirty and clean fixture repos each produce the right row; a repo with no upstream
   reads `no upstream`, not `0 behind`.
4. A root that does not exist is an `unreachable` row naming the path.
5. A `wsl` row with a fake runner that returns two repos: two rows labelled with the WSL env id.
6. The fake runner fails (WSL missing, unknown distro, timeout): one `unreachable` row per case,
   reason text distinct for each.
7. The same repo name in a `local` and a `wsl` root: two rows, never merged.
8. Pull list contains only behind-and-clean rows; behind-and-dirty goes to "needs a person".
9. `--json` round-trips the same rows.
10. An `ssh` row prints `not supported yet` and runs nothing.
11. `ensure_environments_file.py`: creates the template once, never overwrites, template contains no
    real hostname or path (assert against `test_payload_clean` patterns).

Done: those tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, nothing left
in the real state dir, and one real WSL probe measured and written into the docstring (by the
attended pass if the unattended run cannot reach WSL).

## Out of scope

- SSH / remote server checkouts (Q4).
- Any automatic pull, fetch at session start, or change to `repo_sweep.py`'s cached line (Q3).
- B40's aliasing of state across paths.
- Wiring into `/cairn:wrap`, B31 or B38: they call the tool once it exists.

## Side note for the attended pass

The entry says "Extends `repo_sweep.py`". Under Q3 A it does not extend it; it reuses its gate and
its no-network probe and lives beside it. If the reviewer answers Q3 A, the entry's first sentence
should be reworded when it is narrowed.
