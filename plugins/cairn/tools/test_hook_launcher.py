#!/usr/bin/env python3
"""`hooks/run.sh` picks the right Python on every platform, and every hook goes through it.

WHY THIS EXISTS (v1.61.0, D31). Every hook in `hooks.json` used to run bare `python`, which
stock Ubuntu/Debian does not have. Every hook failed before Python was entered, so a Linux
install reported the plugin enabled and wrote none of the global files -- and nothing could say
so, because the code that would warn is the code that could not start. `python3` was not the
fix: on Windows it is often the Store redirector stub while `python` is real (measured on a Windows
machine, 2026-09-25). `run.sh` resolves the name per platform; this file pins that resolution, and pins
that no hook goes back to naming an interpreter directly.

The interpreters here are FAKES -- tiny sh scripts on a PATH that holds nothing else -- so each
case controls exactly which names exist. Skips (exit 0) on a machine with no `sh` at all.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
RUN_SH = PLUGIN / "hooks" / "run.sh"
NW = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
fails = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def find_sh():
    sh = shutil.which("sh")
    if sh:
        return sh
    git = shutil.which("git")          # Git for Windows: <Git>\cmd\git.exe -> <Git>\usr\bin\sh.exe
    if git:
        cand = Path(git).resolve().parents[1] / "usr" / "bin" / "sh.exe"
        if cand.is_file():
            return str(cand)
    return None


SH = find_sh()
if not SH:
    print("SKIP: no `sh` on this machine -- run.sh cannot be exercised here")
    sys.exit(0)

FAKE_ROOT = Path(tempfile.mkdtemp(prefix="hook-launcher-root-"))


def fake(bindir: Path, name: str):
    """An 'interpreter' that reports its own name, its args and its stdin, then exits $FAKE_RC."""
    (bindir / name).write_bytes((
        "#!/bin/sh\n"
        f"echo \"INTERP={name}\"\n"
        "echo \"ARGS=$*\"\n"
        "while IFS= read -r l; do echo \"STDIN=$l\"; done\n"
        "exit ${FAKE_RC:-0}\n").encode())
    os.chmod(bindir / name, 0o755)


def launch(names, hook="probe.py", args=(), windows=False, stdin="", extra_env=None):
    bindir = Path(tempfile.mkdtemp(prefix="hook-launcher-bin-"))
    for n in names:
        fake(bindir, n)
    env = {k: v for k, v in os.environ.items() if k not in ("OS", "CAIRN_PYTHON", "FAKE_RC")}
    env["PATH"] = str(bindir)
    env["CLAUDE_PLUGIN_ROOT"] = str(FAKE_ROOT)
    if windows:
        env["OS"] = "Windows_NT"
    env.update(extra_env or {})
    r = subprocess.run([SH, str(RUN_SH), *([hook] if hook else []), *args], env=env, input=stdin,
                       capture_output=True, text=True, timeout=60, encoding="utf-8",
                       errors="replace", **NW)
    return r, bindir


def interp(r):
    m = re.search(r"^INTERP=(\S+)", r.stdout, re.M)
    return m.group(1) if m else None


print("1. which interpreter is chosen")
r, _ = launch(["python3"])
check("python3 only, not Windows -> python3 (the stock Ubuntu case)", interp(r), "python3")
r, _ = launch(["python"])
check("python only, not Windows -> python", interp(r), "python")
r, _ = launch(["python", "python3"])
check("both, not Windows -> python3", interp(r), "python3")
r, _ = launch(["python", "python3"], windows=True)
check("both, Windows -> python (python3 may be the Store stub)", interp(r), "python")
r, _ = launch(["py", "python3"], windows=True)
check("py + python3, Windows -> py", interp(r), "py")
check("py is asked for Python 3", r.stdout.split("ARGS=")[1].startswith("-3 "), True)
custom_dir = Path(tempfile.mkdtemp(prefix="hook-launcher-custom-"))
fake(custom_dir, "custom")
r, _ = launch(["python", "python3"], extra_env={"CAIRN_PYTHON": str(custom_dir / "custom")})
check("CAIRN_PYTHON wins over everything on PATH", interp(r), "custom")

print("\n2. arguments, stdin and exit code pass straight through")
r, _ = launch(["python3"], args=("a", "b c"), stdin='{"hook_event_name": "Stop"}\n')
args_line = re.search(r"^ARGS=(.*)$", r.stdout, re.M).group(1)
check("the hook file under CLAUDE_PLUGIN_ROOT/hooks is the first argument",
      args_line.startswith(f"{FAKE_ROOT}/hooks/probe.py"), True)
check("the remaining arguments follow it", args_line.endswith(" a b c"), True)
check("stdin reaches the hook", '{"hook_event_name": "Stop"}' in r.stdout, True)
r, _ = launch(["python3"], extra_env={"FAKE_RC": "2"})
check("exit 2 (staged_review_guard's block) is returned unchanged", r.returncode, 2)

print("\n3. no interpreter at all -- the one failure the shell can report")
r, _ = launch([], hook="session_orientation.py")
check("orientation: exit 0, never blocks the session", r.returncode, 0)
check("orientation: the warning is on STDOUT, where the agent reads it",
      "no Python 3 on PATH" in r.stdout and "RELAY FIRST" in r.stdout, True)
check("orientation: it names the fix", "CAIRN_PYTHON" in r.stdout, True)
r, _ = launch([], hook="item_start.py")
check("other hooks: exit 0, never block a tool call", r.returncode, 0)
check("other hooks: nothing on stdout (it would reach the prompt)", r.stdout, "")
check("other hooks: the warning is on stderr", "no Python 3 on PATH" in r.stderr, True)
r, _ = launch([], windows=True, hook="item_start.py")
check("Windows: it lists the Windows names it tried", "python, py -3, python3" in r.stderr, True)
r, _ = launch(["python3"], hook=None)
check("no hook name: exit 0 with a usage line", (r.returncode, "needs a hook" in r.stderr),
      (0, True))

print("\n4. the files themselves")
check("run.sh has no CR bytes (a CRLF shell script does not run)", b"\r" in RUN_SH.read_bytes(),
      False)
cfg = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
cmds = [h["command"] for groups in cfg["hooks"].values() for g in groups for h in g["hooks"]]
check("hooks.json declares hooks at all", len(cmds) > 0, True)
shape = re.compile(r'^sh "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/run\.sh" ([a-z_]+\.py)$')
bad = [c for c in cmds if not shape.match(c)]
check("every hook command is `sh \"${CLAUDE_PLUGIN_ROOT}/hooks/run.sh\" <hook>.py`", bad, [])
missing = [m.group(1) for c in cmds if (m := shape.match(c))
           and not (PLUGIN / "hooks" / m.group(1)).is_file()]
check("every hook it names exists", missing, [])

print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + repr(fails)}")
sys.exit(1 if fails else 0)
