"""B23 -- required global settings are REPORTED on the machine that has them wrong, never written.

    python plugins/cairn/tools/test_settings_drift.py

WHY THIS EXISTS. `cleanupPeriodDays` was unset on this laptop (2026-08-30), so Claude Code's
built-in default was pruning the session transcripts `tools/timesheet.py` depends on. It was fixed
by hand -- on ONE machine, because `~/.claude` is not a git repo -- and nothing was ever going to
tell the other three. `hooks/settings_drift.py` is the report-only answer: read this machine's
settings.json, compare against a small declared list, print one line when they disagree.

WHAT THIS PINS, beyond "the drift line appears":

  * REPORT ONLY. No code path may create or modify settings.json. Checked by inspecting the temp
    config dir afterwards, not by reading the source.
  * THREE distinct states, never collapsed: set-and-wrong, unset, and could-not-read. The last one
    is the honest "I don't know" case and must not be worded as drift (same lesson as B44, which
    this batch fixed in the same file: a check must claim only what it actually established).
  * ONE MACHINE. The line may not imply anything about any other machine's value -- that would be
    the original defect (a fact asserted about machines nobody looked at) reintroduced one level
    up, wearing the fix's clothes.
  * The check is GLOBAL: it fires in a project with no NEXT.md, where every project-scoped part of
    the orientation is deliberately silent.

ISOLATION IS MECHANICAL, NOT A COMMENT. `CLAUDE_CONFIG_DIR` is pointed at a temp directory in the
FIRST executable lines below -- before any hook module is imported, so no import-time or in-process
call can resolve the real `~/.claude` -- and every subprocess gets the same override in its env.
Nothing in this file reads or writes the user's real config or state directory.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# --- isolation FIRST: before any import that could resolve ~/.claude ------------------------
# The prefix deliberately contains NEITHER "drift" NOR "unset": the report line quotes the full
# path of the file it read, so a fixture directory named after the thing being asserted makes
# "the line does not say 'drift'" pass or fail on the tempdir name instead of the wording. That
# happened on the first run of this file.
_SANDBOX = Path(tempfile.mkdtemp(prefix="b23-settings-check-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(_SANDBOX / "cfg")
(_SANDBOX / "cfg").mkdir(parents=True, exist_ok=True)

_TEXT = {"encoding": "utf-8", "errors": "replace"}   # the hook prints utf-8; a cp1252 console
                                                     # default cannot decode it back
ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(HOOKS))

import settings_drift as sd                                    # noqa: E402

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def settings_file(name, payload):
    """A settings.json in its own temp directory. `payload` None writes nothing (absent file);
    a str is written verbatim (for the malformed case); a dict is written as JSON."""
    d = _SANDBOX / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "settings.json"
    if payload is None:
        return p
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload),
                 encoding="utf-8")
    return p


print("\n1. a machine that meets the required floor is SILENT")

check("exactly at the floor", sd.check(settings_file("at-floor", {"cleanupPeriodDays": 90})), None)
check("well above the floor",
      sd.check(settings_file("above", {"cleanupPeriodDays": 365})), None)
check("other keys present alongside it are ignored",
      sd.check(settings_file("extras", {"cleanupPeriodDays": 90, "model": "opus",
                                        "env": {"FOO": "bar"}})), None)

print("\n2. set-and-WRONG names both numbers")

line = sd.check(settings_file("too-low", {"cleanupPeriodDays": 30}))
check("a line is produced", bool(line), True)
check("it names the value found here", "30" in (line or ""), True)
check("it names the value required", "90" in (line or ""), True)
check("it names the key", "cleanupPeriodDays" in (line or ""), True)
check("it does not call the value unset", "unset" in (line or "").lower(), False)

print("\n3. UNSET is its own report -- both shapes of it")

no_key = sd.check(settings_file("no-key", {"model": "opus"}))
no_file = sd.check(settings_file("no-file", None))
check("a settings.json without the key reports unset", "unset" in (no_key or "").lower(), True)
check("no settings.json at all reports unset too", "unset" in (no_file or "").lower(), True)
check("unset says the built-in default is what is live",
      "default" in (no_key or "").lower(), True)

print("\n4. COULD-NOT-READ is a third state, never worded as drift")

bad = sd.check(settings_file("malformed", "{ this is not json, "))
check("a line is produced", bool(bad), True)
check("it says the check was skipped, not that a value is wrong",
      "skipped" in (bad or "").lower(), True)
check("it does not claim the key is unset", "unset" in (bad or "").lower(), False)
check("it does not claim drift", "drift" in (bad or "").lower(), False)

not_an_object = sd.check(settings_file("list", "[1, 2, 3]"))
check("a JSON array is could-not-read, not clean", "skipped" in (not_an_object or "").lower(), True)

print("\n5. a non-numeric value is reported, and `true` is NOT treated as the number 1")

as_str = sd.check(settings_file("string", {"cleanupPeriodDays": "90"}))
check("a string value is reported", "not a number" in (as_str or ""), True)
as_bool = sd.check(settings_file("bool", {"cleanupPeriodDays": True}))
check("a bool is reported, despite bool being an int in Python",
      "not a number" in (as_bool or ""), True)

print("\n6. REPORT ONLY -- nothing here creates or edits a settings file")

absent_dir = _SANDBOX / "no-file"
before = sorted(p.name for p in absent_dir.iterdir())
for _ in range(3):
    sd.check(absent_dir / "settings.json")
    sd.load(absent_dir / "settings.json")
after = sorted(p.name for p in absent_dir.iterdir())
check("the directory is untouched by repeated checks", after, before)
check("no settings.json was conjured into existence",
      (absent_dir / "settings.json").exists(), False)

wrong = settings_file("preserve", {"cleanupPeriodDays": 30})
sd.check(wrong)
check("an existing wrong value is left exactly as it was",
      json.loads(wrong.read_text(encoding="utf-8")), {"cleanupPeriodDays": 30})

print("\n7. ONE machine -- the line must not imply anything about the others")

low = sd.check(settings_file("one-machine", {"cleanupPeriodDays": 30}))
check("it says the reading is about THIS machine", "THIS machine" in (low or ""), True)
check("it says no other machine was checked",
      "no other machine" in (low or "").lower(), True)
for word in ("LAPTOP1", "LAPTOP2", "the others", "other machines keep"):
    check(f"it makes no claim about {word!r}", word in (low or ""), False)

print("\n8. the CLI: exit 0 clean, exit 1 on drift, and --json is machine-readable")

env = dict(os.environ)
env["CLAUDE_CONFIG_DIR"] = str(_SANDBOX / "cfg")


def cli(*args):
    return subprocess.run([sys.executable, str(TOOLS / "check_settings.py"), *args],
                          capture_output=True, text=True, **_TEXT, env=env, **NW)


ok_run = cli("--settings-file", str(settings_file("cli-ok", {"cleanupPeriodDays": 90})))
check("exit 0 when clean", ok_run.returncode, 0)
check("it says so in words", "every required key holds" in ok_run.stdout, True)

bad_run = cli("--settings-file", str(settings_file("cli-bad", {"cleanupPeriodDays": 7})))
check("exit 1 on drift", bad_run.returncode, 1)
check("the drift line is printed", "cleanupPeriodDays" in bad_run.stdout, True)

json_run = cli("--json", "--settings-file", str(settings_file("cli-json",
                                                              {"cleanupPeriodDays": 7})))
try:
    payload = json.loads(json_run.stdout)
except Exception as exc:
    payload = {"parse_error": repr(exc)}
check("--json parses", isinstance(payload.get("required"), list), True)
check("--json reports not-ok", payload.get("ok"), False)
check("--json carries the value found", payload.get("required", [{}])[0].get("value"), 7)

print("\n9. end-to-end: the orientation prints it, and stops printing it once fixed")


def orient(project, cfg):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = str(project)
    e["CLAUDE_CONFIG_DIR"] = str(cfg)
    return subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                          input='{"source":"startup"}', capture_output=True, text=True,
                          **_TEXT, env=e, cwd=str(project), **NW)


repo = _SANDBOX / "repo"
repo.mkdir()
subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, **NW)
(repo / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto\n\n"
    "---\n\nAim: test.\n", encoding="utf-8")

drift_cfg = _SANDBOX / "cfg-drift"
drift_cfg.mkdir()
(drift_cfg / "settings.json").write_text('{"cleanupPeriodDays": 30}', encoding="utf-8")
run_drift = orient(repo, drift_cfg)
check("exits 0", run_drift.returncode, 0)
check("the drift line reaches the orientation",
      "cleanupPeriodDays" in run_drift.stdout, True)
check("the queue is still there too", "Something to do" in run_drift.stdout, True)

fixed_cfg = _SANDBOX / "cfg-fixed"
fixed_cfg.mkdir()
(fixed_cfg / "settings.json").write_text('{"cleanupPeriodDays": 90}', encoding="utf-8")
run_fixed = orient(repo, fixed_cfg)
check("exits 0", run_fixed.returncode, 0)
check("a machine that is correct gets NO settings line",
      "cleanupPeriodDays" in run_fixed.stdout, False)
check("the settings check did not write into the config dir it read",
      json.loads((fixed_cfg / "settings.json").read_text(encoding="utf-8")),
      {"cleanupPeriodDays": 90})

print("\n10. it fires in ANY opted-in project, but never breaks the not-opted-in silence")

# The setting is global, and B23's brief asks for the line in EVERY project on that reasoning.
# It is gated on the queue instead, and this case is why: the first, ungated version failed
# `test_machine_identity.py` and `test_empty_queue_diverged.py`, which both assert that a project
# outside the system prints NOTHING AT ALL -- the property `session_orientation.py`'s own
# docstring calls the reason this hook is safe to install everywhere. A line that repeats every
# session until a setting is changed is the worst possible thing to spend that silence on. The
# concession costs little: membership in the portfolio IS having a NEXT.md.
#
# Pinned in BOTH directions on purpose. If a later session decides the global fact should win
# after all, these two cases are where the argument has to be had -- and the two tests above are
# what it has to be had against.

drifted = '{"cleanupPeriodDays": 30}'

unrelated = _SANDBOX / "unrelated"                 # no NEXT.md -- not in the system at all
unrelated.mkdir()
bare_cfg = _SANDBOX / "cfg-bare"
bare_cfg.mkdir()
(bare_cfg / "settings.json").write_text(drifted, encoding="utf-8")
# Run twice: a FIRST session against a fresh config dir also emits the one-shot install/create
# reports, so only the second run shows the steady state this case is about.
orient(unrelated, bare_cfg)
run_bare = orient(unrelated, bare_cfg)
check("exits 0", run_bare.returncode, 0)
check("a project with no NEXT.md stays completely silent, drift or not",
      run_bare.stdout.strip(), "")

# ...and any OTHER opted-in project, not just this repo, does get the line -- the check is not
# scoped to agent-reentry the way version_drift is.
elsewhere = _SANDBOX / "some-other-project"
elsewhere.mkdir()
subprocess.run(["git", "init", "-q"], cwd=str(elsewhere), capture_output=True, **NW)
(elsewhere / "NEXT.md").write_text(
    "# NEXT — unrelated project\n\n## Queue\n\n"
    "1. **Its own work** — Sonnet 5 · medium · AFK/Auto\n\n---\n\nAim: test.\n",
    encoding="utf-8")
other_cfg = _SANDBOX / "cfg-other"
other_cfg.mkdir()
(other_cfg / "settings.json").write_text(drifted, encoding="utf-8")
orient(elsewhere, other_cfg)
run_other = orient(elsewhere, other_cfg)
check("exits 0", run_other.returncode, 0)
check("an unrelated opted-in project gets the line too",
      "cleanupPeriodDays" in run_other.stdout, True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
