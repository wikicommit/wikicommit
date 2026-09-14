---
name: wikicommit-review
description: Validate and review a manually created or edited wiki page, then mark it reviewed
disable-model-invocation: true
---

# wikicommit-review

For a page under `.wikicommit/entity/`, this proposes frontmatter completions, checks that `sources` exists, checks the consistency between `sources.hash` and the actual file, re-fetches the page's `sources` and performs an independent, source-grounded fact-check against them (Issue #455 — presenting per-criterion findings for the reviewer's explicit confirmation, rather than just re-displaying the page's full text and asking the human to do the checking unaided), and finally records the review as complete. How that last step is recorded depends on which route the page came from (Issue #313):

- **Route B** (a page a human directly created or edited locally, with no tracking Issue): writes `review_status: reviewed` to the page's frontmatter locally. This serves as proof that a human completed the review on the spot; the user then runs `/wikicommit-merge` to commit and merge it as `reviewed`.
- **Route A** (a page `wikicommit-generate` produced, tracked by an open `wikicommit-review`-labeled Issue that `wikicommit-merge` Step 8 created): closes that tracking Issue via `gh issue close`, rather than writing `review_status` locally. Closing the Issue is what triggers `.github/workflows/review-issue-close-sync.yml` to flip `review_status` to `reviewed` on `main` and auto-merge that change once quality checks pass. Running `wikicommit-review` on a Route A page no longer bypasses anything — closing its tracking Issue *is* the mandatory review gate for Route A, now that a solo operator can actually close an Issue they opened (unlike approving their own PR, which GitHub disallows).

Which of the two applies is determined automatically per page (Step 5) — the user does not need to know which route a given page came from.

## Usage

```
/wikicommit-review <page>   # e.g. /wikicommit-review .wikicommit/entity/ja/Person/yamada-taro.md
/wikicommit-review          # if the argument is omitted, present candidates for the user to choose from
```

## Processing Flow

### Step 0: Determine the Target Page

If an argument is given, use it as the target page.

If the argument is omitted:

```bash
git -c core.quotePath=false status --porcelain -- ".wikicommit/entity/**/*.md" ".wikicommit/view/**/*.md"
```

List pages with uncommitted changes (untracked or modified) and let the user pick one. If the output is empty, display "No target pages" and stop.

