#!/usr/bin/env python3
"""The repo's `.claude/settings.json` puts every push that can reach `main`, and `sync_backlog`,
behind an ASK rule, and no allow rule reaches them.

    python plugins/cairn/tools/test_settings_rules.py

WHY THIS EXISTS (B69). A scheduled task starts in Manual and no tool can change that, so an
unattended batch runs on the repo's committed allow list. The same file carries the ask list that
makes "`main` is never pushed unattended" and "never run the backlog sync unattended" mechanical
instead of prompt text: unattended, an ask is a prompt nobody answers, so the run stalls there;
attended, it is one approval card. `ask`, not `deny`, is the user's decision (2026-09-26), because
a deny would also refuse the wrap's own push and sync in attended sessions. Merges, repo/api
writes and a hard reset to origin stay DENIED. A rule list is easy to break by one edit that looks
like a tidy-up: widen `git push origin afk/*` to `git push *`, drop a colon rule, or fold the
`sync_backlog` forms into one that misses `sh run.sh tools/sync_backlog.py`. Nothing else would
notice until a firing pushed.

HOW RULES ARE MATCHED HERE. This is an emulation of the matcher Claude Code documents at
code.claude.com/docs/en/permissions (read 2026-09-26), not the real one:
  - `*` matches any text, spaces included; a rule with no `*` matches one exact command;
  - a trailing ` *` also matches the bare command, but only when it is the rule's ONLY wildcard;
  - `:*` at the very end is the same as ` *`;
  - deny, then ask, then allow; an allow can never carve an exception out of a deny OR an ask;
  - a deny rule matches past any leading `VAR=value` assignment (the docs say this of deny and
    ask rules together in the wrapper section; the emulation applies it to both).
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


def _restrictive(kind, cmd, tool):
    bare = ASSIGN.sub("", cmd)
    return [r for r, rx in rules(kind, tool) if rx.match(cmd) or rx.match(bare)]


def denied(cmd, tool="Bash"):
    return _restrictive("deny", cmd, tool)


def asked(cmd, tool="Bash"):
    return _restrictive("ask", cmd, tool)


def allowed(cmd, tool="Bash"):
    return [r for r, rx in rules("allow", tool) if rx.match(cmd)]


def decision(cmd, tool="Bash"):
    if denied(cmd, tool):
        return "deny"
    if asked(cmd, tool):
        return "ask"
    return "allow" if allowed(cmd, tool) else "prompt"


if not SETTINGS.is_file():
    print(f"SKIP: no {SETTINGS} (an installed plugin copy has no repo root) -- nothing to check")
    sys.exit(0)

DATA = json.loads(SETTINGS.read_text(encoding="utf-8"))

print("1. every push form that can reach main hits an ASK rule (unattended: a stall; attended: one card)")
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
    check(f"ask: {cmd!r}", decision(cmd) == "ask")

print("\n2. no ALLOW rule matches a main-reaching push -- except where no pattern can prevent it")
# Belt and braces: if an ask rule is ever deleted, a matching allow would turn a stall into a push.
# But `*` spans spaces and colons, so the afk/ allow `git push origin afk/*` necessarily matches a
# push that STARTS with an afk/ branch and then names main. For exactly those forms the ask rule is
# load-bearing (ask is checked before allow); they are pinned separately so a reader sees it.
SHADOWED = [c for c in MAIN_REACHING if c.startswith("git push origin afk/")]
check("the shadowed set is exactly the afk/-prefixed forms (6 of them)", len(SHADOWED) == 6)
for cmd in MAIN_REACHING:
    if cmd in SHADOWED:
        check(f"allow matches, ASK stops it: {cmd!r}", bool(allowed(cmd)) and decision(cmd) == "ask")
    else:
        check(f"no allow for {cmd!r}", not allowed(cmd))

print("\n3. the one push an unattended run needs is allowed, and not asked or denied")
for cmd in ["git push origin afk/2026-09-27-01-B69-settings-rules",
            "git push origin afk/2026-09-27-02-B12-main-branch-guard"]:   # slug containing 'main'
    check(f"allow: {cmd!r}", decision(cmd) == "allow")

print("\n4. sync_backlog hits an ASK rule in every invocation form the skills or a shell would use")
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
    check(f"ask: {cmd!r}", decision(cmd) == "ask")
    if cmd.startswith(("python plugins/cairn/tools/", "python3 plugins/cairn/tools/",
                       "sh plugins/cairn/hooks/run.sh ")):
        # The tools/run.sh allows match these by construction; only the ask rule stops them.
        check(f"allow matches, ASK stops it: {cmd!r}", bool(allowed(cmd)) and decision(cmd) == "ask")
    else:
        check(f"no allow for {cmd!r}", not allowed(cmd))

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

print("\n8. the PowerShell tool gets the same rules (Windows sessions have both tools)")
for cmd in ["git push", "git push origin main", "git push origin HEAD:main", "git push --force",
            "python plugins/cairn/tools/sync_backlog.py"]:
    check(f"PowerShell ask: {cmd!r}", decision(cmd, "PowerShell") == "ask")
for cmd in ["gh pr merge 1", "git reset --hard origin/main"]:
    check(f"PowerShell deny: {cmd!r}", decision(cmd, "PowerShell") == "deny")

print("\n8b. push and sync rules live in ask, and nothing else was moved out of deny")
perm = DATA["permissions"]
check("no push or sync_backlog rule left in deny",
      not [r for r in perm["deny"] if "push" in r or "sync_backlog" in r])
check("every ask rule is a push or sync_backlog rule",
      all("push" in r or "sync_backlog" in r for r in perm.get("ask", [])))

print("\n9. no allow rule is a bare Bash / PowerShell, or an unanchored wildcard")
allow = DATA["permissions"]["allow"]
check("no bare Bash or Bash(*)", not {"Bash", "Bash(*)", "PowerShell", "PowerShell(*)"} & set(allow))
check("no allow rule for 'git push *'", not any(re.fullmatch(r"Bash\(git push \*\)", r) for r in allow))
# A specifier ending in `:*` is the documented trailing-wildcard form, so `git push *:*` does NOT
# mean "contains a colon" -- it means `git push * *`, which also catches the afk/ push. The first
# draft of this file had exactly that rule; this emulation is what caught it.
every = DATA["permissions"]["allow"] + DATA["permissions"].get("ask", []) + DATA["permissions"]["deny"]
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
