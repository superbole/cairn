#!/usr/bin/env python3
"""The BACKLOG layer — the issue host, surfaced at session start without a network call.

GitHub via `gh` and GitLab via `glab`, since v1.34.0 (issue #11) — everything
provider-specific lives in `issue_host.py` and is detected from the git remote, so this
file no longer knows which CLI answered.

Settled 2026-08-22 (decision D1 in `code/NEXT.md`, brief
`code/briefs/github-issues-vs-inbox.md`). Three layers, one job each:

    INBOX.md   capture. Ad-hoc, unstructured, always emptied.
    NEXT.md    the WORKING SET. Capped at 5, priority-ordered, item 1 is the single
               highest priority for this project.
    Issues     the BACKLOG. Unbounded, cloud-stored, survives a re-clone or a lost
               machine, and — the part no local file can do — OTHER PEOPLE CAN WRITE
               TO IT.

One board per project, not one board across all repos: "which project today" is
answered by each project's own Queue item 1, so a merged ranking has no job to do.

WHY A CACHE, AND WHY THE REFRESH IS DETACHED
--------------------------------------------
The whole re-entry mechanism currently costs ZERO network in the session-start path —
`session_orientation.py` reads files off disk and nothing else. That property is worth
keeping: this hook runs in every project on every start, and a `gh` call that hangs on
a flaky connection or an expired token turns an orientation aid into dead time before
they can type. `gh` on a cold auth keyring is not fast.

So the hook never waits. It reads whatever the last refresh left behind and fires a
DETACHED child to fetch a fresh copy for next time. The cost is that the view can be
one session stale — which is the right trade for a backlog: an issue filed an hour ago
showing up at the next session instead of this one changes nothing, whereas two seconds
of stall at every single session start is a tax paid forever.

The user chose this over a live 2s-timeout call and over "only the skills call `gh`",
2026-08-22. The third option was the tempting cheap one and it is the one that leaves
the gap open: they rarely types `/cairn:next` — the hook is what fires on its own — so
an issue filed by someone else could sit unseen for weeks. That is the exact failure
this system exists to prevent.

TWO WAYS THE CACHE GETS WRITTEN, AND WHY IT NEEDS BOTH
------------------------------------------------------
1. `--refresh`, spawned detached by the SessionStart hook. Free, automatic, no ritual.
2. `--ingest`, fed on stdin by `/cairn:wrap` from the AGENT'S OWN SHELL.

Route 2 exists because route 1 does not work on the user's private laptop, and the reason
is worth writing down because it will bite anything else that shells out from a hook:

    `python` on that machine resolves to the WindowsApps execution alias
    (`…\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe`). A process started through
    that alias runs in an app container with no access to the Windows Credential
    Manager — so `gh` inside it reports "You are not logged into any GitHub hosts",
    while the very same `gh` binary, run from the same shell, is authenticated fine.

    The container is INHERITED. Re-spawning through `sys.executable` does not escape it,
    even though `sys.executable` reports the real interpreter path and not the alias.
    Measured 2026-08-22: parent rc=1, child rc=1, both from
    `pythoncore-3.14-64\\python.exe`; the identical call from PowerShell returns rc=0.

    Permanent fix is a machine setting the user has to make themselves — turn the alias off
    under Settings → Apps → Advanced app settings → App execution aliases, or put the
    real Python directory ahead of `WindowsApps` on PATH. Until then, route 2 carries it.

Route 2 also happens to be better-timed: the wrap runs at the end of every session, so
the cache the next session reads is at most one session old — exactly the staleness they
signed up for when they chose the cached design over a live call.

FAILURE IS SILENT, ON PURPOSE
-----------------------------
No CLI, not authenticated, a remote on a host with no backend, offline, issues disabled:
the refresh records the reason in the cache and the hook prints NOTHING NEW. A hook that nags every
session about a tool they may not have installed is how a warning gets trained out. The
reason is kept in the cache file so `/cairn:next` and `/cairn:wrap` — which DO call
`gh` live, from a shell where a failure is visible and harmless — can report it properly.

Critically, a failed refresh **keeps the last good listing** (`_write_error`). Where the
app container above applies, the hook-spawned refresh fails at EVERY session start, so a
plain overwrite would erase the wrap's work within one session and the feature would look
like it worked exactly once. Stale-but-real beats empty.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from reentry_state import NO_WINDOW, project_root, state_dir
except Exception:                        # pragma: no cover - defensive, as everywhere here
    project_root = None                  # type: ignore[assignment]
    state_dir = None                     # type: ignore[assignment]
    NO_WINDOW: dict = {}                 # see reentry_state.py; {} = the old flashing behaviour

try:
    import issue_host                    # GitHub via `gh`, GitLab via `glab` (v1.34.0)
except Exception:                        # pragma: no cover - the read path does not need it
    issue_host = None                    # type: ignore[assignment]

try:                                     # cp1252 consoles would raise on the ⚠ below, and
    sys.stdout.reconfigure(encoding="utf-8")   # the resulting exception silently truncated
except Exception:                        # the inbound block on its first real test run
    pass

CACHE_NAME = "issues.json"
SEEN_NAME = "issues_seen.json"

# How many issues to fetch. The backlog is deliberately unbounded, but nothing above a
# hundred is going to be surfaced in a one-line summary anyway.
FETCH_LIMIT = 100

# The attendance label (v1.16.0). A queue item carries `AFK/Auto` or `HITL/Plan` in full;
# a backlog issue carries only the ATTENDANCE half, as a label, because a label is the only
# part of an issue that `gh issue list --label` can filter on. The mode stays in the body,
# where it is read once, at the moment the item is pulled into the Queue.
#
# It earns its place on the summary line for one situation: they have a machine free and no
# attention to give it. Nothing else in the system can answer "is there anything I can just
# set running?" without opening the backlog, which is the thing the one-line summary exists
# to avoid. Appended as a CLAUSE to a line that is already printed — never its own line.
AFK_LABEL = "afk"
HITL_LABEL = "hitl"

# Inbound issues get NAMED, not counted — they are the one thing here that does not come
# from them. More than a few and the orientation would blow its line budget, so the rest
# collapse into the count.
MAX_NAMED_INBOUND = 3

REFRESH_TIMEOUT = 25                     # seconds, in the DETACHED child only


# --------------------------------------------------------------------------- read side


def _paths(root: Path) -> tuple[Path, Path] | None:
    if state_dir is None:
        return None
    d = state_dir(root)
    return (d / CACHE_NAME, d / SEEN_NAME) if d else None


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def open_counts(root: Path) -> tuple[int, int]:
    """(open issues, of which labelled `afk`) from the cache. NO side effects.

    Separate from `summary_lines` because the caller is the TIER decision, which runs
    before anything is printed and must not consume the `seen` baseline — calling
    `summary_lines` for a count would mark every new issue as seen and silently eat the
    "N new since your last session" clause that the same session is about to print.
    Returns (0, 0) for no cache, an unreadable one, or an empty backlog.
    """
    paths = _paths(root)
    if not paths:
        return (0, 0)
    cache = _load(paths[0])
    issues = (cache or {}).get("issues") or []
    afk = sum(1 for i in issues
              if AFK_LABEL in {str(l).lower() for l in (i.get("labels") or [])})
    return (len(issues), afk)


def cached_repo(root: Path) -> str:
    """`owner/name` from the cache, or "" — for labelling the BACKLOG.md summary line."""
    paths = _paths(root)
    if not paths:
        return ""
    return ((_load(paths[0]) or {}).get("repo") or "")


def summary_lines(root: Path, count_line: bool = True) -> list[str]:
    """Lines to print under the queue, or [] for silence.

    `count_line=False` since v1.18.0: where the project has a `BACKLOG.md`, that file is
    the backlog and prints its own count, so all this layer still owes is the part no local
    file can know — an issue somebody ELSE filed. The `seen` baseline is consumed either
    way, because "new since your last session" is answered by the same call.

    Silence is the answer for: no cache yet (first session after install — the refresh
    fired alongside this call fixes that for next time), and an empty backlog. An empty
    backlog genuinely has nothing to say, and saying "0 open issues" every session is the
    alarm-fatigue failure in miniature.
    """
    paths = _paths(root)
    if not paths:
        return []
    cache_path, seen_path = paths
    cache = _load(cache_path)
    if not cache:
        return []
    # An `error` alongside real issues means the last refresh failed but an earlier one
    # succeeded — show the stale list rather than going silent. On their private laptop that
    # is the NORMAL state: every hook-spawned refresh fails in the app container and only
    # the wrap can write a good cache, so treating "error" as "say nothing" would have made
    # the whole feature invisible on the one machine it was built for.
    issues = cache.get("issues") or []
    if not issues:
        return []

    seen = set((_load(seen_path) or {}).get("numbers") or [])
    numbers = [i.get("number") for i in issues if isinstance(i.get("number"), int)]

    # First run has no `seen` file. Everything would read as "new", which is both untrue
    # and the noisiest possible introduction, so treat an absent baseline as "all seen".
    fresh = [i for i in issues if i.get("number") not in seen] if seen else []
    inbound = [i for i in fresh if i.get("inbound")]

    owner_repo = cache.get("repo") or ""
    afk = unjudged = 0
    for i in issues:
        names = {str(l).lower() for l in (i.get("labels") or [])}
        if AFK_LABEL in names:
            afk += 1
        elif HITL_LABEL not in names:
            # Unjudged, NOT `hitl`. An issue filed from the web, from a phone, or by
            # someone else never passes through a wrap, so this is the drift the scheme
            # has to survive: counted here so `--label afk` is never quietly filtering
            # over a partly labelled backlog. Clears itself at the next wrap.
            unjudged += 1
    out = [] if not count_line else [f"  BACKLOG — {len(issues)} open issue(s)"
           + (f" on {owner_repo}" if owner_repo else "")
           + (f", {len(fresh)} new since your last session" if fresh else "")
           + (f", {afk} runnable AFK" if afk else "")
           + (f", {unjudged} unjudged" if unjudged else "")
           + "."]

    if inbound:
        noun = "issue" if len(inbound) == 1 else "issues"
        out.append(f"  ⚠  {len(inbound)} {noun} filed by SOMEONE ELSE — this did not come from you:")
        for i in inbound[:MAX_NAMED_INBOUND]:
            out.append(f"       #{i.get('number')} {(i.get('title') or '')[:70]} — @{i.get('author') or '?'}")
        if len(inbound) > MAX_NAMED_INBOUND:
            out.append(f"       … {len(inbound) - MAX_NAMED_INBOUND} more")

    # Only spend the second line when something actually changed. On a quiet week the count
    # alone says everything, and 20 tokens of standing instruction on every session start in
    # every project is exactly the kind of tax that made the footer cap necessary.
    if fresh and count_line:
        out.append('  The backlog is NOT the queue. Say "triage the backlog" to pull one into NEXT.md.')

    _write(seen_path, {"numbers": numbers, "at": int(time.time())})
    return out


def _write(path: Path, payload: dict) -> None:
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def _write_error(path: Path, reason: str) -> None:
    """Record a failed refresh WITHOUT destroying a good cache.

    The refresh runs unattended in a detached child, and on any machine where it cannot
    authenticate it runs — and fails — at every single session start. A plain overwrite
    would therefore clobber the last good listing within one session of it being written,
    so the feature would appear to work once and then never again. Keep the issues, record
    why the refresh failed, and leave `at` pointing at when the data was actually fetched.
    """
    prev = _load(path) or {}
    prev.update({"error": reason, "error_at": int(time.time())})
    _write(path, prev)


# -------------------------------------------------------------------------- write side


def spawn_refresh(root: Path) -> None:
    """Fire and forget. Must never block, never raise, never print.

    THIS IS THE PLUGIN'S ONE OUTBOUND NETWORK CALL, AND IT IS UNANNOUNCED.
    The child shells out to the issue host (`gh`/`glab`) to cache the issue list. In the
    FIRST session after a project is opted in there is no cache, so that session is the one
    where a network call leaves the machine — detached, outside the hook timeout, with every
    stream sent to DEVNULL, so nothing is printed at the time and a failure is invisible.
    That is deliberate: session start must never wait on, or be broken by, a network. But it
    means opting a project in has a side effect the user is not told about in the moment, so
    it is disclosed up front in `docs/guide.md` and `README.md` instead. Gated on the project
    having a `NEXT.md`; a non-opted-in project makes no call at all.

    The child re-runs this file with `--refresh`. It inherits nothing that matters
    except `CLAUDE_PROJECT_DIR`, which is how it knows which project to ask about —
    cwd alone is not reliable once the parent has exited.
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
            # DETACHED_PROCESS | CREATE_NO_WINDOW — no console flash, and the child
            # outlives the hook rather than being killed with it.
            kwargs["creationflags"] = 0x00000008 | 0x08000000
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--refresh"], **kwargs)
    except Exception:
        pass


