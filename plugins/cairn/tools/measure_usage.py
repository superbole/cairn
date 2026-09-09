#!/usr/bin/env python3
"""What did the sessions on this machine ACTUALLY cost? Read from the transcripts, never guessed.

    python plugins/cairn/tools/measure_usage.py                 # this account, last 7 days
    python plugins/cairn/tools/measure_usage.py --days=30
    python plugins/cairn/tools/measure_usage.py --project=<dir-slug or substring>
    python plugins/cairn/tools/measure_usage.py --window        # the live 5-hour window only
    python plugins/cairn/tools/measure_usage.py --session=<id prefix>

WHY THIS EXISTS (B124, 2026-09-08). `docs/running-a-batch.md` carried a token budget -- "~150k per
lane agent, 8-10 lane agents per 5-hour window" -- that was measured ONCE, by hand, and then
quoted as fact for three days while every batch was planned against it. It is the exact thing
`rules/CLAUDE.md`'s last rule forbids: a bare constant in a file that gets re-read, rotting
silently. On 2026-09-08 a batch planned against it ran out of window mid-flight and killed two lane
agents, which is the third time that has happened.

The numbers were also wrong in SHAPE, not just in value, and no amount of care would have caught
that by estimating:

  * The budget counted LANE AGENTS and treated the orchestrator as one of them. Measured on
    2026-09-08: the orchestrator billed 2,316,354 tokens and the seven subagents billed roughly
    1.6M between them. THE ORCHESTRATOR WAS ~60% OF THE SPEND, and its cost scales with TURNS --
    how long the session runs and how big its context has grown -- not with how many lanes it
    supervises.
  * Cache WRITES dominate. That same session: 468 fresh input tokens, 1,938,162 cache-creation
    tokens, 349,159 output. Any model of cost built on "how much did I read and write" misses 84%
    of it, because the real driver is re-establishing a growing context every turn.
  * The per-agent figure reported in a subagent's completion notification is NOT the billed
    figure. Lane E's notification said 172,876; its transcript says 358,069 billed. Budgeting
    against the reported number understates a lane by ~2x.

WHAT IT READS, AND WHAT IT DELIBERATELY DOES NOT. Claude Code writes one JSONL per session under
`<config>/projects/<project-slug>/`, and every assistant turn carries a `usage` block. This tool
reads ONLY those `usage` blocks plus each line's `timestamp`, `isSidechain` and `message.model`.
It never reads message content, tool input, tool output or file contents, and it never prints
anything from them -- so it can be pointed at a machine whose transcripts contain medical history,
credentials or an employer's source without disclosing any of it. That is not incidental: the
transcripts are the single most sensitive thing this plugin's tooling can reach (see B120, where
mirroring whole transcripts to employer OneDrive was a real incident), and a usage tool has no
business opening the rest of the line.

BILLED vs CACHE READS. `billed` here means `input_tokens + cache_creation_input_tokens +
output_tokens` -- the tokens charged at or near full rate. Cache READS are reported separately
because they are discounted, not free, and because their ratio is the single best signal that a
session has grown too long: 1.01 BILLION cache reads across 22 sessions in one project, against
22.4M billed. This tool does not claim to reproduce the provider's rate-limit accounting, which is
not published; it measures the thing that correlates with hitting it, which is what a budget
needs. Every comparison figure is DERIVED from the history it just read -- see `reference()`.
The single exception is the per-lane cost, which is unmeasurable after the fact and is the only
remembered number in the file, labelled as such wherever it is printed.

SUBAGENT SPEND IS NOT DURABLY RECORDED, AND THIS TOOL SAYS SO RATHER THAN REPORTING ZERO.
A subagent (Task/Agent tool) writes its transcript to a per-session scratchpad `tasks/` directory,
NOT under `<config>/projects/`, and those files are truncated to 0 bytes once the agent finishes.
Measured 2026-09-08: eight subagents ran, one transcript still had content, the other seven were
empty. So `isSidechain` turns are effectively absent from what this tool can read, and a `side%`
of 0% means "not measurable from here", NEVER "no subagents ran". The tool prints that caveat
whenever the figure is zero, because a number that reads identically for "none happened" and
"cannot see any" is the one-value-two-opposite-states defect this repo designs against.

The practical consequence for budgeting: add subagent cost by hand from each completion
notification, and DOUBLE it -- the reported `subagent_tokens` was 172,876 against 358,069 actually
billed on the one lane whose transcript survived.

NO NETWORK, NO WRITES, EXIT 0. A measurement tool must never be the thing that breaks a session.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The rolling window the account limit is enforced over. Named, not inlined, because it is a
# property of the plan and will change.
WINDOW_HOURS = 5.0

# ONE constant, and it is here because it CANNOT be derived -- not because deriving it was hard.
#
# A subagent's transcript is written to a per-session scratchpad `tasks/` directory, outside
# `<config>/projects/`, and truncated to 0 bytes when the agent finishes. So a lane's cost is
# unmeasurable after the fact and this figure has to be remembered. Measured 2026-09-08 from the
# one lane transcript that survived, as `billed` (not the ~2x-smaller number its own completion
# notification reported). Re-measure it the next time a lane transcript is caught intact.
#
# EVERYTHING ELSE IS DERIVED FROM THIS MACHINE'S OWN HISTORY, at runtime, by `reference()` below.
# An earlier version of this file froze four measured values here, which is the exact bare-constant
# defect this tool exists to remove -- committed inside the tool built to remove it. The window
# ceiling in particular MUST be live: it is the number a batch decision is sized against, and a
# frozen one goes stale in the direction that over-commits.
SONNET_LANE_BILLED = 358_069

# A window this size has hit the account limit in practice, so treat the observed peak as a
# ceiling rather than a target. Kept as a ratio, not a second magic number.
CEILING_SAFETY = 0.85


def config_dir() -> Path:
    """Same resolution as every other tool here: honour CLAUDE_CONFIG_DIR, else ~/.claude."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


