---
name: wikicommit-translate
description: Translate a wiki page (or all pending translations) into configured target languages, writing locally only (no Git)
disable-model-invocation: true
---

# wikicommit-translate

Interactive translation Skill (Issue #280). Per-page processing is identical to the unattended Phase 4 pipeline (`docs/DesignDoc-pipeline.md` §6.4) — inject the source page's full text plus `DefinedTerm/` glossary terms, generate a translation, run a same-LLM quality check, and attach `translated_from` / `source_commit` / `translated_at` / `translated_by`. The only difference is *who* calls it and *when*: this Skill is invoked by a human, writes locally, and performs no Git operations. Run `/wikicommit-merge` afterward to commit and open a PR.

## Usage

```
/wikicommit-translate <page> [--lang <target>]   # translate a single page
/wikicommit-translate                            # batch mode: process all untranslated/stale (page, target) pairs
```

`<page>` must be a source page (a page without `translated_from`) — e.g. `.wikicommit/entity/ja/Person/yamada-taro.md`. If the given page itself has `translated_from` (i.e. it is already a translation), stop and tell the user to run this on the original page instead.

## Processing Flow

### Step 0: Read Config

Read `.wikicommit/config.yml` and obtain `translation.primary_lang` and `translation.targets`. If `.wikicommit/config.yml` does not exist, stop and tell the user to run `/wikicommit-init` first.

### Step 1: Determine Mode

- **Argument given** → single-page mode (Step 2).
  - `--lang <target>` given → target language list = `[<target>]`.
  - `--lang` omitted → target language list = `translation.targets`. If `targets` is empty, stop with: "対象言語がありません。`--lang <lang>` を指定するか `config.yml` の `targets` を設定してください。"
- **No argument** → batch mode (Step 3).

### Step 2: Single-Page Mode

For each target language in the target list determined in Step 1:

1. Skip the target if it equals the source page's own `lang` (translating a page into its own language is a no-op).
2. Translate unconditionally — whether or not a translation already exists for this target, always regenerate the full translation from the current source content (same behavior as the Phase 4 pipeline: "新規・更新いずれも無条件に全文再翻訳").
3. Run the per-page translation procedure in Step 4.

After all targets are processed, run the "index.md Update" step below, then show the guidance in "After Completion".

### Step 3: Batch Mode

1. Run:

   ```bash
   python .wikicommit/scripts/check_translation_status.py
   ```

2. Collect two kinds of (source page, target language) pairs from the output:
   - `UNTRANSLATED: <source-page> (target: <lang>)` lines → the pair is `(<source-page>, <lang>)` directly.
   - `STALE: <translation-page> (...)` lines → read the `translation-page`'s frontmatter to get `translated_from` (the source page) and `lang` (the target language); the pair is `(translated_from, lang)`.
3. Combine both lists into a single work list. If the combined count exceeds 5 (same threshold as `wikicommit-generate`'s and `wikicommit-collect`'s no-argument guard), do not start processing yet — show the count and the list of pairs, then ask the user to choose: **(a)** process all of them in this run, or **(b)** process only the first 5 (sorted ascending by the `page:` path from the script output) and leave the rest for a later run. If the count is 5 or fewer, proceed with all of them without asking.
4. For each `(source page, target language)` pair, run the per-page translation procedure in Step 4 (for a `STALE` pair this regenerates the existing translation page in place; for an `UNTRANSLATED` pair this creates a new one).

After all pairs are processed, run the "index.md Update" step below, then show the guidance in "After Completion".

### Step 4: Per-Page Translation Procedure

Given a `(source page, target language)` pair:

1. Read the source page in full (frontmatter + body).
2. Read all pages under `.wikicommit/entity/<source page's lang>/DefinedTerm/` (excluding `index.md`) as a glossary for terminology consistency, if that directory exists.
3. **Translator Notes** (Issue #524): if a translation page already exists at `.wikicommit/entity/<target language>/<Type>/<slug>.md` (same `Type`/`slug` as the source page) and its frontmatter has a non-empty `translator_notes` list, read it. This full re-translation is otherwise completely blind to the existing translation (it never reads the current translation page's frontmatter or body at all) — `translator_notes` is the one exception: it exists specifically so a translation-only fix made via `/wikicommit-fix` (mistranslation, terminology inconsistency, unnatural phrasing the original page doesn't need, since the original is correct as-is) survives being silently overwritten the next time the source page changes and triggers this full re-translation (`docs/DesignDoc-data.md` §4.2). If no translation page exists yet, or it exists but has no `translator_notes` field (or an empty one), skip this step — proceed exactly as before (Issue #524 makes no behavioral change for pages that don't use this field, including every translation page that existed before this Issue).
4. Have the LLM produce a translation:
   - `title`, and the body, translated into the target language.
   - `lang`: the target language.
   - `type`: unchanged (Schema.org type is language-neutral).
   - `tags`: each tag translated into the target language.
   - `properties:` (Issue #495 — the type-specific Schema.org properties block; never drop it or flatten it back to the top level): keep the same set of keys, nested exactly as in the source page. Within it, translate prose values the same way the body is translated (e.g. `properties.description`), while WikiLink-valued properties (e.g. `properties.affiliation: "[[Organization/companya]]"`) and other identifier-shaped values are copied unchanged — slugs and identifiers are language-neutral, only surrounding prose is translated. This copy-unchanged rule always wins over anything a `translator_notes` entry says (below) — a note that appears to target an identifier/WikiLink value (e.g. flagging a wrong `properties.affiliation` slug) is describing a problem with the source page's own data, not a translation choice, and should be fixed on the source page instead; it has no defined effect here.
   - Identifier fields at the top level (`wikidata`, `sameAs`) are copied unchanged — same reasoning as WikiLink-valued properties above.
   - `sources`: omit (translation pages inherit source provenance from the parent via `translated_from`, per `docs/DesignDoc-data.md` §4.2).
   - `translated_from`: the source page's path.
   - `source_commit`: first run `git status --porcelain -- <source page path>` to check the source page's working tree state. If it prints anything (the source page has uncommitted local changes — modified, staged, or untracked), the body you read in step 1 already reflects that uncommitted content, but `git log` can only see the last commit, which predates it. Writing that stale hash would make `source_commit` point to a commit whose content does not match what was actually translated. To avoid recording a hash that doesn't correspond to the translated content, use the empty string in this case too. Otherwise (clean working tree for that path), use the output of `git log -1 --format=%H -- <source page path>`; if that is also empty (the source page has no commits yet — e.g. it was just generated and not yet merged), use the empty string as-is. In all empty-string cases, `check_translation_status.py` will correctly flag this as `STALE` until the source page is committed with no further local edits, which is expected.
   - `translated_at`: today's date (`YYYY-MM-DD`).
   - `translated_by`: set to the **currently running model ID** (e.g., `claude-sonnet-4-6`) — use the actual model ID in use, not a hardcoded value (same self-identification pattern `wikicommit-generate` Pass 3 uses for `generated_by`; Issue #453 — translation pages previously had no field recording which model translated them, so `WikiCommitBanner.tsx`'s reviewer-facing model attribution was silently missing for every translated page).
   - `review_status: pending` (unconditionally, regardless of the source page's own `review_status` — same rule as the Phase 4 pipeline).
   - **Bare URLs in body text**: if the source page's body contains a bare URL (not already in Markdown link syntax `[text](url)`), keep its boundary explicit in the translated body — a space on both sides, or angle brackets (`<https://example.com>`). This is especially relevant when translating into Japanese, where a URL is often immediately followed by punctuation or a particle (e.g. `で公開されている`) with no space; a Markdown parser can then swallow the following characters into the URL itself, producing a broken/percent-encoded link that `lychee` reports as unreachable and `markdownlint-cli2` flags as MD034. When the translated URL is immediately followed by non-space text, prefer the angle-bracket form.
   - **Translator Notes carry-forward** (Issue #524): if step 3 read a non-empty `translator_notes` list, apply each entry's guidance to whatever prose/terminology choice it addresses (e.g. an entry pinning a specific translation for a term overrides the LLM's own default choice for that term — subject to the `properties:` precedence rule above), and set the new page's `translator_notes` field to the same list, unchanged (copy the entries forward verbatim; do not drop, reword, or deduplicate them — this field is otherwise never touched by this per-page procedure, so simply carrying its value through is sufficient). Without this copy step the notes would be silently dropped from this run's output — the same loss-on-re-translation problem this feature exists to prevent, just one step later. If step 3 found no `translator_notes` (or it doesn't exist yet), omit the field from the new page exactly as this procedure already does for a first-time translation.
5. **Quality check**: have the LLM re-read the generated translation against the source page and the glossary from step 2, checking for semantic drift and inconsistent terminology. If it finds a problem, regenerate once; if the second attempt still has a problem, write the file anyway but tell the user what to double-check.
6. Write the translation to `.wikicommit/entity/<target language>/<Type>/<slug>.md` (same `Type`/`slug` as the source page), creating parent directories as needed. This is a local write only — do not `git add` or commit.
7. `index.md` is rebuilt once for all affected directories after all pairs are processed (see below) — no per-page action needed here.

### index.md Update (once, after all pairs)

After all `(source page, target language)` pairs for this run have been processed (i.e. after Step 2 finishes all targets, or Step 3 finishes all pairs), run:

```bash
python .wikicommit/scripts/rebuild_index.py
```

This deterministically rebuilds `index.md` for every Type directory under `.wikicommit/entity/` from the pages currently on disk (Issue #406 — the same script `wikicommit-generate` uses, replacing this Skill's previous per-directory LLM-driven update, Issue #338). It scans each directory itself, so there is no need to track which `<target language>/<Type>/` directories this run touched, and it correctly rebuilds `index.md` if one already exists from a prior `wikicommit-generate` run on the same language. `status: removed` pages are excluded automatically, and the frontmatter uses the bare Type name for `title` (Issue #320). This is a local write only — **do not commit**.

### After Completion

```
Next steps:
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
  (translated pages are written with review_status: pending, same as wikicommit-generate output)
```

## Notes

- Do not commit or create a PR against `main` or any branch (that is `wikicommit-merge`'s responsibility)
- Do not write to `.wikicommit/schema/` (read-only)
- No Git operations of any kind — this Skill only reads the working tree (including via `git log` for `source_commit`) and writes new/updated files under `.wikicommit/entity/`
