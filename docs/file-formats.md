# File formats and conventions

The full spec for the files `reentry` reads and writes: `NEXT.md`'s three lists, the
`AFK/HITL` attendance field and permission modes, `INBOX.md`, `BACKLOG.md` and how it
syncs to GitHub/GitLab Issues, `MISTAKES.md`, `CREDENTIALS.md`, `CHANGELOG.md`, the
rationale record, and the one line of direction. For how to opt a project in and the
`NEXT.md` template, see [../README.md](../README.md#opting-a-project-in).

### The three lists

**`## Queue`** — actionable RIGHT NOW. Max 5, numbered. Every item names its **model, effort and
attendance/mode** and links to a self-contained brief on disk. You say *"do 1"* and the agent
reads the brief; you never paste a prompt.

Since v1.27.0 a tier mismatch is **asymmetric**: if the session is running *above* what the item
asks the agent says so in one line and carries on, and if it is running *below* — Sonnet on an
`Opus 5` item — it **stops before doing any work** and waits for you to switch. Over-tier costs
more and the work is no worse; under-tier produces work that is worse and looks identical, and the
only person who would catch that is the one who forgot to set the tier in the first place.

**`## Decisions`** — his to answer, not an agent's to pick up. `D1`, `D2`, … uncapped. ONE line
each, no continuation, no prose body — full detail lives wherever the project keeps its backlog:

```
**D1. Short title** — answer: `ask <authority>` · added `2026-08-09` → `docs/pending.md`
```

`answer:` is required and is the routing field — `ask <authority>` (name your own authority —
`ask the design lead` in `atlas`, `ask the API docs` elsewhere — its answer decides it, code follows) or
`here` (you tell the session directly, it becomes a code change).
`added` is required, same rule as a watch. **No "do Dn"** — a decision has nothing to execute, it
is waiting on you reading it, not on a trigger. When answered: delete it, log the answer in
`CHANGELOG.md`.

### `AFK/HITL` and the mode — can you start this and walk away?

Model and effort say what the work costs. They do not say whether you have to be *there* — so
every queue item and every watch also carries one token after the effort:

```
1. **Short title** — Opus 5 · high · HITL/Plan
```

**`AFK`** means the agent runs it to completion unattended: nothing it needs is missing from disk,
nothing it does is irreversible. **`HITL`** means it will stop and need you, and the brief has to
say where. The test is not how hard the work is — it is whether the agent would have to **ask you
something it cannot read off disk.** An `Opus 5 · high` item where the agent decides on your
behalf and reports back is `AFK`.

The half after the slash is the **permission mode** — `Auto` · `Manual` · `Accept Edits` · `Plan`
· `Bypass`. It is the one field an agent cannot set for itself, so the queue names it and you set
it (Shift+Tab, or the mode selector) before saying *"do 1"*:

| Mode | For |
|---|---|
| `Plan` | under-specified work: read-only, produces a plan you approve. Always `HITL`. |
| `Accept Edits` | specified edits across many files; you watch the commands, not each write. |
| `Auto` | the default for **both** `AFK` and `HITL`: reads, edits and local tests in one repo. |
| `Manual` | the rare item where each step genuinely warrants review — see below. |
| `Bypass` | `AFK` only, and only where the blast radius is one repo you can `git reset`. |

**`Manual` is not how you protect an irreversible step** (corrected v1.31.0). It gates *every* call,
so you approve dozens of reads to guard one push — spending exactly the attention the queue exists
to save. Put the stop in the **brief** instead (*"commit locally, then stop — the push waits for
you"*). `HITL/Auto` then runs freely, stops once where it matters, and carries on autonomously
afterwards.

`AFK/Plan` and `HITL/Bypass` are contradictions — a plan exists to be approved, and Bypass exists
because nobody is there to approve. The hook counts items missing the field and says so in one
line; it never lists them, because every file written before v1.16.0 is missing it everywhere and
the next wrap fills them in.

**`## Watching`** — waiting on a trigger. `W1`, `W2`, … uncapped. The title goes inside the bold
and the fields after it, in this order:

```
**W1. Short title** — `Opus 5` · effort `high` · added `2026-08-15` · check after `X`
```

`check after` is last. X is a `YYYY-MM-DD` date or free text naming an event. **A dated watch
stays hidden until its day, then surfaces as DUE NOW.** That is the point: "check this on Sunday"
stops being yours to carry.

**`added` is required, and it is what keeps event-gated watches honest.** A dated watch looks
after itself. An event-gated one has no floor under it — if the event never happens, the watch
sits in the file forever and nothing says how long it has been there. So the hook prints the age
of every event-gated watch (`waiting 12d`), flags any that has waited more than 30 days, and
calls out any watch missing the field rather than quietly accepting it.

The test for which list: **if you could not start it today no matter how willing, it is a watch.**
An item blocked by a watch stays in the Queue marked `blocked by Wn` — knowing why you can't pick
it is information you need while picking.

### `INBOX.md`

Optional. Zero-effort capture — a bullet is the whole protocol. Triaged at the start of the next
session into queue items or backlog issues, then cleared. **Nothing is ever parked here.** An item
with a finished brief is backlog, not capture; leaving it in `INBOX.md` turns every future session
start into a nag about something that was triaged days ago.

### GitHub Issues — the backlog

Optional, and inert unless the repo has a GitHub remote with issues enabled.

`NEXT.md` is capped at five on purpose: the cap is what stops it becoming the 7,000-line backlog
this system replaced. But a cap needs somewhere for the sixth item to go, and "back into
`INBOX.md`" is not it. Issues is that somewhere — unbounded, reachable from a phone, safe against
a re-clone, and writable by other people.

One board **per project**. A merged cross-repo ranking has no job to do: "which project should I
open today" is answered by each project's own Queue item 1, which is why the priority ordering of
`NEXT.md` is load-bearing rather than tidy.

**Since v1.18.0 the backlog is `BACKLOG.md` and Issues is a sync target.** The inversion fixed two
holes at once: a project with no GitHub remote previously had *no* backlog layer — the sixth item
was dropped with a one-line note — and an offline wrap discarded displaced items, because a wrap
must never fail over the backlog. Now the wrap writes the file (always, everywhere) and
`tools/sync_backlog.py` reconciles with Issues whenever `gh` works. Everything the sync does is
derived from the file, so there is no outbox to drift and an offline session loses nothing.

The traffic runs **both ways** (v1.17.0+). A sixth Queue item is filed to the backlog at the wrap;
a wrap that ends with the Queue under three **pulls items back** until it has three, writing each
one's brief to disk. The item stays in `BACKLOG.md` marked `queued` — it is closed only when the
work is finished. Until v1.17.0 only the outbound leg existed, so a project could finish its last
queued item and sit with an empty Queue on top of a full backlog, reported at session start as
*"nothing is live"*.

Every issue is labelled **`afk` or `hitl`**, the same judgement the Queue carries — the attendance
half only, because a label is the only part of an issue `gh issue list --label afk` can filter on.
The mode (`Auto`, `Plan`, …) stays in the issue body, where it is read once, when the item is
pulled into the Queue. This is what answers *"I have a machine free and no attention — is there
anything I can just set running?"*, which nothing else in the system could answer without opening
the backlog. An **unlabelled** issue is unjudged, not `hitl` — issues filed from the web or by
someone else never pass through a wrap, so the session-start line counts them separately
(`, 2 unjudged`) rather than letting `--label afk` filter silently over a half-labelled backlog.

The labels themselves are per-repo GitHub state, so they have to be created in each repo before
anything can use them — `gh issue create --label afk` in a repo without the label **fails** rather
than falling back to an unlabelled issue. `/cairn:wrap` runs this first, and it is idempotent,
so it is also the one-liner to run by hand in a new repo:

```bash
python plugins/cairn/tools/label_backlog.py --ensure -R owner/repo
```

(from a clone of this repo; inside a wrap the skill resolves it as
`$CLAUDE_PLUGIN_ROOT/tools/label_backlog.py`. Don't glob the plugin cache — every installed
version is still on disk and the glob would match all of them.)

**Every one of these tools takes `--help`, and since v1.26.0 that is all it does.** They used to
read `sys.argv` by hand, so an unrecognised flag fell through to the DEFAULT path — and
`sync_backlog.py`'s default path is the real sync. Two agents ran `--help` on the same day
expecting usage text and pushed issue bodies to GitHub instead: an outward-facing write nobody
chose. All three now parse through `argparse`, so `--help` exits 0 and an unknown flag exits 2,
both before a single `gh` call. `sync_backlog.py --dry-run` is the other half — it reports what a
sync WOULD do (file, close, relabel, re-body, pull) and writes nothing, here or on GitHub:

```bash
python plugins/cairn/tools/sync_backlog.py --dry-run
```

`tools/test_sync_flags.py` pins this down by asserting on the `gh` calls themselves, since a
silent fallthrough looks exactly like a tool that ran correctly.

Session start prints one line (`BACKLOG — 4 open issue(s) …, 1 new since your last session`) read
from a cache under `~/.claude/reentry-state/` — with `, N runnable AFK` appended when any issue
carries the label — and names any issue **filed by someone other than the repo owner** — the one class of item in this system that can genuinely surprise you. The cache
is written by `/cairn:wrap`, and refreshed opportunistically by a detached child of the hook
where the platform allows it; the start path itself never touches the network.

> **Windows caveat.** If `python` resolves to the WindowsApps execution alias, hooks run inside an
> app container with no access to the Windows Credential Manager, so `gh` called from a hook is
> unauthenticated even though the same binary works from your shell — and the container is
> inherited, so re-spawning does not escape it. The wrap-time refresh covers this; the permanent
> fix is to disable the alias or put the real Python directory ahead of `WindowsApps` on `PATH`.

### `MISTAKES.md` — a running log, not a review

`~/.claude/MISTAKES.md`, global (not per-project — the point is to compare across every project you
touch, which a per-repo file can't do), auto-created by a hook alongside the `CLAUDE.md` rules sync.
`/cairn:wrap` appends to it, newest-first, one entry per mistake caught that session:

```
## 2026-08-27 -- code -- agent

What happened, what it should have been instead, in a sentence or two.
```

Three categories: **agent** (something the agent got wrong and had to be corrected), **yours** (a
misstep on your side, logged the same way — pattern data, not blame), **process** (the reentry
system itself failed to prevent one). Skipped silently if nothing went wrong that session.

**Global here means per-machine, not per-account** — if you work from more than one machine, a
mistake repeating across them won't visibly pattern until something rolls the machines up (tracked
as a known limitation, not yet built).

This is deliberately just a log for now. Once it holds real data, a periodic-review pass (grouping
by category and theme, surfacing repeats) is a natural next step — not built yet, so as not to design
a review mechanism before there's anything to review.

**Until v1.33.0, an agent could work an entire session without ever learning this file existed** —
its only mentions were the one-line creation message (printed once, on the one machine, on the
first run ever) and the `/cairn:wrap` skill (loaded only when that skill runs). A session that
never wraps had no path to it. `rules/CLAUDE.md` now names both `MISTAKES.md` and `CREDENTIALS.md`
directly, so every session carries the pointer, not just the ones that happen to invoke `/wrap`.

### `CREDENTIALS.md` — an inventory, not a vault

`~/.claude/CREDENTIALS.md`, global for the same reason as `MISTAKES.md` — a credential is used
across every project on a machine, not one repo — auto-created by the same hook pattern. Tracks,
per secret:

```
## <purpose> (<system>)

| Name | Machine | Stored via | Expires | Status |
|---|---|---|---|---|
| `<name>` | `<machine>` | Git Credential Manager / SSH agent / etc. | `YYYY-MM-DD` | active |
```

**Never a value.** The point is that the next rotation is a checklist read off this file — which
machine, which token, when it expires — instead of a memory test that fails the moment more than
one machine or server is in play. Recommends one credential per machine over one shared everywhere,
so a leak forces revoking one thing, not chasing every host that might have a copy.

Built 2026-09-01 after exactly that failure: a GitLab PAT shared across machines leaked into a chat
transcript, and there was no way to know its full blast radius because nothing tracked where it had
been used. The fix for the leak (Git Credential Manager instead of a plaintext env file) is
machine-specific and not part of this plugin; the inventory is the part that generalises.

### `CHANGELOG.md`

Where finished work goes, newest-first. `NEXT.md` is a queue, never a history — mixing the two is
what turned an earlier backlog into 7,000 unusable lines. Keep entries under ~20 lines.

**It is not the same thing as your closed-issues list.** Only work that was deferred long enough to
be filed ever becomes an issue — anything that goes Queue → done inside a session never touches the
tracker. Measured across these repos: `atlas` has 255 changelog entries and 1 closed issue.
And closure isn't completion: 4 of `lighthouse`'s 7 closed issues were closed because they
*migrated* to another repo. The issue is a pointer; the changelog is the record.

### The rationale record — why the project is the way it is

`CHANGELOG.md` answers *what shipped and when*. It structurally cannot answer **why, and what was
rejected**: it's chronological and capped per entry, so a reason ends up scattered across dated
entries and findable only by grep. One project's reached 792 KB / 10,204 lines that way.

So each project keeps a rationale record — `docs/decisions.md`, or whatever it already calls it
(this repo keeps two, as `skills/*/references/incidents.md`). **One row per decision, naming the
option that was rejected and what it cost.** The rejected alternative is the half a later session
cannot reconstruct, and the half that stops the same argument being re-run.

Write a row when a decision is **made**. An open question is a `## Decisions` entry in `NEXT.md`;
this is where it lands once answered — opposite ends of the same thing, never the same file.

**Rationale is the only thing in a repo that can't be re-derived from the repo.** That's the test
for what belongs here — and the reason `ARCHITECTURE.md` is *not* part of the spec. An architecture
doc describes a moving target, goes confidently stale (agents believe it), and is largely
re-derivable from the code. Keep one if your project earns it; the system doesn't ask for it.

### One line of direction

The footer below the `---` carries one line on **where the project is going**, alongside the line on
what it is. Everything else in the system is near-term by construction — the Queue is capped at 5,
Watching is triggers, the backlog is unordered — so without it nothing states a destination, and
there's no axis to prioritise against.

One line, present tense, what *done* looks like for the current phase. **A criterion, not a plan**
— it's what lets a wrap close a backlog item as *"no longer serves the aim"* instead of letting the
list grow forever. Re-confirmed at every wrap; a stale one is worse than none, because it's in front
of you at every session start.

Deliberately *not* its own `## Aim` section: the hook routes any unrecognised heading into the queue
bucket, where it would eat the queue's 24-line budget and silently push real items off the end — and
fixed lines at the top of every orientation are the same failure as a wall of text. The footer
already exists, already has a budget, and is already re-read every session.

