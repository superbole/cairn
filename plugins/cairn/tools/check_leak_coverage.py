#!/usr/bin/env python3
"""`test_payload_clean.py` can only catch the names someone remembered to type into it.

    python plugins/cairn/tools/check_leak_coverage.py           # this machine vs the patterns
    python plugins/cairn/tools/check_leak_coverage.py --json

THE INCIDENT (2026-09-07, B51 step 2)
--------------------------------------
`test_payload_clean.py` had reported `ALL PASS` for a version. Its `a private project` pattern
named six repos. The machine had six MORE that matched nothing at all -- hobby hardware, a
couple of personal web apps, a home-automation config, a trading bot -- and one whose spaced
display form evaded the hyphenated pattern that was supposed to cover it. Five were sitting in
the shipped payload at the time -- two `SKILL.md` session-title examples, `check_repos.py`'s
usage block and `repo_sweep.py`'s docstring -- while the checker printed a green tick over them.

The brief written for that cleanup named ONE of the six. So the miss was not carelessness at the
keyboard; it is what a hand-written list of literals IS. It covers the things its author happened
to recall on the day, and it reports success with exactly the same words either way.

WHY DERIVE INSTEAD OF REMEMBER
-------------------------------
This is `check_credentials.py`'s argument applied to leaks. There, a credential that WORKS
generates no error and so stays out of `CREDENTIALS.md` for as long as it keeps working; the fix
was to ask the keyring rather than trust anyone's memory of what they set up. Here, a private name
that is NOT in `BANNED` generates no failure and so stays out of the pattern list for as long as
nobody writes it into a docstring -- and the moment someone does, the checker waves it through.

So this asks the machine what private names actually exist, and reports two different things:

  LEAK      the name is in the payload or the public set RIGHT NOW, and `BANNED` does not catch
            it. This is a live disclosure bug. Exit 1.
  UNCOVERED the name is not in the files today, but nothing would stop it. The pattern list has a
            hole shaped like this name. Exit 0 -- it is a gap, not a bug.

HARD RULE -- READS AND PRINTS, NEVER WRITES
--------------------------------------------
It never edits `BANNED`, and that is deliberate rather than unfinished. Auto-appending every
sibling directory name would put this machine's private project list into a file that ships to
other people's machines -- the precise thing the checker exists to prevent, arrived at from the
other direction. The output is for a terminal. A human decides which candidates are real and
writes the pattern, in the same way `check_credentials.py` prints target names and lets someone
decide which belong in the file.

It also names nothing itself. Every candidate below is derived at runtime from this machine, so
this file is safe to ship and says nothing about whoever runs it.

WHAT IT CANNOT SEE
-------------------
Projects that are not siblings of this one -- a WSL tree, an SSH box, a second `Projects` root
(that is B59). A machine that has never had `MACHINES.md` filled in contributes no ids. A name
that exists only in someone's head contributes nothing at all. So `no gaps` here means "nothing
this machine can see is uncovered", never "the pattern list is complete" -- the same honest
limit `check_credentials.py` states about a keyring it can only read one of.

It does not look INSIDE this project for a private store, either. That is B115's mirror image and
is a PRESENCE question (`is a private file sitting here?`) rather than a coverage one, so it needs
its own check and its own vocabulary -- `LEAK`/`UNCOVERED` do not fit it.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_payload_clean as checker  # noqa: E402  (the patterns are the point of the import)

# This tool and the checker both contain every banned term -- they are their patterns.
SKIP_FILES = {"test_payload_clean.py", "check_leak_coverage.py"}

# `ensure_profile_file.py`'s own constant, restated rather than imported: that file is a hook and
# importing it would run its module-level work. A drift here costs one derivation, not a failure.
PROFILE_SOURCE_ENV = "REENTRY_PROFILE_SOURCE"

# A candidate shorter than this is noise: two-letter directory names collide with ordinary prose
# and would bury the real findings. Stated as a constant because it is a judgement, not a fact.
MIN_CANDIDATE = 4

# Column headings from `MACHINES.md`'s own table, and the git hosts everyone shares. Neither
# identifies anyone, and both flooded the first run -- `github` alone matched 161 lines. A
# self-hosted forge is NOT here on purpose: its hostname is often the most employer-identifying
# string on the machine: a self-hosted forge's hostname is what found the employer here.
NOT_IDENTIFYING = {
    "hostname", "host", "machine", "name", "id", "role", "notes", "short", "example",
    "github", "github.com", "gitlab", "gitlab.com", "bitbucket", "bitbucket.org",
    "codeberg", "codeberg.org", "sourcehut", "git.sr.ht",
}


def _run(*args, cwd=None):
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=10, cwd=cwd,
                             encoding="utf-8", errors="replace")
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _config_dir() -> Path:
    return Path.home() / ".claude"


def sibling_names(root: Path) -> set[str]:
    """Directory names beside this project that are git repos.

    Deliberately NOT `repo_sweep.sibling_repos()`, which gates on `NEXT.md` because it goes on to
    run `git` inside each one. Nothing is executed here -- only the directory NAME is read -- and
    the names that leaked in the incident above were mostly repos with no `NEXT.md`. Gating on it
    would have hidden exactly the ones that mattered.
    """
    names = set()
    try:
        for p in sorted(root.parent.iterdir()):
            if p.is_dir() and (p / ".git").exists() and p.name != root.name:
                names.add(p.name)
    except Exception:
        pass
    return names


def self_published_names(root: Path) -> set[str]:
    """The names this plugin publishes ABOUT ITSELF — its own name, and whoever it ships under.

    Derived rather than listed because it is the difference between a check that works on a fresh
    clone and one that fails on it. `private_store_names()` reads the store's path and remote, and
    on the machine that develops this plugin the store sits beside the plugin's own name and under
    the same git owner — so a plain derivation reports the plugin's name and marketplace owner as
    live LEAKs, in a couple of hundred payload lines, on the first run after install. A fork does
    the same with its own name.

    A name the plugin PUBLISHES cannot be a private name, so it is subtracted here instead of
    needing an `ok:` line on every machine. The subtraction is counted in the output rather than
    applied silently — a partial check that reads like a complete one is the failure this whole
    family of tools exists to prevent.
    """
    names = set()
    for rel in (Path(".claude-plugin") / "marketplace.json",
                Path("plugins") / "cairn" / ".claude-plugin" / "plugin.json"):
        try:
            data = json.loads((root / rel).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for key in ("name", "owner", "author"):
            val = data.get(key)
            if isinstance(val, str):
                names.add(val)
            elif isinstance(val, dict) and isinstance(val.get("name"), str):
                names.add(val["name"])
        for entry in data.get("plugins", []):
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                names.add(entry["name"])
    return {n.strip() for n in names if n.strip()}


def private_store_names() -> set[str]:
    """Names from the private config store — the one directory the design guarantees is OUTSIDE
    `~/Projects`, and therefore a sibling of nothing (B115).

    `ensure_profile_file.py:89` recommends `~/.claude-private/<your-repo>/profile.md`, and making
    that placeholder concrete is the single most natural edit an agent makes. So the store's own
    repo name is among the likeliest private names to reach a docstring — and until this ran it
    could never be reported UNCOVERED no matter how long the tool ran.

    The store's remote OWNER is derived as well as its repo name. `remote_hosts()` keeps only
    hostnames, so an owner is not reachable today, and `<owner>/<private-store>` is as identifying
    as the repo half.
    """
    home = Path.home()
    stores: set[Path] = set()

    for env in (checker.PRIVATE_NAMES_ENV, PROFILE_SOURCE_ENV):
        raw = os.environ.get(env, "").strip()
        if raw:
            stores.add(Path(os.path.expanduser(raw)).parent)

    # Both env vars unset is the ordinary case on a fresh machine, and the payload still names
    # this directory generically — so a store can exist there with nothing pointing at it.
    default = home / ".claude-private"
    if default.is_dir():
        try:
            stores.update(p for p in default.iterdir() if p.is_dir())
        except Exception:
            pass

    names = set()
    for store in stores:
        try:
            rel = store.resolve().relative_to(home.resolve())
        except Exception:
            continue          # a store outside home tells us nothing about whose it is
        # `.claude-private/cairn` -> `claude-private`, `cairn`: a leading dot is a filesystem
        # convention, not part of the name anyone would type into a docstring.
        names.update(part.lstrip(".") for part in rel.parts)
        for line in _run("git", "-C", str(store), "remote", "-v").splitlines():
            m = re.search(r"[:/]([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?(?:\s|$)", line)
            if m:
                names.update(m.groups())
    return {n for n in names if n}


def machine_names() -> set[str]:
    """This host, plus every hostname and short id in `~/.claude/MACHINES.md`."""
    names = {_run("hostname")}
    try:
        text = (_config_dir() / "MACHINES.md").read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {n for n in names if n}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().strip("`*") for c in line.strip().strip("|").split("|")]
        for c in cells:
            # skip the header rule and the template's own placeholder rows
            if c and not set(c) <= set("-: ") and not c.startswith("<"):
                names.add(c)
    return {n for n in names if n}


def identity_names(root: Path) -> set[str]:
    """The person and the employer, from git's own config rather than from a profile file."""
    names = set()
    for word in _run("git", "-C", str(root), "config", "user.name").split():
        names.add(word)
    email = _run("git", "-C", str(root), "config", "user.email")
    if "@" in email:
        local, _, domain = email.partition("@")
        names.add(local)
        # `sub.employer.co.uk` -> `employer`: the registrable label, not the public suffix
        parts = [p for p in domain.split(".") if p not in {"co", "com", "org", "net", "za", "uk"}]
        names.update(parts)
    return names


