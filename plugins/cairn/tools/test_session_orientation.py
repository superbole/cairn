"""Coverage for `session_orientation.py`'s `_inbox_items()` — B15's second bullet counter.

    python plugins/cairn/tools/test_session_orientation.py

THE BUG THIS GUARDS. `_inbox_items()` used to match `- `/`* ` at line-start with no idea
that markdown fences exist — the exact same gap `wrap_receipt._inbox_bullets()` had
(covered separately in `test_wrap_receipt.py` section 13), on the OTHER counter that reads
INBOX.md: the un-triaged item list printed at session start. The live incident (B15) was
an INBOX.md intake contract carrying four example bullets inside a fenced code block,
read as 5 un-triaged items instead of the 1 real one — this file is that fixture, run
directly against `_inbox_items()` rather than through the full SessionStart hook (which
needs a stdin payload and a great deal else this test has no reason to set up).

Also pins: an unclosed fence is reported back (`unclosed_at`) rather than silently
blanked to EOF, and a bare `- `/`* ` bullet with nothing after it (formatting, not an
item) no longer counts — `BULLET_RE` (shared with `fence_check.py` and
`wrap_receipt.py` via `fence_scan.py`) requires actual content after the marker.

Isolation: `CLAUDE_CONFIG_DIR` is redirected before the import, same as
`test_stale_watch_wording.py`; nothing here touches this repo's own INBOX.md (it doesn't
have one) or the real `~/.claude`.
"""
import os
import sys
import tempfile
from pathlib import Path

_SANDBOX = Path(tempfile.mkdtemp(prefix="b15-session-orientation-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(_SANDBOX / "cfg")
(_SANDBOX / "cfg").mkdir(parents=True, exist_ok=True)

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))

import session_orientation as so                              # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def project(name, inbox_text):
    root = Path(tempfile.mkdtemp(prefix=f"b15-inbox-{name}-"))
    (root / "INBOX.md").write_text(inbox_text, encoding="utf-8")
    return root


print("1. no INBOX.md at all")
r1 = Path(tempfile.mkdtemp(prefix="b15-no-inbox-"))
items1, total1, unclosed1 = so._inbox_items(r1)
check("no items", items1, [])
check("total 0", total1, 0)
check("no unclosed-fence signal", unclosed1, None)

print("\n2. B15's live shape — an intake contract with fenced EXAMPLE bullets, one real one")
r2 = project("live-shape", (
    "# INBOX\n\nCapture bullets below. Example:\n\n"
    "```\n- fix the thing\n* another example\n- a third\n- a fourth\n```\n\n"
    "- the one real un-triaged item\n"))
items2, total2, unclosed2 = so._inbox_items(r2)
check("only the ONE real bullet counts, not the four fenced examples", total2, 1)
check("and it is the right one", items2, ["- the one real un-triaged item"])
check("no unclosed-fence signal (the fence closed)", unclosed2, None)

print("\n3. bullets before AND after a closed fence both count; fenced ones do not")
r3 = project("before-and-after", (
    "# INBOX\n\n- before the fence\n\n```\n- inside the fence\n```\n\n- after the fence\n"))
items3, total3, _ = so._inbox_items(r3)
check("2 real bullets counted (before + after), not 3", total3, 2)
check("the fenced one is excluded", "- inside the fence" not in items3)

print("\n4. an unclosed fence is reported back, not silently swallowed")
r4 = project("unclosed", "# INBOX\n\n- before\n\n```\n- swallowed one\n- swallowed two\n")
items4, total4, unclosed4 = so._inbox_items(r4)
check("the bullet before the fence still counts", total4, 1)
check("the swallowed bullets are not silently counted as real items",
      any("swallowed" in it for it in items4), False)
check("the unclosed fence is reported (a line number, not None)", unclosed4 is not None, True)

print("\n5. a ~~~ fence is recognised the same as ```")
r5 = project("tilde", "# INBOX\n\n~~~\n- example\n~~~\n\n- a real thing\n")
items5, total5, unclosed5 = so._inbox_items(r5)
check("only the one real bullet outside the ~~~ fence counts", total5, 1)
check("no unclosed-fence signal", unclosed5, None)

print("\n6. a bare bullet marker with nothing after it is not an item (stricter than before)")
r6 = project("bare-marker", "# INBOX\n\n-\n*\n- a real item\n")
items6, total6, _ = so._inbox_items(r6)
check("only the one real bullet counts, not the two bare markers", total6, 1)

print("\n7. MAX_INBOX_ITEMS still caps what's SHOWN while `total` keeps the real count")
many = "# INBOX\n\n" + "\n".join(f"- item {i}" for i in range(so.MAX_INBOX_ITEMS + 3))
r7 = project("many", many + "\n")
items7, total7, _ = so._inbox_items(r7)
check("shown list capped at MAX_INBOX_ITEMS", len(items7), so.MAX_INBOX_ITEMS)
check("total reflects every real bullet", total7, so.MAX_INBOX_ITEMS + 3)


print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
