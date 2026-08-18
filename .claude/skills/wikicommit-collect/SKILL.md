---
name: wikicommit-collect
description: Discover candidate sources (local files and web pages) related to the configured wiki theme, pending human approval before registration
disable-model-invocation: true
---

# wikicommit-collect

A skill that, based on `.wikicommit/config.yml`'s `theme`, searches for not-yet-ingested files in the repository and related sources on the web, and presents them as candidates. It does not implement a dedicated crawler — it's built entirely from existing file scanning, Claude Code's native web search, and internal calls to `wikicommit-generate`. This skill has no dedicated scripts of its own.

## Usage

```
/wikicommit-collect [optional guidance]
```

The guidance argument is free text, same as `/wikicommit-ask <question>` and other skills that take a free-text argument. It expresses research direction or preferred/excluded sources, e.g.:

```
/wikicommit-collect Search mainly on Wikipedia
/wikicommit-collect Prefer academic sources; avoid personal blogs
```

If omitted, behavior is unchanged from before: only `theme` is used as the search criterion.

## Processing Flow

### Step 1: Check `theme`

Read `.wikicommit/config.yml` and get the `theme` field.

- If the `theme` field is absent, or its value is an empty string:

  ```
  theme is not set, so candidates cannot be narrowed down. Set theme in .wikicommit/config.yml and re-run.
  ```

  Display this and stop (do not search for candidates).

  > `/wikicommit-init` now prompts for `theme` interactively on first run. For a repository that was already initialized before this field existed (or where `theme` was left blank), re-run `/wikicommit-init` and answer the theme prompt with non-blank text — as of Issue #374, it now updates just the `theme:` line of the existing `.wikicommit/config.yml` via a dedicated `--update-theme` flag on `init.py`, instead of silently discarding the answer under `--no-overwrite` as it previously did. Editing `theme: "<free text>"` in `.wikicommit/config.yml` directly still works too, if preferred.

- If `theme` is set, proceed to step 2, using its content as the relevance criterion for steps 4–6.

### Step 2: Hold the Guidance Argument

If a free-text argument was given alongside the command, hold it as "research guidance" for the rest of this run — it narrows or steers the search on top of `theme`, it does not replace `theme`. It is used in steps 4 and 5.

If no argument was given, skip this step; behavior for steps 4–5 is unchanged from before (only `theme` is used).

### Step 3: Inventory Already-Registered Sources

Read the frontmatter of every management file (`.md`) under `.wikicommit/source/`, and collect:

- `source.type: path` → `source.path`
- `source.type: url` / `source.type: wikicommit` → `source.url`
- `extracted_tokens`, if present — used as a size reference in step 6

Use the `source.path`/`source.url` list to exclude duplicates in steps 4 and 5.

### Step 4: Search Local Candidates

Scan files in the repository, excluding:

- `.git/`, `.wikicommit/`, `.claude/`, `node_modules/`, build output directories (`dist/`, `build/`, etc.)
- Files matching a `source.path` already collected in step 3

Restrict target extensions to those `wikicommit-generate` can handle (the "Prerequisite Skills (Text Extraction)" table in `.claude/skills/wikicommit-generate/SKILL.md`): `.md` / `.txt` / `.pdf` / `.docx` / `.pptx` / `.xlsx` / `.epub` / image files (`.jpg` / `.jpeg` / `.png` / `.gif` / `.tiff`, etc.). Extensions outside this set (which fall to the `markitdown` fallback) are not included in this step's target, since they would make the scope of the in-repository scan unbounded.

For the remaining candidates, have the LLM judge relevance to `theme` from the filename and parent directory name. Do not read the full content of files (to avoid the cost blowing up when there are many files). If needed, limit yourself to skimming the first few lines. Exclude files clearly unrelated to `theme` (license files, dependency lock files, CI configuration, etc.) from the candidates. If research guidance was held in step 2, apply it here too where it plausibly applies to local files (e.g. "prefer academic sources" can inform which local documents look more relevant) — but expect limited effect, since guidance aimed at sources like Wikipedia has no local-file equivalent.

### Step 5: Search Web Candidates

Use Claude Code's native web search tool to search for sources related to `theme`. If research guidance was held in step 2, fold it into the search: e.g. guidance like "search mainly on Wikipedia" should produce queries that prioritize `site:wikipedia.org` (or the equivalent site restriction for the site(s) named), and guidance like "prefer academic sources, avoid personal blogs" should be applied as a filter on which results are kept as candidates, not just as extra query text. Keep the URL, title, and summary for each search result. Exclude any URL matching a `source.url` already collected in step 3.

