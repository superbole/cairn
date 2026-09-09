#!/usr/bin/env python3
"""Create `~/.claude/reentry-profile.md` if it doesn't exist. Global, one file, plugin-installed.

WHY THIS EXISTS
---------------
`install_rules.py` writes `rules/CLAUDE.md` verbatim into every installer's `~/.claude/CLAUDE.md`.
Until v1.45.0 that file was written about one named person -- it opened with their medical
history, then named their machines, their projects and their employer's git host. Anyone the
plugin was shared with got all of that installed into their always-loaded context, plus rules
calibrated to someone else's memory rather than their own.

The split is three ways, not two:

  MECHANISM   the three lists, the wrap verdict, attendance/mode, the footer budget, the relay
              tiers. Generic, and the reason the plugin is worth sharing. SHIPS.
  IDENTITY    who the user is, which machines they use, which host their issues live on.
  PREFERENCE  HOW they like work done -- report length, delegation style, which tier for which
              kind of work. Someone else may reasonably want the opposite.

Identity and preference live in the file this module creates. The shipped rules end with an
`@~/.claude/reentry-profile.md` import, so the profile is read every session at no extra
mechanism -- the import is a documented Claude Code feature and resolves at the user level.

The test that separates mechanism from preference, and it is NOT "does it name a person":
*would this rule still be correct for a user with a different working style but the same tooling?*
Yes -> mechanism, however personally phrased. No -> preference, however impersonally phrased.

CROSS-MACHINE: `REENTRY_PROFILE_SOURCE`
---------------------------------------
A profile is worth writing once, not once per machine, and a user working from several machines
has no way to carry one across without help. So this module reads an OPTIONAL environment
variable naming a source file -- typically in a repo or a synced folder they already have:

  unset      seed the commented template once, then never touch the file again. The
             single-machine default, and the behaviour of `ensure_mistakes_file.py` next door.
  set        copy source -> `~/.claude/reentry-profile.md` whenever the source is NEWER.
             One direction only, never source <- target, and the previous content is backed up
             first (same as `install_rules.py`).

Set it persistently in `~/.claude/settings.json`'s `env` block; the plugin only ever READS that
file (`settings_drift.py`'s standing rule), so nothing here writes to it.

What syncs the source folder -- git, OneDrive, Dropbox -- is the user's choice and none of this
plugin's business. This module copies one file, locally, when it is stale. It syncs nothing.

DESIGN RULES (same as ensure_mistakes_file.py)
----------------------------------------------
  - NEVER fail the session. Every path returns quietly; the caller wraps this in try/except too.
  - Idempotent. Nothing to do -> do nothing, print nothing, touch nothing. A source that is
    missing, unreadable, or not newer is not an error and is never reported as one.
  - Content is compared before any write, not just mtimes. `shutil.copy2` preserves mtime, so a
    steady state stays quiet -- but a touched-but-unchanged source must not churn a backup
    either. Same bug class `install_rules._read()` documents (caught 2026-08-22 by testing the
    SECOND run, not the first).
  - Existing content is NEVER discarded without a backup beside it.
  - Say what it did, in ONE line, only on a run that changed something.
"""
import os
import shutil
import sys
from pathlib import Path

try:
    import reentry_state
except Exception:                       # pragma: no cover - absent copy must never break an install
    reentry_state = None                # type: ignore[assignment]

FILENAME = "reentry-profile.md"
SOURCE_ENV = "REENTRY_PROFILE_SOURCE"

