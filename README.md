# cairn

A Claude Code plugin for people who cannot hold state between sessions.

*A cairn is a marker left deliberately on a trail so the way back can be found. This one is
built when you leave a session and read when you arrive at the next.*

It prints where you left off at the start of every session, and gives you two commands: one to
re-enter work, one to end a session so the next one can start from disk instead of from memory.

## Why

Built for a stated problem: several projects running at once, long gaps between them, and no
reliable way to remember where any one of them was. Some people arrive at that through sheer
number of projects, some through how they work, and some for reasons that make holding state
between sessions genuinely not an option. The mechanism does not need to know which.

**Re-entry is the bottleneck, not the code.** A session that produces excellent work and no
recoverable entry point has failed at the part that matters most.

The fix is not a better-organised document. It is removing the need to remember that a document
exists.

## What you get

| Component | What it does |
|---|---|
| `SessionStart` hook | Prints the project's queue, any **due** watches, and un-triaged inbox items — before you type anything. Leads with anything the last session left behind. Silent in projects without a `NEXT.md`. In this plugin's own repo (v1.30.0+), also compares that repo's `plugin.json` version against the version actually installed on the machine and says so in one line if they differ — detects a stale install, never auto-installs. Silent in every other project. Names the **machine** it is running on in one line (v1.31.0), so an item annotated *"run on LAPTOP2"* can be checked instead of assumed — the agent's context carries the cwd and platform but never the hostname. Only where there is a queue; a project without a `NEXT.md` stays bit-for-bit silent. Since v1.36.0 a watch whose trigger reads `[the] next session on <id>` becomes **`DUE NOW`** on that machine — before, the portfolio's most common trigger could only ever render under *"not actionable yet"*, collapsed, on the very machine it named. **The optional article is not decoration (v1.53.1):** the pattern shipped anchored with no article, and every watch anyone actually writes says *"the* next session on …", so for five versions this feature matched none of them and the sentence above described something that did not happen. Also since v1.36.0 the divergence banner survives an **empty Queue**: it was computed and then dropped, which hid it in exactly the projects nobody had worked in lately and so the most likely to be stale. Since v1.32.0 it also compares the installed version against the version of the **rules block actually loaded** into every session (`<!-- reentry:begin v… -->` in `~/.claude/CLAUDE.md`) — this half is deliberately **not** scoped to that one repo, because those rules load everywhere. A file with no block is reported as *never installed*, not as up to date. |
| `rules/CLAUDE.md` | The **rules layer** (v1.9.0+). Installed into `~/.claude/CLAUDE.md` inside markers, so the behaviour the system depends on travels to every machine, not just the one it was written on. **Since v1.45.0 it is the MECHANISM only** — it names no person, machine, employer or private project, because it installs into the always-loaded context of everyone who installs the plugin. Who the user is, and how they like work done, moved to the profile in the row below. `tools/test_payload_clean.py` fails the suite if any of it comes back. See `docs/design-notes.md`. |
| `~/.claude/reentry-profile.md` (v1.45.0+) | **The half that is yours.** The rules are generic and shared; identity (who you are, your machines, your issue host) and preference (report length, delegation style, whether a side quest gets chased or recorded) live here, and reach every session through an `@` import written into the managed block. Seeded once from a commented template by `hooks/ensure_profile_file.py` and then never touched — a hand-written profile is never overwritten without a backup beside it. **Working from more than one machine?** Set `REENTRY_PROFILE_SOURCE` to a copy in a repo or synced folder you already have and the plugin refreshes this file whenever that source is newer — one direction, never back. **Give it a repo with one job, outside the directory your projects live in.** A repo that is itself one of your projects — anything the sibling sweep can see — is the refused case below, so a folder that is convenient *because* you already open it is the one layout that cannot work (B107, then B112 when the fix for B107 chose a repo that was also a project). Whatever syncs the folder is your choice; the plugin syncs nothing. **Since v1.46.0 a source that resolves inside the current project is refused, and a relative path is refused outright** — a project's own `.claude/settings.json` can set this variable for the hook, and an unresolved relative path let any cloned repo overwrite this file the first time it was opened (B100/B103). The refusal is reported every session until fixed, regardless of relay tier. |
| `Stop` + `SessionEnd` hooks | Notice uncommitted work, and commits made with no wrap. Speak only when the state gets **worse**, never once per turn. Silent in projects that have never wrapped. Since v1.29.0 they answer about **your folder, not the whole repository**: a session opened in a subdirectory no longer warns about sibling folders it isn't touching, and per-folder wrap markers work. Projects that are their own repo — nearly all of them — are unaffected. |
| `UserPromptSubmit` hook (v1.20.0+) | Records that you **started** a queue item, so a session that starts item 3 and never wraps is caught at the next session start instead of looking identical to an item nobody touched. Writes a breadcrumb, prints nothing, clears itself. See `docs/design-notes.md`. |
| `/cairn:next` | Re-enter: relay the queue, surface due watches, triage the inbox, start an item by number. Every item says whether it is **`AFK` or `HITL`** and which **permission mode** to set before you start (v1.16.0+). |
| `/cairn:wrap` | Exit: changelog entry, commit, push, rewrite the queue, close finished issues, so the next session starts from disk. **Since v1.44.0 it ends at step 8c by recording a CAIRN receipt, and the close quotes that token instead of wording a verdict** (see the row below). Runs `session_orientation.py --check` on the `NEXT.md` it just wrote (v1.19.0), so a malformed item is caught then, not at the next session start. A declined archive offer (step 10) is remembered outside the repo (v1.28.0) and rides along with the next "no wrap needed"/"wrapped" verdict in the same session, instead of getting lost to conversation memory. Since v1.35.0 step 10 also records that the question was **asked**, before asking it — without that, a bare `NONE` covered two opposite states, and a wrap done by hand that skipped the step read back as settled. **Since v1.40.0 an unattended (`AFK`) item stops before the push** and before the backlog sync, reports what changed and what it decided, and ends the turn — `AFK` is about attendance during a run, never about whether the result gets read. The archive offer is suspended with it, since archiving would end the session that still owes the push.  **Since v1.42.0 that stop is verified rather than asserted** — step 5 captures `HEAD` before it commits and runs `push_check.py`, and the verdict quotes what the check measured. Before dropping a `closed` item, the sync checks `CHANGELOG.md` for a record of it (B45); **since v1.43.0 that check recognises a dated heading at any depth (`##`-`####`), not only a `## YYYY-MM-DD` prefix** — it previously matched zero of one project's 302 `### rev N — YYYY-MM-DD` headings, so every closed item there was reported as unverifiable regardless of what the file actually recorded. The log message also now says whether the file was missing or merely unparsed — naming a missing file when a real one sat there unparsed had twice been read as "the tool is broken." |
| `BACKLOG.md` | The **backlog** layer, in every project since v1.18.0 — unbounded, unordered, on disk, no remote or network needed. Items on the Queue stay listed here marked `queued`; finished ones are marked `closed` and dropped by the next sync.  **Since v1.42.0 the id allocator cannot regress or collide silently:** the next number is the highest of what is in the file, a `<!-- next-id: N -->` marker that survives an item being dropped, and the last-fetched `origin/<branch>` — with a duplicate-id detector reported at session start as the backstop for two sessions racing before either has pushed. The parser is also **fence-aware**, so pasting command output that quotes a `## Bn.` heading no longer mints a phantom item and no longer lets a regeneration edit words inside your quoted evidence. |
| GitHub **or GitLab** Issues (optional) | Where `BACKLOG.md` **syncs** (v1.18.0; it used to *be* the backlog). **Both hosts since v1.34.0** — `gh` for GitHub, `glab` for GitLab, including a self-hosted instance, picked from the git remote with nothing to configure. Edits propagate, not just the first draft — a changed item re-pushes its title and body (v1.21.1); issues other people filed are never overwritten. Unbounded, cloud-stored, and the only part of the system other people can write to. Summarised in one line at session start, from a cache — no network call in the start path. Labelled **`afk`/`hitl`** so you can filter for work you can set running unattended (v1.16.0+). Entirely inert, and honest about it, on a remote no backend covers. |
| `tools/timesheet.py` (v1.21.0+) | **What did I work on this week, and for how long.** Reads the per-message timestamps already in your session transcripts — no new capture, nothing to remember to start or stop. Groups by day and project, joins to session titles, `--csv` for pasting elsewhere. **Since v1.40.0 every `--projects` root prints the age of its newest transcript** — unconditionally, to stderr so it survives a `--csv` redirect — because a stale mirror and a live mount are indistinguishable from a total. A root with no transcripts warns rather than contributing a silent zero. See `docs/design-notes.md`. |
| `tools/timesheet_sync.py` (v1.40.0+) | **The transport that makes `--projects` reachable.** Two laptops with no network path between them: direct SSH was tried and fully reversed — DNS, then a Private-vs-Public firewall profile, then an IP-scoped rule that still timed out, which is a network-level block no local config can fix. This copies **this** machine's `~/.claude/projects` into a OneDrive folder and lets OneDrive's own sync carry it; point `--projects` at the copy on the other side. Deliberately one-shot and manual, not scheduled — a background mechanism that fails silently is what got a machine-global change reverted here the day before. |
| `PostToolUse` hook (v1.25.0+) | Records every git tree the session actually **wrote to** outside its own project — subagent writes included — so `check_repos.py` runs off a record instead of off the agent's memory of where it sent work. Prints nothing, never fails a tool call. See `docs/design-notes.md`. |
| `tools/sync_backlog.py --dry-run` (v1.26.0+) | **Ask what a sync would do without doing it.** All three issue-host tools parse flags through `argparse`, so `--help` prints usage and an unknown flag exits 2 — before any host call. Previously an unrecognised flag fell through to the real sync. It earned its keep on 2026-09-03: a dry run reporting *16 pulls and 0 pullable items* is what exposed the hazard the row below now guards. See `docs/file-formats.md`. |
| `tools/check_repos.py` (v1.24.0+) | **Did the work you sent into other repos actually land?** Every other check here looks at the repo you are sitting in, so a fan-out can leave eight dirty trees while this one is spotless. `/cairn:wrap` step 1a asks it before the changelog entry is written, so a "done" entry can't claim what no repo confirms. Since v1.25.0 it answers with no arguments. Since v1.29.0, a path inside a repo reports **that folder's** dirty count while `unpushed` stays branch-wide, and the row says so. Since v1.35.0 the recorder also parses **`Bash` and `PowerShell`** commands for paths: before that, a session whose file work went through the shell had *zero* recorded coverage while this tool reported "nothing was recorded writing outside this project" as a clean bill of health. That line no longer reads as reassurance, and the tool now prints the project root it resolved — because it can resolve the wrong one when the shell's cwd has drifted. See `docs/design-notes.md`. |
| `tools/check_install.py` (v1.32.0+) | **Did the plugin update actually land on this machine?** Prints the three versions that can disagree — what the repo shipped, what is installed, and what is in the rules block the agent actually reads — with a verdict and the remedy for each case. Answers the one gap no hook can see: `install_rules` writes the rules block from `SessionStart`, so between `claude plugin update` and the next session actually starting, a machine reports the new version and runs the old rules. Update, **start a session**, then check. Replaces the old "grep for a phrase the new version added" advice, which rotted at every bump. Run it from a checkout of this repo as `python plugins/cairn/tools/check_install.py`; **from any other project** — which is where you usually want it — reach the installed copy through the cache, since its path carries the version and so changes at every bump: `python (Get-ChildItem "$env:USERPROFILE\.claude\plugins\cache\superbole\cairn\*\tools\check_install.py" | Sort-Object LastWriteTime | Select-Object -Last 1).FullName` |
| `hooks/issue_host.py` (v1.34.0+) | The **issue host layer** — one interface, two backends. Everything provider-specific lives here, so `sync_backlog.py`, `label_backlog.py` and the session-start cache contain no `gh` and no `glab`. The host comes from the `origin` hostname; a self-hosted instance whose name gives nothing away (`git2.example-corp.net`) is resolved from the CLI's own list of hosts you have logged into — a fact about the machine, never a config key that can be right on one machine and wrong on another. |
| `backlog sync REFUSED` (v1.34.0+) | **A `BACKLOG.md` the parser cannot fully read is never rewritten.** A sync regenerates the file from what it parsed, so an item heading written `## 12.` instead of `## B12.` would be deleted by the next successful sync. `sync_backlog.py` now names those headings and refuses the whole run before a single host call, and `backlog_file.write()` raises rather than clobber the file. Found the day the GitLab backend shipped, in a repo whose 13 headings all parsed to nothing — 206 lines, one write away. |
| Cross-repo staleness sweep (v1.35.0+) | **Every repo in the portfolio, not just the one you are standing in.** The divergence banner existed because work happens on several machines and "the files in front of me are the current ones" stopped being true — but it only ever checked the current repo, so a sibling could sit weeks behind `origin` with nothing saying so. Sibling repos are found by having a `.git` **and their own `NEXT.md`**, so opting in is still just having one. Measured before shipping: a per-repo check costs ~1.0-1.3s even against a local remote and 8 repos took 8.3s, which ruled out running it inline — it reuses the existing cache-plus-detached-refresh pattern instead. Reports, never pulls. One line, and silent when nothing is behind. |
| `tools/check_exits.py` (v1.35.0+) | **Which other projects ended dirty, and how long ago.** Uncommitted work at session end was already detected correctly — the warning just went to a session that was *ending*, and then to the next session start *in that same project*, which may never come. This reads the records back across every project: pure reporting over `~/.claude/reentry-state/`, no git, no network. On its first live run it found a repo four files dirty and ten days stale that nobody had been back to. |
| `tools/run_tests.py` (v1.35.0+) | **One command for the whole test suite.** There was no runner: running the tests meant invoking each script by hand, so nothing made a regression in an untouched file visible. Discovers `tools/test_*.py`, runs each in a subprocess, quiet on pass and full output on fail, and tolerates a test file that will not even import rather than dying with it. **Since v1.38.0 a TIMEOUT is its own state, never folded into `FAILED`** — a loaded machine once reported two tests failed that pass in 2s and 3s, which is *"I could not get an answer"* printed as *"I got an answer and it was bad"*. `--timeout=SECONDS` and a total wall-clock line, so a suite getting slower is visible before it is a problem. |
| `hooks/push_check.py` (v1.42.0+) | **Did the push-stop actually hold?** v1.40.0 made an unattended wrap commit locally and stop before the push — a good rule that nothing could check: the agent decided not to push, reported that it had not pushed, and no mechanism disagreed. This measures it instead, from the ref the repo already has. Four outcomes, never conflated: `HELD`, `ALERT` (commits were made this wrap yet nothing is ahead of `origin` — something pushed them unasked), `NOTHING_TO_HOLD` (this wrap committed nothing, which is routine and not an alarm), and `CANNOT_CHECK` with a reason for every way it could not run. That third outcome came out of review: treating `ahead == 0` as an alert on its own would have fired on every wrap of a read-only session, which is how an alarm gets read as normal and skipped. Offline, never raises, never gates a wrap. |
| `hooks/wrap_receipt.py` — the **CAIRN receipt** (v1.44.0+) | **The wrap verdict is now a quotation, not a sentence.** A verdict was prose composed by the party that would have had to do the work, from inputs it can read without doing any of it — so a diligent impersonation was indistinguishable from a real wrap, and happened twice on 2026-09-06, confidently, from real evidence. This measures each wrap step against a hash of `NEXT.md`/`CHANGELOG.md`/`BACKLOG.md`/`INBOX.md` taken at **session start** — and, since v1.52.0, against git's own record of what *this session* did, because those are not the same question. A `git pull` moves every hash and moves `HEAD`, so three of the six required steps used to read `ran` before any work happened, on exactly the multi-machine sessions the receipt exists for — and the pull is the first thing this plugin's own divergence banner tells you to do. A step now ticks only when the content moved **and** the HEAD reflog says this working tree moved it, so a `pull --ff-only` is named in the receipt instead of being mistaken for a wrap. **Since v1.55.0 that session-start snapshot is written once and never moved** — it used to be re-stamped on every run of the SessionStart hook, so a client re-firing that hook (or anyone invoking it to see its output) silently replaced "session start" with "a moment ago", and the session's genuine rewrite then read `byte-identical to session start`: the same mechanism failing in the opposite direction, and the more dangerous one, because it speaks in the language of a session that skipped its steps. The receipt also now prints when the baseline was taken, the one signal that diagnoses this in a line. It prints one line: `CAIRN SET · <receipt id>`, `CAIRN NOT DUE`, or `CAIRN OPEN` with the steps that are missing. **All three verdicts come from the tool** — *"no wrap needed"* was the exact sentence that started this, so owning only the affirmative would have moved the problem one door down. The id matters: a coined word alone is documented in the skill file the agent reads *before* wrapping, so it can simply be copied; a receipt id cannot be fabricated past `--verify`. Four states per step, never fewer — `ran`, `skipped`, `n/a`, and `unverifiable` for the four steps that genuinely leave no residue (surveying the tree, the memory pass, the session rename, the close), which the receipt states rather than quietly ticking. The **next session** verifies the last receipt at `SessionStart`, because a receipt only he could check is one nobody checks. Silent in any project that has never recorded one. |
| `tools/validate_next.py` (v1.36.0+) | **Does every item actually say whether you can walk away from it?** A previous sweep fixed every *wrong* attendance/mode in the portfolio and never looked for a *missing* one, so an item with no field at all passed clean. That field answers the one question the queue exists to answer, so a missing one is that question silently unanswered. Checks model, effort and attendance/mode on every Queue item and watch, `added` on every watch, `check after` last, and rejects the two contradictions (`AFK/Plan`, `HITL/Bypass`). Reports, never rewrites. Found a real one on its first run. |
| `tools/check_credentials.py` (v1.36.0+) | **Which credentials does this machine hold that `CREDENTIALS.md` has never heard of?** The file is only ever updated by someone who happens to think of it, so a credential that *works* stays invisible to it forever — and a leak is exactly when you need it complete. Lists credential **target names** the machine holds and reports the gap. **Names only, never a value**, and it never writes rows: expiry and token type cannot be read from a target name, and an invented field is worse than a missing one. |
| `MACHINES.md` (v1.36.0+) | A global, plugin-created table at `~/.claude/MACHINES.md` mapping hostname to the short id your `NEXT.md` annotations use (`LAPTOP1`, `LAPTOP2`, …), so a queue item marked *"run on LAPTOP2"* is **checked** rather than trusted to be read. Created empty; an empty or partial table means those annotations are simply never checked, which is the safe failure. The warning fires only on a positive mismatch between two **known** ids — never on an unrecognised host, because a check that fires wrongly on every session is worse than one that stays quiet. |
| `hooks/settings_drift.py` + `tools/check_settings.py` (v1.40.0+) | **Is a setting that must hold on EVERY machine wrong on this one?** `cleanupPeriodDays` was unset, so the 30-day default was silently pruning the session transcripts `timesheet.py` reads — and the fix was machine-local with nothing to carry it to the others. Reads `~/.claude/settings.json` **read-only** and reports drift in one line at session start. **Report-only by design:** a plugin writing a user's global settings is a large blast radius for a small win, and not knowing was the actual harm. The line says `on THIS machine`, names the file it read, and ends *"no other machine is checked by this line"* — asserting anything about the others would reproduce the very defect it fixes. Fires only in projects with a `NEXT.md`, so a non-opted-in project stays bit-for-bit silent. |
| `tools/measure_usage.py` (v1.53.0+) | **What a session actually cost, read from the transcripts rather than remembered.** `docs/running-a-batch.md` carried a token budget measured once by hand and then quoted as fact -- the exact bare constant the rules file forbids -- and a batch planned against it ran out of its 5-hour window mid-flight, killing two agents. It was wrong in *shape*: it counted lane agents and treated the orchestrator as one of them, when the orchestrator was ~60% of the spend and is paid per **turn**, because cache writes are ~79% of billed tokens and every turn re-establishes a growing context. This reads the `usage` blocks Claude Code already writes, so it is **retroactive with no new instrumentation**, and `--window` gives live headroom in both agents *and* turns. Scans every project, since the limit is per account. Reads `usage`, `timestamp`, `isSidechain` and `model` and **nothing else on the line** -- transcripts are the most sensitive thing this tooling can reach, so that is a boundary, not a shortcut. Reports `side%` as *not measurable* rather than 0, because subagent transcripts are truncated when the agent finishes. |
| `docs/running-a-batch.md` (v1.38.1+) | **How to clear a lot of backlog in one day without a stampede.** Say *"run a lane batch"*; the doc is the method. Partition concurrent agents by **file ownership**, not by item count — one agent per lane, disjoint owned files, and every shared file (changelog, backlog, version, queue) written by the orchestrator between waves. Carries the measured budget (~150k tokens per lane, 8–10 lanes per 5-hour window), the review-dossier shape, and the two ways it went wrong in practice. Written after an attempt that spawned 179 agents, burned two 5-hour windows and completed nothing. |
| `MISTAKES.md` (v1.14.0+) | A global, plugin-installed log at `~/.claude/MISTAKES.md`, auto-created on install. `/cairn:wrap` appends one entry per mistake caught that session — yours, the agent's, or the cairn system's own — so recurring ones become visible across every project instead of being re-corrected each time. Plain append-only log; no categorisation or review mechanism yet. Since v1.33.0, `rules/CLAUDE.md` names it directly, so an agent that never runs `/wrap` still knows it exists — before that, the only way to learn of it was the one-line creation message on a fresh machine, or the skill itself. See `docs/file-formats.md`. |
| `CREDENTIALS.md` (v1.33.0+) | A global, plugin-installed inventory at `~/.claude/CREDENTIALS.md`, auto-created the same way as `MISTAKES.md`. Tracks which secret (a PAT, an SSH key) lives on which machine, how it's stored, and when it expires — names and locations only, never a value — so a rotation is a checklist instead of a memory test. Built after a shared PAT leaked into a chat transcript and its full blast radius was unknown because nothing tracked where it was used. See `docs/file-formats.md`. |
| `tools/check_leak_coverage.py` + `~/.claude/reentry-private-names.txt` (v1.49.0+) | **Would the disclosure check actually catch your private names?** `test_payload_clean.py` ships three *generic* patterns that name nobody — health terms, a home-directory path, an email address. Anything specific to you lives in `~/.claude/reentry-private-names.txt`, outside every repo and never committed, so the checker cannot itself become the disclosure (it excludes itself from its own scan, so nothing else would have caught that). This tool derives candidate names from the machine — sibling repo directories, **the private config store's own path and git remote (v1.54.0+)**, `MACHINES.md`, the hostname, `git config` identity, remote hostnames — and reports which of them the patterns would miss: **LEAK** if it is already in a shipped file, **UNCOVERED** if nothing would stop it. The store is included because it is *required* to live outside your projects, so it is a sibling of nothing and its repo name — the one `~/.claude-private/<your-repo>/profile.md` invites you to make concrete — was structurally unreportable before then. Names the plugin publishes about *itself* (its own name, its marketplace owner) are read from its manifests and subtracted, and the subtraction is printed rather than applied silently: without that, the plugin's own name is derived from the store path and reported as a live leak in a couple of hundred payload lines on the first run after install. `ok: <name>` in the same file records one you have judged harmless, so only genuinely new names are ever reported. `REENTRY_PRIVATE_NAMES` shares one list across machines and refuses a path inside the current project, same as the profile source. |

