#!/usr/bin/env python3
"""What did I work on this week, and for how long — from the session transcripts.

    python plugins/cairn/tools/timesheet.py                    # this week, Mon-Sun
    python plugins/cairn/tools/timesheet.py --last-week --sessions
    python plugins/cairn/tools/timesheet.py --attribution exclusive
    python plugins/cairn/tools/timesheet.py --projects //org-laptop1/c$/Users/example/.claude/projects
    python plugins/cairn/tools/timesheet.py --days 14 --csv

    # two machines with no network path between them (B66) -- run on EACH machine first:
    python plugins/cairn/tools/timesheet_sync.py
    # then, on either machine, once OneDrive has caught up:
    python plugins/cairn/tools/timesheet.py --projects "<OneDrive>/ReentryTimesheetSync/LAPTOP2/projects"

WHY TRANSCRIPTS AND NOT `CHANGELOG.md`
--------------------------------------
`CHANGELOG.md` looked like the obvious source and is the wrong one, twice over. Its entries are
keyed to plugin **versions**, not sessions, so several land on one date with nothing separating
them in time; and a session that ships no version bump — triage, a review, a wrap that only moved
the queue — leaves no entry at all. Git commit times are the next-best fallback and still miss
everything before the first commit and after the last.

Session transcripts carry a per-message `timestamp`, a `cwd`, and the session's `custom-title`.
That is the whole timesheet already: **no new capture was needed, and none was added.**

PARALLEL WORK IS REAL WORK  (v1.22.0, after a correction)
---------------------------------------------------------
v1.21.0 summed each session independently, so two live at once produced two minutes per minute of
wall clock, and this file called that "double-counting". The user's correction, 2026-08-29: *"If the
agent/computer is busy and I cannot be working on that computer then it is surely still billable
time? If I'm handling two workloads simultaneously… surely I personally should be able to claim
that as productive?"*

They are right, and the earlier framing silently assumed a wall-clock billing model they had never
stated. **Which model applies is a billing policy, not a property of the data**, so this tool
reports both and never picks:

  --attribution parallel   (DEFAULT) every session accrues in full. Per-project totals may exceed
                           the wall clock, which is the correct answer for per-project effort.
  --attribution exclusive  an overlapping stretch goes to whichever project has the most recent
                           USER message before it, so a day can never exceed real elapsed time.
                           For an engagement billed against a clock.

**The overlap is printed either way.** It is the one number that must never be hidden: it says how
much of the week was parallel, and it is what would show up as two clients billed for one hour.

WHAT COUNTS AS TIME  (the idle threshold is asymmetric on purpose)
------------------------------------------------------------------
v1.21.0 dropped every gap over `--idle`, which under-counted the exact case above: a long agent run
emits records minutes apart and its gaps were discarded as if they had gone for lunch. A gap is
classified by **what ends it**:

  gap ending in a USER record    they were the one being waited for. Capped by `--idle` (default 10
                                 min); a longer one is a break and counts as nothing.
  gap ending in an AGENT record  the machine was mid-work producing it. Counts in FULL, up to
                                 `--max-run`.

`--max-run` defaults to 5 minutes, and that is a MEASURED number, not a guess. Over 67,738
agent-terminated gaps in this machine's transcripts on 2026-08-29: median 0.4s, p90 10.8s, p99
246s. Past about 15 minutes the tail is not work at all — it is a session being resumed hours or
days later, where the first record after the gap happens to be a hook or an assistant message
rather than a prompt. Leaving the cap at 60 minutes admitted 109 hours of that tail in one week;
above an hour it was 813. A genuinely long AFK run is unaffected, because it is made of thousands
of SHORT gaps as tool calls and output stream — the cap only ever truncates a single silent gap.

`attended` and `unattended` are then reported as separate COLUMNS, never as a deduction — a long
agent-only run stays in the total and is labelled, so they can decide per invoice.

TWO MACHINES
------------
Transcripts live under the Claude config dir of the machine that ran the session, so this sees one
machine by default. `--projects PATH` (repeatable) adds another machine's directory — a mount, or a
synced copy. Sessions are deduped by id, so a two-way synced folder is safe. Cursor writes no
Claude Code transcript at all, so the work machines remain out of scope.

B66 (2026-09-05): direct SSH between two laptops turned out to be a network-level dead end (see
BACKLOG.md), so the working transport is `timesheet_sync.py` — it copies THIS machine's own
`~/.claude/projects` into a OneDrive folder, and OneDrive's own sync (not this script, and not a
new background mechanism) carries it to the other side. Point `--projects` at the synced copy.

A SYNCED COPY IS NEVER PRESENTED AS CURRENT WITHOUT SAYING SO. A path handed to `--projects` might
be another machine's live mount, or it might be a OneDrive mirror that is hours or days stale — and
a total with no age attached to it is indistinguishable from one that is live. So every `--projects`
root has its newest transcript's mtime checked and printed (`source_notes`, to stderr always, and
into the header of the human report), never only on request. A root with no transcripts at all
prints a warning rather than silently contributing zero.

A segment is attributed to the day it STARTS in, and each day prints its OWN first/last rather than
the session's — an overnight session otherwise printed a reversed `12:17-10:47` under one day.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_IDLE_MIN = 10
DEFAULT_MAX_RUN_MIN = 5
TITLE_WIDTH = 46


def projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")
    return Path(base) / "projects"


# Directories that were RENAMED, and so hold one project's history under two names. A hyphen or
# underscore change is handled by the fold below; a real rename is not, and the transcripts under
# the old name never move — so without this a rename splits a project's hours in two, permanently
# and silently. Add a row when a directory is renamed, in the same change as the rename.
#   `code` → `workspace` and `projects` → `workspace`: 2026-08-29, aligning this laptop with the
#   work machines. The portfolio hub was `~/code`, then `~/Projects`, and is now
#   `~/Projects/workspace` — one project's hours under three directory names. The user's reason is
#   the one that matters here: recognising several names for one portfolio costs memory and
#   attention, which are the scarce things.
PROJECT_ALIASES = {"code": "workspace", "projects": "workspace"}


def project_key(name: str) -> str:
    """The grouping key for a project directory. Display names are chosen separately.

    Folds case and hyphen/underscore, so `atlas` and `atlas` are one project — splitting a
    week's hours across two spellings is exactly the kind of quietly-wrong total a timesheet must
    not produce. Then applies `PROJECT_ALIASES` for directories that were actually renamed.
    """
    key = name.replace("-", "_").casefold()
    return PROJECT_ALIASES.get(key, key)


def _local(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def _is_user_turn(record: dict) -> bool:
    """A real prompt from them — not a tool result, hook payload or subagent turn."""
    if record.get("type") != "user" or record.get("isMeta") or record.get("isSidechain"):
        return False
    return record.get("toolUseResult") is None


def _prompt_text(record: dict) -> str | None:
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    else:
        return None
    text = " ".join(text.split())
    return text if text and not text.startswith(("<", "[Request interrupted")) else None


def read_session(path: Path) -> dict | None:
    """One transcript → {id, project, key, title, events}. None if it holds no usable time.

    `events` is [(when, is_user)] sorted — that flag is what lets `intervals()` tell their thinking
    time from the machine's working time.
    """
    events: list[tuple[datetime, bool]] = []
    title = prompt = cwd = None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue                       # a partially-flushed line is not a reason to give up
        if record.get("type") == "custom-title":
            title = record.get("customTitle") or title
            continue
        cwd = cwd or record.get("cwd")
        when = record.get("timestamp")
        if when:
            local = _local(when)
            if local:
                events.append((local, _is_user_turn(record)))
        if prompt is None and _is_user_turn(record):
            prompt = _prompt_text(record)
    if len(events) < 2:
        return None                        # a session with one event has no duration to report
    events.sort(key=lambda e: e[0])
    project = Path(cwd).name if cwd else path.parent.name
    return {"id": path.stem, "short": path.stem[:8], "project": project,
            "key": project_key(project), "events": events,
            "users": [w for w, u in events if u],
            "title": title or prompt or "(untitled)"}


def _close_run(run: list[tuple[datetime, datetime]], idle: timedelta) -> list[dict]:
    """Classify one agent TURN — everything the machine did between two of their messages.

    Attended/unattended cannot be decided per gap. Genuine agent work is thousands of sub-second
    gaps, every one of them shorter than any sensible idle threshold, so a per-gap test marks a
    three-hour AFK run as attended throughout. The unit that carries the meaning is the whole run
    between their messages: if the machine worked for longer than `idle` without them saying anything,
    they were not watching it, whatever the individual gaps looked like.
    """
    if not run:
        return []
    worked = sum((b - a for a, b in run), timedelta())
    attended = worked <= idle
    return [{"start": a, "end": b, "attended": attended} for a, b in run]


def intervals(session: dict, idle: timedelta, max_run: timedelta) -> list[dict]:
    """The stretches of real time this session accounts for: {start, end, attended}.

    A gap is classified by WHAT ENDS IT — see the module docstring. One ending in a user record was
    them being waited for (capped by `idle`); one ending in an agent record was the machine working
    (counted in full, capped by `max_run`, past which it is a resumed session rather than a run).
    """
    out: list[dict] = []
    run: list[tuple[datetime, datetime]] = []
    for (start, _), (end, end_is_user) in zip(session["events"], session["events"][1:]):
        gap = end - start
        if end_is_user:
            out += _close_run(run, idle)   # their message ends the machine's turn
            run = []
            if gap <= idle:
                out.append({"start": start, "end": end, "attended": True})
        elif gap <= max_run:
            run.append((start, end))
        # a gap over max_run is a resumed session: it ends the run without contributing
        else:
            out += _close_run(run, idle)
            run = []
    return out + _close_run(run, idle)


def collect(roots: list[Path], idle: timedelta, max_run: timedelta,
            only: str | None) -> list[dict]:
    """Every session across every projects directory, deduped by session id."""
    seen: set[str] = set()
    sessions: list[dict] = []
    for root in roots:
        if not root.is_dir():
            continue
        for transcript in sorted(root.glob("*/*.jsonl")):
            session = read_session(transcript)
            if session is None or session["id"] in seen:
                continue                   # a synced folder may hold both machines' copies
            seen.add(session["id"])
            if only and project_key(only) not in session["key"]:
                continue
            session["intervals"] = intervals(session, idle, max_run)
            if session["intervals"]:
                sessions.append(session)
    return sessions


def source_freshness(root: Path) -> datetime | None:
    """The newest transcript mtime under `root` — how recently a SYNCED copy was refreshed.

    None if the directory holds no transcripts at all (sync has never run, or the path is empty).
    This is the number that keeps a synced `--projects` copy from quietly passing as current: see
    the module docstring's TWO MACHINES section and the guard it describes.
    """
    newest = None
    for f in root.glob("*/*.jsonl"):
        try:
            m = datetime.fromtimestamp(f.stat().st_mtime).astimezone()
        except OSError:
            continue
        if newest is None or m > newest:
            newest = m
    return newest


def _age(when: datetime, now: datetime) -> str:
    minutes = max(int((now - when).total_seconds() // 60), 0)
    if minutes < 60:
        return "%dm" % minutes
    hours, mins = divmod(minutes, 60)
    if hours < 48:
        return "%dh%02dm" % (hours, mins)
    return "%dd" % (hours // 24)


def source_notes(extra_roots: list[Path]) -> list[str]:
    """One line per `--projects` root, naming how stale that copy is — never silent, and never
    skipped just because the report is otherwise unremarkable. See `source_freshness`."""
    now = datetime.now().astimezone()
    notes = []
    for root in extra_roots:
        newest = source_freshness(root)
        if newest is None:
            notes.append("  ! %s -- no transcripts found; sync may never have run" % root)
        else:
            notes.append("  synced copy %s -- newest transcript %s ago (%s)"
                          % (root, _age(newest, now), newest.strftime("%Y-%m-%d %H:%M")))
    return notes


# --- attribution ---------------------------------------------------------------------------

def _segments(sessions: list[dict]):
    """Elementary, non-overlapping time segments, each with the sessions live during it.

    A sweep over every interval boundary. Because segments never overlap, summing them IS the
    wall-clock union — which is what makes `exclusive` attribution and the overlap figure possible.
    """
    edges: set[datetime] = set()
    for s in sessions:
        for iv in s["intervals"]:
            edges.add(iv["start"])
            edges.add(iv["end"])
    marks = sorted(edges)
    starts = {s["id"]: [iv["start"] for iv in s["intervals"]] for s in sessions}
    for a, b in zip(marks, marks[1:]):
        live = []
        for s in sessions:
            i = bisect.bisect_right(starts[s["id"]], a)
            if i and s["intervals"][i - 1]["end"] >= b:
                live.append({"session": s, "attended": s["intervals"][i - 1]["attended"]})
        if live:
            yield a, b, live


def _nearest_user(session: dict, when: datetime) -> datetime | None:
    """The last time HE said something in this session before `when`."""
    i = bisect.bisect_right(session["users"], when)
    return session["users"][i - 1] if i else None


def attribute(sessions: list[dict], exclusive: bool):
    """(totals, day bounds, per-session totals, overlap, union), keyed by (day, project key).

    `parallel` gives every live session the whole segment — the default, and the honest answer for
    per-project effort. `exclusive` gives it to the session whose last user message is most recent,
    because that is the one they were attending; with no user message anywhere in the running, it
    splits evenly rather than guessing.
    """
    totals = defaultdict(lambda: {"attended": timedelta(), "unattended": timedelta()})
    day_bounds: dict[tuple, list] = {}
    per_session = defaultdict(lambda: defaultdict(timedelta))
    # Each SESSION's own first/last within a day. The day/project bounds are wrong for a CSV row:
    # four sessions in one afternoon all printed the afternoon's span as their own.
    session_bounds: dict[tuple, dict] = defaultdict(dict)
    overlap = union = timedelta()

    for a, b, live in _segments(sessions):
        length = b - a
        union += length
        if len({e["session"]["id"] for e in live}) > 1:
            overlap += length * (len(live) - 1)

        if exclusive and len(live) > 1:
            ranked = [(e, _nearest_user(e["session"], a)) for e in live]
            if all(t is None for _, t in ranked):
                chosen = [(e, length / len(live)) for e in live]   # nothing to prefer; split
            else:
                # A session they have actually spoken in outranks one they have not; among those, the
                # most recent wins. The tuple avoids inventing a tz-aware sentinel datetime.
                best = max(ranked, key=lambda r: (r[1] is not None, r[1] or a))
                chosen = [(best[0], length)]
        else:
            chosen = [(e, length) for e in live]

        for entry, amount in chosen:
            s = entry["session"]
            slot = (a.date(), s["key"])
            totals[slot]["attended" if entry["attended"] else "unattended"] += amount
            per_session[slot][s["id"]] += amount
            bounds = day_bounds.setdefault(slot, [a, b])
            bounds[0], bounds[1] = min(bounds[0], a), max(bounds[1], b)
            own = session_bounds[slot].setdefault(s["id"], [a, b])
            own[0], own[1] = min(own[0], a), max(own[1], b)
    return totals, day_bounds, per_session, session_bounds, overlap, union


def total_of(slot: dict) -> timedelta:
    return slot["attended"] + slot["unattended"]


def hm(delta: timedelta) -> str:
    minutes = round(delta.total_seconds() / 60)
    return "%d:%02d" % (minutes // 60, minutes % 60)


def week_bounds(today: date, offset: int = 0) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    return monday, monday + timedelta(days=6)


# --- output --------------------------------------------------------------------------------

def report(sessions, totals, day_bounds, per_session, overlap, union,
           since, until, show_sessions, exclusive, idle, notes=()) -> None:
    slots = {k: v for k, v in totals.items() if since <= k[0] <= until and total_of(v)}
    if not slots:
        print("No sessions with recorded time between %s and %s." % (since, until))
        for n in notes:
            print(n)
        return

    # The MOST RECENT spelling, not the most common: right after a rename the old name still
    # dominates by count, so a "most common" label would keep printing the directory's former name
    # for weeks. What they want to see is what the folder is called now.
    latest: dict[str, tuple] = {}
    for s in sessions:
        when = s["events"][-1][0]
        if s["key"] not in latest or when > latest[s["key"]][0]:
            latest[s["key"]] = (when, s["project"])
    label = {k: v[1] for k, v in latest.items()}
    by_id = {s["id"]: s for s in sessions}

    print("TIMESHEET  %s .. %s        attribution: %s"
          % (since, until, "exclusive" if exclusive else "parallel"))
    for n in notes:
        print(n)
    print("=" * 76)
    print("  %-30s %-11s %8s %10s %7s"
          % ("", "", "attended", "unattended", "total"))

    grand = {"attended": timedelta(), "unattended": timedelta()}
    per_project = defaultdict(lambda: {"attended": timedelta(), "unattended": timedelta()})

    for day in sorted({k[0] for k in slots}):
        rows = sorted(((k[1], v) for k, v in slots.items() if k[0] == day),
                      key=lambda r: label[r[0]].casefold())
        day_tot = sum((total_of(v) for _, v in rows), timedelta())
        print("\n%-59s %7s" % (day.strftime("%a %d %b"), hm(day_tot)))
        for key, v in rows:
            first, last = day_bounds[(day, key)]
            for part in ("attended", "unattended"):
                grand[part] += v[part]
                per_project[key][part] += v[part]
            print("  %-30s %s-%s %8s %10s %7s" % (
                label[key][:30], first.strftime("%H:%M"), last.strftime("%H:%M"),
                hm(v["attended"]), hm(v["unattended"]), hm(total_of(v))))
            if show_sessions:
                for sid, amount in sorted(per_session[(day, key)].items(),
                                          key=lambda kv: -kv[1].total_seconds()):
                    print("      %-*.*s %25s" % (TITLE_WIDTH, TITLE_WIDTH,
                                                 by_id[sid]["title"], hm(amount)))

    print("\n" + "=" * 76)
    for key in sorted(per_project, key=lambda k: -total_of(per_project[k]).total_seconds()):
        v = per_project[key]
        print("  %-30s %11s %8s %10s %7s" % (label[key][:30], "", hm(v["attended"]),
                                             hm(v["unattended"]), hm(total_of(v))))
    print("  %-30s %11s %8s %10s %7s" % ("TOTAL", "", hm(grand["attended"]),
                                         hm(grand["unattended"]), hm(total_of(grand))))

    # Never hidden, in either mode. See the module docstring.
    print("\n  wall-clock union (no double count)                        %s" % hm(union))
    if overlap:
        print("  of which PARALLEL, two or more projects live at once:     %s" % hm(overlap))
        if not exclusive:
            print("\n  Counted in full above, which is the right answer for per-project effort.\n"
                  "  If an engagement bills against a clock, or two CLIENTS would share an\n"
                  "  hour, re-run with --attribution exclusive.")
    else:
        print("  no overlapping sessions in this window.")
    counted = len({sid for (day, _k), sess in per_session.items() if since <= day <= until
                   for sid, amount in sess.items() if amount})
    print("\n  %d sessions in this window. A gap ending in one of your messages is capped at %s;\n"
          "  gaps ending in agent output count in full, because the machine was working.\n"
          "  Claude Code on the directories read. Cursor writes no transcript."
          % (counted, hm(idle)))


def emit_csv(session_bounds, per_session, sessions, since, until) -> None:
    by_id = {s["id"]: s for s in sessions}
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(["date", "project", "session", "title", "start", "end", "minutes"])
    for (day, key), sess in sorted(per_session.items()):
        if not (since <= day <= until):
            continue
        for sid, amount in sorted(sess.items(), key=lambda kv: session_bounds[(day, key)][kv[0]]):
            if not amount:
                continue
            s = by_id[sid]
            first, last = session_bounds[(day, key)][sid]
            out.writerow([day.isoformat(), s["project"], s["short"], s["title"],
                          first.strftime("%H:%M"), last.strftime("%H:%M"),
                          round(amount.total_seconds() / 60)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    window = ap.add_mutually_exclusive_group()
    window.add_argument("--last-week", action="store_true", help="the previous Mon-Sun week")
    window.add_argument("--days", type=int, metavar="N", help="the last N days, ending today")
    window.add_argument("--since", metavar="YYYY-MM-DD", help="explicit start (with --until)")
    ap.add_argument("--until", metavar="YYYY-MM-DD", help="explicit end; defaults to today")
    ap.add_argument("--project", metavar="NAME", help="only projects matching this substring")
    ap.add_argument("--projects", metavar="PATH", action="append", default=[],
                    help="another machine's `projects` directory; repeatable, deduped by "
                         "session id")
    ap.add_argument("--attribution", choices=("parallel", "exclusive"), default="parallel",
                    help="parallel (default): every session accrues in full. exclusive: an "
                         "overlapping stretch goes to the project you touched most recently")
    ap.add_argument("--idle", type=int, default=DEFAULT_IDLE_MIN, metavar="MIN",
                    help="a gap this long ending in YOUR message is a break (default %d)"
                         % DEFAULT_IDLE_MIN)
    ap.add_argument("--max-run", type=int, default=DEFAULT_MAX_RUN_MIN, metavar="MIN",
                    help="cap on ONE silent agent gap; past this it is a resumed session, not "
                         "work (default %d, measured -- see the module docstring)"
                         % DEFAULT_MAX_RUN_MIN)
    ap.add_argument("--sessions", action="store_true",
                    help="list every session under its project, with its title")
    ap.add_argument("--csv", action="store_true", help="machine-readable, one row per day/session")
    args = ap.parse_args()

    today = date.today()
    if args.since:
        try:
            since = date.fromisoformat(args.since)
            until = date.fromisoformat(args.until) if args.until else today
        except ValueError:
            print("--since/--until want YYYY-MM-DD", file=sys.stderr)
            return 2
    elif args.days:
        since, until = today - timedelta(days=args.days - 1), today
    else:
        since, until = week_bounds(today, -1 if args.last_week else 0)

    idle = timedelta(minutes=max(1, args.idle))
    max_run = timedelta(minutes=max(1, args.max_run))
    for p in args.projects:
        if not Path(p).is_dir():
            print("  ! --projects %s is not a readable directory; skipped." % p, file=sys.stderr)
    extra_roots = [Path(p) for p in args.projects if Path(p).is_dir()]
    roots = [projects_dir()] + extra_roots

    # Printed unconditionally, to stderr so it survives even a --csv redirect. See the module
    # docstring's TWO MACHINES section — a synced copy never gets to look current by omission.
    notes = source_notes(extra_roots)
    for n in notes:
        print(n, file=sys.stderr)

    sessions = collect(roots, idle, max_run, args.project)
    exclusive = args.attribution == "exclusive"
    # Attribution runs over EVERY session, not just the window's: one that began before `since`
    # still competes for an overlapping segment inside it. The window is applied when reporting.
    totals, day_bounds, per_session, session_bounds, _ovl, _uni = attribute(sessions, exclusive)

    if args.csv:
        emit_csv(session_bounds, per_session, sessions, since, until)
        return 0

    # Overlap and union are re-derived for the window only, so the two figures under a week's
    # table describe that week and not the whole of history.
    window_sessions = [s for s in sessions
                       if any(since <= iv["start"].date() <= until for iv in s["intervals"])]
    w_overlap = w_union = timedelta()
    for a, b, live in _segments(window_sessions):
        if since <= a.date() <= until:
            w_union += b - a
            if len(live) > 1:
                w_overlap += (b - a) * (len(live) - 1)
    report(sessions, totals, day_bounds, per_session, w_overlap, w_union,
           since, until, args.sessions, exclusive, idle, notes)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
