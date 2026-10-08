---
pass_token: "5bdb5391"
---

# Steps 1–4: choose and read the grounding pages (`ground`)

**The topic** is the run's argument — every entry of the run record's `args` that is not an option (`--max-grounding` and its value are) — or, in survey mode, the last entry of the run record's `workflow.lists.topic`. Read it from the run record (the `run` path), not from memory. In survey mode the angle's pages named at Step 0.2 are candidates too; if they are no longer in front of you (a resumed run), go on without them.

Report one outcome when this step is done:

- `grounded` — the grounding pages were chosen (Step 3) and read in full (Step 4). Pass each one, in order, as its own `--add grounding=<path>`. The workflow engine's check confirms that every one is a live page under `.wikicommit/entity/<primary_lang>/`, carries neither `translated_from` nor `derived_from`, and that there are no more of them than the cap `N`.
- `halted` with `--reason "<the ERROR: line>"` — the search failed (Step 2). The run stops.
- `nothing` — no page survives Step 3; say "No pages related to \"<topic>\" were found". The workflow engine closes the run as finished — the search ran and answered, so this is a finished run rather than one that died partway.

```bash
python .wikicommit/scripts/skill_workflow.py done <run> --step ground --outcome <grounded|nothing|halted> \
    --token 5bdb5391 [--add "grounding=<path>" ...] [--reason "<why>"]
```

Quote every path — a slug is not a validated identifier.

## Step 1: Determine the Search Language