## What this plugin does to your machine

Read this before you install. Everything here is deliberate, and none of it is hidden behind a
prompt at the time it happens.

| What | When, and what it means |
|---|---|
| **Writes `~/.claude/CLAUDE.md`** | The plugin installs its rules into a marked block in your global, **always-loaded** instruction file — the text every Claude Code session on this machine reads before you type. It rewrites that block on every version change, **including an unattended marketplace auto-update you did not trigger**. Only the text between the markers is touched, anything you wrote outside them is left alone, and a backup is written first. **This is the largest thing you are trusting.** |
| **Writes `~/.claude/reentry-profile.md`** | Created once from a commented template, then never overwritten without a backup. An `@` import to it is added to the managed block, so it is read into every session. If you set `REENTRY_PROFILE_SOURCE`, the file is refreshed from that path whenever the source is newer — one direction only. A source that is a relative path, or that resolves inside the project you are currently in, is refused — so point it at a repo that is not itself one of your projects. |
| **Creates `~/.claude/MISTAKES.md`, `CREDENTIALS.md`, `MACHINES.md`** | Created empty, once. Nothing is ever written into them unless you ask for it. |
| **Reads sibling repositories** | Opening a project that is opted in makes the plugin check the git state of up to 25 sibling directories — so it can tell you a *different* project is behind its remote. It only looks at directories that have both a `.git` **and their own `NEXT.md`**: that gate is the boundary, and a repo has to have joined this system to be touched at all. Running `git` in a repository consults **that repository's** config (`core.pager`, `core.fsmonitor`, `core.sshCommand`, aliases), which is worth knowing before you clone something you don't trust next door. It reads and reports; it never pulls, fetches or writes. |
| **Makes one outbound network call** | The first session after you opt a project in shells out to your issue host through `gh` or `glab`, in a **background process that prints nothing**, to cache the issue list. Only in projects that have a `NEXT.md`, and only if you have one of those CLIs installed and authenticated. Nothing is uploaded; it reads. |
| **`tools/measure_context.py` executes the project it measures** | This tool reports how many tokens a project's session start costs. Getting a real number means **running** that project's `SessionStart` hooks and starting its MCP servers — that is what the measurement *is*. It is an on-demand tool, never a hook. **Do not point it at a repository you would not open.** |
| **`tools/timesheet_sync.py` copies transcripts to a folder you name** | On-demand, one shot, never scheduled. It copies this machine's `~/.claude/projects` into a destination directory you pass it, so another machine can read them, and **it never deletes from that destination**. Whatever your session transcripts contain ends up there permanently. |

