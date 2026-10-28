# Weekend burn: multi-project, heartbeat, HITL over issues

Written 2026-10-28 from `workspace` W18. Proposals only: nothing here widens a token or enables a
project. Redesign of the task itself is done (see the end).

## Task as it stands

Three local tasks share one prompt, `~/.claude/scheduled-tasks/cairn-afk-firing/SKILL.md`:
`cairn-afk-fri` (Fri 21:00), `cairn-afk-firing` (Sat 01, 05, 09, 13, 17, 21), `cairn-afk-sun`
(Sun 01, 05, 09, 13). One cron cannot express Friday 21:00 to Sunday 15:00, so three. The two
extra ones are a one-line shim that Reads the main prompt. No reserve logic. A run that hits the
limit stops and the next slot starts clean. A run cut off mid-work leaves an `afk/` or `wip/`
branch dirty; the next run commits it to a local `wip/` branch and carries on (never on main).
Cost of three tasks: tool approvals and the Auto mode are stored per task (B84), so each of the
three needs its first run watched once.

## 4. Multi-project

Hosts stay apart because the token does. Proposal, nothing enabled yet:

| Tier | Projects | Host | Token | Rule |
|---|---|---|---|---|
| 1, on now | `superbole/cairn` | GitHub | `NB5-github-2027-01-26` (cairn only) | as today |
| 2, personal | other `superbole/*` repos he names | GitHub | one more fine-grained PAT, one repo each, Contents + PRs write | personal detail never goes to `pta-git2` |
| 3, work | CSIR repos he names | GitLab `pta-git2` | its own project access token, MR-create only, scoped per repo | CSIR detail never goes to GitHub or into a Discord post |

How a firing covers several: one prompt per tier, never one prompt spanning hosts. A tier-3 task
is a separate scheduled task (`csir-afk-firing`) with its own checkout list, its own summary file
and its own Discord line carrying counts only, no repo or item names. One item per project per
run, its own `afk/` branch, a PR or MR, never merge, never push the default branch, never sync.
Each project opts in by a `weekend-burn: yes` line in its `NEXT.md` footer, so membership stays
"has a file", and a project without it is skipped silently. His to decide: which repos in tier 2
and 3, and creating the tokens. Tier 3 needs `glab` allow rules written as carefully as the `gh`
ones, and a GitLab equivalent of the PR cap.

## 5. Heartbeat (dead-man's check)

Problem: NB5 has no WiFi after a reboot until someone logs in (W20). A dead weekend looks the same
as a quiet one, and the Discord post also dies with NB5, so the check must not depend on NB5.

Proposal: every firing, as its last step, appends the summary to ONE GitHub issue,
`superbole/claude-inbox` "weekend burn heartbeat", with
`gh issue comment <n> -R superbole/claude-inbox --body-file .claude/worktrees/summary.md`.
That shape is already on the allow list. A "no PR" run leaves no trace on GitHub otherwise, so the
comment is the only evidence a run happened. (Not yet added to the prompt: it needs the issue
number, and the issue created.)

The check runs on a different machine (DeepThought, or NB1; he decides). A scheduled task, Fridays
22:00 and again Saturday 09:00 and Sunday 09:00: `gh issue view <n> -R superbole/claude-inbox
--json comments`, and if the newest comment is older than the last expected slot, post to Discord
through `~/.claude/scripts/notify-discord.ps1`. That machine needs its own `CAIRN_DISCORD_WEBHOOK`
and a gh login that can read claude-inbox; the same webhook value is fine since it is post-only,
but it is a second copy to record in `CREDENTIALS.md`. DeepThought is private-account, so a Claude
cloud routine would also work there but needs GitHub access, untested. Recommended: DeepThought,
because NB1 is the same employer network and the same Sunday reset as NB5.

## 7. HITL over issues

Reuse `superbole/claude-inbox`, the pattern `claude-inbox-check` already runs: an issue whose
newest message starts `From Cairn` is his to answer.
- A firing that needs a decision (a groom whose entry is HITL in substance) files ONE issue
  `weekend-burn: <Bnn> question`, body: the question, the options, the recommendation, the brief
  it came from. Label `burn-question`. Not a PR.
- He answers in the issue comment from his phone.
- A later firing (step 4a) first lists open `burn-question` issues whose newest comment is his; if
  one has an answer it takes that item, reads the answer as the decision, and does the work as an
  ordinary item, closing the loop with a PR link comment. No answer means the issue is left alone.
- Cap: 3 open question issues at once, so unanswered ones cannot pile up.
Needs two allow rules (`gh issue create` and `gh issue list` on claude-inbox only) and a decision
on whether the `From Claude:` reply convention applies. Not built; backlog item.

## 6. Allow prompts (done, cairn only)

Measured from `~/.claude/permission-prompts.jsonl` (229 prompts since 2026-10-04): the cause is
shape, not tool. (1) Plugin runner calls by the absolute cache path, version-pinned
(`.../cairn/1.66.0/hooks/run.sh`), so every release invalidates the saved rule; the allow
list only had the repo-relative spelling. (2) Compound commands (`;`, `| tail`, `| Select-String`)
where one part is unlisted, and PowerShell, which had no allow rules for git or gh at all.
(3) `git -C <path>` on sibling repos. (4) `.claude/settings.local.json` fills with one-off exact
strings that never match twice. Fixed in `.claude/settings.json`: version-wildcard runner rules
(three path spellings), `git -C` read-only shapes, PowerShell read-only git/gh/Select-String,
plain `grep/tail/head/wc/ls`. `sync_backlog` and `git push` stay `ask` (ask beats allow).
Not fixed: `python -c`, `cd … ;` chains and `$var=` PowerShell scripts, which are arbitrary code.
Next: clear the one-off rules from `settings.local.json`, then run `/fewer-permission-prompts` in
a week and compare against the log. Other projects get the same pass later (B90).
