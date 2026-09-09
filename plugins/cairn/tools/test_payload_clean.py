"""The shipped payload names no particular person, machine, employer or private project (B12).

    python plugins/cairn/tools/test_payload_clean.py

WHY THIS EXISTS. `install_rules.py` writes `rules/CLAUDE.md` verbatim into every installer's
`~/.claude/CLAUDE.md`, and the skills, hooks and tools beside it install with it. Until v1.45.0
all of that was written about one named person: their medical history, their machines, their
employer's git host, their private projects as the only worked examples. B12 separated the
MECHANISM (ships) from the IDENTITY and PREFERENCE (which now live in
`~/.claude/reentry-profile.md`, per user, per machine).

THE POINT OF THIS FILE IS THAT THE SEPARATION DOES NOT DECAY. Every docstring in this plugin was
written in the personal register, because that is how the whole codebase read at the time; the
next one will be too unless something says no. A rule in a `SKILL.md` is exactly the intervention
this project has recorded failing twice (`docs/decisions.md` D4) — so this is a check, not a rule.

WHAT IT DOES NOT CHECK, deliberately:

  - PRONOUNS. ~575 `he`/`him`/`his` occurrences were rewritten for B12, but a bare pronoun is not
    mechanically distinguishable from correct prose ("the user ... they", "the agent ... its"),
    and a check that cries wolf gets switched off. Register is a review concern, not a grep.
  - The GITHUB HANDLE, in the two places it cannot leave: the install URL and the marketplace
    owner's noreply address. D14 kept it and renamed the slug instead — the slug was the string a
    stranger types. Both are allowlisted below as exact literals, so a bare `superbole` in prose
    still fails.
  - The word FORGE. It named a private project AND is the ordinary technical term for the thing on
    the other end of a git remote — `issue_host.py` exists because those two collided (B19), and
    its docstring has to be able to say so. Banning it would fail the file that records the fix.
  - The private repo's OWN working files. `NEXT.md`, `BACKLOG.md`, `CHANGELOG.md`, `briefs/` and
    the `docs/` files that stay private are the historical record and are not scanned. They name
    work servers, client projects and the employer host, and they are meant to.

WHAT IT ALSO CHECKS, since B51. D1 sends a SECOND, named set public alongside the payload:
`README.md`, `.claude-plugin/marketplace.json` and five `docs/` files. Those are scanned with the
same patterns. The set is listed LITERALLY, never globbed — a new file dropped into `docs/` is
private until someone adds it here on purpose, which is the safe default for a directory that
holds both.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()

# The repo root, when this is run from inside a checkout. `ROOT` is `plugins/cairn`, so its
# grandparent is the repo — confirmed by the marketplace manifest rather than assumed from depth,
# because `ROOT` can be pointed anywhere by argv.
REPO = ROOT.parent.parent
if not (REPO / ".claude-plugin" / "marketplace.json").is_file():
    REPO = None

# D1's public set: what a fresh `git init` copies into `superbole/cairn` alongside the payload.
# Listed literally, never globbed — see the docstring. Anything not on this list stays private.
PUBLIC_SET = [
    "README.md",
    "LICENSE",
    ".claude-plugin/marketplace.json",
    "docs/guide.md",
    "docs/design-notes.md",
    "docs/file-formats.md",
    "docs/running-a-batch.md",
    "docs/decisions.md",
]

# Literals that are deliberately still in the payload. Stripped before scanning, so the terms
# inside them (an install URL contains the handle) do not fire. Each one needs a reason.
ALLOWED = [
    # The GitHub handle. It is in every install URL and the marketplace owner's noreply address, so
    # it cannot leave; D14 kept it deliberately and dropped the given name instead. Allowlisted as
    # the two exact literals rather than as the bare word, so `superbole` in prose still fails.
    ("10409989+superbole@users.noreply.github.com",
     "marketplace.json's owner — a GitHub noreply address is designed to be public"),
    ('"name": "superbole"',
     "the author field in plugin.json and marketplace.json — the handle, not the given name"),
    ("Copyright (c) 2026 superbole",
     "LICENSE's copyright holder — a licence with no named holder grants nothing"),
]

# ---------------------------------------------------------------------------------------------
# THE PATTERNS ARE IN TWO HALVES, AND THE SPLIT IS THE WHOLE POINT.
#
# Until 2026-09-07 they were one list, in this file, in the shipped payload. That list named a
# person, their medical history, their employer, four machines, twelve private repos and four
# devices -- and this file excludes ITSELF from the scan, so it was the one file guaranteed never
# to be checked. Publishing the plugin would have published the most concentrated disclosure in
# the repo, from inside the file whose entire job is preventing disclosure. Worse: closing a gap
# in the list meant ADDING more real names to a file that ships. The fix and the leak were the
# same edit.
#
# So: GENERIC ships and names nobody. Specific names live on the machine that owns them, in
# `~/.claude/reentry-private-names.txt`, which is never committed anywhere.
# ---------------------------------------------------------------------------------------------

# Useful to ANY installer, and identifying of no one. A category, never an instance.
# A literal backslash, built rather than typed. Three separate attempts to write this pattern as
# a string literal on 2026-09-07 were each mangled in transit -- the same class of corruption as
# B96 in the README, which was also an escape interpreted at authoring time. Do not "simplify"
# this back into r"[/\]".
_BS = chr(92)
_SEP = "[/" + _BS + _BS + "]"

# Applied ONLY to the generic patterns below, never to the private ones. A generic pattern
# describes a SHAPE, so it cannot tell a real home path from a documented example -- and this
# codebase is full of deliberate ones (`\Users\Example\`, `t@t.com`, `git@github.com`, which is
# an SSH URL and not an address at all). The first run of these three patterns produced 24
# findings and 24 of them were fixtures. A check that cries wolf gets switched off, so the
# exemption is part of the pattern, not a workaround.
#
# A PRIVATE name is an exact string its owner chose and is never exempted here: if someone's
# real project is called `test-harness`, it must still fail.
GENERIC_PLACEHOLDER = (
    r"\bexamples?\b|\bplaceholder\b|\bsample\b|\byour[-_.]?\w*\b"
    r"|\bfoo\b|\bbar\b|\bdummy\b|\blocalhost\b|\binvalid\b"
    r"|^git@|@t\.com$|@[a-z]\.[a-z]{2,3}$"
)

GENERIC = [
    # NOT `diagnos(is|ed)`: this project's own vocabulary is "the stronger model for diagnosis",
    # and it matched six times in SKILL.md, incidents.md, the guide and decisions.md on the first
    # run. Ordinary technical English is not a health disclosure.
    ("medical or health information",
     r"\bADHD\b|concussion|\bmemory loss\b"),
    ("a home directory path",
     _SEP + r"(?:home|Users)" + _SEP + r"[A-Za-z0-9_.-]+" + _SEP),
    ("an email address",
     r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]

PRIVATE_NAMES_FILE = "reentry-private-names.txt"
PRIVATE_NAMES_ENV = "REENTRY_PRIVATE_NAMES"


def _private_names_path():
    """Where this machine's own names live. `~/.claude/` by default.

    The env override exists so several machines can share one list, the way
    `REENTRY_PROFILE_SOURCE` does for the profile -- and it carries the same refusal, for the same
    reason (B103/B107): a source inside the current project means any repo you open could point
    this at a file it controls, and a checkout could then carry the list it is meant to be
    checked against. A path inside the project is refused, loudly, rather than used.
    """
    raw = os.environ.get(PRIVATE_NAMES_ENV, "").strip()
    if not raw:
        return Path.home() / ".claude" / PRIVATE_NAMES_FILE, None
    if not os.path.isabs(os.path.expanduser(raw)):
        return None, f"{PRIVATE_NAMES_ENV}={raw!r} is a relative path — refused; use an absolute one"
    src = Path(os.path.expanduser(raw))
    try:
        src.resolve().relative_to(Path.cwd().resolve())
        return None, (f"{PRIVATE_NAMES_ENV}={raw!r} resolves inside this project — refused; "
                      "a repo must never supply the list it is checked against")
    except ValueError:
        pass
    return src, None


def load_private_patterns():
    """(patterns, note). One entry per line: `label: regex`, or a bare regex. `#` comments.

    A missing file is NOT an error. A fresh clone on someone else's machine has no private names
    to hide, and failing there would make the check something people switch off. It IS reported,
    because a silent partial check reads exactly like a complete one -- the failure this whole
    file exists to prevent.
    """
    path, refusal = _private_names_path()
    if refusal:
        return [], f"REFUSED: {refusal}"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return [], (f"no {path} — generic patterns only. That is correct on a machine with no "
                    f"private names to hide, and a PARTIAL check on one that has them.")
    except Exception as exc:
        return [], f"could not read {path}: {exc}"
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("ok:"):
            continue          # an ACCEPTED name — judged harmless, so the opposite of a pattern
        label, sep, pattern = line.partition(":")
        label, pattern = (label.strip(), pattern.strip()) if sep and pattern.strip()             else ("a local private name", line)
        try:
            re.compile(pattern)
        except re.error as exc:
            out.append(("UNPARSEABLE", None, f"{pattern!r}: {exc}"))
            continue
        out.append((label, pattern))
    bad = [o for o in out if o[0] == "UNPARSEABLE"]
    good = [o for o in out if o[0] != "UNPARSEABLE"]
    note = f"{len(good)} pattern(s) from {path}"
    if bad:
        note += f" — {len(bad)} unparseable and SKIPPED: " + "; ".join(b[2] for b in bad)
    return good, note


def load_accepted():
    """Names seen, judged NOT identifying, and deliberately not banned. `ok: <name>` lines.

    Without this the coverage tool has only two answers — banned, or a finding — so a name that
    is real but harmless (`workspace`: a repo here, and an ordinary English word appearing 36
    times in the incident records) is reported forever. That is the cry-wolf failure that gets a
    check switched off, arriving by a different door.

    The third answer is "judged, and the answer was no". It costs one line, it carries the
    reason beside it as a comment, and it means anything still reported is genuinely NEW.
    """
    path, refusal = _private_names_path()
    if refusal:
        return set()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return set()
    out = set()
    for line in text.splitlines():
        body = line.split("#", 1)[0].strip()
        if body.lower().startswith("ok:"):
            name = body[3:].strip()
            if name:
                out.add(name.lower())
    return out


ACCEPTED = load_accepted()


PRIVATE, PRIVATE_NOTE = load_private_patterns()
BANNED = GENERIC + PRIVATE

SKIP_DIRS = {"__pycache__", ".git"}

# This file is the one shipped file that MUST contain every banned term — they are its patterns.
# It excluded itself implicitly while it was untracked; the moment it was committed, `git ls-files`
# started returning it and the suite went red on the checker rather than on the payload. Naming the
# exclusion is the fix: an implicit one that depends on a file's git status is not an exclusion,
# it is a window that closes.
SKIP_FILES = {"test_payload_clean.py", "test_leak_patterns.py"}
# ...and `test_leak_patterns.py` for the same reason: it exercises these patterns, so it must
# contain text that trips them (a fabricated address that must NOT look like a placeholder, or
# the case proving the email pattern fires proves nothing). Allowlisting that string instead was
# tried and is WRONG — `_strip_allowed` removes it before the scan, which silently disabled the
# test rather than exempting the file.
#
# THE COST, STATED: these two files are never scanned, so a real private name written into
# either one is invisible here. `test_leak_patterns.py` section 1 is deliberately built to need
# no hardcoded private terms; it compares against the list loaded at runtime instead.


def tracked_files():
    """Every tracked file under the plugin root. Falls back to a walk outside a git checkout."""
    try:
        # --others --exclude-standard: an UNTRACKED file is invisible to plain `ls-files`,
        # so a newly written tool passed this check and would then have been published by the
        # very next `git add`. Found 2026-09-07, by writing exactly such a file. Ignored files
        # stay excluded — they are not going anywhere.
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z",
                              "--cached", "--others", "--exclude-standard"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout:
            return sorted(ROOT / name for name in out.stdout.split("\0") if name)
    except Exception:
        pass
    return sorted(p for p in ROOT.rglob("*")
                  if p.is_file() and not SKIP_DIRS & set(p.parts))


def _strip_allowed(text):
    for literal, _why in ALLOWED:
        text = re.sub(re.escape(literal), "", text, flags=re.I)
    return text


# Adjacent string literals joined across a line break: `"...memory "\n        "loss; ..."`. Python
# concatenates those at compile time, so the EMITTED string says "memory loss" while neither line
# does. A line-by-line grep cannot see it, and this is not a hypothetical: it hid exactly that
# phrase in `session_orientation.py`'s always-on output — a runtime-emitted string, the most
# severe category there is — through the whole B12 pass, and was caught by reading the hook's
# actual output rather than by this file. Found 2026-09-06.
_JOIN = re.compile(r"[\"']\s*\n\s*[\"']")


def scan(path):
    """Yield (line_no_or_None, label, matched_text) for every banned term outside an allowed literal.

    Two passes, because they catch different things. The per-line pass gives a line number, which
    is what makes a finding actionable. The flattened pass joins concatenated string literals and
    collapses newlines, so a phrase broken across lines is still found — at the cost of a line
    number, which it reports as None rather than guessing one.

    A GENERIC hit that looks like a documented placeholder is skipped; a PRIVATE one never is.
    See GENERIC_PLACEHOLDER for why that asymmetry is the pattern rather than a workaround.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except Exception:
        return

    generic_labels = {label for label, _ in GENERIC}
    placeholder = re.compile(GENERIC_PLACEHOLDER, re.I)

    def exempt(label, text):
        return label in generic_labels and placeholder.search(text) is not None

    seen = set()
    for i, line in enumerate(raw.split("\n"), 1):
        for label, pattern in BANNED:
            for hit in re.finditer(pattern, _strip_allowed(line), flags=re.I):
                if exempt(label, hit.group(0)):
                    continue
                seen.add(hit.group(0).lower())
                yield i, label, hit.group(0)

    flat = re.sub(r"\s+", " ", _JOIN.sub("", _strip_allowed(raw)))
    for label, pattern in BANNED:
        for hit in re.finditer(pattern, flat, flags=re.I):
            if hit.group(0).lower() not in seen and not exempt(label, hit.group(0)):
                seen.add(hit.group(0).lower())
                yield None, label, hit.group(0)


