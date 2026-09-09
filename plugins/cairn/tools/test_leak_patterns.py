#!/usr/bin/env python3
"""Test for the split pattern layer in `test_payload_clean.py` (2026-09-07, B51 step 2).

    python plugins/cairn/tools/test_leak_patterns.py

WHAT IS ACTUALLY AT RISK HERE
------------------------------
The checker used to carry its private names inline, in a file that ships to every installer and
that excludes itself from its own scan. Splitting them out fixes the disclosure but introduces a
failure that is worse than the one it replaces: **the checker can now pass because it loaded
nothing.** A missing file, a typo'd env var, one unparseable regex -- and `ALL PASS` means "no
patterns ran", printed in the same words as a real pass.

So the cases below are mostly about the loader, not the patterns. The one that matters most is
section 3: a private name PLANTED in a scanned file must fail. That is the only test that can
tell "the local list is live" from "the local list is empty".

NEVER TOUCHES THE REAL ~/.claude/reentry-private-names.txt. Every case points
`REENTRY_PRIVATE_NAMES` at a fixture this test writes, and reloads the module against it.
"""
import importlib
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_payload_clean as tpc                        # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def reload_with(names_file):
    """Reload the checker with REENTRY_PRIVATE_NAMES pointed at `names_file` (or unset)."""
    if names_file is None:
        os.environ.pop("REENTRY_PRIVATE_NAMES", None)
    else:
        os.environ["REENTRY_PRIVATE_NAMES"] = str(names_file)
    return importlib.reload(tpc)


def write(text):
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def scan_text(mod, text):
    """Run the module's scanner over a throwaway file and return the labels it yields."""
    p = write(text)
    try:
        return [label for _line, label, _hit in mod.scan(p)]
    finally:
        p.unlink(missing_ok=True)


print("1. the shipped generic patterns compile and name nobody")
import re                                               # noqa: E402
for label, pattern in tpc.GENERIC:
    try:
        re.compile(pattern)
        check(f"compiles: {label}", True, True)
    except re.error as exc:
        check(f"compiles: {label}", str(exc), "compiles")
# THIS ASSERTION MUST NOT NAME ANYTHING. The obvious way to write it -- a literal list of the
# real private terms, asserted absent -- puts those terms in a file that ships, which is the
# exact disclosure the split was made to fix. (Written that way first, on 2026-09-07, and caught
# by the checker one run later.) So it compares GENERIC against the patterns loaded at RUNTIME
# from the local file: nothing private is written down here, and the property checked is the one
# that matters -- that the split actually happened and nothing leaked back.
joined = " ".join(p for _l, p in tpc.GENERIC).lower()
if tpc.PRIVATE:
    # Pull the word-ish literals out of each private pattern without letting regex syntax mangle
    # them: `bole` must yield `bole`, not `ole`.
    for label, pattern in tpc.PRIVATE:
        bare = re.sub(r"\[bBdDsSwW]", " ", pattern)
        for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{3,}", bare):
            check(f"generic does not contain a private term for {label!r}",
                  term.lower() in joined, False)
else:
    print("   ---- no local private list on this machine; nothing to compare against")

check("generic patterns are all category names, not instances",
      all(any(c in label for c in " ") for label, _ in tpc.GENERIC), True)

print("\n2. a private list loads, and its patterns are added to the generic ones")
f = write("a person's name: alphaperson\nbare-pattern-no-label\n")
mod = reload_with(f)
check("two patterns loaded", len(mod.PRIVATE), 2)
check("labelled row keeps its label", mod.PRIVATE[0][0], "a person's name")
check("bare row gets the default label", mod.PRIVATE[1][0], "a local private name")
check("BANNED is generic + private", len(mod.BANNED), len(mod.GENERIC) + 2)
check("note names the file", str(f) in mod.PRIVATE_NOTE, True)

print("\n3. THE ONE THAT MATTERS: a planted private name FAILS the scan")
check("planted name is caught", "a person's name" in scan_text(mod, "x = 'alphaperson'"), True)
check("bare-pattern row also catches", "a local private name" in
      scan_text(mod, "see bare-pattern-no-label here"), True)
check("an unrelated word is not caught", scan_text(mod, "ordinary prose about queues"), [])

print("\n4. a MISSING file is reported, not silently treated as a pass")
missing = Path(tempfile.gettempdir()) / "reentry-no-such-names-file.txt"
missing.unlink(missing_ok=True)
mod = reload_with(missing)
check("no private patterns", len(mod.PRIVATE), 0)
check("generic still active", len(mod.BANNED), len(mod.GENERIC))
check("note says PARTIAL", "PARTIAL" in mod.PRIVATE_NOTE, True)
check("note names the path it looked at", str(missing) in mod.PRIVATE_NOTE, True)