def _parse_args(argv):
    opts = {"days": 7, "project": None, "window": False, "session": None}
    for a in argv:
        if a.startswith("--days="):
            opts["days"] = int(a.split("=", 1)[1])
        elif a.startswith("--project="):
            opts["project"] = a.split("=", 1)[1]
        elif a.startswith("--session="):
            opts["session"] = a.split("=", 1)[1]
        elif a == "--window":
            opts["window"] = True
    return opts


def _ts(raw):
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def read_turns(path: Path):
    """Every assistant turn in one transcript, as usage-only dicts. Never raises.

    Only `usage`, `timestamp`, `isSidechain` and `message.model` are touched. Nothing else on the
    line is read -- see the module docstring for why that is a hard boundary and not a shortcut.
    """
    out = []
    try:
        fh = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue                      # a partial last line is normal on a live session
            msg = d.get("message")
            if not isinstance(msg, dict):
                continue
            u = msg.get("usage")
            if not isinstance(u, dict):
                continue
            inp = u.get("input_tokens") or 0
            ccw = u.get("cache_creation_input_tokens") or 0
            out.append({
                "t": _ts(d.get("timestamp")),
                "side": bool(d.get("isSidechain")),
                "model": msg.get("model") or "?",
                "billed": inp + ccw + (u.get("output_tokens") or 0),
                "fresh": inp,
                "cache_w": ccw,
                "cache_r": u.get("cache_read_input_tokens") or 0,
                "out": u.get("output_tokens") or 0,
            })
    return out


def transcripts(cfg: Path, project: str | None):
    """Every session transcript under `<config>/projects/`, optionally filtered by project slug.

    Scans EVERY project by default, on purpose: the rate limit is per ACCOUNT, so a budget built
    from one repo's transcripts understates it by however much work happened elsewhere. That is
    not hypothetical -- the machines here run several projects at once, which is the premise of
    this whole plugin.
    """
    base = cfg / "projects"
    if not base.is_dir():
        return []
    found = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        if project and project.lower() not in d.name.lower():
            continue
        found.extend(sorted(d.glob("*.jsonl")))
    return found


