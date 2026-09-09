# Running a lane-partitioned batch

How to burn down a lot of backlog in one day without a stampede. Written 2026-09-05 after a run
that closed 17 items, and after an earlier attempt that spawned 179 agents, consumed two 5-hour
windows in ten minutes each, and completed nothing.

**To start one, all you need to say is:** *"run a lane batch on the backlog"* — or name a scope,
like *"lane batch, AFK items only"*. Everything below is the agent's job, not yours to remember.

---

## Why the naive version fails

Every item lives in **one repo** whose shared files are large. Fan out N agents and each one
independently reads the same big files, so context cost grows with N × the repo rather than with
the work. Then every agent writes the same four shared files and they conflict. Burn plus zero
completions is the *predicted* outcome of that shape, not bad luck.

**Agent count is the wrong dial.** The useful cap turned out to be four concurrent agents, and what
made four safe was the partition, not the number.

## The rules that make it work

1. **Partition by FILE OWNERSHIP, not by item count.** Group the work into lanes with disjoint
   owned files; one agent per lane, working its items sequentially. Two items that touch the same
   file belong in the same lane even if they are unrelated.
2. **No lane touches a shared file.** `CHANGELOG.md`, `BACKLOG.md`, `NEXT.md`, `plugin.json`,
   `README.md` are the orchestrator's alone, written between waves. This also puts the repo's own
   version-bump/README and `incidents.md` rules in one place where they are actually enforceable.
3. **Paste the backlog entry into the agent prompt.** No agent reads `BACKLOG.md`. The entries
   already name the file, the line, the fix, the rejected alternative and the incident — they *are*
   the briefs. Largest single token saving available.
4. **Sonnet for lanes, Opus for the orchestrator.** Nearly every backlog item here is
   `Sonnet 5 · medium` — diagnosed, decided, mechanical. Judgement lives in the review, not the edit.
5. **Cap at four concurrent.**
6. **A lane that must grep the whole repo runs ALONE.** A rename sweep collides with everything by
   construction.

## Budget — run `tools/measure_usage.py`, do not read a number off this page

```bash
python plugins/cairn/tools/measure_usage.py --window     # before sizing anything
```

**The figures that used to be here were wrong in SHAPE, and they cost a batch on 2026-09-08.**
They said *~150k per lane agent, ~8–10 lane agents per 5-hour window, including an Opus
orchestrator*. Measured from the transcripts that same day, that model fails three ways:

| | this page used to say | measured 2026-09-08 |
|---|---|---|
| a Sonnet lane agent | ~150k tokens | **358,069 billed** — its own completion notification said 172,876, i.e. **the reported number is about half the real one** |
| the orchestrator | one lane-equivalent, counted inside the 8–10 | **2,316,354 billed — about 60% of the whole batch**, and it scales with TURNS, not with how many lanes it supervises |
| the window | 8–10 lane agents | **~3.86M billed** was the worst 5-hour window on this machine, and it hit the limit |

**Budget in TURNS and AGENTS together. Agents alone is the error that keeps recurring.** An
orchestrator turn cost a median of **~4,700 billed** early in a session and **~8,500 by hour four**,
because **cache writes are ~79% of billed spend** — the cost is re-establishing a growing context
every turn, not the work itself. So the same batch gets more expensive the longer the session that
supervises it has been running, which is the thing no per-agent constant can express.

**Working arithmetic, and re-measure it rather than trusting it:** a window is roughly 3.8M billed.
Three Sonnet lanes are ~1.1M. That leaves ~2.7M, which at 5–8.5k per turn is **300–500
orchestrator turns — and a supervising session spends turns fast.** Planning and design agents
count too: on 2026-09-08 the plan budgeted three lanes and **eight agents actually ran** (three
exploration, two design, three lanes); the five planning agents were never counted against the
window at all, and that omission, not the lanes, is what ran it out.

- **Count every agent, including the ones that only read.** An exploration agent costs what a lane
  costs.
- **Subagent spend is not durably recorded** — their transcripts sit in a scratchpad `tasks/`
  directory and are truncated when they finish. Take the figure from each completion notification
  and **double it**.
- Estimate against the **shortest binding window**, not the weekly budget. The 5-hour rolling limit
  is what actually stops work; agents have now been killed mid-flight by forgetting that on three
  separate occasions.
