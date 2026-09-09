"""Flag safety for the tools that shell out to an issue host CLI (issue #18, v1.22.0).

    python plugins/cairn/tools/test_sync_flags.py

WHY THIS IS A TEST AND NOT A CODE REVIEW. All three scripts read `sys.argv` by hand, so an
unrecognised flag fell straight through to the DEFAULT path — and for `sync_backlog.py` the
default path is the real sync. Two agents ran `--help` on 2026-08-30 expecting usage text and
pushed issue bodies to GitHub instead: an outward-facing write nobody chose, the second one
after the first was already logged in `~/.claude/MISTAKES.md`.

The regression is invisible from the outside — a silent fallthrough looks exactly like a tool
that ran correctly — so it needs a test that asserts on the CLI calls THEMSELVES.

THE SEAM MOVED IN v1.34.0 (issue #11). `sync_backlog._gh` is gone; every provider call now
goes through `issue_host.IssueHost._run`, so that ONE method is what gets replaced with a
recorder here. Backend-specific argv and detection are covered separately, in
`test_issue_host.py`. Nothing in either file touches the network, a host, or any file in the
repo.
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tools"))

import backlog_file                                    # noqa: E402
import issue_host                                      # noqa: E402
import sync_backlog as sb                              # noqa: E402
import label_backlog as lb                             # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def _raises(fn):
    """The exception class name a call raises, or None."""
    try:
        fn()
    except Exception as exc:
        return type(exc).__name__
    return None


def exits(label, fn, code):
    try:
        fn()
    except SystemExit as e:
        check(label, e.code, code)
        return
    check(label, "no SystemExit", code)


# `gh` verbs that CHANGE something on GitHub. Everything else is a read.
WRITES = {("issue", "create"), ("issue", "close"), ("issue", "edit"),
          ("label", "create"), ("label", "edit"), ("label", "delete")}


def items():
    """Four items covering every branch push() has: close, file, re-body, label-only."""
    return [
        {"n": 1, "title": "Already done", "model": "Sonnet 5", "effort": "medium",
         "attend": "AFK", "mode": "Auto", "added": "2026-08-01", "issue": 11,
         "queued": False, "inbound": False, "closed": "2026-08-30", "text": "t", "body": []},
        {"n": 2, "title": "Never synced", "model": "Opus 5", "effort": "high",
         "attend": "HITL", "mode": "Plan", "added": "2026-08-02", "issue": None,
         "queued": False, "inbound": False, "closed": None, "text": "t", "body": []},
        {"n": 3, "title": "Body has drifted", "model": None, "effort": None,
         "attend": "AFK", "mode": None, "added": "2026-08-03", "issue": 13,
         "queued": False, "inbound": False, "closed": None, "text": "new text", "body": []},
        {"n": 4, "title": "In step", "model": None, "effort": None,
         "attend": "AFK", "mode": None, "added": "2026-08-04", "issue": 14,
         "queued": False, "inbound": False, "closed": None, "text": "same", "body": []},
    ]


def remote_raw():
    """What `gh issue list --json` would return: #13 stale, #14 current, #15 unseen."""
    in_step = [i for i in items() if i["n"] == 4][0]
    return [
        {"number": 13, "title": "Body has drifted", "body": "the OLD body",
         "author": {"login": "example-user"}, "labels": [{"name": "backlog"}]},
        {"number": 14, "title": "In step", "body": sb._body(in_step),
         "author": {"login": "example-user"}, "labels": [{"name": "backlog"}, {"name": "afk"}]},
        {"number": 15, "title": "Filed by someone else", "body": "please fix",
         "author": {"login": "a-stranger"}, "labels": []},
    ]


def remote_norm():
    """The same three, in `issue_host`'s normalised shape — what the sync now sees."""
    return issue_host.GitHubHost.normalise(remote_raw())


def fake_run(calls, cli="gh"):
    """A stand-in for `IssueHost._run` — the ONE subprocess seam in the whole layer."""
    def _run(self, *args):
        calls.append(tuple(args))
        if args[:2] == ("repo", "view"):
            return json.dumps({"nameWithOwner": "example-user/agent-reentry",
                               "hasIssuesEnabled": True,
                               "owner": {"login": "example-user"}}), ""
        if args[:2] == ("issue", "list"):
            return json.dumps(remote_raw()), ""
        if args[:2] == ("issue", "create"):
            return "https://github.com/example-user/agent-reentry/issues/42\n", ""
        return "", ""
    return _run


