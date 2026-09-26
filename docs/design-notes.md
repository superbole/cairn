# Design notes

Why the hooks and checks in `README.md`'s "What you get" table are shaped the way they
are, the design rules the project holds itself to, and the layer of always-loaded rules
and companion patterns that sit on top of the mechanism.

### The exit-side check, and why it is shaped the way it is

Two things go missing between sessions and neither announces itself: **uncommitted changes**, and
**commits made without a wrap** — a clean tree looks exactly like a finished session, so the
wrap-only steps (the queue, the briefs, memory) get skipped in silence. Nothing else detects the
second one at all.

The obvious build — warn at the end — does not work, twice over:

- `Stop` is not "session end". It fires **once per turn**, so a warning there is repeated after
  every response and becomes wallpaper. So it is deduplicated: it speaks when a **new** dirty path
  appears or the unwrapped count rises, and stays quiet otherwise. Committing half your files does
  not re-trigger it.
- `SessionEnd` fires once, but has **no `systemMessage`** and its output is largely ignored — it
  cannot say anything a human will see. So it writes a breadcrumb instead.

The intervention therefore lives at the **start** of the next session, in the orientation you
already read, which opens with what the last session left and offers to fix it first.

Two markers, both deliberate: `<project>/.claude/.last_wrap` (gitignored) records the wrapped
commit and is what **opts a project in** — no marker, total silence — while the per-turn state and
the exit breadcrumb live under your Claude config dir, never in the repo, so the checker can never
end up warning about its own state file.

**What `.last_wrap` cannot do, and what was added beside it (v1.44.0).** It records that *a* wrap
happened at *some* commit. It cannot distinguish "wrapped now" from "wrapped two sessions ago and
nothing has moved since" — a session that changes nothing inherits the previous wrap's marker and
reads as freshly wrapped. See the receipt below; the marker keeps its opt-in job unchanged.

### The verdict is a quotation, not a sentence (v1.44.0)

The exit-side check above answers *did anything get left behind*. It does not answer *did the wrap
procedure run* — and until v1.44.0 nothing did. The verdict was prose, composed by the party that
would have had to do the work, from inputs it could read without doing any of it. A diligent
impersonation was therefore indistinguishable from a real wrap, and produced one twice in a day.

**The shape of the fix is the interesting part, and it generalises.** The failure was not that a
rule was missing — two were present, in bold, in the always-loaded rules file, and both were
followed. The failure is that *"wrapped"* is a word an honest agent produces from ambient evidence.
So the fix is not a third rule. It is to make the verdict a **token no amount of speaking English
can produce**, emitted by a tool that measured the steps: `CAIRN SET · <id>` / `CAIRN NOT DUE` /
`CAIRN OPEN` / `CAIRN UNKNOWN`.

Four things it took to make that hold:

- **All four verdicts, or none.** The exact sentence produced was *"no wrap needed"*. A tool that
  can only emit the affirmative moves the impersonation one door down rather than closing it.
- **"Measured absent" and "could not be measured" are two verdicts, not one.** They were one
  (`OPEN`) until B2, and the cost was a wrap that had done everything reporting the same token as
  a wrap that had skipped the changelog. A warning that fires when nothing is wrong is how a
  reader learns to discount the one that fires when something is — so `OPEN` is now measured
  absence only, and `UNKNOWN` is blindness. `skipped` is tested first **once a baseline exists**,
  so a wrap that is both still reads `OPEN`. With no usable baseline the verdict is `UNKNOWN`
  outright (B10): "owed" cannot be measured.
- **A per-run id, not just a coined word.** The word has to be documented in the skill file the
  agent reads *before* wrapping, so a fixed string is copyable by exactly the party being guarded
  against. The id is a hash of the receipt and fails `--verify` if invented. That raises a false
  claim from *a sentence anyone would write* to *an identifier one command contradicts* — a large
  jump, and not proof. Nothing in the system describes it as proof.
- **A baseline taken at session start.** `NEXT.md` changing proves nothing; any session can edit
  it. Only a change against the content hash as it stood at `SessionStart` is evidence of a
  rewrite, so the orientation hook stamps one.

**And a four-state result per step, never fewer:** `ran`, `skipped`, `n/a` (conditional and
legitimately absent), `unverifiable` (no residue exists). The last is never rendered as a tick —
four steps are permanently in it. A receipt that quietly ticks what it cannot see would be the same
defect one level down from the one it exists to catch.

**The caller declares an intended push.** The receipt composes the existing push check, whose
`ALERT` means *something pushed this without being asked*. After an ordinary wrap that pushed on
purpose, HEAD has moved and `ahead` is 0 — that alert's exact shape. Whether a push was *intended*
is not visible in git, only to the caller, so the wrap passes `--held` on the stop path and the
default asserts nothing. Caught in the receipt's own first live run, one commit after it shipped.

