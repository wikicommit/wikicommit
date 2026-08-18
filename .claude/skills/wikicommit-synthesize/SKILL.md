---
name: wikicommit-synthesize
description: Synthesize a new wiki page about a topic from existing wiki content, written directly to .wikicommit/entity/
disable-model-invocation: true
---

# wikicommit-synthesize

Synthesizes a new wiki page about a given concept or term from the content of `.wikicommit/entity/` itself — the counterpart to `/wikicommit-generate` (which creates pages from external sources): `generate` starts from a source document, `synthesize` starts from existing wiki pages. Gathering related pages uses the same cross-lingual search logic as `wikicommit-ask` (p3-007). Unlike the `wikicommit-document` Skill this replaces (Issue #283), the result is written directly to `.wikicommit/entity/<lang>/<Type>/<slug>.md` as primary content — subject to the quality gate and mergeable via `/wikicommit-merge` — rather than to the separate, non-authoritative `.wikicommit/exports/` location. This Skill has no dedicated scripts of its own (it only calls `search_index.py` multiple times).

`disable-model-invocation: true` is set because, unlike the read-only `wikicommit-ask`/`wikicommit-quiz` it's derived from, this Skill writes new files under `.wikicommit/entity/` — the same side-effect class as `wikicommit-generate`/`wikicommit-review` (see CONTRIBUTING.md's SKILL.md guidance).

## Usage

```
/wikicommit-synthesize <topic>
```

## Processing Flow

### Step 1: Determine Target Languages

Read `.wikicommit/config.yml` and get `translation.primary_lang` and `translation.targets`. If `.wikicommit/config.yml` doesn't exist, display an error, guide the user to run `/wikicommit-init`, and stop.

Have the LLM determine the language of `<topic>`.

Build the list of languages to search, in the following order, **deduplicating any repeated language** (to avoid searching the same language twice):

1. The language of `<topic>`
2. `primary_lang`
3. Each language in `targets`

### Step 2: Cross-Lingual Search