def run(argv):
    """Run main() with every outward call recorded and every file write intercepted."""
    calls, written = [], []

    saved = (issue_host.IssueHost._run, issue_host.detect,
             backlog_file.exists, backlog_file.parse, backlog_file.unparsed_headings,
             backlog_file.write, backlog_file.counts, backlog_file.next_id,
             backlog_file.changelog_covers)
    issue_host.IssueHost._run = fake_run(calls)
    # The v1.34.0 pre-flight guard reads the REAL BACKLOG.md off disk; with `parse` stubbed
    # to four fictional items it would call every real heading stranded and refuse. Its own
    # behaviour is asserted in section 7, against a fixture.
    backlog_file.unparsed_headings = lambda root: []
    # Detection itself shells out to `git`; pin it so the test does not depend on which
    # checkout it happens to be run from.
    issue_host.detect = lambda root, override="": (
        issue_host.GitHubHost(Path("."), "github.com"), "")
    backlog_file.exists = lambda root: True
    backlog_file.parse = lambda root: items()
    backlog_file.write = lambda root, its, name: written.append([dict(i) for i in its])
    backlog_file.counts = lambda root: (4, 3, 0)
    backlog_file.next_id = lambda root: 9
    # B45's CHANGELOG.md coverage gate is its own concern (see the dedicated section below);
    # every OTHER assertion here predates it and assumes a closed item just closes and drops,
    # so pin it "covered" everywhere except where a section overrides it.
    backlog_file.changelog_covers = lambda root, it: True
    try:
        rc = sb.main(argv)
    finally:
        (issue_host.IssueHost._run, issue_host.detect,
         backlog_file.exists, backlog_file.parse, backlog_file.unparsed_headings,
         backlog_file.write, backlog_file.counts, backlog_file.next_id,
         backlog_file.changelog_covers) = saved
    return rc, calls, written


def writes(calls):
    return [c for c in calls if c[:2] in WRITES]


print("1. --help and an unknown flag stop in the parser, before any work")
exits("sync --help exits 0", lambda: sb._parse_args(["--help"]), 0)
exits("sync -h exits 0", lambda: sb._parse_args(["-h"]), 0)
exits("sync --bogus exits 2", lambda: sb._parse_args(["--bogus-flag"]), 2)
exits("sync bare word exits 2", lambda: sb._parse_args(["sync"]), 2)
exits("label --help exits 0", lambda: lb._parse_args(["--help"]), 0)
exits("label --bogus exits 2", lambda: lb._parse_args(["--bogus-flag"]), 2)

print("\n2. --dry-run makes READS only, and writes no file")
rc, calls, written = run(["--dry-run"])
check("exit 0", rc, 0)
check("no mutating host call", writes(calls), [])
check("the host was still read (open listing, plus B37's any-state listing)",
      [c[:2] for c in calls],
      [("repo", "view"), ("issue", "list"), ("issue", "list")])
check("BACKLOG.md not rewritten", written, [])

print("\n3. the default run still does the real sync — flags changed, behaviour did not")
rc, calls, written = run([])
check("exit 0", rc, 0)
check("closed #11", ("issue", "close", "11") in [c[:3] for c in calls], True)
check("filed the unsynced item", ("issue", "create") in [c[:2] for c in calls], True)
check("re-bodied the drifted #13", ("issue", "edit", "13") in [c[:3] for c in calls], True)
check("BACKLOG.md rewritten once", len(written), 1)
check("the closed item was dropped", [i["n"] for i in written[0]], [2, 3, 4, 9])
check("#15 pulled in as B9", written[0][-1]["issue"], 15)
check("and marked inbound", written[0][-1]["inbound"], True)

print("\n4. --push and --pull still mean one half each")
rc, calls, written = run(["--push"])
check("--push files and closes", len(writes(calls)) > 0, True)
check("--push pulls nothing", [i["n"] for i in written[0]], [2, 3, 4])
rc, calls, written = run(["--pull"])
check("--pull mutates nothing", writes(calls), [])
check("--pull still appends B9", [i["n"] for i in written[0]], [1, 2, 3, 4, 9])

