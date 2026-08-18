---
name: wikicommit-schema-propose
description: Detect wiki page types with no dedicated .wikicommit/schema/ file, propose a new standard (Schema.org) or custom type file, and open a PR for human review (no auto-merge)
disable-model-invocation: true
---

# wikicommit-schema-propose

Detects `type:` values used by wiki pages that have no dedicated `.wikicommit/schema/` file, and proposes a new schema type file via PR (Issue #285). `.wikicommit/schema/` itself is off-limits to write directly from `wikicommit-generate` (that Skill's "Git operations: none, schema/: read-only" contract), so this Skill exists to be the one place schema files actually get added — and only by adding new files, never editing or deleting existing ones.

This complements `coverage_gap_note` (`wikicommit-generate` Pass 2, Issue #284): that mechanism records when an already-correct type is missing a *field*; this Skill addresses when the *type itself* isn't the best fit — e.g. pages generated as `schema:DefinedTerm` when `schema:Game` (with `typicalAgeRange`/`gameItem`/`numberOfPlayers`) would fit better, or `schema:HowTo` when `schema:GovernmentService` (with `jurisdiction`/`availableChannel`/`hoursAvailable`) would fit better. The two do not integrate — `wikicommit-schema-propose` does not consume `coverage_gap_note`.

## Usage

```
/wikicommit-schema-propose
```

No arguments. Always runs a full scan.

## Processing Flow

### Step 0: Resolve Default Branch

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
```

Record the result as `<default branch>` and use it everywhere below in place of a literal `main` (Issue #351 — the repository's actual default branch is not guaranteed to be `main`). If this command fails (no GitHub remote, or `gh` not authenticated), fall back to `main` and warn the user that Step 6's branch/PR operations will fail if the repository's real default branch differs.

### Step 1: Detect coverage gaps

```bash
python .wikicommit/scripts/check_schema_coverage.py
```

Parse each `UNCOVERED: <type> (<N> pages, e.g. <path>)` line — this is the deterministic, guaranteed-complete detection source (a scan of every page currently in `.wikicommit/entity/`). If none, report "No schema coverage gaps found" and stop.

> **Role since Issue #315**: `wikicommit-generate` Pass 2b now resolves most type-necessity judgments inline, at generation time, by writing an approved `.wikicommit/schema/<Type>.md` directly (no PR, no `better_type_candidate` field — that field was removed). This Skill's `check_schema_coverage.py` scan therefore now mainly serves as the **post-hoc safety net**: pages generated before Issue #315 shipped (when `better_type_candidate` was only ever a Completion Notice suggestion, easy to lose across sessions — the exact problem #315 fixed), or any future page that ends up using a type with no dedicated schema file through some other path. It is no longer the primary channel for new type proposals.

### Step 2: Skip types that already have a proposal

For each detected type, compute `<Type>` (the `type:` value with the `schema:` prefix stripped, e.g. `schema:Game` → `Game`, `schema:custom/Recipe` → `custom/Recipe`) and `<TypeSlug>` (`<Type>` with `/` replaced by `-`, e.g. `custom/Recipe` → `custom-Recipe`) — same convention as `wikicommit-merge`'s post-review PR branch naming.

```bash
gh pr list --head "wikicommit/schema-propose-<TypeSlug>" --state all --json number
```

One or more results (open **or** closed/rejected) → skip this type; do not re-propose it. Move to the next detected type. Do not batch this into a single unscoped `gh pr list` call — same `--head`-scoping rationale as `wikicommit-merge` §"Checking for Existing PRs".

### Step 3: Classify as standard or custom

```bash
python .wikicommit/scripts/check_schema_org_type.py --type <Type>
```

- Exit `0` → `<Type>` is a real Schema.org type. Continue with the **Standard type path** (Step 4).
- Exit `1` → not in the Schema.org vocabulary. Continue with the **Custom type path** (Step 5).

### Step 4: Standard type path

1. Using the example page(s) from Step 1, select 3–6 Schema.org properties that materially matter for the observed content — the same judgment `wikicommit-generate` Pass 3 already exercises when filling in a schema template. Rather than relying on memory of the vocabulary, browse `<Type>`'s full available property set first (Issue #497 — the on-demand replacement for the old `recommended` field's role, since Issue #495 removed it):

   ```bash
   python .wikicommit/scripts/check_schema_org_type.py --type <Type> --list-properties
   ```

   Each line is `<property><TAB><declaring type><TAB><entity-range candidates, or "-"><TAB><one-line description>` — pick candidates from this list, matched against what the example page(s) actually discuss. Also pick one candidate parent/near-neighbor type name to consider, if any (used only as commentary — this Skill still creates one file for `<Type>` as-is).
2. Verify every selected property actually belongs to `<Type>` (or one of its ancestors):

   ```bash
   python .wikicommit/scripts/check_schema_org_type.py --type <Type> \
     --property "$(cat <<'EOF'
   <Prop1>
   EOF
   )" \
     --property "$(cat <<'EOF'
   <Prop2>
   EOF
   )" \
     ...
   ```

   Each `--property` value goes through its own quote-delimited heredoc (`docs/DesignDoc-skills.md` §11.7) — these are candidate names this step itself just proposed, not values an earlier script already verified. Drop any property the script reports as `ERROR:` from the candidate list — **never** put an unverified property into the new schema file's `properties:` block. If every candidate property fails verification, proceed with an empty `properties:` block rather than skipping the proposal (the type itself is still verified as real; missing property suggestions is not a blocker for opening the PR — reviewers can add fields by hand).
3. Generate `.wikicommit/schema/<Type>.md` in the standard-type format (`docs/DesignDoc-data.md` §5.2, Issue #495's `properties:`-nested layout). Use `.wikicommit/schema/default.md` (frontmatter skeleton) and `.wikicommit/schema/Person.md` (a concrete, already-standard example) as **fixed** style references — do not attempt dynamic "closest existing type" selection:
   - `wikicommit.base: https://schema.org/<Type>`
   - `wikicommit.provenance: schema-propose` (`docs/DesignDoc-data.md` §5.2, including the "don't copy `Person.md`'s own `provenance: default`" caveat — applies uniformly to both the standard-type and custom-type paths of this Skill, see Step 5 below)
   - `wikicommit.granularity:` 1–3 rules in the same style as `Person.md`/`DefinedTerm.md`, grounded in the observed example page(s). If a property that would technically apply to `<Type>` should deliberately not be recorded (the old `excluded` field's role), state that as a granularity rule in prose instead (e.g. "Do not record `<property>` even when the source states it — out of scope for this wiki's purpose"), rather than declining to verify/list it silently.
   - Frontmatter template fields: `title`, `type: "schema:<Type>"`, `lang`, `sources: []`, `tags: []`, then a blank line and a `properties:` block with one empty-string (or empty-list, matching each verified property's expected shape) placeholder per verified property from step 2 — plus a short body template (2–3 paragraph overview placeholder + a `## Details`-style section), following `default.md`'s shape

### Step 5: Custom type path

1. Derive `<Name>` (the segment after `custom/`) from the `type:` value already used by the detected pages. It must already follow `docs/DesignDoc-data.md` §5.3's naming rule (PascalCase, word characters only, no hyphen) — this Skill only *adds* the missing schema file, it never renames the `type:` value on existing wiki pages. If it doesn't follow the rule (e.g. contains a hyphen), skip this type, log a warning naming the offending pages, and move to the next detected type — renaming is out of scope and left to a human via `wikicommit-fix`.
2. Generate `.wikicommit/schema/custom/<Name>.md` in the custom-type format (`docs/DesignDoc-data.md` §5.3) — unlike a standard type, explicitly document each property's meaning/type/constraints in prose, since the LLM has no built-in knowledge of a project-specific custom type. Pick a `wikicommit.base` value that names the closest real Schema.org parent type as a reference point (informational only, not verified against the vocabulary — custom types by definition fall outside it). Set `wikicommit.provenance: schema-propose` here too (Step 4's note above applies uniformly to both paths).
3. No `check_schema_org_type.py` property verification applies here (nothing to check against). Instead, write one or two sentences explaining *why no existing Schema.org standard type fits* — this becomes the PR's "Schema.org 標準型で代替できない理由" checklist item (see below) and is the human reviewer's main thing to scrutinize for a custom type.

### Step 6: Branch, commit, PR (no auto-merge)

Repeat for each type that reached this step (mirrors `wikicommit-merge`'s post-review PR mechanics, but this Skill's PRs are never auto-merged):

```bash
# 1. Branch from the default branch's HEAD (<default branch> from Step 0)
git checkout "<default branch>"
git checkout -B wikicommit/schema-propose-<TypeSlug>

# 2. Write the new schema file (Write tool) — ONE new file only, never edit/delete an existing one
#    .wikicommit/schema/<Type>.md            (standard type)
#    .wikicommit/schema/custom/<Name>.md      (custom type)

# 3. Commit
git add .wikicommit/schema/<path from step 2>
git commit -m "$(cat <<'EOF'
schema: propose <Type> for <N> uncovered pages

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
Generated-By:   claude-sonnet-4-6
EOF
)"

# 4. Push -> PR (no --auto, no gh pr merge anywhere in this Skill)
git push origin wikicommit/schema-propose-<TypeSlug>
gh pr create \
  --title "$(cat <<'EOF'
schema: propose <Type>
EOF
)" \
  --body "<PR Description Template below>" \
  --base "<default branch>"

# 5. Return to the default branch
git checkout "<default branch>"

# 6. Brief pause before the next type's push/PR-create (GitHub secondary rate limit)
sleep 2
```

`--title` is passed through a quote-delimited heredoc (`docs/DesignDoc-skills.md` §11.7) rather than a plain double-quote embedding, uniformly for both the standard-type and custom-type paths (Issue #398). The two paths were evaluated separately: on the standard-type path `<Type>` is already confirmed real by `check_schema_org_type.py --type <Type>` in Step 3, and Schema.org vocabulary identifiers are themselves alphanumeric CamelCase (no shell metacharacters are possible), so that path alone would qualify for §11.7's "upstream-validated constrained identifier" exemption. On the custom-type path, though, Step 5.1's naming-rule check ("must follow PascalCase, word characters only, no hyphen") is an instruction the LLM carries out by reading the page's existing `type:` value, not a deterministic script-enforced check — so it does not strictly meet the exemption's bar of validation "by an upstream script or command". Rather than branch the `--title` construction on which path produced `<Type>`, the heredoc is applied unconditionally: it costs nothing on the already-safe standard-type path (same reasoning `wikicommit-merge` already uses for applying `:(literal)` uniformly), and it closes the gap on the custom-type path without depending on the rigor of the Step 5.1 LLM check.

Skip step 6 after the last proposed type. If `git push` or `gh pr create` errors, log it, leave the branch for cleanup, and move to the next type rather than aborting the whole run (same resilience pattern as `wikicommit-merge`'s post-review PR loop).

#### PR Description Template

```markdown
## Proposed type

`schema:<Type>` — <N> existing page(s) currently fall back to `default.md` for this type.

## Affected pages (examples)

- <path from Step 1, one per line, up to 5>

## Checklist for review

- [ ] Page count and examples above look right for this type
- [ ] Schema.org standard type could not reasonably replace this <!-- only present for a custom-type proposal -->
- [ ] `properties:` field choices are appropriate
- [ ] `granularity` rules make sense for how this Wiki actually uses the type
- [ ] Next-best alternative type, if any: <alternatives from Step 1, or "none">

🤖 Generated with a [wikicommit-schema-propose](https://github.com/wikicommit/wikicommit) proposal — merge only after reviewing the schema file's actual content, this description alone is not sufficient review.
```

### Completion Notice

Report, per detected type: proposed (with PR link) / skipped (duplicate proposal exists) / skipped (invalid custom name) / failed (push or PR-create error).

## Notes

- Only ever **adds** a new file under `.wikicommit/schema/`. Never edits or deletes an existing schema file.
- Never touches `.wikicommit/entity/` — existing pages keep using their current `type:` value; migrating them to the newly proposed type (if desired) is a separate, human-driven decision.
- Never auto-merges. Every PR this Skill opens waits for a human to review and merge it manually (unlike `wikicommit-merge`'s bulk-update PR or `review-and-merge`'s post-review PR flow).
- `.wikicommit/schemaorg-vocab.json` (built lazily by `check_schema_org_type.py`, committed to Git — Issue #319) has no TTL/auto-refresh — delete it manually to force a rebuild against the latest Schema.org vocabulary.
