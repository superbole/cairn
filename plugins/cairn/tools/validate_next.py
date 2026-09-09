#!/usr/bin/env python3
"""Assert the field SHAPE `NEXT.md`'s own rules require -- and name every item that breaks it.

    python plugins/cairn/tools/validate_next.py                 # this project's NEXT.md
    python plugins/cairn/tools/validate_next.py ~/Projects/bfm   # someone else's

THE INCIDENT THIS EXISTS FOR (B36, filed 2026-08-31)
-----------------------------------------------------
A previous sweep rewrote every `HITL/Manual` in the portfolio to `HITL/Auto` -- the correct fix
for a known-bad VALUE. It worked by searching for that literal string, so it caught every item
that had the wrong mode and could not catch the item that had none: a watch with no
attendance/mode field at all matches no wrong-value search, ever, because there is no value to
find. Two watches in another repo had exactly that -- both predate the mode-field rule -- and the
sweep reported a clean portfolio while they sat there unseen. Nothing since has checked the other
fifteen repos either.

The field exists to answer one question -- *can they start this and walk away, and what must they set
first* -- so a MISSING field is not cosmetic, it is that question silently unanswered, and it is
strictly worse than a wrong value: a wrong value is at least visible as text.

WHY A SEPARATE TOOL FROM `check_next()` IN `session_orientation.py`
--------------------------------------------------------------------
`hooks/session_orientation.py` already has a `check_next()`, and it is not this tool. It runs
after `/cairn:wrap` rewrites the file, on a hair trigger (never break a wrap over a lint), and
it deliberately prints COUNTS only -- "3 queue items are missing AFK|HITL/mode" -- never a
per-item list, because that function's other job is SessionStart, and a per-item dump would
out-shout the queue on every single session in the projects that have the most items to fix.

This tool has the opposite job: an on-demand, human-initiated read that is allowed to be as
verbose as the findings warrant, run across a project whenever anyone wants to know exactly WHICH
items are broken and how. So it reuses `check_next()`'s own building blocks --
`_split_next`/`_watch_trigger`/`_entry_age` -- rather than re-deriving a second, inevitably
slightly-different parse of the same file (see `hooks/backlog_file.py`'s own docstring on the
same lesson, watches parsed tolerantly because two incompatible shapes were already in the wild).
Model/effort/attendance detection reuses `hooks/backlog_file.py`'s field regexes
(`_ATTEND_RE`, `_MODEL_RE`, `_EFFORT_RE`, `_ADDED_RE`) for the same reason: they were written once,
against real hand-edited files, and a third copy is a third place for the two to drift apart.

WHAT COUNTS AS A CONTRADICTION
-------------------------------
`AFK/Plan` and `HITL/Bypass` both assert something false about the item wearing them: `AFK` means
they are not there to answer a permission prompt, but `Plan` mode cannot finish without one; `HITL`
means the item WILL stop for them, but `Bypass` mode never asks. Neither combination can be run as
written, so both are flagged wherever they appear -- a queue item, a watch, anywhere in the file.

REPORT, NEVER REWRITE. This tool answers "what needs a human to fix", the same way `check_repos.py`
answers "what needs a human to commit" -- it never edits `NEXT.md` itself. A missing field is a
judgement call (what IS the right model/effort/mode for this item?) that only the person who
wrote the item can make correctly; guessing one in would be exactly the "confident wrong answer
written into a doc" this plugin's own rules warn against elsewhere.

SCOPE: ONE `NEXT.md` AT A TIME. A cross-project sweep needs enumeration -- walking every sibling
checkout, deciding which ones opt in -- and that is a separate, unbuilt item (this repo's own
`NEXT.md`, B36, is explicit that the cheap single-repo version should ship first). Nothing here
discovers other projects; the caller names the one it wants, or gets the current one.

USAGE
    python validate_next.py                  # NEXT.md under the current/session project
    python validate_next.py PATH              # PATH is a project dir, or a NEXT.md file directly
    python validate_next.py --json PATH

EXIT
    0  NEXT.md parses clean (or there is no NEXT.md here -- nothing to check)
    1  at least one queue item or watch fails the field-shape rules
    2  bad command line (argparse's own contract -- see tools/test_sync_flags.py for why this
       matters: an unrecognised flag must stop here, never fall through to "check the default")
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hooks"))

try:
    import session_orientation as so
    import backlog_file as bf
    from reentry_state import project_root
except Exception as exc:                                    # pragma: no cover
    print(f"NEXT.md validator skipped: cannot import the plugin's own modules ({exc})")
    sys.exit(0)

# The two contradictions named in the brief. Both assert something false about the item: `AFK`
# means nobody is there to clear a permission prompt, but `Plan` mode cannot finish without one;
# `HITL` means the item WILL stop for them, but `Bypass` mode never stops for anyone. Matched
# case-insensitively and independent of the backtick/space styling `_ATTEND_RE` already tolerates
# -- a contradiction typed `afk / plan` is exactly as real as `AFK/Plan`.
_CONTRADICTION_RE = re.compile(r"\b(AFK)\s*/\s*(Plan)\b|\b(HITL)\s*/\s*(Bypass)\b", re.IGNORECASE)

# `backlog_file._MODEL_RE` and `._EFFORT_RE` are BACKLOG.md-shaped, and `NEXT.md`'s two lists do
# not both look like BACKLOG.md. Verified empirically (2026-09-05) by running this tool against
# this very repo's own `NEXT.md` with the imported regexes used unmodified: every real, correctly
# written queue item was reported as "missing model" and "missing effort", because
#   - a WATCH writes `` `Opus 5` `` (backticked) and `` effort `high` `` (keyworded) -- exactly
#     what `backlog_file` expects, since that convention was copied from BACKLOG.md's own; but
#   - a QUEUE item writes bare `Opus 5 · high · HITL/Auto` -- no backticks, no `effort` keyword --
#     per `rules/CLAUDE.md`'s own documented Queue syntax and every real Queue in the portfolio.
# A false "missing" on an item that is actually fine is worse than the miss this tool exists to
# catch (B36's own incident was a FALSE NEGATIVE, not a false positive) -- it teaches whoever
# reads the report to stop trusting it. So all three of these are RELAXED, not re-derived: each
# pattern is built from the imported regex's own `.pattern` string, adjusted where the real
# portfolio proved the original assumption wrong, rather than re-typing the model list or the
# effort/attendance vocabulary a third time.
_MODEL_RE = re.compile(bf._MODEL_RE.pattern.replace("`", "`?"), re.IGNORECASE)
# The lookahead anchors "high"/"medium"/"low" to being a FIELD (immediately followed by the `·`
# separator or end of line) rather than any occurrence of the word in prose -- a queue item's
# title text could otherwise contain "a high priority" and be counted as having an effort field.
_EFFORT_RE = re.compile(r"(?:effort\s+)?`?\b(high|medium|low)\b`?(?=\s*·|\s*$)", re.IGNORECASE)
# `backlog_file._ATTEND_RE`'s tail assertion requires the mode to be followed by `·` or end of
# line -- true of every ordinary Queue/Watch line, but NOT of `workspace`'s own NEXT.md, which is
# a documented exception (its header comment names it "portfolio meta" with its own queue-line
# format): `` `HITL/Auto` — brief: ... `` puts an em-dash straight after the mode, no `·`. Found
# empirically 2026-09-05 -- unmodified, this regex reported "missing attendance/mode" on all 5 of
# that file's queue items, every one of which actually carries `HITL/Auto` in plain sight. Adding
# `—` as a third accepted follower fixes it without loosening the check in the direction that
# would matter (a `·` or end-of-line is still required to end the OTHER two known shapes, so this
# cannot start matching AFK/HITL text that isn't really a field).
_ATTEND_RE = re.compile(bf._ATTEND_RE.pattern.replace(r"(?:\s*·|\s*$)", r"(?:\s*·|\s*—|\s*$)"))


def _title_line(item_lines: list[str]) -> str:
    """The line carrying the fields, for a queue item that may have continuation lines."""
    return item_lines[0] if item_lines else ""


def _queue_entries(queue_lines: list[str]) -> list[list[str]]:
    """Group `_split_next`'s flat queue lines into one entry per numbered item.

    `_split_next` hands back the whole `## Queue` section as a flat list -- correct for its own
    job (truncating at MAX_NEXT_LINES) but not for this one, where a brief link or a note on a
    continuation line still belongs to the item above it. Grouped the same way watches and
    decisions already are in `_split_next` itself, by `_QUEUE_ITEM_RE`'s own anchor.
    """
    entries: list[list[str]] = []
    for ln in queue_lines:
        if so._QUEUE_ITEM_RE.match(ln):
            entries.append([ln])
        elif entries:
            entries[-1].append(ln)
    return entries


def _queue_number(entry: list[str]) -> str:
    m = re.match(r"^\s*\*{0,2}(\d+)\.", entry[0])
    return m.group(1) if m else "?"


def _queue_title(entry: list[str]) -> str:
    """A short label for a queue item, for the report -- title text without the field tail."""
    ln = entry[0].strip()
    m = re.search(r"\*\*(.+?)\*\*", ln)
    return m.group(1) if m else ln[:60]


def _has(regex: re.Pattern, text: str) -> bool:
    return regex.search(text) is not None


def _attendance_state(text: str) -> str:
    """'ok' | 'missing' | 'unrecognised-mode'.

    `backlog_file._ATTEND_RE` matches a BARE `AFK`/`HITL` too (a pulled backlog issue can carry
    the attendance label with no mode yet) -- useful here to tell "no field at all" apart from
    "the field is there but its mode isn't one of the five real ones", which is a different, and
    differently-worded, problem for the person fixing it.
    """
    m = _ATTEND_RE.search(text)
    if not m:
        return "missing"
    mode = (m.group(2) or "").strip()
    if not mode:
        return "missing"           # attendance present, but no mode at all -- same defect
    if mode.strip().lower() not in {"auto", "manual", "accept edits", "plan", "bypass"}:
        return "unrecognised-mode"
    return "ok"


def _field_positions(text: str) -> dict[str, int]:
    """Start index of each named field's match in `text`, for the 'check after LAST' rule."""
    pos: dict[str, int] = {}
    for name, regex in (("model", _MODEL_RE), ("effort", _EFFORT_RE),
                        ("attendance/mode", _ATTEND_RE), ("added", bf._ADDED_RE),
                        ("check after", so._CHECK_AFTER_RE)):
        m = regex.search(text)
        if m:
            pos[name] = m.start()
    return pos


