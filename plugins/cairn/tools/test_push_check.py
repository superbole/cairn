"""Coverage for `push_check.py` (BACKLOG.md B86), which had none before this file.

    python plugins/cairn/tools/test_push_check.py

WHY THIS EXISTS. B22 made the wrap commit locally and stop before the push whenever the
session ran unattended. `push_check.py` is the mechanical check that the stop actually
held — an `origin/<branch>...HEAD` ahead-count, reported LOUDLY when it comes back 0. This
test exists because the entry that asked for the check named the exact trap a check like
this can fall into: "a check that cannot distinguish 'nothing to report' from 'could not
run' is the same defect it is meant to catch." So this file proves all three outcomes
(`HELD`, `ALERT`, `CANNOT_CHECK`) are reachable, mutually exclusive, and — this is the part
worth pinning — that `CANNOT_CHECK` covers every "I couldn't even ask the question" case
(no commits, detached HEAD, no remote, no upstream ref) SEPARATELY from `ALERT`, which only
ever fires once the check has a real `origin/<branch>` ref to compare against.

Runs entirely against throwaway git repos under `tempfile.mkdtemp()` — a bare "origin" plus
clones of it — never the real repo or the real `~/.claude/`. Needs `git` on PATH, same as
`test_item_open.py` / `test_archive_offer.py`.

sys.argv[1], if given, is the PLUGIN ROOT (B70 convention) -- not the hooks directory.
`hooks/` is appended below.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

# Sandboxed BEFORE any import that might touch it, same reasoning as test_archive_offer.py's
# B74 fix: push_check.py's project_root() -> reentry_state stamps a per-session root file
# under CLAUDE_CONFIG_DIR (falls back to the real ~/.claude/ if unset) the moment it resolves
# CLAUDE_PROJECT_DIR. Every call below sets CLAUDE_PROJECT_DIR explicitly, so without this the
# in-process calls would leak a fixture into the user's real state dir on every run of this file.
os.environ["CLAUDE_CONFIG_DIR"] = str(Path(tempfile.mkdtemp(prefix="push-check-cfg-")))

import push_check                                        # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def run(args, cwd):
    r = subprocess.run(("git", *args), cwd=cwd, capture_output=True, text=True, **NW)
    return r


def bare_origin(name):
    """A bare 'remote' repo, default branch pinned to `main` regardless of local git config."""
    root = Path(tempfile.mkdtemp(prefix=f"push-check-{name}-bare-"))
    run(("-c", "init.defaultBranch=main", "init", "-q", "--bare"), root)
    return root


def clone(url, name):
    root = Path(tempfile.mkdtemp(prefix=f"push-check-{name}-clone-"))
    r = run(("clone", "-q", str(url), str(root)), Path(tempfile.gettempdir()))
    assert r.returncode == 0, r.stderr
    run(("config", "user.email", "t@t"), root)
    run(("config", "user.name", "t"), root)
    return root


def commit(root, msg="work", allow_empty=True):
    args = ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg]
    if allow_empty:
        args.append("--allow-empty")
    r = run(args, root)
    assert r.returncode == 0, r.stderr


def push(root, *args):
    r = run(("push", *args), root)
    assert r.returncode == 0, r.stderr


def cli_env(root):
    return {**os.environ, "CLAUDE_PROJECT_DIR": str(root),
            "CLAUDE_CONFIG_DIR": str(Path(tempfile.mkdtemp(prefix="push-check-cfg-"))),
            "PYTHONIOENCODING": "utf-8"}


def cli(root, *argv):
    p = subprocess.run((sys.executable, str(HOOKS / "push_check.py"), *argv), cwd=root,
                       capture_output=True, text=True, env=cli_env(root), **NW)
    return p.returncode, (p.stdout + p.stderr).strip()


def head(root):
    """HEAD's sha -- what a wrap captures BEFORE it commits, to pass as `--since`."""
    r = run(("rev-parse", "HEAD"), root)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


print("1. no commits yet -> CANNOT_CHECK / no-commits (never HELD or ALERT)")
root1 = Path(tempfile.mkdtemp(prefix="push-check-nocommit-"))
run(("-c", "init.defaultBranch=main", "init", "-q"), root1)
result1 = push_check.check(root1)
check("status", result1["status"], push_check.CANNOT_CHECK)
check("reason", result1["reason"], "no-commits")
rc1, out1 = cli(root1)
check("cli exit code is 0 (never fails the wrap)", rc1, 0)
check("cli prints CANNOT_CHECK on the first line", out1.splitlines()[0].startswith("CANNOT_CHECK"), True)

print("\n2. detached HEAD -> CANNOT_CHECK / detached-head")
origin2 = bare_origin("detached")
root2 = clone(origin2, "detached")
commit(root2)
push(root2, "-q", "origin", "HEAD:main")
head2 = run(("rev-parse", "HEAD"), root2).stdout.strip()
run(("checkout", "-q", "--detach", head2), root2)
result2 = push_check.check(root2)
check("status", result2["status"], push_check.CANNOT_CHECK)
check("reason", result2["reason"], "detached-head")

print("\n3. no remote at all -> CANNOT_CHECK / no-remote")
root3 = Path(tempfile.mkdtemp(prefix="push-check-noremote-"))
run(("-c", "init.defaultBranch=main", "init", "-q"), root3)
commit(root3)
result3 = push_check.check(root3)
check("status", result3["status"], push_check.CANNOT_CHECK)
check("reason", result3["reason"], "no-remote")

