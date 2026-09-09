# A user guide to the cairn system

*Draft — this has not been published anywhere. It describes the mechanism, verified against
the current source (v1.36.0); nothing here has been rewritten for marketing.*

## What this solves

If you run more than one project, switch between machines, or simply have gaps of days or
weeks between sessions on the same piece of work, you've hit the same wall: you open the
project again and you don't know where you left off. Not "what does the code do" — a
capable agent can always re-read the code — but "what was I about to do next, why did I
stop, and is it safe to just start from the top of the file again?"

That question is not answerable from the code. It's answerable only from something that
was written down *at the moment you stopped*, and re-read *at the moment you come back*.
Most projects have nothing that does either half.

This system is built for that gap specifically. It doesn't care why you have it — long
gaps between sessions, several projects competing for attention, memory that doesn't
reliably carry state between sittings, or a team where the person picking a project back
up on Monday isn't the person who left it on Friday. Whatever the reason, the fix is the
same: stop treating "where things stand" as something a person or an agent has to remember,
and make it something that lives on disk, gets read automatically, and gets rewritten
every time you stop.

## The core idea

**A project's state lives in a small set of plain files, not in anyone's head or in a chat
transcript.** A session that produces excellent work but leaves nothing on disk describing
where it stands has failed at the part that matters most — because the next session,
whoever or whatever runs it, has to reconstruct that state from nothing.

Two things follow from taking that seriously:

- **Re-entry has to be automatic.** If picking the files up depends on someone remembering
  to open them, it will eventually not happen. So a hook fires at the start of every Claude
  Code session, in every project, and prints what's queued, what's newly due, and what's
  been left uncommitted — before you've typed anything.
- **Ending a session has to write the file, not just do the work.** A session that writes
  good code and says "let me know if you want me to keep going" has not finished the job.
  Finishing the job means the queue, the history, and the next brief are all on disk when
  the session ends — not held in a transcript that gets closed and forgotten.

Everything else in this system is in service of those two points.

## What this plugin does to your machine

Worth reading before you install, not after. All of it is deliberate; none of it stops to ask you
at the moment it happens, which is exactly why it is written down here.

| What | When, and what it means |
|---|---|
| **It writes your global `CLAUDE.md`** | The plugin's rules go into a marked block inside `~/.claude/CLAUDE.md` — the **always-loaded** instruction file every Claude Code session on this machine reads before you type anything. That block is rewritten on every version change, **including an automatic marketplace update you didn't trigger**. Only the text between the markers is touched, anything you wrote outside them is left alone, and a backup is written first. **This is the largest thing you are trusting**, and it is the mechanism that makes the rules travel between your machines at all. |
| **It writes a profile file** | `~/.claude/reentry-profile.md` is created once from a commented template and then never overwritten without a backup beside it. An `@` import is added to the managed block so it's read into every session. If you point `REENTRY_PROFILE_SOURCE` at a copy in a repo or synced folder, the file is refreshed from there whenever the source is newer — one direction only, never back. A source given as a relative path, or one that resolves inside the project you currently have open, is refused. |
| **It creates three more global files** | A mistake log, a credentials inventory and a machine map, next to the two above. Created **empty**, once. Nothing is written into them unless you ask for it. |
| **It reads sibling repositories** | Opening a project that's opted in checks the git state of up to 25 sibling directories, so it can tell you a *different* project has fallen behind its remote. It only looks at directories that have both a `.git` **and their own `NEXT.md`** — that gate is the boundary, and a repo has to have joined this system to be looked at. Running `git` in a repository consults **that repository's own config** (its pager, its filesystem monitor, its ssh command, its aliases), which is worth knowing before you clone something you don't trust into the folder next door. It reads and reports; it never fetches, pulls or writes. |
| **It makes one outbound call** | The first session after you opt a project in shells out to your issue host, through whichever CLI your remote implies, from a **background process that prints nothing** — it's caching the issue list so session start never waits on a network call. Only in projects that have a `NEXT.md`, and only if that CLI is installed and authenticated. It reads; it uploads nothing. |
| **The context measurement tool runs the project it measures** | Asking how many tokens a project's session start costs means actually **starting** that project — its session-start hooks run and its MCP servers come up. That's what a real measurement is. It's an on-demand tool and never a hook, but **don't point it at a repository you wouldn't open.** |
| **The transcript copier never deletes** | The tool that copies this machine's session transcripts to a folder you name, so another machine can read them, is one-shot and manual. It **never removes anything from that destination**. Whatever your transcripts contain is at that location permanently. |

