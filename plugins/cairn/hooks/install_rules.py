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
  - Back up before EVERY modification, one file per outgoing state, never overwritten (B25).
  - Never roll a NEWER block back (B63). An older plugin copy that still runs refuses, writes
    nothing, and says so -- the version marker, not a body diff, decides which block is newer.
  - Find the block STRUCTURALLY — whole lines, a version, one block — and refuse when it is
    ambiguous. A prefix search once let text above the block be swallowed by it (B25).
  - Say what it did, in ONE line. A mechanism that leaves no evidence it ran gets reported as
    broken and cannot be defended without re-reading the code (2026-08-15).
"""
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

try:                                    # the PROFILE layer — see ensure_profile_file.py's docstring
    import ensure_profile_file
except Exception:                       # pragma: no cover - absent copy must never break an install
    ensure_profile_file = None          # type: ignore[assignment]

try:                                    # the ONE version parser (B63) -- shared with check_install
    from version_drift import compare_versions
except Exception:                       # pragma: no cover - absent copy must never break an install
    def compare_versions(a, b):         # type: ignore[misc]
        return None                     # cannot tell the direction == no evidence of a downgrade

BEGIN = "<!-- reentry:begin"
END = "<!-- reentry:end -->"

# The managed block's first line, matched WHOLE (`fullmatch`, one line) — never a prefix search.
# B25: `text.find(BEGIN)` matched the first `<!-- reentry:begin` ANYWHERE, so a user's note above
# the block that quoted the marker became the block's start, and everything from there down to the
# real END — their text included — was replaced. Three conditions, all required: the line starts
# with the marker, carries a version, and the comment closes on that same line. Words between the
# version and the `-->` are allowed (`… v1.31.0 — managed by the reentry plugin. -->`).
#
# The second alternative is the LEGACY header (v1.61.0 and earlier), whose comment ran on for two
# more lines. It is accepted by its exact tail so an installed block still updates; `_block()` no
# longer writes it. Both plugin names, because the rename (D18, v1.51.0) changed the wording.
# B28 will rename the marker itself: keep whatever replaces this a whole-line match.
_BEGIN_LINE = re.compile(
    r"<!-- reentry:begin v(?P<version>[0-9][0-9A-Za-z.+-]*)"
    r"(?:(?: .*?)? -->| — managed by the (?:cairn|reentry) plugin\.)"
)


class MalformedBlock(ValueError):
    """The file has something that looks like a managed block but is not one we can edit safely."""

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


def _backup(target: Path, outgoing: str, content: str) -> Path:
    """`CLAUDE.md.bak-reentry-install-v<outgoing>-<digest>` beside the file — the state being replaced.

    One file per distinct outgoing state (B25). The old single rolling copy was overwritten on
    every modifying run, so two updates in a row — which marketplace auto-update produces with
    nobody acting — destroyed the pre-first-update state, exactly the copy a silent loss needs.
    The digest separates two different files carrying the same version (a rules edit without a
    bump); identical content gets the same name, so a re-run churns nothing. `noblock` names the
    state before the block was first prepended.

    NEVER PRUNED — decided, see `docs/decisions.md` (B25). The fixed-name
    `CLAUDE.md.bak-reentry-install` written up to v1.61.0 is left where it is and never written
    again, and the hand-made `CLAUDE.md.bak-reentry` that predates both is left alone too.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    label = f"v{outgoing}" if outgoing else "noblock"
    return target.with_name(f"{target.name}.bak-reentry-install-{label}-{digest}")


def block_digest(block: str) -> str:
    """A short digest of the managed block's own text — for `tools/check_install.py` (B26).

    Of the BLOCK, never the whole file: two machines running the same rules must match even though
    each has its own notes outside the markers. That is why this is not `wrap_receipt._digest()`,
    which hashes a whole file by path. Newlines are normalised by `_read()` before this is called.
    """
    return hashlib.sha256(block.encode("utf-8")).hexdigest()[:12]


