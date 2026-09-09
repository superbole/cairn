"""B40 -- a `check after `next session on <machine>`` watch becomes DUE on that machine.

    python plugins/cairn/tools/test_watch_machine_trigger.py

WHY THIS EXISTS. `_partition`/`_sort_watches` used to split every watch trigger into just two
buckets: a `YYYY-MM-DD` string went to date-based due/pending, and literally everything else --
including `next session on LAPTOP1` -- fell into `events`, which only ever renders as the collapsed
"Also watching (not actionable yet)" line. There was no path by which an event-gated watch could
ever become DUE. That is exactly backwards for a trigger of this one shape: it names a MACHINE,
`machine_identity.hostname()` already knows which machine this session is on, and "next session
on LAPTOP1" literally means "due the moment a session opens on LAPTOP1" -- so on LAPTOP1 itself it used to
print as one collapsed line among the not-yet-actionable watches, which is the wrong answer on
the one machine where the answer matters.

KEPT NARROW ON PURPOSE (per the brief that added this): only the exact `next session on <X>`
phrase is matched. No other free-text event trigger is interpreted -- that would mean guessing at
English, and a wrong guess turns a watch due on the wrong session, worse than the collapsed line
it replaces. An unmatched event trigger (including this one on a DIFFERENT machine, or with no
hostname available) must keep TODAY's behaviour exactly: fall through to `events`.

Same style as `test_machine_identity.py`. Nothing here touches the network or any file in the
repo; the one subprocess case uses a throwaway git repo in a temp directory.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_TEXT = {"encoding": "utf-8", "errors": "replace"}   # the hook writes utf-8 (it reconfigures
                                                      # stdout for exactly this); the Windows
                                                      # default locale (cp1252) cannot always
                                                      # decode it back -- the DUE NOW box below
                                                      # prints a clock emoji that crashed the
                                                      # subprocess reader thread without this.

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))

import session_orientation as so                          # noqa: E402

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def watch(n, title, trigger, added="2026-08-01"):
    return [f"**W{n}. {title}** — `Opus 5` · effort `high` · `AFK/Auto` · added `{added}` "
            f"· check after `{trigger}`"]


print("\n1. _is_here -- the loose match, same tradeoff as machine_identity's own annotation check")

check("an id contained in the hostname matches", so._is_here("LAPTOP1", "ORG-LAPTOP1"), True)
check("case-insensitive", so._is_here("laptop1", "ORG-LAPTOP1"), True)
check("a machine that IS its own id matches", so._is_here("WORKSTATION", "WORKSTATION"), True)
check("a different id does not match", so._is_here("LAPTOP2", "ORG-LAPTOP1"), False)
check("an empty id never matches", so._is_here("", "ORG-LAPTOP1"), False)
check("an empty hostname never matches", so._is_here("LAPTOP1", ""), False)


print("\n2. _sort_watches -- a machine trigger for THIS host becomes due")

w1 = watch(1, "Machine watch for here", "next session on LAPTOP1")
w2 = watch(2, "Machine watch for elsewhere", "next session on LAPTOP2")
w3 = watch(3, "An ordinary event watch", "the deploy lands")
w4 = watch(4, "A dated watch, already due", "2020-01-01")

due, pending, events = so._sort_watches([w1, w2, w3, w4], "ORG-LAPTOP1")
check("the matching machine watch is due", any("Machine watch for here" in ln
      for _t, e in due for ln in e), True)
check("exactly two watches are due (W1 by machine, W4 by date)", len(due), 2)
check("the OTHER machine's watch is not due", any("Machine watch for elsewhere" in ln
      for _t, e in due for ln in e), False)
check("the other machine's watch instead falls to events",
      any("Machine watch for elsewhere" in ln for _t, e in events for ln in e), True)
check("an ordinary event trigger is unaffected, still in events",
      any("An ordinary event watch" in ln for _t, e in events for ln in e), True)

print("\n3. with NO hostname available, every machine trigger falls back to today's behaviour")

due0, pending0, events0 = so._sort_watches([w1, w2], "")
check("nothing is due without a hostname to compare against", due0, [])
check("both machine watches land in events, same as before B40", len(events0), 2)

print("\n4. a malformed / unparseable trigger still degrades to 'unspecified', unchanged")

w5 = [f"**W5. No check-after field at all** — `Sonnet 5` · effort `medium` · `AFK/Auto` "
      f"· added `2026-08-01`"]
due5, pending5, events5 = so._sort_watches([w5], "ORG-LAPTOP1")
check("it is not due", due5, [])
check("it is reported as an unspecified event", events5[0][0], "unspecified")


print("\n5. end-to-end: the watch surfaces as DUE NOW on the named machine, not elsewhere")

import machine_identity as mi                              # noqa: E402
real_host = mi.hostname()
check("this machine has a real hostname to build the fixture on", bool(real_host), True)

# B40's own match (`_is_here`) runs straight off `machine_identity.hostname()` -- it does not
# consult `~/.claude/MACHINES.md` (that table is B28's, a separate check). So the trigger here
# names the real hostname itself, which is trivially a substring of itself, rather than an
# invented id that would never match.
tmp = Path(tempfile.mkdtemp(prefix="watch-machine-trigger-"))
repo = tmp / "repo"
repo.mkdir()
subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, **NW)
(repo / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto\n\n"
    "## Watching\n\n"
    "**W1. Machine-gated watch** — `Sonnet 5` · effort `medium` · `AFK/Auto` "
    f"· added `2026-08-01` · check after `next session on {real_host}`\n\n"
    "---\n\nAim: test.\n", encoding="utf-8")

# A throwaway CLAUDE_CONFIG_DIR only so install_rules/ensure_*_file's own writes (unrelated to
# this test) never touch the real ~/.claude/.
cfg = tmp / "cfg"
env = dict(os.environ)
env["CLAUDE_PROJECT_DIR"] = str(repo)
env["CLAUDE_CONFIG_DIR"] = str(cfg)
done = subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                      input='{"source":"startup"}', capture_output=True, text=True, **_TEXT,
                      env=env, cwd=str(repo), **NW)
check("exits 0", done.returncode, 0)
check("DUE NOW fires -- the trigger names THIS machine", "DUE NOW" in done.stdout, True)
check("the watch's own title is in the due box", "Machine-gated watch" in done.stdout, True)

print("\n6. and the SAME watch, on a DIFFERENT machine, stays collapsed as not-yet-actionable")

(repo / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto\n\n"
    "## Watching\n\n"
    "**W1. Machine-gated watch** — `Sonnet 5` · effort `medium` · `AFK/Auto` "
    "· added `2026-08-01` · check after `next session on SOME-OTHER-MACHINE-ENTIRELY`\n\n"
    "---\n\nAim: test.\n", encoding="utf-8")
done2 = subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                       input='{"source":"startup"}', capture_output=True, text=True, **_TEXT,
                       env=env, cwd=str(repo), **NW)
check("exits 0", done2.returncode, 0)
check("no DUE NOW box for a watch naming another machine", "DUE NOW" in done2.stdout, False)
check("it still shows up, collapsed, as not actionable yet",
      "not actionable yet" in done2.stdout and "Machine-gated watch" in done2.stdout, True)


# --------------------------------------------------------------------------------------
# B118 -- THE LEADING ARTICLE. Every watch actually written in this portfolio reads
# "THE next session on <machine>", because that is how the sentence reads in English, and
# the original pattern was anchored with no article so it matched NONE of them. The
# consequence is the worst available: the watch falls through to the free-text branch and
# prints under "not actionable yet" ON THE VERY MACHINE WHERE IT IS DUE. Measured live
# twice -- 2026-09-07 (two watches, one machine, both collapsed) and 2026-09-08 (this
# project's own W6 and W8). These cases exist so it never silently regresses.
# --------------------------------------------------------------------------------------
print("")
print("B118. the leading article, which every real watch has")
for phrase, want in (
    ("the next session on LAPTOP1", "LAPTOP1"),
    ("The next session on LAPTOP1", "LAPTOP1"),
    ("next session on LAPTOP1", "LAPTOP1"),
):
    m = so._MACHINE_TRIGGER_RE.match(phrase)
    check("%-30s -> %s" % (phrase, want), m.group(1) if m else None, want)

wA = watch(11, "Articled machine watch", "the next session on LAPTOP1")
dueA, pendingA, eventsA = so._sort_watches([wA], "ORG-LAPTOP1")
check("an articled machine watch is DUE on that machine",
      any("Articled machine watch" in ln for _t, e in dueA for ln in e), True)
check("and does not ALSO land in events", len(eventsA), 0)

# Must NOT match: a trigger that starts the same way but names no machine. A false DUE is
# worse than the collapsed line B118 is about.
wB = watch(12, "Not a machine gate", "the next session that pulls this repo on another machine")
dueB, pendingB, eventsB = so._sort_watches([wB], "ORG-LAPTOP1")
check("a look-alike event trigger is not treated as a machine gate", len(dueB), 0)
check("it stays in events", len(eventsB), 1)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
