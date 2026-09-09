#!/usr/bin/env python3
"""The issue host layer: detection, and both backends' argv (issue #11, v1.34.0).

    python plugins/cairn/tools/test_issue_host.py

WHY THIS EXISTS. `sync_backlog.py` cannot tell a correct `glab` invocation from a wrong one —
it hands the backend a title and a body and reads back a number. So a mis-spelled flag is
invisible until a real wrap runs against the corporate GitLab, which is a place where the
failure is expensive and the user has already stopped watching. These assertions pin the exact
argv, so the four places `glab` differs from `gh` stay pinned:

  * `iid` is the issue number, not `id`
  * `issue create` needs `--yes` or it BLOCKS on a confirmation prompt
  * `issue close` takes no comment; the note is a second call
  * the label colour needs a leading `#`

Nothing here touches the network, a host, a CLI, or any file in the repo — `IssueHost._run`
is replaced with a recorder, and the config-file reader is pointed at temp fixtures.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(ROOT / "hooks"))

import issue_host as ih                                # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"\n        got={got!r}\n        want={want!r}"))


def recorder(responses=None):
    """Replace `_run`; record argv, answer from a {verb-tuple: stdout} table."""
    calls = []
    table = responses or {}

    def _run(self, *args):
        calls.append(tuple(args))
        return table.get(args[:2], ""), ""
    return calls, _run


class _Patch:
    def __init__(self, run):
        self.run = run

    def __enter__(self):
        self.saved = ih.IssueHost._run
        ih.IssueHost._run = self.run
        return self

    def __exit__(self, *a):
        ih.IssueHost._run = self.saved
        return False


# --------------------------------------------------------------- 1. remote URL parsing

print("1. the origin URL yields a hostname, whatever shape it is in")

CASES = [
    ("https://github.com/example-user/agent-reentry.git", "github.com"),
    ("https://git2.example-corp.net/repo-owner/notes.git", "git2.example-corp.net"),
    ("git@github.com:example-user/agent-reentry.git", "github.com"),
    ("ssh://git@git2.example-corp.net:2222/a-group/a-repo.git", "git2.example-corp.net"),
    ("https://repo-owner@git2.example-corp.net/repo-owner/notes.git", "git2.example-corp.net"),
]
for url, want in CASES:
    saved_git = ih._git
    ih._git = lambda root, *a, _u=url: (_u if a[:1] == ("remote",) else "ok")
    try:
        got, err = ih.remote_host(Path("."))
    finally:
        ih._git = saved_git
    check(f"{url[:48]:<48} -> {want}", got, want)

saved_git = ih._git
ih._git = lambda root, *a: ""            # no remote AND no git dir
try:
    check("no checkout at all is 'not a git repository'",
          ih.remote_host(Path("."))[1], "not a git repository")
finally:
    ih._git = saved_git


# ------------------------------------------------------------------- 2. host -> backend

print("\n2. a hostname picks a backend, and an unknown one picks none")
check("github.com", ih.kind_for_host("github.com"), "github")
check("gitlab.com", ih.kind_for_host("gitlab.com"), "gitlab")
check("gitlab.example.org", ih.kind_for_host("gitlab.example.org"), "gitlab")
check("github.mycorp.net (GHE)", ih.kind_for_host("github.mycorp.net"), "github")
check("codeberg.org -> nothing", ih.kind_for_host("codeberg.org"), "")
check("git2.example-corp.net is NOT guessable from the name",
      ih.kind_for_host("git2.example-corp.net") if not ih._known("glab") else "",
      "")

print("\n2a. …but it IS resolvable from the CLI's own list of logged-in hosts")
tmp = Path(tempfile.mkdtemp())
glab_cfg = tmp / "config.yml"
glab_cfg.write_text(
    "git_protocol: ssh\n"
    "host: git2.example-corp.net\n"
    "hosts:\n"
    "    git2.example-corp.net:\n"
    "        api_protocol: https\n"
    "        token: SHOULD-NEVER-BE-READ\n"
    "        user: repo-owner\n"
    "    gitlab.com:\n"
    "        api_protocol: https\n"
    "        token: ALSO-NEVER\n"
    "telemetry: true\n", encoding="utf-8")
gh_cfg = tmp / "hosts.yml"
gh_cfg.write_text(
    "github.com:\n"
    "    users:\n"
    "        example-user:\n"
    "    oauth_token: NEVER-READ\n"
    "github.mycorp.net:\n"
    "    oauth_token: NEVER-READ\n", encoding="utf-8")

check("glab config: both hosts, no other keys",
      ih._yaml_host_keys(glab_cfg, "hosts"), {"git2.example-corp.net", "gitlab.com"})
check("gh hosts.yml: both hosts", ih._yaml_host_keys(gh_cfg),
      {"github.com", "github.mycorp.net"})
check("no token value is ever returned as a host",
      any("never" in h.lower() for h in ih._yaml_host_keys(glab_cfg, "hosts")), False)

saved_paths = ih._config_paths
ih._config_paths = lambda kind: [glab_cfg] if kind == "glab" else [gh_cfg]
try:
    check("a self-hosted host resolves to gitlab once glab has logged in",
          ih.kind_for_host("git2.example-corp.net"), "gitlab")
    check("an unrelated self-hosted name still resolves to nothing",
          ih.kind_for_host("git.someone-else.net"), "")
finally:
    ih._config_paths = saved_paths


# ------------------------------------------------------------------ 3. GitLab, exactly

print("\n3. the GitLab backend's argv — the four places it differs from gh")
gl = ih.GitLabHost(Path("."), "git2.example-corp.net")

calls, run = recorder({("issue", "create"):
                       "https://git2.example-corp.net/repo-owner/notes/-/issues/19\n"})
with _Patch(run):
    num, err = gl.create("A title", "A body", ["backlog", "afk"])
check("create read the iid back off the URL", (num, err), (19, ""))
argv = calls[0]
check("create passes --yes (or it blocks on a prompt)", "--yes" in argv, True)
check("create uses --description, the flag glab ACTUALLY has", "--description" in argv, True)
check("create carries the body as an argv string", argv[argv.index("--description") + 1], "A body")
# These two are the regression guard for B58. The old assertions pinned
# `--description-file`, a flag glab has never had at any version -- so the suite passed while
# every real GitLab push failed with an opaque `could not file: ERROR`. A test that asserts a
# made-up flag is worse than no test: it certifies the bug.
check("create NEVER passes --description-file (B58)", "--description-file" in argv, False)
check("create does not use gh's --body", "--body" in argv, False)
check("create passes each label separately",
      [argv[i + 1] for i, a in enumerate(argv) if a == "--label"], ["backlog", "afk"])

calls, run = recorder()
with _Patch(run):
    ok, err = gl.close(19, "Done 2026-09-03 — see CHANGELOG.md.")
check("close succeeded", (ok, err), (True, ""))
check("close is TWO calls, close first then the note",
      [c[:2] for c in calls], [("issue", "close"), ("issue", "note")])
check("close itself carries no comment flag",
      any(a.startswith("--comment") for a in calls[0]), False)
check("the note names the issue and carries the message",
      calls[1], ("issue", "note", "19", "--message", "Done 2026-09-03 — see CHANGELOG.md."))

calls, run = recorder()
with _Patch(run):
    gl.close(19)                          # no comment
check("no comment means no second call", [c[:2] for c in calls], [("issue", "close")])

calls, run = recorder()
with _Patch(run):
    gl.update(19, title="New", body="New body")
check("update is `issue update`, not gh's `issue edit`", calls[0][:2], ("issue", "update"))
check("update uses --description", "--description" in calls[0], True)
check("update NEVER passes --description-file (B58)", "--description-file" in calls[0], False)

calls, run = recorder()
with _Patch(run):
    gl.add_labels(19, ["backlog", "hitl"])
check("labels are ADDED via `issue update --label`",
      calls[0][:3] + calls[0][3:], ("issue", "update", "19", "--label", "backlog,hitl"))

calls, run = recorder()
with _Patch(run):
    gl.create_label("afk", "0E8A16", "desc")
check("the label colour gets a leading #",
      calls[0][calls[0].index("--color") + 1], "#0E8A16")
check("the label name goes through --name", "--name" in calls[0], True)

calls, run = recorder({("label", "list"): json.dumps(
    [{"name": "Backlog"}, {"name": "afk"}])})
with _Patch(run):
    have, err = gl.list_labels()
check("label names come back lowercased", (have, err), ({"backlog", "afk"}, ""))


# ---------------------------------------------------------------- 4. normalisation

print("\n4. both providers' JSON normalises to ONE shape")

GITLAB_RAW = [{
    "id": 3445, "iid": 18, "state": "opened",
    "title": "Confirm the .env system", "description": "body text",
    "author": {"username": "repo-owner", "name": "Repo Owner"},
    "labels": ["secret-rotation", "afk"], "created_at": "2026-08-25T20:35:26.84Z",
}]
GITHUB_RAW = [{
    "number": 18, "title": "Confirm the .env system", "body": "body text",
    "author": {"login": "example-user"},
    "labels": [{"name": "secret-rotation"}, {"name": "afk"}],
    "createdAt": "2026-08-25T20:35:26Z",
}]

gl_n = ih.GitLabHost.normalise(GITLAB_RAW)[0]
gh_n = ih.GitHubHost.normalise(GITHUB_RAW)[0]
check("GitLab number is the iid, NOT the global id", gl_n["number"], 18)
check("GitLab description becomes body", gl_n["body"], "body text")
check("GitLab author flattens to a username", gl_n["author"], "repo-owner")
check("GitLab labels are already strings", gl_n["labels"], ["secret-rotation", "afk"])
check("GitHub labels flatten to strings", gh_n["labels"], ["secret-rotation", "afk"])
check("both shapes have the same keys", sorted(gl_n), sorted(gh_n))

print("\n4a. a group-owned GitLab project still has an owner to compare against")
calls, run = recorder({("repo", "view"): json.dumps({
    "path_with_namespace": "some-group/some-project",
    "issues_enabled": True,
    "owner": None,
    "namespace": {"full_path": "some-group"},
})})
with _Patch(run):
    slug, owner, err = gl.repo()
check("slug is path_with_namespace", slug, "some-group/some-project")
check("owner falls back to the group, not to ''", owner, "some-group")

print("\n4b. issues disabled is reported, not guessed past")
calls, run = recorder({("repo", "view"): json.dumps(
    {"path_with_namespace": "x/y", "issues_enabled": False})})
with _Patch(run):
    slug, owner, err = gl.repo()
check("no slug", slug, "")
check("and it is a PERMANENT skip", ih.is_permanent(err), True)


# ------------------------------------------------------------- 5. permanent vs retry

print("\n5. `is_permanent` decides which sentence a skip line prints")
check("a missing CLI is worth retrying", ih.is_permanent("glab is not installed"), False)
check("a 401 is worth retrying", ih.is_permanent("401 Unauthorized"), False)
check("an unsupported host never will be",
      ih.is_permanent("no issue host backend for codeberg.org — GitHub and GitLab"), True)
check("nor will a repo with no remote", ih.is_permanent("no git remote called origin"), True)
check("nor a non-repo", ih.is_permanent("not a git repository"), True)


# ------------------------------------------------------- 6. --ingest shape detection

print("\n6. --ingest tells the two JSON schemas apart without being told")
sys.path.insert(0, str(ROOT / "hooks"))
import issues_backlog as ib                            # noqa: E402

got, err = ib._normalise_payload(GITLAB_RAW)
check("GitLab JSON detected by `iid`", (got[0]["number"], err), (18, ""))
got, err = ib._normalise_payload(GITHUB_RAW)
check("GitHub JSON detected by `number`", (got[0]["author"], err), ("example-user", ""))
got, err = ib._normalise_payload(GITLAB_RAW, "github")
check("an explicit --host wins over the shape", got[0]["number"], None)
check("…and reading the WRONG shape does not raise — labels survive either way",
      got[0]["labels"], ["secret-rotation", "afk"])
got, err = ib._normalise_payload([{"nonsense": 1}])
check("neither shape is an honest error, not a guess", got, None)
check("and it says so", "could not tell" in err, True)

print("\n7. `inbound` survives the round trip through the cache builder")
built = ib._build("repo-owner/notes", "repo-owner", ih.GitLabHost.normalise(GITLAB_RAW), "GitLab")
check("their own issue is not inbound", built["issues"][0]["inbound"], False)
built = ib._build("repo-owner/notes", "someone-else",
                  ih.GitLabHost.normalise(GITLAB_RAW), "GitLab")
check("another owner's repo makes it inbound", built["issues"][0]["inbound"], True)
check("the cache records which host it came from", built["host"], "GitLab")

print("\n8. B38 — a missing CLI SEARCHES known Windows spots before saying 'not installed'")

saved_probe = ih._install_probe_paths
try:
    # 8a. nowhere the probe looks has it: honest "not found on PATH", never "not installed"
    # (the false claim B38 reported: a reader sent off to install something already there).
    ih._install_probe_paths = lambda cli: [Path(tempfile.mkdtemp()) / f"{cli}.exe"]
    check("nothing found anywhere: PATH wording", ih._not_on_path_message("gh"),
          "gh not found on PATH")
    check("...and it NEVER claims the CLI does not exist",
          "not installed" in ih._not_on_path_message("glab"), False)

    # 8b. found at a probed location: names the real path, says PATH not existence.
    tmp = Path(tempfile.mkdtemp())
    fake_glab = tmp / "glab.exe"
    fake_glab.write_text("stub", encoding="utf-8")
    ih._install_probe_paths = lambda cli: [fake_glab] if cli == "glab" else []
    check("found elsewhere names the real path, not just 'installed'",
          ih._not_on_path_message("glab"), f"glab is installed at {fake_glab} but not on PATH")
    check("a DIFFERENT cli than the one found still reads as not found",
          ih._not_on_path_message("gh"), "gh not found on PATH")
finally:
    ih._install_probe_paths = saved_probe

print("\n8c. the real probe finds gh AND glab for real, on THIS machine (2026-09-05:"
      " gh 2.99.0, glab 1.116.0, both installed) — not just the mocked case above")
real_gh = ih._find_installed("gh")
real_glab = ih._find_installed("glab")
print(f"        gh  -> {real_gh or '(not found by the probe on this machine)'}")
print(f"        glab-> {real_glab or '(not found by the probe on this machine)'}")
check("gh is findable by the real probe on this machine", bool(real_gh), True)
check("glab is findable by the real probe on this machine", bool(real_glab), True)
check("the found gh path really exists on disk", Path(real_gh).is_file() if real_gh else False, True)
check("the found glab path really exists on disk",
      Path(real_glab).is_file() if real_glab else False, True)

# ------------------------------------------------------------ 9. B82 — page until exhausted

print("\n9. B82 — `limit=None` means every issue, not the newest N")

print("9a. GitHub: `gh` has no `--all`; a `limit=None` ask ships an unbounded --limit")
gh9 = ih.GitHubHost(Path("."), "github.com")
calls, run = recorder({("issue", "list"): json.dumps(
    [{"number": 1, "title": "x", "body": "", "author": {"login": "a"}, "labels": []}])})
with _Patch(run):
    issues, err = gh9.list_issues(state="all", limit=None)
argv = calls[0]
check("the old default 100 is NOT what gets asked for",
      argv[argv.index("--limit") + 1] != "100", True)
check("it asks for the class's own unbounded sentinel, not a made-up number in the test",
      argv[argv.index("--limit") + 1], str(gh9._UNBOUNDED))
check("state=all still passed through", "--state" in argv and "all" in argv, True)
calls2, run2 = recorder({("issue", "list"): "[]"})
with _Patch(run2):
    gh9.list_issues()
check("an ordinary call (limit defaults to 100) is untouched by the B82 fix",
      calls2[0][calls2[0].index("--limit") + 1], "100")

print("\n9b. GitLab: `--per-page` caps at one page regardless of size — `limit=None` "
      "walks `--page` instead")
gl9 = ih.GitLabHost(Path("."), "git2.example-corp.net")


def _page_of(n_start, n_end):
    return [{"iid": i, "title": f"t{i}", "description": "", "author": {"username": "a"},
             "labels": []} for i in range(n_start, n_end)]


PAGE1, PAGE2, PAGE3 = _page_of(1, 101), _page_of(101, 201), _page_of(201, 208)  # 100+100+7


def _paged_run(pages):
    def _run(self, *args):
        page = int(args[args.index("--page") + 1])
        batch = pages[page - 1] if page - 1 < len(pages) else []
        return json.dumps(batch), ""
    return _run


saved_run = ih.IssueHost._run
ih.IssueHost._run = _paged_run([PAGE1, PAGE2, PAGE3])
try:
    issues, err = gl9.list_issues(state="all", limit=None)
finally:
    ih.IssueHost._run = saved_run
check("all three pages collected (100 + 100 + 7 = 207), not just the first hundred",
      len(issues) if issues is not None else -1, 207)
check("no error", err, "")
check("the search stopped at the short page, not a fixed page COUNT",
      issues[-1]["number"] if issues else None, 207)

print("9c. a page failing partway through fails the WHOLE call — never a partial 'known' set")


def _fail_on_page_2(self, *args):
    page = int(args[args.index("--page") + 1])
    if page == 1:
        return json.dumps(PAGE1), ""
    return None, "glab: network blip"


saved_run = ih.IssueHost._run
ih.IssueHost._run = _fail_on_page_2
try:
    issues, err = gl9.list_issues(state="all", limit=None)
finally:
    ih.IssueHost._run = saved_run
check("a mid-loop failure returns None, NOT the 100 already collected — a partial 'known' "
      "set would silently under-report which issues exist and flag real ones as bogus "
      "(B37, one level up)", issues, None)
check("the failure is named", "network blip" in err, True)

print("9d. a host that never returns a short page stops at the loop's own runaway guard "
      "rather than spinning forever")


def _always_full(self, *args):
    return json.dumps(PAGE1), ""            # 100 items, every page, forever


gl9d = ih.GitLabHost(Path("."), "git2.example-corp.net")
gl9d._MAX_PAGES = 3                          # override so the test does not loop 500 times
saved_run = ih.IssueHost._run
ih.IssueHost._run = _always_full
try:
    issues, err = gl9d.list_issues(state="all", limit=None)
finally:
    ih.IssueHost._run = saved_run
check("stopped at MAX_PAGES * PAGE_SIZE rather than looping forever", len(issues), 300)
check("the guard tripping is not itself reported as an error", err, "")

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
