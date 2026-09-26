---
pass_token: "5e9b2d84"
---

# Pass 2b: Type Necessity Judgment

> **Paths in this file.** `references/…`, `scripts/…` and `../<other-skill>/…` are relative to the Skill's directory (the parent of this `references/` directory), not to the repository root — the Skills may be installed under `.claude/skills/` or `.agents/skills/`. Commands still run from the repository root, so spell the path out from there. Paths starting with `.wikicommit/` are repository-root paths as before.

**Stamp `--pass pass2b-type` on entry**, with `--source` naming this source's management file. **Pass `--token 5e9b2d84` with it** — the value of this file's `pass_token`. `record_run.py` opens this file itself to compare, so the stamp records that this file was read rather than that the pass was improvised; without `--token` the stamp reads `token: unchecked`.

Before extracting entities, decide whether the source content calls for a Schema.org type that isn't already in `installed schema/`. This runs **once per source** (not once per entity) and is grounded in the Pass 2a summary. The evidence is the actual source content rather than a single free-text `theme` sentence, so this judgment is comparatively high-confidence.

1. Load the Schema.org type names (this also builds the shared vocabulary cache lazily on first use): `python .wikicommit/scripts/check_schema_org_type.py --list-type-names`. Run this once per `/wikicommit-generate` invocation (not once per source). This prints the 933 type names without their descriptions -- stage one of type recall; step 2 below picks candidates from it and reads only those descriptions. Non-zero exit (vocabulary fetch failed) → skip Pass 2b entirely for every source this run and proceed straight to Pass 2c with only `installed schema/` types available; do not block or fail the run over this.

   **Also determine, once per invocation (not once per candidate)**: is this run interactive
   (a live human can actually answer an Enter prompt right now) or non-interactive/subagent-driven (no
   real answer will ever arrive)? If Pass 1's low-density check already made this determination earlier in
   this run, reuse that answer rather than re-judging it. Make it once here, at the top of Pass 2b, and
   hold it constant for every candidate across every source in this run — interactivity is a property of
   the run, and re-deriving it per candidate risks the judgment flipping mid-run and the Completion Notice
   misrepresenting what actually happened. Step 3 below branches on this stored determination.
2. Using the `--list-type-names` output and the Pass 2a summary, judge whether one or more Schema.org standard types — beyond what's already in `installed schema/` — would fit this source's content meaningfully better than any installed type (not merely "also plausible": a clearer semantic fit, where more of the source's concrete details map onto that type's actual properties). Skip any candidate type that already has a file in `.wikicommit/schema/`, including one just added by an earlier source **in this same run** (scan the directory on disk, same reasoning as the existing-pages scan in Pass 2c, `references/pass2c-entities.md`) — never propose a type twice. Zero candidates is an expected common outcome, not a fallback; do not force a candidate to justify running this step. **This includes the source document itself** when Pass 2a flagged it as a source-entity candidate: judge a type for it the same way as for any other candidate (e.g. `schema:Report` for a whitepaper, `schema:Legislation` for a piece of legislation — not `schema:ScholarlyArticle`/`NewsArticle`/`BlogPosting`/`ShortStory`/`Book`, which already ship in `installed schema/` by default and so are resolved directly in Pass 2c without ever reaching this step). Note that the source management file's `schema:` hint (the Pass 2c context list, `references/pass2c-entities.md`) describes the source's primary discussed *subject* (e.g. `schema:Person` for a biography) — it is not evidence about what the source *document itself* is, so it does not carry over to this judgment; treat the source-entity's type purely on its own content-fit merits, independent of whatever hint applies to the entities discussed within the source.

   **Named-entity pattern**: apply extra scrutiny when a candidate entity is a concrete, named subject — a specific software product, research dataset/benchmark, creative work, standard, etc. — rather than an abstract term, concept, or methodology. `DefinedTerm` is broad enough to technically represent almost anything with a name, which can make it look like a safe default and suppress a proposal that would otherwise pass the bar above. For this pattern specifically, the fact that `DefinedTerm` could technically represent the entity is **not** by itself a reason to skip proposing a more specific standard type (e.g. `SoftwareApplication` for a named software product, `Dataset` for a named benchmark). This does not relax the threshold for abstract terms/concepts/methodologies (e.g. a named approach like "vibe coding" with no more specific standard type) — those should still default to zero candidates.

   **Then confirm the candidates against the vocabulary before going further** (stage two):

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

   Each candidate name goes through its own quote-delimited heredoc, for the same reason the `--property` values in `.wikicommit/schema-authoring.md` do — these are names this step itself just proposed, not values an earlier script already verified. Names alone are enough to bring a type to mind, but not always enough to be sure what it means — read the descriptions of the handful you picked and drop any whose actual definition does not fit. A name that comes back as `ERROR:` was invented rather than recalled; drop it. Call this again if you want to look at more names.
