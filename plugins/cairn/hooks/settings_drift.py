#!/usr/bin/env python3
"""Settings that must be true on EVERY machine, checked on the machine you are actually on.

    python plugins/cairn/hooks/settings_drift.py            # this machine vs the required set
    python plugins/cairn/tools/check_settings.py --json     # same thing, the CLI wrapper

THE INCIDENT (B23, filed 2026-08-30)
------------------------------------
While answering D1, `cleanupPeriodDays` turned out to be UNSET in `~/.claude/settings.json` on
this laptop — so Claude Code's built-in default was live and quietly pruning session transcripts,
which are the only source `tools/timesheet.py` reads. It was set to 90 by hand, there and then.

But `~/.claude` is not a git repo, so that fix reached exactly ONE machine. Every other machine
kept the default and kept deleting the history the timesheets depend on, and nothing
anywhere was ever going to say so. The plugin already ships a RULES payload to every machine
(`rules/CLAUDE.md` -> `~/.claude/CLAUDE.md`, see `install_rules.py`); it had no equivalent for
SETTINGS, so any config fact that has to hold everywhere was carried by memory — the one thing
this whole system exists to stop relying on.

REPORT, NEVER WRITE — decided, not defaulted
--------------------------------------------
The alternative was an installer that merges required keys into `~/.claude/settings.json`. It is
rejected here and in the brief: writing into a user's GLOBAL settings from a plugin install is a
very large blast radius for a very small win, and a change with exactly that shape had to be
reverted on 2026-09-05. The actual harm in the incident above was not that the value was wrong on
three machines; it was that nobody KNEW. One line at orientation fixes that, costs one read of one
small JSON file, and leaves the write to a human who can see what else is in there.

So: this module opens `settings.json` read-only and never writes anything, anywhere. There is no
code path here that opens a file for writing — keep it that way.

WHAT IT IS ALLOWED TO CLAIM (the B44 lesson, applied to a second mechanism the same day)
----------------------------------------------------------------------------------------
This check reads ONE machine: the one it is running on. It cannot see LAPTOP1's settings file, and it
must never imply that it can — "this machine keeps 30 days, the others keep 90" is exactly the
sentence this tool is not entitled to say, because the second half is a guess. What it knows is
(a) the value here and (b) the value the plugin declares as required, and the printed line says
those two things and stops. The plugin ships the same declaration to every machine, so drift is
detectable ON each machine; it is never detectable ABOUT another one from here.

For the same reason a missing file, an unparseable file and a key set to a wrong value are three
DIFFERENT reports, never collapsed into one. "Unset" and "could not tell" are opposite problems.

SCOPE
-----
`REQUIRED` holds exactly one key today, on purpose. It grows when a second concrete setting earns
it the way this one did — a measured incident where the wrong value silently destroyed something —
not because a general settings-sync framework would be tidy.

NEVER RAISES. Every failure resolves to "no line" or to an explicit could-not-check line; an
orientation aid that can break a session start is worse than none (see `session_orientation.py`).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SETTINGS_FILENAME = "settings.json"

# The declared set — facts that must hold on every machine the user works from.
#
# `minimum` is a floor, not an equality: a machine keeping MORE history than required is not
# drift, and flagging it would train them to skim this line, which is the failure mode every
# threshold in this plugin is written against.
#
# `default_note` is what happens when the key is ABSENT. It is a statement about Claude Code's
# built-in behaviour, not about anything this code measured, so it is worded as such wherever it
# is printed — see the docstring on what this module may claim.
REQUIRED: tuple[dict, ...] = (
    {
        "key": "cleanupPeriodDays",
        "minimum": 90,
        "default_note": "30 days at the time this check was written",
        "why": "session transcripts are the only source tools/timesheet.py can read",
    },
)


def _config_dir() -> Path:
    """`~/.claude`, or `$CLAUDE_CONFIG_DIR` when set — identical resolution to
    `machine_identity._config_dir()` and `ensure_credentials_file._config_dir()`.

    The env override is what makes this testable WITHOUT ever touching the real file: every test
    points `CLAUDE_CONFIG_DIR` (or passes an explicit path) at a temp directory, so there is no
    fixture in this repo whose correctness depends on what the user's actual settings say.
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def settings_path(override: str | Path | None = None) -> Path:
    if override:
        return Path(override).expanduser()
    return _config_dir() / SETTINGS_FILENAME


