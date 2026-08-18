---
name: wikicommit-generate
description: Register a source file or URL to .wikicommit/source/ and generate wiki pages locally (no Git)
disable-model-invocation: true
---

# wikicommit-generate

Registers a source and generates wiki pages (local writes only) in one run. Performs no Git operations.

## Usage

```
/wikicommit-generate <path|url> [--include <glob>]   # register a source + generate pages in one run
/wikicommit-generate                                  # process all pending/outdated/partial management files (asks first if more than 5)
```

## Prerequisite Skills (Text Extraction)

If a required skill is not installed, **stop processing and display the install command** before proceeding. Exception: `.pdf` (text-based), `.docx`, `.pptx`, and `.xlsx` do not stop when their respective official skill is unavailable — Pass 1 automatically falls back to running the `markitdown` CLI directly instead (see Pass 1 below); each only stops if `markitdown` itself turns out not to be installed. `.epub` and image files have no such fallback (see rows below) — `markitdown` cannot equivalently cover EPUB or OCR extraction, so these two file types still stop when their skill is unavailable (Issue #268).

| File type | Required skill | Install command |
|---|---|---|
| `.pdf` (text-based) | Anthropic official `pdf` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill pdf` — if this fails to create a `.claude/skills/pdf/` symlink (known upstream bug: [vercel-labs/skills#744](https://github.com/vercel-labs/skills/issues/744), [#851](https://github.com/vercel-labs/skills/issues/851)), no action is needed: Pass 1 detects this and automatically runs the `markitdown` CLI instead. If `markitdown` itself isn't installed, Pass 1 stops and displays `pip install 'markitdown[pdf]'` for you to run |
| `.pdf` (scanned) | `ocr-and-documents` | `npx skills add https://github.com/NousResearch/skills --skill ocr-and-documents` |
| `.docx` | Anthropic official `docx` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill docx` — if this fails to create a `.claude/skills/docx/` symlink (same upstream bug as `.pdf`, see above), no action is needed: Pass 1 detects this and automatically runs the `markitdown` CLI instead (`.docx` needs no extra beyond the base `markitdown` package, unlike `.pdf`'s `[pdf]` extra). If `markitdown` itself isn't installed, Pass 1 stops and displays `pip install markitdown` for you to run |
| `.pptx` | Anthropic official `pptx` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill pptx` — same fallback pattern as `.docx` above (`pip install markitdown` if not yet installed) |
| `.xlsx` | Anthropic official `xlsx` (preferred), falls back to the `markitdown` CLI automatically if unavailable | `npx skills add https://github.com/anthropics/skills --skill xlsx` — same fallback pattern as `.docx` above (`pip install markitdown` if not yet installed) |
| `.epub` | `ebook-extractor` (no `markitdown` fallback — see note above; Issue #268) | `npx skills add https://github.com/anthropics/skills --skill ebook-extractor` |
| Image files | `ocr-and-documents` (no `markitdown` fallback — see note above; Issue #268) | `npx skills add https://github.com/NousResearch/skills --skill ocr-and-documents` |
| URL (web page or direct file link, e.g. PDF) | `markitdown` (Python package, not a Claude Skill), invoked via `add_source.py --fetch-url` rather than the CLI directly — see the Issue #527 note under Pass 1 below | `pip install 'markitdown[pdf]'` — run via `python .claude/skills/wikicommit-generate/scripts/add_source.py --fetch-url <url> --output <path>` (see Pass 1 below) |
| Other (unmatched file extensions) | `markitdown` (fallback; same package as above) | `pip install 'markitdown[pdf]'` — run via CLI: `PYTHONIOENCODING=utf-8 markitdown <path>` |

Every `markitdown` invocation in this skill is prefixed with `PYTHONIOENCODING=utf-8`: on Windows, a Japanese-locale console codepage (`cp932`) can make the `markitdown` subprocess's stdout encoding disagree with the UTF-8 the rest of the pipeline (redirect target, `Read` tool, hash computation) assumes, corrupting extracted text into mojibake before it ever reaches Pass 2 (Issue #272). This `VAR=value command` prefix syntax is POSIX shell — it works unmodified under both Git Bash and WSL, the two execution paths Claude Code's Bash tool uses on Windows (`docs/DesignDoc-skills.md` §11.1); it would need different syntax under raw PowerShell/cmd.exe, but Skills never run there.

## Processing Flow (4-Pass Design)

Before starting, read `.wikicommit/config.yml` and obtain `primary_lang`, `theme`, and `generate.max_retries` (default: 2). If `.wikicommit/config.yml` does not exist, stop immediately and tell the user to run `/wikicommit-init` first. If `theme` is absent from `config.yml`, treat it as an empty string. An empty `theme` disables the exclude judgment described in Pass 2 — all entities are analyzed as `create` / `update` / `ambiguous` only, as before this field existed.

### Step 0: Source Registration (only when argument is given)

If an argument is provided:

1. Determine the source type from the argument:
   - Starts with `https://` → `type: url`
   - Directory path with `--include` option → batch registration
   - Otherwise → `type: path`

2. Run the following command:

   ```bash
   python .claude/skills/wikicommit-generate/scripts/add_source.py <source> [--include "<glob>"]
   ```

3. Check the output and notify the user:
   - `CREATED:` → New registration complete. Proceed to Pass 1.
   - `SKIP:` → Check the management file's `status`:
     - `generated` / `failed` (`type: path` only — for `type: url`/`wikicommit` this state produces `RECHECK:` instead, see below) → Notify: "No changes (skipped). To regenerate, set the management file's status to `pending` and re-run." Then exit.
     - `pending` / `outdated` / `partial` → Proceed to Pass 1.
   - `UPDATED:` → Notify the user that the management file was updated (hash mismatch → `outdated`, or hash unchanged → `outdated → pending` reset). Proceed to Pass 1.
   - `RECHECK:` (`type: url` / `wikicommit` only) → The management file's previous run already completed (`status: generated`/`failed`/`excluded`). Unlike `type: path`, a URL source's hash can't be recomputed locally — the only way to know whether the remote content changed is to actually re-fetch it. Notify the user that WikiCommit will re-fetch the URL to check for changes, then proceed to Pass 1 for this single management file: treat it as selected for processing even though its current `status` is not `pending`/`outdated`/`partial` (Step 0 having picked exactly this file is what qualifies it, same as the "if an argument was given" override in Pass 1 step 1) — and mark it as a **forced recheck** so Pass 1 applies the special handling in its "Hash write-back" section below (bypass the scratch-file cache; compare the fresh fetch to the *current* `source.hash` before deciding whether to proceed).
   - Exit code 1 (error) → Display the error and stop.

If no argument is given, skip Step 0 and start from Pass 1.

### Pass 1: Text Extraction

1. Collect ingest management files with `status: pending`, `status: outdated`, or `status: partial` from `.wikicommit/source/`:
   - If an argument was given: process only the management file Step 0 acted on (`CREATED:`/`UPDATED:`, or `RECHECK:` — a forced recheck is processed here too even though its `status` is still `generated`/`failed`/`excluded`, per Step 0 above)
   - If no argument: collect all matching files under `.wikicommit/source/`. If the count exceeds 5 (same threshold as `wikicommit-collect`'s Step 9 note), do not start processing yet — show the count and the list of matching management file paths, then ask the user to choose: **(a)** process all of them in this run, or **(b)** process only the first 5 (by path, ascending) and leave the rest untouched for a later run. If the user picks (b), proceed with only those 5; the unselected files keep their current `status` unchanged and will naturally be picked up by a future no-argument `/wikicommit-generate` run — no other change is needed for this. If the count is 5 or fewer, proceed with all of them without asking (unchanged behavior for the common case).
2. If no target files are found, output "No management files to process" and exit.
3. For each ingest file, read `source.type` and `source.path` / `source.url`.
4. Extract text based on `source.type` and file extension:
   - `type: wikicommit` (federated source) / `type: url` → **Known JS-shell domain check (Issue #425, guard B)**: before attempting any fetch, run:

     ```bash
     python .wikicommit/scripts/check_extraction_quality.py check-domain <source.url>
     ```

     `BLOCKED:` (exit 1) → do not attempt extraction at all. Treat this source as extraction failure (step 5 below): mark `status: failed`, write the script's `BLOCKED:` line verbatim into `## Failure Reason`, notify the user, and skip to the next source. `OK:` (exit 0) → proceed with the fetch below as normal. This check is deliberately narrow — it only catches domains a prior run has already confirmed return an empty content shell (see the `KNOWN_JS_SHELL_DOMAINS` set in the script); it is not a general JS-detection heuristic. The general case is guard A in step 5 below.

     Extract `source.url` by running `add_source.py --fetch-url` (deterministic conversion, no LLM summarization step in between — this is what makes the **Hash write-back** below genuinely verbatim, unlike the previous WebFetch-based approach; see Issue #189), rather than invoking the `markitdown` CLI on the URL directly. `markitdown`'s own HTTP client sends Python `requests`' default User-Agent when given a bare URL, which Wikimedia domains (Wikipedia, Wikisource, etc. — likely per the [Wikimedia User-Agent policy](https://meta.wikimedia.org/wiki/User-Agent_policy)) reject with `403 Forbidden`; `add_source.py --fetch-url` avoids this by calling `markitdown`'s Python API (`MarkItDown(requests_session=...)`) with a `requests.Session` carrying a WikiCommit-identifying User-Agent instead (Issue #527). This preserves `markitdown`'s normal HTTP-response-based dispatch (Content-Type mimetype **and charset**) exactly as when passing it a bare URL — unlike a `curl`-then-convert-locally two-step, which would fetch to a plain file and lose the HTTP response's charset header, silently degrading `markitdown`'s decoding to statistical guessing for any page whose encoding is declared only via that header (verified to mojibake non-UTF-8, non-ASCII-safe pages, e.g. legacy `windows-1252` sites, during Issue #527's implementation) — so only the User-Agent changes, nothing else about how `markitdown` fetches or decodes the page. Confirm `markitdown` is installed once per run, before the first source of any kind — `type: url`, `type: wikicommit`, the `.pdf`/`.docx`/`.pptx`/`.xlsx` fallbacks below, or the "Other" fallback below — that needs it; do not re-run this check for every subsequent source once it has passed:

     ```bash
     PYTHONIOENCODING=utf-8 markitdown --version
     ```

     Non-zero exit or command not found → stop processing and display the install command from the Prerequisite Skills table above (`pip install 'markitdown[pdf]'`), per the rule at the top of this section. This applies even when this check is being run for the `.pdf` (text-based) fallback or the `.docx`/`.pptx`/`.xlsx` fallbacks (step 4 below) — `markitdown` is the guaranteed path for these formats once the corresponding official skill is unavailable, so its own absence must still stop processing rather than being silently skipped.

     `markitdown` dispatches on the URL's content type / extension internally, so a URL that points directly at a non-HTML file (e.g. `https://arxiv.org/pdf/xxxx.pdf`) is extracted with the appropriate converter automatically — no separate `type: path` registration or pre-download step is needed for this case. Fetch only the registered URL — do not follow or register links found within the extracted content, even if they appear relevant to the topic (out-of-scope fetching risks unintended scope creep, copyright exposure, and unnecessary token usage). If related linked pages are worth ingesting, register them explicitly as separate sources via `/wikicommit-generate <url>`.

   **Hash write-back** (`type: url` / `type: wikicommit`): the management file is registered with `hash: ""`; this step fills it in deterministically via script rather than by hand-editing YAML (manual edits are unreliable — see Issue #157). `<scratch-path>` below is the ingest management file's path relative to `.wikicommit/source/url/`, without the `.md` extension, with the `/` separators kept intact (e.g. management file `.wikicommit/source/url/example.com/article.md` → scratch path `example.com/article`) — mirroring the nested path rather than collapsing it to `-` keeps scratch files unique per source even when several `type: url`/`type: wikicommit` sources are processed in the same run (flattening with `-` is not collision-free here: the nested management file `.wikicommit/source/url/example.com/article.md` and a legacy flat management file `.wikicommit/source/url/example.com-article.md` would both collapse to the same scratch name `example.com-article`).

     **Forced recheck** (source flagged `RECHECK:` in Step 0 — i.e. re-running `/wikicommit-generate <url>` on a source whose `status` was already `generated`/`failed`/`excluded`; Issue #310): skip the **Cache check** below unconditionally and go straight to the fetch — a kept scratch file from the prior successful run would otherwise trivially "match" the management file's still-unchanged `source.hash` and short-circuit the very re-fetch this recheck exists to perform. After the fetch succeeds, before running `--write-hash` (which unconditionally overwrites `source.hash`), first run `--check-hash` against the freshly-fetched scratch file to compare it with the management file's *current* (pre-overwrite) `source.hash`:

     ```bash
     python .claude/skills/wikicommit-generate/scripts/add_source.py --check-hash <ingest-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     - `HASH_MATCH:` (exit 0) → the remote content is unchanged since the last successful check. Do **not** run `--write-hash` and do **not** proceed to Pass 2–4 for this source — leave the management file's `status`/`hash` exactly as they were. Notify the user "No changes: `<url>`" and move on to the next source.
     - `HASH_MISMATCH:` (exit 1) → the content changed. Run `--write-hash` as usual (see below) and continue this source through Pass 1 steps 5–6 and Pass 2–4 normally; Pass 4 step 5's existing status rules (below) already set the appropriate final `status` (`generated`/`partial`/`excluded`/`failed`) once processing completes, so no separate status transition is needed here.

     For a normal (non-recheck) `type: url`/`wikicommit` source, apply the **Cache check** instead: the scratch file at `.wikicommit/.cache/ingest-fetch/<scratch-path>.md` is *kept* after a successful fetch (not deleted — see below), so a source that is processed again with an unchanged `source.hash` (e.g. re-running `/wikicommit-generate` on a source left `status: partial` after a prior run) can reuse it instead of re-fetching against the network (Issue #278). Before fetching, if that scratch file exists, run:

     ```bash
     python .claude/skills/wikicommit-generate/scripts/add_source.py --check-hash <ingest-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     - `HASH_MATCH:` (exit 0) → the cached scratch file's content is still valid for the management file's current `source.hash`. Skip the fetch and the write-hash step below entirely, and jump straight to the "read the scratch file's content in full" step near the end of this bullet.
     - `HASH_MISMATCH:` (exit 1, including "scratch file doesn't exist") → the cache cannot be reused (no scratch file yet, or the source's `hash` has since changed — e.g. re-registered after `status: outdated`). Proceed with the fetch below as normal; this always fetches fresh content rather than trusting a stale scratch file, so a hash change is never masked by an old cache.

     If no scratch file exists yet at that path (or this is a forced recheck — see above), skip the cache check and go straight to the fetch below:

     ```bash
     python .claude/skills/wikicommit-generate/scripts/add_source.py --fetch-url "<source.url>" --output ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     `--fetch-url` creates the scratch file's parent directory itself (it is already gitignored — see `search_index.py` in `DesignDoc-ScriptSpec.md`) and writes exactly what `markitdown` produced to the output path, with nothing in between.

     - `ERROR:` (exit code non-zero — network error, HTTP error status like 403/404, login-required page, unsupported content, etc.) → treat this source as extraction failure (step 5 below) and skip to the next source; do not run the command below.
     - `FETCHED:` (exit 0), forced recheck → run the `--check-hash` comparison described above and branch on `HASH_MATCH`/`HASH_MISMATCH`.
     - `FETCHED:` (exit 0), normal (non-recheck) source → run:

       ```bash
       python .claude/skills/wikicommit-generate/scripts/add_source.py --write-hash <ingest-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
       ```

       Check the output: `HASH_WRITTEN:` → proceed. `ERROR:` (exit code 1) → treat this source as extraction failure (step 5 below) and skip to the next source.

     After `HASH_WRITTEN:` (or after a `HASH_MATCH:` cache hit above), read the scratch file's content **in full** with the Read tool — if the file is large enough that a single call truncates it, issue additional Read calls with `offset` to cover the rest; a partial read here would silently reintroduce the non-verbatim problem the original write-back change was meant to fix. This becomes the "extracted text" for this source used in steps 5–6 below and in Pass 2. **Do not delete the scratch file** — unlike before Issue #278, it is left in place so a later re-run of this same source (unchanged hash) can reuse it via the cache check above. `.wikicommit/.cache/` is a rebuildable, gitignored cache (same category as `search_index.sqlite3` — see `DesignDoc-ScriptSpec.md`), so leaving files there does not conflict with GitOps.
   - `type: path`, `.md` / `.txt` → Read directly with the Read tool
   - `type: path`, `.pdf` (scanned) → Call the `ocr-and-documents` skill
   - `type: path`, `.pdf` (text-based) → Two-tier fallback (Issue #242 — `npx skills add ... --skill pdf` is known to fail to symlink `.claude/skills/pdf/` on some setups, see Prerequisite Skills table above):
     1. Check whether the `pdf` skill is available and recognized, e.g. by checking that `.claude/skills/pdf/SKILL.md` exists. If it exists, call the `pdf` skill (preferred — better table/encrypted-PDF handling).
     2. Otherwise, fall back to the `markitdown` CLI: run `PYTHONIOENCODING=utf-8 markitdown <path>`. This is subject to the same `markitdown --version` prerequisite check described above (once per run, before the first source of any kind that needs `markitdown`) — non-zero exit or command not found → stop processing and display the install command from the Prerequisite Skills table (`pip install 'markitdown[pdf]'`).
     Do not stop processing solely because the `pdf` skill is unavailable — only stop if the `markitdown[pdf]` fallback itself is unavailable.
   - `type: path`, `.docx` → Two-tier fallback (Issue #268 — same upstream `npx skills add` symlink bug as `.pdf`, see Prerequisite Skills table above):
     1. Check whether the `docx` skill is available and recognized, e.g. by checking that `.claude/skills/docx/SKILL.md` exists. If it exists, call the `docx` skill (preferred — tracked-changes/comment handling).
     2. Otherwise, fall back to the `markitdown` CLI: run `PYTHONIOENCODING=utf-8 markitdown <path>`. This is subject to the same `markitdown --version` prerequisite check described above — non-zero exit or command not found → stop processing and display the install command from the Prerequisite Skills table (`pip install markitdown`).
     Do not stop processing solely because the `docx` skill is unavailable — only stop if the `markitdown` fallback itself is unavailable.
   - `type: path`, `.pptx` → Same two-tier fallback pattern as `.docx` above: check `.claude/skills/pptx/SKILL.md`, prefer the `pptx` skill, otherwise fall back to `PYTHONIOENCODING=utf-8 markitdown <path>` (install command `pip install markitdown`).
   - `type: path`, `.xlsx` → Same two-tier fallback pattern as `.docx` above: check `.claude/skills/xlsx/SKILL.md`, prefer the `xlsx` skill, otherwise fall back to `PYTHONIOENCODING=utf-8 markitdown <path>` (install command `pip install markitdown`).
   - `.epub` → Call the `ebook-extractor` skill (no `markitdown` fallback — EPUB extraction is not equivalently covered by `markitdown`; Issue #268)
   - Image files (`.jpg`, `.jpeg`, `.png`, `.gif`, `.tiff`, etc.) → Call the `ocr-and-documents` skill (no `markitdown` fallback — OCR is not equivalently covered by `markitdown`; Issue #268)
   - Other → Run the `markitdown` CLI as fallback (Python package, not a Claude Skill — see Prerequisite Skills table above). Subject to the same `markitdown --version` prerequisite check described above (once per run, before the first source of any kind that needs `markitdown`): non-zero exit or command not found → stop processing and display the install command from the Prerequisite Skills table.
5. If the extracted text is empty or unreadable, mark that source as `status: failed` (extraction error), write a one-to-few-sentence reason to the management file's `## Failure Reason` section (create it if absent, overwrite if present — e.g. `"Text extraction failed: markitdown returned empty output for this PDF."`, naming the extraction tool/skill that was tried and what went wrong), notify the user, and skip to the next source. Do not proceed to Passes 2–4 for this source. Write `## Failure Reason` in English regardless of `<primary_lang>` (Issue #408 — unlike `## Summary`, this section is debugging information for the operator, not reader-facing content, so it does not follow the `<primary_lang>` rule that governs `summary`/`exclude_note`/`coverage_gap_note`).

   **Low-density check (Issue #425, guard A)**: otherwise (extracted text is non-empty and readable), run a general, domain-agnostic check for text that is non-empty but still useless — markup/script/JSON boilerplate rather than real content (the failure mode the guard-B domain check above only catches for a handful of confirmed domains). For a `type: url`/`type: wikicommit` source, run it against the scratch file already on disk:

   ```bash
   python .wikicommit/scripts/check_extraction_quality.py check-density ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
   ```

   For any other source type (the extracted text exists only as this run's context, not as a file), pipe it in via a quoted-delimiter heredoc instead — same reasoning as CLAUDE.md §11.7's "自由記述テキストをCLIへ渡す" rule, even though this text isn't operator-authored free text, a heredoc is still the safe way to hand arbitrary content (which may itself contain shell metacharacters, e.g. backticks inside a code sample the source quotes) to a subprocess's stdin without shell interpretation:

   ```bash
   python .wikicommit/scripts/check_extraction_quality.py check-density <<'EOF'
   <extracted text>
   EOF
   ```

   `LOW_DENSITY:` (exit 1) → treat this exactly like the empty/unreadable case above: mark `status: failed`, write the script's `LOW_DENSITY:` line verbatim into `## Failure Reason`, notify the user, and skip to the next source — do not proceed to Passes 2–4. `OK:` (exit 0) → proceed to step 6 below.
6. Otherwise, compute an approximate token count for the extracted text (a rough estimate is fine — e.g., character count ÷ 4, rounded to the nearest integer; no LLM-specific tokenizer is required, per the BYOLLM design) and write it to the management file's `extracted_tokens` field. Overwrite any existing value every time this step is reached — this happens unconditionally as soon as extraction succeeds, regardless of the Pass 2–4 outcome (unlike `last_generated_at`, which Pass 4 step 5 only sets on the `generated`/`partial` branches).

### Pass 2: Analysis (LLM → JSON)

Pass 2 runs in three sub-steps per source: 2a produces a summary, 2b resolves — inline, right now — whether a Schema.org type outside `installed schema/` should be added before entities are extracted, and 2c extracts entities using whatever types are available after 2b.

#### Pass 2a: Summary

Ask the LLM to read the full extracted text and produce a 2-3 sentence summary of the source's content, in `<primary_lang>`. This summary is used immediately below (Pass 2b) and is also what eventually gets written to the ingest management file's `## Summary` section at the end of Pass 2c — do not write it to the management file yet, since Pass 2c may still need to append `coverage_gap_note`/exclusion notes to the same section (see below).

During this same read, also judge whether the source text is clearly written in a language other than `<primary_lang>` (Issue #336). This is a coarse LLM judgment call, not lexical/library-based language detection — flag only unambiguous cases (e.g., an entirely English document when `primary_lang: ja`), not borderline ones (a `primary_lang` document with a handful of foreign-language proper nouns or quoted snippets). This judgment does not change any generation behavior: entities are still extracted and written in `<primary_lang>` exactly as before (see the `lang` field rule in Pass 2c) — the source's content will be summarized/translated into `<primary_lang>` regardless. If flagged, append this source (its ingest management file path and the detected language) to a running list so all detections across sources can be rolled up together in the Completion Notice below; do not stop, ask for confirmation, or write anything to the management file for this — it is purely informational, unlike `ambiguous`/`exclude`.

**Source-as-entity judgment (Issue #475)**: also judge whether the source document *itself* — as distinct from the individual people/organizations/concepts it describes — has independent citable identity: a title, named author(s) or publishing organization, and a publication date or stable identifier (DOI, permalink URL), such that a reader would recognize it as a standalone "work" worth linking to on its own (e.g. an arXiv paper, an official vendor blog post announcing a product, an official report/whitepaper, a news article). Do not apply this to sources that are more "information" than "work" — a government procedure page, a personal blog's casual technical explainer with no strong standalone identity — where authorship/publication metadata is weak or absent, or the content is instructions/reference material rather than a citable piece of writing. This is a per-source judgment made once here, not per-entity; when it passes, the source document itself becomes an *additional* entity candidate that flows into Pass 2b (type resolution) and Pass 2c (entity extraction) exactly like any other entity — it does not replace or reduce the extraction of concepts/people/organizations discussed *within* the source, and it introduces no new mechanism, frontmatter field, or `sources:` semantics (see the Pass 2c rule and Pass 3 note below).

As a concrete restatement of the same test (Issue #479): does the source have a fixed publication date and author(s) that will not change (a single-instance work — an article, paper, report, or story), or is it a continuously-updated living resource with no meaningful "publication date" of its own (an official document, a government procedure page, a Wikipedia article)? Only the former qualifies. `installed schema/` ships with `ScholarlyArticle`/`NewsArticle`/`BlogPosting`/`ShortStory`/`Book` by default (Issue #479) specifically to cover the common cases of this judgment without needing Pass 2b to propose them — Pass 2b's dynamic type addition remains the fallback for a source-as-entity candidate whose closest fit isn't one of these (e.g. `schema:Report`).

#### Pass 2b: Type Necessity Judgment (Issue #315)

Before extracting entities, decide whether the source content calls for a Schema.org type that isn't already in `installed schema/`. This runs **once per source** (not once per entity) and is grounded in the Pass 2a summary — the same "read the summary, judge against the full Schema.org type list" pattern `wikicommit-init`'s theme-driven suggestion (Issue #286, since removed by Issue #404) used, except here the evidence is the actual source content rather than a single free-text `theme` sentence, so this judgment is comparatively high-confidence.

1. Ensure the shared Schema.org vocabulary cache is available (lazily built on first use): `python .wikicommit/scripts/check_schema_org_type.py --list-types`. Run this once per `/wikicommit-generate` invocation (not once per source), same as before. Non-zero exit (vocabulary fetch failed) → skip Pass 2b entirely for every source this run and proceed straight to Pass 2c with only `installed schema/` types available; do not block or fail the run over this.

   **Also determine, once per invocation (not once per candidate — Issue #507)**: is this run interactive
   (a live human can actually answer an Enter prompt right now) or non-interactive/subagent-driven (no
   real answer will ever arrive)? This is the same self-report judgment step 3 below already made before
   Issue #507; make it once here, at the top of Pass 2b, and hold it constant for every candidate across
   every source in this run — interactivity is a property of the run, not of any individual candidate, so
   re-deriving it per candidate risks the judgment flipping mid-run (one candidate shown a real prompt,
   another silently auto-approved/declined) and the Completion Notice misrepresenting what actually
   happened. Step 3 below branches on this stored determination rather than re-judging it.
2. Using the `--list-types` output and the Pass 2a summary, judge whether one or more Schema.org standard types — beyond what's already in `installed schema/` — would fit this source's content meaningfully better than any installed type (not merely "also plausible": a clearer semantic fit, where more of the source's concrete details map onto that type's actual properties). Skip any candidate type that already has a file in `.wikicommit/schema/`, including one just added by an earlier source **in this same run** (scan the directory on disk, same reasoning as the existing-pages scan in Pass 2c below) — never propose a type twice. Zero candidates is an expected common outcome, not a fallback; do not force a candidate to justify running this step. **This includes the source document itself (Issue #475)** when Pass 2a flagged it as a source-entity candidate: judge a type for it the same way as for any other candidate (e.g. `schema:Report` for a whitepaper, `schema:Legislation` for a piece of legislation — not `schema:ScholarlyArticle`/`NewsArticle`/`BlogPosting`/`ShortStory`/`Book`, which already ship in `installed schema/` by default since Issue #479 and so are resolved directly in Pass 2c without ever reaching this step). Note that the ingest management file's `schema:` hint (Pass 2c context list below) describes the source's primary discussed *subject* (e.g. `schema:Person` for a biography) — it is not evidence about what the source *document itself* is, so it does not carry over to this judgment; treat the source-entity's type purely on its own content-fit merits, independent of whatever hint applies to the entities discussed within the source.

   **Named-entity pattern (Issue #447)**: apply extra scrutiny when a candidate entity is a concrete, named subject — a specific software product, research dataset/benchmark, creative work, standard, etc. — rather than an abstract term, concept, or methodology. `DefinedTerm` is broad enough to technically represent almost anything with a name, which can make it look like a safe default and suppress a proposal that would otherwise pass the bar above. For this pattern specifically, the fact that `DefinedTerm` could technically represent the entity is **not** by itself a reason to skip proposing a more specific standard type (e.g. `SoftwareApplication` for a named software product, `Dataset` for a named benchmark). This does not relax the threshold for abstract terms/concepts/methodologies (e.g. a named approach like "vibe coding" with no more specific standard type) — those should still default to zero candidates as before.
3. For each candidate, branch on the interactive/non-interactive determination made once, for the whole
   run, in step 1 above:

   - **Interactive**: present the candidate and ask for approval, Enter-based (default to **N** on a
     blank Enter), unchanged from before — the step 2 threshold above is the only bar a human-reviewed
     candidate has to clear:

     ```
     This source's content suggests schema:GovernmentService might fit better than any installed
     schema/ type for the following entities: "児童手当の申請手続き" (a government benefit application
     procedure — schema:GovernmentService's jurisdiction/availableChannel/hoursAvailable properties
     fit this content more directly than schema:HowTo's generic step list).

     Add this type now? [y/N]
     ```

     If declined (the user typed N or left it blank), record it as **explicitly declined**.

   - **Non-interactive/subagent-driven**: no human will ever see the prompt above, so defaulting it to N
     unconditionally would silently drop every candidate regardless of merit — this was the actual failure
     mode Issue #507 closes (see Issue #489's background for why this is the common case in a batch
     `/wikicommit-generate` run). Do not show the prompt at all. Instead, apply a second, stricter filter
     to the candidate: is the type **obviously** implied by this source's content, not merely a clearer
     semantic fit than any installed type (step 2's bar) — the same "obviously implied, not merely
     plausible" bar `wikicommit-init`'s theme-driven judgment (Issue #490) and `wikicommit-collect`'s Type
     Proposal step (Issue #489) apply, except grounded here in the actual source content rather than a
     single theme sentence or a handful of candidate titles — the strongest evidence of the three, which
     is why clearing this bar here is treated as high-confidence enough to skip human confirmation
     entirely. This is genuinely stricter than step 2, not the same judgment restated: step 2 only asks
     whether the type fits *better* than any installed type, while this bar asks whether the fit is
     *unmistakable* — a source that merely makes `schema:GovernmentService` the better choice over
     `schema:HowTo` clears step 2 but may not clear this bar; a source unambiguously about a single named
     software product clears both.
       - Clears the stricter bar → treat as **approved without ever showing the prompt** (default **Y**)
         and proceed directly to step 4 for it.
       - Does not clear the stricter bar → record it as **non-interactively declined**.

   Whichever of the three outcomes applies (explicitly declined, non-interactively declined, or
   non-interactively auto-approved), append the candidate — its type name, the motivating
   entities/reasoning, this source's ingest management file path, and which outcome it was — to a running
   list so it can be rolled up in the Completion Notice below (Issue #491, extended by Issue #507). Record
   the actual outcome rather than assuming one: the Completion Notice must describe accurately what
   happened in *this* run, and an interactive session where the user typed N themselves is not
   "non-interactive." This is conversation-only bookkeeping, not a file write — it does not conflict with
   step 5's "no persistence" rule below, and it applies equally to the auto-approved case: the type file
   itself is written in step 4 like any other approval, but *why* it was approved without a human still
   needs to reach the Completion Notice.

4. For each approved candidate, verify it still exists in the vocabulary and pick 2-5 candidate properties for the new type's `properties:` block, verifying each the same way `wikicommit-schema-propose` Step 4 does. If it isn't already obvious from the source content which properties fit, browse the type's full available set first (Issue #497 — `--list-properties` is the on-demand replacement for the old `recommended` field's role now that Issue #495 removed it):

   ```bash
   python .wikicommit/scripts/check_schema_org_type.py --type <Type> --list-properties
   ```

   Each line is `<property><TAB><declaring type><TAB><entity-range candidates, or "-"><TAB><one-line description>`; pick candidates from this list rather than guessing property names from memory, then verify the chosen ones:

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

   Each `--property` value goes through its own quote-delimited heredoc (`docs/DesignDoc-skills.md` §11.7) — these are candidate names this step itself just proposed, not values an earlier script already verified, so they don't qualify for §11.7's upstream-validation exemption (same reasoning as Pass 3's identical `--show-range` call above). Drop any property the script reports as `ERROR:` — never put an unverified property into the new schema file's `properties:` block. Then write `.wikicommit/schema/<Type>.md` directly with the Write tool, in the standard-type format (`docs/DesignDoc-data.md` §5.2 — a `wikicommit:` block with `base`/`granularity`, template frontmatter with the verified property names nested under `properties:` as empty-string placeholders, and a body template), using `.wikicommit/schema/default.md` and `.wikicommit/schema/Person.md` as the fixed style references (identical process to `wikicommit-schema-propose` Step 4). Set `wikicommit.provenance` in the new file's `wikicommit:` block to whichever of the two outcomes step 3 actually recorded for this candidate — `generate-interactive` if a human answered the Enter prompt, `generate-auto` if it was auto-approved with no prompt shown (Issue #507); see `docs/DesignDoc-data.md` §5.2, including the "don't copy `Person.md`'s own `provenance: default`" caveat. This is the one narrow exception to `wikicommit-generate`'s "Git operations: none, `.wikicommit/schema/`: read-only" contract (Notes below) — it only ever *adds* a file that isn't there yet, never edits or deletes an existing one. No PR is involved and no commit happens here: the new file is left on disk exactly like every other file this Skill writes, and `wikicommit-merge` picks it up later (see that Skill's updated `git add` scope).
5. Rejected or no-candidate types are simply not added — there is no **persistence** of a declined candidate to any file anywhere (deliberately: an indirect signal that only surfaces "later, maybe" was the exact problem this Issue replaces). The running list from step 3 above is the one narrow exception, and it stays that way on purpose: it is reported once, in this run's own Completion Notice, and then gone — never written to a management file, never something a *later*, separate `/wikicommit-generate` invocation (with no memory of this run) could discover. If content generated in this run ends up using a `type:` string with no dedicated schema file regardless (e.g. because Pass 2b found nothing but Pass 2c still needs `ambiguous: true` for some other reason), `wikicommit-schema-propose`'s `check_schema_coverage.py`-based scan remains the post-hoc safety net (see that Skill's Notes) — but **not** for a declined candidate that fell back to an already-covered installed type (e.g. `schema:DefinedTerm`): `check_schema_coverage.py` only detects `type:` strings with *no* dedicated schema file, so it cannot tell a declined-then-fell-back-to-`DefinedTerm` page apart from a page that was always meant to be `DefinedTerm` (Issue #447's documented limitation, `docs/DesignDoc-skills.md` §11.6) — do not suggest `/wikicommit-schema-propose` as a way to reconsider a declined Pass 2b candidate; see the Completion Notice section below for the guidance to give instead.

#### Pass 2c: Entity Extraction (LLM → JSON)

Ask the LLM to analyze the extracted text and return **only** the following JSON (no Markdown code block wrapper):

```json
{
  "summary": "2-3 sentence summary of the source's content, in <primary_lang>. If any entities were excluded for theme mismatch, briefly note the reason here too.",
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
      "title": "児童手当の申請手続き",
      "slug": "child-allowance-application",
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

The last example illustrates two things at once: `expires_at` (the source text states multiple deadlines for different disbursement schedules — "8月支給分は7月1日、12月支給分は11月1日、4月支給分は3月1日" — so `2026-07-01`, the earliest of the three, was chosen per the multi-deadline rule below, while the full breakdown still goes into the page body as usual) and the outcome of a Pass 2b approval: this entity is generated directly as `schema:GovernmentService`, the type approved and added to `.wikicommit/schema/` moments earlier in Pass 2b for this exact source, rather than falling back to a generic `schema:HowTo`.

The `kilimanjaro-coffee` example illustrates `coverage_gap_note` (Issue #284): the source text states the coffee's growing altitude, but `.wikicommit/schema/DefinedTerm.md`'s `properties:` block has no field for it, so the LLM records the gap in one sentence instead of silently dropping it or inventing a frontmatter field.

Note that the example above mixes English (`exclude_note` on `Unrelated Corp`) and Japanese (`coverage_gap_note` on `kilimanjaro-coffee`) purely to illustrate several unrelated rules side by side — in an actual run all of `summary`, `exclude_note`, and `coverage_gap_note` must share a single language, `<primary_lang>` (Issue #314; see the rules below).

Provide the LLM with the following context:
- Full extracted text
- List of schema type filenames under `.wikicommit/schema/` (with their `wikicommit.base` values) — **re-scan the directory after Pass 2b**, so any type just added there is available as a candidate here
- `wikicommit.granularity` rules from each schema file
- The `properties:` field list (the keys under each schema file's `properties:` block) from each schema file (used for `coverage_gap_note` detection below)
- Existing pages under `.wikicommit/entity/<primary_lang>/` (title + path) — **include both pages already on `main` and pages written during this run** (scan the directory on disk; do not use `git ls-files` — it only sees tracked files and will miss pages written earlier in this run; do not use `git status`)
- Body section of the ingest management file (used as additional instructions for the LLM)
- The `schema:` field from the ingest management file, if present (e.g., `schema: schema:Person`). When provided, instruct the LLM to treat this as a strong type preference and use it unless the source content clearly contradicts it.
- The `theme` value obtained from `config.yml`. If non-empty, instruct the LLM to set `action: exclude` on entities unrelated to `theme`. If `theme` is empty, instruct the LLM not to use `exclude` at all — every entity must be `create` / `update` / `ambiguous`.
- The current list of type strings already in use by wiki pages that have no dedicated `.wikicommit/schema/` file yet: run `python .wikicommit/scripts/check_schema_coverage.py` once per run and include its `UNCOVERED:` lines. This helps the LLM reuse an existing not-yet-schematized type string for the same concept instead of coining a new one (convergence is encouraged, not guaranteed — see `check_schema_coverage.py`'s own exact-match-only design note). If the list is empty (e.g. first run), omit this from the context.

Set the `lang` field to the `primary_lang` value obtained from `config.yml` for all entities.

Rules:
- Set `slug` following this priority order (Issue #193 — the file name must remain a language-neutral English identifier per CLAUDE.md's WikiLink convention, not a phonetic transliteration of the source language):
  1. Common nouns / concept terms → translate to English (e.g. `キリマンジャロコーヒー` → `kilimanjaro-coffee`; `kirimanjaro-koohii` is a transliteration and not acceptable).
  2. Proper nouns (people, organizations, places, etc.) that have an established English spelling → use that spelling (e.g. `スターバックス` → `starbucks`; `sutaabakkusu` is not acceptable).
  3. Proper nouns with no established English spelling → romanize (e.g. `山田太郎` → `yamada-taro`).
- **Source-as-entity candidates (Issue #475)**: when Pass 2a flagged the source document itself as a citable standalone work, include it as an ordinary entity in this array — its `title` is the work's own original title *verbatim, in whatever language the source itself uses* (e.g. the paper's actual published title), not a concept discussed within it and not translated into `<primary_lang>` — a citable work is identified by its real title, and translating it would defeat the citability this entity exists to capture (this is a narrow, deliberate exception to the general "entity content is written in `<primary_lang>`" rule; the page's `lang` field and body content still follow `<primary_lang>` as usual, only the `title` value itself stays verbatim). `slug` follows the same priority rules above applied to that original title; `type` is whatever Pass 2b resolved for it, or the nearest fitting `installed schema/` type if Pass 2b found nothing. It participates in `action`/`existing_path`/`ambiguous`/`exclude` exactly like any other entity, and nothing about `sources:` changes for it — its page's `sources` is simply the one-element list wrapping this ingest source, same as any other `action: create` entity (Pass 3 step 5 below). This entity is *in addition to*, not instead of, the concepts/people/organizations Pass 2c extracts from within the source as usual.
- Always generate `summary` (2-3 sentences), regardless of whether `theme` is set. This should match the Pass 2a summary unless something in the fuller entity-extraction pass changed the LLM's read of the source — do not treat Pass 2a's summary as merely a draft to diverge from.
- Set `action: update` and `existing_path` if a page with the same type and slug already exists — **scan the directory on disk** (do not use `git ls-files`; it only sees tracked files and will miss pages written by earlier sources in this run). A page written by an earlier source in the same run must be detected as `action: update`, not `action: create`.
- Set `ambiguous: true` when the LLM cannot confidently determine the type; include candidates in `alternatives`
- Skip entities with `ambiguous: true` during page generation. **Immediately** notify the user (console output) with the entity's `title`, candidate `alternatives`, and the source ingest file at the moment of detection — a later source in the same run may abort processing (e.g., missing prerequisite skill, `config.yml` missing, extraction failure) before the Completion Notice is reached, so this notice must not depend on the run completing. Also append the entity to a running list so all detections can be rolled up together in the Completion Notice below.
- Set `action: exclude` (only when `theme` is non-empty) for entities the LLM judges unrelated to `theme`. Set `exclude_reason: "theme_mismatch"` and a short `exclude_note` explaining why, written in `<primary_lang>` — the same language as `summary` (Issue #314; do not let the agent's session/UI language leak in here, which is what caused `## Summary` to mix languages in the `llm-agent-research-wiki` pilot). No human confirmation is needed for `exclude` (unlike `ambiguous`) — it is applied automatically and silently, recorded only in the management file's `## Summary` (see below) and the Completion Notice.
- Set `expires_at` to a concrete `YYYY-MM-DD` date only when the source text explicitly states a calendar date after which the entity's content is expected to be stale — an application deadline, a fiscal-year-bound validity period, a stated expiration date, etc. (Issue #279 — this field previously went unused because Pass 2 never surfaced source-stated dates as a candidate.) Otherwise leave it `null`; never guess or infer a date that is not written in the source (e.g. do not translate a vague "来年度まで" into a specific date), and never derive it from unrelated context like the source's publication date. If the source states several distinct dates that could each plausibly apply to the entity (e.g. different deadlines per sub-case, as in the `HowTo` example above), set `expires_at` to the **earliest** of them — `expires_at` exists to prompt a re-check by the review process (`check_expires.py`), and it is safer to flag content for re-review too early than too late; the full breakdown of all the dates still belongs in the page body, which this field does not replace.
- Set `coverage_gap_note` (Issue #284) to a **single sentence** when the source text contains a concrete, domain-specific attribute for this entity (e.g. target age range, required tools, jurisdiction) that has no corresponding field in the entity's type schema's `properties:` block. If an entity has multiple such gaps, summarize them all in one sentence (do not use an array — follow the same single-string design as `exclude_note`). This applies only to `create`/`update` entities (never `exclude` or `ambiguous` ones). This is evidence-gathering only: never write to `.wikicommit/schema/` and never invent a new frontmatter field to hold the value — the gap information still belongs in the page body as usual, unaffected by this note. Leave `coverage_gap_note` `null` when nothing is missing, which is expected to be the common case. When non-null, write it in `<primary_lang>` — the same language as `summary` (Issue #314; same reasoning as `exclude_note` above).
- After obtaining the JSON, write its `summary` field into the ingest management file's `## Summary` section: create the section (`## Summary` heading followed by the text) if it does not already exist, or overwrite its existing contents if it does. If one or more entities have a non-null `coverage_gap_note`, append them to the same `## Summary` write, one sentence per entity (e.g. `"「キリマンジャロコーヒー」: 産地の標高（1,600〜2,000m）の記載があったが DefinedTerm.md の properties フィールドに受け皿がないため本文にのみ記載"`) — this is the same write, not a separate step, so it must land in the same overwrite as `summary`. Since `exclude_note`/`coverage_gap_note` are already required to be in `<primary_lang>` (same as `summary`, see above), this write never needs to translate anything to make the section consistent — do not translate at write time either. **Never modify a `## User Notes` section** if present — that section is hand-written by a human and must be preserved verbatim.

  > **Heading labels are always fixed English, regardless of `primary_lang`** (Issue #405 — a `primary_lang: en` pilot found the `## サマリ`/`## ユーザーメモ` heading labels hard-coded in Japanese even though the `summary` body text itself was correctly written in English per Issue #314). The ingest management file is an internal bookkeeping file under `.wikicommit/source/`, not reader-facing wiki content, so it is not localized: always write `## Summary` and `## User Notes` verbatim, never a translated or `primary_lang`-dependent heading. Pre-existing management files generated before this change keep their old `## サマリ`/`## ユーザーメモ` headings as-is (no automatic migration, same "both forms may coexist" policy the ingest layout itself already follows — `docs/DesignDoc-data.md` §4.3); only newly written/overwritten `## Summary` sections use the new heading. If a management file still has the old `## サマリ` heading, treat it as the same section (overwrite it in place rather than adding a second, redundant `## Summary` section) — but do not rename an untouched `## ユーザーメモ` heading you are not otherwise touching, since that section must be preserved verbatim per the rule above.

For `action: update` entities, read the existing page with the Read tool and add it as additional context for Pass 3.

### Pass 3: Page Generation (File Boundary Protocol)

**Guard**: before generating any page for this source, if `source.type` is `url` or `wikicommit`, re-read the management file and confirm `source.hash` is non-empty (not `""`). This should already hold — Pass 1's hash write-back step (above) fails the source before reaching Pass 2 otherwise — but re-check here as a safety net (e.g. against a management file left over from before this guard existed). If `source.hash` is still empty, mark this source `status: failed`, write a reason to the management file's `## Failure Reason` section (create it if absent, overwrite if present — e.g. `"source.hash was still empty when Pass 3 was reached; the source could not be confirmed as fetched during Pass 1 (safety-net guard)."`) in English regardless of `<primary_lang>` (same reasoning as the Pass 1 extraction-failure case above — Issue #408), notify the user, and skip Pass 2–4 for it entirely; never write a page whose `sources[].hash` would be empty.

For each entity where `ambiguous: false` and `action` is `create` or `update` (skip `action: exclude` entities entirely — no page generation, no review; they were already recorded in the Pass 2 `## Summary` write):

1. Derive the schema file path from the entity's `type` field:
   - Strip the `schema:` prefix: `schema:Person` → `Person`
   - For custom types, keep the sub-path: `schema:custom/Decision` → `custom/Decision`
   - Schema file path: `.wikicommit/schema/<derived-name>.md`
   - If the schema file does not exist, fall back to `.wikicommit/schema/default.md`
   - Parse the schema file as Markdown-with-frontmatter. `wikicommit:` key = schema instructions (do **not** include in generated pages). Other top-level frontmatter keys (e.g. `title`, `type`, `lang`, `sources`, `tags`) + the nested `properties:` block (Issue #495 — Schema.org-vocabulary-backed, type-specific fields such as `description`/`affiliation`/`jobTitle`) + Markdown body = wiki page template structure — fill in actual values; do not copy placeholder empty strings or empty lists verbatim. Keep `properties:` nested exactly as the schema file has it — do not flatten its keys up to the top level of the generated page's frontmatter.
   - Cache the parsed schema in memory; read each schema file only once per run even if multiple entities share the same type. For a standard (non-`custom/`) type, also resolve and cache the Schema.org `rangeIncludes` classification of every key in that type's `properties:` template — once per type, not once per entity — via:

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
       ... --show-range
     ```

     Each `--property` value is passed through its own quote-delimited heredoc, not a plain double-quote embedding (`docs/DesignDoc-skills.md` §11.7): these key names come straight out of `.wikicommit/schema/<Type>.md`, a human-editable file this Skill only reads, so — unlike `<Type>` here, which the standard-type path already resolves through `check_schema_org_type.py --type <Type>` verification before use — they have not themselves undergone any upstream validation before being embedded into this exact command line. Pass every `properties:` key from the template. This is the same verification call Pass 2b already runs when adding a new type (see that step's own `--property` invocation, updated to the same heredoc form); here it also runs for the pre-installed base types (which never went through Pass 2b). See "Property-value WikiLinks" below for how the resulting `RANGE:` lines are used. Skip this call entirely for `custom/` types — they have no Schema.org vocabulary entry to query (same reasoning as `properties:`'s own domainIncludes check, `validate_frontmatter.py`).

   **`properties:` vs. body placement (Issue #495)**: `properties:` may only hold short, structured values a source states as a single fact — a date, a proper noun, a URL, a reference to another entity (as a WikiLink). Multi-sentence explanation, context, causal reasoning, or synthesis across multiple facts belongs in the body instead, even when a matching Schema.org property name technically exists (e.g. a lengthy `description` is not a reason to also try to cram the same material into another property). Keep `properties.description` itself to a 2-3 sentence summary — the fuller account belongs under a body heading (e.g. `## Background`). This is domain-independent, applies regardless of the wiki's theme, and is close to a restatement of what the existing template body-heading structure (e.g. `## Background`, `## Usage`) already implies rather than a new constraint.

   **Property-value WikiLinks (Issue #496)**: for each `properties:` key, decide whether its value should be written as a `[[Type/slug]]` WikiLink to another entity page rather than a plain scalar, based on the `RANGE:` classification cached in step 1 above:
   - *Entity-only* (e.g. `affiliation` → `Organization`, `birthPlace` → `Place`): if the value names an entity that is (or should become) its own page, write it as a WikiLink. Do not force a WikiLink for an incidental mention that fails the *referenced* entity's own type's independent-subject bar (e.g. Person.md/Organization.md's "named only as someone's employer/affiliation, no independent facts stated" rule) — write the plain name as text in that case instead, same as an incidental mention in body text would be handled.
   - *DataType-only* (e.g. `sameAs` → `URL`): never WikiLink this property's value — always a plain scalar.
   - *Mixed* (e.g. `jobTitle` → `DefinedTerm` or `Text`; `description` → `TextObject` or `Text` — despite the name, `TextObject` is an entity type, not a DataType): WikiLink only when the value genuinely names a distinct entity that independently qualifies for its own page; otherwise write it as a plain scalar. Most `jobTitle`/`description` values ("シニアエンジニア", a one-sentence summary) are plain text, not a `[[DefinedTerm/...]]`/`[[...]]` reference — only WikiLink when the source itself treats the value as referring to a separately citable/definable entity worth its own page.

   **Apply this uniformly across every Entity-only/Mixed property of the type — a `granularity` entry or an inline `[[Type/slug]]` placeholder calling out one specific property is a human-readability aid, not a scope-narrowing statement (Issue #523)**: some type templates additionally reinforce this rule for one property, either in `granularity` prose (e.g. `BlogPosting.md`/`NewsArticle.md`'s `author` line) or via a `properties:` placeholder already written as `"[[Type/slug]]"` instead of `""` (e.g. `Organization.md`'s `founder: "[[Person/slug]]"`). `Issues/registered/p3-205-property-wikilink-publisher-inconsistency.md` (the origin of Issue #523) found two otherwise-comparable generated pages that disagreed on WikiLinking `publisher` even though it has the identical Entity-only classification as `author` (both resolve to `Organization`/`Person` via `--show-range`) and `publisher` had no such reinforcement on either template — a small-sample observation, not a statistically validated rate difference, but the reinforcement asymmetry is the only difference between the two properties. Fixed for `publisher` (both templates) and, since checking the other base-type templates the same way turned up the identical unreinforced-Entity-only-property shape, also for `Organization.md`'s `foundingLocation`, `Person.md`'s `affiliation`, `Place.md`'s `containedInPlace`, and `Event.md`'s `organizer`/`performer`. Whether a property happens to carry this kind of reinforcement is not something to infer meaning from either way — the RANGE classification from step 1 above is the complete and only input to this decision.

   A referenced entity does not need to already have a page for the WikiLink to be valid: `check_wikilinks.py` reports an unresolved WikiLink as a non-blocking WARNING (Issue #340) and `check_wanted_pages.py` tracks it as a WANTED page, exactly as an unresolved WikiLink in body text already works today — both scripts scan the whole file as raw text and do not distinguish frontmatter from body (confirmed for `check_wikilinks.py`/`check_orphans.py`/`check_wanted_pages.py`; no changes were needed to any of them for this Issue). Do not let "the target page doesn't exist yet" stop you from writing the WikiLink. This is advisory, not mechanically enforced: `validate_frontmatter.py` does not require an entity-range property's value to be a WikiLink (Issue #495's `properties:` `domainIncludes` check verifies the *key* belongs to the type; it says nothing about the *value*'s shape) — whether to actually write one is left to this generation-time judgment call, same as any other body-text WikiLink decision.

   **Granularity discipline (Issue #337)**: the page body and `description` must match the schema template's abstraction level, not the source's level of detail. `.wikicommit/schema/<Type>.md`'s body template already encodes the intended abstraction — e.g. `DefinedTerm.md`'s "(Precise one-paragraph definition of the term)" means a single dense paragraph, not an exhaustive account — and this holds regardless of how much raw detail the source text makes available. This matters most when the source is programming language source code (`.py`/`.kt`/`.ts`/etc., typically extracted via the "その他 → markitdown" fallback — see the extraction routing table in `docs/DesignDoc-skills.md` §11.6): source code already reads as prose-adjacent, so the natural failure mode is transcribing implementation internals (internal function/variable names, regex construction logic, class field layouts) straight into the page instead of summarizing them. This actually happened in the `Paperwork-Navigator-wikicommit-pilot` pilot — ingesting a `.kt` file produced `DefinedTerm` pages that read as implementation notes for the developers who wrote the code, not concept definitions for a general reader. When the source is code, describe the concept, its purpose, and how it's used at a level a non-programmer reader can follow; do not name internal functions/variables or restate algorithm steps in prose. Implementation-level detail is not lost — it stays reachable via `sources` (a reader who needs it can open the source file directly) — it just does not belong duplicated into the page body.

   **Thin-source discipline (Issue #428)**: the instruction above to "fill in actual values" does not mean every template heading must be padded into a full-looking section regardless of how little material the source actually contains. When the source does not contain enough material to substantively fill a template section (e.g. no chronological activity/affiliation history for a Person's `## Background` — only a single quoted remark), write only what the source actually supports, even a single accurate sentence, rather than padding with generic, contentless filler to make the section look complete. A short, honest section is preferable to a padded one that restates the same fact across multiple headings — this happened across all 5 `Person/` pages in the `ai-driven-dev-wiki` pilot, where `## Background` converged on the same boilerplate phrasing regardless of how much the source actually said about each person. This is the mirror image of granularity discipline above: that rule reins in over-detailed sources, this one reins in under-filling instructions being read as "manufacture content regardless of source thinness."

   **Representativeness across concrete implementations (Issue #451)**: when the source material describes multiple distinct, concrete implementations or processes that each embody the same broader concept (e.g. several organizations' own named workflows for the same general practice), do not write the page's definition around one specific implementation's details and relegate the others to secondary variants or comparisons — this happens most easily when one implementation is the most detailed or the most widely known among the sources ingested. Follow the schema's `granularity` guidance where it addresses this (e.g. `DefinedTerm.md`, Issue #451); in general, state the concept at the level of generality actually shared across the implementations, and present multiple concrete implementations side by side rather than implicitly crowning one as the standard the others deviate from.
2. Ask the LLM to generate wiki page content using the following **file boundary protocol** format:

```
---FILE: .wikicommit/entity/ja/Person/yamada-taro.md---
---
title: "Taro Yamada"
type: "schema:Person"
lang: ja
tags: [engineer]
sources:
  - type: path
    path: raw/paper-2024.pdf
    hash: sha256:abc123...
review_status: pending
generated_at: "2026-06-27"
generated_by: "<current model ID>"

properties:
  description: "Senior engineer at CompanyA"
  affiliation: "[[Organization/companya]]"
---

Taro Yamada is a senior engineer at CompanyA...

## Background
...
---END FILE---
```

   Note: `generated_at` must be the actual run date in `YYYY-MM-DD` format (e.g., today's date), not the literal string `"YYYY-MM-DD"`.

   If the entity's `expires_at` from Pass 2 is non-null, include an `expires_at: "<that date>"` line in the frontmatter (`docs/DesignDoc-data.md` §4.1). If it is `null`, omit the `expires_at` field from the frontmatter entirely — do not write `expires_at: null` or `expires_at: ""`, since the field is optional and its absence is what `validate_frontmatter.py` and `check_expires.py` expect for "no known expiration".

   `tags`: follow the rules in `docs/DesignDoc-data.md` §4.1 (Issue #275) — `tags` is for cross-page filtering, not a restatement of this page's own identity. Do not include a tag identical or near-identical to the entity's own `title` (e.g. do not tag a page titled "認可保育所" with `認可保育所`), and do not include a tag that only restates what `type` already expresses (e.g. do not tag a `schema:Person` page with `person`/`人物`). Only include tags for concepts that are meaningfully shared across multiple pages (field, category, technology, etc.). If a candidate tag names a specific vendor or product, confirm the concept is actually specific to that vendor before including it (Issue #430) — if the vendor is merely one of several sources discussing the concept, and the concept itself is not that vendor's own (e.g. an industry-general term, or one coined/proposed by a different party), do not tag the page with that vendor's name.

   **Attribution accuracy (Issue #429)**: a page's claims are only checked for *truth* by Pass 4, not for whether they're attached to the right origin — attribution errors have to be prevented here, at generation time. When the source text itself attributes a quote or specific wording to a distinct party (e.g. a source article that quotes or paraphrases a third party's documentation, blog post, or public statement), carry that attribution into the page body rather than collapsing it into the page's own voice or attaching it to a different party mentioned nearby in the same paragraph. This matters most when a single paragraph discusses more than one origin (e.g. both "Party A's own documentation" and "a blog post about Party A's tool written by Party B") — keep each direct quote or specific claim tied to whichever origin the source text itself assigns it to; do not let it drift to the other party just because both are discussed together. Separately: when a definition, framework, or formulation is not an established/consensus term but is presented by the source as one specific party's own proposal (a single paper, blog post, or vendor's argument — not something the source frames as general or widely agreed), phrase it in the page as an attributed claim (e.g. "X proposes that...", "According to X, ...") rather than as unqualified fact. Do not strip the attribution and state a single party's proposal as if it were a settled, general truth.

   **Naming vs. inventing (Issue #451)**: when the source describes one party naming or coining a term for a practice/technique ("X calls this Y", "X coined the term Y for the practice of..."), write only that — do not upgrade it into a claim that this party invented, created, or originated the underlying practice itself. These are different, independently-verifiable facts even when the source discusses them in the same sentence; conflating them overstates what the source actually says. If the source is genuinely ambiguous about whether the party invented the practice or only named an existing one, phrase the page's claim at the same level of certainty the source itself uses — do not resolve the ambiguity toward the stronger claim.

   **Secondary citation discipline (Issue #473)**: when the source text itself discusses, quotes, summarizes, or links to a *distinct* document — a different article, post, or report the current source mentions in passing, separate from the source document Pass 3 is generating this page from — do not restate that other document's own specific date, title, or individually-attributed detail as a page claim. The current source's mention of it is itself only secondhand (a citation of a citation, sometimes called 孫引き); the `sources` entry available to this generation is the document currently in front of Pass 3, not the document it refers to. Write the claim only at the level of generality the current source actually supports (e.g. "in an earlier post, X also described Y" rather than "in a March 19 post titled Z, X described Y") unless the referenced document has separately been registered as its own `sources` entry for this entity (i.e. it was itself ingested as a source, not merely mentioned by another source). This is a stricter version of the Naming vs. inventing check above: that one guards against overstating what act a party performed; this one guards against borrowing a secondary document's own identifying details (date, title) without that document actually being present among `sources`.

   **Source-entity WikiLinks (Issue #475)**: when this page's content is substantively drawn from a source whose own document Pass 2's source-as-entity judgment generated as a *separate, different* entity page in this same run (e.g. an arXiv paper, an official product-announcement post) — this never applies to the source-entity page's own body referencing itself — mention that source-entity page via a natural WikiLink in the body where it reads naturally (e.g. "as reported in [[ScholarlyArticle/vibe-coding-survey]]") rather than only a bare textual reference. This is the natural complement to `sources:` (hash-based, for audit/freshness) — it does not replace `sources:`, and nothing about `sources:` changes to accommodate it.

3. For `action: update` entities, the LLM must merge new information into the existing page:
   - Update content fields (`description`, body text, `tags`, etc.) with new information from the source
   - Preserve `review_status: reviewed` without overwriting; only update `review_status` if the existing value is `pending`
   - Update `generated_at` and `generated_by` to reflect this generation run
   - Append the new source to the `sources` list only if no entry with the same `path` (or `url`) already exists. If an entry with the same `path`/`url` is already present, update that entry's `hash` instead of appending a duplicate.
   - `expires_at`: if Pass 2 returned a non-null `expires_at` for this entity, set/overwrite the page's `expires_at` with it (a source-stated date takes precedence, since it reflects the most recently ingested information). If Pass 2 returned `null`, leave the existing page's `expires_at` untouched either way (don't add one, and don't clear one a human or an earlier run may have set) — `null` here only means "this source didn't mention a date," not "there is no expiration."
   - **Attribution accuracy across merged sources (Issue #429)**: the existing page content being merged into may already carry claims/quotes attributed to whichever source produced it earlier. When folding the new source's material into the same paragraph or section, keep each claim tied to whichever of the (now multiple) sources actually said it — do not let a claim's attribution silently shift to the other source just because they now sit next to each other. If a single-source formulation from the prior version is retained as-is, its attribution phrasing must be preserved, not dropped, even if the new source's material is unattributed general description.
4. Set `generated_by` to the **currently running model ID** (e.g., `claude-sonnet-4-6`). Use the actual model ID in use, not a hardcoded value.
5. For `action: create` entities: set the `sources` field as a **one-element list** wrapping the ingest management file's `source` object — e.g., `sources: [{type: path, path: raw/paper-2024.pdf, hash: sha256:…}]`. Do not recalculate the hash. For `action: update` entities, see step 3 above.
6. **Do not call the Write or Edit tools yet.** Keep the generated content as context for Pass 4 review.
7. The execution order and parallelization of entities is left to the agent's judgment.
8. **Bare URLs in body text**: when the body text contains a bare URL (not already in Markdown link syntax `[text](url)`), surround it with a space on both sides, or wrap it in angle brackets (`<https://example.com>`) to make the URL boundary explicit. This matters especially when non-English prose (e.g. Japanese) follows the URL immediately with punctuation or a particle with no space — a Markdown parser can then swallow the following characters into the URL itself, producing a broken/percent-encoded link that `lychee` reports as unreachable and `markdownlint-cli2` flags as MD034. When a URL is immediately followed by non-space text, prefer the angle-bracket form.
9. **Never write raw HTML tags** (`<script>`, `<iframe>`, `<div>`, `<br>`, etc.) into the page body. Images, external-URL images, video files, and YouTube all embed with standard Markdown image syntax alone (`![alt](path-or-url)` — see CLAUDE.md's 画像・動画埋め込み rule and `docs/DesignDoc-publish.md` §8.6); there is no case in which a raw HTML tag is the right way to express something in a WikiCommit page. This applies even when the source document itself contains raw HTML (e.g. an ingested web page) — extract the meaning, never copy the markup verbatim. `.wikicommit/scripts/check_raw_html.py` enforces this as a blocking `wikicommit-merge` quality gate (Issue #377), so a page containing a raw HTML tag will fail to merge regardless; treating it as a generation-time rule here catches it before that point and avoids a wasted retry cycle.

### Pass 4: Source Integrity Review (Review Subagent)

For each generated page (content is carried as context from Pass 3):

**Evidence binding (Issue #442)**: every check below (steps 1–3) is a *source-to-claim* check, not a *fact* check — the subagent must decide PASS/FAIL based solely on whether the literal text of the source document in front of it states the claim, never on the subagent's own pretrained/world knowledge of whether the claim happens to be true. A claim that is well known to be true (a famous person, a widely reported event, a well-known technical fact) must still **FAIL** if the source text does not actually contain it — most importantly when the "source text" is itself boilerplate (e.g. a JS-rendered page's login/navigation shell with no article body, per Issue #425's known-JS-shell-domain case) that happens to be about a well-known topic. Conversely, an obscure or surprising claim passes if the source text does state it. Instruct the subagent explicitly not to fill in gaps in the provided source text from its own training data.

1. Launch a subagent to verify that the page's key claims are supported by the source document (hallucination detection). If the page's frontmatter has an `expires_at` value, treat it as a claim to verify like any other: the source text must state that exact date (or, per the multi-deadline rule in Pass 2, be the earliest of several dates the source states) for an entity this page covers. An `expires_at` invented or misread from the source fails review the same way a fabricated body-text claim would.

   **Granular fact verification (Issue #451)**: "key claims" includes individually-checkable concrete details embedded in body prose — a stated date, a specific publication/article title, a version number, a named event — not only the page's overall thesis. A claim that is broadly correct but wrong in one such checkable detail (e.g. the general fact that a named person wrote about a topic is true, but the date stated for that publication is not the date the source states) must still **FAIL** — approximate correctness on the broad claim does not excuse an inexact specific detail (`type: HALLUCINATION`). Separately, when a body claim cites, names, or clearly implies a specific document (an article title, a specific publication event) that is not actually present among the page's `sources` entries, this is a **FAIL** (`type: MISSING_SOURCE`) even if the surrounding narrative sounds plausible — the reviewer must not accept "this is the kind of thing this source would say" as a substitute for the cited document actually being present.

   **Naming vs. inventing (Issue #451)**: when the source describes one party giving a name/label to an existing or emerging practice ("X calls this Y", "X coined the term Y"), a page that instead states X *invented*, *created*, or *originated* the underlying practice/technique itself is a **FAIL** (`type: CONTRADICTION`) even though both claims may share the same surface subject — naming a practice and originating it are different, independently-verifiable facts, and the source stating one does not license inferring the other. This is a separate check from Attribution correctness (step 2 below): that step catches wording attributed to the wrong *party*; this one catches the wrong *kind of act* attributed to the correct party.

   **Secondary citation dates/titles (Issue #473 — closes a gap in the Issue #451 MISSING_SOURCE check above)**: apply the MISSING_SOURCE check above even when the specific date/title being verified was not asserted outright by the page but only paraphrased from the current source's own passing mention of a *different* document (e.g. the current source links to or briefly describes an earlier or later article). The test is not "does some source in front of the reviewer say this" but "is the specifically-dated/titled document the page names actually present among this page's own `sources` entries" — the current source merely mentioning another document is not the same as that other document having been ingested as a source. Do not let "this is the kind of detail the source's own linked material would plausibly confirm" substitute for the cited document actually being one of `sources`; this is exactly the loophole that let a secondary citation slip past the Issue #451 check in practice (Issue #473).

   The subagent returns its verdict in the agent-to-agent JSON format defined in `docs/DesignDoc-data.md` §4.6 — `result: "PASS" | "FAIL"`, plus an `issues` array (one entry per defect found: `type` one of `HALLUCINATION`/`CONTRADICTION`/`MISSING_SOURCE`, `claim`, `source_file`, `source_lines`, `source_quote`, `instruction`). This JSON is agent-to-agent only (§4.6 — never written to disk or Git).
2. **Attribution correctness (Issue #429)**: truth-checking alone (step 1) cannot catch an attribution swap, because a misattributed claim can still be true according to *some* source — just not the one the page names. For every claim the page presents as belonging to a specific named origin (a direct quote, or a claim phrased as "X says/argues/proposes..."), verify that the *specific* cited origin actually states it — not merely that some source in the source material does. If the source material shows the wording actually came from a different party than the one the page names (e.g. two organizations are both discussed in the source, and the page attributes Party B's wording to Party A), this is a **FAIL** even though the claim's content is accurate, because the attribution itself is the defect. Record it in `issues` the same way as step 1 (`type: CONTRADICTION` fits best — the page contradicts the source's actual attribution — with `instruction` stating which party the wording actually belongs to).
3. **Unattributed single-source formulations (Issue #429)**: separately, check whether the page states a definition, framework, or formulation as unqualified general fact when the source material shows it is actually one specific party's own proposal (a single paper, blog post, or vendor's argument) rather than an established or widely-agreed term. If so, this is a **FAIL** — the fix is not to remove the content but to add attribution phrasing (per the Pass 3 instruction above), so a retry (step 4 below) can produce a properly-attributed version rather than a factually-identical but still-misleading one. Record it in `issues` (`type: CONTRADICTION`, `instruction` stating to add attribution phrasing rather than remove the content).
4. If the review result is **FAIL** (for any of the above reasons), regenerate the page (up to `generate.max_retries` times from `.wikicommit/config.yml`; default: 2). **Feed the subagent's findings into the retry (Issue #452)**: pass the full `issues` array from step 1 — most importantly each entry's `instruction` — back into the Pass 3 regeneration prompt as explicit, itemized corrections for this attempt, alongside the same source text and context Pass 3 used originally. Do not regenerate from a bare "the previous attempt failed review" instruction with no detail — two consecutive FAILs on the same source for the same underlying defect (e.g. the same inferential gloss re-added both times) is exactly the failure mode this step exists to prevent, since it indicates the retry never actually saw what was wrong with the attempt before it.
5. If the retry limit is exceeded, add the page to `failed_pages` and skip writing it to disk. Also append this entity — its `title`, `type`, the ingest management file's path, and (for `action: update` entities) the pre-existing page's `existing_path`, which was left unchanged — to a running list, the same pattern Pass 2 already uses for `ambiguous`/`exclude` entities, so every such failure can be rolled up together in the Completion Notice below (Issue #452 — previously this information only ever reached the ingest management file's `failed_pages`/`## Failure Reason`, invisible from both the page itself and this run's own summary).
6. Write pages that **passed** review to the working directory using the Write tool. **Do not commit — leave the files as untracked/modified in `git status`.**
7. Update the ingest management file's status locally (do not commit). This step only ever updates *this* source's own management file — a different, already-registered management file whose content happens to also be cited by a page this source's Pass 3/4 touched is deliberately left alone here and reconciled instead by the deterministic script in the "Ingest Status Reconciliation" step below (Issue #474 — an earlier version of this step tried to reconcile such other files inline, using this same per-source Pass 2/4 outcome; code review found that unsafe, since a different file's correct status can depend on entities this source's Pass 2 never produced). Evaluate the following rules **in order** and apply the first one that matches (they are not independent conditions — later rules assume all earlier ones didn't match):
   - Pass 2 returned no entities at all, or every entity's page was generated successfully (no `failed_pages`, no `ambiguous: true`, no `action: exclude`) → `status: generated`, record `generated_pages` list and `last_generated_at`. Delete the `## Failure Reason` section if present (Issue #408 — a prior run's failure has now been resolved by this successful run; a stale reason left in place would contradict the current `status`).
   - One or more entities exist, and **all** of them were `action: exclude` in Pass 2 → `status: excluded`, no `generated_pages` (the exclusion reasons are already recorded in `## Summary` from Pass 2; the Pass 3/4 loops naturally have nothing to iterate over for this source). Delete `## Failure Reason` if present (same reasoning as above).
   - One or more entities exist, and **all** of them were `create`/`update` entities that were attempted and failed (no `ambiguous: true` entities, no `action: exclude` entities, zero successes) → `status: failed`. Write a reason to `## Failure Reason` (create it if absent, overwrite if present) summarizing which entities failed and why in one sentence each — e.g. `"3 of 3 entities failed source-integrity review after 2 retries each (hallucinated or unsupported claims). See the wikicommit-generate session output for the full per-claim review detail — that detail is agent-to-agent only and is not persisted here, per docs/DesignDoc-data.md §4.6."` Write it in English regardless of `<primary_lang>` (Issue #408; same reasoning as the Pass 1/Pass 3 cases above).
   - Anything else (e.g. one or more `ambiguous: true` entities regardless of success count, or any mix of succeeded/failed/excluded entities) → `status: partial`, record `generated_pages` and `failed_pages`, and `last_generated_at` (an ambiguous or excluded entity never had a page written, so it excludes the source from `generated`). Delete `## Failure Reason` if present (same reasoning as the `generated`/`excluded` branches — `partial` is not `failed`, so no failure reason should remain attached to it).
8. Proceed to the next ingest file. `index.md` is rebuilt once for all Type directories after all sources are processed (see below) — no per-source action needed here.

## After All Sources: index.md Update and Completion Notice

### index.md Update (once, after all sources)

After all ingest files have been processed, run:

```bash
python .wikicommit/scripts/rebuild_index.py
```

This deterministically rebuilds `index.md` for every Type directory under `.wikicommit/entity/` from the pages currently on disk (Issue #406) — it scans each directory itself, so there is no need to track which Type directories this run touched, and no risk of the update being skipped or forgotten at the tail end of a long multi-source batch. `status: removed` pages are excluded automatically, and the frontmatter uses the bare Type name for `title` (e.g. `title: "Person"`, not `"Person Index"` — the Explorer tree already conveys that this is a folder, so appending "Index" is redundant, Issue #320). This is a local write only — **do not commit**.

### Ingest Status Reconciliation (once, after all sources; Issue #474)

After the index.md update, run:

```bash
python .wikicommit/scripts/reconcile_ingest_status.py
```

This finds `.wikicommit/source/**/*.md` management files still left at `status: pending` whose `source.hash` is nevertheless already cited in some `.wikicommit/entity/**/*.md` page's `sources[]` — evidence that their content was incorporated into a page during this or an earlier run without their own status ever being written back (the `ai-driven-dev-wiki` round2 pilot that motivated this had 8 such files) — and sets `status: generated` plus `generated_pages` for each. It deliberately never touches `status: outdated` files: `check_ingest_freshness.py` leaves an outdated file's `source.hash` unchanged as the reference point of its *previous* successful generation, so a hash match there means "was generated before the source changed and still needs reprocessing," not "already reconciled" — treating the two the same would silently mask genuine staleness. This is a local write only — **do not commit**. Report how many files this corrected, if any (`RECONCILED:` lines / `reconciled=` count in `SUMMARY:`), in the Completion Notice below.

### Completion Notice

Display a summary of the results (pages succeeded / skipped / failed / excluded). If any entities were skipped for `ambiguous: true` (Pass 2), list them explicitly with their candidate `alternatives` and the source ingest file, and ask the user to confirm the type — e.g.:

```
The following entities were skipped because their type could not be determined. Please confirm the type:
- "Taro Yamada" (candidates: schema:Person, schema:Organization) — source: .wikicommit/source/path/raw/paper-2024.md
```

If any entities were skipped for `action: exclude` (theme mismatch), list them too (no user action required — this is informational, unlike the `ambiguous` list above):

```
The following entities were excluded as unrelated to theme:
- "Unrelated Corp" (theme_mismatch: A personal acquaintance's employer, unrelated to the configured theme) — source: .wikicommit/source/path/raw/paper-2024.md
```

If Pass 2a flagged one or more sources as clearly written in a language other than `primary_lang` (Issue #336), list them too (informational only, no action required — their content is summarized/translated into `primary_lang` as usual):

```
Note: the following source(s) appear to be written in a language other than primary_lang (ja).
Their content will be summarized/translated into ja when generating pages:
- .wikicommit/source/path/docs/privacy-spec.md (appears to be English)
```

If one or more entities were generated as source-entity pages (Issue #475 — Pass 2a judged the source document itself citable as a standalone work), list them too, since they are a page type the user did not explicitly request and may not expect:

```
The following page(s) were generated for a source document itself, not for a concept discussed
within it (Issue #475):
- .wikicommit/entity/en/ScholarlyArticle/vibe-coding-survey.md (source: .wikicommit/source/url/arxiv.org/vibe-coding-survey.md)
```

If Pass 2b added one or more new `.wikicommit/schema/<Type>.md` files during this run, list them too, since they are new local files the user has not yet seen committed anywhere. Annotate each entry with how it was approved per step 3 above — a human answered the prompt, or it was auto-approved with no prompt shown because the run was non-interactive and the candidate cleared the stricter bar (Issue #507):

```
The following Schema.org type(s) were added to .wikicommit/schema/ during this run (Issue #315):
- schema:GovernmentService — approved for "児童手当の申請手続き" (source: .wikicommit/source/path/raw/paper-2024.md)
- schema:Dataset — auto-approved with no human confirmation (non-interactive run, cleared the stricter
  bar — Issue #507) — for the named benchmark "HotPotQA" (source: .wikicommit/source/url/arxiv.org/hotpotqa-paper.md)

These will be included in the next /wikicommit-merge batch (new schema files are picked up
alongside wiki pages — see that Skill's git add scope). Auto-approved entries get no special marker in
the schema file itself. This is not an active review gate — Route A's `wikicommit-merge` batch
auto-merges once its mechanical quality checks pass, with no human approval step in between (Issue #456)
— it is only the same after-the-fact `git log`/PR-diff audit trail every other WikiCommit change relies
on (CLAUDE.md's GitOps principle). Do not describe this as "reviewed before merge" to the user; describe
it as "recorded in git history for later audit" (Issue #507).
```

If Pass 2b step 3's running list has one or more declined type candidates (explicitly declined, or
non-interactively declined for failing the stricter bar), list them too (Issue #491, extended by
Issue #507). By this point in the run, Pass 4 (step 5) has already finished for every source and its own
`failed_pages` list (below) is fully known — cross-check against it so this block is accurate about what
actually happened to each motivating entity: a declined type's motivating entities are not guaranteed to
have become real pages; one may have separately hit `failed_pages` for an unrelated reason (a
source-integrity review failure), in which case say so instead of claiming it "was generated," and drop
it from the "existing installed schema/ type" framing below (it has no page, fallback or otherwise). This
list exists only in this run's own output, never persisted anywhere (Pass 2b step 5). Annotate each
bullet individually with its actual recorded outcome from step 3 (explicit N vs. non-interactive and
failed the stricter bar) — do not use one blanket sentence for the whole list, since different bullets in
the same run can have different outcomes; and do not confuse this block with the auto-approved block
above, which is a different outcome of the same non-interactive path.
**Do not suggest running `/wikicommit-schema-propose` to reconsider these** — its `check_schema_coverage.py`-based
detection only finds `type:` strings with no dedicated schema file at all, which is not the case for an
entity that did get a page (it already has a working, covered type; Issue #447,
`docs/DesignDoc-skills.md` §11.6). This exact wrong suggestion was made in a real non-interactive run and
produced a "No schema coverage gaps found" dead end when the user tried it
(`dev/pilot-ai-driven-dev-wiki-round3.md`) — give the guidance below instead:

```
The following Schema.org type candidate(s) were considered during this run but declined:
- schema:SoftwareApplication — considered for "Claude Code", "Antigravity" (source:
  .wikicommit/source/url/example.com/agents-roundup.md); a human answered N at the prompt. "Kiro" was
  also considered but its page separately failed source-integrity review — see the failed_pages list
  below.
- schema:VideoGame — considered for "Elden Ring" (source: .wikicommit/source/path/raw/gaming-report.md);
  this run is non-interactive/subagent-driven and the candidate did not clear the stricter "obviously
  implied" auto-approval bar (Issue #507).

Entities that did get a page above were generated using an existing installed schema/ type instead
(most likely schema:DefinedTerm). This is not tracked anywhere after this run ends, so
/wikicommit-schema-propose will not find it later — its detection only covers types with no dedicated
schema file, and these entities already have one. To reconsider one of these types: add
.wikicommit/schema/<Type>.md by hand, or re-run /wikicommit-init (its obvious-type judgment may catch it
if config.yml's theme alone clearly implies the type — Issue #490) or /wikicommit-collect next time a
similar source comes up (its Type Proposal step judges from real candidate evidence before registration —
Issue #489).
```

If any entity's page hit `failed_pages` after exhausting `generate.max_retries` (Pass 4 step 5), list them too (Issue #452) — unlike `ambiguous`/`exclude`, this represents an intended `create`/`update` that did **not** take effect, which for `action: update` entities means an existing page was left unchanged with no visible sign anything was attempted:

```
The following pages failed source-integrity review after exhausting retries and were not written
(existing pages, if any, are unchanged):
- "Vibe Engineering" (schema:DefinedTerm, action: update, existing page: .wikicommit/entity/en/DefinedTerm/vibe-engineering.md) — source: .wikicommit/source/url/simonwillison.net/vibe-engineering.md

These are also recorded in each source's ingest management file (`failed_pages` / `## Failure Reason`).
Run /wikicommit-merge next as usual — it will open a tracking Issue per affected source (label:
wikicommit-generation-failure), so this doesn't require watching this run's console output to notice
later.
```

If `reconcile_ingest_status.py` (above) reported `reconciled` > 0, list the corrected files too (Issue #474):

```
The following ingest management files were left at status: pending even though their content is
already in use by a published page — their status has been corrected to "generated":
- .wikicommit/source/url/github.blog/copilot-agent-mode.md → .wikicommit/entity/en/Organization/github.md
```

Then show the next steps:

```
Next steps:
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
```

## Notes

- Do not commit to `main` or any branch
- Do not write to `.wikicommit/schema/`, with one narrow exception: Pass 2b (Issue #315) may write a new `.wikicommit/schema/<Type>.md` file for a candidate that was approved — either by a human answering the Enter prompt in an interactive run, or (Issue #507) auto-approved with no prompt shown because the run was non-interactive and the candidate cleared step 3's stricter bar — it only ever adds a file that wasn't already there, never edits or overwrites an existing schema file
- Do not run `gh pr create` or any PR creation commands
- All file writes go directly to the working directory; `git status` will show them as untracked or modified
- For `type: url` / `type: wikicommit` sources, fetch only the registered `source.url`. Do not run additional `markitdown` calls for links discovered within the extracted content — each source page an operator wants ingested must be registered explicitly via `/wikicommit-generate <url>`.
