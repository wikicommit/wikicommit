---
pass_token: "c41a7f6b"
---

# Pass 2c: Entity Extraction (LLM → JSON)

## Contents

- The analysis JSON this pass returns, field by field
- What to put in the LLM's context (installed types and their hierarchy, existing pages, `theme`, the entity policy, `## User Notes`)
- The rules: `lang`, slug derivation, `action` and `existing_path`, source-as-entity candidates, documents the source only cites in passing, most-specific-type deference, one source yielding several types, tabular sources, `exclude_reason`, `expires_at`, `coverage_gap_note`
- Writing `## Summary` and `## Generation Notes` back to the source management file

**Stamp `--pass pass2c-entities` on entry**, with `--source` naming this source's management file. **Pass `--token c41a7f6b` with it** — the value of this file's `pass_token`. `record_run.py` opens this file itself to compare, so the stamp records that this file was read rather than that the pass was improvised; without `--token` the stamp reads `token: unchecked`.

Ask the LLM to analyze the extracted text and return **only** the following JSON (no Markdown code block wrapper). **`summary` holds only a summary of the source's content — nothing about how this run treated any entity.** An excluded entity's reason belongs in that entity's own `exclude_reason`/`exclude_note` below, never folded into `summary` — `_write_source_page()` publishes `summary`, so a reason written there reaches the public site:

```json
{
  "summary": "2-3 sentence summary of the source's content, in <primary_lang>.",
  "entities": [
    {
      "type": "schema:Person",
      "title": "Taro Yamada",
      "slug": "yamada-taro",
      "lang": "<primary_lang value>",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": null
    },
    {
      "type": "schema:Organization",
      "title": "CompanyA",
      "slug": "companya",
      "lang": "<primary_lang value>",
      "action": "update",
      "existing_path": ".wikicommit/entity/ja/Organization/companya.md",
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": null
    },
    {
      "type": "schema:Organization",
      "title": "Unrelated Corp",
      "slug": "unrelated-corp",
      "lang": "<primary_lang value>",
      "action": "exclude",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "exclude_reason": "theme_mismatch",
      "exclude_note": "A personal acquaintance's employer, unrelated to the configured theme"
    },
    {
      "type": "schema:Person",
      "title": "Hanako Suzuki",
      "slug": "suzuki-hanako",
      "lang": "<primary_lang value>",
      "action": "exclude",
      "existing_path": ".wikicommit/entity/ja/Person/suzuki-hanako.md",
      "ambiguous": false,
      "alternatives": [],
      "exclude_reason": "privacy",
      "exclude_note": "An advisory-committee member named in the source; a private individual, which entity-policy.md rules out"
    },
    {
      "type": "schema:DefinedTerm",
      "title": "キリマンジャロコーヒー",
      "slug": "kilimanjaro-coffee",
      "lang": "<primary_lang value>",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": "産地の標高（1,600〜2,000m）の記載があったが DefinedTerm.md の properties フィールドに受け皿がないため本文にのみ記載"
    },
    {
      "type": "schema:Organization",
      "title": "スターバックス",
      "slug": "starbucks",
      "lang": "<primary_lang value>",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": null
    },
    {
      "type": "schema:GovernmentService",
      "title": "児童手当",
      "slug": "child-allowance",
      "lang": "<primary_lang value>",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": "2026-07-01",
      "coverage_gap_note": null
    }
  ]
}
```

<!-- skill-language-exception: verbatim source text quoted to illustrate the multi-deadline expires_at rule -->
The last example illustrates two things at once: `expires_at` (the source text states multiple deadlines for different disbursement schedules — "8月支給分は7月1日、12月支給分は11月1日、4月支給分は3月1日" — so `2026-07-01`, the earliest of the three, was chosen per the multi-deadline rule below, while the full breakdown still goes into the page body as usual) and the outcome of a Pass 2b approval: this entity is generated directly as `schema:GovernmentService`, the type approved and added to `.wikicommit/schema/` moments earlier in Pass 2b for this exact source, rather than falling back to the nearest already-installed type. Note what that entity is — the allowance scheme itself: who qualifies, what it pays, on what schedule. The ordered steps a resident performs to *apply* for it are a different subject, and if the same source sets them out they are a second entity of a different type, per the deference and one-source-many-types rules below. Do not read this example as `GovernmentService` being the right answer and `HowTo` the wrong one for a single page.

