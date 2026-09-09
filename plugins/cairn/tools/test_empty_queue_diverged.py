"""B71 -- an empty Queue must not swallow THIS repo's own divergence banner.

    python plugins/cairn/tools/test_empty_queue_diverged.py

THE DEFECT. `session_orientation.py`'s "nothing queued here" early return reads:

    if (not nxt and not items and not due and not decisions and not left_behind
            and not siblings_behind):

`diverged` was named in neither this guard nor the inner `if (always_on or _installed or ...)`
print condition right below it, so a project with an EMPTY Queue had its own "you are N commits
behind origin" banner computed correctly and then dropped on the floor -- total silence, even
though `_divergence_warning` ran, fetched, and returned a real string. An empty Queue is exactly
the state a checkout is most likely to be stale in (nobody has worked there lately), so the
banner disappeared in precisely the case it exists for.

NO NETWORK, NO REAL REPO. Every repo here is a fresh temp-dir fixture with a LOCAL bare `origin`
(same pattern as `test_repo_sweep.py`) -- nothing here touches `~/Projects` or any of the user's
real checkouts. `git fetch` only ever runs against a bare repo this file created on the same
disk.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}
_TEXT = {"encoding": "utf-8", "errors": "replace"}   # the hook's banner carries a non-ASCII
                                                      # warning glyph; Windows' default locale
                                                      # codec cannot always decode it back.

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
    # Force the branch name regardless of this machine's `init.defaultBranch` -- see
    # test_repo_sweep.py's own note on why, exactly the same reasoning applies here.
    git(p, "symbolic-ref", "HEAD", "refs/heads/main")
    return p


def make_clone(base, origin, name):
    p = base / name
    git(base, "clone", "-q", str(origin), str(p))
    git(p, "config", "user.email", "t@t.com")
    git(p, "config", "user.name", "t")
    return p


def commit_and_push(repo, fname):
    (repo / fname).write_text("x", encoding="utf-8")
    git(repo, "add", fname)
    git(repo, "commit", "-q", "-m", f"add {fname}")
    git(repo, "push", "-q", "origin", "HEAD:main")


EMPTY_QUEUE_NEXT = (
    "# NEXT — test\n\n## Queue\n\n## Watching\n\n---\n\nAim: test.\n"
)


def run_hook(repo):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    env["CLAUDE_CONFIG_DIR"] = str(repo.parent / "cfg")   # throwaway, never the real ~/.claude
    return subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                          input='{"source":"startup"}', capture_output=True, text=True,
                          **_TEXT, env=env, cwd=str(repo), **NW)


tmp = Path(tempfile.mkdtemp(prefix="empty-queue-diverged-"))

print("1. an empty Queue, genuinely BEHIND a real origin -- the banner must still print")

origin = make_bare(tmp, "origin.git")
behind = make_clone(tmp, origin, "behind")
(behind / "NEXT.md").write_text(EMPTY_QUEUE_NEXT, encoding="utf-8")
commit_and_push(behind, "seed.txt")

# Move origin on without `behind` knowing, via a separate pushing clone -- same technique as
# test_repo_sweep.py's `behind_two`.
pusher = make_clone(tmp, origin, "_pusher")
commit_and_push(pusher, "second.txt")

done = run_hook(behind)
check("exits 0", done.returncode, 0)
check("the divergence banner reaches stdout despite the empty Queue",
      "BEHIND origin" in done.stdout, True)
check("it is presented as the bordered warning box, not a bare line",
      "!" * 10 in done.stdout, True)

print("\n2. an empty Queue, genuinely in sync -- still silent (no false alarm introduced)")

in_sync = make_clone(tmp, origin, "in_sync")
(in_sync / "NEXT.md").write_text(EMPTY_QUEUE_NEXT, encoding="utf-8")
# `in_sync` is cloned AFTER `_pusher`'s commit, so it already has everything origin has.

done2 = run_hook(in_sync)
check("exits 0", done2.returncode, 0)
check("nothing at all is printed -- an empty Queue with no divergence stays silent",
      done2.stdout.strip(), "")

print("\n3. an empty Queue, no remote at all -- still silent (the pre-existing, unaffected case)")

local_only = tmp / "local_only"
local_only.mkdir()
git(local_only, "init", "-q", "-b", "main")
git(local_only, "config", "user.email", "t@t.com")
git(local_only, "config", "user.name", "t")
(local_only / "NEXT.md").write_text(EMPTY_QUEUE_NEXT, encoding="utf-8")
(local_only / "f.txt").write_text("x", encoding="utf-8")
git(local_only, "add", "f.txt")
git(local_only, "commit", "-q", "-m", "init")

done3 = run_hook(local_only)
check("exits 0", done3.returncode, 0)
check("no origin to compare against -> silent, same as before this fix",
      done3.stdout.strip(), "")

print("\n4. a NON-empty Queue, behind origin -- unaffected regression check (worked before too)")

behind_with_queue = make_clone(tmp, origin, "behind_with_queue")
(behind_with_queue / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto\n\n"
    "## Watching\n\n---\n\nAim: test.\n", encoding="utf-8")
commit_and_push(behind_with_queue, "seed-s4.txt")   # NOT seed.txt: origin already carries that exact file and content from
                                                    # section 1, so the commit would have nothing to stage.
# A FRESH clone: `pusher` is stale now that behind_with_queue has pushed, so reusing
# it here fails with a non-fast-forward rather than advancing origin.
pusher4 = make_clone(tmp, origin, "_pusher4")
commit_and_push(pusher4, "third.txt")   # origin moves on again

done4 = run_hook(behind_with_queue)
check("exits 0", done4.returncode, 0)
check("the banner still prints with a real queue present (pre-existing path, unchanged)",
      "BEHIND origin" in done4.stdout, True)
check("and the queue itself still renders", "Something to do" in done4.stdout, True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