def refresh(root: Path, report: bool = False) -> str:
    """Fetch the open issues and write the cache. Returns a one-line status.

    Two callers, two contracts. The SessionStart hook's detached child must print nothing
    ever, so it ignores the return value. `/cairn:wrap` runs the same function from the
    agent's own shell — where the CLI is actually authenticated, see the app-container note
    above — and wants to be told, so it passes `--report`. That replaced a two-command `gh`
    incantation in `wrap/SKILL.md` that could only ever have worked on GitHub (v1.34.0).

    HOST-AGNOSTIC since v1.34.0 (issue #11): `issue_host.detect` picks `gh` or `glab` off
    the git remote, so a work repo on `git2.example-corp.net` populates this cache exactly as
    a GitHub one does. The failure contract is unchanged — record the reason, keep the last
    good listing, print nothing.
    """
    paths = _paths(root)
    if not paths:
        return "no writable state directory — issues cache not refreshed"
    cache_path, _ = paths

    def _fail(reason: str) -> str:
        _write_error(cache_path, reason)
        return f"issues cache NOT refreshed ({reason}) — the last good listing is kept"

    if issue_host is None:
        return _fail("issue_host module unavailable")
    host, err = issue_host.detect(root)
    if host is None:
        return _fail(err)
    slug, owner, err = host.repo()
    if not slug:
        return _fail(err)
    issues, err = host.list_issues(FETCH_LIMIT)
    if issues is None:
        return _fail(err)

    _write(cache_path, _build(slug, owner, issues, host.name))
    return (f"issues cache refreshed from {slug} ({host.name}): "
            f"{len(issues)} open issue(s)")


