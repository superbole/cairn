# Re-entry — user-level rules

Applies to every project on **every machine the `reentry` plugin is installed on**. Project
`CLAUDE.md` files add to this, they don't replace it.

**You are reading a GENERATED file. The source is `rules/CLAUDE.md` in the plugin** — edit it
there, bump the plugin, reinstall. An edit made inside the `reentry:begin` / `reentry:end` markers
is overwritten on the next version bump, silently. Machine-local notes go OUTSIDE the markers,
where the installer never touches them.

**Rules here that also appear in `/cairn:next` or `/cairn:wrap` are duplicated ON PURPOSE.**
A skill only loads when it is invoked, and the sessions that break these rules are the ones that
never invoked it — this is the copy that is always in context. Do not dedupe them away.

**Why each rule exists is recorded elsewhere, not here.** Every rule below was written because an
agent reasoned its way past it or a measurement contradicted it; the incident record lives in
`skills/next/references/incidents.md` and `skills/wrap/references/incidents.md` — in the plugin
source, and in the installed copy under `~/.claude/plugins/cache/<marketplace>/cairn/*/`. **Read
the relevant one before deviating from, weakening, or deleting any rule on this page.**

## The assumption every rule here rests on

**The user cannot be relied on to hold state between sessions.** Whether that is memory, several
projects running at once, long gaps, or simply a preference for working off disk is theirs to say
— it is in their profile, and the mechanism does not need to know which. Reported by a user about
a session that ended with good work and no way back into it: *"You've suggested that this is a
good point to stop, but I don't really know how to pick it back up."*

**Re-entry is the bottleneck, not the code.** A session that produces excellent work and no
recoverable entry point has failed at the part that matters most.

### Never ask the user to remember anything — write it down

If you catch yourself typing *"worth watching over the next few days"*, *"keep an eye on"*,
*"check back after"*, or *"if X happens, do Y"* — **stop**. That is a queue item with a brief, or
a dated watch, not a sentence in chat. Reported 2026-08-06, on being handed exactly that: *"As if
I'm going to remember that!"*

**Finishing the work is not a licence to hand over a loose end afterwards.** This applies to
anything with a future trigger, including work you consider done.

### Say explicitly when it's a good time to stop

Natural breakpoints are easy to miss from inside a session. Say so plainly when a deploy lands
cleanly, a phase completes, or the work is about to pivot — but only once re-entry is written to
disk.

### The WRAP VERDICT is a QUOTATION — you never compose one

Any time you report on the state of the session, the verdict is one line, **produced by a tool and
quoted verbatim**:

```bash
python "$CLAUDE_PLUGIN_ROOT/hooks/wrap_receipt.py" --check     # any time, reports only
python "$CLAUDE_PLUGIN_ROOT/hooks/wrap_receipt.py" --record    # the wrap's own final step
```

Add `--held` **only** on the `AFK` path where the push was deliberately stopped; it turns on an
alert whose shape an ordinary successful push also has.

It prints exactly one of **`CAIRN SET · <id>`**, **`CAIRN NOT DUE`**, **`CAIRN OPEN`** with the
steps that are missing, or **`CAIRN UNKNOWN`**. **All four come from the tool — including the
negatives.** *"No wrap needed"* is ordinary English and an agent produces it without lying, which
is precisely how a diligent impersonation became indistinguishable from a wrap (twice,
2026-09-06). A coined token with a receipt id cannot be produced by speaking English.

**`CAIRN UNKNOWN` is NOT `CAIRN OPEN`, and reporting it as one is a bug.** `OPEN` means a required
step was **measured** not to have run. `UNKNOWN` means the steps could not be measured at all —
almost always because this session started somewhere other than the project it worked in, so no
session-start baseline was stamped for it. **Relay it as what it is**: the wrap may have run in
full, the tool cannot say, and nothing here is evidence that anything was skipped. Do not
"upgrade" it to `SET` on the strength of what you remember doing — that is the composed verdict
this whole mechanism exists to prevent — and do not relay it as `OPEN`, because an `OPEN` that
cries wolf teaches them to discount the `OPEN` that does not.

