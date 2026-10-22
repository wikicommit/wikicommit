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

Counts are integers, so `pr=<number>` records which PR this run produced (the run record's `pr` list holds it). A run that carried no change and only followed up a PR a person merged (the `awaited_prs` list) produced no PR: leave `--count pr` out, and name the followed-up PR in the report instead. This Skill's counts are deliberately not the same keys as the generating Skills': it does not write pages, and a shared vocabulary would mean shipping keys that are permanently zero on one side or the other.

Then report the run record's path and elapsed time along with the following. The Issue numbers from Steps 8 and 9 are not kept in the run record; if this session was resumed after those steps and they are no longer in front of you, say so rather than guessing, and give the counts:

- The bulk update PR number and branch name created in Step 6 (or, for a run that only followed up, the PR numbers in `awaited_prs` that a person merged)
- The warning total Step 3 carried forward, and that it was written into the PR body (omit if there were none)
- The pages and management files the `unreviewed` step held back (the run record's `skipped` list; `python <this Skill's directory>/scripts/workflow_checks.py list --run <run> --list skipped` prints it), and that they stay uncommitted until an AI review record judges each page — `/wikicommit-generate --regenerate <page>` reviews one. Say this even when the run finished with "No changes to merge" because everything was held back (omit if none)
- The list of `<new source files>` included in the bulk update PR from Step 2 item 3 (omit if none)
- The list of tracking Issues newly created in Step 8 (page path, Issue number)
- Any pages skipped in Step 8, with reasons (frontmatter YAML parse failed during the scan / issue creation error), and whether the open tracking Issues could not be read (then nothing was filed and the next merge picks the pages up)
- The list of generation-failure tracking Issues newly created in Step 9 (source management file path, Issue number)
- Any management files skipped in Step 9, with reasons (frontmatter YAML parse failed during the scan / issue creation error), and whether the open generation-failure Issues could not be read

The scans' `WARNING:` lines (a file whose frontmatter could not be parsed, open Issues that could not be read) came in the workflow engine's `notes`, and a step with nothing to file was skipped without being handed to you. If they are no longer in front of you, print them again:

```bash
python <this Skill's directory>/scripts/workflow_checks.py target-warnings --run <run>
```

A step that was skipped filed nothing because nothing needed an Issue: count it as 0.
