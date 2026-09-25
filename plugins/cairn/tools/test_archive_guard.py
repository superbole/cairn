"""Coverage for `archive_guard.py` -- refuse an agent-initiated archive while `CAIRN OPEN` (B64).

    python plugins/cairn/tools/test_archive_guard.py

WHAT THIS FILE IS DEFENDING. The guard is only worth having if it blocks exactly one thing: a
session archiving ITSELF while its own wrap verdict is measured `OPEN`. Both directions of error
are defects:

  * too loose -- the incident itself (SET, then two more commits, then an archive) must DENY,
    which means the imported verdict has to see "HEAD moved after SET" (section 3);
  * too tight -- UNKNOWN, another session's id, a project outside the system, a root with no
    baseline for this session, or any error must ALLOW, because a guard that cries wolf teaches
    people to discount the one that does not (sections 4-7).

Runs entirely against throwaway git repos under `tempfile.mkdtemp()`, with `CLAUDE_CONFIG_DIR`,
`CLAUDE_PROJECT_DIR` and `CLAUDE_CODE_SESSION_ID` pointed at fixtures -- never the real repo, the
real `~/.claude/`, or this session's own id. Needs `git` on PATH.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(sys.argv[1] if len(sys.argv) > 1
             else Path(__file__).resolve().parent.parent / "hooks").resolve()
sys.path.insert(0, str(HOOKS))
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

# Set BEFORE importing anything that resolves a state dir: `state_dir()` falls back to
# `Path.home()/".claude"` when this is unset (B74).
CFG = Path(tempfile.mkdtemp(prefix="cairn-cfg-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(CFG)
SESSION = "test-session-archive-guard"
os.environ["CLAUDE_CODE_SESSION_ID"] = SESSION
os.environ.pop("CLAUDE_PROJECT_DIR", None)

import archive_guard                                         # noqa: E402
import wrap_receipt                                          # noqa: E402

GUARD = HOOKS / "archive_guard.py"
RUN_SH = HOOKS / "run.sh"
TOOL = "mcp__ccd_session_mgmt__archive_session"
fails = []
made = []


def check(label, got, want=True):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def run(root, *args):
    subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=30, **NW)


NEXT_MD = """# NEXT -- fixture

## Queue

1. **A thing to do** -- Opus 5 · high · HITL/Auto
   Brief: [brief](briefs/thing.md)
"""


def head_of(root):
    return subprocess.run(("git", "rev-parse", "HEAD"), cwd=root, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=30,
                          **NW).stdout.strip()


def stamp_marker(root):
    (root / ".claude" / ".last_wrap").write_text(head_of(root) + "\n", encoding="utf-8")


def commit(root, message="more"):
    run(root, "git", "add", "-A")
    run(root, "git", "commit", "-qm", message)


def new_repo(name, parent=None, opted_in=True):
    root = Path(tempfile.mkdtemp(prefix="cairn-ag-%s-" % name, dir=parent))
    made.append(root)
    (root / "briefs").mkdir()
    (root / ".claude").mkdir()
    (root / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (root / "briefs" / "thing.md").write_text("brief\n", encoding="utf-8")
    if opted_in:
        (root / "NEXT.md").write_text(NEXT_MD, encoding="utf-8")
    (root / "INBOX.md").write_text("# INBOX\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# CHANGELOG\n", encoding="utf-8")
    run(root, "git", "init", "-q")
    run(root, "git", "config", "user.email", "t@example.com")
    run(root, "git", "config", "user.name", "T")
    commit(root, "init")
    stamp_marker(root)
    return root


def do_wrap(root):
    (root / "CHANGELOG.md").write_text("# CHANGELOG\n\n## 2026-09-25\n\nDid a thing.\n",
                                       encoding="utf-8")
    (root / "NEXT.md").write_text(NEXT_MD + "\nrewritten\n", encoding="utf-8")
    commit(root, "chore: wrap")
    stamp_marker(root)


def do_work(root, text="work\n"):
    """A commit with no wrap after it -- the shape of the incident's two extra commits."""
    with open(root / "code.txt", "a", encoding="utf-8") as fh:
        fh.write(text)
    commit(root, "feat: more work")


