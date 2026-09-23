# Third-party text reaches session context unmarked — label at the source, neutralise at the printer

`Opus 5` · effort `high` · `HITL/Auto` · from `BACKLOG.md` B27

Migrated 2026-09-23 from the private source repo, where it was B102: finding **S2** of the 2026-09-06
security review, plus three refinements found during its decision pass. Decision recorded as **D10**
in [docs/decisions.md](../docs/decisions.md) — read the row first; it names why the printer alone and
`pull()` alone were both rejected, and why `render()` is off limits. **Line numbers below are from
v1.45.0 — re-locate them before editing.**

## What is wrong

`session_orientation.py` prints to stdout, which SessionStart appends to the model's context. The
plugin's own convention is that a line beginning `[to the agent]` is an instruction the agent
follows — **12 sites emit that literal prefix at column 0**, and `rules/CLAUDE.md` tells the agent
to obey it every session.

File content is printed into the **same stream**, and the only thing separating it from the
mechanism's own voice is a **two-space indent that nothing checks**. The box rules (`"=" * 68`,
`"-" * 68`, `"!" * 68`) are section delimiters printed *around* file content, not per-line fences —
nothing stops a file line carrying its own 68-character rule and a forged header.

**And there is a route for other people's text to get there.** `tools/sync_backlog.py`'s `pull()`
writes a remote issue's `title` and `body` **verbatim** into `BACKLOG.md` (`sync_backlog.py:379-393`),
and both `next/SKILL.md` and the rules instruct the agent to read `BACKLOG.md`. Anyone who can file an
issue on a synced repo can put chosen bytes in front of the model on a later session.

**This is live now.** It was inert while every file was the operator's own; this repo is public and
its backlog syncs to its public issue tracker.

## The full sink inventory

Nothing is escaped or transformed anywhere. The only defences are line-*count* caps and two slices.
**No sink has a per-line length cap.**

| Sink | Site | Count bound | Line bound |
|---|---|---|---|
| `NEXT.md` Queue | `session_orientation.py:1213-1214` | `MAX_NEXT_LINES = 24` | none |
| `## Decisions` entries | `:1249` | **none** | none |
| `## Watching`, DUE — title **and every body line**, verbatim | `:1267-1269` | **none** | none |
| `## Watching`, not-due / event | `:1292`, `:1306` | **none** | none |
| Watch title in the `Say "check …"` invitation | `:1274-1275` | — | none |
| `NEXT.md` footer | `:1325-1328` | `MAX_FOOTER_LINES = 8` | none |
| `INBOX.md` bullets | `:1377-1378` | `MAX_INBOX_ITEMS = 12` | none |
| **`BACKLOG.md` duplicate-id titles** | `backlog_file.py:561-563` | none | none |
| Open-item marker title (from a queue line) | `:1127-1128` ← `item_open.describe` | 1-2 | none; wrapped in `"…"` with **no quote escaping** |
| Remote issue titles + authors | `issues_backlog.py:239-243` | 3 (`MAX_NAMED_INBOUND`) | `title[:70]`; **`author` unbounded** |

`_decision_title` and `_watch_title` both **fall back to the whole raw line** when their regex misses
— so a malformed entry prints more, not less.

The one place that gets this right already is `machine_identity.mismatch_warning`: it echoes only ids
already present in `MACHINES.md`. That is the shape to copy — a whitelist, not an escape.

## The `inbound` flag does not reach the sink that matters

- Set at pull time in `sync_backlog.py`, and stamped into the issues cache in `issues_backlog.py`.
- Rendered as a **bare word on a hand-editable fields line** (`backlog_file.py`), read back by a
  regex — so it can be added or removed by anyone who can write the file.
- **`backlog_file.summary_lines()` never consults it.** The `⚠ filed by SOMEONE ELSE` warning comes
  only from the issues *cache* path, and `session_orientation.py` passes `count_line=not local` — so
  where a local `BACKLOG.md` exists, an inbound title already pulled into it and printed via the
  duplicate-id path is **unmarked**.

## The fix

**Two chokepoints, not the ten print sites.** Patching each `print()` is where the bug surface is
and is not a chokepoint — the next site added would miss it.

1. **`backlog_file.parse()`** — the single entry every `BACKLOG.md` consumer goes through, and it
   already produces a *derived* view (`title`, `text`, `brief`) distinct from the on-disk bytes.
   `_strip_fences()` is the existing precedent for exactly this pattern: *the parser must not be
   fooled by pasted content.*
2. **`session_orientation._read()`** — every line of `NEXT.md` and `INBOX.md` passes through it, and
   it already performs one transformation (`_COMMENT_RE.sub`). A second, narrower one covers eight
   of the ten sinks at once.

At both: **bound the line length**, and **defang anything that mimics the mechanism's own voice** —
a leading `[to the agent]`, a long box rule, a forged section header. Defang, do not drop: a user
who legitimately typed `[to the agent]` in their footer should see it rendered inert, not silently
vanish.

3. **`sync_backlog.pull()`** — carry provenance so it survives into the file: an issue `title`
   containing a newline currently injects arbitrary lines at `render()`'s `## B{n}. {title}`, which
   is a structural break, not just a display one. And make `summary_lines()` consult `inbound` so
   third-party text is marked wherever it prints, not only in the issues-cache warning.

**Also fix, while here:** the uncapped `## Decisions` / `## Watching` entry counts, and the
whole-body DUE watch echo. A cap needs a judgement call — a DUE watch's body is genuinely the most
useful thing in the orientation, so trimming it has a real cost. **That is the one place to stop and
ask.**

## What NOT to do

**Not `backlog_file.render()`.** Its verbatim contract is load-bearing and documented in the module —
items are hand-edited on a phone, and an agent that paraphrases the wording is the same class of
bug. Mutating there corrupts the file instead of the view, and breaks the byte-for-byte round-trip
test in `tools/test_backlog_file.py`.

Do not remove the `[to the agent]` convention. It is what makes the relay tiers work, and it is not
the defect — the absence of a boundary around file content is.

## Verification

- Tests: a `NEXT.md` footer line beginning `[to the agent]` reaches context defanged; an over-long
  line is bounded; a `BACKLOG.md` title containing a newline does not break the file structure; an
  inbound item is marked wherever it prints; the byte-for-byte `render()` round-trip test is
  **untouched and still green**.
- `python plugins/cairn/tools/run_tests.py`.
- `python plugins/cairn/hooks/session_orientation.py` in this repo before and after — the orientation
  must be materially identical for ordinary content.
- `python plugins/cairn/tools/measure_context.py <a project root>` — a per-line cap changes the
  session cost; state it with a number.

## Where it stops

`HITL` — **it stops once**, on the cap for `## Decisions` / `## Watching` and the DUE-watch body,
because that trades a real re-entry benefit against the bound. Everything else is decided. It pushes
when done.
