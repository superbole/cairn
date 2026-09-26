---
name: wrap
description: End a session cleanly — CHANGELOG entry, commit, push, memory update, and a rewritten NEXT.md so the next session re-enters from disk. Use when the user says to wrap up / end the session / "we're done here", and suggest it proactively when a phase completes or a deploy lands cleanly.
---

# /cairn:wrap — end the session so the next one can start

The exit half of this system. `/cairn:next` gets them back in; this is what makes that possible.
**A session that produces excellent work and no recoverable entry point has failed at the part
that matters most.**

The user cannot be relied on to hold state between sessions, and runs several projects at once. **The handoff lives in a FILE, not in this conversation.** Anything
the close says that is also on disk is noise; anything it says that is NOT on disk is a bug — with
two exceptions, both actions only they can take in the UI: continue-or-new-session (step 9) and the
archive prompt (step 10).

## Scope

Any project with a `NEXT.md`. **If the project carries its own wrap skill (as `atlas` does),
read it ALONGSIDE this one, never instead of it.** A local skill is a *delta*: it holds only what
this file cannot know, and it deliberately does not restate the procedure below. **This file owns
the wrap** — the running order, CHANGELOG mechanics, the rationale record, commit and push
discipline, the wrap marker, memory and `MISTAKES.md`, the `NEXT.md` three-list format,
`BACKLOG.md` and its sync, INBOX, session naming, the verdict, the close and the archive offer.

**A local skill keys off NAMED concerns, never off step numbers here.** A `→ step N` reference
breaks silently when this file renumbers and nothing checks it, so do not write one and do not
expect one.

## Why these read as blunt orders

Nearly every rule below exists because an agent reasoned its way past it. The incidents, dates,
measurements and quotes are in **`references/incidents.md`**, in this skill's directory. **Read it
only when a rule looks wrong or you are about to deviate from one** — it is the evidence, and a
working wrap never needs it.

## Procedure

**`<root>` in every command below is the plugin root: two directories above this skill's base
directory** (the `Base directory for this skill:` line). `$CLAUDE_PLUGIN_ROOT` is NOT set in your
shell, and bare `python` is missing on stock Linux — so always go through `hooks/run.sh`. (B59)

1. **Survey the tree.** `git status`. Separate THIS session's files from anything another session
   may have touched; never stage another session's work. Not a git repo → skip steps 4, 5 and 5b
   and say so at the close. The queue still gets written.

