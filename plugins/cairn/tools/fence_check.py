"""Report lines inside fenced code blocks that a line-start parser would read as structure.

B85: backlog_file.parse() matches `## Bn.` with no fence awareness, so pasted command
output containing a heading silently becomes an item and moves next_id().
"""
import io, re, sys

# Patterns the plugin's parsers key off at line start.
PATTERNS = [
    ("BACKLOG item  (backlog_file.parse)", re.compile(r"^## B\d+\.")),
    ("NEXT watch    (session_orientation)", re.compile(r"^\*\*W\d+\.")),
    ("NEXT decision (session_orientation)", re.compile(r"^\*\*D\d+\.")),
    # B83 broadened the real pattern to accept a date anywhere in a `##`-`####` heading (not
    # only a `## YYYY-MM-DD` prefix), so this mirror must accept the same shapes or it silently
    # under-reports fenced text that the real parser would now read as a changelog boundary.
    ("CHANGELOG date (_CHANGELOG_DATE_RE)", re.compile(r"^#{2,4}\s+.*?\d{4}-\d{2}-\d{2}\b")),
]
FENCE = re.compile(r"^\s*(```|~~~)")

hits = 0
for path in sys.argv[1:]:
    text = io.open(path, encoding="utf-8").read().replace("\r\n", "\n")
    in_fence = False
    for i, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        for name, pat in PATTERNS:
            if pat.match(line):
                hits += 1
                print(f"  {path}:{i}  [{name}]  {line[:70]}")
    if in_fence:
        print(f"  {path}: WARNING unclosed fence — the check ran blind past it")

print(f"fence check: {hits} line(s) inside a fence that a parser would read as structure")
sys.exit(1 if hits else 0)
