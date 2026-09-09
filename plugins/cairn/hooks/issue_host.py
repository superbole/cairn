#!/usr/bin/env python3
"""The ISSUE HOST layer — one interface, two backends: GitHub via `gh`, GitLab via `glab`.

WHY THIS FILE EXISTS (issue #11, B11, 2026-09-03)
-------------------------------------------------
The user, 2026-08-31: *"The plugin needs to work on both GitHub and GitLab, my personal code
is in the public GitHub and my work sits in the corporate on-prem GitLab (git2.example-corp.net)."*

Before this, the whole issue layer shelled out to `gh` and nothing else — `tools/sync_backlog.py`,
`tools/label_backlog.py`, `hooks/issues_backlog.py`. On a GitLab remote every one of them
degraded gracefully and correctly, and said so, which meant **the entire work side of their
portfolio was permanently outside the sync layer**. That was a missing feature, not a breakage,
and this file is the feature.

Measured on ORG-LAPTOP1, 2026-09-03: `glab` 1.116.0 installed and authenticated against
`git2.example-corp.net`; `gh` NOT INSTALLED AT ALL. So on this laptop the GitHub backend is the
one that cannot run. That is the argument for a real interface rather than an `if gitlab:`
branch bolted onto the `gh` path — neither backend is the privileged one, and on any given
machine either may be the absent one.

THE NAME IS "ISSUE HOST", DELIBERATELY NOT "FORGE"
--------------------------------------------------
B11 originally specified "a small forge interface". The word collided with a name already in use
in one of the user's own projects, and made them stop and ask what it meant (B19). `issue host` is the neutral term this
plugin now uses for "the thing on the other end of the git remote that stores issues".
**B19 should adopt this word rather than renaming this module.**

DETECTION IS FROM THE GIT REMOTE, NEVER FROM CONFIGURATION
----------------------------------------------------------
A config key naming the host is one more thing that can be right on one machine and wrong on
another — the exact class of problem B23 exists for, and this plugin runs on three machines.
So the host is derived, in this order, from things that are already true:

  1. the `origin` URL's hostname;
  2. an unambiguous public host (`github.com`, `gitlab.com`, anything with a `gitlab` label);
  3. for a self-hosted instance, **the CLI's own list of hosts they have already logged into** —
     `glab`'s `config.yml` and `gh`'s `hosts.yml`. `git2.example-corp.net` contains neither
     "gitlab" nor "github", so step 2 cannot see it; step 3 finds it because they authenticated
     `glab` against it, which is a fact about the machine and not a setting to keep in sync.

Only the host KEYS are read out of those config files. Both files also hold tokens; nothing
here reads, stores, logs or prints one.

EVERY BACKEND RETURNS THE SAME SHAPES
-------------------------------------
Callers see one normalised issue dict and never a provider's own JSON:

    {"number": int, "title": str, "body": str, "author": str, "labels": [str]}

`number` is GitHub's `number` and GitLab's `iid` — the project-relative number that `#18`
means in both UIs. GitLab's global `id` is deliberately discarded: it is not what `BACKLOG.md`
writes and not what they see on their phone.

FAILURE IS A SENTENCE, NEVER AN EXCEPTION
-----------------------------------------
Same contract as everything else in this plugin: a wrap must never fail over the backlog, and a
session start must never break over it. Every method returns `(result, error)` and the error is
a human sentence fit to print in a skip line.

`is_permanent()` is the v1.22.1 lesson generalised. "The next wrap where the CLI works will push
them" is TRUE for a missing CLI or an expired token and FALSE FOREVER for a host nobody has
written a backend for. Saying it anyway left a wrap sounding like the sync was pending when
nothing would ever pick it up.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from reentry_state import NO_WINDOW
except Exception:                        # pragma: no cover — stays usable standalone
    NO_WINDOW: dict = {}

TIMEOUT = 30

# The four labels the backlog uses. Colours are stored bare; each backend adds whatever
# prefix its CLI wants (`gh` takes bare hex, `glab` wants a leading `#`).
LABELS = {
    "backlog":   ("6E7781", "Not in the NEXT.md working set; picked up when the Queue has room"),
    "displaced": ("C5DEF5", "Was on the NEXT.md Queue and was pushed off by something more urgent"),
    "afk":       ("0E8A16", "Backlog: can be started and left to run unattended"),
    "hitl":      ("D93F0B", "Backlog: will stop and need you — decision, credential, push or eyes on a result"),
}

# Errors that no amount of waiting will fix. Anything else is worth retrying at the next wrap.
_PERMANENT = ("no issue host backend", "not a git repository", "no git remote",
              "issues are disabled")


def is_permanent(err: str) -> bool:
    """Will another wrap ever fix this? Decides which sentence the skip line prints."""
    low = (err or "").lower()
    return any(p in low for p in _PERMANENT)


# --------------------------------------------------------------------- remote detection


def _git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(("git", *args), cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10, **NO_WINDOW,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except Exception:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def remote_host(root: Path) -> tuple[str, str]:
    """(hostname, error) from `origin`. Handles https, ssh://, and scp-style `git@host:path`."""
    url = _git(root, "remote", "get-url", "origin")
    if not url:
        if not _git(root, "rev-parse", "--git-dir"):
            return "", "not a git repository"
        return "", "no git remote called origin"
    u = url.strip()
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^@/]+@)?([^/:]+)", u)   # scheme://[user@]host
    if not m:
        m = re.match(r"^(?:[^@/]+@)([^:/]+):", u)                          # git@host:owner/repo
    if not m:
        return "", f"could not read a hostname out of the origin URL ({u[:60]})"
    return m.group(1).lower().rstrip("."), ""


