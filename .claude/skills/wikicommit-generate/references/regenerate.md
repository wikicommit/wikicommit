# Regeneration Mode (`/wikicommit-generate --regenerate`)

> **Paths in this file.** `references/…`, `scripts/…` and `../<other-skill>/…` are relative to the Skill's directory (the parent of this `references/` directory), not to the repository root — the Skills may be installed under `.claude/skills/` or `.agents/skills/`. Commands still run from the repository root, so spell the path out from there. Paths starting with `.wikicommit/` are repository-root paths as before.

## Contents

- Target selection (`<page-path>` / `--type <Type>` / `--all`, and the 5-page cap)
- Merging same pages (`<page-path> --merge <page-path> ...`)
- Eligibility — which pages this mode refuses, and why
- Per-page procedure:
  1. Re-acquire every source (and drop the `status: retracted` ones)
  2. Run Pass 3 as an `action: update` on the page itself
  3. Run Pass 4 unchanged, minus the management-file writes
  4. The unchanged-output valve
  5. Do not write back to the source management file

The procedure for `--regenerate`, kept out of `SKILL.md` because the two modes are
mutually exclusive: an ordinary `/wikicommit-generate` run never uses a byte of this,
and this mode never uses Step 0, Pass 2a/2b/2c or the Completion Notice. `SKILL.md` is
read in full on every invocation, so keeping both there would make each mode carry the
other's instructions.

**The Skill is not split.** Passes 1, 3 and 4 are shared with ordinary generation; this
file holds only what is specific to rebuilding a page that already exists. Read it
together with `SKILL.md`, not instead of it.

Each shared pass has its own file, and this mode reads the same three an ordinary run
does:

| Read | Step here | `--pass` |
|---|---|---|
| `references/pass1-extract.md` | step 1 (re-acquire) | `pass1-extract` |
| `references/pass3-generate.md` | step 2 (generate) | `pass3-generate` |
| `references/pass4-review.md` | step 3 (review) | `pass4-review` |

`references/pass2b-type.md` and `references/pass2c-entities.md` are not read in this mode,
and `references/completion-notice.md` is not either — this mode reports for itself (see the
end of this file). **The driver hands you this file at three points** (the run is started with
`workflow-regenerate.yaml`): as the `choose-pages` step — target selection and eligibility
below — then alongside each of the three pass files above, per page, and finally as the
`report` step. Report each pass to the driver with the `--token` its own file declares,
exactly as an ordinary run does; `record_run.py` narrows the expected set to these three
when the record's `args` carry `--regenerate`, so a pass that never reaches `done` is
reported as `MISSING_PASS:` just as it would be anywhere else.

**Outcomes here differ from an ordinary run.** For `choose-pages`: `chosen`, with
`--add candidates=<page>` for every eligible page, or `none`. For `pass1-extract`:
`acquired`, `skipped` (the page cannot be rebuilt — step 1 below says when; the driver moves
on to the next page), or `halted` with `--reason`. For `pass4-review`: `rebuilt`,
`unchanged`, `failed`, or `halted`. For `report`: `reported`, with `--page` for each page
rebuilt and `--count regenerated=<N> --count unchanged=<N> --count failed=<N>`.

Rebuilds pages that already exist, so that pages generated under older schema templates or older Pass 3 rules can be brought up to the current ones. Ordinary generation is source-driven and only ever touches management files at `status: pending`/`outdated`/`partial`; a source already at `status: generated` is skipped, so "the source has not changed, but the generation rules have" has no way to be expressed. This mode is that expression.

It is **page-driven, not source-driven**. A wiki page carries its full provenance in `sources:` (every `path`/`url` plus `hash`), so a single page can be rebuilt from exactly its own sources — including a page merged from several — without dragging in the unrelated pages that those same sources also produced. That granularity is the whole reason for going page-first: one source commonly generates entities of several types, and a source-driven rebuild would sweep all of them in.

Because the target page's frontmatter already fixes `type`, `title`, `lang` and slug, there is nothing left for Pass 2 to decide:

<!-- skill-vocabulary-exception: pass-structure diagram explaining this mode to the agent; never printed to the user -->
```
Normal generation:  Pass 1 (extract) → Pass 2 (analyze/extract entities) → Pass 3 (generate) → Pass 4 (review)
Regeneration:       Pass 1 (re-acquire) →                                   Pass 3 (generate) → Pass 4 (review)
```

