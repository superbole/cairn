# Why `/cairn:next`'s rules exist — the incident record

**You do not need this file to re-enter a project.** `SKILL.md` is the instruction; this is the
evidence behind it. Read a section only when a rule looks wrong, or when you are about to deviate
from one — which is the situation every entry here was written to prevent.

Each rule exists because an agent reasoned its way past it, or because a measurement contradicted
what the file was asserting. Dates are when it was caught.

---

## Provenance

Written as a user-scope skill; **packaged into the `reentry` plugin on 2026-08-11**, which is what
made it work in every project on every machine rather than in whichever copy happened to be current.
The user's reason, 2026-08-08: *"I'm worried that I am going to have lots of different copies/versions
of the file and/or system."* There were already three divergent states when they said it. **Do not fix
a problem by copying this system into a project** — fix it in the plugin's own source repo, bump the
version, reinstall.

---

## Step 4a — the backlog is a file now (2026-08-28)

Since v1.18.0 `BACKLOG.md` is the backlog and GitHub Issues is where it syncs, so triaging the
backlog is a `Read`, not a `gh` call: it works offline, it works in a project with no remote, and
it costs nothing at session start. The one live `gh` call left in this skill is for an issue
**somebody else filed** — the only thing in the whole system they did not put there themselves, and the
only thing a local file cannot know.

---

## Step 4a — an empty Queue is not an empty project (2026-08-28)

The orientation's tier was computed from `NEXT.md` alone, so an empty Queue on top of five open
backlog issues printed **STAY QUIET — nothing is live**, and the Queue stayed empty until the user
asked why. Fixed in v1.17.0 by a fourth tier (STARVED) and by the wrap's refill rule; the part that
belongs here is the **offer**: one line after their answer, never a listing of the backlog, and never
pulling unasked. Pulling an item means writing its brief on disk — which is work they may not want
done at the moment they asked something else entirely.

---

## The cost note — why the skill tells you not to open it

Established 2026-08-09, when the user asked what each part of the re-entry system actually costs. The
`SessionStart` hook prints the orientation into the agent's context before they type anything, and
the FIRST ACTION rule in `rules/CLAUDE.md` makes the agent relay it whatever they asked. So loading
this skill merely to show the list buys nothing and costs several times the orientation.

That asymmetry is why `next` is trimmed harder than `wrap`: the wrap is only ever read while a wrap
is running, where its size is proportionate. **`next` is read speculatively, by agents that mostly
did not need it.**

**The no-bare-constants rule (2026-08-22).** The cost note used to carry two token numbers and by
that date both were wrong — the second quoted this skill's own out-of-date size as the cost of
loading it. Numbers in an always-loaded file rot silently and are then repeated as fact. Measure
instead.

---

## Step 0 — tidying session titles, and why silence broke it

**2026-08-15: they reported that neither `next` nor `wrap` renames sessions** — in a session where
step 0 had renamed one an hour earlier. The step was ordered to run *silently*, which made it
unfalsifiable, and it could not be defended without re-reading the code. **A mechanism that leaves
no evidence it ran will be reported as broken.** Hence the one-line report.

**Why this is only the retroactive half.** Step 0 fires only if they open *another* session in the
same directory, which for a project they touche monthly may be never. `/cairn:wrap` step 8b is the
primary namer, and it runs at the moment the session's content is actually known.

**Why their own titles win.** Re-titling something they named is worse than leaving a bad auto-title
alone — the title is their index into past work, and overwriting one destroys a landmark they chose.

---

## Step 1 — why some projects carry their own copy of the orientation hook

A repo may ship `.claude/hooks/session_orientation.py` of its own so that re-entry still works on a
machine where the plugin is not installed — a phone checkout is the case that forced it. Prefer the
project's copy when re-running: it is the one that machine actually uses.

---

## Step 1 — the fish tank, and why you must never re-orient mid-session

**2026-08-22.** A mid-session question about silt in a fish tank was answered with five bike queue
items and two watches. The user: *"This should surely not have returned a /next inquiry?"* The cause
was a **compaction refilling the agent's context with the orientation text**, which the agent read
as a fresh session start.