def check_queue(entries: list[list[str]]) -> list[str]:
    problems: list[str] = []
    for entry in entries:
        n = _queue_number(entry)
        title = _queue_title(entry)
        label = f"Queue item {n} ({title})"
        line = _title_line(entry)

        if not _has(_MODEL_RE, line):
            problems.append(f"{label}: missing model.")
        if not _has(_EFFORT_RE, line):
            problems.append(f"{label}: missing effort.")
        state = _attendance_state(line)
        if state == "missing":
            problems.append(f"{label}: missing attendance/mode (AFK|HITL/<mode>).")
        elif state == "unrecognised-mode":
            problems.append(f"{label}: attendance/mode present but the mode is not one of "
                            "Auto/Manual/Accept Edits/Plan/Bypass.")
        if _CONTRADICTION_RE.search(line):
            bad = _CONTRADICTION_RE.search(line).group(0)
            problems.append(f"{label}: contradiction `{bad}` -- AFK/Plan and HITL/Bypass can "
                            "never appear; the mode and the attendance disagree about whether "
                            "anyone is there to clear a prompt.")
    return problems


def check_duplicate_ids(watches: list[list[str]], decisions: list[list[str]]) -> list[str]:
    """Assert every `Wn` and `Dn` in NEXT.md is unique -- B79's converse-of-the-id-list check,
    for this file's own ids (the sibling half, in `backlog_file.next_id()`, does the same for
    BACKLOG.md and is owned by a different lane). Before this, grepping
    `duplicat|Counter|seen` over this module returned nothing: two entries claiming the same
    number parsed cleanly and were never compared to each other.

    Report only, same as everywhere else in this file. Two rejections from BACKLOG.md's B79
    apply unchanged here: a duplicate is sometimes the CORRECT transient state mid-merge (two
    sessions on two machines each minting the next free number before either has seen the
    other's push), so this never blocks; and choosing which entry keeps the id needs
    information this tool doesn't have (which one is actually older), so it names both and
    lets a human decide rather than guessing.
    """
    problems: list[str] = []

    by_id: dict[str, list[str]] = {}
    for entry in watches:
        m = so._WATCH_TITLE_RE.match(entry[0].strip())
        if m:
            by_id.setdefault(m.group(1), []).append(so._watch_title(entry))
    for wid in sorted(by_id):
        titles = by_id[wid]
        if len(titles) > 1:
            problems.append(f"Watch id {wid} used {len(titles)} times, fighting over it: "
                            + "; ".join(titles))

    by_id = {}
    for entry in decisions:
        m = so._DECISION_TITLE_RE.match(entry[0].strip())
        if m:
            by_id.setdefault(m.group(1), []).append(so._decision_title(entry))
    for did in sorted(by_id):
        titles = by_id[did]
        if len(titles) > 1:
            problems.append(f"Decision id {did} used {len(titles)} times, fighting over it: "
                            + "; ".join(titles))
    return problems


