---
pass_token: "a78a97ea"
---

# Steps 5–9: synthesize, review, record and write (`write`)

Write the page from the grounding pages the `ground` step read — they are in the run record's `workflow.lists.grounding`; if their bodies are no longer in front of you (a resumed run), read them again first. The `kind`, if one was chosen at the survey, is the last entry of `workflow.lists.kind`. Read `generate.max_retries` (default: 2) from `.wikicommit/config.yml`.

Report one outcome when this step is done, passing the view page's path (`.wikicommit/view/<lang>/<slug>.md`, Steps 6–7) as `--add page=` in every case but `halted`:

- `written` — the page passed review, was written (Step 9) and the pass recorded (Step 5.5 item 6). The workflow engine's check then confirms, on disk, that the page is at `.wikicommit/view/<primary_lang>/<slug>.md` with `lang`, `title`, `generated_at`, `generated_by` and `review_status: pending`, no `type:` and no `sources:`, a `kind` (if any) from the six below, a body not opening with an H1, and `derived_from` naming **exactly** the grounding pages, each with the `source_commit` Step 9 says — and that the page was written in this run and a `synthesize-step5.5` record with `result: pass` was written for it afterwards (record the pass after the last change to the page, not before).
- `discarded` — still failing after `generate.max_retries` (Step 5.5 item 5). Nothing was written; the check confirms a `synthesize-step5.5` record with `result: discarded` from this run and that the page was not written in this run.
- `declined` — the page already exists and overwriting it was declined (Step 8), or nobody could answer. Nothing was written; the workflow engine closes the run as finished.
- `halted` with `--reason "rules_version mismatch"` — the review could not be run as specified (Step 5.5 item 2). The run stops.

```bash
python .wikicommit/scripts/skill_workflow.py done <run> --step write \
    --outcome <written|discarded|declined|halted> --token a78a97ea \
    [--add "page=<the view page path>"] [--reason "<why>"]
```

## Step 5: Generate the Summary

Generate a summary document about `<topic>`, grounded only in the grounding pages' body content. **Do not include claims in the document that aren't in a grounding page's body content** (hallucination prevention). Step 5.5 then checks that with a review subagent, the way `wikicommit-generate` Pass 4 checks a generated page against its source documents.

Structure the document with sections (`##` and deeper), and include reference links to related pages (in `[[Type/slug]]` form) within the body. Do not append a "Referenced Pages" list to the body — the grounding set is instead recorded in the `derived_from` frontmatter field (Step 9), so listing it again in the body would be redundant.

### Choose a `kind`

A view page's `kind` says what it does with several pages at once — a different
question from what it is about, which is why it is not a Schema.org type.
Pick the one that matches, or **none**: `kind` is optional, and
forcing a page into a kind whose Boundary it then breaks is worse than leaving
it off. Pages piling up without a kind is the signal that a kind is missing, so
leaving it off is a real answer, not a failure.

| kind | What the page does | Boundary — what it must not do |
|---|---|---|
| `practice` | Sets several accounts of one practice against each other: when it applies, what it assumes, how it fails, what kind of evidence stands behind it | **Never write normative advice.** Report what the grounding pages record about a practice; do not tell the reader to adopt it. An invented insight costs more than an absent one |
| `landscape` | Maps an area and points at its hubs and main pages, as a way in | Make no new claim, and **write no counts**. The overview page recomputes totals, reviewed ratios, per-type tallies and gaps on every build; a number written into prose here is wrong by tomorrow with nothing to catch it. Link there instead |
| `comparison` | Puts a few entities of the same kind side by side and draws out where they differ | Do not rank them or declare one better. Differences, not verdicts |
| `pattern` | Describes a shape that recurs across many pages | **Always give the count and name the pages.** A pattern with no cases behind it is an assertion |
| `timeline` | Orders events drawn from several pages along time | Leave each event's detail on its own `Event` page; this page carries the ordering |
| `debate` | Lays out how one question is answered differently, and what backs each answer | Reach no conclusion. Where the grounding pages disagree, that disagreement is the content |

Write the body to fit the chosen kind, and keep inside its Boundary — Step 5.5
checks the Boundary as well as the grounding.

**Do not open the body with an H1 (`# <topic>`), or any other top-level title line**. The page's title lives in the `title` frontmatter field (Step 9) and Quartz renders that as the page heading, so a body H1 duplicates it on the published page. Every schema template's body starts with a paragraph or a `##` heading, which is why `/wikicommit-generate` and `/wikicommit-translate` never produce one — this Skill is the only one that builds a body without going through a template, so it is the only place the convention has to be stated outright.

## Step 5.5: Grounding Integrity Review (Review Subagent)

This path needs a check most: a synthesized page carries `derived_from` and no `sources`, so a reader's only route to the underlying evidence runs through the grounding pages, and if the synthesis misreads them nothing downstream catches it.