Pass 2b (dynamic type addition) does not run either: regeneration takes the existing page's type as given. Deciding a page's type was wrong is a different operation (type re-classification) and is out of scope here, as is splitting pages after a `granularity` change — that changes *which pages should exist*, which a page-driven rebuild cannot express. The one change to which pages exist that this mode does make is a merge a person has already decided on (`--merge`, below): the pages to keep and to absorb are named, so nothing is left for Pass 2 to decide there either.

**Selecting what to rebuild is the human's job.** There is deliberately no freshness script that computes "which pages are stale" per type: read `CHANGELOG.md` for what actually changed in each version, and `grep` `generated_with` to list pages built by an older one. Version granularity is coarser than per-type changes — bumping the version after editing only `Person.md` makes every page look equally old — so the two are only useful together.

#### Target selection

```
/wikicommit-generate --regenerate <page-path>     # one page
/wikicommit-generate --regenerate --type <Type>   # every eligible page of that type, all languages
/wikicommit-generate --regenerate --all           # every eligible page
```

With `--regenerate` the positional argument names a **page**, not a source — the opposite of every other invocation of this Skill. Do not try to infer which one the user meant from the path's shape: require the argument to resolve under `.wikicommit/entity/`, and if it does not, stop and say that `--regenerate` takes a page path while a bare `/wikicommit-generate` takes a source. Silently guessing is how a mistyped source path turns into a no-op that looks like success.

`--type <Type>` matches the page's `type:` frontmatter (`schema:`-stripped, e.g. `Person`, `custom/Decision`), not the directory name, and spans every language directory. Exactly one of a page path, `--type`, or `--all` must be given.

#### Merging same pages (`--merge`)

```
/wikicommit-generate --regenerate <kept page> --merge <absorbed page> [--merge <absorbed page> ...]
```

Rebuilds `<kept page>` from its own sources **and the absorbed pages' sources**, carries the absorbed pages' names over as aliases, and — once the rebuilt page has passed Pass 4 and been written — takes the absorbed pages down and rewrites the links to them (`references/merge.md`, the `merge-absorb` step). `--merge` goes only with a single page path, never with `--type` or `--all`. All the pages are named by their path in `primary_lang`; their translations follow.

**The merge must rest on a person's decision.** Before anything else, run

```bash
python .wikicommit/scripts/merge_pages.py plan --into <kept page> --absorb <absorbed page> [--absorb ...]
```

and stop with its `ERROR:` line when it refuses — above all when no `same` item in `.wikicommit/relations.yml` names the kept page together with each absorbed one: point the person at `/wikicommit-relate`. It also refuses a page outside `primary_lang`, a translation, a synthesized page, a page with a `type: manual` source, and a source the pages record with two different hashes. **Which page is kept is the person's choice** — the one whose slug and title should stay; ask when they named the pages without saying.

Keep the plan's output for the rest of the run:

- `SOURCE:` lines are the merged page's sources — step 1 re-acquires every one of them.
- `ALIAS:` lines are the **merged aliases**: the absorbed pages' titles and aliases and their translations' titles, minus the kept page's own title. Step 2 adds them and Pass 4 leaves them out of the added aliases it checks.

Report `choose-pages` with the kept page as the only candidate. The eligibility rules below apply to it as to any rebuild.

#### Eligibility

Walk the selected pages and drop the ones that cannot be rebuilt, then **report every dropped page and why** — silence here reads as success:

- `index.md`, and any page with `status: removed` — never regenerated.
- A page with `translated_from` (translation) or `derived_from` (synthesized). These have their own producers; `/wikicommit-translate` and `/wikicommit-synthesize` own them. Regenerating an original page makes `check_translation_status.py` report the translation `STALE` and `check_derivation_freshness.py` report the synthesized page `STALE`, which is how the user learns to re-run those Skills. No new following mechanism is added here.
- A page with no `sources`, or with **any** `sources[].type: manual` entry. A manual source cannot be re-acquired, so a rebuild would quietly drop whatever the page drew from it. Skipping the whole page rather than rebuilding from its remaining sources is the conservative choice: losing content is worse than not refreshing it.
- A page **every** one of whose sources is `status: retracted`. Retracted sources are dropped rather than re-acquired (step 1), so there is nothing left to rebuild this page from. Report it and point at `/wikicommit-remove`: a page with no evidence behind it at all is a removal decision, not a regeneration one. Note this is the one exclusion here that is *not* conservative in the same direction as the two above — for a page with at least one surviving source, dropping the retracted entry and rebuilding is exactly what this mode is for, which is why partial retraction is handled in step 1 instead of here.

