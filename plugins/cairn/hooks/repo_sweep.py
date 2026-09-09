#!/usr/bin/env python3
"""The CROSS-REPO staleness sweep — B26, issue #26, 2026-09-05.

`session_orientation.py`'s `_divergence_warning` checks exactly one repo: the one this
session happens to be standing in. The user asked, 2026-08-31: "does the Git staleness
report across all folders/repos under /Projects?" It did not. A portfolio of ten-plus
repos on three machines has the exact same "another machine has work this one doesn't"
problem, ten times over, and nothing said so unless they happened to open that repo.

WHERE THE REPO LIST COMES FROM (decided here, not for relitigation without re-reading
the brief and BACKLOG.md B26 first)
----------------------------------------------------------------------------------
Sibling directories of the project root, filtered to the ones that are (a) git repos
and (b) carry their own `NEXT.md`. No new config file, no `catalog.yml` — the brief's
own recommendation, and B14/B27 already mean "has a NEXT.md" is a real, load-bearing
signal for "this is a project the user actively tracks with this system", not just "a
folder that happens to have a .git in it". Measured 2026-09-05 against the real
`~/Projects`: 9 siblings are git repos, 8 of those carry a NEXT.md — the one exception is a
repo the user has never opted in, and excluding it is correct.

B59 (filed 2026-09-04) is the deliberately NOT-solved-here case: a machine list plus
`catalog.yml` for WSL trees and SSH boxes that are not siblings of anything on this
filesystem. This module only ever answers "the folders next to this one on THIS
machine", which is what B26 asked for and B59 explicitly builds on top of.

WHY THIS IS CACHED AND NEVER RUN INLINE (the other open question the brief left)
---------------------------------------------------------------------------------
Measured 2026-09-05 with a local fixture repo (`git init --bare` origin + a clone), so
this is the FLOOR, not the ceiling — a real fetch to GitHub/GitLab adds real network
latency on top of every number below:

    one `git` subprocess spawn (Windows)              ~105 ms
    one full per-repo check (branch, verify upstream,
      fetch, rev-list — 4 subprocess calls)            ~1.0-1.3 s
    8 repos, sequential, same machine, no network       ~8.3 s

Eight seconds is already the BEST case a session start could see, and it is paid on
every single session in every project, for a feature whose most common outcome (nothing
is behind) has zero payoff to show for the wait. Offline or on a flaky connection each
fetch can instead cost up to its own timeout before failing — worse, not better. That
rules out running this inline, for exactly the reason `issues_backlog.py` already
rejected a live call for the GitHub backlog: this module copies that pattern rather than
inventing a second one. `summary_line()` only reads a JSON cache (a stat + a read, no
subprocess at all); `spawn_refresh()` fires a DETACHED child that does the real work for
the NEXT session. The view is up to one session stale — the same trade `issues_backlog`
already made, for the same reason.

FAILURE IS SILENT, ON PURPOSE — same contract as `_divergence_warning`: offline, no
remote, detached HEAD, credential prompt, git missing. `GIT_TERMINAL_PROMPT=0` and a
short per-repo timeout, so a hung credential prompt in the detached child can never
compound across siblings into something that never finishes. A sweep that prints an
error for every unreachable repo trains the one real warning to be ignored too.

REPORT, NEVER ACT. No automatic `git pull`, `git fetch --prune`, or anything else that
touches a sibling's working tree — a plain `git fetch` only updates that repo's own
remote-tracking refs, the same operation `_divergence_warning` already performs on the
repo the user is standing in.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from reentry_state import NO_WINDOW, project_root, state_dir
except Exception:                        # standalone repo-local copy without the helper
    NO_WINDOW: dict = {}
    project_root = None                  # type: ignore[assignment]
    state_dir = None                     # type: ignore[assignment]

CACHE_NAME = "repo_sweep.json"

# A bound on how many siblings one sweep will check, not a real limit anyone here is
# close to (measured 2026-09-05: 9 git-repo siblings under ~/Projects). It exists to cap
# the DETACHED child's own worst-case runtime — at FETCH_TIMEOUT seconds per repo, a
# portfolio this size cannot turn into a background process that runs for minutes.
MAX_SIBLINGS = 25

# Seconds per sibling's `git fetch`, in the DETACHED child only — this hook's own session
# start never waits on it. Matches `session_orientation.FETCH_TIMEOUT`'s reasoning: best
# effort, never fatal, never worth blocking on.
FETCH_TIMEOUT = 8

# How many behind-repo names to put ON the one summary line before collapsing to a count.
# The line is read at every session start in every project; a name-everything line for a
# portfolio-wide problem would out-grow the "as few lines as possible" budget this whole
# feature is held to.
MAX_NAMED = 5


def sibling_repos(root: Path) -> list[Path]:
    """Sibling directories of `root` that are git repos carrying their own NEXT.md.

    THE `NEXT.md` REQUIREMENT IS THE SECURITY BOUNDARY, NOT ONLY AN OPT-IN FILTER.
    Opening one project makes this run `git` inside directories the user did not open, and
    `git` executes the TARGET repo's own config — `core.pager`, `core.fsmonitor`,
    `core.sshCommand`, aliases. So the set of repos reachable from here is the set of repos
    that can influence this process, and the only thing bounding it is that a repo must have
    joined this system by having its own `NEXT.md`. A clone dropped in the parent directory
    is inert until someone puts a `NEXT.md` in it. **Do not widen this gate to "has a
    `.git`"** — that would make every sibling clone reachable from every session.

    Excludes `root` itself — its own divergence is `_divergence_warning`'s job, already
    printed separately and first. Sorted for a deterministic, reviewable cache; a set
    that reorders itself between sessions would make "did this change" unanswerable by
    eye. Any unreadable entry is skipped, never raised — see the module docstring.
    """
    try:
        me = root.resolve()
        parent = me.parent
    except Exception:
        return []
    out: list[Path] = []
    try:
        candidates = sorted(parent.iterdir(), key=lambda p: p.name.lower())
    except Exception:
        return []
    for p in candidates:
        try:
            if not p.is_dir() or p.resolve() == me:
                continue
            if not (p / ".git").exists():
                continue                 # not a repo — an ordinary sibling folder
            if not (p / "NEXT.md").is_file():
                continue                 # not opted into this system — see docstring
        except OSError:
            continue
        out.append(p)
        if len(out) >= MAX_SIBLINGS:
            break
    return out


def _git(repo: Path, *args: str, timeout: int = 5) -> str | None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        r = subprocess.run(("git", *args), cwd=repo, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env, **NO_WINDOW)
    except Exception:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _behind(repo: Path) -> int | None:
    """Commits `repo` is behind its own `origin/<branch>`, or None for "not comparable
    or any failure" — detached HEAD, no upstream, offline, not a repo, git missing.

    Deliberately answers ONE question. `_divergence_warning` already reports ahead/behind/
    diverged/offline in full detail for the repo the user is standing in; a portfolio sweep
    naming every nuance for every sibling would blow the one-line budget the brief sets.
    Being ahead-only on a sibling is not this feature's problem — nothing there is stale
    FOR HIM reading it from elsewhere.
    """
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD":
        return None
    if not _git(repo, "rev-parse", "--verify", f"origin/{branch}"):
        return None                      # no upstream — nothing to compare
    if _git(repo, "fetch", "origin", branch, timeout=FETCH_TIMEOUT) is None:
        return None                      # offline, no remote, credential prompt, timeout
    counts = _git(repo, "rev-list", "--left-right", "--count", f"origin/{branch}...HEAD")
    if not counts:
        return None
    try:
        behind, _ahead = (int(n) for n in counts.split())
    except ValueError:
        return None
    return behind


def refresh(root: Path) -> None:
    """Sweep every sibling and (re)write the cache. Never raises, never prints.

    Called only from the DETACHED child spawned by `spawn_refresh` (see its docstring)
    or by hand with `--refresh` for testing. Writing an empty `behind` list when nothing
    is stale is what makes `summary_line` silent the next session — no cache and an
    empty cache both read as "say nothing", which is correct either way.
    """
    if state_dir is None:
        return
    d = state_dir(root)
    if d is None:
        return
    behind: list[dict] = []
    for repo in sibling_repos(root):
        try:
            n = _behind(repo)
        except Exception:
            n = None
        if n:                            # None or 0 both mean "nothing to report"
            behind.append({"name": repo.name, "behind": n})
    try:
        (d / CACHE_NAME).write_text(
            json.dumps({"at": int(time.time()), "behind": behind}), encoding="utf-8")
    except Exception:
        pass


def spawn_refresh(root: Path) -> None:
    """Fire and forget, for the NEXT session — never this one.

    Same contract as `issues_backlog.spawn_refresh`, copied rather than reinvented: a
    DETACHED child (Windows: no console flash, outlives the parent hook) that re-runs
    this file with `--refresh`. See the module docstring for why this can never be an
    inline call instead.
    """
    try:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
        kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": str(root),
            "env": env,
        }
        if os.name == "nt":
            kwargs["creationflags"] = 0x00000008 | 0x08000000   # DETACHED | NO_WINDOW
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--refresh"],
                         **kwargs)
    except Exception:
        pass


def summary_line(root: Path) -> str | None:
    """One line naming only the sibling repos behind origin, or None for silence.

    Reads a JSON file — no subprocess, no network, effectively free at session start.
    Silent for: no cache yet (first session after install; a refresh was just spawned
    for next time), a cache with nothing behind (the common case, by design), or an
    unreadable cache. A stale-but-real cache is preferred over none, same as
    `issues_backlog` — this never re-checks whether the cache itself is fresh; that is
    what `spawn_refresh` at the end of every session is for.
    """
    if state_dir is None:
        return None
    d = state_dir(root)
    if d is None:
        return None
    try:
        cache = json.loads((d / CACHE_NAME).read_text(encoding="utf-8"))
    except Exception:
        return None
    behind = cache.get("behind") or []
    named = [b for b in behind if isinstance(b, dict) and b.get("name")]
    if not named:
        return None
    shown = named[:MAX_NAMED]
    names = ", ".join(f"{b['name']} ({b['behind']} behind)" for b in shown)
    extra = len(named) - len(shown)
    noun = "sibling repo is" if len(named) == 1 else "sibling repos are"
    line = f"⚠  {len(named)} {noun} behind origin: {names}"
    if extra > 0:
        line += f", … {extra} more"
    return line


if __name__ == "__main__":
    _root = project_root() if project_root else Path.cwd()
    if "--refresh" in sys.argv:
        # Spawned detached by the SessionStart hook — must stay silent either way.
        refresh(_root)
    else:
        # Manual run: show exactly what the hook would print, from the cache on disk,
        # with no network call — same shape as `issues_backlog.py`'s own default path.
        _line = summary_line(_root)
        print(_line if _line else "(no cache yet, or no sibling repos are behind origin)")
