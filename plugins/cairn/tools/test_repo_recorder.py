"""End-to-end test for the touched-repo recorder (v1.25.0), in throwaway git repos.

    python plugins/cairn/tools/test_repo_recorder.py

Same reasoning as `test_item_open.py`: every case here is a decision about when the
recorder should stay SILENT, and those are the rules a later session will be tempted to
"tighten" without knowing what they cost. The load-bearing ones -- a write inside the
project is not recorded, a file in no git repo is ignored, a malformed payload exits 0 --
all look like omissions from the outside. See `skills/wrap/references/incidents.md`.

Drives `repo_recorder.py` as a subprocess with real `PostToolUse` payloads, so a mistake
in the hook's own argument handling is caught, not just in the module it calls. Needs
`git` on PATH and writes only to a temp directory.

sys.argv[1], if given, is the PLUGIN ROOT (this file's own convention, matching the majority of
`test_*.py` -- see B70) -- not the hooks directory. `hooks/` is appended below.
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS))
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

base = Path(tempfile.mkdtemp(prefix="touched-"))
root = base / "project"                       # the session's own project
sibling = base / "sibling"                    # a repo a subagent writes into
plain = base / "notarepo"                     # an ordinary folder, no git anywhere
for d in (root, sibling, plain):
    d.mkdir(parents=True)
for repo in (root, sibling):
    subprocess.run(("git", "init", "-q"), cwd=repo, capture_output=True, **NW)

os.environ["CLAUDE_PROJECT_DIR"] = str(root)
os.environ["CLAUDE_CONFIG_DIR"] = str(base / "cfg")

import touched_repos                                                    # noqa: E402

fails = []
def check(name, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(name)

def fire(file_path, session="s1", agent=None, tool="Write", **extra):
    """Drive repo_recorder.py exactly as the PostToolUse hook is driven."""
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool,
               "session_id": session, "agent_id": agent, "cwd": str(root),
               "tool_input": {"file_path": str(file_path)}}
    payload.update(extra)
    p = subprocess.run((sys.executable, str(HOOKS / "repo_recorder.py")),
                       input=json.dumps(payload), cwd=str(root),
                       capture_output=True, text=True, **NW)
    return p

def repos(**kw):
    return [p.name for p in touched_repos.touched(root, **kw)]

print("\n1. the recorder writes nothing to the agent's context, ever")
p = fire(sibling / "a.txt")
check("stdout empty", p.stdout, "")
check("exit 0", p.returncode, 0)

print("\n2. what is and is not recorded")
check("a sibling repo IS recorded", repos(since=0), ["sibling"])
fire(root / "own.txt")
check("a write inside the project is NOT recorded", repos(since=0), ["sibling"])
fire(plain / "loose.txt")
check("a file in no git repo is ignored", repos(since=0), ["sibling"])

print("\n3. a subagent's write in a sibling repo is recorded, and marked as one")
second = base / "second"
second.mkdir()
subprocess.run(("git", "init", "-q"), cwd=second, capture_output=True, **NW)
fire(second / "b.txt", agent="ac1b6349d61b1e8a4", tool="Edit")
check("recorded", repos(since=0), ["sibling", "second"])
rec = [r for r in touched_repos.read_records(root) if r["repo"].endswith("second")][0]
check("carries the agent id", rec["agent"], "ac1b6349d61b1e8a4")
check("carries the tool", rec["tool"], "Edit")

print("\n4. repeats do not grow the log, a new session does")
before = len(touched_repos.read_records(root))
for _ in range(5):
    fire(sibling / "a.txt")
    fire(sibling / "c.txt")               # a different file in the SAME repo
check("five more writes, no new lines", len(touched_repos.read_records(root)), before)
fire(sibling / "a.txt", session="s2")
check("a second session appends once", len(touched_repos.read_records(root)), before + 1)
check("but the repo list is still deduped", repos(since=0), ["sibling", "second"])

print("\n5. malformed and hostile payloads never fail the tool call")
for bad in ('', 'not json at all', '{}', '[]', '{"tool_input": null}',
            '{"tool_input": {}}', '{"tool_input": {"file_path": null}}',
            '{"tool_input": {"file_path": ""}}',
            '{"tool_input": {"file_path": 12345}}'):
    q = subprocess.run((sys.executable, str(HOOKS / "repo_recorder.py")),
                       input=bad, cwd=str(root), capture_output=True, text=True, **NW)
    check("exit 0 and silent on %r" % (bad[:28] or "<empty>"),
          (q.returncode, q.stdout), (0, ""))
check("nothing was recorded by any of them", repos(since=0), ["sibling", "second"])

print("\n6. NotebookEdit uses a different key and is still seen")
third = base / "third"
third.mkdir()
subprocess.run(("git", "init", "-q"), cwd=third, capture_output=True, **NW)
q = subprocess.run((sys.executable, str(HOOKS / "repo_recorder.py")),
                   input=json.dumps({"hook_event_name": "PostToolUse",
                                     "tool_name": "NotebookEdit", "session_id": "s1",
                                     "tool_input": {"notebook_path": str(third / "n.ipynb")}}),
                   cwd=str(root), capture_output=True, text=True, **NW)
check("recorded via notebook_path", repos(since=0), ["sibling", "second", "third"])

print("\n7. the wrap marker sets the window -- a wrap hides what came before it")
(root / ".claude").mkdir(exist_ok=True)
(root / ".claude" / ".last_wrap").write_text("deadbeef\n", encoding="utf-8")
check("everything recorded before the wrap drops out", repos(), [])
time.sleep(0.05)
fire(sibling / "after.txt", session="s3")
check("a write after the wrap is reported", repos(), ["sibling"])

print("\n8. a recorded repo that no longer exists is dropped, not reported")
import shutil
shutil.rmtree(second)
check("gone from the list", repos(since=0), ["sibling", "third"])

print("\n9. check_repos.py runs with NO arguments off the record")
out = subprocess.run((sys.executable, str(TOOLS / "check_repos.py")),
                     cwd=str(root), capture_output=True, text=True,
                     env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **NW)
check("names the sibling", "sibling" in out.stdout, True)
check("reports it as not landed", "[!!]" in out.stdout or "have work" in out.stdout, True)
check("says the recorder found it", "found by the recorder" in out.stdout, True)
check("does not check the project itself", "project" in out.stdout.replace(str(base), ""),
      False)

print("\n10. --no-recorded degrades to the v1.24.0 behaviour, never to silence")
out2 = subprocess.run((sys.executable, str(TOOLS / "check_repos.py"), "--no-recorded"),
                      cwd=str(root), capture_output=True, text=True,
                      env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **NW)
check("says there is no record", "No record" in out2.stdout, True)
check("does NOT claim that as a clean bill of health",
      "clean" not in out2.stdout.lower(), True)
check("and says how to get a list anyway", "--known" in out2.stdout, True)
out3 = subprocess.run((sys.executable, str(TOOLS / "check_repos.py"), str(third)),
                      cwd=str(root), capture_output=True, text=True,
                      env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **NW)
check("a named path is still checked", "third" in out3.stdout, True)
check("and the record is added to it", "sibling" in out3.stdout, True)

print("\n11. B39 -- Bash/PowerShell commands are now matched, as a best-effort GUESS")
fourth = base / "fourth"
fourth.mkdir()
subprocess.run(("git", "init", "-q"), cwd=fourth, capture_output=True, **NW)
touched_repos_before = repos(since=0)

print("  11a. a leading `cd <repo> && ...`")
fire(fourth / "unused-for-cd-case.txt",   # placeholder arg, not read by this call shape
     session="bash1", tool="Bash",
     tool_input={"command": "cd \"%s\" && sed -i 's/x/y/' notes.txt" % fourth})
check("the cd target is recorded", "fourth" in repos(since=0), True)

print("  11b. a heredoc naming an absolute path directly (no cd at all)")
fifth = base / "fifth"
fifth.mkdir()
subprocess.run(("git", "init", "-q"), cwd=fifth, capture_output=True, **NW)
heredoc_cmd = "cat > \"%s\" << 'EOF'\nsome content, not a path\nEOF\n" % (fifth / "n.txt")
fire(fifth / "unused.txt", session="bash2", tool="Bash", tool_input={"command": heredoc_cmd})
check("the heredoc's absolute target is recorded", "fifth" in repos(since=0), True)

print("  11c. a PowerShell command is matched the same way")
sixth = base / "sixth"
sixth.mkdir()
subprocess.run(("git", "init", "-q"), cwd=sixth, capture_output=True, **NW)
fire(sixth / "unused.txt", session="ps1", tool="PowerShell",
     tool_input={"command": "Set-Content -Path \"%s\" -Value hi" % (sixth / "n.txt")})
check("the PowerShell target is recorded", "sixth" in repos(since=0), True)

print("  11d. a Bash command with no path-shaped token at all records nothing new")
before_count = len(touched_repos.read_records(root))
fire(fourth / "unused2.txt", session="bash3", tool="Bash",
     tool_input={"command": "echo hello world"})
check("no new line for a pathless command",
      len(touched_repos.read_records(root)), before_count)

print("  11e. Edit/Write are unaffected -- still exact, never regex-guessed")
seventh = base / "seventh"
seventh.mkdir()
subprocess.run(("git", "init", "-q"), cwd=seventh, capture_output=True, **NW)
fire(seventh / "a.txt", session="edit1", tool="Edit")
check("still recorded via the structured path, as before", "seventh" in repos(since=0), True)

print("  11f. a malformed/non-string `command` on a Bash call never raises")
q = subprocess.run((sys.executable, str(HOOKS / "repo_recorder.py")),
                   input=json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                     "session_id": "bash4", "tool_input": {"command": 12345}}),
                   cwd=str(root), capture_output=True, text=True, **NW)
check("exit 0 and silent on a non-string command", (q.returncode, q.stdout), (0, ""))

print("\n12. B67 -- check_repos.py can silently ask the WRONG project; B72 (v1.39.0) fixes the")
print("    common case (a real Claude Code session) and leaves a narrower, still-honest residual")
eighth = base / "eighth"          # this session's own project, per CLAUDE_PROJECT_DIR
sibling2 = base / "sibling2"      # the repo it writes into via Edit (a structured write)
for d in (eighth, sibling2):
    d.mkdir()
    subprocess.run(("git", "init", "-q"), cwd=d, capture_output=True, **NW)
cfg2 = base / "cfg2"
payload = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "session_id": "b67",
           "agent_id": None, "cwd": str(eighth),
           "tool_input": {"file_path": str(sibling2 / "INBOX.md")}}
# Hook-shaped: CLAUDE_PROJECT_DIR set, exactly as Claude Code exports it to a real
# PostToolUse hook. Since B72, `project_root()` ALSO stamps this session's own root under
# CLAUDE_CODE_SESSION_ID whenever it resolves one FROM CLAUDE_PROJECT_DIR -- so this one
# call does double duty: it records the sibling write (as before B72) AND leaves the
# "b72-session" stamp that 12b below reads back.
subprocess.run((sys.executable, str(HOOKS / "repo_recorder.py")),
              input=json.dumps(payload), cwd=str(eighth),
              env={**os.environ, "CLAUDE_PROJECT_DIR": str(eighth),
                   "CLAUDE_CODE_SESSION_ID": "b72-session",
                   "CLAUDE_CONFIG_DIR": str(cfg2)},
              capture_output=True, text=True, **NW)

# Strips BOTH CLAUDE_PROJECT_DIR and any ambient session-id var, so this section's outcome
# never depends on whether IT HAPPENS to run inside a live Claude Code session (which would
# otherwise leak its OWN real CLAUDE_CODE_SESSION_ID in here) -- each case below sets
# exactly the session id (or deliberate absence of one) it means to test.
env_bare = {k: v for k, v in os.environ.items()
            if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID")}
env_bare["CLAUDE_CONFIG_DIR"] = str(cfg2)
env_bare["PYTHONIOENCODING"] = "utf-8"

good = subprocess.run((sys.executable, str(TOOLS / "check_repos.py")), cwd=str(eighth),
                      env={**env_bare, "CLAUDE_PROJECT_DIR": str(eighth)},
                      capture_output=True, text=True, **NW)
check("with CLAUDE_PROJECT_DIR set, the sibling write IS found",
      "sibling2" in good.stdout, True)

print("  12a. no CLAUDE_PROJECT_DIR, NO session id either -- the narrower residual bug shape")
drifted = subprocess.run((sys.executable, str(TOOLS / "check_repos.py")), cwd=str(sibling2),
                         env=env_bare, capture_output=True, text=True, **NW)
check("BUG-SHAPE (B67), still real with no session id at all: no CLAUDE_PROJECT_DIR + a "
      "shell cwd that drifted into the written-to sibling -> falls into the empty-record "
      "branch, not the found-it branch",
      "No record" in drifted.stdout, True)
check("...and it never claims the (correctly-recorded-elsewhere) write landed",
      "[!!]" not in drifted.stdout and "not landed" not in drifted.stdout, True)
check("...but it is no longer reported as a clean bill of health -- it names what it "
      "actually (wrongly) resolved, so the mismatch is visible instead of silent",
      "Resolved project" in drifted.stdout and "sibling2" in drifted.stdout, True)

print("  12b. B72 FIX: same drift, but THIS session has its own stamp from the earlier hook call")
fixed = subprocess.run((sys.executable, str(TOOLS / "check_repos.py")), cwd=str(sibling2),
                       env={**env_bare, "CLAUDE_CODE_SESSION_ID": "b72-session"},
                       capture_output=True, text=True, **NW)
check("the sibling write IS found this time -- no CLAUDE_PROJECT_DIR needed on THIS call, "
      "the session's own earlier stamp resolves the right project",
      "sibling2" in fixed.stdout, True)
check("reported as un-landed work, not a false clean bill of health",
      "not landed" in fixed.stdout, True)

print("  12c. a DIFFERENT session id, same drift -- gets none of this (no cross-session leak, "
      "the exact concern raised against the reverted machine-global stamp)")
other_session = subprocess.run(
    (sys.executable, str(TOOLS / "check_repos.py")), cwd=str(sibling2),
    env={**env_bare, "CLAUDE_CODE_SESSION_ID": "someone-elses-session"},
    capture_output=True, text=True, **NW)
check("an unrelated session does NOT inherit b72-session's stamp (the empty-record "
      "branch prints the CWD it resolved to, which happens to BE sibling2 -- so the real "
      "assertion is that it never gets reported as found/un-landed the way 12b's own "
      "session did, not a bare substring match)",
      "[!!]" in other_session.stdout or "not landed" in other_session.stdout, False)
check("...it hits the same honest empty-record branch as 12a, never someone else's answer",
      "No record" in other_session.stdout, True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
