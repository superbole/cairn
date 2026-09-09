#!/usr/bin/env python3
"""Test for `check_credentials.py` (B48), against fabricated targets and a fixture file only.

    python plugins/cairn/tools/test_check_credentials.py

WHY THIS MUST NEVER TOUCH A REAL KEYRING OR ~/.claude/CREDENTIALS.md
------------------------------------------------------------------------
The tool's whole job is to read `cmdkey /list` (or an equivalent) and the user's real
`CREDENTIALS.md` -- exactly the two things a test must never depend on: the keyring's real
contents change with whatever the machine happens to have installed today, and the real
`CREDENTIALS.md` is the user's actual credential inventory, not a fixture. So every case here
replaces `check_credentials.list_targets` with a fake that returns FABRICATED target strings
(the same shapes real `cmdkey /list` output takes, none of them real machine data), and points
`--credentials-file` at a throwaway file this test writes itself. Nothing here shells out.

Also covers the two hard rules from the module docstring in the one place a test actually can:
`list_targets` is given raw `cmdkey`-shaped text carrying `User:`/`Type:`/`Persist:` lines with
fabricated values on them, and section 1 asserts those values never appear anywhere in the
returned list -- the only thing a test can mechanically check about "never store a value" is
that the value used in the fixture does not resurface.
"""
import io
import json
import sys
import tempfile
import contextlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_credentials as cc                          # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def exits(label, fn, code):
    try:
        fn()
    except SystemExit as e:
        check(label, e.code, code)
        return
    check(label, "no SystemExit", code)


# A fabricated `cmdkey /list` transcript. `FAKE-VALUE-DO-NOT-LEAK` stands in for what a real
# password would be -- `cmdkey` never actually prints one, but this stands in for the general
# class "some field on a non-Target line", and section 1 below asserts it never reaches the
# parsed result.
FAKE_CMDKEY_OUTPUT = """
Currently stored credentials:

    Target: LegacyGeneric:target=git:https://github.com
    Type: Generic
    User: FAKE-VALUE-DO-NOT-LEAK

    Target: LegacyGeneric:target=gh:github.com:fakeuser
    Type: Generic
    User: fakeuser
    Persist: Enterprise

    Target: LegacyGeneric:target=glab:example-gitlab.test:token:
    Type: Generic

    Target: LegacyGeneric:target=SomeApp.Vendor.refreshToken
    Type: Generic

    Target: Domain:target=TERMSRV/some-host
    Type: Domain Password
"""


def fake_runner(out=FAKE_CMDKEY_OUTPUT):
    def _run():
        return out, None
    return _run


print("1. only `Target:` lines are read -- nothing from User:/Type:/Persist: lines leaks through")
targets, err = cc.list_targets(runner=fake_runner())
check("no error", err, None)
check("five targets parsed", len(targets), 5)
check("the fabricated User: value never appears in any parsed target",
      any("FAKE-VALUE-DO-NOT-LEAK" in t for t in targets), False)
check("the real target strings came through",
      "LegacyGeneric:target=git:https://github.com" in targets, True)

print("\n2. a failing backend is a reported gap, not a crash")
def failing_runner():
    return None, "cmdkey not found"
targets2, err2 = cc.list_targets(runner=failing_runner)
check("targets is None", targets2, None)
check("error surfaced", err2, "cmdkey not found")

print("\n3. _strip_prefix removes cmdkey's own wrapper, leaving the file-comparable name")
check("LegacyGeneric stripped", cc._strip_prefix("LegacyGeneric:target=git:https://github.com"),
      "git:https://github.com")
check("Domain stripped", cc._strip_prefix("Domain:target=TERMSRV/x"), "TERMSRV/x")
check("no known prefix -- passed through unchanged",
      cc._strip_prefix("gh:github.com:fakeuser"), "gh:github.com:fakeuser")

print("\n4. _host_of recovers a host from a scheme'd or colon-joined target")
check("scheme form", cc._host_of("git:https://github.com"), "github.com")
check("colon-joined form", cc._host_of("gh:github.com:fakeuser"), "github.com")
check("no separator -- returned as-is", cc._host_of("SomeApp.refreshToken"), "SomeApp.refreshToken")