print("\n4. origin remote configured but never fetched -> CANNOT_CHECK / no-upstream")
origin4 = bare_origin("noupstream")
root4 = Path(tempfile.mkdtemp(prefix="push-check-noupstream-"))
run(("-c", "init.defaultBranch=main", "init", "-q"), root4)
commit(root4)
run(("remote", "add", "origin", str(origin4)), root4)
result4 = push_check.check(root4)
check("status", result4["status"], push_check.CANNOT_CHECK)
check("reason", result4["reason"], "no-upstream")

print("\n5. local commit made and NOT pushed (the B22 stop) -> HELD, ahead > 0")
origin5 = bare_origin("held")
root5 = clone(origin5, "held")
commit(root5, "seed")
push(root5, "-q", "origin", "HEAD:main")
commit(root5, "local work, held back")
result5 = push_check.check(root5)
check("status", result5["status"], push_check.HELD)
check("ahead is 1", result5["ahead"], 1)
check("behind is 0", result5["behind"], 0)
check("ref names origin/main", result5["ref"], "origin/main")
rc5, out5 = cli(root5)
check("cli prints HELD on the first line", out5.splitlines()[0].startswith("HELD"), True)

print("\n6. ahead == 0 with NO --since baseline -> CANNOT_CHECK / no-baseline. The count "
      "alone cannot tell 'pushed unasked' from 'committed nothing', and guessing either "
      "way is the alarm-fatigue bug this file exists to avoid.")
origin6 = bare_origin("alert")
root6 = clone(origin6, "alert")
commit(root6, "seed")
push(root6, "-q", "origin", "HEAD:main")
result6 = push_check.check(root6)
check("status", result6["status"], push_check.CANNOT_CHECK)
check("reason", result6["reason"], "no-baseline")
check("ahead is 0", result6["ahead"], 0)
rc6, out6 = cli(root6)
check("cli prints CANNOT_CHECK on the first line",
      out6.splitlines()[0].startswith("CANNOT_CHECK"), True)

print("\n6b. ahead == 0 and HEAD has NOT moved since the baseline -> NOTHING_TO_HOLD. This "
      "is every wrap of a session that committed nothing, and it must NEVER be an alert.")
base6b = head(root6)
result6b = push_check.check(root6, since=base6b)
check("status", result6b["status"], push_check.NOTHING_TO_HOLD)
check("ahead is 0", result6b["ahead"], 0)
check("NOTHING_TO_HOLD is not ALERT", result6b["status"] == push_check.ALERT, False)
check("NOTHING_TO_HOLD differs from every CANNOT_CHECK case above",
      result6b["status"] not in (r["status"] for r in (result1, result2, result3, result4)),
      True)
rc6b, out6b = cli(root6, "--since", base6b)
check("cli prints NOTHING_TO_HOLD on the first line",
      out6b.splitlines()[0].startswith("NOTHING_TO_HOLD"), True)

print("\n7. HEAD MOVED this wrap and yet ahead == 0 -> ALERT. This is the real B86 failure: "
      "commits were made and something pushed them without being asked.")
origin7 = bare_origin("afterpush")
root7 = clone(origin7, "afterpush")
commit(root7, "seed")
push(root7, "-q", "origin", "HEAD:main")
base7 = head(root7)                        # what the wrap captures BEFORE committing
commit(root7, "more work")
mid7 = push_check.check(root7, since=base7)
check("held before the push", mid7["status"], push_check.HELD)
check("ahead is 1 before the push", mid7["ahead"], 1)
push(root7, "-q", "origin", "HEAD:main")   # the push that should never have happened
after7 = push_check.check(root7, since=base7)
check("ahead back to 0 with a moved HEAD is ALERT", after7["status"], push_check.ALERT)
check("behind is 0 too (in sync, not diverged)", after7["behind"], 0)
check("ALERT differs from NOTHING_TO_HOLD on the same 0 count",
      after7["status"] != result6b["status"], True)
rc7, out7 = cli(root7, "--since", base7)
check("cli prints ALERT on the first line", out7.splitlines()[0].startswith("ALERT"), True)

print("\n7b. an unresolvable --since -> CANNOT_CHECK / bad-baseline, never a guess")
result7b = push_check.check(root7, since="notasha")
check("status", result7b["status"], push_check.CANNOT_CHECK)
check("reason", result7b["reason"], "bad-baseline")

print("\n8. behind is reported too (someone else pushed ahead of us) -- and with an unmoved "
      "HEAD that is NOTHING_TO_HOLD, not an alert")
origin8 = bare_origin("behind")
root8a = clone(origin8, "behind-a")
commit(root8a, "seed")
push(root8a, "-q", "origin", "HEAD:main")
root8b = clone(origin8, "behind-b")
commit(root8a, "someone else's commit")
push(root8a, "-q", "origin", "HEAD:main")
run(("fetch", "-q", "origin"), root8b)  # push_check never fetches itself (see
                                        # upstream_ref's docstring) -- do it here so
                                        # root8b's local origin/main ref is current.
result8 = push_check.check(root8b, since=head(root8b))
check("root8b has 0 local commits ahead", result8["ahead"], 0)
check("...but IS behind, which must show up in behind, not conflated with ahead",
      result8["behind"], 1)
check("being behind with an unmoved HEAD is NOTHING_TO_HOLD, not ALERT",
      result8["status"], push_check.NOTHING_TO_HOLD)

print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + repr(fails)}")
sys.exit(1 if fails else 0)