### Work you sent into other repos (v1.24.0)

Everything above watches **one** repo — the one the session is running in. A session that fans work
out, subagents each writing into a different project, is invisible to all of it: the parent tree
can be spotless while every target is dirty.

That is not hypothetical. On 2026-08-25 a fan-out across 8 repos was logged in this repo's
changelog as finished; a day later all 8 trees were still uncommitted. Nothing had asked them.
*"Recommendation accepted"* had been written down as if it meant *"change committed."*

```bash
python "$CLAUDE_PLUGIN_ROOT/tools/check_repos.py"
```

One line per repo — uncommitted count, unpushed count, and the paths — with a nonzero exit if
anything has not landed.

**Since v1.25.0 it takes no arguments**, because it no longer has to be told where the work went. A
`PostToolUse` hook resolves every written file to its git toplevel and logs the ones outside the
project, so the wrap reads a record rather than the agent's recollection. That matters because the
two failure modes look nothing alike: a forgotten check produces no output, while a list that is
missing one repo produces a confident *"8 repos checked — all clean"* that is true of everything it
was told about and silent about the one it wasn't.

The recorder watches `Edit`, `Write` and `NotebookEdit` — the tools whose input carries a
structured file path — and deliberately not `Bash`, where a command line is not a path and
extracting one would be guesswork. Cost is not the reason (~1.3 s/session for the file-writing
tools, ~3 s if `Bash` were matched; both negligible). **So say plainly what it misses: it would not
have caught 2026-08-25**, which wrote through `Bash`. It catches the ordinary shape of that failure
— a subagent editing a sibling repo — and named paths still work, as an *addition* to the record:

```bash
python "$CLAUDE_PLUGIN_ROOT/tools/check_repos.py" ~/Projects/lighthouse
```

A repo the recorder found that you did **not** name is called out in the header; that is the eighth
repo, and it must not blend into the list. `--known` adds every project the plugin has recorded a
session *ending* in, for when you are still unsure. `--no-recorded` ignores the record entirely.

The window is **since the last wrap**, not "this session" — a previous session that wrote next door
and ended without wrapping is exactly the case worth catching. The log lives in the state dir
outside the repo (a recorder that dirtied the tree would set off the dirty-tree warner), and it is
append-only JSONL because two sessions in one project share that directory.

Two things make the check work rather than just exist. It runs at **wrap step 1a, before the
changelog entry**, not next to the push — by the push the false claim is already written, and the
check exists to constrain what the entry is allowed to say. And step 1a is asked **every** wrap; a
single-repo session answers in one line and moves on. It reports and never fails: a wrap that dies
over a check leaves no queue behind, which is worse than any dirty repo.

Watch for an `[ok]` with a note under it — *"not a repo root"* means the path you named answered
for its parent, so clean proves nothing about the thing you meant.

### The item you started and never closed (v1.20.0)

`.last_wrap` records that a session *wrapped*. Until v1.20.0 nothing recorded that a session
*started an item*, so the system's own worst failure was invisible: start item 3, do half the work,
end without a wrap, and `NEXT.md` still shows item 3 queued — byte-identical to an item nobody has
touched. The half-done work survives only in a transcript you will not re-read.

So `do 3` now leaves a marker, written by a `UserPromptSubmit` hook rather than by the agent: the
sessions that produce a half-done item are exactly the ones that went off-script, so an instruction
the agent has to remember cannot be the mechanism. The next session's orientation folds it into the
same "did not finish cleanly" box, naming the item and when it was opened.

**Everything about it errs toward silence**, because that box also carries uncommitted files and a
warning you learn to skip is worse than none:

- it only ever speaks about a *previous* session — changing your mind mid-session just overwrites it;
- it clears itself three ways, all passive: a wrap, the item leaving `## Queue` by any route, or a
  later item start. Nothing to remember, nothing to run;
- an item whose title you reworded reads as **closed**, never as open;
- it speaks once in full, then degrades to a single line for as long as it is real;
- the prompt regex is anchored at both ends and re-checked against the queue, so `do 3 of those`
  and a bare `3` are ignored. Missing a real start costs nothing; inventing one costs trust.

### Timesheets (v1.21.0)

```bash
python plugins/cairn/tools/timesheet.py --sessions
```

`CHANGELOG.md` is the wrong source for this and looks like the right one: its entries are keyed to
plugin **versions**, not sessions, so several land on the same date with nothing separating them in
time, and a session that ships no version bump leaves no entry at all. Git commit times miss
everything before the first commit and after the last.

