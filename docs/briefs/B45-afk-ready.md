**Not AFK-ready: B45 needs the reviewer's decision (Q1 to Q5 below). Stage 1 (a read-only reader of `MISTAKES.md` that groups entries and marks what is new since the last review) becomes AFK once Q1, Q2 and Q4 are answered. Stage 2 (the review procedure and the nudge that triggers it) waits on Q3 and Q5.**

# B45 — `MISTAKES.md` is written and never read: groom brief

Backlog: `BACKLOG.md` B45 (issue #43), `Opus 5` · effort `high` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-14 against `origin/main` at `4a95fe8`. Every file:line
below was read at that commit. The real `~/.claude/MISTAKES.md` was deliberately not read (it is
private and outside the repo); its entry shapes are taken from the documented format only.

**Prior decisions:** `docs/decisions.md` has no row on `MISTAKES.md` (searched for `MISTAKES` and
`B62`: no match). Bearing on this item: `skills/wrap/references/incidents.md` "Step 6a" (a review
step must not depend on a private resource another installer cannot reach) and B42's rejection of
an LLM judge (per-turn model call, non-deterministic, breaks zero dependencies).

## The ask, as filed

The file exists on every machine and `/cairn:wrap` appends to it, but nothing reviews it, and its
whole justification is that a recurring pattern gets designed against, which needs a reader. Not a
dashboard: a skill or a dated review cadence that reads the log, clusters repeats, proposes **one**
rule or tool change, and writes an `incidents.md` row if accepted. Never auto-edit
`rules/CLAUDE.md` unasked.

Related entries: B41 (`~/.claude` content, this file included, lives on one machine and is backed
up nowhere), B42 and B43 (both cite `MISTAKES.md` as their evidence; B43 says to read it first),
B22 (a new decision contradicting an old one: the same "written, never compared" shape).

## What exists today, with evidence

| Piece | Where | What it means for B45 |
|---|---|---|
| The file is created, never rewritten | `plugins/cairn/hooks/ensure_mistakes_file.py:57-67` writes `HEADER` only when absent; `:22-23` existing content is never touched | A reader can rely on the header being present on a machine where the hook ran, but must not assume it (a file created by hand has none). |
| The header contains an example heading inside a code fence | `ensure_mistakes_file.py:40-44`: `## YYYY-MM-DD -- <project> -- <category>` between ```` ``` ```` lines, then `---` at `:46` | A naive `^## ` parser counts the example as an entry. The reader must skip fenced blocks. It must not skip by position (everything before the first `---`): step 6a says "Append at the TOP", which an agent can read as above the header, and an entry there would be lost. |
| The entry format | `skills/wrap/SKILL.md:232-239` (step 6a): newest first, `## <date> -- <project> -- <category>`, under ~3 lines; `docs/file-formats.md:185-189` the same | One heading per entry, separators ` -- `. Hand-written entries may use an em dash or a single hyphen; nothing enforces the shape. |
| Categories disagree between docs | `ensure_mistakes_file.py:36-38` and `SKILL.md:226-230` say **agent / user / process**; `docs/file-formats.md:191-192` says **agent / yours / process** | The reader must accept `yours` as `user`. The doc drift is listed in the side notes. |
| The wrap is told not to review | `SKILL.md:241-243`: "This is a log, not a review: don't categorise trends or propose fixes here" | The review is deliberately a separate pass. Folding it into the wrap contradicts that line. |
| The receipt sees the step | `plugins/cairn/hooks/wrap_receipt.py:835-855`: step 6a is `ran` when the file's mtime moved this session, `n/a` otherwise | Nothing reads the content. A review pass would be the first reader. |
| Global means per machine | `docs/file-formats.md:195-197` | A review on one machine sees that machine's log only. Rolling machines up is B41's question. |
| "Not built yet, by design" | `ensure_mistakes_file.py:10-11`; `docs/file-formats.md:199-201` ("not built yet, so as not to design a review mechanism before there's anything to review") | The precondition is met: B43 cites 42 entries at filing (`BACKLOG.md` B43). Both passages need a one-line update when stage 1 lands. |
| No review skill exists | Glob `plugins/cairn/skills/*/SKILL.md` finds only `next` and `wrap` | Q1. |
| No review state exists | Grep for `MISTAKES` in `plugins/cairn/hooks/` finds only the creator, the receipt check and the orientation's import of the creator (`session_orientation.py:89`, `:978`) | Q4: there is nowhere yet that records "reviewed up to here". |

## Questions for the reviewer

### Q1. What is the reader: a tool, a skill, or a wrap step?

- **A. A read-only tool first (`tools/mistakes_review.py`, stage 1), and the review itself is an
  attended session that runs it (stage 2).** The tool parses, groups and prints; the agent in that
  session reads the groups, proposes one change, and records it if accepted. No writes from the
  tool, so stage 1 is AFK.
- **B. A third skill, `/cairn:review`.** Gives the pass a name to type. Every skill is loaded only
  when invoked, which is the same "nobody triggers it" gap the entry describes, so it still needs
  Q3's trigger. Can wrap the tool from A later.
- **C. A step in `/cairn:wrap`.** Contradicts step 6a's "a log, not a review" (`SKILL.md:241-243`)
  and grows the skill every session reads, for a question worth asking monthly.

Recommendation: **A**, with B as a thin wrapper only if the reviewer wants a typed name.

### Q2. Who clusters: the tool or the agent?

- **A. The tool groups mechanically, the agent clusters by meaning.** The tool prints counts by
  category and project, and lists candidate repeats: entries that share two or more uncommon words
  (lower-cased, five letters or more, minus a short stop list). The agent reads those groups and
  the entries and decides which are the same mistake. Deterministic, no dependencies.
- **B. The tool clusters fully (similarity scoring, thresholds).** More code, and still wrong on
  paraphrase; the agent would re-check every cluster anyway.
- **C. An LLM call inside the tool.** Rejected already for B42 (non-deterministic, breaks zero
  dependencies).

Recommendation: **A**.

### Q3. What triggers a review?

The entry offers "a skill or a dated review cadence". A cadence the user must remember is the
failure the whole system exists to prevent.

- **A. One orientation line when enough is new**: at session start in a project with `NEXT.md`,
  if the log holds N or more entries since the last review mark (Q4), print
  `MISTAKES.md: <n> entries since the last review (<date>) — say "review mistakes"`. Silent below
  N and silent when the file has no entries. Needs an edit to `hooks/session_orientation.py` and a
  value for N (suggested 10).
- **B. A dated watch.** But `MISTAKES.md` is global and a watch lives in one project's `NEXT.md`,
  so the plugin cannot place it for a stranger; it would be this user's watch, not a mechanism.
- **C. A scheduled task.** Machine-specific and outside the plugin (the scheduled-task prompts live
  under `~/.claude/scheduled-tasks/`), so a stranger's install never gets one.

Recommendation: **A**. It is the only option that ships to a stranger, and it reuses the
orientation the user already reads.

### Q4. Where does "reviewed up to here" live?

- **A. A review heading inside `MISTAKES.md` itself**: `## review <YYYY-MM-DD> -- <n> entries -- <outcome>`
  added at the top by the attended review, with one line naming the change proposed and where it
  went (or `no change`). Entries above the newest review heading are new. Travels with the file,
  readable by a person, needs no state file, and the log stays append-only (nothing is edited).
- **B. A state file under `~/.claude/reentry-state/`.** Invisible to a person reading the log, and
  the state dir is keyed per project path (B40), which is the wrong key for a global file.
- **C. Edit each reviewed entry to add a `reviewed` tag.** Breaks append-only.

Recommendation: **A**. The tool treats a `## review` heading as a marker, never as an entry.

### Q5. Where does the proposed change go?

The entry says "writes an `incidents.md` row if accepted". `incidents.md` is cairn's own rationale
record, but most entries are mistakes made in *other* projects (`incidents.md` "Step 6a" was the
near-miss of treating them as plugin bugs).

- **A. By category.** `process` entries: the proposal is a cairn change, filed in cairn's
  `BACKLOG.md`, and on acceptance a row in the matching `skills/*/references/incidents.md`. `agent`
  and `user` entries: the proposal goes to the project the entries name (its `BACKLOG.md`, or
  `INBOX.md` if the session is not in it, per B32), and on acceptance a row in that project's
  rationale record. A change to `rules/CLAUDE.md` is only ever proposed, never written, per the
  entry.
- **B. Always cairn.** Simple, but files a project's own mistake pattern where that project's
  sessions never read it.

Recommendation: **A**. For a stranger the only rationale record that certainly exists is their own
project's; cairn's `incidents.md` is reachable only from the plugin source.

## Stage 1 slice: the reader (if Q1 = A, Q2 = A, Q4 = A)

Fields line to paste under a new entry (or under B45 once narrowed):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: new `plugins/cairn/tools/mistakes_review.py`, new `plugins/cairn/tools/test_mistakes_review.py`.
No change to any existing code file. Two one-line doc updates, in the same PR if neither is busy or
shared at the time, otherwise in the dossier: `docs/file-formats.md:199-201` (the review tool now
exists, and the `yours`/`user` drift below) and `ensure_mistakes_file.py:10-11` (the docstring's
"no review step yet"). A payload change, so it gets the routine version bump at the attended pass.

- `mistakes_review.py [PATH] [--all] [--json]`. `PATH` defaults to `$CLAUDE_CONFIG_DIR/MISTAKES.md`,
  else `~/.claude/MISTAKES.md`, resolved the same way as `ensure_mistakes_file._config_dir()`.
- Parsing:
  - Parse the whole file. Skip fenced blocks (```` ``` ```` to ```` ``` ````) everywhere, so the
    header's example and any quoted heading in an entry body are never entries. Do not skip the
    header by position: an entry written above the `# Mistakes` title, or a headerless file that
    uses `---` between entries, must still parse.
  - An entry heading is `## <YYYY-MM-DD> <sep> <project> <sep> <category>`, where `<sep>` is ` -- `,
    ` — ` or ` - `. Category is matched case-insensitively against `agent`, `user`, `yours`
    (counted as `user`), `process`; anything else is kept and counted as `other: <word>`.
    Split on the FIRST separator after the date and the LAST separator in the line: the date is the
    first field, the category the last, and everything between is the project, so a project name
    that itself contains ` - ` (or a hyphenated name next to a ` - ` separator) stays whole.
  - A `## review <YYYY-MM-DD>` heading is a review mark (Q4), not an entry. "New" is by position
    (above the newest mark, since the log is newest first). As a cross-check, an entry BELOW the
    newest mark whose date is later than the mark's is listed as `out of order` and counted as new,
    so an entry appended at the bottom by mistake is not hidden as already reviewed.
  - Any other `## ` heading outside a fence is listed as `unparsed` with its line number, never
    dropped silently (B12's lesson: a parser that drops what it cannot read reports success while
    losing data).
  - CRLF and a UTF-8 BOM are accepted.
- Output, default (entries since the newest review mark; `--all` for every entry):
  1. One line: path, total entries, entries since the last review and its date (or `never reviewed`),
     and `this machine's log only`.
  2. Counts by category, then by project, largest first.
  3. Candidate repeats per Q2 A: groups of two or more entries sharing two or more uncommon words,
     each entry shown as `<date> <project> <category>: <first line of body>`. The words that matched
     are printed with the group, so the agent can see why it was grouped.
  4. `unparsed` headings, if any.
- `--json` carries the same data.
- Exit 0 always. A missing or unreadable file is one line saying so. Read only: never writes the log,
  a state file or anything else.

Tests (fixtures only: temp files and a temp `CLAUDE_CONFIG_DIR`; never the real `~/.claude/`):

1. The exact `ensure_mistakes_file.HEADER` alone: zero entries, no `unparsed`, the example heading
   inside its fence is not counted.
2. Header plus three entries in the documented shape: three entries, counts by category and project
   correct.
3. Separators ` -- `, ` — ` and ` - `, and a CRLF file with a BOM: all parse. A heading
   `## 2026-10-02 - site - api - agent` parses as project `site - api`, category `agent`.
4. Category `yours` counts as `user`; an unknown category is `other: <word>`.
5. A `## review 2026-10-01` mark between entries: the default shows only the entries above it, and
   its date; `--all` shows every entry; the mark is never counted as an entry.
6. No review mark: every entry is new, the line says `never reviewed`.
7. An entry body containing a fenced block with a `## 2026-...` line inside it: not an entry.
8. A malformed heading (`## 2026-13-45 something`) is `unparsed` with its line number.
9. Two entries that share two uncommon words are grouped and the words printed; two that share only
   stop words or short words are not.
10. A file with no header that separates entries with `---`, and a file with an entry written
    above the `# Mistakes` title: every entry parses in both.
11. An entry below the newest review mark but dated after it: listed as `out of order`, counted
    as new.
12. Missing file and an unreadable path: one line, exit 0.
13. `--json` has the same counts as the text output.
14. The fixture file's bytes are identical before and after a run.

Done: those tests pass, `python plugins/cairn/tools/run_tests.py --timeout=300` passes, and nothing
is left in the real state dir.

## Stage 2 (not AFK; listed so it is not forgotten)

The review procedure (Q1 A or B), the trigger (Q3) and the routing of the one proposed change
(Q5). The procedure, as the entry describes it: run the reader, pick the single largest repeat,
propose **one** change to the user, file it where Q5 says, write the incidents row only if they
accept, and add the Q4 review heading either way, so a declined proposal still resets the count.
Never edit `rules/CLAUDE.md` unasked.

## Out of scope

- Rolling up several machines' logs (B41).
- Changing the wrap's step 6a. It stays a log.
- Any edit to existing entries.

## Side notes for the attended pass

1. **Category drift.** `docs/file-formats.md:191-192` calls the user category **yours**;
   `ensure_mistakes_file.py:36-38` and `skills/wrap/SKILL.md:226-230` call it **user**. Suggested
   fix: change `file-formats.md` to `user` (the hook header is what every machine's file carries).
   Not changed here: the brief is the deliverable of a groom.
2. **Id drift.** `plugins/cairn/hooks/wrap_receipt.py:35-36` and
   `plugins/cairn/skills/wrap/references/incidents.md:1039` cite "B62 (`MISTAKES.md` is written and
   never read)", which is the predecessor repo's id for this entry. In this repo B62 is the machine
   inbox. Same drift as the B38 brief's side note; suggested fix: replace with "B45" in both.
3. **Grammar.** `wrap_receipt.py:37`: "in the box they already reads" should read "they already read".