The hook has been guarded against this since v1.7.2, but the judgement is the agent's too: a session
already under way has nothing to re-enter.

---

## Step 1a — why the git check is offered, never run

The user works from more than one checkout (a laptop, and a checkout on a phone), so *"the
files in front of me are the current ones"* stopped being safe. Their instinct, 2026-08-08: *"Or at
least check git status?"* — **checking is right, acting is not.** An automatic `git pull` at session
start mutates the repo before they have said what they want, can hit conflicts, and can rebase over
uncommitted work at the exact moment they are least likely to be watching.

---

## Step 2 — the relay tier: how much reaches them, and when

**2026-08-25.** They opened a session with a self-contained question — the plugin reads v1.12.1 here
and v1.4.2 on the work laptop — and got nine lines of orientation before the answer. The queue was
**empty**, no watch was due, the inbox was empty: the relay carried zero information and still ran
first. All five not-due watches were listed in full, which the rules already told the agent to
collapse. Their words: *"This seems wasteful and might get irritating for other users were I to share
this plugin."*

**The premise needed correcting before the fix.** Measured the same day: the hook costs ~826 tokens
of the agent's context whether or not anything is relayed, and the relay itself is ~150 output
tokens. **The cost was never tokens** — it is their attention and the shape of the first reply. So the
fix targets irritation, and the highest irritation is a relay with nothing in it.

**Why the hook decides the tier and the agent does not.** The obvious fix — let the agent read the
opening prompt and judge — is the wrong one. An agent holding a concrete task rates the task more
relevant than the queue every time; that bias is what the old unconditional `whatever they asked`
clause existed to block (it traces to the original 2026-08-15 packaging, with no incident of its own
behind it). And a session that opens with a specific question is often one where they have lost the
thread on another machine, so suppressing a DUE NOW watch on prompt-shape would be this system
failing at the one job it does that they cannot do themselves. The switch is therefore computed from the
FILE — `urgent` (due watch, inbox, divergence banner, unfinished last session) → `live` (queue items
or decisions) → nothing — and the agent's only latitude is **position, never suppression**.

`SessionStart` cannot see the prompt in any case; it fires before they type. Prompt-shaped gating
would need `UserPromptSubmit` plus a once-per-session guard, and would buy nothing measurable.

**The empty-queue bug underneath it.** `_split_next` returns the whole `## Queue` section verbatim,
prose and all, so a file with no numbered items but an explanatory header still made `if nxt:`
truthy — the hook could not tell "five items" from "a paragraph about why there are none". Hence
`_QUEUE_ITEM_RE` and a real count.

**The separator they asked for.** Under `ANSWER FIRST, THEN RELAY` the switch-over has to be visible:
a `---` rule, then `**Where you left off**`, then the list. Without it the queue reads as part of
the answer to their question.

---

## Step 2 — the list, and everything that has been dropped from it

**Prose instead of a list (2026-08-06).** An earlier version of the rule said "two or three lines",
and a session duly compressed five items into *"Top of the list is confirming rev 180 …, followed by
deciding …"* — no numbers, no effort, models on one item only. **Short applies to the prose around
the list, never to the list.** They pick by number; a paragraph makes them count commas to find item 3.

**The brief links (2026-08-21).** They asked whether a `/cairn:next` relay would give them a clickable
brief link and the honest answer was no. The links were sitting in the agent's context the whole
time and the prescribed format dropped them. The link is *not* how an item starts — *"do 1"* still
means the agent reads the brief off disk — it is for choosing between items, or seeing what one
involves before committing a session to it.

**Never invent a brief path.** A queue item with no brief is a real defect, and inventing a plausible
path hides it instead of surfacing it at the next wrap.

---

## Step 2a — why decisions are a separate list

