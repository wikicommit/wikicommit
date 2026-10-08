---
pass_token: "fb06bb64"
---

# Step 4: translate one pair (`translate`)

The workflow engine hands you one `(source page, target language)` pair as `item`, written `<source page> -> <target language>`. Translate it, have it reviewed, record the verdict, and write it — then report one outcome:

- `translated` — the translation passed and was written. The workflow engine's check then confirms, on disk, that `.wikicommit/entity/<target language>/<Type>/<slug>.md` (for a view page, `.wikicommit/view/<target language>/<slug>.md`) exists with `translated_from` naming the source page, `lang` set to the target language, `source_commit` written exactly as item 4 below says, `translated_by` / `translated_at` written and `review_status: pending`, and that a `translate-check` record with `result: pass` was written for it in this run.
- `discarded` — still failing after `generate.max_retries`; nothing was written for this pair. The check confirms a `translate-check` record with `result: discarded` from this run.
- `halted` with `--reason "rules_version mismatch"` — the review could not be run as specified (item 5.2). The run stops.

```bash
python .wikicommit/scripts/skill_workflow.py done <run> --step translate --item "<the item>" \
    --outcome <translated|discarded|halted> --token <the pass_token above> [--reason "<why>"]
```

Read `generate.max_retries` (default: 2) from `.wikicommit/config.yml` if it is not already in front of you. A resumed run re-derives everything here from the item and the files on disk; nothing has to be remembered from an earlier pair.

The per-pair procedure is the same whether the run is in single-page or batch mode. In single-page mode the translation is regenerated unconditionally — whether or not a translation already exists for this target, always produce the full translation from the current source content (a full re-translation every time, new or existing). In batch mode, a `STALE` pair regenerates the existing translation page in place and an `UNTRANSLATED` pair creates a new one.

Given a `(source page, target language)` pair:

1. Read the source page in full (frontmatter + body).
2. **Glossary** — build two distinct things, in this order:

   a. **Term definitions.** Read all pages under `.wikicommit/entity/<source page's lang>/DefinedTerm/` (excluding `index.md`) as a glossary for terminology consistency, if that directory exists. These tell you what each term *means* in the source language.

   b. **Source→target term table**. Definitions alone do not say how a term is *rendered* in the target language, so on their own they leave every page free to re-derive its own wording for the same term. Collect the `title` of each already-translated `DefinedTerm` page in the target language and pair it with the same-slug source page's `title` — the filename is the slug, and slugs are language-neutral, so the basename is the join key. Read only the `title` line, never the whole page:

      ```bash
      grep -m1 -H '^title:' .wikicommit/entity/<target language>/DefinedTerm/*.md 2>/dev/null \
        | grep -v '/index\.md:' | grep -v '/<slug>\.md:'
      ```

      `<slug>` is the slug of the page being translated. That last filter matters only when the page being translated is itself a `DefinedTerm` page: in that case the glob also matches this pair's *own* target-language page, and for a `STALE` pair that page still holds the previous translation of the very term this run is about to re-decide. Feeding it back in would both break the blindness this procedure states in step 3 and, via the step 5 rule below, pin the term to its old wording forever — a corrected source `title` could never reach the target language. For any other type the filter is a harmless no-op (drop it if you prefer).

      Reading these pages in full instead would cost pages × terms of context for information the table does not need. If the directory or the glob matches nothing, the table is simply empty and this step contributes nothing — that is the expected state for the first target-language page of a wiki, and for the first `DefinedTerm` page of a batch run. The command is re-run for each pair rather than once per run, so within a batch run (which processes `DefinedTerm` pairs first — the `collect` step orders them that way) the table grows as the glossary is settled and later pairs see it.

      When translating a `DefinedTerm` page itself, the table therefore covers the sibling terms already translated but not the page's own term (which this run is about to decide) — use it for cross-references in the body, exactly as any other page would.