**If you have no token, you have no verdict.** Say that plainly — *"I cannot produce a wrap verdict
— `wrap_receipt.py` did not run"* — and never substitute an account of what you did.

*"Everything committed and pushed"*, *"all three repos clean"*, *"0 0 against origin"*, *"wrapped"*
and *"no wrap needed"* are **not verdicts.** They leave the user to derive whether a wrap is still
needed, which is exactly the thing they cannot hold. Quote the token first; put the evidence
underneath if it is worth showing.

`--record` reads the archive-offer state live and prints it beside the token; a `PENDING` there is a
declined archive offer from earlier this session, and it rides along with the verdict in the same
reply. (`hooks/archive_offer.py --check` still answers that question on its own.)

**A clean tree is not a wrapped session, and neither is `.claude/.last_wrap`** — a marker inherited
from two sessions ago is indistinguishable from a fresh one, which is the state both false reports
were made in. The receipt is what tells them apart.

## The re-entry system (global since 2026-08-08; a plugin since 2026-08-11)

The mechanism ships as the **`reentry` plugin**. **Install it on every machine the user works
from**; that is what removes the reason for per-machine copies. The **content is per-project**:

| Global — the plugin, one versioned copy | Per-project |
|---|---|
| the `SessionStart` hook (fires automatically) | `<project>/NEXT.md` |
| `/cairn:next` — re-enter work | `<project>/INBOX.md` |
| `/cairn:wrap` — end a session cleanly | `<project>/BACKLOG.md` (everything not queued) |
| the rules in this file | `<project>/CHANGELOG.md` (finished work) |
| `~/.claude/reentry-profile.md` — the user, not the mechanism | the project's **rationale record** (why it is like this) |
| | the briefs `NEXT.md` links to |

Plugin skills are namespaced, so the command is `/cairn:next`, not `/next`. It is rarely typed
— the hook fires on its own — but say the full name if you refer to it.

**Finished work goes to `CHANGELOG.md`, never into `NEXT.md`.** Newest-first, entries under ~20
lines. There is no "Done" section in `NEXT.md` and inventing one is a bug: the hook treats
everything after a `---` as a verbatim footer, so a Done block is just echoed straight back as
noise. **That footer is a pointer with a hard 8-line budget — nothing dated, nothing narrative.**
It is re-read into context on every session forever, and a *"Session of …"* paragraph there has
cost over a thousand tokens per session before now.

**The footer also carries ONE line on where the project is GOING.** The rest of the system is
near-term by construction — the Queue is capped at 5, Watching is triggers, the backlog is an
unordered list — so nothing anywhere states a destination, and without one there is no axis to
prioritise against. One line, present tense, what *done* looks like for the current phase. It is a
criterion, not a plan: it is what lets a wrap close a backlog item as *"no longer serves the aim"*
instead of letting the list grow forever. It shares the 8-line budget and the same prohibition —
nothing dated, nothing narrative. **Re-confirm it at every wrap**; a stale one is worse than none,
and it is in front of the user every session, so say so when it no longer matches the work.

### The rationale record — why the project is the way it is

`CHANGELOG.md` says **what shipped and when**. It cannot say **why, and what was rejected** —
it is chronological and capped at ~20 lines an entry, so a reason is scattered across dated entries
and findable only by grep. One long-running project's reached 792 KB / 10,204 lines this way.

So every project keeps a **rationale record**: `docs/decisions.md`, or whatever the project already
calls it (this plugin keeps two, as `skills/*/references/incidents.md`). **A row per decision,
naming the option that was rejected and what it cost.** No narrative, no status, no dates-as-history
— status is `NEXT.md`, history is `CHANGELOG.md`.

**Write a row when a decision is MADE, not when it is proposed.** The `## Decisions` list in
`NEXT.md` is the *open* question; this file is where it goes once answered — the two are opposite
ends of the same thing, never the same file.