print("\n5. an unparseable line is SKIPPED and named — the rest still load")
f = write("good: alphaperson\nbroken: [unterminated\nalso-good: betaproject\n")
mod = reload_with(f)
check("two good patterns survive", len(mod.PRIVATE), 2)
check("note says unparseable", "unparseable" in mod.PRIVATE_NOTE, True)
check("note quotes the bad pattern", "[unterminated" in mod.PRIVATE_NOTE, True)
check("the good ones still catch", "good" in scan_text(mod, "alphaperson"), True)

print("\n6. a relative or in-project source is REFUSED (B103/B107), not read")
mod = reload_with("relative/names.txt")
check("relative refused", mod.PRIVATE_NOTE.startswith("REFUSED"), True)
check("nothing loaded from a refused source", len(mod.PRIVATE), 0)
in_project = Path.cwd() / "names-inside-the-project.txt"
in_project.write_text("a person's name: alphaperson\n", encoding="utf-8")
try:
    mod = reload_with(in_project)
    check("in-project refused", mod.PRIVATE_NOTE.startswith("REFUSED"), True)
    check("in-project source is not loaded", len(mod.PRIVATE), 0)
    check("and so cannot be caught", scan_text(mod, "alphaperson"), [])
finally:
    in_project.unlink(missing_ok=True)

print("\n7. `ok:` lines become ACCEPTED — the third answer, neither banned nor a finding")
f = write("a person's name: alphaperson\nok: workspace  # generic word\nok: Oscar\n")
mod = reload_with(f)
check("two accepted", len(mod.ACCEPTED), 2)
check("accepted is lowercased", "oscar" in mod.ACCEPTED, True)
check("comment is stripped from the name", "workspace" in mod.ACCEPTED, True)
check("an accepted name is NOT a banned pattern", scan_text(mod, "the workspace directory"), [])

print("\n8. the placeholder exemption applies to GENERIC only, never to a private name")
f = write("a private project: example-corp-internal\n")
mod = reload_with(f)
check("a documented example home path is exempt",
      scan_text(mod, r"path = 'C:\Users\Example\Projects'"), [])
check("an SSH url is not read as an email", scan_text(mod, "git@github.com:owner/repo.git"), [])
check("a real-looking address IS caught",
      "an email address" in scan_text(mod, "contact person.name@acmecorp.co.uk"), True)
check("a PRIVATE name containing 'example' is still caught",
      "a private project" in scan_text(mod, "see example-corp-internal"), True)

print("\n9. the private config store is REACHABLE (B115), and self-identity is subtracted")
# B115: `sibling_names()` walks siblings of the current project, but the store is required to live
# OUTSIDE `~/Projects` -- so its repo name was a sibling of nothing and could never be reported
# UNCOVERED, no matter how long the tool ran. The store is where `profile.md` lives, and
# `ensure_profile_file.py` hands out `~/.claude-private/<your-repo>/profile.md` as the value to
# make concrete, so that name is among the likeliest to reach a docstring.
import shutil                                              # noqa: E402
import check_leak_coverage as clc                           # noqa: E402

repo_root = HERE.parent.parent.parent
store_parent = Path.home() / ".cairn-leaktest-store"
store = store_parent / "zzprivatestorename"
store.mkdir(parents=True, exist_ok=True)
names_fixture = store / "reentry-private-names.txt"
names_fixture.write_text("# empty\n", encoding="utf-8")
prev_profile = os.environ.get("REENTRY_PROFILE_SOURCE")
try:
    os.environ["REENTRY_PROFILE_SOURCE"] = str(store / "profile.md")
    derived = clc.private_store_names()
    check("the store's own directory name is derived", "zzprivatestorename" in derived, True)
    check("so is the directory holding it", "cairn-leaktest-store" in derived, True)

    published = {n.lower() for n in clc.self_published_names(repo_root)}
    check("the plugin's own name is read from its manifest", "cairn" in published, True)
    found, subtracted = clc.candidates(repo_root)
    check("and is therefore NOT a candidate", "cairn" in {n.lower() for n in found}, False)
    check("the subtraction is reported, not silent", "cairn" in {n.lower() for n in subtracted},
          True)
    # The cry-wolf case this guards: without the subtraction, the plugin's own name is derived
    # from the store path on the developing machine and lands in ~230 payload lines as a LEAK.
    check("no self-published name is left to be reported",
          published & {n.lower() for n in found}, set())
finally:
    if prev_profile is None:
        os.environ.pop("REENTRY_PROFILE_SOURCE", None)
    else:
        os.environ["REENTRY_PROFILE_SOURCE"] = prev_profile
    shutil.rmtree(store_parent, ignore_errors=True)

reload_with(None)
print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