def _back_up(target: Path, outgoing: str, content: str) -> None:
    """Copy `target` to its backup name unless that exact state is already saved."""
    dest = _backup(target, outgoing, content)
    if not dest.exists():
        shutil.copy2(target, dest)


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
        f"{BEGIN} v{version} -->\n"
        f"<!-- Managed by the cairn plugin. EDIT `rules/CLAUDE.md` IN THE PLUGIN SOURCE, NOT HERE —\n"
        f"     this block is regenerated. Anything you write OUTSIDE these markers is yours and is\n"
        f"     never touched. -->\n"
        f"{text}\n"
        f"{END}\n"
    )


def _find_block(text: str) -> tuple[int, int, str] | None:
    """Return (start, end_exclusive, installed_version) for the managed block, or None if none.

    None means there is NO managed block and nothing that looks like one, so prepending is safe.
    Raises `MalformedBlock` when prepending or replacing would be a guess:
      - a line starts with the marker but is not a valid header, and no valid header exists
        (prepending would put a second block above a broken one);
      - more than one valid header (which one is ours cannot be told);
      - a valid header with no `END` line after it.

    Mentions of the marker anywhere else — mid-line, indented, in the user's notes above or below —
    are the user's text and are never part of the block. Trailing whitespace on the marker lines is
    tolerated; an editor that strips or adds it must not break the match.
    """
    begins: list[tuple[int, str, int]] = []         # (offset, version, line number)
    lookalikes: list[int] = []
    ends: list[tuple[int, int]] = []                # (offset, offset past the line)
    offset = 0
    for lineno, line in enumerate(text.splitlines(keepends=True), 1):
        bare = line.rstrip()
        match = _BEGIN_LINE.fullmatch(bare)
        if match:
            begins.append((offset, match["version"], lineno))
        elif bare.startswith(BEGIN):
            lookalikes.append(lineno)
        elif bare == END:
            ends.append((offset, offset + len(line)))
        offset += len(line)

    if not begins:
        if lookalikes:
            raise MalformedBlock(
                f"line {lookalikes[0]} starts with `{BEGIN}` but is not a valid header (it needs a "
                f"version and a closing `-->` on the same line)")
        return None
    if len(begins) > 1:
        lines = ", ".join(str(b[2]) for b in begins)
        raise MalformedBlock(f"it has {len(begins)} managed-block headers (lines {lines}), so which "
                             f"one is the real block cannot be told")
    start, version, lineno = begins[0]
    for end_start, end in ends:
        if end_start > start:
            return start, end, version
    raise MalformedBlock(f"the header on line {lineno} has no `{END}` line after it")


