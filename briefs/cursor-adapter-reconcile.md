# Cursor adapter v1 — reconcile the hand-written copy that already exists

`Opus 5` · effort `high` · `HITL/Plan` · from `BACKLOG.md` B57

Migrated 2026-09-23 from the private source repo, where it was queue item 1 (backlog B123).
**Read [docs/cursor-adapter-requirements.md](../docs/cursor-adapter-requirements.md) in full before
anything else.** It is a verification report — hooks, skills, distribution, scripting, identity,
what cannot be honoured — and it already answers the questions a fresh start would re-investigate.
Its backlog ids are the private repo's; the map is in its header.

## Why this exists

A Cursor session reads the same file contract (`NEXT.md`, `INBOX.md`, `BACKLOG.md`, `CHANGELOG.md`,
the rationale record) but gets none of the mechanism: no orientation at session start, no wrap
receipt, no backlog sync, and none of the rules added since it was written. Anyone who uses both
harnesses — or a colleague who uses only Cursor — re-enters from a partial system that *looks* like
the whole one.

## The premise inverted — this is a reconciliation, not a build

Checked 2026-09-09 and re-measured 2026-09-23. **A hand-written adapter is already installed** on one
work laptop, and it is also tracked in git in the operator's hub repo, byte-identical:

| File | Lines | Written | sha256 (2026-09-23) |
|---|---|---|---|
| `~/.cursor/skills/next/SKILL.md` | 40 | 2026-09-04 | `ddb50c58…94b6f3` |
| `~/.cursor/skills/wrap/SKILL.md` | 62 | 2026-09-04 | `7b3536a7…a391efc` |

The hub copies are at `workspace/.cursor/skills/workflow/{next,wrap}/SKILL.md`, so the pair can be
read from any machine that has that repo. It has **not changed since 2026-09-04**. Compare 224 and 736
lines for this plugin's own skills at the time. Its header names *"the `reentry` Claude Code plugin"*,
so it predates the rename (D18) and about fourteen versions of rules, and it says Cursor has no
`SessionStart` equivalent — which the report shows is false. Both skills set
`disable-model-invocation: true`, so neither runs unless typed.

**So the first question is not "what should an adapter do". It is whether the existing pair gets
regenerated from this repo's source, or stays hand-maintained and drifts again.** Two competing
copies is the condition this item exists to prevent, and there are already two — three, counting
the Claude plugin skills that Cursor also surfaces when third-party skill loading is on.

## What is already decided (by the report — do not reopen without reading §6)

- **The file contract is unchanged.** There is no second format.
- **Native `.cursor/hooks.json` hooks for side effects only** (schema v1, flat per-event arrays —
  *not* Claude Code's shape): an item-open stamp on `beforeSubmitPrompt`; a repo recorder on
  `postToolUse` **and** `afterShellExecution`/`afterFileEdit`; a dirty-tree breadcrumb on
  `stop`/`sessionEnd`.
- **Orientation comes from an always-on Cursor rule** (or a tiny auto-invoked skill) that runs
  `session_orientation.py` before the first reply. It does *not* come from
  `sessionStart.additional_context` injection, which is unverified and reported broken.
- **The Python is reused verbatim, with explicit paths.** `CLAUDE_PLUGIN_ROOT` and
  `CLAUDE_PROJECT_DIR` are empty in a Cursor shell, and hook JSON does not travel.
- **The rules text has one source, `rules/CLAUDE.md`, with two generated artefacts** (the
  `~/.claude/CLAUDE.md` block, and a Cursor rule). Never fork the text.
- **There is no timesheet, Cursor version-drift or GitLab push until each has a Cursor-shaped
  path.** See B52 and B56.

## What has to be decided — this is why it is `Plan`

1. **Regenerate or hand-maintain?** If regenerate, from what, and when: a build step in this repo,
   a tool the installer runs, or a Cursor plugin (`.cursor-plugin/plugin.json`)? The report ranks a
   real Cursor plugin first. Note that account-level installs land on every machine sharing the
   Cursor account, which is wanted for the adapter and dangerous for anything machine-specific.
2. **Drift detection.** Nothing on the Cursor side does what `version_drift.py` does. At minimum it
   needs a hash or version of the installed skills compared against the source, and one line in
   the orientation. Warn, never auto-install.
3. **What happens to the existing pair and the hub copies** once generated ones exist. This is the
   operator's hub repo, so it is their call. A change there goes through that repo's `INBOX.md`,
   not a direct edit.

## Where it stops

`HITL` — it stops at the three decisions above, before writing code, with a recommendation for
each. The build then runs and pushes. Installing on each Cursor machine is machine state, so it is
filed as one watch per machine in the operator's machine-state repo, never here.

## Verification

- The generated skills and rule name no private path, and pass `test_payload_clean.py` if any of
  it ships in `plugins/`.
- The orientation runs from a real Cursor session in a project that has a `NEXT.md`. The first reply
  relays the queue. A hand run of the script doesn't count — see the v1.60.0 lesson in
  `CHANGELOG.md` about tests written the same way as the code.
- A drift check fires against a deliberately stale copy, and stays silent against a current one.