def _build(repo: str, owner: str, issues: list, host_name: str = "") -> dict:
    """Stamp `inbound` onto `issue_host`'s already-normalised issue dicts.

    The provider-specific unpacking (`author.login` vs `author.username`, label objects vs
    label strings, `number` vs `iid`) moved into `hooks/issue_host.py` in v1.34.0. What is
    left here is the one judgement the cache exists to carry.
    """
    owner = (owner or "").lower()
    out = []
    for i in issues or []:
        author = i.get("author") or ""
        out.append({
            "number": i.get("number"),
            "title": i.get("title") or "",
            "author": author,
            "createdAt": i.get("createdAt"),
            "labels": [str(l) for l in (i.get("labels") or []) if l],
            # "Inbound" means: not written by the account that owns the repo. That is the
            # only class of item in this whole system that they did not put there themselves,
            # and therefore the only one that can surprise them.
            "inbound": bool(owner) and author.lower() != owner,
        })
    return {"repo": repo, "issues": out, "at": int(time.time()),
            "host": host_name or ""}


def _normalise_payload(raw: list, kind: str = "") -> tuple[list | None, str]:
    """Turn a CLI's own `issue list` JSON into the normalised shape.

    `--ingest` is fed by the WRAP's shell, so the JSON arrives raw from whichever CLI the
    agent ran. `kind` names it when the caller knows; otherwise the shape decides — a
    GitLab issue carries `iid`, a GitHub one carries `number`. Guessing is safe here and
    nowhere else: these are two fixed, disjoint schemas, not an open set.
    """
    if issue_host is None:
        return None, "issue_host module unavailable"
    k = (kind or "").lower()
    if not k:
        first = next((i for i in raw if isinstance(i, dict)), {})
        if "iid" in first:
            k = "gitlab"
        elif "number" in first:
            k = "github"
        else:
            return None, "could not tell GitHub JSON from GitLab JSON"
    cls = issue_host.BACKENDS.get(k)
    if cls is None:
        return None, f"unknown issue host `{kind}`"
    return cls.normalise(raw), ""


