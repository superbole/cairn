#!/usr/bin/env python3
"""install_rules.py: the managed block is found structurally, and every outgoing state is backed up.

    python plugins/cairn/tools/test_install_rules.py [<plugin-root>]

WHY THIS EXISTS (B25). `install_rules` writes the one file the plugin promises to touch only
between its markers, and until this file it had no direct test — its only coverage was the
ordering case in `test_ensure_profile_file.py`. Two defects survived that gap together:

  1. The block's start was `text.find("<!-- reentry:begin")` — the first occurrence ANYWHERE.
     A note above the block that quoted the marker became the block's start, and everything from
     there down to the real END, the user's own text included, was replaced. Silently.
  2. The backup was ONE rolling copy, overwritten on every modifying run, so two updates in a
     row (auto-update does that with nobody acting) destroyed the only copy that could undo 1.

The cases below are the brief's list (`briefs/install-rules-marker-safety.md`) plus the legacy
header every installed machine carries today, which must still update.

Runs entirely under `tempfile.mkdtemp()` with `CLAUDE_CONFIG_DIR` pointed at it, never the real
`~/.claude/`; set before importing anything that reads it. `_install_block()` is called rather
than `install()` so the profile layer (tested in its own file) stays out of these assertions.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(ROOT / "hooks"))

os.environ["CLAUDE_CONFIG_DIR"] = tempfile.mkdtemp(prefix="install-rules-")

import install_rules                                    # noqa: E402

try:                                                    # a failure repr carries `→`/`—`; cp1252 dies on it
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

fails = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}"
          + ("" if ok else f"\n        got:  {got!r:.300}\n        want: {want!r:.300}"))
    if not ok:
        fails.append(label)


def sandbox(name: str) -> Path:
    cfg = Path(tempfile.mkdtemp(prefix=f"install-rules-{name}-"))
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfg)
    return cfg


def at_version(v: str) -> None:
    install_rules._plugin_version = lambda: v


def read(cfg: Path) -> str:
    return (cfg / "CLAUDE.md").read_text(encoding="utf-8")


def write(cfg: Path, text: str) -> None:
    (cfg / "CLAUDE.md").write_text(text, encoding="utf-8", newline="\n")


def backups(cfg: Path) -> list[Path]:
    return sorted(cfg.glob("CLAUDE.md.bak-reentry-install-*"))


BODY = install_rules._rules_source()
assert BODY, "rules/CLAUDE.md is missing - nothing to test against"


def block(v: str) -> str:
    return install_rules._block(v, BODY)


def legacy_block(v: str, plugin: str = "cairn") -> str:
    """The three-line header every machine on v1.61.0 or earlier has on disk."""
    return (f"<!-- reentry:begin v{v} — managed by the {plugin} plugin.\n"
            f"     EDIT `rules/CLAUDE.md` IN THE PLUGIN SOURCE, NOT HERE — this block is regenerated.\n"
            f"     Anything you write OUTSIDE these markers is yours and is never touched. -->\n"
            f"old rules text\n"
            f"<!-- reentry:end -->\n")


ABOVE = ("# My machine notes\n\n"
         "The installer's block starts at a `<!-- reentry:begin` comment; do not edit inside it.\n"
         "<!-- reentry:begin\n"
         "that line above is a lookalike: marker at line start, no version, no close.\n\n")
BELOW = "\n# Below the block\n\nmine too.\n"


print("1. Fresh machine: installs, backs nothing up")
cfg = sandbox("fresh")
at_version("2.0.0")
report, in_ctx = install_rules._install_block()
check("reports the install", bool(report and "Installed" in report), True)
check("file is exactly the block", read(cfg), block("2.0.0"))
check("header closes on its own line", read(cfg).splitlines()[0], "<!-- reentry:begin v2.0.0 -->")
check("no backup for a file that did not exist", backups(cfg), [])

print("\n2. Idempotent: the second run is silent and churns no backup")
report, in_ctx = install_rules._install_block()
check("silent", report, None)
check("in context", in_ctx, True)
check("still no backup", backups(cfg), [])

print("\n3. User text above the block that QUOTES the marker survives an update (the B25 bug)")
cfg = sandbox("above")
at_version("2.0.0")
original = ABOVE + block("2.0.0") + BELOW
write(cfg, original)
at_version("2.1.0")
report, in_ctx = install_rules._install_block()
check("reports the update", bool(report and "v2.0.0 → v2.1.0" in report), True)
check("user text above intact, byte for byte", read(cfg).startswith(ABOVE), True)
check("user text below intact", read(cfg).endswith(BELOW), True)
check("block replaced with the new version", read(cfg), ABOVE + block("2.1.0") + BELOW)
check("one backup", len(backups(cfg)), 1)
check("backup holds the pre-update file", backups(cfg)[0].read_text(encoding="utf-8"), original)
check("backup named after the outgoing version",
      backups(cfg)[0].name.startswith("CLAUDE.md.bak-reentry-install-v2.0.0-"), True)

print("\n4. A marker prefix with no `-->` and no real block: not a block, refused, untouched")
cfg = sandbox("unclosed")
text = "notes\n<!-- reentry:begin v2.0.0\nstuff\n<!-- reentry:end -->\n"
write(cfg, text)
report, in_ctx = install_rules._install_block()
check("refusal reported", bool(report and "Did NOT update" in report and "line 2" in report), True)
check("file untouched (no second block prepended)", read(cfg), text)
check("not in context", in_ctx, False)
check("no backup written", backups(cfg), [])
try:
    install_rules._find_block(text)
    check("_find_block raises", "returned", "raised")
except install_rules.MalformedBlock:
    check("_find_block raises", "raised", "raised")

print("\n5. A block with no version token: refused, not silently rewritten")
cfg = sandbox("noversion")
text = "<!-- reentry:begin -->\nstuff\n<!-- reentry:end -->\nmine\n"
write(cfg, text)
report, _ = install_rules._install_block()
check("refusal reported", bool(report and "Did NOT update" in report), True)
check("file untouched", read(cfg), text)

print("\n6. Two valid headers: ambiguous, refused")
cfg = sandbox("twoheaders")
text = "```\n<!-- reentry:begin v1.0.0 -->\n```\n" + block("2.0.0")
write(cfg, text)
report, _ = install_rules._install_block()
check("refusal names both lines", bool(report and "lines 2, 4" in report), True)
check("file untouched", read(cfg), text)

print("\n7. A header with no END line after it: refused")
cfg = sandbox("noend")
text = "<!-- reentry:end -->\n<!-- reentry:begin v2.0.0 -->\nstuff with no end\n"
write(cfg, text)
report, _ = install_rules._install_block()
check("refusal reported", bool(report and "no `<!-- reentry:end -->` line after it" in report), True)
check("file untouched", read(cfg), text)

print("\n8. Two consecutive updates: BOTH outgoing states are recoverable")
cfg = sandbox("twoupdates")
at_version("2.0.0")
v2 = ABOVE + block("2.0.0") + BELOW
write(cfg, v2)
at_version("2.1.0")
install_rules._install_block()
v21 = read(cfg)
at_version("2.2.0")
install_rules._install_block()
names = [b.name for b in backups(cfg)]
check("two backups", len(names), 2)
by_version = {b.name.split("-install-")[1].split("-")[0]: b for b in backups(cfg)}
check("the pre-first-update state survives", by_version["v2.0.0"].read_text(encoding="utf-8"), v2)
check("the pre-second-update state too", by_version["v2.1.0"].read_text(encoding="utf-8"), v21)
check("final file current", read(cfg), ABOVE + block("2.2.0") + BELOW)

print("\n9. Same version, different block (rules edited without a bump): backed up by digest")
cfg = sandbox("samever")
at_version("2.0.0")
stale = ABOVE + block("2.0.0").replace("# ", "# (stale) ", 1) + BELOW
write(cfg, stale)
report, _ = install_rules._install_block()
check("rewritten", read(cfg), ABOVE + block("2.0.0") + BELOW)
check("one backup holding the stale file", [b.read_text(encoding="utf-8") for b in backups(cfg)], [stale])
report, in_ctx = install_rules._install_block()
check("next run silent", report, None)
check("no further backup", len(backups(cfg)), 1)

print("\n10. The LEGACY three-line header (every machine today) still updates")
for plugin in ("cairn", "reentry"):
    cfg = sandbox(f"legacy-{plugin}")
    text = ABOVE + legacy_block("1.60.0", plugin) + BELOW
    write(cfg, text)
    at_version("2.0.0")
    report, _ = install_rules._install_block()
    check(f"'{plugin}' legacy header: update reported",
          bool(report and "v1.60.0 → v2.0.0" in report), True)
    check(f"'{plugin}' legacy header: replaced, user text intact",
          read(cfg), ABOVE + block("2.0.0") + BELOW)

print("\n10b. A one-line header with words before its `-->` is a header")
cfg = sandbox("wordy")
text = (ABOVE + "<!-- reentry:begin v1.31.0 — managed by the reentry plugin. -->\nold\n"
        "<!-- reentry:end -->\n" + BELOW)
write(cfg, text)
at_version("2.0.0")
report, _ = install_rules._install_block()
check("update reported", bool(report and "v1.31.0 → v2.0.0" in report), True)
check("replaced, user text intact", read(cfg), ABOVE + block("2.0.0") + BELOW)
check("`v1.0 notes, not closed` is still NOT a header",
      install_rules._BEGIN_LINE.fullmatch("<!-- reentry:begin v1.0 notes, not closed"), None)
check("prose after the `-->` is NOT a header",
      install_rules._BEGIN_LINE.fullmatch("<!-- reentry:begin v1.0 --> trailing prose"), None)

print("\n11. CRLF on disk and trailing whitespace on the marker lines still match")
cfg = sandbox("crlf")
at_version("2.0.0")
text = (ABOVE + block("2.0.0").replace(" -->\n", " -->  \n", 1) + BELOW).replace("\n", "\r\n")
(cfg / "CLAUDE.md").write_bytes(text.encode("utf-8"))
at_version("2.1.0")
report, _ = install_rules._install_block()
check("updated", bool(report and "v2.0.0 → v2.1.0" in report), True)
check("user text intact", read(cfg), ABOVE + block("2.1.0") + BELOW)

print("\n12. A file with no block and only mid-line mentions: prepended, old contents kept")
cfg = sandbox("prepend")
text = "my notes mention `<!-- reentry:begin` mid-line only\n"
write(cfg, text)
at_version("2.0.0")
report, _ = install_rules._install_block()
check("prepend reported", bool(report and "Added" in report), True)
check("block on top, notes below", read(cfg), block("2.0.0") + "\n" + text)
check("backup named `noblock`",
      [b.name.split("-install-")[1].split("-")[0] for b in backups(cfg)], ["noblock"])

print("\n13. The pre-v1.62.0 fixed-name backup is never overwritten")
cfg = sandbox("legacybak")
old_bak = cfg / "CLAUDE.md.bak-reentry-install"
old_bak.write_text("the old rolling copy\n", encoding="utf-8")
write(cfg, block("2.0.0"))
at_version("2.1.0")
install_rules._install_block()
check("old backup untouched", old_bak.read_text(encoding="utf-8"), "the old rolling copy\n")

print()
if fails:
    print(f"FAILED: {fails}")
    sys.exit(1)
print("ALL PASS")
