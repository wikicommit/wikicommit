---
name: wikicommit-generate
description: Register a source file or URL to .wikicommit/source/ and generate wiki pages locally, or regenerate existing pages under the current generation rules with --regenerate (no Git)
disable-model-invocation: true
---

# wikicommit-generate

Registers a source and generates wiki pages (local writes only) in one run. Performs no Git operations.

## Usage

```
/wikicommit-generate <path|url> [--include <glob>]   # register a source + generate pages in one run
/wikicommit-generate                                  # process every management file still queued (asks first if more than 5)

/wikicommit-generate --regenerate <page-path>         # rebuild one existing page under the current generation rules
/wikicommit-generate --regenerate --type <Type>       # rebuild every eligible page of that type
/wikicommit-generate --regenerate --all               # rebuild every eligible page (asks first if more than 5)
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
| URL (YouTube video) | `markitdown` **plus** `youtube-transcript-api` — without the second package `markitdown` extracts only the title, keywords, runtime and description and drops the transcript, with no error or warning, so the video's actual content never reaches Pass 2 (Issue #574). Only `https://www.youtube.com/watch?v=<id>` links (and the `youtu.be/<id>` / `m.youtube.com` forms that redirect to them) are recognized as videos at all — a `/shorts/<id>`, `/playlist`, channel, or `music.youtube.com` URL is not, and extracts to navigation boilerplate; register the `watch?v=<id>` equivalent instead | `pip install youtube-transcript-api` (in addition to `markitdown` above). Pass 1 checks for this before fetching and stops with this command if it is missing |
| Other (unmatched file extensions) | `markitdown` (fallback; same package as above) | `pip install 'markitdown[pdf]'` — run via CLI: `PYTHONIOENCODING=utf-8 markitdown <path>` |

Every `markitdown` invocation in this skill is prefixed with `PYTHONIOENCODING=utf-8`: on Windows, a Japanese-locale console codepage (`cp932`) can make the `markitdown` subprocess's stdout encoding disagree with the UTF-8 the rest of the pipeline (redirect target, `Read` tool, hash computation) assumes, corrupting extracted text into mojibake before it ever reaches Pass 2 (Issue #272). This `VAR=value command` prefix syntax is POSIX shell — it works unmodified under both Git Bash and WSL, the two execution paths Claude Code's Bash tool uses on Windows; it would need different syntax under raw PowerShell/cmd.exe, but Skills never run there.

## Processing Flow (4-Pass Design)

Before starting, read `.wikicommit/config.yml` and obtain `primary_lang`, `theme`, and `generate.max_retries` (default: 2). If `.wikicommit/config.yml` does not exist, stop immediately and tell the user to run `/wikicommit-init` first. If `theme` is absent from `config.yml`, treat it as an empty string. An empty `theme` disables the *relevance* judgment described in Pass 2 — no entity is excluded as off-subject, as before this field existed. It does not disable Pass 2's other exclusion axis: the entity policy read below is judged independently and can still exclude an entity on a wiki whose `theme` is empty.