- **Wave 0 is the calibration.** Run `measure_usage.py` after it and before sizing wave 1.
- **A long session is itself a cost.** When `--window` shows per-turn spend well above the median,
  the cheapest remaining move is to wrap and hand off to a fresh session, not to push on.

## A test baseline first, if the code being changed has none

Spend a wave on a runner and characterisation tests **before** any behaviour change, written by an
agent forbidden from touching production code — a lane that writes tests for code it is about to
change will pin the bug as correct behaviour. Label each pinned defect `BUG:` so the fixing lane
must flip it visibly in the diff, and forbid deleting a pinned test to make the suite green.

## The review surface

Reading four agent transcripts is not review, and their sessions cannot be opened anyway. Instead:

- **Every lane writes a dossier to `docs/review/<YYYY-MM-DD>-<HHMM>-<lane>.md`**, where the time is the **run's start**, not the file's. Learned 2026-09-06: two waves on one night produced `lane-a-…` through `lane-d-…` plus one more, and untangling which session wrote which — and which had actually landed versus sat blocked on a permission prompt — cost a morning. A modification time is not enough; it says when a file was last touched, not which run it belongs to. The handover carries the same prefix and is the entry point.
- Each dossier has four fixed sections: what changed
  and why; the verification actually run with **real output pasted, not summarised**; **anything
  decided on your behalf**; and what it chose not to do.
- **The orchestrator publishes one Artifact** collecting every lane — judgement calls first, since
  that is what a human catches by reading. Reference numbers must carry titles or links; a bare
  `B47` means nothing to a reader.
- **The orchestrator reads each dossier against its actual diff before committing.** A lane's
  write-up and its code can disagree silently, and that is the failure neither one alone reveals.

## Hand the orchestrator off between waves

**The orchestrator is usually the most expensive thing in the batch, and it gets more expensive
every turn.** Every request re-sends the whole conversation, so a session that has driven three
waves is paying for all three on every call — while a lane agent always starts cold and costs the
same whether it is the first or the twentieth.

So the wave boundary is also the **session** boundary:

- **Wrap and start a fresh session between waves.** The new session reads `NEXT.md`, `BACKLOG.md`
  and the dossiers off disk — which is the whole point of the system — and pays nothing for the
  history it does not need.
- **Never hand off mid-wave.** Background agents are bound to the session that launched them; a
  handoff with lanes in flight loses them.
- **The trigger is cost, not relevance.** The wrap skill is right that *"the reason to stay is
  never the token count"* when deciding whether an item needs this transcript — but that is about
  a single item's context. An orchestrator carrying a whole day is a different case: its per-turn
  cost is a tax on every remaining lane, and the work it is carrying is already on disk.
- **Symptom to watch for:** the orchestrator spending more of the window than the lanes it is
  supervising. If reviewing and committing costs as much as the work, hand off.

**Learned the hard way, 2026-09-05:** one session drove all three waves, and by the last one the
5-hour window was 70% gone with four lanes still running — over-committed by about a lane, with the
orchestrator's own context a large part of why.

## Running a batch overnight

**Untested as of 2026-09-05 — designed from the tool contracts, not from a run.** Treat the first
night as the experiment.

The handoff rule above says the wave boundary is the session boundary. Overnight that has to happen
with nobody there to start the next session, so it needs a scheduler rather than a loop.

### Use `create_scheduled_task`, not `CronCreate`, and not `/loop`

| | What it does | Overnight? |
|---|---|---|
| **`create_scheduled_task`** | Writes a task to `~/.claude/scheduled-tasks/<id>/SKILL.md`. **Each run starts a fresh session with no memory of the last one.** | **Yes.** Cold context every firing is exactly what is wanted. |
| `CronCreate` | Session-only, in memory, gone when Claude exits, auto-expires in 7 days. | No — needs one session alive all night, which is the context rot being avoided. |
| `/loop` + `ScheduleWakeup` | Keeps *this* session going and re-invokes it. | No — same problem, and per-turn cost grows all night. |

**The task prompt must be fully self-contained** — it cannot see the conversation that created it.
That is fine here: everything it needs is on disk, which is the point of the whole system. A good
prompt is roughly *"read `NEXT.md`, take the AFK items, follow `docs/running-a-batch.md`, commit
each lane, do NOT push, wrap"*.

