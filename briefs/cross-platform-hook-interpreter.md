# Brief — cross-platform hook interpreter

Filed 2026-09-11 from `SBOLE-NB5` (WSL), where it was found during a clean install.

## The bug

All five hook entry points in `plugins/cairn/hooks/hooks.json` invoke the interpreter as bare
`python`:

    "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/session_orientation.py\""

Ubuntu and Debian ship `python3` only. There is no `python` on a stock install, so on those
systems every cairn hook fails to start: `SessionStart`, `UserPromptSubmit`, `PostToolUse`,
`Stop` and `SessionEnd`.

## What that costs

`session_orientation.py` is the hook that calls `install_rules.install()`,
`ensure_profile_file.ensure()`, `ensure_mistakes_file.ensure()`,
`ensure_credentials_file.ensure()` and `machine_identity.ensure_file()`. None of them run, so a
Linux installer gets **none** of the five global files — no `CLAUDE.md`, no `reentry-profile.md`,
no `MISTAKES.md`, no `CREDENTIALS.md`, no `MACHINES.md`. The skills still load, so `/cairn:next`
and `/cairn:wrap` appear in the menu and read state that was never written.

Observed on `SBOLE-NB5`: marketplace added, plugin enabled, `claude plugin list` reporting
`✔ enabled` — and zero state files. Creating `~/.local/bin/python -> /usr/bin/python3` and
re-running the hook by hand generated all five on the first run, and printed nothing on the
second, so the hooks themselves are correct. Only the interpreter name is wrong.

This contradicts the repo's stated aim directly: *"a stranger installs from this repo and orients
in their own project with no manual setup."* Today a stranger on Ubuntu gets silence.

## Why this is not a one-line swap

`python` -> `python3` moves the breakage to Windows, which usually has `python` (Store alias or
`py` launcher) and often no `python3`. No single interpreter name is present on Windows, Linux
and macOS, and `hooks.json` allows one command string per hook with nowhere to branch.

## Why the plugin cannot warn about it

The hook that would report the problem is the hook that cannot start. A preflight check inside
any hook module is unreachable by construction — the failure happens before Python is entered.
So this cannot be fixed by detection; it has to be fixed by the command string, by a launcher
resolved per platform, or by an install-time instruction in the README.

## Decide

1. A launcher shim in the plugin that each platform can execute, with `hooks.json` calling that.
2. Keep `python` and make the requirement explicit at install time (README + a documented
   `python-is-python3` / symlink step). Cheapest, but leaves the silent failure in place for
   anyone who skips it.
3. Something else — worth checking whether Claude Code expands anything in a hook command that
   could carry the interpreter per platform.

## Which machines are affected

`SBOLE-NB5` was found broken and is now patched locally with a
`~/.local/bin/python -> /usr/bin/python3` symlink — a workaround on one machine, not a fix, and it
does not carry to the others. **`SBOLE-NB1` and `DeepThought` have not been checked.** Any of them
running Linux has the same silent failure: plugin enabled, `claude plugin list` green, no state
files. Check each before assuming the install took.

## Done looks like

A fresh install on a stock Ubuntu box, with no `python` on `PATH` and no manual step, produces
all five global files on first session start — and the same install still works on Windows.