**The review discipline is not in this file.** It lives in `.wikicommit/review-rules.md`, shared with `wikicommit-generate` Pass 4 and `wikicommit-review`. What stays here is the choreography, and the fact that `MISSING_SOURCE` means something different on this path is stated there, under this path's own section. The workflow engine's `preflight` step already confirmed the rules file exists, at the start of the run.

1. Launch a subagent and give it exactly these four things, and nothing else:

   1. **The path label `synthesize-step5.5`**, stated as the path this review is running on. The rules file scopes several checks by path ("a check that does not name your path is not yours to run") and has a section per path — including the one that says `MISSING_SOURCE` means something different here — so a subagent left to guess which one it is on may run the cited-document check that does not apply here, or miss the Boundary check that only applies here.
   2. **The generated body from step 5.**
   3. **The full body of each grounding page**, each wrapped in a block marked `SOURCE`.
   4. **`.wikicommit/review-rules.md`**, with an instruction to follow it, plus the page's chosen `kind` and the one Boundary line for it from Step 5's table.

   **Do not include anything else** — not your reasoning for how the synthesis was assembled, not the search results that selected the grounding set, and not a previous round's findings. You are the agent that wrote this page, and handing over your own reading of the grounding makes the review agree with you exactly where that reading was wrong.

   Pass each grounding page's **full body**, not the passages you drew on. Showing the reviewer only the text you wrote from biases it toward PASS by construction.

2. **Check that the returned JSON carries `rules_version` matching `.wikicommit/review-rules.md`'s frontmatter.** A missing or mismatched value means the subagent did not read the rules, so its verdict says nothing about the checks they define. Relaunch **once**; if the second attempt is also missing or wrong, **stop and report it** — report `halted` with `--reason "rules_version mismatch"` (this stops without writing the page) — do not consume `generate.max_retries` and do not record it as a review of this page. This is a problem with the instructions or the environment, not with the synthesis.

3. **Grounding pages that disagree with each other are reported, not failed.** The rules file has the subagent set `page_at_fault: "other"` on those entries and keep `result` at `"PASS"` when they are the only kind of defect found; carry the pairs to the completion report. Failing instead would be a trap with no exit — this Skill cannot edit a grounding page, so every retry would produce a correct synthesis, draw the identical unfixable finding, and end at item 5 with the page discarded.

4. On **FAIL**, regenerate the body by re-running step 5 — up to `generate.max_retries` times from `.wikicommit/config.yml` (default: 2). The same key `/wikicommit-generate` uses; there is no separate setting for this Skill, because it would mean the same thing.

   **Pass the findings into the retry.** Feed the full `issues` array — above all each entry's `instruction` — into the regeneration prompt as explicit, itemized corrections for this attempt, alongside the same grounding bodies step 5 had. Do not retry from a bare "the previous attempt failed review": two consecutive FAILs for the same underlying defect is precisely what that produces, since the retry never saw what was wrong with the attempt before it. Leave out the `page_at_fault: "other"` entries — regenerating cannot fix them, and feeding them in as corrections would push the synthesis away from what the grounding pages actually say.

