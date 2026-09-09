#!/usr/bin/env python3
"""A credential that WORKS is invisible to `CREDENTIALS.md` forever, unless something checks.

    python plugins/cairn/tools/check_credentials.py            # this machine's keyring vs the file
    python plugins/cairn/tools/check_credentials.py --all       # also list the non-dev targets
    python plugins/cairn/tools/check_credentials.py --json

THE INCIDENT (B48, filed 2026-08-31)
-------------------------------------
`~/.claude/CREDENTIALS.md` tracked three GitLab tokens in detail -- name, machine, storage,
scopes, expiry -- and said nothing at all about `github.com`, even though this machine has a
working GitHub credential in Git Credential Manager that every `git push` to a personal repo
already uses. Nobody had forgotten to write the row; nothing had ever asked the question. A
credential that authenticates successfully generates no error, no prompt, and no reason for
anyone to go looking -- so it stays invisible to the one file whose entire job is "what exists,
where, and when does it expire" for exactly as long as it keeps working. A leak is precisely the
moment that file needs to be complete, and precisely the moment nobody has been adding to it.

WHY A TOOL AND NOT A REMINDER TO CHECK
-----------------------------------------
"Remember to update `CREDENTIALS.md` when you set up a new credential" only catches credentials
created THROUGH a session that reads this rule. `git:https://github.com`'s entry in Windows
Credential Manager almost certainly predates this plugin, this file, and the habit -- nothing
"forgot" to log it, because nothing involved in creating it had ever heard of the file. The fix
has to be able to answer for a credential this session never touched, which means asking the
keyring directly rather than trusting anyone's memory of what they set up and when.

HARD RULE 1 -- NAMES ONLY, NEVER A VALUE
-------------------------------------------
`cmdkey /list` prints target names and (for some entries) a `User:` line; it NEVER prints a
password, and this file only ever reads the `Target:` lines out of its output -- every other line
(`User:`, `Type:`, `Persist:`) is skipped without being stored, logged, or inspected, so there is
no path here by which a credential VALUE could reach this tool's output, this repo, or a chat
transcript. Two entries in `~/.claude/MISTAKES.md` (2026-09-01, both this same day) are exactly
this failure from the other direction -- `grep -n` and `git log -p -S | grep` on a secret-shaped
file, where a flag richer than the question needed let a live PAT and a live password print into
a session transcript. The narrowest flag that answers the question is the rule there; the
analogous rule here is even simpler, because `cmdkey` never emits the value at all -- so the only
way to violate this rule would be to add a DIFFERENT backend later that reads more than a target
name (some `secret-tool`/keyring calls can return a stored secret if asked). Any such addition
must keep to enumeration only.

HARD RULE 2 -- REPORT, NEVER WRITE A ROW
-------------------------------------------
This tool never touches `CREDENTIALS.md`. Expiry and token type cannot be read off a keyring
target name -- `cmdkey /list`'s target strings are things like `git:https://github.com` or
`gh:github.com:example-user`, which say what the credential is FOR, never when it expires or what
kind it is -- so an auto-written row would have to invent those two fields, and an invented
expiry is worse than a missing one: the whole point of the file is that a rotation is a checklist
read off it, not a memory test, and a checklist item with a made-up date fails silently exactly
when it matters. Report the gap; a human fills in the row from what they actually know.

WHAT COUNTS AS "MENTIONED"
-----------------------------
A target is treated as mentioned when its exact string (case-insensitive) appears anywhere in
`CREDENTIALS.md` -- true today for `git:https://github.com` and
`glab:git2.example-corp.net:token:` (both are quoted verbatim in the file). Where the exact string
is absent but the HOST portion appears elsewhere (e.g. `github.com` is discussed at length, but
the literal target string `gh:github.com` never appears), that is reported as a SOFTER note, not
a clean pass and not a hard gap -- the file may well be covering this credential in prose without
ever writing its keyring name down verbatim, and only a human can tell the difference.

WHY "DEV-RELEVANT" TARGETS ARE SEPARATED FROM THE REST
---------------------------------------------------------
`cmdkey /list` on a real machine returns everything Windows has ever been asked to remember --
OneDrive, a browser's sync token, a fitness tracker, a 3D-printer account, remote-desktop
credentials -- alongside the two or three that `CREDENTIALS.md` actually exists to track (git,
`gh`, `glab`, anything token/PAT/API-shaped). Reporting all of them as undifferentiated gaps would
bury the two or three the file's own scope covers under a dozen consumer-app entries it was never
meant to include, which is the opposite of the "answer off a record" goal -- so the default view
leads with the dev-shaped ones and gives everything else a single count, with `--all` available
to see the rest named.

NEVER RAISES for the same reason as `check_repos.py`: an unreadable file or an unsupported
platform is reported as a gap in what could be checked, never a crash.

USAGE
    python check_credentials.py
    python check_credentials.py --credentials-file PATH
    python check_credentials.py --all
    python check_credentials.py --json

EXIT
    0  every dev-relevant target this machine holds is at least mentioned in the file
    1  at least one dev-relevant target is not mentioned at all, or the file/listing could not
       be read
    2  bad command line
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

NO_WINDOW: dict = {"creationflags": 0x08000000} if os.name == "nt" else {}

_TARGET_RE = re.compile(r"^\s*Target:\s*(.+?)\s*$")

# Prefixes `cmdkey` puts in front of the actual target string. Stripped for comparison against
# `CREDENTIALS.md` -- the file names credentials like `git:https://github.com`, never with the
# `LegacyGeneric:target=` wrapper `cmdkey` adds, so comparing the raw string would never match
# even a file that names every credential it holds.
_PREFIXES = ("LegacyGeneric:target=", "Domain:target=", "MicrosoftAccount:target=",
            "WindowsLive:target=")

# A target is worth `CREDENTIALS.md`'s attention when its name suggests git/host-auth/API
# tooling. Matched against the RAW target string (before prefix-stripping catches nothing extra),
# case-insensitive substring -- this is a triage heuristic, not a security boundary, so it errs
# toward including anything plausibly relevant rather than toward a tight allowlist that quietly
# drops something real.
_DEV_KEYWORDS = ("git", "gh:", "glab", "ssh", "token", "pat", "api", "github", "gitlab")


def _strip_prefix(raw: str) -> str:
    for p in _PREFIXES:
        if raw.startswith(p):
            return raw[len(p):]
    return raw


def _host_of(target: str) -> str:
    """A weaker key than the full target -- for the 'mentioned elsewhere, not verbatim' note.

    `git:https://github.com` -> `github.com`; `gh:github.com:example-user` -> `github.com`. Best
    effort: anything that doesn't look like `scheme:` or `word:host...` is returned as-is, which
    just means the softer check degrades to the same as the exact check for that entry.
    """
    t = target
    for sep in ("://", ":"):
        if sep in t:
            t = t.split(sep, 1)[1]
            break
    t = t.split("/", 1)[0]
    return t.split(":", 1)[0] or target


def is_dev_relevant(raw_target: str) -> bool:
    low = raw_target.lower()
    return any(k in low for k in _DEV_KEYWORDS)


def _run_cmdkey() -> tuple[str | None, str | None]:
    """(stdout, error). Never raises -- an unavailable `cmdkey` is a reported gap, not a crash."""
    try:
        proc = subprocess.run(("cmdkey", "/list"), capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=10, **NO_WINDOW)
    except Exception as exc:
        return None, f"could not run cmdkey ({exc})"
    if proc.returncode != 0:
        return None, f"cmdkey exited {proc.returncode}"
    return proc.stdout, None


def list_targets(runner=_run_cmdkey) -> tuple[list[str] | None, str | None]:
    """(raw target strings held by this machine, error note). Platform-dispatched.

    Reads ONLY lines beginning `Target:` out of whatever the backend prints -- every other line
    (a `User:`, a `Type:`, a `Persist:`) is discarded unread by this function, never stored in the
    returned list, never printed. See the module docstring, HARD RULE 1.
    """
    if sys.platform == "win32":
        out, err = runner()
        if out is None:
            return None, err
        return [m.group(1) for ln in out.splitlines() if (m := _TARGET_RE.match(ln))], None
    return None, (f"no listing implemented for {sys.platform} yet -- run `secret-tool search "
                  "--all` (GNOME keyring) or your platform's equivalent by hand")


def _credentials_path(override: str | None) -> Path:
    if override:
        return Path(override).expanduser()
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    return Path(base) / "CREDENTIALS.md"


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def classify(target: str, text_lower: str) -> str:
    """'mentioned' | 'soft' | 'gap', for one raw target string against the file's lowercased text."""
    key = _strip_prefix(target)
    if key.lower() in text_lower:
        return "mentioned"
    host = _host_of(key)
    if host and len(host) > 3 and host.lower() in text_lower:
        return "soft"
    return "gap"