Everything else stays inside the project you're working in. In a project with no `NEXT.md`, the
plugin is bit-for-bit silent.

## Installing it

This ships as a Claude Code plugin, from a plugin marketplace. The exact commands depend on
which marketplace and plugin name you were given — ask whoever pointed you at this — but the
shape is always:

```
/plugin marketplace add <owner>/<repo>
/plugin install <plugin-name>@<marketplace-name>
```

Then `/reload-plugins` if the install summary asks for it.

**Install it on every machine you work from.** The whole point is one versioned source of
truth instead of a copy per machine that quietly drifts out of step — a plugin update on
your laptop should mean the same rules apply on your desktop, without you having to notice
and copy anything by hand.

A plugin update needs more than a restart to take effect. Updating the source is one step;
telling your local Claude Code installation to actually pull and repin to the new version is
a separate step (typically something like updating the marketplace clone, then updating the
plugin itself) — and only *after* that does a restart pick up the change. If a change you
expected doesn't seem to have landed, check which version is actually installed before
assuming the restart didn't work.

## Turning it on for a project

**Opting a project in is just creating a `NEXT.md` file in its root.** That's the entire
opt-in — there's no config, no flag to flip. A project with no `NEXT.md` gets total silence
from the hook, which is what makes it safe to have the plugin installed everywhere, including
in projects that will never use it.

If you track more than one project this way, each one owns its own `NEXT.md`. There's no
hub file that lists other projects on their behalf — silence from the hook means exactly one
thing, "this project isn't opted in," never "opted in somewhere I have to remember." An
almost-empty `NEXT.md` costs nothing to carry; the ambiguity of a shared tracking file costs
you the moment you forget which projects are actually in it.

## The files

Four files, three of them optional-but-recommended, doing four different jobs. Getting them
confused with each other is the most common way this system stops working, so it's worth
being precise about what each one is *for*, not just what it looks like.

| File | Job | Bounded? |
|---|---|---|
| `NEXT.md` | What's live right now | Queue capped at 5 |
| `INBOX.md` | Zero-effort capture, triaged away every session | Not meant to hold anything long |
| `BACKLOG.md` | Everything else worth doing, unordered | Unbounded |
| `CHANGELOG.md` | What already shipped | Unbounded, but capped per entry |

### `NEXT.md` — the working set

Three lists. Here's a real shape, with invented content:

```markdown
# NEXT — lighthouse

## Queue

1. **Fix the CSV export losing its last column** — Sonnet 5 · medium · AFK/Auto
   Brief: [briefs/csv-export-bug.md](briefs/csv-export-bug.md)
   Rows with an empty final field silently drop that column on export.

2. **Design the new onboarding flow** — Opus 5 · high · HITL/Plan
   Brief: [briefs/onboarding-flow.md](briefs/onboarding-flow.md)
   Under-specified — this should produce a plan to approve, not code.

## Decisions

**D1. Should exports default to CSV or JSON** — answer: `here` · added `2026-06-01`

## Watching

**W1. Confirm the payment webhook works in production** — `Sonnet 5` · effort `medium` ·
`AFK/Auto` · added `2026-06-01` · check after `2026-06-05`

---
Changelog: [CHANGELOG.md](CHANGELOG.md) · Briefs: [briefs/](briefs/)
Aim: ship the redesigned onboarding flow and retire the old signup form.
```

