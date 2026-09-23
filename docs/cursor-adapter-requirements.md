# Cursor adapter requirements

Verified on **LAPTOP-B**, 2026-09-04, Cursor Agent, worktree
`~/Projects/agent-reentry-cursor-reqs` on `cursor/adapter-requirements` at `4995215`.
This is not an implementation. Cite gaps as **unverified**. A confident wrong answer here
costs more than a hole.

> **Migrated 2026-09-23 from the plugin's private source repo**, where it was written. Machine
> names are pseudonymised (`LAPTOP-A`, `LAPTOP-B`, "the desktop"); everything measured is kept.
> Links to the handoff brief and operating-loop brief were removed, because those stayed private
> (`docs/decisions.md` D22). **Backlog ids below are the PRIVATE repo's, as of 2026-09-04.** Here
> they map to: B2 → **B31** (roll-up) and **B57** (this adapter) · B54 → **B32** · B55 → **B33** ·
> B57 → **B35**. B63's path-identity point is **B40**; the timesheet reader is **B52**. B12, B19,
> B20, B26, B42, B46 and B51 had shipped or closed before the migration. B39 (recorder misses
> Shell writes), B49 and B58 (GitLab write path) are **unverified now**: re-check each against the
> current code before relying on it, and see **B56**. Read this report together with **B57** and
> its brief.
>
> **Two rows are stale, and are corrected in place:** the `check_exits.py` status, and the module
> inventory, which was taken at v1.34.0.

Backlog (private ids): B2 (adapter) · B55 (concurrency) · B56 (this handoff) · B54 (mailbox) · B57 (file set).

---

## How this was verified

| Claim | How |
|---|---|
| Hook *events* exist | Cursor's own `create-hook` skill (`~/.cursor/skills-cursor/create-hook/SKILL.md`) and Cursor docs (`cursor.com/docs/hooks.md`), fetched this session |
| Hooks *fire* on this machine | They do not. No `~/.cursor/hooks.json`, no project `.cursor/hooks.json`. **No hook was observed to run.** |
| Skills locations and invocation | This session's `available_skills` list, plus directory listing of `~/.cursor/skills`, `~/.cursor/skills-cursor`, `~/.agents/skills`, `workspace/.cursor/skills/workflow` |
| Rules auto-load | This session ingested `agent-reentry/CLAUDE.md` as always-on workspace rules with no `AGENTS.md` and no user command beyond the first message |
| Python tools | Ran `session_orientation.py`, `archive_offer.py --check`, `check_repos.py`, `measure_context.py` from this Agent's Shell. `python` is 3.11.9 |
| Cross-repo git | `git -C ~/Projects/workspace status -sb` succeeded. Wrote into the worktree from a Cursor window whose workspace root is still `~/Projects/agent-reentry` |
| Transcripts | Read `~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl` |
| `sessionStart` `additional_context` reaching the model | **Unverified on this machine.** Documented in Cursor docs. Forum reports (Cursor staff, 2026) that injection is broken. This session never installed a hook to test it. |

---

## Findings that are not one of the seven questions

### Default branch is `main`, not `master`

The handoff still says "a Claude Code session may be working in this repo on `master`" and
"Do not merge to `master`". The remote default is `main`. Harmless if read as "the shared
branch", wrong if an agent checks out `master`.

### A branch in the same working tree is not isolation (B55)

B55 currently says a second writer needs "a branch or a worktree". The first half is false.
`git checkout -b` does not isolate uncommitted files. On 2026-09-04 this session and a live
Claude Code session shared `~/Projects/agent-reentry` with a dirty `BACKLOG.md`. A new branch
in that folder would have clobbered Claude's edits.

**Invariant (harness-agnostic):** one writing working tree per repo. A second writer uses a
git worktree (or a separate clone). Read-only sessions may share a tree.

**When it fires (agreed this session):** the working tree is dirty, or another session is
known live, or `git worktree list` already shows a second checkout. Not on every session.
Not only when the four off-limits files would be touched.

**Until a live-session marker exists:** treat "live" as true if any of those three hold, or
the user / a handoff said so. Do not invent a lock (B55 already rejected that).

**Specify, do not build here:** a shared `sessionStart` marker (pid / session-id / timestamp,
warn never block) that both harnesses can read. Cursor's `sessionStart` hook can write a
file; whether that file is the same path Claude Code would write is an adapter design
choice. Cursor `sessionStart` input includes `session_id`. See Q1 and Q5.

**Subagents are a different mechanism.** Claude Code's `isolation: worktree` already pointed
agents at the wrong repo (2026-08-25, eight dirty trees). Do not reuse that as the
independent-session rule.

**This session does not write that rule into `plugins/cairn/rules/CLAUDE.md`.** Off limits.
B55's "or a branch" is the finding.

### Fetch before creating the worktree

`git worktree add -b` copies local `HEAD`. This worktree was created from a local tip 19
commits behind `origin/main`. The first four backlog items written in the parallel Claude
session collided with unrelated upstream B44–B47 and were renumbered B54–B57. Claude's
changelog at `fc209da` records that. An adapter that opens a worktree must `git fetch`
first and base on `origin/main` (or say it did not).

