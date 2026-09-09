"""Characterisation test for `backlog_file.parse()` and friends (issue #69, issue #30).

    python plugins/cairn/tools/test_backlog_file.py

WHY THIS EXISTS. `backlog_file.py` had no test targeting `parse()` even though it is the one
function two fixes changed: B69 (a `## ` subsection heading inside an item's own body truncated
the item and silently dropped everything after it, up to the next real `## Bn.` heading) — FIXED:
`parse()` now ends an item only at a real `_ITEM_RE` match or an `_ITEMISH_RE`-shaped heading,
never at a bare `## `, so a subsection inside the body survives. And B30 (`_CLOSED_RE` requires a
date, so a fields line saying `closed` or `**closed**` with NO date parsed as if there were no
closed marker at all — the item read as still open) — FIXED as a WARNING, not a looser regex: the
undated marker still parses `closed=None` (no date is invented), but the item is now flagged
`closed_undated` and surfaced by `undated_closed_items()` so a caller can say so.

Both were originally pinned here EXACTLY as they behaved before the fix, named unmistakably as
bugs, so the fix would land against a red test rather than a green one that happened to encode the
bug as the spec. Both are now flipped to assert the corrected behaviour, per that plan.

Also covers the plain contract: `parse()`/`render()`/`write()` round-trip an item unchanged,
`unparsed_headings()` finds item-shaped headings this parser cannot read, `write()` refuses to
regenerate a file that would drop them (`force=True` is the documented escape hatch), and
`changelog_covers()` (B45) reads `CHANGELOG.md` for a dated entry naming a closed item.

Sections 9-12, added 2026-09-06, cover the 2026-09-05 numbering incident and its fallout:
B75 (`read_next_id_marker()` — a floor that survives a closed item being dropped from the file),
B79 (`duplicate_ids()` — an offline, one-line assert that two items never silently share an id),
B80 (`_origin_floor()` — `next_id()` also consults the last-fetched `origin/<branch>`, in a REAL
throwaway git repo with a real remote, not a stub), and B85 (fenced code blocks can no longer
spawn phantom items or move `next_id()` — parsed with the exact quoted-evidence shape that broke
this file in the first place, including the write-back corruption the incident found).

Everything here runs against throwaway fixture files under a temp directory. Nothing touches the
repo's own BACKLOG.md, and nothing writes outside `tempfile.mkdtemp()`.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(ROOT / "hooks"))

import backlog_file                                     # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def _raises(fn):
    try:
        fn()
    except Exception as exc:
        return type(exc).__name__
    return None


def fixture(name):
    """A fresh throwaway directory to hold one BACKLOG.md."""
    return Path(tempfile.mkdtemp(prefix="backlog-file-%s-" % name))


print("1. parse() / render() / write() round-trip an item unchanged")
fx1 = fixture("roundtrip")
item = {
    "n": 5, "title": "Round trip item",
    "model": "Sonnet 5", "effort": "medium", "attend": "HITL", "mode": "Auto",
    "added": "2026-08-01", "issue": 42, "queued": True, "inbound": False, "closed": None,
    "text": "Intro paragraph.\n\nSecond paragraph with a [brief](briefs/x.md) link.",
}
backlog_file.write(fx1, [item], "TestProject")
raw = (fx1 / "BACKLOG.md").read_text(encoding="utf-8")
parsed = backlog_file.parse(fx1)
check("one item parsed back", len(parsed), 1)
p = parsed[0]
check("n survives", p["n"], 5)
check("title survives", p["title"], "Round trip item")
check("model survives", p["model"], "Sonnet 5")
check("effort survives", p["effort"], "medium")
check("attend survives", p["attend"], "HITL")
check("mode survives", p["mode"], "Auto")
check("added survives", p["added"], "2026-08-01")
check("issue survives", p["issue"], 42)
check("queued survives", p["queued"], True)
check("inbound survives", p["inbound"], False)
check("closed stays None", p["closed"], None)
check("brief extracted from body", p["brief"], "briefs/x.md")
check("body text survives verbatim, blank line included", p["text"],
      "Intro paragraph.\n\nSecond paragraph with a [brief](briefs/x.md) link.")
check("re-rendering the parse reproduces the file byte-for-byte",
      backlog_file.render(parsed, "TestProject"), raw)

print("\n2. parse() no longer truncates an item at a '## ' subsection in its body (FIXED, B69)")
fx2 = fixture("subsection-bug")
item10 = {
    "n": 10, "title": "Subsection bug item", "added": "2026-08-01",
    "text": "Intro text before the subsection.\n\n## Some Subsection\n\n"
            "This paragraph is lost to the bug.",
}
item11 = {
    "n": 11, "title": "Next real item", "added": "2026-08-02",
    "text": "Next item body, unaffected.",
}
backlog_file.write(fx2, [item10, item11], "TestProject")
parsed2 = backlog_file.parse(fx2)
check("still exactly two items (the subsection heading spawns no phantom item)",
      len(parsed2), 2)
check("FIXED: item 10's body survives past its own '## ' subsection heading",
      parsed2[0]["text"],
      "Intro text before the subsection.\n\n## Some Subsection\n\n"
      "This paragraph is lost to the bug.")
check("FIXED: the paragraph after the subsection is no longer dropped",
      "This paragraph is lost to the bug." in parsed2[0]["text"], True)
check("item 11 (after the boundary) is unaffected", parsed2[1]["text"],
      "Next item body, unaffected.")
# write() regenerates from the (now-intact) parse, so the round trip holds.
backlog_file.write(fx2, parsed2, "TestProject")
after = (fx2 / "BACKLOG.md").read_text(encoding="utf-8")
check("FIXED: write() persists the full body — the paragraph is still there",
      "This paragraph is lost to the bug." in after, True)

print("\n2b. a '### ' sub-heading (three hashes) in the body is already safe")
fx2b = fixture("subsection-safe")
item12 = {
    "n": 12, "title": "Subsection-safe item", "added": "2026-08-03",
    "text": "Intro.\n\n### Real sub-heading\n\nThis paragraph must survive.",
}
backlog_file.write(fx2b, [item12], "TestProject")
parsed2b = backlog_file.parse(fx2b)
check("one item, body intact including the '### ' line", parsed2b[0]["text"],
      "Intro.\n\n### Real sub-heading\n\nThis paragraph must survive.")

print("\n3. an undated 'closed' marker still parses as NOT closed, but is now FLAGGED (FIXED,"
      " B30 — the fix is a warning, not a looser regex that would invent a date they never wrote)")
fx3 = fixture("closed-bug")
(fx3 / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n"
    "## B20. Bare closed marker, no date\n"
    "`Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-08-01` · closed\n\n"
    "Should read as closed, but the parser needs a date to see the marker at all.\n\n"
    "## B21. Bold closed marker, no date\n"
    "added `2026-08-02` · **closed**\n\n"
    "Same bug, bold-markdown spelling.\n", encoding="utf-8")
parsed3 = backlog_file.parse(fx3)
by_n = {i["n"]: i for i in parsed3}
check("two items parsed", sorted(by_n), [20, 21])
check("bare 'closed' (no date) still reads as closed=None — no date is invented",
      by_n[20]["closed"], None)
check("'**closed**' (no date) also still reads as closed=None", by_n[21]["closed"], None)
open_ns = sorted(i["n"] for i in backlog_file.open_items(fx3))
check("both therefore still count as OPEN — that has not changed",
      open_ns, [20, 21])
check("FIXED: bare 'closed' is now FLAGGED closed_undated, so a caller can warn",
      by_n[20]["closed_undated"], True)
check("FIXED: '**closed**' is also flagged closed_undated",
      by_n[21]["closed_undated"], True)
check("FIXED: undated_closed_items() surfaces both, in file order",
      [i["n"] for i in backlog_file.undated_closed_items(parsed3)], [20, 21])
# A properly dated closed marker is NOT affected by the bug — confirms the regex path itself
# works and the failure above is specifically the missing-date case.
fx3b = fixture("closed-good")
(fx3b / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n"
    "## B1. Properly closed\n"
    "added `2026-08-01` · closed `2026-08-05`\n\nbody\n", encoding="utf-8")
p3b = backlog_file.parse(fx3b)[0]
check("a DATED closed marker parses correctly", p3b["closed"], "2026-08-05")
check("and is NOT flagged closed_undated", p3b["closed_undated"], False)
check("and is excluded from open_items()", backlog_file.open_items(fx3b), [])
check("undated_closed_items() is empty when every closed marker carries a date",
      backlog_file.undated_closed_items([p3b]), [])

print("\n4. unparsed_headings() names item-shaped headings parse() cannot read (B46: a bare")
print("   integer heading is now an accepted alias for 'Bn' — only the letter suffix is not)")
fx4 = fixture("unparsed-headings")
(fx4 / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n"
    "## B7. Well-formed\n"
    "added `2026-08-01`\n\nbody seven\n\n"
    "## 12. Bare integer, no B prefix\n"
    "added `2026-08-02`\n\nbody twelve\n\n"
    "## 2b. Malformed letter suffix\n"
    "added `2026-08-03`\n\nbody two-b\n", encoding="utf-8")
stranded = backlog_file.unparsed_headings(fx4)
check("FIXED (B46): only ONE malformed heading now, not two", len(stranded), 1)
check("the well-formed B7 heading is not among them",
      any("B7" in s for s in stranded), False)
check("FIXED (B46): the bare-integer heading is no longer stranded — it parses as item 12",
      any(s.startswith("## 12.") for s in stranded), False)
check("the letter-suffix heading is STILL named — '2b' has no integer for n to become",
      any(s.startswith("## 2b.") for s in stranded), True)
check("parse() now sees BOTH well-formed items — 7 and the bare-integer 12",
      [i["n"] for i in backlog_file.parse(fx4)], [7, 12])
check("exists() is false for a directory with no BACKLOG.md",
      backlog_file.exists(fixture("no-file")), False)

print("\n5. write() refuses to regenerate a file with stranded headings; force=True escapes it")
check("write() without force raises Unreadable (the '2b' heading is still stranded)",
      _raises(lambda: backlog_file.write(fx4, backlog_file.parse(fx4), "Test")), "Unreadable")
check("the file on disk is untouched by the refused write",
      "## 2b." in (fx4 / "BACKLOG.md").read_text(encoding="utf-8"), True)
check("write() with force=True does NOT raise",
      _raises(lambda: backlog_file.write(fx4, backlog_file.parse(fx4), "Test", force=True)), None)
after4 = (fx4 / "BACKLOG.md").read_text(encoding="utf-8")
check("force=True regenerates from the (partial) parse; the still-unreadable '2b' is gone",
      "## 2b." in after4, False)
check("...and the well-formed item survived the regeneration",
      "## B7." in after4, True)
check("B46: the bare-integer item survived too, CANONICALISED to '## Bn.' form on write",
      "## B12." in after4, True)

print("\n6. supporting reads: counts(), next_id(), summary_lines(), open_items()")
fx6 = fixture("counts")
items6 = [
    {"n": 1, "title": "Queued item", "attend": "AFK", "added": "2026-08-01",
     "queued": True, "text": ""},
    {"n": 2, "title": "Pullable AFK item", "attend": "AFK", "added": "2026-08-02",
     "text": ""},
    {"n": 3, "title": "Pullable HITL item", "attend": "HITL", "added": "2026-08-03",
     "text": ""},
    {"n": 4, "title": "Closed item", "added": "2026-08-04", "closed": "2026-08-05",
     "text": ""},
]
backlog_file.write(fx6, items6, "TestProject")
check("next_id() is max(n)+1", backlog_file.next_id(fx6), 5)
check("counts(): 2 pullable, 1 AFK among them, 1 queued", backlog_file.counts(fx6), (2, 1, 1))
check("open_items() excludes the closed one",
      sorted(i["n"] for i in backlog_file.open_items(fx6)), [1, 2, 3])
lines6 = backlog_file.summary_lines(fx6)
check("summary_lines() reports something when there is pullable work", len(lines6) > 0, True)
check("next_id() on an empty project is 1", backlog_file.next_id(fixture("empty")), 1)
check("summary_lines() is silent for a missing BACKLOG.md",
      backlog_file.summary_lines(fixture("no-backlog")), [])

print("\n7. changelog_covers() (B45) — is a closed item actually named in CHANGELOG.md?")
fx7 = fixture("changelog-covers")
(fx7 / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n"
    "## 2026-09-04 — a later entry naming the item\n\n"
    "**B69 closed.** Fixed the subsection-truncation parser bug.\n\n"
    "## 2026-09-03 — a stray fix, named only by its issue number\n\n"
    "Closed out issue #42 with a one-line patch, no backlog item ever filed for it.\n\n"
    "## 2026-09-01 — an earlier entry, before the item was even closed\n\n"
    "**B69 closed.** This one is too EARLY to count as coverage.\n\n"
    "## 2026-08-20 — unrelated work\n\n"
    "Something else entirely, no B-number and no relevant title words.\n",
    encoding="utf-8")
item_b69 = {"n": 69, "title": "sync_backlog.py parser truncates an item", "closed": "2026-09-02"}
check("a same-or-later dated entry naming 'B69' counts as coverage",
      backlog_file.changelog_covers(fx7, item_b69), True)
item_uncovered = {"n": 999, "title": "Nothing anywhere mentions this one",
                  "closed": "2026-09-02"}
check("an item no entry (at or after its close date) names is NOT covered",
      backlog_file.changelog_covers(fx7, item_uncovered), False)
item_issue = {"n": 5, "title": "Something else entirely", "issue": 42, "closed": "2026-09-02"}
check("issue #42 also counts as coverage even without a matching B-number or title",
      backlog_file.changelog_covers(fx7, item_issue), True)
item_open = {"n": 1, "title": "Not closed", "closed": None}
check("an item that is not closed trivially counts as covered (nothing to verify)",
      backlog_file.changelog_covers(fx7, item_open), True)
check("a missing CHANGELOG.md reads as NOT covered, never as 'assume it's fine'",
      backlog_file.changelog_covers(fixture("no-changelog"), item_b69), False)

print("\n8. B46 — a bare '## 12.' heading round-trips as an alias for '## B12.', not verbatim")
fx8 = fixture("bare-integer-alias")
(fx8 / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n"
    "## 30. Written from a phone, no B prefix\n"
    "added `2026-09-05`\n\nbody thirty\n", encoding="utf-8")
parsed8 = backlog_file.parse(fx8)
check("one item parsed from the bare heading", len(parsed8), 1)
check("n is the integer, exactly as '## B30.' would have given", parsed8[0]["n"], 30)
check("title parses past the bare integer heading",
      parsed8[0]["title"], "Written from a phone, no B prefix")
check("body is untouched", parsed8[0]["text"], "body thirty")
# DECIDED (see docs/review/sync-honesty.md): write() CANONICALISES to '## Bn.' rather than
# preserving the bare form they wrote — render() already emits `## B{n}.` unconditionally for
# every item regardless of source shape, so this is existing behaviour applied to a newly
# tolerated input, not a new special case.
after8 = backlog_file.render(parsed8, "Test")
check("re-render uses the canonical '## B30.' heading",
      "## B30. Written from a phone, no B prefix" in after8, True)
check("the bare '## 30.' form does not survive the regenerate", "## 30." in after8, False)
# A second parse of the CANONICALISED output is stable — parsing it again changes nothing.
fx8b = fixture("bare-integer-alias-2")
(fx8b / "BACKLOG.md").write_text(after8, encoding="utf-8")
check("parsing the canonicalised file gives the same item back",
      backlog_file.parse(fx8b)[0]["n"], 30)

print("\n9. B75 — the next-id marker is a floor that SURVIVES a closed item being dropped")
fx9 = fixture("next-id-marker")
items9 = [{"n": n, "title": f"Item {n}", "added": "2026-09-01", "text": ""}
          for n in (1, 2, 3, 10)]
backlog_file.write(fx9, items9, "Test")
raw9 = (fx9 / "BACKLOG.md").read_text(encoding="utf-8")
check("write() stamps a next-id marker matching the current max",
      "<!-- next-id: 10 -->" in raw9, True)
check("read_next_id_marker() reads it back", backlog_file.read_next_id_marker(fx9), 10)
check("next_id() is one past the marker (same as one past the parsed max, here)",
      backlog_file.next_id(fx9), 11)
# Simulate exactly what a sync does: item 10 closes, then a later cycle drops it, leaving
# only items the sync never touched. Old behaviour (max(parsed ns)+1) would now hand out
# B4 — a number B10 already spent. The marker must stop that.
backlog_file.write(fx9, [items9[0], items9[1]], "Test")   # only items 1 and 2 survive
raw9b = (fx9 / "BACKLOG.md").read_text(encoding="utf-8")
check("FIXED (B75): the marker does NOT drop back down to the new max (2)",
      "<!-- next-id: 10 -->" in raw9b, True)
check("FIXED (B75): next_id() still refuses to re-hand-out B10 or anything below it",
      backlog_file.next_id(fx9), 11)
check("parse() itself still only sees the two items actually in the file",
      sorted(i["n"] for i in backlog_file.parse(fx9)), [1, 2])
# Backward compatibility: a file written before B75 shipped has no marker at all. next_id()
# must fall back to the old parsed-max behaviour rather than erroring or stalling at 1.
fx9c = fixture("next-id-marker-legacy")
(fx9c / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n## B7. Pre-B75 item, no marker\nadded `2026-08-01`\n\nbody\n",
    encoding="utf-8")
check("read_next_id_marker() is 0 for a file with no marker at all",
      backlog_file.read_next_id_marker(fx9c), 0)
check("next_id() still falls back to max(parsed)+1 with no marker present",
      backlog_file.next_id(fx9c), 8)

print("\n10. B79 — duplicate_ids() names ids that appear on more than one item, and")
print("    summary_lines() surfaces it even when NOTHING is pullable (never silenced)")
check("duplicate_ids() is empty for a clean list",
      backlog_file.duplicate_ids([{"n": 1, "title": "a"}, {"n": 2, "title": "b"}]), {})
dup_items = [{"n": 5, "title": "First claim on B5"}, {"n": 5, "title": "Second claim on B5"},
             {"n": 6, "title": "Unique"}]
check("duplicate_ids() names the id and both titles fighting over it",
      backlog_file.duplicate_ids(dup_items),
      {5: ["First claim on B5", "Second claim on B5"]})
# A real collision on disk: two sessions' `## B5.` headings in one file, both closed so
# there is nothing else for summary_lines() to report -- this is the case the brief calls
# out explicitly: a duplicate is never allowed to hide behind the "nothing pullable" silence.
fx10 = fixture("duplicate-on-disk")
(fx10 / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n"
    "## B5. First session's B5\n"
    "added `2026-09-05` · closed `2026-09-05`\n\nbody one\n\n"
    "## B5. Second session's B5\n"
    "added `2026-09-05` · closed `2026-09-05`\n\nbody two\n", encoding="utf-8")
check("parse() sees both items sharing n=5 (parse() itself never dedupes)",
      [i["n"] for i in backlog_file.parse(fx10)], [5, 5])
lines10 = backlog_file.summary_lines(fx10)
check("FIXED (B79): summary_lines() is NOT silent even though nothing is pullable",
      len(lines10) > 0, True)
check("the duplicate line names B5 and both titles",
      any("B5" in ln and "First session's B5" in ln and "Second session's B5" in ln
          for ln in lines10), True)

print("\n11. B80 — next_id() also consults the last-fetched origin/<branch>, in a REAL repo")
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _git(cwd, *args):
    return subprocess.run(("git", *args), cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", **NW)


bare = fixture("origin-bare")
_git(bare, "init", "-q", "--bare", "-b", "main")
upstream = fixture("origin-upstream")
_git(upstream, "init", "-q", "-b", "main")
_git(upstream, "remote", "add", "origin", str(bare))
backlog_file.write(upstream, [{"n": n, "title": f"Item {n}", "added": "2026-09-01", "text": ""}
                              for n in (1, 2, 50)], "Test")
_git(upstream, "add", "BACKLOG.md")
_git(upstream, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed")
r = _git(upstream, "push", "-q", "origin", "main")
check("test setup: seeded upstream pushed to the bare 'origin' cleanly", r.returncode, 0)

behind = fixture("origin-behind")
_git(behind, "init", "-q", "-b", "main")
_git(behind, "remote", "add", "origin", str(bare))
_git(behind, "fetch", "-q", "origin")
# This checkout's OWN BACKLOG.md never saw item 50 -- it is behind, exactly like the stale
# checkout in the B75 writeup. A commit is needed so `HEAD` resolves to a real branch name
# rather than an unborn one.
backlog_file.write(behind, [{"n": 1, "title": "Item 1", "added": "2026-09-01", "text": ""}],
                    "Test")
_git(behind, "add", "BACKLOG.md")
_git(behind, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "local only")
check("local file alone would only reach B1 (its own max)",
      max(i["n"] for i in backlog_file.parse(behind)), 1)
check("FIXED (B80): _origin_floor() reads item 50 off the FETCHED origin/main, not the net",
      backlog_file._origin_floor(behind), 50)
check("FIXED (B80): next_id() picks up the higher origin floor, not just the local file",
      backlog_file.next_id(behind), 51)

no_remote = fixture("origin-no-remote")
_git(no_remote, "init", "-q", "-b", "main")
check("_origin_floor() is 0 with git present but no 'origin' remote at all",
      backlog_file._origin_floor(no_remote), 0)
check("_origin_floor() is 0 for a directory that is not a git repo at all",
      backlog_file._origin_floor(fixture("origin-not-a-repo")), 0)

print("\n12. B85 — a `## Bn.` heading quoted inside a fenced code block is never structure")
fx12 = fixture("fenced-heading")
(fx12 / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n"
    "## B84. The repo's own real, current item\n"
    "added `2026-09-05`\n\n"
    "Evidence pasted verbatim, exactly as B85 describes:\n\n"
    "```\n"
    "$ git show b629d4b:BACKLOG.md | grep -E \"^## B133.\"\n"
    "## B133. A post-session can ask a question the state layer never sees\n"
    "```\n\n"
    "End of body.\n", encoding="utf-8")
parsed12 = backlog_file.parse(fx12)
check("FIXED (B85): only the ONE real item is parsed, not a phantom B133 from the fence",
      [i["n"] for i in parsed12], [84])
check("the quoted heading text survives verbatim in the body (never deleted, just not",
      "## B133. A post-session can ask a question the state layer never sees"
      in parsed12[0]["text"], True)
check("FIXED (B85): next_id() is 85, not 134 — the fence never inflates the series",
      backlog_file.next_id(fx12), 85)
check("FIXED (B85): unparsed_headings() does not flag the fenced line as stranded either",
      backlog_file.unparsed_headings(fx12), [])
check("FIXED (B85): duplicate_ids() sees no duplicate from a quoted heading",
      backlog_file.duplicate_ids(parsed12), {})

print("\n12b. B85's write-back: round-tripping a fenced heading through write() must not")
print("     inject a fields line INTO the quoted evidence")
backlog_file.write(fx12, parsed12, "Test")
after12 = (fx12 / "BACKLOG.md").read_text(encoding="utf-8")
check("still exactly one real item after the round trip",
      [i["n"] for i in backlog_file.parse(fx12)], [84])
check("the fenced block is carried through untouched, no 'added `...`' line inserted into it",
      "## B133. A post-session can ask a question the state layer never sees\n```"
      in after12, True)
check("a SECOND round trip is stable (idempotent) -- no drift on repeated syncs",
      backlog_file.next_id(fx12), 85)

print("\n12c. a fence containing a next-id marker-shaped line does not move the real floor")
fx12c = fixture("fenced-marker")
(fx12c / "BACKLOG.md").write_text(
    "# BACKLOG — Test\n\n"
    "## B3. Real item\n"
    "added `2026-09-05`\n\n"
    "```\n"
    "<!-- next-id: 9999 -->\n"
    "```\n", encoding="utf-8")
check("FIXED (B85): a marker-shaped line inside a fence does not become the real floor",
      backlog_file.read_next_id_marker(fx12c), 0)
check("next_id() falls back to the real parsed max, not the fenced 9999",
      backlog_file.next_id(fx12c), 4)

print("\n12d. B85 (its own 'worth checking' note) — changelog_status()'s entry split is")
print("     ALSO fence-aware, so quoted CHANGELOG evidence cannot fake a date boundary or")
print("     fake coverage")
fx12d = fixture("changelog-fenced")
(fx12d / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n"
    "## 2026-09-05 — real entry, no coverage for the item under test\n\n"
    "Unrelated work. Includes pasted evidence naming a DIFFERENT item, fenced:\n\n"
    "```\n"
    "## 2026-09-06 — a fake later date, quoted, not a real entry\n\n"
    "**B900 closed.** Nothing real ever happened here.\n"
    "```\n\n"
    "End of entry.\n", encoding="utf-8")
item_fenced_date = {"n": 900, "title": "Item only 'covered' inside the fenced quote",
                    "closed": "2026-09-05"}
check("FIXED: the fenced '## 2026-09-06' heading is not read as a real entry boundary "
      "(a bare no-date-match would otherwise be uncovered vs. mis-split as 2 entries)",
      backlog_file.changelog_status(fx12d, item_fenced_date), "uncovered")
check("FIXED: the fenced '**B900 closed.**' text does not count as real coverage either",
      backlog_file.changelog_covers(fx12d, item_fenced_date), False)
# The real (unfenced) case still works exactly as B45 always intended.
fx12d2 = fixture("changelog-fenced-real")
(fx12d2 / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n## 2026-09-05 — real coverage\n\n**B901 closed.** Done for real.\n",
    encoding="utf-8")
check("a genuine (unfenced) entry still counts as coverage",
      backlog_file.changelog_covers(fx12d2, {"n": 901, "title": "x", "closed": "2026-09-05"}),
      True)

print("\n13. B88 — the SAME-CALENDAR-DAY gap in changelog_status(), confirmed and NOT fixed")
print("    (see the KNOWN RESIDUAL GAP note on changelog_status() for the full reasoning)")

# 13a. THE REPORTED CASE, reproduced from a synthetic fixture (not the real repo's file): a
# single dated entry, same calendar day as `closed`, whose ONLY mention of the item is a
# non-shipping one ("Bn filed"). The existing date-gate (`h.group(1) < closed`) does NOT
# exclude this entry — it is not BEFORE `closed`, only not-after it either — so the bare-token
# match still fires. This is the real mechanism, confirmed by direct reproduction; it does NOT
# require a second, later entry to exist (see 13b for why the multi-entry theory floated
# before this test ran turned out not to be the actual cause).
fx13a = fixture("changelog-same-day-stale-mention")
(fx13a / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n"
    "## 2026-09-06 - the numbering bug, reconciled across two machines\n\n"
    "**B86 filed** - B22 shipped yesterday saying an unattended item stops before the push, "
    "and nothing verifies it did.\n",
    encoding="utf-8")
item_b86_stale = {"n": 86, "title": "Nothing verifies that the push actually stopped",
                   "closed": "2026-09-06"}
check("KNOWN GAP (B88, not fixed): a same-day 'filed'-only mention still reads as covered",
      backlog_file.changelog_status(fx13a, item_b86_stale), "covered")

# 13b. Why "trust only the topmost same-day entry" was REJECTED, not merely unconsidered:
# it does not even fix 13a (the stale entry IS the sole/topmost same-day entry there), and it
# actively regresses the common case — this project's OWN CHANGELOG.md routinely carries
# several separate entries under one calendar day for unrelated items (2026-09-05 alone has
# six). Reproduced here: the topmost same-day entry is unrelated to the item under test; the
# REAL shipping mention is in a second, older entry the same day. Current (unfixed) code
# checks every eligible header, not just the topmost, and gets this right.
fx13b = fixture("changelog-same-day-multi-entry")
(fx13b / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n"
    "## 2026-09-06 (v1.42.0) - wave 1 of an overnight batch\n\n"
    "Unrelated work this session also shipped; no mention of B77 anywhere in this entry.\n\n"
    "## 2026-09-06 - an older entry the same day\n\n"
    "**B77 closed.** The actual fix, written earlier the same day.\n",
    encoding="utf-8")
item_b77 = {"n": 77, "title": "Some other item entirely", "closed": "2026-09-06"}
check("a real same-day mention in a NON-topmost entry still correctly counts as covered "
      "(this is exactly what a topmost-only restriction would have broken)",
      backlog_file.changelog_status(fx13b, item_b77), "covered")

# 13c. Baseline sanity: a genuine, sole same-day entry using the established shipping
# convention ("**Bn closed.**") reads as covered, as it always has — the gap in 13a is about
# a non-shipping mention specifically, not about same-day entries in general.
fx13c = fixture("changelog-same-day-real")
(fx13c / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n## 2026-09-06 — shipped today\n\n**B55 closed.** Done for real, same day.\n",
    encoding="utf-8")
check("a genuine same-day shipping entry still reads as covered",
      backlog_file.changelog_status(fx13c, {"n": 55, "title": "x", "closed": "2026-09-06"}),
      "covered")

print("\n14. B83 — a CHANGELOG date is recognised anywhere in a depth 2-4 heading, not only a")
print("     '## YYYY-MM-DD' prefix; and the 'no-changelog' message distinguishes missing from")
print("     unparseable")

# 14a. The real atlas shape that the old, narrower `_CHANGELOG_DATE_RE` matched ZERO times:
# a `###` heading with the date in the middle, not at the start.
fx14a = fixture("changelog-depth3-dates")
(fx14a / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n"
    "### rev 264 — 2026-09-05 — eight decisions answered, two evidence packs corrected\n\n"
    "**B3** — closed for real, in this project's own convention.\n\n"
    "### rev 263 — 2026-09-05 — a message that answers AND asks gets one reply, not two\n\n"
    "Unrelated work.\n",
    encoding="utf-8")
check("FIXED (B83): a date inside a '###' heading is now recognised as a dated entry",
      backlog_file.changelog_status(fx14a, {"n": 3, "title": "x", "closed": "2026-09-05"}),
      "covered")
check("_changelog_unreadable_reason() is None once a dated heading is found",
      backlog_file._changelog_unreadable_reason(fx14a), None)

# 14b. A `####` depth heading also matches; a `#` (depth 1) heading does not — the pattern is
# scoped to 2-4 exactly as B83 specified, not "any depth".
fx14b = fixture("changelog-depth4-and-depth1")
(fx14b / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n"
    "#### deep heading — 2026-09-05 — still recognised\n\n**B9** shipped.\n",
    encoding="utf-8")
check("a depth-4 '####' heading with a date is recognised too",
      backlog_file.changelog_status(fx14b, {"n": 9, "title": "x", "closed": "2026-09-05"}),
      "covered")
check("a bare depth-1 '# 2026-09-05 ...' heading is still NOT a dated entry (unchanged scope)",
      bool(backlog_file._CHANGELOG_DATE_RE.search("# 2026-09-05 not a real entry heading")),
      False)

# 14c. The two "no-changelog" sub-cases are now distinguishable via
# `_changelog_unreadable_reason()`, without changing `changelog_status()`'s own three-state
# return contract (every existing caller and test compares that value to an exact string).
check("missing CHANGELOG.md reads as 'missing', not 'unparseable'",
      backlog_file._changelog_unreadable_reason(fixture("no-changelog-14c")), "missing")
fx14d = fixture("changelog-unparseable")
(fx14d / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\nNo dated heading anywhere in this file at all.\n", encoding="utf-8")
check("a real CHANGELOG.md with no parseable dated heading reads as 'unparseable'",
      backlog_file._changelog_unreadable_reason(fx14d), "unparseable")
check("changelog_status() itself is unchanged: still the bare 'no-changelog' string either way",
      backlog_file.changelog_status(fx14d, {"n": 1, "title": "x", "closed": "2026-09-05"}),
      "no-changelog")

# 14d. fence_check.py's OWN mirror of `_CHANGELOG_DATE_RE` (a separate, hand-maintained
# pattern used to flag fenced text a parser would misread as structure) was updated in the
# same commit to accept the same broadened shapes — otherwise it would silently under-report
# fenced `###`-with-embedded-date lines that the real parser now treats as entry boundaries.
fence_check_src = (Path(__file__).resolve().parent / "fence_check.py").read_text(encoding="utf-8")
check("fence_check.py's mirrored CHANGELOG-date pattern was widened alongside the real one",
      r"^#{2,4}\s+.*?\d{4}-\d{2}-\d{2}\b" in fence_check_src, True)
import re as _re
_fence_pat = _re.compile(r"^#{2,4}\s+.*?\d{4}-\d{2}-\d{2}\b")
check("...and it actually matches the atlas-style embedded-date heading",
      bool(_fence_pat.match("### rev 264 — 2026-09-05 — eight decisions answered")), True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