### Constraints that decide whether this is worth doing

- **The permission mode is NOT set by the task prompt, and a task in `Manual` never gets going.**
  Measured 2026-09-06: the 05:00 firing sat for over four hours on a prompt asking permission to run
  a `sed` that reads one backlog entry, and only completed at 09:55 once a human clicked. A prompt
  cannot switch its own mode — this is the same asymmetry as the model tier, except that here the
  human is asleep and there is nobody to click. **So before scheduling an overnight run, say
  plainly which mode he must leave the app in** (`Auto`, or `Accept Edits`), the same way a queue
  item names its mode. `AFK/Manual` is a contradiction exactly like `AFK/Plan`: `Manual` gates
  every call, so an unattended run in it does not run.
- **The app must stay open.** A task due while it is closed runs *at next launch*, not overnight —
  so a closed laptop turns the whole night into one very confused morning run. Check sleep and
  hibernate settings too.
- **Never push, never sync** — but that is the standing rule for every batch (see Push policy),
  not an overnight special case. Overnight only removes the possibility of him overriding it.
- **AFK items only, and enforce it in the prompt.** An `HITL` item overnight is a lane that stalls
  until morning having burned its tokens on the way to a question nobody answered.
- **Size each firing to about 3 lanes, and space firings by the 5-hour window**, not by wall clock.
  Roughly two firings across a night; a third is usually the one that dies mid-flight.
- **Nothing is reviewed overnight. Do not talk yourself into thinking otherwise.** The mechanical
  guards — a green suite, the leak detector failing the run — are a **gate against obviously broken
  code**, not a reviewer. They cannot catch a fix that is coherent, tested, and wrong: on
  2026-09-05 two separate fixes each reproduced, one level up, the exact defect family they were
  fixing, and **both were caught by a human reading the dossier, neither by a test.** So an
  overnight run produces *unreviewed work that compiles*. That is a fine thing to wake up to and a
  terrible thing to push unread.
- **It self-limits, and that is a feature.** Only the AFK backlog is eligible, so the night runs out
  of safe work rather than inventing some.

### What the morning looks like

Several waves of commits, unpushed, each with its dossier in `docs/review/`, and a `NEXT.md` that
was rewritten by the last firing. The review Artifact matters *more* than in an attended batch, not
less — it is the only thing standing between a night's work and a blind push.

## `docs/review/` is an INBOX, not a library

**What is in `docs/review/` is what has not been accepted yet.** Once a batch is pushed, its
dossiers move to `docs/review/archive/`, keeping their `YYYY-MM-DD-HHMM-` prefix.

The point is not tidiness. Before this rule, twenty-five files sat in one flat directory — some
from a batch settled a week ago, some written six hours earlier by a run that had stalled — and
the only way to tell which still wanted reading was to open them. An inbox that never empties
stops being read at all, which is the same alarm-fatigue failure as a banner that fires on a
routine state. Emptying it is what makes a non-empty `docs/review/` mean *"someone owes this a
read."*

**Moving a dossier breaks every pointer to it, which is B76 by hand.** So repoint
`NEXT.md`, `BACKLOG.md`, `CHANGELOG.md`, `docs/` and the two `incidents.md` files in the same
commit as the move, and grep for `docs/review/` afterwards to prove none dangle. B90 exists to
make this a tool rather than a careful habit.

**Not everything in there is a dossier.** `docs/review/user-guide.md` is a standing reference that
a Queue item cites; it stays. The test is whether the file describes *one run* — if it does, it
archives.

## Push policy — never push, never sync, in ANY batch

Lanes commit nothing. The orchestrator commits **per lane, with explicit pathspecs**, and then
**stops**. `origin/main` untouched means the whole batch undoes with one
`git reset --hard origin/main`.

**And say so in the handover, per lane.** "The whole night undoes with one command" is true and
misleading: it describes the only option a reader thinks they have. Because every lane is its own
commit, the unit of acceptance is a **lane**, not the batch — so the handover must list the
commits with what each one is and what it depends on, and name the two moves that are not
`push` or `reset`: revert one lane, and fix the bookkeeping commit by hand afterwards. The
bookkeeping is the only commit touching shared files, which is exactly what makes a single-lane
revert tractable; it is also what makes reverting a lane *without* editing the bookkeeping produce
a `CHANGELOG.md` claiming work no longer in the tree. His question, 2026-09-06: *"Couldn't we
commit each lane's work separately? That way lanes that landed successfully can be merged and ones
that had an issue can be reset?"* — we already did; nothing had told them.

