#!/usr/bin/env python3
"""Has the plugin update actually landed on THIS machine? (v1.39.0, B41 + B49)

    python plugins/cairn/tools/check_install.py          # from anywhere

WHY THIS EXISTS
---------------
There are three versions, and they can disagree in two independent ways:

    repo `plugin.json`                      what has been shipped   (agent-reentry only)
    `installed_plugins.json`                what is downloaded      (machine-global)
    `<!-- reentry:begin v<N> -->` in `~/.claude/CLAUDE.md`
                                            WHAT IS ACTUALLY IN FRONT OF THE AGENT

`version_drift.py` reports the same facts at session start, and that is the route that needs no
remembering. This script is the OUT-OF-SESSION answer, and it exists because the one gap a hook
can never see is the one that caught the user on LAPTOP1 on 2026-09-01: `install_rules` runs from
`SessionStart`, so between `claude plugin update` and the next session actually starting, the
machine reports the new version and runs the old rules. They checked in that window, got a correct
"stale", checked again later, got a correct "current", and nothing anywhere explained either.

So the rule this script encodes, and prints: **update, START A SESSION, then check.**

It replaces the advice it supersedes — "grep `~/.claude/CLAUDE.md` for a phrase the new version
ADDED" — which rots at every bump and cannot tell a stale block from a badly chosen phrase.

Reports, never fixes. Exit 0 when installed and rules agree, 1 when they do not, so it can gate a
script. A repo-vs-installed lag is reported but does NOT set the exit code: it is a different
question (is this machine current?) with a different remedy, and only answerable in one repo.

ISSUE HOST READINESS (B49, 2026-09-05)
---------------------------------------
The user: *"shouldn't installing gh and glab be part of setting up the plugin?"* The install
itself can't be — a plugin has hooks and skills, not a package manager, and auto-installing would
put a network fetch and an elevation prompt in the one path guaranteed never to do that
(`SessionStart`). But the CHECK should exist, and its absence is the defect it was filed against:
on 2026-09-03 one machine had no `gh` at all, so `agent-reentry`'s own backlog sync had been a
silent no-op there for as long as the machine had the plugin, and the only ways to find out were
to run a wrap and read a skip line, or have an agent notice in passing.

So this file also answers, for the project it is run FROM (not `agent-reentry` specifically —
whatever project's directory you are standing in when you run it): which issue host the `origin`
remote implies (`issue_host.detect`), whether that host's CLI is reachable — **on PATH**, or
found in a known install location but **off PATH**, which needs a different fix than reinstalling
— and whether it is authenticated **to that host specifically** (`<cli> auth status --hostname
<host>`), not merely authenticated to *something*. The trap that made "specifically" necessary:
`glab` logged into `gitlab.com` while the remote is a self-hosted instance reads as "authenticated"
by any check that doesn't pass `--hostname`, and a previous session printed a bare `gh auth login`
during a GitLab conversation — the user pasted a token into a prompt that could never have worked.
Every remedy line below names the host explicitly for exactly that reason.

This section never installs, authenticates, or edits anything — it shells out to read-only status
commands (`<cli> auth status --hostname <host>`) and reports. A missing or unauthenticated CLI is
not a hard failure and never changes this script's exit code: `BACKLOG.md` keeps working with no
issue host at all — you only lose phone access, surviving a lost machine, and other people's
writes.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hooks"))
try:
    import issue_host
except Exception:                       # hooks/ missing or broken -- report, never crash
    issue_host = None
try:                                    # B26: the block finder + digest, never re-implemented
    import install_rules
except Exception:                       # hooks/ missing -- the digest line says so, never crashes
    install_rules = None
try:                                    # the ONE version parser (B63), shared with install_rules
    from version_drift import compare_versions
except Exception:                       # hooks/ missing -- no direction, the old wording stands
    def compare_versions(a, b):         # type: ignore[misc]
        return None

try:                                    # Windows consoles default to cp1252 and would
    sys.stdout.reconfigure(encoding="utf-8")   # mangle the em-dashes below
except Exception:
    pass

_MARKER_RE = re.compile(r"reentry:begin\s+v([0-9][0-9.]*)")


def _config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".claude"


def _newer(a: str, b: str) -> bool:
    """Is version `a` strictly newer than `b`? Non-numeric parts compare as 0 rather than raise.

    WHY THIS EXISTS (2026-09-08). The note below used to fire on a bare `repo != installed`, with
    no direction, and always said "this machine is behind what exists -- run `plugin update`". On
    the personal workstation it printed exactly that with installed at v1.53.3 and the repo at
    v1.53.2: the INSTALL was ahead and the REPO CLONE was stale, so the remedy was `git pull` and
    the tool named the opposite one. One message for two opposite states, in a tool whose entire
    job is telling three states apart -- and it is a state that happens routinely here, because
    the plugin installs from its own marketplace clone under `~/.claude/plugins/marketplaces/`,
    which is a SECOND clone of the same repo and is often fresher than the working copy.
    """
    def parts(v):
        out = []
        for chunk in str(v).split("."):
            digits = "".join(c for c in chunk if c.isdigit())
            out.append(int(digits) if digits else 0)
        return out
    pa, pb = parts(a), parts(b)
    pad = max(len(pa), len(pb))
    pa += [0] * (pad - len(pa))
    pb += [0] * (pad - len(pb))
    return pa > pb


def _installed_version(config: Path) -> str | None:
    try:
        data = json.loads((config / "plugins" / "installed_plugins.json").read_text("utf-8"))
    except Exception:
        return None
    for key, installs in (data.get("plugins") or {}).items():
        if key.split("@", 1)[0] != "cairn":
            continue
        for install in installs or []:
            if install.get("version"):
                return str(install["version"])
    return None


def _rules_state(config: Path) -> tuple[str, str | None]:
    """("ok", version) | ("no-marker", None) | ("missing", None) — three states, never two."""
    try:
        text = (config / "CLAUDE.md").read_text("utf-8")
    except Exception:
        return ("missing", None)
    match = _MARKER_RE.search(text)
    return ("ok", match.group(1)) if match else ("no-marker", None)


def _repo_version(start: Path) -> tuple[str | None, Path | None]:
    """Walk up for agent-reentry's manifest. None everywhere else, which is correct, not a failure."""
    for root in (start, *start.parents):
        manifest = root / "plugins" / "cairn" / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            try:
                return str(json.loads(manifest.read_text("utf-8")).get("version") or "") or None, root
            except Exception:
                return None, root
    return None, None


