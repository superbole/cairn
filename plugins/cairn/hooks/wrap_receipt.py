#!/usr/bin/env python3
"""The CAIRN receipt — turn the wrap VERDICT from a claim into a quotation (BACKLOG.md B87).

WHY THIS EXISTS
---------------
Reported by the user 2026-09-06, having been told twice by WORKSTATION that a session was
wrapped when `/cairn:wrap` had never been invoked. Both reports were confident, both
were plausible, and both were reached the way a careful agent would reach them — clean
tree, `0 0` against origin, nothing obviously outstanding. **The failure mode is not
laziness, it is diligence pointed at the wrong evidence.**

`rules/CLAUDE.md` already demands the verdict rather than the git mechanics, and already
says *"a clean tree is not a wrapped session"*. Both rules were followed. What neither
rule can do is make the verdict CHECKABLE: it is a sentence, composed by the party that
would have had to do the work, from inputs it can read without doing any of it.

WHY THE TOKEN CARRIES AN ID, AND NOT JUST A COINED WORD
---------------------------------------------------------
B87's sketch was "a coined token only the wrap tool can emit". A fixed string does not
survive contact with the actual threat: the token has to be documented in
`skills/wrap/SKILL.md` for the skill to instruct quoting it, and that file is read by the
agent BEFORE it wraps. A fixed string in the agent's context is a string the agent can
type. Coining defeats reaching for the word unprompted; it does not defeat copying it out
of the instructions, which is the same diligent-and-wrong failure one level up.

So the line carries a RECEIPT ID — a hash over the receipt body (steps, HEAD, session,
timestamp). An agent can fabricate a plausible id; it cannot fabricate one that survives
`--verify`, and fabricating a structured identifier is a different act from speaking
English. Be honest about the size of that: it raises impersonation from "a sentence anyone
would write" to "a fabricated identifier one command contradicts". That is a large jump.
It is not proof, and nothing here should be described as proof.

WHY THE NEXT SESSION VERIFIES, AND NOT HIM
--------------------------------------------
A receipt only they could check is a receipt nobody checks — the same defect as B62
(`MISTAKES.md` is written and never read). `session_orientation.py` verifies the last
receipt at `SessionStart` and says so in the box they already reads, which is exactly where
both false reports would have surfaced the next morning. No new habit is required of them.

FOUR STATES PER STEP, NEVER FEWER
-----------------------------------
Same family as `archive_offer.py`'s B35 note and `push_check.py`'s `CANNOT_CHECK` reasons:
a value covering two opposite states is the defect this whole file exists to catch.

    ran           measured residue found
    skipped       measured absent, and the step was required
    n/a           measured absent, and the step is legitimately conditional
    unverifiable  the step leaves no residue; this tool cannot know either way

`unverifiable` is never rendered as a tick. Surveying the tree, the memory pass, the
session rename (the current title cannot be read back, by design) and the close itself are
permanently in it, and saying so is the point: it tells them how much the token is claiming.

WHERE THE STATE LIVES
----------------------
`state_dir(root)`, outside the repo — same reasoning as `archive_offer.py` and
`item_open.py`: a marker written by code into the repo makes `git status` dirty, and this
marker's job is to survive being checked by a hand that is also checking git status.
`.claude/.last_wrap` stays exactly where it is and keeps its current job; the receipt
supersedes it as EVIDENCE without moving it.

The BASELINE is keyed by session id, never machine-global — B72's reverted first attempt
is the precedent: The user runs several sessions at once, and a machine-global "last known
state" means session A stamps it and session B reads it as its own.

REJECTED
----------
- **A stricter rule in `rules/CLAUDE.md`.** Two bold rules aimed at exactly this were in
  context both times it went wrong. The rule change that ships with this is a change of
  KIND (quote a measurement) not of emphasis.
- **A `SessionEnd` hook that refuses to end an unwrapped session.** That is B40/B43, and a
  different problem: this one happens mid-session, long before any exit hook fires.
- **Trusting `.last_wrap` alone as the receipt.** It cannot distinguish "wrapped now" from
  "wrapped two sessions ago and nothing has moved since", which is precisely the state both
  false reports were made in.
- **A verdict the tool can only emit for success.** "No wrap needed" was the exact sentence
  produced, so a tool owning only the affirmative leaves the impersonation intact one door
  down. All three verdicts below come from here or none of them do.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reentry_state import (WRAP_MARKER_REL, dirty_paths, git,  # noqa: E402
                           project_root, state_dir)

SCHEMA = 1

# The coined stem. Chosen by the user 2026-09-06 from a shortlist (see
# `docs/wrap-receipt-design.md`): a cairn is a marker deliberately left on a trail so you
# can find your way back, which is what a wrap is FOR them. Grepped against the whole repo
# at the time of choosing: zero prior uses, so any occurrence is this mechanism's.
STEM = "CAIRN"

RECEIPT_NAME = "wrap_receipt.json"
BASELINE_SUBDIR = "wrap_baseline"
BASELINE_TTL_DAYS = 7

# Forensic only. The predicate needs `head` and `at`, both present in schema-1 baselines,
# so old ones keep working and there is no window where sessions go blind. It exists
# because B106's investigation was conducted by reading these files by hand, and a version
# marker is what let that reading be conclusive. `BASELINE_TTL_DAYS` retires v1 on its own.
BASELINE_SCHEMA = 2

# Files whose content is hashed at session start so a later rewrite is MEASURABLE rather
# than asserted. `NEXT.md` is the load-bearing one — step 7 is the step the whole wrap
# exists for, and "the file changed" is not evidence on its own, because any session can
# edit it. Only a change against the hash as it stood at SESSION START is.
TRACKED = ("NEXT.md", "CHANGELOG.md", "BACKLOG.md", "INBOX.md")

# "The file changed since session start" is NOT the same question as "this session changed
# the file", and a `git pull` is the whole difference (B122). So every content hash above is
# conjoined with a second signal that GIT ITSELF writes as a side effect of the act: the
# HEAD reflog. Matched as an anchored prefix on the reflog SUBJECT.
#
# Git sets ONE reflog action for a whole operation, so `pull --rebase: <subject>` is a PULL
# — the work came from origin — while a bare `rebase (pick): ...` is this tree replaying its
# own commits. Anything not listed here (pull, fetch, merge, reset, checkout, clone) moved
# HEAD without this session composing a commit.
#
# An unknown verb is classified INNOCENT, which under-reports toward `OPEN`. That is the
# right default for something this list has never seen, and it is why this is a constant
# with a comment rather than a regex nobody can audit.
AUTHORED_HERE = ("commit", "rebase", "cherry-pick", "revert", "am", "applypatch")

# A session that moves HEAD more than this is not a thing. The cap is here so a pathological
# reflog cannot slow the SessionStart path, which reaches this module via
# `orientation_line()`. A baseline whose head sits further down than this reads
# `unverifiable` — the honest direction.
REFLOG_SCAN = 500

# A wrap that skipped one of these is not a wrap.
REQUIRED = ("next_rewrite", "changelog", "commit", "briefs", "inbox", "marker")

# Measured, but "did not happen" is a legitimate outcome — `n/a`, never `skipped`.
CONDITIONAL = ("decisions", "mistakes")

# No residue exists. Listed so the receipt states its own limits rather than implying
# coverage it does not have.
UNVERIFIABLE = {
    "tree_survey": "step 1 is an input to later steps, not an output",
    "memory": "the memory dir is keyed by host path; this tool cannot map it reliably",
    "session_rename": "the current session title cannot be read back, by design",
    "close": "prose",
}

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+\.md)\)")
_BULLET_RE = re.compile(r"^\s*[-*]\s+\S")


# --------------------------------------------------------------------------- baseline

def _baseline_dir(root: Path) -> Path | None:
    directory = state_dir(root)
    if directory is None:
        return None
    path = directory / BASELINE_SUBDIR
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return path


def _prune(directory: Path) -> None:
    cutoff = time.time() - BASELINE_TTL_DAYS * 86400
    try:
        for old in directory.glob("*.json"):
            if old.stat().st_mtime < cutoff:
                old.unlink()
    except OSError:
        pass


def session_id() -> str:
    """This process's Claude Code session id, sanitised. "" when there is none.

    Same read as `reentry_state._session_id()`, duplicated rather than imported because
    that one is private and this module is also invoked as a bare CLI from a shell with
    no session at all — an empty result is a normal outcome here, not an error.
    """
    raw = (os.environ.get("CLAUDE_CODE_SESSION_ID")
           or os.environ.get("CLAUDE_SESSION_ID") or "")
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in raw.strip())[:128]


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def stamp_baseline(root: Path, session: str = "", force: bool = False) -> bool:
    """Record the state of the tracked files at SESSION START. Best-effort, always silent.

    Returns True if it wrote a baseline, False if it declined or could not.

    WRITE-ONCE PER SESSION, and that is the whole of B134 (2026-09-09). This used to
    overwrite unconditionally, while its own comment at the call site asserted the thing it
    did not enforce -- *"stamp the hashes NOW, while nothing in this session has touched
    them"*, which holds only if `session_orientation.main()` runs exactly once. Re-run it
    and every tracked step is then measured against a MID-session snapshot, so a genuine
    rewrite reads `byte-identical to session start` and the verdict is a false `CAIRN OPEN`.
    Measured live: a baseline stamped at 14:05:45 on a commit the session had itself just
    made, after an earlier receipt in the same session had correctly said `ran`.

    An agent triggered it by running the hook by hand to preview its output, but the rules
    payload already documents that orientation text can reappear on a compaction refill --
    so a client that re-fires `SessionStart` does this to a session that did nothing
    unusual, and that session cannot tell: the receipt reads as one that skipped its steps.

    `force=True` is the ONE legitimate re-stamp and it is reserved for the explicit
    `--stamp-baseline` CLI flag, where an operator is deliberately asking. The automatic
    caller must never pass it. B122 rejected an automatic re-stamp for a different reason
    (it needed whoever ran the pull to remember to call something); this closes the same
    door from the other side.

    Nothing is stranded by declining: baselines are keyed by session id and `baseline()`
    reads only this session's own (B72), so a later session gets a different filename and
    `_prune()` clears the abandoned one on TTL.
    """
    session = session or session_id()
    if not session:
        return False
    directory = _baseline_dir(root)
    if directory is None:
        return False
    if not force and (directory / f"{session}.json").is_file():
        return False
    _prune(directory)
    body = {
        "schema": BASELINE_SCHEMA,
        "at": time.time(),
        # The anchor the reflog window is measured from (B122). Deliberately NOT accompanied
        # by an origin sha: this is stamped from `session_orientation.main()` BEFORE
        # `_divergence_warning` fetches, so any origin position recorded here is the stale
        # one. What a pull leaves behind is already on disk, written by git.
        "head": git(root, "rev-parse", "HEAD") or "",
        "files": {name: _digest(root / name) for name in TRACKED},
    }
    try:
        (directory / f"{session}.json").write_text(json.dumps(body), encoding="utf-8")
    except OSError:
        return False
    return True


def baseline(root: Path, session: str = "") -> dict | None:
    """This session's own baseline, or None — never another session's (B72)."""
    session = session or session_id()
    if not session:
        return None
    directory = _baseline_dir(root)
    if directory is None:
        return None
    try:
        data = json.loads((directory / f"{session}.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ------------------------------------------------------------------------ step checks

def _changed(root: Path, base: dict, name: str) -> bool | None:
    """True/False if measurable against the baseline, None if it is not."""
    if not base:
        return None
    before = (base.get("files") or {}).get(name)
    if before is None and not (root / name).is_file():
        return None
    return _digest(root / name) != before


# ------------------------------------------------------------------- attribution (B122)

def _authored_here(subject: str) -> bool:
    """Does this reflog subject mean THIS working tree composed the commit?"""
    verb = subject.split(":", 1)[0].split()[0] if subject.strip() else ""
    return verb in AUTHORED_HERE


def _reflog_window(root: Path, base: dict | None) -> list[tuple[str, str]] | None:
    """The HEAD reflog entries ABOVE this session's baseline head. None = cannot see.

    `None` AND `[]` ARE OPPOSITE ANSWERS AND MUST NEVER BE CONFLATED. `[]` is "HEAD has
    not moved this session"; `None` is "there is no reflog to read, so a pull cannot be
    told from a commit". Test with `is None`, never with a bare `if not` — the same
    distinction `reentry_state.git()` draws between `""` and `None`.

    Anchored on the baseline SHA, deliberately not on `base["at"]`. Reflog resolution is
    one second and `at` is a float, so a time anchor either drops a commit made inside the
    stamp's own second or (when floored) admits the commit that preceded the stamp. The
    sha is already recorded, and it removes the clock from the predicate entirely — which
    also means a mid-session clock adjustment cannot corrupt a verdict.
    """
    anchor = (base or {}).get("head") or ""
    if not anchor:
        return None
    out = git(root, "reflog", "show", "--format=%H|%gs", "-n", str(REFLOG_SCAN), "HEAD")
    if out is None:
        return None                     # no reflog: a mirror, or core.logAllRefUpdates off
    window: list[tuple[str, str]] = []
    for line in out.splitlines():
        sha, _, subject = line.partition("|")
        if sha == anchor:
            return window               # newest-first, so everything above is this session
        window.append((sha, subject))
    return None                         # anchor not in the scanned entries — cannot see


def attribution(root: Path, base: dict | None) -> dict:
    """What THIS session actually touched, according to git. Computed once per receipt.

    Keys: `window` (reflog entries above the baseline), `commits` (those this tree
    composed), `paths` (repo-relative paths this session changed, committed or not).
    Any of them may be None, meaning unmeasurable — which propagates to `unverifiable`.
    """
    window = _reflog_window(root, base)
    # WHY it cannot see, not just THAT it cannot. Without this the printer had to name a cause,
    # and it named the wrong one: a bare `--check` outside a Claude Code session has no session id
    # and therefore no baseline, and the receipt reported "no HEAD reflog in this checkout" -- one
    # message for two opposite states, in the file that exists to stop exactly that.
    if base and (base.get("head") or ""):
        reason = "" if window is not None else "the baseline HEAD is not in this checkout's reflog"
    else:
        reason = "no session baseline (a bare CLI run outside a session has none)"
    commits = None if window is None else [s for s, subj in window if _authored_here(subj)]

    paths: set[str] | None = None
    if commits is not None:
        # `dirty_paths`, not `git diff --name-only HEAD`: porcelain `-uall` also catches
        # UNTRACKED files, so a project whose NEXT.md was never committed keeps its
        # attribution instead of silently losing it.
        dirty = dirty_paths(root)
        if dirty is not None:
            paths = set()
            for line in dirty:
                entry = line[3:].strip().strip('"').replace("\\", "/")
                # A porcelain rename is `R  old -> new`; both sides were touched here.
                for part in entry.split(" -> "):
                    part = part.strip().strip('"')
                    if part:
                        paths.add(part)
            if commits:
                # `--ignore-missing` so one gc'd sha (a rebase leftover) cannot lose the
                # whole call; `--no-walk` so only these commits are listed, not history.
                out = git(root, "log", "--no-walk", "--ignore-missing", "--name-only",
                          "--format=", *commits)
                if out is None:
                    paths = None
                else:
                    paths |= {ln.strip().replace("\\", "/")
                              for ln in out.splitlines() if ln.strip()}
    return {"window": window, "commits": commits, "paths": paths, "reason": reason}


def _changed_by_session(root: Path, base: dict, attrib: dict, name: str) -> bool | None:
    """True only when the content moved AND git says this tree moved it."""
    changed = _changed(root, base, name)
    if changed is None:
        return None
    paths = attrib.get("paths")
    if paths is None:
        return None
    return bool(changed and name in paths)


def work_head(root: Path, base: dict | None, attrib: dict | None = None) -> str:
    """Where this session actually started working — after any pull, merge or reset.

    B122's "record the pulled head" option, DERIVED rather than recorded: the baseline is
    stamped before `_divergence_warning` fetches, so a recorded origin sha would be the
    stale one.
    """
    attrib = attribution(root, base) if attrib is None else attrib
    for sha, subject in (attrib.get("window") or []):
        if not _authored_here(subject):
            return sha
    return (base or {}).get("head") or ""


def _queue_briefs(root: Path) -> tuple[int, list[str]]:
    """(links checked, links that point at a file which does not exist)."""
    try:
        lines = (root / "NEXT.md").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0, []
    in_queue = False
    checked, missing = 0, []
    for line in lines:
        if line.startswith("## "):
            in_queue = line.strip().lower().startswith("## queue")
            continue
        if not in_queue:
            continue
        for target in _LINK_RE.findall(line):
            if target.startswith(("http://", "https://", "#")):
                continue
            checked += 1
            if not (root / target).exists():
                missing.append(target)
    return checked, missing


def _inbox_bullets(root: Path) -> int | None:
    """Un-triaged bullets left in INBOX.md. None when the project has no INBOX.md."""
    path = root / "INBOX.md"
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return sum(1 for ln in lines if _BULLET_RE.match(ln) and not ln.lstrip().startswith("<!--"))


def _rationale_record(root: Path) -> Path | None:
    """The project's rationale record, whatever it calls itself. None if it has none."""
    for candidate in ("docs/decisions.md", "docs/DECISIONS.md", "DECISIONS.md"):
        if (root / candidate).is_file():
            return root / candidate
    return None


