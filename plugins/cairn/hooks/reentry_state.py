#!/usr/bin/env python3
"""Shared git/state helpers for the cairn plugin's hooks.

Imported by `dirty_tree_warning.py` (Stop + SessionEnd) and, defensively, by
`session_orientation.py` (SessionStart). Nothing here ever raises for a caller:
every function returns a benign empty/None value on any failure, because all
three call sites are hooks and a hook that crashes is worse than a hook that
says nothing.

WHY THE STATE LIVES OUTSIDE THE REPO
------------------------------------
The Stop hook has to remember what it last warned about, and the SessionEnd
hook leaves a breadcrumb for the next session. Both are per-machine, per-clone
facts with no business in git history. Writing them under `<repo>/.claude/`
would also be self-defeating in the exact way this hook exists to prevent: an
untracked state file makes `git status` dirty, so a dirty-tree warner that
stores its state in the repo would warn about itself, forever, in every project
that had not thought to gitignore it. So state goes under the user's Claude
config dir, keyed by a slug of the project path.

The ONE exception is `.claude/.last_wrap` — the wrap marker. That stays
repo-local because it is written by the wrap SKILL (a documented shell step a
human can read and reproduce), not by this code, and `atlas` has been
writing it there since 2026-08-08. It is filtered out of the dirty list below
so it cannot become the thing we nag about.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

# `subprocess` and `tempfile` are imported INSIDE the two functions that need them, not
# here. Measured 2026-08-30 while adding the PostToolUse recorder: they cost ~8 ms and
# ~13 ms of the ~50 ms it takes to import this module, and the recorder — the only hook
# that fires many times per session — calls neither. Every other hook in the plugin fires
# once or twice, so paying it lazily costs them nothing measurable. Keep it that way; a
# module-level import here is a tax on every file write in every project.

# Paths that are never worth reporting as uncommitted work. `.last_wrap` is our own
# marker; `.last_deployed` is atlas's chronically-dirty deploy timestamp, and the
# principle it established (2026-07) is the alarm-fatigue one: a warning that always
# fires trains the reader to skip it.
IGNORED_SUFFIXES = (".claude/.last_wrap", ".last_deployed")

WRAP_MARKER_REL = Path(".claude") / ".last_wrap"

# How far up the tree to look for `.git` before giving up. A guard against a pathological
# path, not a real limit -- no checkout on this machine is close to it.
MAX_WALK = 64

# Files that a wrap touches in ANY project using this plugin's contract. Used only as a
# fallback guess at "was HEAD a wrap commit"; the marker is the real signal.
WRAP_TOUCHED_FILES = {"NEXT.md", "CHANGELOG.md", "INBOX.md"}

# Windows only: a console-subsystem child (git.exe, gh.exe) launched from a parent that
# has NO console of its own is given a brand-new one — a black rectangle that flashes
# over whatever the user is looking at. Claude Code runs hooks windowless, SessionStart
# alone fires ~7 git calls, and the Stop hook fires one per turn, so the visible result
# was a burst of flashes at every session start and a single flash after every reply.
# CREATE_NO_WINDOW (0x08000000) suppresses it. `spawn_refresh` in `issues_backlog.py`
# had passed it since it was written; every LEAF call had been missed. Reported by
# the user 2026-08-25 — from their side the symptom was "windows flash over Claude
# desktop", with no way to tell they were their own hooks.
#
# Spread into EVERY subprocess call in this plugin: `**NO_WINDOW`. A new call site that
# forgets it re-introduces the flash for that one command, which is near-impossible to
# spot in review because the code looks completely normal.
NO_WINDOW: dict = {"creationflags": 0x08000000} if os.name == "nt" else {}

# Subdirectory of the state base holding one small file per SESSION (not per project) --
# `<session-id>.json`, `{"root": ..., "at": ...}`. Named so it can never collide with a
# real project's `state_dir()` slug: those are always `<sanitised-name>-<10 hex>`, and
# nothing here ends in ten hex characters, so `check_repos.known_roots()`'s
# `*/last_exit.json` glob and `check_exits.py`'s slug-stripping never see it. See
# `_stamp_session_root` / `_stamped_session_root` / `project_root()` for what it is for.
SESSION_ROOT_SUBDIR = "_sessions"

# How long a session's stamp is kept once written. Not a correctness bound -- a session's
# CLAUDE_PROJECT_DIR cannot change mid-session, so a stamp is exactly as valid on day 7 as
# on minute 1 -- purely a growth bound, one file per session forever otherwise. Mirrors
# `dirty_tree_warning.py`'s STOP_STATE_TTL_DAYS for the same reason: cheap to keep
# in sync by inspection, not worth importing across a hook/library boundary for one int.
SESSION_ROOT_TTL_DAYS = 7


def _session_id() -> str:
    """This process's own Claude Code session id, sanitised for use as a filename.

    Confirmed live, 2026-09-05 (see BACKLOG.md B72): `CLAUDE_CODE_SESSION_ID` is present
    in the environment of a plain `Bash`-tool subprocess even when `CLAUDE_PROJECT_DIR` is
    completely absent from that same environment -- i.e. exactly the shape `check_repos.py`
    runs in from `wrap/SKILL.md` step 1a. `CLAUDE_SESSION_ID` is accepted too in case a
    future or alternate host names it without the `CODE` segment; neither is documented
    Claude Code API, so both are read defensively and an empty result is a normal, expected
    outcome (a bare terminal invocation with no Claude Code session at all), not an error.

    Returns "" rather than None so every caller can do `if session:` without a second check.
    """
    raw = (os.environ.get("CLAUDE_CODE_SESSION_ID")
           or os.environ.get("CLAUDE_SESSION_ID") or "")
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in raw.strip())[:128]


def _session_root_dir() -> Path | None:
    """`~/.claude/reentry-state/_sessions/` (or its test double). None if unwritable."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    directory = Path(base) / "reentry-state" / SESSION_ROOT_SUBDIR
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return directory