def _yaml_host_keys(path: Path, section: str = "") -> set[str]:
    """Host keys out of a `gh`/`glab` config file, WITHOUT a YAML dependency.

    Both files are machine-written and flat where it matters: `gh`'s `hosts.yml` has the
    hostnames at column 0, `glab`'s `config.yml` nests them one level under `hosts:`. A
    short reader beats adding PyYAML to a plugin that currently has no dependencies at all
    and has to run under whatever Python each of three machines resolves.

    Reads KEYS ONLY. Both files also contain tokens; none is read, kept or printed.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return set()
    out: set[str] = set()
    if not section:
        for ln in lines:
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z0-9.\-]+):\s*$", ln)
            if m:
                out.add(m.group(1).lower())
        return out
    inside = False
    indent = 0
    for ln in lines:
        if re.match(r"^" + re.escape(section) + r":\s*$", ln):
            inside, indent = True, 0
            continue
        if not inside:
            continue
        if ln.strip() and not ln.startswith((" ", "\t")):
            break                                        # back to column 0: section over
        m = re.match(r"^(\s+)([A-Za-z0-9][A-Za-z0-9.\-]*):\s*$", ln)
        if not m:
            continue
        width = len(m.group(1))
        if indent == 0:
            indent = width
        if width == indent:
            out.add(m.group(2).lower())
    return out


def _config_paths(kind: str) -> list[Path]:
    """Where each CLI keeps its host list, across the three machines this runs on."""
    home = Path(os.path.expanduser("~"))
    xdg = os.environ.get("XDG_CONFIG_HOME") or ""
    out: list[Path] = []
    if kind == "glab":
        local = os.environ.get("LOCALAPPDATA") or ""
        if local:
            out.append(Path(local) / "glab-cli" / "config.yml")
        out.append(home / ".config" / "glab-cli" / "config.yml")
        if xdg:
            out.append(Path(xdg) / "glab-cli" / "config.yml")
    else:
        out.append(home / ".config" / "gh" / "hosts.yml")
        appdata = os.environ.get("APPDATA") or ""
        if appdata:
            out.append(Path(appdata) / "GitHub CLI" / "hosts.yml")
        if xdg:
            out.append(Path(xdg) / "gh" / "hosts.yml")
    return out


def _known(kind: str) -> set[str]:
    section = "hosts" if kind == "glab" else ""
    out: set[str] = set()
    for p in _config_paths(kind):
        out |= _yaml_host_keys(p, section)
    return out


def _install_probe_paths(cli: str) -> list[Path]:
    """Where `gh`/`glab` actually land on Windows when installed but NOT on PATH (B38).

    Verified against a real machine, 2026-09-05: `gh` at
    `C:\\Program Files\\GitHub CLI\\gh.exe` (the MSI/winget layout) and `glab` at
    `%LOCALAPPDATA%\\Programs\\glab\\glab.exe` (its per-user installer) — both installed,
    both authenticated, and both simply one PATH entry short. The rest of this list is the
    other common Windows package-manager layouts (`Program Files (x86)`, a user-level
    `Programs\\<Name>`, winget's own Links shim, scoop's shim dir) so the same probe has a
    reasonable shot on a machine set up a different way, not just this one.

    Same shape as `_config_paths()` above — a short, explicit list beats a dependency, and
    both exist because a Windows CLI's location is a fact about the machine, never a setting.
    """
    home = Path(os.path.expanduser("~"))
    pf = os.environ.get("PROGRAMFILES") or r"C:\Program Files"
    pf86 = os.environ.get("PROGRAMFILES(X86)") or r"C:\Program Files (x86)"
    local = os.environ.get("LOCALAPPDATA") or ""
    exe = cli + ".exe"
    out: list[Path] = []
    if cli == "gh":
        out.append(Path(pf) / "GitHub CLI" / exe)
        out.append(Path(pf86) / "GitHub CLI" / exe)
        if local:
            out.append(Path(local) / "Programs" / "GitHub CLI" / exe)
    elif cli == "glab":
        if local:
            out.append(Path(local) / "Programs" / "glab" / exe)
        out.append(Path(pf) / "GLab CLI" / exe)
        out.append(Path(pf) / "GitLab CLI" / exe)
    if local:
        out.append(Path(local) / "Microsoft" / "WinGet" / "Links" / exe)
    out.append(home / "scoop" / "shims" / exe)
    return out


def _find_installed(cli: str) -> str:
    """First existing path for `cli` outside PATH, or `""` if none of the probe spots have it.

    This is the B38 fix: `_run` used to read a bare `FileNotFoundError` as "not installed"
    with no search behind it — the B20 failure (asserting absence rather than checking for
    it) in a new spot. A missing CLI and a CLI one PATH entry away raise the exact same
    exception; only a search tells them apart.
    """
    for p in _install_probe_paths(cli):
        try:
            if p.is_file():
                return str(p)
        except OSError:
            continue
    return ""


def _not_on_path_message(cli: str) -> str:
    """The sentence `_run` prints for a `FileNotFoundError` — never claims non-existence
    (B38): "not installed" sent a reader off to install something already on the machine,
    on the one Windows box where `gh` was on the PATH of every OTHER shell but this one.
    """
    found = _find_installed(cli)
    if found:
        return f"{cli} is installed at {found} but not on PATH"
    return f"{cli} not found on PATH"


def kind_for_host(host: str) -> str:
    """`github` | `gitlab` | `` — from the hostname, then from the CLIs' own host lists."""
    h = (host or "").lower()
    if not h:
        return ""
    labels = h.split(".")
    if h == "github.com" or h.endswith(".github.com"):
        return "github"
    if h == "gitlab.com" or h.endswith(".gitlab.com") or "gitlab" in labels:
        return "gitlab"
    if "github" in labels:                               # github.mycorp.net — a GHE instance
        return "github"
    # Self-hosted with a name that says nothing (git2.example-corp.net). Ask the CLIs which
    # hosts they have actually logged into; that is a fact about this machine, not a setting.
    if h in _known("glab"):
        return "gitlab"
    if h in _known("gh"):
        return "github"
    return ""


