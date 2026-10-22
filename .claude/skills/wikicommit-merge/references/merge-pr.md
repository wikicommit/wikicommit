---
pass_token: "c406d48d"
---

# Step 7: wait for a mergeable state, then merge (`merge-pr`)

`<PR number>` is the run record's `pr` list and `<default branch>` its `default_branch` list. Name the PR explicitly in every `gh pr` command below rather than relying on the current branch, so a resumed run acts on the same PR.

**This is an agent step, not one the workflow engine runs itself**, because the wait can take up to 300 seconds: a command that long would outlast the time limit an agent's shell tool puts on a single command, and the workflow engine runs its own steps synchronously inside one. Poll with separate short commands as described below.

Report `merged` once the merge has gone through and the default branch is checked out and pulled — the workflow engine's check asks GitHub whether the PR is `MERGED` and confirms the current branch, so a merge that did not happen cannot be reported as one. Report `awaiting-merge` when the default branch requires a review the PR does not have yet (below): the PR stays open for a person, and the run ends there as finished, not failed. Report `failed` with `--reason` on any of the failures below, after showing the cleanup procedure: the run then stops before Steps 8 and 9, and its record says why. If a resumed run finds the PR already merged, just make sure the default branch is checked out and pulled, and report `merged`.

### Step 7: Wait for Mergeable State, Then Merge

This skill does not use `gh pr merge --auto`. GitHub's auto-merge feature (the `enablePullRequestAutoMerge` mutation that `--auto` falls back to whenever the PR isn't immediately mergeable yet) is gated by the repository's `allow_auto_merge` setting, and that setting is unavailable — not misconfigured, unavailable — on GitHub Free private repositories; there is no CLI, API, or UI path to turn it on. Since Step 3 already ran every quality gate locally before this PR ever existed, there is nothing left for auto-merge's "wait for checks, then merge" behavior to add. All that's actually needed is to wait out the few seconds GitHub takes to finish computing the PR's mergeability, which is plan-independent and needs no special permission.

Poll:

```bash
gh pr view <PR number> --json state,mergeStateStatus,reviewDecision,statusCheckRollup
```

- Polling interval: 10 seconds (check → wait 10s → check, repeated up to 30 times; the first check happens before any wait)
- Maximum wait: 300 seconds (30 iterations)
- If `state` is `CLOSED` (closed without merging) → stop polling immediately and treat it as a failure
- If `mergeStateStatus` is `CLEAN` → stop polling and proceed to the merge command below
- If `mergeStateStatus` is `DIRTY` → stop polling immediately (do not wait out the remaining iterations) and treat it as a failure: GitHub cannot cleanly compute a merge commit at all (an actual conflict — waiting doesn't fix that)
- If `mergeStateStatus` is `BLOCKED`, read the other two fields before deciding, because `BLOCKED` covers more than one cause:
  - **A required status check is still running** — an entry of `statusCheckRollup` that is a check run (`__typename` `CheckRun`) whose `status` is not `COMPLETED`, or a commit status (`__typename` `StatusContext`, which has `state` and no `status`) whose `state` is `PENDING` or `EXPECTED` → keep polling. A running check is in flight, not a verdict, whatever `reviewDecision` says
  - **A required status check failed** — every check has finished and one of them did not pass (a check run's `conclusion` other than `SUCCESS`, `NEUTRAL` or `SKIPPED`, or a commit status's `state` `FAILURE` / `ERROR`) → stop polling and treat it as a failure
  - **A required review** — no check is running or failed, and `reviewDecision` is `REVIEW_REQUIRED` (or `CHANGES_REQUESTED`) → stop polling: the PR waits for a person (see "Leaving the PR for a person" below). Do not decide this from `reviewDecision` alone while a check is still running
  - **Anything else** (no check running or failed, and no review required — a policy blocker this Skill cannot see) → stop polling and treat it as a failure
- Any other value (`UNKNOWN`, `UNSTABLE`, or anything else GitHub returns) is treated as still in flight and polling continues
- If `CLEAN` is not observed within 300 seconds: when the last poll was `BLOCKED` with `reviewDecision` `REVIEW_REQUIRED` and only running checks in the way, the PR needs a person anyway — leave it for one as below (the checks finish on GitHub before the person merges). Otherwise display an error and abort

On failure (`CLOSED`, `DIRTY`, a `BLOCKED` that is not a required review, or timeout), guide the user through the following and report `failed` (Step 8 and Step 9 do not run — since the merge did not go through, there is nothing new on the default branch for either post-review or generation-failure tracking Issues to target):

- Cleanup procedure for the leftover branch/PR:
  1. `gh pr close <PR number>`
  2. `git push origin --delete <branch name>`
  3. Re-run `/wikicommit-merge`

### Leaving the PR for a person (`awaiting-merge`)

A default branch that requires a review is the user's own choice to have a person read the change before it is published, so a PR blocked on that review is the expected result, not a failure. **Do not show the cleanup procedure and do not close the PR** — closing it throws away exactly what the person is meant to read. Instead:

1. Return to the default branch, so the next run starts from it (the PR's commit stays on its branch and on GitHub):

   ```bash
   git checkout "<default branch>"
   ```

2. Tell the user, in these terms: PR #<PR number> waits for a required review; a person reviews and merges it on GitHub; **after it is merged, run `/wikicommit-merge` again** — that run finds the merged PR, pulls the default branch and files the review tracking Issues (Step 8) and any generation-failure Issues (Step 9) for its pages, even when there is nothing new to merge. Until then its pages are not on the default branch and have no tracking Issue. In a non-interactive run, put the same sentence in what the run hands back.
3. Report `awaiting-merge` (no `--reason` needed). The engine's check asks GitHub that the PR is `OPEN` with `reviewDecision` `REVIEW_REQUIRED` or `CHANGES_REQUESTED`, and that the default branch is checked out. The run then finishes (`finished_because: merge-pr: awaiting-merge`) without Steps 8–10.

Once `mergeStateStatus` reaches `CLEAN`, merge directly without `--auto`:

```bash
gh pr merge <PR number> --squash
```

`gh pr merge` without `--auto` merges immediately using the repository's ordinary (always-available) merge permission, rather than going through `allow_auto_merge`. If this command exits with an error despite `mergeStateStatus` having just reported `CLEAN` (e.g. a race with another merge landing on the base branch in between), display the error, guide the user through the same cleanup procedure above, and report `failed`.

Once the merge is confirmed (`gh pr merge` exits 0), return to the default branch:

```bash
git checkout "<default branch>"
git pull origin "<default branch>"
```
