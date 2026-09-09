#!/usr/bin/env python3
"""Every production `git` capture decodes as UTF-8, never the Windows locale codec.

WHY THIS EXISTS (2026-09-06). `subprocess.run(..., text=True)` with no `encoding=`
decodes with the locale codec -- cp1252 on these machines. Git output in this system is
routinely UTF-8: every commit subject in this repo carries an em-dash and `BACKLOG.md` is
full of middots. The decode then raised UnicodeDecodeError inside subprocess's reader
THREAD, so the exception never reached the caller's `try`; it simply left `r.stdout` as
None with `returncode` still 0, and the caller crashed on `None.strip()` one frame later.

Found by the orchestrator exercising B80's `_origin_floor()` against the REAL repo. Every
one of that lane's own fixtures was ASCII, so the whole suite passed while the feature
could not run on the machine it shipped to. That is the shape worth a permanent test: the
fixtures agreed with each other and disagreed with reality.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
import reentry_state                                                       # noqa: E402

NW = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
fails = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def run(args, cwd):
    return subprocess.run(("git", *args), cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", **NW)


# An em-dash, a middot and a non-Latin-1 character that cp1252 CANNOT represent at all.
SUBJECT = "feat: em-dash — middot · and 中文"

print("1. a commit subject with non-ASCII text round-trips through reentry_state.git()")
root = Path(tempfile.mkdtemp(prefix="git-encoding-"))
run(("-c", "init.defaultBranch=main", "init", "-q"), root)
run(("config", "user.email", "t@t"), root)
run(("config", "user.name", "t"), root)
msg = root / "msg.txt"
msg.write_text(SUBJECT + "\n", encoding="utf-8")
r = run(("commit", "-q", "--allow-empty", "-F", str(msg)), root)
assert r.returncode == 0, r.stderr

got = reentry_state.git(root, "log", "-1", "--format=%s")
check("subject decodes to the exact original", got, SUBJECT)
check("no U+FFFD replacement characters", "�" in (got or ""), False)
check("returns a str, not None (the cp1252 failure mode)", isinstance(got, str), True)

print("\n2. a tracked FILE with non-ASCII content reads back through `git show`")
f = root / "BACKLOG.md"
f.write_text("# BACKLOG — x\n\n## B12. title · body\n", encoding="utf-8")
run(("add", "BACKLOG.md"), root)
run(("commit", "-q", "-m", "add backlog"), root)
shown = reentry_state.git(root, "show", "HEAD:BACKLOG.md", raw=True)
check("file content decodes", shown, "# BACKLOG — x\n\n## B12. title · body")
check("no U+FFFD in file content", "�" in (shown or ""), False)

print("\n3. next_id()'s origin floor survives a non-ASCII BACKLOG.md on origin "
      "(the exact crash this test was written for)")
import backlog_file                                                        # noqa: E402
bare = Path(tempfile.mkdtemp(prefix="git-encoding-bare-"))
run(("-c", "init.defaultBranch=main", "init", "-q", "--bare"), bare)
run(("remote", "add", "origin", str(bare)), root)
run(("push", "-q", "origin", "HEAD:main"), root)
run(("fetch", "-q", "origin"), root)
run(("branch", "--set-upstream-to=origin/main", "main"), root)
check("origin floor reads B12 through the non-ASCII file",
      backlog_file._origin_floor(root), 12)
check("next_id() does not raise and clears the floor",
      backlog_file.next_id(root) > 12, True)

print("\n4. no production subprocess capture is left on the locale codec")
prod = [p for d in ("hooks", "tools") for p in (HOOKS.parent / d).glob("*.py")
        if not p.name.startswith("test_")]
offenders = []
for p in prod:
    for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if "text=True" in ln and "encoding=" not in ln:
            # the encoding may sit on the following line of the same call
            nxt = p.read_text(encoding="utf-8").splitlines()[i:i + 1]
            if not nxt or "encoding=" not in nxt[0]:
                offenders.append(f"{p.name}:{i}")
check("every text=True capture names an encoding", offenders, [])

# ...and names it ONCE. Adding `encoding=` to a call that already carried it on its
# continuation line is a `keyword argument repeated` SyntaxError -- a whole module that
# no longer imports, which a per-line grep for the missing case cannot see. Done exactly
# that way on 2026-09-06 while fixing the bug above, in three files at once.
def _call_text(ls, i):
    """The `subprocess.run(...)` call starting on line i, to its closing paren."""
    depth, out = 0, []
    for ln in ls[i:i + 12]:
        out.append(ln)
        depth += ln.count("(") - ln.count(")")
        if depth <= 0 and out:
            break
    return "".join(out)


dupes = []
for p_ in prod:
    ls = p_.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(ls):
        if "subprocess.run" in ln and _call_text(ls, i).count("encoding=") > 1:
            dupes.append(f"{p_.name}:{i + 1}")
check("no call names an encoding twice", dupes, [])

import py_compile
broken = []
for p_ in prod:
    try:
        py_compile.compile(str(p_), doraise=True, quiet=2)
    except Exception as e:
        broken.append(f"{p_.name}: {type(e).__name__}")
check("every production module still compiles", broken, [])

print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + repr(fails)}")
sys.exit(1 if fails else 0)
