#!/usr/bin/env python3
"""B51: `archive_reviews.py` moves accepted dossiers and leaves no pointer behind.

Throwaway git repos in temp dirs only; `refs/remotes/origin/main` is set by hand, no remote.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "archive_reviews.py"
NW = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
           GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
           GIT_AUTHOR_DATE="2026-01-02T03:04:00+0000")
fails = []


def check(label, got, want=True):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f" -- got {got!r}"))
    if not ok:
        fails.append(label)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=ENV, **NW).stdout.strip()


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def read(repo, rel):
    return (repo / rel).read_bytes().decode("utf-8")


def commit(repo, msg="c"):
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg)
    return git(repo, "rev-parse", "HEAD")


def push(repo):
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")


def run(repo, *args):
    p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(repo), *args],
                       capture_output=True, text=True, encoding="utf-8", env=ENV,
                       timeout=60, **NW)
    return p.returncode, p.stdout + p.stderr


def fixture():
    repo = Path(tempfile.mkdtemp(prefix="archive-reviews-"))
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "core.autocrlf", "false")
    write(repo, "docs/decisions.md", "see [a](review/lane-a-2020-05-05.md#x)\r\n")
    write(repo, "NEXT.md", "→ docs/review/2020-05-05-1139-lane-b.md.\n"
                           "[b](docs/review/2020-05-05-1139-lane-b.md)\n"
                           "gone: docs/review/never-was.md\n"
                           "bare lane-a-2020-05-05.md\n"
                           "shape: docs/review/<name> docs/review/lane-<x>.md docs/review/**\n")
    write(repo, "test_fx.py", "docs/review/lane-a-2020-05-05.md\n")
    write(repo, "docs/review/lane-a-2020-05-05.md",
          "me: `docs/review/lane-a-2020-05-05.md`\n[d](../decisions.md)\n"
          "[b](2020-05-05-1139-lane-b.md)\n[g](user-guide.md)\n")
    write(repo, "docs/review/2020-05-05-1139-lane-b.md", "[a](lane-a-2020-05-05.md)\n")
    write(repo, "docs/review/user-guide.md", "[a](lane-a-2020-05-05.md)\n")
    commit(repo)
    return repo


A_NEW = "docs/review/archive/2020-05-05-0304-lane-a.md"
B_NEW = "docs/review/archive/2020-05-05-1139-lane-b.md"

print("1. the gate: ahead of origin refuses")
repo = fixture()
push(repo)
write(repo, "x.txt", "x\n")
commit(repo)
code, out = run(repo, "--apply")
check("exit 1", code, 1)
check("says why", "1 commit(s) ahead" in out)
check("nothing moved", (repo / "docs/review/lane-a-2020-05-05.md").is_file())

print("2. dry run is the default and writes nothing")
push(repo)
write(repo, "docs/review/untracked.md", "new\n")
code, out = run(repo)
check("exit 0", code, 0)
check("plans two moves", "would move: 2 dossier(s)" in out)
check("tree unchanged", git(repo, "status", "--porcelain"), "?? docs/review/untracked.md")

print("3. --apply moves, derives the prefix, repoints")
code, out = run(repo, "--apply")
check("exit 0", code, 0)
check("unprefixed name derives one", (repo / A_NEW).is_file())
check("prefixed name keeps its own", (repo / B_NEW).is_file())
check("reference stays", (repo / "docs/review/user-guide.md").is_file())
check("untracked stays", (repo / "docs/review/untracked.md").is_file())
check("relative link repointed, fragment and CRLF kept", read(repo, "docs/decisions.md"),
      "see [a](review/archive/2020-05-05-0304-lane-a.md#x)\r\n")
check("path in prose and link repointed", read(repo, "NEXT.md").split("\n")[:2],
      [f"→ {B_NEW}.", f"[b]({B_NEW})"])
check("moved dossier: own path, outward and sibling links", read(repo, A_NEW),
      f"me: `{A_NEW}`\n[d](../../decisions.md)\n"
      "[b](2020-05-05-1139-lane-b.md)\n[g](../user-guide.md)\n")
check("renamed sibling link follows", read(repo, B_NEW), "[a](2020-05-05-0304-lane-a.md)\n")
check("staying file's link follows", read(repo, "docs/review/user-guide.md"),
      "[a](archive/2020-05-05-0304-lane-a.md)\n")
check("test_*.py fixtures are left alone", read(repo, "test_fx.py"),
      "docs/review/lane-a-2020-05-05.md\n")
check("reports a pointer at nothing", "NEXT.md:3: docs/review/never-was.md" in out)
check("reports a bare old name", "NEXT.md:4: bare old name lane-a-2020-05-05.md" in out)
check("exactly those two", "pointing at nothing, fix by hand: 2\n" in out)

print("4. --accepted takes only what the shas last changed, pushed or not")
repo = fixture()
write(repo, "docs/review/2026-01-01-0000-late.md", "late\n")
sha = commit(repo)
code, out = run(repo, "--accepted", sha[:10], "--apply")
check("exit 0", code, 0)
check("only the named one moves", sorted(p.name for p in (repo / "docs/review/archive").iterdir()),
      ["2026-01-01-0000-late.md"])

print("5. --accepted with a merge sha takes what the merge brought in")
repo = fixture()
git(repo, "checkout", "-qb", "lane")
write(repo, "docs/review/2026-01-01-0000-merged.md", "m\n")
commit(repo)
git(repo, "checkout", "-q", "main")
git(repo, "merge", "-q", "--no-ff", "-m", "merge", "lane")
code, out = run(repo, "--accepted", git(repo, "rev-parse", "HEAD"))
check("one move", "would move: 1 dossier(s)" in out)

print("6. a locally modified dossier stays; an existing destination refuses")
repo = fixture()
push(repo)
write(repo, "docs/review/lane-a-2020-05-05.md", "edited\n")
code, out = run(repo)
check("modified stays", "lane-a-2020-05-05.md (uncommitted changes)" in out)
write(repo, B_NEW, "already here\n")
code, out = run(repo, "--apply")
check("exit 1", code, 1)
check("says why", "would be overwritten" in out)
check("source untouched", (repo / "docs/review/2020-05-05-1139-lane-b.md").is_file())

print()
print(f"FAILED: {fails}" if fails else "ALL PASS")
sys.exit(1 if fails else 0)