Added 2026-08-16: five decisions had been living as undated prose that a long queue silently
truncated. They are **theirs** to answer — an agent offering to "do D1" is offering to make a decision
that is not its own. The `answer:` field says where the answer comes from: `ask <authority>` — the
project names its own authority, code follows it (the literal token here until B19 was one
project's own in-house authority by name — a project-specific proper noun that should never have
been the field's only shipped value) — or `here` (they tell the session, it becomes a change).

**A decision waiting 30+ days is treated like a stale watch** for the same reason: at that age it is
either not really their to make, or not really needed.

---

## Step 3 / 3a — watches

**Why a due watch is the most valuable line in the relay.** A dated watch is hidden until its day,
then surfaces as DUE NOW — that is the whole point: *"check this on Sunday"* stops being something
they carrie. It is the one item in the relay they could not have reconstructed themselves.

**Why staleness must be acted on, not relayed.** They spotted the need for the Watching list on
2026-08-08, when three of five queue slots were `Confirm…` items they could not action. An event-gated
watch has no floor under it, so if the event never happens it sits forever. Their ask, 2026-08-15:
*"all watches should have the date they were added so we know when they are stale."* Relaying
`⚠ waiting 47d` without offering to delete or re-scope it hands the carrying straight back to them.

**Never invent the `added` date.** For a watch you did not write, take it from
`git log -S "**Wn." -- NEXT.md | tail -1`. Stamping it with today resets a clock whose whole purpose
is to show age.

---

## Step 4 / 4a — the three layers

Settled 2026-08-22 (decision D1): `INBOX.md` = capture, `NEXT.md` = the capped working set (5 items,
priority-ordered), Issues = the unbounded backlog at
`https://github.com/example-user/example-repo/issues`. An item displaced from the Queue goes to Issues,
never back into `INBOX.md`.

**Why the orientation reads a cache and this step may call `gh` live.** The hook cannot authenticate
`gh` on their private laptop (a WindowsApps python alias problem — see the wrap's incident record and
`CHANGELOG.md` 2026-08-23), so the backlog line is written by `/cairn:wrap` step 8a into a cache
and is at worst one session stale. Calling `gh` from inside a session is safe because a failure is
visible and harmless; calling it from a hook is not.

**Why an issue filed by someone else is called out.** It is the only item in the entire system they did
not put there themselves — the only one that can genuinely surprise them — so it earns a real read
rather than a relayed title.

---

## Step 6 — the model tier

Corrected 2026-08-09. An earlier version of this step claimed they could not switch model mid-session;
that is only true of **Claude Code switching its OWN model**. They can switch with `/model` or the
selector. So naming the tier is a convenience, not a hard gate — but switching part-way does not redo
work already done at the wrong tier, which is why the check happens *before* starting.

**Made ASYMMETRIC 2026-08-30, and the direction is the whole rule.** A session started item 1
(`Sonnet 5 · medium · AFK/Auto`) while running Opus 5 and reported *"fine to continue, just
costlier than the item asks"*. Correct — but the user named the case it does not cover: *"It should
definitely be a hard stop if it's the other way around, a lower level model or effort chosen for
the task... this is the sort of mistake I make... I forget to look at the model."* Over-tier costs money and produces work that is no worse. Under-tier produces work that is
worse and **looks identical**, and the person who would have caught it is the one who forgot to set
the tier. So: over → one line and carry on; under → stop before any work.

**This does NOT contradict "never build a mechanism whose justification is that they are stuck with
the tier they started on."** It relies on the opposite fact. The stop is cheap *because* they can
switch mid-session — one message, nothing already done thrown away. The forbidden mechanism is one
that refuses to proceed *at all*; this one asks them to press two keys.

**Model is checkable, effort is not.** The agent's own model is stated in its context; the effort
setting is not exposed to it. The rule is therefore enforceable for model and advisory for effort —
which is why both go into ONE stop, rather than the agent asserting an effort mismatch it cannot
actually see, or spending a second round trip asking.

Tiering: Opus for diagnosis, design and anything under-specified; Sonnet for fully specified
mechanical work. Effort `high` when the agent will DECIDE something, `medium` when it will EXECUTE a
decision already written down. Never `low`.

---

## Step 7 — naming the session

**`set_session_title` accepts `session_id: "self"`** — verified 2026-08-20. Four files asserted the
opposite until 2026-08-22, and each built a manual hand-off on top of it, so every session handed them
a rename it could have done itself.

**Reading is genuinely impossible**: `get_session` rejects the current session and `list_sessions`
excludes it (verified 2026-08-22). That is why the agent must *say* what it renamed the session to —
that line, not a condition the agent cannot check, is what protects a title they set by hand.

**Why duplicate titles matter.** Consecutive sessions on one queue item would otherwise get one
name, and two identical rows defeat the list they use to find past work.

**No "Item N" (2026-08-22).** Their words: *"It doesn't help to name every session 'item 1' — if I'm
always running the first issue they'll all be item 1."* Exactly right: the queue is priority-ordered
and they pick the top of it, so the number is the one part of the title guaranteed to be the same
every time, and it eats the front of the line where they are scanning.

**Lead with the project (2026-08-22).** Their session list interleaves every project they touche, and a
subject line alone does not say which repo it happened in. The `cwd` is in the data but not in front
of them.

**Why the placeholder is enough — and why it is still worth setting.** All it has to do is stop the
session being called "do 1" if this one ends without a wrap: a session can run long, get abandoned,
or stop early. The work hasn't happened yet, so the disambiguator that actually
identifies the session (in `atlas`, the rev number) does not exist until the wrap. This step was
skipped entirely on 2026-08-15, which is how the gap surfaced.

---

## The Rules section

**"Just do this directly" (2026-08-20, in `workspace`).** A queue item was dropped to make room for a
new one and logged as trivial enough to just do directly — then never done, because saying so reads
as closure so nothing surfaced it again. The same trap applies to INBOX triage: the phrasing is
usually *accurate*, and the miss happens anyway. **"I told them, so it's handled" is never an
option** — telling them once is exactly what they cannot rely on remembering.

**Why "read the files, never the transcript".** The files are the truth and the transcript is
disposable; that is the entire premise of the system. An orientation answered from conversation
memory is confidently wrong the moment another session has touched `NEXT.md`, which happens often —
they run several agents at once.

---

## Step 2 — why an item carries `AFK/HITL` and a mode (2026-08-28)

The user asked for it directly: *"report if a queued item is AFK or HITL and also which Mode to use
(Auto/Manual/Accept Edits/Plan/Bypass permission)."*

**The gap it closes.** Model and effort say what the work costs; nothing said whether they have to be
*there*. They pick an item by number from a relayed list, and the decision they are actually making at
that moment is a decision about their own attention — *do I have twenty minutes of sitting here, or
am I starting something and walking away?* Before this field the only place that answer existed
was inside the brief, and **the brief is read by the agent, not by them** (`SKILL.md`: they are never
asked to open a file). So the one input to their choice lived in the one place they never looks.

**Mode is worse than model in one specific way, and that is why it is on the line.** They can switch
models mid-session and the work already done survives, so naming the tier is a convenience
(`rules/CLAUDE.md` says exactly that, and forbids building a mechanism that assumes otherwise).
The permission mode is not like that: **an agent cannot switch its own**, so an item that needed
`Plan` and got `Manual` costs them the interruption it was chosen to avoid — at the moment they had
decided to leave.

**Rejected: deriving it from model and effort.** The mapping is not a function. Two
`Sonnet 5 · medium` items, one editing files in one repo (`AFK/Auto`) and one that ends in a push
(`HITL/Auto`), differ only in what the brief does. A derived field that is right most of the
time is worse than an absent one — it is believed.

**Rejected: `effort high` implies `HITL`.** They are orthogonal. Effort `high` means *the agent
will decide something*; whether that decision needs HIM is the separate question this field asks.
An agent deciding on their behalf and reporting back is `AFK · high`, and that is the most valuable
combination in the system.

**Rejected: two named fields** (`attend: AFK · mode: Auto`). Correct, parseable, and twice
the width on a line that is relayed in full on every session start. One glued token reads at a
glance and makes the two contradictions (`AFK/Plan`, `HITL/Bypass`) visible as text. The cost is
paid in `session_orientation.py`: `_FIELD_TAIL_RE` has to anchor on the literals `AFK/` and
`HITL/` instead of a field name, so a third attendance value means a code change.

**Missing field → relay a judgement, labelled as one.** Every `NEXT.md` written before v1.16.0
lacks it on every item, and refusing to say anything would leave them with less than they had. Judge
it from the brief, say that you judged it, and let the wrap write it down.

**The backlog label (same day).** the user asked for `afk`/`hitl` on backlog issues as soon as it
was offered. It is the attendance half ONLY: `gh issue list --label afk` can filter on a label and
on nothing else in an issue, and the mode is not needed until the item reaches the Queue, so it
stays in the body. The one-line summary gained a clause rather than a line — `, 2 runnable AFK` —
because the question it answers (*a machine free, no attention to give it*) was otherwise
unanswerable without opening the backlog, and because a second standing line at every session
start in every project is the tax the footer cap exists to prevent. **Unlabelled means unjudged,
never `hitl`** — filtering an unjudged issue out of an `--label afk` listing silently hides work
they could have started.

---

## Step 2 — `Manual` was the wrong way to protect an irreversible step (2026-08-31, v1.31.0)

`rules/CLAUDE.md` and `README.md` both said **"`Manual` for anything irreversible or
outward-facing"** — pushes, deploys, `gh` writes, deletes. The user rejected it while reviewing a
plan that had put `HITL/Manual` on the hub's items:

> *"Be careful about using 'Manual' as then the human needs to approve every single request not just
> the one that the agent cannot do. If it's in Auto then the agent can run up until it really needs
> the human and then can continue autonomously again."*

**Why the old rule was wrong in exactly the way this system cares about.** It reasoned from the
*riskiest call in the item* to the mode for *every call in the item*. An item that ends in one push
spends its first fifty tool calls reading files, and `Manual` charges them an approval for each —
so the field meant to protect their attention was the field spending it. Worse, it lands on `HITL`
items, the ones already chosen because their attention is scarce.

**What replaces it: the stop belongs in the BRIEF, not in the mode.** *"Commit locally, then stop
and report; the push waits for them"* is a sentence the agent reads and obeys. `HITL/Auto` then runs
freely, stops once at the point that genuinely needs a human, and continues autonomously after their
answer. The brief already had to say **where** a `HITL` item stops (`SKILL.md` step 6) — so the
guarantee was already there, and `Manual` was a second, blunter copy of it.

**This is not a licence to drop the mode field.** `Manual` keeps its row for the rare item where
each step genuinely warrants review — an unfamiliar destructive sweep, a first run of something
that deletes. The rejection is of `Manual` **as the default for irreversibility**, not of the mode.

**Do not "restore" the old rule on the grounds that `Auto` might not prompt before a push.** That
is true and is the point: the prompt is not the mechanism, the brief is. A mode-based guarantee that
depends on the allowlist is weaker than an instruction on disk, and it cost them dozens of approvals
to buy.

---

## Steps 7a/7b — a started item was indistinguishable from an untouched one (2026-08-28, v1.20.0)

`.claude/.last_wrap` recorded that a session *wrapped*. Nothing recorded that a session *started
an item*, so the plugin's own worst failure was silent: run `/cairn:next`, start item 3, do half
the work, end without a wrap — and `NEXT.md` still shows item 3 queued, byte-identical to an item
nobody has touched. The half-done work exists only in that session's transcript, which they cannot
read and cannot remember. Issue #2; the one path this system did not watch.

**The writer is a `UserPromptSubmit` hook, not a step in this skill.** The obvious home was step 7,
which already renames the session when an item starts. It is the wrong home for the *only* copy:
this marker's entire population is sessions that went off-script, and an agent that skipped the
wrap would have skipped a "stamp the marker" instruction too. Same reasoning as the relay tier
(2026-08-25) — the mechanism has to work when the agent does not. Step 7a keeps a one-line manual
fallback for the case the regex genuinely cannot see (an item started by conversation), and that
is all it is: a fallback, not the mechanism.

**Rejected: matching a bare number, or "do N" anywhere in a sentence.** The regex is anchored at
both ends and re-checks the number against `## Queue`, so `do 3 of those` and a bare `3` answering
a question are both ignored. Missing a real start costs nothing beyond the pre-v1.20.0 status quo;
inventing one produces a warning about work that never happened, in the box that also carries
uncommitted files — the one thing that would teach them to skip it.

### The cry-wolf boundary — every ambiguity resolves to silence

The brief asked for this to be *decided*, not queued back to them. Decided as follows, and encoded
in `hooks/item_open.py`:

- **An orphan must survive a session boundary — it does by construction.** The marker is only ever
  read at `SessionStart`, so anything found there was written by an earlier session. Changing their
  mind mid-session just overwrites it. (The session id is stored anyway, so a `resume` re-firing
  `SessionStart` cannot report a session to itself.)
- **A commit touching the item's files does NOT count as closed.** The QUEUE is the authority on
  whether an item is open, not the diff — commits that leave the item queued are precisely the
  half-done case worth catching. What closes it is the item's title leaving `## Queue`, by any
  route: a wrap, a hand edit, another session.
- **Three things clear it besides a wrap**, all passive: the title leaving the Queue, a `.last_wrap`
  newer than the marker, or a later item start overwriting it. Nothing asks an agent to remember a
  step. A title reworded past recognition reads as *closed*, never as open — silence is the safe
  failure here and nagging is not.
- **It speaks once in full, then one line.** The full block transfers the fact into their attention
  at the moment they can act; a second identical block is alarm fatigue, and that box also carries
  uncommitted files. Going fully silent would delete the fact, so it degrades rather than
  disappears, and dies the instant the item leaves the Queue.

**Rejected: a fourth warning box.** A started-and-never-closed item *is* "the last session did not
finish cleanly" — it rides in that box, which already has the `RELAY FIRST` tier wired to it. The
open-item half is deliberately NOT gated on `uses_wrap_ritual`, unlike the git halves: the marker
can only exist because a session started a queue item in this project, which is a stronger opt-in
signal than a past wrap.

---

## What the always-loaded rules actually cost, and why almost none of it can move (2026-08-29)

Measured under B3 / issue #3, which asked whether `rules/CLAUDE.md` carries rules belonging in a
per-turn hook. **Nothing was moved; the numbers are recorded here so the next agent does not have
to re-derive them, and so nobody quotes them as constants.** Method:
`tools/measure_context.py` (tiktoken `o200k_base`, ±10–15% vs Claude's real tokenizer, deltas
reliable) plus the session transcripts over the 14 days to 2026-08-29. Full working in `BACKLOG.md`
B3.

**The baseline.** `rules/CLAUDE.md` is **5,429 tok** of a **7,646 tok** per-session load in this
project — **71% of everything a session sees before it reads a file** — at ~5 sessions/day. Two
sections are a third of it: `⚡ FIRST ACTION` (1,035) and `NEXT.md — three lists` (1,000).

**The result that killed the obvious move.** Those two sections are gated on "this project has a
`NEXT.md`", which reads as conditional and is not: **11 of the 14 directories under `~/Projects`
have one**, and of 82 transcripts in the window every session outside the eight
`.claude/worktrees/agent-*` subagent runs was in such a project. A rule that applies ~90% of the
time is unconditional, and relocating it to a per-turn channel moves the same tokens into the same
context window. **Test a "conditional" rule against the transcripts before believing it is
conditional.**

**The redundancy that is real is with the HOOK, not the skills.** `session_orientation.py` prints
**0 tokens** in a `NEXT.md`-less project (verified by running it) and 1,066 in this one, of which
the two `[to the agent]` directives are **103 tok** — 41 for the relay tier, 62 for the list shape.
The always-loaded file spends **769 tok** (the tier table, 320; the relay-shape spec, 449) saying
the same two things. `rules/CLAUDE.md`'s preamble defends duplication *with the skills* and is right
to: a skill loads only when invoked. **That defence does not extend to the `SessionStart` hook,
which fires unconditionally in exactly the sessions where these rules apply.** Anyone tempted to
add a rule to `rules/CLAUDE.md` should check first whether the hook already says it.

**Why the recommendation is "compress", not "relocate".** A rule in `rules/CLAUDE.md` survives a
broken, stale or uninstalled plugin; a rule living only in a hook disappears silently in exactly
those cases, which is the unfalsifiable failure this whole system exists to prevent. Three blocks
pass anyway — the tier table, the relay shape, and the two-machines git banner (172 tok) — for one
specific reason: **each is inert without the hook output it formats.** No hook run means no tier, no
queue, no banner, so nothing is lost that was not already lost. Every other rule fails that test and
stays. Total available saving ≈ **660 tok/session, 12% of the file** — real, not large, and there is
no second tranche behind it. Raised as `NEXT.md` **D3**; their call, not an agent's.

**The two channels that were dismissed, with the numbers.** `UserPromptSubmit` injection of a brief
on "do N": "do N" is only **5.8% of user turns** (30 of 515), so it would be cheap — but the brief
is text the agent already reads with a `Read`, so the token delta is **≈ 0**. It is a reliability
change, not a context-cost one, and must never be argued as the latter. `PostToolUse` cannot change
the call it observes, so it is worthless for injection — but it **does fire for subagent tool
calls**, verified 2026-08-29 by a headless `claude -p` dispatch (payload carried `agent_id` and
`agent_type`; the parent's own `Agent` call fired separately with `agent_id: null`). That settles
B17's stated blocker. Hook spawn cost on this machine: **51 ms**, or 80 ms if it shells out to
`git rev-parse` — so resolve a git toplevel by walking parents in Python. At 18.3
Edit/Write/session the tax is **0.93 s/session**; matching `Bash` too costs 2.97 s. **Cost does not
decide the matcher** — `file_path` being structured does.

## v1.29.1 — the compression D3 asked for, and the number it actually saved

B3/D3 (answered yes 2026-08-30) compressed the tier table, the relay-shape spec, and the
two-machines/git-banner block in `rules/CLAUDE.md` to one-line pointers, per the reasoning above:
each is inert without the `SessionStart` hook's own output. Kept verbatim: the "moving the queue
below the answer is your only latitude" guard, the "don't re-decide the tier" guard, and the
`/cairn:next` outranks `STAY QUIET` exception — the hook prints *which* tier, never these.

Measured with `measure_context.py`'s tokenizer against a simulated post-install file (the repo
edit predates reinstall): 5,750 → 5,014 tokens, **736 tok/session saved**. Higher than the 500
the brief re-estimated after v1.27.0's tier-mismatch rule ate into the original 660 — the original
three blocks were larger than that rule cost.

## B20, third instance — the README asserted an absence and was wrong for weeks (2026-09-04)

`README.md` said, in the "two things the plugin doesn't do" section, **"A tool with no
`SessionStart`-equivalent (e.g. Cursor)"**, and the work-side `~/.cursor/skills/next/SKILL.md`
said **"Cursor has no `SessionStart`-equivalent hook yet"**. Both were false. Cursor documents
`sessionStart`, `beforeSubmitPrompt`, `postToolUse`, `stop` and `sessionEnd`, plus `preToolUse`,
`beforeShellExecution`/`afterShellExecution`, `beforeReadFile`, `subagentStart`/`subagentStop`,
`preCompact` and `workspaceOpen` — events Claude Code has no name for.

**Nobody had looked.** The claim was inferred once, written into a distributed README, and then
re-read as a fact by every session that touched the adapter design — which is why B2's adapter half
sat blocked from 2026-08-22 to 2026-09-04. It took handing the repo to a Cursor session for anyone
to read Cursor's own `create-hook` skill.

**Corrected 2026-09-04**, and the correction is left visible in the README rather than silently
patched — the paragraph now says what it used to claim and why that was wrong, because a reader who
remembers the old sentence needs to know it was retracted.

**The rule, which is B20's:** write **unverified**, never "none". The cost is asymmetric and
obvious in hindsight — "unverified" invites a five-minute check, "none" closes the question and
takes a backlog item with it. Two adjacent claims from the same session show the same shape and are
worth keeping as calibration: *"Cursor writes no transcript"* (it writes its own, in a schema
`timesheet.py` cannot parse — B65) and *"a second writer needs a branch or a worktree"* (a branch
shares the dirty tree and is not isolation at all — B55). Neither was measured before it was
written down.

---

## Step 3a — the stale-watch flag asserted an outcome it cannot observe (2026-09-02, B44)

The orientation printed *"the trigger may never come. Worth deleting or re-scoping, not carrying"*
for any event-gated watch past 30 days, and this skill's step 3a told the agent to act on it. Both
were reading the age of the `added` field, which measures **how long nobody LOOKED**. From inside
the system that is indistinguishable from *"the event happened and nobody noticed"* — nothing
anywhere records a check.

**Measured in `atlas` 2026-09-02.** Eight watches (W74–W81) flagged at 36–51 days.
`dev/peek.py activities --days 55` showed W74's trigger had fired on 07-31, 08-03, 08-05, 08-24,
08-26, 08-28 and 08-31, and W78's on 08-04 and 09-01 — seven firings and two, none noticed. So the
flag was arguing to delete eight unverified production changes, one of them a fail-closed gateway
routing change that had never been exercised.

**The damage is asymmetric**, which is why this is a rule and not a wording preference. A watch
that ages because its trigger never fired costs a line of noise. One that ages because nobody
checked is a silently unverified production change, and the old flag actively argued for throwing
it away.

**Rejected: the backlog's own replacement**, *"nobody has checked this in 47 days"*. That is a
second over-claim in the same shape — nothing records checks either, so the sentence asserts a
negative it cannot see. The only supportable claim is the age itself, so both the hook and this
step now state that and **ask for the check** rather than naming an outcome.

**Not built: a machine-checkable predicate per watch** (a command or grep the hook could actually
run), which is the fix that would let the threshold mean what it originally claimed. It changes the
`NEXT.md` watch format and is a separate, undecided design change — see `docs/review/archive/2026-09-05-orientation.md`.

---

## B12 — why the rules payload is written about nobody in particular

**v1.45.0, 2026-09-06.** Until this version `rules/CLAUDE.md` opened by naming one person and their
medical history, and `install_rules.py` writes that file verbatim into every installer's
`~/.claude/CLAUDE.md`. This `SKILL.md` did the same in its opening paragraph and in its frontmatter
`description`, which is always in the model's skill listing.

**The rule that came out of it:** the shipped payload states the MECHANISM. Who the user is, and
how they like work done, is read from `~/.claude/reentry-profile.md` — seeded once per machine,
never overwritten, pulled into context by an `@` import in the managed block.

**The test, and it is NOT "does it name a person":** *would this rule still be correct for a user
with a different working style but the same tooling?* Yes → mechanism, however personally phrased.
No → preference, however impersonally phrased. The second half is what makes it a real test: a rule
can be written in perfectly neutral prose and still encode one person's priorities. B47's *"document
a side quest thoroughly before returning to the main thread"* is the worked example — *record it
thoroughly, never a stub* is mechanism (the justification is token economics, and that holds for
anybody); *before returning to the main thread* is a priority ruling someone else may invert.

**Why this is a CHECK and not a rule on this page.** Every docstring in this plugin was written in
the personal register, because that is how the whole codebase read at the time, and the next one
will be too. `tools/test_payload_clean.py` fails the suite on any of it coming back. A stricter
sentence here is the intervention `docs/decisions.md` D4 records failing twice.

**What the measurements kept.** Hostnames became `ORG-LAPTOP1`/`ORG-LAPTOP2`/`WORKSTATION`, the
employer host became `git2.example-corp.net`, one long-running project became `atlas` — but every
number, date and quoted correction on this page is unchanged. D1's rule for hostnames, generalised:
**the measurement is the evidence, the name is not.** A record stripped of its measurements would
stop being a reason an agent does not reason past a rule, which is the only reason it ships.
