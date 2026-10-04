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

THE THIRD CHECK (B97) — installed vs THE MARKETPLACE CLONE
---------------------------------------------------------
Neither check above ever looks at what has been PUBLISHED. Outside this plugin's own repo the only
comparison is installed-vs-rules, and both of those move together when an update lands, so a
machine whose auto-update is off stays on an old release forever and every check reads clean.

The published version is already on disk, with no network: Claude Code keeps a git clone of each
marketplace under `<config>/plugins/marketplaces/<name>/`. Two findings come from it:

  - the clone's `plugin.json` is NEWER than the installed version: a release reached this machine
    and was never installed;
  - the clone itself has not been fetched for `STALE_FETCH_DAYS`: this machine cannot see a new
    release at all, so the first finding cannot fire. Last fetch = the newest mtime of
    `.git/FETCH_HEAD` and `.git/logs/HEAD` (a fresh clone has no FETCH_HEAD yet).

Like the rules check, this is NOT scope-guarded: it needs no repo. It is silent whenever an input is
missing or a version does not parse -- no clone, no `.git`, no readable manifest -- because a
warning built from a missing input is the kind that teaches people to ignore the block. An installed
version NEWER than the clone is silent too: that is a stale clone, which the fetch check reports.
"""
import json
import os
import re
import time
from pathlib import Path

# `<!-- reentry:begin v1.62.0 -->` (v1.61.0 and earlier: `… v1.31.0 — managed by …`), written by
# install_rules._block(). A search, not a parse: this only reads the version, it never edits.
_MARKER_RE = re.compile(r"reentry:begin\s+v([0-9][0-9.]*)")

SEPARATOR = "\n\n"      # blank line between findings; the call site adds one before

# B97: how old the marketplace clone's last fetch may get before it is reported. Auto-update
# fetches at session start, so a machine in ordinary use is never near this; a week leaves room for
# a machine that sits unused over a holiday without the first session back crying wolf.
STALE_FETCH_DAYS = 7

# THE ONE VERSION PARSER (B63). `install_rules` imports these to decide whether a write would roll
# the rules block BACK, and `tools/check_install.py` uses them to say which way a mismatch points.
# Strict on purpose: dot-separated integers only. Anything else (`1.2.0-rc1`, `?`, an empty
# string) parses to None, and None means "cannot tell the direction" -- which every caller must
# treat as NO EVIDENCE of a downgrade. A lenient parser that read `1.2.0-rc1` as `1.2.0` would be
# one more place where a guess decides whether rules get written.
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+)*")


def parse_version(value) -> tuple[int, ...] | None:
    """`"1.62.0"` -> `(1, 62)`; None when it is not dot-separated integers.

    Trailing zeros are dropped, so `1.62` and `1.62.0` compare equal.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not _VERSION_RE.fullmatch(text):
        return None
    parts = [int(p) for p in text.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def compare_versions(a, b) -> int | None:
    """-1 / 0 / 1 as `a` is older / equal / newer than `b`; None when EITHER side does not parse."""
    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        return None
    return (pa > pb) - (pa < pb)


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


def _installed_entry() -> tuple[str | None, str | None]:
    """(marketplace name, version) of the installed cairn plugin, from its `cairn@<marketplace>`
    key. Either side None when it cannot be read."""
    path = _config_dir() / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    for key, installs in (data.get("plugins") or {}).items():
        name, _, marketplace = key.partition("@")
        if name != "cairn":
            continue
        for install in installs or []:
            version = install.get("version")
            if version:
                return (marketplace or None), str(version)
    return None, None


def _installed_version() -> str | None:
    return _installed_entry()[1]


def _clone_dir(marketplace: str | None) -> Path | None:
    if not marketplace or "/" in marketplace or "\\" in marketplace or marketplace in (".", ".."):
        return None
    clone = _config_dir() / "plugins" / "marketplaces" / marketplace
    return clone if clone.is_dir() else None


def _clone_version(clone: Path) -> str | None:
    """The cairn version the marketplace clone publishes. Its `marketplace.json` names where the
    plugin lives (`./plugins/cairn` in this repo); `plugins/cairn` when that cannot be read."""
    rel = "plugins/cairn"
    try:
        data = json.loads((clone / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        for entry in data.get("plugins") or []:
            source = entry.get("source") if isinstance(entry, dict) else None
            if entry.get("name") == "cairn" and isinstance(source, str):
                rel = source
                break
    except Exception:
        pass
    manifest = (clone / rel / ".claude-plugin" / "plugin.json").resolve()
    try:
        manifest.relative_to(clone.resolve())      # a source that climbs out of the clone is ignored
        return str(json.loads(manifest.read_text(encoding="utf-8")).get("version") or "") or None
    except Exception:
        return None


def _last_fetch(clone: Path) -> float | None:
    """Newest mtime of `.git/FETCH_HEAD` and `.git/logs/HEAD`; None when neither exists."""
    times = []
    for rel in ("FETCH_HEAD", "logs/HEAD"):
        try:
            times.append((clone / ".git" / rel).stat().st_mtime)
        except OSError:
            pass
    return max(times) if times else None


def _marketplace_drift(marketplace: str | None, installed_version: str | None,
                       now: float | None = None) -> list[str]:
    """Installed plugin vs the marketplace clone on disk (B97). EVERY project; silent on any
    missing input."""
    if installed_version is None:
        return []
    clone = _clone_dir(marketplace)
    if clone is None:
        return []
    found = []
    published = _clone_version(clone)
    if published and compare_versions(installed_version, published) == -1:
        found.append(f"⚠ the installed cairn plugin is v{installed_version}, but the {marketplace} "
                     f"marketplace clone on this machine already has v{published} — a release "
                     f"arrived and was never installed. Run `claude plugin update "
                     f"cairn@{marketplace}`, then restart. If this comes back after a restart, "
                     f"auto-update is off or failing for that marketplace.")
    fetched = _last_fetch(clone)
    if fetched is not None:
        days = int(((time.time() if now is None else now) - fetched) // 86400)
        if days >= STALE_FETCH_DAYS:
            found.append(f"⚠ the {marketplace} marketplace clone on this machine was last fetched "
                         f"{days} days ago, so a newer cairn release would not show up here. "
                         f"Run `claude plugin marketplace update {marketplace}`; if it goes stale "
                         f"again, auto-update is off for that marketplace.")
    return found


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
    if compare_versions(rules_version, installed_version) == 1:
        # B66: the rules block is NEWER than the installed plugin. Since v1.63.0 (D33) `install_rules`
        # KEEPS a newer block rather than roll it back, so the generic wording below -- "restart to
        # resync" -- is backwards in this direction: the PLUGIN is the old side, and restarting will
        # not touch it. Worded like `check_install.py`'s matching STALE branch.
        return (f"⚠ {where}'s rules block is v{rules_version}, NEWER than the installed cairn "
                f"plugin v{installed_version}. `install_rules` keeps a newer block rather than roll "
                f"it back (B63), so a restart will NOT resync this — the plugin is the old side. "
                f"Update it: `claude plugin marketplace update superbole`, then `claude plugin "
                f"update cairn@superbole`, restart.")
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
    marketplace, installed_version = _installed_entry()
    lines = [line for line in (_repo_drift(root, installed_version),
                               _rules_drift(installed_version)) if line]
    lines += _marketplace_drift(marketplace, installed_version)
    return SEPARATOR.join(lines) if lines else None