def rolling_peak(turns, hours=WINDOW_HOURS):
    """(peak billed in any `hours` window, when it ended). Two pointers over a sorted list."""
    dated = sorted((t for t in turns if t["t"]), key=lambda t: t["t"])
    if not dated:
        return 0, None
    span = timedelta(hours=hours)
    best, best_at, run, j = 0, None, 0, 0
    for i, t in enumerate(dated):
        run += t["billed"]
        while dated[j]["t"] < t["t"] - span:
            run -= dated[j]["billed"]
            j += 1
        if run > best:
            best, best_at = run, t["t"]
    return best, best_at


def reference(turns):
    """The comparison figures, DERIVED from the history just read. Never remembered.

    Returns `worst_window`, `median_per_turn` and the session count they came from, so the caller
    can say how much history is behind them -- a peak over two sessions is not evidence, and the
    tool should admit that rather than quote it with the same confidence as a peak over fifty.
    """
    peak, at = rolling_peak(turns)
    per_turn = sorted(t["billed"] for t in turns) or [0]
    return {
        "worst_window": peak,
        "worst_window_at": at,
        "median_per_turn": per_turn[len(per_turn) // 2],
        "turns": len(turns),
    }


def _fmt(n):
    return f"{n:,}"


def main(argv=None):
    opts = _parse_args(argv if argv is not None else sys.argv[1:])
    cfg = config_dir()
    files = transcripts(cfg, opts["project"])
    if not files:
        print(f"no transcripts under {cfg / 'projects'} -- nothing to measure.")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=opts["days"])
    per_session, all_turns = {}, []
    for f in files:
        if opts["session"] and not f.stem.startswith(opts["session"]):
            continue
        turns = read_turns(f)
        if not turns:
            continue
        dated = [t["t"] for t in turns if t["t"]]
        first, last = (min(dated), max(dated)) if dated else (None, None)
        if first and first < cutoff and not opts["session"]:
            continue
        per_session[f] = (turns, first, last)
        all_turns.extend(turns)

    if not per_session:
        print(f"no sessions in the last {opts['days']} day(s). Try --days=30.")
        return 0

    # --- the live window: the one number a batch decision actually needs ------------------
    now = datetime.now(timezone.utc)
    win_start = now - timedelta(hours=WINDOW_HOURS)
    win = [t for t in all_turns if t["t"] and t["t"] >= win_start]
    win_billed = sum(t["billed"] for t in win)
    # Derived from the history just read, not from a number stored in this file.
    ref = reference(all_turns)
    peak = ref["worst_window"]
    budget = int(peak * CEILING_SAFETY) if peak else 0
    print(f"\n=== live {WINDOW_HOURS:.0f}-hour window (all projects on this machine) ===")
    print(f"  spent so far : {_fmt(win_billed)} billed over {len(win)} turn(s)")
    if peak:
        print(f"  observed peak: {_fmt(peak)} -- the worst {WINDOW_HOURS:.0f}h window in "
              f"{opts['days']} day(s) of history on this machine, which HIT the limit")
        print(f"  working cap  : {_fmt(budget)} ({CEILING_SAFETY:.0%} of that peak)")
        print(f"  used         : {win_billed / max(1, budget):.0%} of the working cap")
    else:
        print("  observed peak: not enough history to derive one -- run with --days=30")
    if win and budget:
        rate = win_billed / max(1, len(win))
        print(f"  per turn now : {_fmt(int(rate))} billed "
              f"(median over {ref['turns']} turn(s) of history: "
              f"{_fmt(ref['median_per_turn'])})")
        headroom = max(0, budget - win_billed)
        print(f"  headroom     : ~{_fmt(headroom)} -> about {headroom // SONNET_LANE_BILLED} more "
              f"Sonnet lane agent(s) at {_fmt(SONNET_LANE_BILLED)} each, "
              f"OR ~{headroom // max(1, int(rate))} more orchestrator turns -- not both")
        print(f"  (the lane figure is the ONE number this tool cannot derive -- subagent")
        print(f"   transcripts are truncated when the agent finishes. Measured 2026-09-08.)")
    if opts["window"]:
        return 0

    # --- per session ----------------------------------------------------------------------
    hdr = (f"\n{'session':<10} {'started':<17} {'hrs':>5} {'turns':>6} "
           f"{'billed':>11} {'cache rd':>13} {'side%':>6}")
    print(hdr)
    print("-" * (len(hdr) - 1))
    grand = defaultdict(int)
    for f, (turns, first, last) in sorted(per_session.items(),
                                          key=lambda kv: kv[1][1] or datetime.min):
        billed = sum(t["billed"] for t in turns)
        side = sum(t["billed"] for t in turns if t["side"])
        hrs = ((last - first).total_seconds() / 3600) if first and last else 0.0
        print(f"{f.stem[:8]:<10} {(first.strftime('%Y-%m-%d %H:%M') if first else '?'):<17} "
              f"{hrs:>5.1f} {len(turns):>6} {_fmt(billed):>11} "
              f"{_fmt(sum(t['cache_r'] for t in turns)):>13} "
              f"{(side / billed if billed else 0):>5.0%}")
        grand["billed"] += billed
        grand["cache_r"] += sum(t["cache_r"] for t in turns)
        grand["cache_w"] += sum(t["cache_w"] for t in turns)
        grand["out"] += sum(t["out"] for t in turns)
        grand["turns"] += len(turns)
        grand["side"] += side
    print("-" * (len(hdr) - 1))
    print(f"{'TOTAL':<10} {'':<17} {'':>5} {grand['turns']:>6} "
          f"{_fmt(grand['billed']):>11} {_fmt(grand['cache_r']):>13} "
          f"{(grand['side'] / grand['billed'] if grand['billed'] else 0):>5.0%}")
    if not grand["side"]:
        # NOT the same as "no subagents ran" -- see the module docstring. Saying so is the whole
        # difference between a measurement and a misleading zero.
        print()
        print("  NOTE: side% is 0 because subagent transcripts are written to a scratchpad")
        print("  tasks/ directory and truncated when the agent finishes -- they are NOT under")
        print("  <config>/projects/ and cannot be read back here. Treat 0% as 'not measurable',")
        print("  not as 'no subagents ran'. Add each agent from its completion notification and")
        print("  DOUBLE the reported figure (measured: 172,876 reported vs 358,069 billed).")

    # --- the shape, which is the part a remembered constant always loses ------------------
    print(f"\n=== where it goes ({opts['days']} day(s), {len(per_session)} session(s)) ===")
    if grand["billed"]:
        print(f"  cache writes : {_fmt(grand['cache_w'])} "
              f"({grand['cache_w'] / grand['billed']:.0%} of billed) -- re-establishing context, "
              f"not new work")
        print(f"  output       : {_fmt(grand['out'])} ({grand['out'] / grand['billed']:.0%})")
        print(f"  cache reads  : {_fmt(grand['cache_r'])} "
              f"({grand['cache_r'] / grand['billed']:.1f}x billed) -- discounted, not free")
    per_turn = sorted(sum(t["billed"] for t in ts) / len(ts)
                      for ts, _, _ in per_session.values())
    if per_turn:
        print(f"  billed/turn  : median {_fmt(int(per_turn[len(per_turn) // 2]))}, "
              f"worst session {_fmt(int(per_turn[-1]))}")
    peak, peak_at = rolling_peak(all_turns)
    if peak_at:
        print(f"  peak {WINDOW_HOURS:.0f}h    : {_fmt(peak)} billed, ending "
              f"{peak_at.strftime('%Y-%m-%d %H:%M')} UTC")
    print("\nBudget a batch in TURNS and AGENTS together, never in agents alone -- the orchestrator")
    print("is the larger half and it is paid per turn. Re-run this before planning one.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                  # never break a session over a measurement
        print(f"measure_usage: could not complete ({type(exc).__name__}: {exc})")
        sys.exit(0)