3. For each candidate, branch on the interactive/non-interactive determination made once, for the whole
   run, in step 1 above:

   - **Interactive**: present the candidate and ask for approval, Enter-based (default to **N** on a
     blank Enter) — the step 2 threshold above is the only bar a human-reviewed candidate has to clear:

     ```
     This source's content suggests schema:GovernmentService might fit better than any installed
     schema/ type for the following entities: "児童手当の申請手続き" (a government benefit application
     procedure — schema:GovernmentService's jurisdiction/availableChannel/hoursAvailable properties
     fit this content more directly than schema:HowTo's generic step list).

     Add this type now? [y/N]
     ```

     If declined (the user typed N or left it blank), record it as **explicitly declined**.

   - **Non-interactive/subagent-driven**: no human will ever see the prompt above, so defaulting it to N
     unconditionally would silently drop every candidate regardless of merit. Do not show the prompt at
     all. Instead, apply a second, stricter filter to the candidate: is the type **obviously** implied by
     this source's content, not merely a clearer semantic fit than any installed type (step 2's bar) — the
     same "obviously implied, not merely plausible" bar `wikicommit-init`'s theme-driven judgment and
     `wikicommit-collect`'s Type Proposal step apply, except grounded here in the actual source content,
     the strongest evidence of the three, which is why clearing it is high-confidence enough to skip human
     confirmation entirely. This is genuinely stricter than step 2, not the same judgment restated: step 2 only asks
     whether the type fits *better* than any installed type, while this bar asks whether the fit is
     *unmistakable* — a source that merely makes `schema:GovernmentService` the better choice over
     `schema:HowTo` clears step 2 but may not clear this bar; a source unambiguously about a single named
     software product clears both.
       - Clears the stricter bar → treat as **approved without ever showing the prompt** (default **Y**)
         and proceed directly to step 4 for it.
       - Does not clear the stricter bar → **defer this source**. Do not record the
         candidate as declined and do not carry on to Pass 2c: declining it means Pass 2c runs with
         only the installed types available, the entity is written under an ancestor type, and there
         is no Skill that can reclassify a page afterwards. The judgment "is this type right for this
         subject" is one a human seeing the source would answer. **Deferring is not persisting the candidate**: nothing
         about it is written down. The source simply does not advance, so the next interactive run
         reads the same source, reaches the same candidate, and shows the prompt.

         Concretely, exactly as guard A defers in Pass 1 (`references/pass1-extract.md`): leave `status`
         as it is when it is one the collection step picks up, and on a forced recheck — where it is still
         `generated`/`failed`/`excluded` and nothing would collect it — set it to `pending` instead, for the
         reason given there. Write the candidate type name and the motivating entities into a
         **`## Deferred Reason`** section of this source's management file (English, deleted as soon as the
         source reaches any other outcome), roll the source up in the Completion Notice, and skip to the next
         source. `source.hash` and `extracted_tokens` are already written by the time Pass 2b runs; leave them.

   Whichever of the three outcomes applies (explicitly declined, deferred for want of a human, or
   non-interactively auto-approved), append the candidate — its type name, the motivating
   entities/reasoning, this source's source management file path, and which outcome it was — to a running
   list so it can be rolled up in the Completion Notice (`references/completion-notice.md`). Record
   the actual outcome rather than assuming one: the Completion Notice must describe accurately what
   happened in *this* run, and an interactive session where the user typed N themselves is not a
   deferral — a human answered, and that answer stands. This is conversation-only bookkeeping, not a file write — it does not conflict with
   step 5's "no persistence" rule below, and it applies equally to the auto-approved case: the type file
   itself is written in step 4 like any other approval, but *why* it was approved without a human still
   needs to reach the Completion Notice.

