---
name: wikicommit-translate
description: Translate a wiki page (or all pending translations) into configured target languages, writing locally only (no Git)
disable-model-invocation: true
---

# wikicommit-translate

Interactive translation Skill (Issue #280). Per-page processing is identical to the unattended Phase 4 pipeline — inject the source page's full text plus `DefinedTerm/` glossary terms and the source→target term table built from them, generate a translation, run a same-LLM quality check, and attach `translated_from` / `source_commit` / `translated_at` / `translated_by` / `translated_with`. The only difference is *who* calls it and *when*: this Skill is invoked by a human, writes locally, and performs no Git operations. Run `/wikicommit-merge` afterward to commit and open a PR.

## Usage

```
/wikicommit-translate <page> [--lang <target>]   # translate a single page
/wikicommit-translate                            # batch mode: process all untranslated/stale (page, target) pairs
```

`<page>` must be a source page (a page without `translated_from`) — e.g. `.wikicommit/entity/ja/Person/yamada-taro.md`. If the given page itself has `translated_from` (i.e. it is already a translation), stop and tell the user to run this on the original page instead.

## Processing Flow

### Step 0: Open a Run Record and Read Config

```bash
python .wikicommit/scripts/record_run.py start --skill wikicommit-translate \
    --model "<the model ID this runtime reports for you>" --arg "<each argument, one --arg each>"
```

A record with a start and no end is what says a run did not finish, and nothing else in this repository is keyed on a run — so leaving it open is the signal rather than a failure state to avoid. Keep the path it prints. (Issue #790)

Then read `.wikicommit/config.yml` and obtain `translation.primary_lang` and `translation.targets`. If `.wikicommit/config.yml` does not exist, stop and tell the user to run `/wikicommit-init` first.

### Step 1: Determine Mode

- **Argument given** → single-page mode (Step 2).
  - `--lang <target>` given → target language list = `[<target>]`.
  - `--lang` omitted → target language list = `translation.targets`. If `targets` is empty, stop with: "No target language. Pass `--lang <lang>`, or set `targets` in `config.yml`." (fixed English — read by the operator, so Issue #770's rule applies)
- **No argument** → batch mode (Step 3).

### Step 2: Single-Page Mode

For each target language in the target list determined in Step 1:

1. Skip the target if it equals the source page's own `lang` (translating a page into its own language is a no-op).
2. Translate unconditionally — whether or not a translation already exists for this target, always regenerate the full translation from the current source content (same behavior as the Phase 4 pipeline: a full re-translation every time, whether the target is new or already exists).
3. Run the per-page translation procedure in Step 4.

Single-page mode has no work list to reorder, so it cannot settle the glossary first the way batch mode does (Step 3) — it uses whatever target-language `DefinedTerm` pages already exist, via the same Step 4 step 2b table. Translating a wiki's `DefinedTerm` pages before its other pages is therefore worth doing by hand here, or by running batch mode instead (Issue #554).

After all targets are processed, run the "index.md Update" step below, then show the guidance in "After Completion".

### Step 3: Batch Mode

1. Run:

   ```bash
   python .wikicommit/scripts/check_translation_status.py
   ```

2. Collect two kinds of (source page, target language) pairs from the output:
   - `UNTRANSLATED: <source-page> (target: <lang>)` lines → the pair is `(<source-page>, <lang>)` directly.
   - `STALE: <translation-page> (...)` lines → read the `translation-page`'s frontmatter to get `translated_from` (the source page) and `lang` (the target language); the pair is `(translated_from, lang)`.
3. Combine both lists into a single work list, then **order it so that every `DefinedTerm` pair comes first**, keeping the previous ascending-by-`page:`-path order within each of the two groups (Issue #554). A pair belongs to the first group when the `<Type>` segment of its path is exactly `DefinedTerm`; that segment is identical for a source page and its translation, so the same test works for `UNTRANSLATED` and `STALE` lines alike. The reason is that translating prose before its glossary is settled is backwards: `DefinedTerm` is the most-referenced type in a wiki, and under the previous plain path-ascending order the glossary was as likely as not to be processed after the pages that cite it, since `DefinedTerm/` merely sorts alphabetically between (say) `BlogPosting/` and `custom/`. Step 4's terminology table (step 2 there) is re-read from disk for each pair, so pairs later in this run see the target-language terms this run has already settled.

   If the combined count exceeds 5 (same threshold as `wikicommit-generate`'s and `wikicommit-collect`'s no-argument guard), do not start processing yet — show the count and the **ordered** list of pairs, then ask the user to choose: **(a)** process all of them in this run, or **(b)** process only the first 5 of that order and leave the rest for a later run. If the count is 5 or fewer, proceed with all of them without asking. Because the list is `DefinedTerm`-first, choosing (b) settles the glossary within this run instead of deferring it behind unrelated pages.
4. For each `(source page, target language)` pair, **in that order**, run the per-page translation procedure in Step 4 (for a `STALE` pair this regenerates the existing translation page in place; for an `UNTRANSLATED` pair this creates a new one).

After all pairs are processed, run the "index.md Update" step below, then show the guidance in "After Completion".

### Step 4: Per-Page Translation Procedure

Given a `(source page, target language)` pair:

1. Read the source page in full (frontmatter + body).
2. **Glossary** — build two distinct things, in this order:

   a. **Term definitions.** Read all pages under `.wikicommit/entity/<source page's lang>/DefinedTerm/` (excluding `index.md`) as a glossary for terminology consistency, if that directory exists. These tell you what each term *means* in the source language.

   b. **Source→target term table** (Issue #554). Definitions alone do not say how a term is *rendered* in the target language, so on their own they leave every page free to re-derive its own wording for the same term. Collect the `title` of each already-translated `DefinedTerm` page in the target language and pair it with the same-slug source page's `title` — the filename is the slug, and slugs are language-neutral, so the basename is the join key. Read only the `title` line, never the whole page:

      ```bash
      grep -m1 -H '^title:' .wikicommit/entity/<target language>/DefinedTerm/*.md 2>/dev/null \
        | grep -v '/index\.md:' | grep -v '/<slug>\.md:'
      ```

      `<slug>` is the slug of the page being translated. That last filter matters only when the page being translated is itself a `DefinedTerm` page: in that case the glob also matches this pair's *own* target-language page, and for a `STALE` pair that page still holds the previous translation of the very term this run is about to re-decide. Feeding it back in would both break the blindness this procedure states in step 3 and, via the step 5 rule below, pin the term to its old wording forever — a corrected source `title` could never reach the target language. For any other type the filter is a harmless no-op (drop it if you prefer).

      Reading these pages in full instead would cost pages × terms of context for information the table does not need (a pilot wiki had 43 `DefinedTerm` pages). If the directory or the glob matches nothing, the table is simply empty and this step contributes nothing — that is the expected state for the first target-language page of a wiki, and for the first `DefinedTerm` page of a batch run. The command is re-run for each pair rather than once per run, so within a batch run (which processes `DefinedTerm` pairs first, Step 3) the table grows as the glossary is settled and later pairs see it.

      When translating a `DefinedTerm` page itself, the table therefore covers the sibling terms already translated but not the page's own term (which this run is about to decide) — use it for cross-references in the body, exactly as any other page would.
3. **Translator Notes** (Issue #524): if a translation page already exists at `.wikicommit/entity/<target language>/<Type>/<slug>.md` (same `Type`/`slug` as the source page) and its frontmatter has a non-empty `translator_notes` list, read it. This full re-translation is otherwise completely blind to the existing translation (it never reads the current translation page's frontmatter or body at all) — `translator_notes` is the one exception: it exists specifically so a translation-only fix made via `/wikicommit-fix` (mistranslation, terminology inconsistency, unnatural phrasing the original page doesn't need, since the original is correct as-is) survives being silently overwritten the next time the source page changes and triggers this full re-translation. If no translation page exists yet, or it exists but has no `translator_notes` field (or an empty one), skip this step — proceed exactly as before (Issue #524 makes no behavioral change for pages that don't use this field, including every translation page that existed before this Issue).
4. Have the LLM produce a translation:
   - `title`, and the body, translated into the target language.
   - `lang`: the target language.
   - `type`: unchanged (Schema.org type is language-neutral).
   - `tags`: each tag translated into the target language.
   - `properties:` (Issue #495 — the type-specific Schema.org properties block; never drop it or flatten it back to the top level): keep the same set of keys, nested exactly as in the source page. Within it, translate prose values the same way the body is translated (e.g. `properties.description`), while WikiLink-valued properties (e.g. `properties.affiliation: "[[Organization/companya]]"`) and other identifier-shaped values are copied unchanged — slugs and identifiers are language-neutral, only surrounding prose is translated. This copy-unchanged rule always wins over anything a `translator_notes` entry says (below) — a note that appears to target an identifier/WikiLink value (e.g. flagging a wrong `properties.affiliation` slug) is describing a problem with the source page's own data, not a translation choice, and should be fixed on the source page instead; it has no defined effect here.
   - Identifier fields at the top level (`wikidata`, `sameAs`) are copied unchanged — same reasoning as WikiLink-valued properties above.
   - `sources`: omit (translation pages inherit source provenance from the parent via `translated_from`).
   - `translated_from`: the source page's path.
   - `source_commit`: first run `git status --porcelain -- <source page path>` to check the source page's working tree state. If it prints anything (the source page has uncommitted local changes — modified, staged, or untracked), the body you read in step 1 already reflects that uncommitted content, but `git log` can only see the last commit, which predates it. Writing that stale hash would make `source_commit` point to a commit whose content does not match what was actually translated. To avoid recording a hash that doesn't correspond to the translated content, use the empty string in this case too. Otherwise (clean working tree for that path), use the output of `git log -1 --format=%H -- <source page path>`; if that is also empty (the source page has no commits yet — e.g. it was just generated and not yet merged), use the empty string as-is. In all empty-string cases, `check_translation_status.py` will correctly flag this as `STALE` until the source page is committed with no further local edits, which is expected.
   - `translated_at`: today's date (`YYYY-MM-DD`).
   - `translated_by`: set to the **currently running model ID** (e.g., `claude-sonnet-4-6`) — use the actual model ID in use, not a hardcoded value, written exactly as the runtime reports it (keep any suffix such as `[1m]`; do not shorten or normalize it — Issue #559) (same self-identification pattern `wikicommit-generate` Pass 3 uses for `generated_by`; Issue #453 — translation pages previously had no field recording which model translated them, so `WikiCommitBanner.tsx`'s reviewer-facing model attribution was silently missing for every translated page).
   - `translated_with`: WikiCommit's own version, not a model ID — read it once per run with `python .wikicommit/scripts/_version.py` and write that exact string on every page this run produces (Issue #577; the translation-page counterpart of the `generated_with` `wikicommit-generate` Pass 3 writes). It is what lets a human — reading `CHANGELOG.md` alongside a `grep` for this field — tell which pages were produced under an older set of rules. If that script is missing (a wiki repository initialized before this field existed), omit the field entirely rather than guessing a version — its absence is meaningful, and no back-fill is performed.
   - `review_status: pending` (unconditionally, regardless of the source page's own `review_status` — same rule as the Phase 4 pipeline).
   - **Bare URLs in body text**: if the source page's body contains a bare URL (not already in Markdown link syntax `[text](url)`), keep its boundary explicit in the translated body — a space on both sides, or angle brackets (`<https://example.com>`). This is especially relevant when translating into Japanese, where a URL is often immediately followed by punctuation or a particle (e.g. `で公開されている`) with no space; a Markdown parser can then swallow the following characters into the URL itself, producing a broken/percent-encoded link that `lychee` reports as unreachable and `markdownlint-cli2` flags as MD034. When the translated URL is immediately followed by non-space text, prefer the angle-bracket form.
   - **Translator Notes carry-forward** (Issue #524): if step 3 read a non-empty `translator_notes` list, apply each entry's guidance to whatever prose/terminology choice it addresses (e.g. an entry pinning a specific translation for a term overrides the LLM's own default choice for that term — subject to the `properties:` precedence rule above), and set the new page's `translator_notes` field to the same list, unchanged (copy the entries forward verbatim; do not drop, reword, or deduplicate them — this field is otherwise never touched by this per-page procedure, so simply carrying its value through is sufficient). Without this copy step the notes would be silently dropped from this run's output — the same loss-on-re-translation problem this feature exists to prevent, just one step later. If step 3 found no `translator_notes` (or it doesn't exist yet), omit the field from the new page exactly as this procedure already does for a first-time translation.
5. **Quality check**: have the LLM re-read the generated translation against the source page and the glossary from step 2, checking for semantic drift and inconsistent terminology. Terminology now has an objective referent rather than only the LLM's judgement (Issue #554): where the translation renders a term that appears in the step 2b table, it must use that table's target-language wording, and a divergence is a problem to fix. Two limits on that rule — it applies only to terms that actually have a `DefinedTerm` page in the target language (everything else is still judgement), and it yields to `translator_notes`, since a note is an explicit human decision about this page and the table is a default. It also never applies to the translated page's own term when that page is a `DefinedTerm`, because step 2b excludes that entry from the table. If it finds a problem, regenerate once; if the second attempt still has a problem, write the file anyway but tell the user what to double-check.
6. Write the translation to `.wikicommit/entity/<target language>/<Type>/<slug>.md` (same `Type`/`slug` as the source page), creating parent directories as needed. This is a local write only — do not `git add` or commit.
7. `index.md` is rebuilt once for all affected directories after all pairs are processed (see below) — no per-page action needed here.

### index.md Update (once, after all pairs)

After all `(source page, target language)` pairs for this run have been processed (i.e. after Step 2 finishes all targets, or Step 3 finishes all pairs), run:

```bash
python .wikicommit/scripts/rebuild_index.py
```

This deterministically rebuilds `index.md` for every Type directory under `.wikicommit/entity/` from the pages currently on disk (Issue #406 — the same script `wikicommit-generate` uses, replacing this Skill's previous per-directory LLM-driven update, Issue #338). It scans each directory itself, so there is no need to track which `<target language>/<Type>/` directories this run touched, and it correctly rebuilds `index.md` if one already exists from a prior `wikicommit-generate` run on the same language. `status: removed` pages are excluded automatically, and the frontmatter uses the bare Type name for `title` (Issue #320). This is a local write only — **do not commit**.

### After Completion

Close the run record before reporting, so its elapsed time covers the whole run:

```bash
python .wikicommit/scripts/record_run.py end <the path Step 0 printed> \
    --page <each translation page written> --outcome translated=<N> --outcome failed=<N>
```

Report its path and elapsed time — the record is not committed, so this run's own output is the only place a reader sees them.

```
Next steps:
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
  (translated pages are written with review_status: pending, same as wikicommit-generate output)
```

## Notes

- Do not commit or create a PR against `main` or any branch (that is `wikicommit-merge`'s responsibility)
- Do not write to `.wikicommit/schema/` (read-only)
- No Git operations of any kind — this Skill only reads the working tree (including via `git log` for `source_commit`) and writes new/updated files under `.wikicommit/entity/`
