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

## [0.9.0] - 2026-10-03

### Added

- **The published site now carries `llms.txt`, an index for AIs that have not cloned the
  wiki** (Issue #1117). `/wikicommit-ask` and `/wikicommit-search` need a checkout, so an
  AI working elsewhere could only be handed page URLs one at a time. `convert_wikilinks.py`
  now writes `content/llms.txt` at build time (never committed), which Quartz publishes as
  `https://<site>/llms.txt`: the site name, the primary language's `site_description`, one
  paragraph on how pages are generated and checked, the Type folders with page counts, the
  50 most linked-to pages of the primary language with their `properties.description`, and
  links to the overview and source list. Links point at the published HTML pages, built
  from `baseUrl` in `quartz.config.yaml`. No `llms-full.txt` is written. Nothing to
  configure; it appears on the next deploy.
- **`/wikicommit-organize <Type>` — sort a Type's pages into groups without rewriting any
  page** (Issue #1035). A large Type (DefinedTerm passes 40 pages) was one long list in its
  index and in the site's left pane. The new Skill proposes groups from each page's title,
  description and headings; a person approves or changes them; the grouping is written to
  `.wikicommit/groups/<Type>.yml` (one file per Type, page slugs, so it covers every
  language; labels per language) and opened as a pull request that is not auto-merged.
  **No page changes**, so grouping sends no `reviewed` page back to `pending`. Once merged,
  the Type's `index.md` is split under one heading per group with an unclassified heading
  last, and the Explorer shows each group as a folder inside the Type folder — page URLs do
  not change. New pages are not placed automatically; they wait as unclassified.
  `check_groups.py` and `_groups.py` are new in `.wikicommit/scripts/`; `rebuild_index.py`
  and `convert_wikilinks.py` read the group file (the latter publishes
  `wikicommit-groups.json` beside the content index, only when a group file exists), and
  `/wikicommit-status` adds an "Unclassified grouped pages" row for Types that have a group
  file. A wiki with no group file builds exactly as before. It is a writing Skill and never
  starts on its own (`disable-model-invocation: true`, and
  `policy.allow_implicit_invocation: false` for Codex).
- **`/wikicommit-relate` — decide with a person how pages relate, and record it**
  (Issue #1095). Two sources that call one concept by different names produce two pages,
  and nothing could record a person's decision about them. The new Skill puts each group
  of pages to a person — the same concept, one inside the other, related, or distinct —
  and appends the answer to `.wikicommit/relations.yml`, keyed by `<Type>/<slug>`. Run
  with no argument it works through the name collisions found in the wiki. It does not
  edit pages: a "same" decision is recorded for a later merge. It is a writing Skill and
  never starts on its own (`disable-model-invocation: true`, and
  `policy.allow_implicit_invocation: false` for Codex).
- **`/wikicommit-status` reports name collisions** (Issue #1095) — pages whose title or
  alias another page also answers to, from the new `check_name_collisions.py`. A pair
  recorded with `/wikicommit-relate`, in any relation, is not reported again. The row does
  not gate the healthy verdict. `/wikicommit-merge` now commits `.wikicommit/relations.yml`,
  and `record_relation.py` is new in `.wikicommit/scripts/`.
- **Merge pages a person decided are the same:
  `/wikicommit-generate --regenerate <page> --merge <page> [...]`** (Issue #1119). The
  first page is kept and rebuilt from the sources of every page merged into it, reviewed
  against all of them, and takes over the other pages' titles and aliases (and their
  translations' titles) as its own `aliases`. Once it passes review the other pages and
  their translations are taken down (`removed_reason: merged`, `merged_into`), every
  WikiLink to them is rewritten to the kept page, and the merge is appended to
  `.wikicommit/relations.yml` with the names carried over. The merge is refused unless a
  `same` decision recorded with `/wikicommit-relate` names the pages. The names carried
  over rest on that decision rather than on a source, so review does not check them as
  added aliases, and the one-alias-per-language limit does not apply to them. The merged
  pages' URLs stop working on the published site (their names still redirect, as aliases
  of the kept page); open review-tracking Issues for them are left for you to close after
  `/wikicommit-merge`. New in `.wikicommit/scripts/`: `merge_pages.py` and
  `rewrite_merged_links.py`.
- **Record editions of one series with `/wikicommit-relate`, and qualify their names by
  year** (Issue #1120). A new relation, `series`, records pages that are editions of one
  series — a yearly report, a numbered volume — in series order. The series itself gets no
  page. Before recording, each edition is renamed to the same rule: the slug ends in
  `-<year>` and the title in `（<year>）` (Japanese, Chinese) or `(<year>)` after a space (other
  languages), with the person's agreement. A rename carries the page's translations, the
  links to it, the source files' `generated_pages` and the type indexes along; the old
  slug is taken down as merged into the new one, and its URL stops working on the
  published site. A renamed page and its translations go back to `review_status: pending`,
  because the title changed. When a source is a new edition of a series the wiki already
  has, generation now qualifies the new page by year in the same way and keeps the bare
  series name as an alias, so the older page shows up as a name collision until it is
  qualified. New in `.wikicommit/scripts/`: `rename_page.py`.

### Changed

- **The global graph labels at most 40 nodes on screen instead of following the zoom
  alone** (Issue #1128). On a 1000-page wiki the default zoom filled the screen with text,
  and every zoom in between drew all labels half transparent. Now, while nothing is
  hovered, the global graph labels every node on screen if there are at most
  `labelLimit` of them, and otherwise the best-connected `labelLimit` (pages first; tag
  and source nodes only fill slots left over), each at full opacity and the rest not at
  all. Hovering works as before. A new "Labels on screen" input next to the degree bounds
  changes the limit without re-laying out the graph; the value is kept in the browser
  until Reset, which returns to `globalGraph.labelLimit` in `quartz.config.yaml` (default
  40; `0` restores the zoom rule). The local graph is unchanged, and `opacityScale` now
  only matters there and when `labelLimit` is `0`. Arrives with the next
  `/wikicommit-update`.

- **`/wikicommit-review` and `/wikicommit-fix` now keep a URL fetch as the cache when it
  is the version `/wikicommit-generate` expects** (Issue #1137). On a fresh clone they
  re-fetch every URL source into `.wikicommit/.cache/refetch/`, and that fetch used to be
  left there, so ask, review, fix and generate each fetched the same source again. After
  fetching, both Skills now run `resolve_source_cache_path.py --settle`, the step
  `/wikicommit-ask --include-source` already takes: a fetch whose hash matches the source
  management file's `source.hash` moves into the cache, and any other fetch is read once
  and deleted. The management file is never written. `/wikicommit-review` takes its
  "checked against a different version" note from the same step.

- **A generation-failure Issue for a source that failed before any page was attempted now
  says how to close it** (Issue #1132). `/wikicommit-merge` opens these Issues for
  `status: failed` sources too, but their body only described the `failed_pages` route, which
  does not apply when no page was tried. The body now offers two routes: for a temporary
  failure, set `status` back to `pending` and re-run the source by name; for a URL source that
  cannot be fetched at all, delete the management file and record the URL in `rejected:` (or
  the host in `exclude_domains:`) in `.wikicommit/source-policy.md`. A failed re-check of a
  source that already built pages keeps its management file: it is re-run by name without
  going back to `pending` (which would rebuild every page from the cached copy), or set back to
  `status: generated` if it cannot be fetched at all. A repository file that cannot be extracted is repaired, replaced or
  removed instead. Closing the Issue without one of these does not keep it closed — the next
  `/wikicommit-merge` opens it again.

- **`expires_at` no longer takes a deadline from a document's own history, and a past date is
  reported** (Issue #1130). A report's "governments were asked to send comments by 14 November
  2025" went into `expires_at`, so a page generated in 2026 was EXPIRED in `/wikicommit-status`
  from the moment it was written. The generation rule for `expires_at` (all types) now says the
  date must be when what the page tells its reader goes stale: a deadline the reader acts on (an
  application deadline, a validity period) still counts; a deadline addressed to someone else
  (comments, replies or submissions requested from third parties, a meeting date) does not.
  `validate_frontmatter.py` also prints a WARNING — never an ERROR — when `expires_at` is on or
  before the page's `generated_at`; it shows up at `/wikicommit-merge`. Existing pages are not
  changed, and `/wikicommit-generate --regenerate` keeps a page's `expires_at` as it is, so
  remove such a date by hand (the WARNING names the page whenever it is validated).

- **`/wikicommit-ask --include-source` now fetches a URL source that has no cache**
  (Issue #1036). The cache is gitignored and per machine, so on a fresh clone — every Claude
  Code on the web session — it was always empty and URL sources were always left out. Ask now
  fetches the source with the same fetcher `/wikicommit-generate` uses (after the same
  missing-package check) and compares it with two hashes: the page's own `sources[].hash`
  decides whether it is used without a note, and the source management file's `source.hash`
  decides whether it is kept as the cache, so the next ask and `/wikicommit-generate` find
  it. A fetch that matches neither is used once, with a note, and then deleted. The
  management file is never written. No network access is reported as an environment
  problem, separately from a failed fetch, and stops the remaining fetches for that answer.
  `resolve_source_cache_path.py` now prints `UNREGISTERED:` or `NO_CACHE:` when it exits 1
  (the exit code is unchanged) and has a new `--settle` mode.
- **`/wikicommit-translate` now checks each translation with a separate reviewer and records
  it** (Issue #1031). The quality check used to be the same model re-reading its own
  translation in the same context, and it left no record. A review subagent now compares
  the translation against the source page — and only the source page, not the source
  page's own sources — following the new `translate-check` section of
  `.wikicommit/review-rules.md` (`rules_version` 6): an omission from the original fails
  on this path, as do additions, meaning drift, a broken WikiLink slug or `properties:`
  key, and a term rendered differently from the target-language glossary. The verdict is
  written to `.wikicommit/review/` as `stage: translate-check`, so checked translations no
  longer fill `/wikicommit-status`'s unreviewed list. **A translation that still fails
  after `generate.max_retries` retries is now not written at all** — before, it was
  written anyway with a warning. A new pair stays untranslated and a stale pair keeps its
  old translation until a later run succeeds; the completion report lists them. The run
  stops at the start when `.wikicommit/review-rules.md` is missing — run
  `/wikicommit-init --no-overwrite`. On the published site these checks are shown as
  "checked against the original page", never counted as "checked against sources": the
  banner says so, the front page's per-language counts leave them out, and the overview
  replaces its "no check recorded" line for translations with a checked count once any
  translation carries a record. Translations made before this change have no record and
  get one the next time they are re-translated.
- **A server that stops answering no longer hangs a fetch, and a server that cuts off is no
  longer mistaken for a missing network** (Issue #1038). `add_source.py --fetch-url` had no
  timeout at all, so a server that sent its headers and then stopped held the run until the
  harness gave up, with nothing recorded; every request now gets 15 seconds to connect and
  60 seconds per read. A read timeout, and a server that closed or reset the connection
  after receiving the request, used to come back as `NETWORK_UNAVAILABLE:` — deferring the
  source and, twice in a row, stopping the run as if there were no network. Both now come
  back as `ERROR:`, a problem with that source. The one shape that cannot be told apart —
  a proxy resetting an https connection looks exactly like a server cutting off — stays
  `NETWORK_UNAVAILABLE:` when a proxy is in effect for the URL. So does a connection reset
  during the https handshake — a firewall or sandbox that accepts the connection and then
  drops it — since no request has been sent yet.
- **An update whose page has a source that cannot be fetched is now deferred, not guessed
  at** (Issue #1068). Pass 4 reviews a page against all of its sources, and for a page being
  updated some of those were taken in by earlier runs; on a fresh clone their text has to be
  fetched again, and when that failed there was no rule — runs marked the source
  `excluded` (which drops it from the queue for good), deferred it without a defined reason,
  or reviewed against a different document and deleted a statement. `/wikicommit-generate`
  now fetches those sources at the end of entity extraction, before any page is written. If
  one returns an error (403, 404, a proxy's 502), nothing from the new source is written and
  the source is deferred with a `## Deferred Reason` naming the page and the source — reset
  to `status: pending` when it came from a forced recheck, so the update is not lost. A
  source that reaches no server at all (`NETWORK_UNAVAILABLE:`) is deferred the same way, and
  counts toward the same limit as in text extraction: two in a row stop the run. A
  `type: manual` source has no text to fetch and never defers a page. A hash
  that differs from the page's record is not a reason to stop: the review uses the version
  fetched and notes the difference. `excluded` and deferral are now stated to be used only
  for their defined cases. A source that an earlier run wrongly left `excluded` this way can
  be put back in the queue with `/wikicommit-reconcile --source <url>`.
- **A source that calls an existing concept by one of its aliases now updates that page
  instead of creating a second one** (Issue #1096). Pass 2c used to treat an entity as an
  existing page only when the type and the slug matched, so a name an existing page carried
  in `aliases` produced a duplicate next to it. `/wikicommit-generate` now matches every
  extracted name against the titles and aliases of existing `primary_lang` pages (new
  script `.wikicommit/scripts/match_existing_names.py`) and updates the one same-type page
  it names. Only exact names match — after case, width and whitespace are folded — never
  names that merely mean the same. A name that matches a page of another type, or several
  pages, updates nothing and is listed in the Completion Notice. When the source describes a
  different thing under the same name (another edition, year or volume), the new page is
  still written, and that decision is recorded in the source's `## Generation Notes` and
  the Completion Notice together with the existing page's path. Existing duplicates are
  not merged. Reaches existing wikis through `/wikicommit-update` (the script) and
  `npx skills add` (the Skill).
- **WikiCommit's own labels now come in ten languages** (Issue #1017): English, Japanese,
  German, Spanish, French, Italian, Russian, Chinese (Simplified), Portuguese (Brazil) and
  Polish — the languages the Wikipedia portal lists. The review banner, the sources box,
  page properties, the language switcher, and the generated root index, source pages and
  overview page used to be English on a wiki whose `primary_lang` was anything but `en` or
  `ja`; on those eight languages they now follow the page. The translations were made from
  the English by an LLM, and the English stays canonical — if one reads as claiming more
  than the English does, that is a bug to report. A language outside the ten still renders
  these in English, and `/wikicommit-init` still says so once. `/wikicommit-fix` now
  recognises the `Page:` / `Language:` lines of a report filed from a page in any of the
  ten languages. Reaches existing wikis through `/wikicommit-update` (the plugins and
  `convert_wikilinks.py`) and `npx skills add` (the Skills).
- **`/wikicommit-generate` now follows a driver that holds the order of its steps**
  (Issue #1085). The agent used to read the whole procedure and remember where it was, and
  every failure found so far had that shape: a step at the end that did not run, a
  write-back that did not happen, a result not handed on. `.wikicommit/scripts/driver.py`
  now returns one step at a time, checks on disk that the step was really done before
  moving on (Pass 4 is refused until the management file carries its final status and
  every page it names exists with a review record), and refuses a pass whose instructions
  file was not read (`--token`). The order is replayed from the run record, so after a
  compaction or in a new session `driver.py next <run>` picks up exactly where the run
  stopped. The steps are in `wikicommit-generate/workflow.yaml` (and
  `workflow-regenerate.yaml`); Step 0 moved to `references/step0-register.md`. Run it
  with `--non-interactive` when nobody can answer — the batch cap then takes the first
  five, as before. **`/wikicommit-merge` now refuses a change that carries files an
  unfinished run touched**; changes from `/wikicommit-fix`, `/wikicommit-remove`,
  `/wikicommit-review`, hand edits, and runs that deferred or halted are not affected.
  A run whose session is gone is closed with `driver.py abandon <run> --reason "<why>"`,
  which names the files it left rather than deleting them. A Stop hook example for Claude
  Code is in the design notes; the driver does not depend on it. The checks confirm
  consistency, not proof: they stop a forgotten or skipped step, not a falsified one.
  Reaches existing wikis through `/wikicommit-update` (the new script) and
  `npx skills add` (the Skills).
- **`/wikicommit-remove` now says it removes view pages too** (Issue #1074). It already
  did — a page written by `/wikicommit-synthesize` under `.wikicommit/view/` is marked
  `status: removed` along with its translations, and its line leaves the language's view
  index — but the Skill's instructions described entity pages only, so a view page looked
  like something it could not handle. The behaviour is unchanged.
- **A name or term a source writes in its own language is kept as an alias, and
  translation uses it** (Issue #1078). Pages are written in `primary_lang`, so a term a
  Japanese source coined was normalized into English and came back in a different
  spelling when translated into Japanese — the source's own wording appeared nowhere in
  the wiki. `/wikicommit-generate` now puts that exact wording into the page's `aliases`
  when the extracted text writes the entity's name in a language other than
  `primary_lang` (verbatim only, one per language, never the title again), and the review
  checks each alias it adds against the source. `/wikicommit-translate` uses an alias in
  the target language for the translated page's title and for that term in the body, and
  no longer carries the source page's `aliases` onto the translation (every alias is a
  redirect URL on the published site, and two pages would claim the same one).
  `search_index.py` now indexes `aliases`, so searching the source's wording finds the
  page; the index rebuilds itself on the next search. Existing pages are not changed —
  `/wikicommit-generate --regenerate` adds the alias to a page it rebuilds. An `aliases`
  change counts as a content change, so it returns a `reviewed` page to `pending`.
- **`/wikicommit-synthesize` now grounds a page in up to 30 pages, chosen before any body
  is read, and says how many it left out** (Issue #1075). It used to search every
  configured language five hits at a time, so a synthesized page rested on about five
  pages at most — too few for a `pattern` (which must name every case) or a `landscape` —
  and nothing said when more had matched. It now searches `primary_lang` only (every
  original page is written in it; the other languages hold translations, which made the
  page a translation of a translation and hid later changes to the original), reduces the
  candidates to their title, description and headings, keeps those that treat the topic
  as their subject, and caps them at 30. Before writing it prints "Grounding: N of the M
  pages that treat the topic as their subject", and lists any pages the cap cut. Change
  the cap with `--max-grounding N`. In survey mode the angle list shows the cap, and the
  pages that suggested an angle become grounding candidates. `build_survey_view.py` gains
  a `--pages` mode for this. Existing synthesized pages are not revisited.
- **A non-interactive `/wikicommit-generate` no longer adds a Schema.org type on its own**
  (Issue #1069). When Pass 2b found a type that fits a source better than any installed
  one, an unattended run used to approve it with no prompt if the fit looked obvious, and
  stamp the new `.wikicommit/schema/<Type>.md` with `provenance: generate-auto`. It now
  defers that source instead — the same deferral a low-density source already gets: its
  `status` is left alone, a `## Deferred Reason` names the candidate type, and the next
  interactive run shows the `[y/N]` prompt. A wrongly approved type cannot be undone by
  any Skill (a type file cannot be edited, and no Skill reclassifies the pages written
  under it), while a deferral only makes one source wait. If you run generation unattended,
  sources that need a new type now stay in the queue until someone answers; the Completion
  Notice and `/wikicommit-status` both list them. Type files already stamped
  `generate-auto` stay valid and are still recognised everywhere; whether to keep one is
  your call.
- **`/wikicommit-status` now runs `wikicommit-merge`'s three blocking checks over every
  page** (Issue #976). `validate_frontmatter.py`, `check_wikilinks.py` and
  `check_raw_html.py` only ever ran on the files a merge changed, so a page that broke after
  it was merged — a refreshed Schema.org vocabulary or an imported type template failing an
  old frontmatter, a link to a page removed later — was reported to nobody until it was
  next written, and then blocked that merge. A new row, "Blocking errors merge does not
  re-check", counts their `ERROR:` lines and lists them under it; it reaches 0 when every
  page would still pass. A wrong Type segment is left out of it (`check_wikilinks.py` has
  a new `--skip-type-mismatch` flag) because the wanted-pages row already reports it.
  `/wikicommit-update` now points pre-existing findings of this kind at that row instead of
  saying no check watches them. Arrives with `npx skills add` (the Skill) and
  `/wikicommit-update` (the script).
- **`/wikicommit-merge`'s description now covers edits you made to WikiCommit's policy
  files** (Issue #978). It used to describe its scope as the changes another WikiCommit
  Skill left under `.wikicommit/`, which let an agent read a hand-edited
  `source-policy.md` or `entity-policy.md` as out of scope and commit it some other way,
  past the quality gates. The description now names those edits as in scope; what the Skill
  does is unchanged.

### Fixed

- **Pages whose links were rewritten by a merge no longer show up as `STALE_REVIEW:`**
  (Issue #1133). After `/wikicommit-generate --regenerate <page> --merge <page>`,
  `rewrite_merged_links.py` turns `[[Type/old]]` into `[[Type/new]]` and keeps those pages'
  `review_status`, but their AI review record no longer matched the text, so
  `/wikicommit-status` listed every one of them as `page content changed` and the published
  page dropped its AI review line. `check_review_coverage.py` (and the build's
  `convert_wikilinks.py`) now also try each page with each merge recorded in
  `.wikicommit/relations.yml` undone, and a match keeps the verdict standing. A page that
  already linked to both the kept and the absorbed page before the merge is still listed.
- **Removing the last page of a group no longer leaves an empty heading in the Type's
  index** (Issue #1136). In a Type with a groups file, `index.md` is split under one
  heading per group plus an unclassified heading. `/wikicommit-remove` drops only the
  removed page's line, so taking out the last page of a group — or the last unclassified
  page — left that heading standing over nothing on the published site until the index was
  next rebuilt. The heading now goes with its last page.

- **The overview's per-language table no longer calls the queue "taken in before this
  was recorded"** (Issue #1135). A source has no recorded language either because it was
  processed before languages were recorded, or because it has not been processed yet — a
  newly registered source has an empty `lang:` until generation reads it. Both were
  counted as "Not recorded", so a new wiki with a few sources waiting in the queue told
  its readers it had old intake. Sources that have never finished a run (empty
  `last_generated_at`) now get their own "Not processed yet" row, and the note above the
  table explains both rows in every site language. Counts for sources processed before
  languages were recorded are unchanged. Nothing to do: the table is rebuilt on the next
  deploy.

### Notes

- **No type template (`.wikicommit/schema/`) changed, but several page generation rules
  did**: the `expires_at` rule for all types (Issue #1130), a source's own wording kept in
  `aliases` (Issue #1078), Pass 2c matching names against existing titles and aliases
  (Issue #1096), and the deferrals for an update whose source cannot be fetched
  (Issue #1068) and for a new type in a non-interactive run (Issue #1069), all above. Only
  the first two change what a page says, and neither is a reason to regenerate a whole
  wiki: a source's own wording reaches a page the next time `--regenerate` rebuilds it,
  and a stale `expires_at` is named by the new WARNING and removed by hand.
- **The two new Skills, `/wikicommit-relate` and `/wikicommit-organize`, arrive only with
  `npx skills add`** (or `install.sh`). `/wikicommit-update` brings their scripts
  (`record_relation.py`, `check_name_collisions.py`, `check_groups.py` and the merge
  scripts) but not the Skills themselves; a wiki that takes only the update gets new
  `/wikicommit-status` rows with no Skill to act on them.

## Earlier versions

One file per version, moved here as each new release lands so that this file stays
bounded and a reader only opens the versions between theirs and the latest.

| Version | Date | Entry |
|---|---|---|
| 0.8.0 | 2026-09-26 | [changelog/0.8.0.md](changelog/0.8.0.md) |
| 0.7.0 | 2026-09-19 | [changelog/0.7.0.md](changelog/0.7.0.md) |
| 0.6.1 | 2026-09-15 | [changelog/0.6.1.md](changelog/0.6.1.md) |
| 0.6.0 | 2026-09-14 | [changelog/0.6.0.md](changelog/0.6.0.md) |
| 0.5.0 | 2026-09-09 | [changelog/0.5.0.md](changelog/0.5.0.md) |
| 0.4.0 | 2026-09-07 | [changelog/0.4.0.md](changelog/0.4.0.md) |
| 0.3.0 | 2026-09-06 | [changelog/0.3.0.md](changelog/0.3.0.md) |
| 0.2.0 | 2026-09-01 | [changelog/0.2.0.md](changelog/0.2.0.md) |
| 0.1.0 | 2026-08-29 | [changelog/0.1.0.md](changelog/0.1.0.md) |
