#!/usr/bin/env python3
"""Install the plugin's rules into `~/.claude/CLAUDE.md`, inside markers.

WHY THIS EXISTS
---------------
A Claude Code plugin cannot contribute always-loaded context. Verified 2026-08-22 against the
shipped binary, not the docs: `plugin.json`'s schema is
`$schema, name, displayName, version, description, author, homepage, repository, license,
keywords, defaultEnabled, dependencies, metadata` — no instructions/memory/rules field — and the
plugin component directories are `.claude-plugin, agents, output-styles, themes, hooks, monitors,
workflows` plus commands and skills. Instruction files are discovered ONLY from
`~/.claude/CLAUDE.md`, a project's `CLAUDE.md` / `CLAUDE.local.md` / `.claude/CLAUDE.md` /
`.claude/rules/*.md`, and org-managed memory. There is no plugin path into any of them.

So a plugin has exactly two ways to put words in front of the agent every session:

  1. `SessionStart` hook stdout — ships, but is billed to every session in every project
     forever. It was ~803 tokens in `code/` on 2026-08-22 and must stay small; this system has
     already had to delete a 1,629-token footer and is mid-way through trimming a 13,355-token
     `ARCHITECTURE.md`. The full rules are ~2,500 tokens. They do not go here.
  2. `~/.claude/CLAUDE.md` — always loaded, and ALREADY BILLED (3,969 tokens on 2026-08-22).

This module takes route 2 and removes its one defect: that the file was untracked, in no repo,
and therefore shipped nowhere. The tracked copy at `rules/CLAUDE.md` is now the source; the file
in `~/.claude` becomes a generated artifact. Cost per session is unchanged — the same words were
already being read — but they now arrive on every machine the plugin is installed on, straight
from `plugin install`.

DESIGN RULES
------------
  - NEVER fail the session. Every path returns quietly; the caller wraps this in try/except too.
  - Only ever touch text BETWEEN the markers. Anything the user writes outside them is theirs,
    and a hook that eats a hand-written note is worse than a hook that ships nothing.
  - Idempotent. Same version already installed → do nothing, print nothing, touch nothing.
  - Back up before the first modification, and keep the backup that already exists.
  - Say what it did, in ONE line. A mechanism that leaves no evidence it ran gets reported as
    broken and cannot be defended without re-reading the code (2026-08-15).
"""
import os
import shutil
import sys
from pathlib import Path

try:                                    # the PROFILE layer — see ensure_profile_file.py's docstring
    import ensure_profile_file
except Exception:                       # pragma: no cover - absent copy must never break an install
    ensure_profile_file = None          # type: ignore[assignment]

BEGIN = "<!-- reentry:begin"
END = "<!-- reentry:end -->"

PROFILE_IMPORT = "@~/.claude/reentry-profile.md"


def _read(path: Path) -> str:
    """Read with newlines normalised to \\n.

    Windows text mode translates \\n to \\r\\n on write, so a naive read-back never equals the
    block we just wrote and the installer rewrites the file on EVERY session start — churning
    a backup each time and printing a "v1.9.0 → v1.9.0" update line. Caught by testing the
    second run rather than only the first, 2026-08-22.
    """
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _write(path: Path, text: str) -> None:
    """Write \\n verbatim, so what lands on disk is what we compared against."""
    path.write_text(text, encoding="utf-8", newline="\n")


def _backup(target: Path) -> Path:
    """`CLAUDE.md.bak-reentry-install` beside the file — one rolling copy of the last good state.

    Distinct from the hand-made `CLAUDE.md.bak-reentry` that predates this, which is left alone.
    """
    return target.with_name(target.name + ".bak-reentry-install")


def _config_dir() -> Path:
    """`~/.claude`, unless CLAUDE_CONFIG_DIR says otherwise (the binary honours it, so do we)."""
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def _plugin_version() -> str:
    """Read the version off plugin.json — never hardcode it, it rots (three constants already had)."""
    import json
    manifest = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
    try:
        return str(json.loads(manifest.read_text(encoding="utf-8")).get("version") or "0")
    except Exception:
        return "0"


def _rules_source() -> str | None:
    src = Path(__file__).resolve().parent.parent / "rules" / "CLAUDE.md"
    try:
        return _read(src)
    except Exception:
        return None


def _block(version: str, body: str) -> str:
    """The managed block, ending in the profile import.

    The `@` import is appended HERE rather than left to the rules text, so it ships whether or not
    whoever last edited `rules/CLAUDE.md` remembered it. The mechanism half of this system is
    generic and shared; the person half lives in `~/.claude/reentry-profile.md` and is read every
    session through this line. A rules file that ships without it silently loses the profile — a
    failure that looks exactly like a correct install. See ensure_profile_file.py.
    """
    text = body.rstrip()
    if PROFILE_IMPORT not in text:
        text += (
            "\n\n## Who you're working with — the profile, not the mechanism\n\n"
            "Everything above is the MECHANISM and is the same for everyone. Who the user is, and\n"
            "how they like work done, is theirs and is read from the file below. If it is missing\n"
            "or still the seeded template, say so once and offer to fill it in — never guess.\n\n"
            f"{PROFILE_IMPORT}"
        )
    return (
        f"{BEGIN} v{version} — managed by the cairn plugin.\n"
        f"     EDIT `rules/CLAUDE.md` IN THE PLUGIN SOURCE, NOT HERE — this block is regenerated.\n"
        f"     Anything you write OUTSIDE these markers is yours and is never touched. -->\n"
        f"{text}\n"
        f"{END}\n"
    )


