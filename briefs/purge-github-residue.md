# Finish the purge on GitHub: delete issue #68, ask Support to drop the old commits

`Sonnet 5` · effort `medium` · `HITL/Auto` · from `BACKLOG.md` B96

B93 rewrote and force-pushed history on 2026-10-01 (`main` is `f0e288b` and later). No branch on
`superbole/cairn` contains the old commits now. Two copies are left that only Sheldon can remove,
because both are permanent deletions an agent may not perform, and the second one needs a support
ticket in his name. Decided in `docs/decisions.md` D48.

## What is left

1. **Issue #68.** Its current title and body are clean, but its timeline has a public "changed the
   title" event that shows the old title, and its body has edit revisions. Deleting revisions one by
   one would leave the title event, so the decision is to delete the whole issue.
2. **GitHub's copies of the old commits.** `refs/pull/84/head` through `refs/pull/90/head` (closed
   PRs) still point at the pre-rewrite history, and any old SHA (for example `5d2cd6a`) still opens
   at `github.com/superbole/cairn/commit/<sha>`. Only GitHub Support can remove these.

## Steps

1. **Done 2026-10-01** (he ran it; `gh issue view 68` now returns not found). He runs (permanent, admin only):
   ```bash
   gh issue delete 68 -R superbole/cairn --yes
   ```
2. **He sends** a request at <https://support.github.com/request>. The portal has no sensitive-data
   option: choose Repositories, then **Repository features**, then **Branches**, with URL
   `https://github.com/superbole/cairn`. **Never "Deletes"**: it leads to a
   whole-repository purge confirmation. GitHub's guide ("Removing sensitive data from a repository",
   "Fully removing the data from GitHub") asks for the repo, the number of affected PRs and the
   first changed commit. Draft, plain enough to send as is:

   > I rewrote the history of superbole/cairn on 2026-10-01 to remove personal information about
   > me, and force-pushed every branch. No branch still references the old commits, and the
   > repository has no forks.
   >
   > Affected pull requests: 7 (#84 to #90, all closed). Their refs still point at the old history.
   > First changed commit: 5d2cd6a
   >
   > Please dereference those pull requests, run a garbage collection, and remove the cached views
   > of the old commits. The data is personal rather than a credential, so it can't be rotated.
   > Thank you.

   Do not paste or describe the removed text in the ticket, an issue or the chat. The SHA is enough.
3. **The agent checks**, after he has done both: `gh issue view 68 -R superbole/cairn` should fail
   with not found. B70 has already left `BACKLOG.md` (closed and synced), so nothing in the
   file points at #68. Then close this item.
4. **Support's reply is a watch, not a queue slot.** Once the ticket is sent, replace this item with
   a dated watch (about two weeks out) to check that `github.com/superbole/cairn/commit/5d2cd6a`
   returns 404.

## Where it stops

At step 1 and at step 2. Both are his. The agent drafts and verifies; it does not delete or submit.