4. **For each approved candidate, read `.wikicommit/schema-authoring.md` and follow it** to verify the type, pick and verify its properties, and write `.wikicommit/schema/<Type>.md`. That file holds the whole procedure — property selection and verification, the file format, how to write `granularity`, and the add-only restriction — because four paths write type files and only the judgment differs between them. Pass the value it asks for: **`provenance` is `generate-interactive` if a human answered the Enter prompt in step 3, `generate-auto` if it was auto-approved with no prompt shown**.

   Three things this step is accountable for even if that Read is skipped, so that the fallback is thin guidance rather than none: **every property goes through `check_schema_org_type.py` before it enters `properties:`**, **one `granularity` rule starts with `Boundary —`** (em dash, not a colon), and **`provenance` carries this path's own value** rather than the `default` that `Person.md` shows.

   **If `.wikicommit/schema-authoring.md` is not present** (a wiki initialized before it shipped, or Skills updated without re-running init), **read the copy in the Skill tree instead** — `../wikicommit-init/scripts/templates/schema-authoring.md`, the same file `init.py` expands, which `install.sh` and `npx skills add` carry into every installation of these Skills (the route `/wikicommit-update` already takes for a script an older repository does not have yet). Say which copy you read. **Only if neither is readable**, do not write the file: reject this candidate, name the missing file and `/wikicommit-init --no-overwrite` as the way to get it, and carry on with the rest of the run. The entity falls back to an installed type, which is the same outcome as the ordinary no-candidate case, and `check_schema_coverage.py` reports the gap afterwards. Do **not** abort the run over it — unlike `.wikicommit/review-rules.md`, which every run reaches, this file is reached only when a type is actually being added, and adding none is the normal result.

   Writing the file is the one narrow exception to `wikicommit-generate`'s "Git operations: none, `.wikicommit/schema/`: read-only" contract (the Notes section of `SKILL.md`) — it only ever *adds* a file that is not there yet. No PR and no commit here: the file is left on disk like every other file this Skill writes, and `wikicommit-merge` picks it up later (see that Skill's `git add` scope).

   **If the `granularity` states a boundary against a type that already has a file in `.wikicommit/schema/`**, the shared procedure has you record the new type name, the installed type, and the bullet — carry that into the Completion Notice (`references/completion-notice.md`). It is conversation-only bookkeeping like step 3's list: not a file write, and not covered by step 5's no-persistence rule.

5. Rejected or no-candidate types are simply not added — there is no **persistence** of a declined candidate to any file anywhere (deliberately: an indirect signal that only surfaces "later, maybe" gets lost). The running list from step 3 above is the one narrow exception, and it stays that way on purpose: it is reported once, in this run's own Completion Notice, and then gone — never written to a management file, never something a *later*, separate `/wikicommit-generate` invocation (with no memory of this run) could discover. If content generated in this run ends up using a `type:` string with no dedicated schema file regardless (e.g. because Pass 2b found nothing but Pass 2c still needs `ambiguous: true` for some other reason), `wikicommit-schema-propose`'s `check_schema_coverage.py`-based scan remains the post-hoc safety net (see that Skill's Notes) — but **not** for a declined candidate that fell back to an already-covered installed type (e.g. `schema:DefinedTerm`): `check_schema_coverage.py` only detects `type:` strings with *no* dedicated schema file, so it cannot tell a declined-then-fell-back-to-`DefinedTerm` page apart from a page that was always meant to be `DefinedTerm` — do not suggest `/wikicommit-schema-propose` as a way to reconsider a declined Pass 2b candidate; see `references/completion-notice.md` for the guidance to give instead.
