#!/usr/bin/env python3
"""The BACKLOG layer — `BACKLOG.md`, one file per project, always present.

THE INVERSION (2026-08-28, v1.18.0). Until now the backlog WAS GitHub Issues, and a
project without a GitHub remote had no backlog at all: `NEXT.md` capped at 5, `INBOX.md`
capture-only and explicitly not a parking space, and `/cairn:wrap` step 8a saying "skip
if the repo has no GitHub remote". The sixth item in such a project went nowhere — it was
dropped with a one-line note. The same hole opened in a GitHub project on a bad day: the
wrap must never fail over the backlog, so when `gh` is missing, unauthenticated or offline
the displaced item was discarded at the exact moment they had stopped paying attention.

The user, 2026-08-28: *"Git(Hub/Lab) issues is a first class citizen here in the plugin,
should we also accommodate lower classes such as the pending.md when no repo or issues
list has been established?"*

The answer was not to add a tier BELOW Issues. It was to invert:

    BACKLOG.md   the backlog. Every project has one. No remote, no `gh`, no network, no
                 configuration. This is what the wrap WRITES.
    Issues       a SYNC TARGET, not the backlog — an upgrade for repos that have one.
                 It buys the three things a local file cannot: reachable from their phone,
                 survives a lost machine or a re-clone, and other people can write to it.

One writer, one direction. The alternative — two authoritative copies, a local mirror of
Issues — recreates the failure they named on 2026-08-08 ("I'm worried I'm going to have lots
of different copies/versions of the file and/or system"), which is the reason this whole
system is a plugin and not a folder of scripts.

Offline then costs nothing extra: the wrap writes the file it always writes, and
`tools/sync_backlog.py` reconciles with Issues at the next wrap where `gh` works.

WHAT IS IN THE FILE, AND WHY QUEUED ITEMS STAY
----------------------------------------------
Every open backlog item, INCLUDING the ones currently on `NEXT.md`'s Queue, marked
`queued`. That mirrors the Issues lifecycle exactly (an issue stays open while its item is
queued, and closes when the work lands), which is what keeps sync trivial: one item, one
issue, state changes only on close. It also means a `NEXT.md` lost or rewritten badly by
one of several concurrent sessions does not take the item's brief and rationale with it.

A finished item is marked `closed` and left in place for ONE cycle, then removed by the
sync once the issue is actually closed. That is what replaces an outbox: everything the
sync needs is derivable from the file, so nothing has to be remembered between runs.

NEVER RAISES. Same contract as everything else in the start path — an unparseable file
means an empty list and a silent session, never a broken session start.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FILE_NAME = "BACKLOG.md"

# `## B12. Some title` -- and, B46, a bare `## 12. Some title` too: `n` is the ONLY identity
# this format carries (`next_id()`, the issue mapping and `render()` all key off it), so the
# only thing tolerated here is the missing letter, never an invented `n` for a heading that
# has no integer at all (`## 2b.` — see `_ITEMISH_RE` / `unparsed_headings()` below, which
# still refuses that one). Same tolerant-parsing lesson as the watch parser in
# `session_orientation.py`, where two incompatible shapes were already in the wild before
# anyone thought to check — and the file this reads is hand-edited from a phone.
_ITEM_RE = re.compile(r"^##\s+B?(\d+)\.\s+(.+?)\s*$")
# The fields line, immediately under the header. Parsed TOLERANTLY and field by field —
# the same lesson as the watch parser in session_orientation.py, where two incompatible
# shapes were already in the wild before anyone thought to check.
_ADDED_RE = re.compile(r"added\s+`?(\d{4}-\d{2}-\d{2})`?")
_CLOSED_RE = re.compile(r"closed\s+`?(\d{4}-\d{2}-\d{2})`?")
_ISSUE_RE = re.compile(r"issue\s+`?#(\d+)`?")
_EFFORT_RE = re.compile(r"effort\s+`?(high|medium|low)`?", re.I)
# `AFK/Auto`, and also a BARE `AFK` — a pulled issue carries the attendance label but not
# the mode, and inventing "Auto" for it would be a confident wrong answer written into a
# file they read. Bare means "the mode is still unknown"; the wrap fills it in when the item
# is pulled onto the Queue.
_ATTEND_RE = re.compile(r"`?(AFK|HITL)(?:\s*/\s*([A-Za-z ]+?))?`?(?:\s*·|\s*$)")
_MODEL_RE = re.compile(r"`(Opus 5|Sonnet 5|Haiku 4\.5|Fable 5)`", re.I)
_BRIEF_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# B75/B80's floor marker: `<!-- next-id: 84 -->`. See `read_next_id_marker()` / `write()`.
_NEXT_ID_MARKER_RE = re.compile(r"<!--\s*next-id:\s*(\d+)\s*-->")

# A ``` or ~~~ fence delimiter, line-start (allowing leading whitespace, same as a real
# markdown renderer). Toggled on/off by `_strip_fences()` below.
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _strip_fences(lines: list[str]) -> list[str]:
    """Blank out every line inside a fenced code block (B85).

    `_ITEM_RE`, `_NEXT_ID_MARKER_RE` and `_CHANGELOG_DATE_RE` all match on line-start
    structure with no idea that markdown fences exist, so pasted command output quoting a
    `## Bn.` heading (or a `next-id` marker, or a `## YYYY-MM-DD` CHANGELOG date) reads as
    real structure and silently moves the series — once, permanently, in the direction
    `next_id()`'s `max()` cannot undo. Every caller that scans for that kind of structure
    must scan THIS, never the raw lines.

    Blanked lines are replaced with SPACES of the same length, not emptied — this keeps
    every character offset in the result identical to the original, so a caller doing
    positional slicing (`changelog_status()` splits `CHANGELOG.md` into entries by header
    offset) can run entirely against the cleaned text without the two ever drifting apart.
    Line count and order are preserved either way — callers that index by line position
    (`parse()`'s item/body split, `unparsed_headings()`'s line numbers) depend on that too.
    An unclosed fence (an odd number of markers in the file) is treated as fenced to EOF:
    fail toward ignoring suspect text, never toward inventing structure from it.
    """
    out = []
    in_fence = False
    for ln in lines:
        if _FENCE_RE.match(ln):
            in_fence = not in_fence
            out.append(ln)                             # the fence marker itself never
            continue                                    # matches a heading/marker pattern
        out.append(" " * len(ln) if in_fence else ln)
    return out


def path(root: Path) -> Path:
    return Path(root) / FILE_NAME


def exists(root: Path) -> bool:
    try:
        return path(root).is_file()
    except Exception:
        return False


def _lines(root: Path) -> list[str]:
    try:
        return path(root).read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


def parse(root: Path) -> list[dict]:
    """Every item in the file, in file order. `[]` for missing or unreadable.

    Structural matching (is THIS line a heading, a marker, a fields line?) runs against
    `_strip_fences()`'d text so quoted evidence inside a ``` block is never read as
    structure (B85). Body text is still stored from the ORIGINAL, unstripped line —
    fence-stripping exists to stop a parser from being fooled, not to delete what they
    actually wrote; a quoted heading must survive verbatim in the body it was pasted into.
    """
    items: list[dict] = []
    cur: dict | None = None
    raw = _lines(root)
    for ln, sln in zip(raw, _strip_fences(raw)):
        m = _ITEM_RE.match(sln)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2), "fields": "", "body": []}
            items.append(cur)
            continue
        if cur is None:
            continue                                   # preamble, or the file's own H1
        if _ITEMISH_RE.match(sln):
            # Item-shaped but unparseable by `_ITEM_RE` (missing the `B`, a stray letter
            # suffix, ...) still ends the item — `unparsed_headings()` depends on this
            # boundary to find it below. A bare `## Subsection` inside the body does NOT
            # end the item (B69): the parser cannot otherwise tell "next item" from "this
            # item talks about something with its own `## ` heading", and the old rule —
            # ANY `## ` ends the item — silently truncated a body at its own subsection and
            # discarded everything after it, up to the next real item heading.
            cur = None
            continue
        if not cur["fields"] and sln.strip() and ("·" in sln or _ADDED_RE.search(sln)):
            cur["fields"] = sln.strip()
            continue
        cur["body"].append(ln)

    for it in items:
        f = it["fields"]
        def _g(rx, cast=str):
            m = rx.search(f)
            return cast(m.group(1)) if m else None

        it["added"] = _g(_ADDED_RE)
        it["closed"] = _g(_CLOSED_RE)
        # `_CLOSED_RE` requires a date, so a fields line saying `closed` or `**closed**` with
        # NO date leaves `it["closed"]` at None — indistinguishable from an item that was
        # never closed at all (B30). Flag that specific near-miss so a caller can say so,
        # rather than silently treating the item as still open. `queued`/`inbound` are bare
        # words BY DESIGN and need no such flag; `closed` is the only marker whose absence
        # reads as the OPPOSITE state rather than "unknown".
        it["closed_undated"] = (
            it["closed"] is None
            and bool(re.search(r"(?<![\w-])closed(?![\w-])", f, re.I)))
        it["issue"] = _g(_ISSUE_RE, int)
        it["effort"] = (_g(_EFFORT_RE) or "").lower() or None
        it["model"] = _g(_MODEL_RE)
        am = _ATTEND_RE.search(f)
        it["attend"] = am.group(1).upper() if am else None
        it["mode"] = am.group(2).strip() if (am and am.group(2)) else None
        it["queued"] = bool(re.search(r"(?<![\w-])queued(?![\w-])", f, re.I))
        it["inbound"] = bool(re.search(r"(?<![\w-])inbound(?![\w-])", f, re.I))
        body = "\n".join(it["body"])
        bm = _BRIEF_RE.search(body)
        it["brief"] = bm.group(2) if bm else None
        it["text"] = body.strip()
    return items


def open_items(root: Path) -> list[dict]:
    return [i for i in parse(root) if not i["closed"]]


def undated_closed_items(items: list[dict]) -> list[dict]:
    """Items whose fields line says `closed` with no date attached (see B30 / `closed_undated`).

    Takes an already-`parse()`d list rather than `root`, so a caller that has already parsed
    the file (every caller in this plugin has) does not pay for a second read just to ask this.
    These items read as OPEN everywhere else in this module — `not i["closed"]` is True for
    them too — which is correct: the fix is a warning, not a looser `_CLOSED_RE` that would
    invent a date they never wrote.
    """
    return [i for i in items if i.get("closed_undated")]


# A dated CHANGELOG.md entry header, at ANY depth `##`-`####` this project uses, with the date
# ANYWHERE in the heading text — not only a `## YYYY-MM-DD` prefix.
#
# WHY BROADENED (B83). The plugin's own `CHANGELOG.md` writes `## YYYY-MM-DD — ...`, but that is
# this project's convention, not a rule every project using this hook follows. Measured against
# `atlas`'s real CHANGELOG.md (2026-09-05): 302 `###`-depth headings, each shaped
# `### rev 264 — 2026-09-05 — eight decisions answered, two evidence packs cor...` — date in the
# middle of a `###` heading, not a `##` prefix. The old, narrower pattern matched ZERO of them, so
# `changelog_status()` returned `no-changelog` for every closed item in that project regardless of
# what its CHANGELOG actually recorded — see `_changelog_unreadable_reason()` below for why that
# message was actively misleading, not merely imprecise.
_CHANGELOG_DATE_RE = re.compile(r"(?m)^#{2,4}\s+.*?(\d{4}-\d{2}-\d{2})")


def _changelog_unreadable_reason(root: Path) -> str | None:
    """`None` if `changelog_status()` found dated headings to check; otherwise WHY it could not.

    `"missing"` — no readable `CHANGELOG.md` at all: the project genuinely has none (6 of 9
    tracked projects, per B45's own count), or it exists but is not UTF-8-readable.
    `"unparseable"` — the file exists and reads fine, but nothing in it matches
    `_CHANGELOG_DATE_RE` — a real file in an unrecognised heading shape (B83's `atlas` case),
    NOT the same fact as "this project has no CHANGELOG.md". A caller printing a message should
    say which one it is: naming a missing file when the real file is sitting there unparsed reads
    as "the tool is broken" and stops a reader from investigating further (B83, observed twice).

    Kept as a SEPARATE call from `changelog_status()` rather than widening its own return value —
    every current caller and test compares that value to exactly `"covered"` / `"uncovered"` /
    `"no-changelog"` (B45), and splitting the tri-state contract into four states to carry this
    one extra fact would touch every one of them for a distinction only the printed message needs.
    """
    try:
        raw = (Path(root) / "CHANGELOG.md").read_text(encoding="utf-8")
    except Exception:
        return "missing"
    text = "\n".join(_strip_fences(raw.splitlines()))
    if _CHANGELOG_DATE_RE.search(text):
        return None
    return "unparseable"


def changelog_status(root: Path, item: dict) -> str:
    """`covered`, `uncovered`, or `no-changelog` for a closed item. THREE states, not two.

    WHY (B45). Marking an item `closed` makes the next sync close its issue and delete it from
    `BACKLOG.md` — after that, the CHANGELOG entry is the ONLY surviving record, and nothing
    previously checked one was ever written. A dated NARRATIVE entry counts as coverage; a rev
    or commit citation is neither required nor proof, so this reads entry text for a match, it
    does not grep for a bare identifier.

    A match is `B<n>` (the convention every real entry in this repo already uses — `**B58
    closed.**`, `**B56 closed.**`, ...), `issue #<n>` if the item claims one, or enough of the
    item's own distinctive title words appearing in the same entry.

    WHY THREE STATES AND NOT TWO (corrected 2026-09-05, before this ever shipped). The first
    version of this returned a bare False both for "CHANGELOG.md exists and nothing in it names
    this item" and for "this project has no CHANGELOG.md at all", and the caller blocked on
    either. Measured against the real portfolio, that is not the narrow edge case it looks like:
    **6 of 9 tracked projects have no `CHANGELOG.md`**, so a closed item in any of them could
    never be dropped and would re-log a deferral on every sync, forever.

    That is B45's own defect reproduced one level up — an ABSENT record scoring identically to a
    NEGATIVE one, which is the exact family B30, B35, B37 and B39 are all in. So the absence gets
    its own name here, and the caller decides what to do with it rather than inheriting a guess.

    `covered`      a dated entry on or after `item['closed']` names it — safe to close and drop.
    `uncovered`    there IS a `CHANGELOG.md` and nothing in it since that date names this item.
                   This is the real B45 case: keep the item, say so, let a human add the entry.
    `no-changelog` no readable `CHANGELOG.md`, or none with a dated heading. Nothing can be
                   verified here and nothing ever will be, so blocking is not a safety measure,
                   it is a permanent stall. The caller warns and proceeds. Call
                   `_changelog_unreadable_reason()` separately if the message needs to say
                   WHICH of those two this was (B83).

    Splits into entries against FENCE-STRIPPED text (B85, noted in that item as worth
    checking here too): a `## YYYY-MM-DD` date pasted as evidence inside a ``` block would
    otherwise be read as a real entry boundary, and text quoted inside a fenced entry (e.g.
    an evidence block reproducing `**B69 closed.**`) would otherwise satisfy `b_pat` and
    report coverage that was never actually written as a changelog claim.

    KNOWN RESIDUAL GAP (B88, investigated 2026-09-06, not fixed — read before trying to close
    it further). `h.group(1) < closed` (below) only excludes entries STRICTLY BEFORE the closed
    date; an entry dated the SAME calendar day as `closed` is not before it, so it is eligible
    regardless of whether it was written before or after the actual close — dates here carry no
    time component, and B45's own real CHANGELOG.md closes items and documents them same-day as
    the normal case, not the exception (that is WHY the gate is `>=`, not `>`: a stricter `>`
    would mark same-day coverage — the common case — `uncovered` forever, which is a far worse
    trade than the rare false positive it would prevent).

    That leaves a genuine hole: a same-day entry that merely MENTIONS the item without claiming
    it shipped (`"B86 filed"`, `"related to B86"`) still satisfies `b_pat`, and `changelog_status`
    cannot tell that mention apart from a real `"B86 closed."` written later the same day using
    only date + text-match. Confirmed reproducing this against a synthetic fixture (see
    `tools/test_backlog_file.py` §13): a same-day entry containing only a non-shipping mention
    reads `covered` when it should read `uncovered`.

    Two fixes were tried and REJECTED, not merely skipped:
    - Trust only the topmost same-day entry (CHANGELOG.md is newest-first, so it is the most
      recently written for that date). Does not fix the reported case — the stale mention was
      the ONLY same-day entry at the moment it was wrongly read as covered, so it was already
      topmost. And it actively regresses real usage: this project's own CHANGELOG.md carries 6-7
      separate dated headers on a single day on multiple real dates (2026-09-05, 2026-08-31) for
      unrelated items, so "topmost of the day" routinely is NOT the entry that documents a given
      item, and restricting to it would newly misreport those as `uncovered`.
    - A shipping-verb or bold-marker requirement (B88's own options 2 and 3) — rejected in the
      backlog text itself: brittle against this repo's deliberately-prose entries, and a bold-only
      requirement fails every backfilled entry that never used it.
    No fix was found that closes this gap without reintroducing the same defect one level up
    (a same-day false negative on the common path, in place of a same-day false positive on a
    rare one) or without adding exactly the heuristics B88 already rejected. Shipped as-is: an
    honest, documented, narrow residual limitation rather than a heuristic that cannot be
    verified not to misfire elsewhere.
    """
    closed = item.get("closed")
    if not closed:
        return "covered"                 # nothing to verify; caller only asks this for closed items
    try:
        raw = (Path(root) / "CHANGELOG.md").read_text(encoding="utf-8")
    except Exception:
        return "no-changelog"
    text = "\n".join(_strip_fences(raw.splitlines()))
    headers = list(_CHANGELOG_DATE_RE.finditer(text))
    if not headers:
        return "no-changelog"
    n = item.get("n")
    issue = item.get("issue")
    b_pat = re.compile(r"(?<![\w-])B%d(?!\d)" % n) if n is not None else None
    issue_pat = re.compile(r"#%d(?!\d)" % issue) if issue else None
    title_words = [w for w in re.findall(r"[A-Za-z0-9']+", item.get("title") or "")
                   if len(w) > 3]
    for idx, h in enumerate(headers):
        if h.group(1) < closed:
            continue
        start = h.start()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        entry = text[start:end]
        if b_pat and b_pat.search(entry):
            return "covered"
        if issue_pat and issue_pat.search(entry):
            return "covered"
        if title_words:
            hits = sum(1 for w in title_words if w.lower() in entry.lower())
            if hits >= max(2, (len(title_words) + 1) // 2):
                return "covered"
    return "uncovered"


def changelog_covers(root: Path, item: dict) -> bool:
    """Back-compat wrapper: True only for `covered`. Prefer `changelog_status()`.

    Kept because callers and tests written against the two-state version read more clearly this
    way for the yes/no question. It deliberately folds `uncovered` and `no-changelog` back
    together, so anything that must tell them apart — and the sync must — calls the tri-state
    function instead.
    """
    return changelog_status(root, item) == "covered"


# An `## ` heading that is CLEARLY meant to be an item — it starts with a number — but which
# `_ITEM_RE` did not match. Since B46 a bare `## 12.` is no longer in this set (it now parses
# as an alias for `## B12.`); what is left is a heading with no integer to become — `## 2b.`
# — or one missing the period the parser anchors on — `## B12 no dot`.
_ITEMISH_RE = re.compile(r"^##\s+B?\d+[a-z]?[.)]?\s")


def unparsed_headings(root: Path) -> list[str]:
    """Item-shaped headings this parser CANNOT read. Empty list means safe to regenerate.

    WHY THIS GUARD EXISTS (found 2026-09-03, while enabling the GitLab backend). `write()`
    regenerates the whole file from `parse()`, so anything `parse()` cannot see is DELETED by
    the next write. That is fine while the only writer is the same code that reads it — and it
    stopped being fine the moment a second agent, on a different machine, hand-wrote items as
    `## 12.` instead of `## B12.`.

    Measured in one project that day: 13 item headings, **0 parsed**, 206 lines. The
    file had never synced because `gh` is not installed on that machine, so the mismatch was
    invisible; switching the sync on would have regenerated it from nothing plus 16 pulled
    issues and taken the lot. It was caught by a `--dry-run` reporting 16 pulls and 0 pullable
    items — which is what a `--dry-run` is FOR, and the reason nothing here writes by default.

    So: any caller about to regenerate the file must ask this first. A file it cannot fully
    read is a file it is not allowed to rewrite.

    B46 (2026-09-05) closes the missing-`B` half of exactly this hazard: a bare `## 12.` now
    parses as item 12, because the round-trip only needs the integer `n`, and `render()`
    writes the canonical `## Bn.` form back regardless of which shape they wrote by hand. What
    is deliberately NOT fixed is `## 2b.` — `2b` has no integer to become, and inventing one
    would make `n` something other than the identity `next_id()`, the issue mapping and
    `render()` all assume it is. That still reports here, and a sync still refuses rather
    than guessing at it.
    """
    if not exists(root):
        return []
    parsed = {i["n"] for i in parse(root)}
    out = []
    for ln in _strip_fences(_lines(root)):
        if not _ITEMISH_RE.match(ln):
            continue
        m = _ITEM_RE.match(ln)
        if not m or int(m.group(1)) not in parsed:
            out.append(ln.strip()[:90])
    return out


def counts(root: Path) -> tuple[int, int, int]:
    """(pullable, of which AFK, queued) — pullable EXCLUDES anything already on the Queue.

    The tier decision in session_orientation.py asks "is there anything here they could pull
    in?", and an item already sitting at Queue position 2 is not an answer to that.
    """
    items = open_items(root)
    pull = [i for i in items if not i["queued"]]
    afk = sum(1 for i in pull if (i.get("attend") or "").upper() == "AFK")
    return (len(pull), afk, sum(1 for i in items if i["queued"]))


def duplicate_ids(items: list[dict]) -> dict[int, list[str]]:
    """Ids that appear on more than one item, mapped to every title fighting over them.

    B79 — the cheapest of the three fixes B75 points to: offline, one line, no host, no
    network. Pure over an already-`parse()`d list (parse() is fence-clean since B85, so a
    quoted heading in evidence never counts as a real duplicate here) so a caller that has
    already parsed the file does not pay for a second read just to ask this.

    A DETECTOR, not a preventer — it fires when two sessions' allocations meet on ONE disk
    (a merge, a pull, a shared machine), not at the moment of allocation; that is the
    honest limit and still the best value here (see BACKLOG.md B79).

    Rejected — blocking on a duplicate: a sync must never fail the wrap (same reasoning as
    B37/B45), and a duplicate is sometimes the correct transient state mid-merge; refusing
    to run would strand the person fixing it.
    Rejected — deduping automatically: choosing which item keeps the id needs the
    issue-creation timestamps this function does not have, and getting it backwards
    re-points published references. Report, do not resolve.
    """
    by_n: dict[int, list[str]] = {}
    for it in items:
        by_n.setdefault(it["n"], []).append(it["title"])
    return {n: titles for n, titles in by_n.items() if len(titles) > 1}


def read_next_id_marker(root: Path) -> int:
    """The `<!-- next-id: N -->` floor, or 0 if the file is missing or carries none.

    B75 — the floor that survives DELETION. `parse()` only ever sees items still in the
    file, so once a sync drops B69-B74 (closed → close the issue → drop the row) their
    numbers vanish from `max(parsed ns)` even though they were spent. `write()` reads this
    same marker before every regeneration and carries forward the larger of it and the
    current item set, so the floor can only ever go up — a hand-edit from a phone cannot
    lower it without the result being obviously wrong.

    Read from FENCE-STRIPPED text (B85): the same pasted-evidence hazard that made a
    quoted `## Bn.` heading move the series applies just as much to a quoted marker line,
    and this floor is designed to never go back down on its own — so a phantom reading
    here is the more expensive direction to get wrong. Takes the max of every marker found
    rather than "the first" so a stray duplicate (a bad merge, two hand-edits) still
    resolves toward the higher, safer claim.
    """
    try:
        text = path(root).read_text(encoding="utf-8")
    except Exception:
        return 0
    clean = "\n".join(_strip_fences(text.splitlines()))
    vals = [int(m.group(1)) for m in _NEXT_ID_MARKER_RE.finditer(clean)]
    return max(vals) if vals else 0


def _origin_floor(root: Path, timeout: int = 5) -> int:
    """B80 — the highest Bn already on `origin/<branch>`, or 0. Local-only, best-effort.

    `git show origin/<branch>:BACKLOG.md` resolves entirely from the local object store —
    it reads whatever the last `fetch`/`pull` left behind and never touches the network
    itself, so this composes with the offline contract every other hook in this plugin
    keeps. It is the floor that survives a SIBLING session: two checkouts that each ran
    `next_id()` before either had pushed can still collide (see BACKLOG.md B75's W86 case,
    which only B79's after-the-fact detector catches) — but the far more common case, a
    number already published on `origin` and simply not on THIS disk yet, is exactly what
    this prevents.

    Never raises and never blocks: no git, no repo, no `origin` remote, no upstream
    tracking branch, a detached HEAD, or a timeout all fall through to 0, same as "nothing
    to add here" — `next_id()` still has the local file and the B75 marker either way.

    Rejected — fetching first to make `origin` current: puts a network call in a path that
    must work offline, and the standing rule is that a pull is offered, never run unasked.
    Reading the last-fetched ref is strictly better than reading nothing and costs nothing.
    Rejected — the issue host's high-water mark instead: accurate, but needs a live host in
    an offline path, and would not even have helped the W86 case (both numbers were chosen
    before either was ever filed as an issue).
    """
    try:
        from reentry_state import git                  # lazy: keep this module import-light
    except Exception:
        return 0
    try:
        branch = git(root, "rev-parse", "--abbrev-ref", "HEAD", timeout=timeout)
        if not branch or branch == "HEAD":
            return 0
        text = git(root, "show", f"origin/{branch}:{FILE_NAME}", timeout=timeout, raw=True)
    except Exception:
        return 0              # the docstring above promises this; make it TRUE -- next_id()
                              # is on the sync path and must never be what crashes it
    if text is None:
        return 0
    lines = _strip_fences(text.splitlines())
    ns = [int(m.group(1)) for ln in lines for m in [_ITEM_RE.match(ln)] if m]
    ns += [int(m.group(1)) for m in _NEXT_ID_MARKER_RE.finditer("\n".join(lines))]
    return max(ns) if ns else 0


def next_id(root: Path) -> int:
    """The next unused id — never one any commit has ever spent (B75/B79/B80).

    `max(parsed ns)` alone regresses the moment a closed item is dropped from the file
    (B75) and collides the moment a sibling checkout has allocated ahead of this one
    (B80's origin case) — so the floor is the max of THREE independent signals: what is
    still in the file, the marker that survives deletion, and the last-fetched `origin`.
    None of the three is sufficient alone; together they are the best a local, offline-first
    file can do. B79's duplicate assert is the backstop for what even this cannot prevent
    (two sessions racing before either has pushed) — a detector, not a preventer.
    """
    parsed_max = max((i["n"] for i in parse(root)), default=0)
    floor = max(parsed_max, read_next_id_marker(root), _origin_floor(root))
    return floor + 1


def summary_lines(root: Path, repo: str = "") -> list[str]:
    """The one line printed under the queue at session start, or [] for silence.

    Silence for: no file, and a file with nothing pullable in it. "BACKLOG — 0 items"
    every session in every project is the alarm-fatigue failure in miniature, and this
    line is re-read into context forever.

    A duplicate id (B79) is the one thing that is NEVER silenced this way — it is a red
    flag regardless of whether anything else is pullable, so it lands in this same
    session-start orientation rather than staying buried until a wrap runs the sync.
    """
    if not exists(root):
        return []
    out: list[str] = []
    dups = duplicate_ids(parse(root))
    if dups:
        parts = "; ".join(
            f"B{n} ({' / '.join(titles)})" for n, titles in sorted(dups.items()))
        out.append(f"  BACKLOG — duplicate id(s) on disk: {parts} — see B79.")
    pull, afk, queued = counts(root)
    items = open_items(root)
    unsynced = sum(1 for i in items if i["issue"] is None)
    if not pull and not queued:
        return out
    bits = [f"  BACKLOG — {pull} item(s) in BACKLOG.md"]
    if afk:
        bits.append(f", {afk} runnable AFK")
    if queued:
        bits.append(f", {queued} already queued")
    if repo:
        bits.append(f" · synced to {repo}")
        if unsynced:
            bits.append(f" ({unsynced} not yet pushed)")
    out.append("".join(bits) + ".")
    return out


# --------------------------------------------------------------------------- write side


def render(items: list[dict], project: str = "", next_id_floor: int | None = None) -> str:
    """The whole file, from items. Body text is carried VERBATIM — never re-typed.

    Regeneration is safe only because of that: they edit this file by hand on a phone, and
    an agent that paraphrases their wording while "reformatting" is the same class of bug as
    a wrap rewriting NEXT.md from a stale copy in context.

    `next_id_floor` (B75) is emitted as a `<!-- next-id: N -->` line right under the H1.
    Left as the default `None`, it is derived from `items` alone (`max(n)`, or 0 for an
    empty file) — correct for a pure re-render of what `parse()` just gave back, which is
    what keeps the round-trip in `test_backlog_file.py` byte-for-byte. `write()` passes an
    EXPLICIT value instead: the max of this same derivation and whatever marker was on the
    file being overwritten, which is what lets the floor survive a closed item being
    dropped from `items` (see `read_next_id_marker()`).
    """
    floor = next_id_floor if next_id_floor is not None else max(
        (it["n"] for it in items), default=0)
    out = [f"# BACKLOG — {project}".rstrip(), f"<!-- next-id: {floor} -->", ""]
    out += [
        "Everything worth doing that is NOT in `NEXT.md`'s Queue. Unbounded and unordered —",
        "the ordering that matters lives in the Queue, which is capped at 5 and refilled from here.",
        "",
        "Items marked `queued` are on the Queue right now and stay listed here until the work lands.",
        "Where the repo has GitHub Issues, `tools/sync_backlog.py` mirrors this file to them; the",
        "file is the writer and Issues is the copy that survives a lost machine.",
        "",
    ]
    for it in items:
        out.append(f"## B{it['n']}. {it['title']}")
        out.append(fields_line(it))
        body = (it.get("text") or "").strip()
        if body:
            out.append(body)
        out.append("")
    if not items:
        out.append("_Empty._")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def fields_line(it: dict) -> str:
    bits = []
    if it.get("model"):
        bits.append(f"`{it['model']}`")
    if it.get("effort"):
        bits.append(f"effort `{it['effort']}`")
    if it.get("attend"):
        bits.append(f"`{it['attend']}/{it['mode']}`" if it.get("mode") else f"`{it['attend']}`")
    bits.append(f"added `{it.get('added') or date.today().isoformat()}`")
    if it.get("issue"):
        bits.append(f"issue `#{it['issue']}`")
    if it.get("queued"):
        bits.append("queued")
    if it.get("inbound"):
        bits.append("inbound")
    if it.get("closed"):
        bits.append(f"closed `{it['closed']}`")
    return " · ".join(bits)


class Unreadable(Exception):
    """The file holds item headings `parse()` cannot read — regenerating it would delete them."""


def write(root: Path, items: list[dict], project: str = "", force: bool = False) -> None:
    """Regenerate the file. RAISES `Unreadable` rather than dropping what it cannot parse.

    The only `raise` in this module, and it is deliberate: everything else here degrades to
    silence because it runs in the session-start path, but this function DESTROYS the file it
    is given. Silence is the wrong failure for that. See `unparsed_headings()`.
    """
    if not force:
        stranded = unparsed_headings(root)
        if stranded:
            raise Unreadable(
                f"{len(stranded)} item heading(s) in BACKLOG.md cannot be parsed, so "
                f"rewriting the file would delete them: " + "; ".join(stranded[:3])
                + (" …" if len(stranded) > 3 else ""))
    # B75: read the OLD marker before it is overwritten, and never hand `render()` a floor
    # lower than it. This is what lets the floor survive a closed item being dropped from
    # `items` between one write and the next — `items` alone can only ever tell you the
    # highest number CURRENTLY present, and a sync deliberately removes closed ones.
    floor = max(read_next_id_marker(root),
                max((it["n"] for it in items), default=0))
    # newline="\n" on purpose: this file is edited from a phone, a laptop and a Cursor
    # checkout, and letting Windows translate line endings on every wrap turns a one-item
    # change into a whole-file diff that hides what actually moved.
    with open(path(root), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(items, project or Path(root).name, next_id_floor=floor))


if __name__ == "__main__":                 # manual run: what the hook would print
    try:
        from reentry_state import project_root
        r = project_root() if project_root else Path.cwd()
    except Exception:
        r = Path.cwd()
    for line in summary_lines(r):
        print(line)
    sys.exit(0)
