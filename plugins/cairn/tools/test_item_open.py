"""End-to-end test for the open-item marker (v1.20.0), in a throwaway git repo.

    python plugins/cairn/tools/test_item_open.py

Shipped because the rules it pins down are JUDGEMENT calls, not obvious ones: every case here
is a decision about when the warning should stay SILENT, and those are exactly the rules a later
session will be tempted to "tighten" without knowing what they cost. See
`skills/next/references/incidents.md` for the reasoning behind each. Needs `git` on PATH and
writes only to a temp directory.

sys.argv[1], if given, is the PLUGIN ROOT (this file's own convention, matching the majority of
`test_*.py` -- see B70) -- not the hooks directory. `hooks/` is appended below.
"""
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

NEXT = """# NEXT — demo

## Queue

1. **First thing** — Opus 5 · high · AFK/Auto
   Brief: [briefs/a.md](briefs/a.md)

2. **Second thing** — Sonnet 5 · medium · AFK/Auto
   Brief: [briefs/b.md](briefs/b.md)

## Watching

_None._

---

Aim: prove the marker works.
"""

root = Path(tempfile.mkdtemp(prefix="orphan-"))
os.environ["CLAUDE_PROJECT_DIR"] = str(root)
os.environ["CLAUDE_CONFIG_DIR"] = str(root.parent / (root.name + "-cfg"))
(root / "NEXT.md").write_text(NEXT, encoding="utf-8")
for a in (("init", "-q"), ("add", "NEXT.md"), ("-c", "user.email=t@t", "-c", "user.name=t",
                                               "commit", "-qm", "init")):
    subprocess.run(("git", *a), cwd=root, capture_output=True, **NW)

import item_open, item_start
from reentry_state import state_dir

fails = []
def check(name, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(name)

def prompt(text, session="s1"):
    """Drive item_start.py exactly as the hook is driven."""
    p = subprocess.run((sys.executable, str(HOOKS / "item_start.py")),
                       input=json.dumps({"prompt": text, "session_id": session,
                                         "hook_event_name": "UserPromptSubmit"}),
                       cwd=root, capture_output=True, text=True, **NW)
    return p.stdout

def orient(session="s2"):
    p = subprocess.run((sys.executable, str(HOOKS / "session_orientation.py")),
                       input=json.dumps({"source": "startup", "session_id": session}),
                       cwd=root, capture_output=True, text=True,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **NW)
    return p.stdout + p.stderr

print("\n1. the writer hook")
check("prints nothing", prompt("do 1"), "")
m = item_open.read(root)
check("marker written for item 1", (m or {}).get("item"), 1)
check("marker carries the title", (m or {}).get("title"), "First thing")

item_open.clear(root)
for junk in ("do 3 of those", "3", "what should I do next?", "/cairn:next", "redo 1",
             "do 9"):
    prompt(junk)
    check("ignored: %r" % junk, item_open.read(root), None)
    item_open.clear(root)

print("\n2. same-session resume never reports itself")
prompt("do 2", session="s1")
check("marker is item 2", item_open.read(root)["item"], 2)
check("same session -> silent", item_open.orphan(root, "s1"), None)
check("marker survives", item_open.read(root) is not None, True)

print("\n3. a new session sees the orphan, in the existing box")
out = orient(session="s2")
check("RELAY FIRST tier", "RELAY FIRST" in out, True)
check("names the box", "DID NOT FINISH CLEANLY" in out, True)
check("names the item", 'Item 2 "Second thing" was started' in out, True)
check("offers resume/close", "resume it" in out and "close it" in out, True)

print("\n4. second unresolved session degrades to ONE line")
out2 = orient(session="s3")
check("still flagged", "STILL open since" in out2, True)
check("no longer the full sentence", "was started" in out2, False)
check("full block carried the explanation", "only in that session's transcript" in out, True)
check("one-liner drops the explanation", "only in that session's transcript" in out2, False)

print("\n5. resolution — the item leaves the Queue")
(root / "NEXT.md").write_text(NEXT.replace(
    "2. **Second thing** — Sonnet 5 · medium · AFK/Auto\n   Brief: [briefs/b.md](briefs/b.md)\n",
    ""), encoding="utf-8")
check("orphan() is silent", item_open.orphan(root, "s4"), None)
check("marker cleared", item_open.read(root), None)
out3 = orient(session="s4")
check("orientation says nothing about it", "Item 2" in out3, False)

print("\n6. resolution — a wrap runs after the item was opened")
(root / "NEXT.md").write_text(NEXT, encoding="utf-8")
prompt("do 1", session="s5")
time.sleep(0.05)
(root / ".claude").mkdir(exist_ok=True)
(root / ".claude" / ".last_wrap").write_text("deadbeef\n", encoding="utf-8")
check("silent after a wrap", item_open.orphan(root, "s6"), None)
check("marker cleared", item_open.read(root), None)

print("\n7. an item opened AFTER the wrap is still an orphan")
prompt("do 1", session="s7")
r = item_open.orphan(root, "s8")
check("reported", r is not None and r[1], True)

print("\n8. a title reworded out of recognition goes quiet, never nags")
(root / "NEXT.md").write_text(NEXT.replace("**First thing**", "**Something else entirely**"),
                             encoding="utf-8")
os.utime(root / ".claude" / ".last_wrap", (0, 0))     # wrap is old, so only the title decides
check("silent", item_open.orphan(root, "s9"), None)

print("\n9. no NEXT.md item -> the writer refuses to invent one")
(root / "NEXT.md").write_text("# NEXT\n\n## Queue\n\n_None._\n", encoding="utf-8")
check("stamp refused", item_open.stamp(root, 1, "s10"), None)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