print("\n5. --dry-run reports every change it declined to make")
log = []  # main() prints; re-derive the same lines through push/pull directly
its = items()
calls5 = []
issue_host.IssueHost._run, saved5 = fake_run(calls5), issue_host.IssueHost._run
saved5cc, backlog_file.changelog_covers = backlog_file.changelog_covers, (lambda root, it: True)
try:
    host = issue_host.GitHubHost(Path("."), "github.com")
    log += sb.push(host, its, Path("."), "r", {i["number"]: i for i in remote_norm()}, set(), True)
finally:
    issue_host.IssueHost._run = saved5
    backlog_file.changelog_covers = saved5cc
check("said it would close", any("would close #11" in ln for ln in log), True)
check("said it would file", any("would file" in ln for ln in log), True)
check("said it would re-body", any("would update #13" in ln for ln in log), True)
check("said nothing about #14", any("#14" in ln for ln in log), False)
check("a dry push made no write call", writes(calls5), [])

print("\n6. label_backlog --ensure --dry-run creates nothing")
calls = []


def fake_lb_run(self, *args):
    calls.append(tuple(args))
    if args[:2] == ("label", "list"):
        return json.dumps([{"name": "backlog"}]), ""
    if args[:2] == ("issue", "list"):
        return json.dumps([]), ""
    return "", ""


saved_run = issue_host.IssueHost._run
issue_host.IssueHost._run = fake_lb_run
try:
    line = lb.ensure(issue_host.GitHubHost(Path("."), "github.com"), "", dry=True)
finally:
    issue_host.IssueHost._run = saved_run
check("no label created", writes(calls), [])
check("named the missing three", "would create displaced, afk, hitl" in line, True)

print("\n7. a BACKLOG.md this parser cannot fully read is REFUSED, before any host call")
# The hazard, exactly as found in ~/Projects/workspace on 2026-09-03: headings written
# `## 12.` instead of `## B12.`, so `parse()` saw nothing and a regenerate would have deleted
# 206 lines. B46 (2026-09-05) fixed the `## 12.` half — a bare integer heading now parses as
# an alias for `## Bn.` — so what is left to refuse a sync over is `## 2b.`: no integer for
# `n` to become. One stranded heading is still enough to refuse the whole sync.
import tempfile                                        # noqa: E402

fix = Path(tempfile.mkdtemp())
(fix / "BACKLOG.md").write_text(
    "# BACKLOG — workspace\n\n"
    "## 12. Turn the webroot into a real checkout\n"
    "`Sonnet 5` · effort `medium` · `HITL/Auto` · added 2026-09-03\n\nbody\n\n"
    "## 2b. Extend agent-reentry to STAGING\n"
    "added 2026-09-02\n\nbody\n\n"
    "## B7. This one is in the right shape\n"
    "added 2026-09-01 · issue `#7`\n\nbody\n", encoding="utf-8")

stranded = backlog_file.unparsed_headings(fix)
check("only the letter-suffix heading is named now (B46 fixed the bare-integer half)",
      len(stranded), 1)
check("the well-formed one is not", any("B7" in s for s in stranded), False)
check("B46: parse() now sees the bare-integer heading too, alongside the well-formed one",
      [i["n"] for i in backlog_file.parse(fix)], [12, 7])   # file order: 12 appears before B7

calls7 = []
saved7 = (issue_host.IssueHost._run, issue_host.detect, sb.project_root)
issue_host.IssueHost._run = fake_run(calls7)
issue_host.detect = lambda root, override="": (
    issue_host.GitHubHost(Path("."), "github.com"), "")
sb.project_root = lambda: fix
try:
    rc = sb.main([])
finally:
    (issue_host.IssueHost._run, issue_host.detect, sb.project_root) = saved7
check("the sync exits 0 (a wrap must never fail over the backlog)", rc, 0)
check("and made NO host call at all — not even a read", calls7, [])
check("the file is untouched — the still-stranded '2b' heading is exactly as written",
      "## 2b." in (fix / "BACKLOG.md").read_text(encoding="utf-8"), True)

check("write() refuses too, so a wrap cannot clobber it either",
      _raises(lambda: backlog_file.write(fix, [], "workspace")), "Unreadable")
check("…and force=True is the documented escape hatch",
      _raises(lambda: backlog_file.write(fix, backlog_file.parse(fix), "workspace",
                                         force=True)), None)

