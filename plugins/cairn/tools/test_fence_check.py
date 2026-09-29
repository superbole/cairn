"""Coverage for `fence_check.py` — B14 (default file set) and B15 (the INBOX bullet rule).

    python plugins/cairn/tools/test_fence_check.py

B14. With no arguments, `fence_check.py` used to check nothing (`for path in
sys.argv[1:]`, no default) and print a clean-looking `fence check: 0 line(s)...` — exit 0,
byte-identical to a real pass. Section 1 below is that exact regression: run the tool with
NO arguments against a fixture directory and prove it now reads the four project files
(when present) rather than reading nothing silently.

B15. `fence_check.py` had no idea a bullet inside a fence isn't a bullet, same gap as the
two INBOX counters (covered by `test_wrap_receipt.py` section 13 and
`test_session_orientation.py`). Section 2 covers the new INBOX-only bullet pattern,
including that it must NOT fire on a fenced bullet in a file that merely happens to be
named something else — a bullet in a BACKLOG.md body is prose, not structure.

Runs the script as a subprocess against throwaway `tempfile.mkdtemp()` fixture
directories, never this repo's own NEXT.md/BACKLOG.md/CHANGELOG.md.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
SCRIPT = TOOLS / "fence_check.py"
NW = {"creationflags": 0x08000000} if sys.platform == "win32" else {}

fails = []


def check(label, got, want=True):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def run(args, cwd):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=30, **NW)


def fixture(name):
    return Path(tempfile.mkdtemp(prefix=f"fence-check-{name}-"))


print("1. B14 — no arguments no longer means 'checked nothing, printed a clean pass'")

print("\n1a. an empty directory: no default file is present")
r1a = fixture("empty")
p1a = run([], r1a)
check("exit 0 (nothing to check is not a failure)", p1a.returncode, 0)
check("says none of the default files are present", "none" in p1a.stdout.lower())
check("says 0 file(s) read — the count that makes a vacuous run visible",
      "across 0 file(s) read" in p1a.stdout)

print("\n1b. the four project files present and clean")
r1b = fixture("clean")
(r1b / "NEXT.md").write_text("# NEXT\n\n## Queue\n", encoding="utf-8")
(r1b / "BACKLOG.md").write_text("# BACKLOG\n", encoding="utf-8")
(r1b / "CHANGELOG.md").write_text("# CHANGELOG\n", encoding="utf-8")
(r1b / "INBOX.md").write_text("# INBOX\n\n- a real thing\n", encoding="utf-8")
p1b = run([], r1b)
check("exit 0", p1b.returncode, 0)
check("names all four files it is using",
      all(name in p1b.stdout for name in
          ("NEXT.md", "BACKLOG.md", "CHANGELOG.md", "INBOX.md")))
check("says 4 file(s) read", "across 4 file(s) read" in p1b.stdout)
check("0 hits — a real bullet outside any fence is not structure",
      "fence check: 0 line(s)" in p1b.stdout)

print("\n1c. only some of the four are present (INBOX.md is opt-in — B14's 'when present')")
r1c = fixture("partial")
(r1c / "NEXT.md").write_text("# NEXT\n", encoding="utf-8")
(r1c / "BACKLOG.md").write_text("# BACKLOG\n", encoding="utf-8")
p1c = run([], r1c)
check("exit 0", p1c.returncode, 0)
check("only the two present files are named", "CHANGELOG.md" not in p1c.stdout.split("\n")[0])
check("says 2 file(s) read", "across 2 file(s) read" in p1c.stdout)

print("\n1d. a fenced heading in one of the default files is still caught (the B85 case)")
r1d = fixture("fenced-heading")
(r1d / "BACKLOG.md").write_text(
    "# BACKLOG\n\nPasted output:\n\n```\n## B999. not a real item\n```\n", encoding="utf-8")
p1d = run([], r1d)
check("exit 1 — a real hazard is still reported by default", p1d.returncode, 1)
check("names the BACKLOG item pattern", "BACKLOG item" in p1d.stdout)

print("\n1e. explicit arguments keep working exactly as before (unchanged by B14)")
r1e = fixture("explicit")
docs = r1e / "docs.md"
docs.write_text("```\n## B12. an example in documentation\n```\n", encoding="utf-8")
p1e = run([str(docs)], r1e)
check("exit 1 (explicit-path mode still applies the structure patterns)", p1e.returncode, 1)
check("does not print the default-set banner in explicit mode",
      "using default set" in p1e.stdout, False)


print("\n2. B15 — a bullet is only 'structure' this tool flags inside INBOX.md")

print("\n2a. example bullets fenced inside INBOX.md are flagged by name")
r2a = fixture("inbox-fenced")
(r2a / "INBOX.md").write_text(
    "# INBOX\n\nIntake contract:\n\n```\n- example one\n* example two\n```\n",
    encoding="utf-8")
p2a = run([], r2a)
check("exit 1", p2a.returncode, 1)
check("both fenced bullets are reported", p2a.stdout.count("INBOX bullet") == 2)

print("\n2b. the SAME fenced bullet shape in a BACKLOG.md body does not cry wolf")
r2b = fixture("backlog-fenced-bullets")
(r2b / "BACKLOG.md").write_text(
    "# BACKLOG\n\n## B1. title\n\nExample output:\n\n```\n- one\n- two\n```\n",
    encoding="utf-8")
p2b = run([], r2b)
check("exit 0 — a bullet in a BACKLOG body is prose, not structure", p2b.returncode, 0)
check("no INBOX-bullet hit is reported", "INBOX bullet" not in p2b.stdout)

print("\n2c. the same file, explicitly named something other than INBOX.md, is still spared")
r2c = fixture("renamed-inbox-shape")
odd = r2c / "notes.md"
odd.write_text("```\n- one\n* two\n```\n", encoding="utf-8")
p2c = run([str(odd)], r2c)
check("exit 0 — the bullet rule is scoped to the filename INBOX.md, not the shape",
      p2c.returncode, 0)

print("\n2d. an unclosed fence in INBOX.md still reports what it ran blind past, and says so")
r2d = fixture("inbox-unclosed")
(r2d / "INBOX.md").write_text("# INBOX\n\n```\n- one\n- two\n", encoding="utf-8")
p2d = run([], r2d)
check("WARNING about the unclosed fence is printed", "WARNING unclosed fence" in p2d.stdout)
check("exit 1 — content the tool ran blind past is still flagged, same as any other fence"
      " (this is fence_check reporting a hazard, not the INBOX drained-count — that"
      " asymmetry is deliberate; see wrap_receipt/session_orientation's own unclosed-fence"
      " handling for the OPPOSITE choice and why)",
      p2d.returncode, 1)
check("both bullets past the unclosed marker are named as hits",
      p2d.stdout.count("INBOX bullet") == 2)

print("\n2e. a ~~~ fence is recognised the same as ```")
r2e = fixture("inbox-tilde")
(r2e / "INBOX.md").write_text("# INBOX\n\n~~~\n- example\n~~~\n", encoding="utf-8")
p2e = run([], r2e)
check("exit 1", p2e.returncode, 1)
check("the ~~~-fenced bullet is reported", "INBOX bullet" in p2e.stdout)


print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
