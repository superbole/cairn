"""Report lines inside fenced code blocks that a line-start parser would read as structure.

B85: backlog_file.parse() matches `## Bn.` with no fence awareness, so pasted command
output containing a heading silently becomes an item and moves next_id().

B14: with NO arguments this used to check nothing and print a clean-looking pass — `for
path in sys.argv[1:]` with no default, so `fence check: 0 line(s)...` and exit 0 came out
byte-identical whether the four project files were clean or never opened at all. Fixed by
giving it a default file set (below) instead of requiring an explicit list every time, and
by always printing how many files it actually read — that count is what makes a vacuous
run visible instead of indistinguishable from a real pass.

The default set is deliberately narrow: NEXT.md, BACKLOG.md, CHANGELOG.md and INBOX.md —
the four files this plugin's own parsers read for line-start structure. It does NOT
include the public docs (README.md, docs/guide.md, docs/file-formats.md): those contain
deliberate fenced *examples* of the very syntax being checked for (`## B12.`, `**W3.`,
etc.), which no line-start parser in this plugin ever reads, so scanning them by default
would cry wolf on every doc that documents the format — measured at 9 such hits across the
three files above, none a real hazard. Pass paths explicitly (unchanged from before B14)
to check anything outside the default set; explicit-argument mode keeps every pattern
applied to every path given, same as always.
"""
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
try:
    import fence_scan
except Exception:
    fence_scan = None                  # type: ignore[assignment]

try:                                    # Windows consoles default to cp1252 and would
    sys.stdout.reconfigure(encoding="utf-8")   # mangle the em-dashes below
except Exception:
    pass

# Patterns the plugin's parsers key off at line start, applied regardless of which file is
# being checked (explicit-argument mode has always worked this way; kept for the default
# file set too since none of these shapes plausibly belongs as prose in any of the four).
PATTERNS = [
    ("BACKLOG item  (backlog_file.parse)", re.compile(r"^## B\d+\.")),
    ("NEXT watch    (session_orientation)", re.compile(r"^\*\*W\d+\.")),
    ("NEXT decision (session_orientation)", re.compile(r"^\*\*D\d+\.")),
    # B83 broadened the real pattern to accept a date anywhere in a `##`-`####` heading (not
    # only a `## YYYY-MM-DD` prefix), so this mirror must accept the same shapes or it silently
    # under-reports fenced text that the real parser would now read as a changelog boundary.
    ("CHANGELOG date (_CHANGELOG_DATE_RE)", re.compile(r"^#{2,4}\s+.*?\d{4}-\d{2}-\d{2}\b")),
]

# B15: a bullet is only "structure" a parser reads in INBOX.md — that's the one file where
# "a bullet is the whole protocol" (see rules/CLAUDE.md). A bullet fenced inside a
# BACKLOG.md or CHANGELOG.md BODY is ordinary prose formatting, not something any parser
# in this plugin keys off, so this pattern is scoped to INBOX.md by filename only —
# applying it everywhere would cry wolf on every fenced example list in a backlog entry.
_BULLET_PATTERN = ("INBOX bullet  (wrap_receipt/session_orientation)",
                    fence_scan.BULLET_RE if fence_scan else re.compile(r"^\s*[-*]\s+\S"))

FENCE = fence_scan.FENCE_RE if fence_scan else re.compile(r"^\s*(```|~~~)")

# B14's default set. Order matters only for the printed "checking:" line, not for results.
DEFAULT_FILES = ["NEXT.md", "BACKLOG.md", "CHANGELOG.md", "INBOX.md"]


def patterns_for(path: str) -> list:
    pats = list(PATTERNS)
    if Path(path).name == "INBOX.md":
        pats.append(_BULLET_PATTERN)
    return pats


def check_file(path: str) -> int:
    """Print hits in `path`; return the hit count."""
    hits = 0
    text = io.open(path, encoding="utf-8").read().replace("\r\n", "\n")
    in_fence = False
    pats = patterns_for(path)
    for i, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        for name, pat in pats:
            if pat.match(line):
                hits += 1
                print(f"  {path}:{i}  [{name}]  {line[:70]}")
    if in_fence:
        print(f"  {path}: WARNING unclosed fence — the check ran blind past it")
    return hits


def main(argv: list) -> int:
    explicit = bool(argv)
    if explicit:
        paths = argv
    else:
        root = Path(".")
        paths = [p for p in DEFAULT_FILES if (root / p).is_file()]
        if paths:
            print(f"fence check: no paths given — using default set: {', '.join(paths)}")
        else:
            print("fence check: no paths given and none of NEXT.md, BACKLOG.md, "
                  "CHANGELOG.md, INBOX.md is present in the current directory")

    hits = 0
    for path in paths:
        hits += check_file(path)

    print(f"fence check: {hits} line(s) inside a fence that a parser would read as "
          f"structure, across {len(paths)} file(s) read")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
