#!/usr/bin/env python3
"""Run every `test_*.py` in this directory and report one pass/fail/timeout table (no CI exists).

    python plugins/cairn/tools/run_tests.py
    python plugins/cairn/tools/run_tests.py --timeout=240
    python plugins/cairn/tools/run_tests.py <plugin-root> --timeout=240

WHY THIS EXISTS. The suite is fifteen-and-growing hand-rolled scripts, each runnable on its own
and each printing its own `ALL PASS` / `FAILED: [...]`. There is no CI and no single command that
runs all of them, so "run the tests" has meant opening a shell and invoking scripts by hand, in an
order nobody remembers, and eyeballing separate tails for the one that scrolled a FAIL past the
top of the terminal. A file that never gets run is a file that never catches anything.

This is deliberately NOT a test framework. Every existing test is a standalone script that prints
its own verdict and exits 0 or 1; the runner's only job is to invoke each one as a subprocess (own
process, own interpreter, own `sys.path` manipulation -- exactly how a human would run it) and
roll the exit codes up into one summary. A test file that is still half-written, or throws on
import, must show up as a FAILED row with its captured output -- not crash this script -- because
another session may be adding a new `test_*.py` at the same time this one runs.

Discovers `tools/test_*.py` other than itself; add a new test by naming it that way and it is
picked up with no registration step.

ONE ROOT ARGUMENT, PLUGIN ROOT (B70, fixed 2026-09-05). Every `test_*.py` in this directory now
agrees that an optional `sys.argv[1]` means the PLUGIN ROOT (with `hooks/` appended by the file
itself), or takes no root argument at all and derives everything from its own `__file__`. That
used to be a three-way split -- three files read the same argument as the HOOKS directory
directly -- and this runner worked around it by forwarding an explicit root to children only when
one was given here, never by default. The fix removed the disagreement; this runner still only
forwards when given one explicitly, kept as a harmless default rather than because it is still
required -- see the dossier for which files were changed and why this was not also simplified.

A TIMEOUT IS NOT A FAILURE (B73, 2026-09-05). A file that runs long because the machine is loaded
did not produce a bad result -- it produced NO result, and reporting it inside the same
`FAILED: [...]` line as a real assertion failure erases that difference right when it matters
most (a red suite is a stop signal; it should not fire for "the laptop was busy"). So a per-file
timeout is its own status, `TIMEOUT`, kept out of `FAILED` in every table row and every summary
line, and the summary says how long it waited. The exit code is still non-zero for either --
something the caller should look at either way -- but the two are never worded the same, so a
human or a script can grep `TIMEOUT` and `FAILED` apart. The per-file timeout defaults to 120s and
is settable with `--timeout=SECONDS` for a slower or busier machine; it applies uniformly to every
file rather than scaling per file (see the dossier for why a per-file schedule was not built).

A LEAK INTO THE REAL STATE DIR IS ITS OWN AXIS TOO (B74, 2026-09-05). `~/.claude/reentry-state/`
is the user's actual operator history -- `check_exits.py` reads it and reports on it as fact. A
test that forgets to override `CLAUDE_CONFIG_DIR` (or overrides it for a CLI subprocess but then
also calls the library functions directly, in-process, against the real default) writes a
throwaway fixture directory in there instead of a sandbox, and it never gets cleaned up. Measured
2026-09-05: one full suite run added ~23 such directories against a handful of real ones -- a
ratio around 1:73. So this runner snapshots the entries directly under the state dir before and
after EVERY test file and reports any new ones by name, attributed to the file that created them,
same style as the TIMEOUT axis above: never folded into FAILED (a leak is a different kind of
problem -- state corruption, not a wrong assertion), but IT DOES fail the run. Decided deliberately,
not a default: unlike a slow machine (TIMEOUT), a leak is not a maybe-it-will-pass-next-time
condition -- every leaked directory is real damage to real state that has already happened by the
time this prints, so warning-only would let the plugin's own test suite keep corrupting the thing
`check_exits.py` depends on, silently, forever. See `docs/review/isolation.md` (B74) for the
measurement and the list of files this caught.

A LEAK MUST BE ATTRIBUTED, NOT JUST DETECTED (B75, 2026-09-27). The before/after diff above
cannot tell "a test wrote here" apart from "someone else wrote here while the test was running".
Every worktree lane (and every other concurrent Claude Code session, anywhere on the machine) has
its OWN `SessionStart`/`Stop` hooks writing into this exact directory the whole time this runner
is also polling it, so a plain diff blames whichever test file happened to be running when a
totally unrelated session's hook created or touched its own state dir. Reproduced twice: once as
`agent-<id>-<hash>` (a `SessionStart` firing mid-run for an unrelated agent-worktree session,
2026-09-26) and once as `afk-02-<hash>` (this orchestrator's OWN cwd switching into a sibling
worktree lane created that lane's EMPTY state dir mid-run, 2026-09-27) -- neither has anything to
do with the test file blamed for it, and both failed a fully passing suite.

The fix does not relax the diff (a real leak must still fail the run -- see above) or drop the
global diff for a per-file `CLAUDE_CONFIG_DIR` (rejected: that would silently sandbox a test that
forgot to override it itself, hiding the exact bug B74 exists to catch, one level up). Instead,
every NEW name is attributed before it is allowed to fail anything:

  - It KEYS TO A REAL, EXISTING project or worktree (its slug, reproduced with the same
    derivation `reentry_state.state_dir` uses, matches a currently-live git worktree of this repo
    or a project this machine has previously recorded a session ending in) -- IGNORED. This is
    what both reproductions above look like: a real path, still on disk, that this suite never
    touched.
  - Otherwise, it KEYS TO A DIRECTORY THIS RUN ITSELF JUST CREATED under the system temp dir (the
    shape of a test fixture that forgot to override `CLAUDE_CONFIG_DIR`) -- BLAMED. This is the
    genuine B74 case and still fails the run.
  - Otherwise (matches neither) -- BLAMED. An unrecognised new name is not proof of innocence;
    silently letting it through would be the exact blindness this whole detector exists to avoid
    (its own B74 docstring, two paragraphs up).

`_slug_for` duplicates `state_dir`'s slug math rather than importing it, same reasoning as
`_real_state_base` below: it must be applied to CANDIDATE paths without the side effect
`state_dir()` itself has (it creates the directory it returns), and it must keep working even if
`hooks/reentry_state.py` is mid-edit in a sibling lane.

REAL ROOTS CAN APPEAR MID-RUN TOO (B75 round 2, 2026-09-27). The candidate list above was
computed ONCE at suite start on the assumption that worktrees don't change while the suite runs.
False, and it is exactly the same concurrent-lane shape this whole fix exists for: a full run
reported `afk-05-<hash>` and `afk-06-<hash>` as unrecognised leaks from `test_check_credentials.py`
-- both were live worktrees (`.claude/worktrees/afk-05`, `afk-06`) `git worktree add`ed WHILE the
suite was already running, so the cached list built at suite start could never have matched them.
`_classify_with_refresh` is the fix: when the cached list still leaves a name blamed, recompute
`_real_roots` fresh -- once -- and re-classify before accepting the blame, then keep the fresh
list as the cache for every test file after this one. The normal (nothing blamed) path never
pays for the recompute at all.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Raised from 120 s at v1.52.0. Measured on ORG-LAPTOP1, 2026-09-08: `test_wrap_receipt.py`
# takes 113.9 s once B122's fixtures are in it, because attribution can only be tested
# against real fast-forwards and merges, which means a bare origin plus a peer clone per
# case. At 95% of the old default it would have flaked on any slower machine — a timeout
# reported as a failure is exactly the confusion `TIMEOUT` was made a separate state to
# prevent (B73). Splitting that file is filed as a backlog item rather than done here.
DEFAULT_TIMEOUT = 300.0


def _say(line: str) -> None:
    """Print a captured line that may not be encodable by this console's codepage.

    Measured on ORG-LAPTOP1, 2026-09-08: a failing test whose output contained U+FFFD (the
    replacement char `git_encoding`'s `errors="replace"` produces) raised
    `UnicodeEncodeError` from cp1252 INSIDE this loop, killing the runner before it printed
    the summary or the leak report. So the suite's own reporter was least reliable at the
    exact moment something had failed. Three Windows machines, so this is the normal case.
    """
    try:
        print(line)
    except UnicodeEncodeError:
        enc = (sys.stdout.encoding or "ascii")
        print(line.encode(enc, "replace").decode(enc, "replace"))


def _parse_argv(argv):
    """Order-independent: an optional `--timeout=N` and an optional positional plugin root."""
    root = None
    timeout = DEFAULT_TIMEOUT
    for a in argv:
        if a.startswith("--timeout="):
            timeout = float(a.split("=", 1)[1])
        else:
            root = a
    return root, timeout


_explicit_root, TIMEOUT = _parse_argv(sys.argv[1:])
ROOT = Path(_explicit_root).resolve() if _explicit_root \
    else Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def discover():
    return sorted(
        p for p in TOOLS.glob("test_*.py")
        if p.resolve() != Path(__file__).resolve()
    )


def _real_state_base() -> Path:
    """Where `~/.claude/reentry-state/` actually is for THIS process -- same fallback as
    `reentry_state.state_dir` / `check_exits.state_base`, deliberately kept in sync rather than
    imported: this must watch the exact directory a test leaks into when it forgets to override
    `CLAUDE_CONFIG_DIR`, not a copy of the logic that could drift from it. NOT overridden here --
    this runner intentionally never sets `CLAUDE_CONFIG_DIR` for itself, so this is the REAL
    directory in every normal invocation, which is the whole point (B74)."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    return Path(base) / "reentry-state"


def _snapshot_state_dir() -> set:
    """Names of entries directly under the real state dir, or an empty set if it doesn't exist
    yet. A set of NAMES, not a deep walk -- every leak seen so far (B74) is a whole new
    project-slug directory, never a new file dropped inside an existing one, and a shallow
    snapshot is cheap enough to take before and after every single test file."""
    try:
        return {p.name for p in _real_state_base().iterdir()}
    except OSError:
        return set()


def _slug_for(root: Path) -> str:
    """Reproduce `reentry_state.state_dir`'s slug for ROOT (B75). Deliberately NOT imported --
    `state_dir()` creates the directory it names as a side effect (`mkdir(parents=True,
    exist_ok=True)`), which is exactly wrong to do just to test whether a NAME matches a
    candidate path; and this must keep working even if the hook is mid-edit in a sibling lane,
    same reasoning as `_real_state_base` above. Kept in sync by hand -- see that function's
    docstring for what "in sync" means here."""
    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in root.name)[:32] or "project"
    digest = hashlib.sha1(str(root.resolve()).lower().encode("utf-8")).hexdigest()[:10]
    return "%s-%s" % (name, digest)


