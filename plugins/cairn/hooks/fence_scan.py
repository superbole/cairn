#!/usr/bin/env python3
"""Shared fence-tracking for every parser that reads markdown line-start structure (B14/B15).

WHY THIS EXISTS
---------------
Three places each cared whether a line sits inside a ``` or ~~~ fenced code block, and
before this file existed each had re-derived the answer on its own: `backlog_file.py`'s
`_strip_fences()` (B85, the mature original -- unaffected by this change, still its own
copy, since it is outside this lane's ownership), `tools/fence_check.py`'s own report
loop, and -- until B15 -- neither `wrap_receipt._inbox_bullets()` nor
`session_orientation._inbox_items()` tracked fences AT ALL. Both counted `- `/`* ` bullet
lines by raw line-start regex, fence or no fence, so an INBOX.md intake contract that
carried four EXAMPLE bullets inside a fenced code block was read as 5 un-triaged items
instead of the 1 real one (B15's live incident).

This module is now the one place the RULE is defined -- what a fence is, and what a
bullet is -- for the three files this lane owns (`fence_check.py`, `wrap_receipt.py`,
`session_orientation.py`). It is a deliberately small, dependency-free sibling of
`backlog_file._strip_fences()` rather than a replacement for it: `backlog_file.py` is
owned by another lane, importing a leading-underscore name across that boundary would
couple two lanes' releases together, and this module's callers need a fact
`_strip_fences()` does not hand back at all -- see `mask()` below.

WHY AN UNCLOSED FENCE IS REPORTED, NOT JUST HANDLED
----------------------------------------------------
`backlog_file._strip_fences()` treats an unclosed fence (an odd count of markers in the
file) as fenced to EOF -- "fail toward ignoring suspect text, never toward inventing
structure from it." That is the right call for BACKLOG.md/CHANGELOG.md parsing, where the
risk being defended against is a FALSE POSITIVE (pasted output read as a real item).

For an INBOX.md bullet count the risk runs the other way. INBOX.md's whole contract is
"a bullet is the whole protocol" -- every bullet is presumed real, un-triaged work. An
unclosed fence there is far more likely to be a forgotten closing ``` than a structural
attack, and silently blanking every line after it to EOF would make every real bullet
past that point VANISH from the un-triaged count with no signal at all -- which is B15's
own bug, recurring one level up, in the fix meant to close it. So this module reports the
unclosed-fence fact back to the caller (`mask()`'s second return value) instead of
choosing for it. `fence_check.py` uses it to print the same WARNING line it always has;
`wrap_receipt.py` and `session_orientation.py` use it to say so next to the count they
give, rather than -- either one -- silently swallowing the tail of the file.

WHAT COUNTS AS A BULLET
------------------------
One regex, `BULLET_RE`, shared by `fence_check.py`'s INBOX-only structure pattern and both
counters, so "what is a bullet" cannot drift into three disagreeing answers again. It
requires actual content after the marker (``^\\s*[-*]\\s+\\S``), stricter than
`session_orientation.py`'s previous plain `.startswith(("- ", "* "))` -- a bare `- ` line
with nothing after it is formatting, not an un-triaged item.
"""
from __future__ import annotations

import re

# A ``` or ~~~ fence delimiter, line-start (allowing leading whitespace, same as a real
# markdown renderer, and the same pattern `backlog_file._strip_fences()` uses).
FENCE_RE = re.compile(r"^\s*(```|~~~)")

# A markdown bullet line with actual content after the marker. Matches `-` and `*` (the
# `*` case is B15's own bug: `wrap_receipt.py`'s old `_BULLET_RE` already matched it, and
# a `*`-style example bullet inside a fence was exactly what B15's INBOX.md carried).
BULLET_RE = re.compile(r"^\s*[-*]\s+\S")


def mask(lines: list[str]) -> tuple[list[bool], int | None]:
    """Per-line "is this line inside a fence" flags, plus where an unclosed fence started.

    A fence MARKER line itself is never "inside" the fence it opens or closes -- it flags
    False even though it is the line that flips the state. Returns
    `(in_fence_per_line, unclosed_at)`, where `unclosed_at` is the 1-based line number of
    the last fence marker if the file ends still inside a fence (an odd number of markers
    total), or `None` if every fence closed. This function only MEASURES that fact; it
    does not decide what to do about it -- see the module docstring for why callers differ.
    """
    in_fence = False
    opened_at: int | None = None
    out: list[bool] = []
    for i, ln in enumerate(lines, 1):
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            opened_at = i if in_fence else None
            out.append(False)
            continue
        out.append(in_fence)
    return out, opened_at


def strip_bullets_in_fences(lines: list[str]) -> tuple[list[str], int | None]:
    """`lines`, with every fenced-in line blanked (same length, so offsets don't drift).

    Convenience wrapper around `mask()` for callers (the two INBOX counters) that just
    want fence-clean text to scan for bullets, plus the same unclosed-fence signal.
    """
    in_fence, unclosed_at = mask(lines)
    return [(" " * len(ln)) if fenced else ln
            for ln, fenced in zip(lines, in_fence)], unclosed_at
