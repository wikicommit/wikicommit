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

## [0.6.1] - 2026-09-15

### Fixed

- **A `summary` field description survived Issue #831's fix, so an exclusion reason could
  still land in the one section the wiki publishes** (Issue #943). Issue #831 moved
  `exclude_note`/`coverage_gap_note` out of `## Summary` — the one prose section
  `_write_source_page()` renders to `content/sources/` — because a policy whose whole
  purpose is not writing about a person was publishing the result of its own application
  under that person's name. That fix rewrote the write-back instructions but missed the
  field description the model actually fills in: `references/pass2c-entities.md` still
  asked, in the same breath as asking for a summary, to "briefly note the reason" for any
  exclusion right there in `summary`. A model that read the field description literally
  kept folding the reason into the very string that ends up on the public page, no matter
  how strict the write-back step downstream was.
  - The field description no longer mentions exclusions at all; the prose introducing the
    JSON block now names `exclude_note` as where the reason goes, so the prohibition reads
    as a redirection rather than a bare "don't."
  - The example analysis JSON in the design docs had the same leak folded into its
    `summary` example value; dropped, since the example's `entities[]` already carries
    `exclude_reason`/`exclude_note`.
  - Four exclusion notes already published this way (three naming a living person) are not
    retroactively fixed by this change — the management files that hold them predate the
    fix and are `update: skip`. Removing them is a `/wikicommit-reconcile` job for the
    affected repository, not something this version does on its own.

### Notes

- **No type template (`.wikicommit/schema/`) changed in this version.** The fix is
  instruction prose in `references/pass2c-entities.md` and an example in the design docs;
  it changes what a source management file's `## Summary`/`## Generation Notes` split
  looks like for newly processed sources, not how any entity page is written. **There is
  therefore no reason to regenerate pages for this version.**

## Earlier versions

One file per version, moved here as each new release lands so that this file stays
bounded and a reader only opens the versions between theirs and the latest.

| Version | Date | Entry |
|---|---|---|
| 0.6.0 | 2026-09-14 | [changelog/0.6.0.md](changelog/0.6.0.md) |
| 0.5.0 | 2026-09-09 | [changelog/0.5.0.md](changelog/0.5.0.md) |
| 0.4.0 | 2026-09-07 | [changelog/0.4.0.md](changelog/0.4.0.md) |
| 0.3.0 | 2026-09-06 | [changelog/0.3.0.md](changelog/0.3.0.md) |
| 0.2.0 | 2026-09-01 | [changelog/0.2.0.md](changelog/0.2.0.md) |
| 0.1.0 | 2026-08-29 | [changelog/0.1.0.md](changelog/0.1.0.md) |
