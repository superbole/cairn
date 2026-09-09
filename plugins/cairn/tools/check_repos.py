#!/usr/bin/env python3
"""Assert that work dispatched into OTHER repos actually landed. Run by `/cairn:wrap`.

Every other check in this plugin looks at one repo: the one the session is running in.
`dirty_tree_warning.py` watches its tree, `session_orientation.py` reads its `NEXT.md`,
`unwrapped_commits()` counts against its wrap marker. A session that fans work OUT --
subagents each writing into a different repo -- is invisible to all of them, because the
parent repo can be spotlessly clean while every target is dirty.

THE INCIDENT (2026-08-25, issue #1)
-----------------------------------
A fan-out ran the automation-recommender across 8 repos and this repo's CHANGELOG logged
it finished: "every project kept at least one recommendation." A day later all 8 target
trees were still dirty -- nothing had been committed anywhere. The root cause of the bad
writes was `isolation: worktree` pointing each agent at the wrong repo (fixed by hand on
2026-08-26); the durable hole is that **"recommendation accepted" got written down as if
it meant "change committed"**, and no step anywhere asked the 8 repos whether that was
true. Recovered by accident, a day late.

WHY A TOOL AND NOT JUST A CHECKLIST LINE
----------------------------------------
The rejected option was a checklist step in whatever drives fan-out work. It fails twice:
this plugin does not own the fan-out prompt (so there is no single place to put the line),
and a checklist item is a thing the agent has to *remember* -- which is precisely what did
not happen. A parent session dispatching work is also the one least likely to be watched.
So: a tool that answers the question in one call, plus a rule in `wrap/SKILL.md` step 1a
that makes asking it an unconditional part of the survey.

**Position in the wrap is load-bearing.** Step 1a, BEFORE the CHANGELOG entry at step 2 --
not after the push. The check exists to constrain what the narrative is allowed to claim,
and by step 5 the claim is already written down.

WHERE THE REPOS COME FROM  (three sources, widest first)
--------------------------------------------------------
1. **Recorded** -- `hooks/repo_recorder.py` (PostToolUse, v1.25.0) resolves every written
   file to its git toplevel and logs the ones outside the session's own project. Read by
   default, with no arguments, since the last wrap. This is the source that does not
   depend on anybody remembering anything. Since B39 (v1.35.0) this also covers a best-
   effort regex read of `Bash`/`PowerShell` commands (a `cd`, or an absolute-path-shaped
   token) -- still NOT a shell parser, so still worth naming paths by hand when you know
   them; see `repo_recorder.py`'s own docstring for exactly what it can and cannot see.
2. **Named** -- the paths passed on the command line. Still accepted, and still worth
   passing: the recorder's Bash coverage is a heuristic, not a guarantee, so anything it
   could plausibly miss (a relative path, a variable, a heredoc body) reaches this tool
   only if the agent names it. The named list is now an ADDITION to the record, not the
   whole input.
3. **`--known`** -- every project the plugin has recorded a session ENDING in. A superset
   filtered by recency-of-use, for when you are unsure you have the full list.

A machine where the recorder has never fired degrades to exactly the v1.24.0 behaviour --
name the paths -- never to silence.

**B67 -- an empty record can also mean this SCRIPT asked the wrong project.**
`project_root()` (`reentry_state.py`) trusts `CLAUDE_PROJECT_DIR` when set, and that env
var is reliably exported to genuine hook processes but not necessarily to this script
when it is run as a plain Bash step (as `wrap/SKILL.md` step 1a does: `python
"$CLAUDE_PLUGIN_ROOT/tools/check_repos.py"`, no cwd or env pinned). If the session's
shell has `cd`'d elsewhere since the hook that recorded a write last ran -- e.g. into the
very sibling repo it just edited -- and `CLAUDE_PROJECT_DIR` is absent, `project_root()`
used to fall straight to `cwd()` and silently check that OTHER project's record instead:
"No record" was not "nothing to report", it was "asked about the wrong thing".
Reproduced 2026-09-05: see `docs/review/recorder.md`.

**Fixed at the source, B72 (v1.39.0).** `project_root()` now has a middle fallback
between `CLAUDE_PROJECT_DIR` and `cwd()`: this session's OWN previously-stamped root,
keyed by `CLAUDE_CODE_SESSION_ID` -- confirmed present in a plain-Bash-step's
environment even when `CLAUDE_PROJECT_DIR` is not. Safe under concurrency by
construction, unlike a rejected machine-global stamp (see BACKLOG.md's B72 entry and
`reentry_state._stamp_session_root`'s docstring): the key is this process's own session
id, which a different session can never present, so this can only ever answer for the
session asking. `project_root_source()` reports which of the three sources answered;
the message below still calls out the residual `"cwd"` case (no session id at all, or
none of this session's earlier calls ever saw `CLAUDE_PROJECT_DIR`) as the one still
worth a human's suspicion, since that is exactly the pre-fix behaviour.

NEVER RAISES. Same contract as everything else here: a wrap must never fail over a check.
Anything unreadable is reported as unknown, on its own line, and the exit code stays
advisory.

USAGE
    python check_repos.py                  # whatever this session actually wrote to
    python check_repos.py ~/Projects/atlas ~/Projects/lighthouse
    python check_repos.py --known          # every project this plugin has state for
    python check_repos.py --no-recorded    # ignore the recorder; name paths by hand
    python check_repos.py --json <paths>

EXIT
    0  every repo checked is clean and pushed (or nothing was asked)
    1  at least one repo has uncommitted or unpushed work, or could not be read
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hooks"))

try:
    from reentry_state import dirty_paths, git, project_root, project_root_source
    import touched_repos
except Exception as exc:                                    # pragma: no cover
    print(f"repo check skipped: cannot import the plugin's own modules ({exc})")
    sys.exit(0)

MAX_LISTED = 8


def _unpushed(root: Path) -> tuple[int | None, str | None]:
    """(commits ahead of upstream, note). None means the question has no answer here."""
    upstream = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if not upstream:
        # A repo with no remote-tracking branch is not broken -- plenty of local-only
        # repos exist -- but "committed" and "pushed" stop being the same claim, and the
        # fan-out case cares about the second one from a different machine.
        return None, "no upstream branch"
    count = git(root, "rev-list", "--count", "@{upstream}..HEAD")
    if count is None or not count.isdigit():
        return None, "could not count against %s" % upstream
    return int(count), None


def inspect(path: Path) -> dict:
    """One repo's state. Never raises; every failure becomes a readable field."""
    record: dict = {"path": str(path), "name": path.name, "ok": False, "toplevel": None,
                    "dirty": None, "unpushed": None, "note": None, "paths": []}
    try:
        # resolve(), not just expanduser(): a relative path like "." has an EMPTY .name,
        # so the report would identify the repo as "." -- useless in a list of eight.
        resolved = path.expanduser().resolve()
    except Exception:
        record["note"] = "unreadable path"
        return record
    record["path"] = str(resolved)
    record["name"] = resolved.name or str(resolved)

    if not resolved.is_dir():
        record["note"] = "no such directory"
        return record

    notes: list[str] = []
    changes = dirty_paths(resolved)
    if changes is None:
        # Distinguish the two ways this happens: being handed a path that was never a
        # repo is a different mistake from git being unavailable, and the fan-out case
        # produces the first one (a typo'd or wrongly-nested target) often enough to
        # be worth naming.
        record["note"] = ("not a git repo" if not (resolved / ".git").exists()
                          else "git could not read this repo")
        return record

    # A path INSIDE a repo used to answer for the WHOLE repo, and git said so without
    # complaint. `~/Projects` is itself a repo on this machine, so `~/Projects/docs` -- an
    # ordinary folder, not a checkout -- reported "clean, nothing unpushed" and looked
    # like a verified target. B13 (v1.29.0) fixed that at the source: `dirty_paths` now
    # scopes to the handed path's own subtree, so `dirty` above is about `docs` and not
    # about `Projects`. `_unpushed` below is still repo-WIDE and cannot honestly be
    # otherwise -- "ahead of upstream" is a property of the branch, not of a folder.
    #
    # So the mismatch is still NAMED rather than resolved away silently: the two numbers
    # in the row now answer at different scopes, and a reader who is not told that will
    # read the unpushed count as being about the folder.
    top = git(resolved, "rev-parse", "--show-toplevel")
    if top:
        top_path = Path(top)
        record["toplevel"] = str(top_path)
        try:
            same = top_path.resolve() == resolved
        except Exception:
            same = False
        if not same:
            notes.append("not a repo root -- dirty is this folder only; "
                         "unpushed is all of %s" % top_path.name)
            record["name"] = "%s (in %s)" % (resolved.name, top_path.name)

    record["dirty"] = len(changes)
    record["paths"] = [ln[3:].strip() for ln in changes[:MAX_LISTED]]
    ahead, note = _unpushed(resolved)
    record["unpushed"] = ahead
    if note:
        notes.append(note)
    record["note"] = "; ".join(notes) or None
    record["ok"] = (record["dirty"] == 0 and ahead == 0)
    return record


