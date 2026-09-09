# Why the wrap's rules exist — the incident record

**You do not need this file to run a wrap.** `SKILL.md` is the instruction; this is the evidence
behind it. Read a section only when a rule looks wrong, or when you are about to deviate from one
— which is the situation every entry here was written to prevent.

Each rule below exists because an agent reasoned its way past it, or because a measurement
contradicted what the file was asserting. Dates are when it was caught.

---

## Step 2 — CHANGELOG length, and never logging undone work

**The ~20-line cap (2026-08-11).** `atlas`'s `CHANGELOG.md` reached 596 KB by accumulating
beautiful long entries and now has to be excluded from that project's search index. Write the
entry you would want to read in six months, not the one that proves how much you did.

**"Trivial enough to just do directly" (2026-08-20, in `workspace`).** A Queue item was dropped to
make room for a new one, logged in `CHANGELOG.md` as trivial enough to just do directly — and then
never done, because a CHANGELOG entry reads as closure so nothing surfaced it again. It sat
untracked for two exchanges before the user caught it themselves. The phrasing was *accurate* — it WAS
trivial — and the mistake happened anyway, precisely because it sounded resolved. "I told them, so
it's handled" is never an option: telling them once is exactly what they cannot rely on remembering.

---

## Step 10 — the archive offer went stranded after the wrap (2026-08-28)

Step 10 asks whether to archive exactly once, right after the wrap it belongs to. On
2026-08-28 the wrap ran, they declined, work continued in the same session, and the WRAP
VERDICT was later correctly re-reported as "no wrap needed" — but nothing reconnected
that verdict to the archive offer, because the two were computed independently. The user
caught it: *"So if 'no wrap needed' shouldn't you offer to archive?"*

**Not the fix:** always offering to archive on a clean tree — step 10's gate (only ask if
they asked to wrap, or agreed when suggested) is real, and offering it unconditionally ends
a conversation they were still using. The actual gap was that a declined offer had nowhere
to live once the turn that asked it ended, so the next verdict had no way to know it was
still outstanding short of re-deriving it from conversation memory — which a long session
or a compaction can silently erase.

Fixed by a marker outside the repo (`hooks/archive_offer.py`, same `state_dir()` pattern
as `item_open.py`): step 10 stamps it on decline, clears it on accept, and the WRAP
VERDICT rule checks it before saying "no wrap needed" or "wrapped." The marker is keyed
to HEAD, not to a session id — it is only ever read back within the session that wrote
it, so there is nothing to disambiguate against a later one.

---

## Step 8a — the backlog was a service, not a file (2026-08-28)

The user: *"Git(Hub/Lab) issues is a first class citizen here in the plugin, should we also
accommodate lower classes such as the pending.md when no repo or issues list has been established
for the project?"* — asked in the same breath as whether the plugin needs an offline mode.

Both questions had one answer, and it was not a tier below Issues. **The local file is the base
case; Issues is the upgrade.** A file needs no remote, no `gh`, no auth and no network, which is
also the exact set of things missing when they are offline — so inverting the two fixed the
no-GitHub-project hole and the offline hole with one mechanism instead of two.

What was actually broken before it:

- A project with no GitHub remote had **no backlog layer at all**. `NEXT.md` is capped at 5,
  `INBOX.md` is capture and explicitly not a parking space, and 8a said "skip if the repo has no
  GitHub remote". The sixth item was dropped with a one-line note.
- In a GitHub project, `gh` failing meant the same thing — and it fails *silently by design*,
  because a wrap must never fail over the backlog. The rule was right; the consequence was that
  displaced items were discarded at the moment they had stopped paying attention.

**Rejected: a local mirror of Issues** (the literal `pending.md` reading of their question). Two
authoritative copies of one list is the "lots of different copies/versions of the file and/or
system" failure they named on 2026-08-08 — the failure this system is a plugin to avoid. One writer,
one direction: the file is written, the sync pushes.

**Rejected: an explicit offline/AFK mode.** A mode they must set before leaving is a mode they will be
on a train without having set, and `gh` failing already IS the signal. Detection is free; a switch
is one more thing to remember, which is the thing they cannot do.

**Rejected: an outbox of pending mutations.** Everything the sync needs is derivable from the file
— no issue number means "file it", `closed` means "close it" — and a second list of intentions can
drift from the list of facts. This is why a finished item is marked `closed` and left for one cycle
rather than deleted: deleting it by hand is the one action that loses the close.

---

## Step 7 / 8a — the backlog had no return leg (2026-08-28)

Displacement was automatic ("do not ask first"); refilling was written down nowhere. So the flow
was one-directional: items left the Queue for Issues and nothing ever brought one back. On
2026-08-28 `agent-reentry`'s own Queue was empty with five open backlog issues, three of them
labelled `afk`, and the orientation reported *"nothing is live"* — because the tier was computed
from `NEXT.md` alone and the backlog was read further down, printed as a fact, and never fed back
in. The user: *"why are we not pulling items from the backlog to next?"*

The `backlog` label's own description had been promising *"picked up when the Queue has room"*
since v1.8.0. Nothing implemented it.

Two halves, and both were needed — a rule with no detector waits for someone to notice, a detector
with no rule reports a state nobody is told to fix:

- **step 7's refill rule** — under 3 at the end of a wrap, pull from Issues up to 3;
- **the hook's STARVED tier** (v1.17.0) — an empty Queue plus a non-empty backlog is its own tier,
  worth one offered line after their answer, never a listing.

**Refill to 3, not to the cap of 5.** The cap exists so the week's real work has somewhere to go; a
wrap that fills every slot from the backlog just moves the stale-list problem into `NEXT.md`.

**Pulling writes the brief and leaves the issue OPEN.** An issue closed on being queued vanishes
from the only layer that survives a lost machine, and a brief that says "see issue #4" costs them a
network round-trip at the exact moment they are trying to start.

---

## Step 5b — the wrap marker

The user, 2026-08-08: *"How do we stop you from doing parts of a wrap before wrapping? I.e.
committing and then leaving it open for a wrap?"*

**The answer was not to stop committing mid-session.** That is correct behaviour and their
two-machine workflow depends on it — unpushed work on the laptop is invisible from the other. The
defect was only that a 70%-done wrap (commit, push, `NEXT.md`, `CHANGELOG`) looked identical to a
finished one. The marker fixes the *visibility*, not the committing.

The steps that get skipped in a partial wrap are exactly the wrap-only ones: `NEXT.md`, the
briefs, doc timestamps, the memory pass. `atlas`'s own `/wrap-session` writes the same
`.claude/.last_wrap` path — one marker, two writers, nothing to reconcile.

---

## Step 7 — re-reading `NEXT.md` from disk

Their instruction, 2026-08-23: *"re-read code/NEXT.md from disk before rewriting it."* Said in a
session that had read the queue at 21:40 and rewrote it at 00:52, while a parallel session wrapped
in between. Nothing was lost that time, but only because the write happened to be a targeted
replacement against a fresh read — **mechanism, not discipline.**

## Step 7 — the `## Decisions` list

Added 2026-08-16, when five queue-shaped *"confirm this"* items turned out to actually be *"you
decide this"* — they needed their judgement, not their labor, and a long queue had been silently
truncating them. Before that they lived as undated prose.

## Step 7 — the watch shape and the `**W` parser gotcha

Two incompatible shapes were in use until 2026-08-15: the current one, and
`**W1 — title · check after \`X\`**` with everything inside the bold, which the hook could not
parse at all and printed as a raw line. The parser now accepts both; write the current one.

`atlas`'s W24 invented a **phantom watch** out of a body paragraph that began with a bolded
`**WORKOUT**`, because the parser splits entries on `**W<digit>`. Guarded since 2026-08-15, but the
digit is the only thing separating the two cases.

`added` became required on 2026-08-15 — their ask: *"all watches should have the date they were added
so we know when they are stale."* An event-gated watch has no floor under it; if the event never
happens it sits there forever with nothing saying how long.

## Step 7 — the footer budget, and what it cost

Re-measured 2026-08-22 by running the orientation hook against the historical `atlas/NEXT.md`
and tokenizing its **stdout** (tiktoken `o200k_base`), with and without the footer:

| `atlas/NEXT.md` at | Footer | Cost | of the orientation | of the 11,682 baseline |
|---|---|---|---|---|
| `923ad7b` — trimmed by hand to "one session" | 65 lines | 1,629 tok | 48% | 14% |
| `166a557^` — what the real trim actually deleted | 91 lines | **2,273 tok** | **56%** | **19%** |