**Rationale is the only thing in a repo that cannot be re-derived from the repo.** That is the test
for what belongs here, and it is why this is a spec file while `ARCHITECTURE.md` is not: an
architecture doc describes a moving target, goes confidently stale, and is mostly re-derivable from
the code. Keep one if a project earns it; the system does not ask for it.

**Read the relevant record before deviating from, weakening, or deleting a rule** — an agent
reasoning past a rule because the reason lived somewhere it did not read is the exact failure this
file exists to prevent.

**Opting a project in is just creating `NEXT.md`.** A project without one gets total silence from
the hook — no noise, nothing to configure.

**Portfolio membership IS having a `NEXT.md`** (2026-08-31) — every tracked repo owns its own, and
no project is tracked from a hub on another project's behalf. That is what makes silence mean one
thing: *not in the system*, never *tracked somewhere you have to remember*. An almost-empty
`NEXT.md` costs nothing to carry; the ambiguity it removes has cost a real re-entry.

**Numbers are per-file, so QUALIFY them whenever the conversation spans projects** — say
`<project> D1`, not a bare `D1`, once more than one project's list is in play. Requested
2026-08-31, after two different D1s arrived in one reply. Same rule as never citing a bare issue
number across hosts. **Inside a single project's own session, plain `D1` and `W3` are correct** —
the prefix is verbose, so it buys clarity only where there is real ambiguity to remove.

### In a project that has NO `NEXT.md` — offer, once, at the right moment

Silence is correct at session *start* — an unrelated repo should not be nagged — but silence at
the *end* is how a project stays outside the system forever, and this file is the only thing that
knows the system exists. So: **when a session in a `NEXT.md`-less project produces work with a
future** — an unfinished thread, a "we should also…", a thing to check after a deploy — say so
plainly and offer to start a `NEXT.md`. One sentence, once, at the natural stopping point. Don't
pitch it at the top of the session, don't repeat it if it is declined, and never create the file
unasked: a queue nobody asked for is a file nobody reads.

If the answer is yes, write `NEXT.md` with the `## Queue` and `## Watching` lists below and a brief
per item, exactly as described here — `## Decisions` only gets added once the project actually has
one. There is nothing to install — the hook is already running and will find it next session.

**Do not solve a problem by copying this system into a project.** Fix it in the plugin's own source
repo, bump its version, and reinstall.

### `NEXT.md` — three lists

```
## Queue      actionable RIGHT NOW. Max 5, numbered 1..5. Each names MODEL, EFFORT
              and ATTENDANCE/MODE, and links to a self-contained brief on disk:
              1. **Short title** — Opus 5 · high · HITL/Plan  → [brief](briefs/x.md)
## Decisions  the user's to answer, not an agent's to pick up — no "do Dn". D1, D2,
              ... uncapped. ONE line, no prose body: title, `answer:` field, `added`,
              a link to the full detail (wherever the project keeps its backlog):
              **D1. Short title** — answer: `ask <authority>` · added `2026-08-09`
                                    · → `docs/pending.md`
              `answer:` is `ask <authority>` — the project names its own authority
              (a domain expert, an API doc, a spec), code follows it — or `here`
              (the user tells the session, and it becomes a code or profile change).
              Flagged past 30 days, same as a stale watch.
## Watching   waiting on a trigger. W1, W2, ... uncapped. One shape, fields after the
              bold, `check after` always LAST:
              **W1. Short title** — `Opus 5` · effort `high` · `AFK/Auto`
                                    · added `2026-08-15` · check after `X`
              X is a YYYY-MM-DD date or a free-text event.
```

**`ATTENDANCE/MODE` goes on every queue item and every watch, after model and effort.** It answers
what they don't: *can this be started and walked away from, and what must be set first?*

**`AFK`** = runs to completion unattended. **`HITL`** = it will stop and need the user. **The test:
would the agent have to ask them anything it can't read off disk?** Effort `high` is not `HITL` —
an agent deciding *on their behalf* and reporting is `AFK` + `high`, the most useful pair there is.

