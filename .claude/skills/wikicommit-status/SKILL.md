---
name: wikicommit-status
description: Show wiki health — orphan pages, wanted pages, unreviewed pages, expired pages, stale translations, outdated ingest sources
---

# wikicommit-status

A health-check skill for the wiki as a whole. Calls the six page-count scripts (`check_orphans.py` / `check_wanted_pages.py` / `check_expires.py` / `check_ingest_freshness.py` / `check_translation_status.py` / `check_derivation_freshness.py`) plus `check_actions_pr_permission.py` (a single repository-setting check, not a page count — Issue #478) and `check_property_wikilink_reinforcement.py` (a `.wikicommit/schema/` template check, not a page count either — Issue #539), aggregates their results, and displays them alongside the number of unprocessed `.wikicommit/source/` files and the number of unreviewed `.wikicommit/entity/` pages. This skill has no dedicated scripts of its own (only the existing scripts plus directory scanning).

## Usage

```
/wikicommit-status
```

No arguments. Always targets the whole repository.

## Processing Flow

### Step 1: Check for Unpulled Remote Changes

This skill only scans the local working tree. If PRs (e.g. post-review PRs from `/wikicommit-merge`) were merged on GitHub but not yet pulled locally, the results below will be stale — pages already `reviewed` on GitHub can still be counted as `review_status: pending` here.

Run `git fetch` (read-only; does not modify the working tree) and compare local `HEAD` against `origin/<current branch>` (e.g. via `git rev-list --count HEAD..origin/<branch>`). If the local branch is behind, warn the user before displaying results:

```
Note: your local branch is N commit(s) behind origin/<branch>. Results below may be stale
if PRs were merged on GitHub since your last pull. Run `git pull` first for an accurate picture.
```

Do not run `git pull` automatically — it could conflict with uncommitted local changes, and this skill is read-only by design (see Notes).

### Step 2: Disclose the Side Effect

`check_ingest_freshness.py` has the side effect of rewriting local `.wikicommit/source/` management files (it changes any management file with `status: generated / partial / outdated` whose hash mismatches to `outdated`. Management files with `status: pending / excluded / failed` are not checked even on a hash mismatch, and are not detected by this step). Disclose this to the user before running it:

```
Note: running check_ingest_freshness.py will rewrite the status of any .wikicommit/source/
management file whose source changed to outdated (local change only; will show up in git status).
Run /wikicommit-merge afterward to commit it.
```

### Step 3: Run the Six Scripts

Run the following in order, and for each, take the counts from its `SUMMARY:` line and the corresponding file paths from its `ORPHAN:` / `DUPLICATE:` / `WANTED:` / `page:` lines.

```bash
python .wikicommit/scripts/check_orphans.py
python .wikicommit/scripts/check_wanted_pages.py
python .wikicommit/scripts/check_expires.py
python .wikicommit/scripts/check_ingest_freshness.py
python .wikicommit/scripts/check_translation_status.py
python .wikicommit/scripts/check_derivation_freshness.py
```

- `check_orphans.py` → `SUMMARY: orphans=N, duplicates=N`. Get file paths from the `ORPHAN: <path>` / `DUPLICATE: <path> <-> <path> (title: "...")` lines (these two are the only categories without a `page:` line, so parse them directly).
- `check_wanted_pages.py` → `SUMMARY: wanted=N`. The counterpart to `check_orphans.py`: pages with WikiLinks pointing at them but no backing file in any language (Issue #340 — `check_wikilinks.py`'s missing-target case is a WARNING, not a blocking ERROR, so this report is how these surface for follow-up). Get the `Type/slug` keys from the `page:` lines; the referrer counts and paths are in the corresponding `WANTED:` line directly above each `page:` line.
- `check_expires.py` → `SUMMARY: expired=N`. Get file paths from the `page:` lines.
- `check_ingest_freshness.py` → `SUMMARY: outdated=N, ok=N`. Get file paths from the `page:` lines.
- `check_translation_status.py` → `SUMMARY: stale=N, missing_source=N, untranslated=N`. Get file paths from the `page:` lines (each `STALE:` / `MISSING_SOURCE:` / `UNTRANSLATED:` line is immediately followed by its corresponding `page:` line). `untranslated` is 0 whenever `.wikicommit/config.yml`'s `translation.targets` is empty (no target languages configured).
- `check_derivation_freshness.py` → `SUMMARY: stale=N, missing_source=N`. This is the `wikicommit-synthesize` counterpart of `check_translation_status.py`'s `STALE`/`MISSING_SOURCE` (same output shape, but walks `derived_from` entries instead of `translated_from`). Get file paths from the `page:` lines; a page with multiple stale/missing `derived_from` entries emits a `page:` line once per entry, so the same path may appear more than once here — dedupe when listing paths, but not when counting (the `SUMMARY:` counts entries, not pages). Keep this separate from `check_translation_status.py`'s own stale/missing counts in Step 6 below (different frontmatter field, different root cause — a translation going stale vs. a synthesized page's source going stale).

### Step 4: Check GitHub Actions PR Permission

```bash
python .wikicommit/scripts/check_actions_pr_permission.py
```

Unlike the six scripts in Step 3, this is a single repository-setting check, not a per-page count — it verifies "Allow GitHub Actions to create and approve pull requests" is enabled, which `review-issue-close-sync.yml`'s `Commit and open PR` step depends on (Issue #313). `wikicommit-init` attempts to enable this automatically at repository initialization time, but that attempt can silently fail with no trace in normal operation until a reviewer closes a tracking Issue days later and the workflow run fails deep in GitHub Actions logs (Issue #403). This is the only script this skill calls that invokes `gh`; it never writes to the repository setting itself (read-only, matching every other check).

Take the `OK:`/`WARNING:` line and `SUMMARY: enabled=<true|false|unknown|n/a>` — `n/a` means `review-issue-close-sync.yml` doesn't exist in this repository (not applicable) and `unknown` means the check itself couldn't run (unauthenticated `gh`, unresolvable repository, or a failed `gh api` call) — both are distinct from a confirmed `false`.

### Step 5: Check Property-Value WikiLink Reinforcement

```bash
python .wikicommit/scripts/check_property_wikilink_reinforcement.py
```

Also unlike the six scripts in Step 3, this checks `.wikicommit/schema/` type templates, not `.wikicommit/entity/` pages — for each `properties:` key whose Schema.org range includes a linkable entity type, whether the template gives any textual hint (`granularity` prose mentioning the property, or a `[[Type/slug]]` placeholder already in `properties:`) toward writing that property's value as a WikiLink (Issue #539, automating the manual cross-check Issue #523 did by hand). Purely a human-readability nudge, not a functional requirement — `wikicommit-generate` Pass 3 already applies the WikiLink decision uniformly to every such property regardless of whether the template reinforces it (`docs/DesignDoc-skills.md` §11.6), so an `UNREINFORCED:` finding here is not itself evidence anything is broken. `description` is expected to appear for nearly every type (its Schema.org range is Mixed via `TextObject`, but this wiki's convention keeps it as prose — `docs/DesignDoc-data.md` §4.1) — treat that specific recurring finding as expected noise, not a defect to chase down.

Get the `SUMMARY: unreinforced=N` count and the individual `UNREINFORCED: <Type>.<property> (<path>) — ...` lines.

### Step 6: Tally Unprocessed Ingest Files

Scan `.wikicommit/source/**/*.md` and read each file's frontmatter `status` field. Count the files with `status: pending` and record their paths.

### Step 7: Tally Unreviewed Pages

Scan `.wikicommit/entity/**/*.md` (excluding `index.md`) and read each file's frontmatter `review_status` field. Exclude pages with `status: removed` (as with `check_orphans.py` / `check_expires.py`, removed pages are not review targets). Count files with `review_status: pending`, or where the `review_status` field itself is absent (treated as `pending`, same as `validate_frontmatter.py`'s WARNING behavior), and record their paths.

### Step 8: Display Results

Display in the following format:

```
WikiCommit Status
==================
Unreviewed pages:       <N> (review_status: pending)
Orphan pages:           <N> (zero inbound links)
Duplicate pages:        <N>
Wanted pages:           <N> (linked but no page exists in any language)
Expired pages:          <N> (past expires_at)
Stale translations:     <N> (source_commit mismatch)
Missing translation source: <N> (translated_from target doesn't exist)
Untranslated pages:     <N> (no translation yet for a configured target language)
Stale synthesized pages: <N> (derived_from source_commit mismatch)
Missing synthesis source: <N> (derived_from path doesn't exist)
Unprocessed ingest sources: <N> (status: pending)
Updated sources:        <N> (status: outdated, ingest hash mismatch)
GitHub Actions PR permission: <status>
Unreinforced property-value WikiLinks: <N> (informational — see Step 5)
```

For any category with 1 or more hits, display the list of matching file paths (or, for the last line, the `UNREINFORCED:` lines) directly below that category.

`GitHub Actions PR permission` is not a count — display Step 4's `OK:`/`WARNING:` line verbatim as `<status>` (e.g. `OK: acme/example-wiki: "Allow GitHub Actions to create and approve pull requests" は有効です`, or the full `WARNING: ...` message including the enable command). Skip this line entirely when `SUMMARY: enabled=n/a` (repository doesn't use `review-issue-close-sync.yml`).