Then report `choose-pages` with the eligible pages, **in path order, ascending**. The count guard the rest of this Skill uses is the driver's `batch-cap` step: when more than 5 pages remain it asks whether to **(a)** process all of them or **(b)** process only the first 5, leaving the rest for a later run (no one to ask means (b)). Regeneration costs one full generate-plus-review cycle per page, so `--all` must never run unguarded.

#### Per-page procedure

The driver hands you the page as `item` and the three passes in turn — `pass1-extract` for step 1, `pass3-generate` for step 2, `pass4-review` for steps 3 and 4. `record_run.py` reads `--regenerate` off the record's own `args` and narrows what it expects to those three, so 2b and 2c are not reported as skipped here.

1. **Re-acquire every source** listed in the page's `sources:` — in a merge, every `SOURCE:` line of the plan, the absorbed pages' sources included — (a source whose management file is `status: retracted` is the one exception — it is dropped rather than fetched; see below), using Pass 1's extraction rules for that `source.type` unchanged (including its guards) — but **only the acquisition half of Pass 1**: none of Pass 1's writes to the source management file happen here (no `--write-hash`, no `extracted_tokens`, no `status: failed`/`## Failure Reason`), per step 5 below. `--write-hash` in particular would overwrite the management file's `source.hash` with freshly-fetched content while its `status` stays `generated`, so a later `/wikicommit-generate <url>` would re-fetch, see `HASH_MATCH:` and report "No changes" — the source change this mode just refused to fold in would be lost for good. If a guard blocks a source (known-JS-shell domain, missing fetch capability, low density), skip the page and report it rather than marking the source failed; the source's own management file is not this operation's to change. Two deltas:
   - **Prefer the cache, keyed on the page's own hash.** For a `type: url`/`wikicommit` source, first locate that source's source management file by scanning `.wikicommit/source/url/` for the one whose `source.url` equals this `sources[].url` — do **not** re-derive the filename from the URL, which does not match management files registered under the older flat or percent-encoded naming; `../wikicommit-ask/scripts/resolve_source_cache_path.py` already performs exactly this scan and prints the resulting cache path. `<scratch-path>` is that management file's path relative to `.wikicommit/source/url/` without the `.md` extension, as defined in Pass 1. If `.wikicommit/.cache/ingest-fetch/<scratch-path>.md` exists and its SHA-256 equals the page's own recorded `sources[].hash`, use it and do not fetch. The point of this mode is to apply new generation rules, not to pick up source changes; a network round trip per source would be pure cost. Compare against the **page's** hash directly (e.g. `sha256sum`), not with `add_source.py --check-hash`: that command compares the scratch file against the *management file's* current `source.hash`, which can have moved on since this page was generated (the source was re-registered and re-fetched afterwards), so a `HASH_MATCH:` there would hand the rebuild newer content than the page records — and the next bullet's guard, which only fires after a real fetch, would never run. When there is no matching management file, no scratch file (a clean checkout, a different machine), or the scratch file's hash differs from the page's, fetch normally and let the next bullet decide.
   - **For a `type: path` source, prefer its extraction cache too.** Run `add_source.py --check-path-cache <that source's management file>` — located by the same real-directory scan the retraction bullet below describes, not by deriving a filename. On `CACHE_VALID:`, read the printed file instead of re-extracting: the raw file's hash still matches what the management file recorded, and this mode exists to apply new generation rules, not to pick up source changes. This is where the cache is worth the most — re-running an OCR pass or an EPUB extraction on an unchanged file is pure cost, and it needs an optional Skill installed to work at all. On `CACHE_STALE:` / `ERROR:`, extract normally and let the next bullet decide. Note this does **not** replace that bullet's hash comparison: `--check-path-cache` compares the file on disk against the *management file's* `source.hash`, which can have moved on since this page was generated, so the page's own recorded hash still has to be checked separately — the same distinction the `type: url` bullet above draws about `--check-hash`.
   - **A changed or unavailable source disqualifies the page.** After a real fetch — or, for `type: path`, after hashing the file on disk — compare against the page's recorded `sources[].hash` (in a merge, the hash the plan printed — whichever page recorded the source). On a mismatch, do **not** rebuild: report the page, name the source, and point the user at `/wikicommit-generate <path|url>`, which is the existing `outdated` path for exactly this. Folding a source change into a rules refresh would put two unrelated changes into one page under one review, and would leave the source's own management file describing a state that no longer holds. Treat a source that cannot be re-acquired at all the same way — a `type: path` file no longer on disk, or a fetch that errors out: skip the whole page and report it, rather than rebuilding from the sources that did resolve. Rebuilding on a subset would silently drop whatever the page drew from the missing source, which is the same loss the `manual`-source exclusion above exists to prevent.
   - **`NETWORK_UNAVAILABLE:` from `--fetch-url` is an unavailable source like any other** — skip the page and report it; nothing is written for it either way. As in Pass 1, two in a row mean the environment has no network rather than two pages with broken sources: stop the run there: report `halted` to the driver with `--reason "network unavailable"`.

   **A retracted source is dropped, not fetched, and not carried forward.** Before acquiring any source, read the `status` of that source's management file. For a `type: url`/`wikicommit` source that is the file located above; for a `type: path` source, scan `.wikicommit/source/path/` for the one whose `source.path` equals this `sources[].path` — the same real-directory identity match `add_source.py`'s `find_mgmt_file_for_path()` performs. Do **not** derive the filename from the path, for the same reason the url scan above does not derive it from the URL: a derived name misses management files registered under the older extension-stripped naming. A source with no management file at all has no retraction to read — treat it as not retracted and let the two bullets above decide it. The eligibility rule above (every source retracted) reads these same statuses, so do this lookup once per page and use it for both. If it is `retracted`, do not fetch it: a human read that source, judged its content unreliable and withdrew it, and re-acquiring it here would re-ingest the exact thing `add_source.py`'s `RETRACTED:` result and `check_ingest_freshness.py`'s status allowlist exist to keep out. Rebuild the page from the sources that remain, and **drop the retracted entry from the rebuilt page's `sources:`** (the one exception to step 2's "copied through untouched"). **"From the sources that remain" governs the body too**, and it has to be said here because step 2 runs Pass 3 as an `action: update` whose standing rule is to *merge* into the existing page: whatever the current page asserts on the strength of the retracted source alone is not carried across. Keeping it would be the worst outcome available — the claim survives with nothing in `sources[]` naming where it came from, so `check_retracted_sources.py` never reports the page again and the retraction is lost rather than applied. Report every page this happened to, naming the dropped source and its `## Retraction Reason`.

   This is the opposite treatment from the changed/unavailable/`manual` cases above, and deliberately so. Those skip because the source's content is still wanted and cannot be had — rebuilding without it would silently lose what the page drew from it. A retraction says the opposite: that content is **not** wanted, and removing what rested on it is the point. Rebuilding here is the only route that actually takes a retracted source out of a page's evidence base.

   Keeping the entry while rebuilding without the content would be the worst of both: `sources[]` is a claim about what backs the page's **current** text, so the page would assert support it was not written from, Pass 4 would go on checking it against a document the rebuild ignored, and `check_retracted_sources.py` would report the same page on every run with nothing the user could do about it. Dropping the entry loses "this page once rested on that source" from the page itself, but not from the repository: the management file survives with its `generated_pages[]` still naming the page, its `## Retraction Reason`, and its public `content/sources/` page — and the whole change is one commit in `git log`.