W3 on `NEXT.md` still says this worktree is on abandoned `5dbc97f` and that the reset is
blocked. It is not. Finding only; `NEXT.md` is off limits.

### Do not create `AGENTS.md` in this pass

Cursor ingested `CLAUDE.md` without it. A second always-on file is another thing to drift.
A Cursor-native rules file is a distribution question (Q3), not this session's extra file.

---

## 1. Session lifecycle

**Cursor has equivalents.** README's "a tool with no `SessionStart`-equivalent (e.g. Cursor)"
and the work-side `~/.cursor/skills/next/SKILL.md` line *"Cursor has no `SessionStart`-equivalent
hook yet"* are both **wrong**. Correct the README when the adapter ships; do not correct it
from this branch.

### Event map (documented)

| Claude Code | Cursor | Notes |
|---|---|---|
| `SessionStart` | `sessionStart` | Fire-and-forget. Output: `env`, `additional_context`. Input includes `session_id`. Cloud agents: **not supported**. |
| `UserPromptSubmit` | `beforeSubmitPrompt` | Matcher value documented as `UserPromptSubmit`. Can validate; **unverified** whether it can inject orientation the way Claude Code prints to context. |
| `PostToolUse` | `postToolUse` / `afterFileEdit` | `postToolUse` may return `additional_context`. `afterFileEdit` is side-effect only. |
| `Stop` | `stop` | Agent completion. |
| `SessionEnd` | `sessionEnd` | Fire-and-forget. Output unused. Tied to the IDE session, not cloud agents. |

Cursor extras that Claude Code does not have under these names: `preToolUse`,
`beforeShellExecution` / `afterShellExecution`, `beforeMCPExecution` / `afterMCPExecution`,
`beforeReadFile`, `subagentStart` / `subagentStop`, `preCompact`, `afterAgentResponse` /
`afterAgentThought`, `workspaceOpen` (app lifecycle, can return extra plugin paths).

Config: project `.cursor/hooks.json` + `.cursor/hooks/*`, or user `~/.cursor/hooks.json` +
`~/.cursor/hooks/*`. Schema version 1, flat per-event arrays, `command` or `type: "prompt"`.
This is **not** Claude Code's nested matcher-groups-inside-`settings.json` shape, nor the
plugin file at `plugins/cairn/hooks/hooks.json` (`SessionStart` capital S, `matcher` on
`startup|resume`, `${CLAUDE_PLUGIN_ROOT}`).

Cursor documents that it can load Claude Code hooks if
**Settings → Rules, Skills, Subagents → Include third-party Plugins, Skills, and other configs**
is on, mapping `PreToolUse` → `preToolUse` etc. **Whether that toggle is on for this account
is unverified as a setting.** Circumstantial: this session's skill list included the Claude
Code plugin skills from
`~/.claude/plugins/cache/superbole/cairn/1.34.0/skills/{next,wrap}/`. Circumstantial
the other way: `session_orientation.py` did **not** run at session start. The first reply
did not relay the Queue. `${CLAUDE_PLUGIN_ROOT}` is unset in the Agent shell, so even if
Cursor mapped the plugin `hooks.json`, the command string would not expand.

**Do not assume Claude Code's hook file runs here.** Native `.cursor/hooks.json` is the
adapter's trigger. Reuse the **Python**, not the JSON.

### Earliest forced context without a typed command

Observed this session, in order of certainty:

1. **Always-on rules.** `CLAUDE.md` (this repo), parent `Projects/AGENTS.md`,
   GitLab workflow rule, user rules. No command required. This is stronger than
   "prompt-level only".
2. **Skill catalog.** Names and descriptions are in context; bodies load when the agent
   decides to read them, or when named. See Q2.
3. **`sessionStart` `additional_context`.** Documented as the SessionStart analogue.
   **Unverified that it actually lands in the model.** Cursor staff have called this a
   confirmed bug (forum, 2026): the hook runs and returns JSON, the agent never sees the
   string. `env` from the same hook is reported to work (separate path). Fallback for
   *static* text: `.cursor/rules` with `alwaysApply: true`, or `AGENTS.md`. That cannot
   replace a dynamic orientation (queue, due watches, git divergence, live-session marker).

So the adapter has two layers:

- **Static contract** (file names, write boundary, "read NEXT.md"): Cursor rules, already
  proven to load.
