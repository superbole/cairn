"""B78 -- the wrap close prints its `Next:` line in a fenced block, and only that line.

    python plugins/cairn/tools/test_wrap_close_wording.py

WHY THIS EXISTS. The close of `/cairn:wrap` ends with a one-line handle for the next item
(*"Next: item 1 -- ... Sonnet, effort medium, AFK in Auto mode."*). The user copied it by hand to
start the next session and asked for it in a copy box (a fenced block, which the desktop app gives
a copy button). Step 9 also forbids a ready-to-copy PROMPT (removed 2026-08-09), so the change is a
boundary between the two, and this change's entire content is wording. A test that only checked
"some fence appears" would pass against a skill that fences the whole close.

WHAT THIS PINS. In `skills/wrap/SKILL.md` step 9: the example `Next:` line sits inside a `text`
fence that holds exactly one line, and no other fence in step 9 holds more than one; the skill says
the fence holds the handle's fields and nothing else (the boundary is content, not line count), why
the tag is `text`, that the HITL stop point goes AFTER the fence, and that no startable item means
no fence; the ready-to-copy prohibition is still there and names the handle as the exception. In
`skills/wrap/references/incidents.md`: the B78 entry sits directly after the 2026-08-09 entry it
qualifies, under "Step 9 -- the close", with its boundary, the tag's reason and the rejected options.

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
    """Step 9's text: from the `9. **The close.` line up to step 10. Empty if either heading is
    missing, so a restructured skill reports FAILs below instead of crashing."""
    start = text.find("9. **The close.")
    if start < 0:
        return ""
    m = re.compile(r"\n\s*10\. ").search(text, start)
    return text[start:m.start()] if m else ""


# The example's CONTENT, pinned literally. A line count alone cannot tell a handle from a one-line
# prompt (the incident note's own reason for rejecting it). A shape regex or a word blacklist only
# moves that proxy one level up: a one-line prompt that avoids the words passes, and a real Queue
# title (`NEXT.md`, `/cairn:next`, "dry-run") fails. This test can only ever see the skill's
# example, never what an agent prints at wrap time, so the honest check is the example itself
# (the scheduled review of 2ca0109).
EXAMPLE = "Next: item 1 — move the remaining repos. Sonnet, effort medium, AFK in Auto mode."


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
check("step 9 was found, between its own heading and step 10", bool(s9))
check("exactly one fenced block in step 9 carries a `Next:` line", len(next_blocks), 1)
if next_blocks:
    info, body = next_blocks[0]
    lines = [b for b in body if b]
    check("that block holds exactly one line", len(lines), 1)
    check("the line names effort and attendance/mode",
          bool(lines) and all(w in lines[0] for w in ("effort", "mode"))
          and ("AFK" in lines[0] or "HITL" in lines[0]))
    check("it is tagged `text`, not a shell block (no Run button on a handle)", info, "text")
    check("its content is exactly the handle example: item, title, model, effort, attendance/mode",
          lines[0] if lines else None, EXAMPLE)
# The docstring's promise: a skill that fences a prompt ANYWHERE in the close must fail, not only
# in the block that happens to start with `Next:`.
check("every fenced block in step 9 holds at most one line (no fenced prompt elsewhere)",
      [info for info, body in blocks if len([b for b in body if b]) > 1], [])

print("\n2. the rule around the fence is stated, not just shown")
flat = re.sub(r"\s+", " ", s9)
check("the fence holds the handle and nothing else",
      "The fence holds the handle and nothing else" in flat)
check("the boundary is content: no brief link, no instructions",
      "No brief link, no instructions" in flat)
check("the `text` tag is a written rule, with its reason",
      "Tag the fence `text`, never a shell tag" in flat and "Run button" in flat)
check("the HITL stop point goes after the fence", "AFTER the fence" in flat)
check("no startable item gets no fence",
      "no handle to copy" in flat and "every item is blocked" in flat)
check("the close is still prose, not a labelled list", "never as a labelled list" in flat)

print("\n3. the ready-to-copy prohibition survives, with the handle named as the exception")
check("the prohibition is still there", "Do NOT paste a ready-to-copy prompt into chat" in flat)
check("the 2026-08-09 quote is still there", "We're kinda back there" in flat)
check("the fenced `Next:` line is said not to be that prompt",
      "The fenced `Next:` line above is not that prompt" in flat)
check("anything beyond the handle is named as the forbidden prompt, one line or several",
      "beyond the handle's own fields, on one line or several, is the prompt this rule forbids"
      in flat)

print("\n4. the incident record carries the reason")
start = INCIDENTS.find("## Step 9")
check("the incidents file has a Step 9 section", start >= 0)
close = INCIDENTS[start:] if start >= 0 else ""
end = close.find("\n---")
# No closing `---` would widen the slice to the rest of the file, where a later section could
# satisfy the checks below: report it, and check against nothing.
check("the Step 9 section ends at a `---`", end >= 0)
close = close[:end] if end >= 0 else ""
flat_i = re.sub(r"\s+", " ", close)
paste = flat_i.find("**No paste-ready prompt.**")
b78 = flat_i.find("**The `Next:` line goes in a fence anyway (2026-09-26, B78).**")
stop = flat_i.find("**The stop-vs-continue rule")
check("it keeps the 2026-08-09 entry it qualifies", paste >= 0)
check("the B78 entry follows it directly, before the next entry",
      0 <= paste < b78 and (stop < 0 or b78 < stop))
check("it names the boundary: content, not line count",
      "The boundary is the content, not the line count" in flat_i)
check("it records why the tag is `text`", "The tag is `text`" in flat_i)
check("it names the rejected options, line count among them",
      "Rejected:" in flat_i and "line count as the boundary" in flat_i)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