2. **Run Pass 3** for this one page, as an `action: update` entity whose `existing_path` is the page itself: `type`, `title`, slug and `lang` come from the page's own frontmatter, and the existing page is supplied as context exactly as Pass 3 already does for an update. **In a merge, the absorbed pages are supplied as context too**, and the page is written as one page about the one concept they all describe — what each says is carried over as far as the merged sources support it (Pass 4 checks every claim against all of them). `sources:` is the plan's union: the kept page's entries, then every absorbed page's entry not already listed, copied through untouched. `aliases` keeps every alias the kept page had and adds every merged alias from the plan — **the one-alias-per-language rule of Pass 3 does not apply to them**: it limits names a source supports, and these rest on the person's decision. Every Pass 3 content rule applies unchanged, with one content delta stated in step 1: when a retracted source was dropped, what rested on it is not merged forward from the existing page. Four frontmatter deltas, which override Pass 3 step 3's `action: update` rules:
   - `sources:` is copied through **untouched** — same entries, same hashes, same `license` values. Nothing is appended (in a merge, beyond the absorbed pages' entries above); step 1 already established the sources are the same ones. The single exception is a `status: retracted` entry, which step 1 dropped along with the content behind it.
   - `expires_at` is left as it is. Pass 2 did not run, so there is no source-stated date for this run to prefer, and `null` here would mean "not asked", not "no expiration".
   - `review_status` is reset to **`pending`**, overriding Pass 3 step 3's "preserve `reviewed`" rule. That rule is for incremental merges, where a human's earlier review still covers most of the page; a rebuild replaces the page's structure wholesale, and carrying `reviewed` across would attach a human's sign-off to text no human has read. The trust ladder depends on that never happening. **`reviewed_by` is dropped from the output at the same time**: it names whoever signed off on the previous version, and keeping it beside a fresh `pending` would leave that name to resurface the next time the page reaches `reviewed`. Pass 3 writes the page wholesale, so omitting the field from the output is all that is required — no separate delete step.
   - `generated_at`, `generated_by` and `generated_with` are updated to this run.
3. **Run Pass 4** unchanged, including its retry loop and its one-hop assembly — `build_onehop_context.py` is called here exactly as `references/pass4-review.md` step 1 describes, with the rebuilt page on stdin. Nothing about this mode changes the neighbourhood: the page keeps its path, so its lang/Type/slug and therefore both directions of the hop are the same ones normal generation would find. The same management-file carve-out as step 1 applies: Pass 4 step 5's `failed_pages` entry and step 7's status update do **not** run. Those describe the whole source and every page it produced, not this one rebuild; letting step 7 fire would, for a source that generated five pages, flip its management file from `status: generated` to `status: failed` (with a `## Failure Reason`) because a single rebuilt page failed review, discarding the recorded state of the other four (step 5 below). A page that still FAILs after `generate.max_retries` is **left on disk exactly as it was** — do not write a partial or failed rebuild over a page that was fine before — and reported as a failed regeneration.
4. **Unchanged-output valve.** Before writing, compare the rebuilt page with the one on disk, ignoring only the five bookkeeping fields step 2 rewrites (`review_status`, `reviewed_by`, `generated_at`, `generated_by`, `generated_with`). `reviewed_by` has to be ignored here even though step 2 drops it rather than rewriting it: leave it out of the ignore list and its absence from the rebuilt output counts as a difference, so a page carrying one — that is, every Route A page, exactly the population this valve exists for — could never compare identical and the valve would be dead for them. If the rest is byte-identical, keep the existing `review_status` (so a `reviewed` page stays `reviewed`) **and keep `reviewed_by` with it** — the two always travel together; dropping only the name would leave a page that claims review with no reviewer, breaking the very fact this valve exists to preserve — and write the page with only the three `generated_*` fields updated — the page genuinely was rebuilt under the current rules and found to need no change, so it should stop showing up in the next `generated_with` sweep. `sources:` is part of that comparison, so a page that had a retracted entry dropped — or that took over an absorbed page's sources or names — can never compare identical and always lands on `pending` — which is right: what a page rests on changed, and no earlier review covered the page in that state. The comparison is deliberately textual: a semantic same-meaning judgment would put a non-deterministic decision in charge of whether human review is required. LLM output is not deterministic, so expect this valve to fire rarely. Pass 4 step 6's `reset_review_on_content_change.py` then runs over the written page as it does in the normal flow and agrees with whichever way this went: a rebuilt page is already `pending` so it is skipped, and a page the valve kept at `reviewed` compares equal against HEAD, so nothing here needs a carve-out.
5. **Do not write back to the source management file.** Regeneration creates no new pages, so `generated_pages` is unchanged, and `last_generated_at` records when a source was turned into pages — which is not what happened here. Leaving management files alone also keeps `check_ingest_freshness.py`'s reading of `source.hash` intact.

In a merge, once the kept page is written the driver hands you `references/merge.md` as the `merge-absorb` step. If the kept page failed review or was skipped, that step does not run: nothing is absorbed, and the report says the merge did not happen and why.

After all selected pages are processed the driver runs `rebuild_index.py` itself — a rebuild can change a page's `title`, and `index.md` carries titles. Skip the Ingest Status Reconciliation step: no management file's status was in play. Then report, per page, which were rebuilt, which were unchanged, which were skipped and why, which failed review, which pages were merged into which (`references/merge.md` lists what to say), and which fell back to `.wikicommit/schema/default.md` for want of a schema file for their type (Pass 3 step 1 — this mode never reaches the Completion Notice that otherwise carries that list, and a rebuild run right after `/wikicommit-schema-propose` will still fall back until that Skill's PR is merged, since it deliberately does not auto-merge); remind the user that rebuilt pages are back at `review_status: pending` and that the next `/wikicommit-merge` will open a fresh review-tracking Issue for each (its scan only skips pages with an *open* Issue, so a previously-closed one does not suppress the new one).

This report is the `report` step. Report it to the driver before writing it out, so the record's elapsed time covers the whole run, and give the record's path and duration alongside the report:

```bash
python .wikicommit/scripts/driver.py done <the run path> --step report --outcome reported \
    --page <each page rebuilt> --count regenerated=<N> --count unchanged=<N> --count failed=<N>
```

That call is what closes the run record; without it every regeneration run — including one that did exactly what was asked — would be reported by `check_run_records.py` as a run that did not finish.