def known_roots() -> list[Path]:
    """Project roots this plugin has recorded a session ending in.

    Written by `dirty_tree_warning.py`'s SessionEnd branch, which stores `root` in
    `last_exit.json`. Partial by construction: a project only appears once a session has
    ENDED in it since v1.24.0, so this supplements the paths you name -- it never
    replaces them.
    """
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    found: list[Path] = []
    try:
        for statefile in sorted((Path(base) / "reentry-state").glob("*/last_exit.json")):
            try:
                root = json.loads(statefile.read_text(encoding="utf-8")).get("root")
            except Exception:
                continue
            if root and Path(root).is_dir():
                found.append(Path(root))
    except Exception:
        return []
    seen, unique = set(), []
    for p in found:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def recorded_roots() -> list[Path]:
    """Repos this session's tool calls actually wrote to, since the last wrap.

    The window is deliberately the wrap marker and not the session id: a PREVIOUS session
    that wrote into a sibling repo and then ended without wrapping is precisely the case
    this plugin exists to catch, and this tool -- run from a Bash step -- has no reliable
    way to know its own session id anyway. See `hooks/touched_repos.py`.
    """
    try:
        return touched_repos.touched(project_root())
    except Exception:
        return []


def render(records: list[dict]) -> str:
    lines = []
    for r in records:
        if r["ok"]:
            lines.append("  [ok] %s -- clean, nothing unpushed" % r["name"])
            # An `ok` carrying a note is the dangerous case, not the boring one: it is
            # clean, but not clean in the way you assumed. Never swallow it.
            if r["note"]:
                lines.append("       %s" % r["note"])
            continue
        bits = []
        if r["dirty"]:
            bits.append("%d uncommitted" % r["dirty"])
        if r["unpushed"]:
            bits.append("%d unpushed" % r["unpushed"])
        if r["note"]:
            bits.append(r["note"])
        lines.append("  [!!] %s -- %s" % (r["name"], ", ".join(bits) or "unknown state"))
        lines.append("       %s" % r["path"])
        for p in r["paths"]:
            lines.append("         " + p)
        if r["dirty"] and r["dirty"] > len(r["paths"]):
            lines.append("         ... and %d more" % (r["dirty"] - len(r["paths"])))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", help="repo paths this session dispatched work into")
    ap.add_argument("--known", action="store_true",
                    help="also check every project this plugin has recorded state for")
    ap.add_argument("--no-recorded", action="store_false", dest="recorded",
                    help="ignore the PostToolUse record and check only the paths named")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    targets: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        """Union, first-named-wins. Duplicates would double-report the same repo."""
        try:
            key = str(path.expanduser().resolve()).lower()
        except Exception:
            key = str(path).lower()
        if key not in seen:
            seen.add(key)
            targets.append(path)

    for p in args.paths:
        add(Path(p))
    n_named = len(targets)
    if args.recorded:
        for root in recorded_roots():
            add(root)
    n_recorded = len(targets) - n_named
    if args.known:
        for root in known_roots():
            add(root)

    if not targets:
        # B39/B67/B72: an empty record is NOT a clean bill of health. It is at least
        # THREE different things wearing one sentence -- no writes happened outside this
        # project; a write happened through a tool this recorder does not watch closely
        # enough (Bash/PowerShell writes it could not resolve to a path); or this
        # process itself resolved the WRONG project. That third case used to be silent
        # whenever `CLAUDE_PROJECT_DIR` was unset and the shell's cwd had drifted (B67,
        # reproduced 2026-09-05) -- `project_root()` fell straight to `cwd()`. B72
        # (v1.39.0) closed most of that gap with a session-scoped fallback (see
        # `reentry_state.project_root`), so the residual risk is narrower than before:
        # only when NEITHER this call NOR any earlier one this session ever saw
        # `CLAUDE_PROJECT_DIR` (e.g. a bare terminal run with no Claude Code session at
        # all, or the very first thing a session does). `project_root_source()` says
        # which case this actually is, so the warning below only fires where it is
        # still warranted instead of on every empty record regardless of confidence.
        root = project_root()
        source = project_root_source()
        print("No record -- this may mean no writes happened outside this project, or it "
              "may mean an unwatched tool wrote somewhere this check didn't see. It is NOT "
              "confirmation that nothing landed elsewhere.")
        print("Resolved project: %s" % root)
        if source == "cwd":
            print("Resolved from the shell's cwd (no CLAUDE_PROJECT_DIR, and this "
                  "session has no earlier stamp of its own project either) -- if that "
                  "path is not the repo you expect, this may be asking about the wrong "
                  "project; re-run from the session's own project root.")
        else:
            print("Resolved from %s -- this is trusted as the session's own project, "
                  "even though the shell's cwd may currently be elsewhere."
                  % ("CLAUDE_PROJECT_DIR" if source == "env"
                     else "this session's own earlier project (no CLAUDE_PROJECT_DIR "
                          "on this particular call, but stamped by an earlier one)"))
        print("If this session dispatched work through Bash/PowerShell to a path this "
              "heuristic could not find, or through a tool the recorder does not watch "
              "at all, name those paths, or pass --known.")
        return 0

    records = [inspect(p) for p in targets]
    if args.as_json:
        print(json.dumps(records, indent=2))
    else:
        bad = [r for r in records if not r["ok"]]
        header = ("%d repo(s) checked -- all clean and pushed" % len(records) if not bad
                  else "%d of %d repo(s) still have work that has not landed"
                       % (len(bad), len(records)))
        # Say where the targets came from. A recorded repo that was NOT named is the
        # whole point of the mechanism -- it is the 8th repo of 2026-08-25, and it must
        # be visible as such rather than blending into the list.
        if n_recorded:
            header += " (%d found by the recorder, not named)" % n_recorded
        print(header)
        print(render(records))
        if bad:
            # The whole point of the check: the entry must not claim what is not true.
            print("\nDo NOT write a CHANGELOG entry saying this work landed until "
                  "these are committed and pushed.")
    return 1 if any(not r["ok"] for r in records) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                                # pragma: no cover
        print("repo check could not run (%s) -- check the repos by hand" % exc)
        sys.exit(0)                                         # never break a wrap