def _installed_block_digest(config: Path) -> str:
    """A digest of the installed managed BLOCK (B26) -- never its content, never the whole file.

    Two machines on the same version string can still carry different blocks (a rules edit without
    a bump rewrites the block and keeps the number), and the version line cannot tell them apart.
    Found with `install_rules._find_block`, the same structural finder that writes it, so this can
    never disagree with the installer about where the block is.
    """
    if install_rules is None:
        return "(unavailable: could not import hooks/install_rules.py)"
    try:
        text = install_rules._read(config / "CLAUDE.md")
    except Exception:
        return "(no file)"
    try:
        found = install_rules._find_block(text)
    except install_rules.MalformedBlock:
        return "(malformed block: install_rules refuses to edit it)"
    if found is None:
        return "(no block)"
    start, end, _version = found
    return install_rules.block_digest(text[start:end])


def _repo_block_digest(repo_root: Path | None, repo_version: str | None) -> str | None:
    """The digest of the block THIS repo checkout would install -- same renderer, same digest."""
    if install_rules is None or repo_root is None or not repo_version:
        return None
    try:
        body = install_rules._read(repo_root / "plugins" / "cairn" / "rules" / "CLAUDE.md")
        return install_rules.block_digest(install_rules._block(repo_version, body))
    except Exception:
        return None


# --------------------------------------------------------------- issue host readiness (B49)

# `<cli> auth status --hostname <host>` is a real, read-only call to the host -- `glab`
# especially makes a live API request to confirm the token, so this is generous rather than
# the 10s used for plain `git` calls elsewhere in the plugin. This file runs where a human is
# watching (never from a hook), so being slow is an acceptable trade for a real answer.
AUTH_TIMEOUT = 30


def _locate_cli(cli: str) -> tuple[str, str]:
    """("path", exe) | ("off-path", exe) | ("missing", "") -- never raises.

    "off-path" is the case `shutil.which` cannot tell apart from "missing" on its own, and it
    needs a DIFFERENT remedy (fix PATH, don't reinstall). The off-PATH search itself is
    `issue_host._find_installed` (B38, landed 2026-09-05 in the same batch as this file's own
    B49 work) -- that function already exists, is already tested against this machine's real
    `gh`/`glab` locations, and probes the exact Windows install layouts a second list here
    would only have to keep in sync with by hand. Reused, not reimplemented -- this is the
    "do not duplicate their code" instruction this task was given about that exact seam.
    """
    exe = shutil.which(cli)
    if exe:
        return "path", exe
    if issue_host is not None:
        found = issue_host._find_installed(cli)
        if found:
            return "off-path", found
    return "missing", ""


