#!/usr/bin/env python3
"""Detect that THIS MACHINE is running a stale copy of the cairn plugin.

Origin: the v1.29.0 wrap (2026-08-30) found `installed_plugins.json` reading `1.27.0` while
`plugins/cairn/.claude-plugin/plugin.json` in this repo read `1.29.0` — two versions' worth of
shipped, pushed, committed fixes (including this very hook) had never actually been running on
this machine, and nothing said so. Found only because a wrap happened to look. See
`briefs/version-drift-detection.md`.

Scope guard: only this plugin's own source repo has anything to compare — `plugins/cairn/.claude-plugin/
plugin.json` only exists in this repo, so its absence is what keeps every other project silent.

Does NOT install anything. Detect and say so, nothing more — a `SessionStart` hook cannot restart
the session it's running in to apply an install, and mutating the plugin it's currently executing
from is a shape worth refusing outright.

THE SECOND CHECK (v1.32.0, B41) — installed vs THE RULES BLOCK
--------------------------------------------------------------
There are THREE versions, and until v1.32.0 this module compared two of them:

    repo `plugin.json`   what has been shipped        (only in the plugin's own source repo)
    `installed_plugins.json`   what is downloaded     (machine-global)
    `<!-- reentry:begin v<N> -->` in `~/.claude/CLAUDE.md`
                         WHAT IS ACTUALLY IN FRONT OF THE AGENT, every session, every project

The third was compared to nothing, anywhere. It is the one that matters: a machine can report the
new version and run the old rules, because `install_rules` writes that block from `SessionStart` —
so `claude plugin update` alone never touches it.

**This check is deliberately NOT scope-guarded.** Repo-vs-installed needs a repo and so is right to
be silent outside that repo; installed-vs-rules needs no repo at all, and the rules it is
about are loaded in EVERY project. Inheriting the guard would have hidden it exactly where it
matters most.

**What it can and cannot see.** `session_orientation.py` calls `install_rules.install()` before it
calls this, so in the healthy case the two numbers already agree by the time we look. That is the
point: a mismatch here means the install did not happen or did not stick — the failure
`install_rules` is designed to swallow silently ("NEVER fail the session"). It cannot see the
window between `claude plugin update` and the next session start, because nothing running inside a
session can; `tools/check_install.py` is the out-of-session answer to that.

Found 2026-09-01, when the user updated LAPTOP1 to v1.31.0, checked, and got a correct "stale" followed
minutes later by a correct "current", with nothing anywhere explaining either.
"""
import json
import os
import re
from pathlib import Path

# `<!-- reentry:begin v1.62.0 -->` (v1.61.0 and earlier: `… v1.31.0 — managed by …`), written by
# install_rules._block(). A search, not a parse: this only reads the version, it never edits.
_MARKER_RE = re.compile(r"reentry:begin\s+v([0-9][0-9.]*)")

SEPARATOR = "\n\n"      # blank line between findings; the call site adds one before


def _config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".claude"


def _repo_version(root: Path) -> str | None:
    manifest = root / "plugins" / "cairn" / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        return None          # not the plugin's own source repo — the scope guard
    try:
        return str(json.loads(manifest.read_text(encoding="utf-8")).get("version") or "") or None
    except Exception:
        return None


def _installed_version() -> str | None:
    path = _config_dir() / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for key, installs in (data.get("plugins") or {}).items():
        if key.split("@", 1)[0] != "cairn":
            continue
        for install in installs or []:
            version = install.get("version")
            if version:
                return str(version)
    return None


def rules_state() -> tuple[str, str | None]:
    """What `~/.claude/CLAUDE.md` says about itself.

    Three states, never two — "no marker" must not be indistinguishable from "marker matches".
    That conflation is the defect behind B30, B35 and B37, and this module is not going to add a
    fourth instance of it.

      ("ok", "1.31.0")   a managed block, carrying that version
      ("no-marker", None)  the file exists but has never been installed into
      ("missing", None)    no file at all, or it could not be read
    """
    path = _config_dir() / "CLAUDE.md"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ("missing", None)
    match = _MARKER_RE.search(text)
    return ("ok", match.group(1)) if match else ("no-marker", None)


def _repo_drift(root: Path, installed_version: str | None) -> str | None:
    """Installed plugin vs what the repo has shipped. This plugin's own repo only — see _repo_version."""
    repo_version = _repo_version(root)
    if repo_version is None or installed_version is None:
        return None
    if installed_version == repo_version:
        return None
    return (f"⚠ this machine's installed cairn plugin is v{installed_version}, but this repo's "
            f"plugin.json is v{repo_version} — run `claude plugin update cairn@superbole`, "
            f'then restart. See docs/guide.md, "Shipping a change".')


def _rules_drift(installed_version: str | None) -> str | None:
    """Installed plugin vs the rules block actually loaded into every session. EVERY project.

    Silent when there is nothing to compare against: with no readable `installed_plugins.json`
    a mismatch cannot be told from a missing input, and inventing a warning out of that is how a
    check earns its way into being ignored.
    """
    if installed_version is None:
        return None
    state, rules_version = rules_state()
    if state == "ok" and rules_version == installed_version:
        return None
    where = _config_dir() / "CLAUDE.md"
    if state == "missing":
        return (f"⚠ the cairn plugin is v{installed_version} but {where} could not be read — "
                f"the always-loaded rules are NOT in front of this session. `install_rules` writes "
                f"that file at session start and never fails a session, so this is silent "
                f"otherwise.")
    if state == "no-marker":
        return (f"⚠ the cairn plugin is v{installed_version} but {where} has no "
                f"`reentry:begin` block — the rules have never installed on this machine. Not the "
                f"same as up to date.")
    return (f"⚠ the cairn plugin is v{installed_version} but {where}'s rules block is "
            f"v{rules_version} — this session is running NEW code against OLD rules. Restart to "
            f"let `install_rules` resync; if it survives a restart, the install is failing "
            f"silently.")


def check(root: Path) -> str | None:
    """Lines for the agent about version drift on this machine, or None when all three agree.

    Two independent findings, reported together because they share one remedy path and they should
    never have to assemble them themselves. Order is deliberate: the rules mismatch comes second
    because it is the one they can act on from any project.
    """
    installed_version = _installed_version()
    lines = [line for line in (_repo_drift(root, installed_version),
                               _rules_drift(installed_version)) if line]
    return SEPARATOR.join(lines) if lines else None