# ------------------------------------------------------------------------- the interface


class IssueHost:
    """One backend. Every method returns `(result, error)`; nothing here raises."""

    name = ""                                            # "GitHub" / "GitLab" — for prose
    cli = ""                                             # "gh" / "glab" — for error lines

    @staticmethod
    def _label_names(raw) -> list[str]:
        """Label names out of EITHER shape — `[{"name": …}]` or `["…"]`.

        `gh --json labels` gives objects and `glab --output json` gives plain strings, so
        each backend's `normalise` only ever meets one of them in normal use. It is shared
        anyway because `--ingest --host github` can be pointed at GitLab JSON by hand, and
        the old per-backend version raised `AttributeError` when it was — a hard crash in a
        layer whose entire contract is "returns a sentence, never raises". Caught by
        `test_issue_host.py` before it ever ran for real.
        """
        out = []
        for l in raw or []:
            if isinstance(l, str):
                if l:
                    out.append(l)
            elif isinstance(l, dict) and l.get("name"):
                out.append(l["name"])
        return out

    def __init__(self, root: Path, host: str = "", repo_override: str = "") -> None:
        self.root = Path(root)
        self.host = host
        # `-R owner/repo`, which BOTH CLIs accept on every verb used here. Only
        # `label_backlog.py --repo` sets it: acting on a repo other than the checkout you
        # are standing in. The BACKEND still comes from the checkout's own remote, because
        # that is the only thing that says which CLI can talk to it.
        self.repo_override = repo_override

    # -- the shared subprocess shim ----------------------------------------------------
    def _run(self, *args: str) -> tuple[str | None, str]:
        if self.repo_override:
            args = (*args, "-R", self.repo_override)
        try:
            r = subprocess.run((self.cli, *args), cwd=self.root, capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               timeout=TIMEOUT, **NO_WINDOW,
                               env={**os.environ, "GIT_TERMINAL_PROMPT": "0",
                                    "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"})
        except FileNotFoundError:
            return None, _not_on_path_message(self.cli)
        except Exception as exc:
            return None, f"{self.cli} failed: {type(exc).__name__}"
        if r.returncode != 0:
            # Skip blank and rule-only lines. glab prints a BANNER on error --
            #
            #     (blank)
            #        ERROR
            #     (blank)
            #       Unknown flag: --description-file.
            #
            # so `lines[0]` was the banner word, and every B58 failure surfaced as a bare
            # `could not file: ERROR` with the actual cause one line further down and never
            # printed. A CLI flag drifting under us must name itself in the log (B58, 2026-09-04).
            lines = [ln.strip() for ln in (r.stderr or "").splitlines()]
            lines = [ln for ln in lines if ln and ln.strip("=-_ ").upper() not in ("", "ERROR")]
            return None, (lines[0][:200] if lines else f"{self.cli} returned non-zero")
        return r.stdout, ""

    @staticmethod
    def _body_file(text: str) -> str:
        """Write a body to a temp file and return its path.

        A FILE, NEVER A PIPE. PowerShell 5.1 re-encodes anything piped into a native
        executable and has already corrupted one payload in this repo (2026-08-22).
        """
        fd, tmp = tempfile.mkstemp(suffix=".md", text=False)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return tmp

    # -- what every caller needs -------------------------------------------------------
    def repo(self) -> tuple[str, str, str]:              # pragma: no cover - overridden
        raise NotImplementedError

    def list_issues(self, limit: int | None = 100,
                    state: str = "open") -> tuple[list[dict] | None, str]:
        """`limit=None` means every issue, not the newest N (B82) — page until exhausted."""
        raise NotImplementedError

    def create(self, title: str, body: str, labels: list[str]) -> tuple[int | None, str]:
        raise NotImplementedError

    def close(self, number: int, comment: str = "") -> tuple[bool, str]:
        raise NotImplementedError

    def update(self, number: int, title: str = "", body: str = "") -> tuple[bool, str]:
        raise NotImplementedError

    def add_labels(self, number: int, labels: list[str]) -> tuple[bool, str]:
        raise NotImplementedError

    def list_labels(self) -> tuple[set[str] | None, str]:
        raise NotImplementedError

    def create_label(self, name: str, colour: str, description: str) -> tuple[bool, str]:
        raise NotImplementedError