For each language determined in step 1, **run sequentially, one language at a time** (do not run in parallel — `search_index.py query` automatically runs `build` (`DROP` + full rebuild) when the cache hasn't been generated yet, so calling it for multiple languages in parallel can race on that "cache not yet built" check, causing a double build or a SQLite lock-contention error):

1. Translate `<topic>` (or its key keywords) into that language (the LLM translates on the fly each time — no dedicated translation API or library is used). If the target language matches `<topic>`'s language, skip translation and use it as-is.
2. Run:

```bash
python .wikicommit/scripts/search_index.py query "$(cat <<'EOF'
<translated query>
EOF
)" --lang <lang> --limit 5
```

Pass the query through a quote-delimited heredoc (`docs/DesignDoc-skills.md` §11.7), not a plain double-quote embedding. `<translated query>` is LLM-produced but derives from `<topic>`, which is unvalidated free-form user text — a plain `"<translated query>"` embedding would let shell metacharacters (`` ` ``, `$(...)`) surviving translation be evaluated by the shell when this command line is assembled, regardless of the downstream script being local and read-only (Issue #398).

On exit code `1` (failure, with an `ERROR:` line printed), display that error message as-is to the user and stop.

Collect the `MATCH:` lines (`path` / `title` / `type` / `lang` / `review_status`) and the `SUMMARY:` line (`hits`) from each language's query results.

### Step 3: Merge Results

1. Combine the hits from all languages into a single list.
2. If multiple language versions of the same page (linked via `translated_from`) both show up as hits (i.e. two or more hits share the same `type` and `slug`), narrow it down to one. Priority order: "same language as `<topic>`" > "`primary_lang`" > "the order listed in `targets`".
3. Sort the remaining hits roughly by the bm25 order returned by `search_index.py` (already ranked per-language) and select the top 5–10. A naive cross-language score comparison is acceptable as an approximation.
4. If there are zero hits across all languages combined, display "No pages related to \"<topic>\" were found" and stop (do not run the remaining steps).

### Step 4: Fetch Page Content

Read each selected page with the Read tool and add its body (excluding frontmatter) to the LLM's context. Keep the list of selected page paths — this is the grounding set used for `derived_from` in Step 10.

### Step 5: Generate the Summary

Generate a summary document about `<topic>`, grounded only in the body content injected in step 4. **Do not include claims in the document that aren't in a grounding page's body content** (hallucination prevention). No source-reconciliation subagent (`wikicommit-generate` Pass 4's equivalent) is used here — this single instruction is the only hallucination safeguard, by design (Issue #283 scope).

Structure the document with sections, and include reference links to related pages (in `[[Type/slug]]` form) within the body. Put `<topic>` as a heading at the top of the document. Do not append a "Referenced Pages" list to the body — the grounding set is instead recorded in the `derived_from` frontmatter field (Step 10), so listing it again in the body would be redundant.

### Step 6: Determine the New Page's Type

Unlike the grounding pages (which may span several types — e.g. a `Person` and an `Organization` page both about the same topic), the synthesized page itself needs exactly one `type`. Follow the same type-selection flow as `wikicommit-generate` (`docs/DesignDoc-data.md` §5.4):

1. Have the LLM pick the best-fitting type for `<topic>` given the generated content, checking `.wikicommit/schema/custom/` first, then the standard `.wikicommit/schema/` types.
2. If no schema file matches, fall back to `.wikicommit/schema/default.md`.
3. If the LLM cannot confidently pick a single type, ask the user to confirm instead of guessing silently (same spirit as `wikicommit-generate`'s `ambiguous: true` handling, but resolved interactively here rather than deferred to a review queue, since this Skill runs conversationally).

### Step 7: Determine the New Page's Language

Set `lang` to `.wikicommit/config.yml`'s `primary_lang` (read in Step 1) — regardless of which language(s) were searched in Step 2. This mirrors `wikicommit-generate` Pass 2's rule: the topic may be looked up in multiple languages, but a newly created page's own language is always the wiki's source language.

### Step 8: Generate the topic-slug

Generate a language-neutral English slug from `<topic>` (same convention as WikiLink filenames: a lowercase, hyphen-separated English identifier). For a non-English `<topic>` (e.g. Japanese), have the LLM translate it to English first, then slugify it. Example: "機械学習パイプライン" → `machine-learning-pipeline`.

### Step 9: Safety Check Before Writing

The target path is `.wikicommit/entity/<lang>/<Type>/<slug>.md` (from Steps 6–8) — this is primary wiki content, not a disposable export, so an accidental overwrite here is more costly than the old `exports/` location's was. If the file already exists:

1. Read its frontmatter.
2. If it has a `derived_from` field (i.e. it's the output of a previous `/wikicommit-synthesize` run) → confirm with the user whether it's okay to overwrite, same as before. If declined, stop.
3. If it does **not** have `derived_from` (i.e. it's primary content from `/wikicommit-generate` or a human-authored page) → **stop with an error** instead of asking to overwrite. Tell the user this page already exists as primary content and suggest either choosing a different topic/slug or editing that existing page directly instead of synthesizing over it.

If the file doesn't exist, proceed directly — create the parent `.wikicommit/entity/<lang>/<Type>/` directory automatically if needed.

### Step 10: Write the File

Write frontmatter with:

- `title`: `<topic>` (or its English-translated form used for the slug, whichever reads better as a title in `lang`)
- `type`: from Step 6
- `lang`: from Step 7
- `review_status: pending` (unconditionally — same rule as `wikicommit-generate`/`wikicommit-translate` output)
- `generated_at`: today's date (`YYYY-MM-DD`)
- `generated_by`: the LLM model identifier
- `derived_from`: one entry per grounding page from Step 4, in the form:

  ```yaml
  derived_from:
    - path: .wikicommit/entity/ja/Person/yamada-taro.md
      source_commit: abc123def456abc123def456abc123def456abc123de
    - path: .wikicommit/entity/ja/Organization/companya.md
      source_commit: def456abc123def456abc123def456abc123def456ab
  ```

  Get each `source_commit` with `git log -1 --format=%H -- <path>`. If a grounding page has no commit history yet (newly generated, not yet committed), this command succeeds with empty output — write `source_commit` as an empty string in that case (`check_derivation_freshness.py` will correctly report it as `STALE` until the page is committed, which is expected, same as the equivalent `wikicommit-translate` behavior).

Do **not** write a `sources` field — `derived_from` is this page's provenance record, the same way `translated_from` is for translation pages (`docs/DesignDoc-data.md` §4.2). `validate_frontmatter.py` exempts pages with `derived_from` from the `sources` requirement accordingly.

Write the frontmatter + body (from Step 5) to `.wikicommit/entity/<lang>/<Type>/<slug>.md` with the Write tool.

### Step 11: Guidance

Once the write is complete, tell the user:

```
Written to .wikicommit/entity/<lang>/<Type>/<slug>.md.
This is primary wiki content: it is subject to the quality gate and can be committed via /wikicommit-merge like any other page (review_status: pending, so it will get a post-review PR after merge).
```

## Notes

- Do not commit or create a PR against `main` or any branch (that is `wikicommit-merge`'s responsibility)
- Do not write to `.wikicommit/schema/` (read-only)
- Do not include claims in the document that aren't in a grounding page's body content (hallucination prevention; see Step 5)
- This Skill's only side effect is writing one new file under `.wikicommit/entity/`. `search_index.py` automatically runs `build` if the index file (`.wikicommit/.cache/search_index.sqlite3`, not tracked by Git) doesn't exist
- This Skill does not update the affected `<Type>/index.md` the way `wikicommit-generate` does — the synthesized page will not appear in the type index until a later `wikicommit-generate` run or manual edit regenerates it. Out of scope for Issue #283
- Whether a grounding page's own `review_status: pending` should be surfaced as a warning here (the way `wikicommit-ask` shows "⚠️ This answer references unreviewed pages") is intentionally left unresolved (Issue #283 scope)