def _prune_session_roots(directory: Path) -> None:
    cutoff = time.time() - SESSION_ROOT_TTL_DAYS * 86400
    try:
        for old in directory.glob("*.json"):
            if old.stat().st_mtime < cutoff:
                old.unlink()
    except OSError:
        pass


def _stamp_session_root(session: str, root: Path) -> None:
    """Remember THIS session's own project root, keyed by its OWN session id.

    THE CONSTRAINT THIS EXISTS UNDER (BACKLOG.md B72, objection raised 2026-09-05)
    -----------------------------------------------------------------------------
    A first attempt at this stamped one MACHINE-GLOBAL "last known root" file. It was
    reverted within the hour: The user runs several sessions at once in different
    projects, so a global "last known root" means session A stamps it and session B --
    in a wholly unrelated project, calling a tool with no `CLAUDE_PROJECT_DIR` of its
    own -- silently gets told it is in session A's project. That is worse than the bug
    being fixed (B72 was local and now at least visible; the global stamp was invisible
    and cross-project).

    Keying on `session` instead of the machine makes that failure structurally
    impossible rather than merely unlikely: two concurrent sessions can never share a
    `CLAUDE_CODE_SESSION_ID` (it is how Claude Code tells sessions apart in the first
    place), so a session can only ever read back a root IT ITSELF wrote. There is no
    code path from session B's lookup to session A's file, because the two never look
    in the same place.

    Called from `project_root()` every time it resolves a root FROM `CLAUDE_PROJECT_DIR`
    (i.e. every hook invocation, which -- per `dirty_tree_warning.py`'s `Stop` firing
    once per turn and `repo_recorder.py`'s `PostToolUse` firing on every write -- happens
    many times before a session ever reaches a wrap). By the time `wrap/SKILL.md` step 1a
    runs `check_repos.py` as a plain `Bash` step with neither cwd nor env pinned, this
    session has almost always already stamped its own root at least once.

    Best-effort, like everything else in this module: a failure to write leaves the next
    read with nothing, which degrades to exactly the pre-fix `cwd()` fallback -- never
    worse than today.
    """
    directory = _session_root_dir()
    if directory is None:
        return
    _prune_session_roots(directory)
    try:
        (directory / f"{session}.json").write_text(
            json.dumps({"root": str(root), "at": time.time()}), encoding="utf-8")
    except OSError:
        pass


