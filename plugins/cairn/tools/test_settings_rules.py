#!/usr/bin/env python3
"""The repo's `.claude/settings.json` denies every push that can reach `main`, and `sync_backlog`.

    python plugins/cairn/tools/test_settings_rules.py

WHY THIS EXISTS (B69). A scheduled task starts in Manual and no tool can change that, so an
unattended batch runs on the repo's committed allow list. The same file carries the deny list that
makes "`main` is never pushed unattended" and "never run the backlog sync unattended" mechanical
instead of prompt text. An allow/deny list is easy to break by one edit that looks like a tidy-up:
widen `git push origin afk/*` to `git push *`, drop the `*:*` colon rule, or fold the
`sync_backlog` forms into one that misses `sh run.sh tools/sync_backlog.py`. Nothing else would
notice until a firing pushed.

HOW RULES ARE MATCHED HERE. This is an emulation of the matcher Claude Code documents at
code.claude.com/docs/en/permissions (read 2026-09-26), not the real one:
  - `*` matches any text, spaces included; a rule with no `*` matches one exact command;
  - a trailing ` *` also matches the bare command, but only when it is the rule's ONLY wildcard;
  - `:*` at the very end is the same as ` *`;
  - deny is checked before allow, and an allow can never carve an exception out of a deny;
  - a deny rule matches past any leading `VAR=value` assignment.
Compound commands (`a && b`) are split by Claude Code before matching; every case below is a single
command, so the split is not emulated. The emulation can be wrong where the docs are silent (tab
and quote handling above all); the dossier for B69 lists the forms no pattern can close.

The file is at the REPO root, not in the plugin, so an installed copy of the plugin has no such
file: that case prints SKIP and passes.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SETTINGS = REPO / ".claude" / "settings.json"
GITIGNORE = REPO / ".gitignore"
fails = []


def check(label, ok):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        fails.append(label)


def rule_regex(spec):
    """Compile one rule specifier (the text inside `Bash(...)`) to an anchored regex."""
    if spec.endswith(":*"):
        spec = spec[:-2] + " *"
    stars = spec.count("*")
    body = ".*".join(re.escape(part) for part in spec.split("*"))
    if stars == 1 and spec.endswith(" *"):
        # `Bash(ls *)` matches `ls` as well as `ls -la`.
        body = re.escape(spec[:-2]) + r"(?: .*)?"
    return re.compile(r"\A" + body + r"\Z", re.S)


def rules(kind, tool="Bash"):
    out = []
    for r in DATA["permissions"].get(kind, []):
        m = re.fullmatch(rf"{tool}\((.*)\)", r, re.S)
        if m:
            out.append((r, rule_regex(m.group(1))))
        elif r == tool:
            out.append((r, re.compile(r"\A.*\Z", re.S)))
    return out


ASSIGN = re.compile(r"\A(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+")


def denied(cmd, tool="Bash"):
    bare = ASSIGN.sub("", cmd)
    return [r for r, rx in rules("deny", tool) if rx.match(cmd) or rx.match(bare)]


def allowed(cmd, tool="Bash"):
    return [r for r, rx in rules("allow", tool) if rx.match(cmd)]


def decision(cmd, tool="Bash"):
    if denied(cmd, tool):
        return "deny"
    return "allow" if allowed(cmd, tool) else "prompt"


if not SETTINGS.is_file():
    print(f"SKIP: no {SETTINGS} (an installed plugin copy has no repo root) -- nothing to check")
    sys.exit(0)

DATA = json.loads(SETTINGS.read_text(encoding="utf-8"))

print("1. every push form that can reach main is DENIED (deny holds in every mode, Auto included)")
MAIN_REACHING = [
    "git push",
    "git push origin",
    "git push origin main",
    "git push origin main:main",
    "git push origin HEAD",
    "git push origin HEAD:main",
    "git push origin HEAD:refs/heads/main",
    "git push origin :main",
    "git push origin :",
    "git push origin +main",
    "git push origin +HEAD:main",
    "git push origin refs/heads/main",
    "git push origin 'refs/heads/*'",
    "git push origin @",
    "git push -u origin main",
    "git push --set-upstream origin HEAD",
    "git push --force",
    "git push -f",
    "git push -f origin main",
    "git push --force-with-lease origin main",
    "git push origin main --force",
    "git push --all",
    "git push --all origin",
    "git push --mirror origin",
    "git push --follow-tags",
    "git push --no-verify origin main",
    "git push origin --delete main",
    "git push origin afk/x main",
    "git push origin afk/x:main",
    "git push origin afk/x:refs/heads/main",
    "git push origin afk/x HEAD",
    "git push origin afk/x --all",
    "git push origin afk/x\tmain",
    'git push origin "main"',
    "git push origin 'main'",
    "git push origin ma\\in",
    "git push origin $BRANCH",
    "git push origin ma{i,}n",
    "git push https://github.com/example/repo.git",
    "git push https://github.com/example/repo.git main",
    "git push git@github.com:example/repo.git",
    "git -C . push origin main",
    "git -c push.default=current push",
    "git --git-dir=.git push origin main",
    "/usr/bin/git push origin main",
    "C:/Program\\ Files/Git/cmd/git.exe push origin main",
    "git.exe push origin main",
    "sh -c 'git push origin main'",
    "bash -c \"git push origin main\"",
    "env git push origin main",
    "GIT_TRACE=1 git push origin main",
]
for cmd in MAIN_REACHING:
    check(f"deny: {cmd!r}", decision(cmd) == "deny")

print("\n2. no ALLOW rule matches a main-reaching push, even before deny is consulted")
for cmd in ["git push origin main", "git push origin HEAD:main", "git push", "git push -u origin main"]:
    check(f"no allow for {cmd!r}", not allowed(cmd))

print("\n3. the one push an unattended run needs is allowed, and not denied")
for cmd in ["git push origin afk/2026-09-27-01-B69-settings-rules",
            "git push origin afk/2026-09-27-02-B12-main-branch-guard"]:   # slug containing 'main'
    check(f"allow: {cmd!r}", decision(cmd) == "allow")

print("\n4. sync_backlog is DENIED in every invocation form the skills or a shell would use")
SYNC = [
    "python plugins/cairn/tools/sync_backlog.py",
    "python3 plugins/cairn/tools/sync_backlog.py --pull",
    "py -3 plugins/cairn/tools/sync_backlog.py",
    "python.exe plugins/cairn/tools/sync_backlog.py",
    "C:/Python312/python.exe plugins/cairn/tools/sync_backlog.py",
    "/usr/bin/python3 plugins/cairn/tools/sync_backlog.py",
    "sh plugins/cairn/hooks/run.sh tools/sync_backlog.py",
    'sh "/opt/plugins/cache/m/cairn/1.0.0/hooks/run.sh" tools/sync_backlog.py',
    "bash plugins/cairn/hooks/run.sh tools/sync_backlog.py",
    "./plugins/cairn/tools/sync_backlog.py",
    "plugins/cairn/tools/sync_backlog.py",
]
for cmd in SYNC:
    check(f"deny: {cmd!r}", decision(cmd) == "deny")

print("\n5. a lane can still WORK ON sync_backlog.py: stage it, commit it, test it")
for cmd in ["git add plugins/cairn/tools/sync_backlog.py",
            "git diff -- plugins/cairn/tools/sync_backlog.py",
            'git commit -m "fix(sync): sync_backlog parser"',
            "python plugins/cairn/tools/test_sync_flags.py"]:
    check(f"allow: {cmd!r}", decision(cmd) == "allow")

print("\n6. the rest of what a batch runs is allowed")
for cmd in ["git status --short", "git log --oneline -5", "git fetch origin",
            "git checkout -b afk/2026-09-27-01-B69-x origin/main",
            "git ls-remote origin 'refs/heads/afk/*'",
            "python plugins/cairn/tools/run_tests.py --timeout=300",
            "sh plugins/cairn/hooks/run.sh wrap_receipt.py --check",
            "gh pr create --base main --head afk/2026-09-27-01-B69-x --title t --body-file d.md",
            "gh pr list --state open --search B69", "gh pr view 12"]:
    check(f"allow: {cmd!r}", decision(cmd) == "allow")
for tool in ["Read", "Edit", "Write", "Glob", "Grep", "Agent"]:
    check(f"allow tool: {tool}", tool in DATA["permissions"]["allow"])

print("\n7. merges, repo/api writes and a hard reset to origin are DENIED")
for cmd in ["gh pr merge 12 --squash", "gh api -X POST repos/o/r/merges",
            "gh api repos/o/r/pulls/1/merge --method PUT", "gh api graphql -f query=x",
            "gh repo delete o/r --yes", "gh repo edit --default-branch x",
            "git reset --hard origin/main", "git reset -q --hard origin/main"]:
    check(f"deny: {cmd!r}", decision(cmd) == "deny")
check("allow read: 'gh api repos/o/r/pulls' is not denied", not denied("gh api repos/o/r/pulls"))

print("\n8. the PowerShell tool gets the same push/sync denies (Windows sessions have both tools)")
for cmd in ["git push", "git push origin main", "git push origin HEAD:main", "git push --force",
            "python plugins/cairn/tools/sync_backlog.py", "gh pr merge 1"]:
    check(f"PowerShell deny: {cmd!r}", bool(denied(cmd, "PowerShell")))

print("\n9. no allow rule is a bare Bash / PowerShell, or an unanchored wildcard")
allow = DATA["permissions"]["allow"]
check("no bare Bash or Bash(*)", not {"Bash", "Bash(*)", "PowerShell", "PowerShell(*)"} & set(allow))
check("no allow rule for 'git push *'", not any(re.fullmatch(r"Bash\(git push \*\)", r) for r in allow))
# A specifier ending in `:*` is the documented trailing-wildcard form, so `git push *:*` does NOT
# mean "contains a colon" -- it means `git push * *`, which also denies the afk/ push. The first
# draft of this file had exactly that rule; this emulation is what caught it.
every = DATA["permissions"]["allow"] + DATA["permissions"]["deny"]
check("no rule ends in ':*' (it would be read as a trailing ' *')",
      not [r for r in every if r.endswith(":*)")])

print("\n10. .gitignore keeps worktrees and the personal local file out, and settings.json in")
gi = GITIGNORE.read_text(encoding="utf-8").splitlines() if GITIGNORE.is_file() else []
check(".claude/worktrees/ ignored", ".claude/worktrees/" in gi)
check(".claude/settings.local.json ignored", ".claude/settings.local.json" in gi)
check("no line ignores .claude/ or settings.json wholesale",
      not any(l.strip() in {".claude", ".claude/", ".claude/*", "settings.json", "*.json"} for l in gi))

print()
if fails:
    print(f"FAILED: {fails}")
    sys.exit(1)
print("ALL PASS")