def _run_cli(args: tuple[str, ...], timeout: int = AUTH_TIMEOUT) -> tuple[int, str]:
    """One read-only subprocess call. (returncode, combined stdout+stderr text).

    returncode -2 means the executable could not be started at all (shouldn't happen -- the
    caller already located it with `_locate_cli`); -1 means it timed out, which is inconclusive
    (a network/VPN hiccup), never treated as "not authenticated".
    """
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace",
                           **({"creationflags": 0x08000000} if os.name == "nt" else {}),
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "NO_COLOR": "1"})
    except FileNotFoundError:
        return -2, ""
    except subprocess.TimeoutExpired:
        return -1, ""
    except Exception as exc:                                       # pragma: no cover
        return -3, type(exc).__name__
    return r.returncode, (r.stderr or "") + (r.stdout or "")


def _auth_detail(text: str, host: str) -> str:
    """The one line of `auth status` output worth showing next to a failure.

    Both CLIs lead with a bare hostname header line and `glab` also draws a blank/rule-only
    `ERROR` banner around its real message (the same banner shape `issue_host.py`'s own `_run`
    already has to skip) -- neither is informative next to "NOT authenticated to <host>", so
    both are filtered out before picking the first line left.
    """
    low_host = host.lower()
    out = []
    for ln in text.splitlines():
        s = ln.strip().lstrip("x!✓X").strip(" :")
        if not s or s.lower() == low_host or s.strip("=-_ ").upper() in ("", "ERROR"):
            continue
        out.append(s)
    return out[0][:200] if out else ""


def _auth_state(exe: str, host: str) -> tuple[str, str]:
    """("authenticated", "") | ("unauthenticated", detail) | ("timeout", "") | ("error", detail)."""
    rc, text = _run_cli((exe, "auth", "status", "--hostname", host))
    if rc == 0:
        return "authenticated", ""
    if rc == -1:
        return "timeout", ""
    if rc in (-2, -3):
        return "error", (_auth_detail(text, host) or f"{exe} could not be run")
    return "unauthenticated", _auth_detail(text, host)


def issue_host_report(root: Path) -> list[str]:
    """The B49 readiness section for the issue-host sync of the project at `root`.

    Three questions, always in this order, each printed on its own line: which host does the
    `origin` remote imply, is that host's CLI reachable, is it authenticated to THIS host
    specifically. Stops at the first thing that's wrong and names the one command that fixes
    it -- there is nothing useful to check about auth if the CLI isn't even reachable, and
    nothing to check about the CLI if there's no host to check it against.

    Never raises, never changes this script's exit code: an absent or unauthenticated issue
    host is not a failure of anything -- `BACKLOG.md` keeps working with no host at all.
    """
    lines = ["", "--- issue host sync (BACKLOG.md <-> GitHub/GitLab issues) ---"]
    if issue_host is None:
        lines.append("skipped: could not import hooks/issue_host.py")
        return lines

    host_obj, err = issue_host.detect(root)
    if host_obj is None:
        lines.append(f"host      : no issue host — {err}")
        lines.append("            BACKLOG.md keeps working either way -- an issue host only")
        lines.append("            adds phone access, surviving a lost machine, and other")
        lines.append("            people's writes.")
        return lines

    lines.append(f"host      : {host_obj.name} via `{host_obj.cli}` on {host_obj.host}")

    state, path = _locate_cli(host_obj.cli)
    if state == "path":
        lines.append(f"cli       : on PATH ({path})")
    elif state == "off-path":
        lines.append(f"cli       : installed but OFF PATH — found {path}")
        lines.append(f"remedy    : add that folder to PATH (or reinstall `{host_obj.cli}` so "
                      f"the installer does it), then open a new shell.")
        return lines
    else:
        lines.append(f"cli       : NOT INSTALLED (`{host_obj.cli}`)")
        doc = ("https://cli.github.com/" if host_obj.cli == "gh"
               else "https://gitlab.com/gitlab-org/cli#installation")
        lines.append(f"remedy    : install `{host_obj.cli}` — {doc}")
        return lines

    astate, detail = _auth_state(path, host_obj.host)
    if astate == "authenticated":
        lines.append(f"auth      : OK — logged in to {host_obj.host}")
    elif astate == "timeout":
        lines.append(f"auth      : could not confirm — `{host_obj.cli} auth status` timed out "
                      f"after {AUTH_TIMEOUT}s (network/VPN?). Not a failure — re-run to check "
                      f"again.")
    elif astate == "error":
        lines.append(f"auth      : could not check — {detail}")
    else:
        lines.append(f"auth      : NOT authenticated to {host_obj.host}"
                      + (f" — {detail}" if detail else ""))
        lines.append("            (being authenticated to a DIFFERENT host does not count — "
                      "that exact mix-up is why B49 checks the host by name)")
        lines.append(f"remedy    : {host_obj.cli} auth login --hostname {host_obj.host} --web")
    return lines