class GitHubHost(IssueHost):
    name = "GitHub"
    cli = "gh"

    def repo(self) -> tuple[str, str, str]:
        out, err = self._run("repo", "view", "--json", "nameWithOwner,hasIssuesEnabled,owner")
        if out is None:
            return "", "", err
        try:
            meta = json.loads(out)
        except Exception:
            return "", "", "could not parse `gh repo view`"
        if not meta.get("hasIssuesEnabled"):
            return "", "", "issues are disabled on this repo"
        return (meta.get("nameWithOwner") or "",
                ((meta.get("owner") or {}).get("login") or ""), "")

    # B82: `gh` has no `--all` for `issue list`. Its `--limit` is not a page size that then
    # gets re-requested with a cursor — the CLI already walks the GraphQL pages itself to
    # satisfy whatever count it is asked for, and stops the moment the real data runs out.
    # So a large-enough ask genuinely pages until exhausted; it is not "a bigger fixed cap"
    # in the sense B82 rejects (a number picked to beat today's count that a repo will
    # still outlive later) because nothing here compares to today's count at all — it is
    # sized to outlast any repo this plugin will ever see, and the actual result is always
    # exactly the true total, never a truncated slice of it.
    _UNBOUNDED = 100_000

    def list_issues(self, limit: int | None = 100,
                    state: str = "open") -> tuple[list[dict] | None, str]:
        want = self._UNBOUNDED if limit is None else limit
        out, err = self._run("issue", "list", "--state", state, "--limit", str(want),
                             "--json", "number,title,body,author,createdAt,labels")
        if out is None:
            return None, err
        try:
            return self.normalise(json.loads(out)), ""
        except Exception:
            return None, "could not parse `gh issue list`"

    @staticmethod
    def normalise(raw: list) -> list[dict]:
        out = []
        for i in raw or []:
            out.append({
                "number": i.get("number"),
                "title": i.get("title") or "",
                "body": i.get("body") or "",
                "author": ((i.get("author") or {}).get("login") or ""),
                "createdAt": i.get("createdAt"),
                "labels": IssueHost._label_names(i.get("labels")),
            })
        return out

    def create(self, title, body, labels):
        args = ["issue", "create", "--title", title, "--body", body]
        for lb in labels:
            args += ["--label", lb]
        out, err = self._run(*args)
        if out is None:
            return None, err
        num = ""
        for tok in (out or "").strip().split("/"):       # the URL it prints back
            if tok.strip().isdigit():
                num = tok.strip()
        return (int(num), "") if num else (None, "filed, but could not read the number back")

    def close(self, number, comment=""):
        args = ["issue", "close", str(number)]
        if comment:
            args += ["--comment", comment]
        out, err = self._run(*args)
        return (out is not None), err

    def update(self, number, title="", body=""):
        args = ["issue", "edit", str(number)]
        if title:
            args += ["--title", title]
        tmp = None
        if body:
            tmp = self._body_file(body)
            args += ["--body-file", tmp]
        try:
            out, err = self._run(*args)
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        return (out is not None), err

    def add_labels(self, number, labels):
        out, err = self._run("issue", "edit", str(number), "--add-label", ",".join(labels))
        return (out is not None), err

    def list_labels(self):
        out, err = self._run("label", "list", "--limit", "100", "--json", "name")
        if out is None:
            return None, err
        try:
            return {(l.get("name") or "").lower() for l in json.loads(out)}, ""
        except Exception:
            return None, "could not parse `gh label list`"

    def create_label(self, name, colour, description):
        # INVARIANT: `name` is a hardcoded literal, never derived text.
        # It is the one POSITIONAL argument in a CLI layer that is otherwise all
        # flag/value pairs, so a name beginning with `-` would be parsed by `gh` as a
        # flag rather than as a label name. Every caller passes a key from the fixed
        # label dict, which is why this is unreachable today.
        # If label names ever become derived from a backlog file, an issue body, or
        # anything else a third party can write, THIS BECOMES FLAG INJECTION and needs
        # a real fix at that point. Deliberately not guarded with a `--` separator
        # (D12): two characters that pass the review and hide the fact that matters.
        out, err = self._run("label", "create", name, "--color", colour,
                             "--description", description)
        return (out is not None), err


