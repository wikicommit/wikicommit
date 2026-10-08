---
pass_token: "4b250a1f"
---

# Step 6: push and open the PR (`open-pr`)

Push the branch and open the PR. Report `opened` with `--add pr=<PR number>`: the run record keeps the number, and the next two steps read it from there, so it survives a compaction. The workflow engine's check confirms the number was recorded and that the branch is on `origin`.

If a resumed run finds a PR already open for this branch (`gh pr list --head <branch name> --json number`), do not open a second one — report that one's number.

### Step 6: Create PR

```bash
git push origin <branch name>
python <this Skill's directory>/scripts/workflow_checks.py pr-body --run <run> \
  | gh pr create \
      --title "wiki: bulk update $(date +%Y-%m-%d)" \
      --body-file - \
      --base "<default branch>"
```

**The body is printed by `workflow_checks.py pr-body`, not written by you.** It is built from what the quality checks recorded beside the run, so it is the same after a compaction, and the free-form finding text — a lychee finding is a URL that routinely contains `&`, markdownlint quotes the offending line verbatim — reaches `gh` through a pipe (`--body-file -`), never through a shell-quoted argument. It looks like this:

```markdown
Automatically generated PR by WikiCommit.

Quality checks ran with no blocking errors. Warnings: <total count>.

## Warnings

### <tool or script name> (<count for that tool>)

- <finding>
- <finding>
- (+<N> more)

Only the first few findings per tool are listed here. Re-running WikiCommit's quality checks reproduces the full list.
```

When there are no warnings it is just the first line plus `Quality checks ran with no blocking errors and no warnings.` What it holds is deliberate, so do not edit it:

- **It says what happened, not that everything is fine.** Never a fixed "Quality checks passed." — that is false whenever warnings appeared and the run proceeded. It states the two facts instead — no blocking errors, and how many warnings there were.
- **The body is the same whether or not a person was present.** A PR is a record read later, and what it asserts should not depend on how the run happened to be driven.
- **A few findings per tool, not all of them.** Each tool gets its count and its first 5 findings verbatim, then `(+N more)`. Reproducing everything puts dozens of lychee 4xx lines in the body, and a report that is always long stops being read. The count is what carries the signal; the samples are there so a reader can tell what kind of finding it is.

Obtain `<PR number>` from the `gh pr create` output (the PR URL) or via `gh pr view --json number -q .number`, and pass it as `--add pr=<PR number>` when you report this step; Step 7's cleanup procedure and the completion report read it from the run record.