def check_watches(watches: list[list[str]]) -> list[str]:
    problems: list[str] = []
    for entry in watches:
        title = so._watch_title(entry)
        label = f"Watch {title}"
        line = _title_line(entry)          # same convention as queue items: fields live here
        full = "\n".join(entry)            # for the contradiction scan only, see below

        if not _has(_MODEL_RE, line):
            problems.append(f"{label}: missing model.")
        if not _has(_EFFORT_RE, line):
            problems.append(f"{label}: missing effort.")
        state = _attendance_state(line)
        if state == "missing":
            problems.append(f"{label}: missing attendance/mode (AFK|HITL/<mode>).")
        elif state == "unrecognised-mode":
            problems.append(f"{label}: attendance/mode present but the mode is not one of "
                            "Auto/Manual/Accept Edits/Plan/Bypass.")
        if so._entry_age(entry) is None:
            problems.append(f"{label}: missing `added` (or it is on a continuation line -- "
                            "the live parser only reads the title line, so it would report "
                            "the same 'missing' the way this tool just did).")
        kind, _trigger = so._watch_trigger(entry)
        if kind == "none":
            problems.append(f"{label}: no parseable `check after`.")
        else:
            pos = _field_positions(line)
            if "check after" in pos and pos:
                last_field = max(pos, key=pos.get)
                if last_field != "check after":
                    problems.append(f"{label}: `check after` is not the LAST field on the "
                                    f"line -- `{last_field}` comes after it.")
        # Contradiction scan spans the whole entry (title + continuation): unlike the fields
        # above, a wrong VALUE is visible wherever it sits, so there is no reason to miss one
        # typed on a wrapped line.
        m = _CONTRADICTION_RE.search(full)
        if m:
            problems.append(f"{label}: contradiction `{m.group(0)}` -- AFK/Plan and "
                            "HITL/Bypass can never appear; the mode and the attendance "
                            "disagree about whether anyone is there to clear a prompt.")
    return problems


