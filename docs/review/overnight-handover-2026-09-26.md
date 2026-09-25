# Overnight handover — 2026-09-26

The entry point for W5. The night starts on `42a3fc1`. **Nothing is pushed and the backlog is not
synced.** Both wait for Sheldon.

## Wave 1

Scheduled firing `cairn-lane-batch-2026-09-25-2333`, on NB1. Three Opus lanes ran concurrently on
disjoint files. The result is v1.63.0, unpushed.

### Judgement calls made on your behalf (read these first)

1. **The dossier names follow the task prompt, `docs/review/lane-<x>-2026-09-26.md`.** They do not
   use the `YYYY-MM-DD-HHMM-<lane>` prefix that `docs/running-a-batch.md` asks for. Wave 2's files
   need distinct names, or they will collide with these.
2. **The B26 block digest is a new `install_rules.block_digest()`, not `wrap_receipt._digest()` as
   the brief said.** `_digest()` hashes the whole file, including your own notes outside the
   markers, so no two machines would ever match (D34).
3. **B59: `tools/` scripts go through `run.sh` (widened), not a second shim.** `<root>` is written
   as a placeholder defined in words: two directories above the skill's base directory. In the
   rules file it can also be cairn's `installPath` in `installed_plugins.json` (D35). `run.sh` now
   trusts `CLAUDE_PLUGIN_ROOT` only when `$0` is that root's own `run.sh`. Lane B also fixed two
   call sites the brief's grep missed: step 5b's `push_check` and the verdict rule's `--check`.
4. **The B64 guard does not judge a root where this session has no baseline.** There it allows,
   with an UNKNOWN note, even though `--check` would say OPEN (a stale marker from an earlier
   session). The cost: a session whose baseline stamp failed can archive unwrapped (D36).
5. **B64: `wrap_receipt.py` was not edited.** "HEAD moved after SET" already reads OPEN through the
   `marker` step, and a test pins it.
6. **B63 protects only once every installed copy is v1.63.0+.** A v1.62.0 installer still running
   anywhere (NB1 had one on 2026-09-25) will still downgrade a v1.63.0 block. Since B59 changed
   the rules body, that now actually matters. After you push, update the plugin on every machine
   and restart. `check_install.py` shows the block digest per machine.
7. **The Queue was refilled with B10 (a receipt with no baseline) and B23 (no `tiktoken`).** Their
   briefs are new, written tonight: `briefs/receipt-no-baseline.md` and
   `briefs/measure-context-no-tiktoken.md`. B10 was chosen over the other AFK items because it is
   the verdict's own honesty. B23 was chosen because every lane tonight had to estimate tokens by
   hand. The Cursor adapter (HITL) stays, now as item 3.
8. **The `next-id` marker is written as 68, the highest id spent,** because that is how the parser
   reads it. The 2026-09-25 wrap had written 65, reading it as next-free, so B65 was skipped and
   never filed. Filed as B67.
9. **The README "What you get" table was changed:** a new archive-guard row, plus one sentence
   each in the `/cairn:wrap`, `check_install.py` and "Writes `~/.claude/CLAUDE.md`" rows.
   `incidents.md` was not changed, because no skill RULE changed, only how commands are spelled.

### Items

| Item | Status | Where |
|---|---|---|
| B63 — refuse to downgrade a newer rules block | **closed** | lane A, `ec9b824` |
| B26 — say what changed in the rules block | **closed** | lane A, `ec9b824` |
| B59 — make the skills' tool calls resolve | **closed** | lane B, `0d349dc` |
| B64 — archive guard while the wrap is OPEN | **closed** | lane C, `9ca15ce` |
| B66 — two remedies are wrong after B63 | filed | from lane A's "chose not to do" |
| B67 — `next-id` has two readings | filed | from the bookkeeping |
| B68 — the old command form survives in docs and a docstring | filed | from lane B's "chose not to do" |

Nothing was left unfinished.

### Commits (unpushed), and what each depends on