The `kilimanjaro-coffee` example illustrates `coverage_gap_note`: the source text states the coffee's growing altitude, but `.wikicommit/schema/DefinedTerm.md`'s `properties:` block has no field for it, so the LLM records the gap in one sentence instead of silently dropping it or inventing a frontmatter field.

Note that the example above mixes English (`exclude_note` on `Unrelated Corp`) and Japanese (`coverage_gap_note` on `kilimanjaro-coffee`) purely to illustrate several unrelated rules side by side — in an actual run all of `summary`, `exclude_note`, and `coverage_gap_note` must share a single language, `<primary_lang>` (see the rules below).

Provide the LLM with the following context:
- Full extracted text
- List of schema type filenames under `.wikicommit/schema/` (with their `wikicommit.base` values) — **re-scan the directory after Pass 2b**, so any type just added there is available as a candidate here
- **How those installed types relate to each other**, from `python .wikicommit/scripts/check_schema_org_type.py --list-installed-hierarchy`. One tab-separated line per installed type: the type, then its installed ancestor types nearest-first, or `-`. Run it once per source, after the Pass 2b re-scan (`references/pass2b-type.md`), and include the output verbatim
- `wikicommit.granularity` rules from each schema file
- The `properties:` field list (the keys under each schema file's `properties:` block) from each schema file (used for `coverage_gap_note` detection below)
- Existing pages under `.wikicommit/entity/<primary_lang>/` (title + path) — **include both pages already on `main` and pages written during this run** (scan the directory on disk; do not use `git ls-files` — it only sees tracked files and will miss pages written earlier in this run; do not use `git status`)
- Body section of the source management file (used as additional instructions for the LLM)
- The `schema:` field from the source management file, if present (e.g., `schema: schema:Person`). When provided, instruct the LLM to treat this as a strong type preference and use it unless the source content clearly contradicts it.
- The `theme` value obtained from `config.yml`. If non-empty, instruct the LLM to set `action: exclude` on entities unrelated to `theme`. If `theme` is empty, instruct the LLM not to use `exclude_reason: "theme_mismatch"` at all — no entity may be excluded as off-subject. Say that in those terms rather than as "never use `exclude`": the entity policy in the next bullet is a separate axis that can still exclude an entity here, and a wiki left with the default blank `theme` is exactly the wiki where forbidding `exclude` outright would silently disable it.
- The entity policy held from the Processing Flow block in `SKILL.md`: `exclude_living_persons` and the body prose. Pass both verbatim, and keep them labelled as the permissibility axis so the LLM does not weigh them as relevance — a subject can be squarely on-`theme` and still fall under this policy, and the reverse. When the switch is `false` **and** there is no prose, say so explicitly rather than omitting it: `exclude_reason: "privacy"` must not be used at all in that case, the same way an empty `theme` forbids `theme_mismatch`.
- The current list of type strings already in use by wiki pages that have no dedicated `.wikicommit/schema/` file yet: run `python .wikicommit/scripts/check_schema_coverage.py` once per run and include its `UNCOVERED:` lines. This helps the LLM reuse an existing not-yet-schematized type string for the same concept instead of coining a new one (convergence is encouraged, not guaranteed — see `check_schema_coverage.py`'s own exact-match-only design note). If the list is empty (e.g. first run), omit this from the context.

Set the `lang` field to the `primary_lang` value obtained from `config.yml` for all entities.

Rules:
- Set `slug` following this priority order (the file name must be a language-neutral English identifier, not a phonetic transliteration of the source language):
  1. Common nouns / concept terms → translate to English (e.g. `キリマンジャロコーヒー` → `kilimanjaro-coffee`; `kirimanjaro-koohii` is a transliteration and not acceptable).
  2. Proper nouns (people, organizations, places, etc.) that have an established English spelling → use that spelling (e.g. `スターバックス` → `starbucks`; `sutaabakkusu` is not acceptable).
  3. Proper nouns with no established English spelling → romanize (e.g. `山田太郎` → `yamada-taro`).
- **Source-as-entity candidates**: when Pass 2a flagged the source document itself as a citable standalone work, include it as an ordinary entity in this array — its `title` is the work's own original title *verbatim, in whatever language the source itself uses* (e.g. the paper's actual published title), not a concept discussed within it and not translated into `<primary_lang>` — a citable work is identified by its real title, and translating it would defeat the citability this entity exists to capture (this is a narrow, deliberate exception to the general "entity content is written in `<primary_lang>`" rule; the page's `lang` field and body content still follow `<primary_lang>` as usual, only the `title` value itself stays verbatim). `slug` follows the same priority rules above applied to that original title; `type` is whatever Pass 2b resolved for it, or the nearest fitting `installed schema/` type if Pass 2b found nothing. It participates in `action`/`existing_path`/`ambiguous`/`exclude` exactly like any other entity, and nothing about `sources:` changes for it — its page's `sources` is simply the one-element list wrapping this registered source, same as any other `action: create` entity (Pass 3 step 5, `references/pass3-generate.md`). This entity is *in addition to*, not instead of, the concepts/people/organizations Pass 2c extracts from within the source as usual.
- **Do not extract a document this source only cites in passing.** When the source names another document once — a contrastive citation, a line in a related-work paragraph, an entry in the reference list — while writing about something else, that document is not an entity. Leave it out of `entities` entirely. **The opposite case does extract**: where the source treats that document, or the fact it is cited for, as *its own subject* — its title, or a central claim, is about it — it is an ordinary entity and the rest of the rules here apply to it unchanged. Both halves are written here on purpose: a boundary stated on one side only gets applied on one side only.

  **The test is the same one `.wikicommit/review-rules.md` uses**, applied one stage earlier: does this source treat that document's subject as its own subject, or does it name it once while writing about something else? **Where you cannot tell, treat it as the passing mention and do not extract.** That tie-break is not a preference — check 4 in the review rules breaks the same tie the same way, and a Pass 2c that were more permissive than the review at exactly the unclear cases would guarantee the wasted round: extract, write, fail, record, repeat.

  Why it belongs here and not only downstream: Pass 3 (Secondary citation discipline, `references/pass3-generate.md`) and Pass 4 (`MISSING_SOURCE`) already apply this rule, but only *after* the entity has been cut, so the page gets written and then thrown away — and because that discard is recorded in `failed_pages`, the source keeps matching Pass 1's collection condition (`partial` with a non-empty `failed_pages`), so every later run cuts, writes and discards the same page again.

  **Judge it from how this source treats the document, and do not go looking for whether it is registered.** The registry under `.wikicommit/source/` is deliberately not in your context, and this rule does not ask you to scan it. If that document is registered separately, its own run writes its page; this source contributing nothing to it costs nothing, because a passing mention had no facts to contribute in the first place.

  **This is not Pass 2a's source-as-entity judgment, which is the bullet above.** That one asks whether *this source document itself* should have a page; this one asks whether *a different document the source quotes* should. They are separate decisions and both can fire in one run: a paper can rightly get a page for itself while the paper it cites in passing should not.

  **An entity left out this way leaves no trace, and that is accepted.** An `action: exclude` entity gets a line in `## Generation Notes` and in the Completion Notice; simply not extracting one is silent. A third `exclude_reason` would record it, but the axis is neither relevance nor permissibility — it is evidence — and an enum value with no consumer is not added. **The exposure is bounded in one direction only, which is why this must not be over-applied.** Calling a passing mention what it is drops a page Pass 4 was going to reject anyway, one stage earlier — that is the tie-break above, and it costs nothing. Calling a document the source is genuinely *about* a passing mention is the opposite error, and it is not symmetric: that page would have passed review, and dropping it here removes it with no `exclude_note`, no Completion Notice line and nothing for any health check to find, because a page that was never written is not an orphan and not a wanted page either. The silence sits on the side of the error that is not bounded. So reserve the tie-break for cases you genuinely cannot call: where the source's title or a central claim is about that document, extract it.
- Always generate `summary` (2-3 sentences), regardless of whether `theme` is set. This should match the Pass 2a summary unless something in the fuller entity-extraction pass changed the LLM's read of the source — do not treat Pass 2a's summary as merely a draft to diverge from.
- Set `action: update` and `existing_path` if a page with the same type and slug already exists — **scan the directory on disk** (do not use `git ls-files`; it only sees tracked files and will miss pages written by earlier sources in this run). A page written by an earlier source in the same run must be detected as `action: update`, not `action: create`.
- **Set `existing_path` on an `action: exclude` entity too, when that entity already has a page.** Same lookup, same scan — you are already doing it for the bullet above, and you know this entity's `lang`, type and slug because you just assigned them. Nothing here deletes anything — the two paragraphs below say what it is for and what it is not.

  Why it matters: **generation never removes a page** (`/wikicommit-remove` is the only path that does), so an entity excluded today can have a page from an earlier run still standing and published. `## Generation Notes` records the entity by title, and the slug's derivation is not reversible (a common noun is translated, an established spelling kept, otherwise romanized), so on a wiki whose `primary_lang` is not English, finding the page from the title means grepping `title:` across the tree. You already have the answer, as a by-product of naming the entity.

  **This field is information here and drives nothing.** On a `create`/`update` entity it makes Pass 3 read the existing page into context; Pass 3 only ever handles those two actions, so an `exclude` entity's `existing_path` causes no read and no write. State it rather than leave it implied: nothing about an excluded entity's page is opened, rewritten, or removed on the strength of this field.
- **When several installed types fit, take the most specific one** — the one furthest down the `--list-installed-hierarchy` chain, not the one highest up. An ancestor type always fits: `Park` and `Museum` are descendants of `Place`, so writing a park as a `Place` is never *wrong*, only coarser, and the broader type is the more familiar one to reach for. That is why this needs saying out loud: every quality gate still passes on the coarser type, because it has a schema file, yet the specific type's `properties:` go unused, its content ends up as prose in the body, and its `index.md` lists a fraction of what belongs there.

  This applies only to types **installed in `.wikicommit/schema/`**. A more specific type that exists in Schema.org but has no file here is Pass 2b's business, not this step's; do not reach past the installed set. And specificity never overrides fit — if the source does not actually establish that the subject is a park, `Place` is the correct answer, not a fallback.

  **A `granularity` line that names another type outranks your own read of the fit**. Some type files say, in so many words, when their type is *not* the answer — "prefer `schema:HowTo` when the source's substance is an ordered set of steps the resident performs". When a candidate type's `granularity` hands the case to another type and that other type is installed, follow it. Its author had the whole type in view when they wrote it; you have one source. This holds even when that type file was written by an LLM earlier in this same run.

  Two things follow. If the type it defers to is **not installed**, the deference cannot be acted on — stay with the type you have, and let Pass 2b decide separately whether that other type should exist here. And a deference line is about *this* subject, not the source: a source can perfectly well yield one entity of each type, which is the next rule.
- **One source may yield entities of different types, and sometimes should**. Nothing has ever restricted the `entities` array to a single type — but nothing said to look for the split either, and a source that is mostly about one thing tends to come out as one entity. When a source covers both a thing and a procedure for using it, extract both: a service and the steps for applying to it, a piece of software and a walkthrough for setting it up, an institution and its admission process. A page that runs two or three times the length of its siblings is the tell that two subjects are sharing it. Split only where each part stands on its own as a subject; do not manufacture a second entity to satisfy this rule.
- **Tabular sources: judge independence by the columns, not by the row count**. The schema templates ask whether the source states independent facts about a subject, and in prose the *amount* said about something stands in for that — a paragraph means more than a passing clause. A table breaks that proxy: every row is one row, so a subject with eight attributes and a subject with one look identical by volume. Ask instead what a row's **columns** actually say about it. A row carrying several attributes of its own — a location, a size, a date range, a category — states independent facts and can support a page. A row that carries a name and one relationship does not, and the sheer size of the table around it changes nothing. Where one subject occupies several rows, read those rows together: the same relationship repeated is still one relationship, but if they give that subject a scale, a span or a spread of its own (how many, over what period, of what kinds), the columns are stating attributes of the subject and it can support a page. Aggregating a subject's own rows is the half that is easy to miss.

  When a row yields nothing but that one relationship, **do not create a page for it**. Record the relationship on the *other* end if a page for it already exists (`action: update`), and otherwise let it go — the table itself stays reachable through the page's `sources` and through the source's own page under `content/sources/`, which links back to it. A page written from such a row can only say who is currently responsible for something and until when, which is a fact about a contract, not about the thing.

  Do put the table's *shape* somewhere: the concept the table is about — the scheme, the programme, the category — is usually a real entity with real content, and the aggregate belongs on that page as a characterization (how many, how concentrated, what the range is), not as the rows written out. For example, in a spreadsheet of facilities whose columns are facility, facility count, operator, term, selection method and owning department, a facility fails the column test because no column says anything about the facility itself, while an operator clears it because its own rows, read together, give it a scale, a span of terms and a mix of selection methods — attributes of the operator, not of any one contract. The bare row count never enters into it.
- Set `ambiguous: true` when the LLM cannot confidently determine the type; include candidates in `alternatives`
- Skip entities with `ambiguous: true` during page generation. **Immediately** notify the user (console output) with the entity's `title`, candidate `alternatives`, and the source management file at the moment of detection — a later source in the same run may abort processing (e.g., missing prerequisite skill, `config.yml` missing, extraction failure) before the Completion Notice is reached, so this notice must not depend on the run completing. Also append the entity to a running list so all detections can be rolled up together in the Completion Notice (`references/completion-notice.md`).
- Set `action: exclude` (only when `theme` is non-empty) for entities the LLM judges unrelated to `theme`. Set `exclude_reason: "theme_mismatch"` and a short `exclude_note` explaining why, written in `<primary_lang>` — the same language as `summary` (do not let the agent's session/UI language leak in here). No human confirmation is needed for `exclude` (unlike `ambiguous`) — it is applied automatically and silently, recorded only in the management file's `## Generation Notes` (see the write-back step at the end of this file) and the Completion Notice.
- **Set `action: exclude` with `exclude_reason: "privacy"` for entities the entity policy rules out**, on the same terms as `theme_mismatch`: automatic, no human confirmation, an `exclude_note` in `<primary_lang>` saying which part of the policy applies. This is a second, independent reason to exclude, not a variant of the first — judge relevance against `theme` and permissibility against the policy separately, and where both would exclude the same entity, record `privacy`, since it is the reason that would still hold if the wiki's subject changed. It fires on two inputs:
  - `exclude_living_persons: true` → an entity this source establishes to be a living individual. Judge that as you judge relevance: from what the source says. Where the source does not establish it either way, do not exclude — this switch is about people the source shows to be living, not about anyone it fails to mention a death for.
  - the body prose → whatever categories it names. It is free text and is not limited to people; a policy can rule out matters under dispute (`Event`-shaped) or an organization's unreleased information just as well.

  **Do not over-apply it.** The prose typically names who is *in* as well as who is out, and a wiki that keeps out public figures acting in their public capacity, or historical figures, has lost pages it had every reason to hold. Where the policy does not clearly reach a subject, generate the page; this judgment has a safe direction and it is not the exclusion.

  Nothing here reaches back. Turning the switch on does not remove pages that already exist, because `--regenerate` does not run this pass — say so in the Completion Notice, and point at `/wikicommit-remove` (`removed_reason: gdpr` where that applies) as the way to take one down. **Name the pages** rather than saying it in the abstract: `existing_path` is resolved for excluded entities too (see the `existing_path` bullet above), so where one is set the notice can say which page this applies to.
- Set `expires_at` to a concrete `YYYY-MM-DD` date only when the source text explicitly states a calendar date after which the entity's content is expected to be stale — an application deadline, a fiscal-year-bound validity period, a stated expiration date, etc. Otherwise leave it `null`; never guess or infer a date that is not written in the source (e.g. do not translate a vague "来年度まで" into a specific date), and never derive it from unrelated context like the source's publication date. If the source states several distinct dates that could each plausibly apply to the entity (e.g. different deadlines per sub-case, as in the `GovernmentService` example above), set `expires_at` to the **earliest** of them — `expires_at` exists to prompt a re-check by the review process (`check_expires.py`), and it is safer to flag content for re-review too early than too late; the full breakdown of all the dates still belongs in the page body, which this field does not replace.
- Set `coverage_gap_note` to a **single sentence** when the source text contains a concrete, domain-specific attribute for this entity (e.g. target age range, required tools, jurisdiction) that has no corresponding field in the entity's type schema's `properties:` block. If an entity has multiple such gaps, summarize them all in one sentence (do not use an array — follow the same single-string design as `exclude_note`). This applies only to `create`/`update` entities (never `exclude` or `ambiguous` ones). This is evidence-gathering only: never write to `.wikicommit/schema/` and never invent a new frontmatter field to hold the value — the gap information still belongs in the page body as usual, unaffected by this note. Leave `coverage_gap_note` `null` when nothing is missing, which is expected to be the common case. When non-null, write it in `<primary_lang>` — the same language as `summary` (same reasoning as `exclude_note` above).
- After obtaining the JSON, write its `summary` field into the source management file's `## Summary` section: create the section (`## Summary` heading followed by the text) if it does not already exist, or overwrite its existing contents if it does. **Write nothing else there** — `## Summary` holds a summary of what the source says, and nothing about how this run treated it.
- Write the per-entity notes into a **separate `## Generation Notes` section** (create it if absent, overwrite its contents if present), placed after `## Summary`: one sentence per entity for every non-null `coverage_gap_note` (e.g. `"「キリマンジャロコーヒー」: 産地の標高（1,600〜2,000m）の記載があったが DefinedTerm.md の properties フィールドに受け皿がないため本文にのみ記載"`), and one sentence per `action: exclude` entity naming the entity, its `exclude_reason`, its `exclude_note` and — when the entity turned out to have one — its `existing_path`. The path costs nothing to add here because the sentence is being written anyway, and it is the copy that lasts: the Completion Notice is gone when the run's output scrolls away, while this stays in the management file. **Say what is true of it, not what to do about it** — the page exists and this run did not create or update it. It may be held up perfectly well by another source that this run never touched. If there are none of either, do not create the section (and delete it if a previous run left one). Since `exclude_note`/`coverage_gap_note` are already required to be in `<primary_lang>` (same as `summary`, see above), this write never needs to translate anything — do not translate at write time either. **Never modify a `## User Notes` section** if present — that section is hand-written by a human and must be preserved verbatim. <!-- skill-language-exception: example coverage_gap_note text, quoted to show the shape of the sentence written into ## Generation Notes -->

  > **Why these are not in `## Summary`**: `convert_wikilinks.py` mirrors every management file to a **public** page under `content/sources/`, and `## Summary` is one of the sections it renders there. Exclusion notes named real living people, alongside the reason they were dropped and the internal identifiers behind it (`.wikicommit/entity-policy.md`, `exclude_living_persons`) — so a policy whose whole purpose is to not write about a person was publishing the result of its own application, under that person's name. `coverage_gap_note` leaked internal identifiers the same way (which type file's `properties:` block lacked a field). Neither is reader-facing. `_write_source_page()` renders a **whitelist** of sections, so a new section is private by default — the same way `## User Notes` and `## Failure Reason` already are. Do not move these back into `## Summary`, and do not add `## Generation Notes` to that whitelist.

  > **Heading labels are always fixed English, regardless of `primary_lang`**. Heading labels are identifiers the tooling matches on rather than prose a reader reads, so they are not localized: always write `## Summary`, `## Generation Notes` and `## User Notes` verbatim, never a translated or `primary_lang`-dependent heading. Pre-existing management files generated before this change keep their old `## サマリ`/`## ユーザーメモ` headings as-is (no automatic migration, same "both forms may coexist" policy the source-tree layout itself already follows); only newly written/overwritten `## Summary` sections use the new heading. If a management file still has the old `## サマリ` heading, treat it as the same section (overwrite it in place rather than adding a second, redundant `## Summary` section) — but do not rename an untouched `## ユーザーメモ` heading you are not otherwise touching, since that section must be preserved verbatim per the rule above.

For `action: update` entities, read the existing page in full and add it as additional context for Pass 3.