def _git_worktree_roots(cwd: Path) -> list:
    """Every worktree of the repo containing CWD -- main checkout plus every lane -- via
    `git worktree list --porcelain`. Real, currently-live project roots a concurrent session
    could be running in; this is exactly the shape of both B75 reproductions (a sibling lane's
    own hook writing its own state dir mid-run). Best-effort: no git, no repo, or a parse miss
    just yields nothing -- never raises, never slows the suite down over this."""
    try:
        proc = subprocess.run(
            ("git", "worktree", "list", "--porcelain"),
            cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
    except OSError:
        return []
    if proc.returncode != 0:
        return []
    roots = []
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            roots.append(Path(line[len("worktree "):].strip()))
    return roots


def _recorded_project_roots(state_base: Path) -> list:
    """Project roots this machine has recorded a SESSION ENDING in -- read from `last_exit.json`
    (written by `dirty_tree_warning.py`'s SessionEnd branch), same source `check_repos.py`'s
    `known_roots()` reads. Reimplemented here rather than imported: this runner must never import
    a sibling tool it does not own, so a half-written sibling file can never break the ability to
    run the suite at all. Read-only, no side effects; a missing/unreadable/malformed record is
    silently skipped, never raises."""
    found = []
    try:
        entries = sorted(state_base.glob("*/last_exit.json"))
    except OSError:
        return []
    for statefile in entries:
        try:
            root = json.loads(statefile.read_text(encoding="utf-8")).get("root")
        except Exception:
            continue
        if root:
            found.append(Path(root))
    return found


def _real_roots(state_base: Path) -> list:
    """Candidate real, existing project/worktree roots, deduped case-insensitively (Windows).
    Computed once per suite run, not once per test file: worktrees and recorded projects do not
    change mid-run, and re-shelling to git per test file would be needless cost for no extra
    signal."""
    candidates = _git_worktree_roots(ROOT) + _recorded_project_roots(state_base)
    seen, unique = set(), []
    for p in candidates:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _snapshot_temp_dir() -> set:
    """Top-level entry names under the system temp dir right now. Same shallow-snapshot shape as
    `_snapshot_state_dir` -- cheap enough before and after every test file -- used only to
    recognise a fixture directory THIS test just created (see `_classify_new_entries`); it is
    never itself reported as a leak."""
    try:
        return {p.name for p in Path(tempfile.gettempdir()).iterdir()}
    except OSError:
        return set()


def _classify_new_entries(names, new_temp_names, real_roots):
    """Split newly-appeared state-dir NAMES into (blamed, ignored) (B75).

    ignored: an (name, real_root) pair -- the name's slug matches a REAL, currently-existing
    project or worktree (see `_real_roots`). Created by that project's own concurrent session,
    not by anything this suite did; never counted as a leak. Checked FIRST: a real, on-disk
    project is the stronger signal, and (by construction) cannot also be a fixture this run just
    created in temp.

    blamed: every other name. Two cases, both reported the same way (the run-time distinction is
    not worth a third bucket): its slug matches a directory THIS test just created under the
    system temp dir -- NEW_TEMP_NAMES, from `_snapshot_temp_dir()` before/after -- which is the
    exact shape of a fixture that forgot to override `CLAUDE_CONFIG_DIR` (a genuine B74 leak); or
    it matches neither list, which is deliberate -- an unrecognised new name is not proof of
    innocence, and treating it as harmless would reintroduce the exact blindness this detector
    exists to prevent, one level up.
    """
    real_slugs = {}
    for root in real_roots:
        try:
            if root.is_dir():
                real_slugs[_slug_for(root)] = root
        except OSError:
            continue

    temp_base = Path(tempfile.gettempdir())
    temp_slugs = set()
    for entry_name in new_temp_names:
        try:
            temp_slugs.add(_slug_for(temp_base / entry_name))
        except OSError:
            continue

    blamed, ignored = [], []
    for name in names:
        if name in real_slugs:
            ignored.append((name, real_slugs[name]))
        else:
            blamed.append((name, "matches this run's own temp fixture" if name in temp_slugs
                           else "unrecognised"))
    return blamed, ignored


def _classify_with_refresh(names, new_temp_names, real_roots, state_base):
    """`_classify_new_entries`, but recomputes REAL_ROOTS -- once -- if the cached list still
    leaves something blamed (B75, round 2).

    `_real_roots` is normally computed ONCE at suite start (see `main()`) because worktrees don't
    usually change mid-run. They can: `git worktree add` for a NEW lane (afk-05, afk-06) ran
    WHILE a full suite was in progress, and that lane's own hook stamped its state dir before this
    runner's next snapshot -- the same concurrent-lane shape B75 exists for, just for a worktree
    that did not exist yet when the cache was built, so the cached list could never have matched
    it. A wrong-way fix would be to shell out to `git worktree list` before every single test
    file "just in case"; that pays the cost on every run, including the overwhelming majority
    where nothing is blamed. Instead: try the cheap cached list first, and only pay for a fresh
    `git worktree list` + re-read of every `last_exit.json` when something would otherwise be
    blamed -- at most once per test file, and never on the normal (nothing blamed) path.

    Returns (blamed, ignored, real_roots) -- REAL_ROOTS is the input list unchanged when nothing
    needed refreshing, or the freshly computed one when it did; the caller should keep using
    whichever comes back as its cache for the NEXT test file, so a single refresh benefits every
    file after it too, not just the one that triggered it.
    """
    blamed, ignored = _classify_new_entries(names, new_temp_names, real_roots)
    if not blamed:
        return blamed, ignored, real_roots
    fresh_roots = _real_roots(state_base)
    blamed, ignored = _classify_new_entries(names, new_temp_names, fresh_roots)
    return blamed, ignored, fresh_roots


def run_one(path):
    """Run a single test file as a subprocess; never let it raise out of here.

    Returns (status, output, elapsed_seconds) where status is one of "ok", "FAIL", "TIMEOUT".
    TIMEOUT means the runner never got an answer within TIMEOUT seconds -- an absent result,
    not a negative one -- and must never be folded into "FAIL" (B73).
    """
    argv = (sys.executable, str(path)) + ((str(ROOT),) if _explicit_root else ())
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            argv, cwd=TOOLS, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT,
        )
        elapsed = time.perf_counter() - start
        status = "ok" if proc.returncode == 0 else "FAIL"
        return status, proc.stdout + proc.stderr, elapsed
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start
        out = (exc.stdout or "") + (exc.stderr or "")
        out += ("\n[run_tests] TIMEOUT: no result after %.1fs (limit %.0fs) -- unknown, "
                "not failed. The machine may just be loaded; rerun alone, or with a longer "
                "--timeout, before treating this as a regression.\n") % (elapsed, TIMEOUT)
        return "TIMEOUT", out, elapsed
    except Exception as exc:  # a test file that is half-written, or won't even start
        elapsed = time.perf_counter() - start
        return "FAIL", "[run_tests] could not run this test: %r\n" % (exc,), elapsed