| Commit | What | Depends on |
|---|---|---|
| `ec9b824` | Lane A: B63 + B26 (`install_rules`, `version_drift`, `check_install` and tests) | `42a3fc1` only |
| `0d349dc` | Lane B: B59 (`run.sh`, skills, `rules/CLAUDE.md`, `test_skill_calls.py`) | `42a3fc1` only |
| `9ca15ce` | Lane C: B64 (`archive_guard.py`, `hooks.json`, test) | `42a3fc1` only. Its `hooks.json` entry uses the bare-name `run.sh` form, which works before and after B59 |
| `f4e45e6` | Bookkeeping: v1.63.0, README, CHANGELOG, D33–D36, BACKLOG, NEXT, the two new briefs | all three lanes |
| (this file) | The handover | — |

**Reverting one lane:** `git revert <lane sha>`, then fix `f4e45e6`'s claims by hand. That means
the CHANGELOG bullet, the D-row, the README sentence, and reopening the item in `BACKLOG.md`. A
revert that skips those leaves a CHANGELOG describing work that is no longer in the tree.
Reverting everything is `git reset --hard origin/main`.

### Verification actually run (orchestrator)

The full suite, after the lanes and again after the bookkeeping. The second run is shown:

```
33/33 test files passed
wall clock: 327.5s total (per-file timeout 300s)
ALL PASS

no leak into the real state dir
```

`check_install.py` on NB1, read-only, before the bump. "DIFFERENT block" is correct here: the
repo's rules had B59's edits and the version was not yet bumped:

```
installed : 1.62.0
rules     : 1.62.0   <- C:\Users\SheldonBole\.claude\CLAUDE.md
repo      : 1.62.0   <- C:\Users\SheldonBole\Projects\cairn
block     : 42f6308b63fe (installed)   5f203d1ba733 (this repo's v1.62.0)   — SAME version, DIFFERENT block
OK — installed plugin and loaded rules are both v1.62.0.
exit=0
```

`install_rules._install_block()` was run against a **scratch copy** of the live
`~/.claude/CLAUDE.md` (`CLAUDE_CONFIG_DIR` pointed at the scratchpad; the real file was never
written):

```
('[to the agent] Updated the cairn rules block in …\\cfg\\CLAUDE.md: v1.62.0 → v1.62.0 (same version, different content). Rules text: +4 −0 ~2 lines, in: The WRAP VERDICT is a QUOTATION — you n…. Full diff: `git diff --no-index -- "…\\CLAUDE.md.bak-reentry-install-v1.62.0-f8d3d7b8" "…\\CLAUDE.md"`. The version in YOUR context is the old one until the next session.', False)
---
(None, True)
---   (marker edited to v9.9.9; md5 before and after identical, file count unchanged at 2)
("[to the agent] Did NOT update the cairn rules block in …\\cfg\\CLAUDE.md: it is v9.9.9, NEWER than this plugin's v1.62.0, so writing would roll it back. The file was left untouched; the newer block was kept. This session is running an OLDER copy of the plugin; tell the user to run `claude plugin update cairn@superbole`, then restart.", True)
```

Each lane's own real output is in its dossier. Lane B ran the rewritten lines with
`CLAUDE_PLUGIN_ROOT` unset in Git Bash and WSL Ubuntu, where there is no `python`. Lane C piped a
payload into the guard against the real repo, read-only, and got exit 2 with the real reasons.

**Seen in passing:** the B26 change line is about 600 characters on Windows, because it carries two
absolute scratch paths. It prints once per block change, so I left it.

### Budget

`measure_usage.py --window` before the wave was 53% of the working cap. After the bookkeeping it
was 62%, with about 1.23M billed headroom (~3 Sonnet lanes). The lane completion notifications
reported 163,697, 130,290 and 132,300 subagent tokens. Doubled per `running-a-batch.md`, that is
about 850k.

### Dossiers

- [lane-a-2026-09-26.md](lane-a-2026-09-26.md): B63 then B26
- [lane-b-2026-09-26.md](lane-b-2026-09-26.md): B59
- [lane-c-2026-09-26.md](lane-c-2026-09-26.md): B64

### Waiting on Sheldon

- **The push**, after reading the dossiers against the diffs (W5).
- **`tools/sync_backlog.py`.** It will close #24, #59 and #63, file B64, B66, B67 and B68, and
  label B10 and B23 as queued.
- **After the push, update the plugin on every machine** (judgement call 6).