class GitLabHost(IssueHost):
    """`glab`. Same verbs, most of them spelled differently.

    THE FOUR REAL DIFFERENCES, none of which the callers should have to know:

    * **`iid`, not `number`.** GitLab issues carry a global `id` AND a project-relative
      `iid`; `#18` in the UI and in `BACKLOG.md` is the `iid`. Using `id` would write
      numbers that resolve to nothing.
    * **`close` takes no comment.** `gh issue close --comment` is one call; `glab` needs a
      separate `issue note`. Closing is the ESSENTIAL half, so it goes first and the note
      is best-effort — a closed issue with no changelog pointer is a small loss, an open
      issue with a "Done" comment on it is a wrong state.
    * **`create` prompts.** Without `--yes` it waits for confirmation on stdin, which in a
      hook or a wrap means a hang, not a question. `--yes` is not optional here.
    * **A group-owned project has no `owner`.** See `repo()`.
    """
    name = "GitLab"
    cli = "glab"

    def repo(self) -> tuple[str, str, str]:
        out, err = self._run("repo", "view", "-F", "json")
        if out is None:
            return "", "", err
        try:
            meta = json.loads(out)
        except Exception:
            return "", "", "could not parse `glab repo view`"
        if not meta.get("issues_enabled", True):
            return "", "", "issues are disabled on this repo"
        slug = meta.get("path_with_namespace") or ""
        owner = ((meta.get("owner") or {}).get("username") or "")
        if not owner:
            # A group-owned project has no `owner` at all — the namespace is the group, which
            # is the normal case for the five repos under `infrastructure-innovation`. `owner`
            # is only ever used to spot an issue somebody ELSE filed, and an EMPTY owner
            # switches that check off entirely (every issue reads as "yours"), so fall back
            # to the top-level namespace rather than to nothing.
            owner = ((meta.get("namespace") or {}).get("full_path") or "").split("/")[0]
        return slug, owner, ""

    # GitLab's API hard-caps a single page at 100 REGARDLESS of what `--per-page` asks for --
    # unlike `gh`, a bigger `--per-page` does not get more than one page's worth. So B82's
    # "page until exhausted" has to be real paging here: walk `--page` 1, 2, 3, … and stop the
    # moment a page comes back short of a full page, which is the only reliable "no more data"
    # signal glab gives without a total count in the response.
    _PAGE_SIZE = 100
    _MAX_PAGES = 500                    # ~50k issues -- a runaway-loop guard, not a data cap:
                                         # a wrong page count on a buggy response ends the loop
                                         # instead of spinning forever; no real backlog is close.

    def list_issues(self, limit: int | None = 100,
                    state: str = "open") -> tuple[list[dict] | None, str]:
        # No `--state` at all reproduces the exact argv this sent before `state` existed --
        # `glab issue list` defaults to open issues on its own, and the only NEW case here is
        # `state="all"` for B37's existence check, which needs every state, not just the two
        # `--state` accepts one of.
        state_args: list[str] = []
        if state == "all":
            state_args.append("--all")
        elif state and state != "open":
            state_args += ["--state", state]

        if limit is None:
            # A page failing partway through must fail the WHOLE call, never return what was
            # collected so far as `out` — a caller like `known_issue_numbers()` reads a
            # non-None result as the complete set, so a partial list here would silently
            # under-report which issues exist and flag real ones as bogus (B37, one level up).
            out: list[dict] = []
            page = 1
            while page <= self._MAX_PAGES:
                args = (["issue", "list", "--output", "json",
                        "--per-page", str(self._PAGE_SIZE), "--page", str(page)]
                        + state_args)
                raw, err = self._run(*args)
                if raw is None:
                    return None, err
                try:
                    batch = json.loads(raw)
                except Exception:
                    return None, "could not parse `glab issue list`"
                out += self.normalise(batch)
                if len(batch) < self._PAGE_SIZE:
                    break
                page += 1
            return out, ""

        args = ["issue", "list", "--output", "json", "--per-page", str(limit)] + state_args
        out, err = self._run(*args)
        if out is None:
            return None, err
        try:
            return self.normalise(json.loads(out)), ""
        except Exception:
            return None, "could not parse `glab issue list`"

    @staticmethod
    def normalise(raw: list) -> list[dict]:
        out = []
        for i in raw or []:
            out.append({
                "number": i.get("iid"),
                "title": i.get("title") or "",
                "body": i.get("description") or "",
                "author": ((i.get("author") or {}).get("username") or ""),
                "createdAt": i.get("created_at"),
                "labels": IssueHost._label_names(i.get("labels")),
            })
        return out

    def create(self, title, body, labels):
        # `--description` (`-d`), NOT `--description-file`. That flag does not exist in glab
        # (checked against 1.93.0 and 1.116.0 --help), and passing it broke EVERY GitLab push
        # with an opaque `could not file: ERROR` (B58, 2026-09-04). The body goes as an argv
        # string, exactly as the GitHub backend passes `--body`.
        #
        # An argv string is NOT the pipe that `_body_file` exists to avoid: subprocess passes
        # argv straight to the executable with no shell, so PowerShell never sees it and cannot
        # re-encode it. The temp-file route stays for `gh`'s `--body-file`, which is real.
        args = ["issue", "create", "--yes", "--title", title, "--description", body]
        for lb in labels:
            args += ["--label", lb]
        out, err = self._run(*args)
        if out is None:
            return None, err
        num = ""
        for tok in re.split(r"[/\s#]+", (out or "").strip()):
            if tok.isdigit():
                num = tok
        return (int(num), "") if num else (None, "filed, but could not read the number back")

    def close(self, number, comment=""):
        out, err = self._run("issue", "close", str(number))
        if out is None:
            return False, err
        if comment:
            self._run("issue", "note", str(number), "--message", comment)   # best effort
        return True, ""

    def update(self, number, title="", body=""):
        args = ["issue", "update", str(number)]
        if title:
            args += ["--title", title]
        if body:
            args += ["--description", body]      # see create() -- never --description-file
        out, err = self._run(*args)
        return (out is not None), err

    def add_labels(self, number, labels):
        # `glab issue update --label` ADDS; it does not replace. Same semantics as
        # `gh issue edit --add-label`, which is what the callers assume.
        out, err = self._run("issue", "update", str(number), "--label", ",".join(labels))
        return (out is not None), err

    def list_labels(self):
        out, err = self._run("label", "list", "--output", "json", "--per-page", "100")
        if out is None:
            return None, err
        try:
            raw = json.loads(out)
        except Exception:
            return None, "could not parse `glab label list`"
        return {(l.get("name") or "").lower() for l in raw if isinstance(l, dict)}, ""

    def create_label(self, name, colour, description):
        # `glab` wants the HEX with a leading `#`; `gh` wants it without.
        out, err = self._run("label", "create", "--name", name,
                             "--color", colour if colour.startswith("#") else "#" + colour,
                             "--description", description)
        return (out is not None), err


