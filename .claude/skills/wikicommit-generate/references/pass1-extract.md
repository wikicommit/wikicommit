---
pass_token: "a3f1c07d"
---

# Pass 1: Text Extraction

> **Paths in this file.** `references/…`, `scripts/…` and `../<other-skill>/…` are relative to the Skill's directory (the parent of this `references/` directory), not to the repository root — the Skills may be installed under `.claude/skills/` or `.agents/skills/`. Commands still run from the repository root, so spell the path out from there. Paths starting with `.wikicommit/` are repository-root paths as before.

## Contents

1. Collect the queued source management files (tiers, the 5-source cap, what `partial` and `retracted` mean here)
2. Exit cleanly when nothing is queued — **this closes the run record**
3. Read `source.type` / `source.path` / `source.url`
4. Extract text: guard B (known JS shell) → guard C (fetch capability) → the URL scratch cache → the `type: path` extraction cache → the per-extension routes → guard A (low density)
5. Empty or unreadable extraction → `status: failed` + `## Failure Reason`
6. Otherwise write `extracted_tokens`, and roll up the caption-less YouTube case

- Pass 2a: the summary, the source-language judgment, and the source-as-entity judgment

**Stamp `--pass pass1-extract` before extracting each source**, with `--token a3f1c07d` (the run-record block is in `SKILL.md`; the token is this file's `pass_token`, and `record_run.py` opens this file itself to check it). This is the stamp that survives compaction, so it is the one that always marks how far a run got.

1. Collect source management files from `.wikicommit/source/` whose `status` is `pending` or `outdated`, plus those with `status: partial` **and a non-empty `failed_pages`**:
   - **`status: retracted` is never collected.** The condition above is an allowlist and `retracted` is not on it; a later edit that widens the list must not put a withdrawn source back into circulation. The argument branch below never reaches one either — Step 0 stops on `RETRACTED:` before Pass 1 begins.
   - If an argument was given: process only the management file Step 0 acted on (`CREATED:`/`UPDATED:`, or `RECHECK:` — a forced recheck is processed here even though its `status` is still `generated`/`failed`/`excluded`). The `failed_pages` condition does not apply to this branch: the user named this source, so process it whatever its state.
   - **Why `partial` alone is not enough**: with `failed_pages` non-empty, re-running can succeed, so it belongs here. With `failed_pages` empty, the source is waiting on a human to confirm an entity's type (next bullet), or — on a management file written by an older version — its only shortfall was entities excluded by `theme` or `.wikicommit/entity-policy.md`. Re-reading the same source returns the same judgment every time in both cases, so collecting it would hold slots on every run and starve never-processed sources behind it.
   - **The ambiguity case is recorded but still not collected.** An entity that came back `ambiguous: true` is written to `ambiguous_entities`, so this condition could tell it apart. **It deliberately does not collect them anyway.** Re-reading the source reaches the same entity and returns the same `ambiguous: true`, every run, and what a human decides about a type is not written anywhere the next run could read. What the field buys is that the wait is visible between runs: `/wikicommit-status` names the source and the entity. Once the human has decided, **`/wikicommit-reconcile --source <path|url>`** puts the source back to `status: pending` and the next `/wikicommit-generate` collects it here. Naming the source directly (`/wikicommit-generate <path|url>`) also works, per the argument branch above.
   - If no argument: collect all matching files under `.wikicommit/source/`. **Order them in three tiers**, path ascending within each: (1) `status: outdated`, (2) never processed — no `last_generated_at`, absent or empty, (3) everything else. Sorting by path alone would let the same already-worked-on files take the same slots on every run, and the cap below only makes progress if the chunk changes.

     **Within a tier, a file carrying a `## Deferred Reason` sorts after one that does not.** A deferral leaves `status` untouched, so without this the same deferred sources would hold the same slots every run — and a non-interactive run defers them again — so nothing behind them would ever come up. An interactive run still sees them in the list it shows, and option (a) takes everything.

     `outdated` goes first because a published page's source has changed, so what is on the site is *wrong*, where a never-processed source is only *missing*. It cannot starve the backlog: a source only becomes `outdated` when its content changes, so the tier is small and does not refill on its own.
   - If the count exceeds 5, do not start processing yet — show the count and the matching management file paths, then ask the user to choose: **(a)** process all of them in this run, or **(b)** process only the first 5 in the order above and leave the rest untouched for a later run. If the user picks (b), proceed with only those 5; the rest keep their `status` and a later no-argument `/wikicommit-generate` picks them up — nothing else is needed. If the count is 5 or fewer, proceed with all of them without asking. **In a non-interactive run, take (b) without asking** and say so in the Completion Notice: the unprocessed files stay queued by construction. Do not read the absence of an answer as (a).
   - **Group the list you show under three headings**, in this order, so a source that has never been touched is not presented as interchangeable with one being re-run:

     ```
     Never fetched (no content has been retrieved yet) — 23:
       .wikicommit/source/url/ja.wikipedia.org/...
     Fetched but never generated — 0:
     Re-processing (source changed, or entities failed last time) — 2:
       .wikicommit/source/path/raw/report.pdf.md (outdated)
     ```

     A file belongs to the first group when its `source.hash` is empty, the second when it has a hash but no `last_generated_at`, and the third otherwise. The split between the first two tells a stalled queue apart from a slow one. It only carries meaning for `type: url`/`wikicommit` sources, which get a hash only once Pass 1 fetches them: `add_source.py` hashes a `type: path` file at registration, so a local file never read still lands in the second group. Say so when the first group is empty but the second is not, rather than letting `Never fetched — 0` read as "everything has been retrieved".
2. If no target files are found, output "No management files to process", **close the run record** (`record_run.py end <path>`, with no `--source`/`--page`/`--outcome` — there is nothing to name), and exit. This exit is usually taken before the rest of this file has been read, so the rule is restated here: leaving the record open reports a correctly finished run as one that did not finish, on every `/wikicommit-status` from then on. Closing it with nothing named is also what tells `check_run_records.py` this was a no-op rather than a run that lost its stamps.
3. For each source management file, read `source.type` and `source.path` / `source.url`.
4. Extract text based on `source.type` and file extension:
   - `type: wikicommit` (federated source) / `type: url` → **Known JS-shell domain check (guard B)**: before attempting any fetch, run:

     ```bash
     python .wikicommit/scripts/check_extraction_quality.py check-domain <source.url>
     ```

     `BLOCKED:` (exit 1) → do not attempt extraction at all. Treat this source as extraction failure (step 5 below): mark `status: failed`, write the script's `BLOCKED:` line verbatim into `## Failure Reason`, notify the user, and skip to the next source. `OK:` (exit 0) → proceed with the fetch below as normal. This check only catches domains already confirmed to return an empty content shell (the `KNOWN_JS_SHELL_DOMAINS` set in the script, plus the repository's `exclude_domains`); it is not a general JS-detection heuristic. The general case is guard A in step 5 below.

     **Fetch-capability check (guard C)**: still before fetching, and only once the domain check above returned `OK:`, run:

     ```bash
     python .wikicommit/scripts/check_extraction_quality.py check-fetch-capability <source.url>
     ```

     `MISSING_PACKAGE:` (exit 1) → **stop processing entirely**, close the run record with `record_run.py end <path> --halted-reason "missing package: <name>"` (this path changes no file, so without that line the run leaves no trace at all), and display the `pip install` command from the script's output, exactly like the `markitdown --version` prerequisite check below. This is an environment problem the user fixes once, not a property of this source, so it must not be recorded as a `status: failed` extraction failure. `OK:` (exit 0) → proceed. This only needs to pass once per host per run.

     Guard C is a separate axis from guards A and B: a YouTube page fetched without `youtube-transcript-api` is a *partial* extraction of real prose, which neither of the other guards can tell from a complete one. Checking *before* fetching is also what keeps "the package is missing" distinguishable from "this video has no captions" (step 6 below), which call for opposite responses.

     Extract `source.url` by running `add_source.py --fetch-url`, never with the agent's own web-fetch tool and never with the `markitdown` CLI on the URL directly. A web-fetch tool may return a model-written summary, which would make the **Hash write-back** below hash something other than the source. The bare `markitdown <url>` sends Python `requests`' default User-Agent, which Wikimedia domains reject with `403 Forbidden`; `--fetch-url` calls `markitdown`'s Python API with a WikiCommit User-Agent and changes nothing else. Do not work around it with a `curl`-then-convert two-step either: that loses the HTTP charset header and mojibakes pages whose encoding is declared only there. Confirm `markitdown` is installed once per run, before the first source of any kind — `type: url`, `type: wikicommit`, the `.pdf`/`.docx`/`.pptx`/`.xlsx` fallbacks below, or the "Other" fallback below — that needs it; do not re-run this check once it has passed:

     ```bash
     PYTHONIOENCODING=utf-8 markitdown --version
     ```

     Non-zero exit or command not found → stop processing and display the install command from the install table in `references/text-extraction-routing.md` (`pip install 'markitdown[pdf]'`). This applies even when the check is run for the `.pdf` (text-based) or `.docx`/`.pptx`/`.xlsx` fallbacks below — `markitdown` is the guaranteed path for those formats once the official skill is unavailable, so its absence must stop processing rather than be skipped.

     `markitdown` dispatches on the URL's content type internally, so a URL pointing directly at a non-HTML file (e.g. `https://arxiv.org/pdf/xxxx.pdf`) is extracted with the right converter — no separate `type: path` registration or pre-download is needed. Fetch only the registered URL — do not follow or register links found within the extracted content, even if they look relevant (out-of-scope fetching risks scope creep, copyright exposure, and wasted tokens). If a linked page is worth ingesting, register it explicitly via `/wikicommit-generate <url>`.

   **Hash write-back** (`type: url` / `type: wikicommit`): the management file is registered with `hash: ""`; this step fills it in via script rather than by hand-editing YAML, which is unreliable. `<scratch-path>` below is the source management file's path relative to `.wikicommit/source/url/`, without the `.md` extension, with the `/` separators kept intact (e.g. `.wikicommit/source/url/example.com/article.md` → `example.com/article`). Do not flatten the separators to `-`: the nested file `example.com/article.md` and a legacy flat file `example.com-article.md` would then collide on the same scratch name.

     **Forced recheck** (source flagged `RECHECK:` in Step 0 — a source whose `status` was already `generated`/`failed`/`excluded`): skip the **Cache check** below unconditionally and go straight to the fetch — a kept scratch file from the prior run would trivially "match" the unchanged `source.hash` and short-circuit the very re-fetch the recheck exists to perform. After the fetch succeeds, before running `--write-hash` (which unconditionally overwrites `source.hash`), first run `--check-hash` against the freshly-fetched scratch file to compare it with the management file's *current* `source.hash`:

     ```bash
     python scripts/add_source.py --check-hash <source-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     - `HASH_MATCH:` (exit 0) → the remote content is unchanged since the last successful check. Do **not** run `--write-hash` and do **not** proceed to Pass 2–4 for this source — leave the management file's `status`/`hash` exactly as they were. Notify the user "No changes: `<url>`" and move on to the next source.
     - `HASH_MISMATCH:` (exit 1) → the content changed. Run `--write-hash` as usual (see below) and continue this source through Pass 1 steps 5–6 and Pass 2–4 normally; Pass 4's status rules (`references/pass4-review.md`) set the final `status` once processing completes, so no separate transition is needed here.

     For a normal (non-recheck) `type: url`/`wikicommit` source, apply the **Cache check** instead: the scratch file at `.wikicommit/.cache/ingest-fetch/<scratch-path>.md` is *kept* after a successful fetch, so a source processed again with an unchanged `source.hash` can reuse it instead of re-fetching. Before fetching, if that scratch file exists, run:

     ```bash
     python scripts/add_source.py --check-hash <source-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     - `HASH_MATCH:` (exit 0) → the cached scratch file is still valid for the management file's current `source.hash`. Skip the fetch and the write-hash step below entirely, and jump straight to the "read the scratch file's content in full" step near the end of this bullet.
     - `HASH_MISMATCH:` (exit 1, including "scratch file doesn't exist") → the cache cannot be reused. Proceed with the fetch below; this always fetches fresh content, so a hash change is never masked by an old cache.

     If no scratch file exists yet at that path (or this is a forced recheck — see above), skip the cache check and go straight to the fetch below:

     ```bash
     python scripts/add_source.py --fetch-url "<source.url>" --output ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
     ```

     `--fetch-url` creates the scratch file's parent directory itself (it is already gitignored) and writes exactly what `markitdown` produced to the output path, with nothing in between.

     - `NETWORK_UNAVAILABLE:` (exit code 3 — the request never reached the server: name resolution, connection or proxy failed) → **defer this source; do not mark it `status: failed`**. A sandbox with network access off, a proxy, or no connection is the environment, not the source; recording it as `failed` would put every URL source in the run behind a wrong verdict and a generation-failure Issue each. Defer it exactly as the non-interactive `LOW_DENSITY:` branch below does — leave `status` as it is, write the `NETWORK_UNAVAILABLE:` line verbatim into `## Deferred Reason`, add it to the Completion Notice's deferred list, skip to the next source — with one difference: **on a forced recheck, do not set `status: pending`**. Nothing was fetched, so `source.hash` still describes the content the source's pages were built from, and requeueing it would regenerate unchanged pages. The same holds in an interactive run — there is no question for a person here that retrying later would not answer better.
       **Two in a row stop the run.** Count consecutive `NETWORK_UNAVAILABLE:` results across sources; any `FETCHED:` or `ERROR:` (both prove the network reached a server) resets the count, and a cache hit that skips the fetch leaves it as it is. On the second in a row, **stop processing entirely** as guard C does: close the run record with `record_run.py end <path> --halted-reason "network unavailable"`, say that fetching is failing before it reaches any server, and that the sources not yet reached are untouched and still queued. One is not enough to stop on, because a domain that no longer exists fails name resolution the same way — and that one source is deferred, not lost. Sources already processed in this run keep their results.
     - `ERROR:` (exit code 1 — HTTP error status like 403/404, a read timeout, login-required page, unsupported content, etc.) → treat this source as extraction failure (step 5 below) and skip to the next source; do not run the command below.
     - `FETCHED:` (exit 0), forced recheck → run the `--check-hash` comparison described above and branch on `HASH_MATCH`/`HASH_MISMATCH`.
     - `FETCHED:` (exit 0), normal (non-recheck) source → run:

       ```bash
       python scripts/add_source.py --write-hash <source-management-file> --content-file ".wikicommit/.cache/ingest-fetch/<scratch-path>.md"
       ```

       Check the output: `HASH_WRITTEN:` → proceed. `ERROR:` (exit code 1) → treat this source as extraction failure (step 5 below) and skip to the next source.

     After `HASH_WRITTEN:` (or after a `HASH_MATCH:` cache hit above), read the scratch file's content **in full** — if a single read truncates it, read the rest in further chunks; a partial read would silently substitute a fragment for the source. This becomes the "extracted text" for this source used in steps 5–6 below and in Pass 2. **Do not delete the scratch file** — a later re-run of this source with an unchanged hash reuses it via the cache check above. `.wikicommit/.cache/` is a rebuildable, gitignored cache, so leaving files there does not conflict with GitOps.
   **Extraction cache** (`type: path`): every route below except `.md` / `.txt` turns a file WikiCommit cannot read directly into text, and for a scanned PDF or an EPUB that is the most expensive step in the pipeline and needs an optional Skill installed. The cache lets a re-run of the same source (a `partial` file picked up again, `--regenerate`, a later entity) skip it.

     **Never derive the cache path yourself** — both commands below print it, and that is the only way to get it. It mirrors the management file's path under `.wikicommit/source/path/` **including the trailing `.md`**, so `raw/paper.pdf.md` and `raw/paper.docx.md` stay distinct; re-deriving it by stripping and re-adding the extension makes them collide.

     Before dispatching to a route below — **except for a `.md` / `.txt` source, which is never cached (see below), so skip both commands entirely for those** — ask whether an extraction from an earlier run is still good for this file's current version:

     ```bash
     python scripts/add_source.py --check-path-cache <source-management-file>
     ```

     - `CACHE_VALID:` (exit 0) → the printed path holds this exact version's extracted text. **Skip step 4's routing entirely** — no extraction tool is called, and no Skill needs to be installed for this source on this run. Read that file in full (read the rest in further chunks if one read truncates it) and use it as the extracted text for steps 5–6 and Pass 2.
     - `CACHE_STALE:` (exit 1) → extract normally. The reason on that line (no cache yet, the file changed, or the file is gone) makes no difference here: whatever is cached is not this version.
     - `ERROR:` → the management file is unreadable or is not a `type: path` source. Treat it as `CACHE_STALE:` and extract normally; this check is an optimization and must not be the thing that stops a source from being processed.

     **This check never touches `source.hash`, and neither may anything you do with the cache.** For `type: path`, `source.hash` is the hash of the **raw file** — the reference point `check_ingest_freshness.py` compares against the file on disk. Handing the cache file to `--write-hash` would overwrite it with an extracted-text hash, and freshness detection for that source would report no change when the file has changed. That is also why the check validates by re-hashing the raw file, not the cache.

     After a route below produces text successfully (and only then — a failed extraction must not be cached, and a `.md` / `.txt` source is not cached at all), ask where it belongs and write it there verbatim:

     ```bash
     python scripts/add_source.py --path-cache-path <source-management-file>
     ```

     `CACHE_PATH:` prints the path and creates its parent directory. Write exactly the extracted text to it, with no summarizing, truncating or re-wrapping — a later run reads this file *instead of* extracting, so anything lost here is lost for good. `.wikicommit/.cache/` is gitignored, so nothing needs to be cleaned up before `/wikicommit-merge`.

     **`.md` / `.txt` sources are deliberately not cached**: the raw file *is* the extracted text, so a cache would be a byte-identical second copy in the category where sources run largest. A cache does not expire when the extraction tool changes version, and it is per-machine (a fresh clone extracts everything once).

   - `type: path`, `.md` / `.txt` → read the file directly
   - `type: path`, `.pdf` (scanned) → Call the `ocr-and-documents` skill
   - `type: path`, `.pdf` (text-based) → Two-tier fallback (on some setups `npx skills add ... --skill pdf` does not make the `pdf` skill visible to the agent; see the install table in `references/text-extraction-routing.md`):
     1. Check whether the `pdf` skill is available and recognized, e.g. by checking that `../pdf/SKILL.md` exists (a sibling of this Skill's directory, whichever Skill tree this is). If it exists, call the `pdf` skill (preferred — better table/encrypted-PDF handling).
     2. Otherwise, fall back to the `markitdown` CLI: run `PYTHONIOENCODING=utf-8 markitdown <path>`. This is subject to the same `markitdown --version` prerequisite check described above — non-zero exit or command not found → stop processing and display the install command from the install table in `references/text-extraction-routing.md` (`pip install 'markitdown[pdf]'`).
     Do not stop processing solely because the `pdf` skill is unavailable — only stop if the `markitdown[pdf]` fallback itself is unavailable.
   - `type: path`, `.docx` → Two-tier fallback (same visibility problem as `.pdf`):
     1. Check whether the `docx` skill is available and recognized, e.g. by checking that `../docx/SKILL.md` exists. If it exists, call the `docx` skill (preferred — tracked-changes/comment handling).
     2. Otherwise, fall back to the `markitdown` CLI: run `PYTHONIOENCODING=utf-8 markitdown <path>`. This is subject to the same `markitdown --version` prerequisite check described above — non-zero exit or command not found → stop processing and display the install command from the install table in `references/text-extraction-routing.md` (`pip install markitdown`).
     Do not stop processing solely because the `docx` skill is unavailable — only stop if the `markitdown` fallback itself is unavailable.
   - `type: path`, `.pptx` → Same two-tier fallback pattern as `.docx` above: check `../pptx/SKILL.md`, prefer the `pptx` skill, otherwise fall back to `PYTHONIOENCODING=utf-8 markitdown <path>` (install command `pip install markitdown`).
   - `type: path`, `.xlsx` → Same two-tier fallback pattern as `.docx` above: check `../xlsx/SKILL.md`, prefer the `xlsx` skill, otherwise fall back to `PYTHONIOENCODING=utf-8 markitdown <path>` (install command `pip install markitdown`).
   - `.epub` → Call the `ebook-extractor` skill (no `markitdown` fallback — `markitdown` does not cover EPUB equivalently)
   - Image files (`.jpg`, `.jpeg`, `.png`, `.gif`, `.tiff`, etc.) → Call the `ocr-and-documents` skill (no `markitdown` fallback — `markitdown` does not cover OCR equivalently)
   - Other → Run the `markitdown` CLI as fallback (Python package, not a Claude Skill — see install table in `references/text-extraction-routing.md`). Subject to the same `markitdown --version` prerequisite check described above: non-zero exit or command not found → stop processing and display the install command from the install table in `references/text-extraction-routing.md`.
5. If the extracted text is empty or unreadable, mark that source as `status: failed` (extraction error), write a one-to-few-sentence reason to the management file's `## Failure Reason` section (create it if absent, overwrite if present — e.g. `"Text extraction failed: markitdown returned empty output for this PDF."`, naming the extraction tool/skill that was tried and what went wrong), notify the user, and skip to the next source. Do not proceed to Passes 2–4 for this source. Write `## Failure Reason` in English regardless of `<primary_lang>` — it is debugging information for the operator, not reader-facing content.

   **Low-density check (guard A)**: otherwise (extracted text is non-empty and readable), run a general, domain-agnostic check for text that is non-empty but still useless — markup/script/JSON boilerplate rather than real content. For a source whose extracted text is on disk — a `type: url`/`type: wikicommit` scratch file, or a `type: path` source's extraction cache written just above — run it against that file:

   ```bash
   python .wikicommit/scripts/check_extraction_quality.py check-density "<the scratch file or extraction cache>"
   ```

   For a `type: path` `.md`/`.txt` source — the one kind with no such file, because it is not cached — pipe the extracted text in via a quoted-delimiter heredoc, which hands arbitrary content (possibly containing shell metacharacters, e.g. backticks in a quoted code sample) to stdin without shell interpretation:

   ```bash
   python .wikicommit/scripts/check_extraction_quality.py check-density <<'EOF'
   <extracted text>
   EOF
   ```

   `OK:` (exit 0) → proceed to step 6 below.

   `LOW_DENSITY:` (exit 1) → **a warning to raise with the human, not an automatic failure**. Unlike guard B — a deterministic verdict about a domain already confirmed broken — this is a text-shape heuristic, and a link-dense government site or a statistics table has essentially the same shape as a JS shell; genuine sources are flagged often enough that failing them outright on this signal is not justified. Branch on whether this run is interactive:

   - **Interactive** (a live human can answer right now): show the script's `LOW_DENSITY:` line verbatim — including its `non-prose breakdown:` figures, which let the human tell a link-dense real page (`links` dominant) or a statistics document (`numbers/tables` dominant) from a script/JSON shell (`other markup` dominant) — and ask whether to continue with this source. Continue → proceed to step 6 as if the check had returned `OK:`, and add this source to a running list rolled up in the Completion Notice (`references/completion-notice.md`), so the override is recorded. Decline → mark `status: failed` exactly like the empty/unreadable case above, writing the `LOW_DENSITY:` line verbatim into `## Failure Reason`.
   - **Non-interactive/subagent-driven** (no real answer will ever arrive): **defer this source — do not mark it `status: failed`**. It must not go on to Pass 2 — passing a genuine shell through unreviewed produces a page citing a source URL that never contained its content. But `status: failed` is the wrong way to stop it: it takes the source out of every collection condition, and nothing then reports it (Pass 1 does not collect `failed`, and `wikicommit-merge`'s generation-failure Issue keys on `failed_pages`, which is empty because no page was attempted).

     Deferring means, precisely:

     - **Leave `status` alone when it is already one the collection step picks up** (`pending` or `outdated`). Do not advance it — nothing about this source was decided. `extracted_tokens` is not written (step 6 is never reached). **Do not blank `source.hash`**: by this point it is already written (by `--write-hash` for `type: url`, at registration for `type: path`), and blanking it would leave the management file disagreeing with the extraction cache the next run matches against. `reconcile_ingest_status.py` leaves a deferred source alone because no page cites its hash, not because the hash is empty. The extraction cache stays, so the next run's re-fetch is cheap.
     - **On a forced recheck, set `status: pending` rather than leaving it.** A `RECHECK:` source reaches here with `status` still `generated`/`failed`/`excluded`, which nothing collects, and `--write-hash` has just replaced `source.hash` with the *new* content's hash — so re-running `/wikicommit-generate <url>` would return `HASH_MATCH`, report "No changes", and lose the changed source behind a success message. Writing `pending` is the same requeue `/wikicommit-reconcile` performs, and `reconcile_ingest_status.py` will not undo it (a source generated before carries `generated_pages` and a `last_generated_at`, and the script skips on either).
     - Write the `LOW_DENSITY:` line verbatim into a **`## Deferred Reason`** section of the management file (create it if absent, overwrite if present), in English regardless of `<primary_lang>`, like `## Failure Reason`. Delete that section as soon as this source reaches any other outcome, exactly as `## Failure Reason` is deleted.
     - Add the source to a running list rolled up in the Completion Notice (`references/completion-notice.md`), and skip to the next source.

     Either way the source stays in the queue, so an interactive run picks it up and asks. `/wikicommit-status` counts it separately from "not reached yet", so the deferral stays visible between runs.

   Make the interactive/non-interactive determination the same way Pass 2b step 1 does, **once per invocation**, and hold it constant — whichever pass first needs it makes the judgment and the other reuses it, so a single run never shows a prompt for one decision and silently defaults another.
6. Otherwise, compute an approximate token count for the extracted text (a rough estimate is fine — e.g., character count ÷ 4, rounded to the nearest integer; no model-specific tokenizer is required) and write it to the management file's `extracted_tokens` field. Overwrite any existing value every time this step is reached — unconditionally as soon as extraction succeeds, regardless of the Pass 2–4 outcome (unlike `last_generated_at`, which Pass 4 only sets on the `generated`/`partial` branches).

   **Missing-transcript note**: for a YouTube source, first check that the extracted text actually is a YouTube-converter result — it starts with a `# YouTube` heading and carries a `### Video Metadata` section with the video's title, keywords and runtime. If it does **not**, `markitdown` never recognized the URL as a video and fell through to its generic HTML converter: this happens for every YouTube URL that is not a `/watch?v=…` (or `youtu.be/<id>`) link — `/shorts/<id>`, `/playlist?list=…`, and channel pages all produce a few hundred characters of footer/navigation links with no title, description or transcript, and guard A does not catch them. Treat that as an extraction failure (step 5 above): mark `status: failed`, write a `## Failure Reason` naming the URL form and pointing at the `https://www.youtube.com/watch?v=<id>` equivalent to register instead, notify the user, and skip to the next source — do **not** send footer links to Pass 2. If it *is* a YouTube-converter result but has no `### Transcript` section, then — since guard C already guaranteed `youtube-transcript-api` is installed — *this particular video has no captions*, a fact about the source rather than a broken environment. Do **not** mark that case `status: failed`: the title, keywords, runtime and description are real content and may be enough. Append the source (its management file path) to a running list rolled up in the Completion Notice (`references/completion-notice.md`), and carry on to Pass 2 — the user decides whether a description-only page is worth keeping.


## Pass 2a: Summary

Ask the LLM to read the full extracted text and produce a 2-3 sentence summary of the source's content, in `<primary_lang>`. This summary is used by Pass 2b (`references/pass2b-type.md`) and is written to the source management file's `## Summary` section at the end of Pass 2c — do not write it yet, since Pass 2c writes the management file body in one step. **Nothing but the summary ever goes into `## Summary`**: the per-entity notes Pass 2c produces (`coverage_gap_note`, exclusion notes) go to a separate `## Generation Notes` section, because `## Summary` is published to `content/sources/` and those notes are not reader-facing (the write-back rules for both sections are in `references/pass2c-entities.md`).

During this same read, also **name the language the extracted text is mainly written in**, as one ISO 639-1 code (`en`, `ja`, `zh`, `ko`, …) — the same two-letter vocabulary as a page's `lang:` and `primary_lang`; do not add a region or script (`zh-Hans`, `pt-BR`). This is a coarse judgment from the text you just read, not library-based detection. Always give exactly one answer: "mainly" settles the mixed case — a `primary_lang` document with foreign proper nouns or quoted snippets is still `primary_lang` — so there is no "multiple" or "undetermined" value. **Write it to the management file now**, as `lang:` under `source:` — fill in the empty `  lang:` line if the file has one, otherwise add `  lang: <code>` directly under the other `source:` keys; overwrite any earlier value. Write it here rather than with `status` in Pass 4 so that a source that stops later in this run (Pass 2b deferral, `status: failed`) still records a language that is already known. It is **not** copied into any page's `sources[]` (unlike `source.license`). Choosing a language changes no generation behavior: entities are still extracted and written in `<primary_lang>` (see the `lang` field rule in Pass 2c). **If the code differs from `<primary_lang>`**, also append this source (its management file path and the code) to a running list rolled up in the Completion Notice (`references/completion-notice.md`); do not stop or ask for confirmation for this — it is purely informational, unlike `ambiguous`/`exclude`.

**Source-as-entity judgment**: also judge whether the source document *itself* — as distinct from the individual people/organizations/concepts it describes — has independent citable identity: a title, named author(s) or publishing organization, and a publication date or stable identifier (DOI, permalink URL), such that a reader would recognize it as a standalone "work" worth linking to on its own (e.g. an arXiv paper, an official vendor blog post announcing a product, an official report/whitepaper, a news article). Do not apply this to sources that are more "information" than "work" — a government procedure page, a personal blog's casual technical explainer with no strong standalone identity — where authorship/publication metadata is weak or absent, or the content is instructions/reference material rather than a citable piece of writing. This is a per-source judgment made once here, not per-entity; when it passes, the source document itself becomes an *additional* entity candidate that flows into Pass 2b (type resolution) and Pass 2c (entity extraction) exactly like any other entity — it does not replace or reduce the extraction of concepts/people/organizations discussed *within* the source, and it introduces no new mechanism, frontmatter field, or `sources:` semantics (see the Pass 2c rule in `references/pass2c-entities.md` and the Pass 3 note in `references/pass3-generate.md`).

As a concrete restatement of the same test: does the source have a fixed publication date and author(s) that will not change (a single-instance work — an article, paper, report, or story), or is it a continuously-updated living resource with no meaningful "publication date" of its own (an official document, a government procedure page, a Wikipedia article)? Only the former qualifies. `installed schema/` ships with `ScholarlyArticle`/`NewsArticle`/`BlogPosting`/`ShortStory`/`Book` by default to cover the common cases without Pass 2b proposing them — Pass 2b remains the fallback for a candidate whose closest fit isn't one of these (e.g. `schema:Report`).