def _mistakes_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    return Path(base) / "MISTAKES.md"


def _mtime_after(path: Path, when: float) -> bool | None:
    try:
        return path.stat().st_mtime >= when
    except OSError:
        return None


def _arrival(attrib: dict, with_sha: bool = True) -> str:
    """How the newest change that was NOT this session's arrived — for the detail line.

    Naming the verb is what turns "wrong" into "instructive": the receipt says the file
    moved by `pull --ff-only`, rather than silently declining to tick a step. `with_sha`
    is off where the caller already prints that sha.
    """
    for sha, subject in (attrib.get("window") or []):
        if not _authored_here(subject):
            verb = subject.split(":", 1)[0].strip() or "an unnamed git operation"
            return f"`{verb}`" + (f" ({sha[:8]})" if with_sha else "")
    return "a change from outside this session"


def steps(root: Path, base: dict | None, attrib: dict | None = None) -> dict:
    """Every step's state, measured. Never raises — this runs inside a hook path.

    `attrib` is `attribution()`'s result, passed in so `record()` computes it once. Left
    optional and keyword-only-by-convention so every existing caller keeps working. NOT
    memoised in a module dict: the test suite calls this twice on one fixture with a
    mutation in between, and a cache would serve the second call stale.
    """
    out: dict[str, dict] = {}

    def put(name, state, detail=""):
        out[name] = {"state": state, "detail": detail}

    have_base = bool(base)
    base_head = (base or {}).get("head") or ""
    base_at = float((base or {}).get("at") or 0)
    attrib = attribution(root, base) if attrib is None else attrib
    session_shas = attrib.get("commits")

    def tracked_step(name, filename, ran_detail, idle_detail, blind_detail):
        state = _changed_by_session(root, base or {}, attrib, filename) if have_base else None
        if state is None:
            put(name, "unverifiable", blind_detail)
        elif state:
            put(name, "ran", ran_detail)
        elif _changed(root, base or {}, filename):
            # The whole of B122: content moved, but not by anything this session did.
            put(name, "skipped",
                f"{filename} changed since session start, but the change arrived by "
                f"{_arrival(attrib)} — not from this session")
        else:
            put(name, "skipped", idle_detail)

    # --- step 7: the rewrite the whole wrap exists for -------------------------------
    tracked_step("next_rewrite", "NEXT.md",
                 "NEXT.md rewritten here this session",
                 "NEXT.md is byte-identical to session start",
                 "no session baseline, or no HEAD reflog — cannot tell a rewrite from a pull")

    # --- step 2: the CHANGELOG entry ---------------------------------------------------
    tracked_step("changelog", "CHANGELOG.md",
                 "CHANGELOG.md written here this session",
                 "CHANGELOG.md untouched",
                 "no session baseline, no CHANGELOG.md, or no HEAD reflog")

    # --- step 4: the commit --------------------------------------------------------------
    head = git(root, "rev-parse", "HEAD") or ""
    if not head:
        put("commit", "unverifiable", "not a git repo, or no commits yet")
    elif not have_base:
        put("commit", "unverifiable", "no session baseline to compare HEAD against")
    elif session_shas is None:
        put("commit", "unverifiable",
            "this checkout keeps no HEAD reflog, so a commit cannot be told from a pull")
    elif session_shas:
        put("commit", "ran",
            f"commit {session_shas[0][:8]} created here this session"
            + (f" (+{len(session_shas) - 1} more)" if len(session_shas) > 1 else ""))
    elif head != base_head:
        # HEAD moved and none of it was ours. This sentence IS the bug, printed.
        put("commit", "skipped",
            f"HEAD moved {base_head[:8]} -> {head[:8]} by {_arrival(attrib, False)}, "
            f"not by a commit from this session")
    else:
        put("commit", "skipped", f"HEAD unchanged at {head[:8]} since session start")

    # --- step 3: every queue item's brief resolves --------------------------------------
    checked, missing = _queue_briefs(root)
    if not checked:
        put("briefs", "n/a", "no brief links in the Queue to check")
    elif missing:
        put("briefs", "skipped",
            "%d brief link(s) point at a missing file: %s" % (len(missing), ", ".join(missing[:3])))
    else:
        put("briefs", "ran", f"{checked} brief link(s) resolve")

    # --- step 8: INBOX drained -----------------------------------------------------------
    bullets = _inbox_bullets(root)
    if bullets is None:
        put("inbox", "n/a", "no INBOX.md in this project")
    else:
        put("inbox", "ran" if bullets == 0 else "skipped",
            "INBOX.md is empty" if bullets == 0 else f"{bullets} un-triaged bullet(s) remain")

    # --- step 5b: the wrap marker --------------------------------------------------------
    try:
        marked = (root / WRAP_MARKER_REL).read_text(encoding="utf-8").split()[0]
    except (OSError, IndexError):
        marked = ""
    if not head:
        put("marker", "unverifiable", "no HEAD to compare the marker against")
    elif not marked:
        put("marker", "skipped", "no .claude/.last_wrap")
    elif marked != head:
        put("marker", "skipped", f".last_wrap is {marked[:8]}, HEAD is {head[:8]}")
    elif have_base and _mtime_after(root / WRAP_MARKER_REL, base_at) is False:
        # An INHERITED marker: it names the right sha but was written before this session
        # began, which is the hole B122's last paragraph describes. An honest wrap always
        # rewrites the marker during the session, so this can never cause a false `skipped`.
        put("marker", "skipped",
            f".last_wrap == HEAD ({head[:8]}) but was written before this session started "
            f"— inherited from an earlier one, not stamped here")
    else:
        put("marker", "ran", f".last_wrap == HEAD ({head[:8]}), stamped this session")

    # --- step 2a: the rationale record (conditional) ------------------------------------
    record = _rationale_record(root)
    if record is None:
        put("decisions", "n/a", "this project has no rationale record")
    elif not have_base:
        put("decisions", "unverifiable", "no session baseline")
    else:
        # mtime alone greens on a pull — the rationale record is tracked and routinely
        # pulled — so conjoin it with git's attribution, same as the tracked files above.
        touched = _mtime_after(record, base_at)
        try:
            rel = str(record.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = record.name
        paths = attrib.get("paths")
        ours = None if paths is None else rel in paths
        if ours is None:
            put("decisions", "unverifiable",
                f"{record.name} exists but this checkout keeps no HEAD reflog")
        else:
            put("decisions", "ran" if (touched and ours) else "n/a",
                f"{record.name} written here this session" if (touched and ours)
                else f"{record.name} untouched — legitimate when no decision was made")

    # --- step 6a: MISTAKES.md (conditional) ----------------------------------------------
    # Deliberately still mtime-only, unlike every check above. `~/.claude/MISTAKES.md` lives
    # OUTSIDE the repo, so no `git pull` can touch it and B122 cannot reach here — mtime is
    # not a weak signal here, it is the only signal there is.
    mistakes = _mistakes_path()
    if not have_base:
        put("mistakes", "unverifiable", "no session baseline")
    elif not mistakes.is_file():
        # Measurably not appended to — the plugin creates this file on every machine, so
        # its absence is a fact, not a blind spot. Distinct from the unreadable case below:
        # collapsing the two would be the same "one value, two opposite states" defect this
        # file exists to catch.
        put("mistakes", "n/a", "no MISTAKES.md on this machine yet")
    else:
        touched = _mtime_after(mistakes, base_at)
        if touched is None:
            put("mistakes", "unverifiable", "MISTAKES.md exists but could not be read")
        else:
            put("mistakes", "ran" if touched else "n/a",
                "MISTAKES.md appended this session" if touched
                else "MISTAKES.md untouched — legitimate when nothing went wrong")

    for name, why in UNVERIFIABLE.items():
        put(name, "unverifiable", why)

    return out


def measurements(root: Path, base: dict | None, held: bool = False,
                 attrib: dict | None = None) -> dict:
    """Facts that already have their own tool. Quoted into the receipt, never re-derived.

    Only `push_check.py` (B86) qualifies. It answers a question this receipt needs, at a
    point in the procedure that has already happened when the receipt is recorded (step 5),
    and it has its own carefully-reasoned `CANNOT_CHECK` reason codes — re-implementing it
    here would be a second, inevitably-divergent copy of a check this repo has already
    argued out once.

    `held` IS REQUIRED, AND IT IS NOT A GUESS THE TOOL CAN MAKE
    ------------------------------------------------------------
    `push_check` answers ONE question: *did a stop-before-push hold?* Its `ALERT` means
    "HEAD moved this wrap and nothing is ahead of origin, so something pushed the work
    without being asked". After an ORDINARY wrap that pushed on purpose, that is exactly the
    state — HEAD moved, ahead is 0 — so calling it unconditionally makes every successful
    wrap print `something pushed the work without being asked`. Caught 2026-09-06 in this
    file's own first live run, one commit after it shipped.

    That is the alarm-fatigue failure this repo already knows by name and which
    `push_check.py`'s own docstring warns about for `ahead == 0`: a warning that fires in a
    benign common state gets read as normal and skipped, which destroys the alarm for the
    case that matters. Whether the push was INTENDED is not visible in git; only the caller
    knows. So the wrap declares it (`--record --held` on the `AFK` stop path), and the
    default records the counts as plain facts with no verdict attached.

    `archive_offer.py` deliberately does NOT belong in here, even though B87 names it as
    the model to copy. Step 10 runs AFTER the receipt is recorded, so every receipt would
    freeze an `archive` reading of `NEVER_ASKED` — true at the instant it was taken, wrong
    within a minute, and signed into a receipt id as though it were settled. A value that
    is nearly always the same is a value that trains them to skip the line. It stays what it
    already is: a live check run at verdict time, printed beside the token and outside the
    id (see `advisory()`).
    """
    out: dict[str, str] = {}
    if held:
        try:
            import push_check
            # `since` is what separates push_check's two readings of `ahead == 0` — "this
            # wrap committed nothing" from "something pushed it unasked".
            #
            # NOT the raw baseline head: after a pull that is the PRE-pull sha, so
            # push_check sees "HEAD moved" and can fire its `ALERT` — *something pushed the
            # work without being asked* — on a session that committed nothing (B122, same
            # family). `work_head()` is where this session actually started working.
            result = push_check.check(root, since=work_head(root, base, attrib) or None)
            out["push"] = f"{result.get('status', '?')} — {result.get('message', '')}"
        except Exception:
            out["push"] = "CANNOT_CHECK — push_check unavailable in this checkout"
        return out
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    counts = git(root, "rev-list", "--left-right", "--count", f"origin/{branch}...HEAD")
    parts = counts.split() if counts else []
    if len(parts) == 2 and all(x.lstrip("-").isdigit() for x in parts):
        out["push"] = (f"behind {parts[0]}, ahead {parts[1]} against origin/{branch} "
                       f"(counts only — no stop was declared, so nothing is asserted about "
                       f"whether a push was intended)")
    else:
        out["push"] = (f"CANNOT_CHECK — no origin/{branch} ref in this checkout, so the "
                       f"push position cannot be read")
    return out


def advisory(root: Path) -> str:
    """The archive-offer state, read LIVE. Printed beside the token, never inside the id."""
    try:
        import archive_offer
        if archive_offer.pending(root):
            return "PENDING — a declined archive offer is still outstanding"
        if not archive_offer.asked_marker_used(root):
            return "NONE — no outstanding archive offer for the current HEAD"
        if archive_offer.asked_at_head(root):
            return "NONE — asked and resolved at the current HEAD"
        return "NEVER_ASKED — no record step 10 ran for this HEAD"
    except Exception:
        return "CANNOT_CHECK — archive_offer unavailable in this checkout"


# ----------------------------------------------------------------------------- verdict

def _receipt_path(root: Path) -> Path | None:
    directory = state_dir(root)
    return None if directory is None else directory / RECEIPT_NAME


def last_receipt(root: Path) -> dict | None:
    path = _receipt_path(root)
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def receipt_used(root: Path) -> bool:
    """Whether this project has EVER recorded a receipt.

    Gates every "no cairn" complaint, exactly the way `archive_offer.asked_marker_used()`
    gates `NEVER_ASKED`. Without it, every project that has ever wrapped would be told, at
    its very next session, that its last wrap left no receipt — true, useless, and the
    alarm-fatigue failure this repo already knows by name.
    """
    path = _receipt_path(root)
    return path is not None and path.is_file()


def _receipt_id(body: dict) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _nothing_to_wrap(root: Path, base: dict | None, attrib: dict | None = None) -> bool:
    """True when there is genuinely nothing a wrap would do.

    Deliberately strict, and deliberately measured against THIS SESSION's baseline rather
    than against the last receipt alone: "wrapped two sessions ago and nothing has moved"
    is exactly the state both false reports were made in, so a verdict that cannot see the
    current session's own activity would reproduce the bug it exists to catch.

    This was B122's SECOND consumer of the two contaminated signals, and the one place the
    fix loosens a verdict: a session that pulled and did nothing now reads `NOT DUE` rather
    than `OPEN`. That is the correct answer — nothing happened here that this session owes a
    wrap for, and the pulled commits carry the other machine's receipt. Inherited-but-
    unwrapped commits stay covered by `session_orientation._left_behind_warning`,
    `reentry_state.uses_wrap_ritual` and `orientation_line`.
    """
    if git(root, "rev-parse", "HEAD") is None:
        return False
    changes = dirty_paths(root)
    if changes is None or changes:
        return False
    if base is None:
        return False                    # cannot see this session's activity — never claim
    attrib = attribution(root, base) if attrib is None else attrib
    if attrib.get("commits") is None or attrib.get("paths") is None:
        return False                    # blind: never claim `NOT DUE` while it cannot see
    if attrib["commits"]:
        return False                    # THIS session committed; something is owed a wrap
    for name in TRACKED:
        if _changed_by_session(root, base, attrib, name):
            return False
    return True


def verdict(root: Path, base: dict | None, step_states: dict,
            attrib: dict | None = None) -> tuple[str, list[str]]:
    """(`SET` | `NOT DUE` | `OPEN`, reasons). All three come from here, or none do."""
    if _nothing_to_wrap(root, base, attrib):
        return "NOT DUE", ["no commits, no file changes and a clean tree since session start"]
    skipped = [name for name in REQUIRED if step_states.get(name, {}).get("state") == "skipped"]
    blind = [name for name in REQUIRED
             if step_states.get(name, {}).get("state") == "unverifiable"]
    if skipped:
        return "OPEN", [f"{n}: {step_states[n]['detail']}" for n in skipped]
    if blind:
        return "OPEN", [f"{n}: {step_states[n]['detail']}" for n in blind]
    return "SET", []


def _token(state: str, receipt_id: str = "") -> str:
    return f"{STEM} {state}" + (f" · {receipt_id}" if receipt_id else "")


def record(root: Path, session: str = "", held: bool = False) -> dict:
    """Compute everything, write the receipt, return it. The wrap's final measurement.

    `held=True` only on the `AFK` stop path, where the wrap committed locally and deliberately
    did NOT push — see `measurements()` for why this cannot be inferred.
    """
    session = session or session_id()
    base = baseline(root, session)
    attrib = attribution(root, base)
    step_states = steps(root, base, attrib)
    state, reasons = verdict(root, base, step_states, attrib)
    body = {
        "schema": SCHEMA,
        "at": time.time(),
        "head": git(root, "rev-parse", "HEAD") or "",
        "branch": git(root, "rev-parse", "--abbrev-ref", "HEAD") or "",
        "session": session,
        "verdict": state,
        "reasons": reasons,
        "steps": step_states,
        "measurements": measurements(root, base, held, attrib),
        "held": held,
        "baseline": bool(base),
        # Was git's own attribution readable? A fact about HOW the measurement was taken,
        # so it belongs inside the signature, alongside `baseline` which it mirrors.
        "attributed": attrib.get("paths") is not None,
        "attribution_reason": attrib.get("reason") or "",
    }
    body["id"] = _receipt_id(body)
    # Added AFTER the id is minted, on purpose: the archive offer is read live at verdict
    # time and must never be signed into the receipt. See `measurements()`.
    body["advisory"] = advisory(root)
    # Also after the id, and for a different reason: `baseline` (a bool) is already signed
    # above, so this adds no new fact to the signature -- it only makes the one that
    # diagnosed B134 in a single line READABLE. Nothing was looking at it.
    body["baseline_at"] = float((base or {}).get("at") or 0)
    path = _receipt_path(root)
    if path is not None:
        try:
            path.write_text(json.dumps(body, indent=1), encoding="utf-8")
        except OSError:
            pass
    return body


def verify(root: Path, receipt_id: str) -> tuple[bool, str]:
    """Does `receipt_id` name a receipt actually on disk, for the current HEAD?"""
    data = last_receipt(root)
    if data is None:
        return False, "no receipt has ever been recorded for this project"
    stored = data.get("id") or ""
    if stored != receipt_id:
        return False, (f"no receipt with id {receipt_id} — the most recent is {stored} "
                       f"({data.get('verdict', '?')})")
    head = git(root, "rev-parse", "HEAD") or ""
    if head and data.get("head") and data["head"] != head:
        return False, (f"receipt {receipt_id} is real but was recorded at "
                       f"{str(data['head'])[:8]}; HEAD is now {head[:8]}")
    return True, (f"receipt {receipt_id} verified — {data.get('verdict')} at "
                  f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(float(data.get('at', 0))))}")


