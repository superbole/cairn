#!/usr/bin/env python3
"""SessionStart hook (USER SCOPE) — tell the user where they are, in any project.

This is the global copy, wired in ~/.claude/settings.json, so it runs for EVERY
project on this machine. Installed 2026-08-08.

Origin: built for one repo on 2026-08-06 for a stated problem — a user who
cannot hold state between sessions, running several projects at once, and
unable to re-enter work between them. The fix is not a better-organised
document; it is removing the need to remember that a document exists. On
2026-08-08 they asked the right follow-up: "I'm worried I'm going to have lots of
different copies/versions of the file and/or system." They were already carrying a
second copy into a Cursor project. Hence this, at user scope.

CONTRACT — the two files are per-project, this mechanism is global:

  <project>/NEXT.md   three lists.
                      `## Queue`     — actionable NOW. Max 5. Numbered 1..5.
                      `## Decisions` — their to answer, not an agent's to pick up.
                                      D1, D2, ... uncapped. One line each: title,
                                      `answer: \\`X\\`` (`ask <authority>` | `here`), and
                                      `added \\`YYYY-MM-DD\\``. No "do Dn" — these
                                      have no brief to execute, only a call to make.
                                      Flagged past STALE_WATCH_DAYS same as a watch.
                      `## Watching`  — waiting on a trigger. W1, W2, ... uncapped.
                                      Each ends with `check after \\`X\\`` where X
                                      is a YYYY-MM-DD date or free-text event, and
                                      carries `added \\`YYYY-MM-DD\\`` before it.
                                      Dated watches stay HIDDEN until their day,
                                      then surface as DUE NOW. That is the point:
                                      "check this on Sunday" stops being their to
                                      carry. EVENT-gated ones can't do that, so
                                      they show their age instead and get flagged
                                      past STALE_WATCH_DAYS — otherwise a watch
                                      whose event never happens sits there
                                      forever with nothing saying so.
  <project>/INBOX.md  zero-effort capture; a bullet is the whole protocol.

OPTING IN is just creating NEXT.md. A project without one gets total silence,
which is why this is safe to run everywhere.

Design rules, learned the hard way and worth keeping:
  - NEVER fail the session. Any error prints nothing and exits 0. An orientation
    aid that can block a session start is worse than none.
  - Stay SHORT. This competes with the actual work; a wall of text at session
    start is the same failure as a 7,000-line backlog, just earlier.
  - Print nothing when there is nothing to say. Silence is a valid state.
  - DEFER to a project's own copy of this script (see _project_has_own_copy).
"""
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # for reentry_state, if present

try:                                     # Windows console-flash suppression; see the
    from reentry_state import NO_WINDOW  # NO_WINDOW comment in reentry_state.py.
except Exception:                        # Falling back to {} restores the OLD behaviour
    NO_WINDOW: dict = {}                 # (a visible flash), never a crash.

try:                                    # the BACKLOG layer — BACKLOG.md, a plain file (v1.18.0)
    import backlog_file
except Exception:                       # a missing sibling must never cost a session start
    backlog_file = None                 # type: ignore[assignment]

try:                                    # the SYNC layer — GitHub Issues, from cache only
    import issues_backlog
except Exception:
    issues_backlog = None               # type: ignore[assignment]

try:                                    # the WRAP RECEIPT layer — B87, the CAIRN token
    import wrap_receipt
except Exception:
    wrap_receipt = None                 # type: ignore[assignment]

try:                                    # the CROSS-REPO SWEEP layer — B26, cache only
    import repo_sweep
except Exception:
    repo_sweep = None                   # type: ignore[assignment]

try:                                    # the RULES layer — see install_rules.py's docstring
    import install_rules
except Exception:
    install_rules = None                # type: ignore[assignment]

try:                                    # the MISTAKES layer — see ensure_mistakes_file.py's docstring
    import ensure_mistakes_file
except Exception:
    ensure_mistakes_file = None          # type: ignore[assignment]

try:                                    # the CREDENTIALS layer — see ensure_credentials_file.py's docstring
    import ensure_credentials_file
except Exception:
    ensure_credentials_file = None      # type: ignore[assignment]

try:                                    # the OPEN-ITEM layer — see item_open.py's docstring
    import item_open
except Exception:
    item_open = None                    # type: ignore[assignment]

try:                                    # the VERSION-DRIFT layer — see version_drift.py's docstring
    import version_drift
except Exception:
    version_drift = None                # type: ignore[assignment]

try:                                    # the MACHINE layer — see machine_identity.py's docstring
    import machine_identity
except Exception:
    machine_identity = None             # type: ignore[assignment]

try:                                    # the SETTINGS layer — B23; see settings_drift.py
    import settings_drift
except Exception:
    settings_drift = None               # type: ignore[assignment]

try:                                    # the SCHEDULED-TASK layer — B89/B114; see
    import scheduled_task_watch         # scheduled_task_watch.py's docstring
except Exception:
    scheduled_task_watch = None         # type: ignore[assignment]

try:                                    # Windows consoles default to cp1252 and would
    sys.stdout.reconfigure(encoding="utf-8")   # mangle the em-dashes in these files
except Exception:
    pass

_SESSION_ID = ""         # filled by _is_reentry_moment(); see its docstring

MAX_NEXT_LINES = 24      # roughly one screen; NEXT.md itself is capped tighter
MAX_INBOX_ITEMS = 12
STALE_COMMITS = 4        # commits since NEXT.md changed before we question the queue
FETCH_TIMEOUT = 8        # seconds for the origin fetch — best effort, never fatal

# How long an EVENT-gated watch can sit before it is worth a human look.
#
# NOT "before its trigger is probably never going to fire" — that is what this said until B44
# (2026-09-05), and it is a claim nothing in this system is in a position to make. The number
# below is the age of the `added` field: it measures how long the watch has been OPEN, which is
# indistinguishable from the inside from "the event happened and nobody noticed". Measured in
# atlas 2026-09-02: eight watches flagged at 36-51 days, and two of their triggers had
# actually fired (seven times and twice) — so the flag was inviting the deletion of unverified
# production changes. Anything printed off this threshold must therefore ask for the check, never
# assert the outcome. A machine-checkable predicate per watch — the fix that would let this
# threshold mean what it originally claimed — is a separate, undecided design change; see
# docs/review/orientation.md.
#
# Dated watches look after themselves — they are hidden until their day, then surface as
# DUE NOW. Event-gated ones have no such floor: if the event never happens the watch sits
# in NEXT.md forever and nothing says how long it has been sitting. The user asked for the
# added-date field on 2026-08-15 for exactly this ("so we know when they are stale").
#
# 30 days is chosen against the real cadence, not a guess: every one of atlas's 22
# watches was introduced between 2026-08-08 and 2026-08-15 (measured with `git log -S`
# during the same change), so watches there are normally born and resolved inside a week
# or two. One that reaches a month without its trigger is a genuine anomaly, and a
# threshold that fires most weeks would just train them to skim the watch list — which is
# the failure this whole section exists to avoid.
STALE_WATCH_DAYS = 30

# Everything after the `---` is echoed VERBATIM into the agent's context at every single
# session start, so an unbounded footer is a recurring tax on every session in the project
# forever. Measured 2026-08-15 in atlas: the footer had grown to 65 lines of session
# narrative — 1,629 tokens, 53% of this hook's entire output and 15% of the whole
# per-session baseline — and every one of those revs (201-205) already had its own entry in
# CHANGELOG.md. Pure duplication, paid for on every session.
#
# The wrap rule already said "no history in NEXT.md", and it had been re-violated twice
# (commit 923ad7b trimmed the footer to one session; two wraps later it was three again),
# because the rule names a `## Done` SECTION and this arrives as italic prose under the
# `---` instead. A rule that has failed twice is not the place to fix this — the cap is.
MAX_FOOTER_LINES = 8

