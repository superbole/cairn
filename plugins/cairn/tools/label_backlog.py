#!/usr/bin/env python3
"""The backlog's four labels — create them idempotently, and name what is unjudged.

Works on GitHub and GitLab alike since v1.34.0 (issue #11): every host call goes through
`hooks/issue_host.py`, and the label set, its colours and its descriptions are defined there
so the two backends cannot drift apart. `glab` wants a `#` on the hex and `gh` does not; that
is the backend's problem, not this file's.

WHY THIS IS A TOOL AND NOT A SENTENCE IN `wrap/SKILL.md`
-------------------------------------------------------
The wrap already said "create them once per repo", parenthetically, in the middle of a step
about something else. That is a step an agent runs once per REPO and therefore almost never —
the classic shape of an instruction that is silently skipped, and the failure is invisible when
it happens: filing an issue with `--label afk` in a repo without the label does not fall back
to an unlabelled issue, it FAILS, mid-wrap, at the moment the user has already stopped paying
attention.

So the labelling half is mechanical and belongs in code: four labels, created if absent,
"already exists" swallowed, exit 0 whatever happens. The JUDGEMENT half — is this issue
`afk` or `hitl`? — cannot be automated and is not attempted here. This tool names the
issues that have no attendance label and stops; the wrap reads them and decides.

WHY THE LABELS ARE CREATED EAGERLY, IN EVERY REPO
-------------------------------------------------
Measured 2026-08-28: of the ten opted-in projects, only `agent-reentry` had any open
issues at all. So there was nothing to label anywhere else — and that is exactly the
condition under which this gets forgotten, because the first issue in each of those repos
will be filed by a wrap that is already busy, on a day they are already stopping. Creating
the labels while there is nothing at stake costs one call per repo and removes a failure
mode from every future wrap.

ATTENDANCE IS THE ONLY THING THAT BECOMES A LABEL
-------------------------------------------------
`afk` / `hitl`, not the mode. A label is the only part of an issue that a `--label afk`
listing can filter on, and the mode is not needed until the item is pulled into the Queue —
where it is written in full on the `NEXT.md` line. Putting the mode in a label as well would
be five more labels to keep consistent with a body that already says it.

FLAGS GO THROUGH `argparse` FOR THE SAME REASON AS `sync_backlog.py`
--------------------------------------------------------------------
Both read `sys.argv` by hand, and both write outward (label creation here). An
unrecognised flag used to fall through to the default run rather than stopping, so
`--help` did whatever the tool does by default instead of printing usage. Fixed
2026-08-30 (issue #18): `--help` exits 0, an unknown flag exits 2, and `--dry-run`
names the labels it WOULD create without creating one.

Usage:
    python label_backlog.py --help                       # usage, no host call
    python label_backlog.py --ensure [-R owner/repo]     # create the four labels
    python label_backlog.py --ensure --dry-run           # say what is missing, create nothing
    python label_backlog.py [-R owner/repo]              # report unjudged open issues
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

try:
    import issue_host
    from issue_host import LABELS
    from reentry_state import project_root
except Exception as exc:                 # pragma: no cover — a wrap must never fail here
    print(f"label check skipped: cannot import the plugin's own modules ({exc})")
    sys.exit(0)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ATTENDANCE = ("afk", "hitl")


def _host(repo: str = ""):
    root = project_root() if project_root else Path.cwd()
    return issue_host.detect(root, repo)


def ensure(host, repo: str = "", dry: bool = False) -> str:
    """Create any missing label. Returns ONE line, always; never raises."""
    have, err = host.list_labels()
    if have is None:
        return f"labels not checked ({err})"

    where = f" on {repo}" if repo else ""
    if dry:
        missing = [n for n in LABELS if n not in have]
        return (f"labels{where}: would create {', '.join(missing)}" if missing
                else f"labels{where}: all four already present")

    created, failed = [], []
    for name, (colour, desc) in LABELS.items():
        if name in have:
            continue
        ok, e = host.create_label(name, colour, desc)
        # A racing wrap in another session may have just created it; that is a success.
        # `glab` says "already exists", `gh` says "already exists" too — but each wraps it
        # differently, so match on the phrase rather than on an exit code.
        if not ok and "already exists" not in (e or "").lower():
            failed.append(f"{name} ({e})")
        else:
            created.append(name)

    if failed:
        return f"labels{where}: created {', '.join(created) or 'none'}; FAILED {'; '.join(failed)}"
    if created:
        return f"labels{where}: created {', '.join(created)}"
    return f"labels{where}: all four already present"


def unjudged(host) -> tuple[list[dict], str, int]:
    """Open issues carrying neither `afk` nor `hitl`. These need a HUMAN-ish judgement."""
    raw, err = host.list_issues()
    if raw is None:
        return [], err, 0
    missing = []
    for i in raw:
        names = {str(l).lower() for l in (i.get("labels") or [])}
        if not names & set(ATTENDANCE):
            missing.append({"number": i.get("number"), "title": i.get("title") or ""})
    return missing, "", len(raw)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse first. `SystemExit` from here is a `BaseException`, so it escapes the
    `except Exception` below that keeps a wrap alive — a usage error must not become
    a silent exit 0."""
    p = argparse.ArgumentParser(
        prog="label_backlog.py",
        description="Create the backlog's four labels on the project's issue host (GitHub "
                    "via `gh`, GitLab via `glab`), and name the issues nobody has judged "
                    "AFK or HITL yet.",
        epilog="With no flags it only reports; --ensure is the half that writes.")
    p.add_argument("--ensure", action="store_true",
                   help="create any of the four labels that this repo is missing")
    p.add_argument("--repo", "-R", default="", metavar="OWNER/REPO",
                   help="act on this repo instead of the checkout in the cwd (the BACKEND "
                        "still comes from the checkout's own remote)")
    p.add_argument("--dry-run", action="store_true",
                   help="with --ensure, name the labels it would create and create none")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    repo = args.repo
    host, err = _host(repo)
    if host is None:
        # Same distinction as sync_backlog.py: a missing CLI is worth retrying, an
        # unsupported remote never will be. Say which, rather than a bare skip.
        tail = ("nothing will label it until that changes" if issue_host.is_permanent(err)
                else "worth another try where the CLI works")
        print(f"labels not checked ({err}) — {tail}")
        return
    if args.ensure:
        print(ensure(host, repo, args.dry_run))
    missing, err, total = unjudged(host)
    indent = "  └ " if args.ensure else ""
    if err:
        print(f"{indent}unjudged issues not checked ({err})")
        return
    if not missing:
        # "every open issue is judged" is TRUE and misleading when there are none — the
        # reader is deciding whether the backlog is in order, and an empty backlog is a
        # different answer from a fully judged one. Say which.
        print(f"{indent}no open issues" if not total
              else f"{indent}all {total} open issue(s) carry afk or hitl")
        return
    noun = "issue needs" if len(missing) == 1 else "issues need"
    print(f"{indent}{len(missing)} open {noun} an afk/hitl judgement:")
    for i in missing:
        print(f"  #{i['number']} {i['title'][:70]}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:             # a wrap must never fail over the backlog
        print(f"label check skipped: {type(exc).__name__}")
    sys.exit(0)