**`AFK` is about ATTENDANCE, never about REVIEW.** Outputs get read and real problems get found in
them, so an item that ran unattended **commits locally and STOPS before the push** — and before
`tools/sync_backlog.py`, which writes to the issue host. Report what changed file by file, the
verification actually run with its real output, and anything decided on the user's behalf; then
**end the turn and wait.** Until they say go, record the receipt and quote it — it reads
**`CAIRN OPEN`**, because the marker step legitimately has not run — and add in the same breath
that **the push is waiting on them**. The session stays open; do not archive it. This holds however
the push was reached, not only inside `/cairn:wrap`.

**A `HITL` item PUSHES. Do not stop and ask.** This paragraph exists because the rule above stated
only the `AFK` case, and an agent finishing a `HITL/Auto` item read *"commits locally and STOPS
before the push"* as universal and stopped — reporting *"this item was HITL/Auto, so per convention
I'll stop here before pushing"*, which inverts it (2026-09-08, on a machine migration). `HITL` means
**they are present**; that is the entire content of the field. Stopping to ask an attended human for
permission to push is not caution — it converts a finished item into **one more thing they have to
come back to**, which is the failure this whole system exists to prevent, and it wastes the
attendance that made it `HITL` in the first place. The stop is `AFK`'s alone, and its justification
is that nobody is there to read the output.

**And finishing an item is a WRAP, not a close.** The same session closed the item out of `NEXT.md`,
committed, and stopped — no `CHANGELOG.md` entry, on the reasoning that no repo code had changed. Two
things are wrong with that. Closing a watch **is** finished work and the changelog is the
finished-work record; and `changelog` is a **`REQUIRED`** receipt step, so skipping it means the
verdict is **`CAIRN OPEN`** by construction — the session cannot report a clean finish by its own
tool. When an item completes, run `/cairn:wrap`: changelog, commit, push, rewrite `NEXT.md`, record
the receipt, quote the token.

**Mode** is `Auto` · `Manual` · `Accept Edits` · `Plan` · `Bypass` — `Plan` for under-specified
work, `Auto` the default for **both** `AFK` and `HITL`, `Bypass` only where the blast radius is one
repo a `git reset` undoes. **The user must set it themselves** (Shift+Tab, or the mode selector):
unlike the model, an agent cannot switch its own, so finding out mid-item costs them the re-entry.
`AFK/Plan` and `HITL/Bypass` are contradictions — never write either.

**`Manual` is NOT how you protect an irreversible step** — it gates *every* call, so dozens of
reads get approved to guard one push, which is the attention this whole system exists to save. The
correction, 2026-08-31: *"then the human needs to approve every single request not just the one that
the agent cannot do."* **Put the stop in the BRIEF instead** (*"commit locally, then stop — the push
waits for them"*): `HITL/Auto` then runs freely, stops once where it matters, and continues
autonomously after. Reserve `Manual` for the rare item where each step genuinely warrants review.

**ALWAYS re-read `NEXT.md` from disk immediately before rewriting it, and edit only the parts you
are changing.** Several agents may be running at once, so the copy in your context can be hours
stale — another session may have closed an item, pulled one back from the backlog, or raised a
decision since. A wholesale rewrite from memory silently deletes their work and looks perfectly
correct doing it. Check with `git diff` that the diff is only your intended change. This applies to
any rewrite, not just `/cairn:wrap`'s.

**The test for which list:** if it could not be started today no matter how willing, it is a watch.
*"Confirm rev N works in production"* is always a watch.

A dated watch is **hidden until its day**, then surfaces as **DUE NOW**. That is the whole point —
"check this on Sunday" stops being something anyone carries. An item **blocked** by a watch stays in
the Queue marked `blocked by Wn`; knowing why it can't be picked is information needed *while*
picking.

**`added` is required on every watch**, and it is what makes the *event*-gated ones safe: a dated
watch looks after itself, but an event-gated one has no floor under it and sits there forever if
the event never happens. The hook prints the age of each one (`waiting 12d`), flags anything past
30 days — **that age is time since `added`, so it says nobody has LOOKED, not that the trigger
never fired** (B44) — and calls out a watch with no `added` date rather than accepting it silently.
**Never invent the date** — for a watch you did not write, take it
from `git log -S "**Wn." -- NEXT.md | tail -1`. When a stale watch is flagged, offer to find out
whether it fired FIRST, then to delete or re-scope it; relaying the warning alone just moves the
carrying back onto the user.

