**Stage 1 (document the constraint) is AFK-ready as written below; the entry already decided it ("Document it as a constraint first"). Stage 2 (aliasing) needs the reviewer's decision on Q1 to Q3 and is not AFK.**

# B40 — one repo, several plugin memories: groom brief

Backlog: `BACKLOG.md` B40 (issue #38), `Sonnet 5` · effort `medium` · `HITL/Plan` · added `2026-09-04`.
Written by the scheduled firing on 2026-11-14 against `origin/main` at `4a95fe8`. Every file:line
below was read at that commit.

**Prior decisions:** none. `docs/decisions.md` was searched for B40, its predecessor id B63 (which
there means a different item, D33), `resolve()`, `PROJECT_ALIASES` and WSL; no row decides this.

## The ask, as filed

`state_dir()` keys plugin state on the resolved path, so the same repo seen from Windows, from WSL
(through `/mnt/c/...` or as a separate clone under `~/...`) or on a server has separate state for
wrap receipts, item-open markers, dirty-tree breadcrumbs and timesheet rows. A wrap in one does not
close another, and nothing says so. The entry asks to document this as a constraint first; aliasing
is a later design. Related: B3 (the git-side twin), B36 (the cross-environment sweep, whose groom
brief already cites B40 at `docs/briefs/B36-afk-ready.md:35`).

## What exists today, with evidence

| Piece | Where | What it means for B40 |
|---|---|---|
| The key | `plugins/cairn/hooks/reentry_state.py:507-522` `state_dir(root)`: slug = sanitised `root.name` (32 chars) + the first 10 hex of `sha1(str(root.resolve()).lower())`, under `$CLAUDE_CONFIG_DIR` or `~/.claude`, then `reentry-state/<slug>` | Two things split state: a different **config dir** (WSL has its own `~/.claude`), and a different **resolved path string**. Case is folded (`.lower()`), so a case-only difference does not split. |
| A second fallback silo | `reentry_state.py:515-516`: when the config dir is not writable, the same slug under `tempfile.gettempdir()` | A session that once fell back to the temp dir wrote its markers where the next normal session never looks. Not mentioned in the entry. |
| What lives in `state_dir()` | callers: `item_open.py:107`, `archive_offer.py:86,91`, `dirty_tree_warning.py:98,159`, `repo_sweep.py:248,318`, `session_orientation.py:797`, `touched_repos.py:90`, `staged_review_guard.py:111`, `wrap_receipt.py:235,944`, `issues_backlog.py:149` | The wrap **receipt** and its session-start baseline, item-open markers, the archive offer, Stop/SessionEnd breadcrumbs (`last_exit.json`, `stop-*.json`), the sibling-sweep cache, touched-repo records, the staged-review stamp and the issue cache. All per-path. |
| What does NOT live there | `reentry_state.py:21-25` and `:48`: `.claude/.last_wrap` is written into the working tree by the wrap skill (gitignored) | The wrap **marker** belongs to the working tree, not the path. A WSL session looking at the same tree through `/mnt/c/...` sees the same `.last_wrap`, so its "N commits since the last wrap" count matches Windows, while its receipt (`CAIRN SET`/`OPEN`) does not: the two views disagree with each other about one tree. A separate clone has its own of both. |
| Timesheet rows | `plugins/cairn/tools/timesheet.py:108-110` reads `<config dir>/projects`; `:122` `PROJECT_ALIASES`, `:125-133` `project_key()` | Timesheet rows do **not** go through `state_dir()`. They split by **config dir** (WSL's transcripts sit under WSL's own `~/.claude`) and are grouped by directory name, with aliases for renames. So the entry's "timesheet rows" is the config-dir half of the problem, not the hash half. |
| An existing written statement | `docs/cursor-adapter-requirements.md:601-606` ("Path identity") | Already says the three environments are three silos and "do not pretend a wrap on Windows closes the WSL tree". It is in an internal requirements doc a user never reads; `docs/guide.md` says nothing (Grep for `WSL`, `state_dir`, `reentry-state` in it: no match). |
| A rename or move | the same hash | Moving or renaming a checkout gives it a new slug: every marker, the receipt and the item-open state are left behind under the old slug, silently. Same class as the `code` to `Projects` rename `timesheet.py:117-121` records. |

## Stage 1: document the constraint (AFK)

Fields line to paste under B40 once this brief is accepted (or under a new entry for stage 1):

`` `Sonnet 5` · effort `medium` · `AFK/Auto` ``

Files: `docs/guide.md` only. No code change, no payload change, no version bump.

Add one bullet to `docs/guide.md`'s "What this deliberately doesn't do" list (`docs/guide.md:548`),
after the "It doesn't guess" bullet. Text, to paste as is:

```markdown
- **It doesn't share its memory between copies of a repo.** The plugin keeps what it knows about a
  project (the wrap receipt, an item you started, where the last session ended) under
  `~/.claude/reentry-state/`, filed by the folder's full path. Anything that changes that path or
  that `~/.claude` gives the same repo a separate memory: the repo opened from Windows and from WSL
  (WSL has its own `~/.claude`, and `/mnt/c/...` is a different path anyway), a second clone, a
  checkout on a server, or the same folder after you move or rename it. Your files travel through
  git; this memory does not. So a wrap in one copy does not close another, and nothing tells you.
  The one exception is the wrap marker, `.claude/.last_wrap`, which lives inside the working tree:
  two views of the same folder share it, which is why a WSL session on `/mnt/c/...` can agree with
  Windows about "commits since the last wrap" and still have no record of the wrap's receipt. Wrap
  in the copy you worked in.
```

Tests: none needed for a prose bullet; run `python plugins/cairn/tools/run_tests.py --timeout=300`
anyway, because `docs/guide.md` is on `test_payload_clean.py`'s `PUBLIC_SET` (line 62), so the
new bullet is scanned for personal references. The text above names no real path or person.

Done: the bullet is in `docs/guide.md`, the suite passes, and B40 is narrowed to stage 2 in
`BACKLOG.md` by the attended pass (shared file). Optional, same pass: replace
`docs/cursor-adapter-requirements.md:601-606`'s paragraph with a one-line pointer to the guide, so
the statement lives in one place.

## Questions for the reviewer (stage 2, aliasing)

### Q1. Is aliasing worth building at all?

- **A. No: document only, and close B40 after stage 1.** The cross-environment problem is B36's,
  and B36's brief already proposes naming the environment on every row rather than merging state.
  A wrap is a fact about a working tree; two clones are two trees, and merging their receipts would
  let one tree's `SET` hide the other's unpushed work.
- **B. Alias only views of the SAME tree** (`/mnt/c/x` from WSL and `C:\x` from Windows): one
  memory per physical folder. Needs WSL to read the Windows config dir, which it does not today
  (WSL has its own `~/.claude`; `docs/briefs/B36-afk-ready.md:33`), and a path normaliser (`/mnt/<d>/` to `<D>:\`). Different clones stay
  separate.
- **C. A user-declared alias table** (shaped like `PROJECT_ALIASES`) mapping several paths to one
  slug. Merges clones too, with the risk in A.

Recommendation: **A**. B is the only merge that is clearly correct, and it fixes one view of one
tree while two config dirs still disagree; B36 is where cross-environment reporting belongs.

### Q2. A moved or renamed checkout: carry the state, or just say so?

- **A. Say so.** At session start, when this root's slug has no state but a slug with the same
  sanitised name prefix exists whose recorded `root` (in `last_exit.json`) no longer exists, print
  one line naming the old path. Read only. "No state" means no files in the slug directory, not a
  missing directory: `state_dir()` creates the directory on every call
  (`reentry_state.py:518`), so the check must run before any hook has called it this session, or
  test for files. The name prefix is truncated to 32 characters (`:512`), so compare the slug's
  name half exactly, not as a string prefix of the folder name. This catches a **move** (same folder name, new parent)
  only: a **rename** changes the name half of the slug too, so nothing on disk links the two, and
  a rename stays silent unless the old `last_exit.json` roots are compared by remote URL, which
  is a larger design. It also has a false positive: different repos with the same folder name
  share the name prefix, so after one `workspace` checkout is deleted, the first session in an
  unrelated new `workspace` checkout elsewhere would report a "move" that never happened. The line must say
  "possibly moved" and name the old path, never assert it.
- **B. Migrate**: rename the old state directory to the new slug. Writes on a guess about identity.
- **C. Nothing.**

Recommendation: **A**, as its own small backlog entry if accepted (it touches
`session_orientation.py`, a hook).

### Q3. The temp-dir fallback

- **A. Say so once** when `state_dir()` falls back (a stderr line or an orientation line), since
  state written there is invisible to the next normal session.
- **B. Leave it**: the fallback is rare and better than no state.

Recommendation: **A**, low priority; not part of stage 1.

## Out of scope

- B3 (wraps on another machine, the git half) and B36 (sweeping several environments).
- Any change to `state_dir()`'s key: changing it orphans every existing project's state, which is
  itself the failure this entry describes.

## Side note for the attended pass

`docs/decisions.md` uses "B63" for a different item (D33, the installer refusing a newer rules
block); B40's own entry says it "was `agent-reentry` B63". A reader following "B63" from the entry
lands on D33. Annotating one of them with the old repo's name would remove the ambiguity.
