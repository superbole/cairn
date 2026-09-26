# Brief — spend the weekly allowance on AFK work, through the France trip (1–20 Oct 2026)

**Opus 5 · high · HITL/Auto.** A planning session. It reads, asks, and writes a plan. It creates **no**
scheduled task or routine until Sheldon approves the plan. That stop is written here instead of
relying on Plan mode, because Plan mode is read-only and would block the lanes below.

## Session shape (decided 2026-09-26) — one session, and the lanes stay in their own worktrees

Sheldon doesn't want parallel sessions, because they have overlapped before. So **this one session
also runs Queue items 2 and 3**, as its own background subagents, to use the work week's tokens
before Sunday 16:00:
- **Before anything else**, launch B10 (`briefs/receipt-no-baseline.md`, Opus) and B23
  (`briefs/measure-context-no-tiktoken.md`, `model: sonnet`) as background agents with
  `isolation: "worktree"`, one per item, using `docs/running-a-batch.md`'s lane rules. Each gets only
  its own brief. None touches `NEXT.md`, `BACKLOG.md`, `CHANGELOG.md`, `README.md`,
  `docs/decisions.md` or `plugin.json`. Each writes a dossier and commits on its own branch in its
  worktree. Check first that their files are disjoint from each other and from this plan's files
  (`docs/plans/`, `running-a-batch.md`).
- **Then work item 1 with him** while they run. When a lane reports, pause at the next natural
  break: read its dossier against its diff, run the tests, and merge it into `main` locally. Then
  do the bookkeeping: one version bump, CHANGELOG, closing the item, and the Queue. He is present,
  so this session pushes once he has seen the review (a HITL push).
**Deadline: before he leaves on Thursday 2026-10-01.** A test firing has to run while he is still
home (see step 6).

## The problem

