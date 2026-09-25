#!/usr/bin/env python3
"""Every command the skills and rules tell the AGENT to run resolves, with no env and no `python`.

WHY THIS EXISTS (B59). `skills/*/SKILL.md` and `rules/CLAUDE.md` told the agent to run
`python "$CLAUDE_PLUGIN_ROOT/hooks/wrap_receipt.py" --record`. Two things were wrong, each alone
enough to fail: Claude Code exports CLAUDE_PLUGIN_ROOT to HOOK processes only -- in the agent's
Bash tool it is unset (measured 2026-09-25), so the line expanded to `python "/hooks/..."` on
every platform -- and stock Ubuntu/Debian has no `python` at all (the hook half was D31). Every
wrap had worked only because the agent quietly found the path some other way.

The lines now read `sh "<root>/hooks/run.sh" <file> [args]`, with `<root>` defined in words as two
directories above the skill's base directory. This file pins:
  1. no interpreter name (`python`, `python3`, `py`) is put in front of a .py file, and no
     `$CLAUDE_PLUGIN_ROOT` / `${CLAUDE_PLUGIN_ROOT}` is used as a path, in any spelling;
  2. every run.sh call names a file that exists, spelled the one way run.sh accepts;
  3. every file with a call defines `<root>`, and the definition lands on this plugin;
  4. each call site, launched by run.sh with CLAUDE_PLUGIN_ROOT UNSET and a PATH holding only a
     fake `python3`, reaches the file it names -- the stock-Ubuntu agent shell, reproduced.

`references/*.md` is left out on purpose: it is dated evidence, and quotes old commands verbatim.
"""
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
FILES = sorted(PLUGIN.glob("skills/*/SKILL.md")) + [PLUGIN / "rules" / "CLAUDE.md"]
fails = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def rel(p):
    return p.relative_to(PLUGIN).as_posix()


TEXT = {f: f.read_text(encoding="utf-8") for f in FILES}

# An interpreter name, optionally `-3`, then (maybe quoted) anything ending in .py.
INTERP = re.compile(r"""(?<![\w./-])(?:python3?|py)(?:\.exe)?(?:\s+-3)?\s+["']?[^\s"'`]*\.py\b""")
# The variable used as a PATH, not merely named in prose ("is unset in your shell").
ROOT_VAR = re.compile(r"""\$\{?CLAUDE_PLUGIN_ROOT\}?["']?/""")
CALL = re.compile(r'sh "([^"]*)/hooks/run\.sh" ([^\s`]+)')

print("1. nothing names an interpreter or uses $CLAUDE_PLUGIN_ROOT as a path")
selftest = ['python "$CLAUDE_PLUGIN_ROOT/hooks/x.py"', 'python3 "${CLAUDE_PLUGIN_ROOT}/tools/x.py"',
            'py -3 "$CLAUDE_PLUGIN_ROOT/hooks/x.py"', "python plugins/cairn/hooks/push_check.py",
            "python.exe hooks/x.py"]
check("the pattern itself catches every variant it is meant to",
      [s for s in selftest if not INTERP.search(s)], [])
check("the root pattern catches both spellings",
      [s for s in selftest[:3] if not ROOT_VAR.search(s)], [])
for f, t in TEXT.items():
    hits = [f"{i}: {l.strip()}" for i, l in enumerate(t.splitlines(), 1) if INTERP.search(l)]
    check(f"{rel(f)}: no `python|python3|py <file>.py`", hits, [])
    hits = [f"{i}: {l.strip()}" for i, l in enumerate(t.splitlines(), 1) if ROOT_VAR.search(l)]
    check(f"{rel(f)}: no `$CLAUDE_PLUGIN_ROOT/...` path", hits, [])

print("\n2. every run.sh call names a real file, the way run.sh spells it")
calls = []                                                    # (file, line no, root, arg)
for f, t in TEXT.items():
    for i, l in enumerate(t.splitlines(), 1):
        for m in CALL.finditer(l):
            calls.append((f, i, m.group(1), m.group(2)))
check("there are call sites at all (the regex still matches the text)", len(calls) >= 17, True)
check("every call spells the root `<root>`", sorted({c[2] for c in calls}), ["<root>"])


def target(arg):
    """Where run.sh sends `arg` -- mirrors its case statement."""
    if ".." in arg:
        return None
    if arg.startswith(("hooks/", "tools/")):
        return PLUGIN / arg
    return None if "/" in arg else PLUGIN / "hooks" / arg


missing = [f"{rel(f)}:{i} {a}" for f, i, _, a in calls if not (target(a) and target(a).is_file())]
check("every named file exists where run.sh will look", missing, [])
redundant = [f"{rel(f)}:{i} {a}" for f, i, _, a in calls if a.startswith("hooks/")]
check("hooks are named bare (`wrap_receipt.py`), tools as `tools/<name>.py`", redundant, [])

print("\n3. every file with a call defines <root>, and the definition lands on this plugin")
for f in {c[0] for c in calls}:
    t = re.sub(r"\s+", " ", TEXT[f])
    check(f"{rel(f)}: defines <root> as two directories above a skill's base directory",
          "two directories above" in t and "base directory" in t, True)
for base in sorted(PLUGIN.glob("skills/*")):
    check(f"skills/{base.name}: base directory/../.. has hooks/run.sh",
          (base / ".." / ".." / "hooks" / "run.sh").resolve() == RUN_SH.resolve(), True)


def find_sh():
    sh = shutil.which("sh")
    if sh:
        return sh
    git = shutil.which("git")
    if git:
        cand = Path(git).resolve().parents[1] / "usr" / "bin" / "sh.exe"
        if cand.is_file():
            return str(cand)
    return None


print("\n4. each call, launched the agent's way (no CLAUDE_PLUGIN_ROOT, only `python3`), lands")
SH = find_sh()
if not SH:
    print("  SKIP: no `sh` on this machine")
else:
    bindir = Path(tempfile.mkdtemp(prefix="skill-calls-bin-"))
    (bindir / "python3").write_bytes(
        b'#!/bin/sh\nif [ -f "$1" ]; then echo "LANDED=$1"; else echo "NOFILE=$1"; fi\n')
    os.chmod(bindir / "python3", 0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CAIRN_PYTHON",
                                                            "OS")}
    env["PATH"] = str(bindir)
    for f, i, _, arg in calls:
        # The literal line, with <root> replaced as the definition says: <base dir>/../..
        base = PLUGIN / "skills" / (f.parent.name if f.name == "SKILL.md" else "wrap")
        script = f"{base}/../../hooks/run.sh"
        r = subprocess.run([SH, script, arg], env=env, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace", **NW)
        m = re.search(r"^LANDED=(.*)$", r.stdout, re.M)
        want = arg if "/" in arg else f"hooks/{arg}"
        check(f"{rel(f)}:{i} {arg} -> {want}",
              bool(m) and m.group(1).replace("\\", "/").endswith("/" + want), True)

print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + repr(fails)}")
sys.exit(1 if fails else 0)