print("\n8. B45 - the CHANGELOG gate has THREE states, and they do not behave the same")
# `uncovered` (there IS a CHANGELOG.md and nothing in it names the item) defers the whole
# close-and-drop. `no-changelog` (the project has none at all) does NOT - blocking there is a
# permanent stall, not a safety measure: 6 of the 9 tracked projects have no CHANGELOG.md, so
# the entry the gate waits for is one nobody is ever going to write.
its8 = items()
calls8 = []
issue_host.IssueHost._run, saved8 = fake_run(calls8), issue_host.IssueHost._run
saved8cc = backlog_file.changelog_status
backlog_file.changelog_status = lambda root, it: "uncovered"
try:
    host8 = issue_host.GitHubHost(Path("."), "github.com")
    log8 = sb.push(host8, its8, Path("."), "r",
                   {i["number"]: i for i in remote_norm()}, set(), False)
finally:
    issue_host.IssueHost._run = saved8
    backlog_file.changelog_status = saved8cc
check("uncovered: B1 was NOT closed on the host",
      ("issue", "close", "11") in [c[:3] for c in calls8], False)
check("uncovered: B1 is still in the item list - push() kept it, not dropped it",
      [i["n"] for i in its8], [1, 2, 3, 4])
check("uncovered: a log line names B1 and cites B45",
      any("B1" in ln and "B45" in ln for ln in log8), True)

its8b = items()
calls8b = []
issue_host.IssueHost._run, saved8b = fake_run(calls8b), issue_host.IssueHost._run
backlog_file.changelog_status = lambda root, it: "no-changelog"
try:
    host8b = issue_host.GitHubHost(Path("."), "github.com")
    log8b = sb.push(host8b, its8b, Path("."), "r",
                    {i["number"]: i for i in remote_norm()}, set(), False)
finally:
    issue_host.IssueHost._run = saved8b
    backlog_file.changelog_status = saved8cc
check("no-changelog: B1 IS closed on the host - the gate does not stall forever",
      ("issue", "close", "11") in [c[:3] for c in calls8b], True)
check("no-changelog: B1 is dropped from the item list",
      [i["n"] for i in its8b], [2, 3, 4])
check("no-changelog: but it SAYS the record could not be verified, naming B45",
      any("B1" in ln and "B45" in ln and "not" in ln.lower() for ln in log8b), True)

print("\n9. B37 — an item claiming an issue number the host does not have gets its own report")
check("known=None (host unreachable for the extra listing) reports nothing",
      sb.bogus_issue_report(items(), None), [])
its9 = items()  # B3/#13 and B4/#14 are open and claimed; #13 is real, #14 is not this time
check("no report when every claimed open issue is in the known set",
      sb.bogus_issue_report(its9, {11, 13, 14}), [])
report9 = sb.bogus_issue_report(its9, {11, 13})  # #14 (B4, open) now unknown to the host
check("names the item claiming the missing number", any("B4" in ln for ln in report9), True)
check("cites the issue number it claims", any("#14" in ln for ln in report9), True)
check("cites B37", any("B37" in ln for ln in report9), True)
check("a CLOSED item claiming a missing number is excluded (B1/#11, #11 absent here too)",
      any("B1" in ln for ln in sb.bogus_issue_report(its9, {13, 14})), False)

print("\n10. B76 — a reference elsewhere to an item about to be DROPPED gets reported, "
      "never rewritten")
fix76 = Path(tempfile.mkdtemp())
(fix76 / "NEXT.md").write_text(
    "## Decisions\n**D3. Some question** — answer: `here` · added `2026-09-01` "
    "· → `BACKLOG.md B46`\n", encoding="utf-8")
(fix76 / "CHANGELOG.md").write_text(
    "## 2026-09-01\n- did B46 (see B46 for detail)\n", encoding="utf-8")
(fix76 / "docs").mkdir()
(fix76 / "docs" / "notes.md").write_text("still tracking B46 here\n", encoding="utf-8")

report76 = sb.orphaned_pointers_report(fix76, {46})
check("cites B76 in the header line", "B76" in report76[0], True)
check("found the NEXT.md hit", any("NEXT.md" in ln and "B46" in ln for ln in report76), True)
# B92 (below): CHANGELOG.md is a HISTORY path now, excluded from the scan entirely — this
# exact fixture line ("did B46 (see B46 for detail)") is precisely the false-positive shape
# B92 exists to stop, so it must NOT appear here any more. See section 13 for the dedicated
# B92 coverage.
check("CHANGELOG.md is excluded from the scan (B92) — no hit from it any more",
      any("CHANGELOG.md" in ln for ln in report76), False)