def main():
    print(f"Scanning the shipped payload under {ROOT}")
    print(f"Patterns: {len(GENERIC)} generic (shipped) + {len(PRIVATE)} private (this machine)")
    print(f"  {PRIVATE_NOTE}")
    print()
    print("Allowed, by decision:")
    for literal, why in ALLOWED:
        print(f"  {literal!r} — {why}")
    print()

    def report(paths, base):
        """Scan a set of files, print every finding, return (files_scanned, hits)."""
        files = hits = 0
        for path in paths:
            if not path.is_file() or path.name in SKIP_FILES:
                continue
            files += 1
            for line_no, label, text in scan(path):
                hits += 1
                rel = path.relative_to(base)
                where = f"{rel}:{line_no}" if line_no else f"{rel} (split across lines)"
                print(f"  FAIL {where}  [{label}]  {text!r}")
        return files, hits


    files, hits = report(tracked_files(), ROOT)
    print(f"{files} shipped file(s) scanned, {hits} personal reference(s) found")

    if REPO:
        print()
        print(f"Scanning the public set under {REPO}")
        missing = [n for n in PUBLIC_SET if not (REPO / n).is_file()]
        pub_files, pub_hits = report([REPO / n for n in PUBLIC_SET], REPO)
        for name in missing:
            print(f"  FAIL {name}  [missing]  on the public list but not in the repo")
        hits += pub_hits + len(missing)
        print(f"{pub_files} public file(s) scanned, {pub_hits} personal reference(s) found")
    else:
        print()
        print("Public set NOT scanned — no marketplace.json above the plugin root, so this is not a")
        print("repo checkout. That is correct when scanning an installed copy, and a gap otherwise.")
    if hits:
        print()
        print("FAILED: the payload installs into other people's machines. Identity and preference")
        print("belong in ~/.claude/reentry-profile.md (see hooks/ensure_profile_file.py), not here.")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