Everything else — the queue, the watches, the backlog, the wrap — stays inside the project you are
working in, and the checks report rather than act. If a project has no `NEXT.md`, the plugin is
bit-for-bit silent in it.

## Install

```
/plugin marketplace add superbole/cairn
/plugin install cairn@superbole
```

Then `/reload-plugins` if the install summary asks for it.

Install it on **every machine you work from**. That is the whole point — one versioned source of
truth instead of a copy per machine that quietly drifts.

## Updating — restarting is NOT enough

Quitting and reopening Claude Code does not pick up a new version. The install is **pinned to a
version and a commit SHA** in `~/.claude/plugins/installed_plugins.json`, and startup loads that
pinned `installPath` without ever contacting GitHub. A restart re-reads the *old* files,
faithfully, forever.

```bash
claude plugin marketplace update superbole    # 1. fetch the marketplace clone
claude plugin update cairn@superbole        # 2. repin to the new version
                                            # 3. THEN restart Claude Code
```

Verify rather than assume — this exact confusion cost a session on 2026-08-22, where "restart to
pick it up" was given as advice, followed twice, and did nothing:

```bash
python -c "import json,pathlib;d=json.loads((pathlib.Path.home()/'.claude/plugins/installed_plugins.json').read_text());print(d['plugins']['cairn@superbole'][0]['version'])"
```