TEMPLATE = """# Re-entry profile

Who you are, and how you like work done. The re-entry plugin's rules are the MECHANISM and ship
to everyone; this file is the half that is yours, and it is read into context every session by an
`@` import from the managed block in `~/.claude/CLAUDE.md`.

**Nothing here is generated.** Delete what does not apply, write what does, in your own words. An
empty profile is fine -- the mechanism works without it. A profile full of someone else's
preferences is worse than none.

**Working from more than one machine?** Keep the real copy somewhere private and version
controlled, then point this at it. **The path must be OUTSIDE any project you open** -- a source
inside the current project is refused, because a repo could otherwise supply the file that
overwrites your always-loaded profile (B100/B103). So clone the private repo to a path you never
`cd` into for work, rather than pointing at your working checkout:

```jsonc
// ~/.claude/settings.json
{ "env": { "REENTRY_PROFILE_SOURCE": "~/.claude-private/<your-repo>/profile.md" } }
```

`~/Projects/<your-repo>/profile.md` looks like the obvious value and is the one thing that cannot
work: it is inside a project by construction, so the guard refuses it in exactly the repo where
you edit the profile (B107, found live 2026-09-06 -- this text used to recommend it).

The plugin then refreshes this file from that path whenever the source is newer, one direction
only, backing up what was here first. Unset, this file is seeded once and never touched again.

---

## Who you're working with

Your name or handle, what you do, and anything an agent would otherwise have to infer from your
messages. Say why re-entry matters to you specifically -- the mechanism assumes state cannot be
carried between sessions, and it is worth knowing whether that is a memory problem, too many
projects at once, long gaps between sessions, or simply a preference for working off disk.

## How you like work done

The mechanism does not have opinions about these. Write yours, or delete the ones you do not
care about.

- **Report length.** Short and direct, or thorough with the reasoning shown?
- **Delegation.** Does "if you agree, build it" mean build it, or come back and confirm first?
- **Side quests.** A finding that is not today's work -- record it and stay on the main thread,
  or chase it now while the context is loaded?
- **Disagreement.** How do you push back, and what should an agent do when you do?
- **Model and effort defaults.** Which tier for which kind of work, if the shipped defaults
  (judgement work high, mechanical work medium) are not yours.

## Your machines

One line each: what you call it, what you do on it, anything an agent needs to know before
suggesting a command. `MACHINES.md` holds the hostname mapping the tools read; this is the prose
half, for the things a mapping cannot say.

## Your issue host, and anything else project-wide

Where backlog items sync to, which identity authenticates, and any standing constraint an agent
should not have to rediscover.
"""


def _config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def _backup(target: Path) -> Path:
    """`reentry-profile.md.bak-reentry-profile` beside the file -- the state before a refresh."""
    return target.with_name(target.name + ".bak-reentry-profile")


def _source() -> Path | None:
    """The configured source file, or None. A path that is set but absent is NOT an error.

    Deliberately quiet: a user whose synced folder has not mounted yet, or who is on a machine
    where that path does not exist, gets the profile they already have rather than a warning
    every session about a file the plugin was never going to write anyway.
    """
    raw = os.environ.get(SOURCE_ENV, "").strip().strip("\"").strip("'")
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
    except Exception:
        return None
    return path if path.is_file() else None


