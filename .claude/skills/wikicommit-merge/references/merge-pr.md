---
pass_token: "c406d48d"
---

# Step 7: wait for a mergeable state, then merge (`merge-pr`)

`<PR number>` is the run record's `pr` list and `<default branch>` its `default_branch` list. Name the PR explicitly in every `gh pr` command below rather than relying on the current branch, so a resumed run acts on the same PR.

**This is an agent step, not one the workflow engine runs itself**, because the wait can take up to 300 seconds: a command that long would outlast the time limit an agent's shell tool puts on a single command, and the workflow engine runs its own steps synchronously inside one. Poll with separate short commands as described below.

Report `merged` once the merge has gone through and the default branch is checked out and pulled — the workflow engine's check asks GitHub whether the PR is `MERGED` and confirms the current branch, so a merge that did not happen cannot be reported as one. Report `failed` with `--reason` on any of the failures below, after showing the cleanup procedure: the run then stops before Steps 8 and 9, and its record says why. If a resumed run finds the PR already merged, just make sure the default branch is checked out and pulled, and report `merged`.

### Step 7: Wait for Mergeable State, Then Merge

This skill does not use `gh pr merge --auto`. GitHub's auto-merge feature (the `enablePullRequestAutoMerge` mutation that `--auto` falls back to whenever the PR isn't immediately mergeable yet) is gated by the repository's `allow_auto_merge` setting, and that setting is unavailable — not misconfigured, unavailable — on GitHub Free private repositories; there is no CLI, API, or UI path to turn it on. Since Step 3 already ran every quality gate locally before this PR ever existed, there is nothing left for auto-merge's "wait for checks, then merge" behavior to add. All that's actually needed is to wait out the few seconds GitHub takes to finish computing the PR's mergeability, which is plan-independent and needs no special permission.

Poll:

```bash
gh pr view <PR number> --json state,mergeStateStatus -q '.state + "|" + .mergeStateStatus'
```

- Polling interval: 10 seconds (check → wait 10s → check, repeated up to 30 times; the first check happens before any wait)
- Maximum wait: 300 seconds (30 iterations)
- If `state` is `CLOSED` (closed without merging) → stop polling immediately and treat it as a failure
- If `mergeStateStatus` is `CLEAN` → stop polling and proceed to the merge command below
- If `mergeStateStatus` is `DIRTY` or `BLOCKED` → stop polling immediately (do not wait out the remaining iterations) and treat it as a failure. These are the only two values that, for a PR this skill just created, need not resolve into `CLEAN` no matter how long the wait: `DIRTY` means GitHub cannot cleanly compute a merge commit at all (an actual conflict — waiting doesn't fix that), and `BLOCKED` means a persistent policy blocker (e.g. a required review) rather than an in-flight computation. Any other value (`UNKNOWN`, or anything else GitHub returns) is treated as still in flight and polling continues
- If `CLEAN` is not observed within 300 seconds, display an error and abort

On failure (`CLOSED`, `DIRTY`/`BLOCKED`, or timeout), guide the user through the following and report `failed` (Step 8 and Step 9 do not run — since the merge did not go through, there is nothing new on the default branch for either post-review or generation-failure tracking Issues to target):

- Cleanup procedure for the leftover branch/PR:
  1. `gh pr close <PR number>`
  2. `git push origin --delete <branch name>`
  3. Re-run `/wikicommit-merge`

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
