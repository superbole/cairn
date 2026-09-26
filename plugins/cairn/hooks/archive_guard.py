#!/usr/bin/env python3
"""PreToolUse(archive_session): refuse an agent archiving ITSELF while the wrap is `CAIRN OPEN`.

WHY THIS EXISTS (B64, 2026-09-25)
---------------------------------
A session wrapped (`CAIRN SET` 22:38), then made two more commits and ended unwrapped. The next
session opened with "did not finish cleanly". The user asked for "a hook or something that
doesn't allow a session to archive when the session isn't fully wrapped."

The wrap's step 10 (the archive offer) was the only gate, and it is an INSTRUCTION -- exactly the
thing a session that has gone off-script skips. `archive_offer.py` only records whether the offer
was asked; it blocks nothing. This hook makes the verdict a precondition of the one tool call
that ends the session.

THE VERDICT IS IMPORTED, NEVER RE-DERIVED OR PARSED
---------------------------------------------------
`wrap_receipt.verdict()` is the only source of `SET` / `NOT DUE` / `OPEN` / `UNKNOWN`. A second
copy of that logic here would drift from it, and parsing `--check`'s printed output would break
on the first wording change. "HEAD moved after a SET receipt" -- the exact incident -- already
reads `OPEN` there: the wrap marker `.claude/.last_wrap` names the wrapped HEAD, a later commit
moves HEAD past it, and the `marker` step reads `skipped`. `test_archive_guard.py` pins that.

WHAT IT DECIDES
---------------
  OPEN               -> deny (exit 2), naming the missing steps and the wrap command.
  SET / NOT DUE      -> allow, silently.
  UNKNOWN            -> allow, with ONE line to the user. UNKNOWN is not evidence anything was
                        skipped (rules/CLAUDE.md); blocking on it would teach people to discount
                        the block that is real.
  another session's id, no session id, not the archive tool, no project, no baseline for this
  session, any error, unparseable input -> allow.

WHICH PROJECT IT JUDGES
-----------------------
Every candidate root where THIS session has a session-start baseline: `project_root()` (what
`--check` uses), the git toplevel of the payload's `cwd` (a session that `cd`-ed into another
repo), and the opted-in children of a non-project root (B2's parent-directory session, which
stamps one baseline per child). Any one reading `OPEN` denies.

A root WITHOUT this session's baseline is deliberately not judged. `verdict()` reads `UNKNOWN`
there anyway (B10), so judging it would only cost git calls; the skip is kept as the cheaper route
to the same answer.

KNOWN LIMIT
-----------
A hook only sees TOOL calls. Archiving from the sidebar fires nothing, and `SessionEnd` can warn
but not block. This closes the agent path only; the UI path stays covered by the next session's
"did not finish cleanly" box. It is also the user's escape hatch when they really do want to
archive an unwrapped session, and the refusal says so.

FAILURE POSTURE
---------------
Same contract as `staged_review_guard.py`: any error, any uncertainty -> exit 0 and allow. A
guard that blocks work because it could not read its own state is worse than the defect it
prevents.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ALLOW = 0
BLOCK = 2

TOOL_SUFFIX = "__archive_session"


def _toplevel(cwd: str) -> Path | None:
    try:
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=10)
        out = p.stdout.strip() if p.returncode == 0 else ""
        return Path(out) if out else None
    except Exception:
        return None


def _is_self(tool_input: dict, payload_session: str) -> bool:
    """Is this call archiving the session that is making it?

    `"self"` is the documented spelling. The caller's own id passed explicitly is the same
    session by another name -- accepting only `"self"` would make the guard a spelling test.
    Anything else is another session, which this hook cannot measure, so it is not ours.
    """
    target = str(tool_input.get("session_id") or "").strip()
    if not target:
        return False
    return target == "self" or (bool(payload_session) and target == payload_session)


def _candidate_roots(payload_cwd: str) -> list[Path]:
    import wrap_receipt
    from reentry_state import project_root
    roots: list[Path] = []

    def add(p):
        if p is None:
            return
        try:
            key = p.resolve()
        except OSError:
            return
        if all(key != r.resolve() for r in roots):
            roots.append(p)

    try:
        primary = project_root()
    except Exception:
        primary = None
    add(primary)
    if payload_cwd and os.path.isdir(payload_cwd):
        add(_toplevel(payload_cwd))
    if primary is not None and not (primary / "NEXT.md").is_file():
        try:
            for child in wrap_receipt._opted_in_children(primary):
                add(child)
        except Exception:
            pass
    return roots


def decide(payload) -> tuple[int, str, str]:
    """(exit code, stderr, stdout). Pure enough to test in-process; never raises."""
    try:
        return _decide(payload)
    except Exception:
        return ALLOW, "", ""


def _decide(payload) -> tuple[int, str, str]:
    if not isinstance(payload, dict):
        return ALLOW, "", ""
    tool = str(payload.get("tool_name") or "")
    if not tool.endswith(TOOL_SUFFIX):
        return ALLOW, "", ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ALLOW, "", ""
    payload_session = str(payload.get("session_id") or "").strip()
    if not _is_self(tool_input, payload_session):
        return ALLOW, "", ""

    import wrap_receipt
    from reentry_state import wrap_command

    # The payload's id is the calling session's, by construction. The env var is the fallback
    # `wrap_receipt` itself uses. Sanitised the same way `session_id()` sanitises, because the
    # baseline filename was written with that spelling.
    raw = payload_session or wrap_receipt.session_id()
    session = "".join(c if c.isalnum() or c in "-_" else "-" for c in raw)[:128]

    opened: list[tuple[Path, list[str]]] = []
    blind: list[Path] = []
    for root in _candidate_roots(str(payload.get("cwd") or "")):
        if not (root / "NEXT.md").is_file():
            continue                    # not in the system: silence, same as every other hook
        base = wrap_receipt.baseline(root, session) if session else None
        if base is None:
            blind.append(root)
            continue
        attrib = wrap_receipt.attribution(root, base)
        step_states = wrap_receipt.steps(root, base, attrib)
        state, reasons = wrap_receipt.verdict(root, base, step_states, attrib)
        if state == "OPEN":
            opened.append((root, reasons))
        elif state == "UNKNOWN":
            blind.append(root)

    if opened:
        lines = ["BLOCKED by cairn archive_guard: the wrap verdict is CAIRN OPEN.", ""]
        for root, reasons in opened:
            lines.append(f"{root}:")
            lines.extend(f"  ! {r}" for r in reasons[:10])
            lines.append("")
        cmd = wrap_command(opened[0][0])
        lines += [
            f"Run {cmd} first, and archive only once `wrap_receipt.py --check` reads SET or",
            "NOT DUE. Commits made after a wrap are not covered by it -- re-wrap.",
            "If the user explicitly wants this session archived unwrapped, they can archive",
            "it from the sidebar; this hook sees only tool calls and will not stop that.",
        ]
        return BLOCK, "\n".join(lines) + "\n", ""
    if blind:
        where = ", ".join(str(r) for r in blind[:3])
        msg = (f"cairn archive_guard: the wrap verdict could not be measured for {where} "
               f"(CAIRN UNKNOWN -- no session-start baseline); archive allowed, and nothing "
               f"here is evidence a step was skipped.")
        return ALLOW, "", json.dumps({"systemMessage": msg})
    return ALLOW, "", ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return ALLOW
    code, err, out = decide(payload)
    # Written as UTF-8 bytes, and a failed write never changes the decision. A Windows console
    # stream is cp1252, the reasons come from `wrap_receipt` and carry em-dashes, and an
    # encode error escaping to the outer `except` would have turned a DENY into a silent allow.
    for stream, text in ((sys.stderr, err), (sys.stdout, out + "\n" if out else "")):
        if not text:
            continue
        try:
            stream.buffer.write(text.encode("utf-8", errors="replace"))
            stream.flush()
        except Exception:
            try:
                stream.write(text.encode("ascii", errors="replace").decode("ascii"))
            except Exception:
                pass
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(ALLOW)
