"""B85: check_repos._unpushed must not report a pushed `afk/` branch as unpushed.

    python plugins/cairn/tools/test_check_repos.py

A lane branch is created from origin/main, so it tracks origin/main; `@{u}..HEAD` then
counts the PR's own commits. Real throwaway git repos, local bare origin, no network.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_repos                                          # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def git(cwd, *args):
    r = subprocess.run(("git", *args), cwd=cwd, capture_output=True, text=True,
                       env={"GIT_TERMINAL_PROMPT": "0", **os.environ})
    if r.returncode != 0:
        raise RuntimeError(f"git {args} failed: {r.stderr}")
    return r.stdout.strip()


def commit(repo, name):
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


tmp = Path(tempfile.mkdtemp(prefix="check_repos_"))
try:
    bare = tmp / "origin.git"
    git(tmp, "init", "--bare", "-q", str(bare))
    git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
    work = tmp / "work"
    git(tmp, "clone", "-q", str(bare), str(work))
    git(work, "config", "user.email", "t@t.com")
    git(work, "config", "user.name", "t")
    git(work, "checkout", "-q", "-B", "main")
    commit(work, "base")
    git(work, "push", "-q", "origin", "main")

    # The default `git switch -c x origin/main` tracks origin/main: the B85 shape.
    git(work, "switch", "-q", "-c", "afk/2026-01-01-01-B1-x", "origin/main")
    commit(work, "lane")
    n, note = check_repos._unpushed(work)
    check("afk branch never pushed: no count, honest note",
          (n, "no origin/afk/" in (note or "")), (None, True))
    git(work, "push", "-q", "origin", "afk/2026-01-01-01-B1-x")
    check("pushed afk branch tracking origin/main: 0 unpushed",
          check_repos._unpushed(work), (0, None))
    commit(work, "more")
    check("afk branch 1 ahead of its own remote", check_repos._unpushed(work), (1, None))

    # Non-afk branches keep using the upstream.
    git(work, "switch", "-q", "main")
    check("main in sync with upstream", check_repos._unpushed(work), (0, None))
    commit(work, "m2")
    check("main 1 ahead of upstream", check_repos._unpushed(work), (1, None))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
