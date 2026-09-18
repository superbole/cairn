"""Coverage for `wrap_receipt.py` — the CAIRN receipt (BACKLOG.md B87).

    python plugins/cairn/tools/test_wrap_receipt.py

WHAT THIS FILE IS ACTUALLY DEFENDING. B87's mechanism only works if the token is evidence
rather than vocabulary. Three properties carry that, and each has a section here:

  1. A verdict is never `SET` unless the required steps were MEASURED to have run — in
     particular, "no baseline" must never produce a hopeful `SET`, nor a `NOT DUE`
     (section 2).
  2. All FOUR verdicts come from the tool. "No wrap needed" was the exact sentence
     WORKSTATION produced, so a tool owning only the affirmative moves the impersonation
     one door down rather than closing it (section 4).
  3. A fabricated id fails `--verify`. That is the whole difference between a coined word
     an agent can copy out of `SKILL.md` and a receipt it cannot invent (section 5).

The fourth property is negative and just as load-bearing: `unverifiable` must never be
counted as `ran` (section 6). A receipt that quietly ticks the steps it cannot see is the
same defect one level down from the one B87 reported.

The fifth is B2's, and it is that same defect a level further down: `unverifiable` must not
be reported as `skipped` EITHER. A wrap that ran in full but could not be measured reads
`UNKNOWN`; only a wrap measured incomplete reads `OPEN`; a wrap that is both reads `OPEN`.
Section 11 holds the ordering that guarantees it, and the prevention that makes `UNKNOWN`
rare rather than routine.

Runs entirely against throwaway git repos under `tempfile.mkdtemp()`, with
`CLAUDE_PROJECT_DIR`, `CLAUDE_CONFIG_DIR` and `CLAUDE_CODE_SESSION_ID` pointed at fixtures
— never the real repo, the real `~/.claude/`, or this session's own id. Needs `git` on PATH,
same as `test_item_open.py` and `test_archive_offer.py`.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(sys.argv[1] if len(sys.argv) > 1
             else Path(__file__).resolve().parent.parent / "hooks").resolve()
sys.path.insert(0, str(HOOKS))
NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

# Set BEFORE importing the module under test and before any direct call: `state_dir()`
# falls back to `Path.home()/".claude"` when this is unset, which would write fixtures into
# the user's real operator history. Same B74 fix as `test_archive_offer.py`.
os.environ["CLAUDE_CONFIG_DIR"] = str(Path(tempfile.mkdtemp(prefix="cairn-cfg-")))
os.environ["CLAUDE_CODE_SESSION_ID"] = "test-session-cairn"

import wrap_receipt                                          # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def run(root, *args):
    subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=30, **NW)


NEXT_MD = """# NEXT — fixture

## Queue

1. **A thing to do** — Opus 5 · high · HITL/Auto
   Brief: [brief](briefs/thing.md)

## Watching

