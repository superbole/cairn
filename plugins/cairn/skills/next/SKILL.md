---
name: next
description: Show where this project was left off — the NEXT.md Queue, any DUE watches, and un-triaged INBOX.md items — and start an item on request. Use when the user types /next, asks "where were we?", "what's next?", or opens a session with a greeting and no specific task.
---

# /next — where were we?

The one command that has to work when nothing else is remembered. The user cannot be relied on to
hold state between sessions, and runs several projects; this is how they re-enter any one of them.

**No `NEXT.md` here?** Say so plainly ("nothing queued here"), offer to start one, stop. Never
invent a queue. The exit half is **`/cairn:wrap`** — suggest it when a phase completes.

## Do not load this skill just to relay the queue

The `SessionStart` hook has **already printed the orientation into your context**, along with the
tier that says how much of it to relay and when (`RELAY FIRST` / `ANSWER FIRST, THEN RELAY` /
`STAY QUIET`). "Show me the list" needs nothing from this file — and an explicit `/cairn:next`
outranks a `STAY QUIET`: they asked for the list, so show it.

Load it for what the hook does NOT do: **step 0** (junk session titles), **step 6** (start an item
from its brief), reconciling a stale queue, triaging `INBOX.md`.

**No bare token constants in this file** — they rot silently and get repeated as fact. Measure:
`python "$CLAUDE_PLUGIN_ROOT/tools/measure_context.py" <project-root>`.

## Why these read as blunt orders

Nearly every rule below exists because an agent reasoned its way past it. The incidents, dates,
quotes and measurements are in **`references/incidents.md`**, beside this file. **Read it only when
a rule looks wrong or you are about to deviate from one** — a working re-entry never needs it.

**Steps 0 and 7 are referenced by number** from `rules/CLAUDE.md` and the wrap's incident record.
Do not renumber.

## Procedure

0. **Tidy junk session titles first.** `list_sessions`, and for any non-archived session in **this**
   `cwd` whose title carries no information — "Hello", "Hi", "do 1", "test", "Untitled", a bare date
   — rename it to what it actually was, inferring from `NEXT.md` history, recent commits or
   `search_session_transcripts`. **Their own titles always win**: leave anything sensibly titled alone.
   Don't narrate the sweep — but if you renamed something, say so in ONE line at the end of the
   orientation (*"Renamed one auto-titled session: 'Reentry next' → 'Rev 204 — CTL gap'"*). Silence
   makes the mechanism unfalsifiable.

1. **The orientation has usually already run.** Re-run only if you need it fresh: prefer the
   project's own `.claude/hooks/session_orientation.py` if it has one, else the plugin's
   `hooks/session_orientation.py` under the install directory `/plugin` will show you. If it prints
   nothing, read `NEXT.md` and `INBOX.md` directly — an empty queue is a real answer, a broken hook
   is not.

   **Never re-orient mid-session.** Orientation text reappearing in a running session is a
   compaction refilling your context, not a new session. If they ask *"where were we?"* mid-session,
   answer from what THIS session has done.

1a. **Git divergence banner → lead with it**, before the queue: another machine has work this one
   doesn't, so everything below may be stale. **Offer the pull; never run it unasked.**

2. **Relay the Queue as a LIST, never as prose.** One line per item, the file's own numbers, each
   carrying **model, effort AND attendance/mode** (`Opus 5 · high · HITL/Plan`, not just `Opus 5`)
   and ending with the brief as a markdown link, path copied from `NEXT.md`'s own link — never
   invented:

   ```
   1. The illness brief asks four gates you can't answer — Opus 5 · high · HITL/Plan — [brief](briefs/illness-gates.md)
   2. Set the staging box up to deploy — Sonnet 5 · medium · AFK/Auto — [brief](briefs/staging-deploy.md)
   ```

   They pick by NUMBER. Never summarise the list into a sentence and never drop the numbers, models,
   effort, attendance/mode or links. Keep the prose around the list short — **never the list** —
   and don't send them to a file or a hook transcript instead.

   **`AFK`/`HITL` is what they pick ON when they are short of attention**, and `mode` is the one field
   they have to set HIMSELF before starting (Shift+Tab, or the mode selector) — an agent cannot switch
   its own permission mode. `AFK` = runs to completion unattended; `HITL` = it will stop and need
   them, and the item or its brief should say where. `AFK/Plan` and `HITL/Bypass` are
   contradictions; if you find one in the file, say so and fix it at the next wrap.

   **An item missing the field: judge it from the brief and relay the judgement AS a judgement**
   (*"reads AFK/Auto to me — not stated on the item"*), never silently as fact. Same class of
   defect as a missing brief link, same fix: the next wrap writes it.

   **An item with no brief link stays as it is**, and is a defect to fix at the next wrap. The link
   never replaces reading: *"do 1"* means **you** open the brief. They are never asked to open a file,
   never handed a prompt to paste.