def main() -> int:
    config = _config_dir()
    installed = _installed_version(config)
    state, rules = _rules_state(config)
    repo, repo_root = _repo_version(Path.cwd().resolve())

    print(f"machine   : {platform.node()}")
    print(f"config    : {config}")
    print(f"installed : {installed or '(could not read installed_plugins.json)'}")
    print(f"rules     : {rules or '(' + state + ')'}   <- {config / 'CLAUDE.md'}")
    print(f"repo      : {repo or 'n/a — not in a checkout of the cairn source repo'}"
          + (f"   <- {repo_root}" if repo else ""))
    # B26: comparable across machines; informational only, never part of the exit code below.
    installed_digest = _installed_block_digest(config)
    repo_digest = _repo_block_digest(repo_root, repo)
    line = f"block     : {installed_digest} (installed)"
    if repo_digest:
        line += f"   {repo_digest} (this repo's v{repo})"
        if rules == repo and not installed_digest.startswith("(") and installed_digest != repo_digest:
            line += "   — SAME version, DIFFERENT block"
    print(line)
    print()

    if installed is None:
        print("UNKNOWN — no installed version to compare against. Is the plugin installed at all?")
        rc = 1
    elif state == "missing":
        print(f"STALE — {config / 'CLAUDE.md'} could not be read, so the always-loaded rules are")
        print("        not reaching any session. Start a Claude Code session; install_rules writes")
        print("        that file at session start. If it stays missing, the install is failing")
        print("        silently — it is built never to fail a session.")
        rc = 1
    elif state == "no-marker":
        print("STALE — that file has no `reentry:begin` block, so the rules have NEVER installed")
        print("        on this machine. Not the same as up to date. Start a Claude Code session.")
        rc = 1
    elif rules != installed and compare_versions(rules, installed) == 1:
        # B63: install_rules now KEEPS a newer block rather than rolling it back, so "restart and
        # it resyncs" -- the remedy below -- is false in this direction. The plugin is what is old.
        print(f"STALE — the loaded rules are v{rules}, NEWER than the installed plugin v{installed}.")
        print("        install_rules keeps a newer block rather than roll it back (B63), so a")
        print("        restart will not resync it. Update the plugin: `claude plugin marketplace")
        print("        update superbole`, then `claude plugin update cairn@superbole`, restart,")
        print("        re-run this.")
        rc = 1
    elif rules != installed:
        print(f"STALE — plugin v{installed} is installed but the loaded rules are v{rules}.")
        print("        Start a Claude Code session and re-run this; install_rules resyncs the")
        print("        block at session start, and `claude plugin update` alone never touches it.")
        print("        If it survives a restart, the install is failing silently.")
        rc = 1
    else:
        print(f"OK — installed plugin and loaded rules are both v{installed}.")
        if repo and repo != installed:
            print()
            if _newer(repo, installed):
                print(f"note: this repo has shipped v{repo}, so this machine is behind what "
                      f"exists.")
                print("      `claude plugin marketplace update superbole`, then")
                print("      `claude plugin update cairn@superbole`, restart, re-run this.")
            else:
                # The other direction, and it is NOT the same remedy: the installed plugin comes
                # from the marketplace clone, a second clone of this repo that updates on its own.
                print(f"note: the INSTALLED plugin is v{installed}, NEWER than this working "
                      f"copy's v{repo}.")
                print("      Your clone of the repo is behind, not the install — `git pull` here.")
                print("      The plugin installs from its own marketplace clone, which is a")
                print("      separate checkout of this repo and is often fresher than this one.")
            print("      Not an error either way — a different question with a different remedy.")
        rc = 0

    # B49 — the issue-host readiness section, always shown regardless of the version verdict
    # above: it answers an independent question (can THIS project's backlog sync work?) and
    # never affects the exit code, which stays scoped to the version-drift question this
    # script was built to answer.
    try:
        for ln in issue_host_report(Path.cwd().resolve()):
            print(ln)
    except Exception as exc:                                        # pragma: no cover
        print(f"\nissue host readiness check skipped: {type(exc).__name__}: {exc}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