def _read(path: Path) -> str:
    """Read with newlines normalised, so a CRLF/LF difference is not read as a content change."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _contained_in_project(source: Path, root: Path) -> bool:
    """True if `source` resolves inside `root` -- the project the hook fired for.

    Two checks, because a project need not be a git repo: `relative_to` catches the plain
    directory case, `reentry_state.toplevel()` catches a source that is elsewhere IN THE SAME
    repo (a subdirectory checkout, a worktree) that `relative_to` alone would miss.
    """
    try:
        resolved_source = source.resolve()
        resolved_root = root.resolve()
    except Exception:
        return False
    try:
        resolved_source.relative_to(resolved_root)
        return True
    except ValueError:
        pass
    if reentry_state is None:
        return False
    root_repo = reentry_state.toplevel(resolved_root)
    if root_repo is None:
        return False
    return reentry_state.toplevel(resolved_source) == root_repo


def _refusal(project_root: Path | None) -> str | None:
    """One line if `REENTRY_PROFILE_SOURCE` is set but must be REFUSED, else None.

    B100 proved a project's own `.claude/settings.json` `env` block reaches plugin hook
    environments, and `install_rules.install()` runs on just opening the directory -- not on
    opting the project in. Combined with a relative, unresolved source path, a cloned repo
    needed nothing but `"REENTRY_PROFILE_SOURCE": "profile.md"` and a file in its own root to
    overwrite the victim's ALWAYS-LOADED profile the first time they opened it. Two refusals
    close that: a relative path (no legitimate use -- the variable always names a real,
    already-known location) and a source that resolves inside the current project.

    Silence here would be indistinguishable from "not set" or "file missing" -- both
    deliberately quiet -- so a refusal gets its own line, reported regardless of relay tier:
    the user's always-loaded instructions were about to change. See docs/decisions.md D11.
    """
    raw = os.environ.get(SOURCE_ENV, "").strip().strip("\"").strip("'")
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
    except Exception:
        return None
    if not path.is_absolute():
        return (f"[to the agent] Refused {SOURCE_ENV}={raw!r} -- it is a relative path, which "
                f"resolves against the CURRENT PROJECT's directory rather than a fixed location. "
                f"Point it at an absolute path instead.")
    if project_root is not None and _contained_in_project(path, project_root):
        return (f"[to the agent] Refused {SOURCE_ENV}={raw!r} -- it resolves inside this project "
                f"({project_root}), so opening this directory could overwrite your global, "
                f"always-loaded profile. Point it at a file outside any project instead.")
    return None


def ensure(project_root: Path | None = None) -> str | None:
    """Seed or refresh `~/.claude/reentry-profile.md`. Returns a report line or None.

    `project_root` is the directory the hook fired for -- pass it so a source configured by
    THAT project's own `.claude/settings.json` can be checked for containment before it is
    ever read. None (the default) skips the containment check, not the caller's problem to work
    around; every real caller has a root and passes it.
    """
    target = _config_dir() / FILENAME
    refusal = _refusal(project_root)
    if refusal:
        if not target.exists():         # same fallback as a missing source (3a): never leave
            try:                        # them with no profile at all over a refused one
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(TEMPLATE, encoding="utf-8", newline="\n")
            except Exception:
                pass
        return refusal
    source = _source()

    if source is None:
        if target.exists():
            return None                 # the steady state: seeded once, never touched again
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(TEMPLATE, encoding="utf-8", newline="\n")
        except Exception:
            return None
        return (f"[to the agent] Created {target} -- this machine had none. It is a TEMPLATE: tell "
                f"the user it is theirs to fill in, and that {SOURCE_ENV} carries it between machines.")

    try:
        incoming = _read(source)
    except Exception:
        return None                     # unreadable source -- leave whatever is already there

    if not target.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        except Exception:
            return None
        return f"[to the agent] Installed {target} from {SOURCE_ENV} ({source}) -- this machine had none."

    try:
        current = _read(target)
        if current == incoming:
            return None                 # identical -- never churn a backup over an mtime skew
        # THE ORDERING TRAP, and why mtime alone is not enough. Install the plugin first and the
        # template is seeded NOW; the source in a repo was written whenever it was last edited,
        # which is earlier. Point `REENTRY_PROFILE_SOURCE` at it afterwards -- the obvious order,
        # and the one a first install actually takes -- and the mtime test says "target is newer,
        # a local edit wins", so the real profile never lands and the user reads a template back
        # forever. An UNTOUCHED TEMPLATE is not a local edit: nobody wrote it, so nothing is lost
        # by replacing it, and it is byte-identical to what this module put there.
        if current != TEMPLATE and source.stat().st_mtime <= target.stat().st_mtime:
            return None                 # a real local edit wins until the source itself changes.
                                        # One direction, never back.
        shutil.copy2(target, _backup(target))
        shutil.copy2(source, target)
    except Exception:
        return None
    return (f"[to the agent] Refreshed {target} from {SOURCE_ENV} ({source}); the previous version "
            f"is backed up beside it. The version in YOUR context is the old one until next session.")


if __name__ == "__main__":
    line = ensure()
    if line:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(line)