def remote_hosts(root: Path) -> set[str]:
    """Git remote hostnames across this repo and its siblings -- a self-hosted forge names an
    employer even when nothing else does, and was found exactly this way here."""
    hosts = set()
    roots = [root] + [p for p in root.parent.iterdir() if p.is_dir() and (p / ".git").exists()]
    for repo in roots:
        for line in _run("git", "-C", str(repo), "remote", "-v").splitlines():
            m = re.search(r"(?:@|//)([A-Za-z0-9.\-]+?)(?::|/)", line)
            if m and "." in m.group(1):
                host = m.group(1)
                hosts.add(host)
                label = host.split(".")[0]
                if len(label) >= MIN_CANDIDATE:
                    hosts.add(label)
    return hosts


def candidates(root: Path) -> tuple[dict[str, str], set[str]]:
    """(name -> where it came from, the self-published names subtracted from it)."""
    found = {}
    for name in sibling_names(root):
        found.setdefault(name, "a sibling repo directory")
    for name in private_store_names():
        found.setdefault(name, "the private config store's path or remote")
    for name in machine_names():
        found.setdefault(name, "MACHINES.md or this hostname")
    for name in identity_names(root):
        found.setdefault(name, "git config user.name / user.email")
    for name in remote_hosts(root):
        found.setdefault(name, "a git remote hostname")
    published = {n.lower() for n in self_published_names(root)}
    kept = {n: src for n, src in found.items()
            if len(n) >= MIN_CANDIDATE and n.lower() not in NOT_IDENTIFYING
            and n.lower() not in published}
    subtracted = {n for n in found if n.lower() in published}
    return kept, subtracted