### ⚡ FIRST ACTION OF EVERY SESSION — in a project that has a `NEXT.md`

**ONCE per session, in your FIRST reply — never again.** If the orientation text reappears later
in a running session, that is a *compaction refilling your context*, not a new session, and
relaying it there is a bug — **a session already under way has nothing to re-enter.** If the user
asks *"where were we?"* mid-session, answer from what THIS session has done.

**HOW MUCH to relay is not your call — the hook prints the tier** (`RELAY FIRST` /
`ANSWER FIRST, THEN RELAY` / `STAY QUIET`) in its `[to the agent]` line every session. Follow it
literally. **Moving the queue below the answer is your ONLY latitude — never dropping it.** Don't
re-decide the tier because the question felt self-contained; that judgement is the one this system
does not trust an agent to make (`skills/next/references/incidents.md`). The single exception goes
the other way: an explicit `/cairn:next` outranks `STAY QUIET` — the list was asked for, so show
it. If the session opens with a greeting or *"where were we?"*, the orientation IS the answer.

**Relay the queue as the hook already shapes it: a numbered list**, one line per item —
model · effort · attendance/mode · brief link (path copied from `NEXT.md`, never invented) — never
prose, never summarised, numbers never dropped. Same shape for `## Decisions` (its `answer:`
field, no "do Dn" invitation) and for watches (a `DUE NOW` one gets its own line and an explicit
invitation; not-due ones collapse to one line for the lot, dropped if the reply is already long).
**Short applies to the prose around the list, never to the list.**

### More than one machine — lead with the git banner, never pull unasked

The orientation opens with a warning box when the branch has diverged from `origin` — if it
fired, **say so before the queue**, and **offer the pull; never run it unasked.**

### `BACKLOG.md` — the backlog, in the repo, in every project

**`BACKLOG.md` is the backlog; the issue host is where it syncs** (v1.18.0). Before that the backlog
*was* Issues, so a project with no remote had nowhere for a sixth item to go — it was dropped with a
one-line note — and an offline wrap discarded displaced items at the moment attention had already
moved on. The file works with no remote, no CLI, and no network; Issues adds phone access,
survival of a lost machine, and other people's writes. **The file is the writer, Issues is the
copy** — one direction, no merge, and no second authoritative list.

An item on the Queue **stays** in `BACKLOG.md` marked `queued`, and is marked `closed` — not
deleted — when the work lands. `/cairn:wrap` runs `tools/sync_backlog.py`, which derives
everything it does from the file, so an offline wrap loses nothing.

### `INBOX.md` — triage it at the START of every session

Zero-effort ad-hoc capture; a bullet is the whole protocol. Each one becomes a `NEXT.md` item or a
backlog entry, then clear the file.

### `~/.claude/MISTAKES.md` and `~/.claude/CREDENTIALS.md` — global, exist on every machine

Both are created automatically (idempotent, silent after the first run) and live next to this
file, not in any project. **This paragraph is the only reason an agent discovers either one exists
outside of `/cairn:wrap`** — before it was added (2026-09-01), a session that never ran `/wrap`
had no way to learn `MISTAKES.md` was there, and the same mistake repeated inside a single session
because nothing surfaced it sooner. Read both when the moment calls for them; don't wait for wrap.

- **`MISTAKES.md`** — an append-only log across every project: what went wrong (the user's side, the
  agent's, or the cairn system's own), so a recurring pattern can eventually be designed against
  instead of re-corrected each session. `/cairn:wrap` appends to it, but log an entry the moment
  you catch a real mistake — don't hold it for the wrap.
- **`CREDENTIALS.md`** — which secret (a PAT, an SSH key) lives on which machine, stored how, and
  when it expires. Names and locations only, never a value. Update it whenever a credential is
  created, moved, or revoked. **Read it before assuming a shared secret is safe to reuse across
  machines** — one PAT reused everywhere means one leak forces rotation everywhere.