def ingest(root: Path, repo: str, owner: str, payload: str, kind: str = "") -> str:
    """Write the cache from JSON the AGENT fetched. Returns a one-line status.

    Used by `/cairn:wrap`, which can run the CLI from a shell that is actually
    authenticated — see the app-container note in the module docstring. Unlike every
    other path in this file, this one REPORTS failure: it runs where a human is looking.
    """
    paths = _paths(root)
    if not paths:
        return "no writable state directory — backlog cache not updated"
    try:
        raw = json.loads(payload)
    except Exception:
        return "could not parse the issue JSON — backlog cache not updated"
    if not isinstance(raw, list):
        return "expected a JSON array from `gh issue list` / `glab issue list` — backlog cache not updated"
    issues, err = _normalise_payload(raw, kind)
    if issues is None:
        return f"{err} — backlog cache not updated"
    data = _build(repo, owner, issues, (kind or "").title())
    _write(paths[0], data)
    return f"backlog cache updated: {len(data['issues'])} open issue(s)" + (f" on {repo}" if repo else "")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Hand-rolled `sys.argv` reading is what let `--help` run the default path instead
    of printing usage (issue #18, 2026-08-30). Nothing here writes outward — `--refresh`
    only READS GitHub and rewrites a local cache — so there is no `--dry-run`; the fix
    this file needed was usage text and a hard stop on an unknown flag.

    Parsed OUTSIDE the try below on purpose: that guard swallows every exception so a
    session start is never broken by the backlog, and a usage error must not be swallowed
    into a silent exit 0.
    """
    p = argparse.ArgumentParser(
        prog="issues_backlog.py",
        description="The session-start issues cache: read it, refresh it, or feed it.",
        epilog="With no flags it prints what the SessionStart hook would print, from the "
               "cache on disk, with no network call.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--refresh", action="store_true",
                   help="fetch open issues with `gh` and rewrite the cache; spawned "
                        "detached by the SessionStart hook, for the NEXT session")
    g.add_argument("--ingest", action="store_true",
                   help="rewrite the cache from `gh issue list --json` / `glab issue list "
                        "--output json` output produced by the caller's own shell")
    p.add_argument("--report", action="store_true",
                   help="with --refresh: print one line saying what happened. The hook's "
                        "detached child must stay silent; a wrap wants to be told")
    p.add_argument("--file", default="", metavar="PATH",
                   help="with --ingest: read the JSON from this file. The documented "
                        "route -- PowerShell 5.1 corrupts anything piped into a native exe")
    p.add_argument("--repo", default="", metavar="OWNER/REPO",
                   help="with --ingest: nameWithOwner of the repo the JSON came from")
    p.add_argument("--owner", default="", metavar="LOGIN",
                   help="with --ingest: the repo owner's login, to spot inbound issues")
    p.add_argument("--host", default="", choices=["", "github", "gitlab"],
                   help="with --ingest: which CLI produced the JSON. Optional — the shape "
                        "gives it away (`iid` is GitLab, `number` is GitHub)")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        root = project_root() if project_root else Path.cwd()
        if args.refresh:
            line = refresh(root)
            if args.report:              # the hook's detached child never passes this
                print(line)
        elif args.ingest:
            # `--file` is the documented route and stdin is the fallback, not the other
            # way round: Windows PowerShell 5.1 re-encodes anything piped into a native
            # executable, and it corrupted this exact JSON on the first live run
            # (2026-08-22). A file is the same two lines in every shell and cannot be
            # mangled in transit.
            payload = (Path(args.file).read_text(encoding="utf-8-sig") if args.file
                       else sys.stdin.read())
            print(ingest(root, args.repo, args.owner, payload, args.host))
        else:                            # manual run: show exactly what the hook would print
            for line in summary_lines(root):
                print(line)
    except Exception as exc:
        # --ingest and --report are the callers with a human watching; the rest stay silent.
        if args.ingest or args.report:
            print(f"backlog cache NOT updated: {type(exc).__name__}")
    sys.exit(0)