def orientation_line(root: Path) -> str | None:
    """One line for the SessionStart box, or None when there is nothing worth saying.

    Silent unless this project has recorded at least one receipt (`receipt_used`) — the
    same opt-in discipline as everywhere else in this plugin. A project that has never
    used the mechanism is never nagged about not using it.
    """
    if not receipt_used(root):
        return None
    data = last_receipt(root)
    if data is None:
        return None
    head = git(root, "rev-parse", "HEAD") or ""
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(data.get("at", 0))))
    state = data.get("verdict", "?")
    if state != "SET":
        return (f"Last {STEM}: {state} at {when} — the previous session did not record a "
                f"completed wrap.")
    if head and data.get("head") and data["head"] != head:
        # Third place B122 reached: HEAD moving is not the same as commits being made here.
        # A pull AFTER a wrap used to print "commits after a wrap are not covered by it" at
        # a session that had committed nothing. Same primitive, anchored on the receipt.
        window = _reflog_window(root, {"head": data["head"]})
        if window is not None and not any(_authored_here(s) for _, s in window):
            return (f"Last {STEM} SET at {when} ({str(data['head'])[:8]}); HEAD is now "
                    f"{head[:8]}, which arrived by {_arrival({'window': window})} — nothing "
                    f"has been committed here since.")
        return (f"Last {STEM} SET at {when} ({str(data['head'])[:8]}), but HEAD has moved "
                f"since — commits after a wrap are not covered by it.")
    return None