**Both numbers are real and they are four days apart on the same file — that is the finding, not a
discrepancy.** A hand-trim on 2026-08-15 got it to 65 lines; two wraps later the *same day* it was
back to 91, and every rev it described (201–206) already had its own `CHANGELOG.md` entry. A footer
does not drift, it **regrows**. `MAX_FOOTER_LINES` now truncates past 8 lines with a visible
marker, so overrunning is no longer silent.

The `## Done` rule is about a *heading*; the way this actually goes wrong is *prose* — a
*"Session of 2026-08-14: …"* paragraph, which looks like re-entry context and so slips past the
heading rule entirely.

---

## Step 8 / 8a — the three layers

Settled 2026-08-22 (`D1` in `code/NEXT.md`): `INBOX.md` = capture, `NEXT.md` = the capped working
set, Issues = the unbounded backlog. One board per project, not one across all repos — "which
project today" is answered by each project's own Queue item 1.

**Never park a displaced item back in `INBOX.md`.** It happened twice on 2026-08-22 and the second
one arrived with a *"do NOT re-triage"* note bolted on, which is the tell: an item with a finished
brief is backlog, not capture, and parking it there turns every future session start into a nag
about items that are not un-triaged at all.

**Closing the issue is a step, not a nicety.** Their words: *"Otherwise this is pointless and the
list will become stale."* A `CHANGELOG.md` entry is no longer sufficient closure.

**Auto-filing displaced items, without asking**, was their choice on 2026-08-22 over a confirmation
step — displacement happens at the exact moment they are stopping. Issue #1 in `example-repo` was
displaced twice in two days, which is why a matching open title gets a comment rather than a
second issue.

**Why the hook's own refresh cannot be relied on everywhere.** On their private laptop `python`
resolved to the WindowsApps execution alias, which runs in an app container with no access to the
Windows Credential Manager — so `gh` called from any hook reported "not logged into any GitHub
hosts" while the same binary worked fine from a shell, and the app container is inherited by
children, so re-spawning did not escape it. Measured 2026-08-22.

**Fixed on that laptop on 2026-08-23** by turning the `python.exe` / `python3.exe` aliases off
(Settings → Apps → Advanced app settings → App execution aliases); the real interpreter was already
on `PATH`, just behind `WindowsApps`, and the alias won on ordering alone. `gh auth status` from
inside python now returns rc=0, so the hook-spawned refresh works there.

**It is still not safe to assume.** The other machines have not been checked, a fresh Windows
install re-enables the aliases by default, and a failed refresh silently keeps the last good
listing — so the failure mode is a quietly stale backlog, not an error. That is why the wrap still
refreshes.

**Why the cache JSON goes to a file, not a pipe.** Windows PowerShell 5.1 re-encodes anything piped
into a native executable and corrupted this exact payload on its first live run.

---

## Step 8b — session naming

**`set_session_title(session_id: "self")` works.** Verified by doing it, 2026-08-20. Every version
of this step before 2026-08-22 asserted the opposite, and four files built a manual hand-off on top
of that — so every wrap handed them a rename it could have done itself.

**Reading the current title is impossible.** Verified 2026-08-22: `get_session` rejects both
`"self"` and the current id (*"Session self not found"*), and `list_sessions` excludes the current
session. Writing works, reading does not — so any rule that conditions on "is the current title
junk?" is unenforceable, and the one-line report is what makes the rename safe instead. The
2026-08-20 verification rename overwrote a hand-set title minutes old; it was recoverable *because
it was reported*.

**The format is their, 2026-08-22.** On dropping the item number: *"It doesn't help to name every
session 'item 1' — if I'm always running the first issue they'll all be item 1."* Exactly right —
the queue is priority-ordered and they pick the top, so the number is the one part of the title
guaranteed not to vary, sitting in the part of the line they scan first. On leading with the
project: their session list interleaves every project they touche, and the `cwd` is in the data but
not in front of them.

**Why the wrap renames and not only `/cairn:next` step 0.** At wrap time you know what the
session *was*; `next` can only guess from the item it is about to start. And step 0 is
*retroactive* — it fixes an old title only if they open another session in the same directory, which
for a project they touche monthly may be never. Added 2026-08-15, when they pointed out that neither
skill did this.

---

## Step 9 — the close

**No labelled list.** Emitting *"a. … b. … c. …"* leaks this checklist into their reply. It happened
2026-08-09 and they disliked it on sight.

**No paste-ready prompt.** They removed exactly this on 2026-08-09: *"Part of the reason of building
this system was because you would give me a prompt to copy at the end of a session… We're kinda
back there."* It has come back twice since.

**The stop-vs-continue rule (2026-08-22).** A wrap said *"good point to end the session here"* at
**10% context used**, and they pushed back: *"how do you decide to make that recommendation? Our
current used context is 101.8k tokens (10%). What do we carry and what does it cost to start a new
session?"* The recommendation was right and the stated reason was absent, which reads as though the
tank was filling. The rule is inline in `SKILL.md` rather than here, by this file's own test: an
agent demonstrably *did* skip it and gave an unjustified recommendation.

Historical measurement, `code\`, 2026-08-22 (tiktoken `o200k_base`, hook **stdout** not file size).
**Do not quote these numbers as current — run the tool.**

| Loaded by a new session | tokens |
|---|---|
| `SessionStart` hook output | 1,006 |
| `~/.claude/CLAUDE.md` | 3,969 |
| `MEMORY.md` index | 462 |
| **baseline re-paid per session** | **5,437** |
| + one brief, on `do N` | ~900–1,700 |

The harness (system prompt, tool schemas, skill list) is **identical in both cases** and cancels
out of the decision — never quote it as a cost of starting fresh.

**The wrap verdict (2026-08-21 and 2026-08-22).** On 2026-08-21 a session did changelog, briefs,
commit, push, marker, memory and title by hand, said "good point to end here", and left them to ask
*"should it say whether or not a wrap is still needed?"* — having to ask is itself the failure the
rule exists to prevent. Then 2026-08-22: *"Don't tell me 'everything committed and pushed' tell me
'no wrap needed' or 'I suggest we wrap now' or similar."* The rule was already in this skill — but
the skill only loads when invoked, and the session that broke it had never invoked it, which is why
a copy also lives in the always-loaded `rules/CLAUDE.md`.

---

## Step 10 — archiving the session

Two `INBOX.md` captures from 2026-08-23 turned out to be one feature, joined by the tool schema:

```
archive_session(session_id: "self")
  -> "the conversation ends after this tool result"
  -> "This tool ALWAYS prompts the user for confirmation"