If every category above is 0 **and** `enabled` is `true` or `n/a`, display "Wiki is healthy" instead of the above (a `false`/`unknown` permission state blocks the "healthy" verdict even when every page-level category is clean, since it silently breaks the review-close automation). `Unreinforced property-value WikiLinks` does not gate this verdict either way — it is purely informational (Step 5) and, per that step's `description` caveat, is realistically almost never 0 on any repository using the standard type templates, so requiring it to be 0 would make the "healthy" verdict effectively unreachable.

### Step 9: Cleanup Guidance

If the `outdated` count in step 3's `check_ingest_freshness.py` `SUMMARY:` line is 1 or more (whether newly rewritten this run or already `outdated` before), append the following guidance:

```
Some .wikicommit/source/ management files have status: outdated (either just rewritten by this run,
or already in that state — either way, this is a local change only and will show up in git status).
Run /wikicommit-merge to commit it.
```

## Notes

- Do not commit or create a PR against `main` or any branch
- Do not write to `.wikicommit/schema/`
- No script other than `check_ingest_freshness.py`, and no part of the steps 3, 6–7 scans, has side effects (read-only). `check_actions_pr_permission.py` (Step 4) and `check_property_wikilink_reinforcement.py` (Step 5) are read-only too — unlike `wikicommit-init`'s Step 3, `check_actions_pr_permission.py` never attempts to enable the GitHub Actions PR permission setting itself, only reports its current state