# --------------------------------------------------------------------------------- CLI

def _print_receipt(body: dict) -> None:
    # Say it FIRST, not in a footnote. Three of the six REQUIRED steps are measured against a
    # baseline the SessionStart hook writes, keyed to the session id -- so a run from a plain
    # terminal has no baseline and CANNOT answer them, and the table below is eight `?` rows that
    # look like a broken tool rather than a wrong place to stand. Measured twice on 2026-09-08:
    # the same `--check` was pasted from a PowerShell prompt on two machines, read as a result both
    # times, and it was not one.
    if body.get("attributed") is False and "baseline" in (body.get("attribution_reason") or ""):
        print()
        print("  NOTE: no session baseline, so next_rewrite / changelog / commit CANNOT be")
        print("  measured here. That is a wrong place to stand, not a failure: the baseline is")
        print("  written at SessionStart and keyed to the session id, which a plain terminal does")
        print("  not have. Run this from INSIDE a Claude Code session to get a real answer.")
    order = list(REQUIRED) + list(CONDITIONAL) + list(UNVERIFIABLE)
    glyph = {"ran": "ran ", "skipped": "SKIP", "n/a": "n/a ", "unverifiable": "  ? "}
    for name in order:
        info = body["steps"].get(name)
        if not info:
            continue
        print(f"  [{glyph.get(info['state'], '  ? ')}] {name:<15} {info['detail']}")
    print()
    for key, value in body.get("measurements", {}).items():
        print(f"  {key:<17} {value}")
    # B134 — the tracked steps are only as good as WHEN this was taken, and that was
    # invisible: a baseline silently re-stamped mid-session made a real rewrite read
    # `byte-identical to session start`. Stated, not judged against a threshold — a
    # session-start baseline is normally the oldest thing in the session, and anyone
    # reading a surprising SKIP can now see in one line whether it is.
    if body.get("baseline_at"):
        stamped = time.strftime("%H:%M:%S", time.localtime(body["baseline_at"]))
        age = max(0, int((body.get("at", time.time()) - body["baseline_at"]) / 60))
        print(f"  {'baseline':<17} stamped {stamped}, {age}m before this receipt")
    if body.get("advisory"):
        print(f"  {'archive':<17} {body['advisory']}   (live, not part of the id)")
    # Printed only when there is something to say: without a HEAD reflog, a pull and a
    # commit are indistinguishable and the steps above degrade to `unverifiable` (B122).
    if body.get("attributed") is False:
        why = body.get("attribution_reason") or "cause not recorded"
        print(f"  {'attribution':<17} UNAVAILABLE — {why}, so a pull cannot be told from a commit")
    print()
    if body["verdict"] != "SET":
        for reason in body.get("reasons", []):
            print(f"  ! {reason}")
        print()
    print(_token(body["verdict"], body["id"]))