check("found the docs/ hit", any("notes.md" in ln for ln in report76), True)
check("no dropped ids at all means no report, even with real hits sitting there",
      sb.orphaned_pointers_report(fix76, set()), [])
check("a dropped id that never appears anywhere produces no report",
      sb.orphaned_pointers_report(fix76, {99}), [])
# This fixture never wrote a BACKLOG.md at all, so "not re-grepped" here just means "not a
# candidate file" — B92 below puts BACKLOG.md back INTO the scan (for a different item's
# `blocked by Bn` line) with its own dedicated coverage; this line is kept only to show an
# absent file contributes no hit, not to claim the file is skipped in general any more.
check("no BACKLOG.md file in this fixture means no BACKLOG.md hit either",
      any(ln.strip().startswith("· BACKLOG.md") for ln in report76[1:]), False)

(fix76 / "docs" / "notes.md").write_text("only a longer number appears here: B460\n",
                                         encoding="utf-8")
check("B460 is not mistaken for the dropped id 46 (word boundary correctness)",
      any("notes.md" in ln for ln in sb.orphaned_pointers_report(fix76, {46})), False)

print("\n11. B76 wired into main() — the id it reports is exactly what push() just dropped")
# Goes through the SAME `run()` harness as every other main()-level test in this file: every
# host call and every file read/write is stubbed, so this touches no real file anywhere
# (see `run()`'s docstring-equivalent comment above it). Only `orphaned_pointers_report`
# itself is additionally intercepted here, to capture what main() actually passed it.
seen_dropped = []
saved11_op = sb.orphaned_pointers_report
sb.orphaned_pointers_report = lambda root, dropped: seen_dropped.append(set(dropped)) or []
try:
    rc, calls11, written11 = run([])
finally:
    sb.orphaned_pointers_report = saved11_op
check("main() ran clean", rc, 0)
check("B1 (n=1) is the only item push() drops in the default fixture, and that's exactly "
      "what got passed to the B76 report", seen_dropped, [{1}])

print("\n12. B84 — BACKLOG.md's heading is never derived from the checkout directory's name")
fix84 = Path(tempfile.mkdtemp())
(fix84 / "BACKLOG.md").write_text("# BACKLOG — real-project\n\nbody\n", encoding="utf-8")
check("an existing heading is read back verbatim",
      sb._existing_heading_project(fix84), "real-project")

empty84 = Path(tempfile.mkdtemp())
check("no BACKLOG.md at all reads as no existing heading",
      sb._existing_heading_project(empty84), "")
(empty84 / "BACKLOG.md").write_text("not a heading line at all\n\nbody\n", encoding="utf-8")
check("a file whose first line isn't `# BACKLOG — ...` also reads as no existing heading",
      sb._existing_heading_project(empty84), "")

print("\n12a. `_project_name` derives a NEW heading from git's own common dir, "
      "never `Path(root).name`")
main_repo = Path(tempfile.mkdtemp()) / "atlas"
main_repo.mkdir()
common_git = main_repo / ".git"                  # what a WORKTREE's common-dir resolves to
saved_git = issue_host._git
issue_host._git = lambda root, *a: (
    str(common_git) if a[:2] == ("rev-parse", "--git-common-dir") else "")
try:
    worktree_dir = Path(tempfile.mkdtemp()) / "decisions"   # named like a branch, on purpose
    worktree_dir.mkdir()
    got = sb._project_name(worktree_dir)
    check("the worktree's OWN directory name ('decisions') is NOT what gets used",
          got != "decisions", True)
    check("the MAIN checkout's directory name is used instead", got, "atlas")
finally:
    issue_host._git = saved_git

print("12b. a normal (non-worktree) checkout still names itself from its own directory")
saved_git = issue_host._git
issue_host._git = lambda root, *a: (
    ".git" if a[:2] == ("rev-parse", "--git-common-dir") else "")
try:
    normal_root = Path(tempfile.mkdtemp()) / "agent-reentry"
    normal_root.mkdir()
    check("a relative common-dir (normal checkout) still resolves to the checkout's own name",
          sb._project_name(normal_root), "agent-reentry")
finally:
    issue_host._git = saved_git

