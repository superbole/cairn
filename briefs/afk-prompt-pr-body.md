# Install `body` in the `cairn-afk-firing` prompt's `gh pr view` fields

**Sonnet · medium · HITL/Auto.** Deadline: before the firing on **Sunday 2026-10-04 at 17:00**.
Otherwise that run's reviews of PRs #102 to #105 will again say they couldn't get the PR body
(the dossier).

## What

Source: `superbole/claude-inbox` #2. The `claude-inbox-check` run on 2026-10-03 prepared the diff
and posted it there, but did not install it. Sheldon OK'd installing it from a separate session.

Make three edits to `C:\Users\SheldonBole\.claude\scheduled-tasks\cairn-afk-firing\SKILL.md`, or
use `update_scheduled_task` on `cairn-afk-firing` with the edited prompt:

1. Section 0 allow list: `gh pr view <number> --json number,title,headRefName,...` becomes
   `--json number,title,body,headRefName,headRefOid,files,comments,statusCheckRollup`.
2. Section 3b, R1: make the same field-list change to `gh pr view <n> --json ...`.
3. Section 3b, R3a: "the PR body (dossier) from `gh pr view`" becomes "the PR body (dossier) from
   that `body` field".

Nothing else changes: not the title, the schedule, or `.claude/settings.json` (`gh pr view *` is
already allowed).

## Steps

1. Re-read #2 (`gh issue view 2 -R superbole/claude-inbox --comments`) and check the diff there
   still matches this brief. If Cairn has posted since, follow the newer message.
2. Make the edit. Reading or editing that path asks for approval. That's expected, because it is
   outside the checkout.
3. Read the file back and confirm all three lines changed.
4. Reply on #2 with a comment starting `From Claude:` saying it's installed, then close it.
5. Remove this item from `NEXT.md`'s Queue and add a CHANGELOG entry (`/cairn:wrap`).

**Checkpoint:** the approval prompt on the edit. Sheldon is present for that.
