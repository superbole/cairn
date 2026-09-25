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

print("\n14. B63: a NEWER installed block and an OLDER plugin: refused, nothing written or backed up")
cfg = sandbox("newer")
at_version("1.62.0")
newer = ABOVE + block("1.62.0") + BELOW
write(cfg, newer)
before = (cfg / "CLAUDE.md").read_bytes()
at_version("1.60.0")
report, in_ctx = install_rules._install_block()
check("file byte-identical", (cfg / "CLAUDE.md").read_bytes(), before)
check("no backup written", backups(cfg), [])
check("exactly one report line", len((report or "").splitlines()), 1)
check("the line names both versions",
      bool(report and "v1.62.0" in report and "v1.60.0" in report), True)
check("it is a refusal in the MalformedBlock voice, not an update",
      bool(report and report.startswith("[to the agent] Did NOT update the cairn rules block in")
           and "Updated" not in report), True)
check("it names the remedy", bool(report and "claude plugin update cairn@superbole" in report), True)
check("in context: the file still holds the rules this session read", in_ctx, True)
report2, _ = install_rules._install_block()
check("repeats next session (nothing else will fix it)", report2, report)
check("still no backup after the repeat", backups(cfg), [])

print("\n14b. B63: a newer LEGACY-header block is kept too (numeric compare, not string)")
cfg = sandbox("newer-legacy")
text = ABOVE + legacy_block("1.10.0") + BELOW          # "1.10.0" < "1.9.0" as strings; newer as versions
write(cfg, text)
at_version("1.9.0")
report, in_ctx = install_rules._install_block()
check("refused", bool(report and "Did NOT update" in report and "v1.10.0" in report), True)
check("file untouched", read(cfg), text)

print("\n15. B63: an OLDER installed block and a NEWER plugin still upgrades, as today")
cfg = sandbox("older")
at_version("1.60.0")
write(cfg, ABOVE + block("1.60.0") + BELOW)
at_version("1.62.0")
report, in_ctx = install_rules._install_block()
check("update reported", bool(report and "v1.60.0 → v1.62.0" in report), True)
check("replaced", read(cfg), ABOVE + block("1.62.0") + BELOW)
check("one backup", len(backups(cfg)), 1)

print("\n16. B63: an UNPARSEABLE installed version falls through to today's write")
cfg = sandbox("unparseable")
text = ABOVE + "<!-- reentry:begin v9.0.0-rc1 -->\nold\n<!-- reentry:end -->\n" + BELOW
write(cfg, text)
at_version("1.62.0")
report, in_ctx = install_rules._install_block()
check("written and reported as an update",
      bool(report and "v9.0.0-rc1 → v1.62.0" in report), True)
check("replaced", read(cfg), ABOVE + block("1.62.0") + BELOW)

print("\n16b. B63: an unreadable plugin.json (`_plugin_version()` == '0') is no evidence either")
cfg = sandbox("sentinel")
at_version("1.62.0")
write(cfg, block("1.62.0"))
at_version("0")
report, _ = install_rules._install_block()
check("not reported as a downgrade refusal", bool(report and "NEWER" in report), False)

print("\n16c. The shared comparison helper")
cv = install_rules.compare_versions
check("1.10.0 > 1.9.0", cv("1.10.0", "1.9.0"), 1)
check("1.62 == 1.62.0", cv("1.62", "1.62.0"), 0)
check("1.60.0 < 1.62.0", cv("1.60.0", "1.62.0"), -1)
check("pre-release does not parse", cv("1.62.0-rc1", "1.60.0"), None)
check("None does not parse", cv(None, "1.60.0"), None)
check("empty does not parse", cv("", "1.60.0"), None)