```

**The first capture:** a wrapped session stayed in the open list as though it were still live —
exactly the state this system exists to avoid, since the session list is how they find past work.

**The second capture** looked unrelated. They noticed the wrap ended with a permission prompt they
could *cancel*, and that cancelling let them carry on: *"if I want to ask more questions after the
wrap I can cancel it and carry on the conversation instead of the session just ending."* That was
an accident of which tool happened to be called last, and on a machine with broader allowlists it
would silently disappear. `archive_session` makes it deliberate, because it always prompts
regardless of permissions. **So the escape hatch and the archiving are the same step, not two.**

**Known dead end — do not re-investigate.** They checked on 2026-08-23: a session that had archived
itself still showed as "running tools" in the session list, while `list_sessions` reported
`isRunning: false` / `isArchived: true` for it. The data layer is correct; the badge is stale UI in
the client. Nothing in the wrap can fix it and no amount of extra state-setting will. Worth an
upstream report and nothing else.

---

## The no-bare-constants rule

Found 2026-08-22 by a single grep of the shipped plugin — three numbers in always-loaded files,
all wrong, all quotable as fact:

| Where | Said | Actually |
|---|---|---|
| `skills/next/SKILL.md` | orientation is `~780 tokens` | 1,006 |
| `skills/next/SKILL.md` | loading the skill costs `~1,100` | 2,599 — its own old size |
| `tools/measure_context.py` | baseline for `code\` = 3,969 | 5,437 — 27% low |

The tool was the worst of them: it read `SessionStart` hooks from `<root>/.claude/settings.json`,
which stopped being where the hook lives when it moved into the plugin, so it reported zero for the
hook and missed the `MEMORY.md` index entirely. **A stale measuring instrument is why the other two
went unnoticed.** Fixed in v1.9.0.

By 2026-08-24 every one of those "actual" figures had moved again (the orientation to 823, the
baseline to 5,788, `next` to 3,159) — which is the argument for the rule, not against it.

---

## Step 10 (v1.13.2) — the archive prompt isn't a real ask in auto mode

`archive_session`'s own tool-permission prompt was being relied on as the ask. On a session running
`defaultMode: "auto"` in `settings.json`, that prompt auto-approves — the archive happened with no
choice actually made, indistinguishable from the tool just running silently. Fixed by moving the ask
into the close text itself, in chat, before the tool is ever called, in every permission mode — not
just auto. Caught 2026-08-25.

## Queue regex (v1.13.2) — a populated queue read as empty

`NEXT.md` queue items are written `**1. Title**` (bold, matching the format this skill itself
specifies), but `_QUEUE_ITEM_RE` required a bare `1. ` with no leading bold marker. A real,
populated queue was silently reported as `STAY QUIET` by the relay-tier logic — the failure mode is
invisible by construction, since a hook reporting "nothing to relay" looks identical to a project
that genuinely has nothing queued. Caught 2026-08-25.

---

## Step 6a (v1.14.0) — MISTAKES.md, and why "promote to a GitHub Issue" almost didn't ship wrong

The user asked for a running log of recurring mistakes — theirs, the agent's, the cairn system's own
— so patterns could eventually be fixed systematically instead of re-corrected every session.
Global file (`~/.claude/MISTAKES.md`), same pattern as the `CLAUDE.md` rules sync, appended to here.

**The near-miss, 2026-08-27:** while designing the feature, a `NEXT.md` watch drafted "once a
mistake recurs 2+ times, promote it to a GitHub Issue on `agent-reentry`" as the review step —
without noticing that (a) `MISTAKES.md` is about mistakes made in *whatever project they happen in*,
not reentry-plugin bugs, and (b) other plugin users have no access to the user's private repo, so
that can't be a mechanism the plugin builds in generally. Caught by the user, not self-caught. Logged
in `MISTAKES.md` itself as the file's first real entry — the mistake-log feature's own first bug
was a mistake worth logging. The lesson generalises: **when a fix references a specific private
resource (a repo, an account, a URL only this machine can reach), check whether it still works for
someone else who installs the same plugin** before writing it into a general design.

---

## Step 2a and the direction line (v1.15.0) — what was rejected, and why

The user asked (2026-08-27) whether the spec should adopt two files they'd seen in their own projects:
`atlas/docs/decisions.md` and `atlas/ARCHITECTURE.md`. Neither was in it. One is now.

**Adopted: the rationale record.** The evidence was that they had already built it twice without the
spec asking — `atlas/docs/decisions.md` (11 commits) and this repo's own two
`skills/*/references/incidents.md`. Convergent evolution across two mature projects is the signal.
`CHANGELOG.md` cannot absorb it: chronological, capped per entry, and `atlas`'s had reached
792,078 b / 10,204 lines, which is not a document anyone greps for a reason.

**Rejected: `ARCHITECTURE.md` in the spec.** It is the only file here with a *measured* cost
incident — 25,610 b / 403 lines over 57 commits, needing an explicit rescue at rev 231 (13,781 →
6,379 tokens) plus a dedicated project rule ("never read ARCHITECTURE.md and all sub-docs at once").
`NEXT.md`/`INBOX.md`/`CHANGELOG.md` are append-or-delete structures and hard to make *wrong*; an
architecture doc describes a moving target and goes **confidently** stale, which is worse than
absent because agents believe it. It is also largely re-derivable from the code. **The test that
separated them: rationale is the only thing in a repo that cannot be re-derived from the repo.**

**Rejected: `## Aim` as its own section.** This was the original proposal and their question —
*"how much is it going to cost day to day?"* — killed it. Three costs, measured 2026-08-27:
tokens were **negligible** (71 for a realistic 6-line block, o200k_base) and were *not* the
objection. The real one is that `session_orientation.py`'s section dispatch sends any unrecognised
`## ` heading to the **queue** bucket, where it shares `MAX_NEXT_LINES = 24` and truncation cuts
from the end — so a naive `## Aim` would silently push real queue items off the bottom. And fixed
lines at the top of every orientation are the same failure `W6`/v1.13.0 exist to fix. Shipped
instead as **one line in the footer**, which already exists, already has an 8-line budget, and is
already re-read every session: same ranking criterion, no hook change, ~15 tokens.

**Also settled, from the same conversation:** the closed-issues list is *not* a changelog. Only work
deferred long enough to be filed ever becomes an issue (`atlas`: 255 changelog entries, 1 closed
issue), and closure isn't completion — 4 of `example-repo`'s 7 closed issues were closed because
they *migrated* to this repo. Step 8a already had this right (`"a CHANGELOG.md entry is not
closure"`); the inverse is equally true and is now stated in the README.

**The generalisable lesson:** both of their pushbacks were questions, not rejections, and both
produced a smaller, cheaper design than the one being defended. Cost the thing before proposing it.

---

## Step 6 — `AFK/HITL` and the mode on every item and watch (2026-08-28)

Added at the user's request; the full reasoning, and the four rejected alternatives, are in
`skills/next/references/incidents.md` under the same date. What matters on the wrap side:

**The wrap is the only place items are authored**, so it is the only place the field can be got
right. It is written from the brief — the checkpoints where the agent will stop ARE the `HITL`
answer, which is why step 3 now asks a `HITL` brief to name them. *"It'll need you at some point"*
is precisely the thing they cannot plan around.

**Re-check it whenever you re-sort or re-scope.** It is the field most likely to go quietly stale:
an item that was honestly `AFK/Auto` becomes `HITL/Manual` the moment its brief grows a deploy
step, and nothing else about the item changes to signal it. Same class of rot as an effort tag
left over from a bigger version of the work.

**Watches carry it too**, because a watch that comes due is something they start — and a watch is
where *"can I just run this?"* is asked most often, since they are being handed it by the hook on a
day they did not plan around it.

**The hook counts, it does not list.** Every `NEXT.md` in every project predates the field, so a
per-item warning would out-shout the queue in exactly the projects with the most queued. One line
with a count, and it clears itself at the next wrap.

**Step 8a — the `afk`/`hitl` label (same day).** Every backlog issue carries one, and the wrap
labels issues that are ALREADY open whenever it touches the backlog, not just the ones it files.
A label applied only to newly displaced items would make `--label afk` a filter over the newest
slice of the backlog while looking like a filter over all of it — the same class of silent
half-truth as a queue relayed as prose. The mode is NOT a label: it goes in the body, where it is
read once, when the item is pulled into the Queue.

**Why the label creation became a tool.** The rule first shipped as a parenthetical — *"(`gh label
create` them once per repo)"* — inside a step about filing displaced items. That is an instruction
executed once per REPO, which means almost never, by an agent that has no way to tell whether a
previous session already did it. Two failure modes, both silent: the wrap skips it and
`gh issue create --label afk` then FAILS (it does not fall back to an unlabelled issue), mid-wrap,
at the moment they have stopped watching; or the wrap runs `gh label create` every time and prints an
"already exists" error that reads like a broken wrap. `tools/label_backlog.py --ensure` is
idempotent, swallows "already exists", creates all four, and reports in one line — the same shape
as every other mechanism here: **detect and report, never rely on remembering.**

## Step 7 — the wrap checks the `NEXT.md` it just wrote (2026-08-28, v1.19.0)

On 2026-08-28 a watch's `added`/`check after` fields wrapped onto a continuation line while being
hand-typed. `_split_next` and `_entry_age` in `session_orientation.py` read those fields from an
entry's title line only — by design, since a continuation line is where a watch's own prose lives
— so the wrap that wrote it looked clean, and the NEXT session's orientation silently reported "no
added date" for a watch that had one. Fixed by hand in e9c8916, but the wrap that introduced it had
no way to know: nothing ran the parser over its own output.

**Reuse the orientation's own parser, don't write a second one.** `check_next()` in
`session_orientation.py` calls the exact same `_split_next`/`_sort_watches`/`_entry_age`/
`_ATTEND_RE` the SessionStart hook uses, so a wrap-time check and the next session's read can never
disagree — a second implementation would drift from the first the same way the two watch-title
shapes drifted from each other (see `skills/next/references/incidents.md`).

**A `--check` CLI mode, not a new script.** The alternative — a standalone checker script — means
keeping two files' parsing logic in step forever. `--check` skips `_is_reentry_moment()`'s stdin
read (there is no SessionStart payload outside a real session) and every side effect the hook
normally does — rules sync, mistakes-file creation, the network-backed backlog summary — none of
which belongs to a wrap checking a file it just wrote itself.

**Never lets the wrap fail.** Same rule as `sync_backlog.py` (step 8a) and `label_backlog.py`: a
nonzero exit names what to fix, but a checker that itself cannot run (missing Python, a moved file)
must never look like a broken wrap — one line, carry on.

---

## Step 5b — the wrap marker now also closes an open ITEM (2026-08-28, v1.20.0)

v1.20.0 added a second marker: `item_open.json`, written when a session *starts* a queue item, so
that a session which starts item 3 and ends without a wrap is detected instead of looking
identical to an item nobody touched (issue #2, and `skills/next/references/incidents.md` for the
cry-wolf rules).

**Nothing was added to this procedure, on purpose.** Stamping `.claude/.last_wrap` already closes
it — `item_open.py` treats a wrap marker newer than the item marker as proof the item is no longer
half-done — and step 7's `NEXT.md` rewrite closes it a second way, since an item whose title has
left `## Queue` is closed by definition. A wrap that aborts before step 5b correctly leaves the
open item flagged. **Do not add a "clear the marker" step here**: a marker that depends on an
agent remembering to clear it would fire on every clean wrap, which is exactly the alarm fatigue
the feature was designed around.

---

## Step 1a — the 8 repos that were logged done and were still dirty (2026-08-25, v1.24.0)

A fan-out ran the automation-recommender across 8 repos — a mix of hobby hardware projects, a
couple of personal web apps, a home-automation config and a trading bot, none of them the repo
the session was running in — and this repo's `CHANGELOG.md` recorded it finished:
*"every project kept at least one recommendation."* A day later every one of the 8 trees was still
dirty. Nothing had been committed anywhere. Found by accident; fixed by hand on 2026-08-26.

The bad writes had their own cause — `isolation: worktree` pointed each agent at the wrong repo,
forcing writes through `Bash` instead of `Edit`/`Write` — and that was fixed at the time. **The
durable hole was the sentence, not the worktree:** *"recommendation accepted"* was written down as
if it meant *"change committed"*, and no step anywhere asked the 8 repos whether that was true.
Every other check in this plugin looks at the repo the session is running in, and that repo was
spotless.

**A tool, not a checklist line.** The rejected option was a checklist step in whatever drives
fan-out work. It fails twice: this plugin does not own the fan-out prompt, so there is no single
place to put the line; and a checklist item is a thing the agent has to *remember*, which is
exactly what did not happen — in the session least likely to be watched, since a parent that has
dispatched work is one they have walked away from. `tools/check_repos.py` answers the whole question
in one call and reuses `reentry_state`'s git helpers rather than re-deriving them.

**Step 1a, not 5c — position is the whole design.** The obvious home was next to the push, beside
the other git checks. Wrong: the CHANGELOG entry is written at step 2, so by step 5 the false claim
is already on disk and the check can only contradict it. The check exists to constrain what the
narrative is *allowed* to say, so it has to run before the narrative.

**Asked unconditionally, answered in one line.** The trigger is not "if you remember dispatching
work" — that is the failed checklist again. Step 1a is asked every wrap, and a single-repo session
says so and moves on. What the tool cannot do is *discover* the repos: there is no free signal for
"this session wrote next door", and a `PostToolUse` recorder that would provide one is deferred as
its own backlog item. `--known` is the partial substitute — `dirty_tree_warning.py`'s `SessionEnd`
branch now stores `root` in `last_exit.json` (the state dir is keyed by a *hash* of the path, so
nothing could previously map a state directory back to its project), giving a growing list of the
repos they actually works in.

**`[ok]` with a note is the line that matters.** `~/Projects` is itself a git repo on this machine,
so the first run reported `~/Projects/docs` — an ordinary folder, not a checkout — as *"clean,
nothing unpushed"*. git answers for the enclosing repo without complaint, which is the exact
false-verification this tool exists to prevent, reproduced by the tool on its own second test. The
mismatch is now always named and never resolved away silently. Same trap as BACKLOG B13 on the
warning side.

**Reports, never fails.** Nonzero exit is information. A wrap that dies over a check leaves no
`NEXT.md`, which is worse than any dirty repo — the standing rule from `sync_backlog.py` and
step 7's `--check`.

---

## Step 1a — the record replaces the memory (2026-08-30, v1.25.0)

The paragraph above ends *"what the tool cannot do is discover the repos: there is no free signal
for 'this session wrote next door'."* That was true when it was written and is no longer. B3's
measurement on 2026-08-29 supplied the signal, so step 1a now runs argument-first instead of
paths-first.

**What was still broken after v1.24.0.** Step 1a removed the dependency on the agent remembering
to CHECK. It left the dependency on the agent correctly NAMING, and the two fail differently: a
forgotten check produces no output and looks like a skipped step, while a wrong list produces a
confident `N repo(s) checked -- all clean and pushed` that is true of everything it was told about
and silent about the repo it was not. The 2026-08-25 incident was 8 repos; a list of 7 would have
read as a pass.

**Why a `PostToolUse` hook and not a better prompt.** Same shape as `item_start.py`: the sessions
that get step 1a wrong are the sessions that would also have skipped a "remember to list the repos"
instruction. A recorder watching tool calls has nothing to remember. Confirmed empirically before
building it (B3, 2026-08-29): the hook fires for SUBAGENT tool calls, carrying `agent_id` and the
parent's `session_id`, so a fan-out — the case that produced the incident — is visible.

**`cwd` is the wrong field, and quietly so.** The payload's `cwd` is the parent project's, not the
written file's tree, so a recorder built on it would answer "the project" for every subagent write
and record nothing at all. `tool_input.file_path` resolved to its git toplevel is the only correct
method. `.git` is tested with `exists()`, not `is_dir()` — in a worktree it is a FILE, and
`isolation: worktree` is the mechanism whose misconfiguration caused the original incident.

**Matching `Edit|Write|NotebookEdit` and not `Bash` is a correctness call, not a cost one.**
Measured: the tax is ~1.3 s/session for the file-writing tools and would be ~3 s with `Bash` — both
negligible. The reason is that `file_path` is structured and a shell command line is not. **State
the consequence rather than hiding it: this recorder would NOT have caught 2026-08-25**, which
wrote through `Bash` because worktree isolation was broken. It catches the ordinary shape of that
failure — a subagent editing a sibling repo — and the named-paths route stays in step 1a for the
rest. The named list became an ADDITION to the record, never a replacement, for exactly this reason.

**The read window is the wrap marker, not the session id.** A previous session that wrote next door
and then ended without wrapping is the failure this plugin exists to catch, so scoping the read to
the current session would hide it. `check_repos.py` also runs from a Bash step and has no reliable
way to learn its own session id, so scoping that way would have meant guessing — the thing being
removed. Entries age out after 30 days where a project has never wrapped.

**JSONL append log, not a JSON object.** They run several agents at once and two sessions in one
project share a state dir; a read-modify-write loses the second writer silently, which is the same
class of bug as the wrap that named 7 of 8 repos. Rejected alternative: one file per session — no
dedupe read needed, but it reintroduces the session-id guess above.

**A repo the recorder found and the agent did NOT name is called out in the header.** It is the
8th repo of 2026-08-25 and must not blend into the list.

**Never fails a tool call.** The recorder exits 0 on every path — malformed payload, missing key,
unwritable state dir — and prints nothing, ever. `PostToolUse` output would otherwise be a per-turn
context tax on every file write in every project. Tested against nine malformed payloads
(`tools/test_repo_recorder.py`).

---

## The warning box — git answers about the REPO, the warning is about the PROJECT (2026-08-30)

Not a rule an agent reasoned past: a wrong assumption baked into the detection layer itself, and
recorded here because the *fix* has a rule attached that a later session will be tempted to undo.

Every git-derived warning ran `git` with `cwd` set to the project root and read the answer as being
about the project. Git answers about the whole **repository**, with paths relative to *its* root.
Reproduced 2026-08-29 in a throwaway repo holding `proj-a` and `proj-b`, working in `proj-a` with
only `proj-b` dirty:

```
root:  .../proj-a
dirty: [' M proj-b/b.txt']
```

So a session opened in a subfolder warned about files it was not touching and could not act on —
in the same box that carries the warnings that matter, on **every single session**. That is the
alarm fatigue the "speak only when it gets worse" rule exists to prevent, arriving by a different
door. `unwrapped_commits()` failed in reverse: repo-wide counting meant wrapping one folder marked
every other folder wrapped.

**The rule attached to the fix: root == toplevel must stay byte-identical.** `_scope()` returns an
empty tuple there, and on *every* failure path — no repo, unresolvable path, `OSError` mid-walk —
rather than guessing at a scope. That is every project in use today, so a regression there is a
regression in the only thing currently working. `tools/test_subdir_scope.py` case 5 asserts it
against raw `git` output rather than a remembered value, so it survives the implementation moving.

**Do not make the warning smarter about which sibling matters.** Scope it and stop. A warning that
guesses at relevance becomes untrustworthy in the other direction, which is the failure being
fixed. Same reason there is no setting: detect from the filesystem, per `wrap_command()`'s
docstring.

**Filed believing the work workspace was a monorepo; it is not** — the user corrected that the same
day, and each work project has its own repo. Recorded because the urgency and the defect came apart
here: it was fixed on being cheap and correct, not on firing anywhere they currently works. B14
(hub-tracked projects) is what makes the subdirectory case likely rather than hypothetical.

**`check_repos.py` was NOT made to match.** Its `dirty` is now the handed folder's, but `unpushed`
is branch-wide and cannot honestly be otherwise — "ahead of upstream" is a property of the branch,
not of a folder. The two numbers in a row answer at different scopes, so the row says so. Naming
the mismatch rather than resolving it away silently is that tool's existing principle; this kept it.

## Step 8a — the sync was GitHub-only, so the whole work side never synced (2026-09-03, v1.34.0)

The user, 2026-08-31: *"The plugin needs to work on both GitHub and GitLab, my personal code is in
the public GitHub and my work sits in the corporate on-prem GitLab (git2.example-corp.net)."*

Raised again 2026-09-03, from the other end — a session in `~/Projects/workspace` reported, in their
words as relayed: *"BACKLOG.md's GitHub-Issues sync is skipped every time here since this repo is
on GitLab, not GitHub… BACKLOG.md itself stays the authoritative source, nothing is lost, just
noting the sync step is structurally a no-op for this project."* **Every clause of that was true
and it was still the wrong thing to say**, because it reported a permanent gap as a routine
condition. They read it correctly as a plugin defect.

`grep -rn "gitlab\|glab" plugins/cairn/` returned nothing before this change. Three files shelled
out to `gh` and nothing else, so the six work repos — all `git2.example-corp.net` — were outside the
sync layer with no route in.

**What the environment actually was, measured on ORG-LAPTOP1 the same day, and it is the opposite of
what the brief assumed:** `glab` 1.116.0 installed and authenticated against `git2.example-corp.net`; **`gh` not
installed at all.** So on that laptop the GitHub backend is the one that cannot run, and
`agent-reentry`'s own sync was skipping for exactly the same reason `workspace`'s was. That killed
the tempting shape — a `gh` path with a GitLab branch bolted on — because neither backend is the
privileged one and on any given machine either may be the absent one.

**Rejected: a config key naming the host.** It is one more thing that can be right on one machine
and wrong on another, which is the class of problem B23 exists for, on a plugin that runs on three.
Detection is from the `origin` hostname, then — for a self-hosted instance whose name says nothing,
which `git2.example-corp.net` is — from **the CLI's own list of hosts they have already logged into**.
That is a fact about the machine, not a setting to keep in sync. Only host keys are read out of
those config files; both also hold tokens.

**Rejected: `forge` as the name of the abstraction**, which is what B11 originally specified. The
word collided with a name already in use in one of the user's own projects, and made them stop and
ask what it meant (B19). The term is **issue host**.

**The two-command `gh issue list … | --ingest` block in step 8a is gone.** It named `gh` three
times, so it was structurally incapable of refreshing a GitLab project's cache, and it made the
wrap responsible for JSON plumbing the backend already does. One command now:
`issues_backlog.py --refresh --report`. `--ingest` survives for the one case that needs it — a
shell where the CLI runs but this script's Python cannot reach the credential store (the app
container, above) — and tells the two JSON schemas apart on its own.

**Skip lines say "until that changes", never "never".** Every permanent case is permanent until HE
does something — add a remote, enable issues, get a backend written — and none is fixed by another
wrap. That is the 2026-08-29 distinction, generalised past GitHub.

## Step 8a — `backlog sync REFUSED`, and the 206 lines it saved (2026-09-03, v1.34.0)

Found while verifying the GitLab backend, by a `--dry-run` that reported *16 pulls and 0 pullable
items* against `~/Projects/workspace`. That pair of numbers cannot both be right.

`BACKLOG.md` there had 13 item headings written `## 12.`, `## 2b.`, `## 2c.` — not `## B12.`. The
parser requires the `B`, so **none of the 13 parsed**, and `backlog_file.write()` regenerates the
whole file from what `parse()` returned. The next real sync would have replaced 206 lines of their
work backlog with the 16 issues it pulled, and the diff would have looked like a successful first
sync.

**It had been latent for as long as that file existed.** The repo has a GitLab remote and `gh` is
not installed on that machine, so the sync had never once run there — the bug was invisible
*because* of the gap this same release closes. **Shipping the GitLab backend is what armed it.**
Any feature that switches on a code path for the first time inherits every dormant bug on that
path; the verification step has to look for those, not just for the feature.

**The fix is a refusal, not a repair.** `unparsed_headings()` names any item-shaped `## ` heading
`parse()` could not read; `sync_backlog.py` checks it **before a single host call** and refuses the
whole run, and `backlog_file.write()` raises `Unreadable` so a wrap cannot clobber the file either.
`force=True` is the deliberate escape hatch.

**Rejected: teaching the parser to accept `## 12.` and `## 2b.` here.** It is the better long-term
answer — the file is hand-edited from a phone, and `backlog_file.py`'s own docstring already argues
for tolerant parsing — but a letter suffix has no integer `n`, so it changes the item identity that
`next_id`, the issue mapping and the renderer all key off. That is its own change with its own
blast radius, filed as B46 rather than smuggled into a sync release. The guard is what makes
waiting safe.

**`write()` is now the only function in `backlog_file.py` that raises, on purpose.** Everything
else there degrades to silence because it runs in the session-start path. This one DESTROYS the
file it is handed, and silence is the wrong failure mode for that.

## Scope — "use that instead" told a session to skip the entire wrap (issue #47, 2026-09-03)

Filed from an `atlas` wrap at 12:58 on 2026-09-03, and folded into v1.34.0 before it was pushed
rather than deferred, because the same release was already editing this file.

The Scope paragraph read: *"If the project carries its own wrap skill (as `atlas` does), **use
that instead** — it knows things this one doesn't, and it is written as a delta against these step
numbers."* Both halves were wrong, and they were wrong in opposite directions.

**1. "Use that instead" contradicted the delta model it was describing.** `atlas`'s local skill
opens with the *opposite* instruction — *"Read this WITH the plugin's `/cairn:wrap`, not instead
of it"* — and then deliberately restates none of the procedure, because the plugin owns it. So a
session that followed THIS file's wording literally would load a delta, find no CHANGELOG
mechanics, no commit discipline, no `NEXT.md` rewrite, no verdict, and **skip the whole wrap.**

It worked anyway only because the *local* file corrects the plugin on its first line. **The safety
net was in the project, not in the shared rule** — which means the next project to grow a local
skill inherits the bug with nothing to catch it. `atlas`'s skill was a full copy until
2026-08-22; "instead" was a leftover from when it genuinely was one, and the delta conversion
never updated this end.

**2. The step-number coupling had just been removed at the other end.** `atlas` brief 119
(2026-09-02) stripped every `→ /cairn:wrap step N` reference from its local skill, on the grounds
that the coupling was silent: a renumber here breaks the references there and nothing fails. This
file went on advertising the coupling for a day after it was deleted.

**The rule now states the opposite, deliberately: a local skill keys off NAMED concerns, never off
step numbers.** That is the durable half — it survives any renumber, and it is the instruction a
future project delta needs.

**Why this paragraph and not another:** it is the one thing a session reads to decide how the two
files combine, and it is most likely to be read by a session that has seen neither file before. A
wrong answer there costs the entire wrap, silently.

**Note on the numbering rule at the top of this skill** ("Steps 0 and 7 are referenced by number
from `rules/CLAUDE.md`"): that is a reference from a file shipped in the SAME plugin version, which
moves in lockstep. A *project's* local skill does not, which is the whole distinction.

## `--stamp-asked` at step 10 — why the archive question records that it was asked

**Added 2026-09-05 (B35).** `archive_offer.py --check` returned `PENDING` when an offer had been
made and declined, and `NONE` otherwise — so `NONE` covered two *opposite* states: the offer was
made and accepted (nothing outstanding, correct), and **the offer was never made at all**
(outstanding, and reported as fine).

**The incident.** A wrap was done by hand rather than by invoking `/cairn:wrap`, so step 10 never
ran. `--check` was called, returned `NONE`, and that was read as confirmation the archive question
was settled. The user caught it themselves: *"What about the final step? Archiving?"*

**Why the fix is a third call and not a cleverer `--check`.** `pending()` is correct as designed —
it answers exactly one question, *"is there a DECLINED offer still relevant to the current HEAD"*,
and a cleared marker and a never-created one are genuinely the same answer to that question.
Redefining it would make one return value answer two questions, which is the ambiguity this file
exists to remove one level up. The missing fact is a different one — *was the question asked at
all* — and neither `--stamp` (runs only on decline) nor `--clear` (runs only on accept) can supply
it, because both run after the answer is known. Hence a call at ask-time.

**Why the step says "before you ask it".** Stamping after the answer reintroduces exactly the gap:
a session that asks and then dies, or an agent that skips ahead, leaves no record that the question
was ever put. The stamp is cheap and idempotent; the ordering is the whole point.

**Same family as B30 (an undated `closed` marker), B37 (an unverified `issue #N`), B39 (a recorder
blind to Bash writes) and B45 (a closed item dropped with nothing checking it was recorded)** — in
every one, an ABSENT record was reported identically to a satisfied one, and in every one the fix
was a third state rather than a looser check.

---

## Step 5 / 8a — `AFK` said nothing about whether the OUTPUT gets read (2026-08-30, B22)

The user, 2026-08-30: *"I also need to check the outputs, because I have often found issues by
reading the outputs...?"*

`AFK`/`HITL` describes attendance **during** execution — whether the agent will have to ask them
something it cannot read off disk. It says nothing about the **result**, so `AFK/Auto` read as *"set
it going and it is done"*, which is wrong for how they work. An `AFK` item that ran to completion and
then wrapped would commit **and push** before they had read a line, and step 8a's `sync_backlog.py`
writes to the issue host on top of that — their review landing after two outward-facing acts instead
of before them. It had not bitten yet; this is pre-emptive, which is why the rule states the
mechanism rather than an incident.

**Rejected: a third field on every queue item.** A `review: yes/no` tag would be read at every
re-entry, in every project, forever, and the answer is always *yes* — a field with one value is
noise. It also lengthens the queue relay, the one thing that must stay short.

**The fix reuses a gate that already exists** (v1.31.0, and `skills/next/references/incidents.md`):
`Manual` is never how you protect an irreversible step — you write the stop into the brief and leave
the item `HITL/Auto`. Same mechanism, moved one level up: the stop belongs in this file so that no
brief has to remember it. `AFK` stays honest — nothing interrupts them mid-run, they really can walk
away — and nothing outward-facing lands unread.

**The gate has to END THE TURN.** A report followed by a push in the same breath satisfies the
letter of the rule and reproduces the defect exactly: the outward-facing act still lands before they
reads. Same shape as step 10's *"wait for their answer before calling anything."*

**And step 10 must not run either**, which is the way this rule could most easily defeat itself:
`archive_session` ends the conversation, so a wrap that stopped at the push and then offered to
archive would close the only session able to complete it — the review gate satisfied by killing the
thing it was gating. Step 5b is already conditional on the push succeeding; step 10 is now named
explicitly at step 5 rather than left to be inferred from it.

**Why a rule and not five briefs.** An interim `## Before you push — STOP` block was pasted by hand
into `briefs/subdir-scoped-git-warnings.md`, `briefs/archive-offer-reconnect.md` and
`briefs/argparse-safety-for-sync-tools.md` on 2026-08-30, so the next three items behaved correctly
before this shipped. All three were removed with this change — a rule plus copies of the rule is the
drift this backlog keeps having to correct, and it is the same disease as the B41 entry below.

**A copy also lives in `rules/CLAUDE.md`, deliberately.** This skill only loads when invoked, and a
push can be reached without ever invoking it — the same reasoning as the WRAP VERDICT rule.

---

## Steps 3a and 4 — three generic rules stranded in `atlas`'s local wrap (2026-09-01, B41)

Found auditing whether `atlas`'s local `/wrap-session` still earns its keep. It does —
`wiring_check --strict` gating the wrap, rev numbering and doc-timestamp bumps are genuinely
project-specific — but three of its deltas hold in **any** project with a `NEXT.md`, and were
therefore invisible to every one of them.

**Why it matters beyond tidiness.** That skill was a full COPY of this one until 2026-08-22, and the
duplication produced six contradictory or missing rules in nine days (see the Scope entry, issue
#47). It is a delta now, but a delta carrying generic rules is the same disease in a milder form:
the rule reaches one project, and drifts the moment this file changes.

**1. The work-branch merge — its step 8, now in step 4.** Nothing project-specific about it, and
this file said nothing about branches at all. Step 5's *"if the local branch is BEHIND, hand the
merge decision to them"* is a different case: that is a merge git would force, this is one a session
might helpfully volunteer.

**2. Behaviour changes and the doc that explains them — its step 4, now step 3a.** Staleness tooling
verifies **recency**, never **accuracy**, so a doc stamped today is invisible to it and bumping
first actively HIDES what the check exists to catch. Measured in `atlas` on 2026-08-08: one
session shipped seven changes to the re-entry system and five never reached the doc explaining
it — which had been edited earlier that same day and so already carried today's timestamp. The user
caught it by asking *"what are the chances these changes were added to
reentry_system_portable.md?"*

**3. A fresh timestamp on stale content is worse than a stale timestamp.** The corollary, stated as
its own rule because it is the counter-intuitive half: a stale stamp is a signal, a fresh one on
stale content destroys the only signal anyone had.

**Phrased for projects that have no timestamp convention.** `atlas` enforces a frontmatter
`timestamp:` through its own wiring check; most projects have nothing of the kind. The behaviour
half — update the doc explaining the thing you changed — holds either way, so the ordering rule is
written as conditional on a bump existing rather than presuming a mechanism the project lacks.

**What was left in `atlas` on purpose.** The three project-specific deltas, unchanged. Moving a
generic rule up is not an argument for absorbing a local skill; it is what makes the remaining delta
honestly local.

---

## Step 8a — a side-quest finding had nowhere durable to land except a stub (2026-09-03, B47)

The user stated it as a global rule during `workspace`'s full-environment-audit session: when a side
quest surfaces mid-task and is not today's work, record it thoroughly — what was found, where, what
was already ruled out, why it matters — before returning to the main thread, so it never has to be
re-investigated. *"We use what we have in context and don't need to pay again later to
re-investigate."*

**It had been living in exactly one place: a local memory file on one machine**
(`~/.claude/projects/…/memory/feedback_document_side_quests_thoroughly.md`), which syncs nowhere and
reaches neither their other laptops nor Cursor. It surfaced only because `~/.claude/CREDENTIALS.md`
itself carried a standing note asking for it to be filed — a note asking to be promoted, sitting in
a file nobody re-reads on purpose. Same failure this whole plugin exists to prevent, one level up.

**Primary home is `rules/CLAUDE.md`, not this file.** A side quest can surface at any point in a
session, not only at the wrap, so the always-loaded rules file is where the habit has to live —
the same reasoning this file's own Scope section gives for duplicating anything at all: a skill
only loads when invoked, and the sessions that skip documenting a finding are the ones that were
never going to invoke a skill to be told to. **This entry exists because step 8a — where a finding
becomes a `BACKLOG.md` item — is also the concrete place the habit cashes out**, so a one-line
reinforcement there is worth its keep even with the primary copy already in `rules/CLAUDE.md`.

**Rejected: leaving it to the existing backlog-item format alone.** `BACKLOG.md` items already tend
to carry full context by convention (B19, B20 as written are both thorough), but nothing anywhere
said this was a rule rather than a habit that happened to hold so far — and a habit with no rule
behind it is exactly what let the CREDENTIALS.md note sit unfiled.

---

## Step 5 — B22's push-stop was an instruction with nothing checking it (2026-09-06, B86)

B22 (v1.40.0) made the wrap **commit locally and stop before the push** whenever the session ran
unattended. The day it shipped, a concurrent `atlas` session reported "committed and held" —
and a reflog check, done for an unrelated reason, showed a `PostToolUse` hook had pushed every one
of its commits anyway. The agent had honoured the instruction exactly and the outcome was the
opposite, and it only found out by accident.

**The premise was later corrected**, and the correction is why this survived as its own entry
rather than getting folded into an "audit push hooks" fix: that hook turned out to be
deploy-guarded, not universal, and most of the apparent duplication was a legitimate Bash+
PowerShell pair the project needs on Windows. One push in that session's reflog was still
unaccounted for. So the honest position was never *"a hook pushes everything"* — it was *"nothing
inside the session can tell whether the stop held,"* which is exactly the gap B22's rule needed to
close and never did.

**Rejected — forbidding or auditing push hooks.** Not this plugin's business, the `atlas` hook
turned out to be legitimate on inspection, and a rule that inspects another project's own hook
configuration is a far bigger blast radius than reading one ref this repo already has.

**Rejected — trusting the agent's own account of whether it pushed.** That is the party most
likely to be wrong (B68's objection), and the entire point of a mechanical fix is to stop asking
it.

**Fixed with a check, not another instruction**: `hooks/push_check.py` runs
`git rev-list --left-right --count origin/<branch>...HEAD` at the moment the stop happens and
reports one of three outcomes — `HELD` (ahead > 0, the stop held), `ALERT` (ahead == 0, something
pushed the work without being asked), or `CANNOT_CHECK` (no commits yet, detached HEAD, no
remote, or no `origin/<branch>` ref — the question could not even be asked). Offline: it reads a
ref the repo already has and never fetches.

**The failure-family warning is the point of the three-way split, not a nicety.** B86 named the
trap explicitly: a gate that cannot tell "nothing to report" from "could not run" is the same
defect it exists to catch — the exact shape `archive_offer.py`'s B35 note describes one file over,
where `NONE` used to mean both "asked and accepted" and "never asked at all." Collapsing
`CANNOT_CHECK` into `HELD` here would make a fresh repo, a detached checkout, or a never-pushed
branch look exactly like a verified stop — reassurance with nothing behind it. Step 5 now names
all three outcomes and says `CANNOT_CHECK` must never be read as `HELD`.

### `NOTHING_TO_HOLD` — why the push check has a fourth outcome (2026-09-06)

The first cut of `push_check.py` treated `ahead == 0` as `ALERT` on its own. Review before commit
caught that `ahead == 0` is **ambiguous**, not alarming: it means either *"this wrap committed and
something pushed the work unasked"* — the B86 failure — or *"this wrap committed nothing, so there
was never anything to hold back"*, which is every wrap of a read-only session and therefore
routine.

Shipping the three-outcome version would have fired the alarm on the common benign case, with
`SKILL.md` telling the agent to go read the reflog each time. That is the same failure the
divergence banner already demonstrated in this repo: a warning that fires in a state the system is
in most of the time gets read as normal and skipped, which costs you the one firing that mattered.

So the wrap captures `git rev-parse HEAD` **before** it commits and passes it as `--since`, and the
two readings separate on whether HEAD actually moved. With no baseline the check reports
`CANNOT_CHECK` / `no-baseline` rather than guessing — the same rule as every other reason code in
that file, and the reason `CANNOT_CHECK` must never be read as reassurance.

**The general lesson, which is why this is written down:** the fix for an unfalsifiable claim can
itself be unfalsifiable one level up. B86 exists because *"I did not push"* could not be checked;
its first fix produced a status that could not be interpreted. Ask of every guard not only *does it
measure something* but *can its output be read one way only*.

---

## Step 8c (v1.44.0) — the verdict was prose, so a diligent impersonation passed for a wrap

**Reported by the user 2026-09-06, having been told TWICE by WORKSTATION that a session was
wrapped when `/cairn:wrap` had never been invoked.** Both reports were confident, both were
plausible, and both were reached the way a careful agent would reach them: clean tree, `0 0`
against origin, nothing obviously outstanding. **The failure mode is not laziness, it is
diligence pointed at the wrong evidence.**

Two rules aimed at exactly this were already in the always-loaded rules file, in bold, and were
in context both times — *"report the WRAP VERDICT, never the git mechanics"* and *"a clean tree is
not a wrapped session"*. Both were followed. What neither could do is make the verdict
**checkable**: it is a sentence, composed by the party that would have had to do the work, from
inputs it can read without doing any of it.

**What the procedure left behind before this.** One thing: `git rev-parse HEAD > .claude/.last_wrap`
at step 5b. That is a line in a skill file, not a mechanism — an agent that never opened the skill
leaves no trace, and one that opened it can stamp the marker in a single command having skipped
steps 1-10. Worse, the marker is *indistinguishable from correct in the commonest case*: a session
that changed nothing inherits `.last_wrap == HEAD` from the previous session's wrap and reads as
freshly wrapped. That is precisely the state both false reports were made in.

**The user's own fix, and why it was right.** *"Wrapped"* is ordinary English; an agent produces it
in prose without ever having run anything, because that is what the word means in conversation. It
is not lying, it is speaking English — so the word carries no information about whether the
procedure ran, and no amount of rule-writing can give it any. A coined token that has no other
source in the language inverts that: its presence is evidence the tool ran, its absence evidence it
did not.

**Two things the design added on top of that sketch, both load-bearing:**

- **A fixed token is copyable.** It has to be documented in `SKILL.md` for the skill to instruct
  quoting it, and `SKILL.md` is read by the agent *before* it wraps. Coining defeats reaching for
  the word unprompted; it does not defeat copying it out of the instructions. So the line carries a
  **receipt id** — a hash over the receipt body, checkable with `--verify`. Impersonation goes from
  *a sentence anyone would write* to *a fabricated identifier one command contradicts*. A large
  jump, not proof, and it must never be described as proof.
- **All three verdicts, or none.** *"No wrap needed"* was the exact sentence produced. A tool that
  can only emit the affirmative moves the impersonation one door down rather than closing it.

**Rejected, and recorded here so it is not re-proposed:** a third bold sentence in
`rules/CLAUDE.md` (the intervention that had already failed twice); a `SessionEnd` hook that
refuses to end an unwrapped session (that is B40/B43, and addresses *not wrapping*, whereas this is
*falsely reporting a wrap*, which happens mid-session); and trusting `.last_wrap` alone, for the
reason above.

**Why the NEXT session verifies rather than them.** A receipt only they could check is one nobody
checks — the same defect as B62 (`MISTAKES.md` is written and never read). `session_orientation.py`
reads the last receipt at `SessionStart`, gated on the project having ever recorded one, so no repo
is nagged about a mechanism it has never used.

**What the receipt deliberately cannot see.** Four steps leave no residue and are marked
`unverifiable`, never ticked: surveying the tree (step 1 is an input, not an output), the memory
pass (the memory dir is keyed by host path), the session rename (the current title cannot be read
back, by design) and the close itself. Saying so is the point — it tells the reader how much the
token is claiming.

**The `--held` flag, added the same day (2026-09-06).** Step 8c's first live run printed
`ALERT — something pushed the work without being asked` on a wrap that had pushed entirely on
purpose. `push_check` answers one question — *did a stop-before-push hold?* — and after an ordinary
successful push HEAD has moved and `ahead` is 0, which is that alert's exact shape. Calling it
unconditionally would have made every successful wrap cry wolf, which is the alarm-fatigue failure
`push_check.py`'s own docstring already warns about one level down. Whether a push was INTENDED is
not visible in git; only the caller knows. So the wrap declares it, and the unflagged default
records the counts and asserts nothing. **Do not "simplify" this back into an unconditional call.**

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

---

## Step 8c — the receipt measured the world, not the session

**v1.52.0, 2026-09-07/08.** A session on one work laptop opened the way this plugin tells every
session to open: the divergence banner said the branch was behind, so it pulled — two commits,
touching `NEXT.md`, `CHANGELOG.md`, `BACKLOG.md`. It then ran `wrap_receipt.py --check` before
writing anything at all. **Three of the six `REQUIRED` steps already read `[ran]`:**

    [ran ] next_rewrite    NEXT.md differs from its session-start hash
    [ran ] changelog       CHANGELOG.md changed this session
    [ran ] commit          HEAD moved 7b1fac38 -> c9cac7ac

None of the three had happened. All three measured *against a session-start baseline*, and a pull
moves every signal they read: `stamp_baseline()` hashes `NEXT.md` and `CHANGELOG.md`, so a pull
that rewrites them makes the content-diff true; and `commit` compared `rev-parse HEAD` to the
baseline sha, so a fast-forward satisfied it.

**Why this was not a corner case.** The pull is *prescribed by this system*. The banner's own words
are `Say "pull" before starting.`, and the machine-migration watches open with a `git pull` step. So
the mechanism's recommended first action pre-greened half of the mechanism's own verification, on
exactly the multi-machine sessions the receipt was built for. `CAIRN OPEN` still printed on the day
— but only because `marker` was independently missing. With a `.claude/.last_wrap` inherited at the
right HEAD, a session that pulled and did nothing else would plausibly have read **`CAIRN SET`**.

**The rule that came out of it:** *"this file changed since session start"* is the wrong predicate.
*"**this session** changed this file"* is the right one. A step ticks only when the content moved
**and** the HEAD reflog says this working tree moved it. Anything not composed here — `pull`,
`fetch`, `merge`, `reset`, `checkout`, `clone` — contributes nothing, and the receipt names the verb
in its detail line, so the reader sees *"NEXT.md changed since session start, but the change arrived
by `pull --ff-only` — not from this session"* instead of a tick.

**Why the reflog, and not the two fixes the item itself proposed.** Re-stamping the baseline after a
fast-forward needs whoever ran the pull to *call something*, and an agent that forgets is back to the
false green. Attributing by commit authorship needs a trailer the agent must remember to add — the
same disease with an extra step — and there was no writer or reader for one anywhere in the plugin,
because nothing here creates a commit; the `SKILL.md` instructs the agent to. **A trailer is
asserted by whoever writes it; a reflog entry is written by git as a side effect of the act.** That
is D4's own argument for the verdict token, applied one level down: present or absent, never
asserted.

**Two things the fix deliberately does NOT do.** It records no origin sha in the baseline — the
baseline is stamped before the orientation hook fetches, so any origin position written there is the
stale one, and what a pull leaves behind is already on disk. And it leaves the `MISTAKES.md` check on
mtime alone, because that file lives outside the repo where no pull can reach it: there, mtime is not
a weak signal, it is the only signal there is.

**One verdict got looser, on purpose.** A session that pulls and does nothing now reads
**`CAIRN NOT DUE`** rather than `CAIRN OPEN`. Nothing happened that this session owes a wrap for, and
the pulled commits carry the other machine's receipt. Inherited-but-unwrapped commits are still
caught by the left-behind warning and by the receipt's own orientation line.

**What made this findable at all was a measurement, not a review.** The three `[ran]` lines were
copied out of a real `--check` run. Before the fix shipped, the same fixture was replayed against
the old code and reproduced all three verbatim — a test that passes before the fix is testing
nothing, and the whole of section 9 in `test_wrap_receipt.py` exists because every prior HEAD move
in that file was a local commit, so the fast-forward path had never been exercised once.

---

## Step 8c, the other way round — the baseline moved, so the session's real work vanished

**v1.55.0, 2026-09-09. The exact inverse of the incident above, in the same mechanism.** That one
let a `git pull` be credited as this session's work. This one let this session's work be
discredited — and it is worse, because the previous failure printed `[ran]` on things that had not
happened, where this printed the language of a diligent session that had skipped its steps:

    [SKIP] next_rewrite    NEXT.md is byte-identical to session start
    [SKIP] changelog       CHANGELOG.md untouched

Both were false. `NEXT.md` had been rewritten and `CHANGELOG.md` carried a fresh entry, both
already committed. **An earlier `--record` in the same session had correctly reported `[ran]` for
both** — the receipt contradicted itself across one session, which is the only reason anyone
looked.

**The cause was one unguarded write.** The baseline's own recorded timestamp gave it up in a line:
stamped `14:05:45` on a commit the session had itself just made. `session_orientation.py` called
`stamp_baseline()` on every run and `stamp_baseline()` overwrote unconditionally, so the
"session start" snapshot had been replaced with a mid-session one and every tracked step was then
measured against the session's own output.

**The comment at the call site asserted the invariant it did not enforce** — *"stamp the tracked
files' hashes NOW, while nothing in this session has touched them"* — which is true only if the
hook runs exactly once. Nothing made that so.

**How it was triggered is the least important part, and that is the lesson.** An agent ran
`python plugins/cairn/hooks/session_orientation.py` by hand to preview how two newly written
watches would render: a read-only intention, executed by invoking an actor. **Invoking a hook is
never read-only.** But the rules payload already states that orientation text can reappear
mid-session on a compaction refill, so any client that re-fires `SessionStart` reproduces this
with nobody doing anything unusual — and the affected session cannot tell, because the output is
indistinguishable from a wrap that genuinely did not happen.

**Why this matters more than an ordinary bug.** `rules/CLAUDE.md` forbids an agent from composing
a verdict, precisely so the token cannot be talked into existence. That protection has a
precondition nobody had written down: **the tool must be the only thing that can move the evidence.**
A receipt that can be silently re-baselined mid-run has no backstop by design — the agent is
correctly barred from substituting its own account, so a wrong token is simply believed.

**The fix is write-once per session id**, with `force=True` reserved for the explicit
`--stamp-baseline` flag where an operator is deliberately asking, and that path now says when it
has *replaced* an existing snapshot rather than reporting a bland `baseline stamped`. Declining
strands nothing: baselines are keyed by session id and are only ever read back by the session that
wrote one, so a later session gets a different filename and `_prune()` clears the abandoned one on
TTL. **`test_wrap_receipt.py` section 10b asserts the forced path still discredits the work** —
the guard, not the function, is what protects it, so the test has to show the damage still
reachable on purpose.

**And the diagnostic that solved it in one line is now printed.** `at` was in every baseline from
the beginning and nothing ever read it; the receipt now carries
`baseline  stamped 14:05:45, 3m before this receipt`. Stated as a fact rather than judged against
a threshold — a session-start baseline is normally the oldest thing in the session, and anyone
reading a surprising `SKIP` can now see in one line whether theirs is.

---

## Step 8c — an exception printed beside a default gets chosen

**v1.53.3, 2026-09-08.** Step 8c used to print two commands adjacently:

    python .../wrap_receipt.py --record
    python .../wrap_receipt.py --record --held   # AFK stop path only

with the caveat in the paragraph underneath — *"`--held` ONLY when step 5's stop applied … passing
it there makes every successful wrap cry wolf."* The caveat was correct, specific, and directly
below the code block.

A session on the personal workstation, finishing an attended item, **pushed on purpose and then
passed `--held` anyway.** `push_check` returned the `ALERT` this page predicts — *something pushed
the work without being asked* — and the session then wrote a paragraph explaining it away: *"that
ALERT is expected here, not a real anomaly … the check's shape can't distinguish 'pushed on purpose'
from 'pushed without asking'; only I know which happened."*

**Read that last clause against the caveat: it is the caveat's own sentence, restated as a
limitation of the tool rather than as the reason not to pass the flag.** The tool was right. The
flag was wrong. And the session spent more effort rationalising the false alarm than the correct
call would have cost — which is precisely how an alarm becomes wallpaper.

**The rule that came out of it: the default stands alone, and the exception lives behind a gate.**
8c now prints one command, says *"did you push in step 5? then you are done — do NOT read on to the
flag"*, and puts `--held` inside a collapsed block. Nothing about the reasoning changed; only what a
skimming reader sees first.

**Why the caveat was not enough, and this is the transferable part.** Two runnable forms side by
side read as a menu, and the more specific-looking option looks like the more careful one — so the
flag is *attractive* to exactly the diligent agent this file keeps describing. This is the second
instance of the same shape in one day: `rules/CLAUDE.md` stated only the `AFK` push-stop and never
the `HITL` case, and a session read *"commits locally and STOPS before the push"* as universal and
stopped on an attended item. **Both were fixed by stating the default explicitly instead of leaving
it as the unmarked alternative to a stated exception.**

**What did NOT change:** `--held` still exists and is still the agent's declaration, because whether
a push was intended is genuinely not visible in git. The fix is about presentation order, not about
moving the judgement.