Contributing a change? The maintainer half of this — pushing the source and bumping the version —
is in [the guide](docs/guide.md#shipping-a-change-maintainers).

## Prerequisites

**Both `gh` (GitHub) and `glab` (GitLab) are OPTIONAL.** Nothing above needs either one — the
hooks, `/cairn:next`, `/cairn:wrap`, and `BACKLOG.md` all work with neither CLI installed.
Without one, you keep the whole local system and lose exactly this: **phone access, surviving a
lost machine, and other people's writes** — the three things only a hosted issue tracker adds.
`BACKLOG.md` is the backlog either way; the CLI only lets it sync to GitHub or GitLab Issues.

That is a deliberate inversion (v1.18.0) — the backlog used to *be* Issues, so a project with no
GitHub remote had nowhere for a sixth item to go. Framing either CLI as required here would
undo the reason that changed.

Install the one your project's `origin` remote actually needs — [`gh`](https://cli.github.com/)
for GitHub, [`glab`](https://gitlab.com/gitlab-org/cli#installation) for GitLab, including a
self-hosted instance — then authenticate it against **that specific host**
(`gh auth login --hostname <host> --web` / `glab auth login --hostname <host> --web`). Naming
the host matters: a CLI logged into `gitlab.com` while your remote is a self-hosted instance
reads as authenticated to *something*, not to the host that matters, and the two are not
interchangeable.

`python plugins/cairn/tools/check_install.py` (v1.39.0+), run from inside any project, reports
which host your `origin` implies, whether that host's CLI is reachable — **on PATH**, or found
in a known install location but off it, which needs a different fix than reinstalling — and
whether it is authenticated to that host specifically, with the one command that fixes whichever
is wrong. On-demand only: a missing optional CLI is not news every session, so this never runs
from a hook — check it yourself, or let `/cairn:wrap` surface it when a human is watching.

## Opting a project in

Create a `NEXT.md`. That's the entire opt-in. A project without one gets **total silence** from
the hook, which is why the plugin is safe to have installed everywhere.

**If you track a portfolio, membership *is* having a `NEXT.md`** (v1.31.0). Every tracked repo owns
its own; nothing is tracked from a hub on another project's behalf. Otherwise silence is ambiguous —
*not in the system* or *tracked somewhere you have to remember* — and you find out which by opening
a project and getting a correct, useless answer. An almost-empty `NEXT.md` costs nothing to carry.

```markdown
# NEXT — <project>

## Queue

1. **Short title** — Opus 5 · high · HITL/Plan
   Brief: [briefs/some-slug.md](briefs/some-slug.md)
   One sentence on what this is.

## Decisions

**D1. Short title** — answer: `ask <authority>` · added `2026-08-09` → `docs/pending.md`

## Watching

**W1. Short title** — `Opus 5` · effort `high` · `AFK/Auto` · added `2026-08-15` · check after `2026-08-18`
One or two lines on what to check and why.
```

`## Decisions` is optional — add it only once a project actually has a decision only you can make.

Full spec for `## Queue`, `## Decisions` and `## Watching` — including the `AFK/HITL`
attendance field and permission modes, `INBOX.md`, `BACKLOG.md` and its GitHub/GitLab
Issues sync, `CHANGELOG.md`, the rationale record, and the one line of direction — lives in
[docs/file-formats.md](docs/file-formats.md).

For the reasoning behind the hooks and checks in the table above — why they're shaped the
way they are, the design rules the project holds itself to, and why relaying the queue
matters as much as printing it — see [docs/design-notes.md](docs/design-notes.md).

## Licence

MIT.