def _refusal(target: Path, reason: str, consequence: str) -> str:
    """Every "wrote nothing on purpose" line, in ONE voice: what was refused, why, what follows.

    Shared by the MalformedBlock refusal (B25) and the downgrade refusal (B63) so the agent reads
    the same shape for both, and so B26's change summary has one voice to match.
    """
    return (f"[to the agent] Did NOT update the cairn rules block in {target}: {reason}. The file "
            f"was left untouched; {consequence}")


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

    try:
        found = _find_block(existing)
    except MalformedBlock as exc:
        # Refuse rather than guess. Every other outcome here is silent or reports a success; this
        # one repeats each session until a human fixes the file, which is the point — nothing
        # else will, and a guess is how user text was lost (B25).
        return _refusal(target, str(exc),
                        f"the rules in it may be stale. Tell the user; the block is one "
                        f"`{BEGIN} vX.Y.Z -->` line down to one `{END}` line, and they should fix "
                        f"it by hand."), False

    if found is None:
        # A real file with no managed block: prepend, so the system rules land before whatever
        # was already there, and keep every byte of the user's own text below.
        try:
            _back_up(target, "", existing)
            _write(target, block + "\n" + existing)
        except Exception:
            return None, False
        return (f"[to the agent] Added the cairn rules block to {target} (v{version}); the "
                f"file's previous contents were kept below it and backed up. Not in your "
                f"context until the next session."), False

    start, end, installed = found
    if installed == version and existing[start:end] == block:
        return None, True               # already current — the common case, silent by design

    # B63: never roll a NEWER block back. Seen 2026-09-25 on a work laptop: a v1.60.0 installer and a
    # v1.62.0 one both ran the same day and the orientation printed "Updated … v1.62.0 → v1.60.0",
    # a rollback reported as an update. Harmless while every version wrote the same body; the first
    # release that changes the body would have had an older process silently put the old rules
    # back, every session. Only when BOTH versions parse: an unreadable version is no evidence of a
    # downgrade, so it falls through to the write below. `"0"` is `_plugin_version()`'s own failure
    # sentinel, not a version, so it is no evidence either. Nothing is backed up — nothing changes.
    # in_context is True: the file still holds the block this session has already read.
    if version != "0" and compare_versions(installed, version) == 1:
        return _refusal(target, f"it is v{installed}, NEWER than this plugin's v{version}, so "
                                f"writing would roll it back",
                        "the newer block was kept. This session is running an OLDER copy of the "
                        "plugin; tell the user to run `claude plugin update cairn@superbole`, then "
                        "restart."), True

    try:
        _back_up(target, installed, existing)
        _write(target, existing[:start] + block + existing[end:])
    except Exception:
        return None, False
    # B26: say WHAT moved, not only `vX → vY`. Computed only here, after the write succeeded —
    # never on the silent path above, and never on a refusal. A summary that fails must not cost
    # the report, so it degrades to the pre-B26 line rather than to silence.
    moved = f"v{installed or '?'} → v{version}" if installed != version else \
        f"v{version} → v{version} (same version, different content)"
    try:
        summary = _change_summary(existing[start:end], block)
        diff = f'git diff --no-index -- "{_backup(target, installed, existing)}" "{target}"'
        detail = f" {summary}. Full diff: `{diff}`."
    except Exception:
        detail = ""
    return (f"[to the agent] Updated the cairn rules block in {target}: {moved}.{detail} The "
            f"version in YOUR context is the old one until the next session."), False


# How many `#` headings the change line names before it says "+N more". Three keeps the line
# bounded when the block changes wholesale (a legacy block replaced by the full rules names every
# section) while still naming the one or two sections an ordinary release touches.
_SUMMARY_HEADINGS = 3
_HEADING_WIDTH = 40
_HEADING = re.compile(r"#{1,6}\s+(.*\S)")


def _change_summary(outgoing: str, incoming: str) -> str:
    """`rules text: +A −R ~C lines, in: X, Y, Z (+N more)` — a COUNT and a LOCATION, nothing more.

    Not a classifier (B26 said not to invent one): the headings are only WHERE lines moved, so a
    typo fix under "The re-entry system" and a new rule there read the same. That is why the line
    also carries the exact diff command — the count is a pointer, the diff is the evidence.

    The header line (line 1 of each block) is left out: it carries the version, which the change
    line already states, and counting it would make every pure version bump report "~1 line".
    """
    import difflib                      # here, not at module top: the silent path never pays it
    old = outgoing.splitlines()[1:]
    new = incoming.splitlines()[1:]

    def sections(lines: list[str]) -> list[str]:
        current, out = "(top of block)", []
        for line in lines:
            match = _HEADING.fullmatch(line.strip())
            if match:
                current = match.group(1)
            out.append(current)
        return out

    old_at, new_at = sections(old), sections(new)
    added = removed = changed = 0
    touched: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        both = min(i2 - i1, j2 - j1) if tag == "replace" else 0
        changed += both
        removed += (i2 - i1) - both
        added += (j2 - j1) - both
        for name in new_at[j1:j2] + old_at[i1:i2]:
            if name not in touched:
                touched.append(name)
    if not (added or removed or changed):
        return "Rules text unchanged — only the version marker moved"
    names = [n if len(n) <= _HEADING_WIDTH else n[:_HEADING_WIDTH - 1] + "…"
             for n in touched[:_SUMMARY_HEADINGS]]
    more = f" (+{len(touched) - _SUMMARY_HEADINGS} more)" if len(touched) > _SUMMARY_HEADINGS else ""
    return (f"Rules text: +{added} −{removed} ~{changed} lines, in: "
            f"{', '.join(names)}{more}")


if __name__ == "__main__":
    line, _current = install()
    if line:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(line)