print("12c. git unreachable falls back to the pre-B84 behaviour — never worse than before")
saved_git = issue_host._git
issue_host._git = lambda root, *a: ""
try:
    fallback_root = Path(tempfile.mkdtemp()) / "whatever-name"
    fallback_root.mkdir()
    check("falls back to Path(root).name when git cannot answer at all",
          sb._project_name(fallback_root), "whatever-name")
finally:
    issue_host._git = saved_git

print("\n12d. end-to-end through a real (unmocked) backlog_file.write: a sync run from a "
      "directory named like a worktree keeps the file's OWN heading")
fix84e = Path(tempfile.mkdtemp()) / "decisions"      # named like a worktree, on purpose
fix84e.mkdir()
(fix84e / "BACKLOG.md").write_text(
    "# BACKLOG — atlas\n\n"
    "## B1. Something worth doing\n"
    "`Sonnet 5` · effort `medium` · `AFK/Auto` · added 2026-09-01\n\nbody\n",
    encoding="utf-8")
calls84e = []
saved84e = (issue_host.IssueHost._run, issue_host.detect, sb.project_root)
issue_host.IssueHost._run = fake_run(calls84e)
issue_host.detect = lambda root, override="": (
    issue_host.GitHubHost(Path("."), "github.com"), "")
sb.project_root = lambda: fix84e
try:
    rc = sb.main([])
finally:
    (issue_host.IssueHost._run, issue_host.detect, sb.project_root) = saved84e
after84e = (fix84e / "BACKLOG.md").read_text(encoding="utf-8")
check("the real sync exits clean", rc, 0)
check("the heading stays 'atlas' -- never 'decisions', the fixture directory's own name",
      after84e.splitlines()[0], "# BACKLOG — atlas")

print("\n13. B92 — a HISTORICAL citation is not a stale pointer; a LIVE one still is")
# Part A: `_is_historical_path` as a pure function, independent of what the report actually
# walks — this is the only way to pin the `skills/*/references/incidents.md` shape, because
# in THIS repo that file sits at `plugins/cairn/skills/wrap/references/incidents.md` (six
# segments from the project root), not the four a root-level `skills/` folder would need, and
# `orphaned_pointers_report`'s candidate list below never walks `plugins/` at all.
check("CHANGELOG.md (any case) is historical", sb._is_historical_path("CHANGELOG.md"), True)
check("docs/decisions.md is historical", sb._is_historical_path("docs/decisions.md"), True)
check("docs/Decisions.MD (case-insensitive) is historical",
      sb._is_historical_path("docs/Decisions.MD"), True)
check("docs\\decisions.md (backslash, as a Windows Path would render it) is historical",
      sb._is_historical_path("docs\\decisions.md"), True)
check("docs/review/2026-09-06-x.md is historical", sb._is_historical_path(
    "docs/review/2026-09-06-x.md"), True)
check("docs/review/archive/old.md (nested under review/) is historical",
      sb._is_historical_path("docs/review/archive/old.md"), True)
check("skills/wrap/references/incidents.md (root-level shape) is historical",
      sb._is_historical_path("skills/wrap/references/incidents.md"), True)
check("plugins/cairn/skills/wrap/references/incidents.md (THIS repo's actual nesting) "
      "is historical too — the shape match is depth-flexible",
      sb._is_historical_path("plugins/cairn/skills/wrap/references/incidents.md"), True)
check("NEXT.md is NOT historical", sb._is_historical_path("NEXT.md"), False)
check("BACKLOG.md is NOT historical", sb._is_historical_path("BACKLOG.md"), False)
check("README.md is NOT historical", sb._is_historical_path("README.md"), False)
check("briefs/x.md is NOT historical", sb._is_historical_path("briefs/x.md"), False)
check("a docs/ file that is not decisions.md or under review/ is NOT historical "
      "(docs/wrap-receipt-design.md — a real citation the path rule does not catch)",
      sb._is_historical_path("docs/wrap-receipt-design.md"), False)
check("incidents.md is only excluded under skills/<x>/references/, not anywhere named that",
      sb._is_historical_path("docs/incidents.md"), False)

# Part B: the full report, over a realistic post-close layout — everything the item's own
# measured B87/B99 closes actually produced, minus the id that changes (B87 here).
fix92 = Path(tempfile.mkdtemp())
(fix92 / "NEXT.md").write_text(
    "## Queue\n1. **Still calls it live** — blocked by B87\n", encoding="utf-8")