print("\n5. is_dev_relevant separates git/gh/glab/token/api-shaped targets from consumer apps")
check("git url is dev-relevant", cc.is_dev_relevant("git:https://github.com"), True)
check("gh target is dev-relevant", cc.is_dev_relevant("gh:github.com:fakeuser"), True)
check("a refreshToken is dev-relevant (keyword 'token')",
      cc.is_dev_relevant("SomeApp.Vendor.refreshToken"), True)
check("a TERMSRV domain target is not", cc.is_dev_relevant("TERMSRV/some-host"), False)
check("an OneDrive cookie target is not",
      cc.is_dev_relevant("Microsoft_OneDrive_Cookies_v2_Business1_https://x/"), False)

print("\n6. classify: exact match, host-only soft match, and a true gap")
text = "the file mentions `git:https://github.com` verbatim, and separately talks about " \
      "gitlab.com in prose without ever quoting a target string".lower()
check("exact target string -> mentioned", cc.classify("git:https://github.com", text), "mentioned")
check("host appears, exact target does not -> soft",
      cc.classify("gh:gitlab.com:someone", text), "soft")
check("nothing at all -> gap", cc.classify("glab:totally-unheard-of.example:token:", text), "gap")

print("\n7. report(): gaps and soft matches are named; 'other' targets collapse to a count "
     "unless --all")
targets7 = [
    "LegacyGeneric:target=git:https://github.com",       # mentioned
    "LegacyGeneric:target=gh:gitlab.com:someone",         # soft (host only)
    "LegacyGeneric:target=glab:totally-unheard-of.example:token:",  # gap
    "Domain:target=TERMSRV/some-host",                    # other (not dev-relevant)
]
lines_default = cc.report(targets7, text, show_all=False)
lines_all = cc.report(targets7, text, show_all=True)
check("gap is named", any("glab:totally-unheard-of.example:token:" in ln for ln in lines_default),
      True)
check("soft match is named, distinctly worded",
      any("gh:gitlab.com:someone" in ln and "confirm" in ln for ln in lines_default), True)
check("default view: the 'other' target is NOT named, only counted",
      any("TERMSRV/some-host" in ln for ln in lines_default), False)
check("--all: the 'other' target IS named",
      any("TERMSRV/some-host" in ln for ln in lines_all), True)

print("\n8. main(): exit 0 when every dev-relevant target is at least mentioned")
cred_dir = Path(tempfile.mkdtemp(prefix="check-credentials-"))
clean_cred = cred_dir / "CREDENTIALS.md"
clean_cred.write_text("Tracks `git:https://github.com` and `glab:example.test:token:`.\n",
                      encoding="utf-8")

saved = cc.list_targets
cc.list_targets = lambda: (["LegacyGeneric:target=git:https://github.com",
                          "LegacyGeneric:target=glab:example.test:token:"], None)
try:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cc.main(["--credentials-file", str(clean_cred)])
    check("exit 0, nothing missing", rc, 0)

    print("\n9. main(): exit 1 when a dev-relevant target is not mentioned at all")
    cc.list_targets = lambda: (["LegacyGeneric:target=git:https://github.com",
                              "LegacyGeneric:target=gh:totally-untracked.example:someone"], None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cc.main(["--credentials-file", str(clean_cred)])
    out = buf.getvalue()
    check("exit 1", rc, 1)
    check("names the untracked target",
          "gh:totally-untracked.example:someone" in out, True)
    check("never claims to have written anything",
          "Report only" in out, True)

    print("\n10. main(): a missing CREDENTIALS.md is reported, not a crash, and everything is a gap")
    missing = cred_dir / "does-not-exist.md"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cc.main(["--credentials-file", str(missing)])
    out = buf.getvalue()
    check("exit 1", rc, 1)
    check("says the file is not readable", "not readable" in out, True)

    print("\n11. --json emits machine-readable state, still with no value ever printed")
    cc.list_targets = lambda: (["LegacyGeneric:target=git:https://github.com"], None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cc.main(["--json", "--credentials-file", str(clean_cred)])
    payload = json.loads(buf.getvalue())
    check("json ok true", payload["ok"], True)
    check("json names the target", payload["dev_relevant"][0]["target"], "git:https://github.com")
finally:
    cc.list_targets = saved

print("\n12. --help and an unknown flag stop in argparse, before any keyring or file access")
exits("--help exits 0", lambda: cc.main(["--help"]), 0)
exits("-h exits 0", lambda: cc.main(["-h"]), 0)
exits("--bogus-flag exits 2", lambda: cc.main(["--bogus-flag"]), 2)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