def _split_next_full(root: Path):
    """`session_orientation._split_next`, with its SessionStart relay cap lifted.

    `_split_next`'s `MAX_NEXT_LINES` truncation is correct for its real job -- one screen at
    session start, never more -- and exactly wrong for this one: a validator that silently stops
    checking after line 24 misses every later item, which is a worse failure than the one this
    tool exists to catch. Found empirically, 2026-09-05: this repo's own `NEXT.md` has a 5-item
    queue whose text runs well past 24 lines, and calling `_split_next` unmodified silently
    validated only the first 2 items -- items 3-5 never appeared in the report at all, with
    nothing saying so. Patching the module's own constant for the duration of one call reuses the
    exact same split logic (no second parser) while asking it a different question than
    SessionStart asks.
    """
    saved = so.MAX_NEXT_LINES
    so.MAX_NEXT_LINES = 10 ** 6
    try:
        return so._split_next(root)
    finally:
        so.MAX_NEXT_LINES = saved


def validate(root: Path) -> tuple[bool, list[str], dict]:
    """(ok, report lines, raw counts-by-kind). Never raises -- see `main()`'s own guard too."""
    next_path = root / "NEXT.md"
    if not next_path.is_file():
        return True, [f"No NEXT.md at {next_path} -- nothing to check."], {}

    queue_lines, decisions, watches, _footer = _split_next_full(root)
    entries = _queue_entries(queue_lines)
    problems = (check_queue(entries) + check_watches(watches)
                + check_duplicate_ids(watches, decisions))

    counts = {"queue_items": len(entries), "watches": len(watches),
             "decisions": len(decisions), "problems": len(problems)}
    if not problems:
        return True, [f"NEXT.md validate: OK -- {len(entries)} queue item(s), "
                      f"{len(watches)} watch(es), {len(decisions)} decision(s), all carry "
                      "model, effort, attendance/mode (and, for watches, `added` + "
                      "`check after` last), and no Wn/Dn used twice."], counts

    lines = [f"NEXT.md validate: {len(problems)} issue(s) across "
            f"{len(entries)} queue item(s), {len(watches)} watch(es) and "
            f"{len(decisions)} decision(s):"]
    lines += [f"  - {p}" for p in problems]
    return False, lines, counts


def _resolve_root(arg: str | None) -> Path:
    if not arg:
        return project_root()
    p = Path(arg).expanduser()
    # Accept a NEXT.md path directly, as well as a project directory -- both are the obvious
    # thing to type and there is no ambiguity to preserve by rejecting one of them.
    return p.parent if p.name.lower() == "next.md" else p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="validate_next.py", description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=None,
                    help="project directory (or a NEXT.md file directly); "
                         "defaults to the current project")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    root = _resolve_root(args.path)
    ok, lines, counts = validate(root)
    if args.as_json:
        print(json.dumps({"ok": ok, "root": str(root), **counts,
                          "report": lines}, indent=2))
    else:
        print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise            # argparse's own --help/bad-flag exits -- let them through untouched
    except Exception as exc:                                # pragma: no cover
        print(f"NEXT.md validator could not run ({exc}) -- check the file by hand")
        sys.exit(0)                                         # a report tool must never break
