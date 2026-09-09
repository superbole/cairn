"""Coverage for `archive_offer.py` (issue #35), which had none before this file.

    python plugins/cairn/tools/test_archive_offer.py

WHY THIS EXISTS. `archive_offer.py` carries the wrap's step-10 archive question forward to the
NEXT "no wrap needed"/"wrapped" verdict in the same session, so a decline (or the conversation
just moving on) doesn't get silently dropped. It has three library functions (`stamp`, `clear`,
`pending`) and a three-verb CLI (`--stamp`, `--clear`, `--check`) and none of it was under test.

THE BUG THIS PINS (B35). `pending()` returns `None` for TWO opposite situations: no offer was
ever made, and an offer WAS made and accepted (which clears the marker, per the module's own
"WHAT CLEARS IT" docstring). `--check` therefore prints the identical `NONE — no outstanding
archive offer...` line for both. From the printed text alone there is no way to tell "nothing to
carry forward" from "they already said yes" — this test constructs both paths and pins that their
CLI output is byte-identical, named as a BUG so a fix (if `--check` is ever asked to distinguish
them) is measured against a red test rather than a green one that baked the gap in as the spec.

Runs entirely against a throwaway git repo under `tempfile.mkdtemp()`, with `CLAUDE_PROJECT_DIR`
and `CLAUDE_CONFIG_DIR` pointed at it — never the real repo or the real `~/.claude/`. Needs `git`
on PATH, same as `test_item_open.py`.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(sys.argv[1] if len(sys.argv) > 1
             else Path(__file__).resolve().parent.parent / "hooks").resolve()
sys.path.insert(0, str(HOOKS))
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

import archive_offer                                    # noqa: E402
from reentry_state import state_dir                      # noqa: E402

# B74 FIX. `cli()` below sandboxes CLAUDE_CONFIG_DIR per subprocess, but sections 1-2 and part
# of section 3 call `archive_offer.stamp/clear/pending` and `state_dir()` DIRECTLY, in THIS
# process -- a subprocess env override never reaches them. `state_dir()` falls back to
# `Path.home() / ".claude"` when the env var is unset, so every one of those direct calls was
# writing a real fixture directory into `~/.claude/reentry-state/` (the user's actual operator
# history) on every run of this file. Set once, here, before any such call -- `state_dir()`
# re-reads the env var on every call rather than caching it at import time, so this is the ONE
# place setting it needs to happen; a per-call override would work too but is unnecessary
# duplication for calls that never leave this process.
os.environ["CLAUDE_CONFIG_DIR"] = str(Path(tempfile.mkdtemp(prefix="archive-offer-cfg-")))

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def new_repo(name):
    """A fresh git repo with one commit, and its own isolated state dir."""
    root = Path(tempfile.mkdtemp(prefix="archive-offer-%s-" % name))
    for a in (("init", "-q"), ("-c", "user.email=t@t", "-c", "user.name=t",
                                "commit", "-qm", "init", "--allow-empty")):
        subprocess.run(("git", *a), cwd=root, capture_output=True, **NW)
    return root


def head_of(root):
    r = subprocess.run(("git", "rev-parse", "HEAD"), cwd=root, capture_output=True,
                       text=True, **NW)
    return r.stdout.strip()


def commit_more(root):
    """Move HEAD on, so a marker stamped at the OLD head is now stale."""
    subprocess.run(("git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "more", "--allow-empty"), cwd=root, capture_output=True, **NW)


def cli(root, cfg, *args):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root), "CLAUDE_CONFIG_DIR": str(cfg),
           "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run((sys.executable, str(HOOKS / "archive_offer.py"), *args),
                       cwd=root, capture_output=True, text=True, env=env, **NW)
    return p.returncode, (p.stdout + p.stderr).strip()


print("1. stamp() writes a marker; clear() removes it (and tolerates having nothing to remove)")
root1 = new_repo("lib")
head1 = head_of(root1)
check("nothing pending before any stamp", archive_offer.pending(root1), None)
archive_offer.stamp(root1, head1)
marker_path = state_dir(root1) / archive_offer.MARKER_NAME
check("marker file exists on disk", marker_path.is_file(), True)
recorded = json.loads(marker_path.read_text(encoding="utf-8"))
check("marker records the head it was given", recorded.get("head"), head1)
check("marker records a timestamp", isinstance(recorded.get("at"), (int, float)), True)
archive_offer.clear(root1)
check("marker file gone after clear()", marker_path.exists(), False)
check("clear() on an already-clear marker does not raise",
      (archive_offer.clear(root1), True)[1], True)

print("\n2. pending() — every state")
root2 = new_repo("pending")
head2 = head_of(root2)
check("no marker at all -> None", archive_offer.pending(root2), None)
archive_offer.stamp(root2, head2)
check("marker at the CURRENT head -> returns that head", archive_offer.pending(root2), head2)
commit_more(root2)
newhead2 = head_of(root2)
check("HEAD moved on since the stamp -> now None (superseded)",
      archive_offer.pending(root2), None)
check("HEAD really did change", newhead2 != head2, True)

root2b = new_repo("pending-corrupt")
mp2b = state_dir(root2b) / archive_offer.MARKER_NAME
mp2b.write_text("not json at all {{{", encoding="utf-8")
check("an unreadable (corrupt JSON) marker -> None, not a raised exception",
      archive_offer.pending(root2b), None)

root2c = new_repo("pending-no-head-field")
mp2c = state_dir(root2c) / archive_offer.MARKER_NAME
mp2c.write_text(json.dumps({"at": 123.0}), encoding="utf-8")
check("a marker missing the 'head' field -> None", archive_offer.pending(root2c), None)

root2d = new_repo("pending-blank-head")
mp2d = state_dir(root2d) / archive_offer.MARKER_NAME
mp2d.write_text(json.dumps({"head": "", "at": 123.0}), encoding="utf-8")
check("a marker with an empty 'head' string -> None", archive_offer.pending(root2d), None)

root2e = new_repo("pending-not-a-dict")
mp2e = state_dir(root2e) / archive_offer.MARKER_NAME
mp2e.write_text(json.dumps(["head", "not", "a", "dict"]), encoding="utf-8")
check("a marker whose JSON is not an object -> None", archive_offer.pending(root2e), None)

print("\n3. --check prints NONE for BOTH 'never offered' and 'offered then accepted', "
      "PROVIDED `--stamp-asked` has never been used in this project (B35 -- decided: this "
      "is the CORRECT degraded behaviour for an unmigrated project, not the bug -- "
      "see section 7 for the actual fix, which is gated behind `--stamp-asked` ever "
      "having fired here)")
root3a = new_repo("check-never-offered")
cfg3a = root3a.parent / (root3a.name + "-cfg")
rc3a, out3a = cli(root3a, cfg3a, "--check")
check("exit 0", rc3a, 0)
check("prints NONE", out3a.startswith("NONE"), True)

root3b = new_repo("check-offered-then-accepted")
cfg3b = root3b.parent / (root3b.name + "-cfg")
head3b = head_of(root3b)
archive_offer.stamp(root3b, head3b)          # the offer was made ...
archive_offer.clear(root3b)                  # ... and they said yes, so it was cleared
rc3b, out3b = cli(root3b, cfg3b, "--check")
check("exit 0", rc3b, 0)
check("UNCHANGED BY DESIGN: also prints NONE -- indistinguishable from 'never asked', "
      "because --stamp-asked was never called in this project (see section 7)",
      out3b.startswith("NONE"), True)
check("UNCHANGED BY DESIGN: the two --check outputs are byte-identical -- an unmigrated "
      "project's behaviour must not change out from under it",
      out3a, out3b)

print("\n4. --check prints PENDING when an offer is outstanding at the current HEAD")
root4 = new_repo("check-pending")
cfg4 = root4.parent / (root4.name + "-cfg")
head4 = head_of(root4)
rc4, out4 = cli(root4, cfg4, "--stamp")
check("--stamp exits 0", rc4, 0)
check("--stamp names the head it recorded", head4[:12] in out4, True)
rc4b, out4b = cli(root4, cfg4, "--check")
check("--check now exits 0", rc4b, 0)
check("--check now prints PENDING", out4b.startswith("PENDING"), True)
check("--check names the head", head4[:12] in out4b, True)
rc4c, out4c = cli(root4, cfg4, "--clear")
check("--clear exits 0", rc4c, 0)
check("--clear says so", "cleared" in out4c, True)
rc4d, out4d = cli(root4, cfg4, "--check")
check("--check is back to NONE after --clear", out4d.startswith("NONE"), True)

print("\n5. --stamp with nothing to stamp against")
root5 = Path(tempfile.mkdtemp(prefix="archive-offer-nogit-"))     # deliberately NOT a git repo
cfg5 = root5.parent / (root5.name + "-cfg")
rc5, out5 = cli(root5, cfg5, "--stamp")
check("--stamp on a non-git directory exits 1", rc5, 1)
check("--stamp says there was nothing to stamp", "nothing to stamp" in out5, True)

print("\n6. CLI usage / bad args")
root6 = new_repo("usage")
cfg6 = root6.parent / (root6.name + "-cfg")
rc6a, out6a = cli(root6, cfg6)
check("no args -> exit 2", rc6a, 2)
check("no args -> usage text", "usage:" in out6a, True)
rc6b, out6b = cli(root6, cfg6, "--bogus")
check("unrecognised flag -> exit 2", rc6b, 2)
check("unrecognised flag -> usage text", "usage:" in out6b, True)

print("\n7. B35 FIX -- once `--stamp-asked` has fired in a project, --check can tell "
      "NEVER_ASKED apart from a resolved NONE")
root7 = new_repo("asked-fix")
cfg7 = root7.parent / (root7.name + "-cfg")
head7 = head_of(root7)

print("  7a. asked, then they said yes (--clear) -- resolved, reported as NONE, not NEVER_ASKED")
rc7a, out7a = cli(root7, cfg7, "--stamp-asked")
check("--stamp-asked exits 0", rc7a, 0)
check("--stamp-asked names the head", head7[:12] in out7a, True)
rc7b, out7b = cli(root7, cfg7, "--clear")
check("--clear exits 0", rc7b, 0)
rc7c, out7c = cli(root7, cfg7, "--check")
check("resolved (asked + accepted) -> NONE, not NEVER_ASKED", out7c.startswith("NONE"), True)
check("...and says it was actually resolved, not just silent",
      "resolved" in out7c, True)

print("  7b. a DIFFERENT project that never called --stamp-asked at all -- untouched")
root7z = new_repo("asked-fix-unused")
cfg7z = root7z.parent / (root7z.name + "-cfg")
rc7z, out7z = cli(root7z, cfg7z, "--check")
check("still plain NONE for a project that never used --stamp-asked", out7z.startswith("NONE"),
      True)
check("does not claim anything was resolved", "resolved" not in out7z, True)

print("  7c. asked, then NOTHING answered it (step 10 effectively skipped after asking) "
      "-- reported as NEVER_ASKED once HEAD moves past the ask with no resolution")
root7d = new_repo("asked-then-abandoned")
cfg7d = root7d.parent / (root7d.name + "-cfg")
head7d = head_of(root7d)
rc7d1, _ = cli(root7d, cfg7d, "--stamp-asked")
check("--stamp-asked exits 0", rc7d1, 0)
rc7d2, out7d2 = cli(root7d, cfg7d, "--check")
check("still at the SAME head as the ask, unresolved -> reads as NONE (ask is current, "
      "not yet contradicted) -- this is the ambiguous middle instant right after asking, "
      "before an answer OR a new commit; NEVER_ASKED is about a NEW head with no ask at "
      "all, covered next", out7d2.startswith("NONE"), True)
commit_more(root7d)                       # HEAD moves on with the ask still unresolved
rc7d3, out7d3 = cli(root7d, cfg7d, "--check")
check("HEAD moved on past an ask that was never resolved for ITS OWN head -> NEVER_ASKED",
      out7d3.startswith("NEVER_ASKED"), True)
check("says step 10 may have been skipped", "skipped" in out7d3, True)
check("explicitly disclaims being a settled-question confirmation",
      "NOT" in out7d3 and "settled" in out7d3, True)

print("  7d. PENDING still wins over everything else -- an outstanding decline is never "
      "reported as NEVER_ASKED just because it also happens to be unasked-for-this-head")
root7e = new_repo("pending-beats-never-asked")
cfg7e = root7e.parent / (root7e.name + "-cfg")
head7e = head_of(root7e)
cli(root7e, cfg7e, "--stamp-asked")
cli(root7e, cfg7e, "--stamp")             # declined -- PENDING at the same head
rc7e, out7e = cli(root7e, cfg7e, "--check")
check("PENDING takes priority", out7e.startswith("PENDING"), True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