Session transcripts already carry a per-message timestamp, the `cwd`, and the session title. So the
timesheet is a read, not a new capture — there is nothing to start, stop, or remember.

**Parallel work is real work** (v1.22.0). Two sessions live at once produce two minutes per minute
of wall clock — and that is the right answer for per-project effort, not an error to correct.
Which model applies is your billing policy, so the tool reports both and never picks:
`--attribution parallel` (the default) gives every session its time in full; `--attribution
exclusive` hands an overlapping stretch to whichever project you touched most recently, so a day
can never exceed elapsed time. **The overlap prints either way** — it is the one number that must
not be hidden, because it is what two clients sharing an hour would look like.

Time is classified by what ends a gap. A gap ending in **your** message was you being waited for,
and is capped by `--idle` (default 10 min) — longer is a break and counts as nothing. A gap ending
in **agent output** was the machine working, and counts in full up to `--max-run` (default 5 min,
set from a measurement of 67,738 real gaps: p99 is 246s, and past ~15 min it is a resumed session
rather than a run). A long AFK task is unaffected, because it is built of thousands of short gaps.

`attended` and `unattended` are separate **columns, never a deduction** — machine-busy time stays
in the total, labelled, so you decide per invoice.

`--last-week`, `--days N`, `--since/--until`, `--project NAME`, `--sessions`, `--csv`, and
`--projects PATH` (repeatable) to fold in another machine's transcript directory — a mount or a
synced copy, deduped by session id. Cursor writes no *Claude Code* transcript, so those machines
are out of scope — it does write its own, at
`~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl`, in a schema this reader cannot
parse (no `type`, no structured `timestamp`, no `cwd`). Running `timesheet.py` from Cursor reports
the *Claude* sessions on that laptop, which is silently wrong if you read it as the week's work.

## Design rules worth keeping

- **Never fail a session.** Any hook error prints nothing and exits 0. An orientation aid that can
  block a session start is worse than none.
- **Stay short.** A wall of text at session start is the same failure as a huge backlog, just
  earlier.
