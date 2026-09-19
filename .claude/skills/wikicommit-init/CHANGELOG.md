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

## [0.7.0] - 2026-09-19

### Added

- **`/wikicommit-init` now writes a `skillOverrides` block into `.claude/settings.json`**
  (Issue #953), setting `wikicommit-generate`, `wikicommit-merge` and `wikicommit-translate`
  to `name-only`. Those three lost `disable-model-invocation` in 0.7.0 so that unattended
  runs would have a path at all, which also made it possible for a model to start them off
  a passing request. `name-only` hides the description — the thing a model matches against
  — while leaving the name and the `/` menu intact, so a prompt that names
  `/wikicommit-generate` still works and **nothing has to be flipped to run unattended**.
  `user-invocable-only` would have to be turned back to `on` for that, and that switch is
  all-or-nothing: it re-enables auto-invocation for every Skill in the repository at once.
  - **A key that already has a value is never touched**, under any flag including
    `--no-overwrite`. Setting one to `on` is an operator running unattended on purpose, and
    a re-init quietly putting it back would stop those runs while printing a success line.
    This is a per-key merge rather than a file copy for that reason, and the rest of the
    file — `permissions`, `env`, `hooks` — is left exactly as it was.
  - A `settings.json` that is not a readable JSON object is left strictly alone, and a
    warning says the guard is **not** in place. Rewriting it would destroy settings the
    script cannot read, and saying nothing would report a protection that is not there.
  - `check_distribution_freshness.py` compares this file by **keys, never values**: a Skill
    the template names and this file has no entry for is reported, while a value the
    operator changed is not. Reporting the latter would push them toward undoing the very
    thing they decided.
  - **Existing repositories do not get this.** It arrives only on a repository that runs
    `/wikicommit-init` from here on. The guard that does reach an already-installed wiki is
    the narrowed Skill description from 0.7.0, which travels with `npx skills add`.

### Changed

- **`wikicommit-generate`, `wikicommit-merge` and `wikicommit-translate` can now be started
  by a model, not only by a person typing `/name`** (Issue #945). All three carried
  `disable-model-invocation: true`. That flag was understood here as "do not fire from the
  agent's own automatic trigger judgment", but it does more than that: it also stops the
  Skill being preloaded into a subagent and stops a scheduled run from firing it, and
  because a flagged Skill is not listed to the model at all, an explicit invocation through
  the Skill tool does not reach it either. Only a person typing `/name` was left. Every
  unattended path therefore did not exist — a prompt written to work through a backlog of
  queued sources ended without processing a single one, and there was no error to read,
  because nothing had been invoked.
  - The three descriptions were rewritten to say **when not to use each Skill** as well as
    when to, and to name the read-only Skill that should answer instead. For a repository
    with no per-Skill settings, the description is now the only brake on a Skill that
    writes, so each one names its near misses explicitly — a pasted link someone wants
    read, an ordinary "commit and push", a request to translate a sentence.
  - The other nine distributed writing Skills keep the flag. `wikicommit-collect` gates on
    human approval before registering anything, and `wikicommit-fix` / `wikicommit-remove`
    reach Git through `wikicommit-merge` rather than on their own.
  - **A repository can narrow this back down without editing distributed files.**
    `skillOverrides` in `.claude/settings.json` takes `name-only` (hide the description,
    which is the autonomous-trigger mechanism, but keep the Skill startable by name) or
    `user-invocable-only` (hide it from the model entirely). Unlike the flag, that setting
    belongs to the repository rather than the distribution, so `npx skills add` does not
    overwrite it.

- **`wikicommit-merge` no longer aborts on warnings when no one is there to answer**
  (Issue #945). It now records them and proceeds. Warnings never decided whether a batch
  may merge — every warning this Skill can produce is classified "always mergeable", and
  the confirmation existed to show them to a person. Aborting instead meant an unattended
  run reached the end of generation and then threw the result away, since nothing had been
  committed yet and a cloud working tree does not survive the session.
  - **Blocking findings are unchanged.** `ERROR:` and `DUPLICATE:` still stop the run,
    interactive or not, and still stop it before a branch exists, so the working tree is
    left as it is. No quality-gate script changed.
  - The PR body now carries the warnings — a count per tool, the first few findings from
    each, and `(+N more)`. **This replaces a fixed body that read "Quality checks passed."**,
    which was already untrue in an interactive run where warnings appeared and the person
    chose to proceed. The body is the same either way now, because a PR is a record read
    later and what it asserts should not depend on how the run was driven.

- **`wikicommit-translate` now answers its own five-pair guard when no one is present**,
  taking the first five pairs rather than waiting (Issue #945). This is the answer
  `wikicommit-generate` already gives at the equivalent point. The pairs not taken are
  deferred by construction — nothing on disk changes for them, so the next run finds them
  again.
- **Page generation no longer creates a page for a document a source only cites in passing**
  (Issue #968). A contrastive citation, a line in a related-work paragraph, an entry in a
  reference list — when a source names another document once while writing about something
  else, that document is no longer extracted as an entity. Where the source treats that
  document, or the fact it is cited for, as its **own** subject — its title, or a central
  claim, is about it — nothing changes and it is still extracted.
  - **This was already the rule twice over, but only after the page had been written.** The
    generation step will not restate another document's date or title as established fact,
    and the review fails such a page with `MISSING_SOURCE`. Both sit after the entity has
    been cut, so the page was written and then discarded — and because the discard is
    recorded, the source kept matching the collection condition and every later run cut the
    same entity, wrote the same page and discarded it again. Nothing about the inputs
    changed between runs, so nothing about the outcome did either. That loop now ends on its
    own, with nothing to migrate.
  - **Pages already written this way are not removed for you.** Regeneration does not run
    this step, so an existing page built from a passing mention stays until someone takes it
    down with `/wikicommit-remove`. To find them, look for pages whose only source is a
    document that says almost nothing about them.
  - **Leaving an entity out this way is silent** — there is no exclusion note and no line in
    the completion notice, because the axis is neither relevance nor permissibility but
    evidence, and a reason code with no consumer is not worth adding. The instructions say
    plainly that the safe direction here is only one way round: dropping a genuine passing
    mention costs nothing, while dropping a document the source is actually about loses a
    page that review would have passed.

- **`/wikicommit-status` now says how many of the people who reviewed a page left a note**
  (Issue #952). Closing a review tracking Issue without a comment is a legitimate way to
  close it and stays that way — but until now every output looked the same either way, so
  whether the ask for a line ever reached anyone could not be seen at all. The review
  coverage row now carries that count.
  - **It counts whether a note exists, not what it says.** A one-word note and a paragraph
    are both one, so read it as "did the ask reach anyone", not as "was the page read".
    A low number is not reported as a problem anywhere, and nothing about it changes when
    a page is merged or published.
  - **Nothing on the published site changes.** The reader-facing counts come from each
    page's own review status and never look at the review records, so this number is for
    whoever runs the wiki.

### Fixed

- **The overview page no longer distorts the graph view** (Issue #957). `content/overview/`
  was added without being registered as a reserved prefix with either publishing plugin;
  the explorer half was fixed earlier, and this is the graph half. Unregistered, the node
  fell through to the entity path grammar and read as a page in a language called
  `overview`, which produced four symptoms at once: a language that does not exist appeared
  in the control bar's multi-select, picking a real language made the overview page vanish,
  its Top-N lists made it one of the largest hubs on the canvas, and — the one that decided
  the fix — its "orphans" section drew the twenty pages it reports as orphans with a link
  each, which is the opposite of what that section says. The graph explicitly protects the
  opposite ("entity nodes are never pruned … it is an orphan, which is exactly what the
  reader should be able to see"), and the overview page was quietly undoing it.
  - The page is now **excluded from the global graph outright** rather than given a toggle.
    A toggle's "on" side has nothing to offer: an edge from the overview means "this page is
    on a ranking", not "this page refers to that one". Readers still reach it from the root
    index and from the top of the left pane.
  - **The root index stays in the graph**, deliberately. Its outbound links are the language
    folders, `sources` and `overview` — it grows with the language count, never approaches
    the dozens a Top-N list carries, and states nothing its own edges contradict.
  - **Known limit**: the local graph still shows it. That view is a breadth-first walk from
    the current page, so removing a node after the fact severs paths and strands others. An
    orphan page's local graph therefore still has "Overview" next to it.

### Notes

- **No type template (`.wikicommit/schema/`) changed in this version, but a page generation
  rule did** (Issue #968): a document that a source only cites in passing is no longer cut
  as an entity. **Regenerating does not apply it.** Regeneration works from a page that
  already exists and skips entity extraction entirely, so a page written from a passing
  mention stays until someone takes it down with `/wikicommit-remove`. There is therefore
  no reason to regenerate pages for this version — the same conclusion as before, for a
  different reason.
- **This version arrives by two separate paths, and a wiki that takes only one gets half
  of it.** The Skill tree — the three descriptions and the generation rule above — comes
  with `npx skills add`, which `/wikicommit-update` deliberately does not touch. The
  distributed scripts and the Quartz plugins — the graph fix and the review-coverage count
  — come with `/wikicommit-update`.
- **The new `skillOverrides` block reaches new repositories only.** It is written by
  `/wikicommit-init`, so an already-installed wiki gets it from neither path. The guard
  that does reach one is the narrowed Skill description, which travels with the Skill tree.

## Earlier versions

One file per version, moved here as each new release lands so that this file stays
bounded and a reader only opens the versions between theirs and the latest.

| Version | Date | Entry |
|---|---|---|
| 0.6.1 | 2026-09-15 | [changelog/0.6.1.md](changelog/0.6.1.md) |
| 0.6.0 | 2026-09-14 | [changelog/0.6.0.md](changelog/0.6.0.md) |
| 0.5.0 | 2026-09-09 | [changelog/0.5.0.md](changelog/0.5.0.md) |
| 0.4.0 | 2026-09-07 | [changelog/0.4.0.md](changelog/0.4.0.md) |
| 0.3.0 | 2026-09-06 | [changelog/0.3.0.md](changelog/0.3.0.md) |
| 0.2.0 | 2026-09-01 | [changelog/0.2.0.md](changelog/0.2.0.md) |
| 0.1.0 | 2026-08-29 | [changelog/0.1.0.md](changelog/0.1.0.md) |