def main(argv: list[str] | None = None) -> int:
    try:                                # Windows consoles default to cp1252 and would
        sys.stdout.reconfigure(encoding="utf-8")   # mangle the em-dashes below (B33).
    except Exception:                   # Inside main(), never at import: this module is
        pass                            # imported BY a hook, and reconfiguring another
                                        # program's stdout as a side effect of import is
                                        # not this file's business.
    args = (argv if argv is not None else sys.argv[1:])
    root = project_root()
    if not args:
        print("usage: wrap_receipt.py --record [--held] | --check [--held] | "
              "--verify <id> | --stamp-baseline")
        return 2
    if args[0] == "--stamp-baseline":
        # The one legitimate re-stamp (B134): an operator asking explicitly. Say whether it
        # REPLACED an existing one -- overwriting a real session-start snapshot is how a
        # genuine rewrite comes to read `byte-identical to session start`.
        had = baseline(root) is not None
        wrote = stamp_baseline(root, force=True)
        if wrote and had:
            print("baseline REPLACED — the previous session-start snapshot for this session "
                  "is gone, so steps measured against it now compare to right now")
        elif wrote:
            print("baseline stamped")
        else:
            print("no baseline written (no session id, or no writable state dir) — "
                  "the receipt will report `unverifiable`, never a guess")
        return 0
    if args[0] == "--record":
        body = record(root, held="--held" in args)
        _print_receipt(body)
        return 0 if body["verdict"] in ("SET", "NOT DUE") else 1
    if args[0] == "--check":
        base = baseline(root)
        attrib = attribution(root, base)
        step_states = steps(root, base, attrib)
        state, reasons = verdict(root, base, step_states, attrib)
        body = {"steps": step_states, "verdict": state, "reasons": reasons,
                "measurements": measurements(root, base, "--held" in args, attrib),
                "attributed": attrib.get("paths") is not None,
                "attribution_reason": attrib.get("reason") or "",
                "advisory": advisory(root), "id": ""}
        _print_receipt(body)
        print("  (--check does not record; only --record emits a receipt id)")
        return 0 if state in ("SET", "NOT DUE") else 1
    if args[0] == "--verify":
        if len(args) < 2:
            print("usage: wrap_receipt.py --verify <id>")
            return 2
        ok, message = verify(root, args[1])
        print(("OK — " if ok else "FAILED — ") + message)
        return 0 if ok else 1
    print("usage: wrap_receipt.py --record [--held] | --check [--held] | "
              "--verify <id> | --stamp-baseline")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