**Known JS-shell domain exclusion (Issue #425)**: also exclude any result whose URL fails the check below — these are domains a prior `wikicommit-generate` run has confirmed to sometimes return an empty content shell (real content only renders after JS execution) when fetched with `markitdown`, so presenting them as candidates here just reintroduces a source someone already deliberately excluded, via free-exploration guidance that has no memory of that prior exclusion (this is exactly what happened with the x.com source in the `ai-driven-dev-wiki` pilot that motivated this Issue):

```bash
python .wikicommit/scripts/check_extraction_quality.py check-domain <candidate URL>
```

`BLOCKED:` (exit 1) → drop the candidate silently (no need to mention it in step 6's presentation — it was never a viable candidate in the first place, same as a duplicate already excluded above). `OK:` (exit 0) → keep it as a candidate.

In addition to the normal HTML-oriented search above, always run a second, separate search pass appending `filetype:pdf` to the `theme` (and guidance, if any) query terms. General web search tends to rank news articles and blog posts above primary-source documents (government pamphlets, academic papers, technical specs), which are frequently published as PDF rather than HTML — this pass exists to counter that bias. It supplements the HTML-oriented search; it never replaces it, and it runs unconditionally (not only when guidance mentions documents). Tag each result from this pass as a PDF candidate for use in step 6. The pipeline already handles URLs that point directly at a PDF without any extra registration step (`markitdown` converts by content-type — see `docs/DesignDoc-skills.md` §11.6), so no special handling is needed at registration time (step 8).

### Step 6: Present Candidates

Merge the local and web candidates and present them as a numbered list, ordered by judged relevance (highest first). For each candidate, mark it with `⚠️` and note any copyright/licensing concern (e.g. amounts to a full reprint of a commercial news article, scraping prohibited by terms of service, etc.). If a candidate closely resembles an already-registered source found in Step 3 (e.g. same site, same document series) and that source's management file has `extracted_tokens` recorded, mention that figure as a rough size reference (e.g. "similar to already-ingested X, ~1200 tokens") to help the user gauge context-budget impact before selecting many candidates at once. For `[Web]` candidates, note the file format when it is not a plain HTML page (e.g. `[PDF]`) — in particular, every result surfaced by step 5's `filetype:pdf` pass — so the user can tell primary-source documents apart from HTML pages at a glance.

```
Not-yet-ingested source candidates related to theme "<theme content>":

[Local]
1. raw/report-2024.pdf — (brief reason for relevance)
2. docs/notes/meeting-0512.md — (brief reason for relevance)

[Web]
3. https://example.com/article — "Article Title" (brief reason for relevance)
   ⚠️ Copyright concern: may amount to a full reprint of a commercial news article
4. https://example.gov/pamphlet.pdf — [PDF] "Pamphlet Title" (brief reason for relevance)
```

If there are zero candidates, display "No not-yet-ingested candidates related to theme were found" and stop. Otherwise, hold off on asking the user to select by number — that prompt now comes at the start of step 8, after the type proposal step below has had a chance to run against the full list.

### Step 7: Type Proposal (Issue #489)

Before asking the user to select candidates, look at the candidates just presented in step 6 (titles + web search summaries, not full content) as a group and judge whether one or more Schema.org standard types — beyond what's already in `installed schema/` — would fit several of them meaningfully better than any installed type (the same "clearer semantic fit" bar `wikicommit-generate` Pass 2b uses, not merely "also plausible"). This step exists because, at the time this Issue was written, Pass 2b's own proposal only fired in an interactive session — a batch/subagent-driven `/wikicommit-generate` run silently defaulted every Pass 2b prompt to reject, so a type that was clearly needed never got added (see this Issue's background). Pass 2b has since gained its own non-interactive auto-approval path for candidates clearing a stricter bar (Issue #507), so this step is no longer the *only* mitigation for that failure mode, but it remains valuable in its own right: step 6's candidate list is being reviewed before the user has picked anything from it — the number-selection prompt is deliberately deferred to step 8 precisely so this step's Enter-based approval always runs interactively — and the evidence available (candidate titles + search summaries across multiple candidates) is comparable in strength to what Pass 2b judges from a single source's summary.

Zero candidates is the expected common outcome — do not force one to justify running this step, and do not present anything to the user if nothing clearly qualifies (this keeps the step from becoming the kind of near-always-empty detour Issue #404 removed from `wikicommit-init`, since it stays folded into this existing step rather than becoming a standalone one). Skip any candidate type that already has a file in `.wikicommit/schema/`.

1. Ensure the shared Schema.org vocabulary cache is available (lazily built on first use, same as `wikicommit-generate` Pass 2b step 1): `python .wikicommit/scripts/check_schema_org_type.py --list-types`. Non-zero exit (vocabulary fetch failed) → skip this step entirely and proceed straight to step 8 with only `installed schema/` types available; do not block or fail the run over this. Ground the judgment below in this output — do not propose a type name from memory alone, since an unverified guess (wrong casing, a type that doesn't actually exist) would only surface as a downstream `ERROR:` in step 3 after the user has already approved it.
2. Using the `--list-types` output, judge which candidate types (if any) qualify per the bar above.

For each candidate type that does qualify:

3. Present it to the user and ask for approval, Enter-based (default to **N** on a blank Enter), citing which candidates from step 6 motivate it:

   ```
   Several of the above candidates (2. "Introducing Kiro", 5. "Antigravity overview") describe named
   software products — schema:SoftwareApplication may fit them better than any installed schema/ type.

   Add this type now? [y/N]
   ```

4. For each approved type, re-verify it still exists in the vocabulary and pick 2-5 candidate properties for the new type's `properties:` block, verifying each the same way `wikicommit-generate` Pass 2b / `wikicommit-schema-propose` Step 4 do:

   ```bash
   python .wikicommit/scripts/check_schema_org_type.py --type <Type> \
     --property "$(cat <<'EOF'
   <Prop1>
   EOF
   )" \
     --property "$(cat <<'EOF'
   <Prop2>
   EOF
   )" \
     ...
   ```

   Each `--property` value goes through its own quote-delimited heredoc (`docs/DesignDoc-skills.md` §11.7) — these are candidate names this step itself just proposed, not values an earlier script already verified. If the script reports `<Type>` itself as `ERROR:` (not just a property), abort this candidate entirely — do not write a schema file for it, and tell the user the proposed type name did not resolve in the vocabulary (this should be rare given the `--list-types` grounding in step 1, but is not impossible if the LLM misread a type name from that list). Otherwise, drop any individual property the script reports as `ERROR:` — never put an unverified property into the new schema file's `properties:` block. Then write `.wikicommit/schema/<Type>.md` directly with the Write tool, in the standard-type format (`docs/DesignDoc-data.md` §5.2, Issue #495's `properties:`-nested layout), using `.wikicommit/schema/default.md` and `.wikicommit/schema/Person.md` as the fixed style references — identical process to `wikicommit-generate` Pass 2b step 4 / `wikicommit-schema-propose` Step 4. Set `wikicommit.provenance: collect` in the new file's `wikicommit:` block (`docs/DesignDoc-data.md` §5.2, including the "don't copy `Person.md`'s own `provenance: default`" caveat). This is the one narrow exception to this Skill's "no writes to `.wikicommit/schema/`" rule (see Prohibited Actions below): it only ever *adds* a file that isn't there yet, never edits or deletes an existing one. No commit or PR happens here — the new file is left on disk like any other file `wikicommit-generate` writes, and `wikicommit-merge` picks it up later in the normal batch.

5. Rejected or no-candidate types are simply not added — no persistence of a declined candidate anywhere, same reasoning as `wikicommit-generate` Pass 2b. `wikicommit-schema-propose` remains the post-hoc safety net for anything missed here.

### Step 8: Register the Selected Candidates

Make clear that the copyright/license assessment from step 6 is only a rough guide and **the final judgment is made by a human**, then ask the user to select by number from the step 6 list (multiple selections allowed; "none" is also a valid choice; "all"/「全部」selects every listed candidate at once).

For each candidate the user selected — and only those — run **only** `wikicommit-generate`'s Step 0: Source Registration (`.claude/skills/wikicommit-generate/SKILL.md`) with that candidate's path/url as the argument. Do **not** proceed to Pass 1–4 (text extraction, analysis, page generation, review) here — page generation is deferred to a separate `/wikicommit-generate` run (see Step 9). Running text extraction and analysis for every selected candidate within this same conversation would accumulate each candidate's extracted text in context, risking token exhaustion and long runtimes when many candidates are selected at once.

Do not register candidates the user did not select in `.wikicommit/source/`.

### Step 9: Report Results

Display a list of the outcome for each candidate's registration (`CREATED` / `SKIP` / `UPDATED`, or the failure reason — per Step 0's output). If at least one candidate was registered, guide the user through the next steps:

```
Next steps:
- Run /wikicommit-generate (no arguments) to generate wiki pages for the N registered candidates
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
```

If many candidates were registered (e.g. more than around 5), add a note suggesting the user split page generation across multiple `/wikicommit-generate` runs (no arguments; it processes all pending/outdated management files each time) rather than expecting a single run to handle all of them — each run's context resets when started fresh, which keeps token usage and per-run time manageable.

## Prohibited Actions

- Registering to `.wikicommit/source/` without user approval
- Implementing a new dedicated crawler or scraping script (must be built entirely from a combination of existing web search and extraction skills)
- Committing or creating a PR against `main` or any branch
- Writing to `.wikicommit/schema/`, other than the narrow exception in step 7 (adding a new, human-approved type file only — never editing or deleting an existing one, same "add-only" exception `wikicommit-generate` Pass 2b uses)

## Notes

- The copyright assessment of web search results depends on the LLM's judgment and is not guaranteed accurate. Limit yourself to surfacing concerns — the final judgment is made by a human
- Relevance judgment for local candidates does not read the full content of files. Full-content evaluation is left to `wikicommit-generate`'s Pass 2 (analysis), which runs in a later, separate `/wikicommit-generate` invocation (not called from within this skill — see step 8)
- Setting or changing `theme` is out of scope for this skill (edit `.wikicommit/config.yml` directly)
- **Role split with `wikicommit-init`'s obvious-type judgment and `wikicommit-generate` Pass 2b (Issue #490)**: this Skill's step 7 is the middle of three type-proposal entry points. See `docs/DesignDoc-data.md` §3.3 for the full evidence-chain rationale — that section is the single source of truth for the role split (do not re-derive it here)