print("\n17. B26: the change line says WHAT moved (fixture bodies, not the live rules text)")
# Fixtures, not `rules/CLAUDE.md`: its content changes under other work, and a count asserted
# against it would rot at the next rules edit.
FIX_A = "# Title\n\nintro\n\n## Alpha\n\nalpha one\nalpha two\n\n## Beta\n\nbeta one\n"
FIX_B = "# Title\n\nintro\n\n## Alpha\n\nalpha one\nalpha two edited\n\n## Beta\n\nbeta one\nbeta two new\n"
saved_source = install_rules._rules_source
install_rules._rules_source = lambda: FIX_A
cfg = sandbox("summary")
at_version("3.0.0")
install_rules._install_block()
install_rules._rules_source = lambda: FIX_B
at_version("3.1.0")
report, _ = install_rules._install_block()
check("version change still named", bool(report and "v3.0.0 → v3.1.0" in report), True)
check("nonzero count: +1 added, ~1 changed", bool(report and "+1 −0 ~1 lines" in report), True)
check("names the touched sections", bool(report and "in: Alpha, Beta." in report), True)
bak = backups(cfg)[0]
check("gives the exact diff command against the backup",
      bool(report and f'git diff --no-index -- "{bak}" "{cfg / "CLAUDE.md"}"' in report), True)
check("still ONE line", len(report.splitlines()), 1)

print("\n17b. B26: the diff command it prints actually shows the change")
import subprocess                                                        # noqa: E402
cmd = ["git", "diff", "--no-index", "--", str(bak), str(cfg / "CLAUDE.md")]
out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
check("diff shows the edited line", "+alpha two edited" in out and "+beta two new" in out, True)

print("\n18. B26: same version, edited content — informative instead of `vX → vX`")
cfg = sandbox("summary-samever")
install_rules._rules_source = lambda: FIX_A
at_version("3.0.0")
install_rules._install_block()
install_rules._rules_source = lambda: FIX_B
report, _ = install_rules._install_block()
check("says same version, different content",
      bool(report and "v3.0.0 → v3.0.0 (same version, different content)" in report), True)
check("carries the summary", bool(report and "~1 lines" in report), True)

print("\n19. B26: a pure version bump says the rules text did not change")
cfg = sandbox("summary-bumponly")
install_rules._rules_source = lambda: FIX_A
at_version("3.0.0")
install_rules._install_block()
at_version("3.0.1")
report, _ = install_rules._install_block()
check("no fake count from the header line", bool(report and "only the version marker moved" in report), True)

print("\n20. B26: a wholesale change is bounded")
many = "# Title\n\n" + "".join(f"## Section number {i} with a deliberately long heading name\n\nx{i}\n\n"
                              for i in range(40))
cfg = sandbox("summary-wholesale")
write(cfg, ABOVE + legacy_block("1.60.0") + BELOW)
install_rules._rules_source = lambda: many
at_version("3.0.0")
report, _ = install_rules._install_block()
check("names at most three sections, then +N more", bool(report and "(+" in report and " more)" in report), True)
check("heading names truncated", bool(report and "…" in report), True)
check("line stays bounded (< 700 chars incl. two paths)", len(report) < 700, True)

print("\n21. B26: the silent path computes NOTHING — the summary is never called there, nor on a refusal")
saved_summary = install_rules._change_summary


def _boom(*_a):
    raise AssertionError("summary computed")


install_rules._change_summary = _boom
cfg = sandbox("summary-silent")
install_rules._rules_source = lambda: FIX_A
at_version("3.0.0")
install_rules._install_block()                          # fresh install: no summary path either
report, in_ctx = install_rules._install_block()
check("unchanged: silent", (report, in_ctx), (None, True))
check("unchanged: no backup", backups(cfg), [])
at_version("2.0.0")
report, _ = install_rules._install_block()
check("downgrade refusal: no summary attempted, still refuses", bool(report and "Did NOT update" in report), True)
print("\n21b. B26: a summary that fails degrades to the pre-B26 line, never to silence")
at_version("3.2.0")
report, _ = install_rules._install_block()
check("update still reported", bool(report and "v3.0.0 → v3.2.0" in report and "Full diff" not in report), True)
install_rules._change_summary = saved_summary
install_rules._rules_source = saved_source

print()
if fails:
    print(f"FAILED: {fails}")
    sys.exit(1)
print("ALL PASS")
