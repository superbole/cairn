#!/usr/bin/env python3
"""cairn's Cursor half stays generated, in lockstep, and wired to files that exist (B57, v1.65.0).

    python plugins/cairn/tools/test_cursor_build.py

WHAT THIS PROTECTS. The Cursor adapter replaced three hand-written copies that had drifted apart
on two machines. Each property below is a way the new arrangement could quietly become a fourth
copy, or stop working, while still looking fine:

  1. The generated rule and manifest are CURRENT (`build_cursor.py --check`), and the Cursor
     version EQUALS the Claude one. A version bump that forgets Cursor fails here -- that test is
     the whole lockstep.
  2. `cursor/hooks.json` is Cursor's schema (v1, flat per-event arrays, camelCase events), and
     every command is exactly `sh "${CURSOR_PLUGIN_ROOT}/hooks/run.sh" <hook>.py --harness cursor`
     naming a hook that exists. No shell operators: measured 2026-09-26, Cursor on Windows runs
     hook commands through PowerShell 5.1, which rejects `||` -- the first version chained
     `python … || python3 …` and every hook died on a parse error. `sh` is on Cursor's hook PATH
     there (it prepends Git's `usr/bin`), and run.sh picks the interpreter, as D31 decided.
  3. The Cursor manifest's explicit paths exist, because an explicit path REPLACES Cursor's
     folder discovery: a typo there silently loads nothing.
  4. Every `cursor/skills/*/SKILL.md` defines `<root>` three directories up, lands on this
     plugin, and every file it names under `<root>` exists.
  5. `harness.normalise` turns each Cursor payload into the Claude shape the hooks read, and
     leaves a Claude payload untouched.
  6. Under Cursor, `dirty_tree_warning` prints nothing on `stop` (Cursor would submit it as a new
     prompt) and leaves the breadcrumb; `staged_review_guard` refuses with a `deny` answer.
  7. `cursor_drift` warns on each stale fixture, stays silent on a current one, and its
     Cursor-changed trigger fires once on a change and never on the first run.

Every case runs against a throwaway CLAUDE_CONFIG_DIR and CAIRN_CURSOR_HOME. Nothing touches
`~/.claude`, `~/.cursor` or the network.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(PLUGIN / "tools"))
NW = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
fails = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


SANDBOX = Path(tempfile.mkdtemp(prefix="cursor-build-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(SANDBOX / "claude")
os.environ["CAIRN_CURSOR_HOME"] = str(SANDBOX / "cursor")
(SANDBOX / "claude").mkdir()
(SANDBOX / "cursor").mkdir()

import build_cursor  # noqa: E402
import harness  # noqa: E402
import cursor_drift  # noqa: E402

print("1. generated artefacts are current, and the versions agree")
check("build_cursor --check: nothing stale", [p.name for p in build_cursor.stale()], [])
claude_v = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text("utf-8"))["version"]
cursor_v = json.loads((PLUGIN / ".cursor-plugin" / "plugin.json").read_text("utf-8"))["version"]
check("Cursor plugin version == Claude plugin version", cursor_v, claude_v)
rule = (PLUGIN / "cursor" / "rules" / "cairn.mdc").read_text("utf-8")
check("the rule is always applied", "\nalwaysApply: true\n" in rule.split("---", 2)[1] + "\n", True)
check("the rule carries the rules text verbatim",
      (PLUGIN / "rules" / "CLAUDE.md").read_text("utf-8").strip() in rule, True)
m = cursor_drift._RULE_VERSION_RE.search(rule[:2000])
check("the rule's GENERATED header names this version", m and m.group(1), claude_v)

print("\n2. cursor/hooks.json is Cursor's shape and every command lands")
hooks = json.loads((PLUGIN / "cursor" / "hooks.json").read_text("utf-8"))
check("schema version 1", hooks.get("version"), 1)
CURSOR_EVENTS = {"sessionStart", "sessionEnd", "preToolUse", "postToolUse", "postToolUseFailure",
                 "subagentStart", "subagentStop", "beforeShellExecution", "afterShellExecution",
                 "beforeMCPExecution", "afterMCPExecution", "beforeReadFile", "afterFileEdit",
                 "beforeSubmitPrompt", "preCompact", "stop", "afterAgentResponse",
                 "afterAgentThought", "workspaceOpen"}
check("every event is a Cursor event", sorted(set(hooks["hooks"]) - CURSOR_EVENTS), [])
for want in ("sessionStart", "beforeSubmitPrompt", "afterFileEdit", "afterShellExecution",
             "beforeShellExecution", "stop", "sessionEnd"):
    check(f"{want} is wired", bool(hooks["hooks"].get(want)), True)
for event, entries in hooks["hooks"].items():
    for entry in entries:
        cmd = entry.get("command", "")
        check(f"{event}: entry is flat (no nested `hooks`)", "hooks" in entry, False)
        m = re.fullmatch(r'sh "\$\{CURSOR_PLUGIN_ROOT\}/hooks/run\.sh" ([a-z_]+\.py) --harness cursor'
                         r'( --json)?', cmd)
        check(f"{event}: the one run.sh form, --harness cursor, nothing else", bool(m), True)
        check(f"{event}: the hook it names exists",
              bool(m) and (HOOKS / m.group(1)).is_file(), True)
        check(f"{event}: no shell operator PowerShell 5.1 would reject",
              any(op in cmd for op in ("||", "&&", ";", "$input")), False)

print("\n3. the Cursor manifest's explicit paths exist")
manifest = json.loads((PLUGIN / ".cursor-plugin" / "plugin.json").read_text("utf-8"))
for key in ("rules", "skills", "hooks"):
    check(f"manifest `{key}` -> {manifest.get(key)} exists",
          bool(manifest.get(key)) and (PLUGIN / manifest[key]).exists(), True)
market = PLUGIN.parents[1] / ".cursor-plugin" / "marketplace.json"
if market.is_file():
    entries = json.loads(market.read_text("utf-8"))["plugins"]
    check("marketplace source resolves to this plugin",
          [(PLUGIN.parents[1] / e["source"]).resolve() == PLUGIN.resolve() for e in entries], [True])

print("\n4. each Cursor skill defines <root> three levels up, and what it names exists")
skills = sorted((PLUGIN / "cursor" / "skills").glob("*/SKILL.md"))
check("the three skills are there", [s.parent.name for s in skills],
      ["cairn-next", "cairn-orient", "cairn-wrap"])
for s in skills:
    text = re.sub(r"\s+", " ", s.read_text("utf-8"))
    check(f"{s.parent.name}: name matches its folder",
          f"name: {s.parent.name}" in s.read_text("utf-8"), True)
    check(f"{s.parent.name}: defines <root> as three directories above",
          "three directories above" in text, True)
    check(f"{s.parent.name}: <root> lands on this plugin",
          (s.parent / ".." / ".." / "..").resolve() == PLUGIN.resolve(), True)
    for ref in re.findall(r"<root>/([A-Za-z0-9_./-]+\.(?:py|md))", s.read_text("utf-8")):
        check(f"{s.parent.name}: <root>/{ref} exists", (PLUGIN / ref).is_file(), True)
orient = (PLUGIN / "cursor" / "skills" / "cairn-orient" / "SKILL.md").read_text("utf-8")
check("cairn-orient auto-invokes (no disable-model-invocation)",
      "disable-model-invocation" in orient, False)
check("cairn-orient passes --no-stdin", "--no-stdin" in orient, True)

print("\n5. harness.normalise")
claude_evt = {"hook_event_name": "PostToolUse", "tool_name": "Edit",
              "tool_input": {"file_path": "/x"}, "session_id": "s"}
check("a Claude payload is returned unchanged", harness.normalise(claude_evt), claude_evt)
n = harness.normalise({"hook_event_name": "afterFileEdit", "file_path": "/r/a.py",
                       "conversation_id": "c1", "cursor_version": "3.19.13",
                       "workspace_roots": ["/r"]})
check("afterFileEdit -> Edit + tool_input.file_path, session from conversation_id, cwd from roots",
      (n["hook_event_name"], n["tool_name"], n["tool_input"], n["session_id"], n["cwd"]),
      ("PostToolUse", "Edit", {"file_path": "/r/a.py"}, "c1", "/r"))
n = harness.normalise({"hook_event_name": "afterShellExecution", "command": "git -C /r status",
                       "cursor_version": "3.19.13"})
check("afterShellExecution -> Bash + tool_input.command",
      (n["tool_name"], n["tool_input"]), ("Bash", {"command": "git -C /r status"}))
n = harness.normalise({"hook_event_name": "postToolUse", "tool_name": "Write",
                       "tool_input": json.dumps({"target_file": "/r/b"}), "cursor_version": "x"})
check("postToolUse Write with a JSON-string input -> Edit + file_path",
      (n["tool_name"], n["tool_input"].get("file_path")), ("Edit", "/r/b"))
os.environ.pop("CURSOR_PROJECT_DIR", None)
n = harness.normalise({"hook_event_name": "beforeShellExecution", "command": "git status", "cwd": "",
                       "cursor_version": "3.19.13", "workspace_roots": ["/C:/work/proj"]})
check("an empty cwd falls back to the workspace root, URI slash stripped (live bug, 2026-09-26)",
      n["cwd"], "C:/work/proj")
check("sessionEnd -> SessionEnd", harness.normalise(
    {"hook_event_name": "sessionEnd", "session_id": "s", "cursor_version": "x"})["hook_event_name"],
    "SessionEnd")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
code = ("import sys; sys.path.insert(0, %r); import harness; print(harness.load_stdin().get('k'))"
        % str(HOOKS))
r = subprocess.run([sys.executable, "-c", code], input=b'\xef\xbb\xbf{"k": "v"}',
                   capture_output=True, env=env, timeout=30, **NW)
check("load_stdin reads a payload behind a UTF-8 BOM (PowerShell 5.1 adds one)",
      r.stdout.decode().strip(), "v")
check("is_cursor: the flag", harness.is_cursor({}, ["x.py", "--harness", "cursor"]), True)
check("is_cursor: the payload alone", harness.is_cursor({"cursor_version": "3"}, ["x.py"]), True)
check("is_cursor: a Claude payload, no flag", harness.is_cursor(claude_evt, ["x.py"]), False)


def run_hook(name, payload, cwd, *args):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd))
    return subprocess.run([sys.executable, str(HOOKS / name), "--harness", "cursor", *args],
                          input=json.dumps(payload), capture_output=True, text=True, cwd=cwd,
                          env=env, timeout=60, encoding="utf-8", errors="replace", **NW)


def git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True, **NW)


print("\n6. hooks behave under Cursor")
repo = SANDBOX / "repo"
repo.mkdir()
git(repo, "init", "-q")
git(repo, "config", "user.email", "t@t.com")
git(repo, "config", "user.name", "t")
(repo / "NEXT.md").write_text("# NEXT\n\n## Queue\n\n1. **x** — [brief](b.md)\n", encoding="utf-8")
git(repo, "add", "NEXT.md")
git(repo, "commit", "-q", "-m", "init")
(repo / "dirty.txt").write_text("x", encoding="utf-8")
r = run_hook("dirty_tree_warning.py", {"hook_event_name": "stop", "status": "completed",
                                       "conversation_id": "c1", "cursor_version": "3.19.13"}, repo)
check("stop under Cursor prints nothing", r.stdout.strip(), "")
import reentry_state  # noqa: E402
crumb = (reentry_state.state_dir(repo) or SANDBOX / "none") / "last_exit.json"
check("stop under Cursor leaves the breadcrumb", crumb.is_file(), True)
if crumb.is_file():
    check("the breadcrumb counts the dirty file", json.loads(crumb.read_text("utf-8"))["dirty"], 1)

(repo / "dirty.txt").write_text("y", encoding="utf-8")
git(repo, "add", "dirty.txt")
r = run_hook("staged_review_guard.py", {"hook_event_name": "beforeShellExecution",
                                        "command": "git commit -m x", "cwd": str(repo),
                                        "cursor_version": "3.19.13"}, repo)
answer = json.loads(r.stdout or "{}")
check("an unread staged diff: Cursor gets permission=deny", answer.get("permission"), "deny")
check("…and exit 0, so the python3 fallback does not re-run it", r.returncode, 0)
r = run_hook("staged_review_guard.py", {"hook_event_name": "beforeShellExecution",
                                        "command": "git status", "cwd": str(repo),
                                        "cursor_version": "3.19.13"}, repo)
check("a harmless git command is allowed silently", (r.stdout.strip(), r.returncode), ("", 0))

r = run_hook("session_orientation.py", {"hook_event_name": "sessionStart", "session_id": "c2",
                                        "cursor_version": "3.19.13"}, repo, "--json")
out = json.loads(r.stdout or "{}")
check("sessionStart --json answers additional_context with the queue",
      "WHERE YOU LEFT OFF" in out.get("additional_context", ""), True)
check("…and never wrote ~/.claude/CLAUDE.md", (SANDBOX / "claude" / "CLAUDE.md").exists(), False)

print("\n7. cursor_drift")
home = SANDBOX / "cursor"
check("a clean Cursor home, first run: silent", cursor_drift.check(None, "3.19.13"), None)
check("same version again: silent", cursor_drift.check(None, "3.19.13"), None)
line = cursor_drift.check(None, "3.21.0") or ""
check("a new Cursor version fires the re-probe line once",
      "3.19.13 → 3.21.0" in line and "cursor/gaps.md" in line, True)
check("…and not again", cursor_drift.check(None, "3.21.0"), None)
check("a skill run with no version keeps the last one", cursor_drift.check(None, ""), None)
(home / "skills-cursor" / "rename-chat").mkdir(parents=True)
cursor_drift.check(None, "3.21.0")                               # first listing recorded
(home / "skills-cursor" / "archive-chat").mkdir()
check("a new built-in skill fires the line",
      "archive-chat" in (cursor_drift.check(None, "3.21.0") or ""), True)

(home / "skills" / "next").mkdir(parents=True)
(home / "skills" / "next" / "SKILL.md").write_text("x", encoding="utf-8")
check("a hand-written ~/.cursor/skills/next is flagged",
      "~/.cursor/skills/next" in (cursor_drift.check(None, "3.21.0") or ""), True)
old = home / "plugins" / "cache" / "superbole" / "cairn" / "4ca78f7" / ".claude-plugin"
old.mkdir(parents=True)
(old / "plugin.json").write_text('{"version": "1.53.4"}', encoding="utf-8")
line = cursor_drift.check(None, "3.21.0") or ""
check("a Claude-format cairn in Cursor's cache is flagged, naming its folder",
      "v1.53.4" in line and "4ca78f7" in line and "delete that folder" in line, True)
(old.parent / ".cursor-plugin").mkdir()
check("…but not once it carries a .cursor-plugin",
      "v1.53.4" in (cursor_drift.check(None, "3.21.0") or ""), False)
import shutil  # noqa: E402
shutil.rmtree(old.parent)
check("…and not once the folder is gone (the cleanup clears it)",
      "v1.53.4" in (cursor_drift.check(None, "3.21.0") or ""), False)

installed = SANDBOX / "claude" / "plugins"
installed.mkdir(parents=True)
(installed / "installed_plugins.json").write_text(json.dumps(
    {"plugins": {"cairn@superbole": [{"version": "1.60.0"}]}}), encoding="utf-8")
check("Claude Code on an older cairn: the mismatch names the Claude update",
      "claude plugin update" in (cursor_drift.check(None, "3.21.0") or ""), True)
(installed / "installed_plugins.json").write_text(json.dumps(
    {"plugins": {"cairn@superbole": [{"version": cursor_v}]}}), encoding="utf-8")
check("the same version in both harnesses: no mismatch line",
      "Claude Code on this machine has" in (cursor_drift.check(None, "3.21.0") or ""), False)

print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + repr(fails)}")
sys.exit(1 if fails else 0)