(fix92 / "CHANGELOG.md").write_text(
    "## 2026-09-06\n- closed B87: dangling-pointer follow-up shipped\n", encoding="utf-8")
(fix92 / "docs").mkdir()
(fix92 / "docs" / "decisions.md").write_text(
    "**D8. Some decision** — answer: `here` · added `2026-09-01` · → B87\n", encoding="utf-8")
(fix92 / "docs" / "review").mkdir()
(fix92 / "docs" / "review" / "2026-09-06-dossier.md").write_text(
    "# B87 archived review\nB87 shipped this cycle.\n", encoding="utf-8")
(fix92 / "docs" / "wrap-receipt-design.md").write_text(
    "This document's whole subject is B87.\n", encoding="utf-8")
(fix92 / "BACKLOG.md").write_text(
    "# BACKLOG — fixture\n\n"
    "## B87. The item being dropped\n"
    "`Sonnet 5` · effort `medium` · `AFK/Auto` · added 2026-09-01\n\nno other self-mention\n\n"
    "## B90. A different item\n"
    "`Opus 5` · effort `high` · `HITL/Auto` · added 2026-09-02 · blocked by B87\n\nbody\n",
    encoding="utf-8")
(fix92 / "README.md").write_text(
    "See the Queue — B87 is still open work.\n", encoding="utf-8")
(fix92 / "briefs").mkdir()
(fix92 / "briefs" / "x.md").write_text(
    "This brief still says: see B87 for the design.\n", encoding="utf-8")

report92 = sb.orphaned_pointers_report(fix92, {87})
check("CHANGELOG.md's closing sentence produces no hit (path excludes it outright)",
      any("CHANGELOG.md" in ln for ln in report92), False)
check("docs/decisions.md produces no hit (historical path)",
      any("decisions.md" in ln for ln in report92), False)
check("docs/review/**, including the archived dossier, produces no hit (historical path)",
      any("dossier" in ln for ln in report92), False)
check("BACKLOG.md's OWN heading for B87 (the item being dropped) produces no hit",
      any("BACKLOG.md:3" in ln for ln in report92), False)
check("a DIFFERENT BACKLOG.md item's 'blocked by B87' line still fires — BACKLOG.md is "
      "back in the scan (B92) for exactly this case",
      any("BACKLOG.md" in ln and "B87" in ln for ln in report92), True)
check("NEXT.md's live 'blocked by B87' Queue line still fires",
      any("NEXT.md" in ln for ln in report92), True)
check("README.md asserting B87 is 'still open work' still fires",
      any("README.md" in ln for ln in report92), True)
check("a brief still pointing readers at B87 still fires",
      any("x.md" in ln for ln in report92), True)
# `docs/wrap-receipt-design.md` is deliberately NOT on the excluded-path list (a normal docs/
# file, not docs/decisions.md or under docs/review/) and its one line has no closing token
# either -- so it is exactly the case the item's spec calls out as correctly STILL firing: a
# real citation the path rule alone does not catch. Left undone on purpose; see the dossier's
# "What was left undone" section for why a token guess was rejected as the primary fix.
check("docs/wrap-receipt-design.md (not on the path exclusion list, no closing token) "
      "still fires -- a known, accepted gap, not a bug",
      any("wrap-receipt-design.md" in ln for ln in report92), True)
check("precision on this realistic post-close fixture: exactly 5 hit lines (NEXT.md, "
      "BACKLOG.md's cross-item line, README.md, the brief, and the one accepted-gap doc) "
      "plus the one header line -- CHANGELOG.md, docs/decisions.md and the archived dossier "
      "no longer count, though the id appears in every one of those files too",
      len(report92) - 1, 5)

print("\n14. B76's ORIGINAL case still fires loudly: ids named as OPEN work in NEXT.md")
fix76b = Path(tempfile.mkdtemp())
(fix76b / "NEXT.md").write_text(
    "## Queue\n"
    "1. **Old item A** — Sonnet 5 · medium · AFK/Auto  → [brief](briefs/a.md)\n"
    "2. **Old item B, blocked by B12** — Opus 5 · high · HITL/Auto\n",
    encoding="utf-8")
report76b = sb.orphaned_pointers_report(fix76b, {12})
check("an id still named as live Queue work is reported, exactly the B76 motivating case",
      any("NEXT.md" in ln and "B12" in ln for ln in report76b), True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