1a. **Did this session put work into any OTHER repo? Run this every time, before you write
   anything down.** Subagents writing into sibling projects, a fan-out, a fix applied next door —
   this repo's `git status` says nothing about any of them.

   ```bash
   sh "<root>/hooks/run.sh" tools/check_repos.py
   ```

   - **Run it with NO arguments first.** Since v1.25.0 a `PostToolUse` recorder logs every git
     tree the session actually wrote to, so the tool answers off a record instead of off your
     memory. **Then add any repo the record cannot have seen** — anything written through `Bash`,
     `gh`, or a tool that takes no file path — as extra arguments. Both sources are checked
     together; a repo the recorder found that you did NOT name is called out in the header, and it
     is the single most important line in the output.
   - **Name them even if you believe an agent already committed there.** *"Recommendation
     accepted"* is not *"change committed"*, and on 2026-08-25 that substitution put a
     finished-looking entry in this repo's CHANGELOG while all 8 target trees were still dirty
     (issue #1). `--known` adds every project the plugin has recorded a session ending in, for
     when you are still unsure you have the full list.
   - **The check gates step 2, not step 5.** A CHANGELOG entry must not say work landed in a repo
     the tool reports dirty or unpushed. Three honest options: commit it there now, say plainly in
     the entry that it is written but uncommitted, or leave it out.
   - **`[ok]` with a note under it is the dangerous line**, not the `[!!]` ones — *"not a repo root
     — reporting Projects"* means the path you named answered for its parent, so a clean result
     proves nothing about the thing you meant.
   - **Reports, never fails.** Nonzero exit is information; the wrap continues either way. *"No
     repos to check"* is a real answer and worth one line at the close — say it rather than
     skipping the step silently.

2. **`CHANGELOG.md` — the only place session narrative goes.** Append a dated entry at the TOP
   (newest-first), creating the file if absent:

   ```
   ## 2026-08-11 — <short title>

   What changed, what was found, what was deferred and why.
   ```

   - **Under ~20 lines.** The cap is on you, not on them.
   - **Never in `NEXT.md`** — that is a queue, not a history.
   - **Never describe work that has NOT happened.** If you catch yourself writing *"trivial enough
     to just do directly"* or *"should probably"*, stop: a CHANGELOG entry reads as closure, so
     nothing ever surfaces that work again. Three honest options — do it in this same turn and
     THEN log it, put it in `INBOX.md`, or leave it in the Queue and drop something else.

2a. **The rationale record — log any decision this session MADE.** `CHANGELOG.md` records what
   shipped; this records **why, and what was rejected**. Append to the project's record
   (`docs/decisions.md`, or whatever it already uses — `agent-reentry` keeps two, as
   `skills/*/references/incidents.md`). Create it only if the session actually produced a decision;
   an empty file is noise.

   - **One row per decision, and name the rejected option and what it cost.** The rejected
     alternative is the half a later session cannot reconstruct, and the half that stops the same
     argument being had again.
   - **Made, not proposed.** A question they have not answered is a `## Decisions` entry in `NEXT.md`
     (step 6). This file is where that entry goes once it is answered — the two are opposite ends of
     the same thing, and a proposal logged here reads as settled when it is not.
   - **No narrative, no status.** Not a second changelog. If the row is growing paragraphs of what
     happened, that belongs in step 2.
   - Not every session makes a decision. Most don't. Skip the step rather than padding it — a
     rationale record full of manufactured rows is one nobody reads when it matters.

3. **Write or update the briefs.** Every queue item links to a self-contained brief on disk
   (`briefs/<slug>.md`, or the project's own convention). *"do 1"* must find a complete prompt
   relying on nothing in this conversation — including the reasoning behind decisions already
   made, so a later session doesn't reopen them. **A `HITL` brief names the checkpoints** where
   the agent will stop for them — that is what makes the item's `HITL` tag actionable rather than a
   warning.

3a. **If the session changed how something BEHAVES, the doc that explains it is part of the
   change, not a follow-up.** Update it now, in the same commit — not as a queue item.

   - **Before any timestamp or version bump, never after.** Staleness tooling verifies **recency**,
     never **accuracy**, so a doc stamped today is invisible to it: bumping first actively hides
     what the check exists to catch.
   - **A fresh timestamp on stale content is worse than a stale timestamp** — a stale one is a
     signal, a fresh one destroys it.
   - A project with no timestamp convention still owes the update; the ordering rule simply has
     nothing to order.

4. **Commit.** Stage with **explicit pathspecs** (`git add path/to/file`), NEVER `git add .` —
   that sweeps in other sessions' half-done work. Conventional-commit subject
   (`fix(scope): …`, `docs(scope): …`).

   **Say which BRANCH this session was on.** If it is not the project's main branch, **ASK before
   merging — never merge unprompted.** The merge is their call, same as the behind-upstream case at
   step 5.

5. **Push, and report the count BEFORE and AFTER.**

   **First — if this session ran an `AFK` item, or any work they walked away from, the push STOPS
   HERE** (B22). Commit locally at step 4, then report: what changed file by file, the verification
   actually run **with its real output**, and anything decided on their behalf. **Then end the turn
   and wait** — a report followed by a push in the same breath is the same defect. **Step 8a's
   backlog sync waits with it**: it writes to the issue host, so it is outward-facing too.
   `AFK` is about ATTENDANCE, never about REVIEW — they read outputs and finds real problems in
   them, and pushing first puts that review *after* the outward-facing act. Everything local still
   gets written (CHANGELOG, briefs, `NEXT.md`, memory); 5b's marker does not, and **step 10 does
   not run** — archiving would end the session that still has to push. Record the receipt anyway
   (step 8c): it reads **`CAIRN OPEN`**, correctly, because the marker step has not run. Quote it,
   and add in the same breath that **the push is waiting on them.**

   **If it reads `CAIRN UNKNOWN` instead, quote that** — and say what it means, because the two
   are not interchangeable. `UNKNOWN` is what a session started outside the project it worked in
   gets, or a `--resume`/crash-restart whose SessionStart never stamped: no session-start baseline,
   so `next_rewrite` / `changelog` / `commit` are blind. It is not a claim that anything was
   skipped, and it is not a `SET` you may infer from memory.

   **Verify the stop held — B86, and do not skip this.** Deciding not to push and reporting that
   decision is exactly the thing B86 says cannot be trusted from inside the session. Run

   ```
   sh "<root>/hooks/run.sh" push_check.py --since <HEAD before this wrap committed>
   ```

   **Capture that baseline sha BEFORE step 4 commits** (`git rev-parse HEAD`) and pass it here.
   Without it the check cannot tell "I committed and something pushed it" from "I committed
   nothing", and it will say so rather than guess.

   Report its first-line status in the SAME BREATH as the stop verdict, never separately. Four
   outcomes, read literally, never eyeballed from a raw `git rev-list`:
   - **`HELD`** (ahead > 0) — the stop actually held. Say so alongside the token: *"CAIRN OPEN —
     the push is waiting on you, and I have confirmed nothing has gone out (HELD, N commit(s)
     ahead of origin/<branch>)."*
   - **`ALERT`** (HEAD moved this wrap, yet ahead == 0) — something pushed this session's work
     without being asked. Say so just as plainly and go look at the reflog before reporting
     anything else as fine.
   - **`NOTHING_TO_HOLD`** (ahead == 0 and HEAD never moved) — this wrap committed nothing, so
     there was never anything to hold back. Routine, not an alert, and **not** evidence of a push.
   - **`CANNOT_CHECK`** (no commits yet, detached HEAD, no remote, no `origin/<branch>` ref, or no
     `--since` baseline) — the check could not run, or could not interpret what it found.
     **This is not reassurance and must never be read as `HELD`** — say which reason it gave, same
     as you would say `ALERT`.

   ```
   git rev-list --left-right --count origin/<branch>...HEAD
   ```

   - Before the push it says what is about to move; **run it AGAIN afterwards and expect `0  0`**,
     which is what proves it moved. Two different checks; the second catches a rejected or partial
     push. Re-check `git status --porcelain` after too — tree state, which the count does not cover.
   - **Never force-push.** If the local branch is BEHIND (left number > 0), stop and hand the merge
     decision to them.
   - It is often more than this session's commit, and that is the number worth reading aloud — they
     works from more than one checkout, so unpushed work on one machine is invisible from the other.

5b. **Stamp the wrap marker — AFTER the push has succeeded.**

   ```bash
   git rev-parse HEAD > .claude/.last_wrap
   ```

   Create `.claude/` if needed, and make sure `.gitignore` contains `.claude/.last_wrap` — add
   that line **during step 4** so it ships with the commit; adding it now leaves the tree dirty,
   which is precisely what the exit-side hook then warns about.

   **A clean tree is indistinguishable from a finished session**, so "committed but never wrapped"
   is otherwise invisible — and the steps that get skipped are exactly the wrap-only ones
   (`NEXT.md`, briefs, doc timestamps, memory). `dirty_tree_warning.py` and the session orientation
   both read this marker.

   **This also closes the open-item marker** (v1.20.0) — `item_open.py` treats a `.last_wrap`
   newer than the marker as proof the item it named is no longer half-done, so there is nothing
   extra to run and nothing to remember. Rewriting `NEXT.md` at step 7 clears it a second way: an
   item whose title has left `## Queue` is closed by definition.

   **Position is load-bearing both ways.** After the push, so an aborted wrap never stamps one. And
   the marker is what OPTS THE PROJECT IN — no marker means the hooks stay silent about wrapping,
   so a project that has never wrapped is never nagged. **Do not stop committing mid-session to
   avoid a partial wrap;** mid-session commits are correct behaviour.

6. **Memory update.** Record anything durable learned this session — preferences, corrections,
   project state not derivable from the repo. Delete or fix memories this session proved wrong.

6a. **`MISTAKES.md` — log any mistake made this session, agent's or theirs.** Global file at
   `~/.claude/MISTAKES.md` (`CLAUDE_CONFIG_DIR` if set), not per-project — the point is spotting
   patterns across every project, so it is one file, not one per repo. The plugin creates it with
   a header on a fresh machine; never write the header yourself, just append.

   A mistake is: something the agent got wrong that needed correcting (**agent**), something
   the user did that turned out to be a misstep, logged the same way with no judgement — pattern
   data, not blame (**user**), or a case where the cairn system itself failed to prevent one
   (**process** — these overlap with `references/incidents.md` entries; log here too, so the
   cross-project pattern is visible without opening every skill's incidents file).

   Append at the TOP (newest-first), one entry per mistake, under ~3 lines:

   ```
   ## 2026-08-27 -- code -- agent

   Rewrote NEXT.md wholesale from a stale in-context copy instead of re-reading from disk first,
   dropping a watch another session had added minutes earlier.
   ```

   **If nothing went wrong this session, skip this step silently** — an empty session does not
   need a "no mistakes" entry. This is a log, not a review: don't categorise trends or propose
   fixes here, just record the fact plainly enough that a later pass over the file can.

7. **Rewrite `NEXT.md`. REQUIRED — this is the step the whole wrap exists for.**

   **RE-READ IT FROM DISK FIRST**, immediately before writing, never from your context. They run
   several agents at once and your copy can be hours old — another session may have closed an item,
   pulled one back from the backlog, or raised a decision since. Rewriting from a stale snapshot
   silently deletes their work and looks perfectly correct doing it, because it is a coherent
   version of an old truth.

   Then **edit only the parts you are changing.** A targeted replacement of the queue block leaves
   `## Decisions`, the watches and the footer provably untouched; a wholesale rewrite re-types them
   from memory and drops whatever you never knew was there. **Prove it with `git diff`** — only
   your intended change, nothing else.

   `## Queue` — actionable RIGHT NOW. Max **5**, numbered `1.`–`5.`. Each item: bold title,
   **model, effort AND attendance/mode**, one sentence, and a link to its brief.

   ```
   1. **Short title** — Opus 5 · high · HITL/Plan
      Brief: [briefs/slug.md](briefs/slug.md)
      One sentence on what this is.
   ```
   - **PRIORITY order, most important first, RE-SORTED at every wrap** where priority has plausibly
     shifted — never simply appended to. They pick by number, so the order is a claim about what
     matters. If an item stays high against that (in-flight, cheap, unblocks something), say so in
     the item rather than leaving the anomaly unexplained.
   - A 6th item means one drops out — **to the backlog, which is `BACKLOG.md`** (step 8a), or
     dropped outright. **Never back into `INBOX.md`**: that file is capture, and parking finished
     briefs there nags every future session start about items that are not un-triaged at all.
   - **UNDER 5 means REFILL — the return leg, and the half that was missing until v1.17.0.**
     If the Queue would end this wrap with fewer than 3 items and the backlog is not empty, **pull
     from `BACKLOG.md` until it has 3** (step 8a — a file on disk, so this works offline too). Displacement was automatic and refilling was nobody's job, so a wrap that finished
     the last queued item left an empty Queue on top of an open backlog, and the next session was
     told nothing was live. **Pick against the footer's aim line**, most important first.
     - **Pulling means writing the brief, on disk, now** — model, effort, attendance/mode, and the
       checkpoint if it is `HITL`. An item whose brief is "see issue #4" is not queued, it is a
       link, and reading it costs them the network and the context this system exists to save.
     - **Leave the item in `BACKLOG.md`, marked `queued`** (and its issue open, if it has one). It
       closes at the wrap that finishes the work (step 8a), not at the one that queues it — an item
       deleted on being queued survives only in `NEXT.md`, which is the file most likely to be
       rewritten from a stale copy by one of several concurrent sessions.
     - **Say what you pulled and why, in one line each.** They are stopping; a Queue that refilled
       itself silently is a Queue they did not choose.
     - **Refill 3, not 5.** The cap is 5 so there is room for what THIS week produces; a wrap that
       fills every slot from the backlog leaves the next session's real work nowhere to go.
     - Nothing to pull (empty backlog, or nothing that still serves the aim) is a fine answer —
       **say so explicitly**, and close what no longer serves the aim rather than leaving it to rot.
   - Opus for diagnosis, design, judgement calls, anything under-specified. Sonnet for fully
     specified mechanical work with the decisions already made.
   - Effort `high` when the agent will DECIDE something, `medium` when it will EXECUTE a decision
     already written down. **Never `low`** — the saving is small and a confident wrong answer
     written into a doc is the expensive failure.
   - **Attendance/mode is REQUIRED on every item**, written as one token after effort. It answers
     what model and effort do not: *can they start this and walk away, and what must they set first?*
     - **`AFK`** — runs to completion unattended: nothing it needs is missing from disk, nothing it
       does is irreversible. **`HITL`** — it will stop and need them. **The test: would the agent
       have to ask them anything it cannot read off disk? Then `HITL`.** Effort `high` is NOT
       `HITL` — an agent deciding on their behalf and reporting is `AFK` + `high`.
     - **If it is `HITL`, the brief must name the checkpoint** where it stops. "It'll need you at
       some point" is the thing they cannot plan around.
     - **Mode** is `Auto` · `Manual` · `Accept Edits` · `Plan` · `Bypass` — the permission mode they
       sets before starting, and the ONE field an agent cannot set for them:

       | Mode | For |
       |---|---|
       | `Plan` | under-specified work: read-only, produces a plan they approve. Always `HITL`. |
       | `Accept Edits` | specified edits across many files; they watch the commands, not each write. |
       | `Auto` | the default for **both** `AFK` and `HITL`: reads, edits and local tests in one repo. |
       | `Manual` | the rare item where each step genuinely warrants review. |
       | `Bypass` | `AFK` only, and only where the blast radius is one repo they can `git reset`. |

     - **Never reach for `Manual` to protect an irreversible step** (v1.31.0) — it gates every call,
       so they approve fifty reads to guard one push. **Write the stop into the brief instead**
       (*"commit locally, then stop; the push waits for them"*) and leave the item `HITL/Auto`. The
       brief already has to name the checkpoint, so the guarantee is already there.
       `skills/next/references/incidents.md` carries their correction verbatim — read it before
       putting `Manual` back.
     - **`AFK/Plan` and `HITL/Bypass` are contradictions** — a plan exists to be approved, Bypass
       exists because nobody is there to approve. Never write either.
     - **Re-check it when you re-sort**, same as effort: an item that was `AFK/Auto` becomes
       `HITL/Auto` the moment its brief grows a deploy step — attendance changes, mode usually
       does not.

   `## Decisions` — HIS to answer, not an agent's to pick up. `D1`, `D2`, … uncapped. ONE line
   each, no continuation, no prose body; full detail lives wherever the project keeps its backlog:

   ```
   **D1. Short title** — answer: `ask <authority>` · added `2026-08-09` → `docs/pending.md`
   ```

   - **`answer:` is REQUIRED and is the routing field** — `ask <authority>` (the project names its
     own authority — a domain expert, an API doc, a spec — and the code follows
     it) or `here` (they tell the session, and it becomes a change).
   - **`added` is REQUIRED**, never invented; backfill with `git log -S "**Dn." -- NEXT.md | tail -1`.
   - **No "do Dn."** A decision waits on them reading it, not on a trigger a hook can detect. That
     is what separates it from a watch.
   - **The test:** if it needs their judgement rather than their labor, it is a decision, not a queue
     item.
   - Answered → DELETE it, and log the answer plus what it changed in `CHANGELOG.md`.

   `## Watching` — waiting on a trigger. `W1`, `W2`, … uncapped. One shape, every time:

   ```
   **W1. Short title** — `Opus 5` · effort `high` · `AFK/Auto` · added `2026-08-15` · check after `X`
   ```

   The hook parses these fields, so all five are required and the order matters:

   - **Title inside the bold, fields outside, number followed by a full stop** (`W1.`).
   - **Never start a continuation line with a bolded word beginning in W** (`**WORKOUT**`) — put it
     mid-sentence or leave it unbolded. The parser splits entries on `**W<digit>` and used to
     invent a phantom watch out of such a paragraph. It is guarded now, but the digit is the only
     thing separating the two cases, so don't lean on the guard. **This is a property of the shared
     hook, not of any one project.**
   - **`check after \`X\`` stays LAST.** X is a `YYYY-MM-DD` date or free text naming an event.
     Dated watches stay hidden until their day, then surface as **DUE NOW**.
   - **`added \`YYYY-MM-DD\`` is REQUIRED and goes immediately before it** — the date the watch was
     written, never today's date on a file you are merely editing. An event-gated watch has no
     floor under it, so the hook prints its age (`waiting 12d`) and flags it past 30 days. Never
     invent one; backfill with `git log -S "**Wn." -- NEXT.md | tail -1`.
   - **Model, effort AND attendance/mode, same as a queue item** — a watch that comes due is
     something they start, and a watch is exactly where "can I just run this?" gets asked.
   - **The test:** if they could not start it today no matter how willing, it is a watch.
     *"Confirm X works in production"* always is.
   - An item BLOCKED by a watch stays in the Queue marked `blocked by Wn` — knowing why they can't
     pick it is information they need while picking.
   - Resolved → DELETE it and put the evidence in `CHANGELOG.md`.

   **Run the check before moving on** — a malformed item found NOW, in front of you, is cheap;
   the same item found at the next session start is not, because that is the moment the person
   reading it cannot diagnose it. This is the exact class of bug that shipped 2026-08-28: a
   watch's `added`/`check after` fields wrapped onto a continuation line and the next orientation
   silently misreported it.

   ```bash
   sh "<root>/hooks/run.sh" session_orientation.py --check
   ```

   **Never let it fail a wrap.** A nonzero exit names what to fix — fix it and re-run, don't
   ignore it and don't treat the checker itself failing to run as a wrap blocker: one line, carry
   on. Same rule as `sync_backlog.py` in step 8a.

   **No history, no evidence, no rationale anywhere in `NEXT.md`.** That is `CHANGELOG.md`'s job.

   - **Never invent a `## Done` section.** The hook treats everything after a `---` as a verbatim
     footer, so a Done block is just echoed back at them as noise.
   - **The footer below the `---` is a POINTER with a hard budget: 8 lines.** The Done rule is
     about a *heading*; the way this actually goes wrong is *prose* — a *"Session of 2026-08-14: …"*
     paragraph, which looks like re-entry context and so slips past that rule. It is not re-entry
     context: it is echoed into the agent's context **verbatim, on every session, forever**, and
     its content already exists in `CHANGELOG.md`. A footer does not drift, it **regrows** —
     trimming it is not the fix, never writing narrative into it is. `MAX_FOOTER_LINES` truncates
     past 8 lines with a visible marker, so reaching the cap means the wrap put history in the
     wrong file. What belongs there: a link to `CHANGELOG.md`, a link to the briefs directory, one
     line on what the project is, one line on **where it is going**. Nothing dated, nothing
     narrative.

   - **The direction line — write it, then re-confirm it every wrap.** One line, present tense,
     what *done* looks like for the current phase (`Aim: <…>`). Everything else in the system is
     near-term — Queue capped at 5, Watching is triggers, the backlog unordered — so this is the
     only statement of destination, and the only axis available when you re-sort the Queue or ask
     whether a backlog item still deserves to be open. **It is a criterion, not a plan**: keep it
     to one line and resist growing it into a roadmap, which is what the backlog is for.
     If the session's work no longer matches it, **say so to them in one line** rather than quietly
     rewriting it — a changed destination is their call. A stale direction line is worse than none,
     because it is in front of them at every session start.

8. **Empty `INBOX.md`.** Every bullet becomes a `NEXT.md` item or a backlog item (step 8a). Never
   wrap with un-triaged bullets — they are things they noticed and will not notice again. **Never
   leave anything parked there "for later"**: an item with a finished brief is backlog, not capture.

8a. **The backlog — `BACKLOG.md`. Every project. No exceptions, no configuration, no network.**

   Three layers: `INBOX.md` = capture, `NEXT.md` = the capped working set, **`BACKLOG.md` = the
   backlog** — unbounded, unordered, on disk, in the repo, readable on a phone with no tooling.

   **The ISSUE HOST is a SYNC TARGET, not the backlog** (inverted in v1.18.0 — before that, a
   project with no GitHub remote had no backlog layer at all, and a displaced item was dropped
   with a one-line note at the exact moment they had stopped paying attention). Issues buys three
   things a file cannot: it reaches their phone, it survives a lost machine, and other people can
   write to it. It is an upgrade, never a prerequisite.

   **GitHub AND GitLab, since v1.34.0.** The host is detected from the git remote — `gh` for
   GitHub, `glab` for GitLab, including a self-hosted instance like `git2.example-corp.net` once
   that CLI has logged into it. **Never name a CLI in a wrap; run the commands below and they
   pick the right one.** Anything else is still a graceful skip, and the skip line now says
   whether waiting will ever help.

   - **Write `BACKLOG.md` FIRST, always. It is the writer; Issues is the copy.** An item that
     reaches the file is safe whether or not the CLI works, whether or not there is a remote,
     and whether or not they are online.
   - **File every item displaced from the Queue, automatically. Do not ask first** — displacement
     happens at the exact moment they are stopping. One `## Bn.` section: title, a fields line
     (model · effort · `AFK/Mode` · `added` · `issue` · `queued`), the brief link, and one line on
     *why* it left the Queue.
   - **A side-quest finding this session turned up gets the same treatment, not a one-line stub** —
     what was found, where, what was already ruled out, and why it matters, so a later session costs
     zero re-investigation of ground already paid for in tokens and tool calls this session.
   - **Mark finished items `closed` with today's date; do not delete them.** The sync closes the
     issue and then drops the item. Deleting it by hand loses the close.
   - **An item on the Queue STAYS here, marked `queued`** — same lifecycle as its issue. `NEXT.md`
     is a working set; this file is what any machine rebuilds it from.
   - **Then sync — one command, safe to run anywhere.** It is outward-facing, so after an
     unattended run it **waits for their go-ahead alongside the push** (step 5), not before it:

     ```bash
     sh "<root>/hooks/run.sh" tools/sync_backlog.py
     ```

     It files issues for items that have none, closes the issues of items marked `closed`, keeps
     the `backlog`/`afk`/`hitl` labels in step, and pulls in any open issue that is not in the file
     (marked `inbound` when somebody else filed it). Everything it does is derived from the file,
     so there is no outbox to keep in step and **an offline wrap loses nothing** — it prints one
     line saying so, and the next wrap on a connected machine pushes the lot.

     **Never let it fail a wrap.** No CLI, no auth, no remote, no network: one line, carry on.

     **If it prints `backlog sync REFUSED`, that is not a skip — READ IT.** It means the file
     holds item headings the parser cannot see (`## 12.` instead of `## B12.`), so regenerating
     it would delete them; it made no host call and touched nothing. Fix the headings to
     `## Bn. Title`, keeping every word of the body, then re-run. Found 2026-09-03 in
     `~/Projects/workspace`: 13 headings, 0 parsed, 206 lines one write from gone.
   - **Make the labels exist first** if this repo has never synced — idempotent, cheap:

     ```bash
     sh "<root>/hooks/run.sh" tools/label_backlog.py --ensure
     ```

     Filing an issue with `--label afk` in a repo without the label does not fall back to an
     unlabelled issue — it fails, mid-wrap, at the moment they have already stopped watching.
   - **Pull the Queue back up to 3 if this wrap emptied it** (step 7's refill rule) — read
     `BACKLOG.md`, not Issues. It is on disk, it is current, and it works on a train. **Do not
     delete what you pull**; mark it `queued`.
   - **No `BACKLOG.md` in this project yet?** Create it — the first displaced item is reason
     enough. A project that already has issues seeds the file from them: write an empty one
     (`sh "<root>/hooks/run.sh" backlog_file.py` documents the shape) and run
     `sync_backlog.py --pull`.
   - **Refresh the session-start issues cache** if the issue list changed, so the next session's
     inbound warning is current without a network call. **One command, either host:**

     ```bash
     sh "<root>/hooks/run.sh" issues_backlog.py --refresh --report
     ```

     This replaced a hand-written `gh issue list … | --ingest` pair in v1.34.0. That pair named
     `gh` three times, so it was structurally incapable of refreshing a GitLab project's cache —
     and it made the wrap responsible for JSON plumbing that the backend already does. `--ingest`
     survives for the one case that needs it: a shell where the CLI runs but this script's Python
     cannot reach the credential store. It takes either host's JSON (`--file`, **never a pipe** —
     Windows PowerShell 5.1 re-encodes anything piped into a native executable and corrupted this
     exact payload on its first live run) and tells the two schemas apart on its own.

     **The hook also refreshes this itself**, in a detached child at session start — but only on a
     machine where the CLI works from a hook, which is not universal (see
     `references/incidents.md`).
     A failed refresh keeps the last good listing, so on such a machine the wrap is the only writer
     of a *current* cache. Since v1.18.0 the session-start COUNT comes from `BACKLOG.md`, so this
     cache now serves the one thing no local file can know — **an issue somebody else filed.**

8b. **Name the session. This is the last moment anyone knows what it was.**

   Their session list is a memory aid, and auto-titling names a session after its **first message** —
   so a session that did real work is called "Hello", "do 1" or "Reentry next" unless something
   renames it.

   - **Sweep the ones you CAN fix.** Call `list_sessions` and rename any non-archived session in
     this `cwd` whose title carries no information — "Hello", "do 1", "test", "Untitled", a bare
     date, or an `Item N` prefix. Infer from `CHANGELOG.md`, recent commits, or
     `search_session_transcripts`. **Their own titles always win.**
   - **Rename THIS session — `set_session_title(session_id: "self", …)`.** It works.

     **You cannot READ the current title** — `get_session` rejects it and `list_sessions` excludes
     it. Writing is possible, reading is not, so the junk-title test above **cannot be applied
     here**; the only signal is this session's own transcript. They asked for a title, or told you they
     set one → leave it alone. They didn't → it is an auto-title or the placeholder `/cairn:next`
     step 7 wrote to be overwritten here, so **rename it. Don't ask, don't print a suggestion to
     click.**
   - **Then say in ONE line that you renamed it, and to what.** That line is the actual safety
     mechanism, not the condition above: since the title is unreadable, a rename can in principle
     overwrite one they set silently in the UI, and telling them is what lets them put it back. Saying
     nothing is the only genuinely unsafe option.

   ### The format: `<project> · <what it turned out to be>`

   **The project folder name as-is, then the subject. NEVER the queue number.**

   ```
   code · GitHub Issues as the backlog layer (v1.8.0)
   atlas · revs 229-230, the planner takes the week back
   lighthouse · route import silently drops waypoints
   ```

   The number is the one part of the title guaranteed not to vary — they pick the top of a
   priority-ordered queue — and it sits where they scan first. Their session list interleaves every
   project they touche, and the `cwd` is in the data but not in front of them, so the project leads.
   A name, not a summary: after the `·`, the project's own disambiguator is usually right (in
   `atlas`, the rev number — which is exactly what `/cairn:next` could not know when it set
   the placeholder). **Never emit a title identical to another recent session's in this `cwd`** —
   `list_sessions` is already in hand from the sweep, so check, and break a collision with the date
   (`· 08-22`).

8c. **Record the CAIRN receipt. The verdict is a QUOTATION from here on — never compose one.**

   **This is the command. There is one.**

   ```bash
   sh "<root>/hooks/run.sh" wrap_receipt.py --record
   ```

   **Did you push in step 5? Then you are done — do NOT read on to the flag.** Two forms used to be
   printed here side by side with the caveat underneath, and on 2026-09-08 a session that had pushed
   on purpose reached for `--held`, got the false `ALERT` this page predicts, and then wrote a
   paragraph explaining the alarm away — restating the sentence below as a limitation of the tool
   rather than as the reason not to pass the flag. **An exception printed beside a default gets
   chosen.** So the flag now lives past a gate:

   <details>
   <summary><b>ONLY if step 5's stop applied — you committed locally and deliberately did NOT
   push</b></summary>

   ```bash
   sh "<root>/hooks/run.sh" wrap_receipt.py --record --held
   ```

   </details>

   **`--held` ONLY when step 5's stop applied** — the wrap committed locally and deliberately did
   not push. It opts the receipt into `push_check`'s interpretation, whose `ALERT` means *something
   pushed the work without being asked*. After an ordinary wrap that pushed on purpose, HEAD moved
   and `ahead` is 0, which is that alert's exact shape — so passing it there makes every successful
   wrap cry wolf. Whether a push was INTENDED is not visible in git; only you know, so you declare
   it. Without the flag the receipt records the ahead/behind counts as plain facts and asserts
   nothing.

   Runs last of the writing steps, once everything that leaves residue has left it. It measures
   each step, prints a per-step table and ends with one line:

   ```
   CAIRN SET · 4f2c81a09b6d
   ```

   **Quote that line verbatim in the close. Do not compose a verdict of your own, in any wording,
   in any step, ever again.** `CAIRN SET` / `CAIRN NOT DUE` / `CAIRN OPEN` are the only three
   verdicts, and all three come from this tool — **including the negatives.** *"No wrap needed"*
   was the exact sentence that started B87, so a tool owning only the affirmative would move the
   impersonation one door down rather than close it.

   **If it prints `CAIRN OPEN`, the wrap is not done.** The lines beginning `!` name the steps
   that measured `skipped`. Go back and run them, then re-record — do not report the wrap and do
   not explain the `OPEN` away.

   **You have no verdict if you have no token.** If the tool cannot run, say exactly that: *"I
   cannot produce a wrap verdict — `wrap_receipt.py` did not run."* An account of what you did
   instead is the thing B87 exists to stop.

   The receipt table is honest about what it cannot see: surveying the tree, the memory pass, the
   session rename and the close itself leave no residue and are marked `?`. Do not read a `?` as a
   tick, and do not read the token as proof the whole procedure ran — it is evidence, which is
   strictly more than the sentence it replaces and strictly less than a guarantee.

9. **The close. Say plainly: "good point to end the session here."** They miss natural
   breakpoints, so say it out loud. Then exactly three things, **written as prose — never as a
   labelled list.** The bullets below are this skill's scaffolding, not content; emitting
   *"a. … b. … c. …"* leaks the checklist into their reply.

   **Open with step 8c's token line, quoted** — `CAIRN SET · 4f2c81a09b6d` — then the prose. It is
   one short line and it is the only part of the close they can check.

   - **What's next, with model, effort AND attendance/mode.** *"Next: item 1 — move the remaining
     repos. Sonnet 5, effort medium, AFK in Auto mode."* Never the model alone — and if the next
     item is `HITL`, say where it will stop, so they can judge whether they have the attention for it
     today.
   - **The session's name** (step 8b) — one short line.
   - **Whether to continue here or start a new session:**

     **Ending a session and running out of context are different triggers, and only the second one
     is about tokens.** End a session when the work is **wrapped** and the next thing needs
     **different** context — a different model tier, a different part of the repo, a brief this
     transcript cannot help with. Context *pressure* is a separate and much rarer trigger. **Say
     which one you mean.** *"Good point to end here"* with no reason attached is read as *"you are
     running out of room"*, and at 10% used that is simply false.

     **What carries over to a new session: nothing.** That is the design — a new session loads only
     the fixed baseline plus whatever it reads off disk, which is why the wrap writes to disk. A
     cold start on an item is a few thousand tokens; the harness (system prompt, tool schemas,
     skill list) is identical either way and cancels out of the decision entirely. **Measure it,
     never quote it:** `sh "<root>/hooks/run.sh" tools/measure_context.py <project-root>`. The
     reason to stay is never the token count, and the reason to leave is relevance, not volume.

     | Situation | Say |
     |---|---|
     | Next item needs a different model, effort or mode | **New session** — keeps the title truthful, drops context the new item can't use, re-runs the orientation |
     | Different item, same model | **New session**, same reasons minus the switch |
     | Same item, context genuinely filling | Stay here; `/compact` when it gets long |
     | — | **Avoid `/clear`** — it resets context but keeps the session's identity, so the title then lies about the contents |

   **Do NOT paste a ready-to-copy prompt into chat.** Everything it would contain is already on
   disk, and the hook prints the queue before they type anything next session. They removed exactly
   this on 2026-08-09: *"Part of the reason of building this system was because you would give me a
   prompt to copy at the end of a session… We're kinda back there."*

   Continue-or-new-session is the **only** part of the close deliberately not on disk: an action
   only they can take, not information they would need to recover.

10. **Ask in chat whether to archive — the wrap's final act.** After every write, commit, push and
    the step 8b rename, ask them directly, in the close text they actually reads: approving archives
    and ends the session; declining keeps it running and costs nothing, because the work is already
    committed. One or two sentences. Wait for their answer before calling anything.

    **Stamp that the question was ASKED, before you ask it** — not after, and not conditionally on
    the answer:

    ```bash
    sh "<root>/hooks/run.sh" archive_offer.py --stamp-asked
    ```

    Without this, `--check` cannot tell "asked and accepted" from "never asked at all" — it reports
    a bare `NONE` for both, which are opposite states, and a wrap done by hand that skipped this
    step reads back as *settled* (B35). `--stamp` below records the DECLINE and `--clear` records
    the ACCEPT; both run only once the answer is known, so neither can supply this fact. That is
    why it needs its own call, here, before the question leaves your mouth.

    **Do not rely on `archive_session`'s own tool-permission prompt as the ask.** It is not a
    substitute on a session running in `auto` permission mode (`defaultMode: "auto"` in
    `settings.json`) — there the prompt auto-approves and the archive happens with no real choice
    made, which is indistinguishable from the tool just running silently. Get an explicit answer in
    chat first, in every mode, then call:

    ```
    archive_session(session_id: "self")
    ```

    only once they have said yes.

    **It must come last.** The conversation ends on approval, so anything not already on disk is
    lost. Without it a wrapped session sits in the open list looking live, which is the state this
    whole system exists to prevent — the session list is how they find past work.

    - **Declining is a legitimate outcome, not a failure.** Do not retry, do not re-prompt, do not
      treat a declined archive as an incomplete wrap. The wrap finished at step 9. **Do** record
      that the offer went unanswered, so a later verdict this session can carry it forward instead
      of losing it to conversation memory:

      ```bash
      sh "<root>/hooks/run.sh" archive_offer.py --stamp
      ```

      If they say yes instead, run `--clear` before calling `archive_session` — there is nothing
      left to carry forward once the session is ending. See the WRAP VERDICT rule below for the
      other half of this: checking `--check` before stating a later verdict.
    - **The tool's own description says never to call it speculatively — this is not speculative,
      and here is why, so you don't talk yourself out of the step.** Asking for a wrap *is* the
      request to end the session, and the close text above states plainly what approving does. But
      the condition is real: **only ask to archive if they asked to wrap, or agreed when you
      suggested it.** If a session ran these steps ad hoc and they never said to stop, skip step 10
      and offer instead.
    - **Known dead end — do not investigate.** An archived session can still show a stale "running
      tools" badge in the list while `list_sessions` correctly reports `isArchived: true`. That is
      client-side UI; nothing in the wrap can fix it.

## Rules

- **NEVER imply closure you have not delivered, and never leave the wrap status unstated.**
  "Good point to end here" **must** carry the token in the same breath. Silence on the question is
  the same failure as claiming closure falsely: from the outside they look identical, and they are the
  one who cannot check.

  **The verdict is owed ANY time you report on the state of the session — not only at the close**,
  and since v1.44.0 it is **not yours to word**. Run
  `sh "<root>/hooks/run.sh" wrap_receipt.py --check` and quote what it prints. **Reporting the
  mechanics instead is one failure mode** — *"everything committed and pushed"*, *"all three
  repos clean"*, *"0 0 against origin"* are inputs to a verdict, not a verdict. **Composing your own English verdict is the other, and it is the one that actually
  happened**: *"no wrap needed"* was produced twice, confidently, from real evidence, by a session
  that had never run this skill (B87). Both are now the same rule — quote `CAIRN SET` / `CAIRN NOT
  DUE` / `CAIRN OPEN`, then give the evidence underneath if it is worth showing.

  This applies **however the steps got done.** A session can run every step by hand without ever
  invoking this skill and still be genuinely wrapped — the verdict is about the steps, not the
  command, and `--record` measures the steps, so a hand-run wrap earns a real `CAIRN SET` the same
  way. What it does not earn is a verdict you wrote yourself because the steps *felt* done.
- **A "no wrap needed" or "wrapped" verdict carries the archive offer with it, if one is still
  outstanding.** Step 10 asks once, right after the wrap it belongs to — but a verdict can be owed
  turns later in the same session, after they declined or the conversation moved on without
  answering. Check before stating either verdict:

  ```bash
  sh "<root>/hooks/run.sh" archive_offer.py --check
  ```

  `PENDING` means say the verdict AND re-ask whether to archive, in the same reply — not as two
  separate thoughts. `NONE` means say the verdict alone; there is nothing to reconnect. Never
  re-derive this from what the conversation seems to remember — a long session or a compaction can
  make an earlier decline look, from the inside, like it was never offered at all.
- **Suggest wrapping proactively** when a phase completes, a deploy lands cleanly, or the work is
  about to pivot. Don't wait to be asked.
- **Finishing the work is not a licence to hand them a loose end.** If you catch yourself writing
  *"worth keeping an eye on"* or *"check back after X"* — stop. That is a watch with a date, not a
  sentence in chat.
- **No bare token constants in this file.** A number in an always-loaded file rots silently and is
  then quoted as fact; three had, one of them quoting this system's own out-of-date size. A number
  stays only if it is dated evidence of a specific incident and says so. Everything else is
  `sh "<root>/hooks/run.sh" tools/measure_context.py <project-root>`.
- **Report honestly.** If tests failed or a step was skipped, the wrap says so.