3. **Translator Notes**: if a translation page already exists at `.wikicommit/entity/<target language>/<Type>/<slug>.md` (same `Type`/`slug` as the source page; for a view page, `.wikicommit/view/<target language>/<slug>.md`) and its frontmatter has a non-empty `translator_notes` list, read it. This full re-translation is otherwise completely blind to the existing translation (it never reads the current translation page's frontmatter or body at all) — `translator_notes` is the one exception: it exists specifically so a translation-only fix made via `/wikicommit-fix` (mistranslation, terminology inconsistency, unnatural phrasing the original page doesn't need, since the original is correct as-is) survives being silently overwritten the next time the source page changes and triggers this full re-translation. If no translation page exists yet, or it exists but has no `translator_notes` field (or an empty one), skip this step and proceed as usual.
4. Have the LLM produce a translation:
   - `title`, and the body, translated into the target language.
   - `lang`: the target language.
   - `type`: unchanged (Schema.org type is language-neutral).
   - `tags`: each tag translated into the target language.
   - **The source's own wording, from the source page's `aliases`**: the source page is written in `primary_lang`, and when an original source wrote this entity's name or term in another language, generation keeps that exact wording as an alias of the source page. If one of those aliases is written **in the target language**, use it as this page's `title` and wherever the body names that entity or term, instead of translating the `primary_lang` wording back — a back-translation does not recover the source's spelling (`Testing Skyscraper` becomes `テスティング・スカイスクレイパー` where the source wrote `テストスカイスクレイパー`). Decide an alias's language from the string itself; **if you are not confident it is in the target language** (a string of kanji alone can be Japanese or Chinese), do not use it, and fall back to the glossary table and then to your own translation. Precedence for a term: a `translator_notes` entry (a person's decision about this page) > an alias in the target language > the step 2b glossary table > your own translation.
   - `aliases`: **do not copy the source page's `aliases`** onto the translation. On the published wiki every alias becomes a redirect URL at the site root, so the same alias on both pages makes them claim the same URL; and the one alias that matters here is already this page's `title` and body wording above, where search finds it. Omit the field.
   - `properties:` (the type-specific Schema.org properties block; never drop it or flatten it back to the top level): keep the same set of keys, nested exactly as in the source page. Within it, translate prose values the same way the body is translated (e.g. `properties.description`), while WikiLink-valued properties (e.g. `properties.affiliation: "[[Organization/companya]]"`) and other identifier-shaped values are copied unchanged — slugs and identifiers are language-neutral, only surrounding prose is translated. This copy-unchanged rule always wins over anything a `translator_notes` entry says (below) — a note that appears to target an identifier/WikiLink value (e.g. flagging a wrong `properties.affiliation` slug) is describing a problem with the source page's own data, not a translation choice, and should be fixed on the source page instead; it has no defined effect here.
   - Identifier fields at the top level (`wikidata`, `sameAs`) are copied unchanged — same reasoning as WikiLink-valued properties above.
   - `sources`: omit (translation pages inherit source provenance from the parent via `translated_from`).
   - `translated_from`: the source page's path.
   - `source_commit`: first run `git status --porcelain -- <source page path>` to check the source page's working tree state. If it prints anything (the source page has uncommitted local changes — modified, staged, or untracked), the body you read in step 1 already reflects that uncommitted content, but `git log` can only see the last commit, which predates it. Writing that stale hash would make `source_commit` point to a commit whose content does not match what was actually translated. To avoid recording a hash that doesn't correspond to the translated content, use the empty string in this case too. Otherwise (clean working tree for that path), use the output of `git log -1 --format=%H -- <source page path>`; if that is also empty (the source page has no commits yet — e.g. it was just generated and not yet merged), use the empty string as-is. In all empty-string cases, `check_translation_status.py` will correctly flag this as `STALE` until the source page is committed with no further local edits, which is expected.
   - `translated_at`: today's date (`YYYY-MM-DD`).
   - `translated_by`: set to the **currently running model ID** (e.g., `claude-sonnet-4-6`) — use the actual model ID in use, not a hardcoded value, written exactly as the runtime reports it (keep any suffix such as `[1m]`; do not shorten or normalize it) (same self-identification pattern `wikicommit-generate` Pass 3 uses for `generated_by`; the published banner shows it as the translating model).
   - `translated_with`: WikiCommit's own version, not a model ID — read it once per run with `python .wikicommit/scripts/_version.py` and write that exact string on every page this run produces (the translation-page counterpart of the `generated_with` `wikicommit-generate` Pass 3 writes). It is what lets a human — reading `CHANGELOG.md` alongside a `grep` for this field — tell which pages were produced under an older set of rules. If that script is missing (a wiki repository initialized before this field existed), omit the field entirely rather than guessing a version — its absence is meaningful, and no back-fill is performed.
   - `review_status: pending` (unconditionally, regardless of the source page's own `review_status` — same rule as the Phase 4 pipeline).
   - **Bare URLs in body text**: if the source page's body contains a bare URL (not already in Markdown link syntax `[text](url)`), keep its boundary explicit in the translated body — a space on both sides, or angle brackets (`<https://example.com>`). This is especially relevant when translating into Japanese, where a URL is often immediately followed by punctuation or a particle (e.g. `で公開されている`) with no space; a Markdown parser can then swallow the following characters into the URL itself, producing a broken/percent-encoded link that `lychee` reports as unreachable and `markdownlint-cli2` flags as MD034. When the translated URL is immediately followed by non-space text, prefer the angle-bracket form.
   - **Translator Notes carry-forward**: if step 3 read a non-empty `translator_notes` list, apply each entry's guidance to whatever prose/terminology choice it addresses (e.g. an entry pinning a specific translation for a term overrides the LLM's own default choice for that term — subject to the `properties:` precedence rule above), and set the new page's `translator_notes` field to the same list, unchanged (copy the entries forward verbatim; do not drop, reword, or deduplicate them — this field is otherwise never touched by this per-page procedure, so simply carrying its value through is sufficient). Without this copy step the notes would be silently dropped from this run's output — the same loss-on-re-translation problem this feature exists to prevent, just one step later. If step 3 found no `translator_notes` (or it doesn't exist yet), omit the field from the new page exactly as this procedure already does for a first-time translation.
5. **Quality check — a review subagent compares the translation with the source page.** It is not you re-reading your own translation: you read it the way you meant it, which is exactly where a drift hides. The discipline — what counts as an addition, a drift, an omission, a broken identifier or a terminology mismatch, and the three limits on the step 2b table — is in `.wikicommit/review-rules.md` under `translate-check`, shared with the other review paths. What stays here is the choreography.

   1. Launch a subagent and give it exactly these things, and nothing else:
      1. **The path label `translate-check`**, stated as the path this review is running on.
      2. **The translation from step 4** (frontmatter and body). It is not written yet.
      3. **The source page from step 1, in full**, in the only block marked `SOURCE`. Not the source page's own sources: an error the source page already carries is the source page's review's job, and handing its sources over would blame the translation for it.
      4. **The step 2b term table and the step 3 `translator_notes`**, in a block marked as reference material, not `SOURCE` — they say how to write a term, never what is true.
      5. **`.wikicommit/review-rules.md`**, with an instruction to follow it.

      Do not include anything else — not the step 2a definitions, not your reasons for a wording, not a previous round's findings.
   2. **Check that the returned JSON carries `rules_version` matching `.wikicommit/review-rules.md`'s frontmatter.** A missing or mismatched value means the subagent did not read the rules. Relaunch **once**; if the second attempt is also missing or wrong, **stop the whole run and report it** — report `halted` with `--reason "rules_version mismatch"`, which closes the run record as halted — without writing this page, without consuming `generate.max_retries`, and without recording a review. This is a problem with the instructions or the environment, not with the translation.
   3. On **FAIL**, regenerate the translation (step 4) with the full `issues` array — above all each entry's `instruction` — in the prompt as itemized corrections. Up to `generate.max_retries` times.
   4. **If the retry limit is exceeded, write nothing for this pair** and go on to the next. For a new pair the target stays `UNTRANSLATED`; for a stale one the old translation stays on disk and stays `STALE`, which is the state it was in before this run. Record the verdict (item 5) with `--result discarded` and report `discarded`. The completion report reads the last `issues` back from that record, so nothing needs to be carried in memory.
   5. **Record the verdict either way** — after step 6 has written the page when it passed, immediately when it was discarded:

      ```bash
      python .wikicommit/scripts/record_review.py "$(cat <<'EOF'
      <the translation page path, .wikicommit/entity/<target language>/<Type>/<slug>.md (view: .wikicommit/view/<target language>/<slug>.md)>
      EOF
      )" --kind ai --stage translate-check \
        --model "<the model ID this run's runtime reports for itself>" \
        --skill-blob "$(git hash-object .wikicommit/review-rules.md)" \
        --attempts <how many review rounds this took> --result <pass|discarded> --json - <<'JSON'
      <the review subagent's JSON, with every round's issues merged into one `issues`
       array and each entry carrying the `round` it was raised in>
      JSON
      ```

      On a pass the script records which version of the source page was checked (`translated_from` and `source_commit`); on a discard it records none, because the page on disk is the old translation. If the subagent returned an `observations` array, write it to a file under the gitignored `.wikicommit/.cache/` with a quoted heredoc and pass `--note-file` (never `--note` — it is free text a subagent wrote). Keep that file out of `.wikicommit/review/`, which `/wikicommit-merge` stages whole.
6. Only when item 5 passed: write the translation to `.wikicommit/entity/<target language>/<Type>/<slug>.md` (same `Type`/`slug` as the source page; for a view page, `.wikicommit/view/<target language>/<slug>.md`), creating parent directories as needed. This is a local write only — do not `git add` or commit.
7. `index.md` is rebuilt once, after all pairs, by the workflow engine's `rebuild-index` step (`rebuild_index.py`) — no per-page action needed here.