def _find_block(text: str) -> tuple[int, int, str] | None:
    """Return (start, end_exclusive, installed_version) for an existing managed block."""
    start = text.find(BEGIN)
    if start == -1:
        return None
    end = text.find(END, start)
    if end == -1:
        return None
    end += len(END)
    if text[end:end + 1] == "\n":
        end += 1
    header = text[start:text.find("-->", start) + 3]
    version = ""
    for token in header.split():
        if token.startswith("v") and token[1:2].isdigit():
            version = token[1:]
            break
    return start, end, version


def install(project_root: Path | None = None) -> tuple[str | None, bool]:
    """Seed the profile, then sync the managed block. Same `(report, in_context)` contract.

    ORDERING IS THE POINT, and it is why this call lives here rather than beside
    `ensure_mistakes_file.ensure()` in `session_orientation.main()`. `~/.claude/CLAUDE.md` is
    parsed at LAUNCH; hooks run after. So the block's `@~/.claude/reentry-profile.md` import must
    never be written in a run where that file does not yet exist, or the first session on a fresh
    machine parses an import with no target. Seeding first closes the window completely: every
    run that could write the import has already guaranteed the file.

    `project_root` is passed straight to `ensure_profile_file.ensure()`, which refuses a
    `REENTRY_PROFILE_SOURCE` that resolves inside it (B103) -- this module has no opinion on
    containment itself, it just carries the caller's root down to the layer that checks it.
    """
    profile_line = None
    try:
        profile_line = ensure_profile_file.ensure(project_root) if ensure_profile_file else None
    except Exception:
        profile_line = None             # never fail a session over a file seed
    report, in_context = _install_block()
    both = "\n".join(line for line in (profile_line, report) if line)
    return (both or None), in_context


def _install_block() -> tuple[str | None, bool]:
    """Sync the managed block into `~/.claude/CLAUDE.md`.

    Returns `(report, in_context)`:
      report      — one line for the agent when this run changed something, else None.
      in_context  — True only when the block was ALREADY current before this run, i.e. the
                    session that is starting has read these rules as part of its CLAUDE.md.

    `in_context` is what lets the hook skip its fallback rules block. Those rules are a copy of
    what the file already says, so printing them in the steady state costs ~224 tokens in every
    session in every project to repeat something the agent has just read. They are only worth
    printing in the window where the file is NOT yet in context: a fresh machine's first session,
    the session right after a plugin update, or a failed write. Measured 2026-08-22 — printing
    them unconditionally took `code/` from 4,772 to 5,154 tokens per session.
    """
    body = _rules_source()
    if not body:
        return None, False              # no rules shipped — nothing to install, say nothing
    if BEGIN in body or END in body:
        # The body would contain a copy of its own delimiters, so `_find_block` would stop at
        # the inner one and every later run would rewrite a truncated block. Caught 2026-08-22
        # by the third-run idempotency test, after the rules text gained a paragraph explaining
        # the markers — and quoted them. Refuse rather than corrupt.
        return None, False
    version = _plugin_version()
    target = _config_dir() / "CLAUDE.md"

    try:
        existing = _read(target)
    except FileNotFoundError:
        existing = None
    except Exception:
        return None, False              # unreadable (permissions, encoding) — never guess

    block = _block(version, body)

    if existing is None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            _write(target, block)
        except Exception:
            return None, False
        return (f"[to the agent] Installed the cairn rules into {target} (v{version}) — this "
                f"machine had none. They are NOT in your context yet: ask the user to restart "
                f"this session, or read the file now."), False

    found = _find_block(existing)

    if found is None:
        # A real file with no managed block: prepend, so the system rules land before whatever
        # was already there, and keep every byte of the user's own text below.
        try:
            shutil.copy2(target, _backup(target))
            _write(target, block + "\n" + existing)
        except Exception:
            return None, False
        return (f"[to the agent] Added the cairn rules block to {target} (v{version}); the "
                f"file's previous contents were kept below it and backed up. Not in your "
                f"context until the next session."), False

    start, end, installed = found
    if installed == version and existing[start:end] == block:
        return None, True               # already current — the common case, silent by design

    try:
        shutil.copy2(target, _backup(target))
        _write(target, existing[:start] + block + existing[end:])
    except Exception:
        return None, False
    return (f"[to the agent] Updated the cairn rules block in {target}: v{installed or '?'} → "
            f"v{version}. The version in YOUR context is the old one until the next session."), False


if __name__ == "__main__":
    line, _current = install()
    if line:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(line)
