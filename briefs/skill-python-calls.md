# Brief — make the skills' tool calls resolve (B59)

Filed 2026-09-25 at the v1.61.0 wrap. `Opus 5` · effort `high` · `AFK/Auto`.
**Commit locally, then stop. The push and `tools/sync_backlog.py` wait for the user.**

## The bug

`skills/*/SKILL.md` and `rules/CLAUDE.md` tell the agent to run commands of the form

    python "$CLAUDE_PLUGIN_ROOT/hooks/wrap_receipt.py" --record

There are 17 call sites, listed by `grep -rn 'python "' plugins/cairn/skills plugins/cairn/rules`.
Two independent things are wrong with that line:

1. **`$CLAUDE_PLUGIN_ROOT` is unset in the agent's Bash tool.** Measured 2026-09-25 on NB1 (desktop
   app, Windows) with `echo ${CLAUDE_PLUGIN_ROOT:-unset}` → `unset`. Claude Code exports it to
   *hook* processes only. The skill text is not substituted either: the loaded SKILL.md shows the
   literal `$CLAUDE_PLUGIN_ROOT`. So the command expands to `python "/hooks/…"` **on every
   platform**, and every wrap has been working only because the agent quietly found the path some
   other way (the repo checkout, or the "Base directory for this skill" line the harness prints).
2. **Bare `python`** fails on stock Ubuntu/Debian, the same defect v1.61.0 fixed for the hooks (D31).

The `--record` step is REQUIRED for a `CAIRN SET`, so on a stranger's Linux machine the wrap's
own verdict tool is the thing that fails. That is the aim line.

## What is already known (don't re-derive)

- The hooks now go through `hooks/run.sh` (v1.61.0, D31), which resolves `$CAIRN_PYTHON` → the
  platform's Python names, and falls back to its own directory when `CLAUDE_PLUGIN_ROOT` is unset.
  So `sh "<plugin root>/hooks/run.sh" wrap_receipt.py --record` works anywhere a POSIX shell does,
  and `run.sh` should only launch files under `hooks/`. Tools under `tools/` need either a second
  shim or a `run.sh` that accepts a relative path. Decide which, and add a row to D31 or a new row.
- The harness prints `Base directory for this skill: <path>` at the top of every loaded skill.
  That path is `<plugin root>/skills/<name>`, and it is the one reliable root the agent has.
- The rules file is **always loaded**, so every character added there costs tokens every
  session. Measure before and after with `python plugins/cairn/tools/measure_context.py .`,
  and report both numbers.

## Decide

Likely shape: one short sentence near the top of each skill (and one in `rules/CLAUDE.md`)
defining the plugin root as "two directories above this skill's base directory", plus the call
sites rewritten to go through `run.sh`. Alternatives to weigh: a one-time `CAIRN_PLUGIN_ROOT`
export written into `settings.json` `env` by `install_rules` (that's a settings write, so check
D9's disclosure rule), or keeping `python` and only fixing the root. Record the choice and the
rejected options in `docs/decisions.md`.

## Done looks like

On Windows (Git Bash) and in WSL Ubuntu with no `python`, an agent following each rewritten
line literally, with `CLAUDE_PLUGIN_ROOT` unset, runs the right file. The full
`tools/run_tests.py` suite passes, and a test pins that no skill or rules line contains a bare
`python "$CLAUDE_PLUGIN_ROOT` again. Bump the version, write CHANGELOG, commit locally, then
**stop and report**: files changed, test output, token delta, and anything decided.
