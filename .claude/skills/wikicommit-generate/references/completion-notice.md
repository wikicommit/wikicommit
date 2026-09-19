# Completion notice (`wikicommit-generate`)

> **Contents.** This file is over 20,000 bytes, so it opens with a map rather than making a reader scroll to find out what is in it. The threshold is stated in bytes rather than the 300 lines the Skill guidance names, because a line in this repository's instruction prose runs 40-170 bytes and a line count therefore says very little about how much there is to read (Issue #887 made the same correction to the size metric).

## Contents

- Close the run record **first**
- The notice itself: the counts, then the conditional blocks — `ambiguous` entities, `exclude` decisions with their reasons, `failed_pages`, types added by Pass 2b, deferred sources, types declined, source-language mismatches, extraction warnings, ShareAlike sources, and the checkpoint roll-up

What to report when a run ends, and how. This is over 20,000 bytes of which about 95% are
conditional branches — each one there because some run needed it (Issues #452, #491,
#507, #550) — and none of it is needed until a run is ending. Keeping it in `SKILL.md`
meant loading all of it on every invocation, including the ones that stop at Step 0
(Issue #894).

**What each pass accumulates stays with that pass.** The running lists this file renders
(`ambiguous` entities, `exclude` decisions, `failed_pages`, newly added types, language
mismatches, extraction warnings) are built as the passes run, by instructions in
`references/pass1-extract.md`, `references/pass2b-type.md`, `references/pass2c-entities.md`,
`references/pass3-generate.md` and `references/pass4-review.md` (Issue #911 moved them out
of `SKILL.md`, which now holds the pointers). This file is only the rendering.

## Read this before closing the run record

**The call that closes the run record is in this file, not in `SKILL.md`** — deliberately.
Forgetting to read this file would otherwise cost a report and nothing else, and nothing
would say so; with the closing call here, forgetting it leaves the record open, and
`/wikicommit-status` reports that as `INCOMPLETE_RUN:` (Issue #790). The run's own bookkeeping
is what notices.

Display a summary of the results (pages succeeded / skipped / failed / excluded).

**Close the run record first (Issue #790)**, so the timings and counts it holds are this run's:

```bash
python .wikicommit/scripts/record_run.py end <the path start printed> \
    --source <each source management file processed> --page <each page written> \
    --outcome generated=<N> --outcome failed=<N> --outcome excluded=<N>
```

Then report its path, elapsed time and the passes it stamped in the notice — that duration exists nowhere else, and **the record is not committed**, so this run's own output is the only place a reader sees any of it. That matters most in the unattended cloud runs, where the record dies with the VM: this line is the only form in which the stamps reach a PR body at all (Issue #797).

```
Run record: .wikicommit/run/20260907-104233-generate.md (22m14s)
Passes stamped: pass1-extract x5, pass2b-type x5, pass2c-entities x5, pass3-generate x5, pass4-review x5
```

If any expected pass has no stamp, say so on that line rather than omitting it silently — and say whether it is because the pass genuinely had nothing to do (every source blocked at Pass 1, say) or because you cannot tell.

Then always print one line for the source-integrity review, whatever its outcome (Issue #750):

```
Reviewed 12 page(s) against their sources: 4 finding(s) raised, 2 page(s) corrected
on retry, 1 page(s) not written. Model: claude-opus-5[1m]
  → records in .wikicommit/review/
```

**What makes this worth printing is the denominator.** Everything else in this notice lists only what went wrong, so a reader sees a count of findings with no way to tell whether it is out of 3 pages or 300 — and a run in which every page passed cleanly, a run in which one page failed and was fixed, and a run in which the review never happened at all are today indistinguishable in the output. With the page count present, "0 finding(s) raised" says something: every page went through and came back clean.

Take the numbers from this run: pages recorded, findings across all rounds, pages that took more than one attempt, pages that ended up unwritten, and the model that reviewed. **Do not replace it with a fixed sentence about having written records** — a line whose value never changes stops being read, which is the same reason the low-density guard was demoted from blocking (Issue #562).

If any entities were skipped for `ambiguous: true` (Pass 2), list them explicitly with their candidate `alternatives` and the source management file, and ask the user to confirm the type — e.g.:

```
The following entities were skipped because their type could not be determined. Please confirm the type:
- "Taro Yamada" (candidates: schema:Person, schema:Organization) — source: .wikicommit/source/path/raw/paper-2024.pdf.md
```

Confirming a type does not by itself re-queue the source. That run left its management file at `status: partial` with an empty `failed_pages`, which a bare `/wikicommit-generate` does not collect (Pass 1 step 1) — deliberately, since re-reading the same source would reach the same entity and return the same `ambiguous: true` every run until someone looked. So tell the user what does re-queue it: **`/wikicommit-reconcile --source <the source path or URL shown above>`**, which puts the management file back to `status: pending` for the next run (Issue #874). Naming the source directly (`/wikicommit-generate <the source path or URL shown above>`) also works — the argument branch processes a source whatever its state.

Say it here, but do not rely on this notice being the only place it is said. Since Issue #910 that branch also writes `ambiguous_entities` to the management file, so the wait survives this run's output: `/wikicommit-status` names the source and the entity on every subsequent run until it is resolved.

If any entities were skipped for `action: exclude`, list them too (no user action required — this is informational, unlike the `ambiguous` list above). Group them by `exclude_reason`, so the two reasons stay visibly distinct: one says the entity was off-subject, the other that this wiki has decided not to write about it. Show only the groups that have entries.

**Where an excluded entity's `existing_path` is set, name that page on its line (Issue #876).** Generation never removes a page, so an entity excluded today can have one from an earlier run still standing and published, and nothing else in this run's output points at it. The entity's title is not enough to find it: the filename is a language-neutral English slug whose derivation does not run backwards, so on a wiki whose `primary_lang` is not English the reader would be grepping `title:` across the tree for something Pass 2c already knew.

```
The following entities were excluded as unrelated to theme:
- "Unrelated Corp" (theme_mismatch: A personal acquaintance's employer, unrelated to the configured theme) — source: .wikicommit/source/path/raw/paper-2024.pdf.md
- "Old Partner Ltd" (theme_mismatch: A former supplier, unrelated to the configured theme) — source: .wikicommit/source/path/raw/paper-2024.pdf.md
  A page for this already exists and this run neither created nor updated it: .wikicommit/entity/ja/Organization/old-partner.md

The following entities were excluded by the entity policy (.wikicommit/entity-policy.md):
- "Hanako Suzuki" (privacy: An advisory-committee member named in the source; a private individual) — source: .wikicommit/source/path/raw/paper-2024.pdf.md
  A page for this already exists and this run neither created nor updated it: .wikicommit/entity/ja/Person/suzuki-hanako.md

The policy applies when a page is generated and does not reach back: pages written
before it was set are unaffected, since regeneration does not re-run entity
extraction. Use /wikicommit-remove to take an existing page down — the pages named
in this group are the ones this applies to.
```

**State what is true of the page, not what to do about it.** "A page exists and this run did not create or update it" is the whole of what the exclusion establishes. It is not evidence the page should go: a page can rest on three sources, and one of them judging the entity off-subject today says nothing about the other two. The same posture `check_installed_type_usage.py` takes with `ANCESTOR_FALLBACK:`, which says of itself that it is a suggestion and not a verdict.

**Only the `privacy` group points at `/wikicommit-remove`** — that is the trailing note's job, and it is printed only when that group is non-empty, since it is about that policy and repeating it under an ordinary off-subject exclusion would read as if `theme` had the same reach-back caveat. Under `theme_mismatch`, name the page and stop there: nothing about being off-subject argues for taking a page down. **The trailing note therefore says "the pages named in this group", not "above"** — both groups can name pages, and a note that swept up the off-subject ones would undo the distinction the grouping exists to draw.

**Never call `/wikicommit-remove` yourself.** A policy decides what to create, not what to destroy; removal is irreversible, and which `removed_reason` applies (`obsolete` where the subject drifted out of scope, `gdpr` where a person asked) is a judgment that belongs to a person.

If `.wikicommit/entity-policy.md` was present but could not be read or parsed (see the preamble), repeat that warning here, so an accidentally disabled policy is visible in the run's own summary rather than only in a line that scrolled past:

```
Note: .wikicommit/entity-policy.md could not be parsed, so this run applied no
entity policy at all — every entity was judged on subject relevance alone. Fix the
file's frontmatter and re-run the affected source(s) by name if you rely on it.
```

If Pass 2a flagged one or more sources as clearly written in a language other than `primary_lang` (Issue #336), list them too (informational only, no action required — their content is summarized/translated into `primary_lang` as usual):

```
Note: the following source(s) appear to be written in a language other than primary_lang (ja).
Their content will be summarized/translated into ja when generating pages:
- .wikicommit/source/path/docs/privacy-spec.pdf.md (appears to be English)
```

If the human chose to continue with one or more sources that Pass 1's low-density check flagged (Issue #562), list them too, so that override is recorded in this run's own summary rather than only as a hand-written note in the management file's `## Summary`:

```
Note: the following source(s) were flagged as low-density by the extraction-quality
check (guard A) and generated anyway at your confirmation:
- .wikicommit/source/url/ja.wikipedia.org/saitama-shi.md
  (ratio 0.21, threshold 0.3; non-prose breakdown: links 50%, numbers/tables 1%, other markup 48%)
```

If any YouTube source turned out to have no captions (Issue #574 — the transcript package is installed, so the video itself simply has none), list them too, since the resulting pages rest on the description alone rather than on what the video says:

```
Note: the following video source(s) have no transcript available, so their pages are
based only on the title, keywords, runtime and description:
- .wikicommit/source/url/www.youtube.com/watch-v-96jN2OCOfLs.md
```

If one or more entities were generated as source-entity pages (Issue #475 — Pass 2a judged the source document itself citable as a standalone work), list them too, since they are a page type the user did not explicitly request and may not expect:

```
The following page(s) were generated for a source document itself, not for a concept discussed
within it:
- .wikicommit/entity/en/ScholarlyArticle/vibe-coding-survey.md (source: .wikicommit/source/url/arxiv.org/vibe-coding-survey.md)
```

If any page written in this run has `sources` that are **all** copyleft licensed (share-alike Creative Commons, ODbL, or a copyleft software license — Issue #951 widened the table beyond the first of those), list them. Registration warned once per source; this says which *pages* actually came out that way, which is the thing the obligation would attach to:

```
The following page(s) draw only on copyleft sources, so they may have to be offered under that
license too — check before publishing:
- .wikicommit/entity/ja/Place/hikawa-shrine.md (CC-BY-SA-4.0)

A page with even one non-copyleft source is not listed here. Where a primary source exists,
/wikicommit-collect --index <url> reads an encyclopedia page's citations and offers those instead
of the page itself.
```

Say "may have to" rather than "must", as above. Whether a prose summary of a copyleft document is a derivative work is an open question and WikiCommit does not answer it — what this list reports is which pages are in the position where it has to be asked.

If Pass 4 found a page that contradicts an **existing** page and judged the existing one to be the one at fault (Pass 4 step 3's routing rule, Issue #566), list every such pair. This run deliberately changed nothing about them — it regenerates a page against that page's own sources, and has neither the other page's sources nor any mandate over it — so this Notice is the only place the conflict is recorded at all:

```
The following existing page(s) state a fact differently from a page generated in this run, and this
run's sources support the new page. Nothing was changed on either side:
- 見沼干拓の完了年: .wikicommit/entity/ja/Place/minuma-tsusenbori.md says 1728,
  .wikicommit/entity/ja/Place/minuma.md (existing) says 1727

Check which is right against the existing page's own sources, then fix it with
/wikicommit-fix <page-path> "<instruction>". Only pages one WikiLink hop from a page written in this
run were compared, so this is not a survey of the wiki.
```

If any entity fell back to `.wikicommit/schema/default.md` because its type has no dedicated schema file (Pass 3 step 1, Issue #575), list them too. The pages were still generated, but without that type's `granularity`, `properties:` candidates or body template — the only other signal is `validate_frontmatter.py`'s non-blocking WARNING, which a later `wikicommit-merge` raises only for the files that batch happens to change, so this Notice is the one place every affected page in this run is listed together:

```
The following page(s) were generated from .wikicommit/schema/default.md because their type has no
dedicated schema file — that type's granularity rules, properties: candidates and body template did
not apply:
- schema:Book (looked for .wikicommit/schema/Book.md) — "ドグラ・マグラ"
  (source: .wikicommit/source/url/example.com/article.md)

Run /wikicommit-schema-propose to add the missing file, then regenerate the affected pages with
/wikicommit-generate --regenerate. If you expected the file to exist, check whether it was moved into
a subdirectory: the path is derived straight from `type:`, so .wikicommit/schema/<sub>/Book.md is not
found for schema:Book.
```

If Pass 2b added one or more new `.wikicommit/schema/<Type>.md` files during this run, list them too, since they are new local files the user has not yet seen committed anywhere. Annotate each entry with how it was approved per Pass 2b step 3 in `SKILL.md` — a human answered the prompt, or it was auto-approved with no prompt shown because the run was non-interactive and the candidate cleared the stricter bar (Issue #507):

```
The following Schema.org type(s) were added to .wikicommit/schema/ during this run:
- schema:GovernmentService — approved for "児童手当の申請手続き" (source: .wikicommit/source/path/raw/paper-2024.pdf.md)
- schema:Dataset — auto-approved with no human confirmation (non-interactive run, cleared the stricter
  bar) — for the named benchmark "HotPotQA" (source: .wikicommit/source/url/arxiv.org/hotpotqa-paper.md)

These will be included in the next /wikicommit-merge batch (new schema files are picked up
alongside wiki pages — see that Skill's git add scope). Auto-approved entries get no special marker in
the schema file itself. That batch merges automatically once its mechanical quality checks pass, with no
human approval step in between, so this is not a review gate — it is the same after-the-fact
`git log`/PR-diff audit trail every other WikiCommit change relies on.
```

Do **not** word that last part as "reviewed before merge" — the accurate description is "recorded in git
history for later audit" (Issue #507). The batch auto-merges on mechanical checks alone (Issue #456), so
calling it review would tell the user a human looked at the type when none did.

Quote each added type's `granularity` verbatim in that block (Issue #552). It is the only part of the
file that was written as free prose rather than verified against the vocabulary, nothing downstream
checks its wording, and no Skill can edit it afterwards — so the moment it is printed here is the only
moment anyone sees it before it becomes that Wiki's standing rule for the type:

```
  granularity written for schema:GovernmentService:
    - Create a page for each distinct benefit or service a resident applies for
    - Boundary — a GovernmentService is the service itself, not the ordered steps for applying to it
```

If any of those newly added types wrote a `granularity` bullet drawing a boundary against a type that
already had a file in `.wikicommit/schema/` (recorded in Pass 2b step 4 in `SKILL.md`), say so as well (Issue #550). The
line only exists on the new type's side, and no Skill can add the reciprocal statement to the installed
type's file — a human editing `.wikicommit/schema/` directly is the only way it ever gets there, so this
notice is the only signal that it is missing:

```
The following newly added type(s) state a boundary against a type that was already installed, and the
installed side says nothing about it:
- schema:TechArticle draws a line against schema:HowTo:
  "Boundary — a TechArticle is reference or explanatory material about a subject, not the ordered
   sequence of steps a HowTo covers"
  .wikicommit/schema/HowTo.md carries no matching rule.

Type selection leans toward whichever side of a boundary documented it, so a one-sided rule makes the
undocumented type less likely to be chosen from here on. No Skill can write the other half — edit
.wikicommit/schema/HowTo.md yourself if you want the rule to hold from both directions.
```

Report this even when the run was non-interactive: nobody reads it in the moment, but it lands in the
run's output alongside everything else, and unlike the type file itself the gap leaves no other trace.

**If any source was deferred, list every one (Issue #910).** A deferral is what this Skill does in a
non-interactive run when it reaches a judgment only a person can make: it stops that source, changes
nothing about it, and leaves it in the queue. Two things produce one — guard A's `LOW_DENSITY:` in Pass 1,
and a Pass 2b type candidate that did not clear the stricter auto-approval bar. Both write a
`## Deferred Reason` section to the source's management file, so unlike everything else in this notice
the record outlives the run; report it here anyway, because this is where someone reading the run learns
there is anything to go back for.

```
The following source(s) were deferred — a person needs to look at them, and this run had nobody to ask:
- .wikicommit/source/url/example.com/statistics-2026.md — the extracted text scored 0.11 on the
  natural-language ratio (non-prose breakdown: links 12%, numbers/tables 71%, other markup 17%). That
  shape fits a statistics table as well as it fits an empty JS shell, and the two cannot be told apart
  from the text alone.
- .wikicommit/source/path/raw/gaming-report.pdf.md — schema:VideoGame was considered for "Elden Ring"
  but did not clear the "obviously implied" bar that lets a type be added with no human in the loop.

Nothing about these sources was decided: their status is unchanged and they are still queued — behind
sources this run has not tried yet, so a repeated unattended run does not spend its whole quota on them.
Re-run /wikicommit-generate with someone present and each one asks its question. /wikicommit-status
counts them between runs.
```

**Do not describe a deferral as a failure, and do not tell the reader to re-register the source.** It is
still registered and still queued; the only thing missing is an answer. Saying otherwise invites someone
to "fix" it by deleting and re-adding the management file, which discards the extraction cache and
answers nothing.

If Pass 2b step 3's running list has one or more declined type candidates, list them too (Issue #491,
extended by Issue #507). Since Issue #910 there is only one way a candidate lands here — **a human
answered N**. A candidate that failed the stricter bar in a non-interactive run is no longer declined;
it defers the source, and belongs in the deferral block above instead. By this point in the run, Pass 4 (step 5) has already finished for every source and its own
`failed_pages` list (below) is fully known — cross-check against it so this block is accurate about what
actually happened to each motivating entity: a declined type's motivating entities are not guaranteed to
have become real pages; one may have separately hit `failed_pages` for an unrelated reason (a
source-integrity review failure), in which case say so instead of claiming it "was generated," and drop
it from the "existing installed schema/ type" framing below (it has no page, fallback or otherwise). This
list exists only in this run's own output, never persisted anywhere (Pass 2b step 5). Annotate each
bullet individually with its actual recorded outcome from step 3 — do not use one blanket sentence for
the whole list, since different bullets in the same run can have different outcomes; and do not confuse
this block with the auto-approved block above, which is a different outcome of the same non-interactive
path.
**Do not suggest running `/wikicommit-schema-propose` to reconsider these** — its `check_schema_coverage.py`-based
detection only finds `type:` strings with no dedicated schema file at all, which is not the case for an
entity that did get a page (it already has a working, covered type; Issue #447). This exact wrong
suggestion was made in a real non-interactive run and
produced a "No schema coverage gaps found" dead end when the user tried it — give the guidance
below instead:

```
The following Schema.org type candidate(s) were considered during this run but declined:
- schema:SoftwareApplication — considered for "Claude Code", "Antigravity" (source:
  .wikicommit/source/url/example.com/agents-roundup.md); a human answered N at the prompt. "Kiro" was
  also considered but its page separately failed source-integrity review — see the failed_pages list
  below.

Entities that did get a page above were generated using an existing installed schema/ type instead
(most likely schema:DefinedTerm). This is not tracked anywhere after this run ends, so
/wikicommit-schema-propose will not find it later — its detection only covers types with no dedicated
schema file, and these entities already have one. To reconsider one of these types: add
.wikicommit/schema/<Type>.md by hand, or re-run /wikicommit-init (its obvious-type judgment may catch it
if config.yml's theme alone clearly implies the type) or /wikicommit-collect next time a similar source
comes up (it judges from real candidate evidence before registration).
```

If any entity's page hit `failed_pages` after exhausting `generate.max_retries` (Pass 4 step 5), list them too (Issue #452) — unlike `ambiguous`/`exclude`, this represents an intended `create`/`update` that did **not** take effect, which for `action: update` entities means an existing page was left unchanged with no visible sign anything was attempted:

```
The following pages failed source-integrity review after exhausting retries and were not written
(existing pages, if any, are unchanged):
- "Vibe Engineering" (schema:DefinedTerm, action: update, existing page: .wikicommit/entity/en/DefinedTerm/vibe-engineering.md) — source: .wikicommit/source/url/simonwillison.net/vibe-engineering.md

These are also recorded in each source's source management file (`failed_pages` / `## Failure Reason`).
Run /wikicommit-merge next as usual — it will open a tracking Issue per affected source (label:
wikicommit-generation-failure), so this doesn't require watching this run's console output to notice
later.
```

If Pass 4 step 4's harvest collected any `MISSING_SOURCE` document, list them (Issue #722). These are documents the wiki cited but does not hold — each one is a registration candidate the run already identified, and without this the finding vanishes as soon as the retry drops the offending claim. **Fold duplicates to one line per document**, however many pages or retries raised it, and name the pages under it. Where every page that raised a document ended up discarded (Pass 4 step 5), say so on that line rather than listing the document twice — the failed-pages roll-up above reports the *page*, this one reports the *document*, and a reader should not have to reconcile the two:

```
The following documents were cited by generated pages but are not registered as sources. In each case
the citing page either dropped the claim to get through review or was discarded, so registering one
and re-running will bring back what it supports:
- https://simonwillison.net/2025/Mar/19/vibe-coding/ — cited by .wikicommit/entity/en/Person/simon-willison.md
- "2024 年度 さいたま市統計書" (title only; no URL in the source text) — cited by
  .wikicommit/entity/ja/AdministrativeArea/urawa-ward.md (this page was discarded after retries)

Register one with /wikicommit-generate <url-or-path>; the next run folds it in as an update to the
same page.
```

If `reset_review_on_content_change.py` (Pass 4 step 6) printed any `RESET:` line, list those pages (Issue #724). These were `reviewed` before this run and are not any more, which is a state change a reader of the published wiki will see — the banner's line saying a person read the page disappears, and the reviewer's name with it:

```
The following pages were previously reviewed and had their content rewritten by this run, so they are
back to review_status: pending (the reviewer's name has been removed with it):
- .wikicommit/entity/ja/Place/minuma.md — source: .wikicommit/source/url/example.com/minuma.md

Run /wikicommit-merge next as usual — it opens a fresh review-tracking Issue for each of these.
```

If `reconcile_ingest_status.py` (run from `SKILL.md` before this file) reported `reconciled` > 0, list the corrected files too (Issue #474):

```
The following source management files were left at status: pending even though their content is
already in use by a published page — their status has been corrected to "generated":
- .wikicommit/source/url/github.blog/copilot-agent-mode.md → .wikicommit/entity/en/Organization/github.md
```

Then show the next steps:

```
Next steps:
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
```
