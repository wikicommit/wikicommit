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

## [0.8.0] - 2026-09-26

### Added

- **Each source now records the language its text is mainly written in, as `source.lang`**
  (Issue #989). `/wikicommit-generate` already judged a source's language while reading
  it, but kept the answer only long enough to flag a clear mismatch with `primary_lang`
  in the Completion Notice. It now always names exactly one ISO 639-1 code and writes it
  under `source:` in the management file, and newly registered sources start with an
  empty `lang:` line for it. The overview page's Sources section gains a table by
  language, with sources that have no language recorded yet shown as their own last row
  rather than dropped. Pages are still written in `primary_lang`; the field is not copied
  into any page's `sources[]`. **Existing sources are not filled in** — see Notes.
- **The overview's Knowledge hubs rows now show how many sources each hub stands on**
  (Issue #990), next to its backlink count, and `build_survey_view.py`'s `PAGE:` lines
  carry `sources=N`, so the survey step of `/wikicommit-collect` can see a central page
  that rests on one document. Translation and view pages omit the figure rather than show
  0, since their sources live elsewhere. Existing wikis get it on their next build.
- **A guide to updating the Quartz submodule**, at
  `.wikicommit/guides/updating-the-quartz-submodule.md` (Issue #988). There were no steps
  for moving `quartz/` forward, and a plain `git pull` inside it stops, because building
  the site changes the tracked `quartz/package-lock.json` there. The guide gives the steps
  (drop that change, pull, install, build, record the new pointer) and how to go back.
  `/wikicommit-init`'s preview step no longer says there is nothing to clean up in
  `quartz/`; it names that file and points to the guide. Existing repositories get the
  guide with a re-init or `/wikicommit-update`.
- **The overview's Knowledge hubs section now says when several hubs stand on one source
  alone** (Issue #1006). Each hub row already showed how many sources it has (Issue #990),
  but a column of "1"s could not say that several of them are the *same* one. Below the
  list, each source that is the only source of two or more of the top hubs is named, with
  a link to its source page and how many hubs it holds. It is a report, not a verdict: a
  page about one document, or a wiki about one document, is concentrated because it should
  be — the line above it says so. Nothing is shown when no source holds two. Existing
  wikis get it on their next build.
- **`/wikicommit-init` now writes a README.md into a repository that has none** (Issue #1034).
  It is written only when no README exists anywhere GitHub would show one (the root, `.github/`
  or `docs/`, any extension or case), from a fixed English template: the repository name, a
  short description of what WikiCommit does, a comment where you describe the wiki for
  readers, and the licensing paragraph the next-steps guidance used to offer for pasting.
  Under `--quartz-pages`, once GitHub Pages is enabled, a link to the published site is filled
  in. A README that already exists is never touched, and the one init creates is yours from
  then on — a re-init does not overwrite it. **An existing repository without a README gets one
  on its next re-init.**

### Changed

- **The overview now breaks the AI review's findings down by kind, and counts the pages
  it withheld** (Issue #1063). Under "Findings raised and fixed before publishing", each
  kind gets its own line in reader-facing words (statements the sources do not make,
  statements that contradict them, statements resting on a document not among the
  sources, other), and the lines add up to the total. A new line, "Pages withheld because
  they did not pass the check", counts pages whose newest AI review discarded them and that
  were therefore never published (no page names; not shown when there are none). **The
  findings total drops on existing wikis from the next build**: a cross-page finding that
  blamed a *neighbouring* page (`page_at_fault: other`) was counted as if this page had been
  rewritten for it, and no longer is.
- **The distributed Skills' instructions and the scripts' console output no longer cite
  Issue numbers or carry development history** (Issue #1054). The public repository has
  no Issues, so a reference like `(Issue #527)` could not be followed from a wiki, and the
  history around it was loaded into the agent's context on every run. Every `SKILL.md`,
  `references/*.md`, `.wikicommit/review-rules.md` and `.wikicommit/schema-authoring.md`
  now keeps the instruction and, where it rules out a plausible wrong move, a one-sentence
  reason; the history is gone. The `wikicommit-generate` instructions alone shrink by about
  23 KB. **What the Skills do is unchanged**: steps, templates, tracking-Issue bodies and
  the commit-trailer block read the same, and `rules_version` stays where it was. Messages
  the scripts print (`BLOCKED:`, `WARNING:` and the like) say the same thing without the
  number. If you grep a Skill for an Issue number you remember, look in this file instead.
- **`/wikicommit-update` now reports drift inside `quartz.config.yaml`'s lists, and two
  values it can compute** (Issue #950). The comparison used to stop at mapping keys, so
  all of `plugins` and every `exclude` / `ignorePatterns` list counted as a single key
  and a plugin or exclusion added upstream never showed up. It now compares list items —
  plugins by their `source`, additive only, without looking inside an entry, so turning a
  plugin on or changing its options is never reported. It also checks
  `configuration.locale` against the one `/wikicommit-init` would write for your
  `primary_lang` (language part only; a regional variant you chose is left alone), and
  the footer's GitHub link against this repository's own remote. **Expect new `OUTDATED:`
  lines the first time you run it** — they name drift that was always there and was
  simply not reported, and one file can now produce several.
- **Type index pages no longer appear in the global graph by default** (Issue #983). A
  build-generated index links to every page of its type, so it became the largest hub in
  the graph (on one pilot a single index held 44% of its language's pages) while saying
  nothing about any of them. Setting `showIndexes: true` for the global graph in
  `quartz.config.yaml` brings them back. The local graph still shows them. Arrives with
  the `quartz-plugins/` refresh.
- **The global graph's controls now say what they mean** (Issue #984). The two degree
  inputs carry their own captions, and their tooltip, which was English on every site,
  is now translated. The legend explains that "Visited" means pages opened in this
  browser, and that tags are always drawn in one colour whether visited or not. Nothing
  about how the graph is drawn changed. Arrives with the `quartz-plugins/` refresh.
- **The global graph's Sources and Tags toggles now carry their own shape** (Issue #985).
  The legend used to repeat both words as rows of its own, so the control bar said each
  twice — once pressable, once not. The square and the hollow circle moved into the
  toggle buttons, and the legend keeps "Pages" and the three visit colours, still not
  pressable. The note that tags always use one colour moved to the Tags toggle's tooltip.
  Arrives with the `quartz-plugins/` refresh (re-init or `/wikicommit-update`).
- **A source whose only shortfall is excluded entities now ends as `status: generated`,
  not `partial`** (Issue #992). When `theme` or `.wikicommit/entity-policy.md` left some
  entities out and every other page was written, the run completed as designed — but
  `partial` said "stopped partway" on the published source page and in the overview's
  status table, and nothing else reads the difference. `partial` now means only that a
  page failed (re-running can help) or an entity awaits a human's type decision. The
  exclusions stay recorded in the management file's `## Generation Notes` and in the
  Completion Notice. A source where *every* entity was excluded is still `excluded`.

  **Existing management files do not change by themselves**: `/wikicommit-generate`
  never collects a `partial` with an empty `failed_pages`, so the old value stays. To
  move them, pick the files where `status` is `partial`, `failed_pages` is empty and
  there is no `ambiguous_entities` key, and rewrite only the status — `--require` makes
  it a no-op on any file that has moved on:

  ```bash
  grep -rlZ '^status: partial$' .wikicommit/source --include='*.md' |
  while IFS= read -r -d '' f; do
    grep -q '^failed_pages: \[\]$' "$f" && ! grep -q '^ambiguous_entities:' "$f" && \
      python .wikicommit/scripts/set_frontmatter_field.py "$f" \
        --set 'status=generated' --require 'status=partial'
  done
  ```

  Then run `/wikicommit-merge` as usual. `/wikicommit-reconcile` is not the tool for this:
  it would regenerate every page and send them back for review, with no guarantee the
  source lands on `generated`. **Caveat**: a management file written before
  `ambiguous_entities` existed (Issue #910) also matches this predicate when it is waiting
  on a type decision. Nothing new is lost — such a file was already not listed under
  "Entities awaiting a type", since there is no field to read — but check its
  `## Generation Notes` first if you rely on that list.
- **The review rules now spell out `page_at_fault`'s two values where the return format
  is described** (Issue #987; `.wikicommit/review-rules.md`, `rules_version` 3 → 4). The
  field had been named there without its values, which appeared only much later in the
  prose, and in one pilot's review records 67% of the values written were outside the
  two (`this` / `self` instead of `under-review`). Existing review records are not
  rewritten; nothing reads this field yet, so the old values change no behavior.
- **`index_only:` in `.wikicommit/source-policy.md` now takes a page URL as well as a
  domain** (Issue #1032), so a curated list — an awesome list, a "Further reading" page —
  can serve as a standing index without turning its whole host into one. A domain entry
  (no path) still covers its whole host. A page entry covers that one page, and
  `/wikicommit-collect` also reads it on its own, mining only the sections that bear on
  the run's focus. Candidates taken from index pages are capped at 20 per run across all
  indexes, and the report says when the cap cut some. Both `/wikicommit-collect` and
  `/wikicommit-generate` now match `index_only:` through a new script,
  `match_index_only.py`, instead of by reading the list themselves. **If you wrote an
  `index_only:` entry with a path, it used to mean its whole host and now means that page
  only** — write the bare domain to keep the old meaning. Existing repositories get the
  script with a re-init or `/wikicommit-update`; the template's comment changes only for
  new repositories.
- **Commits made by the writing Skills now name the vendor of the model that ran them, or no
  co-author at all** (Issue #1019). `/wikicommit-merge`, `/wikicommit-schema-propose`,
  `/wikicommit-update` and `/wikicommit-init`'s foundation commit used to write
  `Co-Authored-By: … <noreply@anthropic.com>` whatever model was running, so a commit made
  with another vendor's model showed Claude as its co-author on GitHub while its
  `Generated-By` named the other model. The co-author line is now chosen from the start of
  the `Generated-By` model ID: `claude-…` (including a Bedrock-style `us.anthropic.claude-…`) keeps the previous line, `gpt-…` / `codex…` writes
  `Co-Authored-By: Codex <noreply@openai.com>`, and any other model gets no co-author line —
  `Generated-By` still records it. Commits made with Claude look exactly as before. Existing
  commits are not rewritten.

### Fixed

- **The overview's "Checked against sources (AI)" ratio no longer drops every time a page
  is translated** (Issue #1030). Its numerator and denominator counted translation pages,
  which carry no record of a check against their original, so translating a wiki lowered
  the ratio without anything having got worse — a fully translated two-language wiki read
  as half checked. Both now count only pages generated from sources. When the wiki has
  translation pages, a separate "Translation pages" row gives their number and says no
  check against the original is recorded, with one line under the ratio saying they are
  left out of it; a wiki with no translations shows the same rows as before. The note
  under the ratio now says it covers pages generated from sources. Existing wikis get
  this on their next build.
- **Search no longer uses an index built before the pages it should find** (Issue #1061).
  `search_index.py query` built the index only when the file did not exist; once built it
  was used as is, so every page added, edited or removed afterwards was invisible to
  `/wikicommit-search`, `/wikicommit-ask`, `/wikicommit-quiz --topic` and
  `/wikicommit-synthesize` — a wiki that gained a second language could have that
  language return 0 hits every time, indistinguishable from "the wiki has nothing on
  this". The index now records a fingerprint of the pages (each page's path, modification
  time and size) and is rebuilt before a query whenever it no longer matches, printing a
  `NOTE:` line when it does; a rebuild is written to a temporary file and swapped in only
  when complete. An index made by an older version has no fingerprint and is rebuilt on
  its first query. Existing wikis get this with `/wikicommit-update` or a re-init.
- **Open tracking Issues are now fetched without a 1000-item ceiling** (Issue #1062).
  `/wikicommit-merge` (checking for an existing review or generation-failure tracking
  Issue) and `/wikicommit-review` (deciding whether a page has one) listed them with
  `gh issue list --label … --limit 1000`. With a label filter that command goes through
  GitHub's search API, which stops at 1000 results with no warning whatever `--limit`
  says, so once more than 1000 were open the rest were invisible: `/wikicommit-merge`
  opened a duplicate for the same page on every run, and `/wikicommit-review` wrote
  `reviewed` locally while the real Issue stayed open. Both now read the REST issues list
  with `gh api … --paginate`. **Duplicates already created are not closed for you** —
  look for open `wikicommit-review` / `wikicommit-generation-failure` Issues sharing the
  same `<!-- wikicommit-page: … -->` / `<!-- wikicommit-ingest: … -->` marker and close
  the extras by hand.
- **`/wikicommit-review` and `/wikicommit-fix` now check a page against its source's text,
  not a summary of it** (Issue #1015, Issue #1047). Both re-read a URL source with the
  agent's own web-fetch tool, which in Claude Code returns a model-written summary — the
  reason `/wikicommit-generate` stopped using it long ago. They now read the extraction
  `/wikicommit-generate` cached for that source (for URL sources and for non-plain-text
  files alike) and, only when there is none, fetch it with `add_source.py --fetch-url`
  into `.wikicommit/.cache/refetch/`. Neither writes to a management file. A fetch that
  cannot reach any server is reported as a network problem rather than a missing source.
  When the text `/wikicommit-review` checked against hashes differently from the version
  the page records, it says so in the review record's body rather than as a finding —
  many sites return slightly different text on every fetch. Existing wikis get this with
  `npx skills add`; review records written before it are not changed (see Notes).
- **A generation-failure tracking Issue closed as "acceptable" no longer reappears on the
  next merge** (Issue #977). Its body suggested closing it with a note if the gap was
  acceptable, but the duplicate check looks only at open Issues, so the next
  `/wikicommit-merge` filed it again — and the source kept retrying the same entity. The
  body now describes accepting a gap as recording in the management file's
  `## User Notes` that the source should not produce that entity, re-running that source
  by name, and closing once `failed_pages` is empty. Issues already filed keep their old
  text.
- **Codex users are told how to invoke the Skills where the guidance reaches them**
  (Issue #1015). The `/wikicommit-init` "Next steps" list and the tracking Issues
  `/wikicommit-merge` files name commands as `/wikicommit-…`, which is how Claude Code and
  GitHub Copilot invoke a Skill; both now say once that Codex uses `$wikicommit-…`. The
  Skills' own instructions also no longer name Claude Code tools (`Read tool`,
  `WebFetch`, …), which no other agent has.
- **A fetch that cannot reach any server no longer marks the source failed** (Issue #1020).
  `add_source.py --fetch-url` folded every exception into `ERROR:`, so with no network — a
  sandbox with network access off (Codex's default), a proxy, or no connection — every URL
  source was recorded as `status: failed` and `/wikicommit-merge` then filed a
  generation-failure Issue for each. A failure before the request reaches a server (name
  resolution, refused connection, proxy error) now returns `NETWORK_UNAVAILABLE:` with exit
  code 3; `/wikicommit-generate` defers that source (status unchanged, a
  `## Deferred Reason` written, listed in the Completion Notice) and stops the run after two
  in a row. HTTP errors, read timeouts and conversion failures are still `ERROR:`. Sources
  already marked failed this way are not repaired automatically; `/wikicommit-generate <url>`
  re-fetches one. Existing wikis get this with `npx skills add`.
- **The nine writing Skills that Claude Code keeps from starting on their own are now
  guarded under Codex too** (Issue #1014). `disable-model-invocation: true` and
  `.claude/settings.json`'s `skillOverrides` are read only by Claude Code, so under Codex
  nothing held back `collect`, `fix`, `init`, `reconcile`, `remove`, `review`,
  `schema-propose`, `synthesize` or `update`. Each now ships `agents/openai.yaml` with
  `policy.allow_implicit_invocation: false` (Codex's own switch; naming the Skill with
  `$skill` still runs it), and its description says to use it only when explicitly asked
  and names the read-only Skill to use instead. Under Claude Code only the `/` menu text
  changes. Whether Codex honors the switch has not been checked on Codex itself yet.
  Existing wikis get both with `npx skills add`.
- **The Skills now work when installed under `.agents/skills/` only, as Codex installs them**
  (Issue #1021). `npx skills add --agent codex` (and the new `install.sh --agents`) creates
  no `.claude/skills/`, but the instructions named their own files as
  `.claude/skills/wikicommit-generate/references/…`, so `/wikicommit-generate` could not
  reach Pass 1 there. Paths inside a Skill are now written relative to that Skill's own
  directory (`references/…`, `scripts/…`) or to a sibling Skill (`../wikicommit-init/…`).
  `record_run.py --token` and `check_distribution_freshness.py`, which look into the Skill
  tree from `.wikicommit/scripts/`, now search `.claude/skills` then `.agents/skills`: the
  first no longer stamps a correctly-read pass as `token: missing`, and the second no
  longer says wikicommit-init is not installed when it is merely elsewhere. Existing wikis
  get the scripts with a re-init or `/wikicommit-update`, and the instructions with
  `npx skills add`.
- **A clock stepped backwards can no longer make an older review or run record read as
  the newest** (Issue #991). Which record is current is decided by the order of file
  names, and those came from the wall clock; a container whose host steps the clock back
  could name two records written in sequence in the opposite order. A record's stamp is
  now raised to at least the newest one already in its directory, with a warning on
  stderr when that happens. The file-name format is unchanged and existing records read
  as before. For run records this also decides what rotation deletes, which it could
  otherwise have pointed at the latest run.
- **The View folder now sorts where it should in the explorer** (Issue #981). The rule
  that places it compared against `View`, but Quartz lowercases the published path, so it
  never matched and View sat at the end of the type folders. Arrives with the
  `quartz-plugins/` refresh.
- **Turning off the graph's Tags toggle now removes the tag pages too, not only their
  links** (Issue #982). Quartz publishes each tag as a page, so hiding tags left those
  pages behind as unconnected dots. `removeTags` had the same gap, and now matches tag
  names without regard to case. Arrives with the `quartz-plugins/` refresh.
- **Hovering a page in the graph now shows its neighbours' names** (Issue #986).
  Nodes and links around the hovered page were highlighted, but their labels were not,
  and zooming in showed every label at once. The hovered page and its neighbours now show
  their labels while the rest stay hidden; with `focusOnHover: false` zoom alone decides,
  as before. Arrives with the `quartz-plugins/` refresh.
- **A type filter written in `quartz.config.yaml` no longer empties the global graph**
  (Issue #1005). The graph's node ids are published slugs, which Quartz lowercases, so
  `types: [Person]` — the spelling `type:` uses — matched no `person` page, while the
  control bar showed no type selected. Type names are now compared without regard to
  case, and the control bar marks the configured types as selected. The shipped
  `quartz.config.yaml` never sets this key; only a repository that added it by hand was
  affected. Arrives with the `quartz-plugins/` refresh.

### Notes

- **Reviews recorded by `/wikicommit-review` before this version may have checked a URL
  source against a summary** (Issue #1047, above). Review records never change, so they
  are left as they are, and nothing asks for those pages to be reviewed again.
- **No type template (`.wikicommit/schema/`) changed, but two page generation rules did**:
  Pass 2a now records `source.lang` (Issue #989), and a source whose only shortfall is
  excluded entities ends as `generated` (Issue #992, above). Neither changes what a page
  says, so there is no reason to regenerate pages for this version.
- **`source.lang` is not filled in for sources already processed.** It is written when
  `/wikicommit-generate` reads a source, and a source already at `status: generated` is
  not read again: until then the overview counts it under "Not recorded". To fill it in,
  put the sources back in the queue with `/wikicommit-reconcile` (for example
  `--all`) and run `/wikicommit-generate`; that re-runs the whole pipeline for them, and
  pages that come out different go back to waiting for a reader. Re-checking a URL with
  `/wikicommit-generate <url>` does not do it: an unchanged source stops at "no change"
  before its language is read.
- **Most of this version arrives with `/wikicommit-update`, not with the Skill tree.** The
  graph and explorer fixes live in `quartz-plugins/`, and the overview, survey, record and
  drift-check changes in `.wikicommit/scripts/`, as does `.wikicommit/review-rules.md`.
  The Pass 2a rule comes with `npx skills add`. A wiki that takes only one gets half.

## Earlier versions

One file per version, moved here as each new release lands so that this file stays
bounded and a reader only opens the versions between theirs and the latest.

| Version | Date | Entry |
|---|---|---|
| 0.7.0 | 2026-09-19 | [changelog/0.7.0.md](changelog/0.7.0.md) |
| 0.6.1 | 2026-09-15 | [changelog/0.6.1.md](changelog/0.6.1.md) |
| 0.6.0 | 2026-09-14 | [changelog/0.6.0.md](changelog/0.6.0.md) |
| 0.5.0 | 2026-09-09 | [changelog/0.5.0.md](changelog/0.5.0.md) |
| 0.4.0 | 2026-09-07 | [changelog/0.4.0.md](changelog/0.4.0.md) |
| 0.3.0 | 2026-09-06 | [changelog/0.3.0.md](changelog/0.3.0.md) |
| 0.2.0 | 2026-09-01 | [changelog/0.2.0.md](changelog/0.2.0.md) |
| 0.1.0 | 2026-08-29 | [changelog/0.1.0.md](changelog/0.1.0.md) |
