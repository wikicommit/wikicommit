---
name: wikicommit-synthesize
description: Synthesize a new view page about a topic from existing wiki content, written directly to .wikicommit/view/
disable-model-invocation: true
---

# wikicommit-synthesize

Synthesizes a new **view page** about a given concept or term from the content of `.wikicommit/entity/` itself — the counterpart to `/wikicommit-generate` (which creates pages from external sources): `generate` starts from a source document, `synthesize` starts from existing wiki pages. Gathering related pages uses the same cross-lingual search logic as `wikicommit-ask` (p3-007). The result is written to `.wikicommit/view/<lang>/<slug>.md` — subject to the quality gate and mergeable via `/wikicommit-merge` like any other page. This Skill has no dedicated scripts of its own (it calls the shared `search_index.py`, `rebuild_index.py` and, in survey mode, `build_survey_view.py`).

**Why a separate tree** (Issue #675): the wiki holds two things that are checked against different evidence — a page grounded in an external document (`sources` + hash) and a page grounded in this wiki's own pages (`derived_from`). What separates them is not their subject but what a claim on them can be traced to, and a reader following the site's navigation could not see which was which while both sat in the same type directories. A view page carries **no `type:`** either: Schema.org models things, and what a view page holds is a *reading* of several pages, so making one pick a type meant inventing one. It has an optional **`kind`** instead — what the page does with several pages at once, not what it is about.

`disable-model-invocation: true` is set because, unlike the read-only `wikicommit-ask`/`wikicommit-quiz` it's derived from, this Skill writes new files under `.wikicommit/`  — the same side-effect class as `wikicommit-generate`/`wikicommit-review`.

## Usage

```
/wikicommit-synthesize <topic>     # write about a topic you already have in mind
/wikicommit-synthesize             # survey the wiki first, and pick a topic out of it
```

With no `<topic>`, Step 0 below surveys the whole wiki, proposes angles that only
become visible across pages, and hands the one you choose to Step 1 as `<topic>`.
Everything from Step 1 on is identical in both modes.

## Processing Flow

**Open a run record first (Issue #790)**:

```bash
python .wikicommit/scripts/record_run.py start --skill wikicommit-synthesize \
    --model "<the model ID this runtime reports for you>" --arg "<the topic, if one was given>"
```

A record with a start and no end is what says a run did not finish, and nothing else in this repository is keyed on a run — so leaving it open is the signal rather than a failure state to avoid. Keep the path it prints.

### Step 0: Survey Mode (only when `<topic>` is absent)

Skip this step entirely when `<topic>` was given.

Every later step starts by turning `<topic>` into a search query, so with a
`<topic>` argument the Skill can only write about something the person already
knew to ask for. The angles worth writing about are often the ones that only
appear once you look at several pages at once — a period shared by several
`Event` pages, several `Place` pages that turn out to connect through one
`Person`, a subject whose treatment is split across two type directories. There
was no way in for those.

**This step's output is not deterministic.** The same wiki will suggest
different angles on different runs. That is expected: this is idea support, not
a quality gate, and it is why nothing here writes to disk until you have chosen.

#### 0.1 Build the reduced view

```bash
python .wikicommit/scripts/build_survey_view.py
```

The wiki's full text does not fit in one context, so the script reduces every
page to the lines that carry its cross-cutting structure — title, type, tags,
`properties.description`, its `##` section headings, and the WikiLinks it makes
— and adds the rankings computed from the link graph (`HUB:`, `TAG:`, `TYPE:`).
It lists the wiki's `primary_lang` by default; pass `--lang all` to include
translations, though they restate the same content in another language and
mostly cost context. The link graph is always built from every language.

Read the whole output into context. If it prints a `TRUNCATED:` line, say so
plainly — the survey is incomplete, and the angles it proposes come from only
the most-linked part of the wiki. Offer to re-run with a higher `--max-pages`.

**What this view can and cannot see.** Section headings are the cheapest part of
a body that still names what it covers, and the link graph is where the strongest
cross-page patterns live — "several `Place` pages connect through one `Person`"
is not a statement about any page's text at all, and only a view holding all of
them at once can find it. What the view does not have is body prose: a pattern
that exists only in wording, with nothing in the headings, tags or links to hint
at it, will not surface here. Reading every body through chunked subagents would
reach those, at the cost of reading the whole wiki on each run and of the
splitting problem that comes with it — evidence for one cross-page pattern
landing in two different chunks, with neither subagent able to see it. That is
left for later, and would share its machinery with whole-wiki contradiction
detection.

#### 0.2 Propose angles

From that view, propose **at most 5** angles, matching the count at which the
other Skills stop and ask (`wikicommit-generate` / `wikicommit-collect` /
`wikicommit-translate` all use 5). Fewer is fine; a wiki with little structure
in it should get few. For each, give:

- a short topic phrase, in `primary_lang`, in the form Step 1 can take as `<topic>`
- the **kind** it would be written as (Step 5's table), or none if no kind fits
- one line on what makes it worth writing, naming the specific pages that
  suggested it

**Work through the kinds to find them.** "Propose angles" on its own has no
structure, and the view's own output lines up with the kinds well enough to be
read that way — each row below says where in the view to look:

| Look at | Suggests |
|---|---|
| A `TYPE:` holding a handful of pages of one type | `comparison` — put them side by side and draw out the differences |
| A `TAG:` recurring across many pages | `pattern` — a shape repeating often enough to describe |
| A `HUB:` with many backlinks, or a type barely touched | `landscape` — the entry point into an area |
| Several `Event` pages, or pages whose headings carry dates | `timeline` |
| One `##` heading repeating across pages about one thing | `practice` (several accounts of the same thing) or `debate` (the same question answered differently) |

This is a way in, not a rule: an angle the view supports but no row above
predicted is still worth proposing. Propose only angles the view actually
supports — one no page in the list speaks to would send Step 2 into a search
that returns nothing, and Step 5, grounded solely in what Step 4 fetched, has no
way to write it.

#### 0.3 Let the person choose

Present the numbered list and ask which to write about. They can also type a
topic of their own, in which case use that verbatim.

If the answer is not a choice — no answer arrives, or nothing appeals — stop
here without writing anything, and say the wiki was left untouched. Do not pick
one on your own: this Skill writes primary wiki content, and the whole point of
this step is that the person, not the model, decides what the wiki gets. If this
Skill was invoked without anyone there to answer, stopping is the correct
outcome; re-run it with an explicit `<topic>` to skip the survey. Close the run
record on the way out (`python .wikicommit/scripts/record_run.py end <the path
printed at the start>`): this is a run that finished, and since a non-interactive
argumentless invocation always lands here, leaving it open would report every one
of them as a run that did not finish (Issue #790).

Rejected angles are not recorded anywhere. The view is rebuilt from the wiki on
every run, so any angle still supported by the wiki can be proposed again;
writing down the ones that were passed over would only create the false promise
that they are queued for later (the same reasoning `wikicommit-generate` Pass 2b
applies to type candidates it declines).

The chosen phrase becomes `<topic>`, and the kind proposed alongside it is
carried to Step 5 as this page's `kind` (the person may say a different one, or
none). Continue at Step 1 — no other step changes. Because `<topic>` reaches
Step 2 as ordinary free-form text, it goes through the same quote-delimited
heredocs every search term already uses there.

### Step 1: Determine Target Languages

Read `.wikicommit/config.yml` and get `translation.primary_lang` and `translation.targets`. If `.wikicommit/config.yml` doesn't exist, display an error, guide the user to run `/wikicommit-init`, and stop.

Have the LLM determine the language of `<topic>`.

Build the list of languages to search, in the following order, **deduplicating any repeated language** (to avoid searching the same language twice):

1. The language of `<topic>`
2. `primary_lang`
3. Each language in `targets`

### Step 2: Cross-Lingual Search

For each language determined in step 1, **run sequentially, one language at a time** (do not run in parallel — `search_index.py query` automatically runs `build` (`DROP` + full rebuild) when the cache hasn't been generated yet, so calling it for multiple languages in parallel can race on that "cache not yet built" check, causing a double build or a SQLite lock-contention error):

1. Split `<topic>` into the distinct keywords it names, and translate each into that language (the LLM translates on the fly each time — no dedicated translation API or library is used). If the target language matches `<topic>`'s language, skip translation and use them as-is.
2. **Expand each keyword into a group of alternative wordings** (Issue #581). Translating still leaves the topic phrased one particular way, and FTS5 matches literal text: if the wiki writes `児童手当` where the keyword says `子ども手当`, the search returns nothing even though the wiki covers it. Vector search is the usual answer to that and is deferred; expanding with the LLM's own vocabulary knowledge is the lightweight stand-in, and it is the same move this Skill already makes across languages. Each keyword (in this language) plus its expansions becomes one `--expand` group. This is an internal step — do not report the expansions to the user.

   **Expansion rules.** trigram search matches *substrings*, so inflected forms and longer compounds containing the term (`エンジニア` → `ソフトウェアエンジニア`) are already reached for free; spending expansion slots there only adds noise. Expand only where the vocabulary genuinely differs:

   - **Expand**: synonyms (`児童手当` / `子ども手当`), hypernyms and general terms (`Claude Code` / `AIコーディングツール`), abbreviation–full-form pairs (`LLM` / `大規模言語モデル`), cross-language equivalents (`vibe coding` / `バイブコーディング`), orthographic variants (`サーバ` / `サーバー`).
   - **Do not expand**: inflected forms and word endings, compounds already reachable as a substring, or merely related terms whose meaning sits somewhere else (a term that "gets discussed alongside" the original is not a synonym).
   - **Limits**: at most 2–3 expansions per original term, and roughly 5 expanded terms across the whole search. Left unbounded this widens without end.
   - **Never produce an expansion shorter than 3 characters** — the trigram tokenizer cannot form a token from it, so it can never match (Issue #274).

3. Run, passing one `--expand` per keyword group, each group's terms joined by `|`:

```bash
python .wikicommit/scripts/search_index.py query \
  --expand "$(cat <<'EOF'
<keyword 1 in this language>|<expansion>|<expansion>
EOF
)" \
  --expand "$(cat <<'EOF'
<keyword 2 in this language>|<expansion>
EOF
)" --lang <lang> --limit 5
```

Terms inside a group are OR-ed and the groups are AND-ed, which is why the expansions have to be grouped rather than appended to a single query string: FTS5 AND-s adjacent phrases, so appending a synonym would demand that a page contain every wording at once and would drop the very hit the expansion was meant to reach.

Pass every term through a quote-delimited heredoc, not a plain double-quote embedding. These terms are LLM-produced but derive from `<topic>`, which is unvalidated free-form user text — a plain `"<term>"` embedding would let shell metacharacters (`` ` ``, `$(...)`) surviving translation be evaluated by the shell when this command line is assembled, regardless of the downstream script being local and read-only (Issue #398).

On exit code `1` (failure, with an `ERROR:` line printed), display that error message as-is to the user and stop.

Collect the `MATCH:` lines (`path` / `title` / `type` / `lang` / `review_status`) and the `SUMMARY:` line (`hits`) from each language's query results. A `WARNING: expand group "<a>|<b>" has no term of at least 3 character(s); ...` line means every wording of that keyword was too short for the trigram tokenizer to ever match (Issue #274) and the keyword was dropped, widening the search. A `WARNING: no usable --expand term remains; ...` line means that happened to *every* keyword, so that language's search ran with no terms at all and its `hits=0` says nothing about the wiki's coverage — treat that language as "not searched" rather than "nothing there". The `WARNING: expand term ... its group still matches via: ...` form needs no action, since the keyword survived through a longer wording.

### Step 3: Merge Results

1. Combine the hits from all languages into a single list.
2. If multiple language versions of the same page (linked via `translated_from`) both show up as hits (i.e. two or more hits share the same `type` and `slug`), narrow it down to one. Priority order: "same language as `<topic>`" > "`primary_lang`" > "the order listed in `targets`".
3. **Drop every hit that is itself a synthesized page** (Issue #674) — one under `.wikicommit/view/`, or one in `.wikicommit/entity/` whose frontmatter carries `derived_from` (a synthesis written before the view tree existed stays where it is; old and new coexist rather than being migrated). The path test needs no file read; the frontmatter test below is for the entity tree. `search_index.py`'s `MATCH:` lines do not carry that field, so check the candidates directly. **Skip this item entirely when items 1–2 left no candidates** and go straight to item 5: `grep` with no file operands reads standard input and hangs, the same "do not invoke it with no paths" hazard `/wikicommit-merge` Step 3 spells out for its per-file checks.

   ```bash
   grep -l "^derived_from:" "<candidate path>" "<candidate path>" ...
   ```

   Quote every path. A page's slug is not a validated identifier, and an unquoted path holding a space or a glob metacharacter is split or expanded, so grep checks files that do not exist and reports nothing for the real page — leaving a synthesized page in the grounding set. Exit code `1` here means "no candidate is synthesized" and is the normal result; only exit code `2` is a failure.

   **Then confirm each path grep prints by reading its frontmatter**, the same check Step 9 item 2 makes. grep sees the whole file, so a page that merely quotes a `derived_from:` line in its *body* — a YAML example on a page about the wiki's own schema — matches without being synthesized at all, and dropping it would discard ordinary primary content. Exclude only the paths where `derived_from` is a real frontmatter field.

   Every path left after that confirmation is excluded from the grounding set. This keeps **a synthesized page at most one step above ordinary pages**, and two things depend on that: `check_derivation_freshness.py` compares each `derived_from` entry's `source_commit` against that page's current commit, so a synthesis of a synthesis would only register staleness once the middle page is itself regenerated *and committed* — a change to the original would not propagate; and step 5.5's review always lands on pages that carry `sources`, so a claim can be traced to an external document in at most two hops.

   **This is a filter on the grounding set, not on the index.** Synthesized pages stay searchable — `/wikicommit-search` and `/wikicommit-ask` must still find them, and a reader looking for the topic should reach the page written about it. Do not exclude them from `search_index.py`.

4. Sort the remaining hits roughly by the bm25 order returned by `search_index.py` (already ranked per-language) and select the top 5–10. A naive cross-language score comparison is acceptable as an approximation.
5. If there are zero hits across all languages combined — or every hit was dropped by item 3 — display "No pages related to \"<topic>\" were found" and stop (do not run the remaining steps), closing the run record first with `python .wikicommit/scripts/record_run.py end <the path printed at the start>` — the search ran and answered, so this is a finished run rather than one that died partway (Issue #790).

### Step 4: Fetch Page Content

Read each selected page with the Read tool and add its body (excluding frontmatter) to the LLM's context. Keep the list of selected page paths — this is the grounding set used for `derived_from` in Step 10.

**Say which grounding pages are unreviewed, before writing anything** (Issue #674). Take each page's `review_status` from the frontmatter you just read, **not** from step 2's `MATCH:` line: `search_index.py` rebuilds its cache only when the database file is missing and never checks whether it is stale, so an index built before a page was reset to `pending` (`/wikicommit-generate --regenerate` does exactly that) still reports it as reviewed and the warning is skipped in the one case it exists for. If any selected page is `pending`, list those paths now, in the same words `/wikicommit-ask` uses when its answer rests on pages nobody has read yet (Issue #740 — `pending` states that the page has not reached a person, not that no check ran on it):

```
⚠️ This synthesis is grounded on pages nobody has read yet: .wikicommit/entity/ja/Person/yamada-taro.md
```

This is a warning, not a gate — do not stop, and do not ask for confirmation. A wiki whose pages are all `pending` is the normal state right after a batch of generation, and refusing to synthesize there would make the Skill unusable exactly when it is most useful. What the warning buys is that "unreviewed pages went in, and an unreviewed page came out" is stated rather than silent: the output carries `review_status: pending` either way, which on its own does not distinguish a page built on reviewed material from one built on none.

### Step 5: Generate the Summary

Generate a summary document about `<topic>`, grounded only in the body content injected in step 4. **Do not include claims in the document that aren't in a grounding page's body content** (hallucination prevention). Step 5.5 then checks that with a review subagent, the way `wikicommit-generate` Pass 4 checks a generated page against its source documents — writing the instruction here and verifying it there are two different things, and for a long stretch only the first existed (Issue #674).

Structure the document with sections (`##` and deeper), and include reference links to related pages (in `[[Type/slug]]` form) within the body. Do not append a "Referenced Pages" list to the body — the grounding set is instead recorded in the `derived_from` frontmatter field (Step 10), so listing it again in the body would be redundant.

#### Choose a `kind`

A view page's `kind` says what it does with several pages at once — a different
question from what it is about, which is why it is not a Schema.org type
(Issue #675). Pick the one that matches, or **none**: `kind` is optional, and
forcing a page into a kind whose Boundary it then breaks is worse than leaving
it off. Pages piling up without a kind is the signal that a kind is missing, so
leaving it off is a real answer, not a failure.

| kind | What the page does | Boundary — what it must not do |
|---|---|---|
| `practice` | Sets several accounts of one practice against each other: when it applies, what it assumes, how it fails, what kind of evidence stands behind it | **Never write normative advice.** Report what the grounding pages record about a practice; do not tell the reader to adopt it. An invented insight costs more than an absent one |
| `landscape` | Maps an area and points at its hubs and main pages, as a way in | Make no new claim, and **write no counts**. The overview page recomputes totals, reviewed ratios, per-type tallies and gaps on every build; a number written into prose here is wrong by tomorrow with nothing to catch it. Link there instead |
| `comparison` | Puts a few entities of the same kind side by side and draws out where they differ | Do not rank them or declare one better. Differences, not verdicts |
| `pattern` | Describes a shape that recurs across many pages | **Always give the count and name the pages.** A pattern with no cases behind it is an assertion |
| `timeline` | Orders events drawn from several pages along time | Leave each event's detail on its own `Event` page; this page carries the ordering |
| `debate` | Lays out how one question is answered differently, and what backs each answer | Reach no conclusion. Where the grounding pages disagree, that disagreement is the content |

Write the body to fit the chosen kind, and keep inside its Boundary — Step 5.5
checks the Boundary as well as the grounding.

**Do not open the body with an H1 (`# <topic>`), or any other top-level title line** (Issue #546). The page's title lives in the `title` frontmatter field (Step 10) and Quartz renders that as the page heading, so a body H1 duplicates it on the published page. Every schema template's body starts with a paragraph or a `##` heading, which is why `/wikicommit-generate` and `/wikicommit-translate` never produce one — this Skill is the only one that builds a body without going through a template, so it is the only place the convention has to be stated outright.

### Step 5.5: Grounding Integrity Review (Review Subagent)

Of the three ways a page gets written, this was the only one with no check on the result: `/wikicommit-generate` reconciles a page against its source documents (Pass 4) and `/wikicommit-translate` checks a translation against its original, while this Skill had only the one instruction in step 5 (Issue #674). It is also the path that needs a check most — a synthesized page carries `derived_from` and no `sources`, so a reader's only route to the underlying evidence runs through the grounding pages. If the synthesis misreads them, nothing downstream catches it.

**The review discipline is not in this file (Issue #752).** It lives in `.wikicommit/review-rules.md`, shared with `wikicommit-generate` Pass 4 and `wikicommit-review` — one copy instead of three that had already drifted apart. What stays here is the choreography, and the fact that `MISSING_SOURCE` means something different on this path is stated there, under this path's own section.

**If `.wikicommit/review-rules.md` does not exist, stop and say so.** Do not review without it and do not fall back to a looser check: without those rules this step degrades to a bare "is this supported" pass while still writing a record that a review happened, and its output looks normal. Tell the user to run `/wikicommit-init --no-overwrite`. This is an installation problem, not a defect in the page — nothing about it belongs in a record of this page. **Check for the file at the start of the run, not when this step is reached**: its absence is knowable before Step 1 and does not depend on the topic, so finding out here would discard the whole grounding search and body generation that was never going to be reviewable.

1. Launch a subagent and give it exactly these four things, and nothing else:

   1. **The path label `synthesize-step5.5`**, stated as the path this review is running on. The rules file scopes several checks by path ("a check that does not name your path is not yours to run") and has a section per path — including the one that says `MISSING_SOURCE` means something different here — so a subagent left to guess which one it is on may run the cited-document check that does not apply here, or miss the Boundary check that only applies here.
   2. **The generated body from step 5.**
   3. **The full body of each grounding page from step 4**, each wrapped in a block marked `SOURCE`.
   4. **`.wikicommit/review-rules.md`**, with an instruction to follow it, plus the page's chosen `kind` and the one Boundary line for it from Step 5's table.

   **Do not include anything else** — not your reasoning for how the synthesis was assembled, not the search results that selected the grounding set, and not a previous round's findings. You are the agent that wrote this page, and handing over your own reading of the grounding makes the review agree with you exactly where that reading was wrong.

   Pass each grounding page's **full body**, not the passages you drew on. Showing the reviewer only the text you wrote from biases it toward PASS by construction.

2. **Check that the returned JSON carries `rules_version` matching `.wikicommit/review-rules.md`'s frontmatter.** A missing or mismatched value means the subagent did not read the rules, so its verdict says nothing about the checks they define. Relaunch **once**; if the second attempt is also missing or wrong, **stop and report it** — close the run record with `record_run.py end <path> --halted-reason "rules_version mismatch"` on the way out (Issue #790: this stops without writing the page, so nothing else records that the run happened) — do not consume `generate.max_retries` and do not record it as a review of this page. This is a problem with the instructions or the environment, not with the synthesis.

3. **Grounding pages that disagree with each other are reported, not failed.** The rules file has the subagent set `page_at_fault: "other"` on those entries and keep `result` at `"PASS"` when they are the only kind of defect found; carry the pairs to step 12 and report them there. Failing instead would be a trap with no exit — this Skill cannot edit a grounding page, so every retry would produce a correct synthesis, draw the identical unfixable finding, and end at item 5 with the page discarded.

4. On **FAIL**, regenerate the body by re-running step 5 — up to `generate.max_retries` times from `.wikicommit/config.yml` (default: 2). The same key `/wikicommit-generate` uses; there is no separate setting for this Skill, because it would mean the same thing.

   **Pass the findings into the retry.** Feed the full `issues` array — above all each entry's `instruction` — into the regeneration prompt as explicit, itemized corrections for this attempt, alongside the same grounding bodies step 5 had. Do not retry from a bare "the previous attempt failed review": two consecutive FAILs for the same underlying defect is precisely what that produces, since the retry never saw what was wrong with the attempt before it. Leave out the `page_at_fault: "other"` entries — regenerating cannot fix them, and feeding them in as corrections would push the synthesis away from what the grounding pages actually say.

5. **If the retry limit is exceeded, write nothing and stop**, reporting what still failed (the last `issues` array, in the user's own terms) and which grounding pages were involved. There is no partial success to record: this Skill writes one page per run, and unlike `/wikicommit-generate` it has no source management file in which to leave a `failed_pages` entry — a synthesized page has no management file at all, and `/wikicommit-merge`'s generation-failure tracking scans `.wikicommit/source/`, which this run never touches. Stopping and saying so loses nothing, because there is nowhere else the information would have gone.

   The Skill's **Step 6 onward** do not run. Nothing has been written to disk at this point, so there is nothing to clean up. This does not exempt item 6 of *this* step, which is the record of exactly this outcome — the run that wrote no page is the one whose verdict nothing else survives to describe.

6. **Record the verdict either way (Issue #750).** Run this after the page is written (step 9) when the review passed, and immediately after item 5 when it did not — the failing case is the one worth recording most, since nothing else survives a run that wrote no page:

   ```bash
   python .wikicommit/scripts/record_review.py "$(cat <<'EOF'
   <the view page path, .wikicommit/view/<lang>/<slug>.md>
   EOF
   )" --kind ai --stage synthesize-step5.5 \
     --model "<the model ID this run's runtime reports for itself>" \
     --skill-blob "$(git hash-object .wikicommit/review-rules.md)" \
     --attempts <how many review rounds this took> --result <pass|discarded> --json - <<'JSON'
   <the review subagent's JSON, with every round's issues merged into one `issues`
    array and each entry carrying the `round` it was raised in>
   JSON
   ```

   `--result discarded` is the retry-limit case from item 5: the page was never written, and the script records an empty `page_content_hash` to say so. On a pass, `reviewed_sources` is read from the page's own `derived_from` — the grounding pages and the commits they were read at — which is the same slot an entity page's `sources` occupies, and for the same purpose: the evidence versions this verdict was made against.

   Merge every round's findings into the one array rather than keeping only the last. A synthesis that breached its `kind`'s Boundary on the first attempt and was corrected on the second would otherwise record nothing at all, and that is precisely the drift this Skill's own review exists to catch.

   The `page_at_fault: "other"` entries go in as well. They never made this a FAIL, but they are the only durable trace that two grounding pages disagree — item 3 reports them to the user once and the run then ends.

### Step 6: Determine the New Page's Language

Set `lang` to `.wikicommit/config.yml`'s `primary_lang` (read in Step 1) — regardless of which language(s) were searched in Step 2. This mirrors `wikicommit-generate` Pass 2's rule: the topic may be looked up in multiple languages, but a newly created page's own language is always the wiki's source language.

There is no type-selection step. A view page has no `type:` at all (Issue #675) — which also removes the failure that step used to produce: the same topic once resolved to `custom/Practice` on one run and `Practice` on the next, putting the page somewhere no WikiLink could reach (Issue #545). A view page's location is decided entirely by its language and its slug, so two runs on one topic land in the same place.

### Step 7: Generate the topic-slug

Generate a language-neutral English slug from `<topic>` (same convention as WikiLink filenames: a lowercase, hyphen-separated English identifier). For a non-English `<topic>` (e.g. Japanese), have the LLM translate it to English first, then slugify it. Example: "機械学習パイプライン" → `machine-learning-pipeline`.

### Step 8: Safety Check Before Writing

The target path is `.wikicommit/view/<lang>/<slug>.md` (from Steps 6–7). If the file already exists, confirm with the user whether it is okay to overwrite; if declined, stop.

The check is this short because the view tree holds nothing but this Skill's output — an existing file there is a previous synthesis, and there is no way to land on primary content by accident. That was the risk when synthesized pages were written into `.wikicommit/entity/` alongside everything else, and the reason for the branch that used to be here.

If the file doesn't exist, proceed directly — create the parent `.wikicommit/view/<lang>/` directory automatically if needed.

### Step 9: Write the File

Write frontmatter with:

- `title`: `<topic>` (or its English-translated form used for the slug, whichever reads better as a title in `lang`)
- `lang`: from Step 6
- `kind`: from Step 5, **omitted entirely when no kind fits** (do not write an empty value — `validate_frontmatter.py` accepts only one of the six kinds or no field at all)
- `review_status: pending` (unconditionally — same rule as `wikicommit-generate`/`wikicommit-translate` output)
- `generated_at`: today's date (`YYYY-MM-DD`)
- `generated_by`: the LLM model identifier
- `generated_with`: WikiCommit's own version, not a model ID — read it with `python .wikicommit/scripts/_version.py` and write that exact string (Issue #577; the same stamp `wikicommit-generate` Pass 3 writes). It is what lets a human — reading `CHANGELOG.md` alongside a `grep` for this field — tell which pages were produced under an older set of rules. If that script is missing (a wiki repository initialized before this field existed), omit the field entirely rather than guessing a version — its absence is meaningful, and no back-fill is performed.
- `derived_from`: one entry per grounding page from Step 4, in the form:

  ```yaml
  derived_from:
    - path: .wikicommit/entity/ja/Person/yamada-taro.md
      source_commit: abc123def456abc123def456abc123def456abc123de
    - path: .wikicommit/entity/ja/Organization/companya.md
      source_commit: def456abc123def456abc123def456abc123def456ab
  ```

  Get each `source_commit` with `git log -1 --format=%H -- <path>`. If a grounding page has no commit history yet (newly generated, not yet committed), this command succeeds with empty output — write `source_commit` as an empty string in that case (`check_derivation_freshness.py` will correctly report it as `STALE` until the page is committed, which is expected, same as the equivalent `wikicommit-translate` behavior).

Do **not** write a `type:` or a `sources:` field. `validate_frontmatter.py` reports either one on a page in this tree as an ERROR: the first because a view page has no Schema.org type, the second because `derived_from` is this page's provenance record — the same way `translated_from` is for a translation page.

Write the frontmatter + body (from Step 5) to `.wikicommit/view/<lang>/<slug>.md` with the Write tool.

**Relative links in the body** (images, attachments) are written **as they will appear on the published site**: `../../assets/<name>`, exactly what an entity page writes, because `content/<lang>/View/` sits at the same depth as `content/<lang>/<Type>/`. `convert_wikilinks.py` deliberately leaves a view page's relative targets alone for this reason. WikiLinks (`[[Type/slug]]`, and `[[View/<slug>]]` for another view page) are unaffected — they carry no path.

### Step 10: Update the View Index

The page just written is not in its language's view index yet. Rebuild that one index:

```bash
python .wikicommit/scripts/rebuild_index.py "$(cat <<'EOF'
.wikicommit/view/<lang>
EOF
)"
```

Given a directory in the view tree, `rebuild_index.py` writes a per-language index listing `[[View/<slug>]]` rather than a per-Type one (Issue #675). It rescans from disk, excludes `status: removed` pages, and is idempotent — an index that is already correct comes out byte-identical. This is a local write only — **do not commit** (`/wikicommit-merge` picks it up with the page).

Do not skip this because the page is only one file. A view page has no source of its own (only `derived_from`), so no `/wikicommit-generate` run is scheduled to pick it up — in a wiki where nothing else is being ingested there is no later run to wait for. The page is also unlinked at birth, so without its index entry it is reachable only by direct URL (Issue #547).

**Why one directory and not the whole tree**: `/wikicommit-generate` and `/wikicommit-translate` call `rebuild_index.py` with no arguments, and say why — over a long multi-source batch, tracking which directories were touched is what gets forgotten at the tail end. That reasoning does not carry here: this Skill writes exactly one page, whose `<lang>` Step 6 already determined. Passing it keeps this Skill's stated side effect narrow (it is a conversational Skill, and a tree-wide rebuild can drop unrelated `index.md` diffs into the working tree that the user then has to account for before merging).

### Step 11: Guidance

Close the run record first, so its elapsed time covers the whole run:

```bash
python .wikicommit/scripts/record_run.py end <the path printed at the start> \
    --page <the view page written> --outcome synthesized=1
```

Then tell the user, including that path and its elapsed time — the record is not committed, so this run's own output is the only place a reader sees them:

```
Written to .wikicommit/view/<lang>/<slug>.md, and rebuilt .wikicommit/view/<lang>/index.md so the page appears in the view index.
This page is grounded in other wiki pages rather than in an outside document, which is what the separate location records. It is subject to the quality gate and can be committed via /wikicommit-merge like any other page (review_status: pending, so it will get a tracking issue after merge).
```

Add one line for the grounding review, whatever its outcome (Issue #750) — the denominator is 1 here, but the reason for printing it is the same as in `/wikicommit-generate`: without it, a run in which the review found nothing and a run in which it did not happen read identically:

```
Reviewed 1 page against its grounding pages: 0 finding(s) raised.
  → record in .wikicommit/review/
```

If the review in step 5.5 reported grounding pages that disagree with each other (`page_at_fault: "other"`), list those pairs here — both page paths, the fact, and each page's version of it (step 5.5 item 3 says where in the entry each half lives: one page in `source_file`/`source_quote`, the counterpart in `claim`). Nothing else surfaces them: they are not a defect in the page just written, so they neither failed the review nor appear anywhere in the file. Say plainly that the page just written is not the thing to fix and that the disagreement is between the two pages named.

If step 4 warned that some grounding pages are unreviewed, repeat that here as well. Between the warning and this point the person has read a whole document, and this is where they decide what to do with it.

## Notes

- Do not commit or create a PR against `main` or any branch (that is `wikicommit-merge`'s responsibility)
- Survey mode (Step 0) writes nothing. Its only command is a read-only script, and a run that ends without a topic being chosen leaves the wiki exactly as it was
- Do not write to `.wikicommit/schema/` (read-only)
- Do not include claims in the document that aren't in a grounding page's body content (hallucination prevention; written in Step 5, verified in Step 5.5)
- Do not write a `type:` on a view page, and do not invent a `kind` outside the six in Step 5's table. Both are ERRORs at the quality gate. No kind at all is a valid answer
- The grounding set never includes a page that is itself synthesized (one carrying `derived_from`), so a view page always sits at most one step above ordinary pages (Step 3 item 3). With the view tree that rule also has a location: **no page under `.wikicommit/view/` is ever grounding material**. View pages stay in the search index — the exclusion is on the grounding set only
- This Skill's side effects are confined to two local writes under `.wikicommit/view/`: the view page itself (Step 9) and its language's `index.md` (Step 10). It never writes to `.wikicommit/entity/`. `search_index.py` automatically runs `build` if the index file (`.wikicommit/.cache/search_index.sqlite3`, not tracked by Git) doesn't exist
- A grounding page's own `review_status: pending` **is** surfaced, in the same words `wikicommit-ask` uses (Step 4, repeated in Step 12). It warns and does not block: a wiki fresh out of a generation batch is entirely `pending`, and gating there would disable the Skill exactly when it is most useful (Issue #674 — this was left unresolved when the Skill was introduced)
