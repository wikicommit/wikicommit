---
name: wikicommit-generate
description: Register a source file or URL under .wikicommit/source/ and generate wiki pages from it, process the sources already queued, or rebuild existing pages under the current generation rules with --regenerate. Use this when someone asks to take a source into the wiki, to work through the pending source queue, or to regenerate pages. It writes pages into the repository, so do not use it when someone pastes a link and wants it read, summarized or discussed, and do not use it to answer a question about a source the wiki already holds — wikicommit-ask and wikicommit-search do that without writing.
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

## Prerequisite Skills (Text Extraction) — see `references/text-extraction-routing.md`

Which tool extracts which file type, and the install command for each, are in
`.claude/skills/wikicommit-generate/references/text-extraction-routing.md`. **Pass 1 is the only
reader**, so read it there, when Pass 1 is about to extract its first source. The rule
it opens with holds wherever extraction happens: a missing skill stops the run with an
install command, except for `.pdf` (text-based), `.docx`, `.pptx` and `.xlsx`, which fall
back to the `markitdown` CLI and only stop if `markitdown` itself is absent (Issue #268).

Every `markitdown` invocation in this skill is prefixed with `PYTHONIOENCODING=utf-8`: on
Windows, a Japanese-locale console codepage (`cp932`) can make the `markitdown` subprocess's
stdout encoding disagree with the UTF-8 the rest of the pipeline (redirect target, `Read`
tool, hash computation) assumes, corrupting extracted text into mojibake before it ever
reaches Pass 2 (Issue #272). This `VAR=value command` prefix syntax is POSIX shell — it
works unmodified under both Git Bash and WSL, the two execution paths Claude Code's Bash
tool uses on Windows; it would need different syntax under raw PowerShell/cmd.exe, but
Skills never run there.

## Processing Flow (4-Pass Design)

Before starting, read `.wikicommit/config.yml` and obtain `primary_lang`, `theme`, and `generate.max_retries` (default: 2). If `.wikicommit/config.yml` does not exist, stop immediately and tell the user to run `/wikicommit-init` first. If `theme` is absent from `config.yml`, treat it as an empty string. An empty `theme` disables the *relevance* judgment described in Pass 2 — no entity is excluded as off-subject, as before this field existed. It does not disable Pass 2's other exclusion axis: the entity policy read below is judged independently and can still exclude an entity on a wiki whose `theme` is empty.

Read `.wikicommit/entity-policy.md` at the same time (Issue #667). It answers a different question from `theme`, on the same entities: `theme` decides **relevance** (has this anything to do with the subject?), the entity policy decides **permissibility** (granted it does, should a page exist for it?). A living person at the centre of the subject scores highest on relevance and may still be one this wiki does not want a page about, which is why the two are separate and why neither substitutes for the other. Hold two things from it for Pass 2c: `wikicommit.exclude_living_persons` (a boolean, default `false`) read from the frontmatter, and the body prose — for the prose, **run `python .wikicommit/scripts/read_policy.py .wikicommit/entity-policy.md` rather than judging the body yourself** (Issue #844). If the file is absent, treat it as the shipped default — the switch off and no prose — and carry on silently; a wiki initialized before this file existed keeps working unchanged. If the file **exists** but cannot be read or its frontmatter does not parse, fall back to that same default but **say so**: print a `WARNING:` naming the file at that moment, and repeat it in the Completion Notice. Do not fail open in silence — one mistyped line in a hand-edited file would otherwise turn the whole policy off with nothing in the run's output to distinguish it from a wiki that never set one, and unlike `source-policy.md`'s domain list there is no built-in fallback behind it. A `POLICY:` line means the prose that follows it is the policy; a `NONE:` line means there is none, exactly as an empty `theme` disables the relevance judgment. That script strips the worked example the file ships with, and every other HTML comment, so what reaches you is what someone wrote — deciding that from the body by eye is the deterministic judgment Issue #474 says not to leave to an instruction, and the errors it invites all point the same way: every line of the shipped example argues for excluding something.

**Open a run record before anything else (Issue #790)**:

```bash
python .wikicommit/scripts/record_run.py start --skill wikicommit-generate \
    --model "<the model ID this runtime reports for you>" --arg "<each argument, one --arg each>"
```

**Keep the path it prints** — every exit from this Skill closes that same record, and the closing call needs it. Most of those exits are in the `references/` files this one points at, not in this file, so carry the path into each of them. Nothing else in this repository is keyed on a run: if this one dies partway, half the management files sit at `pending` and half at `generated`, which is indistinguishable from a queue that simply has not reached them, and the two halt paths below change no file at all. A record with a start and no end is exactly the signal that a run did not finish, so **an unclosed record is not a failure state to avoid** — it is the answer. Report the record's path in the Completion Notice.

**Confirm `.wikicommit/review-rules.md` exists, at the start of the run, before Pass 1 fetches anything (Issue #888).** Pass 4 hands that file to its review subagent and refuses to review without it, but the check belongs here rather than there: its absence is knowable from the first moment and depends on no source, so discovering it at Pass 4 would throw away a whole batch of fetching, extraction and generation that was never going to be reviewable. If the file does not exist, stop the run and tell the user to run `/wikicommit-init --no-overwrite` to install it — the same treatment guard C gives a missing extraction package (Issue #574). This is an installation problem, not a defect in any page, so it must not touch `failed_pages` or any source management file's `status`. Do not fall back to a looser review: one that never read those rules degrades to "does the page match the source" and **its output looks completely normal**, while Pass 4 still writes a record asserting that a review happened.

**Check that `.wikicommit/scripts/` is in step with this Skill, before Pass 1 fetches anything (Issue #930).**

```bash
python .claude/skills/wikicommit-init/scripts/templates/scripts/check_distribution_freshness.py \
    --only .wikicommit/scripts
```

Report every `OUTDATED:`, `MISSING:`, `ORPHAN:` and `WARNING:` line it prints, and **carry on — this does not stop the run**. Report all four rather than the `OUTDATED:` lines alone: `MISSING:` means there is no scripts tree at all, so every scripted command below will fail; `ORPHAN:` means a script renamed upstream still sits there under its old name (Issue #583); and `WARNING:` is how the check says it did not actually compare anything — a mistyped path, or one renamed in `_root_outputs.py`, otherwise prints a clean `SUMMARY:` that reads exactly like "in step". A silent clean result is the failure this check exists to remove, so it must not be reintroduced by only reading one of its lines. The two halves arrive by different commands (`npx skills add` for this Skill, `/wikicommit-update` for those scripts), so an instruction written here can meet an older script and fail in a way that names the wrong cause rather than saying nothing at all. Most skew is harmless and nothing here can tell which is which, which is why this warns instead of blocking — unlike the missing `review-rules.md` above, where the consequence is known and total. **Run the copy under `.claude/skills/`, not the one under `.wikicommit/scripts/`** — the latter is the half that may be stale, and a detector shipped in the stale half is the very bug it is looking for. If that path does not exist the Skill tree is not installed, so there is no template to compare against: skip it and say nothing.

**Stamp a checkpoint at the entry to each pass, once per source (Issue #797)**:

```bash
python .wikicommit/scripts/record_run.py checkpoint <the path start printed> \
    --pass <pass1-extract|pass2b-type|pass2c-entities|pass3-generate|pass4-review> \
    --token <the pass_token declared by that pass's file under references/> \
    --source "<the source management file this pass is running for>"
```

`ended_at` says whether this run finished; the stamps say **where it got to and what it skipped**. Both questions have cost this project real audits: the two halt paths (guard C in `references/pass1-extract.md`, and the `rules_version` relaunch in `references/pass4-review.md`) stop without changing a single file, so the record is their only trace and without a stamp that trace has no position — and separately, a step at the tail of this flow silently not running is a failure this Skill has shipped three times (Issues #406, #452, #474), each found afterwards by a human reading a published repository. A pass with no stamp is a pass that did not run, and `/wikicommit-status` reports it.

**A failing `checkpoint` never stops the run.** It exits 1 when the token could not be checked, or when it did not match, and it writes the stamp either way. Neither is a reason to halt: the first says nothing about this source or this page, and the second is already recorded where a reader will find it. Note it and carry on with the pass. "Could not be checked" covers every way the file can fail to yield a token — absent, unreadable, no parseable frontmatter, or no `pass_token` key — and the error names the path it tried, which is where to start: a path under `passes/` rather than `references/` means `.wikicommit/scripts/` is older than these Skills and wants `/wikicommit-update`, while a `references/` path that is missing or yields nothing is a problem in the Skill tree itself, which only a reinstall (`npx skills add`) replaces — no init or update path ever rewrites a pass file.

Under `--regenerate` only `pass1-extract`, `pass3-generate` and `pass4-review` are stamped — that mode takes a page rather than a source, so Pass 2 does not run, and `--source` carries the page being rebuilt. Pass 2a takes no stamp: it runs unconditionally in the same breath as Pass 1's extraction and has no branch of its own, so a stamp there would locate nothing Pass 1's does not.

**The stamping instruction now travels with the pass it stamps (Issue #911).** Each pass's `--pass` value and its `--token` are declared in that pass's own file under `references/`, which is read at the moment the pass starts — so unlike the arrangement this replaced, no stamping instruction has to survive from this file's opening to the tail of a long run. What remains of the old limitation is narrower and points the safe way: a run that never opens a pass file leaves no stamp for it, and `/wikicommit-status` reports `MISSING_PASS:` — which is the correct report, because a pass whose instructions were never read did not run as specified. A pass that really was skipped is still never reported as having run.

With `--regenerate`, skip Step 0 entirely and read `.claude/skills/wikicommit-generate/references/regenerate.md` — that mode takes a page, not a source, registers nothing, and has its procedure in that file (see the Regeneration Mode section below).

**Every pass of this Skill lives in its own file under `references/`, and the pointers are here on purpose (Issue #894, extended by Issue #911).** Each is named again at its point of use further down, but a pointer that is *only* down there is a pointer that compaction can take with the thing it points at — and the whole reason for the split is that the pointer survives where the section did not. This table is the map; read each row's file when the flow reaches it, and **stamp that pass with the `--token` the file declares** (a stamp with no `--token` records `token: unchecked`, which is how a pass executed without its file being opened shows up):

| Read | When | `--pass` |
|---|---|---|
| `.claude/skills/wikicommit-generate/references/text-extraction-routing.md` | Pass 1, before extracting the first source | — |
| `.claude/skills/wikicommit-generate/references/pass1-extract.md` | Pass 1 and Pass 2a, once per source | `pass1-extract` |
| `.claude/skills/wikicommit-generate/references/pass2b-type.md` | Pass 2b, once per source | `pass2b-type` |
| `.claude/skills/wikicommit-generate/references/pass2c-entities.md` | Pass 2c, once per source | `pass2c-entities` |
| `.claude/skills/wikicommit-generate/references/pass3-generate.md` | Pass 3, once per source | `pass3-generate` |
| `.claude/skills/wikicommit-generate/references/pass4-review.md` | Pass 4, once per source | `pass4-review` |
| `.claude/skills/wikicommit-generate/references/completion-notice.md` | when this run is ending, **before closing the run record** | — |

**None of them is optional.** `references/completion-notice.md` is the one to watch: it holds the `record_run.py end` call, so skipping it leaves this run's record open and `/wikicommit-status` reports `INCOMPLETE_RUN:` — that is the intended consequence, not a side effect. Nothing anywhere re-derives the notice, so a run that never reads it reports nothing at all. The five pass files fail the same way from the other end: a pass whose file was never opened leaves no stamp, and `/wikicommit-status` reports `MISSING_PASS:`.

### Step 0: Source Registration (only when argument is given)

If an argument is provided:

0. **Read `.wikicommit/source-policy.md` first, before registering anything (Issue #564)**. It holds this wiki's answer to "which sources do we take in", which nothing else does: `theme` in `config.yml` decides which *entities* get pages once a source is already in, so it has no say here, and it is the only thing this Skill used to read. **Read it with `python .wikicommit/scripts/read_policy.py .wikicommit/source-policy.md`, not by opening the file** (Issue #844): a `POLICY:` line is followed by the prose to apply, and a `NONE:` line means there is none — carry on without one, exactly as an empty `theme` disables the entity judgment. The script removes the worked example this file ships with, and any other HTML comment, so a shipped example is never mistaken for something this wiki decided. Read the frontmatter separately for `rejected:`, `exclude_domains` and `index_only`; the script deliberately does not touch it.

   Read the body as instructions to someone deciding whether this particular document belongs in this wiki, and apply them to the argument you were given. If it clearly falls outside them (a personal blog where the policy asks for primary sources; a promotional page where it excludes advertising), **say which line of the policy it conflicts with and ask whether to register it anyway** — do not register it silently, and do not refuse on your own either: the person running this Skill named this source deliberately and may have a reason the policy does not cover. Proceed on a yes and note it in the Completion Notice. The `rejected:` list in the frontmatter is the same kind of signal: if the argument matches a `url` already listed there, quote that entry's `reason` and ask before going on.

   **In a non-interactive run, where no answer will arrive, register nothing and report it** (Issue #910). This is the one place in this Skill where deferring the usual way is not available: the confirmation happens *before* registration, so there is no management file to leave at `status: pending` and nothing on disk to carry the wait. It is also the one place where that costs nothing — the source is an argument a person typed just now, so naming it in this run's output puts it back in front of the person who chose it. Do not read the absence of an answer as a yes: the whole point of the check is that this source and this wiki's policy disagree.

   `exclude_domains` is enforced for you later — `check_extraction_quality.py check-domain` in Pass 1 unions it with its own built-in list and blocks the fetch — but do not leave it to Pass 1 alone. Pass 1 blocking a source sets `status: failed` and writes a `## Failure Reason`, which is the right record for a domain static fetching genuinely cannot read and the wrong one for a domain this wiki simply decided against: it leaves a management file behind for a source that was never wanted, and `wikicommit-merge` Step 9 then opens a `wikicommit-generation-failure` tracking Issue asking someone to fix a non-failure. So if the argument's host matches an `exclude_domains` entry, treat it exactly like a prose conflict above — name the entry, ask whether to register it anyway, and register nothing until the answer is yes. (Compare hosts the way the script does: case-insensitively, ignoring any scheme, port, path and leading `www.`, so `example.com`, `www.example.com` and `https://example.com/` are one entry.)

   `index_only` gets the same treatment for the opposite reason: **nothing enforces it for you later** (Issue #833). It names domains this wiki reads for their reference lists and never registers, and `check-domain` unions only its built-in list and `exclude_domains` — so an `index_only` host handed to this Skill is fetched and turned into pages with nothing in the way. What that setting protects is not a preference: the wiki decided that what it wants from this domain is the sources it *cites*, not the article itself. A page built from one such article and nothing else tends to be a shorter retelling of it without its footnotes, and where the article is share-alike licensed that page may carry the obligation too (Issue #570) — which is why those pages are meant to be few and deliberate rather than arrived at by handing the URL to this Skill. (Registering it does record and display it as a source, with its license: what is at stake is the decision, not the attribution.) So if the argument's host matches an `index_only` entry, name it, say that the registered page would rest on that page's own framing, and ask before registering anything. Compare hosts exactly as above.

   **Do not refuse it outright**, and do not treat it as stronger than `exclude_domains`. Registering an index-only domain by name is a supported thing to do: some subjects have no primary source at all (a shrine's founding story, a local concept), and the policy deliberately stops short of banning encyclopaedias. What it asks is that this be a decision rather than an accident. When you ask, point at the path that setting was designed for — `/wikicommit-collect --index <url>`, which reads that page's reference section and pulls the primary sources out of it. That flag belongs to `/wikicommit-collect`; this Skill has no `--index`, so name the other command in full rather than writing the flag on its own.

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
   - `RECHECK:` (`type: url` / `wikicommit` only) → The management file's previous run already completed (`status: generated`/`failed`/`excluded`). Unlike `type: path`, a URL source's hash can't be recomputed locally — the only way to know whether the remote content changed is to actually re-fetch it. Notify the user that WikiCommit will re-fetch the URL to check for changes, then proceed to Pass 1 for this single management file: treat it as selected for processing even though its current `status` is not `pending`/`outdated`/`partial` (Step 0 having picked exactly this file is what qualifies it, same as the "if an argument was given" override in Pass 1 step 1) — and mark it as a **forced recheck** so Pass 1 applies the special handling in the "Hash write-back" section of `references/pass1-extract.md` (bypass the scratch-file cache; compare the fresh fetch to the *current* `source.hash` before deciding whether to proceed).
   - `RETRACTED:` → A human previously withdrew this source: they read it, judged its content unreliable, and set the management file's `status` to `retracted` (Issue #737). **Quote the reason the message carries** (`add_source.py` reads it out of the management file's `## Retraction Reason` section) and stop — register nothing, re-fetch nothing, and do not go on to Pass 1. Say what it would take to reverse the decision: edit the management file's `status` back to `pending`, delete its `## Retraction Reason` section, and re-run. Never do that yourself. This is the one status where the machine has no standing to disagree: under the evidence-binding rule the machine judges a page *against* its sources and so cannot judge a source, which is why only a human can write this value and only a human can lift it. If the message says no reason was recorded, say that too rather than treating the retraction as doubtful.
   - Exit code 1 (error) → Display the error and stop.

4. **Source license (Issue #558)**: on `CREATED:`, `add_source.py` writes a `source.license` field into the new management file, filled from its known-domain table (e.g. any `wikipedia.org`/`wikisource.org` host → `CC-BY-SA-4.0`) and left blank otherwise. Blank means *unknown*, not *unrestricted*. If the message reports a license, mention it to the user. If it is blank and the user knows the source's terms, tell them to edit `source.license` in the management file directly (the `--license "<identifier>"` flag only takes effect when a management file is first created, so re-running it against an already-registered source returns `SKIP:`/`RECHECK:` and records nothing). The value is free text (an SPDX identifier such as `CC-BY-SA-4.0` where one exists, otherwise a short phrase such as `Saitama City website terms of use` or `all-rights-reserved`), and it is carried onto every page generated from this source and shown next to that source on the published site. Never guess a license on the user's behalf, and never present the table's value as a legal determination: WikiCommit records and displays what it is told, it does not decide what a source's terms are or whether they permit this use.

   **Copyleft sources (Issue #570, widened beyond Creative Commons by Issue #951)**: when the message says the license is copyleft, `add_source.py` appends a line saying so — this now covers software copyleft (GPL / AGPL / LGPL / MPL / EPL and the like) as well as share-alike Creative Commons and ODbL. Pass it on and say what it means concretely — a page written from this source **and nothing else** may have to be offered under that same license, and that question is the wiki's to answer, not WikiCommit's. Keep the "may": whether a prose summary of a copyleft document is a derivative work is genuinely open, and stating it as settled would be answering a question this project has decided not to answer. It is not a reason to refuse the source: some subjects have no primary source at all (a shrine's founding legend, a local custom), and an encyclopedia article is the honest answer there. It is a reason to know it is happening. Where a primary source does exist, two things reduce how many pages end up in that position: take the structural overview from the primary source, and use the encyclopedia as an index instead — `/wikicommit-collect --index <url>` reads a page's citations and offers those, without registering the page. See the worked example in `.wikicommit/source-policy.md`, which describes this shape (it is commented out there, so it is guidance for whoever writes that file rather than a policy this wiki has adopted).

5. **Sources whose fetch is known to be partial (Issue #715)**: on `CREATED:`, `add_source.py` also appends a `partial extraction:` line when the URL matches a shape whose static fetch is confirmed to return the page's body but silently drop part of what the page carries. Today that is a GitHub issue or pull-request thread — the body comes through, every comment on it does not, and nothing errors. Pass the line on and say plainly which part will be missing, so the person can decide whether the body alone is the source they wanted.

   **This is a notice, not a guard.** Do not treat it as a reason to stop, do not set `status: failed`, and do not ask for confirmation the way an `exclude_domains` match does: the fetch really does succeed and what it returns really is the page's body, so an issue whose body is the whole point is a perfectly good source. It is the *silence* that was the defect, not the partial result. If the missing part is the part they wanted, the answer is to get that content another way and register that instead — not to register this URL and hope.

If no argument is given, skip Step 0 and start from Pass 1.

### Regeneration Mode (`--regenerate`) — see `references/regenerate.md`

`--regenerate` rebuilds pages that already exist, so that pages generated under older schema templates or older Pass 3 rules can be brought up to the current ones (Issue #578). It is **page-driven, not source-driven**, and it shares Passes 1, 3 and 4 with ordinary generation while using none of Step 0, Pass 2a/2b/2c or the Completion Notice.

**When `--regenerate` is given, read `.claude/skills/wikicommit-generate/references/regenerate.md` and follow it.** The procedure lives there rather than here because the two modes are mutually exclusive — an ordinary run never uses a byte of it, and a regeneration run never uses the 40% of this file that belongs to the other mode — and this file is read in full on every invocation (Issue #887).

There is no fallback to improvise from: if that file cannot be read, **stop and say so** rather than attempting a rebuild. Unlike a shared data file whose absence degrades the guidance, this one *is* the procedure, so skipping the read cannot fail quietly.

### Pass 1: Text Extraction, and Pass 2a: Summary — see `references/pass1-extract.md`

**Read `.claude/skills/wikicommit-generate/references/pass1-extract.md` now and follow it**, once per source. It holds the collection rules and the 5-source cap, the three extraction guards (known JS-shell domain, fetch capability, low information density), the URL scratch and `type: path` extraction caches, and Pass 2a's summary, source-language and source-as-entity judgments. Pass 2a sits in that file rather than with 2b/2c because it reads the text Pass 1 just extracted and takes no checkpoint of its own.

### Pass 2: Analysis (LLM → JSON)

Pass 2 runs in three sub-steps per source: 2a produces a summary (in `references/pass1-extract.md`, next to the extraction it reads from), 2b resolves — inline, right now — whether a Schema.org type outside `installed schema/` should be added before entities are extracted, and 2c extracts entities using whatever types are available after 2b.

#### Pass 2b: Type Necessity Judgment — see `references/pass2b-type.md`

**Read `.claude/skills/wikicommit-generate/references/pass2b-type.md` now and follow it.** It holds the two-stage type recall, the interactive and non-interactive approval bars, and the narrow write exception that lets this Skill add — never edit — a file under `.wikicommit/schema/`.

#### Pass 2c: Entity Extraction — see `references/pass2c-entities.md`

**Read `.claude/skills/wikicommit-generate/references/pass2c-entities.md` now and follow it.** It holds the analysis JSON format, the context the LLM is given, the `action` and `exclude_reason` rules, slug derivation, and the `## Summary` / `## Generation Notes` write-back.

### Pass 3: Page Generation (File Boundary Protocol) — see `references/pass3-generate.md`

**Read `.claude/skills/wikicommit-generate/references/pass3-generate.md` now and follow it.** It holds the `---FILE:`/`---END FILE---` output contract, the frontmatter rules, property-value WikiLinks, granularity and thin-source discipline, and the `sources[]` merge rules for `action: update`.

### Pass 4: Source Integrity Review (Review Subagent) — see `references/pass4-review.md`

**Read `.claude/skills/wikicommit-generate/references/pass4-review.md` now and follow it.** It holds what the review subagent is given, the retry loop, `failed_pages`, the review record, and the final `status` rules for the source management file. **It sends you on to one more file**: the review discipline itself is in `.wikicommit/review-rules.md` (Issue #752), which is shared with `/wikicommit-review` and `/wikicommit-synthesize` and is not restated anywhere in this Skill. Two files deep is stated here rather than left to be discovered, because a second hop that nobody announces is a second hop that gets skipped without anyone noticing.

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

This finds `.wikicommit/source/**/*.md` management files still left at `status: pending` whose `source.hash` is nevertheless already cited in some `.wikicommit/entity/**/*.md` page's `sources[]` — evidence that their content was incorporated into a page during this or an earlier run without their own status ever being written back (the `ai-driven-dev-wiki` round2 pilot that motivated this had 8 such files) — and sets `status: generated` plus `generated_pages` for each. A `pending` file that already lists `generated_pages` is left alone (Issue #874): it was put back in the queue on purpose, so flipping it to `generated` would empty that queue under a success message. It deliberately never touches `status: outdated` files: `check_ingest_freshness.py` leaves an outdated file's `source.hash` unchanged as the reference point of its *previous* successful generation, so a hash match there means "was generated before the source changed and still needs reprocessing," not "already reconciled" — treating the two the same would silently mask genuine staleness. This is a local write only — **do not commit**. Report how many files this corrected, if any (`RECONCILED:` lines / `reconciled=` count in `SUMMARY:`), in the Completion Notice (`references/completion-notice.md`).

### Completion Notice — see `references/completion-notice.md`

Read `.claude/skills/wikicommit-generate/references/completion-notice.md` now and follow it. It holds
what to report and how, **and the `record_run.py end` call that closes this run's record** —
so a run that skips it leaves an open record, which `/wikicommit-status` reports as
`INCOMPLETE_RUN:`.

Everything it renders was accumulated by the passes above. Do not re-derive any of it here.

## Notes

- Do not commit to `main` or any branch
- Do not write to `.wikicommit/schema/`, with one narrow exception: Pass 2b (Issue #315) may write a new `.wikicommit/schema/<Type>.md` file for a candidate that was approved — either by a human answering the Enter prompt in an interactive run, or (Issue #507) auto-approved with no prompt shown because the run was non-interactive and the candidate cleared step 3's stricter bar — it only ever adds a file that wasn't already there, never edits or overwrites an existing schema file
- Do not run `gh pr create` or any PR creation commands
- All file writes go directly to the working directory; `git status` will show them as untracked or modified
- For `type: url` / `type: wikicommit` sources, fetch only the registered `source.url`. Do not run additional `markitdown` calls for links discovered within the extracted content — each source page an operator wants ingested must be registered explicitly via `/wikicommit-generate <url>`.
