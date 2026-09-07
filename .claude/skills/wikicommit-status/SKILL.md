---
name: wikicommit-status
description: Show wiki health — orphan pages, wanted pages, unreviewed pages, expired pages, stale translations, outdated sources, types with no schema file, recurring plain-text characters, unlinked entity mentions, unused installed types, self-referential tags
---

# wikicommit-status

A health-check skill for the wiki as a whole. Calls the six page-count scripts (`check_orphans.py` / `check_wanted_pages.py` / `check_expires.py` / `check_ingest_freshness.py` / `check_translation_status.py` / `check_derivation_freshness.py`) plus `check_actions_pr_permission.py` (a single repository-setting check, not a page count — Issue #478), `check_property_wikilink_reinforcement.py` (a `.wikicommit/schema/` template check, not a page count either — Issue #539), `check_schema_coverage.py` (types in use with no dedicated schema file — Issue #575), `check_recurring_characters.py` (characters left as plain text in `properties.character` — Issue #560) and `check_unlinked_entity_mentions.py` (a `properties:` value naming a page that exists, written as plain text — Issue #561) and `check_installed_type_usage.py` (installed type files with no pages, and pages sitting on an ancestor of an installed type — Issue #565) and `check_self_referential_tags.py` (tags that only repeat a page's own title or type — Issue #571), aggregates their results, and displays them alongside the number of unprocessed `.wikicommit/source/` files and the number of unreviewed `.wikicommit/entity/` pages. This skill has no dedicated scripts of its own (only the existing scripts plus directory scanning).

## Usage

```
/wikicommit-status
```

No arguments. Always targets the whole repository.

## Processing Flow

### Step 1: Check for Unpulled Remote Changes

This skill only scans the local working tree. If PRs (e.g. post-review PRs from `/wikicommit-merge`) were merged on GitHub but not yet pulled locally, the results below will be stale — pages already `reviewed` on GitHub can still be counted as `review_status: pending` here.

Run `git fetch` (read-only; does not modify the working tree) and compare local `HEAD` against `origin/<current branch>` (e.g. via `git rev-list --count HEAD..origin/<branch>`). If the local branch is behind, warn the user before displaying results:

```
Note: your local branch is N commit(s) behind origin/<branch>. Results below may be stale
if PRs were merged on GitHub since your last pull. Run `git pull` first for an accurate picture.
```

Do not run `git pull` automatically — it could conflict with uncommitted local changes, and this skill is read-only by design (see Notes).

### Step 2: Disclose the Side Effect

`check_ingest_freshness.py` has the side effect of rewriting local `.wikicommit/source/` management files (it changes any management file with `status: generated / partial / outdated` whose hash mismatches to `outdated`. Management files with `status: pending / excluded / failed` are not checked even on a hash mismatch, and are not detected by this step). Disclose this to the user before running it:

```
Note: running check_ingest_freshness.py will rewrite the status of any .wikicommit/source/
management file whose source changed to outdated (local change only; will show up in git status).
Run /wikicommit-merge afterward to commit it.
```

### Step 3: Run the Six Scripts

Run the following in order, and for each, take the counts from its `SUMMARY:` line and the corresponding file paths from its `ORPHAN:` / `DUPLICATE:` / `WANTED:` / `TYPE_MISMATCH:` / `page:` lines.

```bash
python .wikicommit/scripts/check_orphans.py
python .wikicommit/scripts/check_wanted_pages.py
python .wikicommit/scripts/check_expires.py
python .wikicommit/scripts/check_ingest_freshness.py
python .wikicommit/scripts/check_translation_status.py
python .wikicommit/scripts/check_derivation_freshness.py
```

- `check_orphans.py` → `SUMMARY: orphans=N, duplicates=N`. Get file paths from the `ORPHAN: <path> (sources: ...)` / `DUPLICATE: <path> <-> <path> (title: "...")` lines (these two are the only categories without a `page:` line, so parse them directly). Keep the `sources:` part when listing orphans (Issue #570) — the useful next question about an unreachable page is which source produced it, and a run of orphans sharing one source usually means that source covers something the rest of the wiki does not link to yet.
- `check_wanted_pages.py` → `SUMMARY: wanted=N, type_mismatch=N`. The counterpart to `check_orphans.py`: pages with WikiLinks pointing at them but no backing file in any language (Issue #340 — `check_wikilinks.py`'s missing-target case is a WARNING, not a blocking ERROR, so this report is how these surface for follow-up). Get the `Type/slug` keys from the `page:` lines; the referrer counts and paths are in the corresponding `WANTED:` or `TYPE_MISMATCH:` line directly above each `page:` line. **Report the two counts as separate categories and never merge them** — they call for opposite actions (Issue #563). A `WANTED:` key is a page to write. A `TYPE_MISMATCH:` key is a link whose slug already has a page under a different Type, named in that line: writing the "missing" page would duplicate the existing one, so the fix is to correct the Type segment in each referring page instead. Every `TYPE_MISMATCH:` key also blocks `wikicommit-merge` as a `check_wikilinks.py` ERROR once one of its referring pages is next changed, so treat it as work due now rather than a backlog item.
- `check_expires.py` → `SUMMARY: expired=N`. Get file paths from the `page:` lines.
- `check_ingest_freshness.py` → `SUMMARY: outdated=N, ok=N`. Get file paths from the `page:` lines.
- `check_translation_status.py` → `SUMMARY: stale=N, missing_source=N, untranslated=N`. Get file paths from the `page:` lines (each `STALE:` / `MISSING_SOURCE:` / `UNTRANSLATED:` line is immediately followed by its corresponding `page:` line). `untranslated` is 0 whenever `.wikicommit/config.yml`'s `translation.targets` is empty (no target languages configured).
- `check_derivation_freshness.py` → `SUMMARY: stale=N, missing_source=N`. This is the `wikicommit-synthesize` counterpart of `check_translation_status.py`'s `STALE`/`MISSING_SOURCE` (same output shape, but walks `derived_from` entries instead of `translated_from`). Get file paths from the `page:` lines; a page with multiple stale/missing `derived_from` entries emits a `page:` line once per entry, so the same path may appear more than once here — dedupe when listing paths, but not when counting (the `SUMMARY:` counts entries, not pages). Keep this separate from `check_translation_status.py`'s own stale/missing counts (the line directly above) — different frontmatter field, different root cause: a translation going stale vs. a synthesized page's source going stale.

### Step 4: Check GitHub Actions PR Permission

```bash
python .wikicommit/scripts/check_actions_pr_permission.py
```

Unlike the six scripts in Step 3, this is a single repository-setting check, not a per-page count — it verifies "Allow GitHub Actions to create and approve pull requests" is enabled, which `review-issue-close-sync.yml`'s `Commit and open PR` step depends on (Issue #313). `wikicommit-init` attempts to enable this automatically at repository initialization time, but that attempt can silently fail with no trace in normal operation until a reviewer closes a tracking Issue days later and the workflow run fails deep in GitHub Actions logs (Issue #403). This is the only script this skill calls that invokes `gh`; it never writes to the repository setting itself (read-only, matching every other check).

Take the `OK:`/`WARNING:` line and `SUMMARY: enabled=<true|false|unknown|n/a>` — `n/a` means `review-issue-close-sync.yml` doesn't exist in this repository (not applicable) and `unknown` means the check itself couldn't run (unauthenticated `gh`, unresolvable repository, or a failed `gh api` call) — both are distinct from a confirmed `false`.

### Step 5: Check Property-Value WikiLink Reinforcement

```bash
python .wikicommit/scripts/check_property_wikilink_reinforcement.py
```

Also unlike the six scripts in Step 3, this checks `.wikicommit/schema/` type templates, not `.wikicommit/entity/` pages — for each `properties:` key whose Schema.org range includes a linkable entity type, whether the template gives any textual hint (a `granularity` bullet that names the property *and* points toward linking it — the rest of that bullet contains `[[` or the word `link` — or a `[[Type/slug]]` placeholder already in `properties:`) toward writing that property's value as a WikiLink (Issue #539, automating the manual cross-check Issue #523 did by hand). Purely a human-readability nudge, not a functional requirement — `wikicommit-generate` Pass 3 already applies the WikiLink decision uniformly to every such property regardless of whether the template reinforces it, so an `UNREINFORCED:` finding here is not itself evidence anything is broken. `description` is expected to appear for nearly every type (its Schema.org range is Mixed via `TextObject`, but this wiki's convention keeps it as prose) — treat that specific recurring finding as expected noise, not a defect to chase down. `HowTo`'s `tool` and `supply` are the same: that template names them only to say they are often empty and should be left out, which does not count as pointing at a WikiLink (Issue #650), so they are reported and are meant to stay that way.

Get the `SUMMARY: unreinforced=N` count and the individual `UNREINFORCED: <Type>.<property> (<path>) — ...` lines. Also surface any `WARNING: <path>: wikicommit.granularity...` line and keep it next to the findings for that same file: it means a `granularity` bullet parsed as something other than a string (usually a `": "` inside an unquoted list item, which YAML reads as a one-key mapping), so the reinforcement search never saw that bullet's prose. An `UNREINFORCED:` line for a file that carries such a warning may well be a parse artifact rather than genuinely missing reinforcement — the fix is to rewrite the bullet in the schema file (em dash instead of the colon, or wrap the bullet in double quotes), not to add reinforcement that is already there.

### Step 6: Check Schema Coverage

```bash
python .wikicommit/scripts/check_schema_coverage.py
```

Like Step 5, this is about `.wikicommit/schema/` rather than page health as such: it reports each `type:` value in use by pages that has **no dedicated schema file**, so those pages were generated (and are validated) against `default.md` alone — that type's `granularity` rules, `properties:` candidate keys and body template never applied (Issue #575).

Falling back to `default.md` is correct, intended behavior, so this never blocks a merge — the script always exits 0, and `validate_frontmatter.py` keeps this a WARNING rather than an ERROR for the same reason. It does count against the "Wiki is healthy" verdict in Step 17, which is a different thing: a repository whose schema files match the types it uses reaches 0 here, and a repository that does not has a concrete fix available. A repository initialized before Pass 2b (Issue #315) may well start non-zero; that is the finding doing its job, not a reason to exclude it. The reason it belongs in a periodic health check is that nothing else surfaces it once the pages exist: `wikicommit-generate` reports it only in the Completion Notice of the run that generated the page, and `validate_frontmatter.py`'s WARNING reaches only the files a given `wikicommit-merge` batch happens to change — so if a schema file is moved, renamed or deleted after the fact, every page that already existed goes on failing silently and is never re-checked. The trigger that breaks it (editing `.wikicommit/schema/`) and the trigger that would notice (changing a page) are unrelated events.

Get the `SUMMARY: unschemaed_types=N` count and the individual `UNCOVERED: <type> (<N> pages, e.g. <path>)` lines.

When the count is 1 or more, note that `/wikicommit-schema-propose` opens a PR adding the missing file — and warn about one trap before running it: it always writes `.wikicommit/schema/<Type>.md`, derived from `type:`. If the file is missing because someone filed it under a subdirectory (`.wikicommit/schema/<sub>/<Type>.md`), that path is not what the lookup reads, so the proposal produces a **second** definition of the same type with only the new one in effect. In that case move the existing file back to `.wikicommit/schema/<Type>.md` instead of running the Skill.

### Step 7: Check Recurring Plain-Text Characters

```bash
python .wikicommit/scripts/check_recurring_characters.py
```

Back to `.wikicommit/entity/` pages, but reading `properties:` values rather than WikiLinks: `ShortStory.md` / `Book.md` tell Pass 3 to WikiLink a character who qualifies for a `[[Person/slug]]` page and to list the rest as plain text, and nothing ever revisits that call afterwards (Issue #560). A plain-text name is invisible to every other check here — `check_wanted_pages.py` reads only `[[Type/slug]]` WikiLinks, so an unpromoted character is not even counted as wanted (the Issue #318 limitation, applied to `properties:` values), and `check_orphans.py` is about backlinks to pages that already exist.

Take the `SUMMARY: recurring=N` count and the individual `RECURRING:` lines (no `page:` lines — each finding line names the works itself). A `RECURRING:` line is the same name in two or more works with no `Person` page anywhere: recurrence across works is the evidence a single work cannot give, so this is a page worth writing (or a decision, once, that the character stays plain text). Works are counted by `<Type>/<slug>`, so the language versions of one story count once.

A name that *does* already have a page is Step 8's finding, not this one — the two call for opposite work (write a page vs. link to the one that exists), which is why they are separate scripts and separate counts.

This is not blocking, and does not gate the health verdict in Step 17 — the promotion bar is a judgment call belonging to `Person.md`'s `granularity` at generation time, and a wiki can legitimately decide a recurring character stays plain text. Note also what this cannot see: a protagonist appearing in exactly one work never recurs, so a wiki whose characters are all one-work leads reports 0 here while still having the gap this check exists for.

### Step 8: Check Unlinked Entity Mentions

```bash
python .wikicommit/scripts/check_unlinked_entity_mentions.py
```

The mirror image of `check_wanted_pages.py` (Step 3): that one finds a link with no page behind it, this one finds a page with no link in front of it (Issue #561). It reads every `properties:` value whose key has a linkable entity type in its Schema.org range — the same `--show-range` classification Step 5 uses — and reports the plain-text values that name a page which actually exists.

Pass 3 is told in so many words not to let a missing target page stop it from writing a WikiLink, but `wikicommit/decameron-wiki` split one `Book`'s ten-name `character` list eight-to-two along exactly that line: the pages an earlier ingest had already written became WikiLinks, the ones a later ingest created stayed bare strings. Nothing self-corrects — `action: update` reaches a page only when a source for *that page* is re-ingested — and nothing else reports it either: `check_wikilinks.py` reads only the WikiLinks that were written, and `check_orphans.py` misses the case whenever the target page has backlinks from elsewhere.

Take the `SUMMARY: unlinked=N` count and the `UNLINKED:` lines with their `page:` lines. Each names the referring page, the property, the value, and the page it resolves to. The fix is `/wikicommit-fix <page-path> "<instruction>"` on the referring page — deliberately not an automatic rewrite, since a value matching a page title is evidence, not proof (two subjects can share a name), and `properties:` is not something a health check should write to.

Not blocking, and does not gate the health verdict in Step 17 for the same reason: the value's shape is a generation-time judgment `validate_frontmatter.py` deliberately does not enforce (Issue #495 checks that a `properties:` *key* belongs to the type, never the *value*'s shape).

### Step 9: Check Installed Type Usage

```bash
python .wikicommit/scripts/check_installed_type_usage.py
```

The counterpart to Step 6: that one finds a `type:` in use with no schema file behind it, this one finds a schema file with no pages in front of it (Issue #565). `wikicommit/saitama-city-wiki` had `Park.md` and `Museum.md` installed and human-approved and generated seven parks and two museums as plain `Place`, in the same batch that added the type files — and Step 6 reported zero the whole time, because `Place` does have a schema file.

Take the `SUMMARY: unused=N, ancestor_fallback=N` counts and the individual lines. The two differ in strength on purpose:

- `UNUSED:` — a type file with zero pages. Either the type was a misjudgment, or generation is not reaching for it. `provenance: default` types are exempt, since they ship with every wiki whether or not its subject calls for them.
- `ANCESTOR_FALLBACK:` — pages on a type whose descendant is also installed. **Suggestive, never conclusive**: a wiki with `Park.md` still has legitimate `Place` pages that are not parks. Read it as "worth a look".

Neither is blocking and neither gates the health verdict in Step 17 — which type fits a subject is a judgment call this script cannot make, only point at. When something here does look wrong, note that re-typing an existing page is not something any Skill does today: it means a directory move plus rewriting the Type segment of every WikiLink that points at it. What this check is really for is catching the pattern early, so the next batch generates at the right grain.

### Step 10: Check Self-Referential Tags

```bash
python .wikicommit/scripts/check_self_referential_tags.py
```

`tags` groups pages across the wiki by something they share. A tag equal to the page's own `title` groups the page with itself, and one equal to its `type` repeats what `type:` already says — both were ruled out in prose when `tags` was defined (Issue #275), and both came back in a later pilot (Issue #571). A generation-time rule with nothing checking it drifts.

Take `SUMMARY: title_echo=N, type_echo=N` and the `TITLE_ECHO:` / `TYPE_ECHO:` lines with their `page:` lines. The fix is to drop the tag — `/wikicommit-fix <page-path> "<instruction>"`, or by hand.

Matching is exact after normalization and never partial: `見沼` on a page titled `見沼田んぼ` is the useful kind of tag and is not reported. One thing it cannot see is a type tag written in the wiki's own language (`博物館` on a `schema:Museum` page), which would need a translation of the Schema.org vocabulary — type names are language-neutral identifiers here and no such table exists. Non-English wikis get the title half only.

Not blocking, and does not gate the health verdict in Step 17: a tag is a judgment call, and a wiki may have a reason for one this check flags.

### Step 11: Check Distribution Freshness

```bash
python .wikicommit/scripts/check_distribution_freshness.py
```

Like Step 4, this looks at the state of the installation rather than at pages. It compares what is on disk against the templates the installed `wikicommit-init` Skill ships, and reports three things: `OUTDATED:` (present but no longer matching), `MISSING:` (the template has it, this repository does not) and `ORPHAN:` (this repository has a file the template no longer does — `/wikicommit-init` refreshes trees but never deletes from them, so a script renamed upstream leaves its old name behind). Read-only; unlike `check_ingest_freshness.py` in Step 3 it writes nothing.

What each path is compared against, and whether it is compared at all, is declared once in the Skill's own `_root_outputs.py` alongside the variant and `git add` decisions for the same path. Paths WikiCommit owns outright are compared byte for byte, because a re-init refreshes them and any difference is a version gap. Paths the user may have edited are reported only when the **template has gained something this repository lacks** — a new configuration key, a new frontmatter key, a new ignore pattern. Changing a value or rewriting the prose is the user doing their job and is never reported. Do not read a quiet result as "this file is identical to the template"; read it as "nothing has been added upstream that is missing here".

Take the `VERSION:` line and the `SUMMARY: outdated=<N>, missing=<N>, orphan=<N>` counts. `synced=unknown` on the `VERSION:` line means the repository predates the version stamp (Issue #577) — it is reported for the reader and never gates a comparison, so the findings are as reliable as on any other repository. A `WARNING:` line instead of findings means the `wikicommit-init` Skill is not installed here, so there was no template to compare against; that is not a defect in the wiki, and the fix is to install the Skills.

Everything this reports is fixed by re-running `/wikicommit-init` (with `--no-overwrite`, though the update policies protect the user's files either way), **except orphans** — those are deleted by hand, after checking that nothing still calls the file.

### Step 12: Check Pages Resting on a Retracted Source

```bash
python .wikicommit/scripts/check_retracted_sources.py
```

`status: retracted` on a source management file records that a human read a registered source, judged its content unreliable, and took it out of use (Issue #737). Setting it stops the source being ingested again, but it does nothing to the pages already written from it — those keep it in their `sources[]`, unchanged and unremarked. This step is what surfaces them.

Take `SUMMARY: retracted_sources=N, affected_pages=N` and the `RETRACTED_SOURCE:` lines with their `page:` lines. Each line names the page, the retracted identity its `sources[]` still carries, the management file that retracted it, and **how many other sources that page still rests on** — which is the number that decides what to do: a page with at least one remaining source can be rebuilt from what is left with `/wikicommit-generate --regenerate <page>`, which drops the retracted source and its `sources[]` entry (Issue #744) and is the route that actually takes it out of the page's evidence base — with one exception the count itself cannot show you: Regeneration Mode excludes any page carrying a `sources[].type: manual` entry, which this count treats as a remaining source, so a page whose only remainder is a manual one is a `/wikicommit-fix` too; a page whose problem is narrower than a rebuild is a `/wikicommit-fix`; and a page down to zero has nothing left holding it up, so it is a `/wikicommit-remove`.

**Reporting is the whole intervention here, deliberately** (Issue #737). Resetting these pages to `review_status: pending` was considered and rejected: Issue #724 delegates "did the content actually change?" to a deterministic script specifically so that a non-deterministic judgment never decides whether a human must re-read a page, and a retraction changes no content at all — it changes the standing of the evidence behind it. Beyond that, `pending` would say "read this again" without saying what is now unsupported.

Only a human can set this status, and only a human can lift it. That is not a gap: under the evidence-binding rule (Issue #442) the machine judges a page *against* its sources, so it cannot judge the sources themselves. The three fetch guards (Issues #425 / #574 / #715) catch sources whose *retrieval* is broken; a source that fetched perfectly and is simply wrong is outside what any of them can see.

Not blocking, and does not gate the health verdict in Step 17: whether a retracted source's pages need rewriting, removing or leaving alone is a judgment call, and `retracted_sources=0` (nothing has ever been retracted here) is reported the same way as no affected pages.

### Step 13: Check Review Coverage

```bash
python .wikicommit/scripts/check_review_coverage.py
```

Reads the review records under `.wikicommit/review/` (Issue #750) and reports what has been reviewed, by what, and which verdicts no longer hold:

- `SUMMARY:` — pages, how many carry a **standing** machine review, how many carry a standing human one, total findings, distinct models. "Standing" throughout this step means the newest record that judged the page as it now stands (Issue #766): a `result: discarded` review judged a draft that was thrown away, so it says nothing about the text on disk and is not counted as coverage of it
- `COVERAGE:` — per model: pages, findings, how many needed more than one attempt — all three from the standing record — and last, how many pages whose **newest AI record** is a discarded one this model wrote. That last number is the one thing here that reads a discarded record, and it is what makes a quiet `RISKY:` legible rather than contradictory: a page can be listed as discarded here and correctly appear in no verdict line at all. It is keyed on the page's newest AI record rather than on each model's own newest, because it exists to explain a missing `RISKY:` line — once a later review has judged the current text there is nothing missing to explain, so a superseded discard is not counted
- `UNREVIEWED:` — a page with no standing record. Almost always that means no record at all; it also covers a page whose records exist but none of which judged the page as it now stands, and the line says which case it is — every record discarded, or none carrying a `page_content_hash` (Issue #766). All of them want the same response — someone has to look at this page — which is why they are one list
- `RISKY:` — a page whose **standing** review took more than one attempt or drew findings. **This is the sampling list**: it is the closest thing the wiki has to "which pages are most worth a human reading", and it exists only because the verdicts are now kept. "Standing" is the newest record that judged the page as it now stands, of either kind (Issue #760) — so a page drops off once a later review comes back clean, and a human's own findings put a page on the list. It reads that one record rather than the history, because records are immutable and never deleted: summing over all of them meant a page that was ever retried stayed listed forever, and the list converged on the whole wiki, at which point it selects nothing. The "took two rounds to pass" signal is not lost by this — that review is the standing one and carries its own `attempts`
- `STALE_REVIEW:` — a recorded verdict that no longer applies, either because the page's text changed after it or because a source under it did
- `RETRACTED_EVIDENCE:` — a verdict that rested on a source since retracted (Issue #737). Distinct from Step 12: that step reports pages that still *name* a retracted source, while this one reports that a judgment was actually made on the strength of it

Report the counts, and list `UNREVIEWED:` / `RISKY:` / `STALE_REVIEW:` / `RETRACTED_EVIDENCE:` findings if there are any.

Not blocking, and does not gate the health verdict in Step 17. There is deliberately no threshold here — no coverage percentage to hit and no automatic action. A human reads `RISKY:` and decides whether to read the page or re-run `/wikicommit-generate --regenerate`; a number invented before there is data to set it from would only look like a standard.

A wiki initialized before this existed has no `.wikicommit/review/` and reports zeros with a note saying so — the absence of records means "generated before reviews were recorded", not "never reviewed".

### Step 14: Check Run Records

```bash
python .wikicommit/scripts/check_run_records.py
```

Reads the run records under `.wikicommit/run/` (Issue #790). Every other layer in this repository is keyed on an artifact — a file, a source, a page, a review — and this is the only one keyed on **a run**, which is what these two lines need:

- `LAST_RUN:` — when the last run of any Skill was, how long it took, and what it produced. Both the timestamp and the duration exist nowhere else: `generated_at` is a date, a commit timestamp is the merge rather than the generation, and no layer has ever held an elapsed time at all
- `INCOMPLETE_RUN:` — a record with a start and no end, i.e. a run that did not finish. Without it the state such a run leaves behind (some management files `pending`, some `generated`) is indistinguishable from a backlog that has simply not come up yet, which Step 15 counts; and on the two paths that halt before any file changes there is nothing in Git at all to notice. `halted_reason` is on the line when the run recorded one

Only one `LAST_RUN:` is printed, and every incomplete record is listed. **A forgotten closing stamp shows up here too**, and that is the accepted direction of the error rather than a defect — a completed run reported as incomplete costs a glance, while the reverse would quietly retire the question the record exists to answer.

Not blocking, and does not gate the health verdict in Step 17: this describes how the wiki was operated, not whether its content is sound.

These records are not tracked by Git, so **they are local to this machine and this checkout** — a clone sees none, and a cloud session's records go when its VM does. A repository that reports zeros here has not necessarily been idle.

### Step 15: Tally Unprocessed Source Management Files

Scan `.wikicommit/source/**/*.md` and read each file's frontmatter `status` field. Count the files with `status: pending` and record their paths.

From that same scan, also count how many of those `pending` files have **never been processed at all** — no `last_generated_at` (absent or empty) (Issue #567). Record their paths, and note how many of those have an empty `source.hash` as well, meaning nothing has even been retrieved for them yet (only `type: url`/`wikicommit` files can be in that state — `add_source.py` hashes a `type: path` file at registration).

Keep this restricted to the `pending` files counted above rather than every file with no `last_generated_at`: `wikicommit-generate` Pass 4 writes that field only on its `generated` and `partial` branches, so a `failed` or `excluded` source has none either — but it *has* been processed, it just produced nothing, and `wikicommit-merge` Step 9 already raises a tracking Issue for the failing kind. Counting those here would inflate the number and report an already-tracked failure as work that has not come up yet.

This is a subset of the `pending` count, not a separate population, and it is the part that matters: a source registered weeks ago and never once processed looks exactly like one registered this morning. In `wikicommit/saitama-city-wiki`, 23 of 70 registered sources were in this state — including good, subject-specific articles for places whose pages had meanwhile been written from a thin tourism-portal listing. Nothing was failing; the queue simply never reached them, because eight `partial` sources that could never make further progress were taking the slots (Issue #567 changed which sources `/wikicommit-generate` collects and in what order).

Unlike `failed_pages`, which `wikicommit-merge` raises as a tracking Issue (Issue #452), this is not a failure — it is work that has not come up yet, so counting it here is the whole intervention.

### Step 16: Tally Unreviewed Pages

Scan `.wikicommit/entity/**/*.md` **and `.wikicommit/view/**/*.md`** (excluding `index.md` in both) and read each file's frontmatter `review_status` field. Exclude pages with `status: removed` (as with `check_orphans.py` / `check_expires.py`, removed pages are not review targets). Count files with `review_status: pending`, or where the `review_status` field itself is absent (treated as `pending`, same as `validate_frontmatter.py`'s WARNING behavior), and record their paths.

The view tree is included (Issue #675) because a view page is written `review_status: pending` like any other generated page, and `wikicommit-merge` Step 9 scans both trees and opens a tracking Issue for it. Counting only the entity tree would report a wiki as fully reviewed while open `wikicommit-review` Issues are outstanding — the exact backlog this tally exists to surface. This differs from `check_orphans.py`'s exclusion of the same tree, which rests on a property of view pages themselves (unlinked at birth) rather than on which fields they carry.

### Step 17: Display Results

Display in the following format:

```
WikiCommit Status
==================
Unreviewed pages:       <N> (review_status: pending)
Orphan pages:           <N> (zero inbound links)
Duplicate pages:        <N>
Wanted pages:           <N> (linked but no page exists in any language)
Type-mismatched links:  <N> (slug exists under a different Type — fix the link, do not create the page)
Expired pages:          <N> (past expires_at)
Stale translations:     <N> (source_commit mismatch)
Missing translation source: <N> (translated_from target doesn't exist)
Untranslated pages:     <N> (no translation yet for a configured target language)
Stale synthesized pages: <N> (derived_from source_commit mismatch)
Missing synthesis source: <N> (derived_from path doesn't exist)
Unprocessed sources:    <N> (status: pending)
Never-processed sources: <N> (registered but never generated; <M> not even fetched)
Updated sources:        <N> (status: outdated, source hash mismatch)
GitHub Actions PR permission: <status>
Unreinforced property-value WikiLinks: <N> (informational — check_property_wikilink_reinforcement.py)
Types with no schema file: <N> (pages generated against default.md alone — check_schema_coverage.py)
Recurring plain-text characters: <N> (in 2+ works, no Person page — check_recurring_characters.py)
Unlinked entity mentions: <N> (properties: value naming a page that exists — check_unlinked_entity_mentions.py)
Unused installed types:  <N> (schema file with zero pages — check_installed_type_usage.py)
Possible ancestor-type fallback: <N> (pages on a type whose installed descendant may fit better — check_installed_type_usage.py)
Self-referential tags:  <N> title echoes / <N> type echoes (check_self_referential_tags.py)
Distribution freshness: <N> outdated / <N> missing / <N> orphan (check_distribution_freshness.py)
Pages on a retracted source: <N> (sources[] names a source a human withdrew — check_retracted_sources.py)
Review coverage:        <A>/<T> pages with a standing AI review, <H> with a standing human one (check_review_coverage.py)
Pages with no standing review: <N> (no record judges the page as it stands — check_review_coverage.py)
Risky pages:            <N> (retried, or findings raised — the sampling list — check_review_coverage.py)
Stale reviews:          <N> (page text or a source changed after the verdict — check_review_coverage.py)
Reviews on retracted evidence: <N> (check_review_coverage.py)
Last run:               <when> <skill> (<elapsed>, <outcome>) — check_run_records.py
Runs that did not finish: <N> (started, never closed — check_run_records.py)
```

For any category with 1 or more hits, display the list of matching file paths directly below that category — with three exceptions, which have no per-page paths to list: for `Unreinforced property-value WikiLinks` display the `UNREINFORCED:` lines, for `Types with no schema file` display the `UNCOVERED:` lines (`check_schema_coverage.py` emits no `page:` lines at all — each `UNCOVERED:` line carries a page count and one example path for that type), and for `Recurring plain-text characters` display the matching `RECURRING:` lines (each already names the works the name was found in). `Unlinked entity mentions` does have `page:` lines, so it follows the normal rule — list the referring page paths, each with its `UNLINKED:` line. The two Step 9 categories have no `page:` lines either — display the matching `UNUSED:` / `ANCESTOR_FALLBACK:` lines.

For `Distribution freshness`, display the `VERSION:` line and then the matching `OUTDATED:` / `MISSING:` / `ORPHAN:` lines — this check has no `page:` lines either, and each of its lines already names the path and says what is wrong with it.

`Pages on a retracted source` does have `page:` lines, so it follows the normal rule — list the affected page paths, each with its `RETRACTED_SOURCE:` line, since that line carries the two things needed to decide what to do: which retracted source the page still names, and how many sources it has left.

The five review-coverage rows all come from Step 13's single run. `Review coverage` is not a count of problems — take `<A>`, `<T>` and `<H>` from its `SUMMARY:` line (`ai_reviewed`, `pages`, `human_reviewed`) and display the `COVERAGE:` lines underneath it, one per model, since the per-model split is the whole reason the denominator is worth printing. The other four rows are counts of the `UNREVIEWED:` / `RISKY:` / `STALE_REVIEW:` / `RETRACTED_EVIDENCE:` lines; for any of them with 1 or more hits, display those lines directly below the row (each already names its page and, where it applies, what changed). When Step 13 printed the `NOTE: .wikicommit/review/ does not exist yet` line instead, display that note in place of all five rows — the wiki predates review recording, and reporting `0/0` there would read as "nothing to review" rather than "nothing recorded yet".

The two run rows come from Step 14's single run. `Last run` is not a count either — display its `LAST_RUN:` line's content, or `none recorded` when Step 14 printed a `NOTE:` instead. For `Runs that did not finish`, display the `INCOMPLETE_RUN:` lines below the row when there are any. Say alongside them that these records are local to this checkout and are not committed, so zeros here mean "nothing recorded on this machine" rather than "nothing has been run".

`GitHub Actions PR permission` is not a count — display Step 4's `OK:`/`WARNING:` line verbatim as `<status>` (e.g. `OK: acme/example-wiki: "Allow GitHub Actions to create and approve pull requests" is enabled`, or the full `WARNING: ...` message including the enable command). Skip this line entirely when `SUMMARY: enabled=n/a` (repository doesn't use `review-issue-close-sync.yml`).

If every category above is 0 **and** `enabled` is `true` or `n/a`, display "Wiki is healthy" instead of the above (a `false`/`unknown` permission state blocks the "healthy" verdict even when every page-level category is clean, since it silently breaks the review-close automation). `Unreinforced property-value WikiLinks` does not gate this verdict either way — it is purely informational (Step 5) and, per that step's `description` caveat, is realistically almost never 0 on any repository using the standard type templates, so requiring it to be 0 would make the "healthy" verdict effectively unreachable. Neither `Recurring plain-text characters` nor `Unlinked entity mentions` gates it: promoting a character is a judgment call `Person.md`'s `granularity` makes at generation time and a wiki may legitimately decide a recurring character stays plain text (Issue #560), and an unlinked mention is likewise a generation-time judgment `validate_frontmatter.py` deliberately does not enforce on `properties:` values (Issue #561) — a standing non-zero count in either is a backlog to look at rather than a defect. The two Step 9 categories do not gate it either (Issue #565): both are judgment prompts rather than defects, and `ANCESTOR_FALLBACK` in particular is expected to be non-zero on any wiki that installs a descendant type at all. `Self-referential tags` does not gate it either (Issue #571) — same reason. `Pages on a retracted source` does not gate it either (Issue #737): the check reports so a human can choose between removing, regenerating and fixing the page, and none of those is automatically the right answer. `Distribution freshness` does not gate it either (Issue #712): it describes how current the installation is, not whether the wiki's content is sound, and a repository can be entirely healthy while running a version behind. Neither run row gates it either (Issue #790): they describe how the wiki was operated rather than whether its content is sound, and since the records are not committed, a fresh clone or a new machine would otherwise be barred from the verdict by an absence that means "not recorded here". None of the five review-coverage rows gates it either (Issue #750): they measure how much reviewing has been recorded rather than whether the content is sound, there is deliberately no coverage threshold to reach (Step 13), and a wiki that predates the record tree — or one whose pages were all generated before it — would otherwise be permanently barred from the verdict by an absence that means "not recorded", not "not reviewed". `Types with no schema file` **does** gate it (Issue #575): unlike the reinforcement check, a non-zero count here means a type definition is not being applied at all, it is 0 on a repository whose schema files match the types it uses, and the fix is a concrete one (add the file, or move it back out of a subdirectory).

### Step 18: Cleanup Guidance

If the `outdated` count in Step 3's `check_ingest_freshness.py` `SUMMARY:` line is 1 or more (whether newly rewritten this run or already `outdated` before), append the following guidance:

```
Some .wikicommit/source/ management files have status: outdated (either just rewritten by this run,
or already in that state — either way, this is a local change only and will show up in git status).
Run /wikicommit-merge to commit it.
```

## Notes

- Do not commit or create a PR against `main` or any branch
- Do not write to `.wikicommit/schema/`
- No script other than `check_ingest_freshness.py`, and no part of the Step 3 / Step 15–16 scans, has side effects (read-only). `check_actions_pr_permission.py` (Step 4), `check_property_wikilink_reinforcement.py` (Step 5), `check_schema_coverage.py` (Step 6), `check_recurring_characters.py` (Step 7) and `check_unlinked_entity_mentions.py` (Step 8) and `check_installed_type_usage.py` (Step 9) and `check_self_referential_tags.py` (Step 10) and `check_distribution_freshness.py` (Step 11) and `check_retracted_sources.py` (Step 12) and `check_review_coverage.py` (Step 13) and `check_run_records.py` (Step 14) are read-only too — unlike `wikicommit-init`'s Step 3, `check_actions_pr_permission.py` never attempts to enable the GitHub Actions PR permission setting itself, only reports its current state
