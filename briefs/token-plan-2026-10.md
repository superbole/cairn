# Brief — spend the weekly allowance on AFK work, through the France trip (1–20 Oct 2026)

**Opus 5 · high · HITL/Plan.** A plan session. It reads, asks, and writes a plan. It creates **no**
scheduled task or routine until Sheldon approves the plan.
**Deadline: before he leaves on Thursday 2026-10-01.** A test firing has to run while he is still
home (see step 6).

## The problem

The weekly allowance is use-it-or-lose-it (see the profile, "Claude accounts and weekly usage
resets"). On Saturday 2026-09-26 at ~11:00 the work account stood at **69%** used, with the reset at
Sunday 16:00. He is in France **1–20 Oct**. Three work resets fall inside that trip, on 4, 11 and 18
Oct, so about three weeks of allowance go unspent unless AFK work runs without him. France is CEST
(UTC+2), the same offset as SAST until 25 Oct, so local times line up.

## What is already known — do not re-derive

- **Local scheduled tasks (Claude Desktop)** only run while the machine is on and awake. On NB1 the
  VPN must also be up: the 05:00 wave on 2026-09-26 died on `ECONNREFUSED` when it dropped. That is
  `workspace` W11 on pta-git2, in `~/Projects/workspace/docs/briefs/nb1-sync.md`. They also start in
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
- **Ways to reach him:** Claude Code has a `PushNotification` tool, and Remote Control lets him answer
  a session from claude.ai/code on his phone. Neither has been tested for this. WhatsApp or Discord
  would need an MCP or integration. Prefer the built-ins, unless testing shows they fail.

## Do

1. **Ask for the private account's weekly reset (DeepThought), and write it into the profile** at
   `~/.claude-private/cairn/profile.md` (repo `superbole/cairn-private`). Copy it to
   `~/.claude/reentry-profile.md`, commit and push. This is the first checkpoint.
2. **Inventory the runnable AFK work, per project, on both accounts.** Every repo with a `NEXT.md`
   under `~/Projects` on NB1, and ask what lives on DeepThought. For each: its AFK/Auto backlog count,
   its git host, and whether the cloud can reach it. Use `check_repos.py --known` for the list.
   Don't read every backlog in full: count first, then read only the candidates.
3. **Decide with him** (the checkpoint):
   - which machines stay on during the trip, and whether NB1 can hold the VPN (always-on, no sleep);
   - the review model while he's away. For example: cloud routines push to a branch and open a PR he
     can read on his phone, with nothing merging to `main` unreviewed. Or everything piles up locally
     until 20 Oct;
   - the notification channel. Test `PushNotification` to his phone **now**, while he's here.
4. **Draft the schedule.** Dated firings per account, sized against the weekly allowance: cloud
   where the repo is reachable, local only where it must be. Lanes follow `running-a-batch.md`.
   Front-load each week, so a failed firing can still be retried before the reset. Put the dossier
   and handover names in the `YYYY-MM-DD-HHMM-<lane>` form that doc asks for.
5. **Prerequisites before any local firing:** B69 (allow and deny rules in `.claude/settings.json`,
   so the run can't stall in Manual and can't push) and W11 (the VPN route). Queue them if the
   plan needs them.
6. **A dry run before Thursday:** one small real firing, per mechanism the plan uses. Confirm the
   notification reached him and the output landed where the review model says.
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
