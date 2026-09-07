# Changelog

A record of changes to WikiCommit itself — the Skills and the template tree they expand.

The distribution repository (`wikicommit/wikicommit`) carries no development history: it
is a stack of single sync commits, so `git log` shows the same commit every time. That
makes this file the only way a user can learn what changed since the version they last
installed.

It is also what a person reads to decide whether existing wiki pages should be
regenerated. `grep`ing a page's `generated_with` lists the pages built by an older
version, but a version is coarser than a type — bumping the version after changing a
single type template makes every page look equally old. The prose here is what fills
that gap; the two only work as a pair. **In any version that changes a type template
(`.wikicommit/schema/<Type>.md`) or a page generation rule, always write down which type
changed and how.**

This file is kept in two places and **the two copies must match exactly**
(`tests/test_changelog_sync.py` enforces this in CI). The repository root is the copy you
edit; `.claude/skills/wikicommit-init/CHANGELOG.md` is its duplicate. The duplicate is
needed because neither `install.sh` nor `npx skills add` carries anything outside a Skill
directory, so **without it this file never reaches the user's wiki repository at all** —
and the Skill tree is exactly where `/wikicommit-update` reads "what changed since the
version I last synced with".

**This file is written in English, and English is the canonical version** (Issue #772).
Like the SKILL.md files (Issue #154) and the console output of the distributed scripts
(Issue #770), it is a distributed artifact, and this project's public surface is
English-first. `CHANGELOG_ja.md` at the repository root is a Japanese rendering of this
file, in the same position as `README_ja.md`: a convenience for readers, not something a
machine reads, kept only at the root and allowed to drift. Nothing depends on it, so it
is not covered by the sync test — but when you add an entry here, update it too if you
can.

**Do not write `docs/`, `Issues/`, or `dev/` paths in this file.** As described above it
travels all the way to the user's wiki repository, and none of those directories are
reachable from there, so such a reference is untraceable by construction
(`tools/check_distributed_path_refs.py` stops this in CI). To record design rationale,
**write the Issue number alone**, or fold the point into a sentence.

When bumping the version, update all four of these together (`tests/test_version_sync.py`
enforces that 1 and 2 agree; `tests/test_changelog_sync.py` enforces that 3 and 4 do):

1. `VERSION` in `.claude/skills/wikicommit-init/scripts/templates/scripts/_version.py`
2. `version` in `.claude-plugin/plugin.json`
3. A new entry in this file
4. `.claude/skills/wikicommit-init/CHANGELOG.md` (the copy of this file)

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
version numbers follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-09-07

### Added

- **A record of each run, keyed on the run rather than on what it produced** (Issue #790).
  Every record layer here is keyed on an artifact — Git history on files, the source
  management files on one source, the review records on one review, the tracking Issues on
  one page — and nothing was keyed on a run, which left three questions unanswerable.
  - **Did the run finish?** A run that dies partway leaves some management files at
    `pending` and some at `generated`, which looks exactly like a queue that has not
    reached them yet; and the two paths that halt everything change no file at all, so
    they left no trace whatsoever. A record with a start and no end now says so.
  - **How long did it take, and when?** `generated_at` is a date, a commit timestamp is
    the merge rather than the generation, and no layer held an elapsed time at all.
  - `/wikicommit-generate`, `/wikicommit-translate`, `/wikicommit-synthesize` and
    `/wikicommit-merge` open a record and close it; `/wikicommit-status` reports the last
    run and any that did not finish. The other Skills do not: a single small edit is its
    own diff, `/wikicommit-collect` has a human watching, and asking whether a read-only
    Skill finished means nothing.
  - **These records are not committed**, unlike the review records, and the difference is
    deliberate: only the last run and unfinished ones are ever read, so nothing needs a
    history — while tracking them would put a file into every run's pull request and, since
    deleting a file in Git does not make it go away, would make retention impossible to
    express. They rotate automatically (newest 50) and are added to `.gitignore`. **They
    are therefore local to one checkout**: a clone sees none, so zero here means "nothing
    recorded on this machine", not "nothing has been run".
  - A forgotten closing stamp reports a finished run as unfinished. That direction is
    chosen: a false "did not finish" costs a glance, while a false "finished" would
    quietly retire the question the record exists to answer.

### Changed

- **The banner no longer claims that nobody has read the page** (Issue #774). The pending
  heading said "Nobody has read this page yet", which **is false in front of the person
  reading it**: what it actually reported was that no read by someone with write access
  had been recorded, a distinction most readers do not hold. The heading now states a fact
  true of the page in either state — that an LLM generated it — and `reviewed` adds a line
  to it.
  - **The cause was that the heading swapped.** Issue #739's principle is that review
    *adds* a line rather than retracting a warning, but the heading was still
    `isPending ? title : titleReviewed`, and while it swaps the pending side has to say
    *something* — with only a negation left to say. **The state now shows in whether the
    read line is there**, which is both simpler and more accurate: a reader is no longer
    handed "no record" as "nobody has read it".
  - **Issue #751 had to land first.** With the machine's own source check stated a line
    below, dropping the claim about reading cannot be read as "nothing has been done to
    this page".
  - The heading and the body were **split into the fact and what follows from it**
    ("This page was generated by an LLM" / "It may contain inaccuracies."); before, the two
    said nearly the same thing.
  - **The ⚠️ now appears in both states.** It used to belong to "nobody has read this
    yet"; with that claim gone it belongs to the heading, and being written by a model does
    not end at review. Keeping it pending-only would write back into the markup the
    reading Issue #739 denied.
  - **A reviewed page with no `reviewed_by` now gets a line of its own** ("A person has
    read this page") — the previous decision, that the heading already carried the fact, no
    longer holds now that the heading is gone. Route B pages (`/wikicommit-review` runs
    locally and cannot obtain a GitHub login) and anything reviewed before Issue #663 have
    no name, and without the line they would be indistinguishable from a pending page.
    With a name, `Read by: <login>` says both halves and the fallback is not printed.
  - **Calling this display a "badge" stopped** in the places this change touched. The word
    had no definition anywhere and is stronger than the thing: one ternary and one
    conditional `<p>`, not a distinct UI component. The repository was **not** search-and-
    replaced — registered Issues and published CHANGELOG entries are records of what was
    thought at the time.
  - Existing published repositories pick this up on the next build. `review_status`, the
    tracking Issues and `review-issue-close-sync.yml` are unchanged.

- **Review tracking Issues are now written in the wiki's `primary_lang`** (Issue #773).
  The templates in `/wikicommit-merge` Step 8 are English and the Issue was raised in
  English regardless of `primary_lang`, so the operator of a Japanese wiki received one
  English Issue per Japanese page. **The published site already switches and this did
  not**: the banner, the sources box, and the build-generated pages all render in the
  page's language, and the tracking Issue was the one reader-facing surface with no
  language at all.
  - This points the opposite way from Issue #770 (script console output) and Issue #772
    (the CHANGELOG) in the same batch, under **the same rule: the language follows the
    reader**. Those two are read by an operator and an agent and are diagnostics, so they
    are fixed English. This one is read by whoever closes it, which by design (Issue #313)
    includes someone who only reads the published wiki and has no Claude Code session.
  - **`.github/ISSUE_TEMPLATE/report.md` stays English** and is not the same case: it says
    in its own words that there is one of it per repository, so it has no language of its
    own. A tracking Issue is one per page, and that page has a `lang`.
  - **`primary_lang`, not the page's own `lang`.** The reader is whoever holds write
    access to close it — a property of the repository, not of the page. Using the page's
    language would send one operator Issues in two languages on a wiki with `targets`.
  - **Not translated**: the `<!-- wikicommit-page: ... -->` marker (the only part any
    machine reads), the Issue title (an identifier that listing and search depend on),
    anything anyone types or looks at (command names, paths, frontmatter keys and values,
    the `wikicommit-review` label), and the field values themselves.
  - The English templates stay canonical — translating at write time rather than shipping
    one template per language, which would double this Skill's instruction area for no
    gain. **`review-issue-close-sync.yml` is unchanged** (its contract of reading only the
    marker is untouched).
  - The wording varies between runs, since an LLM renders the template. Each Issue is read
    once, so that is accepted. **Issues already open are not rewritten.**

- **The front page's summary now shows the AI review count too** (Issue #769). Issue #751
  made Pass 4's verdict visible to readers, but **it reached two of the three surfaces**:
  the per-page banner and the overview page, not the front page — which is the wiki's
  entrance, and the very place Issue #664 judged a bare number to be read at its worst.
  The note there said only what the count is *not* ("not a guarantee", "not how much is
  finished") and never that **the remaining pages have been checked against their
  sources**, so "95 pages / 12 read by a person" read as "nothing has been done to the
  other 83". That is the understatement half of what Issue #750 named, with only the
  weakening half of the fix having arrived.
  - **Omitted at zero rather than written as 0, and that is accuracy rather than
    tidiness.** A wiki generated before review records existed has none (they are not
    created retroactively), and a language of nothing but translation pages has none
    either (the translation quality check is deliberately not recorded). Both mean "no
    record", while `checked against sources: 0` reports that as "nothing was checked".
    The overview page already omits its own line the same way. A repository with no
    records produces a byte-identical `content/index.md`.
  - **Counted per language on a multilingual wiki**, for the same reason Issue #730 split
    the other two counts and with the reason holding harder: a translation page carries no
    record, so a site-wide figure would be diluted by however many translations exist. The
    order is full-coverage first, then the part a person has read — the same order the
    overview page uses.
  - The note is a **separate key** shown only with the count it explains, worded like the
    overview page's: it names what the check does **not** cover. Stating only what it does
    would rebuild, facing the other way, the overstatement Issue #740 removed from "read
    by a person". No sampling vocabulary appears in reader-facing copy.
  - **`"The count above is"` was replaced with the label's own name** in
    `siteSummaryReviewNote` and the overview's `reviewed_note`. With a third number on the
    page it no longer identified which one it explained — and on the overview page it had
    already become ambiguous when Issue #751 added its row. The per-language note has
    named its label since Issue #730, so all three now read the same way.

- **`/wikicommit-init --quartz` now derives `locale` in `quartz.config.yaml` from
  `primary_lang`** (Issue #771). The template carried `locale: en-US` as a **fixed value
  rather than a placeholder**, and `init.py` never substituted it, so publishing a
  Japanese wiki with the default settings gave **body text and banner in Japanese and the
  sidebar, search, and graph in English**. The ja-JP translations exist in all three
  plugins that draw the chrome; they were simply never reached. Issue #378 had fixed the
  opposite symptom for WikiCommit's own plugins, which is why everything WikiCommit writes
  has looked right since — what was overlooked is the **chrome around** the same page.
  - The template now has a `{LOCALE}` placeholder, substituted from
    `QUARTZ_LOCALE_BY_PRIMARY_LANG` (ISO 639-1 → BCP 47; its values are taken from the 30
    locales the community-derived plugins actually ship). A language with no entry stays
    `en-US` — the chrome would be English either way, and an invented tag would only make
    the config claim otherwise.
  - **This is not the same table as `LANG_TO_LOCALE` in the plugins' own `src/i18n/`**
    (which lists the two languages WikiCommit itself has translations for). The names are
    deliberately different so the two do not look like copies to keep in sync.
    `tests/test_init.py` checks that every locale the table names still exists in all
    three plugins — upstream dropping one degrades silently to English chrome at build
    time.
  - **The remaining asymmetry cannot be solved by configuration and is now documented in
    the `locale` line itself** (which previously carried no explanation at all): `locale`
    is one per site and the three community plugins cannot switch per page, so in a
    multilingual wiki a translated page keeps the chrome of the original language.
  - No locale was added to WikiCommit's own four plugins, and
    `wikicommit-language-switcher` did not gain `resolveLocale()` — both are separate
    questions (Issue #771 records why).
  - **⚠ This does not reach existing repositories automatically.**
    `quartz.config.yaml` is `update: review`, so neither re-init nor `/wikicommit-update`
    overwrites it. Take in the one `locale` line by hand. No page regeneration is needed
    (this is a build setting).

- **Made English the canonical language of `CHANGELOG.md`, with a Japanese edition in a
  separate file** (Issue #772). This file is a **distributed artifact** — neither
  `install.sh` nor `npx skills add` carries anything outside a Skill directory, so a copy
  lives in the Skill tree and that is where `/wikicommit-update` reads what changed since
  the version last synced with. It nonetheless was entirely in Japanese, leaving the
  CHANGELOG as the only distributed artifact still in Japanese after the SKILL.md files
  (Issue #154) and the console output of the distributed scripts (Issue #770).
  - `CHANGELOG.md` (root **and** the Skill tree, still two identical copies) is now
    English, including all past entries. `tests/test_changelog_sync.py` keeps enforcing
    that the two copies match and now also checks that the body is English.
  - `CHANGELOG_ja.md` (**root only**) is the Japanese edition, in the same position as
    `README_ja.md`: a convenience for readers, not something a machine reads. It is not
    distributed and **not covered by the sync test, so it is allowed to drift** — enforcing
    it would make a verbatim translation of every entry mandatory for a file nobody reads
    mechanically. It states its own position at the top so nobody mistakes a stale copy
    for the canonical one.
  - The rule was added to `CONTRIBUTING.md`, and the header of `CHANGELOG.md` says how the
    Japanese edition is handled.

- **Unified the console output of the distributed scripts on English** (Issue #770).
  What `.claude/skills/**/scripts/*.py` printed to stdout and stderr was split between
  Japanese and English along the lines of when each script was written (20 with Japanese
  in a `print()`, 15 English-only; `set_frontmatter_field.py` and
  `reset_review_on_content_change.py` were even mixed internally — structured output in
  English, argparse argument errors in Japanese). The readers are the operator running
  `/wikicommit-status` or `/wikicommit-merge` and the agent that reads the same output to
  decide what to do next — not the wiki's audience — so this is fixed English, the same
  call Issue #405 made for the headings of source management files. Diagnostics are also
  the canonical case for the internationalization rule that machine-readable output is
  not translated: error strings get pasted verbatim into search engines and issue
  trackers, and translating them stops two people who hit the same problem from landing
  on the same string.
  - **Structured prefixes (`ERROR:` / `WARNING:` / `OK:` / `SUMMARY:` / `WANTED:` /
    `TYPE_MISMATCH:` and the rest) and exit codes are unchanged.** Only the
    human-readable part after the prefix moved, so the machine-readable contract the
    Skills parse is untouched.
  - **Comments and docstrings stay in Japanese** (their reader is the developer).
    Reader-facing labels on published pages (`ROOT_INDEX_LABELS` / `OVERVIEW_LABELS` /
    `SOURCE_*_LABELS` in `convert_wikilinks.py`) and the Quartz plugin locale files are
    likewise out of scope — Japanese is the correct language for that layer.
  - The frontmatter completion in `wikicommit-review` matched the literal Japanese body
    of a `validate_frontmatter.py` message (`必須フィールドがありません`), so the same
    change moved it to `required field is missing`. Splitting the two would not have
    raised an error; completion would simply have stopped proposing anything. The
    `check_actions_pr_permission.py` output example that `wikicommit-status` displays
    verbatim was translated as well.
  - To stop this recurring, `tools/check_script_output_language.py` was added and runs
    **blocking** in CI. It walks the string literals in `print()` arguments (including
    the constant parts of an f-string) with `ast` and reports an ERROR on any CJK.
    **Known limitation**: a script that returns its messages rather than printing them
    (`_frontmatter.py`) is invisible to this scan and has to be checked by hand.
  - **No retroactive work is needed in already-distributed repositories.**
    `.wikicommit/scripts/` is overwritten on re-init (`update: overwrite`), so the next
    `/wikicommit-init --no-overwrite` or `/wikicommit-update` replaces it with the new
    version.

### Notes

- No type template (`.wikicommit/schema/`) changed in this version (byte-identical to
  0.3.0), and no page generation rule changed either — the edits to
  `wikicommit-generate` / `wikicommit-translate` / `wikicommit-synthesize` only open and
  close a run record. **There is therefore no need to regenerate existing pages for this
  version.**
- **Two of the changes here are rendering-layer and arrive on the next build**, with no
  page rewrite: the banner no longer claiming that nobody has read the page (Issue #774)
  and the front page's summary showing the AI review count (Issue #769). A published
  repository picks both up by rebuilding.
- **One change does not arrive on its own.** `quartz.config.yaml` is `update: review`, so
  neither re-init nor `/wikicommit-update` overwrites it: take the one `locale` line in by
  hand to stop the sidebar, search, and graph from staying English on a non-English wiki
  (Issue #771).
- **Run records (`.wikicommit/run/`) are not committed and are local to one checkout**
  (Issue #790). They rotate at the newest 50, so a fresh clone sees none — zero there
  means "nothing recorded on this machine", not "nothing has been run". They are also not
  created retroactively: the first record is the first run made from this version onward.
  - **The `.gitignore` entry does not reach an existing repository on its own**, for the
    same reason as the `locale` line above: `.gitignore` is `update: review`. Until it is
    taken in, run records show up as untracked files. They are still never committed —
    `/wikicommit-merge` stages a fixed list of directories and `.wikicommit/run/` is not
    among them — so this is noise in `git status` rather than records leaking into a pull
    request. `check_distribution_freshness.py` reports the missing line, and
    `/wikicommit-update` presents it.
- Nothing is applied retroactively to existing wiki repositories. Review tracking Issues
  already open keep their English text (Issue #773), and review records still cannot be
  created for pages generated before 0.3.0 (Issue #750).

## [0.3.0] - 2026-09-06

### Changed

- **Stopped counting a page whose only records are `result: discarded` as reviewed, and
  started naming it instead** (Issue #766). `main()` in `check_review_coverage.py` read
  "this page's records" under three different definitions, and even after Issue #760
  narrowed `RISKY:` to the one standing verdict, the totals and `UNREVIEWED:` were left
  on their own rules — "the latest AI record (whether or not it judged anything)" and
  "does a record exist". The result was that **a page holding nothing but discarded
  records appeared on no per-page line at all while still being counted in
  `SUMMARY: ai_reviewed` and `COVERAGE:`** (the mismatch where `COVERAGE:` says
  `1 pages with attempts>=2` with no corresponding `RISKY:` anywhere had the same cause).
  The path there is not hypothetical: for an `action: update` entity, exhausting
  `max_retries` in Pass 4 leaves the existing page on disk and records `discarded`.
  - **The output changes meaning**: `SUMMARY: ai_reviewed` / `human_reviewed` and
    `COVERAGE:`'s `pages` / `findings` / `attempts>=2` are now all counted from the
    **standing record** (the latest record that judged the page as it now stands). In an
    existing wiki `ai_reviewed` may go down — no review was lost; the earlier number was
    counting discarded verdicts.
  - **`UNREVIEWED:` widens**: besides pages with no record at all, it now also lists
    pages with **no standing record**. A note on the line tells the two apart.
  - **`COVERAGE:` gains a fourth number**: `<N> discarded` — pages whose latest AI record
    was discarded and was written by this model. It keeps discarded attempts out of the
    coverage figures while letting `COVERAGE:` explain its own silence rather than appear
    to contradict a quiet `RISKY:`.
  - `SUMMARY: findings=` stays **cumulative** (findings from discarded verdicts still
    count). That number answers a historical question and is out of scope for Issue #766.
  - No retroactive processing of existing records (their immutability is central to the
    Issue #750 design). No threshold was introduced either.

- **Made the closing comment on route A (closing a tracking Issue on GitHub) the body of
  the review record** (Issue #762). What a tracking Issue mainly asks for is "write one
  line about what you took away from this page, then close it", and because
  `review_status` is a two-valued field that line does not fit in a field — the record's
  prose body is its only home. `/wikicommit-review` passed it with `--note`, but
  **`review-issue-close-sync.yml` did not, so the same artifact survived or vanished
  depending on which door it came through** — and by design that is the main door.
  - What is taken is **the single latest comment by the person who closed the Issue**.
    "The last comment before the close" mistakes someone else's unrelated comment for it,
    and "concatenate every comment" sweeps in change requests and discussion. Narrowing
    to that person costs nothing: the closer's login is already re-fetched live, and the
    job fails earlier if it cannot be resolved.
  - Comment bodies are free text written by third parties, so they **never appear on a
    shell command line**. The API response is written to a file, the selected comment to
    another, and that is passed with `--note-file` (no `${{ }}` expansion, no shell
    re-expansion) — the same rule this workflow imposes on every step.
  - "Latest" is not left to the API's ordering. `GET .../issues/{issue_number}/comments`
    accepts only `since` / `per_page` / `page`; `sort` / `direction` belong to the
    **repository-level** endpoint — passing them is silently ignored and the response
    comes back in ascending ID (oldest first) order. Every comment is fetched with
    `--paginate` and the maximum `created_at` is chosen here.
  - When an Issue is closed with no comments at all, a record is written with no body.
    Closing in silence is a normal way to close, not a failure (the result is exactly
    what it was before this change). A failed fetch or selection degrades to no body in
    the same way — this step sits between rewriting `review_status` and committing it, and
    failing here would leave the Issue closed and the page `pending` (this workflow only
    fires on `issues: closed`, so there is no retry path).
  - Collecting and aggregating closing comments in a UI remains out of scope. No
    retroactive work on already-closed Issues.

- **Made `RISKY:` look only at the verdict that currently stands** (Issue #760). `RISKY:`
  in `check_review_coverage.py` aggregated `max(attempts)` and the finding count across
  **every record** for a page. Records are immutable and never deleted, so **a page that
  was retried once, or received one finding once, never left the list again no matter how
  cleanly it was reviewed afterwards**. In a wiki that keeps ingesting, the list converges
  on the whole wiki, and at that point it selects nothing — `RISKY:` exists to decide
  which page a person reads next, so that is the feature disappearing.
  - This is not a new policy. Within the same function, `COVERAGE:` looked at the single
    latest AI record and `STALE_REVIEW:` at the latest AI record that judged the written
    page; only `RISKY:` looked at all of them. It now follows "the latest verdict only".
  - **The "it only passed on the second try" signal is not lost.** One review is one
    record, and the record itself carries `attempts`, so the record for a page that
    passed on the second attempt goes on reporting `attempts: 2` as the standing verdict.
    It drops off only once a newer review has judged the current body.
  - Kind is not filtered. `/wikicommit-review` can record findings for a human verdict
    too, so restricting to `kind: ai` would mean a human's finding never appears in
    `RISKY:` at all — a worse gap than the old behaviour. `STALE_REVIEW:` still looks at
    AI records only.
  - `result: discarded` records are not counted. They judge a page that was never
    written and say nothing about the page on disk.
  - `SUMMARY: findings=` stays cumulative; it answers "how many findings has review
    caught over this wiki's lifetime", a historical quantity.
  - No threshold was introduced. The question asked was which records to look at, not how
    many warrant a warning. No retroactive processing either — only the reading changes;
    not one byte of any record is rewritten.

- **Gave review tracking Issues a way to receive "the source itself is wrong"**
  (Issue #743). None of the items had ever asked whether a source is trustworthy — they
  consistently asked whether the page matches the source, and **if the source is wrong the
  page faithfully reflects it, so no amount of page-against-source checking will ever
  fail**. This is structural rather than accidental: under the evidence-binding rule the
  source is the yardstick, not the thing being judged, so a machine cannot doubt it.
  - The wording goes only in the `sources` variant. A translation page has no `sources`
    of its own and a synthesized page has only `derived_from`, so in both cases the
    document in question belongs to another page (both variants already redirect there).
  - The report lands in the retraction Issue #737 introduced (a human writes
    `status: retracted` and `## Retraction Reason` by hand), after which
    `/wikicommit-status` lists every page standing on that source. Because the answer goes
    to a human edit rather than to a command, it travels as a comment — the second
    exception to "a comment alone does not reach anything".
  - The same question, with the same scope, was added to `/wikicommit-review`.

- **Aligned what completing a review records with what `review_status` can actually
  carry** (Issue #740). A two-valued field can structurally only say "did it happen or
  not". Putting a **claim** ("this page is correct") into it was the distortion: a claim
  needs content, the content had to be bolted on, the result was a checklist, and because
  that shape read as a guarantee, closing became a signature. What went in instead is the
  artifact the container fits — **a person read this page to the end**, i.e. this wiki's
  knowledge reached at least one person other than the machine that generated it.
  **Review was not abandoned**: one reading produces noticing a defect, receiving
  knowledge, and judging value all at once; only the shape each artifact records in
  differs.
  - **Nor is this stepping back from quality assurance. The work split between full
    coverage and sampling.** Defects decidable by checking against the sources are caught
    by Pass 4 on **every page** (that verdict is recorded as of Issue #750 and made
    visible to readers by Issue #751), and the two things a machine cannot do in principle
    — harm to real people and organizations, and disagreement with the reader's own
    knowledge (Issue #723) — **are adequately covered by a sample**. Sampling is the
    design, not a hole, and it holds only because the full-coverage side is recorded and
    can therefore claim to be full coverage. `RISKY:` in `check_review_coverage.py`
    (pages that were retried or received findings) says where to start sampling.
    But **there is no population, sampling rate, or pass/fail judgement** — a sampling
    design chosen before any measurement is guesswork, and is added together with its
    consumer (Issue #553).
  - The `- [ ]` boxes were removed from all three review tracking Issue templates and
    replaced with one line of "what you took away from this page" plus a bullet list of
    anything you noticed. "This is not a comprehension test" is stated explicitly.
  - Display strings were aligned with the new meaning: the banner heading (unreviewed →
    **nobody has read this page yet**), "Reviewed by:" → "Read by:", "Human-reviewed:" →
    "Read by a person:", the per-language counts on the top page, `reviewed` /
    `reviewed_note` / `col_reviewed` on the overview page, and the notes in
    `wikicommit-ask` / `wikicommit-synthesize`. **"N unreviewed" is not "N units of
    unverified debt"** — every page has been checked against its sources, and N is how
    many of them have not yet reached anyone.
  - The `review_status` / `reviewed_by` field names, the `wikicommit-review` label, the
    workflow file names, the Skill names, and the commit trailers are **unchanged**. The
    word "review" covers all three artifacts above; what changed is which of them this
    field records. (Renaming the label would also break duplicate detection against
    existing tracking Issues and re-file one for every page.)
  - No retroactive work on already-closed tracking Issues, and no regeneration of
    existing pages.

- **Started showing the AI review result on published pages and the overview page**
  (Issue #751). Pass 4 checks every generated page against its sources, and since
  Issue #750 that verdict is recorded in `.wikicommit/review/`, but readers could not see
  it. `convert_wikilinks.py` now reads the records as a second input and injects
  `ai_review_model` / `ai_review_at` **into the `content/` side only** (pages under
  `.wikicommit/entity/` are unchanged).
  - Nothing is shown when there is no verdict, when it has gone stale (an edit by
    `/wikicommit-fix`, or a changed source), or when it is not `pass`. Staleness is
    recomputed every build from `page_content_hash` and `reviewed_sources`, so the failure
    mode where a copy on the page goes out of date cannot occur by construction.
  - The wording states what was checked. Comprehensiveness, effects on real people and
    organizations, and disagreement with the reader's own knowledge **are not checked**.
  - Finding counts are not shown per page (they read backwards); they are aggregated on
    the overview page.

- **Started noting on the report link of published pages that a GitHub account is
  required** (Issue #742). Opening the report link while logged out lands on a login wall,
  and the link gave no warning. The pre-filled content is restored after authentication,
  so the response is limited to stating that one fact. No account-free intake was added.

- **Redefined `wikicommit_version` from "the version that initialized this repository" to
  "the version last synced with"** (Issue #713). Its writers now include
  `/wikicommit-update`, not just the first init, so it is rewritten on every sync. That
  makes "where did we come from last time" something the repository retains, which lets
  `/wikicommit-update` cut **just this update's range** out of `CHANGELOG.md`. Nothing
  consumed the old "version that initialized this repository", and where that is needed it
  can be recovered with `git log --diff-filter=A -- .wikicommit/config.yml`.
  **It is not applied retroactively** — a repository with no stamp gets one on its first
  `/wikicommit-update`.

- **Started keeping `CHANGELOG.md` at `.claude/skills/wikicommit-init/CHANGELOG.md` as
  well** (Issue #713). Neither `install.sh` nor `npx skills add` carries anything outside
  a Skill directory, so without a copy there this file never reached a user's wiki
  repository at all, and `/wikicommit-update` had nowhere to read "what changed since the
  version I last synced with". `tests/test_changelog_sync.py` enforces that the two copies
  match in CI.

- **⚠ Re-init now updates WikiCommit's own distributed artifacts** (Issue #712). Until
  now, re-running `/wikicommit-init` treated every root-level output except
  `.wikicommit/scripts/` (Issue #647) uniformly as "leave it alone if it already exists".
  That uniformity **treated "must not be broken" and "must always be current" the same
  way**, so a repository initialized one version earlier silently kept using an old
  workflow, old plugin `dist/`, and old build scripts (all three pilots were carrying the
  same stale version). **The following are now overwritten on re-init** (with or without
  `--no-overwrite`):

  - `.github/workflows/review-issue-close-sync.yml`
  - `.github/workflows/deploy.yml`
  - `quartz-plugins/` (`src/` and `dist/` of all four plugins)
  - `prebuild-symlinks.cjs` / `repair-plugin-builds.cjs` / `install-local-plugins.cjs`

  Every one of these is WikiCommit's own distribution payload, with no structural
  expectation that a user edits it (`quartz-plugins/` is distributed with `dist/`
  committed, and `install-local-plugins.cjs` only runs `npm install`). **If you have
  hand-edited any of these files, move them aside before re-initializing.** Repository-specific
  CI can be added as a separate workflow file.

  `config.yml`, `quartz.config.yaml`, `.wikicommit/schema/`, `package.json`,
  `.lychee.toml`, `.markdownlint.json`, `.gitignore`,
  `.github/ISSUE_TEMPLATE/report.md`, `source-policy.md`, and `entity-policy.md` are
  **left completely untouched, as before**.

- **`config.yml` and `.wikicommit/schema/` are now protected even if you forget
  `--no-overwrite`** (Issue #712). Neither carried any copy flag, so dropping
  `--no-overwrite` erased `theme`, reset `targets` to `[]`, and reverted hand-edited type
  templates. Both are now declared `review`, which protects them regardless of the flag.

### Added

- **Made it possible to enable giscus (comments and reactions on a page)** (Issue #741).
  The default stays `enabled: false`, and **enabling it is a manual step for the
  operator**. There was nowhere in this wiki to write down a not-yet-certain observation —
  "huh, that's interesting", "this feels like it disagrees with another page somehow".
  The report link opens an Issue, which asks the writer to be sure enough to say something
  should be fixed.

  The point is that **what goes missing overlaps with what a machine cannot reach in
  principle**. A contradiction between two pages generated in different batches is by
  design beyond every automated check (Issue #566 states this), and the only party in the
  system holding several pages across batches is **a human**.

  - The comment block in the `quartz.config.yaml` template documents the three
    prerequisites (public / the giscus app / Discussions), recommends an Announcements-type
    category, and gives the enabling steps. **The four values (`repo` / `repoId` /
    `category` / `categoryId`) are not shipped as empty keys** — in most repositories they
    would stay empty forever (Issue #553).
  - An "Enabling comments (giscus)" section was added to the `wikicommit-init` SKILL.md.
  - **Reactions are not wired to `review_status`.** A 👍 does not mean "read", no
    threshold has any principle behind it, it bypasses the write permission a close
    requires, and it would make "pages nobody has read yet" impossible to list (a
    Discussion only exists once there is a first reaction).
  - **`comments: false` was added to build-generated navigation pages** — per-type
    indexes, **per-view indexes**, the root index, `content/sources/`, and
    `content/overview/`. giscus goes into `afterBody`, so left alone it attaches to every
    page, and these are not knowledge pages. It is one more key in **exactly the same
    place** that already stamps `review_status: reviewed`.
  - **Two kinds of page that frontmatter cannot reach are excluded through layout
    settings** — the folder and tag pages Quartz synthesizes itself have no corresponding
    `.md`, so there is no writer to stamp. In particular `content/<lang>/index.md` is not
    written, which makes every language top page (`/ja/` and so on) a synthesized folder
    page. `comments` was added to `layout.byPageType.folder.exclude` / `tag.exclude` —
    the same lists already exclude `wikicommit-banner` for the same reason (Issue #648).

  **⚠ This does not reach existing wikis automatically.** `quartz.config.yaml` is
  `update: review` (Issue #712), so neither re-init nor `/wikicommit-update` overwrites it,
  and because the block already exists it does not show up in drift detection either. An
  existing wiki that wants to enable this has to copy the comment block and the two
  `exclude` entries from the template by hand.

- **Consolidated the review discipline into `.wikicommit/review-rules.md`** (Issue #752).
  The same discipline was written in **three places** — `wikicommit-generate` Pass 4,
  `wikicommit-review` Step 4, and `wikicommit-synthesize` Step 5.5 (27KB ≒ 6,800 tokens
  measured) — **and they had already diverged**: the checks only Pass 4 had (disagreement
  between sources, one-hop contradictions between pages, naming vs. inventing, secondary
  citations) were absent from `wikicommit-review`, while only `wikicommit-review` had the
  warning about model independence. Nobody had decided which was right.

  - Only "**what is checked**" moved. The procedure (retries, `failed_pages`, writing the
    page, updating `status`, recording) stays in each Skill.
    `tests/test_review_rules_single_source.py` pins both directions in CI — that the
    discipline has not been written back into a SKILL.md, and that the procedure has not
    disappeared from the Skills.
  - **Guarded from both sides**: the rules file (the receiver) says "only blocks marked
    `SOURCE` may be treated as evidence", and the SKILL.md (the sender) says "pass the
    subagent exactly three things: the page, the **full** extracted text, and one hop
    out". The prompt is assembled by **the agent that wrote the page itself**, whose
    context is full of things that must not be passed along (the `summary`, the analysis
    JSON, the previous round's verdict). The evidence-binding rule cannot stop this — what
    it forbids is judging from your own **world knowledge**, and a `summary` is not world
    knowledge, so it slips through.
  - **`rules_version` echo check**: the subagent is required to include the rules file's
    `rules_version` in the JSON it returns, and the orchestrator verifies it. If the file
    is not read, the review degrades to a bare one **and the output still looks normal**.
    A missing or mismatched value triggers exactly one restart, and if that fails too the
    **whole run stops and reports** (without consuming the page's `generate.max_retries`
    and without dropping it into `failed_pages` — this is a problem with the environment
    or the instructions, not a defect in the page).
  - **⚠ Without `.wikicommit/review-rules.md`, all three routes stop.** It is an
    `update: overwrite` file distributed by re-init (`/wikicommit-init --no-overwrite`), so
    a repository that updated only its Skills with `npx skills add` **has to re-init
    first**. It does not fail open because a silently degraded review would go on to write
    a record claiming the page was reviewed.
  - What `skill_blob` in a page record (Issue #750) points at also moved from the SKILL.md
    to this file.

- **Started recording AI review verdicts in `.wikicommit/review/`** (Issue #750).
  `wikicommit-generate` Pass 4 ran eight kinds of check over **every** generated page
  without keeping a single byte of the verdict — which meant **a page that passed cleanly
  on the first try and a page that was caught hallucinating and passed on the second
  looked completely identical on disk**. All that remained was `failed_pages` (pages never
  written at all), which is not a record of review working but a record of review failing
  to save something.

  **One review = one file = immutable.** Written create-only to
  `.wikicommit/review/<tree>/<lang>/<type>/<slug>/<YYYYMMDD>-<HHMMSS>-<kind>.md` and never
  edited again (no read-modify-write, git merges trivially, several review perspectives
  are expressed naturally, and a person can read it). Records survive the deletion of the
  page, and **a directory is created even for a page that was never written** — that is
  the most valuable record of all.

  - `record_review.py` (new) writes them. There are four callers:
    `wikicommit-generate` Pass 4 (**both** a PASS and a page that was never written),
    `wikicommit-review`, `wikicommit-synthesize`, and `review-issue-close-sync.yml`.
    **The last one is the crux** — closing a tracking Issue from GitHub's web or mobile UI
    runs no local script at all, so without it the totals would go on reporting "0 human
    reviews" even while people were reading. It writes the record in the **same commit**
    that rewrites `review_status`.
  - `check_review_coverage.py` (new) reads them back and is called by `wikicommit-status`:
    `SUMMARY:` / `COVERAGE:` (per model) / `UNREVIEWED:` / `RISKY:` (sampling candidates) /
    `STALE_REVIEW:` (**both** a changed page body and a changed source) /
    `RETRACTED_EVIDENCE:`.
  - `source_quote` (a verbatim excerpt of the source document) is **not recorded even if
    the caller passes it** — the script drops it, so the guarantee does not depend on an
    instruction being followed.
  - `page_content_hash` is computed by **importing** the six-field ignore list from
    `reset_review_on_content_change.py` (not copying it). That makes "is this review still
    valid for the page as it stands" a deterministic question.
  - `findings` holds **every round**, flat, tagged with `round:`. Recording only the final
    round would leave a page that failed once and was fixed with `findings: []`, erasing
    exactly the signal worth having.
  - The Completion Notice of `wikicommit-generate` now prints that run's **denominator**
    (pages reviewed), finding count, and model on one line. Without a denominator, "a run
    where nothing was wrong" and "a run where review never happened" are indistinguishable
    in the output.

  **No retroactive generation for existing pages or repositories** — a missing record
  means "generated before this feature existed". **And measurement cannot be created
  retroactively** (the period without records is blank forever). `review_status` /
  `reviewed_by` / the trust ladder / the tracking Issue templates / the banner are
  **unchanged**.

- **`/wikicommit-update`** (Issue #713). A new Skill that syncs the repository with the
  installed distribution and turns the result into a PR. It runs in nine stages (compare
  versions → detect drift with `check_distribution_freshness.py` → apply the distribution
  payload by re-init → confirm orphan deletions → present diffs for files a user may have
  edited → stamp `wikicommit_version` → verify → PR → report what changed). Like
  `wikicommit-schema-propose` it **opens its own PR and does not auto-merge** — deleting
  orphans and applying diffs are both human judgements, and the PR is where they are
  reviewed. **Updating `.claude/skills/` itself happens outside this Skill** (a human runs
  `npx skills add` first), because rewriting your own `SKILL.md` leaves the running agent
  holding the old instructions it loaded at startup.

- **`init.py --update-version <VERSION>` / `init.py --add-config-keys <KEY>...`**
  (Issue #713). The first rewrites only the `wikicommit_version` line of an existing
  `.wikicommit/config.yml`; the second adds only the top-level keys the template has
  gained, together with the commented-out examples that explain them. Both are
  **text-level rewrites** like `--update-theme`, with no YAML round-trip — `config.yml`
  ships commented-out examples (some, like `site_description`, show the shape in a comment
  without shipping the key at all), and `yaml.safe_load` + `yaml.dump` drops all of them.
  `--add-config-keys` never rewrites an existing value, and if the result would not parse
  as YAML it writes nothing and exits with an error.

- **`check_distribution_freshness.py`** (Issue #712). A read-only script that reports
  whether the installed distribution matches the templates `wikicommit-init` ships. It
  runs as Step 11 of `/wikicommit-status`. It reports `OUTDATED:` (stale), `MISSING:`
  (absent), and `ORPHAN:` (no counterpart in the template — the remains of an upstream
  rename, which stay because `copy_tree` never deletes), and always exits 0. For files a
  user may have edited it reports only **what the template newly gained** (config keys,
  frontmatter keys, ignore patterns), not that a value was changed or prose rewritten —
  a warning that is always lit stops being read. If `wikicommit-init` is not installed it
  prints one warning and reports nothing.

### Fixed

- **The two numbers on the root index were totals across all languages** (Issue #730). In
  a multilingual wiki this produced figures **no reader ever experiences**, such as
  `Total pages: 522` (174 pages each in it/en/ja). The reviewed ratio was also diluted by
  translations (ja at 100% but it/en at 0% reads as 33% overall), which skewed a number
  placed there as a statement of the trust ladder toward pessimism. A multilingual wiki
  now emits neither `wikicommit_page_count` nor `wikicommit_reviewed_count` (which stops
  the banner's site summary from rendering; no plugin change was needed) and instead puts
  a per-language count on each line of the language list, as
  `- [ja](./ja/) (174 pages / 174 read)`. The one line saying what the number counts moves
  into the body and stays. A single-language wiki has no language list, so it still shows
  the totals in the banner as before. **No retroactive work is needed** — the root index is
  regenerated on every build, so the next deploy picks up the new display.

- **The conditional "type selection" item was missing from the tracking Issue
  implementation** (Issue #729). The item asking whether the chosen type suits the subject
  existed in the design documents and in `wikicommit-review`, but **not in the
  `wikicommit-merge` template that actually writes the tracking Issue on GitHub**. As a
  result, for a page whose type `wikicommit-generate` Pass 2b added on the spot, the
  tracking Issue never offered a human the chance to check that type choice (in a
  non-interactive run Pass 2b can add a type without even an Enter confirmation). All
  three places now carry the same item, and the condition is decided by whether
  `wikicommit.provenance` in `.wikicommit/schema/<Type>.md` is `generate-interactive` or
  `generate-auto` — looking at a permanent stamp rather than a batch diff means a page
  picked up later, after Issue creation failed on an earlier run, receives the same
  checklist. **No retroactive work on already-closed tracking Issues.**

- **The root index dropped real languages that were not in `translation.targets`**
  (Issue #731). The language chooser was built from `targets` alone, so **a language with
  real pages but no entry in `targets` had no link at all**. The pipeline itself creates
  that state: `/wikicommit-translate <page> --lang <lang>` writes a translation page
  without touching `config.yml`, and the error message for an empty `targets` explicitly
  offers the option that does not edit `config.yml`. The same happens when pages are added
  by hand, when `primary_lang` is changed afterwards, or when `targets` is trimmed after
  translations exist. The list is now the union of `targets` (still narrowed by
  `existing_lang_targets()` as before) and **the languages that actually had published
  pages written**. The order is `primary_lang`, then the order given in `targets`, then
  discovered languages (sorted), so an existing wiki's ordering does not change. Only the
  site's entrance was broken; the Explorer, the language switcher, the overview page, and
  `/wikicommit-search` already handled unlisted languages. **No retroactive work is
  needed** — the root index is regenerated on every build.

### Notes

- No type template (`.wikicommit/schema/`) changed in this version (byte-identical to
  0.2.0). The only difference in page generation is how `review_status` / `reviewed_by`
  are handled on an `action: update`; nothing about how the body, `properties`, or `tags`
  are written changed. **There is therefore no need to regenerate existing pages for this
  version.**
- However, **review records (`.wikicommit/review/`) cannot be created retroactively**
  (Issue #750). Pages generated before this version have no record,
  `check_review_coverage.py` reports them as `UNREVIEWED:`, and published pages carry no
  "checked against sources (AI)" line. Records attach only to pages generated or reviewed
  from this version onward.
- Nothing is applied retroactively to existing wiki repositories. A missing
  `wikicommit_version` means "created before this feature existed", and the stamp first
  appears on the initial `/wikicommit-update` (Issue #713).

## [0.2.0] - 2026-09-01

### Added

- **Split synthesized pages out into `.wikicommit/view/` and gave them a `kind` instead of
  a Schema.org type** (Issue #675). The output of `/wikicommit-synthesize` moved from
  `.wikicommit/entity/<lang>/<Type>/<slug>.md` to `.wikicommit/view/<lang>/<slug>.md`
  (**with no Type segment**), is published as `content/<lang>/View/<slug>.md`, and is
  referenced with `[[View/<slug>]]`. Two different things had been living together under
  `.wikicommit/entity/` — primary knowledge that can be checked against an external source
  document (`sources` + hash), and secondary knowledge that can only be checked against
  the wiki's own pages (`derived_from`). The difference is not the page's subject but
  **what it can be checked against**, and mixed into the same type directories it was
  invisible to readers. A view page **has no `type:`** — Schema.org is a vocabulary for
  modelling things, and something carrying "when it applies, its premises, its failure
  modes, the kind of evidence behind it" is not a class of thing but **a way of reading**.
  It carries an optional `kind` instead (`practice` / `landscape` / `comparison` /
  `pattern` / `timeline` / `debate`), which says what you do with several pages at once.
  Each kind has a `Boundary` (`landscape` writes no numbers, `comparison` does not rank,
  and so on) that the review subagent in Step 5.5 checks — without a check, `kind` becomes
  a label nobody looks at and drifts. **`kind` does not appear in the path** (letting a
  wrong kind move the file would reproduce the breakage of Issue #545). As a side effect,
  removing the type-selection step entirely made the Issue #545 problem — two runs on the
  same topic resolving to different paths — structurally impossible. `VIEW_DIR` /
  `VIEW_TYPE_SEGMENT` / `VIEW_KINDS` / `parse_view_path()` / `collect_view_pages()` were
  added to `_wikilink.py`, and each script decides one at a time whether to walk the view
  tree (the exclusions are pinned by `tests/test_view_tree.py` — the reasons for excluding
  hold regardless of the tree's contents, so a later change to walk both trees would not
  error, it would just add findings nobody can act on). `rebuild_index.py` gained a
  per-language index mode and `build_survey_view.py` gained `--include-view`. **Existing
  synthesized pages are not migrated automatically** (they stay under `entity/` and keep
  working). Design details are in Issue #675.

- Running `/wikicommit-collect` with no arguments now runs a step (Step 3.5) that
  **surveys the whole wiki and picks a focus** before exploring (Issue #672). It reads
  three things — `build_survey_view.py` (what exists), `WANTED:` from
  `check_wanted_pages.py` (gaps the wiki itself has declared it wants filled), and
  `ORPHAN:` from `check_orphans.py` (which carries the originating source, so thin areas
  show) — and proposes up to five angles. Whichever the human picks becomes that run's
  research guidance (it does not replace `theme`), and the rest of the exploration uses
  it. `theme` is the wiki's overall content scope and is too coarse to steer a single
  exploration, but writing that steer requires seeing the wiki's current state, and
  collect had no way to do that — so an argument-less run searched with the same breadth
  every time and kept turning up candidates in areas that were already thick. It is the
  same shape of step as the survey mode of `/wikicommit-synthesize` (Issue #586), placed
  on the exploration side; the confluence point (research guidance) already existed, so no
  new concept was needed. **It is not automatic exploration** — the human decides, and the
  survey only supplies material. If nothing is chosen it explores nothing and stops,
  including in a non-interactive run (`/wikicommit-collect <guidance>` skips the survey).
  The survey step writes nothing, and rejected angles are not persisted anywhere.

- The published site's top page can now carry **a reader-facing site description, one per
  language** (Issue #671). Writing a top-level `site_description` in `config.yml` (a
  language code to a one-to-three-sentence string) makes `load_site_description()` in
  `convert_wikilinks.py` read it, and `generate_root_index()` appends that language's
  description to each line of the language chooser (`- [ja](./ja/) — ...`). In a
  single-language wiki it is one line directly under the "Wiki top" link. It replaces the
  `theme` display Issue #670 removed, but **its audience is different** (the former is one
  string telling an LLM the content scope; this is prose for readers), so no rule ties the
  two together — deriving one from the other would return to the mixture Issue #564
  resolved. It goes **in the body** rather than being rendered by the banner via
  frontmatter, because the value is a per-language mapping that does not fit in a single
  string, and because putting each description directly under its language's link removes
  the need for a caption at all and so avoids the banner i18n two-locale constraint. Only
  languages with real pages are included (following the existing safety valve of
  `existing_lang_targets()`; Issue #190). It is a field **a human writes**:
  `/wikicommit-init` gains no extra prompt, and the template carries only a commented-out
  example (the key itself is not shipped; Issue #553). It is not applied retroactively to
  existing repositories, and without the field the output is what it was before.

- Added `check_self_referential_tags.py`, called from Step 10 of `/wikicommit-status`
  (Issue #571). It reports tags identical to the page's own `title` (which can only group
  the page with itself) and tags identical to its `type` (which `type:` already says).
  Issue #275 forbade both in prose and they came back anyway — a rule with no detector
  drifts. Matching is **exact after normalization** only, never partial (the tag `見沼` on a
  page titled `見沼田んぼ` is the useful kind). Warning only; it blocks neither a merge nor
  a health verdict.
- `/wikicommit-collect` can now **mine an index page's reference section** (Issue #570).
  A page named by `index_only:` in `.wikicommit/source-policy.md` (per domain) or by the
  `--index <url>` argument is never a candidate itself; instead its citation and external
  link sections are mined for primary-source URLs, which flow into the candidate list.
  **Never registering the index page itself** is the boundary between the safe and unsafe
  version of this: reading its body to decide *what to write* produces an unattributed
  derivative work, because that page is not in `sources:` and so neither Pass 4's
  source checking nor the attribution display applies to it. The example guidance in
  Step 2 was also replaced (`"search mainly on Wikipedia"` → `site:wikipedia.org`), so
  that guidance naming an encyclopedia is clarified before acting on it.
- Registering a source under a ShareAlike license now says so once in the registration
  message (Issue #570). A page whose `sources` are **entirely** ShareAlike is also listed
  in the `/wikicommit-generate` Completion Notice (the obligation attaches to the page, not
  the source). This is not a blanket ban — subjects with no primary sources (a shrine's
  history, a local cultural concept) will always exist, and the goal is to keep the pages
  that carry the obligation deliberately few.
- The `ORPHAN:` lines of `check_orphans.py` now carry the page's `sources` (Issue #570).
  The question worth asking after "is it orphaned" is "which source produced it", and this
  makes the **hypothesis worth testing** — that leading with a skeleton source produces
  fewer orphans — checkable during normal operation.
- Added `.wikicommit/source-policy.md` (Issue #564). It is the file that says **which
  sources to take in**, answering a different question from `config.yml`'s `theme` (what
  the wiki is about, i.e. which entities from already-ingested sources become pages).
  Having had nowhere else to go, source policy was being pushed into `theme`, where the
  main route (running `/wikicommit-generate <path|url>` directly) never read it at all
  while it leaked as noise into Pass 2c's entity exclusion decisions. `/wikicommit-init`
  ships an empty template and does not overwrite it on re-run. **An existing repository
  without the file works exactly as before** (an empty body means there is no prose
  policy). Its frontmatter carries `exclude_domains` (unioned with the built-in list in
  `check_extraction_quality.py`; the built-in side cannot be disabled) and `rejected`
  (sources considered and turned down, which `/wikicommit-collect` appends to with a
  reason right after they are rejected — without it, free exploration re-proposes the same
  candidates every time). Each `exclude_domains` entry is compared by **exact match** after
  stripping the scheme, path, port, and a leading `www.` (`example.com` does not match
  `blog.example.com`). `/wikicommit-merge` detects and commits changes to this file (an
  uncommitted append does not function as a record).
- Added `check_installed_type_usage.py`, called from Step 9 of `/wikicommit-status`
  (Issue #565). It is the counterpart to `check_schema_coverage.py`, reporting **a schema
  file with zero pages** (`UNUSED`; types with `provenance: default` are exempt) and
  **pages written under an ancestor type while a more specific descendant is installed**
  (`ANCESTOR_FALLBACK`; a hint, not an assertion). In one pilot, `Park.md` and `Museum.md`
  were installed with approval while seven parks and two museums were generated as plain
  `Place`, and because `Place` has a schema file the existing gates kept reporting zero.
  Warning only; it blocks neither a merge nor a health verdict.
- Added `--list-installed-hierarchy` to `check_schema_org_type.py` (Issue #565). For each
  type installed under `.wikicommit/schema/`, it prints **only the installed ancestors**,
  nearest first. `wikicommit-generate` Pass 2c includes this in its context.
- Added `check_unlinked_entity_mentions.py`, called from Step 8 of `/wikicommit-status`
  (Issue #561). It reports values of `properties:` keys whose range includes an entity type
  that **name an existing page but are written as plain text**. It is the mirror image of
  `check_wanted_pages.py` (a link with no page behind it). In one pilot, of ten people in a
  single value list, only the eight whose pages were created in the same ingest as the Book
  page were turned into WikiLinks, while the two whose pages came from a later ingest
  stayed plain text (same property, same type, same qualification — the only difference was
  ingest order). The fix is `/wikicommit-fix <page-path>`; there is no bulk rewrite.
  Warning only; it blocks neither a merge nor a health verdict.
- Added `check_recurring_characters.py`, called from Step 7 of `/wikicommit-status`
  (Issue #560). It aggregates characters listed as plain text in `properties.character`
  across every page and reports names that recur in two or more works without a `Person`
  page (`RECURRING`) and names that already have a `Person` page but are not linked
  (`UNLINKED`). A plain-text name is invisible to `check_wanted_pages.py` (which reads only
  WikiLinks), so these had never surfaced anywhere. Warning only; it blocks neither a merge
  nor a health verdict.

- Added `/wikicommit-generate --regenerate` (Issue #578). A page-oriented mode that
  rebuilds an existing wiki page with the current schema templates and generation rules.
  It re-fetches the page's `sources` and runs only Pass 3 and Pass 4, skipping Pass 2 and
  Pass 2b. A regenerated page's `review_status` returns to `pending` (so that proof of
  review is not inherited by content no human has ever read).
- Gave layers ② (site-wide) and ④ (README) of the license display somewhere to land
  (Issue #645; layer ① — per-page attribution — shipped in Issue #558). Layer ② became a
  note on the root `content/index.md` and `content/sources/index.md` generated by
  `convert_wikilinks.py`, saying that terms differ per page, that there is no single
  site-wide license, and to look at each page's sources section — Quartz's footer plugin
  accepts only `links` (label → URL) and cannot emit prose, and putting links alone in the
  footer breaks precisely on a GitHub Pages project page, where `baseUrl` is
  `<owner>.github.io/<repo>`. The wording is Japanese or English depending on
  `primary_lang`. It is shown even with zero registered sources (it describes how the wiki
  is made). Layer ④ became an item for the README in `wikicommit-init`'s Next steps
  (`_LICENSING_STEP`), which offers ready-to-paste wording — README.md is display-only
  (agents do not edit it), so nothing is generated or appended automatically.

- The candidate list in `/wikicommit-collect` now shows the same known license that would
  be recorded at registration (Issue #646). A read-only `--license-for-url` was added to
  `add_source.py`, and `wikicommit-collect` Step 6 calls it. For a ShareAlike source it
  also notes that a page built from that source alone carries an obligation to offer it
  under the same license — moving the registration-time warning (Issue #570) one step
  earlier, while you can still decline. **Nothing is written for a domain not in the
  table** (the table only holds sites that state a license for their whole site, which is
  most candidates, and a note on nearly every line gets skipped). Instead the preamble to
  the candidate list says once that a license is shown only for confirmed sites, and that
  its absence means "we do not know the terms", not "there are none".

- Added a source-consistency review (Step 5.5) to `/wikicommit-synthesize` (Issue #674).
  Of the three routes that write a page, only synthesis had no verification —
  `/wikicommit-generate` checks against external source documents in Pass 4 and
  `/wikicommit-translate` against the source page, while synthesis was protected by a
  single sentence saying "do not write a claim that is not in a grounding page's body".
  **Synthesized pages are the ones that need verification most**: having no `sources` and
  only `derived_from`, a reader's only way to check the content is to follow the grounding
  pages. A review subagent of the same shape as Pass 4 was inserted, and on FAIL the
  `issues[].instruction` is passed into the regeneration prompt. Retries reuse
  `generate.max_retries` (no new key), and exceeding the limit stops and reports without
  writing the page. Disagreement between grounding pages is not a FAIL and is listed in
  the completion report instead (this Skill has no authority to rewrite a grounding page,
  so failing would mean rebuilding a correct synthesis only to receive the same finding
  again).
- Also in `/wikicommit-synthesize`, grounding pages with `review_status: pending` are now
  listed before the body is generated (Issue #674; the wording matches the ⚠️ in
  `/wikicommit-ask`). **It is a warning, not a gate** — right after a generation batch
  every page is `pending`, and stopping there would make the Skill unusable exactly when
  it is most useful.
- Also, pages with `derived_from` (other synthesized pages) are now excluded from the
  grounding set (Issue #674). This establishes the invariant that a synthesized page is
  only ever one level above ordinary pages, which lets `check_derivation_freshness.py`
  catch staleness completely. **They are not excluded from the indexes** —
  `/wikicommit-search` and `/wikicommit-ask` still find synthesized pages.

### Changed

- **Measured the effect of the CI job reductions and settled the `actions/cache` question
  that was still open** (Issue #641; documentation only — no workflow definition changed).
  Issue #591's reductions had never been exercised by an actual CI run, so their effect
  remained a paper estimate; it has now been measured over 25 successful runs. A PR
  touching only Issue drafts started neither job (0 workflow runs, 0 check-runs), and a
  real PR confirmed that `mergeable_state` stays `clean` and does not block the merge.
  **`actions/cache` for `node_modules` is not adopted**: the `npm ci` calls total only 77
  seconds, while the cache target is 394 MB compressed / 1.3 GB uncompressed — every
  lockfile change adds a new cache entry that evicts other entries, and the very run that
  updates the cache ends up slower. The method and the figures are recorded in Issue #641.

- **Established "review must be splittable" as a design principle** (Issue #676;
  documentation only — no code changed). It was written up as a design principle and the
  opening of both READMEs was aligned with it (the development repository's project
  instructions and requirements document say the same). **An LLM generates pages faster
  than one person can read, so a design in which review can only advance a batch at a time
  jams up the faster generation gets** — fixing the unit of review at a single page (one
  page = one review tracking Issue = one close) is the condition for avoiding that. Where
  the existing §1.5 "incremental trust" describes the **order** of the gates (vertical),
  §1.6 describes the **splitting** of the unit (horizontal). This gives a reason to a
  design already implemented — the reason review tracking Issues are per page had been
  recorded only as the circumstance that "GitHub does not let a PR's own author approve
  it", so what the requirements document calls the core of the design was written on the
  DesignDoc side as a workaround for a constraint. That account is kept as-is with a
  reference to §1.6 added. It also states explicitly that **WikiCommit supplies the unit
  and nothing about assigning it to a person** (there is no assignee, no priority queue,
  and no reviewer recruitment as a mechanism).

- **Made the site name appear in browser tab and OGP titles** (Issue #679). The
  `quartz.config.yaml` generated by `/wikicommit-init --quartz` now fills
  `pageTitleSuffix` with `" - <repository directory name>"` (the same substitution
  mechanism as `pageTitle`). Quartz's own `Head.tsx` builds `<title>` from just the page's
  frontmatter `title` plus this suffix; `pageTitle` never enters it (it reaches only the
  left sidebar and OGP's `og:site_name`). With the suffix empty, **not only did the top
  page's tab read `Wiki` and nothing more, no page's tab, `og:title`, or `twitter:title`
  carried the site name at all** — sharing any page produced a link card headed `Sources`
  or `山田太郎`. The top page's own `title: "Wiki"` is unchanged (with the suffix it becomes
  `Wiki - <site name>`, which removes the reported symptom).
  **This does not reach existing repositories automatically** (`quartz.config.yaml` is not
  overwritten on re-init). Editing one line by hand gives the same result:

  ```yaml
  pageTitle: "decameron-wiki"
  pageTitleSuffix: " - decameron-wiki"
  ```

  Forgetting the leading space makes the tab read `Wiki- decameron-wiki`. No page
  regeneration is needed (this is a build setting, not something `generated_with` covers).

- **Removed the "Theme:" display from the top page** (Issue #670). The
  `Theme: <config.yml theme>` line on the third row of the site summary block was dropped,
  along with `load_theme()` in `convert_wikilinks.py`, the `wikicommit_theme` frontmatter
  of `content/index.md`, the banner i18n key `siteSummaryTheme`, and the SCSS
  `.wikicommit-site-summary__theme`. The reason is not that it was untranslated but that
  **it was never prose written for readers** — `theme` is a content-scope instruction for
  an LLM (its readers are `wikicommit-generate` Pass 2c and `wikicommit-collect`), it has
  only one value so it reaches every reader in whatever language it was written in, and in
  practice it tends to contain the source-selection policy that Issue #564 split out into
  `.wikicommit/source-policy.md`, putting an instruction to the generator straight onto the
  top page. **The total page count and reviewed count stay** (numbers are
  language-independent and do not have this problem). The `theme` value in `config.yml` is
  not rewritten (it remains valid as a value for the LLM). Nothing is needed for existing
  published sites — `content/index.md` is fully rewritten on every build, so the line
  disappears on the next deploy. Giving readers a site description is the job of the
  follow-up Issue #671; the i18n key was deleted along with everything else so that no
  empty receptacle is left behind (Issue #553).

- Replaced the "Reviewed" display at the wiki's two entrances **with an explanation of the
  state, keeping the number** (Issue #664). The site summary banner on the top page
  (`Reviewed: 0`) and Totals on the overview page (`- **Reviewed**: 0 / 486 (0%)`) were
  designed as a statement of honesty, but to a first-time reader they read as "a project
  nobody cares about", so the same number worked against its intent. The top page also
  links to the overview page, so a reader sees both in sequence. The labels became
  `Human-reviewed` / `人によるレビュー済み`, each with a line under it saying "pages are
  published the moment the LLM generates them; this number is how many of them a person
  has checked". **The number is not hidden** (hiding it would betray the original decision
  to print `Reviewed: 0`). **No call to participate and no link were added** — this wiki
  does not recruit outside reviewers, so it would be an invitation to people who cannot
  accept. The column heading of the per-type table on the overview page was left alone, as
  it is never read on its own.

- **Started showing who reviewed a reviewed page** (Issue #663).
  `review-issue-close-sync.yml` writes the GitHub login of whoever closed the review
  tracking Issue into the `reviewed_by` frontmatter (in the same commit that rewrites
  `review_status`), and `WikiCommitBanner` renders it as a link to that GitHub profile.
  Until now the reviewer survived only as a `Reviewed-by:` commit trailer in git history,
  invisible to a reader of the published site — the `reviewed` badge said a review had
  happened but not whose judgement it was, leaving the top of the trust ladder looking like
  a bare flag. **An existing `reviewed` page without the field falls back to the previous
  display with no reviewer name** (no empty label, no `unknown` — unlike `generated_at` /
  `generated_by` on an unreviewed page, a missing reviewer is a normal state). It is not
  applied retroactively. The field is also absent on route B (`/wikicommit-review` writing
  `reviewed` locally) and in wikis that do not deploy this workflow. **Known limitation**:
  there is no path that clears a `reviewed_by` once written, so if a page reviewed via
  route A returns to `pending` (through `--regenerate` or a manual revert) and is then
  re-reviewed via route B, the previous reviewer's name is still displayed.

- **Unified the "claims of this document" section of the three article types
  (`ScholarlyArticle` / `NewsArticle` / `BlogPosting`) on `## Key Points`, one bullet per
  claim** (Issue #673). Only `ScholarlyArticle` called it `## Key Contributions`, and all
  three ended their instruction with `in list or prose form` (prose was acceptable) — with
  both in place, claims cannot be taken out one at a time from prose, nor searched for
  across types. Two disciplines were added to the bullets themselves: keep to what the
  document states (do not write a date or figure it merely quotes from another document as
  established fact; Issue #473), and where the evidence is narrower than it looks, say so
  in that bullet (a single dataset, a single interview source, the author's own
  experience, a vendor's own product documentation). **No new script or property was
  added** — `build_survey_view.py` already extracts each page's `##` headings
  (Issue #586), so once the heading is uniform the survey mode of `/wikicommit-synthesize`
  can use the section as a cross-page signal. **Pages of these three types generated
  before this change are worth rebuilding**
  (`/wikicommit-generate --regenerate --type ScholarlyArticle`, and so on). Existing
  `## Key Contributions` sections are not rewritten and simply remain.

- Added a `granularity` rule to the `Person.md` type template that **narrows what may be
  written about a living individual** (Issue #668). Keep to what the person has published
  themselves (their writing, their statements, the role they claim), and do not write
  facts that need corroboration from a primary source — career history, affiliations,
  date of birth — even when a source states them. It extends the existing "do not record
  family relationships or physical attributes" rule to where the cost of being wrong is
  highest (Issue #473 — a person page that stated the date and content of an article not
  in its `sources` as established fact). The same caveat was added to `## Background` in
  the body template, because leaving the section instruction as "chronological activities,
  affiliations, and roles" would give opposite instructions within a single file (the same
  shape of contradiction Issue #552 recorded in `TechArticle.md`). **No `properties:` key
  was removed** — `affiliation` / `jobTitle` / `birthDate` remain valid candidates for the
  dead and for historical figures, and anything decided against is dropped key and all by
  the Issue #553 rule that unfillable keys are omitted. **`Person` pages for living
  individuals generated before this change are worth rebuilding**
  (`/wikicommit-generate --regenerate --type Person`). Whether to create the page at all is
  a separate axis, handled by `exclude_living_persons` (off by default) in
  `.wikicommit/entity-policy.md`.

- Added one boundary rule (a `granularity` bullet beginning with `Boundary`) stating what
  the type **is not** to each of the eleven distributed `base_types` templates
  (Issue #550). A type that states its boundary is more likely to be selected, so types
  without one — `HowTo`, `Place`, `Event`, `Book`, `ShortStory` — had been one-sidedly
  losing out. **Type selection tendencies change, but only for new generation; this does
  not reach existing pages even with `--regenerate`** — boundary rules act during type
  selection (Pass 2c), and regeneration takes the existing page's type as given and does
  not run Pass 2c. Reclassifying types remains out of scope.
- Added instructions for writing `granularity` when `wikicommit-generate` Pass 2b adds a
  new type at run time (Issue #552). Beyond what to write, it states explicitly not to
  write anything that contradicts the SKILL.md's own other rules (particularly the
  source-as-entity decision in Pass 2a). The `granularity` of an added type is printed in
  full in the Completion Notice. Existing schema files are unchanged.
- Added guidance for writing about practices and techniques to the `DefinedTerm.md` type
  template (Issue #551). The `granularity` now names three categories — phenomena and
  problems, mechanisms and components, practices and techniques — and the four items that
  matter only for the third (when it applies, its premises, its failure modes, the strength
  of the evidence), and the body template gained a `## When It Applies` section (omitted
  entirely for the other two). **`DefinedTerm` pages about practices and techniques
  generated before this template change are worth rebuilding**
  (`/wikicommit-generate --regenerate --type DefinedTerm`).
- Stated in `HowTo.md`'s `granularity` that a HowTo is still a HowTo when `tool` and
  `supply` are empty (Issue #551), responding to the observation that these two
  properties' recipe/DIY appearance was acting as a reason not to choose `HowTo`. The
  meaning of the type is unchanged, so existing pages need no regeneration.
- Removed `inDefinedTermSet` and `termCode` from `properties:` in the `DefinedTerm.md`
  type template (Issue #553). There was no way for a wiki to supply a conforming value for
  the first (a `DefinedTermSet` entity, or a URL naming one), and the second loses its
  anchor without it, so both stayed in generated pages as empty placeholders nobody could
  fill (in one pilot, 14 of 43 `DefinedTerm` pages carried `inDefinedTermSet` and none had
  a value). The `granularity` names where they go instead — membership in a classification
  scheme goes in `tags`, and the scheme itself is described in the body. **Existing pages'
  `inDefinedTermSet` / `termCode` remain valid keys** (`validate_frontmatter.py` validates
  against Schema.org's `domainIncludes`, not against the template's key list), so no
  retroactive removal is needed — but **`DefinedTerm` pages dealing with a classification
  scheme are worth rebuilding** (`/wikicommit-generate --regenerate --type DefinedTerm`).
- Narrowed the role of `config.yml`'s `theme` to **content scope only** (Issue #564). The
  `/wikicommit-init` prompt now says explicitly "write the subject; do not write which
  sources to use", and the `config.yml` template comment says the same. **A `theme` in an
  existing repository that mixes in source policy is not migrated automatically** — moving
  it by hand into `.wikicommit/source-policy.md` makes it readable on the main route as
  well, and removes the noise from entity exclusion decisions at the same time.
- Step 0 of `/wikicommit-generate` now reads `.wikicommit/source-policy.md` before
  registering a source (Issue #564). An argument that clearly conflicts with the policy
  prompts for confirmation, naming the line it conflicts with (neither registering
  silently nor refusing on its own authority). `/wikicommit-collect` reads the same file in
  Step 2.5 and uses it as a standing filter on candidates (the guidance argument steers a
  single run and does not silently override the standing policy).
- `wikicommit-generate` Pass 2c now follows a type schema's `granularity` when it says
  "defer to another type in this case" (Issue #569). In one pilot, `GovernmentService.md`
  stated "Prefer schema:HowTo when the source's substance is an ordered set of steps..."
  and still produced 6 `GovernmentService` pages and 0 `HowTo` pages, one of which
  reproduced numbered steps verbatim from a household waste manual. **Preference between
  types stays in `granularity`** (no dedicated key — whether to defer is not mechanizable,
  and adding a key would still leave an LLM to evaluate its condition). All four routes
  that write `granularity` (the theme-driven proposal in `wikicommit-init`, the Type
  Proposal in `wikicommit-collect`, Pass 2b, and `wikicommit-schema-propose`) were also
  told to name the type when another installed type is the right home.
- Told Pass 2c explicitly that **one source may yield several entities of different
  types** (Issue #569). A source covering both a thing and the procedure for using it may
  produce both. The waste-disposal case above should have been split into the collection
  service itself (`GovernmentService`) and how to put out bulky waste (`HowTo`).
  **Neither of these two takes effect anywhere but new generation** —
  `/wikicommit-generate --regenerate` does not run Pass 2c and takes the page's type as
  given, so it can neither change an existing page's type nor split one page into two.
  Type reclassification and page splitting/merging remain out of scope (the same call as
  Issues #447 and #565).
- Added two rules to `wikicommit-generate` Pass 3 (Issue #571). **Do not emit a heading
  with nothing under it** — on a 239-character page, two headings each restated the first
  and second half of the opening paragraph. A template's headings describe the shape a
  well-supported page takes; they are not a form to fill in. **Do not write in the body
  what a source failed to cover** — "the tourism site used as a source says nothing about
  its history" is a note about this run, not something for a reader, and belongs in the
  operator-facing run report (`coverage_gap_note` is for an attribute a source **does**
  state with no `properties:` slot to hold it; the meaning is the reverse, so it is not
  reused here). **Notes about the confidence of the content do stay in the body**
  ("the source records this as legend", and so on). **Being a Pass 3 change, it reaches
  existing pages through `--regenerate`.**
- Stated in `wikicommit-generate` Pass 4 step 5 that a human in an interactive run may be
  asked about exceeding `max_retries`, but only while the retries keep producing **a
  different** defect each time (Issue #571). The limit exists to give up on a page that
  never gets fixed, whereas a different defect each round is not a failure to converge but
  review doing its job. A non-interactive run never extends, and neither does a page that
  keeps failing the same way.
- Added instructions to `wikicommit-generate` for tabular sources (CSV/XLSX) (Issue #568).
  **Independence is judged by what the columns say, not by the number of rows** — in prose,
  the depth of a mention proxies for independence, but in a table every row has the same
  depth (one row), so that proxy breaks. A row that carries several attributes of its own
  subject is an independent fact; a row holding a name and a single relation is not. **Do
  not create entity pages from a correspondence table that carries no descriptive
  information** — record the relation with `action: update` if the other side already has a
  page, and write aggregate figures as characterization on the page for the concept the
  table is about (rather than turning rows into prose). The failure shape of transcribing
  a table was also added as an example to the Issue #337 Pass 3 instruction about
  respecting the abstraction level the schema expects. **The transcription fix (Pass 3)
  reaches existing pages through `--regenerate`, but the extraction decisions (Pass 2c) do
  not** — regeneration does not revisit which pages should exist, so an entity page that
  was never created stays uncreated and one that should not exist stays.
- Changed which sources `/wikicommit-generate` collects for processing, and in what order
  (Issue #567). `status: partial` expressed both "some pages failed to generate (a rerun
  might succeed)" and "some entities were excluded for not matching `theme` (the same
  `theme` gives the same answer every time)" with one value, and the latter returns to
  `partial` however many times it runs. **`partial` is now collected only when
  `failed_pages` is non-empty** (no new `status` value was added). The five-item guard's
  selection order also changed so that sources never generated at all (no
  `last_generated_at`) come first — precisely, three tiers: (1) `outdated`, (2) never
  generated, (3) the rest, with `outdated` ahead of the backlog because a changed source
  behind an already-published page means the page is *wrong*, not *missing*. The list of
  what will be processed is now split three ways as well: not yet fetched, fetched but not
  generated, and awaiting reprocessing. Because the collection condition changed, a URL
  source that is `partial` with an empty `failed_pages` loses the "it is already queued"
  premise behind `SKIP`, so `process_url()` in `add_source.py` now returns `RECHECK` for
  that state (otherwise that URL would have no route left for re-checking freshness). In
  one pilot, 8 `partial` sources (all from exclusions, and all behaving exactly as
  intended) held the slots while 23 never-processed sources queued up behind them. **No
  retroactive processing is needed** (a `partial` with an empty `failed_pages` simply stops
  being collected on the next run). A `partial` arising from `ambiguous` likewise falls out
  of collection because `failed_pages` is empty — once the type is settled, rerun with the
  source named explicitly.
- Added a count of "sources registered but never processed" to `/wikicommit-status`
  (Issue #567). These are not failures, only things whose turn has not come, so they are
  reported as a total rather than turned into tracking Issues.
- `wikicommit-generate` Pass 4 now performs **contradiction detection** (Issue #566). The
  design's quality gate table had long listed "contradiction between pages" as a Pass 4
  responsibility, but the implementation only checked one page against that page's own
  `sources`, with no step anywhere that looked at another page. Two things were added:
  (1) **disagreement between sources** — when a page has two or more `sources` that
  disagree, take the one whose document treats that fact as its own subject (a list or
  directory is weaker evidence than a document about that item); (2) **contradictions
  between pages within one WikiLink hop** — up to five existing linked-to and linking-from
  pages are supplied as extra context. When the other page looks like the wrong one, it is
  not a FAIL but a report in the Completion Notice (Pass 4 has neither that page's sources
  nor authority over it). **Contradictions across batches are out of reach** (a
  whole-repository scan is recorded as future work). **Pages with several sources, and
  pages that link to each other, are worth rebuilding.**
- Added a rule to `wikicommit-generate` Pass 2c: when several installed types fit, choose
  the most specific (Issue #565). An ancestor type always fits (writing a park as `Place`
  is not wrong, only coarse), so without instruction the broadly familiar type was picked
  by default. `granularity` in `Place.md` (208 descendant types), `Organization.md` (166),
  and `Event.md` (35) also gained a note about deferring when a more specific type is
  installed. **This takes effect only for new generation and does not reach existing pages
  even with `--regenerate`** — type selection is Pass 2c, and regeneration takes the
  existing type as given. Reclassifying existing pages remains out of scope (it entails
  moving directories and rewriting the Type segment of every WikiLink).
- Added a rule to `wikicommit-generate` Pass 3: re-read a `properties:` value list once it
  is written (Issue #561). When WikiLinks and plain text are mixed within one list, the
  plain-text side must be plain because that entity does not meet the target type's
  independent-subject bar, and **the target page not existing yet is not a reason** (this
  was already forbidden by name, but only as a per-value decision, with no view of the list
  as a whole). **Pages in wikis where one entity is mentioned across several ingests — such
  as stories and government services — are worth rebuilding.**
- Moved the `UNLINKED` finding out of `check_recurring_characters.py` into
  `check_unlinked_entity_mentions.py` (Issue #561). "A name with no page recurring across
  works" (create a page) and "a page exists but is not linked" (make it a link) demand
  opposite actions, so the scripts and their counts were split. The former's `SUMMARY:`
  line is now just `recurring=N`.
- Wrote into the type templates the criteria for promoting a character in a narrative
  source to a `Person` page (Issue #560). The existing rules gave only the conditions for
  *not* creating one, leaving each tale's protagonist buried as plain text in
  `properties.character` (in one pilot, not one protagonist of a hundred tales had a
  `Person` page). `Person.md`'s `granularity` gained "if a work is entirely about that
  person, they are an independent subject (fictional or real is irrelevant)", and the
  `character` line in `ShortStory.md` / `Book.md` gained "if the same name appears in
  another work's page, re-evaluate them as a candidate for their own page". **Promotion is
  limited to at most one page per work plus recurring characters; it does not cover every
  named character. Promotion itself acts only during new generation** — which pages should
  exist is decided by Pass 2c, and regeneration does not run it. The other side (Pass 3
  turning an existing work page's `character` into a WikiLink) does reach existing pages
  through `--regenerate`.
- Added "omit an unfillable `properties:` key rather than leaving it empty" to the page
  generation rules of `wikicommit-generate` Pass 3 (Issue #553). The old wording said only
  "do not copy the template's empty placeholders" and never said what to do with a key
  whose value cannot be determined, so Pass 3 passed it through, neither filling nor
  removing it. A key that already has a value on an existing page is not removed on an
  `action: update` ("this source does not mention it" is not "it is empty").

### Removed

- **Deleted the `review:` block from `config.yml`** (Issue #669). `review.auto_merge` and
  `review.chain_of_thought` had both sat there since the initial Phase 1 design with not
  one place in `.claude/skills/*/SKILL.md` or `.wikicommit/scripts/*.py` reading their
  values (grepping for `auto_merge` finds only GitHub's own `allow_auto_merge`,
  Issue #456, a different thing with a similar name). Removing both empties the block, so
  the block went too. **The harm was not that an unread setting existed but that it misled
  anyone who did read it** — a design discussion that began from "setting
  `auto_merge: false` for the `Person` type will stop auto-merge" did not hold, because
  there is no global gate at all, let alone a per-type branch. The actual merge condition
  is only "every blocking quality check passes". `auto_merge` would introduce a third state
  into the trust ladder (a two-valued design that publishes even at `pending`), so it will
  be designed on its own when it is actually needed. `chain_of_thought` was removed for a
  different reason: the repository has no way to measure review quality, so nobody could
  tell whether enabling it helped, while the cost increase would be certain (the intent is
  recorded in Issue #669). **`config.yml` in an existing repository is not rewritten** (a
  re-init skips `config.yml` wholesale). The values harm nothing since nobody reads them,
  and there is no need to delete them by hand.

### Fixed

- **Stopped the previous reviewer's name from surviving a re-review on route B**
  (Issue #705). There was **no path anywhere that cleared `reviewed_by`** (the GitHub login
  of whoever closed the review tracking Issue; Issue #663), so the following sequence
  published the name of someone who had not seen that version: (1) route A reviews the page
  and attaches `reviewed_by: alice`; (2) `--regenerate` or a manual edit returns
  `review_status` to `pending` (**`reviewed_by: alice` stays**); (3) route B
  (`/wikicommit-review`) re-reviews and rewrites **only** `review_status` to `reviewed`;
  (4) the published page shows alice as the reviewer. `set_frontmatter_field.py` gained
  **`--unset KEY`** (the same line-level operation as `--set`, a no-op when the key is
  absent; a call with `--unset` and no `--set` is accepted), and route B now clears
  `reviewed_by` in the same call that writes `review_status: reviewed`. `--require` applies
  to both `--set` and `--unset` together, so the existing contract that one call is one
  atomic rewrite of one page is unchanged. Regeneration (`--regenerate`) also leaves no
  `reviewed_by`, but without `--unset` — Pass 3 rewrites the whole page, so leaving it out
  of the output is enough. **When the unchanged-output valve keeps `review_status:
  reviewed`, however, `reviewed_by` is kept too** (dropping only the name would break one
  half of the very fact the valve protects: that this is still the version a human
  actually reviewed). Route A (`review-issue-close-sync.yml`) is unchanged, as its
  unconditional `--set` already self-heals. **Existing pages are not corrected
  retroactively** — a page already carrying a stale `reviewed_by` keeps it until route A
  reviews it again or `/wikicommit-fix` corrects it.

- Fixed per-type index lines rendering as a duplicated title on the published site
  (`Adaptive Context Compaction — Adaptive Context Compaction`) (Issue #678).
  `rebuild_index.py` wrote lines as `[[Type/slug]] — {title}` while `convert_wikilinks.py`
  renders a WikiLink using **the target page's `title`**, so the two overlapped. Per-type
  indexes are one of the main entrances for moving around the wiki, and every line of every
  type in every language looked like this. Lines are now bullets, `- [[Type/slug]]`
  (**dropping the suffix alone is not enough** — the lines are consecutive with no blank
  line between them, and the distributed `quartz.config.yaml` ships with `hard-line-breaks`
  disabled, so CommonMark folds them into one paragraph. The suffix happened to be acting
  as the separator, and removing it without a marker would leave the link texts adjacent,
  one space apart, on a single long line. Every other list `convert_wikilinks.py` writes
  already uses `- [{title}]({link})`). `remove_index_entry()` in `remove_page.py` was also
  made to treat the leading list marker as optional so that it matches all three old and
  new line forms. **Losing the readable title when reading the raw Markdown in the
  repository is accepted** — that reader is the operator, not the audience, and the file
  name in the same directory carries the slug. Ordering (slug ascending) and exclusions
  (`status: removed`, missing `title`) are unchanged. **No migration is needed** (each type
  directory is corrected the next time `rebuild_index.py` runs there; run it once with no
  arguments to align every type immediately, and the published site follows on the next
  deploy).

- Fixed the backlink index in `check_wikilinks.py` **coming out empty whenever any
  ancestor directory of the repository was named `assets`** (Issue #677). The script built
  an absolute `entity_dir` while applying the `assets/` exclusion to that full path. What
  was lost is exactly the dangling-WikiLink warning the deletion flow relies on, and
  because **it does not error, only report fewer findings**, `/wikicommit-remove` →
  `/wikicommit-merge` still appears to complete normally. The same walk condition had been
  written out independently in 18 places with the `assets/` test split across three
  different semantics; that was consolidated into `collect_entity_pages()` /
  `is_entity_asset()` in `_wikilink.py` — the correct implementation already existed in
  `build_slug_type_index()` in the same file, where a comment warned about this very
  mistake by name. `assets/` now has the narrowest definition: the single directory
  immediately under `entity/` (`validate_frontmatter.py` and `check_raw_html.py` are not
  migrated, as their subject is "every `.md` on disk"; `generate_overview_page()` in
  `convert_wikilinks.py` moved its type-mismatch test onto the shared
  `other_types_for_slug()`).

- Fixed the two places `/wikicommit-collect` embeds a candidate URL into a CLI argument
  (`check-domain` in step 5 and the license lookup in step 6) to use the heredoc pattern
  (Issue #646; unvalidated free-form text is passed through a heredoc with a quoted
  delimiter). Unquoted, a URL containing `&` (an ordinary permalink such as
  `…/w/index.php?title=X&oldid=1`) is split by the shell, running the first half in the
  background and the second as a command. On the `check-domain` side, the background job's
  exit code of 0 is read as `OK:`, **letting through a domain this wiki decided to
  exclude**.

- Made `check_wikilinks.py` with no arguments cover every page under `.wikicommit/entity/`
  (Issue #571). It previously checked nothing, printed `OK: 0 files checked, 0 errors,
  0 warnings`, and exited 0 — **output indistinguishable from a check that genuinely
  passed**. `wikicommit-merge` always passes `--changed`, so the diff-scoped behaviour is
  unchanged.

- Fixed three `granularity` lines in the type templates that contained `(Issue #NNN)`
  somewhere other than at the end of the line being truncated where YAML read `#` as a
  comment (up to 714 characters were lost in `DefinedTerm.md`). The lines were quoted and a
  regression test was added to `tests/test_schema_template_boundary_rules.py`.

- Made re-running `/wikicommit-init` (which always carries `--no-overwrite` against an
  existing repository) update `.wikicommit/scripts/` (Issue #647). The tree was previously
  skipped wholesale, so installing a newer version of the Skills and re-initializing left
  `.wikicommit/scripts/_version.py` at the version of the first init, and **pages generated
  by the new Skills were stamped with the old version** (`generated_with` /
  `translated_with`). A missing stamp is harmless (Issue #577's "created before this
  feature existed"), but a wrong stamp actively gives the wrong answer to this field's only
  use — cross-referencing this CHANGELOG with `grep` to choose which pages to rebuild. It
  follows the ownership line that `.wikicommit/scripts/` is shared script code the Skills
  call, i.e. a distributed artifact, and so has a different owner from the user files
  `--no-overwrite` protects (`config.yml`, `schema/`, the pages under `entity/`, and the
  configuration files at the repository root). `wikicommit_version` in `config.yml` (the
  version that initialized the repository) is still not updated. Note that **a re-init now
  surfaces a diff under `.wikicommit/scripts/` for committing** (this is intended; review
  and commit it as usual). `.wikicommit/schema/` is still not refreshed (it is the one area
  where direct human editing is allowed). When moving to a version that changed a type
  template, a re-init alone advances the version while leaving the templates behind, and
  pages generated afterwards come from the old templates while carrying the new
  `generated_with`. **For a version that changes type templates, take in the
  `.wikicommit/schema/` diff by hand as well as re-initializing.**

- Deleted the ten development-repository path references left in `.ts` / `.tsx` comments
  under `quartz-plugins/` (paths to the development repository's design documents) and
  rebuilt `wikicommit-explorer`, `wikicommit-properties`, and `wikicommit-sources` so that
  `dist/` matches `src/` (Issue #644; the last layer deliberately left out of scope by
  Issue #549). Those references are untraceable by construction because `docs/` does not
  exist at the destination. Where the design rationale was worth keeping, only the Issue
  number was left; everything else was folded into a sentence or removed. The
  `DEFERRED_DIRS` mechanism of the distributed-path-reference check was removed as well, so
  `quartz-plugins/` is now held to the same `ERROR` rule as every other distributed
  artifact (`deferred=` disappears from `SUMMARY:`). `.map` was added to `TEXT_SUFFIXES` —
  the bundler drops most comments from `dist/*.js` while `.js.map`'s `sourcesContent`
  carries `src/` verbatim, so without scanning `.map` a "fixed `src/` but forgot to
  rebuild" passes silently (of the ten references here, all appeared in the `.map` of all
  three plugins but survived in the `dist/*.js` of only one).

## [0.1.0] - 2026-08-29

The first entry, marking the introduction of version numbers to WikiCommit (Issue #577).
Changes before this point had neither a `git tag` nor a version string, so they are not
recorded here.

### Added

- Defined WikiCommit's own version `0.1.0`. There are two sources of truth:
  `.wikicommit/scripts/_version.py` (which reaches the installation) and `version` in
  `.claude-plugin/plugin.json` (which Claude Code's plugin mechanism reads).
- `/wikicommit-init` now stamps `wikicommit_version` into `.wikicommit/config.yml`
  (a record of which version initialized that repository).
- `/wikicommit-generate` and `/wikicommit-synthesize` now write `generated_with` into a
  generated page's frontmatter, and `/wikicommit-translate` writes `translated_with` into
  a translation page (a record of which version generated or translated that page).
- `validate_frontmatter.py` now validates `generated_with` / `translated_with` (optional
  fields; an empty string is an ERROR only when the field is present).
- Added this file (`CHANGELOG.md`).

### Notes

- No type template or page generation rule changed in this version. **There is therefore
  no need to regenerate existing pages for this version.**
- Nothing is applied retroactively to existing wiki repositories or existing pages. A
  missing `wikicommit_version` / `generated_with` / `translated_with` means "created
  before this feature existed".
