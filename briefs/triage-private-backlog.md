# Triage the private backlog into this repo

`Opus 5` · effort `high` · `HITL/Plan`

## Why this item exists

This repo was seeded by a fresh `git init` (`docs/decisions.md` D1), so its working files started
blank. Development now happens here and installs come from here — but roughly half the actual
backlog is still in the private source repo, `agent-reentry`. Until this item runs, the queue in
this repo is thinner than the work that exists, which is exactly the unheld state the plugin is
built to prevent.

It was queue item 1 from seeding until 2026-09-14, when two shipped defects displaced it to 3.
Both of those are the footer's aim line failing outright; this item is about queue completeness,
which matters but does not stop a stranger installing.

**This brief names no path or URL inside the private repo, deliberately** — `docs/decisions.md` D22
settles that a brief here never points into it. The operator knows where their own clone is.

## What has already migrated, so do not redo it

- **`docs/decisions.md` arrived whole.** Every answered decision, with its rejected options. It is
  one of the eight files the seed copied and it passes the disclosure checker. Do not re-import it,
  and do not start a second D-sequence here.
- **`plugins/cairn/**` and the two `incidents.md` records** came with the payload. The incidents
  behind the rules are already here.

## What has to be decided per item, and the rule

**Split on whether the item is about the plugin or about the operator's own work.** The private
repo's backlog names work servers, client projects, an employer's git host and specific machines;
those items are not publishable and are not this repo's concern either way.

- **Migrates:** anything whose subject is the plugin — a hook that misreports, a parser that cannot
  read a format, a tool with no default file set, a check that passes vacuously.
- **Stays:** anything naming a work server, a client, an employer, a specific machine, or the
  operator's own portfolio. Also anything whose only value is historical.
- **Rewrite rather than drop** where an item is a real plugin defect described in private terms.
  The defect migrates; the private example does not. Keep every measurement — a count is evidence,
  a name is not (`docs/decisions.md` D15).

**Rough sizing measured 2026-09-09:** 55 items in the private backlog; a keyword pass put about 25
as plugin-generic and about 30 as naming something private. Treat that as a starting estimate, not
an answer — the keyword pass is not a judgement.

## The open decisions

Three were open in the private repo when this repo was seeded. They are not all this repo's:

- **The identity of a letter-suffixed backlog item** (`## 2b.`) — a parser question, wholly about
  the plugin. **Migrates.** The simple answer (letter-suffixed items are not a thing) has a
  recorded cost: splitting one item had to spend a fresh integer id instead.
- **One D-sequence per repo** — also a plugin question, and this repo should start correct rather
  than inherit the collision. **Migrates.** In the private repo, `NEXT.md`'s open decisions and
  `docs/decisions.md`'s answered rows used separate counters and had already collided on D4.
- **Which git identity authenticates on which machine**, and whether billing codes belong in item
  ids — operator-specific and employer data respectively. **Stay.**

## How to run it

1. Read the private backlog in full before moving anything. It is long; the point is the split, not
   speed.
2. Move in batches by theme, not in id order — related items share a decision.
3. **Ids restart here.** `BACKLOG.md`'s `<!-- next-id: N -->` marker is the id floor and only ever
   goes up; let `tools/backlog_file.py` assign, and never hand-write an id to match the old one.
   A migrated item gets a new id and says in its body what it was called before.
4. An item that lands on this repo's Queue needs a brief **here**. If its old brief is publishable,
   bring the content across as a new file; if not, write a fresh one.
5. Leave the item in the private repo until its copy here is committed, then remove it there — so
   nothing is in flight in two places.

## Verification

```bash
python plugins/cairn/tools/validate_next.py
python plugins/cairn/tools/test_payload_clean.py
python plugins/cairn/tools/fence_check.py NEXT.md BACKLOG.md CHANGELOG.md
```

- `test_payload_clean.py` must still pass over **both** file sets. A migrated item that names a
  work server is exactly what it exists to catch — but note it scans the payload and the eight
  public files, **not** `BACKLOG.md`, so a leak here is caught by reading, not by the tool.
- `validate_next.py` passes and every queue item's brief link resolves inside this repo.
- No link anywhere in this repo points into the private one.

## Where it stops

`HITL`. The judgement calls are the work, so expect to be asked about individual items — but it
pushes when it is done rather than stopping to ask for permission to.