**W1. Something** — `Sonnet 5` · effort `medium` · `AFK/Auto` · added `2026-01-01` · check after `x`
"""


def new_repo(name, *, inbox="# INBOX\n\n<!-- Add bullets below. -->\n"):
    """A wrapped-shaped fixture project: NEXT.md with a resolving brief, empty INBOX,
    a CHANGELOG, a BACKLOG, one commit, and a .last_wrap pointing at it."""
    root = Path(tempfile.mkdtemp(prefix="cairn-%s-" % name))
    (root / "briefs").mkdir()
    (root / ".claude").mkdir()
    (root / "briefs" / "thing.md").write_text("brief\n", encoding="utf-8")
    (root / "NEXT.md").write_text(NEXT_MD, encoding="utf-8")
    (root / "INBOX.md").write_text(inbox, encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# CHANGELOG\n", encoding="utf-8")
    (root / "BACKLOG.md").write_text("# BACKLOG\n", encoding="utf-8")
    run(root, "git", "init", "-q")
    run(root, "git", "config", "user.email", "t@example.com")
    run(root, "git", "config", "user.name", "T")
    run(root, "git", "add", "-A")
    run(root, "git", "commit", "-qm", "init")
    stamp_marker(root)
    return root


def head_of(root):
    return subprocess.run(("git", "rev-parse", "HEAD"), cwd=root, capture_output=True,
                          text=True, timeout=30, **NW).stdout.strip()


def stamp_marker(root):
    (root / ".claude" / ".last_wrap").write_text(head_of(root) + "\n", encoding="utf-8")


def commit(root, message="more"):
    run(root, "git", "add", "-A")
    run(root, "git", "commit", "-qm", message)


def do_wrap(root):
    """Everything the wrap procedure leaves behind, so the receipt should read SET."""
    (root / "CHANGELOG.md").write_text("# CHANGELOG\n\n## 2026-09-06\n\nDid a thing.\n",
                                       encoding="utf-8")
    (root / "NEXT.md").write_text(NEXT_MD + "\nrewritten\n", encoding="utf-8")
    commit(root, "chore: wrap")
    stamp_marker(root)


print("\n1. A baseline is per-session and only ever read back by the session that wrote it")
r1 = new_repo("baseline")
check("no baseline before SessionStart stamps one", wrap_receipt.baseline(r1) is None)
wrap_receipt.stamp_baseline(r1)
b1 = wrap_receipt.baseline(r1)
check("baseline exists after stamping", isinstance(b1, dict))
check("it records HEAD", b1.get("head") == head_of(r1))
check("it hashes NEXT.md", bool((b1.get("files") or {}).get("NEXT.md")))
check("another session id cannot read it (B72)",
      wrap_receipt.baseline(r1, "some-other-session") is None)


print("\n2. NO BASELINE never yields SET — the required steps report `unverifiable`")
r2 = new_repo("no-baseline")
do_wrap(r2)                                  # a real wrap, but nothing stamped a baseline
st2 = wrap_receipt.steps(r2, None)
v2, why2 = wrap_receipt.verdict(r2, None, st2)
check("next_rewrite is unverifiable, not ran", st2["next_rewrite"]["state"], "unverifiable")
check("changelog is unverifiable, not ran", st2["changelog"]["state"], "unverifiable")
check("commit is unverifiable, not ran", st2["commit"]["state"], "unverifiable")
check("verdict is never SET without measurement", v2 != "SET")
check("nor NOT DUE — the tool cannot see this session at all", v2 != "NOT DUE")
check("it is UNKNOWN, not OPEN: nothing was measured skipped (B2)", v2, "UNKNOWN")
check("and it says why", bool(why2))


print("\n3. A real wrap, with a baseline, reads SET and gets an id")
r3 = new_repo("real-wrap")
wrap_receipt.stamp_baseline(r3)
do_wrap(r3)
body3 = wrap_receipt.record(r3)
check("verdict SET", body3["verdict"], "SET")
check("next_rewrite measured ran", body3["steps"]["next_rewrite"]["state"], "ran")
check("changelog measured ran", body3["steps"]["changelog"]["state"], "ran")
check("commit measured ran", body3["steps"]["commit"]["state"], "ran")
check("marker measured ran", body3["steps"]["marker"]["state"], "ran")
check("briefs measured ran", body3["steps"]["briefs"]["state"], "ran")
check("inbox measured ran", body3["steps"]["inbox"]["state"], "ran")
check("a 12-char receipt id was minted", len(body3["id"]), 12)
check("the receipt is on disk", wrap_receipt.receipt_used(r3))

print("\n3a. Each required step, broken on its own, drops SET to OPEN")
r3b = new_repo("skip-inbox", inbox="# INBOX\n\n- an un-triaged thing\n")
wrap_receipt.stamp_baseline(r3b)
do_wrap(r3b)
st3b = wrap_receipt.steps(r3b, wrap_receipt.baseline(r3b))
check("an un-drained INBOX is `skipped`", st3b["inbox"]["state"], "skipped")
check("so the verdict is OPEN", wrap_receipt.verdict(r3b, wrap_receipt.baseline(r3b), st3b)[0],
      "OPEN")

r3c = new_repo("missing-brief")
(r3c / "briefs" / "thing.md").unlink()
wrap_receipt.stamp_baseline(r3c)
do_wrap(r3c)
st3c = wrap_receipt.steps(r3c, wrap_receipt.baseline(r3c))
check("a brief link pointing at nothing is `skipped`", st3c["briefs"]["state"], "skipped")

r3d = new_repo("stale-marker")
wrap_receipt.stamp_baseline(r3d)
(r3d / "CHANGELOG.md").write_text("# CHANGELOG\n\n## 2026-09-06\n\nx\n", encoding="utf-8")
(r3d / "NEXT.md").write_text(NEXT_MD + "\nrewritten\n", encoding="utf-8")
commit(r3d, "chore: wrap")                   # committed, but .last_wrap NOT re-stamped
st3d = wrap_receipt.steps(r3d, wrap_receipt.baseline(r3d))
check("a .last_wrap inherited from an earlier commit is `skipped`, not `ran` — the exact "
      "state both false reports were made in", st3d["marker"]["state"], "skipped")


print("\n4. The tool owns ALL THREE verdicts — `NOT DUE` is not the agent's to say")
r4 = new_repo("not-due")
wrap_receipt.stamp_baseline(r4)              # clean tree, nothing done since
st4 = wrap_receipt.steps(r4, wrap_receipt.baseline(r4))
check("nothing happened -> NOT DUE",
      wrap_receipt.verdict(r4, wrap_receipt.baseline(r4), st4)[0], "NOT DUE")

(r4 / "NEXT.md").write_text(NEXT_MD + "\nedited\n", encoding="utf-8")
st4b = wrap_receipt.steps(r4, wrap_receipt.baseline(r4))
check("a dirty tree is never NOT DUE",
      wrap_receipt.verdict(r4, wrap_receipt.baseline(r4), st4b)[0], "OPEN")

r4c = new_repo("not-due-committed")
wrap_receipt.stamp_baseline(r4c)
(r4c / "CHANGELOG.md").write_text("# CHANGELOG\n\nwork\n", encoding="utf-8")
commit(r4c, "feat: work with no wrap")       # committed and clean — the tempting case
st4c = wrap_receipt.steps(r4c, wrap_receipt.baseline(r4c))
check("committed-then-clean is NOT 'nothing to wrap' — this is the false-report shape",
      wrap_receipt.verdict(r4c, wrap_receipt.baseline(r4c), st4c)[0], "OPEN")

r4d = new_repo("not-due-no-baseline")
st4d = wrap_receipt.steps(r4d, None)
check("without a baseline the tool cannot see this session, so never claims NOT DUE",
      wrap_receipt.verdict(r4d, None, st4d)[0] != "NOT DUE")
check("and it is UNKNOWN, not OPEN (B2)",
      wrap_receipt.verdict(r4d, None, st4d)[0], "UNKNOWN")


print("\n5. A fabricated id fails --verify — the property the whole mechanism rests on")
ok5, msg5 = wrap_receipt.verify(r3, body3["id"])
check("the real id verifies", ok5)
ok5b, msg5b = wrap_receipt.verify(r3, "deadbeefcafe")
check("an invented id does not", ok5b, False)
check("and the failure names the real one", body3["id"] in msg5b)
ok5c, _ = wrap_receipt.verify(new_repo("never-recorded"), body3["id"])
check("an id from another project does not verify here", ok5c, False)
commit(r3, "later work")
ok5d, msg5d = wrap_receipt.verify(r3, body3["id"])
check("a real id stops verifying once HEAD moves past it", ok5d, False)
check("and says so distinctly from 'no such id'", "HEAD is now" in msg5d)


print("\n6. `unverifiable` is never rendered as coverage, and `n/a` is never `skipped`")
check("steps with no residue are listed, not omitted",
      set(wrap_receipt.UNVERIFIABLE) <= set(body3["steps"]))
for name in wrap_receipt.UNVERIFIABLE:
    check(f"{name} stays unverifiable even in a perfect wrap",
          body3["steps"][name]["state"], "unverifiable")
check("an untouched rationale record is n/a, not skipped",
      body3["steps"]["decisions"]["state"], "n/a")
check("an untouched MISTAKES.md is n/a, not skipped",
      body3["steps"]["mistakes"]["state"], "n/a")
check("no unverifiable step is in REQUIRED",
      set(wrap_receipt.UNVERIFIABLE).isdisjoint(wrap_receipt.REQUIRED))


print("\n7. The orientation line is silent until the project has used the mechanism")
r7 = new_repo("orientation")
check("never recorded a receipt -> silent", wrap_receipt.orientation_line(r7) is None)
wrap_receipt.stamp_baseline(r7)
do_wrap(r7)
wrap_receipt.record(r7)
check("a clean SET at the current HEAD -> still silent, nothing to report",
      wrap_receipt.orientation_line(r7) is None)
commit(r7, "work after the wrap")
line7 = wrap_receipt.orientation_line(r7)
check("HEAD moved past a SET receipt -> says so", isinstance(line7, str) and "moved" in line7)

r7b = new_repo("orientation-open")
wrap_receipt.stamp_baseline(r7b)
commit(r7b, "work")
wrap_receipt.record(r7b)                     # records an OPEN receipt
line7b = wrap_receipt.orientation_line(r7b)
check("an OPEN receipt is surfaced at the next session",
      isinstance(line7b, str) and "OPEN" in line7b)


print("\n7a. The push measurement never cries wolf on an ordinary wrap that DID push")
r7c = new_repo("push-measure")
wrap_receipt.stamp_baseline(r7c)
do_wrap(r7c)
m_default = wrap_receipt.measurements(r7c, wrap_receipt.baseline(r7c))
check("with no stop declared, the default is counts only, no verdict word",
      "ALERT" not in m_default["push"] and "HELD" not in m_default["push"])
check("and it says what it is NOT claiming, rather than staying silent about it",
      "nothing is asserted" in m_default["push"] or "CANNOT_CHECK" in m_default["push"])
m_held = wrap_receipt.measurements(r7c, wrap_receipt.baseline(r7c), held=True)
check("declaring the stop opts INTO push_check's interpretation",
      any(s in m_held["push"] for s in ("HELD", "ALERT", "CANNOT_CHECK", "NOTHING_TO_HOLD")))
check("`held` is recorded on the receipt, so a reader knows which reading applies",
      wrap_receipt.record(r7c, held=True)["held"], True)

print("\n8. The CLI — exit codes and the token line")
def cli(root, *args):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    r = subprocess.run((sys.executable, str(HOOKS / "wrap_receipt.py"), *args), cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60, env=env, **NW)
    return r.returncode, (r.stdout or "") + (r.stderr or "")

r8 = new_repo("cli")
rc, out = cli(r8, "--stamp-baseline")
check("--stamp-baseline exits 0", rc, 0)
do_wrap(r8)
rc, out = cli(r8, "--record")
check("--record exits 0 on a real wrap", rc, 0)
check("prints the CAIRN token", "CAIRN SET" in out)
check("the token carries an id", "CAIRN SET · " in out)
rid = out.strip().rsplit("· ", 1)[-1].strip()
rc, out = cli(r8, "--verify", rid)
check("the printed id verifies from the CLI", rc, 0)
rc, out = cli(r8, "--verify", "000000000000")
check("a fabricated id exits non-zero", rc, 1)
rc, out = cli(r8, "--check")
check("--check does not mint an id", "does not record" in out)
rc, out = cli(new_repo("cli-open"), "--check")
check("a project that never wrapped this session exits 1 from --check", rc, 1)
check("and says UNKNOWN — blind, not measured incomplete", "CAIRN UNKNOWN" in out)
check("never OPEN, which would be the cry-wolf B2 reported", "CAIRN OPEN" not in out)
check("and the note names the real cause rather than blaming a plain terminal",
      "started somewhere else" in out)

# --------------------------------------------------------------------------------------
# 9. B122 — a `git pull` must not green a step this session did not perform.
#
# Every HEAD move in sections 1-8 is a local `commit()`, and `new_repo()` has no remote, so
# the whole fast-forward path was uncovered. These fixtures add a bare origin and a second
# clone that publishes work, which is the only way to produce the real signal: a HEAD that
# moved, and tracked files whose content changed, with nothing done by this session.
# Bare-local origin only — no network, same pattern as `test_push_check.py`.
# --------------------------------------------------------------------------------------

def new_repo_with_origin(name, **kw):
    """`new_repo()` plus a bare origin it tracks."""
    root = new_repo(name, **kw)
    origin = Path(tempfile.mkdtemp(prefix="cairn-%s-origin-" % name)) / "origin.git"
    run(root, "git", "init", "-q", "--bare", str(origin))
    run(root, "git", "remote", "add", "origin", str(origin))
    branch = subprocess.run(("git", "rev-parse", "--abbrev-ref", "HEAD"), cwd=root,
                            capture_output=True, text=True, timeout=30, **NW).stdout.strip()
    run(root, "git", "push", "-q", "-u", "origin", branch)
    return root, origin, branch


def peer(origin, name):
    """A second clone of `origin`, standing in for the other machine."""
    where = Path(tempfile.mkdtemp(prefix="cairn-%s-peer-" % name))
    run(where, "git", "clone", "-q", str(origin), "peer")
    root = where / "peer"
    run(root, "git", "config", "user.email", "peer@example.com")
    run(root, "git", "config", "user.name", "P")
    return root


def peer_publishes(origin, name, files):
    """Commit `files` in a peer clone and push them, so a pull will bring them down."""
    p = peer(origin, name)
    for rel, text in files.items():
        (p / rel).write_text(text, encoding="utf-8")
    commit(p, "peer: %s" % ", ".join(files))
    run(p, "git", "push", "-q", "origin", "HEAD")


def pull(root, *args):
    run(root, "git", "pull", "-q", *(args or ("--ff-only",)))


def states(root):
    base = wrap_receipt.baseline(root)
    attrib = wrap_receipt.attribution(root, base)
    st = wrap_receipt.steps(root, base, attrib)
    return st, wrap_receipt.verdict(root, base, st, attrib)[0]


def pulled_and_idle(name):
    """The exact 2026-09-07 measurement: stamp a baseline, pull real work, do nothing."""
    root, origin, _ = new_repo_with_origin(name)
    wrap_receipt.stamp_baseline(root)
    peer_publishes(origin, name, {"NEXT.md": NEXT_MD + "\nfrom the other machine\n",
                                  "CHANGELOG.md": "# CHANGELOG\n\n## 2026-09-07\n\nTheirs.\n"})
    pull(root)
    return root, origin


print("\n9a. A pull that changed NEXT.md and CHANGELOG.md greens nothing (B122)")
r9a, o9a = pulled_and_idle("b122-pull")
st, v = states(r9a)
check("the pull really did move the tracked files",
      wrap_receipt._changed(r9a, wrap_receipt.baseline(r9a), "NEXT.md"))
check("next_rewrite is skipped, not ran", st["next_rewrite"]["state"], "skipped")
check("changelog is skipped, not ran", st["changelog"]["state"], "skipped")
check("commit is skipped, not ran", st["commit"]["state"], "skipped")
check("the commit detail names the pull", "pull" in st["commit"]["detail"])
check("the next_rewrite detail says the change came from outside the session",
      "not from this session" in st["next_rewrite"]["detail"])

print("\n9b. A real wrap after that pull still reads SET (no false negative)")
r9b, o9b = pulled_and_idle("b122-then-wrap")
do_wrap(r9b)
st, v = states(r9b)
check("next_rewrite ran", st["next_rewrite"]["state"], "ran")
check("changelog ran", st["changelog"]["state"], "ran")
check("commit ran", st["commit"]["state"], "ran")
check("marker ran", st["marker"]["state"], "ran")
check("verdict is SET", v, "SET")

print("\n9c. An uncommitted edit after a pull is attributed, and the commit is not")
r9c, o9c = pulled_and_idle("b122-edit-only")
(r9c / "NEXT.md").write_text(NEXT_MD + "\nmine, uncommitted\n", encoding="utf-8")
st, v = states(r9c)
check("next_rewrite ran (an untracked-by-commit edit still counts)",
      st["next_rewrite"]["state"], "ran")
check("commit is still skipped", st["commit"]["state"], "skipped")
check("verdict is OPEN", v, "OPEN")

print("\n9d. Per-file attribution inside ONE HEAD move (a real merge)")
r9d, o9d, _ = new_repo_with_origin("b122-merge")
wrap_receipt.stamp_baseline(r9d)
peer_publishes(o9d, "b122-merge", {"CHANGELOG.md": "# CHANGELOG\n\n## 2026-09-07\n\nTheirs.\n"})
(r9d / "NEXT.md").write_text(NEXT_MD + "\nmine\n", encoding="utf-8")
commit(r9d, "mine: next")
pull(r9d, "--no-rebase", "--no-edit")
st, v = states(r9d)
check("my NEXT.md edit is attributed to me", st["next_rewrite"]["state"], "ran")
check("their CHANGELOG.md is not", st["changelog"]["state"], "skipped")
check("commit ran, because I did commit", st["commit"]["state"], "ran")

print("\n9e. A pulled-and-idle session is NOT DUE, not OPEN")
r9e, o9e = pulled_and_idle("b122-not-due")
base = wrap_receipt.baseline(r9e)
check("_nothing_to_wrap is True", wrap_receipt._nothing_to_wrap(r9e, base))
check("verdict is NOT DUE", states(r9e)[1], "NOT DUE")

print("\n9f. orientation_line names the pull instead of claiming commits after a wrap")
r9f, o9f, _ = new_repo_with_origin("b122-orient")
wrap_receipt.stamp_baseline(r9f)
do_wrap(r9f)
wrap_receipt.record(r9f)
run(r9f, "git", "push", "-q", "origin", "HEAD")
peer_publishes(o9f, "b122-orient", {"BACKLOG.md": "# BACKLOG\n\ntheirs\n"})
pull(r9f)
line = wrap_receipt.orientation_line(r9f) or ""
check("it does not claim commits after the wrap", "commits after a wrap" not in line)
check("it names the pull", "pull" in line)

print("\n9g. With no HEAD reflog, the steps are unverifiable — never a guess")
r9g, o9g = pulled_and_idle("b122-no-reflog")
run(r9g, "git", "config", "core.logallrefupdates", "false")
shutil.rmtree(r9g / ".git" / "logs", ignore_errors=True)
base = wrap_receipt.baseline(r9g)
attrib = wrap_receipt.attribution(r9g, base)
check("the window is None, not empty", attrib["window"] is None)
st, v = states(r9g)
check("next_rewrite is unverifiable", st["next_rewrite"]["state"], "unverifiable")
check("changelog is unverifiable", st["changelog"]["state"], "unverifiable")
check("commit is unverifiable", st["commit"]["state"], "unverifiable")
check("verdict is OPEN, never NOT DUE", v, "OPEN")
check("a blind session is never NOT DUE",
      wrap_receipt._nothing_to_wrap(r9g, base), False)
check("the receipt records that attribution was unavailable",
      wrap_receipt.record(r9g)["attributed"], False)

print("\n9h. The baseline still records everything its other consumers need")
r9h = new_repo("b122-baseline")
wrap_receipt.stamp_baseline(r9h)
b9h = wrap_receipt.baseline(r9h)
check("schema is stamped", b9h.get("schema"), wrap_receipt.BASELINE_SCHEMA)
check("head is still recorded", b9h.get("head"), head_of(r9h))
check("all four tracked digests are still recorded",
      sorted(b9h.get("files") or {}), sorted(wrap_receipt.TRACKED))

print("\n9i. A file left dirty BEFORE the baseline is not this session's work")
r9i = new_repo("b122-pre-dirty")
(r9i / "NEXT.md").write_text(NEXT_MD + "\ndirty before the session\n", encoding="utf-8")
wrap_receipt.stamp_baseline(r9i)
st, v = states(r9i)
check("next_rewrite is skipped (the snapshot half still carries its weight)",
      st["next_rewrite"]["state"], "skipped")

print("\n9j. A .last_wrap inherited from an earlier session does not green the marker")
r9j = new_repo("b122-inherited-marker")
old = os.stat(r9j / ".claude" / ".last_wrap").st_mtime - 3600
os.utime(r9j / ".claude" / ".last_wrap", (old, old))
wrap_receipt.stamp_baseline(r9j)
st, v = states(r9j)
check("the marker names HEAD",
      (r9j / ".claude" / ".last_wrap").read_text().split()[0], head_of(r9j))
check("but the marker step is skipped", st["marker"]["state"], "skipped")
check("and it says why", "inherited" in st["marker"]["detail"])

print("\n10. B134 — a SECOND stamp must not move the session-start baseline")
# Found live 2026-09-09: an agent ran `session_orientation.py` by hand to preview its output,
# which re-stamped the baseline to a mid-session state. The next receipt reported
# `[SKIP] next_rewrite  NEXT.md is byte-identical to session start` for a rewrite already
# committed, after an earlier receipt in the same session had said `ran`. The hand-run is the
# smaller half: the rules payload documents that orientation text can reappear on a compaction
# refill, so a re-fired SessionStart does this to a session that did nothing unusual.
r10 = new_repo("b134-restamp")
wrap_receipt.stamp_baseline(r10)
first = wrap_receipt.baseline(r10)
do_wrap(r10)                                  # the session does its real work
check("the work registers while the baseline is intact",
      wrap_receipt.steps(r10, wrap_receipt.baseline(r10))["next_rewrite"]["state"], "ran")

wrote_again = wrap_receipt.stamp_baseline(r10)     # the hook fires a second time
check("the second stamp declines", wrote_again, False)
again = wrap_receipt.baseline(r10)
check("the baseline is byte-identical to the first", again, first)
check("so the rewrite is STILL credited",
      wrap_receipt.steps(r10, again)["next_rewrite"]["state"], "ran")
body10 = wrap_receipt.record(r10)
check("and the verdict survives a re-fired SessionStart", body10["verdict"], "SET")
check("the receipt now reports when the baseline was taken", bool(body10.get("baseline_at")))

print("\n10b. `force=True` still re-stamps — the explicit operator path is unchanged")
forced = wrap_receipt.stamp_baseline(r10, force=True)
check("a forced stamp writes", forced, True)
moved = wrap_receipt.baseline(r10)
check("and it really moved", moved != first)
check("which is exactly what discredits the work",
      wrap_receipt.steps(r10, moved)["next_rewrite"]["state"], "skipped")

# --------------------------------------------------------------------------------------
# 11. B2 — a session rooted outside the project it works in.
#
# Two halves, and the order matters. PREVENTION (11a): a session start in a directory that
# is not itself a project stamps baselines for its opted-in children, so the ordinary shape
# — a parent folder full of repos — earns a real verdict. HONESTY (11b/11c): where
# prevention cannot reach, `unverifiable` reads `UNKNOWN`, never `OPEN`, and `skipped` still
# outranks it.
#
# The bug being defended against: a wrap that wrote a 19-line CHANGELOG entry, rewrote
# NEXT.md, committed and pushed reported `CAIRN OPEN` — the same token an actually-skipped
# changelog produces. Receipt 9274cfbf13da, 2026-09-14.
# --------------------------------------------------------------------------------------
print("\n11a. A parent directory stamps baselines for its opted-in children (B2)")
parent = Path(tempfile.mkdtemp(prefix="cairn-parent-"))
_kid = new_repo("child")
kid = parent / _kid.name
shutil.move(str(_kid), str(kid))
plain = parent / "not-a-repo"                 # a NEXT.md, but no .git
plain.mkdir()
(plain / "NEXT.md").write_text(NEXT_MD, encoding="utf-8")
_out = new_repo("opted-out")                  # a real repo that never joined the system
(_out / "NEXT.md").unlink()
opted_out = parent / _out.name
shutil.move(str(_out), str(opted_out))

check("the parent is not itself a project", (parent / "NEXT.md").is_file(), False)
check("so the child has no baseline yet", wrap_receipt.baseline(kid) is None)
stamped = wrap_receipt.stamp_child_baselines(parent)
check("stamping the parent's children reaches the opted-in child", kid in stamped)
check("a NEXT.md-less repo is NOT reached — that gate is the security boundary",
      opted_out not in stamped)
check("nor is a NEXT.md-carrying directory that is not a repo", plain not in stamped)
check("the child now has a real session-start baseline",
      isinstance(wrap_receipt.baseline(kid), dict))

do_wrap(kid)
body11 = wrap_receipt.record(kid)
check("so a wrap of the child earns the SAME verdict as one started inside it",
      body11["verdict"], "SET")
check("and a real receipt id with it", len(body11["id"]), 12)

print("\n11b. Where prevention cannot reach, a blind wrap is UNKNOWN — never OPEN")
r11 = new_repo("foreign-root")
do_wrap(r11)                                  # a complete wrap; nothing stamped a baseline
st11 = wrap_receipt.steps(r11, None)
v11, why11 = wrap_receipt.verdict(r11, None, st11)
check("every tracked step is unverifiable, not skipped",
      [st11[n]["state"] for n in ("next_rewrite", "changelog", "commit")],
      ["unverifiable"] * 3)
check("the verdict is UNKNOWN", v11, "UNKNOWN")
check("and the reasons name what could not be measured",
      any("baseline" in reason for reason in why11))
body11b = wrap_receipt.record(r11)
check("UNKNOWN still RECORDS a receipt — refusing would leave nothing to quote",
      body11b["verdict"], "UNKNOWN")
check("with a verifiable id", wrap_receipt.verify(r11, body11b["id"])[0])
check("and the next session is told it was unmeasured, not that it did not wrap",
      "could not be measured" in (wrap_receipt.orientation_line(r11) or ""))

print("\n11c. `skipped` still outranks `unverifiable` — UNKNOWN is not a soft landing")
r11c = new_repo("blind-and-skipped", inbox="# INBOX\n\n- an un-triaged thing\n")
do_wrap(r11c)                                 # no baseline AND a required step measurably gone
st11c = wrap_receipt.steps(r11c, None)
check("inbox is measured skipped even with no baseline", st11c["inbox"]["state"], "skipped")
check("so the verdict is OPEN, not UNKNOWN — verdict()'s ordering is the guarantee",
      wrap_receipt.verdict(r11c, None, st11c)[0], "OPEN")


print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
