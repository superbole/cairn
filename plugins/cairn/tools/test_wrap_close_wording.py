"""B78 -- the wrap close prints its `Next:` line in a fenced block, and only that line.

    python plugins/cairn/tools/test_wrap_close_wording.py

WHY THIS EXISTS. The close of `/cairn:wrap` ends with a one-line handle for the next item
(*"Next: item 1 -- ... Sonnet, effort medium, AFK in Auto mode."*). The user copied it by hand to
start the next session and asked for it in a copy box (a fenced block, which the desktop app gives
a copy button). Step 9 also forbids a ready-to-copy PROMPT (removed 2026-08-09), so the change is a
boundary between the two, and this change's entire content is wording. A test that only checked
"some fence appears" would pass against a skill that fences the whole close.

WHAT THIS PINS. In `skills/wrap/SKILL.md` step 9: the example `Next:` line sits inside a fenced
block that holds exactly one line; the skill says the fence holds that line and nothing else; the
HITL stop point goes AFTER the fence; an empty Queue means no fence; the ready-to-copy prohibition
is still there and now names the one-line handle as the exception. In
`skills/wrap/references/incidents.md`: the B78 entry exists under "Step 9 -- the close" and keeps
the 2026-08-09 entry it qualifies.

Reads files only; touches no state and no `~/.claude`.
"""
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
SKILL = (ROOT / "skills" / "wrap" / "SKILL.md").read_text(encoding="utf-8")
INCIDENTS = (ROOT / "skills" / "wrap" / "references" / "incidents.md").read_text(encoding="utf-8")

fails = []


def check(label, got, want=True):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def step9(text):
    """Step 9's text: from the `9. **The close.` line up to step 10."""
    start = text.index("9. **The close.")
    end = text.index("\n10. ", start)
    return text[start:end]


def fenced_blocks(text):
    """Every fenced block in TEXT as (info string, [body lines]), indent stripped."""
    blocks, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        m = re.match(r"^\s*(```|~~~)(.*)$", lines[i])
        if not m:
            i += 1
            continue
        marker, info, body = m.group(1), m.group(2).strip(), []
        i += 1
        while i < len(lines) and not re.match(r"^\s*" + re.escape(marker) + r"\s*$", lines[i]):
            body.append(lines[i].strip())
            i += 1
        blocks.append((info, body))
        i += 1
    return blocks


s9 = step9(SKILL)
blocks = fenced_blocks(s9)
next_blocks = [(info, body) for info, body in blocks if any(b.startswith("Next:") for b in body)]

print("\n1. the `Next:` example is fenced, as one line")
check("exactly one fenced block in step 9 carries a `Next:` line", len(next_blocks), 1)
if next_blocks:
    info, body = next_blocks[0]
    check("that block holds exactly one line", len([b for b in body if b]), 1)
    check("the line names model, effort and attendance/mode",
          all(w in body[0] for w in ("Sonnet", "effort", "AFK", "mode")))
    check("it is not tagged as a shell block (no Run button on a handle)",
          info in ("", "text"))

print("\n2. the rule around the fence is stated, not just shown")
flat = re.sub(r"\s+", " ", s9)
check("the fence holds that one line and nothing else",
      "The fence holds that one line and nothing else" in flat)
check("the HITL stop point goes after the fence", "in the sentence AFTER the fence" in flat)
check("an empty Queue gets no fence",
      "If the Queue is empty there is no handle to copy: say so in prose, no fence" in flat)
check("the close is still prose, not a labelled list", "never as a labelled list" in flat)

print("\n3. the ready-to-copy prohibition survives, with the handle named as the exception")
check("the prohibition is still there", "Do NOT paste a ready-to-copy prompt into chat" in flat)
check("the 2026-08-09 quote is still there", "We're kinda back there" in flat)
check("the fenced `Next:` line is said not to be that prompt",
      "The fenced `Next:` line above is not that prompt" in flat)
check("more than one line in a fence is named as the forbidden prompt",
      "Anything longer than that one line in a fence is the prompt this rule forbids" in flat)

print("\n4. the incident record carries the reason")
close = INCIDENTS[INCIDENTS.index("## Step 9"):]
close = close[:close.index("\n---")]
flat_i = re.sub(r"\s+", " ", close)
check("the B78 entry is under Step 9", "B78" in close)
check("it keeps the 2026-08-09 entry it qualifies", "**No paste-ready prompt.**" in close)
check("it names the boundary: the line count", "The boundary is the line count" in flat_i)
check("it names the rejected options", "Rejected:" in flat_i)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
