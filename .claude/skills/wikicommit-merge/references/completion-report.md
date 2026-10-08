---
pass_token: "b4f1fae7"
---

# Step 10: completion report (`report`)

Report this step to the workflow engine **first** — finishing the last step is what closes the run record, so its elapsed time covers the whole run.

### Step 10: Completion Report

Report `reported` with the counts, which the workflow engine writes into the run record's `outcome` as it closes it:

```bash
python .wikicommit/scripts/skill_workflow.py done <run> --step report --outcome reported \
    --token <the pass_token above> \
    --count pr=<PR number> --count tracking_issues=<N> --count failure_issues=<N>
```

Counts are integers, so `pr=<number>` records which PR this run produced (the run record's `pr` list holds it). This Skill's counts are deliberately not the same keys as the generating Skills': it does not write pages, and a shared vocabulary would mean shipping keys that are permanently zero on one side or the other.

Then report the run record's path and elapsed time along with the following. The Issue numbers from Steps 8 and 9 are not kept in the run record; if this session was resumed after those steps and they are no longer in front of you, say so rather than guessing, and give the counts:

- The bulk update PR number and branch name created in Step 6
- The warning total Step 3 carried forward, and that it was written into the PR body (omit if there were none)
- The list of `<new source files>` included in the bulk update PR from Step 2 item 3 (omit if none)
- The list of tracking Issues newly created in Step 8 (page path, Issue number)
- Any pages skipped in Step 8, with reasons (frontmatter YAML parse failed during the extraction scan / an open tracking Issue already exists / issue creation error)
- The list of generation-failure tracking Issues newly created in Step 9 (source management file path, Issue number)
- Any management files skipped in Step 9, with reasons (frontmatter YAML parse failed during the extraction scan / an open tracking Issue already exists / issue creation error)
