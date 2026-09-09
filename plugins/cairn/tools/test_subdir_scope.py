"""End-to-end test for subtree-scoped git warnings (v1.29.0, issue #13), in throwaway repos.

    python plugins/cairn/tools/test_subdir_scope.py

The defect: every git-derived warning ran git with `cwd=project_root` and read the answer
as being about the PROJECT, while git answered about the whole REPOSITORY. A session
opened in a subfolder therefore warned, on every single session, about files in sibling
folders it was not touching -- the alarm fatigue this plugin is otherwise careful about.

Two halves, and the SECOND is the load-bearing one:

  1. root != toplevel -- warnings are scoped to the session's own subtree.
  2. root == toplevel -- output is byte-identical to the unscoped commands. That is every
     project the user actually works in today, so a regression there is a regression in the
     only thing currently working. Case 5 asserts it against raw git, not against a
     remembered value, so it stays true as the implementation moves.

Same style as `test_repo_recorder.py` and `test_item_open.py`. Needs `git` on PATH and
writes only to a temp directory.

sys.argv[1], if given, is the PLUGIN ROOT (this file's own convention, matching the majority of
`test_*.py` -- see B70) -- not the hooks directory. `hooks/` is appended below.
"""
import os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

base = Path(tempfile.mkdtemp(prefix="subdir-scope-"))
mono = base / "mono"                          # ONE repo holding two project folders
a, b = mono / "proj-a", mono / "proj-b"       # a = the session's project, b = a sibling
solo = base / "solo"                          # an ordinary project: root IS the toplevel
for d in (a, b, solo):
    d.mkdir(parents=True)


def run(*args, cwd):
    return subprocess.run(("git", *args), cwd=cwd, capture_output=True, text=True,
                          **NW).stdout


def commit(repo, message):
    run("add", "-A", cwd=repo)
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message, cwd=repo)


for repo in (mono, solo):
    run("init", "-q", cwd=repo)
    # `.claude/` is ignored here for the same reason it usually is in a real checkout: the
    # wrap marker is a per-clone fact. It also keeps this test honest -- without it the
    # `git add -A` below stages proj-a's marker into a "proj-b only" commit, and case 4
    # measures the test's own bookkeeping instead of the scoping.
    (repo / ".gitignore").write_text(".claude/" + chr(10))
(a / "a.txt").write_text("a\n")
(b / "b.txt").write_text("b\n")
(solo / "s.txt").write_text("s\n")
commit(mono, "init")
commit(solo, "init")

os.environ["CLAUDE_CONFIG_DIR"] = str(base / "cfg")
import reentry_state as st                                              # noqa: E402

fails = []
def check(name, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(name)

def paths(root):
    return sorted(ln[3:].strip() for ln in (st.dirty_paths(root) or []))

def wrap_at(root, ref="HEAD"):
    marker = root / st.WRAP_MARKER_REL
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(run("rev-parse", ref, cwd=root).strip() + "\n")


print("\n1. _scope detects the two cases and nothing else")
check("subfolder of a repo is scoped", st._scope(a), ("--", "."))
check("the repo root itself is NOT scoped", st._scope(mono), ())
check("an ordinary project is NOT scoped", st._scope(solo), ())
check("a path in no repo is NOT scoped", st._scope(base), ())

print("\n2. dirty files in a SIBLING folder are not reported")
(b / "b.txt").write_text("b changed\n")
check("the sibling itself sees them", paths(b), ["proj-b/b.txt"])
check("proj-a reports nothing", paths(a), [])
check("the repo root still sees everything", paths(mono), ["proj-b/b.txt"])

print("\n3. dirty files in your OWN subtree are still reported")
(a / "a.txt").write_text("a changed\n")
(a / "new.txt").write_text("untracked\n")
check("proj-a sees its own, tracked and not",
      paths(a), ["proj-a/a.txt", "proj-a/new.txt"])
check("proj-b is unaffected", paths(b), ["proj-b/b.txt"])
commit(mono, "clean up")
check("proj-a clean again", paths(a), [])

print("\n4. a commit in a sibling does not raise your unwrapped count")
wrap_at(a)                                    # proj-a wraps at the current commit
wrap_at(b)
(b / "b.txt").write_text("more\n")
commit(mono, "work in proj-b only")
check("proj-b counts its own commit", st.unwrapped_commits(b), 1)
check("proj-a is NOT dragged along", st.unwrapped_commits(a), 0)
(a / "a.txt").write_text("more\n")
commit(mono, "work in proj-a")
check("proj-a counts its own", st.unwrapped_commits(a), 1)
check("proj-b unchanged by proj-a's commit", st.unwrapped_commits(b), 1)

print("\n5. root == toplevel is byte-identical to the unscoped commands  (load-bearing)")
(solo / "s.txt").write_text("s changed\n")
(solo / "extra.txt").write_text("new\n")
raw = subprocess.run(("git", "status", "--porcelain", "-uall"), cwd=solo,
                     capture_output=True, text=True, **NW).stdout.rstrip("\r\n")
want = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
check("dirty_paths == raw porcelain", st.dirty_paths(solo), want)
commit(solo, "second")
wrap_at(solo, "HEAD~1")
raw_count = subprocess.run(("git", "rev-list", "--count",
                            (solo / st.WRAP_MARKER_REL).read_text().strip() + "..HEAD"),
                           cwd=solo, capture_output=True, text=True, **NW).stdout.strip()
check("unwrapped_commits == raw rev-list", st.unwrapped_commits(solo), int(raw_count))

print("\n6. the failure modes stay silent, not scoped-wrong")
check("no repo anywhere -> None, as before", st.dirty_paths(base), None)
check("no wrap marker -> None, as before", st.unwrapped_commits(mono), None)

print("\n%d check(s) failed" % len(fails) if fails else "\nall checks passed")
print("temp tree: %s" % base)
sys.exit(1 if fails else 0)