def main(argv):
    tests = discover()
    if not tests:
        print("no test_*.py files found under %s" % TOOLS)
        return 1

    real_roots = _real_roots(_real_state_base())

    results = []
    leaked = {}                            # test filename -> sorted list of (name, reason)
    ignored_total = []                     # (name, real_root) attributed away, informational only
    suite_start = time.perf_counter()
    for path in tests:
        before = _snapshot_state_dir()
        temp_before = _snapshot_temp_dir()
        status, output, elapsed = run_one(path)
        after = _snapshot_state_dir()
        temp_after = _snapshot_temp_dir()
        new_entries = sorted(after - before)
        blamed, ignored = ([], [])
        if new_entries:
            blamed, ignored, real_roots = _classify_with_refresh(
                new_entries, sorted(temp_after - temp_before), real_roots, _real_state_base())
        if blamed:
            leaked[path.name] = blamed
        if ignored:
            ignored_total.extend(ignored)
        results.append((path.name, status))
        label = {"ok": "ok  ", "FAIL": "FAIL", "TIMEOUT": "TIME"}[status]
        print("%s  %s  (%.1fs)" % (label, path.name, elapsed))
        if status != "ok":
            print("  --- output from %s ---" % path.name)
            for line in output.rstrip("\n").splitlines():
                _say("  " + line)
            print("  --- end %s ---" % path.name)
        if blamed:
            plural = "y" if len(blamed) == 1 else "ies"
            print("  !!! LEAK: %s wrote %d new director%s into the REAL %s:"
                  % (path.name, len(blamed), plural, _real_state_base()))
            for name, reason in blamed:
                print("      %s  (%s)" % (name, reason))
        if ignored:
            plural = "y" if len(ignored) == 1 else "ies"
            print("  (ignored %d new director%s while %s ran -- keys to a real, still-existing "
                  "project/worktree, not this test:" % (len(ignored), plural, path.name))
            for name, real_root in ignored:
                print("      %s  -> %s" % (name, real_root))
            print("  )")
    wall = time.perf_counter() - suite_start

    failed = [name for name, status in results if status == "FAIL"]
    timed_out = [name for name, status in results if status == "TIMEOUT"]
    ok_count = len(results) - len(failed) - len(timed_out)

    print("\n%d/%d test files passed" % (ok_count, len(results)))
    print("wall clock: %.1fs total (per-file timeout %.0fs)" % (wall, TIMEOUT))
    if not failed and not timed_out:
        print("ALL PASS")
    else:
        if failed:
            print("FAILED: %s" % failed)
        if timed_out:
            print("TIMEOUT (inconclusive -- not a failure, rerun to confirm): %s" % timed_out)

    if leaked:
        total = sum(len(v) for v in leaked.values())
        plural = "y" if total == 1 else "ies"
        print("\nLEAKED %d new director%s into %s from %d file(s): %s"
              % (total, plural, _real_state_base(), len(leaked), sorted(leaked)))
        print("None of these matched a real, still-existing project or worktree (the reason on "
              "each row above says whether it matched this run's own temp fixtures -- a "
              "confirmed leak -- or matched neither list -- unrecognised, still treated as a "
              "leak; see run_tests.py's B75 docstring for why). Real operator state, not a "
              "sandbox, and FAILS the run (see the B74 docstring for why fail, not warn). Fix: "
              "set a throwaway CLAUDE_CONFIG_DIR before the FIRST call that can touch "
              "state_dir(), including direct library calls, not only CLI subprocess env.")
    else:
        print("\nno leak into the real state dir")
    if ignored_total:
        print("(%d new director%s attributed away this run -- keyed to a real, still-existing "
              "project or worktree, not counted as a leak: %s)"
              % (len(ignored_total), "y" if len(ignored_total) == 1 else "ies",
                 sorted(name for name, _ in ignored_total)))

    return 1 if (failed or timed_out or leaked) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