The weekly allowance is use-it-or-lose-it (see the profile, "Claude accounts and weekly usage
resets"). On Saturday 2026-09-26 at ~11:00 the work account stood at **69%** used, with the reset at
Sunday 16:00. He is in France **1–20 Oct**. Three work resets fall inside that trip, on 4, 11 and 18
Oct, so about three weeks of allowance go unspent unless AFK work runs without him. France is CEST
(UTC+2), the same offset as SAST until 25 Oct, so local times line up.

## Decided by Sheldon on 2026-09-26 — do not reopen

- **Reset times are in the profile.** Work is Sunday 16:00, private (DeepThought) is Thursday 15:00,
  both SAST. The private account resets on the day he leaves (1 Oct), then on 8 and 15 Oct. So the
  private week that ends Thu 1 Oct 15:00 is spent before departure, and 1–15 Oct is two more private
  weeks with nobody home.
- **DeepThought stays on during the trip** and runs the private account's AFK work the same way.
  He expects `forge` has backlog items. Check that repo's `BACKLOG.md`; it lives on DeepThought, so
  that inventory happens there. The private week ending Thu 1 Oct 15:00 can start on DeepThought now.
- **Local scheduled runs on the work account go on NB5, not NB1.** NB5 is always on at the office,
  on the office network (so the VPN-only proxy that killed NB1's 05:00 run is not a factor), and a
  colleague can get to it if something breaks. Someone has to be at NB5 to set it up, so the setup
  day is part of the plan. NB5's hub is the work-GitLab `workspace` hub, and its watches go there.
- **No Remote Control and no push notifications on the work account:** ICT blocks them. Don't plan
  either for NB5. Untested on the private account. Because of this, **the PR is the notification**,
  but only for GitHub-hosted repos (`superbole/*`, cairn included, whichever Claude account runs
  them), where the GitHub mobile app alerts him. **Work repos are on the work GitLab**, so this does
  not reach them. Open: does GitLab's MR email reach his work mailbox on his phone, and can he open
  the MR from France without the VPN? If he can't, work-GitLab output piles up until 20 Oct, and the
  plan should put the trip's AFK work on GitHub-hosted projects.
- **Review model: one branch and one PR (or MR) per item, and nothing merges to `main`
  unreviewed.** He wants the branches kept in order. **Naming confirmed by him 2026-09-26:**
  `afk/<YYYY-MM-DD>-<nn>-<Bnn>-<slug>`, where `nn` is the order within that day's firing and `Bnn`
  the backlog item. Branch each one off the current `origin/main`, not off the previous branch, so
  the PRs merge in any order and a bad one can be closed without touching the rest. Stack only
  where one item truly depends on another, and say so in both PR bodies. The PR body is the lane
  dossier: its four fixed sections from `running-a-batch.md`. This **replaces** "commit locally, stop
  before the push" for the trip. Pushing a branch is not merging, but it is outward-facing. Write
  the exception into `running-a-batch.md` and `docs/decisions.md`, scoped to `afk/` branches, and
  keep `main` push-denied (B69's deny rule, narrowed to `git push origin main`).

## What is already known — do not re-derive

- **Local scheduled tasks (Claude Desktop)** only run while the machine is on and awake. On NB1 the
  VPN must also be up: the 05:00 wave on 2026-09-26 died on `ECONNREFUSED` when it dropped. That is
  `workspace` W11 (work GitLab), in `~/Projects/workspace/docs/briefs/nb1-sync.md`. They also start in
  Manual mode (`cairn` B69 in `BACKLOG.md`), and a failed firing shows up only in the routine's Runs
  list.
- **Cloud routines** (the `schedule` skill) run on Anthropic's infrastructure, with no laptop and no
  VPN. They can only reach repos the cloud can clone. GitHub `superbole/*` should be fine; the
  on-prem GitLab probably is not. **Verify both before building on either.**
- **The AFK rule:** unattended work commits locally and stops before the push (`rules/CLAUDE.md`).
  Nineteen days of that is a large unreviewed pile. This plan has to decide the review model, not
  inherit it by accident.
- **Batch mechanics are binding:** `docs/running-a-batch.md`. Headroom comes from
  `tools/measure_usage.py --window`, which measures only the 5-hour window, not the weekly one. File
  ownership has to be disjoint across lanes.
- **Ways to reach him:** on the work account, only the PR or MR itself (see above). On the private
  account, `PushNotification` and Remote Control are untested; test them on DeepThought. WhatsApp or
  Discord would need an MCP or integration, and on a work machine ICT would likely block that too.

## Do

1. **Read the profile's reset table.** Both times are recorded; don't ask again.
2. **Inventory the runnable AFK work, per project, on both accounts.** Every repo with a `NEXT.md`
   under `~/Projects` on NB1, and ask what lives on DeepThought. For each: its AFK/Auto backlog count,
   its git host, and whether the cloud can reach it. Use `check_repos.py --known` for the list.
   Don't read every backlog in full: count first, then read only the candidates.
3. **Decide with him** (the checkpoint). Only what the section above leaves open:
   - for the private account, whether to use local runs on DeepThought (decided it stays on) or
     cloud routines, and whether `PushNotification` works there;
   - when he can get to NB5 before Thursday to set it up;
   - whether work-GitLab MRs can be read from France (see above).
4. **Draft the schedule.** Dated firings per account, sized against the weekly allowance: cloud
   where the repo is reachable, local only where it must be. Lanes follow `running-a-batch.md`.
   Front-load each week, so a failed firing can still be retried before the reset. Put the dossier
   and handover names in the `YYYY-MM-DD-HHMM-<lane>` form that doc asks for.
5. **Prerequisites before any local firing:** B69 (allow and deny rules in `.claude/settings.json`,
   so the run can't stall in Manual and can't push) and W11 (the VPN route). Queue them if the
   plan needs them.
6. **A dry run before Thursday:** one small real firing per mechanism the plan uses (NB5 local, a
   cloud routine, DeepThought if it's used). Confirm the PR reached his phone and the branch name
   and base came out as specified.
7. **Write it down:** the plan as `docs/plans/2026-10-trip.md`, a watch in each affected
   `NEXT.md` for every review point (dated, with `added`), and the queue refills with briefs. Create
   the scheduled tasks and routines **only after he approves the plan.**

## Also decide

Should cairn learn the reset itself (a `resets:` field the orientation reads, printing
"work allowance resets in 29h, 31% left, N AFK items runnable"), or is the profile line enough?
If it should, file it in `BACKLOG.md` with the design; don't build it in this session.

## Done when

The plan is approved and on disk, the dry run passed, and every firing and review point is a
dated watch. Nothing is left for him to remember.