- **Dynamic orientation** (`session_orientation.py` stdout): needs a hook whose output
  reaches the model. Until `additional_context` is proven on this account, the honest v1
  is: a `sessionStart` *command* hook that **writes a marker file and/or prints nothing
  the model will miss**, plus an auto-invoked skill (or a rule that says "run
  `session_orientation.py` before the first reply"). Relying on hook injection alone is
  currently a gamble.

`stop` / `sessionEnd` are the right events for `dirty_tree_warning.py`. Same caveat:
side effects (print to a log, write a marker) are reliable; "speak to the agent" is not
proven.

---

## 2. Skills

### Where Cursor looks

| Location | What is there on LAPTOP-B | In this session's skill list? |
|---|---|---|
| `~/.cursor/skills/<name>/SKILL.md` | `next`, `wrap` (Cursor-side cairn copies) | **No** |
| `<project>/.cursor/skills/<name>/SKILL.md` | none in `agent-reentry` | n/a |
| `workspace/.cursor/skills/workflow/{next,wrap}/SKILL.md` | yes; **byte-identical** to `~/.cursor/skills/{next,wrap}` (SHA-256 compared this session) | not as a project skill of *this* repo |
| `~/.cursor/skills-cursor/` | Cursor built-ins (`create-hook`, `create-skill`, `create-rule`, …). Reserved; do not write here | Yes |
| `~/.agents/skills/` | user/shared skills (`grill-me`, `tdd`, `wsl-local-dev`, …) | Yes |
| `~/.cursor/plugins/cache/…` | GitLab plugin (MCP), not a cairn skill | GitLab MCP namespace present (`needsAuth`) |
| `~/.claude/plugins/cache/superbole/cairn/1.34.0/skills/{next,wrap}/` | Claude Code plugin payload | **Yes** |

Per-project and per-user locations both exist. Cursor's own `create-skill` skill states:

- Personal: `~/.cursor/skills/skill-name/`
- Project: `.cursor/skills/skill-name/`
- Never write `~/.cursor/skills-cursor/`

### Auto-invoke vs explicit

`create-skill` default is `disable-model-invocation: true` (load only when named). Omit
that field to allow description-match auto-invoke.

The work-side `next` and `wrap` **set `disable-model-invocation: true`**. They do not run
at session start. That is why README's "point a Cursor skill at the same three files"
does not give Claude Code's automatic print: the copies that exist are opt-in slash
skills, and this session was not given those files in the skill list anyway.

This session *was* given the Claude Code plugin `next`/`wrap` skills (no
`disable-model-invocation` in the ones I read from the plugin cache; they auto-load on
description match). I did not follow `/next` because the user handed a specific brief.
An adapter that ships Cursor `next`/`wrap` into `~/.cursor/skills/` can still lose to
the Claude plugin copies if third-party skill loading is on. **Two `next` skills, two
procedures, one of them claims Cursor has no SessionStart hook.** Drift is not only
LAPTOP-A vs LAPTOP-B. It is two harnesses on the same machine.

### What the adapter should require

- One Cursor `next` and one Cursor `wrap`, project or user, with descriptions that
  mention `/next` and `/wrap`.
- If orientation must happen with no typed command, **omit** `disable-model-invocation`
  on a small "reentry-orient" skill whose description matches session start, **or**
  drive it from a hook (Q1). Do not depend on the user typing `/next`. That is the
  failure the Claude Code hook exists to prevent.
- Do not install the Claude Code `SKILL.md` files as-is. They call
  `set_session_title`, `$CLAUDE_PLUGIN_ROOT`, and `/cairn:wrap` step numbers.

---

## 3. Distribution

Claude Code: one marketplace plugin, versioned, `installed_plugins.json`,
`version_drift.py` compares repo / installed / rules block.

Cursor's analogue is **not** that format. Cursor plugins use `.cursor-plugin/plugin.json`
(example on this machine: GitLab plugin `name: gitlab`, `version: 0.1.0`, in
`~/.cursor/plugins/cache/cursor-public/gitlab/<sha>/`). Hooks can ship inside Cursor
plugins. Enterprise/team dashboard hooks exist on Enterprise plans. **Unverified:**
whether a private Cursor marketplace can host `reentry` the way `superbole` hosts
the Claude plugin. This account has `cursor-public` in the plugin cache, nothing
self-hosted.

### Least-bad options, ranked for this portfolio

1. **A real Cursor plugin** (versioned, one install, hooks + skills + a pointer at the
   Python). Same "one copy, N projects" property. Cost: author a second plugin format
   and a second install path. LAPTOP-A and LAPTOP-B share a work Cursor *account*, so an
   account-level plugin install would land on both; that is wanted for the adapter and
   dangerous for anything machine-specific (B2 already flags this).
2. **Git-tracked project skills** in `workspace/.cursor/skills/workflow/` (already
   there) plus a documented copy step to `~/.cursor/skills/`. Current state on LAPTOP-B:
   the two copies match. There is **no detector**. `version_drift.py` reads
   `~/.claude/plugins/installed_plugins.json` and the `reentry:begin` marker in
   `~/.claude/CLAUDE.md`. Neither exists on the Cursor side.
3. **Reuse Claude Code's install via third-party skill loading.** Observed to surface
   plugin skills in this session. Does not give working hooks (`CLAUDE_PLUGIN_ROOT`
   unset; injection unproven). Pulls the wrong `SKILL.md` (Q2).

### Drift detection (does not exist)

Require a Cursor-side check that compares, at session start, at least:

- hashes or versions of `~/.cursor/skills/{next,wrap}/SKILL.md` against the copies in
  `workspace` (or against the Cursor plugin version);
- presence of `~/.cursor/hooks.json` / project `.cursor/hooks.json` if those are part
  of the install.

A one-line "stale" in orientation, same job as `version_drift.py`. Warn, never
auto-install. Until that exists, the only detection this session performed was a
manual `Get-FileHash` of two files.

Account-shared settings (rules, enabled plugins, third-party toggle) will not stay
per-machine. Machine-local state (`~/.cursor/hooks`, Python on PATH, `glab` host)
will. The adapter must not store "which GitLab host" in an account setting (same
reason `issue_host.py` refuses a config key).

---

## 4. Scripting

**Yes. A Cursor skill can shell out to Python.** This Agent's Shell ran the plugin
scripts with no Claude Code environment.

| Tool | Result this session |
|---|---|
| `hooks/session_orientation.py` | Ran. Printed queue, `machine: LAPTOP-B`, wrap-verdict instructions, version-drift warning (`plugin.json` 1.34.0 vs rules block 1.33.0), git-ahead banner. Discovered project root from cwd, not `CLAUDE_PROJECT_DIR` (unset). |
| `hooks/archive_offer.py --check` | Ran. `NONE` |
| `tools/check_repos.py` | Ran. "No repos to check" (B39 shape: this session's writes went through Shell, which the recorder does not watch unless hooked) |
| `tools/measure_context.py <worktree>` | Ran. Counted `~/.claude/CLAUDE.md` + project `CLAUDE.md` + plugin hook/skills. It is measuring **Claude Code's** baseline, not Cursor's. |
| `hooks/machine_identity.py` as a CLI | No `__main__`. Identity appeared because `session_orientation.py` calls `check()`. |
| `tools/sync_backlog.py` | **Not run** (would talk to the issue host). Plain Python, but it now goes through `issue_host.py`, which shells out to `gh` or `glab`. |

`CLAUDE_PLUGIN_ROOT` and `CLAUDE_PROJECT_DIR` are **empty** in the Cursor Agent shell.
Scripts that take a path argument, or that fall back to cwd, work. Skill instructions
that still say `python "$CLAUDE_PLUGIN_ROOT/tools/..." ` do not, unless the adapter
sets that env (Cursor `sessionStart` can return `env`; **unverified it sticks for
subsequent Shell tool calls**, documented only as "available to all subsequent hook
executions").

**Reusable verbatim, with caveats:**

- The Python has no Claude Code import. It runs.
- Anything that substitutes `${CLAUDE_PLUGIN_ROOT}` in a *hook JSON command string*
  will not. Point Cursor hooks at absolute or repo-relative paths, or set `env`.
- `measure_context.py` / `timesheet.py` / `version_drift.py` / `check_install.py` are
  Claude-install-shaped. Running them from Cursor reports the Claude side of the
  same machine, which is still useful on a dual-harness laptop and silent-wrong on
  LAPTOP-A/LAPTOP-B if you read the numbers as "this session's cost".
- `sync_backlog.py` is reusable as a program. On this machine it is gated by B49
  (LAPTOP-B `glab` host) and B58 (`glab` 1.93.0 has no `--description-file`; every GitLab
  *push* fails inside `issue_host.py`). That is not a Cursor bug. An adapter that
  calls `sync_backlog.py` on LAPTOP-B will hit it.

Windows: `python` resolved to 3.11.9, not the WindowsApps stub. README's Windows
alias caveat did not fire here. **Unverified on LAPTOP-A / the desktop / WSL.**

---

## 5. Identity and state

### Machine

Cursor's injected `user_info` has OS, shell, and workspace path. It does **not**
name the host. Same gap `machine_identity.py` was written for. Running
`session_orientation.py` printed `machine: LAPTOP-B` (`platform.node()`). The
adapter should keep calling that function. Do not teach the model to guess from
`LAPTOP-B` in a path; the path is not always there.

### Session id

Cursor docs: `sessionStart` input `session_id` (same as `conversation_id`). Transcript
directories are named with a UUID
(`agent-transcripts/b3b1bfa8-804d-4b9f-b45c-5d26d91397ca/…`). **Unverified** that
those two UUIDs are always the same, and **unverified** the id is exposed to a skill
without a hook (no `CURSOR_SESSION` env in the shell).

### `timesheet.py` — included, and it is a build, not a reuse

`tools/timesheet.py` is first-class Claude Code functionality (README row, v1.21.0+):
hours from transcripts, no new capture, `--attribution parallel|exclusive`,
`--projects PATH` for a second machine. The work machines are out of scope today
because it only reads Claude Code jsonl.

Cursor **does** write transcripts. They are not that jsonl.

- Path: `~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl`
- Shape (this session): `{"role":"user"|"assistant","message":{"content":[…]}}`
- `timesheet.py` wants `type == "user"`, a structured `timestamp`, `cwd`,
  `custom-title`. None of those keys were in the Cursor file I opened.
- User turns here carry a clock *inside the prompt text*
  (`<timestamp>Friday, Sep 4, 2026, 1:11 PM (UTC+2)</timestamp>`). That is
  parseable and is not an API. Assistant turns in the same file had no clock.
  Gap classification (user-wait vs agent-run) therefore has nothing to stand on
  for agent-terminated gaps.
- `sessionEnd` input documents `duration_ms` and `session_id`. That is one number
  per session, not the per-message series `timesheet.py` is built on.
- README: "Cursor writes no Claude Code transcript, so those machines are out of
  scope." The second clause is still right. The first is easy to misread as
  "Cursor writes nothing."

**Do not call `timesheet.py` from a Cursor skill and expect LAPTOP-B hours.** It will
run, read `~/.claude/projects/`, and report Claude Code sessions on this laptop
(few or none) as if that were the week's work.

**What the adapter can build** (pick one; do not do both in v1):

1. A Cursor backend inside `timesheet.py` (or a sibling) that reads
   `~/.cursor/projects/*/agent-transcripts/*/*.jsonl`, maps `role` to user/agent,
   and takes timestamps from the injected `<timestamp>` tag where present.
   Mark agent-gap duration **unverified** until assistant records carry a clock
   or the reader uses file mtime (a bad clock). `--projects` should accept a
   Cursor transcripts root the same way it accepts a Claude one.
2. A `sessionEnd` command hook that appends one row
   `{session_id, cwd, duration_ms, reason}` to a gitignored jsonl that a thin
   reporter sums. Loses per-project overlap attribution. Survives even if
   transcript schema changes.

Rejected: a derived ledger next to `NEXT.md` (B10: second store that drifts).
Rejected: pretending the existing reader will start working.

Work-machine timesheet is **optional v1**. Re-entry does not depend on it.
Billing on LAPTOP-A/LAPTOP-B does. If that is in scope for B2, it is a named sub-deliverable,
not a freebie of "the Python is reusable."

### Other state Claude Code has that Cursor does not expose here

- `set_session_title` / `list_sessions` (Claude Code). Cursor has a `rename-chat`
  MCP tool on some projects; **unverified in this repo's MCP set** (this session
  did not receive it).
- `.claude/.last_wrap`, `reentry-state/`, item-open markers. Files on disk. A Cursor
  session can read and write them if it knows the paths. Nothing currently writes
  them on this harness. `session_orientation.py` still *read* wrap state when we
  ran it by hand ("24 commits since the last wrap").

---

## Plugin surface vs adapter (what Claude has that the first draft under-specified)

Inventoried against `plugins/cairn/` on this tree (v1.34.0). Tests omitted.
`audit_coverage.py` is an authoring tool for trimming rules, not session runtime.

**Free if the adapter runs `session_orientation.py` at start** (this session
observed machine line, drift warning, and a rules-block rewrite message when we
ran it by hand):

| Module | Job |
|---|---|
| `session_orientation.py` | Queue, due watches, inbox, wrap leftover, relay tier |
| `install_rules.py` | Writes `~/.claude/CLAUDE.md` between markers |
| `ensure_mistakes_file.py` | Creates `~/.claude/MISTAKES.md` if missing |
| `ensure_credentials_file.py` | Creates `~/.claude/CREDENTIALS.md` if missing |
| `version_drift.py` | Repo vs installed vs rules-block (Claude plugin paths) |
| `machine_identity.py` | `platform.node()` |
| `item_open.py` | Read orphan "started an item, never wrapped" |
| `issues_backlog.py` | Disk cache of issue counts; detached refresh; no network on the start path |
| `backlog_file.py` | Local `BACKLOG.md` parse / refuse-unreadable |

Cursor-specific gap inside that bundle: `install_rules.py` targets
`~/.claude/CLAUDE.md`. **Unverified** that Cursor loads that file in a work
project. The adapter should either keep writing it (one file, both harnesses, on
a dual-install machine) **and** install a Cursor always-on rule
(`.cursor/rules/reentry.mdc` or `AGENTS.md`) from the same source. Two generated
artifacts, one source (`rules/CLAUDE.md`). Do not fork the rules text.

`MISTAKES.md` / `CREDENTIALS.md` should stay at `~/.claude/` even on Cursor-only
machines so one log covers both harnesses when both exist. Create the directory
if missing (the ensure scripts already do). Wrap on Cursor must append
`MISTAKES.md`; the work-side `wrap` skill does not mention it.

**Separate hooks. Claude Code wires them. Cursor can. Not inside orientation.**

| Module | Claude event | Cursor event | Build? |
|---|---|---|---|
| `item_start.py` | `UserPromptSubmit` | `beforeSubmitPrompt` (matcher `UserPromptSubmit`) | Yes. Prints nothing; stamps `item_open`. Cursor stdin JSON **unverified** against the regex that reads the prompt text. May need a thin stdin adapter. |
| `repo_recorder.py` | `PostToolUse` `Edit\|Write\|NotebookEdit` | `postToolUse` + **`afterShellExecution` / `afterFileEdit`** | Yes. Cursor can cover B39 (Bash-mediated writes) which Claude's matcher currently misses. This session was exactly that shape. |
| `dirty_tree_warning.py` | `Stop` + `SessionEnd` | `stop` + `sessionEnd` | Yes as side effects. Cursor `stop` is per-completion; same "speak only when worse" logic applies. `sessionEnd` output is unused in both harnesses; the breadcrumb on disk is the payload. |
| `archive_offer.py` | wrap skill, not a hook | wrap skill | Yes. We ran `--check`. State lives outside the repo. |

**Wrap/next tools the work-side Cursor skills currently skip or under-call:**

| Module | Job | Adapter |
|---|---|---|
| `check_repos.py` | Did fan-out writes land? | Call from wrap, same as Claude. Needs the recorder hooked or `--known`. |
| `sync_backlog.py` | File is writer; host is copy | Call from wrap. LAPTOP-B write path is B58 until fixed. |
| `label_backlog.py` | Ensure `afk`/`hitl` labels | Call from wrap. `--ensure` is mechanical. |
| `issues_backlog.py --refresh --report` | Cache refresh that names `gh`/`glab` | Call from wrap. Replaces the old `gh issue list` block. |
| `session_orientation.py --check` | Validate the `NEXT.md` just written | Call from wrap. |
| `measure_context.py` | Token baseline | Optional. Measures Claude's load, not Cursor's, until taught otherwise. |
| `check_install.py` | Did the plugin update land? | Needs a Cursor equivalent (plugin version or skill hashes). Do not run the Claude one and believe it about Cursor. |
| `timesheet.py` | Hours | See Q5. New reader or `sessionEnd` row. Optional v1. |

**Not in the plugin yet** (do not invent in the adapter): `inbox_post.py` (B54, here B32) and
`ensure_project_files.py` (B57, here B35). Call them when they exist. *(Corrected 2026-09-23:
`check_exits.py` is no longer on this list. It ships, as `tools/check_exits.py`.)*

*(Added 2026-09-23: the inventory above was taken at v1.34.0. These modules have been added since
and are missing from it: `push_check.py`, `settings_drift.py`, `wrap_receipt.py`, `repo_sweep.py`,
`touched_repos.py`, `ensure_profile_file.py`, `staged_review_guard.py`, `tools/validate_next.py`,
`tools/check_settings.py`, `tools/check_credentials.py`, `tools/check_leak_coverage.py`,
`tools/fence_check.py`. Re-inventory `plugins/cairn/` before designing.)*

**Claude Code APIs with no Cursor twin in this session:** `set_session_title`,
`list_sessions` (junk-title sweep at `/next` step 0). Cursor `rename-chat` MCP
exists on other projects in this account; **not in this session's tool list**.
Unverified. Do not block v1 on pretty titles.

---

## 6. What of the contract cannot be honoured

The contract: `NEXT.md` / `INBOX.md` / `BACKLOG.md` / `CHANGELOG.md` plus a rationale
record. B57: every tracked project should carry all five, blank if need be. **Not
yet true on disk** (measured in B57: 1 `INBOX.md` in 18 repos). The adapter must
**not** create them (handoff forbids demonstration creates). It may *assume* they
will exist once B57 lands, and must degrade when they do not.

| Piece | Cursor can honour? | Why |
|---|---|---|
| Read `NEXT.md` / `INBOX.md` / `BACKLOG.md` / `CHANGELOG.md` / rationale | Yes | Ordinary file reads. Proven this session. |
| Rewrite `NEXT.md` at wrap | Yes, as a skill | Same hazard as Claude Code: wholesale rewrite from a stale copy. B55's re-read rule applies. The work-side `wrap` skill already rewrites `NEXT.md`. |
| Append `INBOX.md` (B54) | Yes, if the file exists | Shell `>>` or Python `open(..., "a")`. Most projects have no file (B57). |
| `BACKLOG.md` as writer of record | Yes as a file | Sync to the issue host is `sync_backlog.py` + `issue_host.py`, not Cursor-specific. On LAPTOP-B the GitLab *write* path is B49/B50/B58, not "Cursor cannot". |
| Automatic session-start orientation | **Not honoured today** | Hook events exist; none installed; `additional_context` injection unverified/possibly broken. Skills that would substitute are `disable-model-invocation: true` and/or the wrong SKILL.md. |
| `UserPromptSubmit` item-open marker | **Not honoured today** | `beforeSubmitPrompt` exists, not wired. |
| `PostToolUse` repo recorder | **Not honoured today** | `postToolUse` exists, not wired. B39 confirmed live this session: `check_repos.py` saw nothing because writes went through Shell. |
| `Stop` / `SessionEnd` dirty-tree / unwrapped warning | **Not honoured today** | Events exist, not wired. Side-effect hooks should work even if injection does not. |
| Plugin install / version drift | **Cannot honour as written** | Different plugin format. No `version_drift.py` counterpart. |
| Timesheet | **Cannot reuse `timesheet.py`** | Different path and schema. A Cursor reader or `sessionEnd` row is buildable; see Q5. |
| `CLAUDE_PLUGIN_ROOT` skill snippets | **Cannot honour** | Env unset. |
| `set_session_title` as in `/next` step 7 | **Unverified / likely no** | Different harness. |
| EnterWorktree | **No as a tool** | `git worktree` works; Cursor does not expose Claude Code's `EnterWorktree`. The operator (or the agent via Shell) must add the worktree and point the window at it. This session's Cursor window stayed rooted in the original folder and wrote via absolute paths. That is workable and easy to get wrong. |
| AFK / permission mode as Claude Code Shift+Tab | **Unverified** | Cursor has Agent / Plan / Ask / … The work `wrap` skill already uses Cursor's mode vocabulary. Mapping `AFK/Auto` onto Cursor permission prompts is unverified. |
| Rules payload `~/.claude/CLAUDE.md` | Partial | This *repo's* `CLAUDE.md` loaded. The generated user-level `~/.claude/CLAUDE.md` is what `measure_context.py` counted (5,643 tokens) and what `install_rules` writes. **Unverified** whether Cursor injects that file in a project that is not `agent-reentry`. Work projects may only see `.cursor/rules` / `AGENTS.md`. |
| Cloud / background agents | Weaker | No `sessionStart` / `sessionEnd` on cloud agents. User `~/.cursor/hooks.json` does not travel there. Project `.cursor/hooks.json` does. |

**This section decides the adapter's shape.** v1 that actually works:

1. File contract unchanged (markdown on disk). Do not invent a second format.
2. Native Cursor hooks for side effects (marker file, dirty-tree log, item-open stamp,
   repo recorder). Do not wait on `additional_context`. Wire `afterShellExecution` as
   well as `postToolUse` / `afterFileEdit`, or B39 repeats (Shell writes stay invisible).
3. Always-on Cursor rule (or a tiny auto-invoked skill) that says: before the first
   user-visible reply in a project that has `NEXT.md`, run `session_orientation.py` and
   relay it. That is the substitute for Claude Code printing the hook stdout into
   context. Running that one script already pulls in `install_rules`, `ensure_mistakes_file`,
   `ensure_credentials_file`, `version_drift`, `machine_identity`, `item_open`, and
   `issues_backlog` cache+detached-refresh. See the inventory below.
4. Cursor-native `next` / `wrap` skills that call the same Python with explicit paths,
   not `$CLAUDE_PLUGIN_ROOT`. Drop `disable-model-invocation` on the orient skill only.
   Wrap must keep calling `check_repos.py`, `session_orientation.py --check`,
   `sync_backlog.py`, `label_backlog.py --ensure`, `issues_backlog.py --refresh --report`,
   `archive_offer.py`. The work-side `wrap` skill currently names almost none of these.
5. Worktree rule as in the findings (B55). Cursor has no `EnterWorktree`; the skill
   must say `git worktree add` and then operate with `-C` / absolute paths, or ask him
   to reopen the folder (HITL).
6. Do not claim timesheet, Cursor version-drift, or GitLab push until those have a
   Cursor-shaped path. `timesheet.py` as-is will lie on LAPTOP-B. GitLab push is B58 on any
   harness.

---

## 7. Cross-project messaging (B54)

Can a Cursor skill write outside the open project and run git in that other tree?

**Write outside the open project: yes, verified.** This window's workspace root is
`~/Projects/agent-reentry`. It created and reset
`~/Projects/agent-reentry-cursor-reqs`, copied files there, and ran git with
`git -C`. There is no project jail on the Shell/Write tools used here.

**Git in another tree: yes, verified** (`git -C ~/Projects/workspace status -sb` →
`## master...origin/master`).

**Commit and push the append: not demonstrated** (handoff forbids creating
`INBOX.md` elsewhere as a demo). Same Shell tool, same `git -C`. **Unverified:**
whether Cursor's permission UI blocks `git push` in a foreign repo, sandbox
network, or `glab`/`gh` auth on LAPTOP-B.

**What it can do instead if push is blocked:** write the append, commit locally,
say the push failed. B54 already requires that. Do not leave a chat-only note.

**Catalog resolution (`workspace/docs/catalog.yml`):** **unverified this session**
(not opened). B54's `inbox_post.py` does not exist yet. The adapter should call
that tool once it exists, not reimplement project lookup in a skill.

**Fallback when there is no local clone:** B54 says file an issue on the issue host
(`gh` / `glab`), not the browser. v1.34.0 shipped the host layer. On LAPTOP-B the write
path is still B49/B50/B58. A Cursor skill that "successfully" shells out to
`sync_backlog.py` / `glab issue create --description-file` will fail opaquely
(`could not file: ERROR`). Until B58 is fixed, the honest fallback on this machine
is: say you cannot file, paste the bullet for him. Do not report success.

**One work repo checked has no `INBOX.md`.** B57. A foreign post there today
has nowhere to land. This repo now has one (`INBOX.md` on this branch), so it can
receive a B54 post. Other projects still cannot.

---

## What Claude gets wrong (do not copy into the adapter)

These are harness or payload defects, not Cursor-only. An adapter that clones them
gives colleagues two broken copies.

| Failure | Evidence | Adapter / shared-plugin rule |
|---|---|---|
| Assert a capability is absent without searching | README and work `next` skill: "Cursor has no SessionStart-equivalent." False. B20. | Write **unverified**, not "none." |
| `isolation: worktree` as default for nested agents | 2026-08-25: eight dirty trees, agents pointed at the wrong repo | Independent *sessions* get a worktree. Subagents do not inherit that blindly. |
| "Second writer needs a branch or a worktree" | B55; this session. A branch shares the dirty tree. | Worktree or separate clone. Not a branch in the same folder. |
| Donor keeps writing after handover | Workspace INBOX 2026-09-04: Claude wrapped/pushed `main` while Cursor held a worktree | B55 **GAP**: donor stops, including wrap-to-main, until the other reports done. |
| `ask Forge` as global vocabulary | B19. Forge was also the name of one of the operator's private projects. | Fixed 2026-09-05: the token is now `ask <authority>` everywhere, `issue host` for the generic sense. Don't reintroduce `forge` as a name in the adapter. |
| Recorder ignores Shell | B39; this session: `check_repos.py` saw nothing | Cursor: also wire `afterShellExecution`. Do not copy the Edit\|Write matcher and stop. |
| Git fetch is one repo | B26; 19-commit miss while standing in `workspace` | Hub sweep is catalog-scale. Per-session hook stays one repo. |
| `$CLAUDE_PLUGIN_ROOT` in skills | Unset in Cursor | Python with explicit paths is the portable unit. |
| `timesheet.py` as if it were harness-neutral | Claude jsonl only | Cursor needs a reader or `sessionEnd` row. Optional v1. |
| `## 12.` vs `## B12.` | B46; would have deleted 206 lines | Parser / refuse already shipped; colleagues' files will use both shapes. |
| `glab --description-file` | B58. Every GitLab push fails on 1.93.0 | Fix before calling GitLab shipped. Not a Cursor bug. |
| Rules payload is the operator | B12. Personal and employer details in `~/.claude/CLAUDE.md` (stripped at v1.45.0) | Do not generate `.cursor/rules` from that file until B12. |
| Absence of `INBOX.md` meaning two things | B57 | Blank file vs opted-out. Adapter degrades; does not invent membership. |
| WSL git identity item left stale | B34 vs measured 2026-09-04 `user.email` is set | Re-check before queueing. Credential helper half may still be open. |

Claude Code also gets some things **right** that Cursor should keep: file-is-writer
(v1.18.0), never pull unasked, warn-never-block, fail open on hooks, issue host
detected from origin not config, `MISTAKES.md` as pattern log not a mailbox (B54).

---

## Sharing, other harnesses, other hosts, other filesystems

Colleagues will run Claude, Cursor, or both. The operator cannot test other agents.
GitHub and GitLab are the two hosts; others should degrade like a missing backend.
Clones live on Windows, WSL, and SSH servers, sometimes as a folder of repos,
sometimes as a subfolder of a repo (v1.29.0 already scopes git warnings to the
subtree).

**Contract that travels:** the five markdown files, append-only foreign `INBOX.md`,
one writer per working tree, wrap rewrites only its own tree. Unknown harness:
one sentence ("no session-start hook: orientation is a skill"), same files.

**What must not travel until B12/B51:** the person-specific payload. D1: a separate
public plugin repo, fresh `git init`, not this history. Installing on a shared SSH
server before B12 is how a colleague reads the operator's personal paragraph.

**Issue hosts:** `issue_host.py` is the extension point. A third host is a backend,
not a new `BACKLOG.md`. Permanent vs retry skip lines must stay honest. B58 is the
live GitLab hole.

**Path identity:** `state_dir()` hashes `root.resolve()`. Windows, WSL (`/mnt/c/...`
vs `~/Projects/...`), and an SSH checkout of the same repo are three silos for
wrap markers, item-open, dirty-tree breadcrumbs, and timesheet rows. Git files
sync; plugin memory does not. Same class as `code` → `Projects` (B15). Do not
pretend a wrap on Windows closes the WSL tree. Catalog git sweep (B26 extended)
must name the environment, not only the repo.

**SSH servers (B32):** decide whether a staging box is a project you re-enter or a
deploy target. Until that is "deploy target", server work lives in the laptop
repo's `NEXT.md`. The plugin assumes a working tree with a queue, auth, and a
home directory it may write under `~/.claude`. Shared machines fail B12.

**Subfolders:** already handled for dirty-tree noise. A hub catalog must still
list *projects* (`NEXT.md`), not every git root.

The operating loop (morning pull, hub vs stay, evening wrap, MISTAKES review, and what is CI/CD
and must stay out) is summarised in `BACKLOG.md` B31 and B38. Its brief stayed private.

---

## Adapter constraints (summary)

Build around these, not around feature parity:

1. Cursor has the hook *surface*. This machine has none wired, and model injection
   from `sessionStart` is unproven. Side effects and rules/skills are the reliable
   channels.
2. Python tools run. Env vars and hook JSON from Claude Code do not travel.
3. Two skill trees already coexist on LAPTOP-B (Cursor copies vs Claude plugin cache)
   and only one appeared in this session. Distribution has to pick a winner and
   detect drift.
4. Transcripts exist and are the wrong shape. Timesheet stays Claude-only until
   someone writes a reader.
5. Cross-repo append + `git -C` works. Issue-host push on LAPTOP-B currently does not
   (B58), independent of Cursor.
6. Isolation is a worktree, not a branch. Cursor will not `EnterWorktree` for you.
   Donor GAP (B55): stop writing the handed repo, including wrap-to-main.
7. Do not create the five files in *other* repos as a demo. Assume B57; degrade
   if a file is missing. This repo's `INBOX.md` was created here so capture had
   a mailbox (user asked; B57).
8. Do not copy the Claude misses table into Cursor as "parity."
9. Do not generate colleague-facing rules from today's `rules/CLAUDE.md` (B12).

---

## What this session did not do

- Did not install or fire a Cursor hook (would have been implementation).
- Did not toggle or inspect "Include third-party Plugins, Skills, and other configs"
  in the UI.
- Did not run `sync_backlog.py` or any `gh`/`glab` write.
- Did not open Cursor on LAPTOP-A or the desktop.
- Did not verify cloud/background agents.
- Did not prove `sessionStart.additional_context` injection.
- Did not create `AGENTS.md`, project `.cursor/rules`, or `.cursor/hooks.json`.
- Did not edit `BACKLOG.md` or `NEXT.md` (off limits; merge conflicts with `main`).
  Capture went to `INBOX.md` + `briefs/daily-operating-loop.md` for wrap triage.