def payload(root, target="self", session=SESSION, tool=TOOL, cwd=None):
    body = {"hook_event_name": "PreToolUse", "tool_name": tool,
            "cwd": str(cwd or root), "tool_input": {}}
    if target is not None:
        body["tool_input"]["session_id"] = target
    if session is not None:
        body["session_id"] = session
    return body


def guard(root, body, raw=None, via_run_sh=False):
    """Run the hook as Claude Code would: a subprocess, JSON on stdin, env pointed at fixtures."""
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(CFG), "CLAUDE_PROJECT_DIR": str(root),
           "CLAUDE_CODE_SESSION_ID": SESSION}
    stdin = raw if raw is not None else json.dumps(body)
    args = (["sh", str(RUN_SH), "archive_guard.py"] if via_run_sh
            else [sys.executable, str(GUARD)])
    if via_run_sh:
        env["CAIRN_PYTHON"] = sys.executable
        env["CLAUDE_PLUGIN_ROOT"] = str(HOOKS.parent)
    return subprocess.run(args, input=stdin, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60, **NW)


def verdict_of(root):
    base = wrap_receipt.baseline(root, SESSION)
    attrib = wrap_receipt.attribution(root, base)
    st = wrap_receipt.steps(root, base, attrib)
    return wrap_receipt.verdict(root, base, st, attrib)


