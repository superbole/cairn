#!/usr/bin/env python3
"""The B49 issue-host readiness section of `check_install.py`, plus the fallthrough refactor
it required.

    python plugins/cairn/tools/test_check_install.py

WHY THIS EXISTS. Before B49, `main()` returned early from each version-drift branch (UNKNOWN /
STALE / OK) -- adding a section that must print in EVERY branch meant turning those `return`s
into a single `rc` computed once at the end, which is exactly the kind of refactor a later edit
can silently re-break (one more `return 1` slipped back into a branch, and the new section goes
quiet for that case forever). Section 5 below pins that fallthrough for all three branches.

THE READINESS SECTION ITSELF answers three questions in order -- which host does `origin`
imply, is that host's CLI reachable, is it authenticated to THAT host specifically -- and each
one has its own remedy line. The one this file protects hardest is the wrong-host trap: `glab`
(or `gh`) logged into a DIFFERENT host than the project's remote must never read as
"authenticated", because a previous session printed a bare `gh auth login` during a GitLab
conversation and the user pasted a token into a prompt that could never have worked (see
`check_install.py`'s own docstring). Section 4d reproduces that exact shape against a fixture.

NOTHING HERE TOUCHES THE NETWORK, A REAL CLI, OR `~/.claude`. `_run_cli` -- the one function that
would shell out to `gh`/`glab` -- is never exercised directly; every auth-status behaviour is
tested through `_auth_state` with `_run_cli` replaced, or through `issue_host_report` with
`_locate_cli`/`_auth_state` replaced. `_config_dir` is always pointed at a throwaway
`tempfile.mkdtemp()` directory, never at the real config dir.
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tools"))

import check_install as ci                              # noqa: E402
import issue_host                                        # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def any_line(out, needle):
    return any(needle in ln for ln in out)


class _FakeHost:
    def __init__(self, cli, name, host):
        self.cli, self.name, self.host = cli, name, host


print("1. _locate_cli — on PATH, off PATH via issue_host's own probe, missing from both")
# `_find_installed` is `issue_host.py`'s (B38, landed the same day as this file's B49 work) --
# reused here rather than re-probing Windows install locations a second time. This section
# pins the SEAM (check_install calls `issue_host._find_installed`), not that function's own
# probe list, which is `test_issue_host.py`'s job.
saved_which = ci.shutil.which
saved_find = issue_host._find_installed

ci.shutil.which = lambda cli: (r"C:\fake\gh.exe" if cli == "gh" else None)
state, path = ci._locate_cli("gh")
check("on PATH", state, "path")
check("on PATH — path is what which() returned", path, r"C:\fake\gh.exe")

ci.shutil.which = lambda cli: None
issue_host._find_installed = lambda cli: (r"C:\fake\install\gh.exe" if cli == "gh" else "")
state, path = ci._locate_cli("gh")
check("off-path found via issue_host._find_installed", state, "off-path")
check("off-path — path is what the probe returned", path, r"C:\fake\install\gh.exe")

issue_host._find_installed = lambda cli: ""
state, path = ci._locate_cli("gh")
check("missing when neither which() nor issue_host's probe finds it", state, "missing")
check("missing — no path", path, "")

ci.shutil.which = saved_which
issue_host._find_installed = saved_find

print("\n2. _auth_detail strips the bare hostname header and glab's blank/ERROR banner")
raw = ("gitlab.com\n"
       "  x gitlab.com: API call failed: GET https://gitlab.com/api/v4/user: 401 "
       "{message: 401 Unauthorized}\n"
       "  \u2713 Git operations for gitlab.com configured to use ssh protocol.\n"
       "          \n"
       "   ERROR  \n"
       "          \n"
       "  X could not authenticate to one or more of the configured GitLab instances.\n")
detail = ci._auth_detail(raw, "gitlab.com")
check("real message picked, not the header", detail.startswith("gitlab.com: API call failed"), True)
check("never just the bare hostname", detail.strip().lower() == "gitlab.com", False)
check("the ERROR banner line is not picked", detail.strip().upper() == "ERROR", False)
check("blank input never raises", ci._auth_detail("", "gitlab.com"), "")
check("output with only a header and a banner collapses to empty",
      ci._auth_detail("gitlab.com\n  \n  ERROR  \n  \n", "gitlab.com"), "")

print("\n3. _auth_state maps a real subprocess call's (rc, text) into one of four states")
saved_run = ci._run_cli
ci._run_cli = lambda args, timeout=ci.AUTH_TIMEOUT: (0, "")
check("rc 0 -> authenticated", ci._auth_state("gh", "github.com"), ("authenticated", ""))
ci._run_cli = lambda args, timeout=ci.AUTH_TIMEOUT: (-1, "")
check("rc -1 (timed out) -> timeout, never treated as unauthenticated",
      ci._auth_state("glab", "git2.example-corp.net"), ("timeout", ""))
ci._run_cli = lambda args, timeout=ci.AUTH_TIMEOUT: (-2, "")
astate, adetail = ci._auth_state("gh", "github.com")
check("rc -2 (could not start) -> error", astate, "error")
check("error detail falls back to a sentence when there is nothing to parse",
      "could not be run" in adetail, True)
ci._run_cli = lambda args, timeout=ci.AUTH_TIMEOUT: (
    1, "gitlab.com\n  x gitlab.com: could not authenticate\n")
astate, adetail = ci._auth_state("glab", "gitlab.com")
check("rc 1 -> unauthenticated", astate, "unauthenticated")
check("…with the filtered detail line, not the header", "could not authenticate" in adetail, True)
ci._run_cli = saved_run

print("\n4. issue_host_report assembles the right section for each case")
saved_detect = issue_host.detect
saved_locate = ci._locate_cli
saved_authstate = ci._auth_state

print("   4a. no issue host at all (unsupported remote, no remote, not a git repo)")
issue_host.detect = lambda root, override="": (None, "not a git repository")
out = ci.issue_host_report(Path("."))
check("names the reason", any_line(out, "not a git repository"), True)
check("reassures BACKLOG.md still works with no host", any_line(out, "BACKLOG.md keeps working"), True)
check("never reaches a cli/auth line", any(ln.startswith(("cli", "auth")) for ln in out), False)

print("   4b. CLI not installed at all")
issue_host.detect = lambda root, override="": (_FakeHost("gh", "GitHub", "github.com"), "")
ci._locate_cli = lambda cli: ("missing", "")
out = ci.issue_host_report(Path("."))
check("says NOT INSTALLED", any_line(out, "NOT INSTALLED"), True)
check("gives an install link for THIS cli (gh)", any_line(out, "cli.github.com"), True)
check("never reaches an auth line — nothing to check auth with", any(ln.startswith("auth") for ln in out), False)

print("   4c. CLI installed but off PATH — a different remedy than reinstalling")
ci._locate_cli = lambda cli: ("off-path", r"C:\fake\install\gh.exe")
out = ci.issue_host_report(Path("."))
check("says OFF PATH and names the found path", any_line(out, "OFF PATH") and any_line(out, "fake"), True)
check("remedy is fixing PATH, not reinstalling", any_line(out, "add that folder to PATH"), True)
check("still never reaches an auth line", any(ln.startswith("auth") for ln in out), False)

print("   4d. the wrong-host trap — glab authenticated, but to a DIFFERENT host than the remote")
issue_host.detect = lambda root, override="": (_FakeHost("glab", "GitLab", "gitlab.com"), "")
ci._locate_cli = lambda cli: ("path", "/usr/bin/glab")
ci._auth_state = lambda exe, host: (
    "unauthenticated", "gitlab.com: API call failed: GET .../user: 401 {message: 401 Unauthorized}")
out = ci.issue_host_report(Path("."))
check("names the actual host it is NOT authenticated to", any_line(out, "NOT authenticated to gitlab.com"), True)
check("calls out the different-host mix-up explicitly", any_line(out, "DIFFERENT host does not count"), True)
check("remedy names --hostname explicitly, never a bare `glab auth login`",
      "remedy    : glab auth login --hostname gitlab.com --web" in out, True)

print("   4e. the healthy path — on PATH and authenticated to the right host")
ci._auth_state = lambda exe, host: ("authenticated", "")
out = ci.issue_host_report(Path("."))
check("OK line names the host", any_line(out, "OK — logged in to gitlab.com"), True)
check("no remedy line when everything checks out", any(ln.startswith("remedy") for ln in out), False)

print("   4f. auth status timed out — inconclusive, not a failure")
ci._auth_state = lambda exe, host: ("timeout", "")
out = ci.issue_host_report(Path("."))
check("reported as inconclusive", any_line(out, "Not a failure"), True)
check("no auth-login remedy printed for a mere timeout", any(ln.startswith("remedy") for ln in out), False)

issue_host.detect = saved_detect
ci._locate_cli = saved_locate
ci._auth_state = saved_authstate

print("\n5. main()'s exit code is governed ONLY by the version-drift check, in EVERY branch")
saved_config_dir = ci._config_dir
saved_repo_version = ci._repo_version
saved_report = ci.issue_host_report
ci._repo_version = lambda start: (None, None)


def _set_config(installed_version, rules_version, missing=False):
    cfg = Path(tempfile.mkdtemp())
    if not missing:
        (cfg / "plugins").mkdir()
        (cfg / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"plugins": {"cairn@superbole": [{"version": installed_version}]}}),
            encoding="utf-8")
        (cfg / "CLAUDE.md").write_text(
            f"<!-- reentry:begin v{rules_version} -->\nstuff\n<!-- reentry:end -->\n",
            encoding="utf-8")
    ci._config_dir = lambda: cfg


print("   5a. OK branch: a crash inside the issue-host section must not fail the version check")
_set_config("1.39.0", "1.39.0")
ci.issue_host_report = lambda root: (_ for _ in ()).throw(RuntimeError("boom"))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = ci.main()
check("rc 0 — versions agree, a broken readiness section does not change that", rc, 0)
check("the crash is reported, not swallowed silently",
      "issue host readiness check skipped" in buf.getvalue(), True)

print("   5b. STALE branch (rules != installed): rc 1 even though the readiness section is healthy")
_set_config("1.39.0", "1.30.0")
ci.issue_host_report = lambda root: ["", "--- issue host sync ---", "auth      : OK — logged in to github.com"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = ci.main()
check("rc 1 — a genuine version mismatch, unaffected by a HEALTHY issue-host report", rc, 1)
check("the issue-host section still printed", "auth      : OK" in buf.getvalue(), True)

print("   5b2. STALE the other way (B63): rules NEWER than the plugin -- restart will not resync")
_set_config("1.60.0", "1.62.0")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = ci.main()
check("rc 1 — still a mismatch", rc, 1)
check("says the rules are the newer side", "NEWER than the installed plugin v1.60.0" in buf.getvalue(), True)
check("does NOT promise a restart resyncs", "resyncs the" in buf.getvalue(), False)
check("names the plugin update", "claude plugin update cairn@superbole" in buf.getvalue(), True)

print("   5c. UNKNOWN branch (no installed_plugins.json at all): the section still runs")
_set_config(None, None, missing=True)
ci.issue_host_report = lambda root: ["", "--- issue host sync ---", "host      : irrelevant here"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = ci.main()
check("rc 1 for UNKNOWN install state", rc, 1)
check("issue-host section still printed even though the version state is UNKNOWN",
      "issue host sync" in buf.getvalue(), True)

print("   5d. B26: the block digest line — present, comparable, never content, never the exit code")
_set_config("1.39.0", "1.39.0")
cfg = ci._config_dir()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = ci.main()
want = ci.install_rules.block_digest("<!-- reentry:begin v1.39.0 -->\nstuff\n<!-- reentry:end -->\n")
check("digest line printed", f"block     : {want} (installed)" in buf.getvalue(), True)
check("no block content printed", "stuff" in buf.getvalue(), False)
check("rc unchanged (0, versions agree)", rc, 0)
(cfg / "CLAUDE.md").write_text("my own notes\n" + (cfg / "CLAUDE.md").read_text("utf-8"), encoding="utf-8")
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    ci.main()
check("text OUTSIDE the markers does not change the digest",
      f"block     : {want} (installed)" in buf2.getvalue(), True)

repo = Path(tempfile.mkdtemp())
(repo / "plugins" / "cairn" / "rules").mkdir(parents=True)
(repo / "plugins" / "cairn" / "rules" / "CLAUDE.md").write_text("# rules\n\nthe repo's text\n", encoding="utf-8")
ci._repo_version = lambda start: ("1.39.0", repo)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = ci.main()
check("same version, different block: flagged", "SAME version, DIFFERENT block" in buf.getvalue(), True)
check("...and the exit code is still unchanged", rc, 0)
(cfg / "CLAUDE.md").write_text(ci.install_rules._block("1.39.0", "# rules\n\nthe repo's text\n"), encoding="utf-8")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ci.main()
check("matching block: not flagged", "DIFFERENT block" in buf.getvalue(), False)
ci._repo_version = lambda start: (None, None)
(cfg / "CLAUDE.md").write_text("<!-- reentry:begin v1.39.0 -->\nno end\n", encoding="utf-8")
check("malformed block reported as such, not crashed",
      ci._installed_block_digest(cfg).startswith("(malformed"), True)

ci._config_dir = saved_config_dir
ci._repo_version = saved_repo_version
ci.issue_host_report = saved_report

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