The second pathspec covers the view tree (Issue #675), where `/wikicommit-synthesize` writes. Without it, the most common way to arrive here — synthesize a page, then review it before merging — lists nothing at all and stops at "No target pages" while the page sits uncommitted in the working tree. This mirrors `wikicommit-merge` Step 1, which detects changes across both trees. A view page carries `derived_from` rather than `sources`, so Step 3 below takes the `derived_from` branch for it; a wiki that has never run `/wikicommit-synthesize` has no such directory and the pathspec simply matches nothing.

If the target file does not exist, display an error and stop.

### Step 1: Complete Frontmatter

1. Run:

   ```bash
   python .wikicommit/scripts/validate_frontmatter.py <page>
   ```

2. Extract the names of missing fields from the `ERROR:` lines in the output (lines containing the literal string `required field is missing`, which is what `validate_frontmatter.py` currently prints for a missing required field; format-violation errors are not subject to completion proposals — they are only presented to the user in step 4).
3. Determine the corresponding schema file from the target page's `type`:
   - `schema:Person` → `.wikicommit/schema/Person.md`
   - `schema:custom/Decision` → `.wikicommit/schema/custom/Decision.md`
   - Fall back to `.wikicommit/schema/default.md` if it does not exist
4. If there are missing fields, have the LLM propose completions using the page body and the type schema's `properties:` block (its keys and any inline template comments) as clues. **Get the user's confirmation before** writing to the frontmatter (never rewrite without asking). Leave any field the user declines to complete as-is. A completion for a key that belongs under `properties:` (Issue #495) must be nested there, not written flat at the top level.
5. If there are format-violation errors (missing `sha256:` prefix, invalid date format, etc.), likewise present them to the user and fix them only after confirmation.
6. After completion, re-run `python .wikicommit/scripts/validate_frontmatter.py <page>` to check for any remaining errors. Errors caused by fields the user declined to complete may remain — proceeding to the next step is fine (whether to proceed overall is ultimately left to the user in step 4).

### Step 2: Check `sources`

- If the target page is a translated page with `translated_from`, exempt it from the `sources` check (same exception rule as `validate_frontmatter.py` — source information is inherited from the parent page).
- If `sources` does not exist (and the page is not a translated page), prompt to set `type: manual`. Confirm `author` (the creator's name) and `created_at` (`YYYY-MM-DD` format; suggest today's date if omitted) with the user, and add to `sources` in the following form:

  ```yaml
  sources:
    - type: manual
      author: "<user input>"
      created_at: "<YYYY-MM-DD>"
  ```

### Step 3: Consistency Check

For each element of `sources` with `type: path`:

1. Recompute the SHA-256 of the actual file at `sources[].path`:

   ```bash
   python3 -c "
   import hashlib, sys
   h = hashlib.sha256()
   with open(sys.argv[1], 'rb') as f:
       for chunk in iter(lambda: f.read(65536), b''):
           h.update(chunk)
   print(f'sha256:{h.hexdigest()}')
   " "<sources[].path>"
   ```

2. Compare the recomputed result with `sources[].hash`.
3. If they don't match, present it to the user and confirm whether to update `hash` to the recomputed value (never overwrite without asking). If the user declines, leave it as-is.

If `sources[].path` does not exist in the repository, this has already been detected as an ERROR in step 1, so skip recomputation here.

### Step 4: Independent Fact-Check Against Sources

Steps 1–3 only validate structure (frontmatter shape, `sources` presence, hash consistency) — none of them actually check the page's content against anything. This step does that (Issue #455), reusing the source-fetching logic `wikicommit-fix` Step 3 already implements.

**This step covers the machine half of the review, and only that half (Issue #723).** It used to run the tracking-Issue template's checklist verbatim, but that template now also asks things no LLM can answer here: whether the page conflicts with what the reviewer already knows, and whether any sentence unfairly harms a real person or organization. The first is ruled out by the very discipline item 3 imposes — judging on the literal source text and not on world knowledge — so an LLM answering it would be violating the rule that makes the rest of this step trustworthy. The second is a contextual judgment whose false positives delete legitimate writing, which is why WikiCommit keeps it with a human (the same reason `.wikicommit/entity-policy.md` has a human write its prose). Item 3 below therefore reports machine findings only, and item 5 puts the human-only prompts — and the ask for a line on what they took away (Issue #740) — to the reviewer directly.

**For the strongest result, run this Skill in a separate session (and, if practical, a different model) from whichever one generated the page** — see step 2 below for why. WikiCommit ships no LLM inference of its own — you bring the session — so switching session or model costs nothing but re-running the Skill.

**If `.wikicommit/review-rules.md` does not exist, stop and say so.** Do not fall back to a looser check. Without those rules item 3 below degrades to "does the page match the source" and its output still looks normal, while Step 5 goes on to record that a review happened. Tell the user to run `/wikicommit-init --no-overwrite` to install the file. This is an installation problem, not a defect in the page. **Check for the file at the start of the run, before Step 0 offers a page to pick and before Step 1 asks the reviewer anything** — the same point in the run the other two review paths check at, and not when this step is reached (Issue #888). Its absence is knowable from the first moment and depends on no page, so deferring it to item 3 below would mean having already put the reviewer through picking a page, completing frontmatter, confirming a `sources` entry and a hash, and then waiting for every source document to be fetched, for a review that was never going to run.

**This stops pages that would never have read the rules at all, and that is deliberate (Issue #917).** Item 1's last bullet sends a page with no retrievable ground truth — `type: manual`, a fetch that failed, an empty `sources` with no parent, a `derived_from` whose paths all fail to resolve — straight to item 4's full-text fallback, skipping item 3, which is the only consumer of the rules file. Such a page could be reviewed without the file present, and before the check moved here it was. Three things make stopping it the right call anyway, and the first alone is not enough to see why:

- **Whether a page has ground truth is not knowable this early.** Of item 1's four conditions only two (`type: manual`, and an empty `sources` with no parent) can be read off the frontmatter; a failed fetch and an unresolvable `derived_from` are settled by going and looking. So the earliest a conditional gate could sit is *after* item 1 — which puts every page that does have sources through picking, frontmatter completion, hash confirmation and a full fetch of every source document before it can fail. The exception would spend the common case's time to spare the rare one.
- **Mixed records would be indistinguishable in the aggregate.** A `--stage review-skill` record written without the rules and one written with them differ only in whether `--skill-blob` is present, and `check_review_coverage.py` does not read that field. Telling them apart would mean adding a consumer for it, which is the receptacle-without-a-consumer that Issue #553 rules out.
- **The wall is one command wide.** It only stands in a repository that has no `.wikicommit/review-rules.md`, and that file is `update: overwrite` in `_root_outputs.py` — `/wikicommit-init --no-overwrite` installs it with nothing of the user's at risk. What Issue #313 guarantees is not lost, only deferred by one command.

Be plain about this when it fires: say that the file is missing, that some pages — those with no retrievable ground truth — would not have used it and this stop does not tell them apart, and that one `/wikicommit-init --no-overwrite` clears it. **Do not assert it of the page in hand**: the check runs before Step 0 has offered a page to pick, and even when one was named as an argument, two of the four conditions above are not settled until item 1 has fetched — which is the first bullet above, applied to the wording of the message as well as to where the check sits.

1. **Fetch the source documents** (same routing as `wikicommit-fix` Step 3, extended with a third route for synthesized pages — Issue #537):
   - If `sources` is non-empty, use the normal per-element routing below — `derived_from` and `translated_from` only exempt a page from `sources` being *required*, not from carrying one (`validate_frontmatter.py` skips the required-field check for these pages but still format-validates `sources` if present; `wikicommit-fix` Step 3's translated-page branch draws the same "permitted, not required" distinction).
   - Otherwise, if the page has `derived_from` (a `wikicommit-synthesize` output, Issue #283), read each `derived_from[].path` entry directly with the Read tool — these are `.wikicommit/entity/` pages within this repo, not external sources needing extraction or fetching. A page written before the Issue #477 `.wikicommit/wiki/` → `.wikicommit/entity/` rename may still store the old prefix in this field with no auto-migration; if the literal stored path doesn't exist, retry after substituting `.wikicommit/entity/` for a leading `.wikicommit/wiki/` before concluding the entry is missing (same tolerance Step 5 item 1 applies to the tracking-Issue marker path). Treat each entry independently — a page with several `derived_from` entries where only some paths resolve should still fact-check against whichever entries were successfully read.
   - Otherwise, if `sources` is empty and the page is a translated page with `translated_from`, read the parent page's `sources` instead (a translation page inherits its source information from the parent).
   - **Once the `sources` list is settled, and before fetching anything, drop the entries a human has withdrawn (Issue #928).** Run `python .wikicommit/scripts/check_retracted_sources.py --list` once for the run; every `RETRACTED: <identity> (<management file>)` line names a source whose management file carries `status: retracted`, written by hand to record that someone read the document and judged its content unreliable (Issue #737). Match those identities against this page's `sources[]` entries by `path`/`url` and **leave the matching entries out of the fetch below**, keeping a note of which ones and of the management file each was named in. Three things about where this sits:
     - **Before the fetch, not after.** Fetching costs a round trip and, worse, puts the withdrawn text into context, after which "do not use it" depends on instruction-following. `resolve_source_cache_path.py` checks `status` before it looks for a cache for the same reason.
     - **After the `sources` list is settled, not before.** A translation page has no `sources` of its own and inherits the parent's, so a guard applied earlier would let a withdrawn source through on exactly those pages.
     - **Not on the `derived_from` route.** Those entries are `.wikicommit/entity/` pages, which carry no `status` to read. The indirect case — a grounding page still standing on a withdrawn source — is out of scope here and is reported one hop earlier by `check_retracted_sources.py`, which names that grounding page itself.

     If the script or the `--list` flag is not there (an older `.wikicommit/scripts/`), **say so and carry on** — the degradation is the behaviour from before Issue #928, and on a wiki that has retracted nothing it is a no-op either way. Do not stop over it, and do not pass over it in silence.
   - For each element of `sources`:
     - `type: path` and `.md`/`.txt` → read directly with the Read tool
     - `type: path` with any other extension → call the corresponding extraction skill per the "Prerequisite Skills (Text Extraction)" table in `.claude/skills/wikicommit-generate/SKILL.md`. If the required skill is not installed, guide the user through the install command and stop.
     - `type: url` / `type: wikicommit` → fetch `source.url` with the WebFetch tool
     - `type: manual` → no source document exists for this page
   - If no source document could be obtained at all (fetch failure, `type: manual`, empty `sources` with no parent page to fall back to, every `derived_from` entry's path unresolvable, or **every remaining entry withdrawn by the bullet above**), there is no ground truth to check the page against — skip step 3 and go straight to the full-text fallback in step 4. The retracted case needs no branch of its own: what is left is a page with nothing to measure it by, which is what that fallback already handles.

2. **Self-report the currently running model ID** (the same self-identification pattern `wikicommit-generate` Pass 3 uses — see that SKILL.md's "Set `generated_by` to the currently running model ID" step) and compare it to the page's frontmatter `generated_by` (or, for a translated page with `translated_from`, its `translated_by` — the field `wikicommit-translate` writes instead of `generated_by`), whichever is present. If they match, note in your output that this review is not independent of the generation/translation that produced the page, and recommend re-running `/wikicommit-review` in a separate session and/or under a different model for a stronger check. Skip this note entirely if neither field is present (typical for Route B pages a human created or edited directly, which never went through `wikicommit-generate`/`wikicommit-translate`).

3. **Check the page against the fetched source documents**, reporting one finding per item (`OK`, or `NEEDS REVIEW: <reason>`).

   **The checks themselves are in `.wikicommit/review-rules.md` (Issue #752)** — read it and follow it. That file is the single copy of the review discipline, shared with `wikicommit-generate` Pass 4 and `wikicommit-synthesize` Step 5.5; it scopes checks by path and has a section per path, and **this path is `review-skill`** — the same label Step 5's `--stage` records. Before this it was restated in all three, and the three had already drifted: checks this path never had (naming vs. inventing, secondary citations, source-vs-source disagreement) now apply here too, because this path fetches the same sources and can run them.

   **This path has no subagent**, so there is nothing to hand the rules to and nothing to echo `rules_version` back — you read them yourself. That also means the echo check that protects the other two paths does not protect this one; read the file rather than working from memory of it.

   **What to do with a cited-but-unheld document.** The rules file's check 4 detects it; what happens next is this Skill's business, and differs from the other paths: there is no retry loop to roll it up into, so report it as a finding of its own naming that URL or title. It is a **registration candidate**, not just a defect — `/wikicommit-generate <url-or-path>` registers it and the next run folds it in. Skip it when the page traces a claim only to something unidentifiable ("an earlier post" with neither URL nor title): there would be nothing to register. It does not arise at all on a `derived_from` page — the rules file exempts that case, because the evidence there is grounding pages and a claim they do not carry names no document to register.

   **What a withdrawn source leaves behind.** When item 1 dropped one, the checks run against the narrowed evidence set — and that is the point rather than a side effect. Claims the page made on the strength of the withdrawn document now have nothing carrying them, and check 1 surfaces them one at a time. **That information exists nowhere else**: `check_retracted_sources.py` can say this page names that source, but not which of its sentences depended on it, and the latter is the granularity a person needs in order to choose between rebuilding the page, correcting it and taking it down. Report each as a finding of its own, naming the withdrawn source, and **word it as "this passage stood only on a source that has since been withdrawn" and not as "this passage is wrong"** — the page may be perfectly faithful to what it was written from, and the other wording pushes the reviewer toward deleting text when `/wikicommit-generate --regenerate` (Issue #744, which drops the retracted entry and rebuilds from what remains) is often the right route. Do not fold these into check 4's registration candidates: nothing here wants registering, since a person deliberately took a document out of use.

   One thing this step decides that the rules do not: **which page type's checklist applies** is settled by the page's provenance field — the same three-way split `wikicommit-merge`'s tracking-Issue template uses (Issue #525), and the rules file lists the three under this path. On a `sources`-based page there is one extra item, conditional: only if this page's `type` was added on the fly by `wikicommit-generate` Pass 2b (Issue #315) — read `.wikicommit/schema/<Type>.md`, where `<Type>` is the frontmatter `type` value with the `schema:` prefix stripped (`schema:Person` → `Person`, `schema:custom/Decision` → `custom/Decision`), and check whether its `wikicommit.provenance` is `generate-interactive` or `generate-auto` (Issue #519 / #507); any other value, or no schema file at all, means skip it — is that type the right one for this subject, and do the `properties:` keys that schema file lists fit it? (`recommended` is not the field to look for: Issue #495 removed the type-level `recommended` list and `properties:` took over its role.) This is the same condition, resolved the same way, that `wikicommit-merge`'s tracking-Issue template uses for its own copy of this item (Issue #729): the batch that generated the page is not knowable from the page alone, whereas `provenance` is a permanent stamp any run can read.

4. **Do not display the page's full text by default.** Present only the findings from steps 2–3 to the reviewer. Fall back to displaying the full content (frontmatter + body) when either the reviewer explicitly asks to see it, or step 1 found no usable source document — this preserves Issue #313's original guarantee (a human actually read the page) for exactly the cases where the fact-check above has no ground truth to lean on.

5. Ask the reviewer to confirm, and ask them for one line. Phrase this in user-facing terms — describe what confirming will do (e.g. "so I can record that you have read this page") rather than naming the internal step that follows.

   **Ask for the line first (Issue #740).** `review_status` is a two-valued field, so what it can carry is an event: this page was read by a person, or it has not been. That is what closing records, and the line is its trace. **Recording `reviewed` states two things (Issue #800)**: that this page's knowledge reached a person, and that nothing struck them as obviously wrong while reading — not that the content is correct. The second half fits in a two-valued field because it is a claim about the *reading* (it ends when they finish reading), not about the page ("this page has no problems" is a negative proof with no end); keep the "not being asked to go looking" wording below for exactly that reason. Ask for **one line on what they took away from the page** — not a summary; "that surprised me" or "nothing here was new to me" is enough — and say plainly that **this is not a test of their understanding**, because without that the request reads as something they will be marked on and reintroduces the weight this shape removes. There is no correct answer, so there is nothing to mark and nothing to fake. Do not tell them "this is not a review": all of it comes from one reading, and the word covers the whole of it.

   **Then put the human-only prompts in the same breath (Issue #723)**, so confirming means answering them rather than waving past them. Introduce them as what the check above did *not* cover — item 3 compared the page against its sources, and the published banner says so too (Issue #751), so a reader who is not told this may assume nothing was checked. Ask plainly, and say outright that they are **not** being asked to go looking:
   - Anything that conflicts with what they already know, or an important fact about the subject that none of its sources carry. If they have a URL, take it: `/wikicommit-generate <url>` folds what it says into the page, which then comes back to be read again.
   - Anything about a real person or organization that reads as overstated, as settled when it is disputed, or as a private detail the page has no reason to hold.
   - Anything another page on this wiki says differently. The machine can only compare a page against ones written before it in the same batch (Issue #566 records this limit as accepted, not solved), so a contradiction across batches is visible to nobody but a person reading several pages over time.
   - Anything wrong with a **source** the page was written from, rather than with the page (Issue #743). Ask this as its own question: item 3 above measured the page *against* those sources, so a page faithfully repeating a source's error came back clean. Under the evidence-binding rule that makes item 3 trustworthy, no machine can doubt a source — this is the same class of thing as harm. If they name one, tell them the source's management file needs `status: retracted` and a `## Retraction Reason` written by hand (Issue #737), and that `/wikicommit-status` then lists every page still standing on it. Do not write either yourself: which sources this wiki trusts is not a call this Skill makes.

   **If item 1 dropped a withdrawn source, tell them before they confirm (Issue #928).** The bullet above asks what to do when a reviewer finds a bad source; this is the same thing from the other end — someone already did, and this page still rests on what they withdrew. Name the source, point at the management file where they wrote `## Retraction Reason` (the only place the reason exists), and say which passages item 3 found standing only on it. Then leave the decision where Issue #737 put it: `/wikicommit-generate --regenerate` rebuilds from the sources that remain, `/wikicommit-fix` corrects the text by hand, `/wikicommit-remove` takes the page down when nothing is left holding it up. **Do not make confirming conditional on any of it.** Recording `reviewed` states that a person read the page and that nothing struck them as obviously wrong (Issue #800) — a claim about the reading, not about the standing of the evidence behind it. Refusing to record it here would add a third state to the trust ladder by the back door and leave the page unable to reach `reviewed` until someone acts, which is exactly the call Issue #737 left with a human.

   **Ask the knowledge prompt, the cross-page one and the source-validity one only for a `sources`-based page.** On a translation, a stale or wrong fact — including one another page contradicts — belongs to the original page, and on a `derived_from` page it belongs to whichever grounding page states it — the same redirect `wikicommit-fix` makes (Issue #529), and the same split `wikicommit-merge`'s three tracking-Issue variants make (Issue #525), which carry the contradiction and source-validity prompts on the `sources` variant only. A translation has no `sources` of its own and a synthesized page has `derived_from`, so on both the documents in question belong to a different page. Ask the harm prompt on all three: a harmful sentence is harmful whatever produced it, and on a synthesized page it is the only check of its kind, since every automated check there compares single claims against grounding pages and never asks what several of them imply together.

   **Record the line.** Whatever they answer goes into `record_review.py`'s `--note` in Step 5 item 4, which is where a human record's prose body is meant to live. Declining to write one is not a blocker — the review is still recorded — but the record then carries no trace of what landed.

   **If the reviewer names a document the page does not already cite, stop here too**, and tell them to register it with `/wikicommit-generate <url-or-path>` (then `/wikicommit-merge`) before re-running this Skill. Recording the review now would sign off a version that does not yet reflect what they just told you, and the answer would survive only in this conversation — the tracking-Issue checklist promises the opposite, that a registered URL is folded in and the page comes back for review. Report it in your output the same way item 3 reports a document the page cites but does not hold: it is a registration candidate, not a defect in the page.

   If the reviewer declines to confirm, or flags a problem, stop here without doing anything in Step 5 (declining to write the line is not that — record the review with no `--note`); let them fix the page (directly, or via `/wikicommit-fix`) and re-run `/wikicommit-review` afterward. **Do not record `reviewed` over a flagged problem** — with the second half of the claim above, doing so would state something the reviewer just contradicted. This matches the tracking Issue's instruction on route A, where a reader who noticed something is told to comment and leave the Issue open.

### Step 5: Check for a Tracking Issue, Then Record Review Completion

1. Check whether the target page has an open tracking Issue (created by `wikicommit-merge` Step 8 for Route A pages):

   ```bash
   gh issue list --label wikicommit-review --state open --json number,body --limit 1000
   ```

   Scan the returned `body` values locally for the exact marker `<!-- wikicommit-page: <page> -->`, where `<page>` is the target page's repo-relative path (e.g. `.wikicommit/entity/ja/Person/yamada-taro.md`) **or** the same marker with `.wikicommit/entity/` replaced by the pre-Issue-#477 `.wikicommit/wiki/` (an Issue opened before that rename still embeds its marker with the old prefix verbatim; old and new forms are allowed to coexist rather than being auto-migrated) — matching only the current-prefix form would misclassify such a page as Route B (no Issue found) and write `review_status: reviewed` locally instead of closing the real Issue, leaving it open and orphaned. Do not rely on `gh issue list --search` for this (same tokenization caveat as `wikicommit-merge` Step 8's "Checking for Existing Tracking Issues" — an HTML comment containing `/`, `.`, `-`, `:` is not guaranteed to be treated as one exact-match search token).

2. **If a matching open Issue is found** (Route A page): confirm with the user, then close it:

   ```bash
   gh issue close <number>
   ```

   Do not write `review_status` locally in this case. Closing the Issue is what triggers `.github/workflows/review-issue-close-sync.yml` (Issue #313), which flips `review_status` from `pending` to `reviewed` on `main` via its own PR once quality checks pass. If the target page *also* has local uncommitted edits, tell the user to run `/wikicommit-merge` first so the version on `main` reflects those edits, then come back and close the Issue — closing it now would sync `review_status` against the older `main` version, not the local edits.

3. **If no matching open Issue is found** (Route B page — created or edited locally, never routed through `wikicommit-merge` Step 8): fall back to the original local write.

   1. Check the target page's current `review_status` value (available from the frontmatter read in step 1). If the value is neither `pending` nor unset (e.g. already `reviewed`), explicitly confirm with the user whether it's okay to overwrite it (tell them what will be lost — e.g. "review_status is currently `reviewed`. Overwriting it will discard that state. Continue?").
   2. Present the results of steps 1–4 to the user and confirm whether to proceed. Only write `review_status: reviewed` to the target page's frontmatter (locally only, do not commit) if the user approves.

   ```bash
   python .wikicommit/scripts/set_frontmatter_field.py "<page>" --set review_status=reviewed --unset reviewed_by
   ```

   `--unset reviewed_by` drops any reviewer login left behind by a previous review (Issue #705). That field records the GitHub login of whoever closed a tracking Issue, and only the tracking-Issue workflow can write it — this Skill runs locally and has no authenticated login to record. If the page had been reviewed that way before, was later returned to `pending`, and is now being reviewed here, leaving the old value would publish the previous reviewer's name against a version they never saw. Removing it is a no-op when the field is absent, which is the common case.

   This rewrites (or appends) the `review_status` line and drops the `reviewed_by` line inside the frontmatter block, leaving every other field, the body, and the original line-ending convention untouched (`set_frontmatter_field.py` uses regex substitution rather than re-serializing with pyyaml, which would change indentation, quoting, and key order). This same script is shared with `.github/workflows/review-issue-close-sync.yml`'s equivalent rewrite for Route A pages (Issue #371 — both previously carried independent copies of this logic, which had already drifted once: the workflow guarded on the current value being exactly `pending` before Issue #370's review surfaced that this Step did not).

   If no frontmatter is found (`FRONTMATTER_RE` does not match), stop and display an error.

4. **Record the review, on both paths (Issue #750).** Do this whether the tracking Issue was closed in item 2 or `review_status` was written locally in item 3 — the record is of the review, not of how its outcome was filed:

   ```bash
   python .wikicommit/scripts/record_review.py "$(cat <<'EOF'
   <page>
   EOF
   )" --kind <ai|human> --stage review-skill \
     --skill-blob "$(git hash-object .wikicommit/review-rules.md)" \
     --attempts 1 --result <pass|fail> \
     [--model "<model ID>" | --reviewer "<GitHub login>"] \
     --note "<the reviewer's own one-line observation, if any>"
   ```

   **`--kind` follows who actually made the judgment**, not which Skill was running. A person who read the fact-check findings above and decided is `human`; an unattended run in which the model settled it is `ai`. Pass `--model` for `ai` and `--reviewer` for `human` — and leave `--reviewer` off when there is no authenticated GitHub login to record, which is the normal case here: this Skill runs locally, and a git author is self-asserted (the same reason `reviewed_by` is only ever written by the tracking-Issue workflow, Issue #705). An absent reviewer reads as unknown; a guessed one reads as a name that never signed off.

   `--result` is the verdict of the fact-check above, not the state of the page afterwards: `pass` when it found nothing to fix, `fail` when it did. If that step produced findings in the shared JSON form, pass them through with `--json -` so the specifics are kept rather than summarized away.

   Then print one line reporting what was recorded — how many findings, and who or what reviewed — so the run says what it did rather than only that it finished:

   ```
   Reviewed 1 page against its sources: 0 finding(s) raised.
     → record in .wikicommit/review/
   ```


### Guidance After Completion

Give the user status- and action-oriented guidance (never echo the internal `Route A`/`Route B` labels themselves; describe the actual state instead). The conditions below are for you to select between, not text to output — send the user only the sentence(s) that follow the matching condition:

If the target page had a tracking Issue that was just closed:

```
This page had a tracking Issue, and it's now closed.
Next steps:
- Nothing further to do. .github/workflows/review-issue-close-sync.yml will open its own PR
  for this page and auto-merge it once quality checks pass.
```

If the target page had no tracking Issue, so review_status was written locally:

```
No tracking Issue was found for this page, so review_status: reviewed was recorded locally.
Next steps:
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
  (pages with review_status: reviewed are excluded from tracking-Issue generation)
```

## Notes

- Do not commit or create a PR against `main` or any branch (that is `wikicommit-merge`'s responsibility)
- Do not write to `.wikicommit/schema/` (read-only)
- Never overwrite frontmatter without user confirmation (applies to steps 1, 2, 3, and 5 alike)
- Never close a tracking Issue without user confirmation (Step 5)