2a. **Surface `## Decisions` separately.** Their to answer, not an agent's to pick up — never offer
   "do Dn". One line each with the `answer:` field (`ask <authority>` | `here`), so they know what
   answering involves:

   ```
   D1. Does this endpoint require an API key? — answer: ask the API docs
   D2. Does a full Z1 commute count as your test? — answer: here
   ```

   A decision waiting 30+ days gets the same treatment as a stale watch (3a).

3. **A DUE watch gets its own line**, with its **model, effort and attendance/mode** and an
   explicit invitation (*"W1 is ready to check today"*) — it is the one thing they could not have worked out for themselves.
   Watches that aren't due collapse to a single line, or drop if the reply is already long.

3a. **A STALE watch (`⚠ waiting 47d on: …`) — the age is time since `added`, so it says nobody has
   LOOKED, not that the trigger never fired** (B44). **Offer to find out whether it fired FIRST**, then
   to delete or re-scope it — once. Measured in `atlas`: of eight watches flagged at 36-51 days,
   two triggers had already fired, seven times and twice. Relaying the
   warning alone moves the carrying back onto them. A watch missing its `added` date: offer to
   backfill from `git log -S "**Wn." -- NEXT.md | tail -1`. **Never stamp it with today.**

4. **Surface INBOX items separately**, say they are unprocessed, and offer to triage them into
   `NEXT.md` items or GitHub issues.

4a. **The backlog is `BACKLOG.md`, and it is NOT the queue.** `INBOX.md` = capture, `NEXT.md` =
   the capped working set, **`BACKLOG.md` = the unbounded backlog** — a file in the repo, so
   reading it costs no network and works offline. **GitHub Issues is where that file SYNCS**
   (v1.18.0), not where the backlog lives; before the inversion a project without a GitHub remote
   had no backlog at all.

   - **They asked to see or triage the backlog** — read `BACKLOG.md`. **If what they are short of is
     ATTENTION rather than time** (*"anything I can just set running?"*, or the orientation says
     `N runnable AFK`), filter to the items marked `AFK`. An item with no attendance field is
     unjudged, not `HITL` — say how many rather than filtering them away silently. Judging them is
     a wrap job; offer it, don't do it here. Pulling one into the Queue means writing or confirming
     its brief on disk and **deleting nothing**: mark it `queued` and leave it, closed only at the
     wrap that finishes the work.
   - **The Queue is EMPTY and the backlog is not** — the orientation prints the tier for this
     (*"the Queue is EMPTY and the backlog has N"*). **Offer, in one line, to pull the top few in;
     do not list the backlog and do not pull unasked.** If they say yes, it is `/cairn:wrap`
     step 7's refill: read the issue bodies, write a brief per item on disk, leave every issue
     open and labelled. An empty Queue with an open backlog is a bookkeeping gap, not a finished
     project — before v1.17.0 it read as "nothing is live" and stayed empty until they happened to
     ask.
   - **The orientation flagged an issue filed by SOMEONE ELSE** — the only item here they did not put
     there themselves, so the only one that can surprise them. `gh issue view <n>`, not the title. This
     is the one thing the local file cannot know, and the only reason the issues cache still exists.

   `BACKLOG.md` missing in a project that clearly needs one, or the sync visibly behind? Don't
   debug it here — `/cairn:wrap` step 8a writes the file and runs `tools/sync_backlog.py`.

5. **Staleness warning fired?** Say plainly that the last session may have ended without wrapping,
   so the queue could describe work already done. Offer to reconcile it against recent commits.

