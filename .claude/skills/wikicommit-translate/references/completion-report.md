---
pass_token: "2bb66e58"
---

# After Completion (`report`)

Report this step to the workflow engine **first** — finishing the last step is what closes the run record, so its elapsed time covers the whole run.

Count the pairs from the run record, not from memory: each `translate` entry in its `workflow.log` carries the pair as `item` and its `outcome` (`translated` or `discarded`). `failed` counts the discarded pairs. Pass `--page` once for each translation written (the target page of every `translated` pair):

```bash
python .wikicommit/scripts/skill_workflow.py done <run> --step report --outcome reported \
    --token <the pass_token above> \
    --page <each translation page written> --count translated=<N> --count failed=<N>
```

Then report the run record's path and elapsed time — the record is not committed, so this run's own output is the only place a reader sees them.

**List every discarded pair** — the source page, the target language, and what still failed in plain words. Nothing was written for them, so this report is the only place a reader learns why: a new pair stays untranslated, and a stale pair keeps its old translation, until a later run succeeds. Read what failed from the pair's `result: discarded` record under `.wikicommit/review/` (the newest `translate-check` record in the translation page's record directory); it holds every round's `issues`.

**If only the first 5 pairs were done because nobody could answer** — the run record's `workflow.log` has a `batch-cap` entry answered `first-five` by the `non-interactive default` — say so: the remaining pairs were left for a later run on purpose, and nothing on disk changed for them, so the next run's `check_translation_status.py` reports them again.

```
Next steps:
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
  (translated pages are written with review_status: pending, same as wikicommit-generate output)
```
