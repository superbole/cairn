"""Fixture test for the B26 cross-repo sweep (`hooks/repo_sweep.py`).

    python plugins/cairn/tools/test_repo_sweep.py

WHY THIS IS A TEST AND NOT A CODE REVIEW. `repo_sweep.py` has three failure modes that are
each invisible from reading the code alone: (1) `sibling_repos` silently including a folder
that never opted into the system (no NEXT.md) — the exact scope B26 was raised to avoid
guessing at; (2) `_behind` silently misreading "no upstream"/"detached HEAD"/"in sync" as
"behind"; (3) the cache round-trip (`refresh` writes, `summary_line` reads) disagreeing about
shape and going silent for the wrong reason. All three need REAL git repos to catch, because
they are decided by what real `git` commands actually return, not by what the code appears to
do.

NO NETWORK, NO REAL REPO. Every repo here is built fresh under a temp dir with a LOCAL
`file://`-shaped `origin` (a bare repo on the same disk) — the instruction this lane was given
is explicit that `git fetch` against a fixture repo it created is fine, and that is the only
kind of fetch this file ever issues. Nothing here touches `~/Projects` or any of the user's own
checkouts.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(ROOT / "hooks"))

import repo_sweep as rs                                 # noqa: E402
import reentry_state                                    # noqa: E402

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
        raise RuntimeError(f"git {args} failed in {cwd}: {r.stderr}")
    return r.stdout.strip()


def make_bare(base, name):
    p = base / name
    git(base, "init", "--bare", "-q", str(p))
    # Force the branch name regardless of this machine's `init.defaultBranch`. Left to the
    # ambient config, a clone of the still-empty bare repo can pick a DIFFERENT default
    # branch than the one later pushes create ("remote HEAD refers to nonexistent ref"),
    # so every later clone checks out an unrelated unborn branch and the first push from
    # it is rejected as non-fast-forward against a history it never descended from.
    git(p, "symbolic-ref", "HEAD", "refs/heads/main")
    return p


def make_clone(base, origin, name, branch="main"):
    p = base / name
    git(base, "clone", "-q", str(origin), str(p))
    git(p, "config", "user.email", "t@t.com")
    git(p, "config", "user.name", "t")
    return p


def commit_and_push(repo, fname, branch="main"):
    (repo / fname).write_text("x", encoding="utf-8")
    git(repo, "add", fname)
    git(repo, "commit", "-q", "-m", f"add {fname}")
    git(repo, "push", "-q", "origin", f"HEAD:{branch}")


# --------------------------------------------------------------------------- build fixtures

tmp = Path(tempfile.mkdtemp(prefix="repo_sweep_test_"))

# B74 FIX. `rs.state_dir` is monkey-patched below (see the refresh/summary_line section) and
# restored in that block's own `finally`, so it protects THOSE calls -- but `spawn_refresh`
# launches a DETACHED CHILD PROCESS that re-imports `reentry_state` fresh in its own
# interpreter; a monkey-patched function reference in THIS process never reaches it. That
# child resolves `state_dir()` the normal way -- `CLAUDE_CONFIG_DIR` or `Path.home() /
# ".claude"` -- so with nothing set here it wrote its cache into the REAL
# `~/.claude/reentry-state/<slug-of-this-temp-root>`, a fresh slug every run since `root`
# lives under a fresh `tempfile.mkdtemp()`. An env var, unlike the monkey-patch, IS inherited
# by the child (`spawn_refresh` builds its env as `{**os.environ, ...}`), so this is the fix
# that actually reaches it.
os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")

try:
    projects = tmp / "Projects"
    projects.mkdir()

    origin = make_bare(projects, "origin.git")

    # `root` — the project this session is standing in. Carries its own NEXT.md, same as
    # every project this whole plugin cares about, but its OWN divergence is not this
    # module's job (that is `_divergence_warning`) — it must never appear in its own sweep.
    root = make_clone(projects, origin, "root")
    (root / "NEXT.md").write_text("# NEXT\n", encoding="utf-8")
    commit_and_push(root, "seed.txt")

    # behind_two — cloned at THIS point (one commit), then origin moves on without it via a
    # separate pushing clone. Must be cloned and left alone BEFORE origin advances again.
    behind_two = make_clone(projects, origin, "behind_two")
    (behind_two / "NEXT.md").write_text("# NEXT\n", encoding="utf-8")
    pusher = make_clone(projects, origin, "_pusher")
    commit_and_push(pusher, "second.txt")
    commit_and_push(pusher, "third.txt")

    # in_sync — cloned AFTER origin's later commits, so it is genuinely fully caught up.
    # Cloning it earlier (before `_pusher` advances origin) would make it just as behind as
    # `behind_two` once `_behind` fetches — this ordering is what makes "in sync" true.
    in_sync = make_clone(projects, origin, "in_sync")
    (in_sync / "NEXT.md").write_text("# NEXT\n", encoding="utf-8")

    # no_next — a real git repo, up to date with a real remote, but never opted into this
    # system. Must be EXCLUDED from the sweep entirely, not just reported as "0 behind".
    no_next = make_clone(projects, origin, "no_next")

    # not_a_repo — an ordinary folder that happens to sit next to the real projects.
    not_a_repo = projects / "not_a_repo"
    not_a_repo.mkdir()
    (not_a_repo / "NEXT.md").write_text("# NEXT\n", encoding="utf-8")

    # local_only — has NEXT.md, IS a repo, but no remote at all (a scratch project they have
    # never pushed anywhere). `_behind` must answer None, not crash and not claim "behind".
    local_only = projects / "local_only"
    local_only.mkdir()
    git(local_only, "init", "-q", "-b", "main")
    (local_only / "NEXT.md").write_text("# NEXT\n", encoding="utf-8")
    git(local_only, "config", "user.email", "t@t.com")
    git(local_only, "config", "user.name", "t")
    (local_only / "f.txt").write_text("x", encoding="utf-8")
    git(local_only, "add", "f.txt")
    git(local_only, "commit", "-q", "-m", "init")

    # ------------------------------------------------------------------------- sibling_repos

    found = rs.sibling_repos(root)
    names = sorted(p.name for p in found)
    check("sibling_repos: excludes root itself, `no_next` (no NEXT.md), `_pusher` and "
          "`not_a_repo` (no .git / no .git respectively)",
          names, sorted(["behind_two", "in_sync", "local_only"]))

    # MAX_SIBLINGS caps the worst case regardless of how big the portfolio gets.
    many = projects / "many"
    many.mkdir()
    for i in range(rs.MAX_SIBLINGS + 5):
        d = many / f"repo{i:02d}"
        d.mkdir()
        (d / ".git").mkdir()               # only its EXISTENCE is checked — no real repo needed
        (d / "NEXT.md").write_text("x", encoding="utf-8")
    capped_root = many / "repo00"           # any entry works; it is excluded from its own list
    capped = rs.sibling_repos(capped_root)
    check(f"sibling_repos: capped at MAX_SIBLINGS ({rs.MAX_SIBLINGS}) even with "
          f"{rs.MAX_SIBLINGS + 5} candidates", len(capped), rs.MAX_SIBLINGS)

    # ------------------------------------------------------------------------------ _behind

    check("_behind: in sync reports 0", rs._behind(in_sync), 0)
    check("_behind: two commits behind reports 2", rs._behind(behind_two), 2)
    check("_behind: no remote at all reports None (not a crash, not 'behind')",
          rs._behind(local_only), None)

    detached = projects / "detached"
    shutil.copytree(in_sync, detached)
    git(detached, "checkout", "-q", "--detach", "HEAD")
    check("_behind: detached HEAD reports None", rs._behind(detached), None)

    missing = projects / "does_not_exist"
    check("_behind: a path with no .git at all reports None, never raises",
          rs._behind(missing), None)

    # ------------------------------------------------------------------- refresh / summary_line

    # Point `state_dir` at a throwaway location under the SAME temp dir, so this test never
    # touches the real `~/.claude/reentry-state/` and two runs never collide.
    state_base = tmp / "state"
    saved_state_dir = reentry_state.state_dir
    rs.state_dir = lambda r: (state_base / "proj").resolve()
    (state_base / "proj").mkdir(parents=True, exist_ok=True)
    try:
        rs.refresh(root)
        cache = json.loads((state_base / "proj" / rs.CACHE_NAME).read_text(encoding="utf-8"))
        behind_names = sorted(b["name"] for b in cache["behind"])
        check("refresh: cache lists only the repo(s) actually behind", behind_names,
              ["behind_two"])

        line = rs.summary_line(root)
        check("summary_line: names the repo and its count",
              line is not None and "behind_two" in line and "2 behind" in line, True)
        check("summary_line: does not mention repos that are not behind",
              "in_sync" in (line or ""), False)

        # Empty cache -> total silence, the common case.
        (state_base / "proj" / rs.CACHE_NAME).write_text(
            json.dumps({"at": 0, "behind": []}), encoding="utf-8")
        check("summary_line: nothing behind -> None (silence)", rs.summary_line(root), None)

        # No cache file at all (first session after install) -> also silence, never an error.
        (state_base / "proj" / rs.CACHE_NAME).unlink()
        check("summary_line: no cache yet -> None (silence)", rs.summary_line(root), None)

        # MAX_NAMED truncation: more behind-repos than the line budget collapse to a count.
        many_behind = [{"name": f"r{i}", "behind": i + 1} for i in range(rs.MAX_NAMED + 3)]
        (state_base / "proj" / rs.CACHE_NAME).write_text(
            json.dumps({"at": 0, "behind": many_behind}), encoding="utf-8")
        line2 = rs.summary_line(root)
        check(f"summary_line: names at most MAX_NAMED ({rs.MAX_NAMED}) then collapses",
              line2 is not None and "… 3 more" in line2, True)
        check("summary_line: states the TRUE total, not just the named ones",
              line2 is not None and str(len(many_behind)) in line2, True)
    finally:
        rs.state_dir = saved_state_dir

    # spawn_refresh must never raise, even against a root with no writable state dir nearby —
    # it is fire-and-forget by contract and this is the one call site that could otherwise
    # crash a session-ending hook.
    threw = False
    try:
        rs.spawn_refresh(root)
    except Exception:
        threw = True
    check("spawn_refresh: never raises", threw, False)

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