6. **They pick an item ("do 1") → read that item's brief off disk and follow it.** Check the model,
   effort and mode named on the item against this session, **before** starting — they can switch
   (`/model` or the selector; Shift+Tab for the mode), and would rather do that than run a
   diagnosis task on the cheap tier or hit a permission prompt on an item they walked away from.

   **The DIRECTION of a mismatch decides what you do.** Running ABOVE the item — Opus on a
   `Sonnet 5` item, `high` on a `medium` one — is a cost, not a defect: say it in one line and
   carry on. Running BELOW it — Sonnet on an `Opus 5` item, `medium` on a `high` one — is a
   **HARD STOP. Do not start.** Name what to switch to and wait for them.

   They forget to set the tier; that is the entire reason the item names it. Over-tier spends more
   money and the work is no worse. Under-tier produces work that is worse and **looks identical**,
   and the only person who would catch it is the one who just forgot to look. The stop costs one
   message and throws away nothing, because they CAN switch mid-session — it is not the "stuck with
   the tier they started on" mechanism the rules forbid, it is what that fact makes affordable.

   **Your own model is in your context; the effort setting is not.** So check the model yourself,
   and put the item's effort into the SAME stop for them to confirm. Never assert an effort
   mismatch you cannot see, and never spend a second round trip on it.

   **If the item is `HITL`, say WHERE it will need them**, in one line, before starting — *"this
   stops at the push for your approval"*. If it is `AFK`, say that too: it is their cue that they can
   leave, which is the whole reason the field exists.

7. **Name the session after the item, in the same reply that starts it.** `set_session_title` with
   `session_id: "self"` renames the current session.

   - **You cannot READ the current title** — `get_session` rejects it, `list_sessions` excludes it.
     At session start it is an auto-title unless their first message named the session. **Rename it.**
   - **If they asked for a specific title, leave it.** Their own titles always win.
   - **Never duplicate another recent session's title in this `cwd`** — check the `list_sessions`
     you already have from step 0; on a collision, suffix the date (*"code · wrap delta · 08-22"*).
   - **Say in ONE line what you renamed it to.** The title is unreadable, so that line is the only
     thing that lets them correct a rename that landed on a title they set themselves.

   **Format: `<project> · <what it is about>`** — the directory name as-is (`atlas`, not
   `Atlas Coaching`, so it matches what they type), then the subject:

   ```
   code · GitHub Issues as the backlog layer
   atlas · the gate parser and the Z1 test
   lighthouse · route import silently drops waypoints
   ```

   **Never "Item N"** — they always picks the top of a priority-ordered queue, so the number is the one
   part of the title guaranteed to be identical every time. Take the item's own bold title from
   `NEXT.md`. **Lead with the project**: their session list interleaves every repo they touche.

   This name is a **placeholder the wrap overwrites** at step 8b. Don't strain for a clever name;
   name the item.

7a. **The open-item marker writes itself — do nothing unless they did not type "do N".** A
   `UserPromptSubmit` hook (`hooks/item_start.py`) stamps it the moment they say *"do 3"*, so a
   session that starts an item and never wraps is caught at the next session start instead of
   vanishing. It is deliberately not your job: the sessions that produce a half-done item are the
   ones that went off-script, so an instruction you have to remember is the one thing that cannot
   be the mechanism.

   **The ONE case it cannot see** is an item started by conversation rather than by "do N"
   (*"let's look at the fan-out one"*). Then, and only then:

   ```bash
   python "$CLAUDE_PLUGIN_ROOT/hooks/item_start.py" --item 2
   ```

   Nothing clears it by hand — a wrap, or the item leaving `## Queue` by any route, does that.

7b. **The orientation flagged an open item from a previous session** — it rides inside the "did
   not finish cleanly" box, naming the item and the date it was opened. Say it plainly, and say
   what it does and does not mean: the item is still queued **as if untouched**, so there may be
   half-done work in a transcript you cannot read. Offer both directions — resume it, or close it
   out — and do neither unasked. If they ignore it, it degrades to one line at the next start and
   dies the moment the item leaves the Queue; don't re-argue it.

## Rules

- **Never make them paste a prompt.** The brief is on disk; read it.
- **Never answer from this conversation's memory** — read the files. The files are the truth and the
  transcript is disposable.
- **Keep it short.** A wall of text at re-entry is the same failure as a 7,000-line backlog — but
  short applies to the prose around the list, never to the list.
- **"Just do this directly" is only a valid triage if you actually do it in this turn.** Otherwise
  the INBOX item goes to `NEXT.md`, not just into the reply.
