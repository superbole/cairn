#!/usr/bin/env python3
"""`measure_usage.py` — does it measure, and does it refuse to guess?

The two things worth pinning are not the arithmetic. They are:
  1. it reads ONLY usage/timestamp/isSidechain/model, and never touches message content — the
     transcripts hold medical history, credentials and an employer's source (B120), so this is a
     disclosure boundary, not a style preference;
  2. a `side%` of 0 is reported as NOT MEASURABLE, never as "no subagents ran" — subagent
     transcripts live outside `<config>/projects/` and are truncated on completion, so a bare 0
     would be one value covering two opposite states.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(sys.argv[1] if len(sys.argv) > 1
             else Path(__file__).resolve().parent).resolve()
if TOOLS.name != "tools":
    TOOLS = TOOLS / "tools"
sys.path.insert(0, str(TOOLS))

# BEFORE importing: `config_dir()` falls back to the real `~/.claude`, and this test writes
# fixture transcripts. Same B74 isolation as every other test file here.
_SANDBOX = Path(tempfile.mkdtemp(prefix="cairn-usage-cfg-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(_SANDBOX)

import measure_usage                                              # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label
          + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def turn(minutes_ago, billed_in=0, cache_w=0, cache_r=0, out=0, side=False,
         model="claude-opus-5", secret="THIS-MUST-NEVER-BE-PRINTED"):
    """One transcript line shaped like the real thing, carrying a canary in every content field."""
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return json.dumps({
        "type": "assistant",
        "timestamp": t.isoformat().replace("+00:00", "Z"),
        "isSidechain": side,
        "cwd": secret,
        "gitBranch": secret,
        "message": {
            "model": model,
            "content": [{"type": "text", "text": secret}],
            "usage": {
                "input_tokens": billed_in,
                "cache_creation_input_tokens": cache_w,
                "cache_read_input_tokens": cache_r,
                "output_tokens": out,
            },
        },
    })


def write_session(project, name, lines):
    d = _SANDBOX / "projects" / project
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d / f"{name}.jsonl"


def run_cli(*args):
    r = subprocess.run((sys.executable, str(TOOLS / "measure_usage.py")) + args,
                       capture_output=True, text=True, timeout=120,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                       **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    return r.returncode, r.stdout + r.stderr


print("\n1. billed = fresh input + cache writes + output; cache reads are counted separately")
f1 = write_session("proj-alpha", "s1", [
    turn(10, billed_in=100, cache_w=1_000, cache_r=50_000, out=200),
    turn(5, billed_in=0, cache_w=2_000, cache_r=90_000, out=300),
])
turns = measure_usage.read_turns(f1)
check("both turns parsed", len(turns), 2)
check("billed sums the three charged fields", sum(t["billed"] for t in turns), 3_600)
check("cache reads are kept apart, not folded in", sum(t["cache_r"] for t in turns), 140_000)

print("\n2. it reads usage only — no message content, ever")
src = (TOOLS / "measure_usage.py").read_text(encoding="utf-8")
check("never indexes message content", '["content"]' not in src and "'content'" not in src)
for t in turns:
    check("no canary leaked into a parsed turn",
          not any("MUST-NEVER" in str(v) for v in t.values()))
    break
rc, out = run_cli("--days=1")
check("CLI exits 0", rc, 0)
check("no canary reaches stdout", "MUST-NEVER" not in out)

print("\n3. a malformed or truncated transcript degrades, never raises")
f3 = write_session("proj-beta", "s2", [
    "{not json at all",
    json.dumps({"type": "user", "message": "no usage here"}),
    turn(3, billed_in=10, out=20),
    '{"type":"assistant","message":{"usage":{"input_tokens":',      # truncated last line
])
t3 = measure_usage.read_turns(f3)
check("only the one usable turn is counted", len(t3), 1)
check("read_turns on a missing file returns empty, does not raise",
      measure_usage.read_turns(_SANDBOX / "nope.jsonl"), [])

print("\n4. side% of 0 is reported as NOT MEASURABLE, never as 'no subagents ran'")
rc, out = run_cli("--days=1")
check("exits 0", rc, 0)
check("says it cannot measure subagents", "not measurable" in out.lower())
check("names why — the transcripts are elsewhere and truncated", "truncated" in out.lower())
check("tells the reader to double the reported figure", "DOUBLE" in out)

print("\n5. a sidechain turn IS attributed when one is present")
write_session("proj-gamma", "s3", [
    turn(4, cache_w=1_000, out=100),
    turn(3, cache_w=5_000, out=500, side=True, model="claude-sonnet-5"),
])
rc, out = run_cli("--days=1")
check("exits 0", rc, 0)
check("the not-measurable note is now absent", "not measurable" not in out.lower())

print("\n6. the rolling window is a window, not a total")
old = write_session("proj-delta", "s4", [
    turn(60 * 24, cache_w=9_000_000),        # a day ago: outside any 5-hour window from now
    turn(30, cache_w=1_000),
])
peak, at = measure_usage.rolling_peak(measure_usage.read_turns(old))
check("the day-old turn is not in the same window as the recent one", peak, 9_000_000)
rc, out = run_cli("--window")
check("--window exits 0", rc, 0)
check("--window reports the live spend", "spent so far" in out)
check("--window offers headroom in BOTH agents and turns, not one",
      "lane agent" in out and "orchestrator turns" in out)

print("\n7. no transcripts at all is a sentence, not a traceback")
empty = Path(tempfile.mkdtemp(prefix="cairn-usage-empty-"))
r = subprocess.run((sys.executable, str(TOOLS / "measure_usage.py")),
                   capture_output=True, text=True, timeout=60,
                   env={**os.environ, "CLAUDE_CONFIG_DIR": str(empty),
                        "PYTHONIOENCODING": "utf-8"},
                   **({"creationflags": 0x08000000} if os.name == "nt" else {}))
check("exits 0 with no data", r.returncode, 0)
check("says there is nothing to measure", "nothing to measure" in r.stdout.lower())
check("no traceback", "Traceback" not in (r.stdout + r.stderr))

print("\n8. printed output survives a cp1252 console (three Windows machines)")
non_ascii = [(i + 1, ln.strip()[:60]) for i, ln in enumerate(src.split("\n"))
             if "print(" in ln and any(ord(c) > 127 for c in ln)]
check("no non-ASCII in any printed string", non_ascii, [])

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