print("\n1. OPEN denies")
r1 = new_repo("open")
wrap_receipt.stamp_baseline(r1, SESSION)
do_work(r1)
check("fixture really reads OPEN", verdict_of(r1)[0], "OPEN")
p = guard(r1, payload(r1))
check("exit 2 (deny)", p.returncode, 2)
check("names the verdict", "CAIRN OPEN" in p.stderr)
check("names the wrap command", "/cairn:wrap" in p.stderr)
check("lists a missing step", "! " in p.stderr)
check("names the sidebar escape hatch", "sidebar" in p.stderr)
p = guard(r1, payload(r1, target=SESSION))
check("the caller's own id spelled out is still self -> deny", p.returncode, 2)
r1e = new_repo("encoding")
wrap_receipt.stamp_baseline(r1e, SESSION)
(r1e / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")   # dirty, marker inherited
reasons_e = verdict_of(r1e)[1]
check("fixture has a non-ASCII reason (the inherited-marker em-dash)",
      any(not r.isascii() for r in reasons_e))
env_ascii = os.environ.get("PYTHONIOENCODING")
os.environ["PYTHONIOENCODING"] = "ascii"
try:
    p = guard(r1e, payload(r1e))
finally:
    if env_ascii is None:
        os.environ.pop("PYTHONIOENCODING", None)
    else:
        os.environ["PYTHONIOENCODING"] = env_ascii
check("an ASCII-only stderr cannot turn the deny into an allow", p.returncode, 2)
check("...and the refusal still gets written", "CAIRN OPEN" in p.stderr)
if shutil.which("sh"):
    p = guard(r1, payload(r1), via_run_sh=True)
    check("through run.sh, the exit 2 reaches Claude Code unchanged", p.returncode, 2)
else:
    print("  skip no `sh` on PATH, run.sh path not exercised")

print("\n2. SET and NOT DUE allow, silently")
r2 = new_repo("set")
wrap_receipt.stamp_baseline(r2, SESSION)
do_wrap(r2)
check("fixture really reads SET", verdict_of(r2)[0], "SET")
p = guard(r2, payload(r2))
check("SET: exit 0", p.returncode, 0)
check("SET: nothing on stdout or stderr", (p.stdout, p.stderr), ("", ""))
r2b = new_repo("notdue")
wrap_receipt.stamp_baseline(r2b, SESSION)
check("fixture really reads NOT DUE", verdict_of(r2b)[0], "NOT DUE")
p = guard(r2b, payload(r2b))
check("NOT DUE: exit 0, silent", (p.returncode, p.stdout, p.stderr), (0, "", ""))

print("\n3. SET followed by a new commit denies (the 2026-09-25 incident)")
r3 = new_repo("incident")
wrap_receipt.stamp_baseline(r3, SESSION)
do_wrap(r3)
body = wrap_receipt.record(r3, SESSION)
check("the wrap recorded CAIRN SET", body["verdict"], "SET")
check("archive right after the wrap is allowed", guard(r3, payload(r3)).returncode, 0)
do_work(r3, "one\n")
do_work(r3, "two\n")
state, reasons = verdict_of(r3)
check("--check's verdict() reads OPEN once HEAD moves past the receipt", state, "OPEN")
check("...because the marker no longer names HEAD",
      any(r.startswith("marker:") for r in reasons))
line = wrap_receipt.orientation_line(r3) or ""
check("orientation still says 'but HEAD has moved'", "but HEAD has moved" in line)
p = guard(r3, payload(r3))
check("so the archive is denied", p.returncode, 2)
check("and the refusal says commits after a wrap are not covered",
      "not covered" in p.stderr)

print("\n4. UNKNOWN allows, with one line")
r4 = new_repo("unknown")
do_work(r4)                          # marker now stale -- and no baseline for this session
check("no baseline for this session", wrap_receipt.baseline(r4, SESSION), None)
check("--check alone would say OPEN here (stale marker, no baseline)", verdict_of(r4)[0], "OPEN")
p = guard(r4, payload(r4))
check("guard allows: no baseline means it did not measure THIS session", p.returncode, 0)
note = json.loads(p.stdout or "{}").get("systemMessage", "")
check("one line to the user naming UNKNOWN", "CAIRN UNKNOWN" in note and "\n" not in note)
check("nothing on stderr", p.stderr, "")
p = guard(r4, payload(r4, session=None))
check("no session id anywhere in the payload -> env fallback, still allows", p.returncode, 0)

print("\n5. An error, or input it cannot read, allows")
p = guard(r1, None, raw="{not json")
check("unparseable stdin: exit 0", (p.returncode, p.stderr), (0, ""))
p = guard(r1, None, raw="")
check("empty stdin: exit 0", p.returncode, 0)
p = guard(r1, None, raw='["a list"]')
check("a JSON non-object: exit 0", p.returncode, 0)
p = guard(r1, {"tool_name": TOOL, "tool_input": "self", "session_id": SESSION})
check("tool_input not an object: exit 0", p.returncode, 0)
real_verdict = wrap_receipt.verdict


def boom(*a, **k):
    raise RuntimeError("simulated")


wrap_receipt.verdict = boom
os.environ["CLAUDE_PROJECT_DIR"] = str(r1)
try:
    code, err, out = archive_guard.decide(payload(r1))
finally:
    wrap_receipt.verdict = real_verdict
    os.environ.pop("CLAUDE_PROJECT_DIR", None)
check("verdict() raising: allow, silently", (code, err, out), (0, "", ""))

print("\n6. Another session's id, or no target, allows")
p = guard(r1, payload(r1, target="some-other-session-id"))
check("another session's id on an OPEN project: allow", (p.returncode, p.stderr), (0, ""))
p = guard(r1, payload(r1, target=None))
check("no session_id in tool_input: allow", p.returncode, 0)
p = guard(r1, payload(r1, tool="mcp__ccd_session_mgmt__list_sessions"))
check("a different tool entirely: allow", p.returncode, 0)

print("\n7. Which project it judges")
r7 = new_repo("outside", opted_in=False)
wrap_receipt.stamp_baseline(r7, SESSION)
do_work(r7)
p = guard(r7, payload(r7))
check("a project with no NEXT.md: allow, silently", (p.returncode, p.stdout, p.stderr),
      (0, "", ""))
p = guard(r2, payload(r2, cwd=r1))
check("project dir SET but the session cd-ed into an OPEN repo: deny", p.returncode, 2)
check("...naming the OPEN repo", r1.name in p.stderr)
parent = Path(tempfile.mkdtemp(prefix="cairn-ag-parent-"))
made.append(parent)
child = new_repo("child", parent=str(parent))
wrap_receipt.stamp_baseline(child, SESSION)
do_work(child)
p = guard(parent, payload(parent))
check("parent-directory session, OPEN child with this session's baseline: deny",
      p.returncode, 2)
quiet = new_repo("quietchild", parent=str(parent))
p = guard(parent, payload(parent, cwd=parent))
check("...and a child without this session's baseline does not add a block of its own",
      quiet.name in p.stderr, False)

for d in made:
    shutil.rmtree(d, ignore_errors=True)
shutil.rmtree(CFG, ignore_errors=True)

print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + repr(fails)}")
sys.exit(1 if fails else 0)
