"""B134 -- every brief names the rationale-record rows it must respect: a `**Prior decisions:**` line.

    python plugins/cairn/tools/test_brief_prior_decisions.py

WHY THIS EXISTS. Step 3 of `/cairn:wrap` asked a brief to carry "the reasoning behind decisions
already made", but only as prose about the session writing it. An agent starting the item was never
pointed at the rows of the rationale record that applied, so it re-derived rules that were already
on disk, and got some of them wrong. The fix is wording only: step 3 now requires a
`**Prior decisions:**` line naming the rows (or `none`). This pins that wording, scoped to step 3,
so a later edit cannot drop it or move it somewhere a brief-writer will not read.

WHAT THIS PINS. In `skills/wrap/SKILL.md` step 3 (from `3. **Write or update the briefs.` up to
step 3a): the line's literal label, that `none` is the explicit empty answer, that rows are named
and not copied, and the pointer to the incident record. In `skills/wrap/references/incidents.md`:
a "Step 3" section that names B134 and the two rejected options, ending at a `---`.

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


def step3(text):
    """Step 3's text: from `3. **Write or update the briefs.` up to the `3a.` step. Empty if either
    is missing, so a restructured skill reports FAILs below instead of crashing."""
    start = text.find("3. **Write or update the briefs.")
    if start < 0:
        return ""
    m = re.compile(r"\n\s*3a\. ").search(text, start)
    return text[start:m.start()] if m else ""


def incident_section(text):
    """The `## Step 3 ...` section of the incident record, up to its closing `---`. Empty if the
    heading or the closing rule is missing, so a later section cannot satisfy the checks."""
    m = re.search(r"^## Step 3 [^\n]*$", text, re.M)
    if not m:
        return ""
    end = text.find("\n---", m.end())
    return text[m.start():end] if end >= 0 else ""


s3 = step3(SKILL)
flat = re.sub(r"\s+", " ", s3)

print("\n1. step 3 requires the line")
check("step 3 was found, between its own heading and step 3a", bool(s3))
check("it names the literal label `**Prior decisions:**`", "`**Prior decisions:**`" in flat)
check("it says every brief carries it", "Every brief carries a `**Prior decisions:**` line" in flat)
check("it is filled in when the brief is written", "filled in when the brief is written" in flat)
check("`none` is the explicit empty answer", "`**Prior decisions:** none`" in flat
      and "`none` is an answer, not a blank" in flat)
check("rows are named, not copied", "Name the rows; do not copy them in" in flat)
check("it points at the incident record", "`references/incidents.md`, \"Step 3\"" in flat)
# Control: the scoping bites. The same sentence placed in step 3a must not satisfy step 3.
moved = SKILL.replace("**Every brief carries a `**Prior decisions:**` line**", "", 1)
moved = moved.replace("3a. **If the session changed",
                      "3a. **Every brief carries a `**Prior decisions:**` line** **If the session changed", 1)
check("control: the rule moved into step 3a is not found in step 3",
      "Every brief carries a `**Prior decisions:**` line" in re.sub(r"\s+", " ", step3(moved)), False)

print("\n2. the incident record carries the reason")
sec = incident_section(INCIDENTS)
flat_i = re.sub(r"\s+", " ", sec)
check("the incidents file has a Step 3 section ending at a `---`", bool(sec))
check("it names B134", "B134" in flat_i)
check("it names the rejected options",
      "Rejected:" in flat_i and "`CLAUDE.md`" in flat_i and "copying the rows into the brief" in flat_i)
check("the section sits before any Step 5 or later section",
      0 <= INCIDENTS.find("## Step 3 ") < INCIDENTS.find("## Step 5"))
# Control: a missing closing rule yields nothing rather than the rest of the file.
check("control: a Step 3 heading with no closing `---` gives an empty section",
      incident_section("## Step 3 x\n\nRejected: B134\n"), "")

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