# Both files carry multi-line <!-- --> blocks holding the rules for the AGENT, which the
# human must never see at session start. Stripping only lines that START with "<!--" left
# the entire comment body in place — it then consumed the whole line budget and pushed the
# actual items (and the whole inbox section) off the end. Caught by running the hook rather
# than trusting it; strip the full block.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Watch syntax, per NEXT.md's own rules block. Canonical title line since 2026-08-15:
#
#   **W1. Short title** — `Opus 5` · effort `high` · added `2026-08-15` · check after `X`
#
# `check after` stays LAST — every doc describes it as the field that ends the line — and
# `added` goes immediately before it.
#
# PARSE TOLERANTLY. Two incompatible shapes were already in the wild: atlas writes
# `**W1. title**` with the fields outside the bold, while this plugin's own README (and
# code/NEXT.md, written from it) wrote `**W1 — title · check after `X`**` with everything
# inside. The old anchor required a literal `W1.`, so the second shape never matched and
# fell through to printing its entire raw title line — a silent degradation in the file
# the plugin's own documentation told them to write. These files get edited by hand, late,
# by someone who cannot check the format from memory: accept both shapes and normalise.
_CHECK_AFTER_RE = re.compile(r"check after\s+`([^`]+)`", re.IGNORECASE)
_WATCH_TITLE_RE = re.compile(r"^\*\*(W\d+)\s*[.\-—:]?\s*(.+?)\*\*")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Trailing metadata fields, for when they sit INSIDE the bold and land in the title.
# Anchored on the known field names so a `·` in a real title survives. `answer` covers
# decision titles too — same function, shared with watches. `AFK/` and `HITL/` are the
# attendance/mode field (v1.16.0) — the one field carrying no name in front of it, because
# it is read at a glance on every relayed line and `attend x · mode y` doubled the width of
# every item for nothing. Anchor on the two literals instead.
_FIELD_TAIL_RE = re.compile(
    r"\s*·\s*(?:added|effort|check after|answer|`?(?:AFK|HITL)/)\b.*$", re.IGNORECASE)

# Backticks optional: the field is worth having even when it is typed in a hurry.
_ADDED_RE = re.compile(r"\badded[:\s]+`?(\d{4}-\d{2}-\d{2})`?", re.IGNORECASE)

# What STARTS a new watch entry. The digit is load-bearing: this was `startswith("**W")`,
# so any continuation line opening with a bolded W-word split its own watch in two and
# invented a phantom. atlas's W24 begins a body line with `**WORKOUT** (not a note)…`
# and duly appeared in the watch list as its own entry, waiting on "unspecified". Found
# 2026-08-15 by running the hook against the real file — the synthetic fixture had no
# such line, which is exactly why it has to be run against both.
_WATCH_START_RE = re.compile(r"^\*\*W\d")

# `## Decisions` — the third list (brief 28, 2026-08-16). Same shape as a watch's title
# line, but a decision has no `check after`: it is not waiting on a trigger, it is waiting
# on the user reading it. One line each, no continuation — `_split_next` still tolerates a
# stray continuation line the way watches do, so a hand-edit that adds one degrades rather
# than crashes.
#   **D1. Short title** — answer: `ask <authority>` · added `2026-08-09`
_DECISION_START_RE = re.compile(r"^\*\*D\d")
_DECISION_TITLE_RE = re.compile(r"^\*\*(D\d+)\s*[.\-—:]?\s*(.+?)\*\*")
_ANSWER_RE = re.compile(r"\banswer:\s*`([^`]+)`", re.IGNORECASE)

# A REAL queue item, for the relay tier below. `_split_next` returns the whole `## Queue`
# section verbatim, prose and all — so a file whose queue is empty but whose header explains
# what the project is still comes back truthy, and `if nxt:` cannot tell the two apart.
# That is exactly how an empty queue produced a nine-line relay on 2026-08-25. Count the
# numbered lines instead; the queue is `1..5` by contract, and the truncation marker
# `… more — open NEXT.md` does not match, which is correct — it is not an item.
_QUEUE_ITEM_RE = re.compile(r"^\s*\*{0,2}\d+\.\s")

# Attendance/mode, on a queue item's title line or a watch's field run (v1.16.0). `AFK` =
# they can start it and walk away; `HITL` = it will stop and need them; the mode after the
# slash is the permission mode they have to set BEFORE starting, because an agent cannot
# switch its own. Deliberately unnamed and glued with a slash: it rides on every relayed
# line, and the pair is one decision, not two fields.
#
# Only the COUNT of items missing it is printed — never a per-item list. Every NEXT.md
# written before this field existed is missing it on every item, so a per-item warning
# would out-shout the queue itself in exactly the projects that have most to lose, and it
# clears itself at the next wrap either way.
_ATTEND_RE = re.compile(r"\b(?:AFK|HITL)\s*/\s*(?:Auto|Manual|Accept Edits|Plan|Bypass)\b",
                        re.IGNORECASE)

# B40 (2026-09-05) — the one event trigger that IS machine-readable. `_sort_watches` used to
# put every non-date trigger into `events`, the collapsed "not actionable yet" line, with no
# way for one to ever become due. That is wrong for a trigger of exactly this shape: `check
# after `next session on LAPTOP1`` means "due the moment a session opens on LAPTOP1" — which
# `machine_identity.hostname()` already answers on every session (it produces the `machine:
# ORG-LAPTOP1` line) without interpreting the hostname further.
#
# KEPT NARROW ON PURPOSE, per the brief: only THIS phrase shape is matched, never free-text
# event triggers in general — that would mean guessing at English, and a wrong guess here
# turns a watch DUE on the wrong session, which is worse than the collapsed line it replaces.
# An unmatched event trigger (including this one when hostname is unknown) keeps today's
# behaviour exactly: it falls through to `events`.
# An optional leading article, and it is NOT cosmetic (B118, measured 2026-09-08). Every watch
# actually written in this portfolio reads "THE next session on <machine>", because that is how the
# sentence reads in English -- and this pattern was anchored with no article, so it matched none of
# them. The consequence is the worst available: the watch falls through to the free-text branch and
# prints under "not actionable yet" ON THE VERY MACHINE WHERE IT IS DUE. Confirmed live on
# 2026-09-07 (two watches both due on one machine, both collapsed as not-due) and again on
# 2026-09-08 against `cairn` W6 and W8. A one-word near-miss, not a missing branch -- which is why
# B118's own entry had to be corrected before it could be worked.
_MACHINE_TRIGGER_RE = re.compile(r"^(?:the\s+)?next session on\s+(.+?)\s*$", re.IGNORECASE)


def _is_here(machine_id: str, host: str) -> bool:
    """Loose match, same tradeoff `machine_identity.py` documents for the `run on` annotation:
    every id in the portfolio today is recoverable from its hostname as a case-insensitive
    substring (`ORG-LAPTOP1` contains `LAPTOP1`, `WORKSTATION` is its own). Comparing exactly would
    silently stop matching the day someone writes "check after `next session on LAPTOP1`" while
    the hostname is `ORG-LAPTOP1`, which is the normal case, not the edge case.
    """
    if not machine_id or not host:
        return False
    return machine_id.strip().lower() in host.strip().lower()


