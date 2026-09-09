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

## [0.5.0] - 2026-09-09

### Added

- **A run record now carries a stamp at the entry to each pass, so it says where a run got
  to and which passes it skipped** (Issue #797). The records added in 0.4.0 answer whether
  a run finished; they said nothing about what happened inside it, and both halves of that
  gap have already cost this project real audits.
  - **The two paths that halt a run outright change no file at all** — the fetch-capability
    guard and a `rules_version` mismatch — so the run record is their only trace, and until
    now that trace had no position in the flow.
  - **A step at the tail of a long flow silently not running is a failure this project has
    shipped three times** (Issues #406, #452, #474), each found afterwards by a person
    reading an already-published repository. A pass with no stamp is now a pass that did
    not run.
  - `record_run.py checkpoint` appends the stamp to the record; `/wikicommit-status`
    reports the last pass reached, and — for runs that *did* finish — any pass left without
    a stamp, as `MISSING_PASS:`. That line is an observation rather than a verdict: a run
    whose sources were all blocked at Pass 1 has nothing for the later passes to do, and
    stopping there is correct.
  - **Records written before this version print nothing about passes.** They carry no
    stamps at all, which is not the same as a run that skipped everything.
  - **Known limitation.** Only the first stamping instruction is reliably still in context
    late in a long run; context compaction can drop the later ones while the run continues,
    so a compacted run can report a pass that did in fact execute. The error falls on the
    safe side — a pass that really was skipped is never reported as having run — and it
    lasts until `wikicommit-generate`'s SKILL.md is split by pass.

- **`/wikicommit-init` now says once, up front, that WikiCommit's own labels have no
  translation for the language you picked** (Issue #825). WikiCommit ships labels in
  `en` and `ja`. On a wiki in any other language, page bodies and Quartz's own chrome
  follow that language while the review banner, the sources box, page properties and
  the generated index/overview pages render in English.
  - That fallback is deliberate: several of those strings say what this wiki does and
    does not vouch for, and a translation nobody here can verify fails invisibly where
    plain English fails visibly. What was undecided was whether anyone gets told it
    happened.
  - **The published pages say nothing about it, and that is now a decision rather than
    an omission.** A notice would not restore what was lost — the English string is the
    canonical wording, so a reader who can read it has already received the claim, and
    one who cannot could not read the notice either. A flag or an `(en)` tag only
    restates what English text on a non-English page already shows. And it would stand
    on every surface of every page while being something no reader can act on.
  - `init.py` prints a `NOTE:` line instead, to the one party who can act on it. Nothing
    is printed for an `en` or `ja` wiki, and no published output changed.

### Changed

- **`reviewed` now states two things rather than one, and the wording on every surface that
  shows it was changed to match** (Issue #800). Since 0.3.0 the badge meant only that a
  person had read the page all the way through — an event, deliberately carrying no claim
  about the page itself. That turned out to be weaker than what the person closing the
  Issue had actually done, and weak enough that the badge was hard to justify the effort of
  earning.
  - It now says **(1) a person read this page** and **(2) nothing obviously wrong stood out
    while reading**. The second is a claim, but it is a claim **about the reading, not about
    the page**: "there is nothing wrong with this page" is a negative proof with no defined
    end, while "nothing stood out while I read it" ends when the reading ends. Keep that
    distinction — read as a claim about the page, it puts "did you look hard enough?" back
    into the judgment, which is the weight 0.3.0 removed. The tracking Issue template's
    **"you do not need to go looking"** is the sentence holding this in place.
  - **No mechanism changed.** `review_status` is still two-valued, the tracking Issues and
    the close-sync workflow are untouched, and closing one already meant this in practice —
    the template has always said to fix problems before closing. What changed is the
    definition and the words.
  - **Reader-facing strings on all three surfaces moved together**: the review banner
    (`Read by {name} — nothing obviously wrong stood out`, and `A person read this page —
    nothing obviously wrong stood out` where no name was recorded), the root index counts,
    and the build-generated overview page. The count label is now **"read and checked by a
    person"**.
  - **The note under those counts now says the human number is partial by design**
    (Issue #769). The machine's check against sources runs on every page; a person reads
    some of them. Without that sentence the number reads as a backlog — "12 of 83" looks
    like 71 pages of unfinished work, rather than a wiki whose every page has been checked
    against its sources and 12 of which someone has also read. Saying only "not a guarantee
    of correctness" left a reader nothing to draw from the number at all.
  - **Sampling vocabulary stays out of the reader-facing text.** Whether the selection of
    pages to read actually picks well is still unmeasured, and the word alone would imply a
    formal sampling design that does not exist yet.
  - **These strings reach existing pages without regenerating anything** — they live in the
    banner plugin and in `convert_wikilinks.py`, so a re-init followed by one Pages build
    is enough. Pages already closed as `reviewed` under the old definition are not revisited.

- **`/wikicommit-fix`'s completion comment now follows the page the reporter read,
  not the wiki's `primary_lang`** (Issue #824). When the fix is merged, Step 7 comments
  back on the originating Issue and asks the reporter to close it. That comment used to
  render in `translation.primary_lang`, on the reasoning that a reporter who read the
  page can read the language it is written in.
  - The reasoning was right and the target was wrong. A reporter reads *one page*, and a
    page's banner and report link render in that page's own `lang` — so on a
    `primary_lang: ja` wiki with `targets: [en]`, an English reader got a Japanese reply
    about an Issue only they can close. This Skill deliberately never closes the Issue
    itself, so an unreadable reply leaves it open indefinitely.
  - It now renders in the `lang` of the target page identified in Step 2, falling back to
    `primary_lang` and then English only if that field cannot be read. **Nothing changes
    on a wiki with no `targets`**, where the two values are always identical.
  - When the Issue came from a published page's report link, the prefilled body already
    names the page and its language — `Page:` / `Language:`, or `ページ:` / `言語:` on a
    Japanese page, since the banner writes those labels in the page's own locale — and
    that takes precedence: on that route Step 2 states no `.wikicommit/entity/` path, so
    it keyword-searches instead, and that search merges a page with its translations into
    one row, which would otherwise resolve an English reporter's Issue to the `ja`
    original.
  - A fix redirected to the original page (a content-derived point on a translated page)
    does not move the reader, so the comment still follows the page that was read — which
    is the case where it matters most, since the comment must then explain that the
    translation itself is unchanged until a future re-translation.
  - The tracking-Issue bodies `/wikicommit-merge` writes still render in `primary_lang`
    and are unaffected: those are read by whoever holds write access to close them, which
    is a property of the repository rather than of one page.

- **`check_schema_org_type.py --list-types` was removed; type recall is now two stages**
  (Issue #798). The three Skills that propose a Schema.org type — `/wikicommit-init`'s
  theme-driven step, `/wikicommit-collect`'s Type Proposal, and `/wikicommit-generate`
  Pass 2b — each loaded all 933 type names **with their descriptions** into the main
  context on every run: 147 KB, regardless of how many sources were being processed.
  - What that list actually did was *recall* — jog a candidate type loose from a short
    piece of text. It never established that a type exists; `--type` settles that
    separately and deterministically, after a candidate is approved. Recall does not
    need the descriptions of the 928 types nobody is considering.
  - `--list-type-names` now prints the names alone (13 KB), and
    `--describe <TypeName>...` prints the descriptions of just the candidates picked
    from them (well under a kilobyte). Together, ~14 KB — a 90% reduction.
  - This takes `/wikicommit-generate`'s fixed overhead from ~84K tokens to ~51K,
    independent of source count. On a 200K context window a five-source run now fits
    (~126K, 63%) where it previously did not (~154K, 77%); the window no longer sits
    below the five-source guard's own limit. See Requirements → Context window in the
    README.
  - `--describe` treats a name that is not in the vocabulary as an ERROR rather than
    omitting it silently: stage one hands the model 933 real names, so a name that does
    not come back is an invention, and it is better caught there than carried into the
    approval step.
  - **If you call `--list-types` from your own scripts**, switch to `--list-type-names`
    plus `--describe`. It was removed rather than kept alongside because, once the three
    Skills moved, nothing called it — and shipping the expensive path while documenting
    that nothing should use it is the receptacle-without-a-consumer shape this project
    keeps out.
  - The proposal thresholds themselves are unchanged. Only the amount of material handed
    to the judgment changed, and whether that costs any recall cannot be measured here;
    the next pilot records whether types with `provenance: init-theme` / `collect` /
    `generate-interactive` / `generate-auto` are still being created.

- **The last hardcoded Japanese in reader- and operator-facing output is gone, and a CI
  check now keeps it out** (Issue #808). 0.4.0 did this for the distributed scripts'
  console output; six kinds of it survived one layer up, in the SKILL.md files and in two
  config files the user reads at the root of their own repository. No new judgment was
  needed — three earlier Issues had already answered the same question the same way, and
  none of those answers produces hardcoded Japanese.
  - `/wikicommit-fix`'s confirmation prompt, `/wikicommit-translate`'s missing-target
    error, and `/wikicommit-review`'s findings label (`要確認:` → `NEEDS REVIEW:`, which
    also lines it up with `OK`) are now English, their reader being the operator.
  - `/wikicommit-collect`'s select-all answer no longer carries a Japanese special case;
    the language-neutral `*` was added instead. A hand-maintained list of translations for
    one keyword has no end, and an operator whose language is not on it silently loses an
    option.
  - **The comments in `quartz.config.yaml` (86 lines) and `.lychee.toml` are now English.**
    Both are files the user reads and edits directly. **No setting changed** — every value
    is byte-for-byte identical.
  - `tools/check_skill_output_language.py` was added and runs **blocking** in CI. It looks
    for Japanese sentence-ending punctuation and corner brackets rather than for CJK
    characters: a SKILL.md legitimately contains Japanese *examples* — titles, search terms,
    quotations — and CJK alone cannot tell an example from an output string. **Known
    limitation**: a label with no sentence-ending punctuation is invisible to it.
  - **The two config files need a hand edit to take in**, being `update: review` — neither
    re-init nor `/wikicommit-update` overwrites them. Nothing breaks if you leave them: the
    comments stay in Japanese and the settings are unaffected.

### Notes

- **No type template (`.wikicommit/schema/`) changed in this version** — every one is
  byte-identical to 0.4.0 — and no page generation rule changed either. The edits to
  `wikicommit-generate` add the pass stamps and narrow what Pass 2b is handed to think
  with; neither changes how a page gets written. **There is therefore no reason to
  regenerate pages for this version.**
- **What reaches existing wiki repositories without regenerating anything**: the reworded
  banner, root index counts and overview page (Issue #800), the two-stage type lookup
  (Issue #798), and the pass stamps (Issue #797). All of them live under
  `.wikicommit/scripts/` or `quartz-plugins/`, which are `update: overwrite` — one
  `/wikicommit-update` (or `/wikicommit-init --no-overwrite`) plus one `deploy.yml` run is
  enough. The three reader-facing surfaces are recomputed at build time, so pages written
  months ago pick up the new wording.
- **What does not arrive on its own**: the English comments in `quartz.config.yaml` and
  `.lychee.toml` (Issue #808), both `update: review`. Nothing breaks if you leave them —
  no setting changed, only the comments — so this is optional in a way the `locale` line
  from 0.4.0 was not.
- **Run records written before this version carry no pass stamps**, and
  `/wikicommit-status` prints nothing about passes for them (Issue #797). A record with no
  stamps is not a run that skipped every pass.
- Nothing is applied retroactively. Pages already closed as `reviewed` under the narrower
  0.3.0 definition are not revisited (Issue #800), and tracking Issues already open keep
  the text they were created with.

## Earlier versions

One file per version, moved here as each new release lands so that this file stays
bounded and a reader only opens the versions between theirs and the latest.

| Version | Date | Entry |
|---|---|---|
| 0.4.0 | 2026-09-07 | [changelog/0.4.0.md](changelog/0.4.0.md) |
| 0.3.0 | 2026-09-06 | [changelog/0.3.0.md](changelog/0.3.0.md) |
| 0.2.0 | 2026-09-01 | [changelog/0.2.0.md](changelog/0.2.0.md) |
| 0.1.0 | 2026-08-29 | [changelog/0.1.0.md](changelog/0.1.0.md) |
