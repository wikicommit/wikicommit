---
name: wikicommit-ask
description: Answer a question using wiki content as grounding, with cross-lingual search across configured languages
---

# wikicommit-ask

A RAG-style skill that answers questions grounded in the content of `.wikicommit/entity/`. Search is delegated to the shared script `.wikicommit/scripts/search_index.py` (p3-005), and this skill implements `CLAUDE.md`'s cross-lingual search policy (agent-driven query translation: search multiple times, once in the original language and once per language configured in `config.yml`). Besides calling `search_index.py` multiple times, this skill has one dedicated script of its own, `scripts/resolve_source_cache_path.py` (Issue #470), used only by the opt-in `--include-source` path in Step 4.3.

## Usage

```
/wikicommit-ask <question> [--include-source]
```

- `<question>`: the question to answer
- `--include-source` (optional; Issue #470): also read each grounding page's underlying primary source document(s) — the `sources` it cites — and include their raw content as additional grounding, on top of the page's own body content. **Off by default — omitting this flag leaves every other step in this skill completely unchanged.** Useful when a page's `type` schema summarizes or omits detail the primary source actually contains (e.g. a `DefinedTerm`/`Person` page distilled from a novel, where the question asks about detail only present in the original text, not in the wiki page's own body).

## Processing Flow

### Step 1: Determine Target Languages

Read `.wikicommit/config.yml` and get `translation.primary_lang` and `translation.targets`. If `.wikicommit/config.yml` doesn't exist, display an error, guide the user to run `/wikicommit-init`, and stop.

Have the LLM determine the language of the question.

Build the list of languages to search, in the following order, **deduplicating any repeated language** (to avoid searching the same language twice):

1. The language of the question
2. `primary_lang`
3. Each language in `targets`

Example: if the question is in `ja`, `primary_lang: ja`, and `targets: [en, zh]` → `[ja, en, zh]` (the question's language and `primary_lang` are merged since they're the same). If `targets` is an empty array (translation disabled) → only the question's language and `primary_lang` (or just one language if they're the same).

### Step 2: Cross-Lingual Search

For each language determined in step 1:

1. Extract the key search keywords from the question — never pass the full natural-language question text to `search_index.py`, even when no translation is needed. `search_index.py`'s `query_index()` splits the query on whitespace (`query.split()`) and ANDs each resulting term as a phrase query (`docs/DesignDoc-ScriptSpec.md`). For languages that don't use whitespace as a word boundary (e.g. `ja`, `zh`), a full sentence contains no whitespace at all, so `query.split()` returns the entire sentence as a single verbatim phrase query — which will structurally never match page body text, producing 0 hits regardless of whether the wiki actually covers the topic (Issue #356).
   - If the target language matches the question's language, use the extracted keywords as-is (space-separated) — do not fall back to the raw question text.
   - Otherwise, translate each extracted keyword individually into the target language (the LLM translates on the fly each time — no dedicated translation API or library is used), then join the translated keywords with spaces. Do not translate the question as one full sentence and pass that.
2. Run:

```bash
python .wikicommit/scripts/search_index.py query "$(cat <<'EOF'
<translated query>
EOF
)" --lang <lang> --limit 5
```

Pass the query through a quote-delimited heredoc (`docs/DesignDoc-skills.md` §11.7), not a plain double-quote embedding. `<translated query>` is LLM-produced but derives from `<question>`, which is unvalidated free-form user text (and, when this skill is invoked as part of `wikicommit-fix`, may itself indirectly reflect a third party's external Issue text) — a plain `"<translated query>"` embedding would let shell metacharacters (`` ` ``, `$(...)`) surviving translation be evaluated by the shell when this command line is assembled, regardless of the downstream script being local and read-only (Issue #398).

On exit code `1` (failure, with an `ERROR:` line printed), display that error message as-is to the user and stop.

Collect the `MATCH:` lines (`path` / `title` / `type` / `lang` / `review_status`), the `SUMMARY:` line (`hits`), and any `WARNING: query term "<term>" has <N> character(s); ...` lines from each language's query results. The `WARNING:` lines mean `search_index.py` found a translated query term too short for the trigram tokenizer to ever match (Issue #274) — keep them (with which language they came from) for use in step 3.4.

### Step 3: Merge Results

1. Combine the hits from all languages into a single list.
2. If multiple language versions of the same page (linked via `translated_from`) both show up as hits (i.e. two or more hits share the same `type` and `slug`), narrow it down to one. Priority order: "same language as the question" > "`primary_lang`" > "the order listed in `targets`"; exclude all others (including cases where three or more languages hit simultaneously).
3. Sort the remaining hits roughly by the bm25 order returned by `search_index.py` (already ranked per-language) and select the top 5–10. A naive cross-language score comparison is acceptable as an approximation (corpus size and trigram distribution differ per language, making a strict comparison impossible. Phase 3 accepts this rough approximation; a strict ranking is left as a future-phase reconsideration).
4. If there are zero hits across all languages combined, skip steps 4–6 and answer "No relevant knowledge was found" and stop. If any language's query in step 2 produced a `WARNING:` (short term) line, append a supplementary note to that answer, same wording and reasoning as `wikicommit-search`'s Step 3 (`docs/DesignDoc-skills.md` §11.5 — this skill delegates the same short-term detection to `search_index.py` rather than re-implementing it): a term this short can never match via trigram search regardless of translation, so it's worth telling the user their query (or its translation) may be too short rather than letting "no relevant knowledge was found" look like a gap in the wiki's content.

### Step 4: Fetch Page Content

1. Read each page selected in Step 3 with the Read tool and add its body (excluding frontmatter) to the LLM's context.

2. **WikiLink hop expansion (Issue #459)**: a flat keyword hit misses relevant content that a selected page only reaches via `[[Type/slug]]` — e.g. a hit page's body says "affiliated with `[[Organization/companya]]`" without repeating that organization's own detail, which the question may actually be asking about. Extend the grounding set by one hop:

   1. From each page selected in Step 3 (not from any page added by this step — see the depth cap below), extract every `[[Type/slug]]` occurrence in its body using the same pattern `.wikicommit/scripts/_wikilink.py`'s `WIKILINK_RE` implements: `\[\[([A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z0-9_]+)*)/([A-Za-z0-9_-]+)\]\]` (capture group 1 is `Type`, possibly containing `/` for nested custom types; group 2 is `slug`).
   2. Resolve each `(Type, slug)` pair to a file using the same priority order `.wikicommit/scripts/check_wikilinks.py` uses: try `.wikicommit/entity/<lang>/<Type>/<slug>.md` first, where `<lang>` is the *referencing* page's own `lang` (from its frontmatter, not necessarily the question's language); if that doesn't exist and `<lang>` differs from `primary_lang` (Step 1), try `.wikicommit/entity/<primary_lang>/<Type>/<slug>.md`. If neither resolves, skip that WikiLink — same non-blocking treatment `check_wikilinks.py` gives an unresolved link (a WARNING, not an ERROR); an unresolved link here just means nothing to add, not a failure.
   3. Drop any resolved candidate that: is already one of the Step 3 hits (avoid re-adding/duplicating), or has `status: removed` in its frontmatter (a removed page should never ground an answer).
   4. Depth is **one hop only** — do not extract WikiLinks from pages added by this step itself. (Whether a second hop is worth the added cost is deferred to a follow-up once real usage shows how much the first hop helps.)
   5. Cap the candidates: **at most 2–3 per Step-3 hit page**, and **at most ~5 additional pages in total** across every hit combined. If more candidates resolve than the cap allows, keep only the ones judged most relevant in the next step.
   6. This is an agent-native Skill (`docs/DesignDoc-skills.md` §11.0) — do not mechanically read every resolved candidate. Have the LLM judge each resolved candidate's relevance to the question (title and, if needed, a quick skim of its body) and select only the ones that would actually help answer it; discard the rest. This keeps an incidental "affiliated with X" mention from pulling in X's entire unrelated page.
   7. Read the selected candidates with the Read tool and add their bodies (excluding frontmatter) to the LLM's context, the same as step 1 above.

3. **Raw source inclusion (opt-in `--include-source`, Issue #470)**: skip this entirely if `--include-source` was not given. Otherwise, for each page in the grounding set assembled so far (every Step 3 hit page, plus every page step 4.2 added via WikiLink hop expansion — treated identically here):

   1. Resolve the page's `sources` list. The Read tool call from step 1 above already returned this page's full file content including frontmatter — step 1 only says to inject the *body* into the LLM's context, it doesn't discard the frontmatter — so re-use that, no new Read call needed for this branch:
      - If the page has a non-empty `sources` field, use it directly.
      - If the page has no `sources` field but has `derived_from` (a synthesized page, `docs/DesignDoc-data.md` §4.2): skip this page entirely for raw-source purposes. `derived_from` entries point to other `.wikicommit/entity/` pages, not external primary sources, and those pages are already reachable through ordinary grounding (Step 3 hits, step 4.2 WikiLink expansion) — there is no "original source" concept for a synthesized page.
      - Otherwise, if the page has `translated_from` (a translation page, `docs/DesignDoc-data.md` §4.2): resolve the parent page at `translated_from` and use *its* `sources` instead — the same "read through to the parent" pattern `wikicommit-search`'s Step 2.5 uses (Issue #458). This does require a fresh Read call (the parent page wasn't read in step 1 — it isn't itself part of the grounding set). If the parent page is missing, skip this page for raw-source purposes.
   2. Track a running set of sources already included this turn, keyed by `sources[].path` or `sources[].url` (whichever applies) — two or more grounding pages can cite the same underlying document (e.g. both derived from the same interview article), and reading + injecting the same file twice only doubles the context cost the "Known limitation" paragraph below already flags for a single inclusion. Skip an entry already in this set (but still count its page toward the Step 6 attribution list below).
   3. For each not-yet-included entry in the resolved `sources` list:
      - `type: path` → Read the file at `sources[].path` (repo-root-relative) with the Read tool and add its full content to the LLM's context, labeled with which page it grounds (e.g. "Raw source for `.wikicommit/entity/ja/Person/character-a.md`: `raw/novel.txt`"). If the file no longer exists at that path, skip it silently — that drift is `validate_frontmatter.py`'s concern, not this skill's. The Read tool renders binary/non-plain-text formats (`.docx`/`.pptx`/`.xlsx`/`.epub`/scanned images — all valid `type: path` sources per `wikicommit-generate`'s extraction routing table, `docs/DesignDoc-skills.md` §11.6) as garbled or unusable text; `wikicommit-ask` does not invoke that routing table's dedicated extraction Skills here — treat non-plain-text `path` sources as a known limitation of `--include-source` in Phase 3, not something this step handles.
      - `type: url` / `type: wikicommit` → run:

        ```bash
        python .claude/skills/wikicommit-ask/scripts/resolve_source_cache_path.py <<'EOF'
        <sources[].url>
        EOF
        ```

        Pass the URL via a quote-delimited heredoc, not a plain argument — `sources[].url` is only format-validated (`validate_frontmatter.py` checks the `https://` prefix, nothing more), which doesn't meet the bar `docs/DesignDoc-skills.md` §11.7 sets for exempting a value from this rule. This script locates the *actual* ingest management file for the URL (by scanning `.wikicommit/source/url/` for a matching `source.url`, rather than recomputing a filename from the URL) and prints the matching `.wikicommit/.cache/ingest-fetch/` path — deliberately not `add_source.py`'s `url_to_filename()` recomputed fresh from the URL, which would silently miss any pre-Issue-#191 management file still using the old flat naming (`docs/DesignDoc-data.md` §4.3 documents these as never auto-migrated). On exit code `0`, Read the printed path and add its content to the LLM's context the same way as the `path` case above. On exit code `1` (no matching management file registered for this URL, or the cache file is missing — cache never populated, a different machine, or the cache was cleared), do **not** attempt a live re-fetch — `wikicommit-ask` has no side effects (see Notes) and adding a network call here would break that guarantee. Instead, record `sources[].url` as unavailable for the Step 6 fallback note. Note this script doesn't verify the cached content is still current with the source's live `source.hash` — a stale-but-present cache is used with the same confidence as a fresh one; that's a known limitation, not something this step checks.
      - `type: manual` → skip (no underlying file or URL to read; `sources[].author`/`created_at` is already visible wherever this page's `sources` list was resolved from in step 1 above — the page's own frontmatter, or the parent page's if resolved via `translated_from`).

   **Known limitations**: (1) a large raw source (e.g. a novel-length `.txt`/`.md` file) is read in full, with no chunking or excerpt selection — this can substantially inflate the LLM's context for a single grounding page; (2) non-plain-text `type: path` sources and cache-staleness for `type: url`/`wikicommit` sources, both noted above. `wikicommit-ask` does not attempt to mitigate any of these in Phase 3 — treat them as known limitations of `--include-source`, not bugs; a follow-up can revisit if any of these prove to matter in practice.

### Step 5: Generate the Answer

Answer **in the language of the question determined in Step 1** — do not re-detect or otherwise decide the answer's language independently; reuse the Step 1 determination as-is. Answer the question grounded only in the body content injected in step 4 — this includes the Step 3 hit pages, any pages step 4.2 added via WikiLink hop expansion, and (if `--include-source` was given) any raw source content step 4.3 added; all are grounding on equal footing. **Do not include claims in the answer that aren't in the grounding pages' body content** (hallucination prevention) — this applies equally to raw source content added by step 4.3. Note that a raw source can contain material `wikicommit-generate`'s Pass 2 deliberately chose not to promote into the wiki page (a `theme`-mismatched `action: exclude` entity, or detail a schema's granularity rules left out) — with `--include-source`, such material is fair game for grounding an answer even though the wiki page itself omits it; that's the feature's intent, not an oversight.

### Step 6: Prepend Notes

Before the answer body, insert zero or more of the following notes, each on its own line and in this fixed order (never reorder — "prepend" below means "insert here, above the answer body and above any note listed after it", not "insert at the very front regardless of the other notes' positions"):

1. If any page used as grounding — a Step 3 hit page or a page step 4.2 added via WikiLink hop expansion, treated identically here — has `review_status: pending`, prepend a note formatted like `wikicommit-search`'s `⚠️ Unreviewed` label:

   ```
   ⚠️ This answer references unreviewed pages: .wikicommit/entity/ja/Person/yamada-taro.md
   ```

   If there are multiple, list them comma-separated. Omit if all are `reviewed`.

2. If `--include-source` was given and step 4.3 added at least one page's raw source content, prepend a note naming which grounding page(s) it was added for (the same comma-separated attribution the note above uses, for the same reason — so a reader can tell which specific claims rest on an un-reviewed raw file versus the vetted wiki body) — this is a different concern from note 1 above (it isn't about `review_status`; it's that the content bypassed the Pass 3/4 generation and review pipeline entirely):

   ```
   ⚠️ This answer includes content read directly from the original source document(s) of the following page(s), which have not gone through the wiki page generation/review process: .wikicommit/entity/ja/Person/character-a.md
   ```

3. If `--include-source` was given but step 4.3 recorded at least one `type: url`/`wikicommit` source as unavailable (no cached fetch found), prepend a best-effort note naming the skipped source(s):

   ```
   ⚠️ Could not include the original source for the following URL(s) because no cached fetch was found: https://example.com/article
   ```

```
<note 1, if any>
<note 2, if any>
<note 3, if any>

<answer body>
```

## Notes

- Do not commit or create a PR against `main` or any branch
- Do not write to `.wikicommit/schema/`
- Do not include claims in the answer that aren't in a grounding page's body content (hallucination)
- This skill itself has no side effects. However, `search_index.py` automatically runs `build` if the index file (`.wikicommit/.cache/search_index.sqlite3`, not tracked by Git) doesn't exist