def _root() -> Path:
    """The project this session is in.

    ONE script, two install locations — ~/.claude/hooks/ (global, every project)
    and <repo>/.claude/hooks/ (travels with a repo to machines that have no global
    install). Keeping them byte-identical is the whole point; `dev/install_global_reentry.py`
    copies this file to the global location, so never let the two drift.

    Resolution order:
      1. CLAUDE_PROJECT_DIR — exported to hook commands by Claude Code. Normal case.
      2. The repo two levels up, IF this is a repo-local install and that repo has a
         NEXT.md. (Guarding on NEXT.md matters: from ~/.claude/hooks/ the same
         arithmetic yields the HOME directory, which is not a project.)
      3. cwd — documented fallback, "handlers run in the current directory".
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    if here.parent.name == "hooks" and here.parent.parent.name == ".claude":
        candidate = here.parents[2]
        if (candidate / "NEXT.md").is_file():
            return candidate
    return Path.cwd()


def _project_has_own_copy(root: Path) -> bool:
    """True when the project ships its own session_orientation.py — then stand down.

    A repo that carries its own copy works on ANY machine it is cloned to. That is
    not hypothetical: a user may work on one project from a laptop and from a
    checkout on a phone, and the phone has its own ~/.claude/ that this install
    knows nothing about. So repo-local copies must keep working, and the global
    one must not print the same orientation a second time on the machine that has
    both.

    Do NOT "tidy this up" by deleting a project's copy in favour of this one —
    that trades a duplicate-print for a silent failure on every other machine.
    """
    own = root / ".claude" / "hooks" / "session_orientation.py"
    try:
        return own.is_file() and own.resolve() != Path(__file__).resolve()
    except OSError:
        return False


def _read(root: Path, name: str) -> list[str]:
    p = root / name
    if not p.exists():
        return []
    try:
        # errors="replace", not strict: these files are hand-edited, sometimes on a
        # phone or in an editor that saves Windows ANSI. A single un-decodable byte used
        # to raise UnicodeDecodeError — which `except OSError` did not catch, so the
        # outer guard swallowed it and the orientation printed NOTHING AT ALL. Found
        # 2026-08-21 by running the hook against a cp1252-encoded NEXT.md. A mangled
        # em-dash is a cosmetic problem; a silent blank orientation is the failure this
        # entire system exists to prevent.
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    return _COMMENT_RE.sub("", text).splitlines()


def _split_next(root: Path) -> tuple[list[str], list[list[str]], list[list[str]], list[str]]:
    """Split NEXT.md into (queue lines, decision entries, watch entries, footer lines).

    Two lists since 2026-08-08, a third (`## Decisions`) since 2026-08-16 (brief 28).
    Three of five queue slots had become "confirm rev N works in production" items —
    things that cannot be DONE, only CHECKED once something else happens. They crowded
    out work they could actually pick up and taught them to skim past the queue, which
    defeats the whole file. The five 🔴 decisions had the same problem in reverse: they
    lived as prose inside the queue's own section, so they shared `MAX_NEXT_LINES` with
    it and vanished mid-sentence the moment the queue got long (2026-08-16). Giving them
    their own section here — not just their own heading in the file — is the actual fix;
    the heading alone was cosmetic.

    A watch or decision entry is its title line plus any continuation lines up to the
    next `**W`/`**D` marker.
    """
    lines = [ln for ln in _read(root, "NEXT.md") if ln.strip()]
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]           # drop the title; our own header says it

    queue: list[str] = []
    decisions: list[list[str]] = []
    watches: list[list[str]] = []
    footer: list[str] = []
    section = "queue"

    for ln in lines:
        stripped = ln.strip()
        if stripped == "---":
            section = "footer"      # the closing note belongs to neither list
            continue
        if stripped.startswith("## "):
            low = stripped.lower()
            section = ("watching" if "watching" in low else
                       "decisions" if "decision" in low else "queue")
            continue                # section headers are structure, not content
        if section == "queue":
            queue.append(ln)
        elif section == "footer":
            footer.append(ln)
        elif section == "decisions":
            if _DECISION_START_RE.match(stripped):
                decisions.append([ln])   # new entry
            elif decisions:
                decisions[-1].append(ln)  # continuation of the current entry
        elif _WATCH_START_RE.match(stripped):
            watches.append([ln])    # new entry
        elif watches:
            watches[-1].append(ln)  # continuation of the current entry

    if len(queue) > MAX_NEXT_LINES:
        queue = queue[:MAX_NEXT_LINES]
        queue.append("   … more — open NEXT.md")

    while footer and not footer[-1].strip():
        footer.pop()                # trailing blanks shouldn't spend the footer budget
    if len(footer) > MAX_FOOTER_LINES:
        footer = footer[:MAX_FOOTER_LINES]
        footer.append("… footer truncated — it is meant to be a short pointer, "
                      "not session history. Finished work belongs in CHANGELOG.md.")
    return queue, decisions, watches, footer


def _watch_trigger(entry: list[str]) -> tuple[str, str]:
    """Return (kind, trigger) where kind is 'date' | 'event' | 'none'."""
    m = _CHECK_AFTER_RE.search(entry[0])
    if not m:
        return "none", ""
    trigger = m.group(1).strip()
    return ("date" if _DATE_RE.fullmatch(trigger) else "event"), trigger


def _watch_title(entry: list[str]) -> str:
    """`W1. short title` — for the compact one-line forms, from either title shape."""
    m = _WATCH_TITLE_RE.match(entry[0].strip())
    if not m:
        return entry[0].strip()
    return f"{m.group(1)}. {_FIELD_TAIL_RE.sub('', m.group(2)).strip()}"


def _entry_age(entry: list[str]) -> int | None:
    """Days since a watch or decision was added, or None when it carries no added date.

    None is a REPORTED state, not a silent one — see the note in main(). A field that can
    be skipped without consequence decays, and this one is only useful if every entry has
    it. Shared by watches and decisions — both use the same "added YYYY-MM-DD" field.
    """
    m = _ADDED_RE.search(entry[0])
    if not m:
        return None
    try:
        return (date.today() - date.fromisoformat(m.group(1))).days
    except ValueError:
        return None                 # a real date-shaped string that isn't a date


def _decision_title(entry: list[str]) -> str:
    """`D1. short title` — mirrors _watch_title for the compact one-line form."""
    m = _DECISION_TITLE_RE.match(entry[0].strip())
    if not m:
        return entry[0].strip()
    return f"{m.group(1)}. {_FIELD_TAIL_RE.sub('', m.group(2)).strip()}"


def _decision_answer(entry: list[str]) -> str:
    m = _ANSWER_RE.search(entry[0])
    return m.group(1).strip() if m else "?"


def _sort_watches(watches: list[list[str]], host: str = "") -> tuple[list, list, list]:
    """Partition into (due now, date-gated but not yet due, event-gated).

    `host` (B40) is this session's raw hostname, passed in rather than resolved here — the
    caller already has it from `machine_identity.hostname()`. A `next session on <X>` trigger
    that names THIS machine is due now, same as an arrived date; every other event trigger,
    including that same shape on a different machine or with no hostname available, is
    unchanged from before and falls to `events`.
    """
    today = date.today().isoformat()
    due, pending, events = [], [], []
    for entry in watches:
        kind, trigger = _watch_trigger(entry)
        if kind == "date":
            (due if trigger <= today else pending).append((trigger, entry))
        else:
            m = _MACHINE_TRIGGER_RE.match(trigger) if trigger else None
            if m and host and _is_here(m.group(1), host):
                due.append((trigger, entry))
            else:
                # No parseable trigger, or a machine trigger that isn't this one, is treated
                # as event-gated rather than dropped — a malformed or not-yet-due watch must
                # still be visible, just quietly.
                events.append((trigger or "unspecified", entry))
    return due, sorted(pending), events


def _inbox_items(root: Path):
    """Un-triaged ad-hoc captures: bullet lines only, so prose in the file is ignored."""
    items = [ln.strip() for ln in _read(root, "INBOX.md")
             if ln.strip().startswith(("- ", "* "))]
    return items[:MAX_INBOX_ITEMS], len(items)


# B81 (2026-09-05). `_divergence_warning` below already fires on plain divergence -- ahead/behind
# counts a worktree carries almost permanently, which is exactly why the warning did nothing on
# 2026-09-05: it said "2 behind, 1 ahead", this repo's own guidance is that running two sessions in
# worktrees is the CORRECT pattern, and the session read the banner as that ordinary background
# state and minted a `Wn` another, unseen commit had already taken. What actually separates a
# numbering hazard from routine divergence is not the counts, it is WHICH files the diverging
# commits touch. Checked here, not folded into B79's own duplicate-id scan (`tools/validate_next.py`
# / `hooks/backlog_file.py`): B79 fires at PARSE time, usually after the id has already been
# written; this fires at SESSION START, before anything is allocated -- the only moment a warning
# can still change what gets minted.
_NUMBERING_HAZARD_FILES = {"NEXT.md", "BACKLOG.md", "CHANGELOG.md"}


def _numbering_hazard_files(root: Path, branch: str, behind: int, ahead: int) -> set[str]:
    """Which of NEXT.md/BACKLOG.md/CHANGELOG.md were touched by the commits making up the
    divergence -- checked on BOTH sides, since the colliding commit is exactly as real when it
    is the one this checkout is AHEAD by as when it is the one it is BEHIND by. `git log
    --name-only` over each range, not `git diff` against one tip -- a diff against a single side
    only ever answers about that side.

    Never raises -- same contract as everything else in this module: a missing branch, a bad
    range, a `git` binary that times out all fall through to an empty set (no hazard reported)
    rather than a crash reaching the caller. Answers "no hazard" without touching git at all
    when there is nothing to compare (`behind` and `ahead` both zero).
    """
    if not (behind or ahead):
        return set()
    import subprocess

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    touched: set[str] = set()
    for rng in (f"HEAD..origin/{branch}", f"origin/{branch}..HEAD"):
        try:
            r = subprocess.run(("git", "log", "--name-only", "--format=", rng), cwd=root,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, env=env, **NO_WINDOW)
        except Exception:
            continue                # never let a slow/broken git hide the rest of the banner
        if r.returncode == 0 and r.stdout:
            touched |= {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
    return touched & _NUMBERING_HAZARD_FILES


def _divergence_warning(root: Path) -> str | None:
    """Warn when this checkout has diverged from `origin`. Added 2026-08-08.

    A user working from two machines — a laptop and a checkout on a phone — makes
    "the files in front of me are the current ones" stop being true.
    Being BEHIND is the dangerous half: you edit stale code, and the merge lands on
    whoever gets there second. It is also completely silent; nothing announces it.

    REPORT, never act. An automatic `git pull` at session start mutates the repo
    before they have said what they want, can hit conflicts, and can rebase over
    uncommitted work — at the exact moment they are least likely to be paying
    attention. Surface the state, offer the action, let them choose. Their words,
    2026-08-08: "Or at least check git status?" — checking was the right instinct.

    Cost is one fetch per session start. Kept cheap: short timeout, terminal prompts
    disabled so a credential request can never hang the hook, and total silence on
    any failure (offline, no remote, not a repo).
    """
    import subprocess

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}     # never block on a credential prompt

    def _git(*args: str, timeout: int = 5) -> str | None:
        try:
            r = subprocess.run(("git", *args), cwd=root, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env, **NO_WINDOW)
        except Exception:
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD":          # detached, or not a repo
        return None
    if not _git("rev-parse", "--verify", f"origin/{branch}"):
        return None                             # no upstream — nothing to compare

    # `is not None` matters: a successful fetch prints nothing to stdout, so the
    # empty string means SUCCESS here, not failure.
    fetched = _git("fetch", "origin", branch, timeout=FETCH_TIMEOUT) is not None

    counts = _git("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD")
    if not counts:
        return None
    try:
        behind, ahead = (int(n) for n in counts.split())
    except ValueError:
        return None

    # A failed fetch used to return None — total silence, identical to being in sync.
    # That ambiguity is the dangerous kind for someone relying on this to catch
    # stale-file editing: "no banner" has to mean ONE thing. Offline, on mobile data,
    # or without cached credentials, say so instead of implying all-clear.
    # (the user spotted this before ever trusting it, 2026-08-08.)
    stale_note = ("" if fetched else
                  " — NOTE: could not reach origin, so this is compared against the "
                  "last-known remote state and may itself be out of date")

    # B81 — name the numbering hazard specifically, rather than let it hide inside a count that
    # reads as routine. Only computed for the two branches below: `ahead`-only means nothing is
    # HIDDEN from this checkout (nothing "published that you cannot see" — the words below are
    # literal), so there is nothing to warn about there.
    hazard = _numbering_hazard_files(root, branch, behind, ahead)
    hazard_note = ""
    if hazard:
        files = " and ".join(sorted(hazard))
        verb = "is" if len(hazard) == 1 else "are"
        # Deliberately does NOT say which side the file was touched on: the scan covers both
        # ranges (see `_numbering_hazard_files`), so "the commits you're missing" would be a
        # false statement whenever the file only moved on the AHEAD side of a divergence.
        hazard_note = (f" {files} {verb} touched by the commits this checkout and origin "
                       "disagree about — another session has published items or watches you "
                       "cannot see; any number you allocate may already be taken. Re-read "
                       "after you pull, and reconcile before minting a new Wn/Dn/backlog id.")

    if behind and ahead:
        return (f"`{branch}` has DIVERGED from origin — {behind} commit(s) behind, "
                f"{ahead} ahead. Another machine has work this one doesn't, and this "
                f'one has work it hasn\'t pushed. Say "sort out git" before starting.'
                f"{hazard_note}{stale_note}")
    if behind:
        return (f"`{branch}` is {behind} commit(s) BEHIND origin — another machine "
                f"(the phone?) has work this one doesn't. Anything below may be stale. "
                f'Say "pull" before starting.{hazard_note}{stale_note}')
    if ahead:
        return (f"`{branch}` is {ahead} commit(s) ahead of origin — unpushed work "
                f"sitting on this machine only. Worth pushing before you switch devices."
                f"{stale_note}")
    if not fetched:
        return ("Could not reach origin to check whether this checkout is current "
                "(offline, or no cached credentials). The last known state was in sync, "
                "but another machine may have pushed since. **Silence here is not a "
                "clean bill of health** — pull before trusting anything below.")
    return None


def _left_behind_warning(root: Path) -> list[str] | None:
    """What the LAST session left behind — uncommitted work, unwrapped commits, an open item.

    This is the intervention. The exit-side hook (`dirty_tree_warning.py`) can only
    warn at a moment when they are leaving, and `SessionEnd` cannot even do that — the
    hooks reference gives it no `systemMessage` and largely ignores its output. The
    orientation is the one thing they reliably reads, so the strong move is not a louder
    exit warning: it is that the next session OPENS with "the last one left N files
    uncommitted and never wrapped" and offers to deal with it first.

    The git halves are gated on the project having wrapped at least once. A project that
    does not use the ritual gets total silence there, the same way it does everywhere else
    in this system — otherwise every repo with a permanently-dirty working file would be
    nagged at every session start, which is the failure mode this whole rewrite exists to
    remove.

    The OPEN-ITEM half (v1.20.0, issue #2) is NOT gated on the ritual: the marker can only
    exist because a session started a queue item in this project, which is a stronger
    opt-in signal than a past wrap. It rides in this box rather than a fourth warning of
    its own — a started-and-never-closed item IS "the last session did not finish
    cleanly", and a fourth box would compete with the three that already earn their space.
    See `item_open.py` for the cry-wolf rules that decide when it speaks at all.
    """
    try:
        from reentry_state import (dirty_paths, state_dir, unwrapped_commits,
                                   uses_wrap_ritual, wrap_command)
    except Exception:
        return None          # standalone repo-local copy without the helper — feature off

    orphan = None
    if item_open is not None:
        try:
            orphan = item_open.orphan(root, _SESSION_ID)
        except Exception:
            orphan = None    # a breadcrumb is never worth failing an orientation over

    changes: list[str] | None = []
    unwrapped = 0
    if uses_wrap_ritual(root):
        changes = dirty_paths(root)
        if changes is None:
            changes = []
        else:
            unwrapped = unwrapped_commits(root) or 0

    # B87 — the last wrap's CAIRN receipt, verified rather than believed. This is the half
    # `.last_wrap` cannot do: a marker inherited from two sessions ago is indistinguishable
    # from a fresh one, which is the exact state both false "wrapped" reports were made in.
    # Silent until this project has recorded at least one receipt (`receipt_used`), so no
    # repo is nagged for not yet using a mechanism it has never used — the same opt-in
    # discipline as `archive_offer.py`'s NEVER_ASKED gate.
    cairn = None
    if wrap_receipt is not None:
        try:
            cairn = wrap_receipt.orientation_line(root)
        except Exception:
            cairn = None     # a breadcrumb is never worth failing an orientation over

    if not changes and not unwrapped and orphan is None and cairn is None:
        return None

    out: list[str] = []
    if cairn:
        out.append(cairn)
    if orphan is not None:
        marker, first = orphan
        out.extend(item_open.describe(marker, first))
        item_open.mark_reported(root)    # stamped here, not at the print site: the caller
                                         # always prints a non-None result, and a crash in
                                         # between costs a downgraded warning, not a lost one
    if changes:
        noun = "file is" if len(changes) == 1 else "files are"
        out.append(f"{len(changes)} {noun} uncommitted in this tree:")
        for ln in changes[:8]:
            out.append(f"     {ln}")
        if len(changes) > 8:
            out.append(f"     … and {len(changes) - 8} more")
    if unwrapped:
        noun = "commit" if unwrapped == 1 else "commits"
        out.append(f"{unwrapped} {noun} since the last wrap — NEXT.md, the briefs and "
                   f"memory may not reflect them.")

    # The breadcrumb is evidence the exit hook ran, at a moment nothing on screen could
    # prove it. Absent = the session died without a SessionEnd (crash, laptop shut),
    # which is exactly the case the warning matters most for — so its absence is never
    # treated as "all clear".
    directory = state_dir(root)
    if directory is not None:
        try:
            exit_state = json.loads((directory / "last_exit.json").read_text(encoding="utf-8"))
            when = datetime.fromtimestamp(float(exit_state["at"])).strftime("%Y-%m-%d %H:%M")
            out.append(f"Last session ended {when} ({exit_state.get('reason', 'other')}).")
        except Exception:
            pass

    if changes or unwrapped:
        out.append(f'Say "clean that up" and I will commit what is yours and run '
                   f"{wrap_command(root)}.")
    elif orphan is not None:
        out.append(f'Say "resume it" to pick that item back up, or "close it" and I will '
                   f"take it off the Queue and run {wrap_command(root)}.")
    else:
        # Only the CAIRN line got us here: nothing is dirty, nothing is unwrapped and no
        # item is open, but the last wrap did not leave a completed receipt. The offer has
        # to match that — telling them to "clean that up" when the tree is clean is the kind
        # of not-quite-right instruction that teaches them to stop reading the box.
        out.append(f"Nothing is uncommitted here — say \"wrap it properly\" and I will run "
                   f"{wrap_command(root)} so the missing steps actually run.")
    return out


def _staleness_warning(root: Path) -> str | None:
    """Warn when NEXT.md has not been touched in a while but the repo has moved on.

    The system's one real weakness: it depends on the wrap step running. A session
    that ends abruptly — laptop shut, context exhausted — leaves NEXT.md describing a
    world that no longer exists, and it does so SILENTLY, which is worse than being
    empty. A stale queue confidently pointing at finished work is exactly the kind of
    thing this user cannot catch from memory.

    Cheap proxy: commits since NEXT.md was last committed. Not proof — some sessions
    legitimately change nothing about the queue — so the wording is a question.
    """
    import subprocess

    def _git(*args: str) -> str:
        return subprocess.run(("git", *args), cwd=root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=5, **NO_WINDOW).stdout.strip()

    last = _git("log", "-1", "--format=%H", "--", "NEXT.md")
    if not last:
        return None
    behind = _git("rev-list", "--count", f"{last}..HEAD")
    if not behind.isdigit() or int(behind) < STALE_COMMITS:
        return None
    when = _git("log", "-1", "--format=%cd", "--date=short", "--", "NEXT.md")
    return (f"NEXT.md was last updated {when} — {behind} commits ago. "
            f"If a session ended without wrapping, this queue may be out of date. "
            f'Ask me to "update NEXT.md" if it looks wrong.')


def check_next(root: Path) -> tuple[bool, list[str]]:
    """Parse `NEXT.md` and report anything a hand-edit could get wrong — for the WRAP to
    run on the file it just wrote, not for SessionStart.

    Deliberately thin: reuses `_split_next`/`_sort_watches`/`_entry_age`/`_ATTEND_RE`, the
    exact functions the next orientation runs, so a wrap-time check and the next session's
    read of the same file can never disagree. No rules sync, no network, no relay tier —
    those exist for a human at session start, not for a wrap checking its own output.

    Built after a watch's `added`/`check after` fields wrapped onto a continuation line on
    2026-08-28: the parser reads those fields from the entry's title line only, so the next
    orientation reported "no added date" for a watch that had one. The wrap that wrote it
    had no way to know until the NEXT session opened — see issue #5.

    Returns (ok, lines). `ok` is False when something here would surface as a warning in
    the orientation; `lines` is what to print either way, so the caller never has to build
    its own success/failure text.
    """
    if not (root / "NEXT.md").exists():
        return True, ["NEXT.md check: no NEXT.md here — nothing to check."]

    nxt, decisions, watches, _footer = _split_next(root)
    problems: list[str] = []

    unmarked = sum(1 for ln in nxt if _QUEUE_ITEM_RE.match(ln) and not _ATTEND_RE.search(ln))
    if unmarked:
        verb = "queue item is" if unmarked == 1 else "queue items are"
        problems.append(f"{unmarked} {verb} missing AFK|HITL/mode.")

    for entry in decisions:
        if _entry_age(entry) is None:
            problems.append(f"{_decision_title(entry)} is missing `added`.")

    for entry in watches:
        title = _watch_title(entry)
        kind, _trigger = _watch_trigger(entry)
        if kind == "none":
            problems.append(f"{title} has no parseable `check after`.")
        if _entry_age(entry) is None:
            problems.append(f"{title} is missing `added`.")

    if problems:
        noun = "issue" if len(problems) == 1 else "issues"
        lines = [f"NEXT.md check: {len(problems)} {noun} found:"]
        lines += [f"  - {p}" for p in problems]
        return False, lines
    return True, ["NEXT.md check: OK — queue, decisions and watches all parse cleanly."]


def _is_reentry_moment() -> bool:
    """True only when this SessionStart is a genuine RE-ENTRY, not a mid-session refill.

    SessionStart fires with `source` in {startup, resume, clear, compact}. Only the
    first two are moments where they have lost their place; `compact` and `clear` happen
    MID-SESSION, in the middle of whatever they are actually doing.

    Why this guard exists (reported 2026-08-22, twice, from two angles): the rules tell
    the agent to open its FIRST REPLY with the orientation. A compaction re-injects this
    output into a running session, the agent reads it as a fresh session start, and
    relays the queue — so a mid-session question about silt in a fish tank was answered
    with five bike queue items and two watches. Their words: "This should surely not have
    returned a /next inquiry?" It should not. The orientation is a re-entry aid; a
    session already under way has nothing to re-enter.

    Never fail the session over this: an unreadable or absent payload is treated as a
    real start, which is the pre-2026-08-22 behaviour.

    Side effect: stashes `session_id` in `_SESSION_ID`. stdin can only be read once, and
    the open-item check needs the id to tell a `resume` re-firing inside a session apart
    from a genuinely new one. Absent id degrades to "", which the check treats as unknown.
    """
    global _SESSION_ID
    try:
        payload = sys.stdin.read()
    except Exception:
        return True
    if not payload.strip():
        return True                 # no payload (manual run, older client) — print
    try:
        event = json.loads(payload)
        source = event.get("source")
        _SESSION_ID = str(event.get("session_id") or "")
    except Exception:
        return True
    return source in (None, "startup", "resume")


def main() -> None:
    if not _is_reentry_moment():
        return                      # mid-session compact/clear — they have not lost their place

    # Computed here, ahead of its other use further down, because install_rules.install() needs
    # it NOW: a REENTRY_PROFILE_SOURCE set by THIS project's own .claude/settings.json (B100) must
    # be checked for containment before ensure_profile_file.py ever reads it (B103). `_root()` is
    # a pure read (env var, then a file-existence check) — computing it early costs nothing.
    root = _root()

    # FIRST, and before every early return below: sync the rules into ~/.claude/CLAUDE.md.
    # It is machine-global, not project-specific, so it must happen even in a project with no
    # NEXT.md and even where the repo carries its own copy of this script. Silent when already
    # current, which is almost always. See install_rules.py for why this route exists at all.
    try:
        _installed, _rules_in_context = (
            install_rules.install(root) if install_rules else (None, False))
    except Exception:
        _installed, _rules_in_context = None, False   # never fail a session over a file sync

    # Same spot, same reasoning: MISTAKES.md is global too, so it must exist even in a project
    # with no NEXT.md. Silent when already present, which is almost always.
    try:
        _mistakes_created = (
            ensure_mistakes_file.ensure() if ensure_mistakes_file else None)
    except Exception:
        _mistakes_created = None

    # Same spot, same reasoning again: CREDENTIALS.md is global too. See
    # ensure_credentials_file.py's docstring for the incident that started it.
    try:
        _credentials_created = (
            ensure_credentials_file.ensure() if ensure_credentials_file else None)
    except Exception:
        _credentials_created = None

    # Same spot, same reasoning again: MACHINES.md (B28) is global too — the mapping it holds
    # is a fact about the fleet, not one project. See machine_identity.py's docstring for why
    # it lives here rather than in NEXT.md.
    try:
        _machines_created = (
            machine_identity.ensure_file() if machine_identity else None)
    except Exception:
        _machines_created = None

    # B87 — stamp the tracked files' hashes NOW, while nothing in this session has touched
    # them. Without a session-start baseline, `NEXT.md` changing proves nothing (any session
    # can edit it) and the wrap receipt can only ever report `unverifiable` for step 7, the
    # step the whole wrap exists for. Silent, best-effort, outside the repo, and gated on the
    # project having opted in — a repo with no NEXT.md gets no state written for it, the same
    # silence it gets everywhere else. Before the own-copy return below on purpose: a project
    # shipping its own orientation still wraps with the plugin's skill.
    #
    # B134 — "while nothing has touched them" is an assumption about how often THIS function
    # runs, and it was never enforced here. `stamp_baseline()` is now write-once per session
    # id, so a second run of this hook (a hand-invocation, or a client re-firing SessionStart
    # on a compaction refill) leaves the real session-start snapshot alone. Never pass
    # `force=True` from here: that is the explicit `--stamp-baseline` operator path only.
    #
    # B2 -- the `if NEXT.md` gate above is correct and is also why a whole class of session
    # got no baseline at all. A session started in a PARENT directory (`~/Projects`, which is
    # not itself a repo) that does all its work in a child project below it falls through this
    # gate, so the wrap of that child had nothing to measure against and read a false
    # `CAIRN OPEN`. A baseline can only be taken NOW, before anything is touched, so there is
    # no later moment to recover it -- hence stamping every opted-in child up front. Gated on
    # the root NOT being a project, so an ordinary session still stamps exactly one baseline
    # and pays nothing for this. See `wrap_receipt.stamp_child_baselines()` for the cost
    # measurement and for why siblings are deliberately not covered.
    try:
        if wrap_receipt and (root / "NEXT.md").is_file():
            wrap_receipt.stamp_baseline(root)
        elif wrap_receipt:
            wrap_receipt.stamp_child_baselines(root)
    except Exception:
        pass                     # a baseline is never worth failing an orientation over

    try:
        _drift = version_drift.check(root) if version_drift else None
    except Exception:
        _drift = None            # a breadcrumb is never worth failing an orientation over

    try:
        _machine = machine_identity.check() if machine_identity else None
    except Exception:
        _machine = None          # same: never fail an orientation over a breadcrumb

    try:                          # raw form of the same fact, for B40's watch-trigger match
        _host = machine_identity.hostname() if machine_identity else ""
    except Exception:
        _host = ""

    if _project_has_own_copy(root):
        if _installed:
            print()
            print(_installed)
        if _mistakes_created:
            print()
            print(_mistakes_created)
        if _credentials_created:
            print()
            print(_credentials_created)
        if _machines_created:
            print()
            print(_machines_created)
        if _drift:
            print()
            print(_drift)
        return                      # the repo's own copy will print; don't double up

    nxt, decisions, watches, footer = _split_next(root)
    due, pending, events = _sort_watches(watches, _host)

    # B23 — a required GLOBAL setting that is wrong on THIS machine (today: `cleanupPeriodDays`,
    # whose default was silently pruning the transcripts `tools/timesheet.py` reads). Read-only,
    # one small JSON file, and None on any machine that is already correct — which is every
    # machine, once it has been fixed once.
    #
    # GATED ON `nxt`, and that is a real concession. The fact it reports is global, and B23's
    # brief asks for it in every project on that reasoning. But the first version, ungated, broke
    # two existing invariant tests on the spot (`test_machine_identity.py`,
    # `test_empty_queue_diverged.py`), both asserting the same thing this file's docstring calls
    # the property that makes the hook safe to install everywhere: a project that has not opted in
    # prints NOTHING. A persistent, repeats-every-session line is a much worse thing to spend that
    # silence on than the one-shot install reports that are allowed through it. Gating loses very
    # little in practice — portfolio membership IS having a NEXT.md, so every project they actually
    # works in is opted in, and the line fires there every session until the setting is fixed.
    # Recorded in docs/review/orientation.md as a decision to overrule if they want it louder.
    try:
        _settings = settings_drift.check() if (settings_drift and nxt) else None
    except Exception:
        _settings = None         # never fail an orientation over a config read

    # B89/B114 — same gate and reasoning as B23 above: a global, machine-scoped fact,
    # deliberately only surfaced in a project that has opted into this system (has a
    # NEXT.md), so a repo that never heard of `cairn` stays bit-for-bit silent. See
    # scheduled_task_watch.py for what each half can and cannot say.
    try:
        _sched_armed = (scheduled_task_watch.armed_summary()
                        if (scheduled_task_watch and nxt) else None)
    except Exception:
        _sched_armed = None       # never fail an orientation over a breadcrumb
    try:
        _sched_alerts = (scheduled_task_watch.alerts()
                         if (scheduled_task_watch and nxt) else [])
    except Exception:
        _sched_alerts = []        # never fail an orientation over a breadcrumb

    items, total = _inbox_items(root)
    try:                             # B28 — a `run on <machine>` annotation that isn't this one
        _machine_mismatch = machine_identity.mismatch_warning(nxt) if machine_identity else None
    except Exception:
        _machine_mismatch = None    # never fail an orientation over a breadcrumb
    try:
        left_behind = _left_behind_warning(root)
    except Exception:
        left_behind = None          # git missing, not a repo — never block
    # Computed HERE rather than at its print site further down, because the relay tier needs
    # it: being behind origin means another machine has work this one doesn't, which outranks
    # anything they typed. It still PRINTS first, in its own box.
    try:
        diverged = _divergence_warning(root)
    except Exception:
        diverged = None             # offline, no remote, git missing — never block

    # B26 — the SAME question, one repo boundary wider: are any SIBLING projects behind
    # THEIR origin. Read-only cache lookup (see repo_sweep.py for why this can never be a
    # live sweep at session start); the real check runs detached, for next time.
    try:
        siblings_behind = repo_sweep.summary_line(root) if repo_sweep else None
    except Exception:
        siblings_behind = None      # unreadable cache, no state dir — never block

    # --- THE RELAY TIER (2026-08-25) -----------------------------------------------------
    # Everything above went into the AGENT's context; the tier decides how much of it reaches
    # THE USER, and when. Until today the rule was "orientation first, whatever they asked", and
    # it fired identically on a morning with three due watches and on one with nothing live at
    # all: they opened a session with a plugin-version question, the queue was empty, the inbox
    # was empty, nothing was due — and got nine lines of orientation before their answer. Their
    # words: "this seems wasteful and might get irritating for other users".
    #
    # WHY THE HOOK DECIDES AND NOT THE AGENT. The obvious fix is to let the agent read the
    # opening prompt and judge. It is the wrong fix: an agent holding a concrete task rates
    # the task more relevant than the queue every time, and the sessions where they type a
    # specific question are often the ones where they have lost the thread on another machine.
    # Suppressing a DUE NOW watch because they asked about a plugin version would be this system
    # failing at the single job it does that they cannot do themselves. So the switch is computed
    # from the FILE, deterministically, and the agent's only latitude is position.
    #
    # (`SessionStart` cannot see the prompt anyway — it fires before they type. Prompt-shaped
    # gating would need `UserPromptSubmit` plus a once-per-session guard, which buys nothing:
    # measured 2026-08-25, this hook costs ~826 tokens of context whether or not anything is
    # relayed, and the relay itself is ~150 output tokens. The cost was never tokens.)
    queue_n = sum(1 for ln in nxt if _QUEUE_ITEM_RE.match(ln))
    urgent = bool(due or items or diverged or left_behind or siblings_behind
                  or _machine_mismatch or _sched_alerts)
    live = bool(queue_n or decisions)

    # STARVED — an empty Queue on top of a non-empty backlog (v1.17.0). Until now this
    # computed as STAY QUIET, because `live` only ever looked at NEXT.md: the backlog was
    # read further down, printed as a fact, and never fed back into the tier. So the state
    # the whole three-layer scheme is supposed to make impossible — nothing to do here, five
    # issues sitting in the backlog — announced itself as "nothing is live", and the queue
    # stayed empty for as long as nobody happened to ask. They caught it on 2026-08-28: "why
    # are we not pulling items from the backlog to next?"
    #
    # It is NOT urgent (nothing here has a deadline) and it is NOT `live` (there is no list
    # to relay). It is its own tier, and it buys exactly one line after their answer — an
    # offer, not a listing. Gated on `nxt` for the same reason the backlog block below is:
    # a repo that never opted in stays silent.
    #
    # v1.18.0: `BACKLOG.md` is the backlog and Issues is a sync target, so the count comes
    # from the FILE where there is one — which is also the only source available in a
    # project with no GitHub remote, i.e. the projects that had no backlog layer at all
    # before the inversion. The issues cache stays as the fallback for a repo that has not
    # been migrated yet.
    backlog_n = backlog_afk = 0
    if nxt and backlog_file is not None and backlog_file.exists(root):
        try:
            backlog_n, backlog_afk, _queued = backlog_file.counts(root)
        except Exception:
            backlog_n = backlog_afk = 0
    elif nxt and issues_backlog is not None:
        try:
            backlog_n, backlog_afk = issues_backlog.open_counts(root)
        except Exception:
            backlog_n = backlog_afk = 0
    starved = bool(backlog_n) and not queue_n and not live
    # The FALLBACK rules — printed only while ~/.claude/CLAUDE.md does NOT already carry them.
    #
    # Until 2026-08-22 all three `[to the agent]` directives lived inside `if nxt:` below, so a
    # project without a NEXT.md got none of them — the wrap verdict included, on this machine as
    # well as on LAPTOP1/LAPTOP2. That was the failure they caught twice that day, and the fix is the
    # shipped rules file, not this block.
    #
    # So this exists for exactly one window: a fresh machine's FIRST session (the file was just
    # written and is not in context until the next start), the session right after a plugin
    # update, or a write that failed. In the steady state `_rules_in_context` is True and none of
    # this prints — it would be ~224 tokens per session in every project restating what the agent
    # read seconds earlier. Keep it to FOUR LINES: it is a floor, not a second copy.
    always_on = [] if _rules_in_context else [
        "[to the agent] Reporting session state? The WRAP VERDICT is a QUOTATION: run "
        "`hooks/wrap_receipt.py --check` and quote CAIRN SET/NOT DUE/OPEN/UNKNOWN. Never compose one "
        "yourself, and never give git mechanics; a clean tree is not a wrapped session.",
        "[to the agent] Anything with a future trigger — \"check after the deploy\", \"keep an "
        "eye on X\" — is a queue item or a dated watch, never a sentence in chat. The user cannot "
        "be relied on to hold it between sessions; never ask them to.",
        "[to the agent] Rename this session yourself via set_session_title(session_id=\"self\") "
        "— format `<project> · <subject>`, never \"Item N\", never a title they set themselves — and "
        "say in one line what you renamed it to.",
    ]
    if not nxt and not _rules_in_context:
        always_on.append(
            "[to the agent] This project has NO NEXT.md, so there is no queue — say so if they "
            "asks where they left off. If THIS session produces work with a future, offer once, "
            "at the stopping point, to start one. Never create it unasked.")

    if (not nxt and not items and not due and not decisions and not left_behind
            and not siblings_behind and not diverged):
        # Nothing queued here. Print only if the fallback rules, an install report, a
        # sibling sweep result, or this repo's OWN divergence banner are owed; otherwise
        # total silence, which is what makes this hook safe to run in every repo.
        #
        # `diverged` belongs in both this guard and the print condition below it (B71,
        # 2026-09-05): an empty Queue means nobody has worked this project lately, which is
        # exactly when a checkout goes stale behind `origin` — so the one case this banner
        # exists for was also the one case that silently dropped it. Found the hard way: it
        # was computed correctly above and then never reached a print statement, because
        # neither condition here named it.
        #
        # B23's `_settings` is deliberately NOT in this list. Reaching here means `nxt` is empty,
        # which is exactly the gate it is computed behind — it is always None on this path, and
        # naming it would read as though an empty-queue project could still print it. It cannot;
        # see the comment where it is computed for why that concession was made.
        if (always_on or _installed or _mistakes_created or _credentials_created
                or _machines_created or _drift or siblings_behind or diverged):
            print()
            if diverged:
                print("!" * 68)
                print(f"  ⚠  {diverged}")
                print("!" * 68)
                print()
            for ln in always_on:
                print(ln)
            if _installed:
                print(_installed)
            if _mistakes_created:
                print(_mistakes_created)
            if _credentials_created:
                print(_credentials_created)
            if _machines_created:
                print(_machines_created)
            if _drift:
                print(_drift)
            if siblings_behind:
                print(f"  {siblings_behind}")
        return

    print()

    # Being behind origin invalidates everything printed below it, so it goes FIRST.
    if diverged:
        print("!" * 68)
        print(f"  ⚠  {diverged}")
        print("!" * 68)
        print()

    # B26 — the portfolio-wide version of the box above, ONE line by design (brief:
    # "as few lines as possible… silent when none"). It never invalidates what follows
    # the way `diverged` does — these are SIBLING repos, not this one — so no box, no
    # blank line eaten from the budget, just the line itself.
    if siblings_behind:
        print(f"  {siblings_behind}")
        print()

    # Unfinished business from last time outranks the queue: picking item 1 on top of
    # four uncommitted files is how a session's work gets swept into someone else's
    # commit, and an unwrapped commit means the queue below may already be wrong.
    if left_behind:
        print("-" * 68)
        print("  ⚠  THE LAST SESSION DID NOT FINISH CLEANLY")
        print("-" * 68)
        for ln in left_behind:
            print(f"  {ln}")
        print()

    # Which machine this is, before anything that might say "run on <machine>". Deliberately NOT
    # in the silence path above: a project with no NEXT.md has no queue to misread, and staying
    # bit-for-bit silent there is what makes this hook safe to run in every repo.
    if _machine:
        print(_machine)
    # B28 — a queue item annotated for a DIFFERENT known machine. Right after `_machine` on
    # purpose: this line only makes sense once they already knows which machine they are on.
    if _machine_mismatch:
        print(f"  ⚠  {_machine_mismatch}")
    # B23 — also a fact about THIS machine, so it sits with the two lines above rather than in a
    # box of its own (the brief: "in or beside the existing warning box, not a new UI element").
    if _settings:
        print(f"  {_settings}")
    # B89/B114 — same spot, same reasoning: facts about THIS machine's scheduled work, not
    # about this project. `_sched_armed` is informational (what is registered here);
    # `_sched_alerts` are the two things worth a ⚠ — a stalled run, or a failed/stale sync.
    if _sched_armed:
        print(f"  {_sched_armed}")
    for _ln in _sched_alerts:
        print(f"  ⚠  {_ln}")

    for ln in always_on:
        print(ln)
    if _installed:
        print(_installed)
    if _mistakes_created:
        print(_mistakes_created)
    if _credentials_created:
        print(_credentials_created)
    if _machines_created:
        print(_machines_created)
    if _drift:
        print(_drift)

    # This block is addressed to the AGENT, not to the user — everything this hook
    # prints goes into the agent's context, never onto their screen (verified
    # 2026-08-06, when they started a fresh session, saw nothing, and asked whether they
    # needed to send a message). Relaying is what orients HIM.
    #
    # It lives here because it is the only place it can TRAVEL. The same instruction
    # is also in ~/.claude/CLAUDE.md, which is the copy that normally fires — but
    # that file is untracked, in no repo, and ships with nothing. On any other
    # machine (a work laptop, the phone) `/plugin install reentry` delivers the hook
    # and the skills and none of the rules, so the queue below would land in context
    # with nothing saying what to do with it, and get paraphrased into prose — the
    # exact 2026-08-06 failure. The `next` skill says it too, but its own cost note
    # tells you not to load it just to relay, so it cannot be the guarantee either.
    #
    # It is NOT gated on `nxt`: a due watch or an un-triaged inbox in a project whose
    # queue happens to be empty still has to be relayed, and before today that case
    # fell through with no directive at all.
    #
    # The wrap-verdict directive used to live here too. It moved into `always_on` above on
    # 2026-08-22, because gating it on `nxt` meant it did not exist in a project without a
    # NEXT.md — which is most of them, on every machine.
    #
    # Keep it SHORT — it is re-read on every session in every project, forever, and this
    # system has already had to delete a 1,629-token footer for that reason.
    if urgent:
        print("[to the agent] RELAY FIRST — something below is time-sensitive (due watch, "
              "inbox, git divergence — this repo's own or a sibling's — an unfinished last "
              "session, or a queue item marked for a different machine). Open your first "
              "reply with it, before answering whatever they asked.")
    elif live:
        print("[to the agent] ANSWER FIRST, THEN RELAY — nothing below is time-sensitive. "
              "Answer what they actually asked, then a `---` rule, then \"**Where you left "
              "off**\" and the list. Relay first only if they opened with a greeting or "
              "\"where were we?\".")
    elif starved:
        print(f"[to the agent] ANSWER FIRST, THEN ONE LINE — the Queue is EMPTY and the "
              f"backlog has {backlog_n}"
              + (f" ({backlog_afk} runnable AFK)" if backlog_afk else "")
              + ". After answering them, say the Queue is empty and OFFER to pull the top "
                "few in (brief written to disk, the item stays in the backlog marked "
                "`queued`). Do NOT list the backlog.")
    else:
        print("[to the agent] STAY QUIET — nothing is live: no queue items, no decisions, "
              "nothing due, inbox empty. Do NOT relay a queue; just answer them. One closing "
              "line at most.")
    if queue_n or decisions or due:
        print("[to the agent] When you do relay: a NUMBERED LIST, the file's own numbers, "
              "each ending · model · effort · AFK|HITL/mode · [brief](link). Never prose, "
              "never summarised. Not-due watches collapse to ONE line for the lot of them.")

    if nxt:
        print()
        print("=" * 68)
        print("  WHERE YOU LEFT OFF  —  NEXT.md")
        print("=" * 68)
        for ln in nxt:
            print(f"  {ln}")
        print()
        print('  Say "do 1" (or 2, 3…) and I will read the full prompt off disk.')
        unmarked = sum(1 for ln in nxt
                       if _QUEUE_ITEM_RE.match(ln) and not _ATTEND_RE.search(ln))
        if unmarked:
            verb = "item does" if unmarked == 1 else "items do"
            print(f"  ⚠  {unmarked} queue {verb} not say AFK|HITL/mode. Judge it from the "
                  f"brief and relay that AS a judgement; fix the file at the next wrap.")
        try:
            stale = _staleness_warning(root)
        except Exception:
            stale = None            # git missing, not a repo, timeout — never block
        if stale:
            print()
            print(f"  ⚠  {stale}")

    # The third list (brief 28, 2026-08-16). These are HIS to answer, not an agent's to
    # pick up — no "do Dn". Compact, one line each, same staleness flag a watch gets:
    # a decision waiting 30+ days is either not really their to make or not really needed.
    if decisions:
        print()
        print("-" * 68)
        print(f"  \U0001f534 DECISIONS — these need YOU, not an agent")
        print("-" * 68)
        undated = stale = 0
        for entry in decisions:
            age = _entry_age(entry)
            tag = ""
            if age is None:
                undated += 1
                tag = "  ⚠ no added date"
            elif age >= STALE_WATCH_DAYS:
                stale += 1
                tag = f"  ⚠ waiting {age}d"
            print(f"  {_decision_title(entry)} — answer: {_decision_answer(entry)}{tag}")
        if stale:
            verb = "decision has" if stale == 1 else "decisions have"
            print(f"    ⚠ {stale} {verb} waited over {STALE_WATCH_DAYS} days without an "
                  f"answer — worth deciding or dropping, not carrying.")
        if undated:
            verb = "decision is" if undated == 1 else "decisions are"
            print(f"    ⚠ {undated} {verb} missing `added` on the title line.")

    # A watch whose date has arrived is the ONE thing here they could not have worked out
    # for themselves — it is the whole reason dates are machine-readable. Give it its own
    # box, above the quiet stuff.
    if due:
        print()
        print("-" * 68)
        noun = "watch is" if len(due) == 1 else "watches are"
        print(f"  ⏰ DUE NOW — {len(due)} {noun} ready to check")
        print("-" * 68)
        for _trigger, entry in due:
            for ln in entry:
                print(f"  {ln}")
        print()
        # Name the watch that is ACTUALLY due. This was hardcoded to "W1", which is an
        # example everywhere except the one case that matters — when something other than
        # W1 comes due, the invitation points at the wrong watch.
        first = _watch_title(due[0][1]).split(".")[0].strip()
        print(f'  Say "check {first}" and I will read its prompt off disk.')

    # Everything still waiting collapses to one line each. Visible, never noisy.
    #
    # Age goes on EVENT-gated watches only. A dated watch already says everything a reader
    # needs — it surfaces on its day — whereas an event-gated one is the open-ended kind,
    # and "how long has this been sitting" is the question its added date exists to answer.
    # Showing an age on every one of them, rather than only past the threshold, is
    # deliberate: this hook already learned once (the origin-fetch bug, 2026-08-08) that a
    # blank has to mean exactly ONE thing. If age appeared only when stale, a missing age
    # would ambiguously mean "fresh" or "no added date", which are opposite problems.
    if pending or events:
        print()
        print("  Also watching (not actionable yet):")
        for trigger, entry in pending:
            # Was "from <date>", which reads as the date it was ADDED — precisely the
            # field being introduced here. Say what the date actually means.
            print(f"    · {_watch_title(entry)} — not until {trigger}")
        stale = undated = 0
        for trigger, entry in events:
            age = _entry_age(entry)
            if age is None:
                undated += 1
                note = "⚠ no added date, waiting on"
            elif age == 0:
                note = "added today, waiting on"
            elif age >= STALE_WATCH_DAYS:
                stale += 1
                note = f"⚠ waiting {age}d on"
            else:
                note = f"waiting {age}d on"
            print(f"    · {_watch_title(entry)} — {note}: {trigger}")
        if stale:
            # B44 (2026-09-05). This used to read "the trigger may never come" — a claim this
            # code cannot make. See the STALE_WATCH_DAYS note above: the age is time since
            # `added`, and nothing anywhere records whether the trigger FIRED. Measured in
            # atlas on 2026-09-02: of eight watches flagged at 36-51d, one trigger had
            # fired SEVEN times and another twice, so the old line was arguing to delete eight
            # unverified production fixes on the strength of a number that never meant
            # what it said. Claim only the true thing, and ask for the check.
            verb = "watch has" if stale == 1 else "watches have"
            them = "it" if stale == 1 else "each"
            print(f"    ⚠ {stale} {verb} been open over {STALE_WATCH_DAYS} days. That is time "
                  f"since `added` — nothing here knows whether the trigger has FIRED. Find out "
                  f"whether it did before deleting or re-scoping {them}.")
        if undated:
            verb = "watch is" if undated == 1 else "watches are"
            print(f"    ⚠ {undated} {verb} missing `added` on the title line, so staleness "
                  f"cannot be judged. Ask me to backfill the dates from git history.")

    if nxt and footer:
        print()
        for ln in footer:
            print(f"  {ln}")

    # The BACKLOG, from a cache written by the PREVIOUS session's detached refresh — see
    # issues_backlog.py for why nothing here is allowed to touch the network. Gated on
    # `nxt` so a repo that has not opted into the system stays completely silent, and so
    # an unrelated project never spawns a `gh` process it did not ask for.
    if nxt and (issues_backlog is not None or backlog_file is not None):
        backlog = []
        local = backlog_file is not None and backlog_file.exists(root)
        if local:
            # The file is the backlog. Issues still owes ONE thing no local file can know:
            # an issue somebody else filed. `count_line=False` asks for exactly that part.
            try:
                repo = issues_backlog.cached_repo(root) if issues_backlog else ""
                backlog += backlog_file.summary_lines(root, repo)
            except Exception:
                pass
        try:
            if issues_backlog is not None:
                backlog += issues_backlog.summary_lines(root, count_line=not local)
        except Exception:
            pass
        if backlog:
            # No rule-off box here: the queue is what deserves the visual weight, and the
            # backlog is normally ONE line. A three-line frame around one line of content
            # is the sort of thing that quietly triples this hook's per-session cost.
            print()
            for ln in backlog:
                print(ln)
        try:
            if issues_backlog is not None:
                issues_backlog.spawn_refresh(root)  # for NEXT session, not this one
        except Exception:
            pass

    # B26's own refresh, same gate and the same reasoning as the backlog's above: a repo
    # that has not opted into this system (no NEXT.md) never spawns a background sweep of
    # its own siblings. See repo_sweep.py for why this can never run inline.
    if nxt and repo_sweep is not None:
        try:
            repo_sweep.spawn_refresh(root)          # for NEXT session, not this one
        except Exception:
            pass

    if items:
        print()
        print("-" * 68)
        print(f"  INBOX — {total} un-triaged item(s) you captured since last session")
        print("-" * 68)
        for it in items:
            print(f"  {it}")
        if total > len(items):
            print(f"   … {total - len(items)} more — open INBOX.md")
        print()
        print("  These are UNPROCESSED. Ask me to triage them into NEXT.md or the backlog.")
    print()


if __name__ == "__main__":
    if "--check" in sys.argv:
        # A standalone entry point for the WRAP, not SessionStart — no stdin payload to
        # read, no rules/mistakes sync, no network. Exit code is the signal: 0 clean,
        # 1 something is malformed. Never used to gate the wrap itself — see check_next's
        # docstring; the wrap prints the result and carries on either way.
        _idx = sys.argv.index("--check")
        _target = Path(sys.argv[_idx + 1]) if len(sys.argv) > _idx + 1 else _root()
        try:
            _ok, _lines = check_next(_target)
        except Exception as exc:
            print(f"NEXT.md check: could not run ({exc})")
            sys.exit(0)          # a broken checker must never look like a broken wrap
        for _ln in _lines:
            print(_ln)
        sys.exit(0 if _ok else 1)
    try:
        main()
    except Exception:
        # Never break a session start over an orientation aid.
        sys.exit(0)