### Session titles are part of the memory aid

The session list is how past work gets found, and auto-titling names a session after the first
message — so real work ends up filed under "Hello", "do 1" or "Reentry next".
`set_session_title` **CAN rename the current session** — pass `session_id: "self"`. Naming takes
two halves; neither is the user's to do:

- **Rename the CURRENT session yourself** — once when an item starts (`/cairn:next` step 7, a
  placeholder naming the item) and again at the close (`/cairn:wrap` step 8b, which knows how
  the work turned out and overwrites it). **The current title cannot be READ** — `get_session`
  rejects it and `list_sessions` excludes it — so the only signal is the transcript: if the user
  asked for a title, leave it; otherwise it is an auto-title, so rename it. Never set a title
  identical to another recent session's in the same directory. **Always say in one line what you
  renamed it to** — that, not a condition you cannot check, is what protects a hand-set title.
- **Rename earlier ones yourself**, at the wrap and at the next session's step 0. Don't narrate
  the sweep, but say it in one line when you actually renamed something.

**The user's own titles always win** — re-titling something they named is worse than leaving a bad
auto-title alone.

**A mechanism that leaves no evidence it ran will be reported as broken**, and cannot be defended
without re-reading the code. That is why every step above reports in one line.

## How work gets done

These are the mechanism's defaults. Where the profile contradicts one, the profile wins — it is
the user's own working style, and this list is not.

- **Model tiering:** the stronger model for diagnosis, design, judgement calls, anything
  under-specified; the cheaper one for fully specified mechanical work with the decisions already
  made. Every queued item names its tier so it can be set before starting.
  **The user CAN switch model mid-session** (`/model`, or the selector); only *Claude Code
  switching its own model* is impossible. Switching part-way does not redo work already done at the
  wrong tier, so naming the tier up front is a convenience, not a hard gate — **never build a
  mechanism whose justification is that they are stuck with the tier they started on.**
  **A mismatch is ASYMMETRIC.** ABOVE the item (a stronger model on a cheaper item, `high` on a
  `medium` one): one line, carry on. BELOW it: **HARD STOP before any work** — name the switch,
  wait. Not the "stuck with the tier" mechanism above but its opposite — the stop is cheap
  *because* they can switch, and it is easy to forget to check; a wrong answer at the cheap tier
  reads like a right one.
  **Check the MODEL, ASK about the EFFORT**: your model is in your context, the effort is not.
- **Effort:** `high` when the agent will DECIDE something, `medium` when it will EXECUTE a
  decision already written down. Never `low` — the saving is small and a confident wrong answer
  written into a doc is the costly failure.
- **Attendance and mode:** say `AFK` or `HITL` before anything starts, and for `HITL` name the
  point it stops at — starting something is a decision about the user's own attention. Flag a mode
  mismatch with this session **before** starting; it cannot be fixed once you are running.
- **Stage commits with explicit pathspecs** (`git add path/to/file`), never `git add .`.
- **Verify, don't assume.** Shown numbers from real calls beat asserted reasoning.
- **Never say a tool, file or capability does not exist without searching in the same turn** —
  and say which search you ran. An absence feels like something you know; it is something you
  look up. A wrong "that doesn't exist yet" is hard to catch from the outside, and the cost is
  rebuilding working code.
- **Record a side quest thoroughly, never as a one-line stub.** A finding that surfaces mid-task
  and is not today's work — a root cause, a "we should check X" aside — goes into the project's
  `BACKLOG.md` (or `NEXT.md`'s `## Decisions`/`## Watching` if it needs the user specifically) with
  what was found, where, what was ruled out, and why it matters. The context was already paid for
  in tokens and tool calls; a stub throws it away and a later session pays for it twice. *Whether
  to chase it now or stay on the main thread is a preference — the profile decides that, not this
  rule.*
- **No bare constants.** Token counts and sizes in an always-loaded file rot silently and are then
  repeated as fact. Measure with the plugin's `tools/measure_context.py` instead of quoting.