def _stamped_session_root(session: str) -> Path | None:
    """This session's own previously-stamped root, or None.

    None covers every reason there could be nothing to read: no prior stamp (this is the
    first thing this session has done, or nothing in it ever saw `CLAUDE_PROJECT_DIR`),
    an unwritable/unreadable state dir, a torn/partial write, or a stamped path that no
    longer exists (moved or deleted since). Every one of those falls through to
    `project_root()`'s final `cwd()` fallback -- the same one that ran before this
    existed -- so a bad read here can only ever cost back the pre-fix behaviour, never
    introduce a new failure mode.
    """
    directory = _session_root_dir()
    if directory is None:
        return None
    try:
        data = json.loads((directory / f"{session}.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    root = data.get("root") if isinstance(data, dict) else None
    if not root:
        return None
    candidate = Path(root)
    return candidate if candidate.is_dir() else None


def _resolve_project_root() -> tuple[Path, str]:
    """`project_root()`'s implementation, plus WHICH of three sources answered.

    Split from `project_root()` so a caller that wants to say how confident the answer is
    (`check_repos.py`'s empty-record message, B72) can ask, without changing the signature
    every existing caller of `project_root()` already depends on. See `project_root_source`.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        root = Path(env)
        session = _session_id()
        if session:
            _stamp_session_root(session, root)
        return root, "env"
    session = _session_id()
    if session:
        stamped = _stamped_session_root(session)
        if stamped is not None:
            return stamped, "session-stamp"
    return Path.cwd(), "cwd"


def project_root() -> Path:
    """The project this hook -- or, since B72 (v1.39.0), this session's own plain `Bash`
    step -- is running against.

    Three sources, in order, cheapest-and-most-trustworthy first:

      1. `CLAUDE_PROJECT_DIR` -- exported to hook commands by Claude Code. The normal
         case for every hook in this plugin, and trusted outright.
      2. THIS SESSION's own stamp, keyed by `CLAUDE_CODE_SESSION_ID` -- see
         `_stamp_session_root`. Reached only when (1) is absent, which is the normal
         case for a plain `Bash` tool step, not a hook -- `check_repos.py`, run from
         `wrap/SKILL.md` step 1a with no cwd or env pinned, is the motivating case
         (B72/B67). Safe under concurrency BY CONSTRUCTION: the key is this process's
         own session id, which no other session can ever present, so this can only ever
         answer for the session asking -- never for a different one, which is exactly
         what made the machine-global first attempt at this unsafe (see
         `_stamp_session_root`'s docstring and BACKLOG.md's B72 entry).
      3. `cwd()` -- the documented fallback, and the ONLY thing this function did before
         B72. Reached when neither of the above resolved anything: no session id at all
         (this process was not launched by Claude Code, e.g. a bare terminal run), or a
         session id with no stamp yet (nothing in this session has seen
         `CLAUDE_PROJECT_DIR` so far). Byte-identical to the pre-B72 behaviour in every
         such case -- this function can only ever get MORE accurate than before, never
         less.

    Use `project_root_source()` alongside this when a caller needs to say how the answer
    was reached, not just what it is.
    """
    return _resolve_project_root()[0]


def project_root_source() -> str:
    """Which of `project_root()`'s three sources answered, most recently: `"env"`
    (CLAUDE_PROJECT_DIR set -- fully trustworthy), `"session-stamp"` (this session's own
    prior stamp -- trustworthy: see `project_root()`), or `"cwd"` (neither -- the one
    case still worth a caller flagging, since it is the pre-B72 fallback and the cwd may
    have drifted).

    Recomputes independently rather than caching the paired call's answer: cheap (two
    env reads and, on the stamp path, one small file read) and avoids a second piece of
    state to keep in sync with `project_root()` itself.
    """
    return _resolve_project_root()[1]


def toplevel(path: Path) -> Path | None:
    """The git repo containing `path`, by walking parents for a `.git` entry.

    Lives HERE rather than in `touched_repos.py` (where it was written, v1.25.0) only
    because `dirty_paths` and `unwrapped_commits` below need it and `touched_repos`
    already imports this module -- putting it the other way round is a cycle. The
    re-export there keeps `touched_repos.toplevel` working for its own callers.

    `.git` is checked with `exists()`, not `is_dir()`: in a worktree or a submodule it is
    a FILE holding a gitdir pointer, and `isolation: worktree` -- the mechanism whose
    misconfiguration caused the 2026-08-25 incident in the first place -- produces exactly
    that shape. Requiring a directory would blind this to the case it was built for.

    Returns the NEAREST enclosing repo. That is what makes a file in `~/Projects/foo`
    report `foo` even though `~/Projects` is itself a repo on this machine -- the trap
    `check_repos.py` has to name explicitly when it is handed a path by hand.

    Walking parents is not a micro-optimisation dressed up as a design note: measured
    2026-08-29, it costs nothing over the process spawn (51 ms) where `git rev-parse
    --show-toplevel` costs 80 ms, and the callers below run in hooks that fire on every
    session start. Re-measure before quoting these as current.
    """
    try:
        start = path if path.is_dir() else path.parent
        current = start.resolve()
    except Exception:
        return None
    for _ in range(MAX_WALK):
        try:
            if (current / ".git").exists():
                return current
        except OSError:
            return None
        if current.parent == current:
            return None
        current = current.parent
    return None


def _scope(root: Path) -> tuple[str, ...]:
    """`("--", ".")` when `root` is a SUBDIRECTORY of its repo, `()` when it IS the root.

    THE BUG THIS FIXES (issue #13, reproduced 2026-08-29)
    -----------------------------------------------------
    Every git-derived warning in this plugin runs git with `cwd=root` and reads the
    answer as being about the PROJECT. Git answers about the whole REPOSITORY. Where the
    two differ -- a session opened in any subfolder of a repo -- the warnings are about
    files the session is not touching and cannot act on, on EVERY session. In a throwaway
    repo holding `proj-a` and `proj-b`, working in `proj-a` with only `proj-b` dirty:
    `root: .../proj-a` / `dirty: [' M proj-b/b.txt']`. `unwrapped_commits` fails the same
    way in reverse -- a commit in any folder makes every other folder look unwrapped.

    The empty tuple is not just the fast path, it is the SAFE one: every project the user
    currently works in has root == toplevel, so the git commands there must stay
    byte-identical to what they were before this existed. Every failure mode -- no repo,
    an unresolvable path, an OSError mid-walk -- therefore returns `()` and keeps today's
    behaviour rather than guessing at a scope.

    Scoping and nothing else. Do NOT extend this into deciding which sibling folders are
    "relevant" -- a warning that guesses becomes untrustworthy in the other direction,
    which is the failure it is being fixed to avoid.
    """
    top = toplevel(root)
    if top is None:
        return ()
    try:
        if str(top.resolve()).lower() == str(Path(root).resolve()).lower():
            return ()
    except Exception:
        return ()
    return ("--", ".")


def git(root: Path, *args: str, timeout: int = 10, raw: bool = False) -> str | None:
    """stdout on success, None on failure.

    NOTE the trap this signature exists to avoid: a successful command with empty
    output returns `""` — falsy but NOT None. Never test these results with a bare
    `if not ...`; `git cat-file -e` succeeds with no output, and doing exactly that
    silently disabled the unwrapped-commit check when it was first written (atlas,
    2026-08-08).

    THE ENCODING IS NOT OPTIONAL (2026-09-06). `text=True` with no `encoding=` decodes
    with the LOCALE codec, which on these Windows machines is cp1252. Git output here is
    routinely UTF-8 -- every commit subject in this repo carries an em-dash, `BACKLOG.md`
    is full of middots -- so `git show`/`git log` raised UnicodeDecodeError inside
    subprocess's reader THREAD, which left `r.stdout` as None while `returncode` stayed 0,
    and the caller then crashed on `None.strip()`. Found when B80's `_origin_floor()` read
    `origin/main:BACKLOG.md` on the real repo, having passed every ASCII fixture test.
    `errors="replace"` because a report tool must never be the thing that fails: a mangled
    character is cosmetic, an exception on the session-start path is not.

    `raw=True` keeps LEADING whitespace, and porcelain output needs it. `git status
    --porcelain` prefixes every line with a two-character XY status followed by a space,
    and for an unstaged modification X is a SPACE (" M INBOX.md"). Stripping the whole
    stdout eats that space on the FIRST line only, shifting it one column, so the path
    slice below returned "NBOX.md". Caught 2026-08-21 from a state file written by the
    live hook — a one-character bug that no amount of re-reading the slice would have
    shown, because the slice is correct and its input was not.
    """
    import subprocess                 # deferred: see the note at the top of the file
    try:
        r = subprocess.run(("git", *args), cwd=root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, **NO_WINDOW,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except Exception:
        return None
    if r.returncode != 0 or r.stdout is None:
        return None
    return r.stdout.rstrip("\r\n") if raw else r.stdout.strip()


def dirty_paths(root: Path) -> list[str] | None:
    """Porcelain status lines, minus our own artifacts. None = not a git repo.

    Scoped to `root`'s own subtree when it is not the repo root -- see `_scope`. Paths
    stay REPO-root-relative either way, because that is what porcelain emits and what
    `check_repos.py`'s `ln[3:]` slice expects.
    """
    # `-uall` expands untracked DIRECTORIES into their files. Without it git reports a
    # wholly-untracked `.claude/` as one entry, the per-file ignore below never matches,
    # and the wrap marker this plugin writes becomes a permanent warning about itself in
    # any project whose `.claude/` isn't tracked. Caught 2026-08-21 in the test repo.
    status = git(root, "status", "--porcelain", "-uall", *_scope(root), raw=True)
    if status is None:
        return None
    out = []
    for ln in status.splitlines():
        if not ln.strip():
            continue
        path = ln[3:].strip().strip('"').replace("\\", "/")
        if any(path.endswith(sfx) for sfx in IGNORED_SUFFIXES):
            continue
        out.append(ln.rstrip())
    return out


def uses_wrap_ritual(root: Path) -> bool:
    """True once this project has ever completed a wrap.

    No marker means the project does not use the ritual, and a project that does not
    use it must never be nagged about it — that silence is deliberate and is what makes
    the plugin safe to install everywhere.
    """
    return (root / WRAP_MARKER_REL).is_file()


def unwrapped_commits(root: Path) -> int | None:
    """Commits made since the last wrap, or None if unknowable.

    The load-bearing check. A clean tree is indistinguishable from a finished session,
    and the parts that silently get skipped when a session commits-but-never-wraps are
    precisely the wrap-only ones: NEXT.md, the briefs, doc timestamps, the memory pass.

    Counts only commits touching `root`'s subtree when it is not the repo root -- see
    `_scope`. `.claude/.last_wrap` is already per-root, so per-folder wrap markers start
    working the moment the counting is scoped; nothing about the marker needed changing.
    """
    try:
        wrapped_at = (root / WRAP_MARKER_REL).read_text(encoding="utf-8").split()[0]
    except (OSError, IndexError):
        return None
    if git(root, "cat-file", "-e", f"{wrapped_at}^{{commit}}") is None:
        return None                      # marker points at a rewritten/absent commit
    count = git(root, "rev-list", "--count", f"{wrapped_at}..HEAD", *_scope(root))
    return int(count) if count and count.isdigit() else None


def last_commit_is_wrap_shaped(root: Path) -> bool:
    """Best-effort guess at whether HEAD looks like a wrap commit."""
    subject = git(root, "log", "-1", "--format=%s")
    if subject and "wrap" in subject.lower():
        return True
    touched = git(root, "show", "--stat=200", "--name-only", "--format=", "-1")
    if not touched:
        return False
    return any(f.strip() in WRAP_TOUCHED_FILES for f in touched.splitlines())


def wrap_command(root: Path) -> str:
    """The command to name in a warning. Detect, do not configure.

    A project's OWN wrap wins: it does everything the plugin's does and more (rev
    numbering, wiring checks, doc timestamps in atlas's case). Reading the
    filesystem keeps this deterministic with no per-project setting to forget, and it
    degrades to the plugin's command in a repo that has never heard of atlas.

    If a project ever ships a wrap skill under a third name this returns the wrong
    string — accepted: the failure mode is a slightly wrong command name inside a
    warning, not a broken hook.
    """
    for name in ("wrap-session", "wrap"):
        if (root / ".claude" / "skills" / name / "SKILL.md").is_file():
            return f"/{name}"
    return "/cairn:wrap"


def state_dir(root: Path) -> Path | None:
    """Per-project state directory, OUTSIDE the repo. None if nowhere is writable."""
    import tempfile                   # deferred: see the note at the top of the file
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    slug = "%s-%s" % (
        "".join(c if c.isalnum() or c in "-_" else "-" for c in root.name)[:32] or "project",
        hashlib.sha1(str(root.resolve()).lower().encode("utf-8")).hexdigest()[:10],
    )
    for candidate in (Path(base) / "reentry-state" / slug,
                      Path(tempfile.gettempdir()) / "reentry-state" / slug):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    return None
