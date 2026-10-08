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

## [0.10.0] - 2026-10-08

### Added

- **`/wikicommit-status` reports broken external links across every page** (Issue #1182).
  `/wikicommit-merge` now checks only the pages it merges, so a link that broke after its
  page was merged had nowhere to be found. `/wikicommit-status --links` checks every
  published page (entity and view, removed pages left out) with the new
  `.wikicommit/scripts/check_external_links.py`, a few pages per lychee call and within the
  shell's time limit: while it prints `CONTINUE:`, the agent runs it again, and it carries on
  where it stopped. The result is kept under `.wikicommit/.cache/lychee/`, and a plain
  `/wikicommit-status` reads it back without touching the network, as a `Broken external
  links` row with the time of the last check (`not checked yet` until one has completed). The
  row does not block the "Wiki is healthy" verdict. The merge's lychee wrapper uses the same
  batching code and shares lychee's cache. Run `/wikicommit-update` after updating the Skills,
  since the new script is in `.wikicommit/scripts/` — `/wikicommit-merge` needs it too.
  Each finding is stored with its kind (broken link or not checked) and the pages it is about
  (Issue #1243), so the count of broken links never depends on how a message is worded. A
  check left unfinished by a development build of this version starts over once; a
  completed result from one is still read.

- **Each public source page now states the source's language** (Issue #1007). The page's
  `## Summary` is written in the wiki's `primary_lang`, so a source in another language
  (a Japanese article in an English wiki, say) looked like a `primary_lang` source, and
  nothing on the page said otherwise. A `Language: <code>` line now appears next to the
  license line whenever `source.lang` is recorded — also when it matches `primary_lang`, so
  the line is a plain fact on every page rather than a mark on the "foreign" ones. Sources
  processed before `source.lang` was recorded get no line (as with an unrecorded license);
  the overview page's language table still counts them. Norwegian (`lang: no`, which YAML
  reads as `false`) is shown as `no`.

### Changed

- **A renamed page keeps the review records of its old name** (Issue #1162). When
  `/wikicommit-relate` renames an edition of a series, the review records stay under the old
  path, so `/wikicommit-status` used to list the renamed page as never reviewed. It now reads
  the old name's records through `.wikicommit/relations.yml`; since the title changed, the
  check shows up as a stale review naming the old name, and `/wikicommit-review` on the new
  page clears it. If only the slug changed, the original page's check still stands, and its
  published page keeps its AI review line; neither the page's title nor its review status is
  touched. A translation's check does not stand: its `translated_from` now names the new
  path, so it shows up as a stale review, and `/wikicommit-status` also lists the
  translation as out of date — `/wikicommit-translate` brings it up to date (Issue #1246).

- **`ScholarlyArticle`'s `properties.keywords` now holds only the paper's own declared
  keywords** (Issue #1177). Pages mixed three readings — the paper's Keywords section copied
  as is, that list with entries dropped or replaced, and subject terms the generator picked
  when the paper declared none (sometimes an arXiv subject class) — and the published page
  shows them beside the authors and date, where a reader takes them as the paper's own.
  Pass 3 now has a type-independent rule: a property that stands for a list the source
  declares about itself (a Keywords section, Index Terms, Key words, CCS Concepts) is copied
  in full, in the source's order and wording, and is omitted when the source declares none;
  subject terms you chose go in `tags:` (the JSON-LD `keywords` already comes from `tags`).
  Pass 4 checks it: `.wikicommit/review-rules.md` (`rules_version` 7) fails an entry the
  source does not declare, and a `keywords` list on a page whose source declares none, as
  `HALLUCINATION`; leaving out declared entries is not a failure. **The rule reaches existing
  wikis with the Skills, but the type template does not**: `.wikicommit/schema/` is not
  rewritten by `/wikicommit-update`, so the new `granularity` line in `ScholarlyArticle.md`
  (the same rule, stated for this type) appears only in newly initialized wikis — copy it
  into your `.wikicommit/schema/ScholarlyArticle.md` by hand if you want it there too.
  Existing pages keep their `keywords` until regenerated. To fix them,
  `/wikicommit-generate --regenerate --type ScholarlyArticle` rewrites every page of the type
  (each page goes through generation and Pass 4 again), so it costs about as much as
  generating them did; regenerating only the pages you are about to review
  (`--regenerate <page>`) is the cheaper alternative.

- **`/wikicommit-generate` reads a symlinked `type: path` source the way `/wikicommit-review`
  and `/wikicommit-fix` do** (Issue #1216). Pass 1 decided between reading a source as text and
  extracting it — and which extraction tool to use — from the name in `source.path`, so a
  `raw/notes.md` symlink pointing at a PDF was read as raw PDF bytes, while review and fix
  extract the PDF it points at: the page was generated from one text and checked against
  another. `add_source.py --check-path-cache` now makes that decision on the file the path
  resolves to: it prints `RAW: <file>` for a `.md` / `.txt` target (read it directly; it is
  never cached) and adds `extract=<file>` to `CACHE_STALE:`, and Pass 1 runs it for every
  `type: path` source. The extraction Pass 1 caches for such a link is the one review and fix
  look up, so they no longer re-extract it each time. Run `/wikicommit-update` after updating
  the Skills, since the change is in `.wikicommit/scripts/`.

- **`/wikicommit-review` and `/wikicommit-fix` get a page's source texts with one command**
  (Issue #1211). Both used to follow a shared step-by-step procedure, run once per source:
  check for withdrawn sources, then call `resolve_source_cache_path.py --obtain` for each
  entry. `resolve_source_cache_path.py --obtain-sources` now takes the page whose `sources`
  apply (the parent page, for a translation) and handles every entry in one go, printing
  one line each — `READ:`, `EXTRACT:`, `RETRACTED:`, `UNAVAILABLE:` or `MANUAL:`, each with
  the entry's position — and a `SUMMARY:` line. A withdrawn source is still never read or
  fetched, a path outside the repository is still refused, and the agent's own web-fetch
  tool is still never used. Leftover scratch files from an earlier run under the same label
  are cleared before fetching. The shared procedure file
  (`wikicommit-ask/shared/source-fetch.md`) is gone, so `wikicommit-ask` no longer depends
  on `wikicommit-generate`, and `wikicommit-review` / `wikicommit-fix` now depend on
  `wikicommit-generate` directly instead of on `wikicommit-ask`. Run `/wikicommit-update`
  after updating the Skills, since the new flag is in `.wikicommit/scripts/`.

- **`/wikicommit-merge` checks external links only on the pages it is about to merge,
  and runs its classification and fast quality checks as scripts** (Issue #1196). lychee
  used to fetch every link in `.wikicommit/entity/` on every merge, so a large wiki could
  outlast the agent's shell time limit and the PR body filled up with broken links on pages
  the batch never touched. It now checks the changed pages only, a few per call (with
  `--cache`, kept under `.wikicommit/.cache/lychee/`), and the agent calls it again until
  it prints `LINKS: done`. Sorting the changes into what gets checked and staged, and the
  frontmatter, WikiLink, raw-HTML and orphan/duplicate checks, are now steps the workflow
  engine runs itself; a blocking finding halts the run with that finding as its reason, as
  before. The lists are kept in the run record, so a resumed commit step no longer works
  them out again, and the PR body is printed by `workflow_checks.py pr-body` instead of
  being written by the agent. A merge run left open from before this update follows the
  old steps: close it with `skill_workflow.py abandon <run> --reason …` and run
  `/wikicommit-merge` again.

- **`/wikicommit-generate` no longer stops in the middle of a batch to ask about a
  low-density source or a new type** (Issue #1116). Both questions used to be asked on the
  spot in an interactive run, so a 30-source run needed someone at the keyboard for each
  one, and the agent itself decided whether anyone was there. Now the source is always set
  aside with a `## Deferred Reason`, and once every source has been through the passes the
  run asks all the questions at once — a type candidate once per type, however many sources
  proposed it — and takes the answered sources through the passes again in the same run.
  With a single source the question comes where it always did. A run started with
  `--non-interactive` asks nothing and leaves the deferrals queued, exactly as before. A type
  approved at the end was not available to the sources the run had already finished; the
  Completion Notice says so and points at `/wikicommit-reconcile --source`. The workflow
  engine (`.wikicommit/scripts/skill_workflow.py`) gained what this needs, so **run
  `/wikicommit-update` and merge its PR before the next `/wikicommit-generate`**.

- **The step checks of `/wikicommit-generate`, `/wikicommit-merge`, `/wikicommit-translate`
  and `/wikicommit-synthesize` share one module, `.wikicommit/scripts/_workflow_checks.py`**
  (Issue #1219). Each of these Skills used to carry its own copy of how a run record, a
  recorded answer and a review record are read, and the copies had begun to differ. They
  now import the one copy in `.wikicommit/scripts/`. **Run `/wikicommit-update` and merge
  its PR before the next run of any of the four**: until then the module is missing, and
  each stops at its first step and says to run `/wikicommit-update`. What the checks accept
  is unchanged.

- **`add_source.py`, `resolve_source_cache_path.py` and `remove_page.py` now live in
  `.wikicommit/scripts/`** (Issue #1210). They used to sit inside one Skill each
  (`wikicommit-generate`, `wikicommit-ask`, `wikicommit-remove`) while other Skills reached
  them across Skill directories. Every Skill now calls them from `.wikicommit/scripts/`, so
  **run `/wikicommit-update` and merge its PR before the next `/wikicommit-generate`**: until
  then `.wikicommit/scripts/` does not have them, and `/wikicommit-generate`,
  `/wikicommit-collect`, `/wikicommit-remove`, `/wikicommit-relate`, `/wikicommit-review`,
  `/wikicommit-fix` and `/wikicommit-ask --include-source` stop and say so. Each SKILL.md
  now declares the other Skills it reads files from in `metadata.requires` (for example
  `wikicommit-collect` requires `wikicommit-generate` and `wikicommit-init`).

- **`.wikicommit/scripts/driver.py` is now `skill_workflow.py`** (Issue #1203). The script
  that holds the order of a multi-step Skill's steps is renamed to match the workflow
  definitions it runs (`workflow.yaml`); its commands (`start`, `next`, `done`, `status`,
  `check-merge`, `abandon`) are unchanged. New run records keep its state under
  `workflow:` instead of `driver:`; a record written by `driver.py` is still read, so a run
  that stopped partway before the update continues with `skill_workflow.py next <run>`.
  After `/wikicommit-update`, the old `.wikicommit/scripts/driver.py` remains and
  `check_distribution_freshness.py` reports it as `ORPHAN:` — no distributed Skill calls it
  any more, and `/wikicommit-update` asks before deleting it. If you added a Stop hook that
  runs `driver.py status --stop-hook`, change its command to `skill_workflow.py` — keeping
  `driver.py` does not keep the hook working, since the old script reads only `driver:` and
  no longer sees any run opened or advanced after the update.

- **Inside a run record's `workflow:` state, the workflow definition's path and hash are now
  `definition` / `definition_sha256`** (Issue #1209). They were `workflow` /
  `workflow_sha256`, which put a path named `workflow` inside the mapping named `workflow`.
  A record written with the old names — under either `workflow:` or `driver:` — is still
  read, so a run that stopped partway continues with `skill_workflow.py next <run>`, and its
  next write moves the fields to the new names.

- **`/wikicommit-review` and `/wikicommit-fix` get each source's text with one command per
  entry** (Issue #1190). `resolve_source_cache_path.py --obtain` now does what the shared
  procedure used to spell out step by step — the retraction check, the extraction cache
  (for a `type: path` source, only while the file is still the version it was extracted
  from), the fetch through `wikicommit-generate`'s fetcher, and settling that fetch into the
  cache — and prints one `READ:` / `EXTRACT:` / `RETRACTED:` / `UNAVAILABLE:` line. The
  agent is left with one decision (call the extraction skill on `EXTRACT:`), and the
  instructions both Skills read are about 2KB shorter.

- **`/wikicommit-translate` now runs step by step under the same Skill workflow engine** (Issue #1194).
  `.wikicommit/scripts/skill_workflow.py` checks the configuration and the arguments, collects the
  (page, target language) pairs — glossary pages first in batch mode, as before — and hands
  them out one at a time. A pair is not marked done until the translation is on disk with
  `translated_from`, a `source_commit` that matches the source page, and
  `review_status: pending`, and a `translate-check` review record from this run is there
  (for a pair that still failed review, the discarded record alone). The pairs and their
  results are kept in the run record, so a batch interrupted partway continues with
  `skill_workflow.py next <run>` from the pair it stopped at. Run `/wikicommit-update` so
  `.wikicommit/scripts/` matches before the next translation.

- **`/wikicommit-synthesize` now runs step by step under the same Skill workflow engine** (Issue #1195).
  `.wikicommit/scripts/skill_workflow.py` checks the configuration, `review-rules.md` and
  `--max-grounding` before any search, and does not mark a step done until it is: the
  grounding pages until each is an original page in `primary_lang` — not a translation, not
  itself a synthesis — and there are no more of them than the cap; the written page until it
  is in `.wikicommit/view/<primary_lang>/`, its `derived_from` names exactly those pages at
  their commits, and a `synthesize-step5.5` review record from this run is there (for a
  synthesis that still failed review, the discarded record alone, with nothing written). The
  chosen topic and kind, the grounding pages and the page path are kept in the run record, so
  a run interrupted partway continues with `skill_workflow.py next <run>` from the step it stopped
  at. In a run with nobody to answer, an existing view page is no longer at risk of being
  overwritten: the run leaves it as it is. Run `/wikicommit-update` so `.wikicommit/scripts/`
  matches before the next synthesis.

- **`/wikicommit-merge` now runs step by step under the same Skill workflow
  engine as `/wikicommit-generate`** (Issue #1094). `.wikicommit/scripts/skill_workflow.py` holds the order of
  its steps, runs the ones that need only a command itself (the scripts version check, the
  default branch, change detection, another run's unfinished work), and does not mark a step
  done until it is: the commit step until the merge branch holds every detected change, the
  PR step until the branch is on `origin`, the merge step until GitHub reports the PR as
  `MERGED` and the default branch is checked out. The default branch, the warnings and the PR
  number are kept in the run record, so a merge interrupted partway — by a compaction or a
  new session — continues with `skill_workflow.py next <run>` from the step it stopped at, on the
  same PR. The warnings question is now asked as its own step; a run started with
  `--non-interactive` still records the warnings in the PR body and proceeds, and answering
  "stop" ends the run normally instead of leaving its record open. `skill_workflow.py` gains
  `check-merge --except-run <run>` and a `finishes_on` list for questions. Run
  `/wikicommit-update` so `.wikicommit/scripts/skill_workflow.py` matches before the next merge.

### Fixed

- **`/wikicommit-review` and `/wikicommit-fix` no longer get cut off while fetching a page's
  sources** (Issue #1240). Getting every source in one command meant that a page with several
  uncached URL sources could outlast the agent's shell time limit (120 seconds by default in
  Claude Code), and with no network every URL waited for its own failure. The command now
  starts no new fetch after 45 seconds (`--budget`): it prints a `CONTINUE: next=<n>` line,
  and the agent calls it again with `--from <n>` until no such line is printed. After two
  fetches in a row fail for want of a network, the remaining URLs are not fetched and are
  reported as `UNAVAILABLE: … environment … (not fetched: …)`. Run `/wikicommit-update` after
  updating the Skills, since the change is in `.wikicommit/scripts/`.

- **`/wikicommit-merge` no longer commits a page whose file name is not valid UTF-8 without
  checking it** (Issue #1258). Such a page dropped out of the pages the quality checks read
  without a word, yet the commit still staged it; the merge now stops and asks you to rename
  the file (page file names are English identifiers, so this does not arise in normal use).
  A file with such a name inside a directory `source.path` is left out of the commit with a
  warning instead, as an ignored file is. The warning about a `.gitignore`d `source.path`
  written as `./raw/x.pdf` or `raw/dir/` no longer names the same path twice.

- **Non-ASCII paths no longer slip through the Skill workflow engine** (Issue #1256). An
  unfinished run that touched a file with a non-ASCII name (a raw source named in Japanese,
  or the management file that mirrors it) no longer lets `/wikicommit-merge` carry that
  file: the engine read `git status` without `-z`, so git's quoted, escaped form of the path
  matched nothing the run had recorded, and `abandon` did not name the file as left behind
  either. On a locale that is not UTF-8 (cp932 / cp1252 on Windows), every Skill on the
  engine — generate, translate, synthesize and merge — now reads its checks' output, and
  writes its own JSON, as UTF-8, so a non-ASCII path no longer drops out of a step's list
  or stops the run with `UnicodeEncodeError` / `UnicodeDecodeError`. The same goes for the
  output of `add_source.py` read by `/wikicommit-ask --include-source`, lychee read by
  `check_external_links.py`, and gh read by `check_actions_pr_permission.py`. Merge
  `/wikicommit-update` first: the Skills now need the updated `.wikicommit/scripts/`.

- **A Skill's checks run directly on a locale that is not UTF-8 no longer stop at a non-ASCII
  path** (Issue #1264). The steps that tell the agent to run `workflow_checks.py` itself
  (`/wikicommit-merge`'s commit and pull request steps, for example) printed a Japanese path
  through the locale's codec, and on a cp1252 terminal or pipe that raised
  `UnicodeEncodeError`. The checks of generate, translate, synthesize and merge now write
  their output as UTF-8 whoever runs them, as the workflow engine already did.

- **`/wikicommit-ask --include-source` no longer stops at a non-ASCII source on a locale that
  is not UTF-8** (Issue #1265). `resolve_source_cache_path.py` read `add_source.py`'s output
  as UTF-8 but printed its own `READ:` / `EXTRACT:` / `RETRACTED:` / `UNAVAILABLE:` lines
  through the locale's codec, so on a cp1252 terminal or pipe a Japanese path or URL raised
  `UnicodeEncodeError` after the fetch had succeeded. It now writes its output as UTF-8, and
  reads the identifier on stdin as the system reads file names. `/wikicommit-review` and
  `/wikicommit-fix`, which get a page's sources the same way, are fixed too.

- **`/wikicommit-merge` now warns about links left pointing at a page being removed**
  (Issue #1257). The page being marked `status: removed` is always among the changed
  pages too, and `check_wikilinks.py` skipped the backlink check for a page passed with
  both `--changed` and `--deleted` — so in an ordinary merge the "a backlink remains"
  WARNING that `/wikicommit-remove` promises never appeared. A page in both lists now
  gets both checks (its own links, and the links other pages still make to it; a page's
  link to itself is not counted, nor is a link from any other page that is itself
  `status: removed`, and a link counts against the page it resolves to from the
  referrer's language, so removing a page with its translations does not report each
  link once per language). The merge calls the two checks separately, once per
  group of changed pages and once per group of removed pages, so the result no longer
  depends on how many calls the change is split into, and no call reads the whole wiki
  for nothing.

- **`add_source.py --check-path-cache` hashes and names the same file** (Issue #1242). The
  existence check, the hash and the `extract=` on `CACHE_STALE:` / `ERROR:` now all come
  from one resolution of `source.path`'s symlinks, instead of the hash opening the link
  again and `extract=` re-reading the management file. A link swapped mid-check can no
  longer leave Pass 1 extracting a different file from the one whose hash was compared.

- **`/wikicommit-merge`'s classification and quality checks handle four edge cases**
  (Issue #1237). The output of git and of the Python checks is now read as UTF-8 whatever
  the locale says, so on Windows (cp932 / cp1252) a page with a non-ASCII name no longer
  drops out of the quality checks or stops the run with a `UnicodeDecodeError`, and a
  check's Japanese finding no longer crashes the check. A batch removing hundreds of pages
  no longer halts with `check_wikilinks.py: could not run`: the length of the repeated
  `--deleted` list now counts toward each command line, and the list is split when it is
  long. A management file whose `source.path` is a directory now carries only the untracked
  files in it, never a tracked file's unrelated uncommitted edit. A run with no changed page
  (assets, policy files or records only) skips the lychee/markdownlint step instead of
  handing it to the agent.

- **A missing PyYAML no longer sends you to `/wikicommit-update`** (Issue #1233). Run
  directly (as the merge and generate steps tell the agent to), the `workflow_checks.py` of
  `/wikicommit-generate` and `/wikicommit-merge` read a missing PyYAML as an outdated
  `.wikicommit/scripts/` and said to run `/wikicommit-update`, which does not install it;
  those of `/wikicommit-translate` and `/wikicommit-synthesize` stopped with a traceback and
  exit code 1, which a workflow condition reads as "skip this step". All four now stop with
  exit code 2 and say to install PyYAML (`pip install pyyaml`).

- **A source language recorded as something other than one code no longer reaches the
  published site as a stringified value** (Issue #1193). A management file whose
  `source.lang` is a list (`[ja, en]`), `true` (an unquoted `yes` / `on`) or a number used
  to show `['ja', 'en']` or `true` on its public source page and as a row in the overview
  page's per-language table. Such a value is now treated as not recorded: the source page
  omits the language line, and the table counts the source under "Not recorded" (or "Not
  processed yet" if it has never finished a run). `lang: no` is still read as Norwegian.
  Re-running the source (`/wikicommit-reconcile`, or a forced recheck with
  `/wikicommit-generate <url>`) writes a proper code.
- **`/wikicommit-translate --lang <target>` without a page translates only that language**
  (Issue #1202). Batch mode used to take every target's pairs and ignore `--lang` without
  saying so. It now narrows to that language, keeping the glossary-first order; a `--lang`
  outside `translation.targets` with no translations yet halts the run before anything is
  translated, because batch mode could never find anything for it — name a page or add the
  language to `targets`. One outside `targets` that already has translations still refreshes
  the stale ones.
- **`/wikicommit-translate` and `/wikicommit-synthesize` fail a step's check when the run
  record's `started_at` cannot be read** (Issue #1202). Without it the check cannot tell
  this run's review records from an earlier run's, and it used to accept every record on
  disk, so an earlier `pass` could complete the step. The check now fails and says the run
  record is damaged.
- **`/wikicommit-review` and `/wikicommit-fix` judge a `type: path` symlink by the file it
  points to** (Issue #1208). `resolve_source_cache_path.py --obtain` decided between reading
  the raw file and extracting it from the link's own name, so `raw/notes.md` pointing at a
  PDF had the PDF's bytes handed over as text. The `.md`/`.txt` decision now uses the
  symlink's target, and the `READ:` / `EXTRACT:` line names the target, so the extraction
  skill is chosen by the real file's extension.
- **`/wikicommit-status` and `/wikicommit-generate` no longer hash a source file outside the
  repository named by a management file** (Issue #1207). A hand-written
  `.wikicommit/source/path/**` file whose `source.path` was an absolute path, climbed out
  with `..`, or named a symlink pointing outside the repository had that file hashed, and
  the output told whether it existed. `check_ingest_freshness.py` now skips such a file with
  `WARNING: … source.path resolves outside the repository … — not checked` (its `status` is
  left as is), and `add_source.py --check-path-cache` returns `ERROR: … resolves outside the
  repository` instead of `CACHE_STALE`. Both decide on the resolved path and before the
  existence check, so neither answer depends on whether the outside file exists.
- **`/wikicommit-ask --include-source` no longer reads a `type: path` source that points
  outside the repository** (Issue #1206). The same paths Issue #1201 closed for review and fix
  still reached ask, which answers a missing cache by reading the raw file. In its default
  mode `resolve_source_cache_path.py --type path` now prints `OUTSIDE: <path>` (exit 1) for
  an absolute path, a `..` that climbs out, or a symlink pointing outside the repository —
  before `UNREGISTERED:` / `NO_CACHE:`, so a registered outside path is caught too — and
  ask skips the entry and names it in the "could not include" note instead of opening it.
- **`/wikicommit-review` and `/wikicommit-fix` no longer read a `type: path` source that
  points outside the repository** (Issue #1201). A page whose `sources[].path` was an
  absolute path (`/etc/passwd`), climbed out with `..`, or named a symlink pointing outside
  the repository had that file read into the agent's context. `resolve_source_cache_path.py
  --obtain` now prints `UNAVAILABLE: outside (…)` for such an entry — judged on the resolved
  path, and before the existence check so the reply does not reveal whether the outside
  file exists — and the shared procedure tells the agent not to open it. A symlink pointing
  inside the repository is still read. `validate_frontmatter.py` reports the same paths as
  an ERROR (`resolves outside the repository`), so `/wikicommit-merge` stops such a page
  before it lands, and `/wikicommit-generate` no longer registers such a path as a source.

- **`/wikicommit-generate --regenerate …` and `/wikicommit-translate <page> --lang …` start
  their run** (Issue #1194). Both Skills told the agent to pass each argument as
  `--arg "<argument>"`, and `skill_workflow.py start` rejects a value that starts with `--` written
  that way, so a run with an option argument could not start. They now say `--arg=<argument>`.

- **Answering the theme prompt again on a wiki whose theme spans several lines no longer
  breaks `config.yml`** (Issue #1179). `init.py --update-theme` replaced only the first line
  of the existing `theme:` value, leaving its continuation lines behind, so the whole file
  stopped parsing and every Skill that reads `config.yml` failed. Earlier versions of init
  folded any theme longer than about 80 characters onto several lines, so most real themes
  were affected; hand-written block (`|`) and folded values were too. The update now
  replaces the whole value, keeps comments and every other key as they were, and refuses to
  write (with an `ERROR:`) if the result would not read back as the new theme. Init and
  `--update-theme` now write the theme on a single line however long it is.
- **Updating a single value in `config.yml` no longer changes the line endings of the whole
  file** (Issue #1189). `init.py --update-theme`, `--update-version` and `--add-config-keys`
  rewrote every line break to the running OS's default, so a CRLF `config.yml` on Linux or
  macOS became LF (and an LF one on Windows became CRLF), and `git diff` showed every line as
  changed. They now keep the file's own line endings and write any added lines with them;
  the same applies to the `exclude_living_persons` switch init sets in `entity-policy.md`.

### Notes

- **One type template changed, `ScholarlyArticle`, and so did one page generation rule**
  (Issue #1177, above). Pass 3 now copies a list a source declares about itself (its
  Keywords section and the like) in full and in the source's wording, for any type, and
  Pass 4 (`.wikicommit/review-rules.md`, `rules_version` 7) fails entries the source does
  not declare. The `granularity` line added to `ScholarlyArticle.md` reaches only newly
  initialized wikis; copy it by hand if you want it in an existing one. Existing pages keep
  their `keywords` until regenerated, and regenerating a whole type costs about as much as
  generating it did, so this is not a reason to regenerate a wiki — regenerate the pages
  you are about to review instead.
- **Run `/wikicommit-update` and merge its PR before running any Skill again.** Much of this
  version moves work from instructions into `.wikicommit/scripts/`: the shared step checks
  (`_workflow_checks.py`), the three scripts that left their Skill directories
  (`add_source.py`, `resolve_source_cache_path.py`, `remove_page.py`), the renamed
  workflow engine (`skill_workflow.py`) and the external link check
  (`check_external_links.py`). Until the update is merged, the Skills that need them stop
  at their first step and say so. A `/wikicommit-merge` run left open from before the
  update follows its old steps; close it with `skill_workflow.py abandon` and start again.
- **`wikicommit-review` and `wikicommit-fix` now need `wikicommit-generate` installed
  beside them** (Issue #1211), instead of `wikicommit-ask`. A partial install that left
  out `wikicommit-generate` must add it.
- **No new Skills.** `npx skills add` brings the changed Skill files; nothing needs to be
  installed for the first time.

## Earlier versions

One file per version, moved here as each new release lands so that this file stays
bounded and a reader only opens the versions between theirs and the latest.

| Version | Date | Entry |
|---|---|---|
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
