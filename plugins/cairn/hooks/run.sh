#!/bin/sh
# Launch one cairn hook under whatever this machine calls Python 3. (v1.61.0, D31)
#
#     sh "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" session_orientation.py [args...]
#     sh "<plugin root>/hooks/run.sh" tools/measure_context.py [args...]      (B59)
#
# A bare name is a file in hooks/. A name with a slash must start hooks/ or tools/ and contain
# no `..` -- that second form is for the AGENT, which the skills send through here too: the
# agent's own shell has no CLAUDE_PLUGIN_ROOT (measured 2026-09-25) and may have no `python`,
# so a skill line naming either one fails. The skills tell it to find this file from the
# skill's base directory instead, and everything after that is resolved here, once.
#
# WHY A SHELL SCRIPT. `hooks.json` allows one command string per hook, and no interpreter name
# exists on all three platforms: stock Ubuntu/Debian has only `python3`, and on Windows `python3`
# is often the Microsoft Store redirector stub while `python` is the real one (measured on a
# Windows machine, 2026-09-25). Bare `python` meant every hook failed on Linux before Python
# was entered, so the plugin installed "enabled" and wrote nothing. The one thing every hook
# DOES have is a POSIX shell -- Claude Code runs shell-form hooks via `sh -c` on macOS/Linux and
# Git Bash on Windows -- so the resolution happens here.
#
# BECAUSE THE SHELL RUNS WHEN PYTHON DOES NOT, this is the one place a missing interpreter can be
# REPORTED. Every other layer of the plugin is Python and cannot see its own absence.
#
# ORDER. `$CAIRN_PYTHON` wins when set (a full path, via the `env` block of settings.json). On
# Windows `python` comes first, so behaviour there is exactly what it was before this file
# existed; everywhere else `python3` comes first. `command -v` only -- a probe that starts Python
# would cost a second interpreter launch on every tool call (PostToolUse).
#
# Stdin, arguments and the exit code pass straight through `exec`: `staged_review_guard.py`
# blocks a commit with exit 2, and that must reach Claude Code unchanged.

hook=${1:-}
if [ -z "$hook" ]; then
  echo "cairn: run.sh needs a hook file name, e.g. run.sh session_orientation.py" >&2
  exit 0
fi
shift

# CLAUDE_PLUGIN_ROOT is used only when it names THIS file's own plugin -- true of every hook,
# at the cost of one string compare. Anywhere else (the agent's shell, where it is unset, or a
# checkout run by path while it points at the installed copy) the root is where this file is.
root=${CLAUDE_PLUGIN_ROOT:-}
if [ -z "$root" ] || [ "$0" != "$root/hooks/run.sh" ]; then
  # Parameter expansion, not `dirname`: builtins only, so it works on a PATH with nothing on it.
  dir=${0%/*}
  [ "$dir" = "$0" ] && dir=${0%\\*}        # a Windows path with only backslashes
  [ "$dir" = "$0" ] && dir=.               # `sh run.sh` from inside hooks/
  root=$(cd "$dir/.." && pwd)
fi
case "$hook" in
  *..*) bad=1 ;;
  hooks/*|tools/*) bad= ; target="$root/$hook" ;;
  */*) bad=1 ;;
  *) bad= ; target="$root/hooks/$hook" ;;
esac
if [ -n "$bad" ]; then
  echo "cairn: run.sh only runs a hooks/ or tools/ file of its own plugin, not: $hook" >&2
  exit 0
fi

found() { command -v "$1" >/dev/null 2>&1; }

if [ -n "${CAIRN_PYTHON:-}" ]; then
  exec "$CAIRN_PYTHON" "$target" "$@"
fi

if [ "${OS:-}" = "Windows_NT" ]; then
  if found python;  then exec python  "$target" "$@"; fi
  if found py;      then exec py -3   "$target" "$@"; fi
  if found python3; then exec python3 "$target" "$@"; fi
  tried="python, py -3, python3"
else
  if found python3; then exec python3 "$target" "$@"; fi
  if found python;  then exec python  "$target" "$@"; fi
  tried="python3, python"
fi

# Nothing to exec. Exit 0 regardless: a broken install must never block a tool call.
msg="cairn: no Python 3 on PATH (tried: $tried), so no cairn hook or tool can run on this machine. Install Python 3, or set CAIRN_PYTHON to its full path in the \"env\" block of ~/.claude/settings.json."
if [ "$hook" = "session_orientation.py" ]; then
  # SessionStart stdout lands in the agent's context -- the only route to the user.
  echo "[to the agent] RELAY FIRST -- $msg"
else
  echo "$msg" >&2
fi
exit 0
