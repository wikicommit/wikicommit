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

**Which changes get an entry** (Issue #1016). A change gets one when a user could notice
it: when it alters what a distributed Skill or script does or prints, what the published
site shows, or the shape of a file WikiCommit writes into the wiki, or when it adds a file
that reaches the wiki repository. Where it arrives from does not matter — a fix inside
`quartz-plugins/` counts as much as a Skill change, because `/wikicommit-update` carries
it into every existing wiki and the site changes the next time it builds. A change goes
without an entry only when nothing a user runs or reads behaves differently: comments,
tests, a refactor with identical output, a rebuilt `dist/` that follows a source change
already entered. **When unsure, write it** — a missing line is the failure this file
exists to prevent, while an extra one costs a moment's reading. **Write the entry in the
change that makes it, not at release time**: after a release, `[Unreleased]` is the only
list of what the next version carries, and a line left for later is a line nobody writes.
In the development repository a check fails a pull request that changes the distributed
Skills without touching this file (Issue #1029); a change that needs no entry says so with
the commit trailer `Changelog: none — <reason>`, and the reason may not be empty.

This file is kept in two places and **the two copies must match exactly**
(`tests/test_changelog_sync.py` enforces this in CI). The repository root is the copy you
edit; `.claude/skills/wikicommit-init/CHANGELOG.md` is its duplicate. The duplicate is
needed because neither `install.sh` nor `npx skills add` carries anything outside a Skill
directory, so **without it this file never reaches the user's wiki repository at all** —
and the Skill tree is exactly where `/wikicommit-update` reads "what changed since the
version I last synced with". The same applies to `changelog/`, which is duplicated
alongside it; `install.sh` walks a Skill directory with `find -type f`, so the
subdirectory travels without any change to that script.

**One released version lives here; every earlier one lives in `changelog/<version>.md`**
(Issue #801). A reader — and `/wikicommit-update` — should open only the versions between
theirs and the latest, and this file used to make that impossible: the whole history sat
in one place, so a user one version behind read exactly as much as a user ten versions
behind. Rotating on every release keeps what is read proportional to how far behind the
reader is, and keeps this file bounded rather than growing without limit. The index at the
bottom is the map, and `tests/test_changelog_structure.py` holds all of it together.

**This file is written in English, and English is the canonical version** (Issue #772).
Like the SKILL.md files (Issue #154) and the console output of the distributed scripts
(Issue #770), it is a distributed artifact, and this project's public surface is
English-first.

**Do not write `docs/`, `Issues/`, or `dev/` paths in this file.** As described above it
travels all the way to the user's wiki repository, and none of those directories are
reachable from there, so such a reference is untraceable by construction
(`tools/check_distributed_path_refs.py` stops this in CI). To record design rationale,
**write the Issue number alone**, or fold the point into a sentence.

When bumping the version, update all five of these together (`tests/test_version_sync.py`
enforces that 1 and 2 agree; `tests/test_changelog_sync.py` enforces that 3, 4 and 5 do;
`tests/test_changelog_structure.py` enforces that 5 actually happened):

1. `VERSION` in `.claude/skills/wikicommit-init/scripts/templates/scripts/_version.py`
2. `version` in `.claude-plugin/plugin.json`
3. A new entry in this file
4. `.claude/skills/wikicommit-init/CHANGELOG.md` (the copy of this file)
5. **Rotate**: move the previously released entry out to `changelog/<version>.md`, add its
   row to the index at the bottom, and copy both into the Skill tree. This happens on every
   release rather than occasionally, which is why it is a numbered step and not a note.

**Not `pyproject.toml`.** Its `version` declares this development repository's own Python
package (the test/lint dependencies) and is deliberately never synced with the five above,
so it sits well behind them — see the comment at the top of that file and `_version.py`'s
docstring (Issue #577 / #799). Leave it alone.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
version numbers follow [Semantic Versioning](https://semver.org/). **The entry format is
Keep a Changelog's; only the storage is split** across `changelog/<version>.md` — the same
deviation Django and Node.js make, for the same reason. Do not "restore" it to one file.

## [Unreleased]

## [0.12.0] - 2026-10-22

### Added

- **A wiki can use its own image for link cards** (Issue #1371). Since the `og-image`
  plugin was dropped, every page shared on social media or in a chat showed the Quartz
  logo as its card image. Put a PNG at `.wikicommit/assets/og-image.png` (1200x630 suits
  most sites) and the GitHub Pages deploy now copies it over Quartz's
  `static/og-image.png` after the build, so every page's card shows it; the `quartz/`
  submodule is not touched. Without the file nothing changes and the card stays the
  Quartz logo. Only the published site is affected — a local preview still shows the
  Quartz logo. No default image is shipped. Existing wikis get the step through
  `/wikicommit-update` (`.github/workflows/deploy.yml`).
- **A check that measures how much of a page repeats its source's wording**
  (`check_source_overlap.py`, Issue #1380). It counts the share of a page's words that sit
  in a run of six or more words (twelve characters on a Japanese or Chinese page) also
  found in the extracted text of the page's sources, leaving out quotations, code,
  blockquotes, tables and `## Generation Notes`, and reports a page over 20% with its
  share and longest copied run (`OVERLAP:`). The review against the sources checks that a
  page is faithful to them, so a page that copies them passes it, and nothing found copied
  wording before. `/wikicommit-generate` (and `--regenerate`) runs it over the pages it
  wrote and lists them in the Completion Notice; `/wikicommit-merge` runs it over the
  changed pages as a warning that never blocks. A page none of whose sources has
  extracted text on the machine (the cache is gitignored) is reported as `NO_SOURCE_TEXT`
  rather than passed — in `/wikicommit-merge` as a count in the notes, not a warning — and
  a page written from a source in another language is skipped. The threshold was set by
  measuring three wikis: pages written under the own-words rule above measured 0–11%, the
  same pages under the earlier rules 20–37%.

### Changed

- **`/wikicommit-merge` leaves out pages `/wikicommit-generate` wrote that no AI review
  has judged** (Issue #1328). Before anything is checked or committed, a new step looks
  at the changed entity pages that generate wrote (their `generated_at`,
  `generated_by` or `generated_with` differs from the last commit, or the page is new) and
  holds back each one that no AI review record judges as it now stands — the same reading
  as `check_review_coverage.py`'s `UNREVIEWED:` and `STALE_REVIEW:`. A source management
  file whose `generated_pages` names a held-back page is held back with it. Both stay in
  the working tree, uncommitted, get no review tracking Issue, and are listed in the run's
  notes, the PR body ("Not included") and the completion report;
  `/wikicommit-generate --regenerate <page>` reviews such a page so the next merge carries
  it. Pages fixed with `/wikicommit-fix`, written by hand or translated are never held
  back. Today generate writes a page only after its review passes, so this normally holds
  back nothing; it keeps what is published reviewed when generate stops writing pages
  only after review.
- **`/wikicommit-generate` no longer takes a type approved in the same answer for an
  entity whose type was ambiguous** (Issue #1378). When you answer the deferred questions,
  an entity whose type could not be settled can be given one of its candidate types or a
  type already installed; a type you approve in that same answer is refused for it, with
  a reason, and you give that entity its type in the next run. The type's file is written
  only when the source that proposed it is processed again, and nothing made that happen
  first, so the entity's page could be generated without the type file.
- **`/wikicommit-merge` leaves a PR for a person when the default branch requires a
  review** (Issue #1377). A PR blocked on a required review used to end the run as
  failed, with a cleanup that told you to close the PR and delete its branch, and no
  review tracking Issue was ever filed for its pages. Now, once no required status check is
  still running or failed and GitHub reports the review as required, the run finishes as
  `awaiting-merge` with the PR left open and the default branch checked out. After a
  person merges the PR on GitHub, run `/wikicommit-merge` again: it finds the merged PR in
  its run records, pulls the default branch and files the review tracking Issues (and any
  generation-failure Issues) even when there is nothing new to merge; while the PR is
  still open it says so (`AWAITING_MERGE:`). A `BLOCKED` PR whose required checks are
  still running is now waited on instead of failed at once.
- **Closing a review tracking Issue reaches `reviewed` when the default branch requires a
  review** (Issue #1396). The PR that `review-issue-close-sync.yml` opens to mark the page
  `reviewed` was blocked by the required review too, and the workflow failed, leaving the
  page `pending` and the PR open with nobody told. Now, once no required check is still
  running or failed, a PR blocked on a required review is left open and the workflow
  comments on the Issue with a link to it: approve and merge it, and the page becomes
  `reviewed` and the published site is rebuilt by `deploy.yml` on that push. The PR is
  opened by `github-actions[bot]`, so the person who closed the Issue can approve it
  themselves. A required check that never starts — a `pull_request` workflow does not run
  for a PR opened by GitHub Actions — is named in the comment instead of being waited on
  for five minutes; close and reopen the PR yourself to run it. Existing wikis get the
  change through `/wikicommit-update` (`.github/workflows/review-issue-close-sync.yml`).
- **A GitHub repository's top page is fetched as its README** (Issue #1374). For a URL
  of the form `github.com/<owner>/<repo>`, `add_source.py --fetch-url` now fetches the
  README's raw text from `raw.githubusercontent.com` instead of the rendered page, and
  that text is what `source.hash` is taken from and what generation reads. The rendered
  page carries star, fork and commit counts and each file's last commit, so its hash
  changed on nearly every fetch even when the README had not, which made a forced
  recheck rerun Passes 2–4 every time and stopped `--regenerate`. Other GitHub URLs
  (`blob`, `tree`, issues, pull requests) and every other host are fetched as before. If
  the repository has no README the rendered page is fetched instead; any other failure
  (a rate limit, a 5xx) is reported as an error rather than falling back, so the same
  source never hashes differently depending on which route worked. Registering such a URL
  says so once. **The first recheck after upgrading reports every repository-top source
  as changed and regenerates its pages once.** Facts that only the page's sidebar shows
  (the license badge, the description, topics) are not in the README; register the
  repository's `LICENSE` file as a separate source if a page needs the license.
- **A paper's own account of its versions is checked as a claim, not as a missing
  document** (Issue #1373). When a source says what it is a version of or where it was
  published ("an extended version of *Title*, published at Venue '26", "accepted at",
  "to appear in", "the camera-ready version for") and the page repeats that as the
  source's bibliography, the review against the sources now checks it as an ordinary
  claim (check 1) and passes it if the source states it — even when the other version is
  named by title and date, and even when the source says so only in a footnote or a
  running head. Before, the generation review passed such a sentence while
  `/wikicommit-review` could fail it as a cited document the wiki does not hold
  (`MISSING_SOURCE`), so the same page passed or failed depending on which review read it.
  A page that takes a finding from the other version ("the conference version found …")
  still fails as before (`review-rules.md` `rules_version` 12). Run `/wikicommit-update`
  so the wiki has the new `review-rules.md`; no page needs regenerating.
- **A translation copies the source's declared `keywords` unchanged** (Issue #1372).
  `properties.keywords` holds the list the source declares about itself, in the source's
  own wording, and the published page shows it among the bibliographic fields, so
  `/wikicommit-translate` now copies it entry for entry from the original page instead of
  translating it, the same way a paper's title is not translated; subject terms in the
  target language stay in `tags:`. The review of a translation (`translate-check`) now
  fails an entry that is translated, reworded, dropped, added or reordered
  (`review-rules.md` `rules_version` 11). Translations made earlier carry translated
  entries and do not show up as `STALE`, since their original pages have not changed: to
  fix them, list the translation pages that have a `keywords` value
  (`grep -rl '^  keywords:' .wikicommit/entity/<target language>/`) and re-run
  `/wikicommit-translate <original page> --lang <target language>` for the page each one's
  `translated_from` names — single-page mode re-translates whether or not the pair is stale.
  Run `/wikicommit-update` first so the wiki has the new `review-rules.md`.
- **An edition of a recurring event is related to the event's own page as broader, not
  series** (Issue #1370). When a page with a year collides with a page carrying the bare
  name, `/wikicommit-relate` now asks what the bare-name page is about: one edition whose
  name lacks the year is still a series, but a page about the whole that recurs (a
  recurring event's own page) is the broader page, and the Skill proposes broader —
  series would rename the event's page with a year. Pass 2c of `/wikicommit-generate`
  still qualifies the edition by its year and keeps the bare name as an alias, and now
  notes in `## Generation Notes` and the Completion Notice that the existing page is the
  event's own page, to be related as broader.
- **View pages are written by the same writing rules as entity pages, and open by
  answering their kind's question** (Issue #1381). The writing rules every entity page
  follows (lead, own words, main point first, headings, tables, examples, terms, reported
  findings) now live in one file, `wikicommit-generate`'s `references/writing-rules.md`;
  Pass 3 reads them from there with the wording unchanged, and `/wikicommit-synthesize`
  Step 5 reads the same file, with "the source" read as the grounding pages. Step 5 adds
  the rules only a view page needs: the subject is never the grounding pages (no "Several
  pages in this wiki…" opening, no page as the subject of a sentence), every case is
  named, the lead does not turn what holds for some cases into what holds for all, facts
  that appear only in a grounding page's frontmatter (such as an author list) are not
  used — the review sees only the bodies, so they failed the page — and the opening
  answers the kind's own question (a `pattern` opens with the shape and the names of its
  cases). The kind table gains that question and fuller Boundaries (a `comparison`'s
  axes, how a `pattern`'s shape may be named, no running-prose `timeline` and no
  estimated dates, nothing in a `debate` that settles it), and a Boundary every view page
  keeps: a juxtaposition that plainly implies a conclusion no grounding page states.
  `.wikicommit/review-rules.md` (`rules_version` 10) checks all of these in check 9,
  including the shared one on a page with no kind. The survey now proposes a kind only
  when the opening question it would have to answer can already be answered, so angles
  stop defaulting to `comparison`. `wikicommit-synthesize` now needs `wikicommit-generate`
  installed alongside it. Existing view pages are unchanged.
- **A review record that says a round failed must carry what that round found, and every
  record names the model that wrote the page** (Issue #1384). `record_review.py` now
  refuses a record in which a round that failed — every round before the last, and the
  last too under `result: discarded` — has no finding of its own (one whose
  `page_at_fault` is not `other`): a retry only follows a failed review, so such a call
  has dropped that round,
  and a record cannot be corrected once written — in the pilot wikis 75 records had lost
  their findings this way, and `wikicommit-status` listed those pages for a person to read
  with nothing to say what to look for. Records also gain `generated_by`, copied from the
  page's own `generated_by` (`translated_by` for a translation), beside `model`, the model
  that reviewed it — so a model whose pages draw few findings can be told apart from one
  whose reviews are lenient. A discarded page has no `generated_by`. Existing records are
  unchanged and still read.
- **Generated pages are written in their own words, and `## Key Points` keeps to the
  main claims** (Issue #1379). Measured against their source articles, generated pages
  carried the source's sentences and turns of phrase without quotation marks (12–37% of a
  BlogPosting page's words sat in runs of six or more words shared with the source), and
  their Key Points followed the source's order point by point. A new Pass 3 writing rule
  for every type says: write in your own sentences; do not carry a run of more than about
  six of the source's words into the body unquoted; quote only wording that matters (a
  coined term or definition, a claim whose exact words are the point), briefly, in
  quotation marks and attributed; names, terms, figures and code do not count; order the
  body by what the reader needs (the type's reader questions or headings, what most
  readers need first), not by the source's sections; and keep every
  qualifier when rewording. The `## Key Points` instruction in `ScholarlyArticle`,
  `NewsArticle` and `BlogPosting` now asks for at most seven bullets, ordered by
  importance rather than by where the source raises them. `BlogPosting`'s granularity line
  "not restate it verbatim" is removed (the common rule replaces it), and in
  `ScholarlyArticle` and `NewsArticle` "not restate the full abstract/article verbatim"
  becomes "not walk through the full abstract/article". Existing pages are unchanged until
  regenerated; `--regenerate --type BlogPosting` (and the other two types) applies both
  rules.

- **`/wikicommit-generate` asks for the type of an ambiguous entity at the end of the run
  and writes it in the same run** (Issue #1235). An entity whose type could not be settled
  used to be listed in the Completion Notice and left for `/wikicommit-reconcile --source`
  or a named re-run, which read the source again and came back just as unsure. Now, in an
  interactive run, the question asked once every source has been through the passes also
  asks for the type of each such entity; a source whose entities were given a type goes
  through the passes again straight away, with the answer handed to entity extraction, and
  the page is written in that run. The source is still recorded as `partial` with
  `ambiguous_entities` until then, so a `--non-interactive` run, an answer of "later" or a
  run that stops part-way leaves it exactly as before.
- **`Person`: a living person whom a work of fiction portrays gets no page while the work is
  the only source** (Issue #1341). The rule for a real person a work refers to used to allow
  a page holding only the work's portrayal, which clashed with the rule that a living
  person's page carries only what they made public themselves. For a living person the
  portrayal now stays on the work's own page, where it tells its characters; the person's
  page is created once a source about them comes in, and the portrayal is added to it then
  as a section framed as the work's. Historical figures are unchanged. Whether a living
  person gets a page at all is still decided by `.wikicommit/entity-policy.md`. Accept the
  template change through `/wikicommit-update`. A page already generated for a living person
  from a work alone is not removed for you; remove it with `/wikicommit-remove` if you want
  it gone. `Book` and `ShortStory` now list such a person in `character` as plain text
  rather than linking a page that is not created yet.
- **A source language written with a region or script is counted under its language**
  (Issue #1247). A management file's `source.lang` written as `zh-Hans` or `pt-BR` used to
  appear on the public source page and the overview page's per-language table as
  `zh-hans` / `pt-br`, a row apart from `zh` / `pt`. Only the leading language subtag is now
  shown and counted (`zh`, `pt`). A value that still is not one two-letter code — a language
  name such as `japanese`, or a list such as `ja, en` — shows no language line on the source
  page and is counted as not recorded (or not processed yet) on the overview page, like a
  non-string value already was. Existing management files need no change.
- **Three messages no longer cite development tracker numbers** (Issue #1376). The
  `--help` of `init.py --update-theme` and of `add_source.py --fetch-url`, and the `ERROR:`
  that `add_source.py --check-path-cache` / `--path-cache-path` print for a management file
  outside `.wikicommit/source/path/`, carried issue numbers a user cannot look up. They now
  give only the reason (the `ERROR:` calls the tree a legacy `.wikicommit/ingest/` tree).

### Notes

- **Six distributed type templates changed, and so did the page generation rules**
  (Issues #1341, #1379, #1381, above). `Person`, `Book` and `ShortStory` changed how a
  living person portrayed in a work is handled; `ScholarlyArticle`, `NewsArticle` and
  `BlogPosting` changed their `## Key Points` instruction. Every type is now written by the
  own-words rule, and view pages by the same writing rules as entity pages.
  `.wikicommit/review-rules.md` is at `rules_version` 12 (Issues #1372, #1373, #1381).
  `/wikicommit-update` shows each type file's difference and applies only what you accept.
  Existing pages keep their shape until regenerated; regenerate the types or pages you are
  about to review rather than the whole wiki.
- **Run `/wikicommit-update` and merge its PR before generating again.** Until it is
  merged, Pass 4, `/wikicommit-review` and `/wikicommit-translate` keep reviewing with the
  wiki's older `review-rules.md`, and nothing says so. The update also brings the changed
  `.github/workflows/deploy.yml` (Issue #1371) and
  `.github/workflows/review-issue-close-sync.yml` (Issue #1396).
- **The first recheck after upgrading regenerates every source that is a GitHub
  repository's top page, once** (Issue #1374), because its hash is now taken from the
  README rather than the rendered page.
- **Things the update does not do for you**, each described above: re-translate
  translation pages whose `keywords` were translated (Issue #1372), and put an image at
  `.wikicommit/assets/og-image.png` if you want your own link card image (Issue #1371).
- **No new Skills**, but `/wikicommit-synthesize` now needs `/wikicommit-generate`
  installed alongside it (Issue #1381). `npx skills add` brings the changed Skill files.

## Earlier versions

One file per version, moved here as each new release lands so that this file stays
bounded and a reader only opens the versions between theirs and the latest.

| Version | Date | Entry |
|---|---|---|
| 0.11.0 | 2026-10-17 | [changelog/0.11.0.md](changelog/0.11.0.md) |
| 0.10.0 | 2026-10-08 | [changelog/0.10.0.md](changelog/0.10.0.md) |
| 0.9.0 | 2026-10-03 | [changelog/0.9.0.md](changelog/0.9.0.md) |
| 0.8.0 | 2026-09-26 | [changelog/0.8.0.md](changelog/0.8.0.md) |
| 0.7.0 | 2026-09-19 | [changelog/0.7.0.md](changelog/0.7.0.md) |
| 0.6.1 | 2026-09-15 | [changelog/0.6.1.md](changelog/0.6.1.md) |
| 0.6.0 | 2026-09-14 | [changelog/0.6.0.md](changelog/0.6.0.md) |
| 0.5.0 | 2026-09-09 | [changelog/0.5.0.md](changelog/0.5.0.md) |
| 0.4.0 | 2026-09-07 | [changelog/0.4.0.md](changelog/0.4.0.md) |
| 0.3.0 | 2026-09-06 | [changelog/0.3.0.md](changelog/0.3.0.md) |
| 0.2.0 | 2026-09-01 | [changelog/0.2.0.md](changelog/0.2.0.md) |
| 0.1.0 | 2026-08-29 | [changelog/0.1.0.md](changelog/0.1.0.md) |