**The push and the backlog sync are yours, always — not just overnight.** They are the two
outward-facing acts in the whole procedure: a push publishes, and the sync writes to an issue
tracker other people can see. Neither is reversible in the way a local commit is, and neither is
urgent. This is B22's rule applied to the batch as a whole: *an `AFK` item commits locally and
stops before the push*, so nothing outward-facing lands before he has read it.

An attended batch is not an exception. If he says "push it" mid-run, that is a decision he made
about work he has seen — not a licence to push the next wave too.

## The two failure modes actually seen

Both were caught in review, neither by the lane that wrote them.

- **A fix reproducing, one level up, the defect family it was fixing.** Twice in one day. A gate
  meant to stop "record missing, reported as fine" returned the same value for *"no matching
  entry"* and *"no file at all"*. A fix for "cwd drift makes me answer about the wrong project"
  introduced "another session makes me answer about the wrong project, for two hours". **Ask of
  every fix: does this reintroduce its own bug at the next level up?**
- **Tests writing into real user state.** "Fixtures only, never the real `~/.claude/`" was in every
  brief and it still happened, poisoning a live tool within the hour. A rule in a brief is not a
  mechanism. Where a lane can touch shared state, make the check mechanical.

## Order of operations

```
wave 0   test baseline (if needed)      → commit
wave 1   4 lanes, disjoint files        → review dossiers vs diffs → commit per lane
         bookkeeping: version, README, CHANGELOG, BACKLOG closes, NEXT.md
wave 2+  remainder                      → same
         publish the review Artifact
         push, then the backlog sync (a separate outward-facing act)
         /cairn:wrap
```


## The bookkeeping is a DETECTOR, not the orchestrator's chore

Measured on 2026-09-05, second full batch. Four lane agents closed **8 backlog items**. The
bookkeeping between and after the waves — closing items, refilling the queue, rewriting `NEXT.md`,
running the sync — found **B75, B76, B77, B84 and B86**, and those are the more consequential half.

That is not luck, and it is worth understanding rather than repeating:

- **A lane sees one partition. The bookkeeping sees the whole file.** Every defect in that list is
  a property of the shared files no lane was allowed to touch — the id allocator, the pointers
  between items, the writer. A partition that makes lanes safe is exactly what makes them blind
  to this class.
- **The bookkeeping is the only step that EXERCISES the shared machinery.** B84 and B85 are
  `render()` bugs; nothing but a sync calls `render()`. A batch that skips the sync ships without
  ever running the code most likely to corrupt the file.
- **It is also where a stale claim meets a fresh one.** Twice that day, prose in `NEXT.md`
  contradicted `CHANGELOG.md` — and both times it surfaced while reconciling the two, never while
  editing either.

**So budget for it, and do not hand it to a lane.** Reckon the orchestrator's bookkeeping at
roughly the cost of a lane agent, and treat findings from it as expected output rather than as
interruptions. **Run the sync inside the batch, not after it** — it is the integrity test.

## One writer per repo, and it should be the machine holding the work

The partition rule above governs lanes inside one session. The same rule governs *sessions*, and it
is the one that actually bit on 2026-09-05: two sessions on two machines, both writing the same
project's files, neither able to see the other's commits. Four id collisions came out of it.

What worked, once it was done deliberately:

- **Each repo has exactly one writing session at a time**, and it is the one on the machine where
  the unpushed work already lives. That night this repo was written from LAPTOP1 and `atlas`
  from WORKSTATION, each syncing its own — no relaying findings through a human, no merges.
- **A stale checkout is disqualifying.** The session that offered to write into the other repo was
  78 commits behind; its earlier attempt had already minted three ids that were long taken. **Pull
  first, and if you cannot, hand the findings over as text rather than writing them.**
- **Push before handing off, always.** The handoff is not the report, it is the push — a finding
  that exists only on one laptop is not handed off at all, whatever was said in chat.
- **Watch the horizon** — see `docs/decisions.md`. "Re-read from disk first" defends the wrong one
  here, and following it exactly is what produced the collisions.