5. **If the retry limit is exceeded, write nothing**, record the verdict (item 6) and report `discarded`; the completion report says what still failed (the last `issues` array, in the user's own terms) and which grounding pages were involved. There is no partial success to record: this Skill writes one page per run, and unlike `/wikicommit-generate` it has no source management file in which to leave a `failed_pages` entry — a synthesized page has no management file at all, and `/wikicommit-merge`'s generation-failure tracking scans `.wikicommit/source/`, which this run never touches.

   Steps 6–7 still run (the record needs the page path), Steps 8–9 do not. Nothing has been written to disk at this point, so there is nothing to clean up.

6. **Record the verdict either way.** Run this after the page is written (step 9) when the review passed, and immediately after item 5 when it did not — the failing case is the one worth recording most, since nothing else survives a run that wrote no page:

   ```bash
   python .wikicommit/scripts/record_review.py "$(cat <<'EOF'
   <the view page path, .wikicommit/view/<lang>/<slug>.md>
   EOF
   )" --kind ai --stage synthesize-step5.5 \
     --model "<the model ID this run's runtime reports for itself>" \
     --skill-blob "$(git hash-object .wikicommit/review-rules.md)" \
     --attempts <how many review rounds this took> --result <pass|discarded> --json - <<'JSON'
   <the review subagent's JSON, with every round's issues merged into one `issues`
    array and each entry carrying the `round` it was raised in>
   JSON
   ```

   `--result discarded` is the retry-limit case from item 5: the page was never written, and the script records an empty `page_content_hash` to say so. On a pass, `reviewed_sources` is read from the page's own `derived_from` — the grounding pages and the commits they were read at — which is the same slot an entity page's `sources` occupies, and for the same purpose: the evidence versions this verdict was made against.

   **If the subagent returned an `observations` array, write it to a file under the gitignored `.wikicommit/.cache/` with a quoted heredoc and pass `--note-file`.** Those are the remarks it made while deciding PASS, which are not defects and so never reach `issues`; without this they live only in this session's console, and a page reviewed with a remark records exactly what a page reviewed in silence records. Do not pass them with `--note` — the text is free-text a subagent wrote, and this project keeps such text off the command line. Pass neither flag when the array is absent or empty. Keep the file out of `.wikicommit/review/`: `/wikicommit-merge` stages that directory whole, so a scratch file left there is committed as if it were a review record.

   Merge every round's findings into the one array rather than keeping only the last. A synthesis that breached its `kind`'s Boundary on the first attempt and was corrected on the second would otherwise record nothing at all, and that is precisely the drift this Skill's own review exists to catch.

   The `page_at_fault: "other"` entries go in as well. They never made this a FAIL, but they are the only durable trace that two grounding pages disagree — item 3 reports them to the user once and the run then ends.

## Step 6: Determine the New Page's Language

Set `lang` to `.wikicommit/config.yml`'s `primary_lang` — whatever language `<topic>` was given in. This mirrors `wikicommit-generate`'s rule that a newly created page's own language is always the wiki's source language, and it is the language every grounding page is written in.

There is no type-selection step: a view page has no `type:`, so its location is decided entirely by its language and its slug, and two runs on one topic land in the same place.

## Step 7: Generate the topic-slug

Generate a language-neutral English slug from `<topic>` (same convention as WikiLink filenames: a lowercase, hyphen-separated English identifier). For a non-English `<topic>` (e.g. Japanese), have the LLM translate it to English first, then slugify it. Example: "機械学習パイプライン" → `machine-learning-pipeline`.

## Step 8: Safety Check Before Writing

The target path is `.wikicommit/view/<lang>/<slug>.md` (from Steps 6–7). If the file already exists, confirm with the user whether it is okay to overwrite; if declined, report `declined`. **When nobody can answer** (a non-interactive run), do not overwrite: report `declined`. A previous synthesis stays as it is, and re-running interactively can still replace it.

The check is this short because the view tree holds nothing but this Skill's output — an existing file there is a previous synthesis, and there is no way to land on primary content by accident.

If the file doesn't exist, proceed directly — create the parent `.wikicommit/view/<lang>/` directory automatically if needed.

## Step 9: Write the File

Write frontmatter with:

- `title`: `<topic>` (or its English-translated form used for the slug, whichever reads better as a title in `lang`)
- `lang`: from Step 6
- `kind`: from Step 5, **omitted entirely when no kind fits** (do not write an empty value — `validate_frontmatter.py` accepts only one of the six kinds or no field at all)
- `review_status: pending` (unconditionally — same rule as `wikicommit-generate`/`wikicommit-translate` output)
- `generated_at`: today's date (`YYYY-MM-DD`)
- `generated_by`: the LLM model identifier
- `generated_with`: WikiCommit's own version, not a model ID — read it with `python .wikicommit/scripts/_version.py` and write that exact string (the same stamp `wikicommit-generate` Pass 3 writes). It is what lets a human — reading `CHANGELOG.md` alongside a `grep` for this field — tell which pages were produced under an older set of rules. If that script is missing (a wiki repository initialized before this field existed), omit the field entirely rather than guessing a version — its absence is meaningful, and no back-fill is performed.
- `derived_from`: one entry per grounding page (every path in `workflow.lists.grounding`, no more and no fewer), in the form:

  ```yaml
  derived_from:
    - path: .wikicommit/entity/ja/Person/yamada-taro.md
      source_commit: abc123def456abc123def456abc123def456abc123de
    - path: .wikicommit/entity/ja/Organization/companya.md
      source_commit: def456abc123def456abc123def456abc123def456ab
  ```

  Get each `source_commit` with `git log -1 --format=%H -- <path>`. If a grounding page has no commit history yet (newly generated, not yet committed), this command succeeds with empty output — write `source_commit` as an empty string in that case (`check_derivation_freshness.py` will correctly report it as `STALE` until the page is committed, which is expected, same as the equivalent `wikicommit-translate` behavior).

Do **not** write a `type:` or a `sources:` field. `validate_frontmatter.py` reports either one on a page in this tree as an ERROR: the first because a view page has no Schema.org type, the second because `derived_from` is this page's provenance record — the same way `translated_from` is for a translation page.

Write the frontmatter + body (from Step 5) to `.wikicommit/view/<lang>/<slug>.md` as a new file. Then record the pass (Step 5.5 item 6) and report `written`.

**Relative links in the body** (images, attachments) are written **as they will appear on the published site**: `../../assets/<name>`, exactly what an entity page writes, because `content/<lang>/View/` sits at the same depth as `content/<lang>/<Type>/`. `convert_wikilinks.py` deliberately leaves a view page's relative targets alone for this reason. WikiLinks (`[[Type/slug]]`, and `[[View/<slug>]]` for another view page) are unaffected — they carry no path.
