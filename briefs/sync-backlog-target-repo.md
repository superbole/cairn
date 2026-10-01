# Repo-acting tools must act on the repo they are run in, not the session's stamped project

`Opus 5` · effort `high` · `AFK/Auto` · from `BACKLOG.md` B98 (issue #109)

## The bug

From a `workspace` session, `cd ~/Projects/inflow && sh <root>/hooks/run.sh tools/sync_backlog.py --dry-run`
printed `DRY RUN against SBole/workspace`. `sync_backlog.main()` resolves the project through
`reentry_state.project_root()`, which prefers `CLAUDE_PROJECT_DIR`, then the session stamp (B72), and
only then the cwd. A real run would have synced workspace's backlog while the agent believed it was
syncing inflow's. The one output line that names the target is easy to skim past.

**Worse:** the workaround `CLAUDE_PROJECT_DIR=<repo>` re-stamps the session root
(`_resolve_project_root` calls `_stamp_session_root`), so every later cairn tool in the session
(`check_repos.py`, `wrap_receipt.py`) resolves to the sibling unless the variable is passed again.

**Same family:** `staged_review_guard.py` does not count `git -C <repo> diff --cached` as reading the
staged diff; only `cd <repo> && git diff --cached` clears it.

Ruled out: not a glab/GitLab issue. With the variable set, the sync targeted and filed correctly.

## What to build

1. Repo-acting tools (`sync_backlog.py` first; check `label_backlog.py`, `issues_backlog.py`) use the git
   toplevel of the cwd when it differs from the stamped root. If both are plausible and differ, refuse
   and name both rather than guess. Session-scoped tools (`wrap_receipt.py`, the orientation) keep the
   stamp.
2. An environment override must not overwrite the session stamp. Separate "resolve for this call" from
   "stamp the session".
3. `staged_review_guard.py` accepts `git -C <repo> diff --cached` as a read of that repo's staged diff.
4. Tests for each: a sibling cwd, an override that leaves the stamp alone, and the `-C` form.

Decide the exact precedence yourself and record it as a row in `docs/decisions.md`, naming the rejected
order.

## Where it stops

`AFK`: commit locally on an `afk/` branch per `docs/running-a-batch.md`, run the suite, and stop before
any push or `sync_backlog.py` run. Report files changed, test output and the precedence decision.