Read `.wikicommit/config.yml` and get `translation.primary_lang` (the workflow engine's `preflight` step already confirmed the file exists).

**Search `primary_lang` only.** Every original page is written in `primary_lang` — `/wikicommit-generate` writes in it whatever the source's language, and a page in any other language is a translation made by `/wikicommit-translate`, carrying `translated_from`. Searching the `targets` languages therefore finds only translations of pages the `primary_lang` search already reaches, and adds no evidence. Worse, a translation chosen as grounding makes this page a translation of a translation, can be older than its original, and hides a later change to the original from `check_derivation_freshness.py` (which watches the translation named in `derived_from`, not the original behind it). Differences in wording are bridged by the expansions in Step 2, not by searching other languages.

Settle the grounding cap **`N`** now: the last entry of the run record's `workflow.lists.max_grounding` if the person named one at the survey, otherwise the `--max-grounding` argument, otherwise **30**. It is one number whatever the `kind` — how many pages a page needs depends on its subject, not on its kind (a `comparison` of seventeen tools needs more than one of three). There is no "unlimited" value; pass a large number instead.

## Step 2: Search

1. Split `<topic>` into the distinct keywords it names, and translate each into `primary_lang` if `<topic>` is written in another language (the LLM translates on the fly — no dedicated translation API or library is used).
2. **Expand each keyword into a group of alternative wordings**. FTS5 matches literal text: if the wiki writes `児童手当` where the keyword says `子ども手当`, the search returns nothing even though the wiki covers it. Each keyword plus its expansions becomes one `--expand` group. This is an internal step — do not report the expansions to the user.

   **Expansion rules.** trigram search matches *substrings*, so inflected forms and longer compounds containing the term (`エンジニア` → `ソフトウェアエンジニア`) are already reached for free; spending expansion slots there only adds noise. Expand only where the vocabulary genuinely differs:

   - **Expand**: synonyms (`児童手当` / `子ども手当`), hypernyms and general terms (`Claude Code` / `AIコーディングツール`), abbreviation–full-form pairs (`LLM` / `大規模言語モデル`), terms borrowed from another language (`vibe coding` / `バイブコーディング`), orthographic variants (`サーバ` / `サーバー`).
   - **Do not expand**: inflected forms and word endings, compounds already reachable as a substring, or merely related terms whose meaning sits somewhere else (a term that "gets discussed alongside" the original is not a synonym).
   - **Limits**: at most 2–3 expansions per original term, and roughly 5 expanded terms across the whole search. Left unbounded this widens without end.
   - **Never produce an expansion shorter than 3 characters** — the trigram tokenizer cannot form a token from it, so it can never match.

3. Run, passing one `--expand` per keyword group, each group's terms joined by `|`, with `--limit` set to the larger of 40 and `N` — the search only gathers candidates, and a fixed limit would make a raised `N` ineffective:

```bash
python .wikicommit/scripts/search_index.py query \
  --expand "$(cat <<'EOF'
<keyword 1>|<expansion>|<expansion>
EOF
)" \
  --expand "$(cat <<'EOF'
<keyword 2>|<expansion>
EOF
)" --lang <primary_lang> --limit <max(40, N)>
```

Terms inside a group are OR-ed and the groups are AND-ed, which is why the expansions have to be grouped rather than appended to a single query string: FTS5 AND-s adjacent phrases, so appending a synonym would demand that a page contain every wording at once and would drop the very hit the expansion was meant to reach.

Pass every term through a quote-delimited heredoc, not a plain double-quote embedding. These terms are LLM-produced but derive from `<topic>`, which is unvalidated free-form user text — a plain `"<term>"` embedding would let shell metacharacters (`` ` ``, `$(...)`) surviving translation be evaluated by the shell when this command line is assembled, regardless of the downstream script being local and read-only.

On exit code `1` (failure, with an `ERROR:` line printed), display that error message as-is to the user and report `halted` with `--reason` set to that message. Do not report `nothing`: the search did not run, so it has not answered whether the wiki covers the topic.

Collect the `MATCH:` lines (`path` / `title` / `type` / `lang` / `review_status`), in the bm25 order they came in, and the `SUMMARY:` line (`hits`). A `WARNING: expand group "<a>|<b>" has no term of at least 3 character(s); ...` line means every wording of that keyword was too short for the trigram tokenizer to ever match and the keyword was dropped, widening the search. A `WARNING: no usable --expand term remains; ...` line means that happened to *every* keyword, so the search ran with no terms at all and its `hits=0` says nothing about the wiki's coverage — say so rather than reporting that the wiki has nothing on the topic. The `WARNING: expand term ... its group still matches via: ...` form needs no action, since the keyword survived through a longer wording.

## Step 3: Choose the Grounding Set Before Reading Any Body

Every page chosen here is read in full twice — by you in Step 4 and by the review subagent in Step 5.5 — and becomes one `derived_from` line. So choose on the cheap part of each page first, and read bodies only for the pages chosen.

1. **Candidates** are the search hits from Step 2, in their bm25 order, followed by any page Step 0.2 named as the source of the chosen angle that the search did not return (in survey mode only). A named page gets no free pass: it goes through items 2–3 like any other. Step 0.2 names pages by the `Type/slug` key the survey prints, not by path — turn each into `.wikicommit/entity/<primary_lang>/<Type/slug>.md` (the survey lists `primary_lang` only) before passing it on; a bare key is not a path and comes back as `MISSING:`. **If there are no candidates at all, skip item 2 and go straight to item 6.**
2. **Reduce every candidate to its title, description and headings** with one call, passing the paths in candidate order:

   ```bash
   python .wikicommit/scripts/build_survey_view.py --pages "<candidate path>" "<candidate path>" ...
   ```

   Quote every path — a slug is not a validated identifier, and an unquoted path holding a space or a glob metacharacter is split or expanded. Each `PAGE:` line carries `path=`, and ends in `translation` and/or `synthesized` when the page is one; a `MISSING:` line names a candidate that is not a live page (removed, or gone since the index was built) — drop it. The flags come from the frontmatter, so a page that merely quotes a `derived_from:` line in its body is not mistaken for a synthesis.

   **Drop every page marked `translation`.** It restates an original in another language (Step 1 says why an original is always the better grounding).

   **Drop every page marked `synthesized`** — a view page, or an entity page carrying `derived_from` (a synthesis written before the view tree existed stays where it is). This keeps **a synthesized page at most one step above ordinary pages**, and two things depend on that: `check_derivation_freshness.py` compares each `derived_from` entry's `source_commit` against that page's current commit, so a synthesis of a synthesis would only register staleness once the middle page is itself regenerated *and committed* — a change to the original would not propagate; and step 5.5's review always lands on pages that carry `sources`, so a claim can be traced to an external document in at most two hops. **This is a filter on the grounding set, not on the index.** Synthesized pages stay searchable — `/wikicommit-search` and `/wikicommit-ask` must still find them. Do not exclude them from `search_index.py`.

3. **Keep only the pages that treat `<topic>` as their subject.** Judge from the title, `DESC:` and `HEADINGS:` lines — not from the body, which is what this step exists to avoid reading. A page whose title or main subject is the topic, or one of its parts, stays; a page that only mentions the topic in passing while being about something else goes. This is the same subject test the review rules apply (a source that treats a fact as its own subject, against one that mentions it on the way to something else), so no new standard is introduced here. **When you cannot tell, drop the page**: an over-broad grounding set makes the review more likely to find a similar sentence somewhere and pass a claim, while a smaller one only makes the page more modest.
4. **Cap at `N`**, keeping the kept pages in their Step 2 order (named pages from Step 0.2 that the search did not return come after the hits). Remember `M`, the number kept by item 3, and the paths of any pages the cap cut.
5. **Say what was chosen before reading anything**: `Grounding: <N'> of the <M> pages that treat "<topic>" as their subject` (with `N'` = `min(M, N)`). When the cap cut pages, list them, and say that re-running with `--max-grounding <larger N>` would include them. The completion report repeats this.
6. If no page survives items 2–3, report `nothing`.

## Step 4: Fetch Page Content

Read each selected page in full and add its body (excluding frontmatter) to the LLM's context. The list of selected page paths is the grounding set, recorded in `derived_from` by the `write` step — which is why each goes to the workflow engine as `--add grounding=<path>`.

If `--max-grounding` was raised far enough that the selected set runs to around a hundred pages, say before reading that this many full bodies will crowd the context (and the review subagent's, which receives them all again). Do not stop — the number was chosen on purpose.

**Say which grounding pages are unreviewed, before writing anything**. Take each page's `review_status` from the frontmatter you just read, **not** from step 2's `MATCH:` line: the page itself is the source of truth, and reading it rules out even a sub-second race between the index and a page rewritten after it was built. If any selected page is `pending`, list those paths now, in the same words `/wikicommit-ask` uses when its answer rests on pages nobody has read yet (`pending` states that the page has not reached a person, not that no check ran on it):

```
⚠️ This synthesis is grounded on pages nobody has read yet: .wikicommit/entity/ja/Person/yamada-taro.md
```

This is a warning, not a gate — do not stop, and do not ask for confirmation. A wiki whose pages are all `pending` is the normal state right after a batch of generation, and refusing to synthesize there would make the Skill unusable exactly when it is most useful. What the warning buys is that "unreviewed pages went in, and an unreviewed page came out" is stated rather than silent: the output carries `review_status: pending` either way, which on its own does not distinguish a page built on reviewed material from one built on none.

The bodies you read here are what the `write` step synthesizes from. If the run resumes at `write` in a new session, read the pages in the run record's `workflow.lists.grounding` again before writing.
