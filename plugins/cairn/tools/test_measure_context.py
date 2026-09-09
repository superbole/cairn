"""Test for `measure_context.py`'s optional-tiktoken fallback (B95, found 2026-09-06).

    python plugins/cairn/tools/test_measure_context.py

THE BUG THIS GUARDS
--------------------
`import tiktoken` used to sit at module level with no guard. On a machine where the package is
genuinely absent (confirmed on this machine: `pip show tiktoken` -> not found, Python 3.14.0) the
tool died with a bare `ModuleNotFoundError` before printing anything -- and the plugin's own
always-loaded rules file (`rules/CLAUDE.md`) tells every agent to run this tool "instead of
quoting" a bare token count. A tool the rule points at that cannot run forces exactly the choice
the rule forbids.

The fix makes the `tiktoken` import optional: present -> exact BPE counts, unchanged from before;
absent -> every count becomes a labelled `~N` estimate (bytes / 4), the tool still exits 0, and the
output says how to get exact counts. The one thing that must never happen is a bare number that
could be either -- that is the "one value, two opposite states" defect this repo designs against
elsewhere, and it would be worse than the crash it replaces.

WHY THE ABSENT PATH IS SIMULATED, NOT RELIED ON FROM THE MACHINE
-------------------------------------------------------------------
Whether tiktoken happens to be installed here is not something this test controls, so both
branches are exercised deterministically by planting (or blocking) `sys.modules["tiktoken"]`
before each fresh import of `measure_context` -- `sys.modules[name] = None` is the standard way to
force `import <name>` to raise `ImportError` regardless of what is actually on disk, and a small
fake module with a `get_encoding` stands in for a present tiktoken. Neither branch depends on this
machine's real installation state.

WHY `main()` IS RUN AGAINST A THROWAWAY EMPTY PROJECT, NEVER THIS REPO
--------------------------------------------------------------------------
`measure_context.py`'s own docstring is explicit: measuring a project RUNS it -- it executes
whatever SessionStart hooks that project's config declares. Pointing it at this repo (or at the
real `~/.claude`) from an automated test would fire real hooks against real state, exactly the
leak `run_tests.py` polices for and fails the whole suite over. So section 4 below points both
`CLAUDE_CONFIG_DIR` and the "project root" argument at fresh empty temp directories with nothing
in them -- no `.claude/settings.json`, no installed plugins, no real memory index -- so there is
nothing for it to execute; it is only exercising the estimate-mode banner and exit code.
"""
import importlib
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="measure-context-test-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(TMP / "cfg")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

fails = []


def check(label, got, want=True):
    ok = got == want
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def _fresh_import(tiktoken_module):
    """(Re)import `measure_context` with `sys.modules["tiktoken"]` forced to `tiktoken_module`.

    `tiktoken_module = None` forces `import tiktoken` to raise `ImportError` (the absent-package
    case), regardless of whether the real package happens to be installed on this machine.
    """
    sys.modules.pop("measure_context", None)
    saved = sys.modules.get("tiktoken", "<unset>")
    sys.modules["tiktoken"] = tiktoken_module
    try:
        return importlib.import_module("measure_context")
    finally:
        if saved == "<unset>":
            sys.modules.pop("tiktoken", None)
        else:
            sys.modules["tiktoken"] = saved


class _FakeEncoding:
    """Stand-in for a real tiktoken encoding: token count = word count, not byte-accurate --
    only used to prove the PRESENT branch wires `ENC.encode` through, not to match real BPE."""

    def encode(self, text, disallowed_special=()):
        return text.split()


def _fake_tiktoken_module():
    mod = types.ModuleType("tiktoken")
    mod.get_encoding = lambda name: _FakeEncoding()
    return mod


print("1. tiktoken ABSENT -- import must not raise, module must fall back cleanly")
mc_absent = _fresh_import(None)
check("ENC is None", mc_absent.ENC is None)
check("TOKENS_ARE_ESTIMATED is True", mc_absent.TOKENS_ARE_ESTIMATED, True)
check("install hint is present and non-empty", bool(mc_absent.TIKTOKEN_INSTALL_HINT))
check("toks() still returns an int, never raises",
      isinstance(mc_absent.toks("hello world, this is a test"), int))
check("toks() estimate is bytes // 4",
      mc_absent.toks("abcdefgh"), len("abcdefgh".encode("utf-8")) // 4)

print("\n2. tiktoken PRESENT (faked) -- exact path unchanged, wired through ENC.encode")
mc_present = _fresh_import(_fake_tiktoken_module())
check("ENC is set", mc_present.ENC is not None)
check("TOKENS_ARE_ESTIMATED is False", mc_present.TOKENS_ARE_ESTIMATED, False)
check("toks() delegates to ENC.encode (fake counts words)",
      mc_present.toks("a b c d"), 4)

print("\n3. fmt_tokens labels an estimate and NEVER prints an exact-looking number for one")
check("absent module: fmt_tokens marks with a leading ~", mc_absent.fmt_tokens(1234), "~1,234")
check("absent module: still readable with thousands separator", mc_absent.fmt_tokens(1000000), "~1,000,000")
check("present module: fmt_tokens is plain, no ~", mc_present.fmt_tokens(1234), "1,234")
check("the two never render identically for the same number",
      mc_absent.fmt_tokens(42) != mc_present.fmt_tokens(42), True)

print("\n4. running the real script end-to-end with tiktoken blocked: exit 0, labelled output, "
      "no traceback -- against a throwaway EMPTY project so nothing real gets executed")
fake_root = TMP / "empty-project"
fake_root.mkdir(parents=True, exist_ok=True)
fake_cfg = TMP / "fake-cfg"
fake_cfg.mkdir(parents=True, exist_ok=True)
script = HERE / "measure_context.py"

driver = (
    "import sys, runpy\n"
    "sys.modules['tiktoken'] = None\n"
    f"sys.argv = [{str(script)!r}, {str(fake_root)!r}]\n"
    f"runpy.run_path({str(script)!r}, run_name='__main__')\n"
)
env = {**os.environ, "CLAUDE_CONFIG_DIR": str(fake_cfg)}
result = subprocess.run(
    [sys.executable, "-c", driver],
    cwd=str(fake_root), env=env, capture_output=True, text=True, timeout=60,
    encoding="utf-8", errors="replace",
)
check("subprocess with tiktoken blocked exits 0", result.returncode, 0)
check("estimate banner names tiktoken as NOT INSTALLED",
      "NOT INSTALLED" in result.stdout, True)
check("install hint printed for exact counts", "pip install tiktoken" in result.stdout, True)
check("no traceback leaked to stdout", "Traceback" not in result.stdout, True)
check("stderr is empty (no crash noise)", result.stderr.strip(), "")

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
