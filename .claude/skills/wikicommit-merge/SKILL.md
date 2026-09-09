---
name: wikicommit-merge
description: Run quality gates on local WikiCommit changes, then branch, PR, merge to the repository's default branch, and open per-page post-review tracking Issues
disable-model-invocation: true
---

# wikicommit-merge

Runs quality checks against the uncommitted changes under `.wikicommit/` (wiki pages, source management files), then performs branch creation, PR creation, merge (without relying on GitHub's auto-merge feature — see Step 7, Issue #456), merge confirmation, and post-review tracking Issue generation end-to-end.

## Usage

```
/wikicommit-merge
```

## Processing Flow

### Step 0: Open a Run Record and Resolve Default Branch

```bash
python .wikicommit/scripts/record_run.py start --skill wikicommit-merge \
    --model "<the model ID this runtime reports for you>"
```

Keep the path it prints; Step 10 closes it. A record with a start and no end is what says a run did not finish, and this Skill has more ways to stop partway than any other here — a blocking quality check in Step 3, a PR that never reaches a mergeable state in Step 7, a rate-limited Issue creation in Step 8 — several of which leave a branch and a PR behind with nothing recording that a run was underway (Issue #790). Leaving the record open is that signal, not a failure state to avoid.

Then:

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
```

Record the result as `<default branch>` and use it everywhere below in place of a literal `main` (Issue #351 — an existing repository's actual default branch is not guaranteed to be `main`, e.g. a pre-2020 repository still on `master`; hardcoding `main` makes every PR/merge operation in this Skill fail silently on such repositories). If this command fails (no GitHub remote configured, or `gh` not authenticated), fall back to `main` and warn the user that Step 6's PR creation and Step 7's return-to-default-branch will fail if the repository's real default branch differs.

### Step 1: Detect Changes

```bash
git -c core.quotePath=false status --porcelain -- ".wikicommit/entity/**/*.md" ".wikicommit/view/**/*.md" ".wikicommit/source/**/*.md" ".wikicommit/review/**/*.md" ".wikicommit/entity/assets/**" ".wikicommit/source-policy.md" ".wikicommit/entity-policy.md"
```

> The `.wikicommit/entity/assets/**` pathspec covers assets — images and attachments under `.wikicommit/entity/assets/` (Issue #589). Without it, a run that only adds an image stops at "No changes to merge" and the asset is never committed, even though Step 5's `git add` (which takes directories, not `*.md`) would have staged it had some other `.md` change carried the run that far. Note this is detection only: assets must **not** enter `<changed .md files>` in Step 2 item 1, whose pathspec stays `*.md`-only — every quality check it feeds (`validate_frontmatter.py`, `check_wikilinks.py`, `check_raw_html.py`, `markdownlint-cli2`) parses frontmatter and would fail on a PNG. Because of that, an assets-only run reaches Step 3 with an **empty** `<changed .md files>`; see Step 3, which must skip the per-file checks in that case rather than invoking them with no paths.
>
> The `.wikicommit/view/**/*.md` pathspec covers the view tree (Issue #675) — second-order pages grounded in this wiki's own pages (`derived_from`) rather than in an external document, which `/wikicommit-synthesize` writes there. Unlike assets and the policy files below, these **are** wiki pages and do belong in `<changed .md files>`: every per-file check handles them (`validate_frontmatter.py` applies the view-page rules, `check_wikilinks.py` resolves `[[View/<slug>]]`, `check_raw_html.py` and `markdownlint-cli2` are content checks that do not care which tree a page came from). A wiki that has never run `/wikicommit-synthesize` has no such directory, and the pathspec simply matches nothing.
>
> The two policy-file pathspecs cover `.wikicommit/source-policy.md` (Issue #564) and `.wikicommit/entity-policy.md` (Issue #667). `wikicommit-collect`'s Step 8 appends a declined candidate to that file's `rejected:` list, and neither `.wikicommit/entity/` nor `.wikicommit/source/` contains it (`.wikicommit/source/` is a directory pathspec and does not match the sibling file `source-policy.md`). Without this pathspec a collect run in which the user declines every candidate stops at "No changes to merge" and the record of that decision is never committed — which defeats the whole point of the list, since the next free exploration re-proposes the source it was meant to remember. Like assets, this is a `.md` file that must **not** enter `<changed .md files>` in Step 2 item 1: it is not a wiki page, and `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` would all fail on it. Step 2 item 6 stages them separately. The entity policy is there for the same reason one axis over — it is hand-edited prose deciding whether an entity may be written about at all, and `wikicommit-generate` acts on it, so a run in which the human edits only that file must not stop at "No changes to merge".
>
> The `.wikicommit/review/**/*.md` pathspec covers the review records (Issue #750) — one immutable file per review, written by `record_review.py` under `.wikicommit/review/`. They are what makes "every page was reviewed" a checkable statement rather than an assertion, so a run whose records are never committed is indistinguishable from one where no review happened. Like assets and the policy files, these are `.md` files that must **not** enter `<changed .md files>` in Step 2 item 1: they are not wiki pages, and `validate_frontmatter.py` / `check_wikilinks.py` would fail on them. Step 5's `git add` takes the directory.
>
> Note also that `lychee` is invoked with an explicit path argument (Step 3), so it does not walk this tree — a record's `source_file` can hold a URL, and an unscoped run would re-fetch every one of them on every merge.
>
> `git diff --name-only HEAD` does not detect untracked files. Wiki pages and management files newly generated by `wikicommit-generate` are untracked (not yet `git add`-ed), so use `git status --porcelain` instead (it lists untracked files too, in `?? path` form).
>
> `-c core.quotePath=false` is applied to every `git status --porcelain` call in this skill (also in Step 2, items 1 and 3). By default, paths containing non-ASCII characters (e.g. Japanese filenames) are quoted and octal-escaped in the output, and naively extracting them as `rest = line[3:]` yields a path string that doesn't actually exist (Issue #115).

If the output is empty → close the run record (`python .wikicommit/scripts/record_run.py end <the path Step 0 printed>`), display "No changes to merge" and stop. Close it here rather than leaving it open: this is the Skill finding nothing to do and saying so, which is a run that finished, and it is a common enough outcome that leaving the record open would fill `check_run_records.py`'s `INCOMPLETE_RUN:` list with runs that had no problem — diluting the signal it exists to carry (Issue #790).

### Step 2: Classify Changed Files

1. Obtain **`<changed .md files>`**:

   ```bash
   git -c core.quotePath=false status --porcelain -- ".wikicommit/entity/**/*.md" ".wikicommit/view/**/*.md"
   ```

   Strip the leading 2-character status code (`??`, ` M`, `A `, `D `, etc.) and the following space from each line to extract the path. For rename lines (`R  old -> new`), use only the path to the right of `->`.

   Exclude files with status `D` (deleted) — i.e. files with no on-disk content — from `<changed .md files>` (`validate_frontmatter.py` / `check_wikilinks.py` assume they can read the current frontmatter, and cannot validate a file that no longer exists. The removal flow only assumes soft deletion via `status: removed`; physical file deletion is out of scope for this skill).

2. Determine **`<files being removed>`** (files in `<changed .md files>` that satisfy both of the following):
   - `git show HEAD:<path>` succeeds and the retrieved frontmatter's `status` is not `removed` (if `git show HEAD:<path>` fails because the file is new, it is not in scope for the removal flow)
   - The current file's frontmatter has `status: removed`

   If no files match, `<files being removed>` is empty.

3. Determine **`<new source files>`** (Issue #106: commit timing for the actual source files targeted by `wikicommit-generate`):

   From each line produced by:

   ```bash
   git -c core.quotePath=false status --porcelain -- ".wikicommit/source/**/*.md"
   ```

   exclude lines whose status code (leading 2 characters) contains `D` (deleted), since those have no on-disk content (same rule as Step 2 item 1). For each remaining changed file (new or updated), read the frontmatter's `source.type` and `source.path`. Only run the following when `source.type: path` (`url` / `wikicommit` are out of scope since they have no file entity in the repository):

   First, check whether `<source.path>` exists on disk (e.g. `test -e -- "<source.path>"`, or an equivalent direct file check). This check must run, and its result must be branched on, **before** the git status command below is ever invoked for this file. `git status --porcelain` only reports on paths it finds in the working tree, so a `source.path` that was deleted after ingest registration produces the exact same empty output as a `source.path` that is tracked with no changes — the two cases cannot be told apart from the git status output alone (Issue #368).

   - `<source.path>` does not exist on disk (e.g. deleted after ingest registration) → do not add to `<new source files>`; print `WARNING: <source management file path>: source.path (<source.path>) does not exist` to the console (non-blocking); do not run the git status command below for this file
   - `<source.path>` exists on disk → run:

     ```bash
     git -c core.quotePath=false status --porcelain --ignored -- ":(literal)<source.path>"
     ```

     Never pass `<source.path>` as-is as a pathspec — always prefix it with `:(literal)` (Issue #115). By default, pathspecs after `--` are interpreted as fnmatch-style patterns, so if `source.path` contains metacharacters such as `[`, `]`, `*`, `?` (e.g. `raw/report[2024].pdf`), it may unintentionally match an unrelated file (`[2024]` gets interpreted as a character class, and an unrelated file in the same directory can be returned as `??` even when the target file doesn't exist). `:(literal)` disables this pattern interpretation and matches `source.path` as an exact byte string.

     - Output starts with `??` (untracked — never committed to the repository) → add to `<new source files>`
     - Output starts with `!!` (ignored via `.gitignore`) → do not add; print `WARNING: <source management file path>: source.path (<source.path>) is excluded by .gitignore and will not be included in the commit` to the console (non-blocking). Without `--ignored`, ignored files produce the same empty output as the "tracked, no changes" case, making the two indistinguishable — hence `--ignored` is required
     - Output is empty (tracked, no changes) → do not add. Because existence was already confirmed above, an empty result here unambiguously means "tracked, no changes" — it can no longer also mean "does not exist". A file that already existed before ingest registration (e.g. `src/auth.py`) has already been committed for another purpose, and this skill need not concern itself with it
     - Output starts with ` M`, etc. (tracked but has uncommitted changes) → do not add. This is deliberately out of scope, to avoid accidentally sweeping in unrelated code changes into the commit

   If no files match, `<new source files>` is empty.

4. Determine **`<new schema files>`** (Issue #315: `wikicommit-generate` Pass 2b may write a new `.wikicommit/schema/<Type>.md` file locally, for a Schema.org type outside `installed schema/` that was approved for that run — either by a human at the Enter prompt, or, in a non-interactive run, auto-approved with no prompt shown after clearing a stricter bar (Issue #507); `wikicommit-collect`'s Step 7 — Issue #489 — is a second, equally valid source of the same kind of untracked file, always approved the Enter-based way over a batch of source candidates before their registration, since that step always runs interactively). This batch does not distinguish a human-approved schema file from a non-interactively auto-approved one — both are picked up and committed the same way; auto-approved ones carry no marker of that fact beyond the originating session's own Completion Notice (Issue #507).

   ```bash
   git -c core.quotePath=false status --porcelain -- ".wikicommit/schema/*.md" ".wikicommit/schema/**/*.md"
   ```

   `git status --porcelain` pathspec globbing treats `**` as matching one or more directory levels, not zero or more (verified against git 2.54.0), so `.wikicommit/schema/**/*.md` alone never matches files directly under `.wikicommit/schema/` (e.g. a standard-type file Pass 2b writes there, per Issue #315) — only files nested one level deeper (e.g. `.wikicommit/schema/custom/<Name>.md`). Passing both pathspecs together covers both cases in a single call; `git status --porcelain` deduplicates any file that happens to match both (Issue #355).

   - Output starts with `??` (untracked — never committed) → add to `<new schema files>`
   - Any other status (e.g. ` M`, tracked with uncommitted changes) → do not add; print `WARNING: <path>: an existing schema file has uncommitted changes and will not be included in this batch — .wikicommit/schema/ edits to already-committed files are never auto-merged (only wikicommit-schema-propose's own, separately-reviewed PR touches an existing schema file)` to the console (non-blocking). This should not normally happen — Pass 2b only ever adds a file, never edits one — but this guard keeps an unexpected manual edit from slipping into an auto-merged batch.

   If no files match, `<new schema files>` is empty.

5. Determine **`<new vocab file>`** (Issue #319: `check_schema_org_type.py` lazily builds `.wikicommit/schemaorg-vocab.json` on first use — from `wikicommit-generate` Pass 2b/2c or `wikicommit-schema-propose` — and unlike `.wikicommit/.cache/`, this file is committed to Git rather than gitignored):

   ```bash
   git -c core.quotePath=false status --porcelain -- ".wikicommit/schemaorg-vocab.json"
   ```

   - Output starts with `??` (untracked — never committed) → set `<new vocab file>` to this path
   - Any other status (e.g. ` M`, tracked with uncommitted changes, or no output at all) → do not add. A modified-but-already-tracked vocab file (e.g. someone manually deleted and regenerated it to refresh the Schema.org vocabulary) is a deliberate content update, not this Skill's routine bulk-update commit — leave it for the user to commit and review separately, the same way `.wikicommit/schema/` edits to an already-committed file are excluded from item 4 above.

   If no file matches, `<new vocab file>` is empty.

6. Determine **`<policy files>`** — zero, one or both of the two sibling policy files (Issue #564: `wikicommit-collect`'s Step 8 appends a declined candidate to `wikicommit.rejected` in `.wikicommit/source-policy.md`; Issue #667: `.wikicommit/entity-policy.md` is hand-edited only. The human may have edited either one's prose by hand). One variable holds both because they are staged identically and neither needs to be told apart downstream:

   ```bash
   git -c core.quotePath=false status --porcelain -- ".wikicommit/source-policy.md" ".wikicommit/entity-policy.md"
   ```

   - For each of the two paths that appears in the output at all (`??` untracked, or ` M` tracked-with-changes) → add it to `<policy files>`
   - Neither appears → `<policy files>` is empty

   Unlike items 4 and 5, a **modified** tracked file is the normal case here rather than a red flag: the file exists from `/wikicommit-init` onward and every legitimate write to it is an in-place edit. Nothing else in WikiCommit ever commits it, so excluding modified copies would leave the append permanently uncommitted. It carries no wiki content and is not published, so no quality gate applies to it.

### Step 3: Quality Checks (Sequential)

Run the following in order. Blocking status is determined not by each tool's exit code but by the criteria in the table below (whether the script printed `ERROR:` / `DUPLICATE:`; lychee and markdownlint-cli2 are always non-blocking). As soon as a blocking error occurs, stop running further checks, display the error to the user, and abort (leave the working tree changes as-is; do not create a branch).

```bash
python .wikicommit/scripts/validate_frontmatter.py <changed .md files>
python .wikicommit/scripts/check_wikilinks.py --changed <changed .md files> [--deleted <files being removed>]
python .wikicommit/scripts/check_raw_html.py <changed .md files>
lychee --config .lychee.toml .wikicommit/entity/
npx markdownlint-cli2 --config .markdownlint.json <changed .md files>
python .wikicommit/scripts/check_orphans.py
```

If `<changed .md files>` is empty (e.g. an assets-only run, or a run that only rewrote source management files), **skip the four per-file checks entirely** — `validate_frontmatter.py`, `check_wikilinks.py`, `check_raw_html.py` and `markdownlint-cli2` — and run only `lychee` and `check_orphans.py`. Do not invoke them with no paths: `validate_frontmatter.py`, `check_raw_html.py` and `check_wikilinks.py` all interpret "no arguments" as "check every page under `.wikicommit/entity/`" (Issue #571 gave `check_wikilinks.py` that behaviour too), which would block this batch on pre-existing errors in pages it never touched — and `check_wikilinks.py --changed` with no values after it aborts with an argparse usage error while printing no `ERROR:` line, i.e. it silently counts as a pass under the blocking rule above without ever having run. Neither shape is an acceptable substitute for skipping.

Omit the `--deleted` option entirely when `<files being removed>` is empty. When `<changed .md files>` is large, use `xargs` to avoid exceeding the command-line length limit, e.g. (assuming the paths from `<changed .md files>` are stored one per line in a shell array `changed_md_files`, populated from Step 2's file list before running this step):

```bash
printf '%s\n' "${changed_md_files[@]}" | xargs -- python .wikicommit/scripts/validate_frontmatter.py
printf '%s\n' "${changed_md_files[@]}" | xargs -- python .wikicommit/scripts/check_raw_html.py
printf '%s\n' "${changed_md_files[@]}" | xargs -- npx markdownlint-cli2 --config .markdownlint.json
```

Run these as direct Bash-tool invocations exactly as shown above. Do not write an ad-hoc Python `subprocess` wrapper (e.g. building the file list via a temp file + `cat`/`tr`, or calling `subprocess.run(['npx', ...])`) to work around a large file count — doing so has caused real failures on Windows: `subprocess.run(['npx', ...], shell=False)` raises `FileNotFoundError` because `npx` resolves to `npx.cmd` on Windows and requires `shell=True` (or an explicit path to `npx.cmd`) to be found, and passing paths through a temp file plus `cat`/`tr` has silently dropped every path in practice. `xargs` piped directly from the Bash tool avoids both failure modes and needs no Windows-specific handling.

| Script / tool | Blocking condition (equivalent to exit code 1) | Warning only |
|---|---|---|
| `validate_frontmatter.py` | Any `ERROR:` output | Any `WARNING:` output |
| `check_wikilinks.py` | Any `ERROR:` output | Any `WARNING:` output |
| `check_raw_html.py` | Any `ERROR:` output (raw HTML tag detected in page body) | Any `WARNING:` output |
| `lychee` | None (always warning only) | HTTP 4xx, timeouts, connection errors |
| `markdownlint-cli2` | None (always warning only) | All violations (not made blocking in Phase 2) |
| `check_orphans.py` | Any `DUPLICATE:` output (duplicate pages) | Any `ORPHAN:` output |

If all checks finish with no blocking errors but some warnings remain, present the warnings to the user and confirm whether to proceed. If the user chooses not to proceed, abort (no branch has been created yet at this point, so the working tree changes remain as-is).

### Step 4: Create Branch

```bash
git checkout -b wikicommit/merge-$(date +%Y%m%d-%H%M%S)
```

Branch naming rule (exception): use the form `wikicommit/merge-<YYYYMMDD>-<HHMMSS>`. CLAUDE.md's `issue-NNN` convention is for issue-driven development branches and does not apply to the temporary branches this skill auto-generates.

### Step 5: Commit

```bash
git add -- .wikicommit/entity/ .wikicommit/view/ .wikicommit/source/ .wikicommit/review/ <new source files...> <new schema files...> <new vocab file> <policy files...>
git commit -m "$(cat <<'EOF'
wiki: bulk update <YYYY-MM-DD>

Co-Authored-By: <Claude display name> <noreply@anthropic.com>
Generated-By:   <current model ID>
EOF
)"
```

**The trailer's model fields are placeholders, not literals (Issue #559).** Replace `<current model ID>` with the ID of the model actually running this skill — the same self-reported value `wikicommit-generate` writes into a page's `generated_by`, spelled exactly as the runtime reports it (keep any suffix; do not shorten or normalize it). Replace `<Claude display name>` with that model's human-readable name, or write just `Claude` when the running model's display name is not known with confidence: GitHub links a co-author by the email address, not by the name, so a conservative `Claude` costs nothing while a guessed name misattributes the commit in the GitHub UI. `<noreply@anthropic.com>` is a fixed literal. Never hardcode a model ID here — a commit whose trailer names one model while the page frontmatter it is committing records another is self-contradictory, and defeats the stated purpose of `Generated-By` (precise tracking of which model generated the content).

Replace `<YYYY-MM-DD>` with the output of `date +%Y-%m-%d` (use the same date in both the commit message title and body). Pass each path determined in Step 2 item 3 as a separate argument prefixed with `:(literal)` for `<new source files...>` (e.g. `:(literal)raw/report[2024].pdf`; omit if there are none). For the same reason as Step 2 item 3 (Issue #115), passing a path containing metacharacters to `git add` without the prefix can accidentally stage an unrelated file. Pass each path determined in Step 2 item 4 for `<new schema files...>` the same way (omit if there are none) — these are always plain `.wikicommit/schema/<Type>.md` paths (Schema.org type names contain no glob metacharacters), but using `:(literal)` uniformly costs nothing and avoids re-deriving the rule if a custom type name ever did. Pass the path determined in Step 2 item 5 for `<new vocab file>` verbatim (omit if empty) — it is always the fixed literal path `.wikicommit/schemaorg-vocab.json`, so no `:(literal)` prefix is needed. Pass each path determined in Step 2 item 6 for `<policy files...>` verbatim as well, as its own argument (omit if none) — these too are fixed literal paths, `.wikicommit/source-policy.md` and `.wikicommit/entity-policy.md`.

**Drop any of the four `.wikicommit/` directories that does not exist on disk.** `git add` treats a pathspec matching nothing as fatal and aborts the *whole* invocation — nothing is staged, and the commit that follows has no content — so listing `.wikicommit/review/` (Issue #750) unconditionally would break every merge on a wiki that has one of them missing. That is not a hypothetical: `.wikicommit/review/` is created by `/wikicommit-init`, so a repository that updated its Skills (`npx skills add`) without re-running init does not have it, and neither does one initialized before `.wikicommit/view/` existed (Issue #675). Check each with a plain directory test and pass only the ones present; the ones you drop are, by definition, directories with nothing to stage.

### Step 6: Create PR

```bash
git push origin <branch name>
gh pr create \
  --title "wiki: bulk update $(date +%Y-%m-%d)" \
  --body "Automatically generated PR by WikiCommit. Quality checks passed." \
  --base "<default branch>"
```

Obtain `<PR number>` from the `gh pr create` output (the PR URL) or via `gh pr view --json number -q .number`, and record it for use in Step 7's cleanup procedure and the completion report.

### Step 7: Wait for Mergeable State, Then Merge

This skill does not use `gh pr merge --auto` (Issue #456). GitHub's auto-merge feature (the `enablePullRequestAutoMerge` mutation that `--auto` falls back to whenever the PR isn't immediately mergeable yet) is gated by the repository's `allow_auto_merge` setting, and that setting is unavailable — not misconfigured, unavailable — on GitHub Free private repositories; there is no CLI, API, or UI path to turn it on. Since Step 3 already ran every quality gate locally before this PR ever existed, there is nothing left for auto-merge's "wait for checks, then merge" behavior to add. All that's actually needed is to wait out the few seconds GitHub takes to finish computing the PR's mergeability, which is plan-independent and needs no special permission.

Poll:

```bash
gh pr view --json state,mergeStateStatus -q '.state + "|" + .mergeStateStatus'
```

- Polling interval: 10 seconds (check → wait 10s → check, repeated up to 30 times; the first check happens before any wait)
- Maximum wait: 300 seconds (30 iterations)
- If `state` is `CLOSED` (closed without merging) → stop polling immediately and treat it as a failure
- If `mergeStateStatus` is `CLEAN` → stop polling and proceed to the merge command below
- If `mergeStateStatus` is `DIRTY` or `BLOCKED` → stop polling immediately (do not wait out the remaining iterations) and treat it as a failure. These are the only two values that, for a PR this skill just created, need not resolve into `CLEAN` no matter how long the wait: `DIRTY` means GitHub cannot cleanly compute a merge commit at all (an actual conflict — waiting doesn't fix that), and `BLOCKED` means a persistent policy blocker (e.g. a required review) rather than an in-flight computation. Any other value (`UNKNOWN`, or anything else GitHub returns) is treated as still in flight and polling continues
- If `CLEAN` is not observed within 300 seconds, display an error and abort

On failure (`CLOSED`, `DIRTY`/`BLOCKED`, or timeout), guide the user through the following and abort (do not run Step 8 or Step 9 — since the merge did not go through, there is nothing new on the default branch for either post-review or generation-failure tracking Issues to target):

- Cleanup procedure for the leftover branch/PR:
  1. `gh pr close <PR number>`
  2. `git push origin --delete <branch name>`
  3. Re-run `/wikicommit-merge`

Once `mergeStateStatus` reaches `CLEAN`, merge directly without `--auto`:

```bash
gh pr merge --squash
```

`gh pr merge` without `--auto` merges immediately using the repository's ordinary (always-available) merge permission, rather than going through `allow_auto_merge`. If this command exits with an error despite `mergeStateStatus` having just reported `CLEAN` (e.g. a race with another merge landing on the base branch in between), display the error, guide the user through the same cleanup procedure above, and abort.

Once the merge is confirmed (`gh pr merge` exits 0), return to the default branch:

```bash
git checkout "<default branch>"
git pull origin "<default branch>"
```

### Step 8: Generate Post-Review Tracking Issues

Only run this step if Step 7 confirmed the merge completed (`gh pr merge` exited 0).

> **Why a tracking Issue instead of a post-review PR (Issue #313)**: GitHub does not let a PR author approve their own PR, and `wikicommit-merge` always opened post-review PRs under the wiki operator's own GitHub account — for a solo operator (one of WikiCommit's primary user profiles), the Approve button on those PRs was never actually selectable. Closing a GitHub Issue carries no such self-approval restriction (any repo write-access holder can close an Issue regardless of who opened it), and additionally lets someone who only reads the published wiki — with no Claude Code session at all — mark a page reviewed straight from GitHub. This replaces the `review-pr-auto-merge.yml` (Issue #281) design.

#### Extracting Target Pages

Scan the **entire `.wikicommit/entity/` and `.wikicommit/view/` trees on the default branch** (`<default branch>` from Step 0) — not just the `<changed .md files>` from Step 2. This batch's changes have already been merged into the default branch by Step 7, so scoping the scan to this batch alone would miss two cases: (a) a page whose tracking-Issue creation failed in a *previous* run (API error — see Issue Generation below) and is therefore still `pending` on the default branch without an open tracking Issue to show for it, and (b) any page that entered `review_status: pending` through a path other than the immediately preceding bulk-merge batch (e.g. a page touched by `wikicommit-fix`, or one that was merged in an earlier run before this scan existed). A full-tree scan makes every still-pending page visible on every run, regardless of which run originally introduced it.

Exclude `index.md` files (Type index pages, and a view tree's per-language index, auto-generated by `rebuild_index.py`; they are build-generated navigation, not LLM-authored content, and are stamped `review_status: reviewed` at write time for that reason — Issue #580) and pages whose frontmatter has `status: removed` (already leaving the wiki; not meaningful to route through post-review). Among the rest, target those whose frontmatter has `review_status: pending` (also treat a missing `review_status` as `pending`).

```bash
python -c "
import re, sys
from pathlib import Path
import yaml
FRONTMATTER_RE = re.compile(r'^---\r?\n(.*?)\r?\n---\r?\n?', re.DOTALL)
for path in sorted(Path('.wikicommit/entity').rglob('*.md')) + sorted(Path('.wikicommit/view').rglob('*.md')):
    if path.name == 'index.md':
        continue
    content = path.read_text(encoding='utf-8-sig')
    m = FRONTMATTER_RE.match(content)
    try:
        fm = (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError as e:
        print(f'WARNING: {path}: frontmatter YAML parse failed, skipping ({e})', file=sys.stderr)
        continue
    if not isinstance(fm, dict) or fm.get('status') == 'removed':
        continue
    if fm.get('review_status', 'pending') == 'pending':
        print(path)
"
```

Use the same line-anchored regex (`FRONTMATTER_RE`) as `parse_frontmatter` in `.wikicommit/scripts/check_wikilinks.py` to extract the frontmatter. Do not use a naive `content.split('---')[1]`, since it misdetects the frontmatter boundary — and causes a YAML parse error — when a value such as `title` or `description` happens to contain the literal string `---`.

The `try`/`except` around `yaml.safe_load` is required here specifically because this script now scans the entire wiki tree in a single process (unlike a per-file invocation, where a parse failure would only affect that one file): without it, one page anywhere in the tree with malformed frontmatter YAML would raise an uncaught exception and abort the scan before any target page is printed, silently blocking tracking-Issue generation for every page on every future run until that one file is fixed. Any `WARNING:` lines printed to stderr should be relayed to the user in the Step 10 completion report alongside the other skip reasons.

Pages with `review_status: reviewed` (Route B, via `wikicommit-review`) are excluded. The paths above come out already sorted (`sorted()` over `rglob`) — keep this order; it makes the processing order (and the Step 10 report) deterministic and reproducible across runs.

If there are zero target pages, display "No pages require post-review" and proceed to Step 9.

#### No Cap — Rate Limit Safety Margin Instead

Process **every** target page found above in this same run; there is no cap on the number of tracking Issues generated per run (Issue #195 revisits and removes the 10-PR-per-run cap the post-review step originally shipped with; that reasoning carries over unchanged now that this step opens Issues instead of PRs). The number of Issues a human eventually has to review is the same either way — a cap only staggers *when* they appear — and the cap was the root cause of a page-stranding bug (Issue #168). Reviewers can page through however many Issues this produces using GitHub's own Issue list filters and sort options at their own pace; the Skill does not need to pace Issue *creation* on their behalf.

The only real constraint on generating many Issues back-to-back is GitHub's secondary rate limit on rapid successive mutations. Guard against it with a short pause between pages rather than a page count cap: sleep 2 seconds after each page's `gh issue create` (step 1 of Issue Generation below) before starting the next page. This is a technical safety margin, not a review-pacing mechanism.

#### Checking for Existing Tracking Issues (per target page)

Obtain `<lang>` and `<slug>` from the target page's frontmatter `lang` field and its filename (without extension). `<Type>` is the value of the frontmatter `type` field with the `schema:` prefix stripped (e.g. `schema:Person` → `Person`, `schema:custom/Decision` → `custom/Decision`); always use this `<Type>` (including the `/`) in Issue titles. **A page under `.wikicommit/view/` has no `type:` field at all** (Issue #675), so for one of those `<Type>` is the reserved constant `View` — the same segment `[[View/<slug>]]` and the published `content/<lang>/View/` path use. Do not leave it empty; an Issue titled `Review: /<slug> (<lang>)` names nothing. While reading this frontmatter, also check for `translated_from` and `derived_from` — which one is present (if either) selects the Issue Body Template variant used below.

**Also determine `<Pass-2b type?>` for a `sources`-based page** (Issue #729), once the duplicate check below has confirmed this page still needs an Issue — a page that already has an open tracking Issue is skipped without a body being built, so reading a schema file for it is wasted on every future run. Read `.wikicommit/schema/<Type>.md` (`<Type>` as derived just above, i.e. with the `schema:` prefix already stripped) and check whether its `wikicommit.provenance` is `generate-interactive` or `generate-auto` — the two values `wikicommit-generate` Pass 2b stamps when it adds a type on the fly (Issue #519 / #507). If it is, the `sources` variant's checklist below gains one extra item; otherwise that item is omitted. Treat a missing or unreadable schema file, a missing `provenance`, or any other value (`default`, `init-theme`, `collect`, `schema-propose`, `manual`) as "no" — every one of those means a human either installed the type deliberately or approved it through a path that already had its own confirmation. Skip this read entirely for translation and synthesized pages: neither variant carries the item.

> **Why `provenance` rather than this batch's diff.** The design doc words the condition as "a type newly added in this batch", and Pass 2b's schema file does land in the same batch, so a `git show` against the squash-merge commit could answer it. But this step deliberately scans the whole default branch rather than the batch (Issue #313) precisely so that a page whose Issue creation failed in an earlier run is still picked up — and a batch-scoped condition would give that rescued page a *different* checklist from the one it would have received on its original run, purely as a function of when the API happened to fail. `provenance` is a permanent stamp on the schema file, so it answers the same question identically on every run, from a read this step can make about any page it finds.
>
> The cost is that the condition is broader than "this batch": every page of a Pass 2b-added type carries the item from then on, so for that type it is not really conditional any more. That is accepted — Pass 2b adding a type at all is the uncommon case (zero candidates is its normal outcome), and the alternative trades a bounded amount of repetition for a checklist that is not reproducible.

**`<page path>`** is the target page's own repo-relative path, exactly as the scan above printed it — `.wikicommit/entity/<lang>/<Type>/<slug>.md` for an entity page, `.wikicommit/view/<lang>/<slug>.md` for a view page. Use that value verbatim in the "Review Target" line and the marker below; do not rebuild it from `<lang>`/`<Type>`/`<slug>`, because a view page's path contains no Type segment and reconstructing one produces `.wikicommit/entity/<lang>//<slug>.md`, a path nothing on disk matches.

Each tracking Issue embeds an exact machine-readable marker in its body: `<!-- wikicommit-page: <page path> -->`. This is the marker `review-issue-close-sync.yml` resolves on close, and it accepts both tree layouts; a marker naming a path that does not exist makes that workflow exit quietly at its "page already removed" branch, leaving the page `pending` with nothing to show for the close. To check whether a page already has an open tracking Issue, fetch open `wikicommit-review`-labeled issues and scan their `body` for that exact marker locally:

```bash
gh issue list --label wikicommit-review --state open --json number,body --limit 1000
```

- If any returned issue's `body` contains the exact marker for this page **or** the same marker with `.wikicommit/entity/` replaced by the pre-Issue-#477 `.wikicommit/wiki/` (a tracking Issue opened before that rename still embeds its marker with the old prefix verbatim — GitHub Issues are external state untouched by the directory `git mv`; old and new forms are allowed to coexist rather than being auto-migrated) → skip this page and move to the next
- If neither form is present in any open issue → create a new tracking Issue

> **Match the marker against `body` locally; do not rely on `gh issue list --search`.** GitHub's issue search API tokenizes text for relevance ranking, with no guarantee it treats an HTML comment containing `/`, `.`, `-`, `:` as one exact-match unit — a false negative there would create a duplicate tracking Issue. Scanning `body` directly for the literal marker string is deterministic. `--limit 1000` avoids `gh issue list`'s default 30-item cap; unlike the old `--head`-scoped PR lookup (which returned at most 1 result per query), there is no per-page-scoped equivalent for Issues, so this list must be fetched once per run and reused across all target pages rather than re-fetched per page.

#### Issue Generation (repeat per target page)

```bash
# 1. Create the tracking Issue
gh issue create \
  --title "$(cat <<'EOF'
Review: <Type>/<slug> (<lang>)
EOF
)" \
  --label wikicommit-review \
  --body "$(the Issue body template below — selected per the translated_from/derived_from check above — with the relevant fields and the marker filled in)"

# 2. Brief pause before the next page's issue create, to stay clear of GitHub's secondary rate limit
sleep 2
```

Pass `--title` through a quote-delimited heredoc, not a plain `--title "Review: <Type>/<slug> (<lang>)"` double-quote embedding. `<Type>` and `<slug>` are not upstream-validated constrained identifiers, so they do not qualify for the exemption this rule grants to values a script or command has already validated deterministically: `validate_frontmatter.py` only checks that `type` starts with the `schema:` prefix (no constraint on the characters after it), and `<slug>` is simply the page's filename with no character-class enforcement anywhere in the pipeline. A page whose `type`/filename contains shell metacharacters (via a hand-edited page, Route B, or a future ingest bug) would otherwise be interpolated verbatim into this `gh issue create` command (Issue #398).

Skip step 2 after the last target page (no next iteration to protect).

If `gh issue create` fails because the `wikicommit-review` label does not exist yet in this repository (`could not add label: 'wikicommit-review' not found` or similar), create it once — `gh label create wikicommit-review --description "WikiCommit page review tracking (Issue #313)" --color <any color>` — then retry the same `gh issue create`. This only happens the first time this step ever runs in a given repository; the label persists afterward.

Obtain `<Issue number>` from the `gh issue create` output (the Issue URL) or via `gh issue view --json number -q .number`, and record it for use in the Step 10 completion report.

If `gh issue create` fails for any other reason (API error, etc., after the label-retry above), skip this page, record the error to the console, and move to the next page (do not abort all of Step 8 due to a single page's failure).

If `generated_at`/`generated_by` (`sources`-based and synthesized pages) or `translated_at`/`translated_by` (translation pages, see below) is missing from the target page's frontmatter, write "unknown" in the Issue body for that field.

#### Issue Body Template

##### Language of the Issue body

**Render the chosen template in the wiki's `primary_lang`** — `translation.primary_lang` from `.wikicommit/config.yml`, the same value `/wikicommit-init` set. When it is `en`, or when the file is missing, unreadable, or has no `primary_lang`, emit the English template verbatim as before.

The English templates below stay canonical: translate at write time rather than keeping one template per language. Three variants times two languages would double this Skill's instruction area, and a SKILL.md is loaded in full on every invocation.

**Why this Issue is translated when the console output of the distributed scripts and this repository's `CHANGELOG.md` are fixed English** (Issue #773, against Issue #770 / #772): the rule is the same one in all three cases — the language follows the reader. Those two are read by an operator and by an agent, so they are diagnostics and stay in one language. This Issue is read by whoever closes it, which by design (Issue #313) includes someone who only reads the published wiki and has no Claude Code session at all. Every other reader-facing surface already switches (the banner, the sources box, the build-generated pages); the tracking Issue was the one that did not.

**`.github/ISSUE_TEMPLATE/report.md` is not the same case and stays English.** It says why in its own words: there is one of it per repository, so it has no language of its own. A tracking Issue is one per page, and that page has a `lang`, so the same reasoning lands the other way.

**`primary_lang`, not the page's own `lang`.** A tracking Issue follows one page, which makes the page's language the intuitive choice, but the person who reads it is whoever holds write access to close it — a property of the repository, not of the page. On a wiki with `targets`, using the page's `lang` would send that one operator Issues in two languages.

Leave these untranslated wherever they appear:

- The marker line `<!-- wikicommit-page: <page path> -->`. `review-issue-close-sync.yml` matches it exactly, and it is the only part of the body any machine reads.
- The Issue title (`Review: <Type>/<slug> (<lang>)`). It is an identifier, and listing and searching depend on its shape.
- Anything anyone is expected to type or look at: command names (`/wikicommit-fix`, `/wikicommit-generate <url>`, `/wikicommit-merge`, `/wikicommit-status`), file paths, frontmatter keys and values (`sources:`, `properties:`, `review_status`, `status: retracted`), and the `wikicommit-review` label.
- The field values themselves — the page path, the dates, and the model IDs — and the literal `unknown` this step writes in place of a missing one (it stands in a field-value slot, and Step 9's Issues use the same literal).

The section headings and the prose are translated, since they are what the reader is there to read. **This includes the shared "How to Proceed" section**: "insert this verbatim" below means the three variants all get the same text, not that this one section stays English. Leaving it untranslated would hand the reader this change is for — someone closing the Issue with no Claude Code session — the write-access requirement, the warning that a comment asking for a change does not make the change, and the two comment exceptions in a language they may not read, inside a body that is otherwise in their own.

Three variants exist, selected by which provenance field the target page's frontmatter has:

- **`sources`-based pages** (no `translated_from`, no `derived_from`) — a normal `wikicommit-generate` output.
- **Translation pages** (`translated_from` present) — a `wikicommit-translate` output (Issue #280). Carries `translated_from`/`translated_at`/`translated_by` instead of `generated_at`/`generated_by`, and its `sources` is inherited from the original page rather than set directly — so "does the content match the source document?" does not translate meaningfully to it, and its checklist below is a distinct set of translation-quality questions rather than a reworded copy of the `sources`-based checklist.
- **Synthesized pages** (`derived_from` present) — a `wikicommit-synthesize` output (Issue #283). Carries `derived_from` (an array of `{path, source_commit}`) instead of `sources`, but — unlike a translation page — does carry `generated_at`/`generated_by` the same as a `sources`-based page; only its "Review Target"/"Once You Have Read It" content differs, not the at/by fields.

These three provenance fields are mutually exclusive per page, so exactly one variant applies to any given target page. All three share the same "How to Proceed" text below — it only describes `review-issue-close-sync.yml`'s reaction to the Issue closing, which is identical regardless of page provenance — and the same `wikicommit-review` label / `<!-- wikicommit-page: ... -->` marker format, so no change to that workflow is required for any of the three.

**What these checklists ask for changed (Issue #723).** They used to hold the same three questions
`wikicommit-review` Step 4 asks, and two of those three — does it match the source, are there
hallucinations — are exactly what Pass 4 already checks, twice over and with far more machinery
behind it (evidence binding, per-fact verification, secondary citations, source-vs-source
disagreement, one-hop cross-page contradiction). A human closing the Issue was walking a third lap
of a check the machine is better at, and the top rung of the trust ladder was being signed on that
basis. The `saitama` pilot bears this out: four review agents comparing pages to their originals
found zero hallucinations, fabrications, misattributions, secondary citations or wrong dates — what
they did find was three cross-page contradictions. The source-fidelity layer works; the defects left
are a different kind. Asking the same three questions on every page, and having them pass every
time, is also what stops a checklist from being read at all (Issue #562's reason for demoting the
low-density guard).

The split is not arbitrary. **Pass 4's evidence-binding rule (Issue #442) defines it**: that rule
forbids the machine from judging on anything but the literal source text, so outside knowledge is,
by construction, the one kind of evidence only a human can bring. A reviewer who happens to know an
ordinance changed in April holds evidence no automated layer can reach. The second human-only item
is harm: `.wikicommit/entity-policy.md` (Issue #667) decides whether a page about an entity gets
written, but nothing anywhere checks whether a sentence inside a page that legitimately exists
treats a real person or organization unfairly — Pass 4 has no harm check of any kind.

Two rules govern how the new items are worded. **The knowledge item says "tell us if you know", never
"go and find out"** — turning it into research would reintroduce, on the human side, exactly what
Issue #722 rules out on the machine side, and would make each review cost an open-ended search;
reporting what you already know costs nothing. And **the knowledge item goes in the `sources`
variant only**: on a translation, a stale fact belongs to the original page, and on a synthesized
page it belongs to whichever grounding page states it — the same redirect `wikicommit-fix` makes
(Issue #529), and the reason the three variants exist at all (Issue #525). **Harm goes in all
three**, because a harmful sentence is harmful whatever produced it.

**Issue #740 then changed the shape, not just the contents.** `review_status` is a two-valued
field, which makes it structurally a container for an *event* — it happened, or it has not. What it
held was a *claim* about the page, and a claim has content, which is why the content had to be
bolted on as a checklist in the first place; once that checklist took the form of an attestation,
closing became a signature. So the checkboxes are gone. What the Issue asks for now is the product
this field can actually carry: **one line on what the reader took away**, which records that this
wiki's knowledge reached at least one person who is not the machine that wrote it. Anything they
noticed goes in the same comment, as prompts rather than as boxes to tick.

That also removes the four-item ceiling this section used to impose: the ceiling existed because
every item was a claim a closer had to underwrite, and a list of prompts costs nothing to skip. Keep
the list short anyway — one of these Issues is generated per page.

**"This is not a test" has to be written down.** Without it, a reader takes the request for a line
as something they will be marked on, and the weight this change removes comes back in another form.
The line is not asked for as verification — verification is impossible, an LLM can write it — but
because the product being recorded is an event, and the line is that event's trace. It differs from
a quiz on every axis that matters: there is no correct answer, so it cannot be marked, so there is
nothing to fake, and nobody who read the page is unable to write one.

**Do not write "this is not a review" anywhere.** All three products come from one reading, and the
word covers the whole of it; what differs is which product each is recorded as (Issue #583's line,
applied here: change the reader-facing strings and the definitions, leave `review_status`,
`reviewed_by`, the `wikicommit-review` label, the workflow filenames, the Skill names and the commit
trailers alone).

**Say the machine's half out loud.** Since Issue #751 the banner states that the page was checked
against its sources, so the prompts here can be introduced as what that check does *not* cover
without the reader inferring that nothing was checked at all.

**The source itself is a separate thing to ask about (Issue #743).** Nothing in the template used
to question whether a source is any good; every item measured the page *against* its sources, which
means a page faithfully repeating a source's error passes all of them. That gap is structural rather
than an oversight: Pass 4's evidence-binding rule (Issue #442) makes the sources the standard, and
under that discipline the machine cannot doubt them — so this is the same class of thing as harm and
outside knowledge, something only a person can say. Issue #737 built the receiving end
(`status: retracted` plus a `## Retraction Reason`, both written by hand), so there is now somewhere
for the answer to go; before that, saying it would have led nowhere.

It goes in the **`sources` variant only**, and the two redirect sentences carry it on the other two.
A translation has no `sources` of its own — it inherits the original's — and a synthesized page has
`derived_from` instead, so on both the documents in question belong to a different page, exactly the
split Issue #525 created the three variants for and Issue #529 made `wikicommit-fix` follow. Putting
the prompt on all three would invite a reviewer to retract a source on the strength of a page one or
two removes from it.

Because the answer needs a human edit rather than a command, it travels as a comment — which makes
it the second exception to "a comment does not carry through", alongside Issue #736's URL. Both
exceptions exist for the same reason and are stated together: `/wikicommit-fix` edits a page's text
and cannot touch its sources at all.

**Keep this text different from the report link's (Issue #738).** Both point at the same
machine-blind areas, but the audiences differ: the report link addresses any reader, asking only
that they say something if they noticed it, while this Issue addresses whoever can close it — the
side that speaks for what this wiki claims. Copying one into the other makes each look like a worse
copy of the other and gets both skimmed. The distinct part here is the ask for a line, which the
report link does not make at all; one sentence naming the difference keeps it legible.

##### Shared "How to Proceed" section (all variants)

Insert this verbatim into every Issue body, between "## Once You Have Read It" and the marker line — "verbatim" meaning identical across all three variants, not exempt from "Language of the Issue body" above; render it in `primary_lang` along with the variant it is inserted into:

```markdown
## How to Proceed

Closing this Issue takes write access to this repository (or triage access, if it is owned by an organization) — GitHub only lets you close an Issue you did not open yourself if you have one of those, and hides the button otherwise. If you are reading this without that access, open a new Issue of your own describing what is wrong instead: that needs no special access, and `/wikicommit-fix` reads it. On a published wiki, the report link in the banner at the top of the page does this for you with the page already filled in (that link is worded in the page's own language, so its exact label differs from page to page).
Read the page (locally, or on the published wiki once it's live) and, if everything looks good, simply close this Issue — that alone is enough. A GitHub Actions workflow (`.github/workflows/review-issue-close-sync.yml`) detects the close, flips this page's `review_status` from `pending` to `reviewed`, and auto-merges that change once quality checks pass. There is no PR to Approve here — closing this Issue is the entire action, and it works the same whether you use Claude Code or just the GitHub web/mobile UI.
If changes are needed, write what you found in a comment and leave this Issue open. **You do not have to make the fix yourself** — `/wikicommit-fix <this Issue's URL>` reads this body and its comments. It is closed once the fix has landed.
**A comment saying what you took away, or what you noticed, is exactly what this Issue is for** — that needs nothing further from you, and nothing else has to happen to it.
**A comment asking for a change does not make the change**: the workflow that runs on close only reads the marker line at the bottom of this Issue's body and flips `review_status` from `pending` to `reviewed` — it never reads comments. Closing after only asking for a fix merges the page with that fix unmade. To have it applied, run `/wikicommit-fix <this Issue's URL>` explicitly (it reads both this Issue's body and its comments and proposes a fix), and close this Issue only after that fix has landed.
**Two kinds of comment are the exception, because both are about a page's sources rather than its text, and `/wikicommit-fix` cannot touch sources at all.**
**A URL naming a document a page should have been written from** needs `/wikicommit-generate <url>` followed by `/wikicommit-merge` — that folds what the document says into the page written from it, which comes back for review once it lands (if this Issue tracks a translated or a synthesized page, that is the page this one derives from, not this one). If you cannot run those, leaving the URL in a comment hands it to someone who can — but leave this Issue open until they have, because closing it still merges this page as reviewed.
**Saying that one of the sources itself is wrong** is the other. Nothing automated can reach that judgment — every check this wiki runs treats the sources as the standard the page is measured against, so a page faithfully repeating a source's error passes all of them. Name the source and say what is wrong with it in a comment; someone with write access marks it `status: retracted` with the reason in its management file, and `/wikicommit-status` then lists every page still standing on it. Name only a document this page itself was written from — if this Issue tracks a translated or a synthesized page, it has no sources of its own and the documents belong to the page it derives from, so raise it there rather than here. Leave this Issue open until that has happened, for the same reason as above.
```

##### `sources`-based pages (no `translated_from`, no `derived_from`)

```markdown
## Review Target

- Page: `<page path>`
- Generated at: <generated_at> (write "unknown" if not set)
- Generated by: <generated_by> (write "unknown" if not set)

## Once You Have Read It

When you have read this page, put **one line on what you took away from it** in a comment and close
this Issue (the box you type into when you close is the same one). It does not have to be a summary
— "that surprised me" or "nothing here was new to me" is enough.

**This is not a test of your understanding.** It is the record that this page's knowledge actually
reached a person. Closing this Issue states two things — that this page's knowledge reached a
person, and that **nothing struck you as obviously wrong while reading**. It is not a guarantee
that the content is correct.

This page was already checked against the documents it was written from, by machine, when it was
generated — where the published page shows it, the banner at the top names the model and the date. Nothing below was
checked by any automation, so if you noticed any of it while reading, put that in the same comment.
**You are not being asked to go looking.**

- Anything about a real person or organization that reads as overstated, or as settled when it is
  disputed, or as a private detail this page has no reason to hold. Whether this page should exist
  at all was judged against `.wikicommit/entity-policy.md` when it was generated; the sentences
  inside it were not.
- Anything that conflicts with what you already know, or an important fact about this subject that
  none of its sources carry. **If you have a URL for it, put the URL in the comment** — that one is
  carried onward even though nothing else in a comment is (see "How to Proceed"). `/wikicommit-generate <url>`
  folds what it says into this page, and the page comes back here to be read again; run it yourself
  if you have write access, or leave the URL for someone who does.
- Anything another page on this wiki says differently. The machine can only compare a page against
  ones written before it in the same batch, so a contradiction across batches is visible to nobody
  but a person reading several pages over time.
- **Anything wrong with a source this page was written from**, rather than with the page. This is a
  separate thing to say, and saying the page looks fine does not cover it: every automated check
  measures the page *against* its sources, so a page that faithfully repeats a source's error passes
  all of them. If you know one of the documents this page lists under `sources:` to be unreliable,
  say which and why — a comment carries this one onward (see "How to Proceed").
- Is `<Type>` the right type for this subject, and do the `properties:` keys listed in `.wikicommit/schema/<Type>.md` fit it? This type was added automatically while this page was being written, and no automated check judges whether it *fits* — only that it exists in the Schema.org vocabulary.

**If something did stick out, a comment is all that is asked of you — and in that case do not close
this Issue.** The fix is not yours to make; whoever has access closes this once it has landed.

On a published wiki, the report link on the page collects the same kinds of thing from any reader
who happens to notice one. This Issue is the step above it: closing it is how this wiki records that someone
read the page, which is why it takes write access.

<the shared "How to Proceed" section above, inserted verbatim>

<!-- wikicommit-page: <page path> -->
```

**The last bullet is conditional: emit it only when `<Pass-2b type?>` (determined above) is yes, and drop the whole line otherwise**, leaving the bullets that always apply. Do not emit it commented out or with the condition written into it — what a reader sees must contain only what they are actually being asked, and an HTML comment placed inside the body would travel into the Issue verbatim the way the `wikicommit-page` marker does. It appears only on pages whose type was added on the fly, which is the uncommon case, and it is the only place the tracking Issue surfaces a type decision that may have been taken with no human confirmation at all (Issue #729 / #507).

##### Translation pages (`translated_from` present)

```markdown
## Review Target

- Page: `<page path>`
- Translated from: `<translated_from>` (the original-language page; this Issue tracks only the translation's own `review_status`, not the original's — the original may already be `reviewed`, or may never have been through this review flow at all, so it will not always have a tracking Issue of its own)
- Translated at: <translated_at> (write "unknown" if not set)
- Translated by: <translated_by> (write "unknown" if not set)

## Once You Have Read It

When you have read this page, put **one line on what you took away from it** in a comment and close
this Issue (the box you type into when you close is the same one). It does not have to be a summary
— "that surprised me" or "nothing here was new to me" is enough.

**This is not a test of your understanding.** It is the record that this page's knowledge actually
reached a person. Closing this Issue states two things — that this page's knowledge reached a
person, and that **nothing struck you as obviously wrong while reading**. It is not a guarantee
that the content is correct.

This page was already checked against the original it was translated from, by a machine translation-quality
pass, when it was generated. Nothing
below was checked by any automation, so if you noticed any of it while reading, put that in the same
comment. **You are not being asked to go looking.**

- Anywhere the translation does not carry the original's meaning, reads awkwardly or too literally,
  or uses a term differently from the `DefinedTerm/` glossary.
- Anything about a real person or organization that reads as overstated, or as settled when it is
  disputed, or as a private detail this page has no reason to hold. Whether this page should exist
  at all was judged against `.wikicommit/entity-policy.md` when it was generated; the sentences
  inside it were not.

If a fact here is out of date or wrong on the substance rather than the wording, the page to fix is the original this was translated from, not this one — a fix written here is overwritten the next time the original changes and the translation is regenerated. The same goes for a source: this page has none of its own, and anything wrong with the documents behind it belongs to the original's own sources.

**If something did stick out, a comment is all that is asked of you — and in that case do not close
this Issue.** The fix is not yours to make; whoever has access closes this once it has landed.

On a published wiki, the report link on the page collects the same kinds of thing from any reader
who happens to notice one. This Issue is the step above it: closing it is how this wiki records that someone
read the page, which is why it takes write access.

<the shared "How to Proceed" section above, inserted verbatim>

<!-- wikicommit-page: <page path> -->
```

##### Synthesized pages (`derived_from` present)

```markdown
## Review Target

- Page: `<page path>`
- Derived from: `<derived_from[0].path>`, `<derived_from[1].path>`, ... (one entry per `derived_from` array element)
- Generated at: <generated_at> (write "unknown" if not set)
- Generated by: <generated_by> (write "unknown" if not set)

## Once You Have Read It

When you have read this page, put **one line on what you took away from it** in a comment and close
this Issue (the box you type into when you close is the same one). It does not have to be a summary
— "that surprised me" or "nothing here was new to me" is enough.

**This is not a test of your understanding.** It is the record that this page's knowledge actually
reached a person. Closing this Issue states two things — that this page's knowledge reached a
person, and that **nothing struck you as obviously wrong while reading**. It is not a guarantee
that the content is correct.

Every claim on this page was already checked, by machine, against the pages listed under "Derived
from". Nothing below was checked by any automation, so if you noticed any of it while reading, put
that in the same comment. **You are not being asked to go looking.**

- Anything about a real person or organization that reads as overstated, or as settled when it is
  disputed, or as a private detail this page has no reason to hold. Whether this page should exist
  at all was judged against `.wikicommit/entity-policy.md` when it was generated; the sentences
  inside it were not.

This is the page where that one earns the most. Every automated check here compares a single claim against the pages under "Derived from"; an implication that arises only from putting several of their statements side by side is visible to no check at all — and putting statements side by side is exactly what this page does.

If a fact here is wrong rather than badly combined, the page to fix is the one under "Derived from" that states it, not this one. The same goes for a source: this page has none of its own, and anything wrong with the documents behind it belongs to whichever page under "Derived from" was written from them.

**If something did stick out, a comment is all that is asked of you — and in that case do not close
this Issue.** The fix is not yours to make; whoever has access closes this once it has landed.

On a published wiki, the report link on the page collects the same kinds of thing from any reader
who happens to notice one. This Issue is the step above it: closing it is how this wiki records that someone
read the page, which is why it takes write access.

<the shared "How to Proceed" section above, inserted verbatim>

<!-- wikicommit-page: <page path> -->
```

The marker line is an HTML comment: GitHub does not render it in the Issue view, so it stays invisible to the human reviewer while still being retrievable via `gh issue view --json body` for the "Checking for Existing Tracking Issues" step above and for `review-issue-close-sync.yml`.

GitHub has no native way to require a comment before an Issue is closed ("Require conversation resolution" applies to PRs, not Issues). The ask for a line, and the prompts under it, are guidance for the human reviewer, not an enforced gate — which is why the wording has to earn the line rather than demand it.

### Step 9: Generate Generation-Failure Tracking Issues

Only run this step if Step 7 confirmed the merge completed (`gh pr merge` exited 0).

> **Why this step exists (Issue #452)**: when a `wikicommit-generate` entity fails source-integrity review (Pass 4) after exhausting `generate.max_retries`, it is recorded only inside the source management file's `failed_pages` list and `## Failure Reason` section — invisible from the page itself (for `action: update`, the pre-existing page is simply left unchanged, with no sign anything was attempted) and invisible from any later session unless someone happens to re-open that exact management file. This mirrors Step 8's tracking-Issue mechanism (Issue #313) but for a different failure class: Step 8 surfaces successfully-generated pages awaiting human review; this step surfaces generation attempts that did *not* produce a page at all. It intentionally does not trigger any automation on close (unlike Step 8's `review_status` flip via `review-issue-close-sync.yml`) — closing this Issue is purely a human record-keeping action, since there is no single well-defined "fixed" state analogous to `review_status: reviewed` for a page that was never written. To actually retry, re-run `/wikicommit-generate` on the source.

#### Extracting Target Management Files

Scan the **entire `.wikicommit/source/` tree on the default branch** (`<default branch>` from Step 0) — not just this batch's changes — for the same reason as Step 8's full-tree scan: a management file whose tracking-Issue creation failed in a *previous* run, or one that picked up `failed_pages` through a batch other than the immediately preceding one, must still be caught on every run regardless of which run originally introduced it.

```bash
python -c "
import re, sys
from pathlib import Path
import yaml
FRONTMATTER_RE = re.compile(r'^---\r?\n(.*?)\r?\n---\r?\n?', re.DOTALL)
for path in sorted(Path('.wikicommit/source').rglob('*.md')):
    content = path.read_text(encoding='utf-8-sig')
    m = FRONTMATTER_RE.match(content)
    try:
        fm = (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError as e:
        print(f'WARNING: {path}: frontmatter YAML parse failed, skipping ({e})', file=sys.stderr)
        continue
    if not isinstance(fm, dict):
        continue
    failed = fm.get('failed_pages') or []
    if isinstance(failed, list) and failed:
        print(path)
"
```

Same `FRONTMATTER_RE` and `try`/`except` resilience as Step 8's extraction script, for the same reason: one management file anywhere in the tree with malformed frontmatter must not abort the scan before every other target file is found. Relay any `WARNING:` lines to the user in the Step 10 completion report, same as Step 8.

If there are zero target management files, display "No generation failures require tracking" and proceed to Step 10.

Process every target management file found in this same run — same no-cap, sleep-2-seconds-between-creates rate-limit approach as Step 8's "No Cap — Rate Limit Safety Margin Instead" section, for the same reasons.

#### Checking for Existing Tracking Issues (per target management file)

Each tracking Issue embeds an exact machine-readable marker in its body: `<!-- wikicommit-ingest: <source management file path> -->`. Fetch open `wikicommit-generation-failure`-labeled issues and scan their `body` for that exact marker locally (same rationale as Step 8 — do not rely on `gh issue list --search`):

```bash
gh issue list --label wikicommit-generation-failure --state open --json number,body --limit 1000
```

- If any returned issue's `body` contains the exact marker for this management file → skip it and move to the next
- If none do → create a new tracking Issue

#### Issue Generation (repeat per target management file)

Read the management file's `source.type`, `source.path`/`source.url`, `failed_pages`, and `last_generated_at` fields, and its `## Failure Reason` section body (write "unknown" in the Issue body for `last_generated_at` if unset, and "unknown" for the failure reason if the section is absent — same "unknown" fallback Step 8 uses for missing `generated_at`/`generated_by`).

```bash
# 1. Create the tracking Issue
gh issue create \
  --title "$(cat <<'EOF'
Generation failure: <source management file path>
EOF
)" \
  --label wikicommit-generation-failure \
  --body "$(the Issue body template below, with source, failed_pages, last_generated_at, and the failure reason filled in)"

# 2. Brief pause before the next management file's issue create, to stay clear of GitHub's secondary rate limit
sleep 2
```

Pass `--title` through the same quote-delimited heredoc pattern as Step 8, for the same reason — the source management file path is deterministic but not itself upstream-validated against a constrained character set (Issue #398's exemption criterion), so it is not exempt from this rule.

Skip step 2 after the last target management file (no next iteration to protect).

If `gh issue create` fails because the `wikicommit-generation-failure` label does not exist yet in this repository, create it once — `gh label create wikicommit-generation-failure --description "WikiCommit generate-pass failure tracking (Issue #452)" --color <any color>` — then retry the same `gh issue create`. This only happens the first time this step ever runs in a given repository; the label persists afterward.

Obtain `<Issue number>` from the `gh issue create` output (the Issue URL) or via `gh issue view --json number -q .number`, and record it for use in the Step 10 completion report.

If `gh issue create` fails for any other reason (API error, etc., after the label-retry above), skip this management file, record the error to the console, and move to the next one (do not abort all of Step 9 due to a single file's failure).

#### Issue Body Template

```markdown
## Generation Failure

- Source: `<source.type>` — `<source.path or source.url>`
- Ingest management file: `<source management file path>`
- Last attempted: <last_generated_at> (write "unknown" if not set)
- Failed pages (intended `create`/`update` targets that were not written; any existing page among these was left unchanged):
  - `<failed_pages[0]>`
  - `<failed_pages[1]>`
  - ...

## Failure Reason

<## Failure Reason section body from the source management file, or "unknown" if that section is absent>

## How to Proceed

This Issue is a visibility record, not an automation trigger — closing it does not change anything on its own (unlike a `wikicommit-review` tracking Issue, whose close is detected by `review-issue-close-sync.yml`). Investigate the failure reason above, then either fix the underlying issue (adjust the source content, or add guidance to the management file's `## User Notes`) and re-run `/wikicommit-generate` on this source to retry, or close this Issue with a note if the gap is acceptable as-is.

<!-- wikicommit-ingest: <source management file path> -->
```

The marker line is an HTML comment, same as Step 8's — invisible in the Issue view, retrievable via `gh issue view --json body`.

### Step 10: Completion Report

Close the run record first, so its elapsed time covers the whole run:

```bash
python .wikicommit/scripts/record_run.py end <the path Step 0 printed> \
    --outcome pr=<PR number> --outcome tracking_issues=<N> --outcome failure_issues=<N>
```

`--outcome` takes integers, so `pr=<number>` records which PR this run produced. This Skill's counts are deliberately not the same keys as the generating Skills' (Issue #790): it does not write pages, and a shared vocabulary would mean shipping keys that are permanently zero on one side or the other.

Report its path and elapsed time along with the following:

- The bulk update PR number and branch name created in Step 6
- The list of `<new source files>` included in the bulk update PR from Step 2 item 3 (omit if none)
- The list of tracking Issues newly created in Step 8 (page path, Issue number)
- Any pages skipped in Step 8, with reasons (frontmatter YAML parse failed during the extraction scan / an open tracking Issue already exists / issue creation error)
- The list of generation-failure tracking Issues newly created in Step 9 (source management file path, Issue number)
- Any management files skipped in Step 9, with reasons (frontmatter YAML parse failed during the extraction scan / an open tracking Issue already exists / issue creation error)

## Notes

- In Phase 2, lychee's timeout can take up to 10 seconds × `max_retries` (2) = potentially over 20 seconds per link. This wait time is separate from Step 7's 300-second polling limit and affects Step 3's execution time
- Never commit directly to the default branch. Commits always happen on a `wikicommit/merge-*` branch (Step 8 no longer creates a `wikicommit/review-*` branch itself — that branch is created by `review-issue-close-sync.yml` when the tracking Issue is closed, per Issue #313)
- Do not write to `.wikicommit/schema/` — this skill only ever *commits* new schema files `wikicommit-generate` Pass 2b already wrote to disk (Step 2 item 4, Step 5), it never creates or edits their content itself
- Do not use `--force-push`
- Never delete a branch, PR, or Issue without the user's confirmation (present the cleanup procedure to the user and confirm before running it)
