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
"""
import os
import subprocess
import sys
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

    results = []
    leaked = {}                            # test filename -> sorted list of new dir names
    suite_start = time.perf_counter()
    for path in tests:
        before = _snapshot_state_dir()
        status, output, elapsed = run_one(path)
        after = _snapshot_state_dir()
        new_entries = sorted(after - before)
        if new_entries:
            leaked[path.name] = new_entries
        results.append((path.name, status))
        label = {"ok": "ok  ", "FAIL": "FAIL", "TIMEOUT": "TIME"}[status]
        print("%s  %s  (%.1fs)" % (label, path.name, elapsed))
        if status != "ok":
            print("  --- output from %s ---" % path.name)
            for line in output.rstrip("\n").splitlines():
                _say("  " + line)
            print("  --- end %s ---" % path.name)
        if new_entries:
            plural = "y" if len(new_entries) == 1 else "ies"
            print("  !!! LEAK: %s wrote %d new director%s into the REAL %s:"
                  % (path.name, len(new_entries), plural, _real_state_base()))
            for name in new_entries:
                print("      %s" % name)
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
        print("This is real operator state, not a sandbox -- FAILS the run (see run_tests.py's "
              "B74 docstring for why fail, not warn). Fix: set a throwaway CLAUDE_CONFIG_DIR "
              "before the FIRST call that can touch state_dir(), including direct library calls, "
              "not only CLI subprocess env.")
    else:
        print("\nno leak into the real state dir")

    return 1 if (failed or timed_out or leaked) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
