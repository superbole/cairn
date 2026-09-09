#!/usr/bin/env python3
"""Reconcile `BACKLOG.md` with the project's issue host. Run by `/cairn:wrap`, never by a hook.

`BACKLOG.md` is the backlog (see `hooks/backlog_file.py` for why the inversion happened).
The issue host is the copy that reaches their phone, survives a lost machine, and lets other
people file work. This script is the bridge, and it runs where a human is watching — unlike
the session-start path, it is allowed to be slow and allowed to print.

**GitHub AND GitLab, since v1.34.0** (issue #11). Everything host-specific lives in
`hooks/issue_host.py`; this file has no `gh` or `glab` in it and does not know which one ran.
The host is detected from the git remote, so a work repo on `git2.example-corp.net` syncs exactly
as `agent-reentry` does on `github.com` — before this, the whole work side of the portfolio was
permanently outside the sync layer while reporting, correctly, that nothing was lost.

WHAT IT DOES, ALL DERIVED FROM THE FILE — there is no outbox to keep in step:

  item with no `issue #N`      → create the issue, write the number back into the file
  item marked `closed`         → close the issue, then drop the item from the file
  open issue not in the file   → append it as an item, marked `inbound`
  every synced item            → ensure `backlog` + `afk`/`hitl` labels match the file

Derivation is the whole design. An explicit queue of pending mutations is one more thing
that can drift from reality, and the state it would record is already written in the file
in a form they can read on a phone.

OFFLINE IS NOT AN ERROR. No CLI, not authenticated, no remote, no network: print one line
and exit 0. The wrap continues, `BACKLOG.md` is already written, and the next wrap on a
connected machine pushes everything at once. A wrap must never fail over the backlog —
that rule predates this file and is the reason the local layer now exists at all.

DRY RUN by default in one direction only: `--pull` never deletes local items, and nothing
here ever closes an issue that the file does not say is closed.

FLAGS GO THROUGH `argparse`, AND THAT IS A SAFETY PROPERTY, NOT TIDINESS. This script used to
read `sys.argv` by hand, so an unrecognised flag fell straight through to the default -- the
REAL sync. Two agents ran `--help` on 2026-08-30 expecting usage text and pushed issue bodies
to GitHub instead: an outward-facing write nobody chose. `argparse` gives `--help` for free and
turns an unknown flag into exit 2 before a single host call. `--dry-run` is the other half of
the same fix: a way to ask what a sync WOULD do. It makes read-only calls -- it cannot report a
drifted body without reading the remote one -- and no write of any kind, local or remote.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hooks"))

try:
    import backlog_file
    import issue_host
    from reentry_state import project_root
except Exception as exc:                                    # pragma: no cover
    print(f"backlog sync skipped: cannot import the plugin's own modules ({exc})")
    sys.exit(0)

try:                                 # same guard as label_backlog.py: the log lines carry
    sys.stdout.reconfigure(encoding="utf-8")   # "·" and "—", which a cp1252 console mangles
except Exception:
    pass


def _body(it: dict) -> str:
    """The issue body. Carries the fields the Queue needs, so a pull can requeue it."""
    head = []
    if it.get("model"):
        head.append(f"**{it['model']}**")
    if it.get("effort"):
        head.append(f"effort **{it['effort']}**")
    if it.get("attend"):
        head.append(f"**{it['attend']}/{it['mode']}**" if it.get("mode") else f"**{it['attend']}**")
    lead = " · ".join(head)
    text = (it.get("text") or "").strip()
    tail = f"\n\n_Synced from `BACKLOG.md` (item B{it['n']}) by the reentry plugin._"
    return (lead + "\n\n" + text).strip() + tail


def _labels_for(it: dict) -> list[str]:
    out = ["backlog"]
    att = (it.get("attend") or "").upper()
    if att in ("AFK", "HITL"):
        out.append(att.lower())
    return out


def _norm_text(s: str) -> str:
    """Line endings and trailing space are not a difference worth a round trip to the host."""
    return "\n".join(ln.rstrip() for ln in (s or "").replace("\r\n", "\n").strip().splitlines())


def list_issues(host) -> dict[int, dict] | None:
    """Open issues by number, or None if the host could not be reached.

    Fetched ONCE per sync and shared by `push` and `pull`. `push` needs it to answer a question
    it could not previously ask — "is the copy on the host still what the file says?"

    The dicts are `issue_host`'s NORMALISED shape — flat `author`, `labels` as plain strings —
    so nothing below this line depends on which provider answered.
    """
    issues, err = host.list_issues()
    if issues is None:
        return None
    return {i["number"]: i for i in issues if i.get("number")}


def known_issue_numbers(host) -> set[int] | None:
    """Every issue number on the host, ANY state — one extra `issue list` call, not one per item.

    WHY (B37). The sync treats a claimed ``issue `#N` `` as proof #N exists and skips filing —
    nothing ever checked the number against the remote, so a hand-written or invented one
    silently suppressed the filing it was meant to record. Hit live: `issue #36` written before
    any issue existed; the sync reported "16 pullable ... 1 change(s)" and filed nothing, a
    clean success line over a no-op.

    `list_issues()` above is OPEN issues only (that is what `pull()` needs), so it cannot tell
    "claims a closed issue" from "claims one that never existed" — this asks once, across every
    state, purely to answer "does this number exist at all". None means the host could not be
    reached for this second call; the caller must skip the check rather than read absence as
    proof of a bogus number.

    `limit=None` (B82, 2026-09-05): this used to fall through to `list_issues`' default
    `limit=100`, so every issue below the newest hundred silently fell out of "known" and was
    reported as not existing "in ANY state". Measured on `atlas`: 137 issues total, only the
    newest 100 seen, 31 real items wrongly flagged bogus (30 false, 1 real) — a wolf-crying
    check is worse than no check. `limit=None` means every backend pages until it is genuinely
    exhausted, rather than swapping in a bigger number the repo would just as surely outgrow.
    """
    issues, err = host.list_issues(state="all", limit=None)
    if issues is None:
        return None
    return {i["number"] for i in issues if i.get("number")}


def bogus_issue_report(items: list[dict], known: set[int] | None) -> list[str]:
    """Log lines for B37: an item claiming an issue number that does not exist, in ANY state.

    `known=None` means the host could not be asked (the extra listing failed or was
    unreachable) — absence of proof is not proof of a bogus number, so nothing is reported.
    Excludes `closed` items: they are either gated by B45 already or on their way out of the
    file regardless, and the harm B37 guards against — a claimed number silently suppressing a
    NEW filing — only applies to an open one.
    """
    if known is None:
        return []
    bogus = [it for it in items
             if it.get("issue") and not it.get("closed") and it["issue"] not in known]
    if not bogus:
        return []
    out = [f"backlog: {len(bogus)} item(s) claim an issue number not found on the issue host "
           f"(B37) — filing stays suppressed for these until the number is fixed or cleared:"]
    for it in bogus:
        out.append(f"  · B{it['n']}. {it['title'][:50]} — claims issue #{it['issue']}")
    return out


# B92: paths this repo already treats as HISTORY rather than STATUS. History RECORDS that an
# item existed (`CHANGELOG.md`, an incident log, a decision record, an archived review dossier);
# status ASSERTS an item is still LIVE (`NEXT.md`, a brief, a `blocked by Bn` line). Only the
# second kind is worth a warning. Measured: closing B87 hit 22 lines here, 0 of them a real
# stale pointer (the CHANGELOG.md entry, `skills/wrap/references/incidents.md`,
# `docs/decisions.md`, a design doc whose whole subject was B87, an archived review dossier, and
# NEXT.md's own "B87 shipped" footer note); closing B99 hit 6, also 0/6, and the exact same run
# minutes later hit 11 once the CHANGELOG.md entry recording the close existed — the warning grew
# in proportion to how well the close was documented. The plugin's own `rules/CLAUDE.md` already
# draws this exact line (CHANGELOG.md = history, NEXT.md = status); this only makes the scanner
# agree with a split the repo already keeps by hand. Crude, on purpose — see the module-level
# reasoning next to `push_check.py`'s `NOTHING_TO_HOLD` for why a rule that can be checked beats
# one that has to be guessed: a wrong guess about prose would silence a REAL stale pointer, which
# is the original B76 case (`NEXT.md`'s D3 pointing at a dropped B46) this mechanism exists for.
_HISTORICAL_EXACT = ("changelog.md", "docs/decisions.md")

# B92's SECOND discriminator — inside a file that IS scanned, a line that itself says the id is
# done is a citation, not a pointer. Deliberately NOT the primary mechanism (that is the path
# rule above): this only ever SUPPRESSES a hit inside an already-scanned file, on an exact,
# checkable token — never the reverse, and never applied to decide which FILES get scanned.
# Kept to the three words the item explicitly names; guessing at synonyms is exactly the
# prose-sniffing this file was told not to do.
_CLOSING_TOKEN_RE = re.compile(r"\b(closed|shipped|dropped)\b", re.IGNORECASE)


# `.../skills/<any-one-segment>/references/incidents.md`, at ANY depth — in THIS repo that is
# `plugins/cairn/skills/{next,wrap}/references/incidents.md`, six segments from the project
# root, not the four a root-level `skills/` folder would need. End-anchored so it only ever
# matches the exact incidents.md leaf, never a sibling like `incidents.md.bak` or a deeper file
# that merely sits under a `references` directory.
_INCIDENTS_LOG_RE = re.compile(r"(^|/)skills/[^/]+/references/incidents\.md$")


def _is_historical_path(rel: str) -> bool:
    """True for a repo-relative path (forward slashes, any case) that is HISTORY, not status.

    Exact matches: `CHANGELOG.md`, `docs/decisions.md`. Prefix match: anything under
    `docs/review/` (an archived dossier included — `docs/review/archive/...` still starts with
    `docs/review/`). Shape match: `.../skills/<any>/references/incidents.md` at any nesting
    depth — this plugin's own two incident logs, and the same shape a project that copies the
    pattern would use.
    """
    rel = rel.replace("\\", "/").lower()
    if rel in _HISTORICAL_EXACT:
        return True
    if rel.startswith("docs/review/"):
        return True
    if _INCIDENTS_LOG_RE.search(rel):
        return True
    return False


def orphaned_pointers_report(root: Path, dropped_ids: set[int]) -> list[str]:
    """Log lines for B76: warn about anything else in the repo still pointing at an id this
    sync is about to drop from `BACKLOG.md`.

    WHY (B76, sibling of B75). A dropped closed item vanishes from the one file `parse()`
    reads, but nothing else in the repo that named it gets touched — and those references
    (`NEXT.md`'s `## Decisions`, its footer, a brief, a `blocked by Bn` line) are exactly what a
    re-entering session reads FIRST. Live instance, 2026-09-05: `NEXT.md`'s D3 still pointed
    `→ BACKLOG.md B46` hours after B46 was dropped, and a session reading it concluded the sync
    had deleted seven OPEN items and was three minutes from restoring 351 lines of correctly
    closed work. The stale pointer was the whole reason the wrong conclusion looked evidenced.

    B92: a raw grep for the id treats a `CHANGELOG.md` entry the same as a live `NEXT.md`
    pointer, and in practice almost every hit is the former — see `_is_historical_path`'s
    docstring for the measured counts. Scans `NEXT.md`, `BACKLOG.md`, `README.md`,
    `briefs/**/*.md` and `docs/**/*.md`, MINUS `_is_historical_path` (which drops
    `CHANGELOG.md`, `docs/decisions.md`, `docs/review/**` and `skills/*/references/incidents.md`
    from the scan entirely), then drops any remaining line that itself carries a
    `_CLOSING_TOKEN_RE` hit (a sentence that already says the id shipped/closed/dropped).
    `BACKLOG.md` gets one extra exemption: the heading line of the item BEING dropped is not a
    pointer TO it, it IS it — still on disk because this report runs before
    `backlog_file.write()` regenerates the file — so only that one line is skipped; a
    DIFFERENT item's `blocked by Bn` line is exactly the live case worth keeping BACKLOG.md in
    the scan for.

    REPORTS, NEVER REWRITES — same reasoning as B23: a tool editing prose it does not
    understand is a much larger blast radius than a line telling a human where to look.
    """
    if not dropped_ids:
        return []
    root = Path(root)
    candidates: list[Path] = []
    for name in ("NEXT.md", "CHANGELOG.md", "BACKLOG.md", "README.md"):
        p = root / name
        if p.is_file():
            candidates.append(p)
    for sub in ("docs", "briefs"):
        d = root / sub
        if d.is_dir():
            candidates += sorted(p for p in d.rglob("*.md") if p.is_file())

    hits: list[str] = []
    for p in candidates:
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            rel = str(p).replace("\\", "/")
        if _is_historical_path(rel):
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        is_backlog = rel.lower() == "backlog.md"
        for i, ln in enumerate(lines, start=1):
            for n in sorted(dropped_ids):
                if not re.search(rf"\bB{n}\b", ln):
                    continue
                if is_backlog and re.match(rf"^#+\s*B{n}\b", ln.strip()):
                    continue                             # the dropped item's own heading
                if _CLOSING_TOKEN_RE.search(ln):
                    continue                             # a citation, not a live pointer
                hits.append(f"  · {rel}:{i} — still names B{n}, which this sync is about "
                            f"to drop: {ln.strip()[:80]}")
    if not hits:
        return []
    out = [f"backlog: {len(hits)} reference(s) elsewhere still name an item this sync is about "
           f"to drop (B76) — they will point at nothing once BACKLOG.md is rewritten; fix them "
           f"by hand:"]
    out += hits
    return out


def _update_body(host, it: dict, remote: dict, dry: bool = False) -> str | None:
    """Re-push title/body when the file has moved on. One log line, or None if in step.

    WHY THIS EXISTS (issue #9, 2026-08-29). `gh issue create --body` ran once and nothing ever
    wrote a body again — only `--add-label`. So the moment an item's text changed in `BACKLOG.md`
    the remote copy went stale SILENTLY, and the sync reported "no changes" because it compared
    nothing but labels. Caught within an hour of filing B8: the file was corrected, the sync ran
    clean, and the issue still carried the superseded framing.

    That contradicts the claim the whole v1.18.0 inversion rests on — the file is the writer and
    the host is the copy. A copy that only ever reflects the first draft is worse than no copy,
    because the issue tracker is what they read on their phone, which is exactly when they cannot see
    the file.

    **Never touches an issue somebody else filed.** An `inbound` item's `text` IS the remote body,
    so re-rendering it through `_body()` would wrap another person's issue in our fields header and
    push it back over theirs.
    """
    if it.get("inbound"):
        return None
    want_title, want_body = it["title"], _body(it)
    same_title = _norm_text(remote.get("title") or "") == _norm_text(want_title)
    same_body = _norm_text(remote.get("body") or "") == _norm_text(want_body)
    if same_title and same_body:
        return None

    what = "title + body" if not (same_title or same_body) else (
        "title" if not same_title else "body")
    if dry:
        return f"  · would update #{it['issue']} {what} — B{it['n']} {it['title'][:44]}"

    ok, err = host.update(it["issue"],
                          title="" if same_title else want_title,
                          body="" if same_body else want_body)
    if not ok:
        return f"  ! B{it['n']} — could not update #{it['issue']}: {err} (file is still right)"
    return f"  · updated #{it['issue']} {what} — B{it['n']} {it['title'][:44]}"


def push(host, items: list[dict], root: Path, repo: str,
         remote: dict[int, dict] | None = None,
         closed: set[int] | None = None,
         dry: bool = False) -> list[str]:
    """Create, close, label and re-body. Mutates `items` in place; the caller writes the file.

    Adds every issue number it CLOSES to `closed`, which `pull` must then ignore. Sharing one
    issue listing between the two halves (v1.21.1) made that mandatory: the listing is fetched
    before anything closes, so a just-closed issue is still "open" in it AND no longer in `items`,
    which is exactly `pull`'s definition of an issue to bring back in. The first run after the
    v1.21.1 change closed #9 and immediately re-filed it as B10.

    B45: closing an item deletes it from BOTH copies, so `CHANGELOG.md` becomes the only
    surviving record — and nothing previously checked one was written. Gated by
    `backlog_file.changelog_covers()` BEFORE the close-and-drop, not just before the drop: an
    issue closed on the host with no local record left is the same loss the file-side check
    exists to prevent, just moved one step earlier.
    """
    log: list[str] = []
    keep: list[dict] = []
    for it in items:
        if it.get("closed"):
            status = backlog_file.changelog_status(root, it)
            if status == "uncovered":
                log.append(f"  · kept B{it['n']} — closed {it['closed']} but no CHANGELOG.md "
                           f"entry since then names it (B45); add one, or the sync will keep "
                           f"deferring this")
                keep.append(it)
                continue
            if status == "no-changelog":
                # NOT the same as "uncovered", and blocking here would be a permanent stall
                # rather than a safety measure: 6 of the 9 tracked projects have no
                # CHANGELOG.md at all (measured 2026-09-05), so the entry this gate waits for
                # is one nobody is ever going to write. Say what cannot be verified, and let
                # the close proceed — which is exactly the behaviour before B45 shipped.
                #
                # B83: "no-changelog" collapses two different facts — no file at all, vs. a
                # real file with no heading `_CHANGELOG_DATE_RE` recognises (e.g. `atlas`'s
                # `### rev N — YYYY-MM-DD — ...` headings, before that pattern was broadened).
                # Naming a MISSING file when the real problem was an unparsed one reads as "the
                # tool is broken" and stops a reader from looking further (observed twice) — so
                # ask which one this actually is before picking the wording.
                reason = backlog_file._changelog_unreadable_reason(root)
                if reason == "unparseable":
                    log.append(f"  · B{it['n']} closed {it['closed']} — this project HAS a "
                               f"CHANGELOG.md, but no heading in it matches a dated entry "
                               f"(B83), so the record could NOT be verified (B45). "
                               f"Closing anyway; the item is about to exist nowhere.")
                else:
                    log.append(f"  · B{it['n']} closed {it['closed']} — this project has no "
                               f"CHANGELOG.md, so the record could NOT be verified (B45). "
                               f"Closing anyway; the item is about to exist nowhere.")
            if it.get("issue"):
                if dry:
                    log.append(f"  · would close #{it['issue']} — "
                               f"B{it['n']} {it['title'][:50]}")
                    if closed is not None:
                        closed.add(it["issue"])
                    continue
                ok, err = host.close(it["issue"],
                                     f"Done {it['closed']} — see CHANGELOG.md.")
                if not ok:
                    log.append(f"  ! B{it['n']} — could not close #{it['issue']}: {err} (kept)")
                    keep.append(it)
                    continue
                log.append(f"  · closed #{it['issue']} — B{it['n']} {it['title'][:50]}")
                if closed is not None:
                    closed.add(it["issue"])
            else:
                log.append(f"  · {'would drop' if dry else 'dropped'} B{it['n']} "
                           f"(closed, never synced)")
            continue                                     # dropped from the file entirely
        if not it.get("issue"):
            if dry:
                log.append(f"  · would file a new issue — B{it['n']} {it['title'][:50]}")
            else:
                num, err = host.create(it["title"], _body(it), _labels_for(it))
                if num is None:
                    log.append(f"  ! B{it['n']} — could not file: {err} (stays local)")
                else:
                    it["issue"] = num
                    log.append(f"  · filed #{num} — B{it['n']} {it['title'][:50]}")
        else:
            want = _labels_for(it)
            if dry:
                # Only reportable when the remote listing actually carries this issue --
                # an empty label set on a missing issue would read as "all of them missing".
                rem = (remote or {}).get(it["issue"])
                if rem is not None:
                    have = {str(l).lower() for l in (rem.get("labels") or [])}
                    gap = [lb for lb in want if lb.lower() not in have]
                    if gap:
                        log.append(f"  · would add label(s) {', '.join(gap)} to "
                                   f"#{it['issue']} — B{it['n']}")
            else:
                host.add_labels(it["issue"], want)
            if remote is not None and it["issue"] in remote:
                line = _update_body(host, it, remote[it["issue"]], dry)
                if line:
                    log.append(line)
        keep.append(it)
    items[:] = keep
    return log


def pull(root: Path, items: list[dict], owner: str,
         remote: dict[int, dict] | None = None,
         skip: set[int] | None = None,
         dry: bool = False) -> list[str]:
    """Bring in issues that are not in the file. NEVER deletes a local item.

    `skip` is what `push` just closed — see its docstring for why that cannot be inferred here.
    """
    if remote is None:
        return ["  ! could not list issues"]
    raw = list(remote.values())

    known = {i["issue"] for i in items if i.get("issue")} | (skip or set())
    log: list[str] = []
    n = backlog_file.next_id(root)
    for iss in raw:
        num = iss.get("number")
        if num in known:
            continue
        names = {str(l).lower() for l in (iss.get("labels") or [])}
        author = iss.get("author") or ""
        inbound = bool(owner) and author.lower() != owner.lower()
        items.append({
            "n": n,
            "title": iss.get("title") or f"issue #{num}",
            "model": None,
            "effort": None,
            "attend": "AFK" if "afk" in names else ("HITL" if "hitl" in names else None),
            "mode": None,
            "added": date.today().isoformat(),
            "issue": num,
            "queued": False,
            "inbound": inbound,
            "closed": None,
            "text": (iss.get("body") or "").strip(),
            "body": [],
        })
        log.append(f"  · {'would pull' if dry else 'pulled'} #{num} into B{n}"
                   + (f" — filed by @{author}, NOT by you" if inbound else ""))
        n += 1
    return log


def _existing_heading_project(root: Path) -> str:
    """The project name already in `BACKLOG.md`'s `# BACKLOG — <name>` heading, or `""` for a
    file with no heading (or no file) yet.

    B84, first half of the fix: the file is the writer and this sync is a one-directional
    mirror onto the issue host, so the heading is not this script's line to change once it
    already says something. Reading it back before `write()` regenerates the file is how "do
    not rewrite the heading" is honoured without touching `backlog_file.py`'s renderer, which
    this lane does not own.
    """
    try:
        first = backlog_file.path(root).read_text(encoding="utf-8").splitlines()[0]
    except Exception:
        return ""
    m = re.match(r"^#\s*BACKLOG\s*—\s*(.+?)\s*$", first)
    return m.group(1) if m else ""


def _project_name(root: Path) -> str:
    """A project name for a BRAND NEW `BACKLOG.md` heading — never the checkout directory's
    own name, which is a worktree's branch label, not the project (B84).

    `backlog_file.write()` falls back to `Path(root).name` when handed no project name, which
    is correct at a normal checkout but wrong from a git worktree: run from
    `~/atlas-worktrees/decisions`, `Path(root).name` is `decisions`, not `atlas`, and the
    2026-09-05 sync wrote exactly that into the heading. `git rev-parse --git-common-dir`
    always resolves to the MAIN checkout's `.git`, worktree or not — its parent is the real
    project directory. Falls back to the old `Path(root).name` behaviour if git cannot answer
    (never worse than before this fix), and only runs at all when `_existing_heading_project`
    above found nothing to preserve.
    """
    common = issue_host._git(Path(root), "rev-parse", "--git-common-dir")
    if common:
        common_path = Path(common)
        if not common_path.is_absolute():
            common_path = (Path(root) / common_path).resolve()
        if common_path.parent.name:
            return common_path.parent.name
    return Path(root).name


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse before ANYTHING else happens. `--help` and a bad flag must both exit here.

    `argparse` raises `SystemExit`, which is a `BaseException` — so it sails straight past
    the `except Exception` at the bottom of this file that exists to stop a wrap failing
    over the backlog. That guard must never swallow a usage error into a silent exit 0.
    """
    p = argparse.ArgumentParser(
        prog="sync_backlog.py",
        description="Reconcile BACKLOG.md with the project's issue host (GitHub via `gh`, "
                    "GitLab via `glab`). Run by /cairn:wrap.",
        epilog="With neither --push nor --pull, both halves run. The host is detected from "
               "the git remote. Offline is not an error: one line, exit 0, and the next "
               "connected wrap pushes the lot.")
    p.add_argument("--push", action="store_true",
                   help="file, close, label and re-body issues from BACKLOG.md")
    p.add_argument("--pull", action="store_true",
                   help="append open issues BACKLOG.md has never seen (never deletes)")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would change; makes read-only host calls and no write, "
                        "local or remote")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    dry = args.dry_run
    root = project_root() if project_root else Path.cwd()
    do_push = args.push or not args.pull
    do_pull = args.pull or not args.push

    if not backlog_file.exists(root):
        print("backlog sync skipped: no BACKLOG.md in this project.")
        return 0

    # PRE-FLIGHT, BEFORE A SINGLE HOST CALL. A sync ends by regenerating BACKLOG.md from
    # what it could parse, so a file holding item headings this parser cannot read must not
    # be synced at all — not even the push half, which would file issues for a subset and
    # then be unable to write the numbers back. Found 2026-09-03 in `~/Projects/workspace`:
    # 13 headings written as `## 12.` instead of `## B12.`, none of them parsed, 206 lines
    # one write away from being replaced by 16 pulled issues. That repo had never synced
    # because `gh` is not installed on that machine, so switching the GitLab backend on is
    # exactly what would have armed it.
    stranded = backlog_file.unparsed_headings(root)
    if stranded:
        print(f"backlog sync REFUSED: {len(stranded)} item heading(s) in BACKLOG.md are not "
              f"in the `## Bn. Title` shape this parser reads, and a sync rewrites the whole "
              f"file — it would delete them. Nothing was read or written. Fix the headings "
              f"(or ask an agent to), then re-run:")
        for ln in stranded[:8]:
            print(f"  · {ln}")
        if len(stranded) > 8:
            print(f"  · … {len(stranded) - 8} more")
        return 0

    items = backlog_file.parse(root)

    # A WARNING, not a looser `_CLOSED_RE` (B30). An undated `closed` marker parses as
    # `closed=None` — indistinguishable from an item that was never closed — so it would
    # otherwise stay open on the host forever with BACKLOG.md insisting it is done. This has
    # to run whether or not a host is reachable: it is a local-file problem, and the file is
    # what they read regardless of connectivity.
    undated = backlog_file.undated_closed_items(items)
    if undated:
        print(f"backlog: {len(undated)} item(s) say `closed` with NO date (B30) — read as "
              f"still OPEN until a date is added:")
        for it in undated:
            print(f"  · B{it['n']}. {it['title'][:60]}")

    host, err = issue_host.detect(root)
    repo = owner = ""
    if host is not None:
        repo, owner, err = host.repo()
    if not repo:
        pull_n, afk, queued = backlog_file.counts(root)
        # "the next wrap where the CLI works will push them" is TRUE for a transient failure
        # (offline, not authenticated, CLI not installed) and FALSE on a host nobody has
        # written a backend for — an unsupported remote never becomes a supported one by
        # waiting. Saying it anyway left the wrap sounding like the sync was pending when
        # nothing would ever pick it up (2026-08-29). `issue_host.is_permanent` is that
        # distinction, generalised past GitHub in v1.34.0.
        # "…until that changes", not "never": every permanent case is permanent until HE does
        # something (add a remote, enable issues, get a backend written), and none of them is
        # fixed by another wrap. That is the distinction the line has to carry — a wrap that
        # sounds like a sync is pending when nothing will pick it up is the 2026-08-29 bug.
        outlook = ("nothing will sync it until that changes — the file IS the backlog and "
                   "loses nothing" if issue_host.is_permanent(err) else
                   "the next wrap where the CLI works will push them")
        where = f" to {host.name}" if host is not None else ""
        print(f"backlog sync{where} skipped ({err or 'no issue host'}) — BACKLOG.md is "
              f"written and holds {pull_n} pullable item(s). Nothing is lost; {outlook}.")
        return 0

    log: list[str] = []
    # ONE listing, shared by both halves: push needs it to notice a body that has drifted from
    # the file (issue #9), and pull needs it to find issues the file has never seen. None means
    # the host was unreachable -- push still creates/closes/labels, pull says so and changes
    # nothing.
    remote = list_issues(host)

    # B37: a claimed `issue #N` is trusted as proof N exists and nothing files in its place --
    # so a hand-written or invented number silently suppresses the filing it was meant to
    # record, and the run reports a clean success line over what was actually a no-op. ONE
    # extra `issue list` call for the lot, not one per item; None means it could not be asked
    # (host unreachable for this second call) and the check is skipped rather than treating
    # absence as proof of a bogus number.
    known = known_issue_numbers(host)
    for ln in bogus_issue_report(items, known):
        print(ln)

    just_closed: set[int] = set()
    ids_before = {it["n"] for it in items}
    if do_push:
        log += push(host, items, root, repo, remote, just_closed, dry)
    if do_pull:
        log += pull(root, items, owner, remote, just_closed, dry)

    # B76: whatever `push()` just decided to drop -- computed as a plain before/after set
    # difference so this works identically whether the drop was real or (in `--dry-run`) only
    # simulated in `items` -- is about to disappear from the one file `parse()` reads. Anything
    # elsewhere that still names it becomes a pointer to nothing; report it before the write
    # that would otherwise make the mismatch silent.
    dropped_ids = ids_before - {it["n"] for it in items}
    for ln in orphaned_pointers_report(root, dropped_ids):
        print(ln)

    if dry:
        print(f"DRY RUN against {repo} on {host.name} — nothing was written, "
              f"here or on {host.name}.")
        for ln in log or ["  · no changes"]:
            print(ln)
        return 0

    try:
        # B84: never `Path(root).name` -- in a git worktree that is the worktree's OWN
        # directory name (a branch label, e.g. `decisions`), not the project. Keep whatever
        # heading is already there; only a brand-new file falls through to a name derived from
        # the real repo, never the checkout directory.
        project = _existing_heading_project(root) or _project_name(root)
        backlog_file.write(root, items, project)
    except Exception as exc:
        print(f"backlog sync: {type(exc).__name__} writing BACKLOG.md — nothing was lost "
              f"on {host.name}, but re-check the file.")
        return 0

    pull_n, afk, queued = backlog_file.counts(root)
    print(f"backlog synced with {repo} ({host.name}): {pull_n} pullable"
          + (f", {afk} AFK" if afk else "")
          + (f", {queued} queued" if queued else "")
          + (f", {len(log)} change(s)" if log else ", no changes") + ".")
    for ln in log:
        print(ln)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                # a wrap must never fail over the backlog
        print(f"backlog sync skipped: {type(exc).__name__}")
        sys.exit(0)