- **Print nothing when there's nothing to say.** Silence is a valid state.
- **A check reports; it never acts on your work.** The hook warns when a checkout has diverged from
  `origin`; it never pulls. An automatic pull mutates the repo before you've said what you want, and
  can rebase over uncommitted work at the moment you're least likely to be watching.
  **This is a rule about the checks, and stating that scope makes it stronger, not weaker.** The
  plugin's own installed footprint is the deliberate exception — the managed block in
  `~/.claude/CLAUDE.md` and the files created beside it are written on install and on every update
  without asking, because a `SessionStart` hook has no way to prompt. That is disclosed in full in
  [guide.md](guide.md#what-this-plugin-does-to-your-machine) rather than being papered over here; an
  undocumented deliberate choice is indistinguishable from an oversight.
- **Where a claim can be measured, measure it — and never let one value cover two opposite
  states.** A gate that cannot tell "nothing to report" from "could not run" is the defect it was
  built to catch. Every check here carries explicit reasons for *could not run*, and the wrap
  receipt's `unverifiable` exists for the same reason.
- **Attribute a change to the actor, not to the clock.** A diff against a session-start snapshot
  measures *the world*, not *the session* — and the difference is a `git pull`, which this plugin's
  own divergence banner tells you to run first. Where the question is "did this session do X",
  prefer a record git writes as a side effect of the act (the HEAD reflog) over a hash, an mtime or
  a HEAD comparison. A trailer or a marker the agent must remember to write is *asserted*; a reflog
  entry is *present or absent*. B122: three of the wrap receipt's six required steps read `ran`
  after a bare pull, and the two candidates the item itself proposed both relied on someone
  remembering to call something.
- **A mechanism that has never run in a project stays silent about not having run.** The receipt
  check, the archive-offer check and the wrap marker are all gated on the project having used them
  at least once. Otherwise every repo is told, forever, about a mechanism it never adopted.
- **Defer to a project's own copy.** A repo carrying its own `.claude/hooks/session_orientation.py`
  works on machines with no plugin installed; the plugin stands down there rather than printing
  twice.

## Relaying matters as much as printing

The hook's output goes into the **agent's** context, not onto your screen. It orients the agent.
Relaying it is what orients *you* — and you're the one who can't remember where you were. Any
`CLAUDE.md` using this plugin should carry a rule to relay the queue **as a numbered list, never as
prose.**

**How much to relay, and when, is not the agent's judgement call.** Since v1.13.0 the hook computes
a tier from what is actually in the file and prints it as an explicit instruction:

| Tier | Fires when | The agent |
|---|---|---|
| `RELAY FIRST` | a due watch, an un-triaged inbox, the divergence banner, or an unfinished last session | leads with the orientation, whatever you asked |
| `ANSWER FIRST, THEN RELAY` | queue items or decisions, nothing time-sensitive | answers you, then a `---` rule, then the list |
| `ANSWER FIRST, THEN ONE LINE` | the Queue is empty and the backlog is not (v1.17.0+) | answers you, then offers in one line to pull the top few in |
| `STAY QUIET` | nothing live at all | just answers you |

The tempting alternative — have the agent read your opening prompt and decide — is deliberately not
done. An agent holding a concrete task rates the task above the queue every time, and a session that
opens with a specific question is often one where you have lost the thread on another machine. The
agent may move the queue below the answer; it may never drop it.

## The rules layer — why the plugin writes `~/.claude/CLAUDE.md`

A hook and two skills are a *mechanism*. The behaviour that makes the mechanism work — relay the
queue as a list, give the wrap verdict, never leave a future trigger in chat, never pull unasked —
lived in `~/.claude/CLAUDE.md`, which is **untracked, in no repo, and ships nowhere**. So
`claude plugin install` on a second machine delivered the mechanism and none of the behaviour, and
rules had to be rescued into the hook one at a time, each after a failure.

**A plugin cannot contribute always-loaded context.** Checked against the shipped binary rather
than the docs (2026-08-22): `plugin.json` has no instructions/memory/rules field, and instruction
files are discovered only from `~/.claude/CLAUDE.md`, a project's `CLAUDE.md` / `CLAUDE.local.md` /
`.claude/CLAUDE.md` / `.claude/rules/*.md`, and org-managed memory. There is no plugin path into
any of them.

So the plugin ships `rules/CLAUDE.md` as the tracked source and installs it into
`~/.claude/CLAUDE.md` between `reentry:begin` / `reentry:end` markers:

- **Only the marked block is ever touched.** Anything you write outside the markers is yours and
  survives every update. A pre-existing file gets the block prepended and its contents kept below.
- **Idempotent.** Same version already installed → nothing written, nothing printed.
- **Found structurally, or not at all** (v1.62.0, D32). The header is one whole line,
  `<!-- reentry:begin v<version> -->`, and the end marker is a whole line too, so a note that
  quotes the marker is never mistaken for the block. A header-like line with no real block, two
  real headers, or a header with no end marker → nothing is written, and each session says so
  until you fix the file.
- **Backed up** before every modification, to `CLAUDE.md.bak-reentry-install-v<outgoing>-<digest>`:
  one file per distinct state it replaced, never pruned. (Up to v1.61.0 it was one rolling
  `CLAUDE.md.bak-reentry-install`, which is left in place.)
- **Never fails a session.** Every failure path returns quietly.
- The rules are not in the *current* session's context — `CLAUDE.md` is read before the hook runs
  — so the session that installs them says so and tells you to restart. Only that session pays for
  the four-line fallback block the hook prints; once the file is current, it prints nothing.

Cost, measured on `code/` with `tools/measure_context.py`: 4,895 → 5,003 tokens per session
(**+108**), for markers plus a header saying which file is the source. The hook itself got
*smaller* (926 → 876), because the wrap-verdict directive moved out of it and into the file.

**Edit `plugins/cairn/rules/CLAUDE.md`, never `~/.claude/CLAUDE.md`** — an edit inside the
markers is overwritten on the next version bump, silently.

### The profile layer — why the rules ship the mechanism and read the person (v1.45.0)

The block above installs into **everyone's** always-loaded context. Until v1.45.0 the text it
installed opened by naming one person and their medical history, then their machines, their
projects and their employer's git host — so sharing the plugin meant installing all of that into a
stranger's global config, along with rules calibrated to somebody else's memory (B12).

The split is **three** ways, not two, and the third is the one that is easy to miss:

| | Ships | Why |
|---|---|---|
| **MECHANISM** | yes | the three lists, the verdict, attendance/mode, the relay tiers — the reason the plugin is worth sharing at all |
| **IDENTITY** | no | who the user is, their machines, their issue host |
| **PREFERENCE** | no | *how* they like work done — report length, delegation style, whether a side quest is chased or recorded |

**The test is not "does it name a person":** *would this rule still be correct for a user with a
different working style but the same tooling?* Yes → mechanism, however personally phrased. No →
preference, however impersonally phrased. A rule can be written in perfectly neutral prose and
still encode one person's priorities, which is exactly what the second half catches.

Identity and preference live in `~/.claude/reentry-profile.md`, seeded once from a commented
template by `hooks/ensure_profile_file.py` and reached through an `@~/.claude/reentry-profile.md`
import that `install_rules._block()` appends to the managed block. **The import is appended by the
installer, not left to the rules text** — a rules file that ships without it silently loses the
profile, and that failure looks identical to a correct install.

**Ordering is load-bearing, for the same reason as the wrap marker's position.** `~/.claude/CLAUDE.md`
is parsed at launch; hooks run after. So `ensure()` is called from *inside* `install()`, before the
block is written — the import can never be written in a run where its target does not yet exist.

**Cross-machine is a shipped mechanism, not documentation.** `REENTRY_PROFILE_SOURCE` names a copy
in any repo or synced folder; unset, the template is seeded once and never touched again. Set, the
source is copied in whenever it is newer — one direction, backed up first, content compared before
any write. **An untouched template is replaced regardless of mtime**: install first and set the
pointer after (the order a first install actually takes) leaves a template newer than a source that
was edited days ago, and a pure mtime test would keep the template forever.

**A source is refused, not just read, if it could be set by the project itself (B103).** A
project's own `.claude/settings.json` `env` block reaches plugin hook environments (B100), and
`install_rules.install()` runs on every session start regardless of opt-in — so the trigger for a
hostile `REENTRY_PROFILE_SOURCE` is opening the directory, not adding a `NEXT.md`. Two refusals,
both in `ensure_profile_file.py`: a relative path (no legitimate use — the variable always names a
real, already-known location, and a relative one resolves against the hook's cwd, i.e. the
project), and an absolute path that still resolves inside the current project (`reentry_state.
toplevel()` plus a plain `relative_to` check, since a project need not be a git repo). A refusal
seeds the usual template if none exists yet rather than leaving the user with nothing, and reports
itself every session the misconfiguration stands — deliberately not idempotent-quiet the way a
successful copy is, because a security refusal firing repeatedly is the point, not a bug.

The plugin syncs nothing itself. What carries the source folder between machines — git, OneDrive,
Dropbox — is the user's choice and none of its business.

**`tools/test_payload_clean.py` is what keeps this true.** Every docstring in this plugin was
written in the personal register, so the next one will be too unless something says no; a rule on
the page is the intervention `decisions.md` D4 records failing. It scans every tracked file under
`plugins/cairn/` for names, machines, employer hosts, medical terms and private project names —
**twice**: once per line for an actionable line number, and once over the whole file with adjacent
string literals joined and whitespace collapsed. The second pass exists because
`session_orientation.py` emitted *"…have memory " "loss…"* split across two literals, which a
line-by-line grep cannot see and which survived the entire B12 pass.

## Companion patterns (deliberately outside the plugin's scope)

Two things the plugin doesn't do, on purpose, but that slot in cleanly on top of the same
`NEXT.md`/`INBOX.md`/`CHANGELOG.md` files — found solving these for a work portfolio (managed
laptops, a self-hosted git, Cursor in the mix) on 2026-08-20, distinct from this repo's own use.

**A tool whose session-start hook isn't wired yet (e.g. Cursor today).** The file format has no
hook dependency baked in — `NEXT.md`/`INBOX.md`/`CHANGELOG.md` are just markdown. Point that
tool's own mechanism (a skill, an always-on rule) at the same files instead of inventing a second
format; it kills the two-tool-two-truths problem outright, and unlike this plugin's hook and
skills, that mechanism is yours to edit freely.

**This paragraph used to say Cursor has no `SessionStart`-equivalent. That was wrong** — corrected
2026-09-04 from Cursor's own verification on a second laptop, written up separately. Cursor
documents `sessionStart`, `beforeSubmitPrompt`, `postToolUse`, `stop` and `sessionEnd`, plus events
Claude Code has no name for. What is genuinely unproven is whether `sessionStart`'s
`additional_context` ever reaches the model, so the reliable channels there are side-effect hooks
plus an always-on rule that runs `session_orientation.py` — not hook injection. Asserting an
absence without searching is the B20 failure; write **unverified**, not "none."

**Tracking many projects at once.** The plugin is deliberately single-repo — the hook only ever
orients you in the one project `CLAUDE_PROJECT_DIR` (or `cwd`) points at. A separate,
repo-external script that reads each project's `NEXT.md` (`## Queue` / `## Watching`) across a
catalog of projects gives you the cross-repo "which of my N projects needs attention" view the
plugin intentionally doesn't provide. Keep it outside the plugin — portfolio triage and
single-session orientation are different jobs with different failure modes (a stale portfolio
scan is a missed heads-up; a stale per-session orientation is what this whole plugin exists to
prevent).