BACKENDS = {"github": GitHubHost, "gitlab": GitLabHost}


def for_kind(kind: str, root: Path, host: str = "") -> IssueHost | None:
    """A backend by name — for `--ingest`, where the caller already knows which CLI ran."""
    cls = BACKENDS.get((kind or "").lower())
    return cls(Path(root), host) if cls else None


def detect(root: Path, repo_override: str = "") -> tuple[IssueHost | None, str]:
    """The one entry point. `(host, "")`, or `(None, sentence)` fit to print in a skip line."""
    host, err = remote_host(Path(root))
    if err:
        return None, err
    kind = kind_for_host(host)
    if not kind:
        return None, ("no issue host backend for " + host + " — GitHub and GitLab are "
                      "supported, and a self-hosted instance is recognised once `gh` or "
                      "`glab` has logged into it")
    return BACKENDS[kind](Path(root), host, repo_override), ""


if __name__ == "__main__":               # manual run: what would this repo sync to?
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        from reentry_state import project_root
        r = project_root() if project_root else Path.cwd()
    except Exception:
        r = Path.cwd()
    h, e = detect(Path(r))
    if not h:
        print(Path(r).name + ": no issue host — " + e
              + ("  (permanent)" if is_permanent(e) else "  (may work later)"))
        sys.exit(0)
    slug, owner, e2 = h.repo()
    print(Path(r).name + ": " + h.name + " via `" + h.cli + "` on " + h.host
          + (" — " + slug + " (owner " + owner + ")" if slug else " — " + e2))
    sys.exit(0)