**`## Queue`** — what's actionable *right now*, capped at five items, numbered. Every item
names three things after the title, separated by `·`:

- **model** — which model tier this needs (a design/judgement call needs a stronger model
  than a fully-specified mechanical change; naming it up front means you can set the right
  one before you start, rather than discovering partway through that the work was under-
  powered for what it needed).
- **effort** — `high` when the agent has to *decide* something, `medium` when it's executing
  a decision that's already been made. There's no `low`: the tokens saved rarely justify a
  confidently wrong answer written into a file.
- **attendance/mode**, as a single slash-joined pair — covered in its own section below,
  because it answers a different question than the first two.

Each item also links to a **brief** — a self-contained file on disk with everything needed
to do the work, including *why* any decisions in it were already made, so picking it up
doesn't mean re-opening settled questions. You say "do 1"; you never paste a prompt.

**`## Decisions`** is for something only *you* can answer — not a task for an agent to pick
up. `D1`, `D2`, uncapped, one line each. The `answer:` field says how it gets answered:
`here` (you tell whoever's running the session, and it becomes a change) or a value that
means "some outside authority decides and the work follows" (a design lead, a spec, a client
— whatever plays that role on your project). There's no "do D1" — a decision waits on you
reading it, not on a trigger.

**`## Watching`** is for something waiting on a trigger you can't act on yet. `W1`, `W2`,
uncapped. `check after` is always last, and it's either a date or a description of an event.
A dated watch stays completely invisible until its day arrives, then surfaces as due — that's
the entire point: "check this next Tuesday" stops being something you have to remember,
because the file remembers it for you and the hook surfaces it exactly once it's relevant.
An event-gated watch (no date to key off) instead shows its age, and gets flagged once it's
been sitting a while with nothing checking it — a trigger that never fires is otherwise
invisible forever.

The test for which list something belongs in: **if you genuinely couldn't start it today no
matter how willing you were, it's a watch, not a queue item.** "Confirm the deploy worked in
production" is always a watch — you can't do it until the deploy has happened.

The footer below the `---` is a short pointer (links to the changelog and the briefs
directory, one line on what the project is, one line on where it's headed) — never a history
section. It gets re-read into context on *every* session forever, so it's kept to a handful
of lines on purpose.

### `INBOX.md` — capture, not storage

```markdown
# INBOX

- the search box doesn't clear after a failed query
- ask the design lead whether disabled buttons should still show tooltips
```

Zero-effort capture. A bullet is the whole protocol — you don't have to shape it into a
queue item or a backlog entry in the moment you notice it. It gets triaged at the start of
the next session, into either a `NEXT.md` item or a `BACKLOG.md` entry, and then cleared.
Nothing is meant to sit here across a session boundary; an item with a finished brief
belongs in the backlog, not in the inbox — leaving it here just turns every future session
start into a nag about something that was already triaged.

### `BACKLOG.md` — everything else, unordered

```markdown
# BACKLOG — lighthouse

## B3. Migrate the image uploader to signed URLs
`Sonnet 5` · effort `high` · `AFK/Auto` · added `2026-05-20` · issue `#12` · queued
Brief: [briefs/signed-url-uploads.md](briefs/signed-url-uploads.md)

Dropped from the Queue on 2026-05-28 to make room for the onboarding redesign — still
worth doing, not urgent.
```

The Queue is capped at five on purpose — that cap is what stops `NEXT.md` from becoming an
unreadable multi-thousand-line list over time. But a cap needs somewhere for the sixth item
to go, and this is it: unbounded, unordered (the ordering that matters is the Queue's own
priority order), and a plain file in the repo, so reading or editing it costs no network and
works with no tooling at all.

An item that's currently on the Queue stays listed here too, marked `queued` — it's only
marked `closed` (not deleted) once the work actually lands. That matters because it means a
`NEXT.md` that gets lost or badly overwritten doesn't take the item's brief and rationale
down with it; the backlog is what any copy of `NEXT.md` gets rebuilt from.

Traffic runs both ways: a sixth item displaced from the Queue gets filed here automatically,
and if a session ends with the Queue under three items, items get pulled *back* from here
until it has three again — writing a full brief to disk for each one, not just linking to an
issue number. A queue with fewer than three items sitting on top of a non-empty backlog is a
bookkeeping gap, not a sign the project is finished.

### `CHANGELOG.md` — history, and only history

```markdown
## 2026-06-01 — signed URL uploads shipped

Replaced direct-to-bucket uploads with short-lived signed URLs. Old uploads still resolve;
new ones expire after 10 minutes if unused. Deferred: batch upload UI (filed as backlog B7).
```

Newest-first, one entry per piece of finished work, each kept short (roughly 20 lines is a
reasonable ceiling). This is the *only* place session narrative goes. `NEXT.md` is a queue,
never a history — the moment "what we did" and "what's next" start mixing in one file, that
file stops being something you can scan in ten seconds, which is the entire reason it exists.

A related point worth being explicit about: **this file records what shipped, not why a
rejected alternative was rejected.** If your project makes real design decisions worth
remembering — "we tried X, it cost us Y, so we did Z instead" — that belongs in a separate,
much smaller rationale record (however you want to name it — `docs/decisions.md` is a
reasonable default), one row per decision. The changelog is chronological and capped per
entry, so a reason recorded there is scattered across dozens of dated entries and effectively
unfindable a year later. A dedicated record with one row per decision is the only thing in a
project that a full read of the code and the changelog together *cannot* reconstruct — which
is the actual test for whether something belongs there.

## How a session actually goes

1. **You open the project.** A `SessionStart` hook fires automatically — nothing to type —
   and reads `NEXT.md`, `INBOX.md`, and (if the project syncs to an issue tracker) a cached
   backlog summary. It prints, into the agent's context, whatever is actually live: the
   queue, anything newly due, anything left uncommitted from a session that ended without
   properly wrapping up.

   The hook also decides *how much* of that the agent should say back to you before doing
   anything else, based on what's actually in the file — not on guessing from what you
   typed. If something is time-sensitive (a due watch, an unfinished last session, work on
   another machine that hasn't reached this one), it's relayed first, before anything else.
   If the queue just has ordinary items sitting in it, your actual question gets answered
   first, with the queue offered afterward. If nothing at all is live, none of this shows up
   and the session behaves like a project with no tracking file.

2. **You pick something.** You say "do 1" (or 2, 3…) and the agent reads that item's brief
   off disk — a self-contained file with everything needed to start, so you never have to
   paste a prompt. If the item names a model or effort tier the current session isn't
   running at, that gets flagged before any work starts, not after.

   The moment you say "do 1," a marker gets written recording that this item is now open.
   That's not something you have to do or remember — it happens automatically. What it buys
   you: if this session ends abruptly (a crash, a closed laptop, forgetting to wrap up)
   without finishing the item, the *next* session opens by saying so — "item 1 was started
   and never closed out" — rather than showing the same queue as if nothing had happened.
   Without that marker, a half-done item and an untouched one look identical from disk.

3. **You work.** Ordinary session, whatever the item needs.

4. **You end it — and this is the half most systems skip.** Ending a session properly means:
   a changelog entry describing what happened, briefs written or updated for anything still
   queued, the file committed and pushed, and `NEXT.md` rewritten to reflect reality — read
   fresh from disk immediately before rewriting it, not from whatever the agent remembers
   from earlier in the conversation, because another session (yours, on another machine, or
   a teammate's) may have changed it since. A session that does real work and stops without
   this step leaves the *next* session with a file describing a world that no longer exists,
   and it does so silently — which is worse than an empty file, because an empty file at
   least tells the truth.

5. **The session tells you whether that actually happened — and it is not allowed to just say
   so.** This is the part worth understanding, because it is the one place the system does not
   trust the agent's own account.

   *"Wrapped"* is ordinary English. An agent will produce that word from a clean tree and nothing
   outstanding, without lying and without having run any of step 4 — it is simply what the word
   means in conversation. So the word carries no information about whether the procedure ran, and
   no amount of instruction can give it any. (This is not hypothetical: it happened twice in one
   day, confidently, from real evidence, in sessions that had the rules against it in front of
   them.)

   So the wrap ends by running a small tool that **measures** each step against a hash of your
   tracked files taken at session start, and prints one line:

   ```
   CAIRN SET · 3f119b5df86c
   ```

   The agent quotes that line; it never composes a verdict of its own. There are exactly three,
   and all three come from the tool — `CAIRN SET` (with a receipt id), `CAIRN NOT DUE` (there was
   genuinely nothing to wrap), and `CAIRN OPEN` followed by the steps that are missing. Owning
   only the affirmative would not have helped: *"no wrap needed"* is just as ordinary a sentence,
   so it has to be the tool's to say too.

   **Why the id and not just the coined word.** The word has to be written down in the
   instructions the agent reads *before* wrapping, so on its own it is copyable. The id is a hash
   of the receipt, and a fabricated one fails `--verify`. That moves a false claim from *a
   sentence anyone would write* to *an identifier one command contradicts*. It is a large jump. It
   is not proof, and the tool does not present it as proof.

   **The receipt says what it cannot see.** Four steps leave no residue anyone can read back —
   surveying the tree, the memory pass, renaming the session (the current title cannot be read
   back), and the closing summary itself. Those are marked `?`, never ticked. What you are being
   shown is how much the token is claiming, which is the difference between evidence and
   reassurance.

## Attendance and mode: can you start this and walk away?

Model and effort say what a piece of work costs. They don't say whether you have to be
*there* for it — which is a genuinely different question, so every queue item and every
watch carries a third field for it, written as one token after effort:

```
1. **Short title** — Opus 5 · high · HITL/Plan
```

**`AFK`** means the work can run to completion with nobody watching — nothing it needs is
missing from disk, and nothing it does is irreversible. **`HITL`** means it will stop and
need you at some point, and whatever describes the item should say where. The test isn't
how hard the work is: a high-effort item where the agent makes a judgement call on your
behalf and reports back afterward is still `AFK`. The question is only whether the agent
would ever have to ask you something it can't read off disk.

The half after the slash is the **permission mode** — the actual Claude Code setting
(`Auto`, `Manual`, `Accept Edits`, `Plan`, `Bypass`) you need to have set *before* you start,
because it's the one field an agent can't switch for itself mid-session.

| Mode | For |
|---|---|
| `Plan` | Under-specified work: read-only, produces a plan for you to approve. Always `HITL`. |
| `Accept Edits` | Specified edits across many files; you watch the commands, not every write. |
| `Auto` | The default for both `AFK` and `HITL`: reads, edits, and local tests in one repo. |
| `Manual` | The rare item where each individual step genuinely warrants review. |
| `Bypass` | `AFK` only, and only where the worst case is one repo you can reset. |

One thing worth being explicit about, because it's a natural but wrong instinct: **`Manual`
is not how you protect a single irreversible step**, like a push or a deploy. It gates
*every* tool call, which means you end up approving dozens of harmless reads just to guard
the one action that actually matters — which spends exactly the attention this whole system
exists to save. The better pattern is to put the stop *in the brief itself* ("commit
locally, then stop — the push needs your go-ahead") and leave the item in `Auto` mode. It
then runs freely, stops exactly once where it matters, and continues on its own afterward.

`AFK` paired with `Plan` mode is a contradiction (a plan exists to be approved by someone),
and so is `HITL` paired with `Bypass` (nobody's there to catch anything). Neither should
appear on a real item.

## Clearing a lot of backlog at once (optional)

Everything above is one item at a time. When a backlog has accumulated more small, fully-diagnosed
items than you can work through in order, there is a second mode: several agents in parallel, one
orchestrator collecting the results. The full method is
[running-a-batch.md](running-a-batch.md); what follows is enough to know whether you want it.

**The rule that makes it work is counter-intuitive: partition by FILE OWNERSHIP, not by item
count.** Give each agent a lane of items whose files do not overlap any other lane's. Two unrelated
items that touch the same file belong in the *same* lane. Shared files — the changelog, the
backlog, the queue, the version, the README — belong to nobody but the orchestrator, which writes
them between waves. Split by "four items each" instead and the agents collide on exactly the files
that record what happened, which is the failure the whole scheme exists to avoid.

A few things that come from having actually run it, rather than from reasoning about it:

- **Budget against the shortest binding window.** Roughly 150k tokens and 5–20 minutes per lane
  agent, and 8–10 lanes per five-hour window including the orchestrator. It is the rolling window
  that stops work, not the weekly total.
- **Treat the first wave as calibration.** Report what it actually cost before sizing the next one.
- **Write the tests first if the code has none** — and have them written by an agent forbidden from
  touching production code. A lane that writes tests for code it is about to change will pin the
  current bug as correct behaviour.
- **A batch never pushes.** Everything is committed locally and waits for you, because parallel
  work is exactly when you are least able to watch.

### Reviewing it: `docs/review/` is an inbox, not a library

You cannot review a parallel batch by reading agent transcripts — there are too many and their
sessions cannot be reopened. So every lane writes a **dossier** to
`docs/review/<date>-<time>-<lane>.md`, timestamped with the *run's* start rather than the file's,
with four fixed sections: what changed and why, the verification actually run **with real output
pasted rather than summarised**, anything decided on your behalf, and what it chose not to do. The
orchestrator reads each dossier against its actual diff before committing — a write-up and its code
can disagree silently, and that is the failure neither one alone reveals.

**What is still sitting in `docs/review/` is what has not been accepted yet.** Once a batch is
pushed, its dossiers move to `docs/review/archive/`. That is not tidiness: before the rule,
twenty-five files sat in one flat directory and the only way to tell which still wanted reading was
to open them. An inbox that never empties stops being read — the same failure as a warning that
fires in a routine state. Emptying it is what makes a non-empty `docs/review/` mean *someone owes
this a read*.

**Be warned that archiving is a manual job today.** Moving a dossier breaks every pointer to it, so
the move has to repoint the queue, the backlog, the changelog and the docs in the same commit, and
you grep for the old path afterwards to prove none dangle. Making that a tool rather than a careful
habit is a known open item, not a solved problem.

## Syncing the backlog to an issue tracker (optional)

`BACKLOG.md` works with no network, no CLI tool, and no tracker configured — that's the
baseline, and it's a deliberate one: a backlog layer that only exists when you happen to have
a GitHub or GitLab remote configured is a backlog layer that silently doesn't exist for a lot
of real projects.

Where a tracker *is* available, the file can sync to it — GitHub and GitLab (including a
self-hosted GitLab instance) are both supported, detected from the git remote, using whichever
CLI (`gh` or `glab`) is already authenticated on the machine. **The file is always the writer;
the tracker is the copy.** A sync regenerates issues from what's in the file, closes the
issues of items the file says are closed, and pulls in anything filed on the tracker that
isn't in the file yet (marking it as filed by someone else, since that's the one thing a
local file genuinely can't know on its own).

**What syncing buys you, concretely:** the backlog becomes reachable from your phone, it
survives a lost or wiped machine, and other people can file items into it — none of which a
local markdown file can do by itself.

**What you lose without it: nothing that matters day to day.** `BACKLOG.md` keeps working
exactly as described above — read, written, and pulled from at every session. The only
things you give up are the three above: phone access, survival of a completely lost machine,
and other people writing to the backlog directly. If you're working solo, on one or two
machines you don't expect to lose, syncing is a convenience, not a requirement.

A sync command should always be run with a dry-run flag first if you want to see what it
would do before it does it, and a genuinely malformed backlog file (headings the sync can't
parse) causes the sync to refuse to run rather than silently rewriting the file and losing
whatever it couldn't parse.

## Two more files, kept outside any one project

The mechanism also maintains a couple of small files at the user level (not per-project),
created automatically the first time they're needed:

- **A running mistake log.** An append-only record of things that went wrong in a session —
  something an agent got wrong and had to be corrected, a misstep on your own side logged
  the same neutral way, or a case where this system itself failed to catch something it
  should have. The point of keeping it in one place rather than per-project is that a
  pattern repeating across several projects is only visible if there's one file it all lands
  in.
- **A credentials inventory.** Which secret (a token, a key) lives on which machine, how
  it's stored, and when it expires — names and locations only, **never a value**. The point
  is that rotating or revoking a credential becomes a checklist read off this file instead of
  a memory test that fails the moment more than one machine is involved.

Neither of these needs any setup. They're created empty the first time a session runs
anywhere on a machine that doesn't have them yet, and stay silent otherwise.

## The tools you can run

Every tool in the table below is **report-first**: it tells you what it found and changes nothing
unless you ask. None of them need a network, and none are wired into session start — a missing
optional thing is not news every session. (That is a claim about these tools, not about the whole
plugin — what the plugin itself writes is listed under
[What this plugin does to your machine](#what-this-plugin-does-to-your-machine).)

| Command | Answers |
|---|---|
| `check_install.py` | Did the plugin update actually land on this machine? Reports the three versions that can disagree — what the repo ships, what is installed, and what is in the rules block the agent actually reads. Also reports **issue-tracker readiness** for the project you run it in: which host your `origin` remote implies, whether that CLI is reachable, and whether it is authenticated **to that host specifically** — the common trap is a CLI logged in to the public service while your remote is a self-hosted one. |
| `wrap_receipt.py` | Was this session actually wrapped, or does it only look like it? `--check` reports the current verdict without recording anything; `--verify <id>` says whether a receipt id someone quoted at you is real and still covers the current commit. The one check whose answer you cannot get by looking at `git status`. |
| `check_repos.py` | Did work this session sent into *other* repos actually land? Every other check looks at the repo you are sitting in, so a fan-out can leave several dirty trees while this one is spotless. |
| `check_exits.py` | Which other projects ended a session dirty or unwrapped, and how long ago. The warning fires when a session ends — but it fires *into* that ending session, and then into the next session in that same project, which may never come. This reads the records back across every project. |
| `validate_next.py` | Does every queue item and watch actually say whether you can start it and walk away? Checks model, effort and attendance/mode are present, that watches carry a date, and rejects the two combinations that are contradictions. |
| `check_credentials.py` | Which credentials does this machine hold that your credential inventory has never heard of? **Names only, never values**, and it never writes rows — an expiry it cannot read is worse invented than missing. |
| `timesheet.py` | What did you work on this week, and for how long. Reads timestamps already in your session transcripts; captures nothing new. |
| `run_tests.py` | Runs the plugin's own test suite. Reports three outcomes, not two: pass, fail, and **timeout** — a timeout means *no answer*, which is not the same as a wrong answer, and conflating them turns a busy machine into a false alarm. |

### One more file, outside any project

`MACHINES.md`, next to your other global files, maps a hostname to the short id your queue items
use. It lets an item marked *"run on the desktop"* be **checked** rather than trusted to be read.
It is created empty, and an empty table simply means those annotations are never checked — which is
the safe failure. The warning fires only on a positive mismatch between two machines it knows;
never on an unrecognised host, because a check that cries wolf every session is worse than one that
stays quiet.

## Telling when something's wrong

A few things are worth knowing exist, so a genuinely broken piece of state doesn't sit
unnoticed:

- **A malformed `NEXT.md`.** The same parser that reads the file for the session-start hook
  can be run standalone to check it — it reports things like a watch missing its trigger
  date, a queue item with no model/effort/attendance field, or a decision missing when it
  was added, without printing the whole queue.
- **Work that was sent into another repo and never actually landed there.** If a session (or
  an agent working on its behalf) writes into a sibling project, that project's own git
  status says nothing about it from where you're standing. A separate check can report,
  across every repo touched during the session, which ones still have uncommitted or
  unpushed changes.
- **A project that was left dirty a while ago and nobody's been back.** The same idea run in
  reverse — reading back across every project this system has ever seen a session end in,
  reporting which ones ended with uncommitted work and how long ago, entirely from local
  records, with no network call needed.
- **A session that was reported as wrapped but wasn't.** The single hardest thing to notice,
  because the report is prose and the evidence for it — clean tree, nothing unpushed — is real
  and points the wrong way. The wrap's own receipt can be re-read at any time, and the *next*
  session checks the last one automatically and says so if it was `OPEN`, or if commits landed
  after it. You are never asked to remember to check.
- **A plugin update that hasn't actually taken effect on this machine.** Because the update
  and the "apply it" step are separate (see Installing it, above), it's worth being able to
  check directly what version is actually installed, versus what's been pulled into a running
  session's rules, rather than assuming a restart was enough.

Every **check** in this section is designed to *report* — to tell you what it found and leave the
acting to you — and never to fail the session it's checked from, because a broken checker should
never be able to take down an otherwise-working session.

That is a rule about the checks, and it is worth being exact about its edges: the plugin as a
whole *does* write, without asking, in the places listed under
[What this plugin does to your machine](#what-this-plugin-does-to-your-machine) — most
consequentially the managed block in your global `CLAUDE.md`. What none of these checks do is
change your work.

## What this deliberately doesn't do

- **It doesn't manage a portfolio for you.** Each project's `NEXT.md` is its own thing; there
  is no cross-project dashboard bundled in, and "which of my projects needs attention today"
  isn't a question this mechanism answers on its own. If you track many projects, that's a
  separate concern layered on top, reading each project's own file — not something this
  system tries to be.
- **It doesn't guess.** Anywhere the mechanism can't tell something for certain — whether a
  hostname it doesn't recognize is really the machine an item was meant for, whether a git
  fetch that failed means you're actually behind or just offline — it says so plainly rather
  than assuming, because a wrong assumption stated confidently is worse than an honest "I
  don't know."
- **It doesn't touch your work without asking.** It will tell you your checkout has fallen
  behind the remote; it will never pull for you. It will tell you a sync would create or close
  issues; a plain preview mode exists specifically so you can see that before it happens. The
  exception, and it is a real one, is its own installed footprint: the managed block in your
  global `CLAUDE.md` and the files it creates under `~/.claude` are written on install and on
  update without a prompt, because a `SessionStart` hook has no way to ask. Those are listed in
  full under [What this plugin does to your machine](#what-this-plugin-does-to-your-machine).

## Shipping a change (maintainers)

Only relevant if you are editing the plugin's own source. Editing the repo does nothing to a
running Claude Code, and neither does restarting it — the install is pinned to a version and a
commit SHA, and startup loads that pinned path without contacting the host.

Four steps, and the middle two are the ones that get forgotten:

```bash
git push                                    # 1. the source
claude plugin marketplace update superbole    # 2. fetch the marketplace clone
claude plugin update cairn@superbole        # 3. repin to the new version
                                            # 4. THEN restart Claude Code
```

**Bump `plugins/cairn/.claude-plugin/plugin.json`'s `version` in the same commit as the change.**
Step 3 resolves by version, so an edit shipped without a bump can leave the pin looking current
while the files are stale.
