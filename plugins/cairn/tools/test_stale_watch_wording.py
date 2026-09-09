"""B44 -- the stale-watch flag may claim only what it actually knows.

    python plugins/cairn/tools/test_stale_watch_wording.py

WHY THIS EXISTS. The flag on an event-gated watch past `STALE_WATCH_DAYS` used to read "the
trigger may never come. Worth deleting or re-scoping, not carrying." Nothing in this system
records whether a trigger FIRED -- the number it is printed from is the age of the `added` field,
which measures how long the watch has been open. Those two are indistinguishable from the inside,
and the sentence asserted the one that had not been established.

Measured in `atlas` on 2026-09-02: eight watches (W74-W81) were flagged at 36-51 days, and
`dev/peek.py` showed W74's trigger had fired on seven separate days and W78's on two. So the
prompt was arguing to delete nine unverified production changes -- one of them a fail-closed
gateway routing change that had never been exercised -- on the strength of a number that meant
something else entirely. A line of noise is the cost of the harmless case; that is the cost of the
harmful one, and the asymmetry is the whole reason this is a plugin-level fix.

WHAT THIS PINS. Wording, deliberately -- this is a change whose entire content IS the wording, so
a test that only checked "some warning appears" would pass against the sentence being removed. It
pins the retraction (the false claim is gone), the honest claim (age = time since `added`), and
the ask (find out whether it fired) -- and, on the other side, that the mechanism around it is
untouched: the threshold, which watches are flagged, and the per-entry `waiting Nd on:` marker
that `skills/next/SKILL.md` step 3a quotes verbatim.

NOT IN SCOPE, and asserted here so a later session does not "fix" it by symmetry: the DECISIONS
list keeps its "waited over N days without an answer" wording. That claim is TRUE -- a decision
waits on the user reading it, and the age genuinely measures how long they have not, with no hidden
event that could have fired unobserved.

Isolation: `CLAUDE_CONFIG_DIR` is redirected to a temp directory before any hook import, and every
subprocess is given the same override, so nothing here reads or writes the real `~/.claude`.
"""
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

# --- isolation FIRST: before any import that could resolve ~/.claude ------------------------
_SANDBOX = Path(tempfile.mkdtemp(prefix="b44-stale-wording-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(_SANDBOX / "cfg")
(_SANDBOX / "cfg").mkdir(parents=True, exist_ok=True)
# A settings.json that already meets B23's floor, so this file's assertions are about watch
# wording only and never about the settings line that shares the same output.
(_SANDBOX / "cfg" / "settings.json").write_text('{"cleanupPeriodDays": 90}', encoding="utf-8")

_TEXT = {"encoding": "utf-8", "errors": "replace"}
ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))

import session_orientation as so                              # noqa: E402

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def orient(next_md):
    """Run the hook over a throwaway repo carrying `next_md`, return stdout."""
    repo = Path(tempfile.mkdtemp(dir=_SANDBOX, prefix="repo-"))
    subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, **NW)
    (repo / "NEXT.md").write_text(next_md, encoding="utf-8")
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    env["CLAUDE_CONFIG_DIR"] = str(_SANDBOX / "cfg")
    done = subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                          input='{"source":"startup"}', capture_output=True, text=True,
                          **_TEXT, env=env, cwd=str(repo), **NW)
    return done.returncode, done.stdout


def next_md(watch_line, decision_line=""):
    return ("# NEXT — test\n\n## Queue\n\n"
            "1. **Something to do** — Sonnet 5 · medium · AFK/Auto\n\n"
            + (f"## Decisions\n\n{decision_line}\n\n" if decision_line else "")
            + f"## Watching\n\n{watch_line}\n\n---\n\nAim: test.\n")


STALE_AGE = so.STALE_WATCH_DAYS + 17          # 47d when the threshold is 30 -- the atlas case
FRESH_AGE = max(1, so.STALE_WATCH_DAYS - 18)

stale_watch = (f"**W1. Two-leg commute day handling** — `Opus 5` · effort `high` · `AFK/Auto` "
               f"· added `{ago(STALE_AGE)}` · check after `a two-leg commute day`")
fresh_watch = (f"**W1. Something recent** — `Opus 5` · effort `high` · `AFK/Auto` "
               f"· added `{ago(FRESH_AGE)}` · check after `the next deploy`")

print("\n1. a watch past the threshold no longer asserts that the trigger will not fire")

rc, out = orient(next_md(stale_watch))
check("exits 0", rc, 0)
check("the retracted claim is gone", "may never come" in out, False)
check("it is not phrased as 'worth deleting, not carrying' either",
      "not carrying" in out, False)

print("\n2. ...and says the true thing instead: the number is an AGE, not evidence")

check("it names the field the age actually comes from", "since `added`" in out, True)
check("it says the firing is unknown", "FIRED" in out, True)
check("it asks for the check before any deletion",
      "Find out" in out and "before deleting" in out, True)
check("deleting/re-scoping is still offered, just second",
      "re-scoping" in out, True)
check("the threshold is still named", str(so.STALE_WATCH_DAYS) in out, True)

print("\n3. the MECHANISM around the wording is untouched")

check("the watch is still flagged with its age",
      f"waiting {STALE_AGE}d on" in out, True)
check("the per-entry marker skills/next/SKILL.md step 3a quotes still matches",
      "⚠ waiting" in out, True)
check("the watch's own title still shows", "Two-leg commute day handling" in out, True)

rc2, out2 = orient(next_md(fresh_watch))
check("exits 0", rc2, 0)
check("a watch UNDER the threshold gets no stale flag at all",
      "been open over" in out2, False)
check("it is still listed with its age, unflagged",
      f"waiting {FRESH_AGE}d on" in out2, True)

print("\n4. a DATED watch is unaffected -- it was never the thing making a false claim")

dated = (f"**W1. Check the thing on a date** — `Opus 5` · effort `high` · `AFK/Auto` "
         f"· added `{ago(STALE_AGE)}` · check after `{(date.today() + timedelta(days=9)).isoformat()}`")
rc3, out3 = orient(next_md(dated))
check("exits 0", rc3, 0)
check("no stale-watch flag for a date-gated watch", "been open over" in out3, False)
check("it shows as not-yet-due instead", "not until" in out3, True)

print("\n5. the DECISIONS wording is deliberately NOT changed -- that claim is true")

old_decision = (f"**D1. Something they have to call** — answer: `here` · added `{ago(STALE_AGE)}`")
rc4, out4 = orient(next_md(fresh_watch, old_decision))
check("exits 0", rc4, 0)
check("a stale decision still says it has waited without an answer",
      "without an answer" in out4, True)
check("and still offers deciding or dropping", "deciding or dropping" in out4, True)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
