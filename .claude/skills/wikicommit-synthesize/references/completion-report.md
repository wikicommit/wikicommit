---
pass_token: "3887442a"
---

# Step 11: Guidance (`report`)

Report this step to the workflow engine **first** — finishing the last step is what closes the run record, so its elapsed time covers the whole run.

Read what happened from the run record, not from memory: the `write` entry in its `workflow.log` carries the outcome (`written` or `discarded`), and `workflow.lists.page` the view page's path. Pass `--page` only when the page was written:

```bash
python .wikicommit/scripts/skill_workflow.py done <run> --step report --outcome reported \
    --token 3887442a [--page <the view page written>] \
    --count synthesized=<1 if written, else 0> --count failed=<1 if discarded, else 0>
```

Then tell the user the run record's path and its elapsed time, and the `ground` step's grounding line (`<N'> of <M>` pages) — and, when the cap cut pages, their paths and the `--max-grounding` re-run that would include them — the record is not committed, so this run's own output is the only place a reader sees them.

**When the page was written**:

```
Written to .wikicommit/view/<lang>/<slug>.md, and rebuilt .wikicommit/view/<lang>/index.md so the page appears in the view index.
This page is grounded in other wiki pages rather than in an outside document, which is what the separate location records. It is subject to the quality gate and can be committed via /wikicommit-merge like any other page (review_status: pending, so it will get a tracking issue after merge).
```

**When it was discarded**, say that nothing was written, what still failed — the last round's `issues`, in the user's own terms — and which grounding pages were involved. Read them from the `result: discarded` record under `.wikicommit/review/view/<lang>/<slug>/` (the newest `synthesize-step5.5` record); it holds every round's `issues`. There is nowhere else this survives.

Add one line for the grounding review, whatever its outcome — the denominator is 1 here, but the reason for printing it is the same as in `/wikicommit-generate`: without it, a run in which the review found nothing and a run in which it did not happen read identically:

```
Reviewed 1 page against its grounding pages: 0 finding(s) raised.
  → record in .wikicommit/review/
```

If the review in step 5.5 reported grounding pages that disagree with each other (`page_at_fault: "other"`), list those pairs here — both page paths, the fact, and each page's version of it (step 5.5 item 3 says where in the entry each half lives: one page in `source_file`/`source_quote`, the counterpart in `claim`). Nothing else surfaces them: they are not a defect in the page just written, so they neither failed the review nor appear anywhere in the file. Say plainly that the page just written is not the thing to fix and that the disagreement is between the two pages named.

If the `ground` step warned that some grounding pages are unreviewed, repeat that here as well. Between the warning and this point the person has read a whole document, and this is where they decide what to do with it.