Read `.wikicommit/entity-policy.md` at the same time (Issue #667). It answers a different question from `theme`, on the same entities: `theme` decides **relevance** (has this anything to do with the subject?), the entity policy decides **permissibility** (granted it does, should a page exist for it?). A living person at the centre of the subject scores highest on relevance and may still be one this wiki does not want a page about, which is why the two are separate and why neither substitutes for the other. Hold two things from it for Pass 2c: `wikicommit.exclude_living_persons` (a boolean, default `false`) and the body prose. If the file is absent, treat it as the shipped default — the switch off and no prose — and carry on silently; a wiki initialized before this file existed keeps working unchanged. If the file **exists** but cannot be read or its frontmatter does not parse, fall back to that same default but **say so**: print a `WARNING:` naming the file at that moment, and repeat it in the Completion Notice. Do not fail open in silence — one mistyped line in a hand-edited file would otherwise turn the whole policy off with nothing in the run's output to distinguish it from a wiki that never set one, and unlike `source-policy.md`'s domain list there is no built-in fallback behind it. If the body is empty or still the shipped comment, there is no prose policy, exactly as an empty `theme` disables the relevance judgment.

**Open a run record before anything else (Issue #790)**:

```bash
python .wikicommit/scripts/record_run.py start --skill wikicommit-generate \
    --model "<the model ID this runtime reports for you>" --arg "<each argument, one --arg each>"
```

**Keep the path it prints** — every exit from this Skill below closes that same record, and the closing call needs it. Nothing else in this repository is keyed on a run: if this one dies partway, half the management files sit at `pending` and half at `generated`, which is indistinguishable from a queue that simply has not reached them, and the two halt paths below change no file at all. A record with a start and no end is exactly the signal that a run did not finish, so **an unclosed record is not a failure state to avoid** — it is the answer. Report the record's path in the Completion Notice.

**Stamp a checkpoint at the entry to each pass, once per source (Issue #797)**:

```bash
python .wikicommit/scripts/record_run.py checkpoint <the path start printed> \
    --pass <pass1-extract|pass2b-type|pass2c-entities|pass3-generate|pass4-review> \
    --source "<the source management file this pass is running for>"
```

`ended_at` says whether this run finished; the stamps say **where it got to and what it skipped**. Both questions have cost this project real audits: the two halt paths below stop without changing a single file, so the record is their only trace and without a stamp that trace has no position — and separately, a step at the tail of this flow silently not running is a failure this Skill has shipped three times (Issues #406, #452, #474), each found afterwards by a human reading a published repository. A pass with no stamp is a pass that did not run, and `/wikicommit-status` reports it.

Under `--regenerate` only `pass1-extract`, `pass3-generate` and `pass4-review` are stamped — that mode takes a page rather than a source, so Pass 2 does not run, and `--source` carries the page being rebuilt. Pass 2a takes no stamp: it runs unconditionally in the same breath as Pass 1's extraction and has no branch of its own, so a stamp there would locate nothing Pass 1's does not.

**Known limitation, until this file is split by pass**: only the instruction for the *first* stamp is reliably still in context late in a long run. The stamping instructions for Pass 2 onward sit past this file's opening, and context compaction can drop them while the run continues — so on a compacted run the later stamps go missing whether or not the passes ran, and `MISSING_PASS:` reports a pass that in fact executed. The error falls on the safe side (a pass that really was skipped is never reported as having run), and it costs a glance at a run that was fine.

With `--regenerate`, skip Step 0 entirely and go to the Regeneration Mode section below — that mode takes a page, not a source, and registers nothing.

### Step 0: Source Registration (only when argument is given)

If an argument is provided:

0. **Read `.wikicommit/source-policy.md` first, before registering anything (Issue #564)**. It holds this wiki's answer to "which sources do we take in", which nothing else does: `theme` in `config.yml` decides which *entities* get pages once a source is already in, so it has no say here, and it is the only thing this Skill used to read. If the file is absent, or its body is empty or still the shipped comment, there is no prose policy — carry on without one, exactly as an empty `theme` disables the entity judgment.

   Read the body as instructions to someone deciding whether this particular document belongs in this wiki, and apply them to the argument you were given. If it clearly falls outside them (a personal blog where the policy asks for primary sources; a promotional page where it excludes advertising), **say which line of the policy it conflicts with and ask whether to register it anyway** — do not register it silently, and do not refuse on your own either: the person running this Skill named this source deliberately and may have a reason the policy does not cover. Proceed on a yes and note it in the Completion Notice. The `rejected:` list in the frontmatter is the same kind of signal: if the argument matches a `url` already listed there, quote that entry's `reason` and ask before going on.

   `exclude_domains` is enforced for you later — `check_extraction_quality.py check-domain` in Pass 1 unions it with its own built-in list and blocks the fetch — but do not leave it to Pass 1 alone. Pass 1 blocking a source sets `status: failed` and writes a `## Failure Reason`, which is the right record for a domain static fetching genuinely cannot read and the wrong one for a domain this wiki simply decided against: it leaves a management file behind for a source that was never wanted, and `wikicommit-merge` Step 9 then opens a `wikicommit-generation-failure` tracking Issue asking someone to fix a non-failure. So if the argument's host matches an `exclude_domains` entry, treat it exactly like a prose conflict above — name the entry, ask whether to register it anyway, and register nothing until the answer is yes. (Compare hosts the way the script does: case-insensitively, ignoring any scheme, port and leading `www.`.)

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
   - `RETRACTED:` → A human previously withdrew this source: they read it, judged its content unreliable, and set the management file's `status` to `retracted` (Issue #737). **Quote the reason the message carries** (`add_source.py` reads it out of the management file's `## Retraction Reason` section) and stop — register nothing, re-fetch nothing, and do not go on to Pass 1. Say what it would take to reverse the decision: edit the management file's `status` back to `pending`, delete its `## Retraction Reason` section, and re-run. Never do that yourself. This is the one status where the machine has no standing to disagree: under the evidence-binding rule the machine judges a page *against* its sources and so cannot judge a source, which is why only a human can write this value and only a human can lift it. If the message says no reason was recorded, say that too rather than treating the retraction as doubtful.
   - Exit code 1 (error) → Display the error and stop.

4. **Source license (Issue #558)**: on `CREATED:`, `add_source.py` writes a `source.license` field into the new management file, filled from its known-domain table (e.g. any `wikipedia.org`/`wikisource.org` host → `CC-BY-SA-4.0`) and left blank otherwise. Blank means *unknown*, not *unrestricted*. If the message reports a license, mention it to the user. If it is blank and the user knows the source's terms, tell them to edit `source.license` in the management file directly (the `--license "<identifier>"` flag only takes effect when a management file is first created, so re-running it against an already-registered source returns `SKIP:`/`RECHECK:` and records nothing). The value is free text (an SPDX identifier such as `CC-BY-SA-4.0` where one exists, otherwise a short phrase such as `Saitama City website terms of use` or `all-rights-reserved`), and it is carried onto every page generated from this source and shown next to that source on the published site. Never guess a license on the user's behalf, and never present the table's value as a legal determination: WikiCommit records and displays what it is told, it does not decide what a source's terms are or whether they permit this use.

   **Share-alike sources (Issue #570)**: when the message says the license is share-alike, `add_source.py` appends a line saying so. Pass it on and say what it means concretely — a page written from this source **and nothing else** has to be offered under that same license, and that obligation is on the wiki, not on WikiCommit. It is not a reason to refuse the source: some subjects have no primary source at all (a shrine's founding legend, a local custom), and an encyclopedia article is the honest answer there. It is a reason to know it is happening. Where a primary source does exist, two things reduce how many pages end up in that position: take the structural overview from the primary source, and use the encyclopedia as an index instead — `/wikicommit-collect --index <url>` reads a page's citations and offers those, without registering the page. See `.wikicommit/source-policy.md`, whose shipped comment describes this shape.

5. **Sources whose fetch is known to be partial (Issue #715)**: on `CREATED:`, `add_source.py` also appends a `partial extraction:` line when the URL matches a shape whose static fetch is confirmed to return the page's body but silently drop part of what the page carries. Today that is a GitHub issue or pull-request thread — the body comes through, every comment on it does not, and nothing errors. Pass the line on and say plainly which part will be missing, so the person can decide whether the body alone is the source they wanted.

   **This is a notice, not a guard.** Do not treat it as a reason to stop, do not set `status: failed`, and do not ask for confirmation the way an `exclude_domains` match does: the fetch really does succeed and what it returns really is the page's body, so an issue whose body is the whole point is a perfectly good source. It is the *silence* that was the defect, not the partial result. If the missing part is the part they wanted, the answer is to get that content another way and register that instead — not to register this URL and hope.

If no argument is given, skip Step 0 and start from Pass 1.

### Regeneration Mode (`--regenerate`)

Rebuilds pages that already exist, so that pages generated under older schema templates or older Pass 3 rules can be brought up to the current ones (Issue #578). Ordinary generation is source-driven and only ever touches management files at `status: pending`/`outdated`/`partial`; a source already at `status: generated` is skipped, so "the source has not changed, but the generation rules have" has no way to be expressed. This mode is that expression.

It is **page-driven, not source-driven**. A wiki page carries its full provenance in `sources:` (every `path`/`url` plus `hash`), so a single page can be rebuilt from exactly its own sources — including a page merged from several — without dragging in the unrelated pages that those same sources also produced. That granularity is the whole reason for going page-first: one source commonly generates entities of several types, and a source-driven rebuild would sweep all of them in.

Because the target page's frontmatter already fixes `type`, `title`, `lang` and slug, there is nothing left for Pass 2 to decide:

<!-- skill-vocabulary-exception: pass-structure diagram explaining this mode to the agent; never printed to the user -->
```
Normal generation:  Pass 1 (extract) → Pass 2 (analyze/extract entities) → Pass 3 (generate) → Pass 4 (review)
Regeneration:       Pass 1 (re-acquire) →                                   Pass 3 (generate) → Pass 4 (review)
```

Pass 2b (dynamic type addition) does not run either: regeneration takes the existing page's type as given. Deciding a page's type was wrong is a different operation (type re-classification) and is out of scope here, as is splitting or merging pages after a `granularity` change — that changes *which pages should exist*, which a page-driven rebuild cannot express.

**Selecting what to rebuild is the human's job.** There is deliberately no freshness script that computes "which pages are stale" per type: read `CHANGELOG.md` for what actually changed in each version, and `grep` `generated_with` to list pages built by an older one. Version granularity is coarser than per-type changes — bumping the version after editing only `Person.md` makes every page look equally old — so the two are only useful together.

#### Target selection

```
/wikicommit-generate --regenerate <page-path>     # one page
/wikicommit-generate --regenerate --type <Type>   # every eligible page of that type, all languages
/wikicommit-generate --regenerate --all           # every eligible page
```

With `--regenerate` the positional argument names a **page**, not a source — the opposite of every other invocation of this Skill. Do not try to infer which one the user meant from the path's shape: require the argument to resolve under `.wikicommit/entity/`, and if it does not, stop and say that `--regenerate` takes a page path while a bare `/wikicommit-generate` takes a source. Silently guessing is how a mistyped source path turns into a no-op that looks like success.

`--type <Type>` matches the page's `type:` frontmatter (`schema:`-stripped, e.g. `Person`, `custom/Decision`), not the directory name, and spans every language directory. Exactly one of a page path, `--type`, or `--all` must be given.

#### Eligibility

Walk the selected pages and drop the ones that cannot be rebuilt, then **report every dropped page and why** — silence here reads as success:

- `index.md`, and any page with `status: removed` — never regenerated.
- A page with `translated_from` (translation) or `derived_from` (synthesized). These have their own producers; `/wikicommit-translate` and `/wikicommit-synthesize` own them. Regenerating an original page makes `check_translation_status.py` report the translation `STALE` and `check_derivation_freshness.py` report the synthesized page `STALE`, which is how the user learns to re-run those Skills. No new following mechanism is added here.
- A page with no `sources`, or with **any** `sources[].type: manual` entry. A manual source cannot be re-acquired, so a rebuild would quietly drop whatever the page drew from it. Skipping the whole page rather than rebuilding from its remaining sources is the conservative choice: losing content is worse than not refreshing it.
- A page **every** one of whose sources is `status: retracted` (Issue #744). Retracted sources are dropped rather than re-acquired (step 1), so there is nothing left to rebuild this page from. Report it and point at `/wikicommit-remove`: a page with no evidence behind it at all is a removal decision, not a regeneration one. Note this is the one exclusion here that is *not* conservative in the same direction as the two above — for a page with at least one surviving source, dropping the retracted entry and rebuilding is exactly what this mode is for, which is why partial retraction is handled in step 1 instead of here.

Then apply the same count guard the rest of this Skill uses: if more than 5 pages remain, show the count and the list, and ask whether to **(a)** process all of them or **(b)** process only the first 5 by path, ascending, leaving the rest for a later run. 5 or fewer proceeds without asking. Regeneration costs one full generate-plus-review cycle per page, so `--all` must never run unguarded.

#### Per-page procedure

Stamp checkpoints as in the normal flow, but only the three passes this mode runs — `pass1-extract` before step 1, `pass3-generate` before step 2, `pass4-review` before step 3 — with `--source` naming the page being rebuilt. `record_run.py` reads `--regenerate` off the record's own `args` and narrows what it expects to those three, so 2b and 2c are not reported as skipped here (Issue #797).

1. **Re-acquire every source** listed in the page's `sources:` (a source whose management file is `status: retracted` is the one exception — it is dropped rather than fetched; see below), using Pass 1's extraction rules for that `source.type` unchanged (including its guards) — but **only the acquisition half of Pass 1**: none of Pass 1's writes to the source management file happen here (no `--write-hash`, no `extracted_tokens`, no `status: failed`/`## Failure Reason`), per step 5 below. `--write-hash` in particular would overwrite the management file's `source.hash` with freshly-fetched content while its `status` stays `generated`, so a later `/wikicommit-generate <url>` would re-fetch, see `HASH_MATCH:` and report "No changes" — the source change this mode just refused to fold in would be lost for good. If a guard blocks a source (known-JS-shell domain, missing fetch capability, low density), skip the page and report it rather than marking the source failed; the source's own management file is not this operation's to change. Two deltas:
   - **Prefer the cache, keyed on the page's own hash.** For a `type: url`/`wikicommit` source, first locate that source's source management file by scanning `.wikicommit/source/url/` for the one whose `source.url` equals this `sources[].url` — do **not** re-derive the filename from the URL, which does not match management files registered under the older flat or percent-encoded naming (Issue #191/#192/#572); `.claude/skills/wikicommit-ask/scripts/resolve_source_cache_path.py` already performs exactly this scan and prints the resulting cache path. `<scratch-path>` is that management file's path relative to `.wikicommit/source/url/` without the `.md` extension, as defined in Pass 1. If `.wikicommit/.cache/ingest-fetch/<scratch-path>.md` exists and its SHA-256 equals the page's own recorded `sources[].hash`, use it and do not fetch. The point of this mode is to apply new generation rules, not to pick up source changes; a network round trip per source would be pure cost. Compare against the **page's** hash directly (e.g. `sha256sum`), not with `add_source.py --check-hash`: that command compares the scratch file against the *management file's* current `source.hash`, which can have moved on since this page was generated (the source was re-registered and re-fetched afterwards), so a `HASH_MATCH:` there would hand the rebuild newer content than the page records — and the next bullet's guard, which only fires after a real fetch, would never run. When there is no matching management file, no scratch file (a clean checkout, a different machine), or the scratch file's hash differs from the page's, fetch normally and let the next bullet decide.
   - **A changed or unavailable source disqualifies the page.** After a real fetch — or, for `type: path`, after hashing the file on disk — compare against the page's recorded `sources[].hash`. On a mismatch, do **not** rebuild: report the page, name the source, and point the user at `/wikicommit-generate <path|url>`, which is the existing `outdated` path for exactly this. Folding a source change into a rules refresh would put two unrelated changes into one page under one review, and would leave the source's own management file describing a state that no longer holds. Treat a source that cannot be re-acquired at all the same way — a `type: path` file no longer on disk, or a fetch that errors out: skip the whole page and report it, rather than rebuilding from the sources that did resolve. Rebuilding on a subset would silently drop whatever the page drew from the missing source, which is the same loss the `manual`-source exclusion above exists to prevent.

   **A retracted source is dropped, not fetched, and not carried forward (Issues #737 / #744).** Before acquiring any source, read the `status` of that source's management file. For a `type: url`/`wikicommit` source that is the file located above; for a `type: path` source, scan `.wikicommit/source/path/` for the one whose `source.path` equals this `sources[].path` — the same real-directory identity match `add_source.py`'s `find_mgmt_file_for_path()` performs. Do **not** derive the filename from the path, for the same reason the url scan above does not derive it from the URL: a derived name misses management files registered under the older extension-stripped naming (Issue #573). A source with no management file at all has no retraction to read — treat it as not retracted and let the two bullets above decide it. The eligibility rule above (every source retracted) reads these same statuses, so do this lookup once per page and use it for both. If it is `retracted`, do not fetch it: a human read that source, judged its content unreliable and withdrew it, and re-acquiring it here would re-ingest the exact thing `add_source.py`'s `RETRACTED:` result and `check_ingest_freshness.py`'s status allowlist exist to keep out. Rebuild the page from the sources that remain, and **drop the retracted entry from the rebuilt page's `sources:`** (the one exception to step 2's "copied through untouched"). **"From the sources that remain" governs the body too**, and it has to be said here because step 2 runs Pass 3 as an `action: update` whose standing rule is to *merge* into the existing page: whatever the current page asserts on the strength of the retracted source alone is not carried across. Keeping it would be the worst outcome available — the claim survives with nothing in `sources[]` naming where it came from, so `check_retracted_sources.py` never reports the page again and the retraction is lost rather than applied. Report every page this happened to, naming the dropped source and its `## Retraction Reason`.

   This is the opposite treatment from the changed/unavailable/`manual` cases above, and deliberately so. Those skip because the source's content is still wanted and cannot be had — rebuilding without it would silently lose what the page drew from it. A retraction says the opposite: that content is **not** wanted, and removing what rested on it is the point. Rebuilding here is the only route that actually takes a retracted source out of a page's evidence base, which is why Issue #737 could leave the page side to the existing routes at all.

   Keeping the entry while rebuilding without the content would be the worst of both: `sources[]` is a claim about what backs the page's **current** text, so the page would assert support it was not written from, Pass 4 would go on checking it against a document the rebuild ignored, and `check_retracted_sources.py` would report the same page on every run with nothing the user could do about it. Dropping the entry loses "this page once rested on that source" from the page itself, but not from the repository: the management file survives with its `generated_pages[]` still naming the page, its `## Retraction Reason`, and its public `content/sources/` page — and the whole change is one commit in `git log`.
2. **Run Pass 3** for this one page, as an `action: update` entity whose `existing_path` is the page itself: `type`, `title`, slug and `lang` come from the page's own frontmatter, and the existing page is supplied as context exactly as Pass 3 already does for an update. Every Pass 3 content rule applies unchanged, with one content delta stated in step 1: when a retracted source was dropped, what rested on it is not merged forward from the existing page. Four frontmatter deltas, which override Pass 3 step 3's `action: update` rules:
   - `sources:` is copied through **untouched** — same entries, same hashes, same `license` values. Nothing is appended; step 1 already established the sources are the same ones. The single exception is a `status: retracted` entry, which step 1 dropped along with the content behind it (Issue #744).
   - `expires_at` is left as it is. Pass 2 did not run, so there is no source-stated date for this run to prefer, and `null` here would mean "not asked", not "no expiration".
   - `review_status` is reset to **`pending`**, overriding Pass 3 step 3's "preserve `reviewed`" rule. That rule is for incremental merges, where a human's earlier review still covers most of the page; a rebuild replaces the page's structure wholesale, and carrying `reviewed` across would attach a human's sign-off to text no human has read. The trust ladder depends on that never happening. **`reviewed_by` is dropped from the output at the same time** (Issue #705): it names whoever signed off on the previous version, and keeping it beside a fresh `pending` would leave that name to resurface the next time the page reaches `reviewed`. Pass 3 writes the page wholesale, so omitting the field from the output is all that is required — no separate delete step.
   - `generated_at`, `generated_by` and `generated_with` are updated to this run.
3. **Run Pass 4** unchanged, including its retry loop — with the same management-file carve-out as step 1: Pass 4 step 5's `failed_pages` entry and step 7's status update do **not** run. Those describe the whole source and every page it produced, not this one rebuild; letting step 7 fire would, for a source that generated five pages, flip its management file from `status: generated` to `status: failed` (with a `## Failure Reason`) because a single rebuilt page failed review, discarding the recorded state of the other four (step 5 below). A page that still FAILs after `generate.max_retries` is **left on disk exactly as it was** — do not write a partial or failed rebuild over a page that was fine before — and reported as a failed regeneration.
4. **Unchanged-output valve.** Before writing, compare the rebuilt page with the one on disk, ignoring only the five bookkeeping fields step 2 rewrites (`review_status`, `reviewed_by`, `generated_at`, `generated_by`, `generated_with`). `reviewed_by` has to be ignored here even though step 2 drops it rather than rewriting it: leave it out of the ignore list and its absence from the rebuilt output counts as a difference, so a page carrying one — that is, every Route A page, exactly the population this valve exists for — could never compare identical and the valve would be dead for them. If the rest is byte-identical, keep the existing `review_status` (so a `reviewed` page stays `reviewed`) **and keep `reviewed_by` with it** — the two always travel together (Issue #705); dropping only the name would leave a page that claims review with no reviewer, breaking the very fact this valve exists to preserve — and write the page with only the three `generated_*` fields updated — the page genuinely was rebuilt under the current rules and found to need no change, so it should stop showing up in the next `generated_with` sweep. `sources:` is part of that comparison, so a page that had a retracted entry dropped can never compare identical and always lands on `pending` (Issue #744) — which is right: what a page rests on changed, and no earlier review covered the page in that state. The comparison is deliberately textual: a semantic same-meaning judgment would put a non-deterministic decision in charge of whether human review is required. LLM output is not deterministic, so expect this valve to fire rarely. Pass 4 step 6's `reset_review_on_content_change.py` (Issue #724) then runs over the written page as it does in the normal flow and agrees with whichever way this went: a rebuilt page is already `pending` so it is skipped, and a page the valve kept at `reviewed` compares equal against HEAD, so nothing here needs a carve-out.
5. **Do not write back to the source management file.** Regeneration creates no new pages, so `generated_pages` is unchanged, and `last_generated_at` records when a source was turned into pages — which is not what happened here. Leaving management files alone also keeps `check_ingest_freshness.py`'s reading of `source.hash` intact.

After all selected pages are processed, run `rebuild_index.py` exactly as the normal flow does (below) — a rebuild can change a page's `title`, and `index.md` carries titles (Issue #406). Skip the Ingest Status Reconciliation step: no management file's status was in play. Then report, per page, which were rebuilt, which were unchanged, which were skipped and why, which failed review, and which fell back to `.wikicommit/schema/default.md` for want of a schema file for their type (Pass 3 step 1, Issue #575 — this mode never reaches the Completion Notice that otherwise carries that list, and a rebuild run right after `/wikicommit-schema-propose` will still fall back until that Skill's PR is merged, since it deliberately does not auto-merge); remind the user that rebuilt pages are back at `review_status: pending` and that the next `/wikicommit-merge` will open a fresh review-tracking Issue for each (its scan only skips pages with an *open* Issue, so a previously-closed one does not suppress the new one).

Close the run record opened at the start of this Skill before writing that report, so its elapsed time covers the whole run, and give its path and duration alongside the report:

```bash
python .wikicommit/scripts/record_run.py end <the path start printed> \
    --page <each page rebuilt> --outcome regenerated=<N> --outcome unchanged=<N> --outcome failed=<N>
```

This mode does not reach the Completion Notice, which is where the closing call otherwise lives, so without this line every regeneration run — including one that did exactly what was asked — would be reported by `check_run_records.py` as a run that did not finish, and the elapsed time the record exists to hold would never be written (Issue #790).

### Pass 1: Text Extraction

**Stamp `--pass pass1-extract` before extracting each source** (see the run-record block above). This is the stamp that survives compaction, so it is the one that always marks how far a run got.

1. Collect source management files from `.wikicommit/source/` whose `status` is `pending` or `outdated`, plus those with `status: partial` **and a non-empty `failed_pages`** (Issue #567):
   - **`status: retracted` is never collected** (Issue #737), and this needs no extra rule: the condition above is an allowlist, and `retracted` is not on it. Say it explicitly anyway, because a later edit that widens this list would silently put a withdrawn source back into circulation. The argument branch below does not reach one either — Step 0 stops on `RETRACTED:` before Pass 1 begins, so "the user named this source, so process it whatever its state" never applies to a retraction.
   - If an argument was given: process only the management file Step 0 acted on (`CREATED:`/`UPDATED:`, or `RECHECK:` — a forced recheck is processed here too even though its `status` is still `generated`/`failed`/`excluded`, per Step 0 above). The `failed_pages` condition does not apply to this branch: the user named this source, so process it whatever its state.
   - **Why `partial` alone is not enough**: `partial` covers two states that behave nothing alike. One is "some entities failed to generate" (`failed_pages` non-empty) — re-running can succeed, so it belongs here. The other is "some entities were excluded as off-`theme`" (`failed_pages` empty) — the same `theme` produces the same judgment every time, so re-running lands on `partial` again, forever. In `wikicommit/saitama-city-wiki` **all eight** `partial` sources were the second kind, and all eight were excluding people from ward articles exactly as intended, so nothing was even wrong. They stayed in the collection list on every run regardless, and 23 sources that had never been processed at all sat behind them. Nothing needs migrating for this: an existing `partial` with an empty `failed_pages` simply stops being collected.
   - **The one case this over-collects out**: an empty `failed_pages` does not only mean "excluded as off-`theme`". Pass 4 step 7 also lands on `partial` when an entity came back `ambiguous: true`, and an ambiguous entity is never added to `failed_pages` either — yet unlike an exclusion it *is* resolvable, because it is waiting on a human to confirm its type. Nothing in the management file tells the two apart, so a source left `partial` by an ambiguity stops being collected as well. Confirming a type therefore does not re-queue anything on its own: re-run that source **by name** (`/wikicommit-generate <path|url>`), which the argument branch above processes whatever its state. The Completion Notice's ambiguous list says the same thing where the user actually sees it.
   - If no argument: collect all matching files under `.wikicommit/source/`. **Order them in three tiers**, path ascending within each: (1) `status: outdated`, (2) never processed — no `last_generated_at`, absent or empty, (3) everything else. Sorting by path alone lets the same already-worked-on files take the same slots on every run: the whole point of the cap is to make progress in bounded chunks, which it stops doing if the chunk never changes.

     `outdated` goes ahead of the backlog rather than behind it because it means something different: a page is already published and its source has since changed, so what is on the site is *wrong*, where a never-processed source is only *missing*. It also cannot starve the backlog — a source only becomes `outdated` when its content actually changes, so the tier is small and does not refill on its own.
   - If the count exceeds 5 (same threshold as `wikicommit-collect`'s Step 9 note), do not start processing yet — show the count and the matching management file paths, then ask the user to choose: **(a)** process all of them in this run, or **(b)** process only the first 5 in the order above and leave the rest untouched for a later run. If the user picks (b), proceed with only those 5; the unselected files keep their current `status` unchanged and will naturally be picked up by a future no-argument `/wikicommit-generate` run — no other change is needed for this. If the count is 5 or fewer, proceed with all of them without asking (unchanged behavior for the common case).
   - **Group the list you show under three headings**, in this order, so a source that has never been touched is not presented as interchangeable with one being re-run:

     ```
     Never fetched (no content has been retrieved yet) — 23:
       .wikicommit/source/url/ja.wikipedia.org/...
     Fetched but never generated — 0:
     Re-processing (source changed, or entities failed last time) — 2:
       .wikicommit/source/path/raw/report.pdf.md (outdated)
     ```

     A file belongs to the first group when its `source.hash` is empty, the second when it has a hash but no `last_generated_at`, and the third otherwise. The first two are the "never processed" tier the ordering above puts first; the split between them says whether anything has been retrieved yet, which is what tells a stalled queue apart from a slow one. That split only carries meaning for `type: url`/`wikicommit` sources, whose management file is created with an empty hash and only gets one once Pass 1 actually fetches: `add_source.py` hashes a `type: path` file at registration, so a local file that has never once been read still has a hash and lands in the second group. Say so when the first group is empty but the second is not, rather than letting `Never fetched — 0` read as "everything has been retrieved".
2. If no target files are found, output "No management files to process" and exit.
3. For each source management file, read `source.type` and `source.path` / `source.url`.
4. Extract text based on `source.type` and file extension:
   - `type: wikicommit` (federated source) / `type: url` → **Known JS-shell domain check (Issue #425, guard B)**: before attempting any fetch, run:

     ```bash
     python .wikicommit/scripts/check_extraction_quality.py check-domain <source.url>
     ```

     `BLOCKED:` (exit 1) → do not attempt extraction at all. Treat this source as extraction failure (step 5 below): mark `status: failed`, write the script's `BLOCKED:` line verbatim into `## Failure Reason`, notify the user, and skip to the next source. `OK:` (exit 0) → proceed with the fetch below as normal. This check is deliberately narrow — it only catches domains a prior run has already confirmed return an empty content shell (see the `KNOWN_JS_SHELL_DOMAINS` set in the script); it is not a general JS-detection heuristic. The general case is guard A in step 5 below.

     **Fetch-capability check (Issue #574, guard C)**: still before fetching, and only once the domain check above returned `OK:`, run:

     ```bash
     python .wikicommit/scripts/check_extraction_quality.py check-fetch-capability <source.url>
     ```

     `MISSING_PACKAGE:` (exit 1) → **stop processing entirely**, close the run record with `record_run.py end <path> --halted-reason "missing package: <name>"` (this path changes no file, so without that line the run leaves no trace at all — Issue #790), display the `pip install` command from the script's output, exactly like the `markitdown --version` prerequisite check below — this is an environment problem the user fixes once, not a property of this source, so it is not a `status: failed` extraction failure and must not be recorded as one. `OK:` (exit 0) → proceed. Like the `markitdown` check, this only needs to pass once per host per run; do not re-run it for every subsequent source with the same host.

     This is a third axis, separate from guards A and B (Issue #574). A YouTube page fetched without `youtube-transcript-api` is neither an empty shell (guard B's domains) nor low-density boilerplate (guard A) — it is a *partial* extraction of real prose, measuring 0.90 on guard A's ratio with the transcript missing versus 0.93 with it present, so neither existing guard can distinguish it from a complete one. Checking the capability *before* fetching also keeps "the package is missing" distinguishable from "this video has no captions" (see the transcript roll-up in step 6 below); checking after the fact could not tell those two apart, and they call for opposite responses.

     Extract `source.url` by running `add_source.py --fetch-url` (deterministic conversion, no LLM summarization step in between — this is what makes the **Hash write-back** below genuinely verbatim, unlike the previous WebFetch-based approach; see Issue #189), rather than invoking the `markitdown` CLI on the URL directly. `markitdown`'s own HTTP client sends Python `requests`' default User-Agent when given a bare URL, which Wikimedia domains (Wikipedia, Wikisource, etc. — likely per the [Wikimedia User-Agent policy](https://meta.wikimedia.org/wiki/User-Agent_policy)) reject with `403 Forbidden`; `add_source.py --fetch-url` avoids this by calling `markitdown`'s Python API (`MarkItDown(requests_session=...)`) with a `requests.Session` carrying a WikiCommit-identifying User-Agent instead (Issue #527). This preserves `markitdown`'s normal HTTP-response-based dispatch (Content-Type mimetype **and charset**) exactly as when passing it a bare URL — unlike a `curl`-then-convert-locally two-step, which would fetch to a plain file and lose the HTTP response's charset header, silently degrading `markitdown`'s decoding to statistical guessing for any page whose encoding is declared only via that header (verified to mojibake non-UTF-8, non-ASCII-safe pages, e.g. legacy `windows-1252` sites, during Issue #527's implementation) — so only the User-Agent changes, nothing else about how `markitdown` fetches or decodes the page. Confirm `markitdown` is installed once per run, before the first source of any kind — `type: url`, `type: wikicommit`, the `.pdf`/`.docx`/`.pptx`/`.xlsx` fallbacks below, or the "Other" fallback below — that needs it; do not re-run this check for every subsequent source once it has passed:

     ```bash
     PYTHONIOENCODING=utf-8 markitdown --version
     ```

     Non-zero exit or command not found → stop processing and display the install command from the Prerequisite Skills table above (`pip install 'markitdown[pdf]'`), per the rule at the top of this section. This applies even when this check is being run for the `.pdf` (text-based) fallback or the `.docx`/`.pptx`/`.xlsx` fallbacks (step 4 below) — `markitdown` is the guaranteed path for these formats once the corresponding official skill is unavailable, so its own absence must still stop processing rather than being silently skipped.

     `markitdown` dispatches on the URL's content type / extension internally, so a URL that points directly at a non-HTML file (e.g. `https://arxiv.org/pdf/xxxx.pdf`) is extracted with the appropriate converter automatically — no separate `type: path` registration or pre-download step is needed for this case. Fetch only the registered URL — do not follow or register links found within the extracted content, even if they appear relevant to the topic (out-of-scope fetching risks unintended scope creep, copyright exposure, and unnecessary token usage). If related linked pages are worth ingesting, register them explicitly as separate sources via `/wikicommit-generate <url>`.

   **Hash write-back** (`type: url` / `type: wikicommit`): the management file is registered with `hash: ""`; this step fills it in deterministically via script rather than by hand-editing YAML (manual edits are unreliable — see Issue #157). `<scratch-path>` below is the source management file's path relative to `.wikicommit/source/url/`, without the `.md` extension, with the `/` separators kept intact (e.g. management file `.wikicommit/source/url/example.com/article.md` → scratch path `example.com/article`) — mirroring the nested path rather than collapsing it to `-` keeps scratch files unique per source even when several `type: url`/`type: wikicommit` sources are processed in the same run (flattening with `-` is not collision-free here: the nested management file `.wikicommit/source/url/example.com/article.md` and a legacy flat management file `.wikicommit/source/url/example.com-article.md` would both collapse to the same scratch name `example.com-article`).

     **Forced recheck** (source flagged `RECHECK:` in Step 0 — i.e. re-running `/wikicommit-generate <url>` on a source whose `status` was already `generated`/`failed`/`excluded`; Issue #310): skip the **Cache check** below unconditionally and go straight to the fetch — a kept scratch file from the prior successful run would otherwise trivially "match" the management file's still-unchanged `source.hash` and short-circuit the very re-fetch this recheck exists to perform. After the fetch succeeds, before running `--write-hash` (which unconditionally overwrites `source.hash`), first run `--check-hash` against the freshly-fetched scratch file to compare it with the management file's *current* (pre-overwrite) `source.hash`:

     ```bash
     python .claude/skills/wikicommit-generate/scripts/add_source.py --check-hash <source-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     - `HASH_MATCH:` (exit 0) → the remote content is unchanged since the last successful check. Do **not** run `--write-hash` and do **not** proceed to Pass 2–4 for this source — leave the management file's `status`/`hash` exactly as they were. Notify the user "No changes: `<url>`" and move on to the next source.
     - `HASH_MISMATCH:` (exit 1) → the content changed. Run `--write-hash` as usual (see below) and continue this source through Pass 1 steps 5–6 and Pass 2–4 normally; Pass 4 step 5's existing status rules (below) already set the appropriate final `status` (`generated`/`partial`/`excluded`/`failed`) once processing completes, so no separate status transition is needed here.

     For a normal (non-recheck) `type: url`/`wikicommit` source, apply the **Cache check** instead: the scratch file at `.wikicommit/.cache/ingest-fetch/<scratch-path>.md` is *kept* after a successful fetch (not deleted — see below), so a source that is processed again with an unchanged `source.hash` (e.g. re-running `/wikicommit-generate` on a source left `status: partial` after a prior run) can reuse it instead of re-fetching against the network (Issue #278). Before fetching, if that scratch file exists, run:

     ```bash
     python .claude/skills/wikicommit-generate/scripts/add_source.py --check-hash <source-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     - `HASH_MATCH:` (exit 0) → the cached scratch file's content is still valid for the management file's current `source.hash`. Skip the fetch and the write-hash step below entirely, and jump straight to the "read the scratch file's content in full" step near the end of this bullet.
     - `HASH_MISMATCH:` (exit 1, including "scratch file doesn't exist") → the cache cannot be reused (no scratch file yet, or the source's `hash` has since changed — e.g. re-registered after `status: outdated`). Proceed with the fetch below as normal; this always fetches fresh content rather than trusting a stale scratch file, so a hash change is never masked by an old cache.

     If no scratch file exists yet at that path (or this is a forced recheck — see above), skip the cache check and go straight to the fetch below:

     ```bash
     python .claude/skills/wikicommit-generate/scripts/add_source.py --fetch-url "<source.url>" --output ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     `--fetch-url` creates the scratch file's parent directory itself (it is already gitignored) and writes exactly what `markitdown` produced to the output path, with nothing in between.

     - `ERROR:` (exit code non-zero — network error, HTTP error status like 403/404, login-required page, unsupported content, etc.) → treat this source as extraction failure (step 5 below) and skip to the next source; do not run the command below.
     - `FETCHED:` (exit 0), forced recheck → run the `--check-hash` comparison described above and branch on `HASH_MATCH`/`HASH_MISMATCH`.
     - `FETCHED:` (exit 0), normal (non-recheck) source → run:

       ```bash
       python .claude/skills/wikicommit-generate/scripts/add_source.py --write-hash <source-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
       ```

       Check the output: `HASH_WRITTEN:` → proceed. `ERROR:` (exit code 1) → treat this source as extraction failure (step 5 below) and skip to the next source.

     After `HASH_WRITTEN:` (or after a `HASH_MATCH:` cache hit above), read the scratch file's content **in full** with the Read tool — if the file is large enough that a single call truncates it, issue additional Read calls with `offset` to cover the rest; a partial read here would silently reintroduce the non-verbatim problem the original write-back change was meant to fix. This becomes the "extracted text" for this source used in steps 5–6 below and in Pass 2. **Do not delete the scratch file** — unlike before Issue #278, it is left in place so a later re-run of this same source (unchanged hash) can reuse it via the cache check above. `.wikicommit/.cache/` is a rebuildable, gitignored cache (same category as `search_index.sqlite3`), so leaving files there does not conflict with GitOps.
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

   For any other source type (the extracted text exists only as this run's context, not as a file), pipe it in via a quoted-delimiter heredoc instead — same reasoning as the "pass free-form text to a CLI via a quoted-delimiter heredoc" rule, even though this text isn't operator-authored free text, a heredoc is still the safe way to hand arbitrary content (which may itself contain shell metacharacters, e.g. backticks inside a code sample the source quotes) to a subprocess's stdin without shell interpretation:

   ```bash
   python .wikicommit/scripts/check_extraction_quality.py check-density <<'EOF'
   <extracted text>
   EOF
   ```

   `OK:` (exit 0) → proceed to step 6 below.

   `LOW_DENSITY:` (exit 1) → **a warning to raise with the human, not an automatic failure** (Issue #562). Unlike the guard-B domain check above — a deterministic verdict about a domain someone already confirmed broken — this is a text-shape heuristic, and a link-dense government site or a statistics table has essentially the same shape as a JS shell. The saitama-wiki pilot had 4 of 8 genuine sources flagged and the operator overrode every one, so failing the source outright on this signal alone is not justified. Branch on whether this run is interactive:

   - **Interactive** (a live human can answer right now): show the script's `LOW_DENSITY:` line verbatim — including its `non-prose breakdown:` figures, which are there precisely so the human can tell a link-dense real page (`links` dominant) or a statistics document (`numbers/tables` dominant) from a script/JSON shell (`other markup` dominant) — and ask whether to continue with this source. Continue → proceed to step 6 as if the check had returned `OK:`, and add this source to a running list rolled up in the Completion Notice below, so the override is recorded somewhere other than a hand-written note in `## Summary`. Decline → mark `status: failed` exactly like the empty/unreadable case above, writing the `LOW_DENSITY:` line verbatim into `## Failure Reason`.
   - **Non-interactive/subagent-driven** (no real answer will ever arrive): mark `status: failed` as above and skip to the next source, i.e. the pre-Issue #562 behavior. A false positive costs one source's worth of re-running once a human is present; passing a genuine shell through unreviewed costs a hallucinated page with a source URL that never contained it, which is the provenance failure Issue #425 exists to prevent.

   Make the interactive/non-interactive determination the same way Pass 2b step 1 does, **once per invocation**, and hold it constant — whichever pass first needs it makes the judgment and the other reuses it, so a single run never shows a prompt for one decision and silently defaults another.
6. Otherwise, compute an approximate token count for the extracted text (a rough estimate is fine — e.g., character count ÷ 4, rounded to the nearest integer; no LLM-specific tokenizer is required, per the BYOLLM design) and write it to the management file's `extracted_tokens` field. Overwrite any existing value every time this step is reached — this happens unconditionally as soon as extraction succeeds, regardless of the Pass 2–4 outcome (unlike `last_generated_at`, which Pass 4 step 5 only sets on the `generated`/`partial` branches).

   **Missing-transcript note (Issue #574)**: for a YouTube source, first check that the extracted text actually is a YouTube-converter result — it starts with a `# YouTube` heading and carries a `### Video Metadata` section with the video's title, keywords and runtime. If it does **not**, `markitdown` never recognized the URL as a video at all and fell through to its generic HTML converter: this happens for every YouTube URL that is not a `/watch?v=…` (or `youtu.be/<id>`) link — `/shorts/<id>`, `/playlist?list=…`, and channel pages all land here, and all produce a few hundred characters of footer/navigation links with no title, description or transcript (a `/shorts/` URL measured 0.40 on guard A, so guard A does not catch it either). Treat that as an extraction failure (step 5 above): mark `status: failed`, write a `## Failure Reason` naming the URL form and pointing at the `https://www.youtube.com/watch?v=<id>` equivalent to register instead, notify the user, and skip to the next source — do **not** send footer links to Pass 2. If it *is* a YouTube-converter result but has no `### Transcript` section, then — since guard C above already guaranteed `youtube-transcript-api` is installed — that means *this particular video has no captions*, a fact about the source rather than a broken environment. Do **not** mark that case `status: failed`: the title, keywords, runtime and description are real content and may well be enough. Append the source (its management file path) to a running list rolled up in the Completion Notice below, the same pattern as `ambiguous`/`exclude`/`failed_pages`, and carry on to Pass 2 — the user decides whether a description-only page is worth keeping.

### Pass 2: Analysis (LLM → JSON)

Pass 2 runs in three sub-steps per source: 2a produces a summary, 2b resolves — inline, right now — whether a Schema.org type outside `installed schema/` should be added before entities are extracted, and 2c extracts entities using whatever types are available after 2b.

#### Pass 2a: Summary

Ask the LLM to read the full extracted text and produce a 2-3 sentence summary of the source's content, in `<primary_lang>`. This summary is used immediately below (Pass 2b) and is also what eventually gets written to the source management file's `## Summary` section at the end of Pass 2c — do not write it to the management file yet, since Pass 2c may still need to append `coverage_gap_note`/exclusion notes to the same section (see below).

During this same read, also judge whether the source text is clearly written in a language other than `<primary_lang>` (Issue #336). This is a coarse LLM judgment call, not lexical/library-based language detection — flag only unambiguous cases (e.g., an entirely English document when `primary_lang: ja`), not borderline ones (a `primary_lang` document with a handful of foreign-language proper nouns or quoted snippets). This judgment does not change any generation behavior: entities are still extracted and written in `<primary_lang>` exactly as before (see the `lang` field rule in Pass 2c) — the source's content will be summarized/translated into `<primary_lang>` regardless. If flagged, append this source (its source management file path and the detected language) to a running list so all detections across sources can be rolled up together in the Completion Notice below; do not stop, ask for confirmation, or write anything to the management file for this — it is purely informational, unlike `ambiguous`/`exclude`.

**Source-as-entity judgment (Issue #475)**: also judge whether the source document *itself* — as distinct from the individual people/organizations/concepts it describes — has independent citable identity: a title, named author(s) or publishing organization, and a publication date or stable identifier (DOI, permalink URL), such that a reader would recognize it as a standalone "work" worth linking to on its own (e.g. an arXiv paper, an official vendor blog post announcing a product, an official report/whitepaper, a news article). Do not apply this to sources that are more "information" than "work" — a government procedure page, a personal blog's casual technical explainer with no strong standalone identity — where authorship/publication metadata is weak or absent, or the content is instructions/reference material rather than a citable piece of writing. This is a per-source judgment made once here, not per-entity; when it passes, the source document itself becomes an *additional* entity candidate that flows into Pass 2b (type resolution) and Pass 2c (entity extraction) exactly like any other entity — it does not replace or reduce the extraction of concepts/people/organizations discussed *within* the source, and it introduces no new mechanism, frontmatter field, or `sources:` semantics (see the Pass 2c rule and Pass 3 note below).

As a concrete restatement of the same test (Issue #479): does the source have a fixed publication date and author(s) that will not change (a single-instance work — an article, paper, report, or story), or is it a continuously-updated living resource with no meaningful "publication date" of its own (an official document, a government procedure page, a Wikipedia article)? Only the former qualifies. `installed schema/` ships with `ScholarlyArticle`/`NewsArticle`/`BlogPosting`/`ShortStory`/`Book` by default (Issue #479) specifically to cover the common cases of this judgment without needing Pass 2b to propose them — Pass 2b's dynamic type addition remains the fallback for a source-as-entity candidate whose closest fit isn't one of these (e.g. `schema:Report`).

#### Pass 2b: Type Necessity Judgment (Issue #315)

**Stamp `--pass pass2b-type` on entry**, with `--source` naming this source's management file.

Before extracting entities, decide whether the source content calls for a Schema.org type that isn't already in `installed schema/`. This runs **once per source** (not once per entity) and is grounded in the Pass 2a summary — the same "read the summary, judge against the full Schema.org type list" pattern `wikicommit-init`'s theme-driven suggestion (Issue #286, since removed by Issue #404) used, except here the evidence is the actual source content rather than a single free-text `theme` sentence, so this judgment is comparatively high-confidence.

1. Load the Schema.org type names (this also builds the shared vocabulary cache lazily on first use): `python .wikicommit/scripts/check_schema_org_type.py --list-type-names`. Run this once per `/wikicommit-generate` invocation (not once per source), same as before. This prints the 933 type names without their descriptions -- stage one of type recall (Issue #798); step 2 below picks candidates from it and reads only those descriptions. Non-zero exit (vocabulary fetch failed) → skip Pass 2b entirely for every source this run and proceed straight to Pass 2c with only `installed schema/` types available; do not block or fail the run over this.

   **Also determine, once per invocation (not once per candidate — Issue #507)**: is this run interactive
   (a live human can actually answer an Enter prompt right now) or non-interactive/subagent-driven (no
   real answer will ever arrive)? If Pass 1's low-density check already made this determination earlier in
   this run (Issue #562), reuse that answer rather than re-judging it. This is the same self-report judgment
   step 3 below already made before
   Issue #507; make it once here, at the top of Pass 2b, and hold it constant for every candidate across
   every source in this run — interactivity is a property of the run, not of any individual candidate, so
   re-deriving it per candidate risks the judgment flipping mid-run (one candidate shown a real prompt,
   another silently auto-approved/declined) and the Completion Notice misrepresenting what actually
   happened. Step 3 below branches on this stored determination rather than re-judging it.
2. Using the `--list-type-names` output and the Pass 2a summary, judge whether one or more Schema.org standard types — beyond what's already in `installed schema/` — would fit this source's content meaningfully better than any installed type (not merely "also plausible": a clearer semantic fit, where more of the source's concrete details map onto that type's actual properties). Skip any candidate type that already has a file in `.wikicommit/schema/`, including one just added by an earlier source **in this same run** (scan the directory on disk, same reasoning as the existing-pages scan in Pass 2c below) — never propose a type twice. Zero candidates is an expected common outcome, not a fallback; do not force a candidate to justify running this step. **This includes the source document itself (Issue #475)** when Pass 2a flagged it as a source-entity candidate: judge a type for it the same way as for any other candidate (e.g. `schema:Report` for a whitepaper, `schema:Legislation` for a piece of legislation — not `schema:ScholarlyArticle`/`NewsArticle`/`BlogPosting`/`ShortStory`/`Book`, which already ship in `installed schema/` by default since Issue #479 and so are resolved directly in Pass 2c without ever reaching this step). Note that the source management file's `schema:` hint (Pass 2c context list below) describes the source's primary discussed *subject* (e.g. `schema:Person` for a biography) — it is not evidence about what the source *document itself* is, so it does not carry over to this judgment; treat the source-entity's type purely on its own content-fit merits, independent of whatever hint applies to the entities discussed within the source.

   **Named-entity pattern (Issue #447)**: apply extra scrutiny when a candidate entity is a concrete, named subject — a specific software product, research dataset/benchmark, creative work, standard, etc. — rather than an abstract term, concept, or methodology. `DefinedTerm` is broad enough to technically represent almost anything with a name, which can make it look like a safe default and suppress a proposal that would otherwise pass the bar above. For this pattern specifically, the fact that `DefinedTerm` could technically represent the entity is **not** by itself a reason to skip proposing a more specific standard type (e.g. `SoftwareApplication` for a named software product, `Dataset` for a named benchmark). This does not relax the threshold for abstract terms/concepts/methodologies (e.g. a named approach like "vibe coding" with no more specific standard type) — those should still default to zero candidates as before.

   **Then confirm the candidates against the vocabulary before going further** (stage two, Issue #798):

   ```bash
   python .wikicommit/scripts/check_schema_org_type.py --describe \
     "$(cat <<'EOF'
   <Candidate1>
   EOF
   )" \
     "$(cat <<'EOF'
   <Candidate2>
   EOF
   )"
   ```

   Each candidate name goes through its own quote-delimited heredoc, for the same reason step 4's `--property` values do — these are names this step itself just proposed, not values an earlier script already verified. Names alone are enough to bring a type to mind, but not always enough to be sure what it means — read the descriptions of the handful you picked and drop any whose actual definition does not fit. A name that comes back as `ERROR:` was invented rather than recalled; drop it. Call this again if you want to look at more names.
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
   entities/reasoning, this source's source management file path, and which outcome it was — to a running
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

   Each `--property` value goes through its own quote-delimited heredoc — these are candidate names this step itself just proposed, not values an earlier script already verified, so they don't qualify for the upstream-validation exemption (same reasoning as Pass 3's identical `--show-range` call above). Drop any property the script reports as `ERROR:` — never put an unverified property into the new schema file's `properties:` block. Then write `.wikicommit/schema/<Type>.md` directly with the Write tool, in the standard-type format (a `wikicommit:` block with `base`/`granularity`, template frontmatter with the verified property names nested under `properties:` as empty-string placeholders, and a body template), using `.wikicommit/schema/default.md` and `.wikicommit/schema/Person.md` as the fixed style references (identical process to `wikicommit-schema-propose` Step 4). Set `wikicommit.provenance` in the new file's `wikicommit:` block to whichever of the two outcomes step 3 actually recorded for this candidate — `generate-interactive` if a human answered the Enter prompt, `generate-auto` if it was auto-approved with no prompt shown (Issue #507). Do not copy `Person.md`'s own `provenance: default` value — each write site stamps its own origin. **If the `granularity` you write states a boundary against a type that already has a file in `.wikicommit/schema/`** (e.g. "a TechArticle is reference material, not the ordered step sequence a HowTo covers"), record that fact — the new type name, the installed type it draws the line against, and the bullet itself — for the Completion Notice below (Issue #550). You may not write the reciprocal statement into the installed type's own file — no Skill anywhere can edit an existing schema file, not just this one — so without that report the boundary would exist on one side only and nothing would ever say so. Reporting it is the whole remedy; a human can edit `.wikicommit/schema/` directly (CLAUDE.md's write restriction binds LLMs and Skills, not people). This is conversation-only bookkeeping like step 3's list — not a file write, and not covered by step 5's no-persistence rule. This is the one narrow exception to `wikicommit-generate`'s "Git operations: none, `.wikicommit/schema/`: read-only" contract (Notes below) — it only ever *adds* a file that isn't there yet, never edits or deletes an existing one. No PR is involved and no commit happens here: the new file is left on disk exactly like every other file this Skill writes, and `wikicommit-merge` picks it up later (see that Skill's updated `git add` scope).

   **Writing the new type's `granularity` (Issue #552)**: this is the one part of the file that is
   free prose rather than a verified value, and nothing downstream checks it — `validate_frontmatter.py`
   reads only `wikicommit.frontmatter.required`, `check_schema_org_type.py` verifies existence and not
   wording, and `wikicommit-merge` auto-merges the file along with the run's wiki pages. Whatever you
   write here is what that Wiki's type selection follows from then on, and no Skill can ever edit it
   afterwards. So:

   - Write 1–3 rules, in the style of `.wikicommit/schema/Person.md` and `.wikicommit/schema/DefinedTerm.md`,
     grounded in what this specific source actually contained rather than in the type's Schema.org
     definition in the abstract. State when a page of this type should be created and when the subject
     belongs in someone else's page instead.
   - Include one rule starting with `Boundary` saying what the type is *not* for (the convention every
     distributed base type follows — Issue #550). If it draws the line against a type already installed,
     report it per the paragraph above.
   - Where another **installed** type is the better home for a recognizable class of subject, say so as
     its own rule and name that type: `Prefer schema:HowTo when the source's substance is an ordered set
     of steps the reader performs`. `granularity` is where cross-type deference lives — there is no
     separate field for it, and Pass 2c is instructed to follow such a line over its own read of the fit
     (Issue #569). Deference is not the same as the `Boundary` rule above: `Boundary` says what the type
     is not, this says who should have it instead, and a type can want both. Name only types that are
     actually installed — a line pointing at a type this wiki does not have cannot be acted on.
   - Every bullet has to survive YAML parsing as a plain **string**. Write the boundary rule as
     `Boundary — …` with an em dash, never `Boundary: …`: a `": "` inside an unquoted list item turns
     that bullet into a one-key mapping, and every consumer that filters on `isinstance(g, str)` (e.g.
     `check_property_wikilink_reinforcement.py`) then skips it — that one script warns that it did, no other consumer does. Likewise a ` #` anywhere
     but the very end of an unquoted bullet opens a YAML comment and silently truncates the rest of the
     line. If the wording you want needs either character, wrap the whole bullet in double quotes — the
     same fix the installed base-type templates use (see `.wikicommit/schema/DefinedTerm.md`). Nothing
     validates a schema file, so a bullet mangled this way is merged and stays broken.
   - **Never write a rule that contradicts a rule this SKILL.md states elsewhere.** The known collision
     is Pass 2a's source-as-entity test: it admits a source with a fixed publication date and authors
     (a single-instance work) and *excludes* a continuously-updated living resource with no publication
     date of its own — an official document, a government procedure page, a Wikipedia article. A
     `granularity` saying official product documentation qualifies for a page of its own contradicts it
     head-on. This exact contradiction was written in a real run and left in that Wiki permanently
     (`TechArticle.md`); the run only came out right because the agent happened to follow Pass 2a, and
     nothing guarantees the next one will. When the type you are adding is a kind of *document* rather
     than a kind of subject discussed *inside* documents, re-read Pass 2a before writing the rule.
   - Do not restate Pass 2a/2c rules that already apply to every type — a `granularity` is for what is
     specific to *this* type. Repeating a general rule is how it gets paraphrased into a contradiction.

5. Rejected or no-candidate types are simply not added — there is no **persistence** of a declined candidate to any file anywhere (deliberately: an indirect signal that only surfaces "later, maybe" was the exact problem this Issue replaces). The running list from step 3 above is the one narrow exception, and it stays that way on purpose: it is reported once, in this run's own Completion Notice, and then gone — never written to a management file, never something a *later*, separate `/wikicommit-generate` invocation (with no memory of this run) could discover. If content generated in this run ends up using a `type:` string with no dedicated schema file regardless (e.g. because Pass 2b found nothing but Pass 2c still needs `ambiguous: true` for some other reason), `wikicommit-schema-propose`'s `check_schema_coverage.py`-based scan remains the post-hoc safety net (see that Skill's Notes) — but **not** for a declined candidate that fell back to an already-covered installed type (e.g. `schema:DefinedTerm`): `check_schema_coverage.py` only detects `type:` strings with *no* dedicated schema file, so it cannot tell a declined-then-fell-back-to-`DefinedTerm` page apart from a page that was always meant to be `DefinedTerm` (Issue #447's documented limitation) — do not suggest `/wikicommit-schema-propose` as a way to reconsider a declined Pass 2b candidate; see the Completion Notice section below for the guidance to give instead.

#### Pass 2c: Entity Extraction (LLM → JSON)

**Stamp `--pass pass2c-entities` on entry**, with `--source` naming this source's management file.

Ask the LLM to analyze the extracted text and return **only** the following JSON (no Markdown code block wrapper):

```json
{
  "summary": "2-3 sentence summary of the source's content, in <primary_lang>. If any entities were excluded (theme mismatch or entity policy), briefly note the reason here too.",
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
      "existing_path": null,
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

The `kilimanjaro-coffee` example illustrates `coverage_gap_note` (Issue #284): the source text states the coffee's growing altitude, but `.wikicommit/schema/DefinedTerm.md`'s `properties:` block has no field for it, so the LLM records the gap in one sentence instead of silently dropping it or inventing a frontmatter field.

Note that the example above mixes English (`exclude_note` on `Unrelated Corp`) and Japanese (`coverage_gap_note` on `kilimanjaro-coffee`) purely to illustrate several unrelated rules side by side — in an actual run all of `summary`, `exclude_note`, and `coverage_gap_note` must share a single language, `<primary_lang>` (Issue #314; see the rules below).

Provide the LLM with the following context:
- Full extracted text
- List of schema type filenames under `.wikicommit/schema/` (with their `wikicommit.base` values) — **re-scan the directory after Pass 2b**, so any type just added there is available as a candidate here
- **How those installed types relate to each other**, from `python .wikicommit/scripts/check_schema_org_type.py --list-installed-hierarchy` (Issue #565). One tab-separated line per installed type: the type, then its installed ancestor types nearest-first, or `-`. Run it once per source, after the Pass 2b re-scan above, and include the output verbatim
- `wikicommit.granularity` rules from each schema file
- The `properties:` field list (the keys under each schema file's `properties:` block) from each schema file (used for `coverage_gap_note` detection below)
- Existing pages under `.wikicommit/entity/<primary_lang>/` (title + path) — **include both pages already on `main` and pages written during this run** (scan the directory on disk; do not use `git ls-files` — it only sees tracked files and will miss pages written earlier in this run; do not use `git status`)
- Body section of the source management file (used as additional instructions for the LLM)
- The `schema:` field from the source management file, if present (e.g., `schema: schema:Person`). When provided, instruct the LLM to treat this as a strong type preference and use it unless the source content clearly contradicts it.
- The `theme` value obtained from `config.yml`. If non-empty, instruct the LLM to set `action: exclude` on entities unrelated to `theme`. If `theme` is empty, instruct the LLM not to use `exclude_reason: "theme_mismatch"` at all — no entity may be excluded as off-subject. Say that in those terms rather than as "never use `exclude`": the entity policy in the next bullet is a separate axis that can still exclude an entity here, and a wiki left with the default blank `theme` is exactly the wiki where forbidding `exclude` outright would silently disable it.
- The entity policy held above: `exclude_living_persons` and the body prose. Pass both verbatim, and keep them labelled as the permissibility axis so the LLM does not weigh them as relevance — a subject can be squarely on-`theme` and still fall under this policy, and the reverse. When the switch is `false` **and** there is no prose, say so explicitly rather than omitting it: `exclude_reason: "privacy"` must not be used at all in that case, the same way an empty `theme` forbids `theme_mismatch`.
- The current list of type strings already in use by wiki pages that have no dedicated `.wikicommit/schema/` file yet: run `python .wikicommit/scripts/check_schema_coverage.py` once per run and include its `UNCOVERED:` lines. This helps the LLM reuse an existing not-yet-schematized type string for the same concept instead of coining a new one (convergence is encouraged, not guaranteed — see `check_schema_coverage.py`'s own exact-match-only design note). If the list is empty (e.g. first run), omit this from the context.

Set the `lang` field to the `primary_lang` value obtained from `config.yml` for all entities.

Rules:
- Set `slug` following this priority order (Issue #193 — the file name must remain a language-neutral English identifier per CLAUDE.md's WikiLink convention, not a phonetic transliteration of the source language):
  1. Common nouns / concept terms → translate to English (e.g. `キリマンジャロコーヒー` → `kilimanjaro-coffee`; `kirimanjaro-koohii` is a transliteration and not acceptable).
  2. Proper nouns (people, organizations, places, etc.) that have an established English spelling → use that spelling (e.g. `スターバックス` → `starbucks`; `sutaabakkusu` is not acceptable).
  3. Proper nouns with no established English spelling → romanize (e.g. `山田太郎` → `yamada-taro`).
- **Source-as-entity candidates (Issue #475)**: when Pass 2a flagged the source document itself as a citable standalone work, include it as an ordinary entity in this array — its `title` is the work's own original title *verbatim, in whatever language the source itself uses* (e.g. the paper's actual published title), not a concept discussed within it and not translated into `<primary_lang>` — a citable work is identified by its real title, and translating it would defeat the citability this entity exists to capture (this is a narrow, deliberate exception to the general "entity content is written in `<primary_lang>`" rule; the page's `lang` field and body content still follow `<primary_lang>` as usual, only the `title` value itself stays verbatim). `slug` follows the same priority rules above applied to that original title; `type` is whatever Pass 2b resolved for it, or the nearest fitting `installed schema/` type if Pass 2b found nothing. It participates in `action`/`existing_path`/`ambiguous`/`exclude` exactly like any other entity, and nothing about `sources:` changes for it — its page's `sources` is simply the one-element list wrapping this registered source, same as any other `action: create` entity (Pass 3 step 5 below). This entity is *in addition to*, not instead of, the concepts/people/organizations Pass 2c extracts from within the source as usual.
- Always generate `summary` (2-3 sentences), regardless of whether `theme` is set. This should match the Pass 2a summary unless something in the fuller entity-extraction pass changed the LLM's read of the source — do not treat Pass 2a's summary as merely a draft to diverge from.
- Set `action: update` and `existing_path` if a page with the same type and slug already exists — **scan the directory on disk** (do not use `git ls-files`; it only sees tracked files and will miss pages written by earlier sources in this run). A page written by an earlier source in the same run must be detected as `action: update`, not `action: create`.
- **When several installed types fit, take the most specific one (Issue #565)** — the one furthest down the `--list-installed-hierarchy` chain, not the one highest up. An ancestor type always fits: `Park` and `Museum` are descendants of `Place`, so writing a park as a `Place` is never *wrong*, only coarser, and the broader type is the more familiar one to reach for. That combination is why this needs saying out loud rather than being left to the model's judgment: `wikicommit/saitama-city-wiki` had `Park.md` and `Museum.md` installed and human-approved, and generated seven parks plus two museums as plain `Place` — in the same batch that added the type files, so nothing was stale. Every quality gate passed, because `Place` does have a schema file. What is lost is real: that type's `properties:` go unused and its content ends up as prose in the body, and its `index.md` — one of the wiki's main ways to get around — lists a fraction of what belongs there.

  This applies only to types **installed in `.wikicommit/schema/`**. A more specific type that exists in Schema.org but has no file here is Pass 2b's business, not this step's; do not reach past the installed set. And specificity never overrides fit — if the source does not actually establish that the subject is a park, `Place` is the correct answer, not a fallback.

  **A `granularity` line that names another type outranks your own read of the fit (Issue #569)**. Some type files say, in so many words, when their type is *not* the answer — "prefer `schema:HowTo` when the source's substance is an ordered set of steps the resident performs". When a candidate type's `granularity` hands the case to another type and that other type is installed, follow it. Its author had the whole type in view when they wrote it; you have one source. In `wikicommit/saitama-city-wiki` a `GovernmentService.md` carrying exactly that line produced six `GovernmentService` pages and zero `HowTo` — including one written from a document titled "how to put out household waste" whose substance is a numbered procedure (call the centre, note the reservation number, buy the fee sticker, attach it, put it out before 08:30) and whose page reproduces that procedure step by step. The line was not contradicted; it was simply not weighed. What makes this worth stating is who wrote the line: `GovernmentService.md` is not a distributed template — it was written minutes earlier, by an LLM, in `wikicommit-init`'s own type-proposal step, and then not followed by the same model in Pass 2c.

  Two things follow. If the type it defers to is **not installed**, the deference cannot be acted on — stay with the type you have, and let Pass 2b decide separately whether that other type should exist here. And a deference line is about *this* subject, not the source: a source can perfectly well yield one entity of each type, which is the next rule.
- **One source may yield entities of different types, and sometimes should (Issue #569)**. Nothing has ever restricted the `entities` array to a single type — but nothing said to look for the split either, and a source that is mostly about one thing tends to come out as one entity. When a source covers both a thing and a procedure for using it, extract both: a service and the steps for applying to it, a piece of software and a walkthrough for setting it up, an institution and its admission process. The waste-disposal source above should have produced a `GovernmentService` for the collection service and a `HowTo` for putting out bulky waste; instead one page carried both, at 48 body lines against the 15–20 of its siblings — the size difference is the tell that two subjects were sharing a page. Split only where each part stands on its own as a subject; do not manufacture a second entity to satisfy this rule.
- **Tabular sources: judge independence by the columns, not by the row count (Issue #568)**. The schema templates ask whether the source states independent facts about a subject, and in prose the *amount* said about something stands in for that — a paragraph means more than a passing clause. A table breaks that proxy: every row is one row, so a subject with eight attributes and a subject with one look identical by volume. Ask instead what a row's **columns** actually say about it. A row carrying several attributes of its own — a location, a size, a date range, a category — states independent facts and can support a page. A row that carries a name and one relationship does not, and the sheer size of the table around it changes nothing. Where one subject occupies several rows, read those rows together: the same relationship repeated is still one relationship, but if they give that subject a scale, a span or a spread of its own (how many, over what period, of what kinds), the columns are stating attributes of the subject and it can support a page. Aggregating a subject's own rows is the half that is easy to miss — it is what the pilot below got wrong.

  When a row yields nothing but that one relationship, **do not create a page for it**. Record the relationship on the *other* end if a page for it already exists (`action: update`), and otherwise let it go — the table itself stays reachable through the page's `sources` and through the source's own page under `content/sources/`, which links back to it. A page written from such a row can only say who is currently responsible for something and until when, which is a fact about a contract, not about the thing.

  Do put the table's *shape* somewhere: the concept the table is about — the scheme, the programme, the category — is usually a real entity with real content, and the aggregate belongs on that page as a characterization (how many, how concentrated, what the range is), not as the rows written out. In `wikicommit/saitama-city-wiki` a 236-facility spreadsheet with six columns (facility, facility count, operator, term in years, selection method, owning department) yielded five pages and no facility pages at all. That count was defensible — the sheet says nothing about what any facility *is* or where it stands — but it was reached by reading "one row" as "incidental", which also dropped six mid-sized operators. Both halves follow from the column test: a facility fails it because no column says anything about the facility itself, while an operator clears it because its own rows, read together, give it a scale (thirteen facilities, eight facilities), a span of terms and a mix of selection methods — attributes of the operator, not of any one contract. The bare row count never should have entered into it.
- Set `ambiguous: true` when the LLM cannot confidently determine the type; include candidates in `alternatives`
- Skip entities with `ambiguous: true` during page generation. **Immediately** notify the user (console output) with the entity's `title`, candidate `alternatives`, and the source management file at the moment of detection — a later source in the same run may abort processing (e.g., missing prerequisite skill, `config.yml` missing, extraction failure) before the Completion Notice is reached, so this notice must not depend on the run completing. Also append the entity to a running list so all detections can be rolled up together in the Completion Notice below.
- Set `action: exclude` (only when `theme` is non-empty) for entities the LLM judges unrelated to `theme`. Set `exclude_reason: "theme_mismatch"` and a short `exclude_note` explaining why, written in `<primary_lang>` — the same language as `summary` (Issue #314; do not let the agent's session/UI language leak in here, which is what caused `## Summary` to mix languages in the `llm-agent-research-wiki` pilot). No human confirmation is needed for `exclude` (unlike `ambiguous`) — it is applied automatically and silently, recorded only in the management file's `## Summary` (see below) and the Completion Notice.
- **Set `action: exclude` with `exclude_reason: "privacy"` for entities the entity policy rules out (Issue #667)**, on the same terms as `theme_mismatch`: automatic, no human confirmation, an `exclude_note` in `<primary_lang>` saying which part of the policy applies. This is a second, independent reason to exclude, not a variant of the first — judge relevance against `theme` and permissibility against the policy separately, and where both would exclude the same entity, record `privacy`, since it is the reason that would still hold if the wiki's subject changed. It fires on two inputs:
  - `exclude_living_persons: true` → an entity this source establishes to be a living individual. Judge that as you judge relevance: from what the source says. Where the source does not establish it either way, do not exclude — this switch is about people the source shows to be living, not about anyone it fails to mention a death for.
  - the body prose → whatever categories it names. It is free text and is not limited to people; a policy can rule out matters under dispute (`Event`-shaped) or an organization's unreleased information just as well.

  **Do not over-apply it.** The prose typically names who is *in* as well as who is out, and a wiki that keeps out public figures acting in their public capacity, or historical figures, has lost pages it had every reason to hold. In `wikicommit/saitama-city-wiki` `theme` alone was used for this and the wiki ended up with zero `Person` pages, three of the four people dropped being historical figures (died 1486, 1738 and 1830) repeatedly named in its own body text — the pilot's own notes record that outcome as questionable. Where the policy does not clearly reach a subject, generate the page; this judgment has a safe direction and it is not the exclusion.

  Nothing here reaches back. Turning the switch on does not remove pages that already exist, because `--regenerate` does not run this pass — say so in the Completion Notice below, and point at `/wikicommit-remove` (`removed_reason: gdpr` where that applies) as the way to take one down.
- Set `expires_at` to a concrete `YYYY-MM-DD` date only when the source text explicitly states a calendar date after which the entity's content is expected to be stale — an application deadline, a fiscal-year-bound validity period, a stated expiration date, etc. (Issue #279 — this field previously went unused because Pass 2 never surfaced source-stated dates as a candidate.) Otherwise leave it `null`; never guess or infer a date that is not written in the source (e.g. do not translate a vague "来年度まで" into a specific date), and never derive it from unrelated context like the source's publication date. If the source states several distinct dates that could each plausibly apply to the entity (e.g. different deadlines per sub-case, as in the `GovernmentService` example above), set `expires_at` to the **earliest** of them — `expires_at` exists to prompt a re-check by the review process (`check_expires.py`), and it is safer to flag content for re-review too early than too late; the full breakdown of all the dates still belongs in the page body, which this field does not replace.
- Set `coverage_gap_note` (Issue #284) to a **single sentence** when the source text contains a concrete, domain-specific attribute for this entity (e.g. target age range, required tools, jurisdiction) that has no corresponding field in the entity's type schema's `properties:` block. If an entity has multiple such gaps, summarize them all in one sentence (do not use an array — follow the same single-string design as `exclude_note`). This applies only to `create`/`update` entities (never `exclude` or `ambiguous` ones). This is evidence-gathering only: never write to `.wikicommit/schema/` and never invent a new frontmatter field to hold the value — the gap information still belongs in the page body as usual, unaffected by this note. Leave `coverage_gap_note` `null` when nothing is missing, which is expected to be the common case. When non-null, write it in `<primary_lang>` — the same language as `summary` (Issue #314; same reasoning as `exclude_note` above).
- After obtaining the JSON, write its `summary` field into the source management file's `## Summary` section: create the section (`## Summary` heading followed by the text) if it does not already exist, or overwrite its existing contents if it does. If one or more entities have a non-null `coverage_gap_note`, append them to the same `## Summary` write, one sentence per entity (e.g. `"「キリマンジャロコーヒー」: 産地の標高（1,600〜2,000m）の記載があったが DefinedTerm.md の properties フィールドに受け皿がないため本文にのみ記載"`) — this is the same write, not a separate step, so it must land in the same overwrite as `summary`. Since `exclude_note`/`coverage_gap_note` are already required to be in `<primary_lang>` (same as `summary`, see above), this write never needs to translate anything to make the section consistent — do not translate at write time either. **Never modify a `## User Notes` section** if present — that section is hand-written by a human and must be preserved verbatim. <!-- skill-language-exception: example coverage_gap_note text, quoted to show the shape of the sentence written into ## Summary -->

  > **Heading labels are always fixed English, regardless of `primary_lang`** (Issue #405 — a `primary_lang: en` pilot found the `## サマリ`/`## ユーザーメモ` heading labels hard-coded in Japanese even though the `summary` body text itself was correctly written in English per Issue #314). The source management file is an internal bookkeeping file under `.wikicommit/source/`, not reader-facing wiki content, so it is not localized: always write `## Summary` and `## User Notes` verbatim, never a translated or `primary_lang`-dependent heading. Pre-existing management files generated before this change keep their old `## サマリ`/`## ユーザーメモ` headings as-is (no automatic migration, same "both forms may coexist" policy the source-tree layout itself already follows); only newly written/overwritten `## Summary` sections use the new heading. If a management file still has the old `## サマリ` heading, treat it as the same section (overwrite it in place rather than adding a second, redundant `## Summary` section) — but do not rename an untouched `## ユーザーメモ` heading you are not otherwise touching, since that section must be preserved verbatim per the rule above.

For `action: update` entities, read the existing page with the Read tool and add it as additional context for Pass 3.

### Pass 3: Page Generation (File Boundary Protocol)

**Stamp `--pass pass3-generate` on entry**, with `--source` naming this source's management file (under `--regenerate`, the page being rebuilt).

**Guard**: before generating any page for this source, if `source.type` is `url` or `wikicommit`, re-read the management file and confirm `source.hash` is non-empty (not `""`). This should already hold — Pass 1's hash write-back step (above) fails the source before reaching Pass 2 otherwise — but re-check here as a safety net (e.g. against a management file left over from before this guard existed). If `source.hash` is still empty, mark this source `status: failed`, write a reason to the management file's `## Failure Reason` section (create it if absent, overwrite if present — e.g. `"source.hash was still empty when Pass 3 was reached; the source could not be confirmed as fetched during Pass 1 (safety-net guard)."`) in English regardless of `<primary_lang>` (same reasoning as the Pass 1 extraction-failure case above — Issue #408), notify the user, and skip Pass 2–4 for it entirely; never write a page whose `sources[].hash` would be empty.

For each entity where `ambiguous: false` and `action` is `create` or `update` (skip `action: exclude` entities entirely — no page generation, no review; they were already recorded in the Pass 2 `## Summary` write):

1. Derive the schema file path from the entity's `type` field:
   - Strip the `schema:` prefix: `schema:Person` → `Person`
   - For custom types, keep the sub-path: `schema:custom/Decision` → `custom/Decision`
   - Schema file path: `.wikicommit/schema/<derived-name>.md`
   - This same `<derived-name>` — `/` and all — is the `<Type>` path segment of the page written in step 2 below: `.wikicommit/entity/<lang>/<derived-name>/<slug>.md`, so a `schema:custom/Decision` entity goes to `.wikicommit/entity/<lang>/custom/Decision/`, never `.wikicommit/entity/<lang>/Decision/`. Stated explicitly because the file-boundary-protocol example below only shows a standard type; leaving the custom case to inference is exactly what made `/wikicommit-synthesize`'s output path non-deterministic (Issue #545), and `validate_frontmatter.py` now reports a page whose path and `type:` disagree as an ERROR.
   - If the schema file does not exist, fall back to `.wikicommit/schema/default.md` — and **append this entity to a running list rolled up in the Completion Notice below** (Issue #575), recording the `type:` value, the schema path that was looked for, the entity's `title`, and the source source management file. In Regeneration Mode there is no Completion Notice — roll the same list into that mode's per-page report instead. The fallback itself is correct and intended behavior for a type with no dedicated file, so do not stop or ask for confirmation; what must not stay silent is its consequence. Falling back drops that type's `granularity` rules, its `properties:` candidate keys, and its body template **in their entirety**, and the resulting page still looks well-formed — `validate_frontmatter.py` applies only `default.md`'s required fields, so the page passes every required-field check. It does emit a non-blocking WARNING naming the missing schema file, but `wikicommit-merge` runs it over the files that batch happens to change, so a page written now and never edited again is never re-checked. Every other partial outcome this Skill can produce (`ambiguous`, `exclude`, `failed_pages`, a Pass 2b type addition) is listed in that Notice; a type definition that never applied is at least as consequential.
   - This lookup is a plain path derivation — `.wikicommit/schema/<derived-name>.md`, nothing scans the directory for a file by type name — so moving `Person.md` into, say, `.wikicommit/schema/standard/` disables it just as thoroughly as deleting it. Subdirectories under `.wikicommit/schema/` carry no meaning beyond the `custom/` segment that is itself part of the type name.
   - Parse the schema file as Markdown-with-frontmatter. `wikicommit:` key = schema instructions (do **not** include in generated pages). Other top-level frontmatter keys (e.g. `title`, `type`, `lang`, `sources`, `tags`) + the nested `properties:` block (Issue #495 — Schema.org-vocabulary-backed, type-specific fields such as `description`/`affiliation`/`jobTitle`) + Markdown body = wiki page template structure — fill in actual values; do not copy placeholder empty strings or empty lists verbatim. **A key you cannot fill is omitted, not left empty** (Issue #553): when the source states nothing that belongs under a `properties:` key, drop that key from the generated page entirely rather than carrying the template's `""` or `[]` through. Every `properties:` key is optional — no type can mark one required (Issue #495) — so omitting is always valid, while an empty value is indistinguishable from "the source says this is blank" and is rendered to readers as an empty row by the `wikicommit-properties` plugin. This is the specific failure `DefinedTerm.inDefinedTermSet` produced before it was removed from that template: 14 of 43 pages in one wiki carried the key and none of them carried a value, because the key was neither fillable nor dropped. **This rule only decides what a key the template offers gets written as; it never removes a value the page already holds.** For an `action: update` entity, a `properties:` key the existing page already carries a value for is left exactly as it is when this source says nothing about it — same reasoning as `expires_at` in step 3 below, where "this source didn't mention it" is not "there is nothing to record." That applies equally to a key the current template no longer lists at all (e.g. a page written when `DefinedTerm` still shipped `termCode`/`inDefinedTermSet`): those keys remain valid — `validate_frontmatter.py` checks a `properties:` key against Schema.org's `domainIncludes`, not against the template's key list — so carry them across unchanged instead of stripping them. **If every key ends up omitted, omit the `properties:` key itself** rather than writing it with nothing under it: a value-less `properties:` parses as YAML null, which the `wikicommit-properties` plugin renders as one more empty row — the very outcome this rule exists to prevent. Keep `properties:` nested exactly as the schema file has it — do not flatten its keys up to the top level of the generated page's frontmatter. Keep the body's heading levels as the template has them too: every schema template's body opens with a paragraph or a `##` heading and none of them uses an H1, so **do not add a `# <title>` line at the top of a generated page** — the title lives in the `title` frontmatter field and Quartz renders that as the page heading (Issue #546).
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

     Each `--property` value is passed through its own quote-delimited heredoc, not a plain double-quote embedding: these key names come straight out of `.wikicommit/schema/<Type>.md`, a human-editable file this Skill only reads, so — unlike `<Type>` here, which the standard-type path already resolves through `check_schema_org_type.py --type <Type>` verification before use — they have not themselves undergone any upstream validation before being embedded into this exact command line. Pass every `properties:` key from the template. This is the same verification call Pass 2b already runs when adding a new type (see that step's own `--property` invocation, updated to the same heredoc form); here it also runs for the pre-installed base types (which never went through Pass 2b). See "Property-value WikiLinks" below for how the resulting `RANGE:` lines are used. Skip this call entirely for `custom/` types — they have no Schema.org vocabulary entry to query (same reasoning as `properties:`'s own domainIncludes check, `validate_frontmatter.py`).

   **`properties:` vs. body placement (Issue #495)**: `properties:` may only hold short, structured values a source states as a single fact — a date, a proper noun, a URL, a reference to another entity (as a WikiLink). Multi-sentence explanation, context, causal reasoning, or synthesis across multiple facts belongs in the body instead, even when a matching Schema.org property name technically exists (e.g. a lengthy `description` is not a reason to also try to cram the same material into another property). Keep `properties.description` itself to a 2-3 sentence summary — the fuller account belongs under a body heading (e.g. `## Background`). This is domain-independent, applies regardless of the wiki's theme, and is close to a restatement of what the existing template body-heading structure (e.g. `## Background`, `## Usage`) already implies rather than a new constraint.

   **Property-value WikiLinks (Issue #496)**: for each `properties:` key, decide whether its value should be written as a `[[Type/slug]]` WikiLink to another entity page rather than a plain scalar, based on the `RANGE:` classification cached in step 1 above:
   - *Entity-only* (e.g. `affiliation` → `Organization`, `birthPlace` → `Place`): if the value names an entity that is (or should become) its own page, write it as a WikiLink. Do not force a WikiLink for an incidental mention that fails the *referenced* entity's own type's independent-subject bar (e.g. Person.md/Organization.md's "named only as someone's employer/affiliation, no independent facts stated" rule) — write the plain name as text in that case instead, same as an incidental mention in body text would be handled.
   - *DataType-only* (e.g. `sameAs` → `URL`): never WikiLink this property's value — always a plain scalar.
   - *Mixed* (e.g. `jobTitle` → `DefinedTerm` or `Text`; `description` → `TextObject` or `Text` — despite the name, `TextObject` is an entity type, not a DataType): WikiLink only when the value genuinely names a distinct entity that independently qualifies for its own page; otherwise write it as a plain scalar. Most `jobTitle`/`description` values ("シニアエンジニア", a one-sentence summary) are plain text, not a `[[DefinedTerm/...]]`/`[[...]]` reference — only WikiLink when the source itself treats the value as referring to a separately citable/definable entity worth its own page.

   **Apply this uniformly across every Entity-only/Mixed property of the type — a `granularity` entry or an inline `[[Type/slug]]` placeholder calling out one specific property is a human-readability aid, not a scope-narrowing statement (Issue #523)**: some type templates additionally reinforce this rule for one property, either in `granularity` prose (e.g. `BlogPosting.md`/`NewsArticle.md`'s `author` line) or via a `properties:` placeholder already written as `"[[Type/slug]]"` instead of `""` (e.g. `Organization.md`'s `founder: "[[Person/slug]]"`). The observation behind Issue #523 found two otherwise-comparable generated pages that disagreed on WikiLinking `publisher` even though it has the identical Entity-only classification as `author` (both resolve to `Organization`/`Person` via `--show-range`) and `publisher` had no such reinforcement on either template — a small-sample observation, not a statistically validated rate difference, but the reinforcement asymmetry is the only difference between the two properties. Fixed for `publisher` (both templates) and, since checking the other base-type templates the same way turned up the identical unreinforced-Entity-only-property shape, also for `Organization.md`'s `foundingLocation`, `Person.md`'s `affiliation`, `Place.md`'s `containedInPlace`, and `Event.md`'s `organizer`/`performer`. Whether a property happens to carry this kind of reinforcement is not something to infer meaning from either way — the RANGE classification from step 1 above is the complete and only input to this decision.

   **Use the Type an existing page already has — never guess a Type for a slug that is already taken (Issue #563)**: once you have decided a value gets written as `[[Type/slug]]`, look up whether `.wikicommit/entity/*/*/<slug>.md` already exists under *any* Type (the existing-page list you were given in Pass 2 is the same inventory), and if it does, use that page's Type verbatim rather than the one the property's `RANGE:` line suggests. A link resolves only when both segments match, so `[[Organization/saitama-city]]` written against an existing `AdministrativeArea/saitama-city.md` is simply broken — and it fails in the least visible way, because "the page does not exist" is indistinguishable from a not-yet-written concept unless something checks the other Types. This bites hardest exactly where a `RANGE:` line is most tempting to follow literally: an entity plausibly typed two ways (an administrative body as `AdministrativeArea` or `Organization`, a venue as `Place` or `Organization`, a work as `CreativeWork` or `Book`) will have been filed under exactly one of them. `check_wikilinks.py` blocks this case as an ERROR naming the Type that actually exists, so getting it wrong costs a `wikicommit-merge` round trip.

   A referenced entity does not need to already have a page for the WikiLink to be valid: `check_wikilinks.py` reports an unresolved WikiLink as a non-blocking WARNING (Issue #340) and `check_wanted_pages.py` tracks it as a WANTED page, exactly as an unresolved WikiLink in body text already works today — both scripts scan the whole file as raw text and do not distinguish frontmatter from body (confirmed for `check_wikilinks.py`/`check_orphans.py`/`check_wanted_pages.py`; no changes were needed to any of them for this Issue). Do not let "the target page doesn't exist yet" stop you from writing the WikiLink. This is advisory, not mechanically enforced: `validate_frontmatter.py` does not require an entity-range property's value to be a WikiLink (Issue #495's `properties:` `domainIncludes` check verifies the *key* belongs to the type; it says nothing about the *value*'s shape) — whether to actually write one is left to this generation-time judgment call, same as any other body-text WikiLink decision.

   **Check the whole value list before moving on, not one value at a time (Issue #561)**: after writing a property whose value is a list, read the list back. If some entries came out as `[[Type/slug]]` and others as plain strings, every plain one must be plain because *that particular entity* does not clear the independent-subject bar of the type its page would have — the reason the paragraph above gives for leaving a value unlinked. "Its page does not exist yet" is not that reason and never makes a value plain; neither does "I did not happen to see it in the existing-page list". A list whose entries are all the same kind of thing (a cast of characters, a set of providers) should come out all linked or all plain; a split inside one such list is the shape to stop and re-check. This is what went wrong in `wikicommit/decameron-wiki`: a `Book`'s `character` listed ten narrators, and the eight whose `Person` pages an earlier ingest had already written were WikiLinks while the two a later ingest created were bare strings — same property, same type, same qualification, split purely by the order the sources were ingested in. Nothing repairs that afterwards, because `action: update` reaches a page only when a source for *that page* is re-ingested, so the later ingest that finally created the two pages had no reason to revisit the Book page. `check_unlinked_entity_mentions.py` reports the case once it has happened, and `/wikicommit-fix <page-path> "<instruction>"` is how it gets repaired.

   **Granularity discipline (Issue #337)**: the page body and `description` must match the schema template's abstraction level, not the source's level of detail. `.wikicommit/schema/<Type>.md`'s body template already encodes the intended abstraction — e.g. `DefinedTerm.md`'s "(Precise one-paragraph definition of the term)" means a single dense paragraph, not an exhaustive account — and this holds regardless of how much raw detail the source text makes available. This matters most when the source is programming language source code (`.py`/`.kt`/`.ts`/etc., typically extracted via the "その他 → markitdown" fallback in the extraction routing table above): source code already reads as prose-adjacent, so the natural failure mode is transcribing implementation internals (internal function/variable names, regex construction logic, class field layouts) straight into the page instead of summarizing them. This actually happened in the `Paperwork-Navigator-wikicommit-pilot` pilot — ingesting a `.kt` file produced `DefinedTerm` pages that read as implementation notes for the developers who wrote the code, not concept definitions for a general reader. When the source is code, describe the concept, its purpose, and how it's used at a level a non-programmer reader can follow; do not name internal functions/variables or restate algorithm steps in prose. Implementation-level detail is not lost — it stays reachable via `sources` (a reader who needs it can open the source file directly) — it just does not belong duplicated into the page body. **The same failure has a tabular form (Issue #568)**: a spreadsheet or CSV extracted to a Markdown table invites narrating the rows back out — one sentence per row, or a paragraph listing every value in a column. In `wikicommit/saitama-city-wiki` a `DefinedTerm` page about a public-facility management scheme opened with a precise, correct definition and then spent fifteen lines restating the table, one of which enumerated all eighteen owning departments by name. Every figure was right; none of it was a definition. Write what the table *shows* — the scale, the shape of the distribution, the handful of facts that would still be true next year — and leave the rows to `sources`. Contract dates and counts go stale within a few years, so transcribing them also quietly hands the page an expiry no `expires_at` is tracking.

   **Thin-source discipline (Issue #428)**: the instruction above to "fill in actual values" does not mean every template heading must be padded into a full-looking section regardless of how little material the source actually contains. When the source does not contain enough material to substantively fill a template section (e.g. no chronological activity/affiliation history for a Person's `## Background` — only a single quoted remark), write only what the source actually supports, even a single accurate sentence, rather than padding with generic, contentless filler to make the section look complete. A short, honest section is preferable to a padded one that restates the same fact across multiple headings — this happened across all 5 `Person/` pages in the `ai-driven-dev-wiki` pilot, where `## Background` converged on the same boilerplate phrasing regardless of how much the source actually said about each person. This is the mirror image of granularity discipline above: that rule reins in over-detailed sources, this one reins in under-filling instructions being read as "manufacture content regardless of source thinness."

   **Omit a heading you can only fill by repeating yourself (Issue #571)**. The rule above says write the one honest sentence rather than padding; this says where even that has no home, leave the heading out. A 239-character page whose `Geography & Access` and `History & Significance` sections were the first and second halves of its own opening paragraph made the reader read the same thing twice, and five sibling pages did it too. The template's headings are the shape a well-sourced page of that type takes, not a form to complete. Keep a heading when the source gives it something of its own; drop it otherwise.

   **Do not write about what the source did not say (Issue #571)**. A page's body is for the subject, not for the state of the evidence about it — "the tourism site used as a source only introduces the facility in outline and says nothing about its history" is a note about this run, and it shipped to readers. Such an observation belongs in what you report to the operator at the end of the run, not in the page: drop the sentence and, where the missing material would have filled a template heading, drop the heading too (the rule above). Do not reach for `coverage_gap_note` instead — that field is Pass 2's and means something narrower (the source *does* state an attribute and the type schema's `properties:` block has no field for it), and Pass 2 has already written `## Summary` by the time this pass runs. It is the same separation Issue #524 drew when it moved translator notes out of page bodies.

   **The line is what the remark is about.** A remark about *how this page came to be written* — a source's coverage, what could not be found, which source was used — is out. A remark about *how confident the content is* stays in: "the founding date and the shrine's standing are both recorded by the source as tradition" tells a reader how to read what follows, and would be true in any page written from that material. When unsure, ask whether the sentence would still make sense to someone who did not know WikiCommit generated the page.

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
    license: CC-BY-SA-4.0   # only when the management file records one; omit the key otherwise
review_status: pending
generated_at: "2026-06-27"
generated_by: "<current model ID>"
generated_with: "<WikiCommit version>"

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

   Note: `generated_with` is WikiCommit's own version, not a model ID — read it once per run with `python .wikicommit/scripts/_version.py` and write that exact string on every page this run produces (Issue #577). It is what lets a human — reading `CHANGELOG.md` alongside a `grep` for this field — tell which pages were built under an older set of generation rules. If that script is missing (a wiki repository initialized before this field existed), omit the field entirely rather than guessing a version — its absence is meaningful, and no back-fill is performed.

   If the entity's `expires_at` from Pass 2 is non-null, include an `expires_at: "<that date>"` line in the frontmatter. If it is `null`, omit the `expires_at` field from the frontmatter entirely — do not write `expires_at: null` or `expires_at: ""`, since the field is optional and its absence is what `validate_frontmatter.py` and `check_expires.py` expect for "no known expiration".

   `tags` (Issue #275): `tags` is for cross-page filtering, not a restatement of this page's own identity. Do not include a tag identical or near-identical to the entity's own `title` (e.g. do not tag a page titled "認可保育所" with `認可保育所`), and do not include a tag that only restates what `type` already expresses (e.g. do not tag a `schema:Person` page with `person`/`人物`). Only include tags for concepts that are meaningfully shared across multiple pages (field, category, technology, etc.). If a candidate tag names a specific vendor or product, confirm the concept is actually specific to that vendor before including it (Issue #430) — if the vendor is merely one of several sources discussing the concept, and the concept itself is not that vendor's own (e.g. an industry-general term, or one coined/proposed by a different party), do not tag the page with that vendor's name.

   **Attribution accuracy (Issue #429)**: a page's claims are only checked for *truth* by Pass 4, not for whether they're attached to the right origin — attribution errors have to be prevented here, at generation time. When the source text itself attributes a quote or specific wording to a distinct party (e.g. a source article that quotes or paraphrases a third party's documentation, blog post, or public statement), carry that attribution into the page body rather than collapsing it into the page's own voice or attaching it to a different party mentioned nearby in the same paragraph. This matters most when a single paragraph discusses more than one origin (e.g. both "Party A's own documentation" and "a blog post about Party A's tool written by Party B") — keep each direct quote or specific claim tied to whichever origin the source text itself assigns it to; do not let it drift to the other party just because both are discussed together. Separately: when a definition, framework, or formulation is not an established/consensus term but is presented by the source as one specific party's own proposal (a single paper, blog post, or vendor's argument — not something the source frames as general or widely agreed), phrase it in the page as an attributed claim (e.g. "X proposes that...", "According to X, ...") rather than as unqualified fact. Do not strip the attribution and state a single party's proposal as if it were a settled, general truth.

   **Naming vs. inventing (Issue #451)**: when the source describes one party naming or coining a term for a practice/technique ("X calls this Y", "X coined the term Y for the practice of..."), write only that — do not upgrade it into a claim that this party invented, created, or originated the underlying practice itself. These are different, independently-verifiable facts even when the source discusses them in the same sentence; conflating them overstates what the source actually says. If the source is genuinely ambiguous about whether the party invented the practice or only named an existing one, phrase the page's claim at the same level of certainty the source itself uses — do not resolve the ambiguity toward the stronger claim.

   **Auto-generated transcript caution (Issue #574)**: when the source text is a YouTube video's `### Transcript` section, treat it as an approximate record of what was said, not as a verbatim document. YouTube's automatic captions carry no punctuation, routinely mis-transcribe proper nouns and technical terms, do not mark who is speaking, and capture nothing that was only shown on screen (slides, diagrams, code, on-screen text) — and nothing in the extracted text distinguishes an auto-generated track from a human-authored one. So do not state a name's spelling, an exact figure, or a word-for-word quotation as settled fact on transcript evidence alone: write the substance at the level of confidence the transcript actually supports, or corroborate the specific detail against another source registered for this entity. Note that Pass 4 cannot catch this for you — it checks the page against the source text, so a claim that faithfully reproduces a transcription error reads as a PASS.

   **Secondary citation discipline (Issue #473)**: when the source text itself discusses, quotes, summarizes, or links to a *distinct* document — a different article, post, or report the current source mentions in passing, separate from the source document Pass 3 is generating this page from — do not restate that other document's own specific date, title, or individually-attributed detail as a page claim. The current source's mention of it is itself only secondhand (a citation of a citation, sometimes called 孫引き); the `sources` entry available to this generation is the document currently in front of Pass 3, not the document it refers to. Write the claim only at the level of generality the current source actually supports (e.g. "in an earlier post, X also described Y" rather than "in a March 19 post titled Z, X described Y") unless the referenced document has separately been registered as its own `sources` entry for this entity (i.e. it was itself ingested as a source, not merely mentioned by another source). This is a stricter version of the Naming vs. inventing check above: that one guards against overstating what act a party performed; this one guards against borrowing a secondary document's own identifying details (date, title) without that document actually being present among `sources`.

   **Source-entity WikiLinks (Issue #475)**: when this page's content is substantively drawn from a source whose own document Pass 2's source-as-entity judgment generated as a *separate, different* entity page in this same run (e.g. an arXiv paper, an official product-announcement post) — this never applies to the source-entity page's own body referencing itself — mention that source-entity page via a natural WikiLink in the body where it reads naturally (e.g. "as reported in [[ScholarlyArticle/vibe-coding-survey]]") rather than only a bare textual reference. This is the natural complement to `sources:` (hash-based, for audit/freshness) — it does not replace `sources:`, and nothing about `sources:` changes to accommodate it.

3. For `action: update` entities, the LLM must merge new information into the existing page:
   - Update content fields (`description`, body text, `tags`, etc.) with new information from the source
   - Carry the existing `review_status` and `reviewed_by` across unchanged here, and do not decide them in this Pass. **A page that is `reviewed` does not simply stay `reviewed` (Issue #724)**: this same branch rewrites the body, `properties` (`description` included), `tags` and `expires_at` from the new source, and leaving `review_status` where it is would attach a human's sign-off — and, since Issue #663, that human's real name — to text no one has read. Every other write path (`action: create`, `--regenerate`, `wikicommit-translate`, `wikicommit-synthesize`) writes `pending`; this one is the outlier. The decision is not made by judgment: Pass 4 step 6 runs `reset_review_on_content_change.py` on each page it writes, which compares it against `git show HEAD:` and demotes it only when a **content** field actually differs (`sources[]` and the `generated_*` fields do not count — an `action: update` that only appends a source leaves the review standing, which is the whole reason this is a comparison rather than an unconditional reset)
   - Update `generated_at`, `generated_by` and `generated_with` to reflect this generation run
   - Append the new source to the `sources` list only if no entry with the same `path` (or `url`) already exists, carrying that source's `license` across from the management file as in step 5 below. If an entry with the same `path`/`url` is already present, update that entry's `hash` instead of appending a duplicate, and leave its existing `license` alone unless the management file now records one and the page entry has none (Issue #558 — a human may have corrected the page's value, so never overwrite a non-empty one).
   - `expires_at`: if Pass 2 returned a non-null `expires_at` for this entity, set/overwrite the page's `expires_at` with it (a source-stated date takes precedence, since it reflects the most recently ingested information). If Pass 2 returned `null`, leave the existing page's `expires_at` untouched either way (don't add one, and don't clear one a human or an earlier run may have set) — `null` here only means "this source didn't mention a date," not "there is no expiration."
   - **Attribution accuracy across merged sources (Issue #429)**: the existing page content being merged into may already carry claims/quotes attributed to whichever source produced it earlier. When folding the new source's material into the same paragraph or section, keep each claim tied to whichever of the (now multiple) sources actually said it — do not let a claim's attribution silently shift to the other source just because they now sit next to each other. If a single-source formulation from the prior version is retained as-is, its attribution phrasing must be preserved, not dropped, even if the new source's material is unattributed general description.
4. Set `generated_by` to the **currently running model ID** (e.g., `claude-sonnet-4-6`). Use the actual model ID in use, not a hardcoded value. Write it exactly as the runtime reports it: keep any suffix it carries (e.g. a context-window marker such as `[1m]`) and do not shorten or normalize it, so one wiki does not end up holding two spellings of the same model — `claude-opus-5[1m]` (79 pages) and `claude-opus-5` (4 pages) both appear in a single pilot repository today (Issue #559). WikiCommit deliberately keeps no registry of valid model IDs to normalize against: a new model would be missing from it the day it ships, and the check would then reject the truth.
5. For `action: create` entities: set the `sources` field as a **one-element list** wrapping the source management file's `source` object — e.g., `sources: [{type: path, path: raw/paper-2024.pdf, hash: sha256:…}]`. Do not recalculate the hash. Copy the management file's `source.license` across verbatim as `sources[0].license` when it holds a value; when it is blank, omit the `license` key entirely rather than writing an empty string (Issue #558 — a blank license would render on the published page as if a license had been recorded). For `action: update` entities, see step 3 above.
6. **Do not call the Write or Edit tools yet.** Keep the generated content as context for Pass 4 review.
7. The execution order and parallelization of entities is left to the agent's judgment.
8. **Bare URLs in body text**: when the body text contains a bare URL (not already in Markdown link syntax `[text](url)`), surround it with a space on both sides, or wrap it in angle brackets (`<https://example.com>`) to make the URL boundary explicit. This matters especially when non-English prose (e.g. Japanese) follows the URL immediately with punctuation or a particle with no space — a Markdown parser can then swallow the following characters into the URL itself, producing a broken/percent-encoded link that `lychee` reports as unreachable and `markdownlint-cli2` flags as MD034. When a URL is immediately followed by non-space text, prefer the angle-bracket form.
9. **Never write raw HTML tags** (`<script>`, `<iframe>`, `<div>`, `<br>`, etc.) into the page body. Images, external-URL images, video files, and YouTube all embed with standard Markdown image syntax alone (`![alt](path-or-url)` — Quartz handles these natively, with no extra configuration); there is no case in which a raw HTML tag is the right way to express something in a WikiCommit page. This applies even when the source document itself contains raw HTML (e.g. an ingested web page) — extract the meaning, never copy the markup verbatim. `.wikicommit/scripts/check_raw_html.py` enforces this as a blocking `wikicommit-merge` quality gate (Issue #377), so a page containing a raw HTML tag will fail to merge regardless; treating it as a generation-time rule here catches it before that point and avoids a wasted retry cycle.

### Pass 4: Source Integrity Review (Review Subagent)

**Stamp `--pass pass4-review` on entry**, with `--source` naming this source's management file (under `--regenerate`, the page being rebuilt).

For each generated page (content is carried as context from Pass 3):

**The review discipline is not in this file (Issue #752).** It lives in `.wikicommit/review-rules.md` — one copy, read by all three review paths, instead of three copies that had already drifted apart. What stays here is the choreography: how the subagent is launched, what to hand it, and what to do with what comes back.

**If `.wikicommit/review-rules.md` does not exist, stop the whole run and say so.** Do not review without it and do not fall back to a looser check. A review that never read those rules degrades to "does the page match the source" — losing evidence binding, the attribution checks, source-vs-source disagreement, cross-page contradiction and the rest — and **its output looks completely normal**. Since step 6 now writes a record asserting that a review happened, a silent degradation would additionally be recorded as one. This is an installation problem, not a defect in any page, so it must not touch `failed_pages` or any source management file's `status`: tell the user to run `/wikicommit-init --no-overwrite` to install the file, and stop (the same treatment guard C gives a missing extraction package, Issue #574). **Check for the file once at the start of the run, before Pass 1 fetches anything** — like guard C, and unlike waiting until this Pass is reached. Its absence is knowable from the first moment and does not depend on any source, so discovering it here would throw away a whole batch of fetching, extraction and generation that was never going to be reviewable.

1. Launch a subagent and give it exactly these five things, and nothing else:

   1. **The path label `generate-pass4`**, stated as the path this review is running on. The rules file scopes several checks by path ("a check that does not name your path is not yours to run") and has a section per path, so a subagent left to guess which one it is on may skip the cross-page check the one-hop pages below were assembled for, or follow the `review-skill` section's "report findings; do not decide" and return no verdict for step 3/4 to route.
   2. **The page under review**, as generated by Pass 3.
   3. **The full extracted text of each of the page's sources**, each wrapped in a block marked `SOURCE` — the whole text Pass 1 extracted, not a summary of it and not the passages you consider relevant.
   4. **The existing pages one WikiLink hop away** (assembled as below), marked as context rather than `SOURCE`.
   5. **`.wikicommit/review-rules.md`**, with an instruction to follow it.

   **Do not include anything else.** Not Pass 2a's `summary`, not Pass 2c's analysis JSON, not your reasoning for how you wrote the page, and not the findings of a previous review round. You are the agent that wrote this page, and all of that is your own reading of the sources — handing it over makes the review agree with you exactly where your reading was wrong. The evidence-binding rule cannot catch this on its own: a summary is not world knowledge, so it slips past a rule about world knowledge while being just as much not-the-source.

   Passing the **full** extracted text rather than an excerpt is the same point in a different place. Choosing which passages the reviewer sees means showing it only the evidence you wrote from, which biases the review toward PASS by construction.

   **Assembling the one-hop pages**: the existing pages this page links to, plus the pages that link to it — found with a `Grep` for this page's own WikiLink with the brackets **escaped** (`\[\[<Type>/<slug>\]\]`), since that tool is ripgrep and a bare `[[…]]` is a regex character class that matches almost every file rather than the link itself. Skip three kinds of hit: `index.md` (`rebuild_index.py` writes every page's own WikiLink into its Type index, so the inbound Grep always hits it, and it states no facts of its own), pages carrying `status: removed`, and a translation of the page under review (a page whose `translated_from` points at it — a disagreement there is translation staleness, which `check_translation_status.py` already reports as `STALE`). **Cap the total at 5**, outbound first, in order of appearance — the same order-of-magnitude bound `wikicommit-ask` uses for its own one-hop expansion (Issue #459).

   Two limits, both accepted rather than solved here. Within a batch, a page only ever sees siblings generated **before** it, so a pair may be checked from one side only or not at all; and a contradiction between pages generated in **different** batches is out of reach entirely, since neither run ever sees the other's page as new. A repository-wide sweep is the answer to both and is deliberately not built here.

2. **Check that the returned JSON carries `rules_version`, and that it matches the value in `.wikicommit/review-rules.md`'s frontmatter.** A missing or mismatched value means the subagent did not read the rules, and its verdict then says nothing about the checks those rules define — a PASS from an unread rulebook is indistinguishable from a real one, which is the whole reason for the echo.

   Relaunch the review **once**. If the second attempt is also missing or wrong, **stop the entire run and report it** — close the run record with `record_run.py end <path> --halted-reason "rules_version mismatch"` first, for the same reason as the fetch-capability halt above (Issue #790: this stops without changing a file, so nothing else records that it happened) — do not consume `generate.max_retries`, do not add the page to `failed_pages`, and do not write `status: failed`. Nothing is wrong with the page: this is a problem with the instructions or the environment, and recording it against the page would leave a false record (Issue #574's precedent, and Issue #567 on a wrong record being worse than none).

3. **Route the cross-page findings the rules produce.** An entry with `page_at_fault: "other"` is not a FAIL — so when it is the only kind of defect found, `result` is `"PASS"` and step 6 writes the page normally. Do not regenerate, and do not touch the other page: Pass 4 regenerates one page against its own sources and has neither the other page's sources nor any mandate over it. Once the page's review has settled as a pass and step 6 has written it, append the pair — both page paths, the fact, and both versions — to a running list for the Completion Notice, the same way `ambiguous` / `exclude` / `failed_pages` are rolled up. Append it then rather than on each review attempt, so a retry driven by some *other* defect does not report the same pair twice, and a page discarded at step 5 is not reported as one this run generated.
4. If the review result is **FAIL** (for any of the above reasons), regenerate the page (up to `generate.max_retries` times from `.wikicommit/config.yml`; default: 2). **Feed the subagent's findings into the retry (Issue #452)**: pass the full `issues` array from step 1 — most importantly each entry's `instruction` — back into the Pass 3 regeneration prompt as explicit, itemized corrections for this attempt, alongside the same source text and context Pass 3 used originally. Do not regenerate from a bare "the previous attempt failed review" instruction with no detail — two consecutive FAILs on the same source for the same underlying defect (e.g. the same inferential gloss re-added both times) is exactly the failure mode this step exists to prevent, since it indicates the retry never actually saw what was wrong with the attempt before it. Leave out the cross-page findings that point at the *other* page (`page_at_fault: "other"` — step 3's routing rule): regenerating this page cannot fix them, and feeding them in as corrections would push it away from what its own sources say.

   **Harvest the `MISSING_SOURCE` entries from every review round (Issue #722)** — before each retry, and also on the final round that exhausts the retry budget and sends the page to step 5, which has no retry after it but still names the document the roll-up below must report as coming from a discarded page. Each entry names a document the page cited that is not among its `sources` — and a retry is about to make that finding disappear, because the fix is to drop the claim, after which the page PASSes and nothing records which document was missing. That is a real registration candidate thrown away: the reviewer could only raise `MISSING_SOURCE` because the source text identified the document, so its URL or title is already in hand. Append it to a running list for the Completion Notice — the same pattern step 5 uses for `failed_pages` — with the document's URL if the source text gives one, otherwise the specific title it names, plus the page and source this came up on. **Skip an entry that identifies no specific document** (a claim traced only to "an earlier post" with neither URL nor title): there is nothing to register, and a line saying so would be noise on every run. Do not let this change any verdict — harvesting is a side effect of the finding, not a substitute for the FAIL.
5. If the retry limit is exceeded, add the page to `failed_pages` and skip writing it to disk. **A human running this interactively may override that (Issue #571)** — `max_retries` exists to stop a page that will not converge, and each retry finding a *different* defect is not that: it is the review working. When the retries have been turning up new defects rather than the same one, and the page is otherwise substantial, say so and ask whether to try once more instead of discarding it. In one pilot the third pass on a ward page found a genuinely new problem (a claim about which shops stand near a station, broader than the source supported), and the operator judged that losing the whole page over one over-broad sentence cost more than fixing it. Do not extend on your own in a non-interactive run, and do not extend a page that keeps failing the same way. Also append this entity — its `title`, `type`, the source management file's path, and (for `action: update` entities) the pre-existing page's `existing_path`, which was left unchanged — to a running list, the same pattern Pass 2 already uses for `ambiguous`/`exclude` entities, so every such failure can be rolled up together in the Completion Notice below (Issue #452 — previously this information only ever reached the source management file's `failed_pages`/`## Failure Reason`, invisible from both the page itself and this run's own summary).

   **Record the review even though the page was discarded (Issue #750)** — this is the record most worth having, because a page that was never written leaves nothing else behind but a `failed_pages` entry naming it. Run `record_review.py` as described in step 6 below, with `--result discarded` and the page path the entity *would* have had; add `--sources-from` once per source management file whose text this review used, since there is no page on disk to read `sources` off. `page_content_hash` comes out empty, which is how a record says the page was never written.
6. Write pages that **passed** review to the working directory using the Write tool. **Do not commit — leave the files as untracked/modified in `git status`.** Then, in one call, pass every page just written to:

   ```bash
   python .wikicommit/scripts/reset_review_on_content_change.py "$(cat <<'EOF'
   <page 1>
   EOF
   )" "$(cat <<'EOF'
   <page 2>
   EOF
   )"
   ```

   Repeat the `"$(cat <<'EOF' … EOF)"` argument once per page. It is the free-text-in-shell-argument form rather than a bare path because `<Type>` and `<slug>` are not validated anywhere in the pipeline, and both come out of Pass 2's reading of a source document.

   This is what actually settles `review_status` for `action: update` entities (Pass 3 step 3, Issue #724). It compares each page against `git show HEAD:` ignoring six bookkeeping fields (`generated_at`/`generated_by`/`generated_with`, `review_status`, `reviewed_by`, `sources`) and, when anything else differs, sets `review_status: pending` and drops `reviewed_by` — so a `reviewed` page whose prose this run rewrote goes back into the review queue, while one that only gained a source keeps its sign-off. `action: create` pages and pages not yet tracked at HEAD are reported as skipped and left alone; the script is safe to hand every written page. A `RESET:` line means that page needs review again, and the next `/wikicommit-merge` will open a tracking Issue for it (its scan looks for `pending`, so no change is needed there) — roll those pages up in the Completion Notice so the user knows which previously-reviewed pages this run sent back. Do not decide this yourself instead of running the script: the comparison is deliberately textual, because letting a judgment call decide whether human review is required is exactly what the trust ladder cannot afford.

   Then record each page's review verdict, once per page (Issue #750):

   ```bash
   python .wikicommit/scripts/record_review.py "$(cat <<'EOF'
   <page>
   EOF
   )" --kind ai --stage generate-pass4 \
     --model "<the model ID this run's runtime reports for itself>" \
     --skill-blob "$(git hash-object .wikicommit/review-rules.md)" \
     --attempts <how many review rounds this page took> --result pass --json - <<'JSON'
   <the review subagent's JSON for this page, with every round's issues merged into
    one `issues` array and each entry carrying the `round` it was raised in>
   JSON
   ```

   **Record every page, not only the ones that had findings.** The denominator is the point: without it, a run in which nothing went wrong and a run in which review never happened produce the same silence. A page that passed on the first attempt gets `--attempts 1 --result pass` and an empty `issues` array.

   **Merge all rounds into the one `issues` array.** Each round of step 4 can find a different defect, and recording only the final round would give a page that failed once and was then fixed an empty `findings` list — erasing exactly the signal worth keeping. Tag each entry with the `round` it came from. `attempts` is passed separately because the last round may have found nothing at all.

   Pass the JSON through as it came back. The script drops `source_quote` itself, so there is nothing to strip by hand — and because it is the script that drops it, the guarantee does not depend on this instruction being followed. `page_content_hash` and `reviewed_sources` are computed by the script from the page on disk; do not try to supply them.

   `--skill-blob` records which version of the review instructions produced this verdict — the hash of `.wikicommit/review-rules.md`, which is where the discipline actually lives (Issue #752). `rules_version` and this hash are not redundant: the first is echoed by the subagent to prove it read the rules, the second is computed here to record which text judged the page, and a forgotten `rules_version` bump would make the first lie while the second stays true. If `git hash-object` fails (the file is present but not yet committed), omit the flag rather than passing a placeholder: an absent value reads as "unknown", a made-up one reads as a version that never existed.
7. Update the source management file's status locally (do not commit). This step only ever updates *this* source's own management file — a different, already-registered management file whose content happens to also be cited by a page this source's Pass 3/4 touched is deliberately left alone here and reconciled instead by the deterministic script in the "Ingest Status Reconciliation" step below (Issue #474 — an earlier version of this step tried to reconcile such other files inline, using this same per-source Pass 2/4 outcome; code review found that unsafe, since a different file's correct status can depend on entities this source's Pass 2 never produced). Evaluate the following rules **in order** and apply the first one that matches (they are not independent conditions — later rules assume all earlier ones didn't match):
   - Pass 2 returned no entities at all, or every entity's page was generated successfully (no `failed_pages`, no `ambiguous: true`, no `action: exclude`) → `status: generated`, record `generated_pages` list and `last_generated_at`. Delete the `## Failure Reason` section if present (Issue #408 — a prior run's failure has now been resolved by this successful run; a stale reason left in place would contradict the current `status`).
   - One or more entities exist, and **all** of them were `action: exclude` in Pass 2 → `status: excluded`, no `generated_pages` (the exclusion reasons are already recorded in `## Summary` from Pass 2; the Pass 3/4 loops naturally have nothing to iterate over for this source). Delete `## Failure Reason` if present (same reasoning as above).
   - One or more entities exist, and **all** of them were `create`/`update` entities that were attempted and failed (no `ambiguous: true` entities, no `action: exclude` entities, zero successes) → `status: failed`. Write a reason to `## Failure Reason` (create it if absent, overwrite if present) summarizing which entities failed and why in one sentence each — e.g. `"3 of 3 entities failed source-integrity review after 2 retries each (hallucinated or unsupported claims). See the wikicommit-generate session output for the full per-claim review detail — that detail is agent-to-agent only and is not persisted here."` Write it in English regardless of `<primary_lang>` (Issue #408; same reasoning as the Pass 1/Pass 3 cases above).
   - Anything else (e.g. one or more `ambiguous: true` entities regardless of success count, or any mix of succeeded/failed/excluded entities) → `status: partial`, record `generated_pages` and `failed_pages`, and `last_generated_at` (an ambiguous or excluded entity never had a page written, so it excludes the source from `generated`). Delete `## Failure Reason` if present (same reasoning as the `generated`/`excluded` branches — `partial` is not `failed`, so no failure reason should remain attached to it).
8. Proceed to the next source management file. `index.md` is rebuilt once for all Type directories after all sources are processed (see below) — no per-source action needed here.

## After All Sources: index.md Update and Completion Notice

### index.md Update (once, after all sources)

After all source management files have been processed, run:

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

Display a summary of the results (pages succeeded / skipped / failed / excluded).

**Close the run record first (Issue #790)**, so the timings and counts it holds are this run's:

```bash
python .wikicommit/scripts/record_run.py end <the path start printed> \
    --source <each source management file processed> --page <each page written> \
    --outcome generated=<N> --outcome failed=<N> --outcome excluded=<N>
```

Then report its path, elapsed time and the passes it stamped in the notice — that duration exists nowhere else, and **the record is not committed**, so this run's own output is the only place a reader sees any of it. That matters most in the unattended cloud runs, where the record dies with the VM: this line is the only form in which the stamps reach a PR body at all (Issue #797).

```
Run record: .wikicommit/run/20260907-104233-generate.md (22m14s)
Passes stamped: pass1-extract x5, pass2b-type x5, pass2c-entities x5, pass3-generate x5, pass4-review x5
```

If any expected pass has no stamp, say so on that line rather than omitting it silently — and say whether it is because the pass genuinely had nothing to do (every source blocked at Pass 1, say) or because you cannot tell.

Then always print one line for the source-integrity review, whatever its outcome (Issue #750):

```
Reviewed 12 page(s) against their sources: 4 finding(s) raised, 2 page(s) corrected
on retry, 1 page(s) not written. Model: claude-opus-5[1m]
  → records in .wikicommit/review/
```

**What makes this worth printing is the denominator.** Everything else in this notice lists only what went wrong, so a reader sees a count of findings with no way to tell whether it is out of 3 pages or 300 — and a run in which every page passed cleanly, a run in which one page failed and was fixed, and a run in which the review never happened at all are today indistinguishable in the output. With the page count present, "0 finding(s) raised" says something: every page went through and came back clean.

Take the numbers from this run: pages recorded, findings across all rounds, pages that took more than one attempt, pages that ended up unwritten, and the model that reviewed. **Do not replace it with a fixed sentence about having written records** — a line whose value never changes stops being read, which is the same reason the low-density guard was demoted from blocking (Issue #562).

If any entities were skipped for `ambiguous: true` (Pass 2), list them explicitly with their candidate `alternatives` and the source management file, and ask the user to confirm the type — e.g.:

```
The following entities were skipped because their type could not be determined. Please confirm the type:
- "Taro Yamada" (candidates: schema:Person, schema:Organization) — source: .wikicommit/source/path/raw/paper-2024.pdf.md
```

Confirming a type does not by itself re-queue the source. That run left its management file at `status: partial` with an empty `failed_pages`, which a bare `/wikicommit-generate` no longer collects (Pass 1 step 1) — so tell the user to re-run it by name: `/wikicommit-generate <the source path or URL shown above>`.

If any entities were skipped for `action: exclude`, list them too (no user action required — this is informational, unlike the `ambiguous` list above). Group them by `exclude_reason`, so the two reasons stay visibly distinct: one says the entity was off-subject, the other that this wiki has decided not to write about it. Show only the groups that have entries.

```
The following entities were excluded as unrelated to theme:
- "Unrelated Corp" (theme_mismatch: A personal acquaintance's employer, unrelated to the configured theme) — source: .wikicommit/source/path/raw/paper-2024.pdf.md

The following entities were excluded by the entity policy (.wikicommit/entity-policy.md):
- "Hanako Suzuki" (privacy: An advisory-committee member named in the source; a private individual) — source: .wikicommit/source/path/raw/paper-2024.pdf.md

The policy applies when a page is generated and does not reach back: pages written
before it was set are unaffected, since regeneration does not re-run entity
extraction. Use /wikicommit-remove to take an existing page down.
```

Print the trailing note only when the `privacy` group is non-empty — it is about that policy, and repeating it under an ordinary off-subject exclusion would read as if `theme` had the same reach-back caveat.

If `.wikicommit/entity-policy.md` was present but could not be read or parsed (see the preamble), repeat that warning here, so an accidentally disabled policy is visible in the run's own summary rather than only in a line that scrolled past:

```
Note: .wikicommit/entity-policy.md could not be parsed, so this run applied no
entity policy at all — every entity was judged on subject relevance alone. Fix the
file's frontmatter and re-run the affected source(s) by name if you rely on it.
```

If Pass 2a flagged one or more sources as clearly written in a language other than `primary_lang` (Issue #336), list them too (informational only, no action required — their content is summarized/translated into `primary_lang` as usual):

```
Note: the following source(s) appear to be written in a language other than primary_lang (ja).
Their content will be summarized/translated into ja when generating pages:
- .wikicommit/source/path/docs/privacy-spec.pdf.md (appears to be English)
```

If the human chose to continue with one or more sources that Pass 1's low-density check flagged (Issue #562), list them too, so that override is recorded in this run's own summary rather than only as a hand-written note in the management file's `## Summary`:

```
Note: the following source(s) were flagged as low-density by the extraction-quality
check (guard A) and generated anyway at your confirmation:
- .wikicommit/source/url/ja.wikipedia.org/saitama-shi.md
  (ratio 0.21, threshold 0.3; non-prose breakdown: links 50%, numbers/tables 1%, other markup 48%)
```

If any YouTube source turned out to have no captions (Issue #574 — the transcript package is installed, so the video itself simply has none), list them too, since the resulting pages rest on the description alone rather than on what the video says:

```
Note: the following video source(s) have no transcript available, so their pages are
based only on the title, keywords, runtime and description:
- .wikicommit/source/url/www.youtube.com/watch-v-96jN2OCOfLs.md
```

If one or more entities were generated as source-entity pages (Issue #475 — Pass 2a judged the source document itself citable as a standalone work), list them too, since they are a page type the user did not explicitly request and may not expect:

```
The following page(s) were generated for a source document itself, not for a concept discussed
within it:
- .wikicommit/entity/en/ScholarlyArticle/vibe-coding-survey.md (source: .wikicommit/source/url/arxiv.org/vibe-coding-survey.md)
```

If any page written in this run has `sources` that are **all** share-alike licensed, list them. Registration warned once per source; this says which *pages* actually came out that way, which is the thing the obligation attaches to:

```
The following page(s) draw only on share-alike sources, so they must be offered under that license
too:
- .wikicommit/entity/ja/Place/hikawa-shrine.md (CC-BY-SA-4.0)

A page with even one non-share-alike source is not listed here. Where a primary source exists,
/wikicommit-collect --index <url> reads an encyclopedia page's citations and offers those instead
of the page itself.
```

If Pass 4 found a page that contradicts an **existing** page and judged the existing one to be the one at fault (Pass 4 step 3's routing rule, Issue #566), list every such pair. This run deliberately changed nothing about them — it regenerates a page against that page's own sources, and has neither the other page's sources nor any mandate over it — so this Notice is the only place the conflict is recorded at all:

```
The following existing page(s) state a fact differently from a page generated in this run, and this
run's sources support the new page. Nothing was changed on either side:
- 見沼干拓の完了年: .wikicommit/entity/ja/Place/minuma-tsusenbori.md says 1728,
  .wikicommit/entity/ja/Place/minuma.md (existing) says 1727

Check which is right against the existing page's own sources, then fix it with
/wikicommit-fix <page-path> "<instruction>". Only pages one WikiLink hop from a page written in this
run were compared, so this is not a survey of the wiki.
```

If any entity fell back to `.wikicommit/schema/default.md` because its type has no dedicated schema file (Pass 3 step 1, Issue #575), list them too. The pages were still generated, but without that type's `granularity`, `properties:` candidates or body template — the only other signal is `validate_frontmatter.py`'s non-blocking WARNING, which a later `wikicommit-merge` raises only for the files that batch happens to change, so this Notice is the one place every affected page in this run is listed together:

```
The following page(s) were generated from .wikicommit/schema/default.md because their type has no
dedicated schema file — that type's granularity rules, properties: candidates and body template did
not apply:
- schema:Book (looked for .wikicommit/schema/Book.md) — "ドグラ・マグラ"
  (source: .wikicommit/source/url/example.com/article.md)

Run /wikicommit-schema-propose to add the missing file, then regenerate the affected pages with
/wikicommit-generate --regenerate. If you expected the file to exist, check whether it was moved into
a subdirectory: the path is derived straight from `type:`, so .wikicommit/schema/<sub>/Book.md is not
found for schema:Book.
```

If Pass 2b added one or more new `.wikicommit/schema/<Type>.md` files during this run, list them too, since they are new local files the user has not yet seen committed anywhere. Annotate each entry with how it was approved per step 3 above — a human answered the prompt, or it was auto-approved with no prompt shown because the run was non-interactive and the candidate cleared the stricter bar (Issue #507):

```
The following Schema.org type(s) were added to .wikicommit/schema/ during this run:
- schema:GovernmentService — approved for "児童手当の申請手続き" (source: .wikicommit/source/path/raw/paper-2024.pdf.md)
- schema:Dataset — auto-approved with no human confirmation (non-interactive run, cleared the stricter
  bar) — for the named benchmark "HotPotQA" (source: .wikicommit/source/url/arxiv.org/hotpotqa-paper.md)

These will be included in the next /wikicommit-merge batch (new schema files are picked up
alongside wiki pages — see that Skill's git add scope). Auto-approved entries get no special marker in
the schema file itself. That batch merges automatically once its mechanical quality checks pass, with no
human approval step in between, so this is not a review gate — it is the same after-the-fact
`git log`/PR-diff audit trail every other WikiCommit change relies on.
```

Do **not** word that last part as "reviewed before merge" — the accurate description is "recorded in git
history for later audit" (Issue #507). The batch auto-merges on mechanical checks alone (Issue #456), so
calling it review would tell the user a human looked at the type when none did.

Quote each added type's `granularity` verbatim in that block (Issue #552). It is the only part of the
file that was written as free prose rather than verified against the vocabulary, nothing downstream
checks its wording, and no Skill can edit it afterwards — so the moment it is printed here is the only
moment anyone sees it before it becomes that Wiki's standing rule for the type:

```
  granularity written for schema:GovernmentService:
    - Create a page for each distinct benefit or service a resident applies for
    - Boundary — a GovernmentService is the service itself, not the ordered steps for applying to it
```

If any of those newly added types wrote a `granularity` bullet drawing a boundary against a type that
already had a file in `.wikicommit/schema/` (recorded in step 4 above), say so as well (Issue #550). The
line only exists on the new type's side, and no Skill can add the reciprocal statement to the installed
type's file — a human editing `.wikicommit/schema/` directly is the only way it ever gets there, so this
notice is the only signal that it is missing:

```
The following newly added type(s) state a boundary against a type that was already installed, and the
installed side says nothing about it:
- schema:TechArticle draws a line against schema:HowTo:
  "Boundary — a TechArticle is reference or explanatory material about a subject, not the ordered
   sequence of steps a HowTo covers"
  .wikicommit/schema/HowTo.md carries no matching rule.

Type selection leans toward whichever side of a boundary documented it, so a one-sided rule makes the
undocumented type less likely to be chosen from here on. No Skill can write the other half — edit
.wikicommit/schema/HowTo.md yourself if you want the rule to hold from both directions.
```

Report this even when the run was non-interactive: nobody reads it in the moment, but it lands in the
run's output alongside everything else, and unlike the type file itself the gap leaves no other trace.

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
entity that did get a page (it already has a working, covered type; Issue #447). This exact wrong
suggestion was made in a real non-interactive run and
produced a "No schema coverage gaps found" dead end when the user tried it — give the guidance
below instead:

```
The following Schema.org type candidate(s) were considered during this run but declined:
- schema:SoftwareApplication — considered for "Claude Code", "Antigravity" (source:
  .wikicommit/source/url/example.com/agents-roundup.md); a human answered N at the prompt. "Kiro" was
  also considered but its page separately failed source-integrity review — see the failed_pages list
  below.
- schema:VideoGame — considered for "Elden Ring" (source: .wikicommit/source/path/raw/gaming-report.pdf.md);
  this run is non-interactive/subagent-driven and the candidate did not clear the stricter "obviously
  implied" auto-approval bar.

Entities that did get a page above were generated using an existing installed schema/ type instead
(most likely schema:DefinedTerm). This is not tracked anywhere after this run ends, so
/wikicommit-schema-propose will not find it later — its detection only covers types with no dedicated
schema file, and these entities already have one. To reconsider one of these types: add
.wikicommit/schema/<Type>.md by hand, or re-run /wikicommit-init (its obvious-type judgment may catch it
if config.yml's theme alone clearly implies the type) or /wikicommit-collect next time a similar source
comes up (it judges from real candidate evidence before registration).
```

If any entity's page hit `failed_pages` after exhausting `generate.max_retries` (Pass 4 step 5), list them too (Issue #452) — unlike `ambiguous`/`exclude`, this represents an intended `create`/`update` that did **not** take effect, which for `action: update` entities means an existing page was left unchanged with no visible sign anything was attempted:

```
The following pages failed source-integrity review after exhausting retries and were not written
(existing pages, if any, are unchanged):
- "Vibe Engineering" (schema:DefinedTerm, action: update, existing page: .wikicommit/entity/en/DefinedTerm/vibe-engineering.md) — source: .wikicommit/source/url/simonwillison.net/vibe-engineering.md

These are also recorded in each source's source management file (`failed_pages` / `## Failure Reason`).
Run /wikicommit-merge next as usual — it will open a tracking Issue per affected source (label:
wikicommit-generation-failure), so this doesn't require watching this run's console output to notice
later.
```

If Pass 4 step 4's harvest collected any `MISSING_SOURCE` document, list them (Issue #722). These are documents the wiki cited but does not hold — each one is a registration candidate the run already identified, and without this the finding vanishes as soon as the retry drops the offending claim. **Fold duplicates to one line per document**, however many pages or retries raised it, and name the pages under it. Where every page that raised a document ended up discarded (Pass 4 step 5), say so on that line rather than listing the document twice — the failed-pages roll-up above reports the *page*, this one reports the *document*, and a reader should not have to reconcile the two:

```
The following documents were cited by generated pages but are not registered as sources. In each case
the citing page either dropped the claim to get through review or was discarded, so registering one
and re-running will bring back what it supports:
- https://simonwillison.net/2025/Mar/19/vibe-coding/ — cited by .wikicommit/entity/en/Person/simon-willison.md
- "2024 年度 さいたま市統計書" (title only; no URL in the source text) — cited by
  .wikicommit/entity/ja/AdministrativeArea/urawa-ward.md (this page was discarded after retries)

Register one with /wikicommit-generate <url-or-path>; the next run folds it in as an update to the
same page.
```

If `reset_review_on_content_change.py` (Pass 4 step 6) printed any `RESET:` line, list those pages (Issue #724). These were `reviewed` before this run and are not any more, which is a state change a reader of the published wiki will see — the banner's line saying a person read the page disappears, and the reviewer's name with it:

```
The following pages were previously reviewed and had their content rewritten by this run, so they are
back to review_status: pending (the reviewer's name has been removed with it):
- .wikicommit/entity/ja/Place/minuma.md — source: .wikicommit/source/url/example.com/minuma.md

Run /wikicommit-merge next as usual — it opens a fresh review-tracking Issue for each of these.
```

If `reconcile_ingest_status.py` (above) reported `reconciled` > 0, list the corrected files too (Issue #474):

```
The following source management files were left at status: pending even though their content is
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