def load(override: str | Path | None = None) -> tuple[dict | None, str | None]:
    """(settings, problem). `({}, None)` for a file that does not exist — an absent settings file
    genuinely means every key is unset, which is a KNOWN state, not an unknown one.

    `(None, "...")` only when the file is there and cannot be understood: unreadable, or not JSON,
    or JSON that isn't an object. Those are the cases where the honest answer is "could not tell",
    and the caller renders them differently from drift.

    Reads ONLY `settings.json` in the config dir. Claude Code also merges project-scope settings
    and any managed policy file; this module does not attempt to reconstruct that merge, because a
    half-right merge would produce confident wrong answers about which value is live. It says which
    file it read.
    """
    path = settings_path(override)
    if not path.exists():
        return {}, None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return None, f"could not read {path} ({exc.__class__.__name__})"
    try:
        data = json.loads(raw)
    except Exception:
        return None, f"{path} is not valid JSON"
    if not isinstance(data, dict):
        return None, f"{path} does not contain a JSON object"
    return data, None


def findings(settings: dict) -> list[str]:
    """One short phrase per required key that is unset or below its floor. Empty list = clean."""
    out: list[str] = []
    for spec in REQUIRED:
        key, floor = spec["key"], spec["minimum"]
        if key not in settings:
            out.append(f"`{key}` is unset here (Claude Code's built-in default applies — "
                       f"{spec['default_note']}), cairn expects >= {floor}: {spec['why']}")
            continue
        value = settings[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            out.append(f"`{key}` here is {value!r}, which is not a number; reentry expects "
                       f">= {floor}: {spec['why']}")
        elif value < floor:
            out.append(f"`{key}` here is {value}, cairn expects >= {floor}: {spec['why']}")
    return out


def check(override: str | Path | None = None) -> str | None:
    """ONE line for the orientation, or None when this machine is clean.

    None is the overwhelmingly common case — a machine is fixed once and then silent forever —
    which is what makes this cheap enough to run in every project on every session.
    """
    settings, problem = load(override)
    path = settings_path(override)
    if problem is not None:
        return (f"settings check skipped: {problem}. The keys cairn needs "
                f"({', '.join(s['key'] for s in REQUIRED)}) could not be read on this machine.")
    found = findings(settings or {})
    if not found:
        return None
    # "on THIS machine" is load-bearing, not padding: the value on any OTHER machine is not
    # something this line has seen, and the closing clause says so rather than letting the reader
    # infer a fleet-wide statement from a one-machine reading.
    return ("⚠ settings drift on THIS machine (" + str(path) + "): " + "; ".join(found)
            + ". Report only — nothing here writes to settings.json, and no other machine is "
              "checked by this line.")


def _cli(argv: list[str] | None = None) -> int:
    """Shared by `python hooks/settings_drift.py` and `tools/check_settings.py`.

    Exit 0 = every required key holds on this machine; 1 = drift, or the file could not be read.
    """
    import argparse
    import sys

    # The report line carries `⚠` and an em-dash, and a Windows console defaults to cp1252 --
    # which raised UnicodeEncodeError inside `print`, was caught by the never-break handler
    # below, and turned a DRIFT verdict into "could not run" plus exit 0. A report tool that
    # cannot break is only safe if it also cannot silently invert its own answer. Found by
    # running the CLI, not by reading it. `session_orientation.py` does the same thing at import
    # for the same reason.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(prog="settings_drift.py",
                                 description="Check this machine's settings.json against the "
                                             "keys cairn requires everywhere. Read-only.")
    ap.add_argument("--settings-file", default=None,
                    help="path to settings.json (default: $CLAUDE_CONFIG_DIR or ~/.claude)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    path = settings_path(args.settings_file)
    settings, problem = load(args.settings_file)
    found = [] if settings is None else findings(settings)
    ok = problem is None and not found

    if args.as_json:
        print(json.dumps({
            "ok": ok,
            "settings_file": str(path),
            "readable": problem is None,
            "problem": problem,
            "required": [{"key": s["key"], "minimum": s["minimum"],
                          "value": (settings or {}).get(s["key"])} for s in REQUIRED],
            "findings": found,
        }, indent=2))
    else:
        print(f"settings.json: {path}" + ("" if path.exists() else " (does not exist)"))
        line = check(args.settings_file)
        print(line if line else
              "every required key holds on this machine: "
              + ", ".join(f"{s['key']} >= {s['minimum']}" for s in REQUIRED))
        print("\nThis reads ONE machine — the one you are on. It cannot see any other machine's "
              "settings, and never writes.")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    try:
        sys.exit(_cli())
    except SystemExit:
        raise
    except Exception as exc:                                  # pragma: no cover
        print(f"settings check could not run ({exc}) - check settings.json by hand")
        sys.exit(0)                                           # a report tool must never break
