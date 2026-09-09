"""Test for `reentry_state.project_root()`'s session-scoped identity fallback (B72, v1.39.0).

    python plugins/cairn/tools/test_reentry_state.py

THE BUG THIS GUARDS (BACKLOG.md B72; B67 reproduced 2026-09-05, see docs/review/recorder.md)
---------------------------------------------------------------------------------------------
`check_repos.py`, run from `wrap/SKILL.md` step 1a as a plain `Bash` step, gets no
`CLAUDE_PROJECT_DIR` (that is only reliably exported to hook commands) and no pinned cwd. If the
session's shell has drifted into a sibling repo since the write it needs to check was recorded,
`project_root()` used to fall straight to `cwd()` and silently ask about the WRONG project -- the
write was correctly recorded under the real project the whole time; only the READ asked the wrong
question.

THE REJECTED FIX, AND WHY (BACKLOG.md B72's objection block, raised 2026-09-05 mid-implementation)
----------------------------------------------------------------------------------------------------
A first attempt stamped a MACHINE-GLOBAL "last known root" file with a TTL. It was reverted within
the hour: The user runs several sessions at once in different projects, so a global stamp means
session A's root leaks into session B's answer whenever B calls a tool with no `CLAUDE_PROJECT_DIR`
of its own -- silently, for up to the TTL. That is worse than the bug it fixed.

THE FIX SHIPPED HERE: key the stamp on `CLAUDE_CODE_SESSION_ID`, not the machine. Two concurrent
sessions can never share that value, so a stamp can only ever answer for the session that wrote it.
Section 5 below is the direct proof of that constraint, not just of the happy path.

WHY THIS MUST NEVER TOUCH ~/.claude/reentry-state (same reasoning as `test_check_exits.py`,
`test_repo_recorder.py`, `test_archive_offer.py`): every case here builds its own `reentry-state/`
tree under a temp directory via `CLAUDE_CONFIG_DIR`, set and VERIFIED before anything is written.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="reentry-state-"))
CFG = TMP / "cfg"
os.environ["CLAUDE_CONFIG_DIR"] = str(CFG)

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(HOOKS))

import reentry_state as rs                              # noqa: E402

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


# ---------------------------------------------------------------------------------------
# Env helpers. `project_root()` reads three env vars; every case below sets exactly the
# ones it means to and clears the rest, so no case can accidentally inherit a leftover
# from a previous one (this file runs as ONE process across every section).
# ---------------------------------------------------------------------------------------
_ENV_KEYS = ("CLAUDE_PROJECT_DIR", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID")


def _set_env(project_dir=None, session=None):
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    if project_dir is not None:
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_dir)
    if session is not None:
        os.environ["CLAUDE_CODE_SESSION_ID"] = session


print("0. CLAUDE_CONFIG_DIR override actually takes effect before anything is written")
_set_env()
real_home_state = (Path.home() / ".claude" / "reentry-state" / "_sessions")
fixture_state = CFG / "reentry-state" / "_sessions"
check("no fixture dir exists yet", fixture_state.exists(), False)
_set_env(session="probe")
probed = rs._session_root_dir()
check("resolves under CLAUDE_CONFIG_DIR, not the real ~/.claude",
      probed is not None and str(probed).startswith(str(CFG)), True)
check("never under the real home state dir",
      probed is None or str(real_home_state) not in str(probed), True)

root_a = TMP / "project-a"
root_b = TMP / "project-b"
for d in (root_a, root_b):
    d.mkdir()

print("\n1. CLAUDE_PROJECT_DIR set -> source is \"env\", and this session stamps its own root")
_set_env(project_dir=root_a, session="sess-1")
check("resolves to CLAUDE_PROJECT_DIR", rs.project_root().resolve(), root_a.resolve())
check("source is env", rs.project_root_source(), "env")
stamp_path = fixture_state / "sess-1.json"
check("a stamp file was written for THIS session", stamp_path.is_file(), True)
stamped = json.loads(stamp_path.read_text(encoding="utf-8"))
check("the stamp names the right root", Path(stamped["root"]).resolve(), root_a.resolve())

print("\n2. no CLAUDE_PROJECT_DIR, SAME session -> falls back to ITS OWN stamp, not cwd")
_set_env(session="sess-1")                      # no project_dir this time
real_cwd = Path.cwd()
os.chdir(root_b)                                # simulate the shell having drifted into a sibling
try:
    check("resolves to the earlier-stamped root, NOT the drifted cwd",
          rs.project_root().resolve(), root_a.resolve())
    check("source says session-stamp", rs.project_root_source(), "session-stamp")
finally:
    os.chdir(real_cwd)

print("\n3. no CLAUDE_PROJECT_DIR, a session id NEVER stamped -> the pre-fix cwd fallback")
_set_env(session="sess-2-never-stamped")
os.chdir(root_b)
try:
    check("falls back to cwd, unchanged from before B72",
          rs.project_root().resolve(), root_b.resolve())
    check("source says cwd", rs.project_root_source(), "cwd")
finally:
    os.chdir(real_cwd)

print("\n4. NO session id at all (e.g. a bare terminal, not a Claude Code session) -> cwd,")
print("   even though sess-1's stamp for project-a still exists on disk")
_set_env()                                       # neither CLAUDE_PROJECT_DIR nor any session var
os.chdir(root_b)
try:
    check("falls back to cwd with no session id to key on",
          rs.project_root().resolve(), root_b.resolve())
    check("source says cwd", rs.project_root_source(), "cwd")
finally:
    os.chdir(real_cwd)

print("\n5. THE OBJECTION'S OWN TEST: a DIFFERENT concurrent session can never read")
print("   session 1's stamp -- this is what made the reverted global stamp unsafe")
_set_env(session="sess-3-a-different-session")   # never stamped anything of its own
os.chdir(root_b)
try:
    got = rs.project_root().resolve()
    check("session 3 does NOT get session 1's project-a", got != root_a.resolve(), True)
    check("...it gets its own cwd instead, never someone else's project",
          got, root_b.resolve())
    check("source confirms this was the cwd fallback, not a cross-session hit",
          rs.project_root_source(), "cwd")
finally:
    os.chdir(real_cwd)

print("\n6. a stamped root that no longer exists on disk is treated as no stamp at all")
_set_env(session="sess-4")
ghost = TMP / "moved-or-deleted"
(fixture_state / "sess-4.json").write_text(
    json.dumps({"root": str(ghost), "at": 0}), encoding="utf-8")
os.chdir(root_b)
try:
    check("falls through to cwd rather than pointing at a path that is gone",
          rs.project_root().resolve(), root_b.resolve())
finally:
    os.chdir(real_cwd)

print("\n7. a torn/corrupt stamp file never raises, and degrades to cwd")
_set_env(session="sess-5")
(fixture_state / "sess-5.json").write_text("{not json", encoding="utf-8")
os.chdir(root_b)
try:
    check("no exception, falls back to cwd",
          rs.project_root().resolve(), root_b.resolve())
finally:
    os.chdir(real_cwd)

print("\n8. the session-stamp directory is invisible to check_repos.known_roots()")
sys.path.insert(0, str(TOOLS))
import check_repos as cr                                # noqa: E402
_set_env()
known = cr.known_roots()
check("no phantom project surfaces from the _sessions bookkeeping directory",
      any("_sessions" in str(p) or "sess-" in str(p) for p in known), False)

print("\n9. LIVE REPRO with real subprocesses and real git repos -- the shape B67 named,")
print("   with the fix in place: a hook-shaped call stamps the root, then a plain-Bash-shaped")
print("   check_repos.py call (cwd drifted into the sibling, NO CLAUDE_PROJECT_DIR) finds it")
base = Path(tempfile.mkdtemp(prefix="b72-live-"))
proj = base / "real-project"           # this session's actual project
sib = base / "sibling"                 # the repo a write landed in, and where the shell drifted
for d in (proj, sib):
    d.mkdir()
    subprocess.run(("git", "init", "-q"), cwd=d, capture_output=True, **NW)
cfg9 = base / "cfg"
env_base = {k: v for k, v in os.environ.items() if k not in _ENV_KEYS}
env_base["CLAUDE_CONFIG_DIR"] = str(cfg9)
env_base["PYTHONIOENCODING"] = "utf-8"

# Record a real write into the sibling, under the real project -- exactly what
# `repo_recorder.py` does on a PostToolUse hook, which reliably HAS CLAUDE_PROJECT_DIR.
payload = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "session_id": "live-9",
           "agent_id": None, "cwd": str(proj),
           "tool_input": {"file_path": str(sib / "NOTES.md")}}
subprocess.run((sys.executable, str(HOOKS / "repo_recorder.py")),
              input=json.dumps(payload),
              env={**env_base, "CLAUDE_PROJECT_DIR": str(proj),
                   "CLAUDE_CODE_SESSION_ID": "live-9"},
              cwd=str(proj), capture_output=True, text=True, **NW)
# The SAME hook call also exercises `project_root()` with CLAUDE_PROJECT_DIR set, which is
# what stamps this session's root -- no separate call needed to produce the stamp.

before = subprocess.run((sys.executable, str(TOOLS / "check_repos.py")), cwd=str(sib),
                        env={**env_base, "CLAUDE_CODE_SESSION_ID": "a-session-with-no-stamp"},
                        capture_output=True, text=True, **NW)
print("  -- a session with NO earlier stamp, cwd drifted into the sibling --")
for ln in before.stdout.splitlines():
    print("     " + ln)
check("an unrelated/unstamped session still hits the honest 'no record' branch",
      "No record" in before.stdout, True)
check("...and names cwd as the source, the residual case worth suspicion",
      "shell's cwd" in before.stdout, True)

after = subprocess.run((sys.executable, str(TOOLS / "check_repos.py")), cwd=str(sib),
                       env={**env_base, "CLAUDE_CODE_SESSION_ID": "live-9"},
                       capture_output=True, text=True, **NW)
print("  -- THIS session (live-9), cwd drifted into the sibling, NO CLAUDE_PROJECT_DIR --")
for ln in after.stdout.splitlines():
    print("     " + ln)
check("B72 FIXED: the sibling write is found, even though the shell's cwd had drifted",
      "sibling" in after.stdout, True)
check("found via the RECORDER against the real project (live-9's stamped root), "
      "not named on the command line -- proof project_root() resolved to `proj`, not `sib`",
      "found by the recorder, not named" in after.stdout, True)
check("not the honest-but-wrong 'no record' branch this time",
      "No record" not in after.stdout, True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
