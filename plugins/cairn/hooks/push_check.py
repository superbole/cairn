#!/usr/bin/env python3
"""Verify, mechanically, that a wrap's push-stop actually held (BACKLOG.md B86).

WHY THIS EXISTS
---------------
B22 (v1.40.0) made step 5 of `skills/wrap/SKILL.md` **commit locally and stop before the
push** whenever the session ran unattended (`AFK`) or otherwise walked away before they could
read the output. The rule was never falsifiable: the agent decides not to push, *reports*
that it did not push, and nothing anywhere checked. The day it shipped, a concurrent
`atlas` session reported "committed and held" while a `PostToolUse` hook had, in fact,
pushed every one of its commits — it honoured the instruction exactly and the outcome was
the opposite, and it only found out by going looking for an unrelated reason.

The premise was later corrected (that hook is deploy-guarded, not universal, and most of the
apparent duplication was a legitimate Bash+PowerShell pair) — but one push in that session's
reflog was still unaccounted for, so the honest position is *"we cannot tell, from inside the
session, whether the stop held"* — which is exactly the thing B22's rule needs to be able to
state. See BACKLOG.md B86 and `skills/wrap/references/incidents.md` for the incident this
file exists to make checkable.

THE FIX IS A MEASUREMENT, NOT AN INSTRUCTION
---------------------------------------------
At the moment the wrap stops (or succeeds), run

    git rev-list --left-right --count origin/<branch>...HEAD

`--left-right` against `origin/<branch>...HEAD` reports two counts: how many commits are
reachable from `origin/<branch>` and not `HEAD` (BEHIND), and how many are reachable from
`HEAD` and not `origin/<branch>` (AHEAD). If the wrap just committed locally and stopped,
AHEAD must be > 0 — those are the commits it is holding back. **An AHEAD of 0 right after a
commit-and-stop means something pushed the work without being asked**, which is precisely
the failure B86 exists to catch.

REJECTED (both named in B86, and repeated here on purpose)
------------------------------------------------------------
- **Forbidding or auditing push hooks.** Not this plugin's business, the `atlas` hook
  turned out to be legitimate, and inspecting another project's hook configuration is a far
  larger blast radius than reading one ref this repo already has.
- **Trusting the agent's own account of whether it pushed.** That is the party most likely
  to be wrong (B68's objection) — the entire point of this file is to replace that account
  with something measured.

THE FAMILY OF BUG THIS FILE MUST NOT REINTRODUCE
--------------------------------------------------
B86 itself names the trap: a gate that cannot distinguish "nothing to report" from "could not
run" is the same defect it exists to catch (see `archive_offer.py`'s B35 note for the same
shape, one file over). `ahead == 0` is loud and alarming ONLY when the check actually ran
against a real `origin/<branch>` ref. So every reason this cannot run — no repo, no commits
yet, detached HEAD, no `origin` remote, no `origin/<branch>` ref (never pushed, or never
fetched) — is its own `CANNOT_CHECK` reason code, never silently folded into "ahead is 0."

**And `ahead == 0` is by itself AMBIGUOUS, which is the same trap one turn further in.** It
means either "this wrap committed and something pushed it unasked" (the alarm) or "this wrap
committed nothing, so there was never anything to hold" (utterly routine — every wrap of a
session that only read). A check that shouts ALERT at the routine case is the alarm-fatigue
failure this repo already knows by name: a warning that fires in a benign common state gets
read as normal and skipped, which destroys the alarm for the case that matters. So the caller
passes `--since <sha of HEAD before the wrap committed>` and the two readings are separated
by whether HEAD actually moved; with no baseline the honest answer is `CANNOT_CHECK`
(`no-baseline`), never a guess in either direction.

The four top-level outcomes (`HELD`, `ALERT`, `NOTHING_TO_HOLD`, `CANNOT_CHECK`) are mutually
exclusive and the CLI's first line is always one of those four tokens, so a caller (or a
human) can tell them apart without parsing prose.

OFFLINE, NEVER BLOCKS, NEVER FAILS THE WRAP
---------------------------------------------
Reads a ref the repo already has (`origin/<branch>`, from the last fetch/push — no network
call here) and never raises: every failure path returns a `CANNOT_CHECK` reason rather than
an exception, and `main()` always exits 0. This is a report, not a gate — it must never be
the reason a wrap stalls.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reentry_state import git, project_root                       # noqa: E402

HELD = "HELD"
ALERT = "ALERT"
NOTHING_TO_HOLD = "NOTHING_TO_HOLD"
CANNOT_CHECK = "CANNOT_CHECK"


def current_branch(root: Path) -> str | None:
    """The checked-out branch name, or None if detached (or unreadable)."""
    name = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if not name or name == "HEAD":
        return None
    return name


def has_commits(root: Path) -> bool:
    return git(root, "rev-parse", "HEAD") is not None


def has_remote(root: Path, remote: str = "origin") -> bool:
    remotes = git(root, "remote")
    if remotes is None:
        return False
    return remote in remotes.splitlines()


def upstream_ref(root: Path, branch: str, remote: str = "origin") -> str | None:
    """`origin/<branch>` if that ref exists in this checkout, else None.

    Existence, not freshness — this never fetches. A stale `origin/<branch>` (behind the
    real remote HEAD) still answers the question this file asks: did commits leave the
    working tree since the last time we knew where origin stood.
    """
    ref = f"{remote}/{branch}"
    return ref if git(root, "rev-parse", "--verify", "--quiet", ref) is not None else None


def check(root: Path, remote: str = "origin", since: str | None = None) -> dict:
    """The whole verification, as a plain dict — never raises.

    Keys always present: `status` (`HELD` | `ALERT` | `CANNOT_CHECK`), `message` (one
    human-readable line). On `HELD`/`ALERT` only: `ahead`, `behind`, `branch`, `ref`. On
    `CANNOT_CHECK` only: `reason` (a short machine-readable code).
    """
    if not has_commits(root):
        return {"status": CANNOT_CHECK, "reason": "no-commits",
                "message": "no commits yet in this repo — nothing to check"}

    branch = current_branch(root)
    if branch is None:
        return {"status": CANNOT_CHECK, "reason": "detached-head",
                "message": "HEAD is detached (no branch name) — cannot compare against "
                           "an upstream branch"}

    if not has_remote(root, remote):
        return {"status": CANNOT_CHECK, "reason": "no-remote",
                "message": f'no "{remote}" remote configured — nothing to compare against'}

    ref = upstream_ref(root, branch, remote)
    if ref is None:
        return {"status": CANNOT_CHECK, "reason": "no-upstream",
                "message": f"no {remote}/{branch} ref in this checkout — the branch has "
                           "never been pushed/fetched here, so there is nothing to "
                           "compare HEAD against"}

    counts = git(root, "rev-list", "--left-right", "--count", f"{ref}...HEAD")
    parts = counts.split() if counts else []
    if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
        return {"status": CANNOT_CHECK, "reason": "rev-list-failed",
                "message": f"`git rev-list --left-right --count {ref}...HEAD` did not "
                           "return two counts — cannot tell whether the push held"}

    behind, ahead = int(parts[0]), int(parts[1])
    common = {"ahead": ahead, "behind": behind, "branch": branch, "ref": ref}
    if ahead > 0:
        return {"status": HELD, **common,
                "message": f"{ahead} commit(s) ahead of {ref}, not pushed: the stop held."}

    # ahead == 0. On its own that is AMBIGUOUS, and saying ALERT here anyway is the exact
    # bug family this file exists to avoid -- see the module docstring. Only the baseline
    # sha (HEAD as it stood BEFORE this wrap committed) separates the two readings.
    if since is None:
        return {"status": CANNOT_CHECK, "reason": "no-baseline", **common,
                "message": f"0 commits ahead of {ref}, and no --since baseline was given, "
                           "so this cannot tell 'nothing was committed' from 'the commits "
                           "were pushed unasked'. Re-run with --since <sha of HEAD before "
                           "the wrap committed>."}

    head = git(root, "rev-parse", "HEAD")
    base = git(root, "rev-parse", "--verify", "--quiet", since)
    if head is None or base is None:
        return {"status": CANNOT_CHECK, "reason": "bad-baseline", **common,
                "message": f"--since {since!r} is not a resolvable commit in this repo, so "
                           "the 0-ahead count cannot be interpreted."}

    if head == base:
        return {"status": NOTHING_TO_HOLD, **common,
                "message": f"0 commits ahead of {ref} and HEAD has not moved since {since[:12]}: "
                           "this wrap committed nothing, so there was never anything to hold "
                           "back. Not an alert."}

    return {"status": ALERT, **common,
            "message": f"HEAD moved from {base[:12]} to {head[:12]} this wrap, yet it is 0 "
                       f"commits ahead of {ref}: something pushed the work without being "
                       "asked. Check the reflog before reporting anything else as fine."}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    since = None
    for i, a in enumerate(argv):
        if a == "--since" and i + 1 < len(argv):
            since = argv[i + 1]
        elif a.startswith("--since="):
            since = a.split("=", 1)[1]

    root = project_root()
    result = check(root, since=since)
    print(f"{result['status']} — {result['message']}")
    if "branch" in result:
        print(f"  branch={result['branch']} ahead={result['ahead']} "
              f"behind={result['behind']} against={result['ref']}")
    if "reason" in result:
        print(f"  reason={result['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