def report(targets: list[str], text: str | None, show_all: bool) -> list[str]:
    lines: list[str] = []
    text_lower = (text or "").lower()

    dev = [t for t in targets if is_dev_relevant(t)]
    other = [t for t in targets if not is_dev_relevant(t)]

    if text is None:
        lines.append("No CREDENTIALS.md readable -- every dev-relevant target below is "
                     "unmentioned by definition.")

    gaps, soft, ok = [], [], []
    for t in dev:
        state = classify(t, text_lower) if text is not None else "gap"
        (gaps if state == "gap" else soft if state == "soft" else ok).append(t)

    lines.append(f"{len(dev)} dev-relevant target(s) held by this machine "
                f"({len(ok)} mentioned, {len(soft)} soft match, {len(gaps)} not mentioned at all)")
    for t in gaps:
        lines.append(f"  [!!] not mentioned in CREDENTIALS.md: {_strip_prefix(t)}")
    for t in soft:
        lines.append(f"  [? ] host mentioned, but not this exact target: {_strip_prefix(t)}"
                     " -- confirm CREDENTIALS.md really covers it")

    if other:
        if show_all:
            lines.append(f"\n{len(other)} other target(s) held (not dev-tooling-shaped by name; "
                         "CREDENTIALS.md's scope may not cover these at all):")
            for t in other:
                lines.append(f"       {_strip_prefix(t)}")
        else:
            lines.append(f"\n{len(other)} other target(s) held, not dev-tooling-shaped by name "
                         "(--all lists them; CREDENTIALS.md's scope may not cover these at all).")

    if gaps:
        lines.append("\nReport only -- this tool never writes to CREDENTIALS.md. A human adds "
                     "the row: name, machine, storage, scopes, expiry. Never invent an expiry.")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_credentials.py", description=__doc__.splitlines()[0])
    ap.add_argument("--credentials-file", default=None,
                    help="path to CREDENTIALS.md (default: $CLAUDE_CONFIG_DIR or ~/.claude)")
    ap.add_argument("--all", action="store_true", dest="show_all",
                    help="also list non-dev-shaped targets by name, not just a count")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    targets, err = list_targets()
    cred_path = _credentials_path(args.credentials_file)
    text = _read_text(cred_path)

    if targets is None:
        msg = f"could not list held credentials: {err}"
        if args.as_json:
            print(json.dumps({"ok": False, "error": msg}, indent=2))
        else:
            print(msg)
        return 1

    lines = report(targets, text, args.show_all)
    dev_gaps = sum(1 for ln in lines if ln.startswith("  [!!]"))
    ok = dev_gaps == 0

    if args.as_json:
        dev = [t for t in targets if is_dev_relevant(t)]
        text_lower = (text or "").lower()
        print(json.dumps({
            "ok": ok,
            "credentials_file": str(cred_path),
            "credentials_file_readable": text is not None,
            "dev_relevant": [{"target": _strip_prefix(t),
                             "state": classify(t, text_lower) if text is not None else "gap"}
                            for t in dev],
            "other_count": sum(1 for t in targets if not is_dev_relevant(t)),
        }, indent=2))
    else:
        print(f"CREDENTIALS.md: {cred_path}" + ("" if text is not None else " (not readable)"))
        print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:                                # pragma: no cover
        print(f"credential check could not run ({exc}) -- check CREDENTIALS.md by hand")
        sys.exit(0)                                          # a report tool must never break