def covered_by(name: str) -> str | None:
    """The label of the first BANNED pattern that would catch `name`, or None."""
    for label, pattern in checker.BANNED:
        if re.search(pattern, name, flags=re.I):
            return label
    return None


def scanned_files(root: Path):
    """Everything the checker actually scans: the payload plus D1's public set."""
    plugin_root = root / "plugins" / "cairn"
    checker.ROOT = plugin_root
    for p in checker.tracked_files():
        if p.is_file() and p.name not in SKIP_FILES:
            yield p
    for rel in checker.PUBLIC_SET:
        p = root / rel
        if p.is_file():
            yield p


def occurrences(root: Path, names) -> dict[str, list[str]]:
    """name -> ['path:line', ...] for every name that is actually present in a scanned file."""
    pats = {n: re.compile(re.escape(n), re.I) for n in names}
    hits: dict[str, list[str]] = {}
    for path in scanned_files(root):
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        stripped = checker._strip_allowed(raw)
        for name, pat in pats.items():
            if not pat.search(stripped):
                continue
            for i, line in enumerate(stripped.split("\n"), 1):
                if pat.search(line):
                    hits.setdefault(name, []).append(f"{path.relative_to(root)}:{i}")
    return hits


def main(argv):
    root = Path(__file__).resolve().parent.parent.parent.parent
    if not (root / ".claude-plugin" / "marketplace.json").is_file():
        print("Not a checkout of this plugin's repo — nothing to check.")
        return 0

    found, published = candidates(root)
    uncovered = {n: src for n, src in found.items()
                 if covered_by(n) is None and n.lower() not in checker.ACCEPTED}
    leaks = occurrences(root, uncovered) if uncovered else {}

    if "--json" in argv:
        print(json.dumps({
            "candidates": found,
            "self_published": sorted(published),
            "uncovered": uncovered,
            "leaks": {k: v[:20] for k, v in leaks.items()},
        }, indent=2, sort_keys=True))
        return 1 if leaks else 0

    print(f"{len(found)} name(s) this machine can see; "
          f"{len(found) - len(uncovered)} already banned or judged not identifying.")
    if published:
        print(f"{len(published)} subtracted as this plugin's own published identity: "
              f"{', '.join(sorted(published))}")
    print()

    if leaks:
        print("LEAK — in a scanned file NOW, and no pattern catches it:")
        for name in sorted(leaks):
            print(f"  {name}   ({found[name]})")
            for where in leaks[name][:8]:
                print(f"      {where}")
            if len(leaks[name]) > 8:
                print(f"      … and {len(leaks[name]) - 8} more")
        print()

    gaps = sorted(n for n in uncovered if n not in leaks)
    if gaps:
        print("UNCOVERED — not in the files today, but nothing would stop it:")
        for name in gaps:
            print(f"  {name}   ({uncovered[name]})")
        print()
        print("Not every one of these is worth a pattern — a generic directory name may be fine.")
        print(f"In {checker._private_names_path()[0]}:")
        print("  a pattern line  -> it identifies someone, ban it")
        print("  `ok: <name>`    -> judged harmless; say why in a comment beside it")
        print()

    if leaks:
        print("FAILED: a private name is in a file that ships, and the checker cannot see it.")
        return 1
    if not gaps:
        print("No gaps: every name this machine can see is already covered.")
        print("That is not 'the list is complete' — see WHAT IT CANNOT SEE in this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
