---
name: wikicommit-init
description: Initialize WikiCommit directory structure, schema, and configuration in a repository
disable-model-invocation: true
---

# wikicommit-init

Generates WikiCommit's `.wikicommit/` directory structure, schema, and configuration files in the repository.

## Prerequisites

Confirm the following with the user (use the default value if there is no answer):

1. **Primary language** (primary_lang): `en` (default). This is the source language of the wiki the user is creating (not the language of the WikiCommit tool itself). Users who want a Japanese-language wiki (e.g. the `world-kids-play-wiki` pilot) should explicitly answer `ja`.
2. **Wiki theme** (theme): free text, empty (default, skip with a blank Enter). Used by `wikicommit-generate`'s exclude judgment to automatically skip entities unrelated to the wiki's topic; leaving it empty disables that judgment (all entities are generated as before). Example prompt:

   ```
   What is this wiki's theme? (free text, optional — leave blank to skip)
   e.g. "Knowledge base for an internal engineering org. Personal-blog-style topics are out of scope."
   ```

   Just hold the answer for now — if non-blank, it also drives an obvious-type judgment that runs later,
   in Processing Flow step 3, once `init.py` has actually created `.wikicommit/` (see that step for why
   it can't run here yet: this repository's root path isn't confirmed until prerequisite 3 below, and
   `.wikicommit/schema/` doesn't exist until `init.py` runs in step 2).

3. **Repository root path**: current directory (default)
4. **Publish with Quartz v5**: confirm in two stages (Issue #335 — local build/preview and automatic
   GitHub Pages publishing are independent choices; a user who only wants to preview the wiki locally
   should not be forced into enabling GitHub Pages).

   a. Local build/preview:

      ```
      Set up Quartz v5? Quartz v5 is the static site generator that builds your wiki into a
      browsable website. Answering Y lets you preview the wiki locally anytime with
      `/wikicommit-serve` — you don't have to wait for a deploy to see how it looks.
      [Y/n]
      ```

      If Y (default), pass `--quartz` to `init.py`. If N, do not pass it (only `.wikicommit/` is
      generated) and skip sub-step b below — do not ask it.

   b. Automatic GitHub Pages publishing (only ask if a. was answered Y):

      ```
      Also set up automatic publishing to GitHub Pages? This adds .github/workflows/deploy.yml, so
      every merge to main automatically rebuilds and republishes the wiki, and enables GitHub Pages
      (Source: GitHub Actions) on this repository.
      ⚠️ For private repositories, this requires GitHub Pro/Team/Enterprise. On the free plan,
         deploy.yml will fail with a 404 on private repositories.
      [Y/n]
      ```

      If Y (default), pass `--quartz-pages` in addition to `--quartz`. If N, pass `--quartz` alone
      (local build/preview only — no GitHub Pages, no `deploy.yml`; this can be added later by
      re-running `wikicommit-init` and answering Y here).
      If the target repository is known to be private, recommend N given the caveat above.

## Processing Flow

1. Check whether `.wikicommit/` already exists:
   - Does not exist → run `init.py` without `--no-overwrite`
   - Exists → add `--no-overwrite` and run. Notify the user that existing configuration will be preserved

2. Run the following command with the confirmed values:

   **New repository:**

   ```bash
   python .claude/skills/wikicommit-init/scripts/init.py \
     --primary-lang <primary_lang> \
     [--quartz] \
     [--quartz-pages]
   ```

   **Adding to an existing repository (when `.wikicommit/` already exists):**

   ```bash
   python .claude/skills/wikicommit-init/scripts/init.py \
     --primary-lang <primary_lang> \
     --no-overwrite \
     [--quartz] \
     [--quartz-pages]
   ```

   If the user answered the theme prompt with non-blank text, add `--theme` to the **New repository**
   form above; do not add it to the **Adding to an existing repository** form — `--theme` has no effect
   there (Issue #374): an already-existing `config.yml` is always skipped wholesale under
   `--no-overwrite`, silently discarding whatever the user just answered at the theme prompt. Use
   `--update-theme` afterward instead — a dedicated flag that rewrites only the `theme:` line of the
   existing `config.yml`, leaving the rest of the file untouched. Skip it if the user left the theme
   prompt blank — a blank answer means "leave it as is," not "clear it," and `--update-theme` always
   overwrites unconditionally once invoked (that is the point of it being a separate, explicitly-named
   flag rather than folded into `--theme` itself: it signals an intentional overwrite of whatever theme
   value — set or still empty — was there before).

   In both cases, embed the theme text with a quoted-delimiter heredoc via command substitution, never
   as a bare double-quoted string (Issue #375 — the theme prompt answer is free-form text the user
   typed, and if it contains shell metacharacters such as `` ` ``, `$(...)`, or `"`, a plain
   `--theme="<theme text>"` embedding could let those characters be interpreted by the shell instead of
   passed through literally; see `docs/DesignDoc-skills.md` §11.7 for the general rule this follows,
   already used for `gh pr create --body` elsewhere in these Skills). This form also sidesteps the
   argparse leading-dash misparse that an older revision of this file worked around with the
   `--theme="<text>"` `=`-joined convention — a heredoc-produced value is always a single `--theme=...`
   shell word regardless of what the text starts with:

   ```bash
   --theme="$(cat <<'EOF'
   <theme text>
   EOF
   )"
   ```

   ```bash
   python .claude/skills/wikicommit-init/scripts/init.py --update-theme="$(cat <<'EOF'
   <theme text>
   EOF
   )" [--repo-root <path>]
   ```

   Do not pass `--targets` — it is no longer collected in the Prerequisites step, so `config.yml` is always
   generated with `targets: []`. The translation pipeline itself is Phase 4 scope and not yet implemented
   (`docs/DesignDoc-pipeline.md` §6.4); once it lands, users configure `targets` by hand-editing `config.yml`.
   Only pass `--quartz` if the user answered Y to the Quartz local build/preview confirmation (4a).
   Only pass `--quartz-pages` if the user additionally answered Y to the GitHub Pages confirmation
   (4b) — never pass `--quartz-pages` without `--quartz` (`init.py` rejects that combination with
   exit code 1; sub-step 4b is only ever asked when 4a was already Y, so this should not occur in
   practice, but the check exists as a safety net in `init.py` itself).
   Add `--repo-root <path>` if a non-default repository root was specified.

   When `--quartz` is given, in addition to `.lychee.toml` / `.markdownlint.json`, it also generates
   `quartz.config.yaml` / `package.json` / `prebuild-symlinks.cjs` / `repair-plugin-builds.cjs`
   (Issue #382 — retries any Quartz community plugin whose build failed after a successful clone,
   since Quartz's own installer marks that state "installed" and never retries it on its own)
   / `quartz-plugins/`
   (a custom plugin providing the review_status banner and JSON-LD embedding, including the pre-built `dist/`)
   / `.github/ISSUE_TEMPLATE/report.md` (backs the banner's "Report an issue" link, Issue #339)
   at the repository root — everything needed for `/wikicommit-serve` to work locally.
   When `--quartz-pages` is additionally given, it also generates `.github/workflows/deploy.yml`
   (Issue #335 — this is the one file that actually opts the repository into automatic GitHub Pages
   publishing on every merge to main; `--quartz` alone never generates it).
   `.lychee.toml` / `.markdownlint.json` are always generated regardless of `--quartz`
   (they are required by `wikicommit-merge`'s quality checks).
   These root-level files are never overwritten if they already exist, regardless of `--no-overwrite`
   (to avoid breaking existing configuration when running init on an existing repository).

3. If `init.py` succeeds (exit code 0), guide the user through the next steps:

   **Obvious-type judgment (Issue #490, a narrower revival of the removed Issue #286 step)**: runs here,
   not in Prerequisites, because it needs two things Prerequisites can't yet guarantee: the confirmed
   repository root (prerequisite 3, asked after the theme prompt) and `.wikicommit/schema/` actually
   existing with the 6 base type files in it (only true once `init.py` has just run, immediately above).
   This whole sub-step is best-effort end to end — any failure at any point falls through silently to the
   lychee auto-install below, and never stops the overall init flow. Skip it entirely if the theme answer
   from Prerequisites was blank — a blank theme gives nothing to reason from.

   Otherwise:

   i. Ensure the shared Schema.org vocabulary cache is available (lazily built on first use, same call
      `wikicommit-generate` Pass 2b and `wikicommit-collect`'s Type Proposal step make):

      ```bash
      python .wikicommit/scripts/check_schema_org_type.py --list-types
      ```

      Non-zero exit (vocabulary fetch failed, e.g. no network) → skip the rest of this sub-step.
      Zero exit → record that the vocabulary cache now exists on disk (`.wikicommit/schemaorg-vocab.json`)
      — this becomes the `--vocab-cache-created` flag passed to `print_next_steps.py` at the end of this
      step, so the printed `git add` command actually includes this new file (it is committed like any
      other WikiCommit output, per that script's own docstring).

   ii. Using the `--list-types` output and the theme text alone, judge whether a Schema.org standard
      type — beyond the 6 always-generated base types (Person/Place/Organization/Event/HowTo/DefinedTerm)
      — is **obviously** implied by the theme, not merely plausible. This bar is deliberately stricter
      than the original Issue #286 step Issue #404 removed: that step treated "zero candidates" as the
      expected common case and still turned out to fire rarely enough to be pure friction; here the bar
      is raised again so that firing is rarer still, but a firing is worth far more when it happens —
      e.g. a theme like "Knowledge base for AI-driven development tooling" obviously implies
      `schema:SoftwareApplication` (named software products are near-certain to be a core topic), whereas
      a vague or broad theme with no single unmistakably-implied type should yield zero candidates, same
      as leaving theme blank. **Re-scan `.wikicommit/schema/` on disk right now** (not from memory of
      Prerequisites) and skip any type that already has a file there — this directory only just gained
      its 6 base type files moments ago in step 2 above, so this is the first point where that scan is
      trustworthy.

   iii. For each candidate found, list it for the user and ask for approval, Enter-based (default **N**
      on a blank Enter — this suggestion must never be added silently):

      ```
      Based on the theme you entered ("Knowledge base for AI-driven development tooling"), this
      Schema.org type seems clearly implied: schema:SoftwareApplication (named software products/tools
      are a near-certain topic for this theme).

      Add this type now? [y/N]
      ```

   iv. For each approved type, verify it still exists in the vocabulary and pick 2–5 candidate
      properties for the new type's `properties:` block, verifying each the same way `wikicommit-generate`
      Pass 2b / `wikicommit-collect`'s Type Proposal step / `wikicommit-schema-propose` Step 4 do:

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

      Each `--property` value goes through its own quote-delimited heredoc (`docs/DesignDoc-skills.md`
      §11.7) — these are candidate names this step itself just proposed, not values an earlier script
      already verified.

      If the script reports `<Type>` itself as `ERROR:`, drop this type silently and move to the next
      approved type — do not write a schema file for it. Otherwise, drop any individual property the
      script reports as `ERROR:` — never put an unverified property into the new schema file's `properties:` block.

   v. Write `.wikicommit/schema/<Type>.md` directly with the Write tool, in the standard-type format
      (`docs/DesignDoc-data.md` §5.2, Issue #495's `properties:`-nested layout), using `.wikicommit/schema/default.md` and
      `.wikicommit/schema/Person.md` (both just written by `init.py`) as the fixed style references. Set
      `wikicommit.provenance: init-theme` in the new file's `wikicommit:` block (`docs/DesignDoc-data.md`
      §5.2, including the "don't copy `Person.md`'s own `provenance: default`" caveat). This
      is the one narrow exception to the "the agent must not write to `.wikicommit/schema/` directly"
      rule in Notes below — it only ever *adds* a file that isn't there yet (step ii's on-disk re-scan is
      what makes this guarantee actually hold), never edits or overwrites one `init.py` wrote. No PR is
      involved (same as every other file `wikicommit-init` produces): the new file just becomes part of
      the `git add` command in the "Commit the generated foundational files" step of the guidance printed
      at the end of this step — do not run `git add`/`commit`/`push` yourself here either.

   First, attempt to auto-install `lychee` (used for external link validation). This runs
   regardless of whether `--quartz` was specified — `.lychee.toml` is always generated either way.
   Unlike the GitHub Pages step below, this needs no prior user confirmation: it only installs a
   local dev tool and never touches Git or `main`.

   i. Check whether `lychee` is already installed:

      ```bash
      lychee --version
      ```

      - Exit code 0 → already installed → skip step ii
      - Exit code non-zero → proceed to step ii

   ii. Attempt to install it via `cargo`. Compiling lychee from source (its dependency tree
      includes reqwest/tokio/hyper) commonly takes several minutes, which exceeds the Bash
      tool's default 120-second timeout — run it with an extended timeout (up to the tool's
      600000ms/10-minute max) so a slow-but-successful compile isn't mistaken for a failure:

      ```bash
      cargo install lychee
      ```

   This step never stops the overall init flow, regardless of the outcome. Record whether lychee
   ended up installed (already present in step i, or `cargo install lychee` exited 0 in step ii) —
   this becomes the `--lychee-installed` flag passed to `print_next_steps.py` at the end of this
   step (see below).

   Next, attempt to auto-install `markitdown` (the Python package `wikicommit-generate` uses to extract
   `type: url` / `type: wikicommit` sources, and as its fallback for file extensions with no dedicated
   Skill — see `wikicommit-generate`'s Prerequisite Skills table). Like the lychee step above, this runs
   unconditionally and needs no prior user confirmation — it only installs a local Python package and
   never touches Git or `main`.

   i. Check whether `markitdown` is already installed:

      ```bash
      markitdown --version
      ```

      This is informational only — always proceed to step ii regardless of the result. `markitdown
      --version` only reports whether the core package is present, not whether the `[pdf]` extra
      (needed for PDF parsing) is installed alongside it, so a bare "already installed" cannot be
      trusted to skip the install step (Issue #242 — an environment with a pre-existing plain
      `markitdown` install, from before the `[pdf]` extra was required, would otherwise never get it).

   ii. Attempt to install it via `pip` (this project assumes a Python environment throughout, unlike
      lychee's Rust/`cargo` toolchain). This is safe to run even when step i reported markitdown as
      already installed — `pip install` on an already-satisfied requirement is a fast no-op:

      ```bash
      pip install 'markitdown[pdf]'
      ```

   This step never stops the overall init flow, regardless of the outcome. Record whether
   markitdown ended up installed (already present, or `pip install 'markitdown[pdf]'` exited 0) —
   this becomes the `--markitdown-installed` flag passed to `print_next_steps.py` below,
   independently of the lychee outcome above.

   Next, attempt to enable the repository setting "Allow GitHub Actions to create and approve pull
   requests" (Settings → Actions → General → Workflow permissions). This runs unconditionally,
   regardless of `--quartz`/`--quartz-pages` (unlike the GitHub Pages step below) —
   `review-issue-close-sync.yml` (Issue #313) is generated in every variant, and without this
   setting its `Commit and open PR` step fails once a reviewer closes a tracking Issue (Issue
   #403). There is no Y/n prompt for this — just attempt it and report the result, same
   best-effort pattern as the GitHub Pages step below.

   i. Skip straight to the fallback guidance below (no `gh api` calls) if `gh auth status` fails,
      or if `gh repo view --json nameWithOwner -q .nameWithOwner` fails (same repo-resolution
      safety rationale as the GitHub Pages step's Issue #333 note below — print
      `Detected repository: <owner>/<repo>`; since this step runs before the GitHub Pages step
      below, its own repo-resolution print can reuse this result instead of repeating it).

   ii. Otherwise, `gh api repos/{owner}/{repo}/actions/permissions/workflow` (GET-before-PUT, not
      a blind PUT). Non-zero exit → fallback. Zero exit → parse `can_approve_pull_request_reviews`;
      already `true` → record as enabled, done. `false` → note `default_workflow_permissions`
      from this same response (must be preserved verbatim below) and proceed to step iii.

   iii. `gh api -X PUT repos/{owner}/{repo}/actions/permissions/workflow -F
      can_approve_pull_request_reviews=true -f default_workflow_permissions=<value from step ii>`
      (re-sending the existing value so this sub-step never silently changes that unrelated
      field). Exit 0 → record as enabled. Non-zero → fallback.

   Never stops the overall init flow; proceed to the GitHub Pages step below regardless of the
   outcome. Record whether the setting ended up enabled — this becomes the
   `--actions-pr-permission-enabled` flag passed to `print_next_steps.py` at the end of this step
   (omit it on any failure/skip above; the script prints the manual fallback on its own then).

   When `--quartz-pages` was specified (this GitHub Pages activation sub-step is skipped entirely
   when `--quartz` was given without `--quartz-pages` — proceed straight to the "Also attempt to set
   up Quartz v5's dependencies" paragraph below in that case):

   First, attempt to enable GitHub Pages (Source: GitHub Actions) automatically. The user already
   consented to this in the Prerequisites Y/n confirmation (4b), so do not ask again — just do it
   and report the result.

   a. Skip straight to the fallback guidance below (do not run `gh api`) if `gh auth status` fails
      (`gh` not authenticated).

   b. Otherwise, before touching Pages at all, resolve and print which repository `gh` will operate on
      (Issue #333 — GitHub Pages enablement is a hard-to-reverse, shared-system operation, and `gh api
      repos/{owner}/{repo}/pages` silently trusts whatever `gh` resolves the current repository to
      without ever showing it; a misconfigured or leftover remote — e.g. still pointing at a real
      repository during isolated pilot/test work — could enable Pages on the wrong repository with no
      on-screen indication). The "Allow GitHub Actions to create and approve pull requests" sub-step
      above already ran this same resolution and print unconditionally — reuse that result here
      instead of repeating the call and the print, unless that sub-step fell back to manual guidance
      (in which case redo it here):

      ```bash
      gh repo view --json nameWithOwner -q .nameWithOwner
      ```

      Print `Detected repository: <owner>/<repo>` using this output. `gh repo view` resolves the
      current repository using `gh`'s own remote-detection logic, which is not limited to a remote
      literally named `origin` — a GitHub remote named `github`, `upstream`, or anything else resolves
      exactly the same way (Issue #373 — an earlier version of this step separately required
      `git remote get-url origin` to succeed before even attempting this call, which skipped straight
      to the manual fallback whenever the repository had no remote named `origin`, even if `gh` could
      already resolve it fine through a differently-named one; that redundant, more restrictive check
      has been removed in favor of letting this single `gh repo view` call double as both the
      existence check and the resolution step). If this command itself fails (e.g. no remote resolves
      to a GitHub repository `gh` can view), treat it the same as the auth check in step a — skip
      straight to the fallback guidance below.
      This is informational only — do not pause for confirmation (the user already consented in the
      Prerequisites Y/n confirmation (4b); this step only makes the target visible, per SKILL.md's
      existing non-blocking policy for this sub-step).

   c. Check first whether Pages is already enabled, then only create it if not
      (a GET-before-POST check, not a POST followed by guessing from error text):

      ```bash
      gh api repos/{owner}/{repo}/pages
      ```

      `gh api` resolves `{owner}` and `{repo}` from the current repository's GitHub remote automatically.

      - Exit code 0 → Pages is already enabled (idempotent case — a previous run or manual setup) →
        extract the `html_url` field from this same response (e.g. `gh api repos/{owner}/{repo}/pages
        --jq .html_url`) and record it for the `--pages-html-url` flag below (Issue #282 — the API's
        `html_url` is used as-is rather than hand-built from `{owner}`/`{repo}`, since it resolves
        correctly for project pages, user/org pages, and custom domains alike) and skip step d below
      - Exit code non-zero (typically because no Pages site exists yet) → proceed to step d

   d. Create the Pages site:

      ```bash
      gh api repos/{owner}/{repo}/pages -X POST -f build_type=workflow
      ```

      - Exit code 0 → extract `html_url` from this response the same way as step c above and record
        it for the `--pages-html-url` flag below
      - Exit code non-zero (e.g. private repo without GitHub Pro/Team/Enterprise, insufficient `gh`
        permissions) → no `html_url` is available

   When (a) is skipped, (b) fails, or (d) fails with a real error, no `html_url` is available —
   omit `--pages-html-url` when calling `print_next_steps.py` below; the script prints the
   `⚠️ Could not enable GitHub Pages automatically` fallback guidance on its own in that case.

   This step never stops the overall init flow — proceed to the Quartz dependencies step below
   regardless of the outcome.

   Also attempt to set up Quartz v5's dependencies automatically whenever `--quartz` was specified
   (this runs regardless of `--quartz-pages`, and regardless of the GitHub Pages step above's
   outcome when that step did run), unless step 2's `init.py` output logged
   `SKIPPED: package.json (already exists)` — in that case the repository has its own pre-existing
   `package.json` that is not the WikiCommit template, and auto-running `npm install` would install
   and execute that project's own dependencies and lifecycle scripts without the user's
   confirmation, so skip this step (e below) entirely and pass `--package-json-skipped` to
   `print_next_steps.py` at the end of this step instead (Issue #276 — without this, the "Preview
   the wiki locally" step in the guidance still unconditionally tells the user to run
   `/wikicommit-serve`, which would fail with "missing script" since the WikiCommit template's
   `scripts`/`devDependencies` were never merged into the pre-existing `package.json`). The script
   prints a warning explaining the required manual merge, and keeps both lines of the "Set up
   Quartz v5" step unchanged — `git submodule add` and `npm install` themselves don't depend on the
   `preview`/`build` scripts being present.

   `package.json`'s `postinstall` hook runs `git submodule update --init --recursive` (a no-op when
   `quartz` hasn't been added as a submodule yet) and then, only if `quartz/` exists, installs the
   submodule's own dependencies inside it — the template guards this step on `quartz/`'s existence,
   so a first-time init (before the user has run `git submodule add`, below) is skipped rather than
   crashing with `ENOENT`. This means `npm install` below always exits 0 regardless of whether the
   submodule has been added yet; only checking for `quartz/` afterward distinguishes "fully set up"
   from "top-level dependencies only".

   e. Otherwise (package.json was not skipped), determine Quartz v5's setup status and run
      `npm install` if needed by calling the setup-state script (script delegation pattern — see
      `docs/DesignDoc-skills.md` §11.5; this replaces a multi-branch `test -d` decision that
      previously had to be walked as prose, see #229):

      ```bash
      python .claude/skills/wikicommit-init/scripts/check_quartz_setup.py
      ```

      It always exits 0 and prints one JSON line, e.g. `{"status": "fully_set_up"}`. Record the
      `status` field verbatim — this becomes the `--quartz-status` flag passed to
      `print_next_steps.py` below, which decides both the announcement line above the numbered list
      and whether/how the "Set up Quartz v5" step appears in it (e.g. `npm_install_failed_submodule_exists`
      keeps only the `npm install` line — re-running `git submodule add` on a path already
      registered in the index fails with `fatal: 'quartz' already exists in the index`).

      Whenever `quartz/` already exists (`status` is `fully_set_up`,
      `npm_install_completed_fully_set_up`, or `npm_install_failed_submodule_exists`), the script
      also attempts `npm run install-plugins` itself and includes the outcome as an
      `install_plugins_ok` boolean field in the same JSON line (Issue #380 — otherwise a
      `--no-overwrite --quartz` re-init that finds Quartz already set up never surfaces this
      guidance anywhere, since the "Set up Quartz v5" step that normally carries it is the one
      being omitted). When present, pass it through as `--install-plugins-status ok` or
      `--install-plugins-status failed` to `print_next_steps.py` below; omit the flag entirely when
      the field is absent from the JSON (quartz/ did not exist yet, so the attempt could not run).

      This step never stops the overall init flow, regardless of the outcome — like the GitHub
      Pages step above and the lychee step earlier in this section, it is unconditionally best-effort.

   Finally, render and print the complete "Next steps" guidance by calling the templating script
   (script delegation pattern — see `docs/DesignDoc-skills.md` §11.5; this is what replaced the
   three near-duplicate hardcoded guidance blocks that used to live here and pushed this file past
   the 500-line recommendation, see #350):

   ```bash
   python .claude/skills/wikicommit-init/scripts/print_next_steps.py \
     --variant <none|quartz_only|quartz_pages> \
     [--lychee-installed] [--markitdown-installed] \
     [--actions-pr-permission-enabled] \
     [--package-json-skipped] [--quartz-status <status>] \
     [--install-plugins-status <ok|failed>] \
     [--pages-html-url <url>] [--vocab-cache-created]
   ```

   - `--variant`: `none` if `--quartz` was not passed to `init.py` in step 2; `quartz_only` if
     `--quartz` was passed without `--quartz-pages`; `quartz_pages` if both were passed.
   - `--vocab-cache-created`: pass this whenever the obvious-type judgment's step i above got a zero
     exit from `--list-types` (regardless of whether any type ended up approved in step iii — the
     vocabulary cache file is written to disk as soon as that call succeeds); omit it if that call was
     skipped (blank theme) or failed (non-zero exit, e.g. no network).
   - `--lychee-installed` / `--markitdown-installed`: pass whichever of these ended up installed,
     per the auto-install steps above.
   - `--actions-pr-permission-enabled`: pass this whenever the "Allow GitHub Actions to create and
     approve pull requests" setting ended up enabled (already `true`, or the `PUT` succeeded) per
     the sub-step above; omit it on any failure/skip there, regardless of `--variant` (this setting
     is unconditional — `review-issue-close-sync.yml` ships in every variant).
   - `--package-json-skipped` / `--quartz-status`: only meaningful when `--variant` is
     `quartz_only` or `quartz_pages`. Pass `--package-json-skipped` if step 2's `init.py` output
     logged `SKIPPED: package.json (already exists)`; otherwise pass `--quartz-status <status>`
     with the `status` value recorded from `check_quartz_setup.py` above.
   - `--install-plugins-status`: only meaningful alongside `--quartz-status` (omit whenever
     `--package-json-skipped` is passed instead, or when `check_quartz_setup.py`'s JSON had no
     `install_plugins_ok` field). Pass `ok` or `failed` based on that field's value.
   - `--pages-html-url`: only meaningful when `--variant` is `quartz_pages` — pass the `html_url`
     recorded above, if any (omit it if the GitHub Pages activation fell back to manual guidance).

   Print the script's stdout output to the user verbatim — it is the complete guidance (any
   `✅`/`⚠️` announcement lines, the numbered "Next steps" list, and the `quartz_only` variant's
   trailing note about GitHub Pages not being set up, where applicable). It always exits 0.

4. If `init.py` fails (exit code 1), display the stdout and stderr output to the user and stop.

## Notes

- The README.md link suggestion in the `--quartz-pages` guidance (the final numbered step) is display-only, same as the `git add`/`commit`/`push` commands above it — the agent never edits README.md itself (Issue #282). Unlike `.wikicommit/config.yml` or the schema templates, README.md is very likely a pre-existing file with its own structure (especially when WikiCommit is added to an existing repository, see `docs/DesignDoc-data.md` §3.1), so an automatic insertion risks breaking it
- Call `init.py`. Do not manually create directories in the agent itself (script delegation pattern)
- Writing to `.wikicommit/schema/` is done by `init.py`. The agent must not write to it directly, with one narrow exception: step 3's obvious-type judgment (Issue #490, reviving a narrower version of the Issue #286 step Issue #404 removed) may write a new `.wikicommit/schema/<Type>.md` file the user approved there — it only ever adds a file that isn't already there, never edits or overwrites one `init.py` wrote. See `docs/DesignDoc-data.md` §3.3 for how this entry point's evidence and approval bar differ from `wikicommit-generate` Pass 2b (Issue #315) and `wikicommit-collect`'s Type Proposal step (Issue #489) — the three are not redundant with each other, and that section is the single source of truth for the role split (do not re-derive it here)
- `init.py` does not fetch the Quartz v5 core (`quartz/` directory) automatically. Adding the git submodule involves network and git operations, so the user must run it manually per the next-steps guidance above
- The `git add` / `git commit` / `git push` commands shown in the next-steps guidance above are display commands meant for the user to copy and run themselves. The agent must never run them on the user's behalf (writes to `main` and `.wikicommit/schema/` are prohibited for the LLM)
- The `gh api repos/{owner}/{repo}/pages` call in step 3 only runs when `--quartz-pages` was specified (Issue #335 — `--quartz` alone sets up local build/preview only and never touches GitHub Pages). It is a GitHub *repository setting* change (enabling Pages), not a write to `main` or to the wiki content, so the agent runs it directly — unlike the `git add`/`commit`/`push` commands above, it does not need to be deferred to the user. It is unconditionally best-effort: any failure (missing remote, unauthenticated `gh`, plan restriction, permissions) falls back to printed manual instructions and never aborts `wikicommit-init`
- The `gh api repos/{owner}/{repo}/actions/permissions/workflow` calls in step 3 (enabling "Allow GitHub Actions to create and approve pull requests") run unconditionally, regardless of `--quartz`/`--quartz-pages` — unlike the Pages setting immediately above, this one backs `review-issue-close-sync.yml`, which every variant generates (Issue #313). It is the same kind of GitHub *repository setting* change as the Pages call, not a write to `main` or the wiki content, so the agent runs it directly and does not defer it to the user. It is unconditionally best-effort (Issue #403 — discovered via a repository where the review-Issue-close auto-merge flow had never once completed successfully; this was one of three compounding causes, alongside the `closed_by` webhook payload and missing `issues: read` permission fixed directly in the `review-issue-close-sync.yml` template): any failure (missing remote, unauthenticated `gh`, insufficient token scope) falls back to printed manual instructions and never aborts `wikicommit-init`. The GET-before-PUT check exists to make the change idempotent and to avoid silently overwriting the unrelated `default_workflow_permissions` field the same API endpoint also controls
- The `lychee --version` / `cargo install lychee` calls in step 3 only install a local dev tool — they touch neither Git nor `main` — so the agent runs them directly and unconditionally (no prior user confirmation needed, unlike the Quartz Y/n prerequisite). Like the GitHub Pages step, this is best-effort: any failure (`cargo` missing, network unreachable) falls back to the printed manual instructions and never aborts `wikicommit-init`
- The `markitdown --version` / `pip install 'markitdown[pdf]'` calls in step 3 mirror the lychee handling above — a local Python package install that touches neither Git nor `main`, so the agent runs them directly and unconditionally, independently of the lychee outcome. `pip` (not `cargo`) is used because `markitdown` is a Python package and this project assumes a Python environment throughout (`docs/DesignDoc-ScriptSpec.md`). It is best-effort: any failure (`pip` missing, network unreachable) falls back to the printed manual instructions and never aborts `wikicommit-init` (Issue #208 — `markitdown` became a required dependency for `wikicommit-generate`'s `type: url` / `type: wikicommit` extraction path in Issue #189, but `wikicommit-init` had no corresponding install-assist step, unlike lychee; the `[pdf]` extra was added in Issue #242 once `.pdf` (text-based) extraction started using `markitdown` as its own fallback when the `pdf` skill is unavailable)
- The `check_quartz_setup.py` call in step 3.d (when `--quartz` was specified, and only if `init.py` actually generated `package.json` rather than skipping a pre-existing one — see step 3 above) mirrors the lychee "check first, only act if needed" pattern, now delegated to a script rather than agent-read prose (#229): the script's own `node_modules` / `quartz/node_modules` pre-check avoids re-running a possibly slow `npm install` when a `--no-overwrite` re-init finds Quartz v5 already fully set up, and it runs `npm install` itself when needed. `npm install` is a local, network-only-for-fetching-packages operation — it touches neither Git history nor `main` (git operations it may trigger via `postinstall`, namely `git submodule update`, only affect the working tree, not `main`) — so the agent runs the script directly without prior user confirmation, same as lychee. The `package.json` template's `postinstall` hook guards on `quartz/`'s existence before installing the submodule's own dependencies (Issue #214 — previously it crashed with an uncaught `ENOENT` on every first-time `wikicommit-init --quartz` run, before the user had manually run `git submodule add`), so `npm install` now exits 0 either way; the script distinguishes "fully set up" from "top-level dependencies only" by checking for `quartz/` afterward, not by `npm install`'s exit code, and reports both outcomes as the same top-level JSON contract so the agent no longer needs to branch on exit codes itself. It is still best-effort end to end: any `npm install` failure (`npm`/Node.js not installed, network unreachable, malformed `package.json`) is reported as one of the `npm_install_failed_*` statuses, which map to keeping `npm install` in the printed manual instructions; the script always exits 0 and never aborts `wikicommit-init`
- `print_next_steps.py` (step 3's final call, Issue #350) owns the "Next steps" guidance text itself — which lines to show/omit/reword is fully determined by the flags the preceding sub-steps already computed (variant, install statuses, GitHub Pages `html_url`, Quartz setup status), so encoding that branching in Python once instead of three hand-maintained near-duplicate prose blocks in this file is the same script delegation trade-off as `check_quartz_setup.py` above. It only ever formats and prints text to stdout — it never touches Git, `main`, or `.wikicommit/schema/`, so the agent runs it directly and prints its output to the user verbatim, same as the other auto-run steps in step 3
- The "Set up Quartz v5" guidance line (`print_next_steps.py`'s `_QUARTZ_SETUP_FULL`/`_QUARTZ_SETUP_NPM_ONLY`) appends `npm run install-plugins` after `git submodule add` / `npm install`, with a note that the first run commonly takes several minutes (Issue #353). `check_quartz_setup.py` cannot auto-run this itself on a first-time init: at the point it runs, the user has not yet run `git submodule add`, so `quartz/` does not exist and `cd quartz && npx quartz plugin install` has nothing to operate on. Folding it into the same manual guidance block as `git submodule add`/`npm install` instead means the user pays this cost once, right after adding the submodule, rather than it landing silently on whichever `/wikicommit-serve` run happens to call `npm run install-plugins` first (previously this was `/wikicommit-serve --build`, a Skill designed to be a lightweight, Git-free sanity check — see Issue #276 — timing out under Bash's default 5-minute foreground limit)
- **`--no-overwrite --quartz` re-init and `npm run install-plugins` (Issue #380)**: the "Set up Quartz v5" guidance line above only exists for the statuses where `git submodule add` and/or `npm install` still need to happen. When `quartz/` already exists and is fully set up (`fully_set_up`, `npm_install_completed_fully_set_up`), `build_quartz_setup_step()` used to omit the entire step — including the only place `npm run install-plugins` was mentioned — silently dropping that guidance on any `--no-overwrite --quartz` re-run that found Quartz already set up, even though having `node_modules`/`quartz/node_modules` says nothing about whether the separate `npx quartz plugin install --from-config` step (community plugin symlinking) had ever run. `check_quartz_setup.py` now closes this the same way it already handles `npm install` itself: whenever `quartz/` exists (all three statuses above plus `npm_install_failed_submodule_exists`), it also runs `npm run install-plugins` best-effort and reports the outcome as `install_plugins_ok`. `print_next_steps.py` uses that field to decide the remaining branching: success needs no further guidance (and gets a `✅ Quartz community plugins installed` announcement instead); failure prints a standalone `_INSTALL_PLUGINS_STEP` reminder in the previously-omitted-entirely case, or drops the now-redundant `npm run install-plugins` line from `_QUARTZ_SETUP_NPM_ONLY` (→ `_QUARTZ_SETUP_NPM_INSTALL_ONLY`) in the `npm_install_failed_submodule_exists` case where success already happened despite the top-level `npm install` failing. This mirrors `check_quartz_setup.py`'s own `npm install` best-effort pattern — same local, Git-free, no-`main`-write operation, so no additional user confirmation is needed
- **`repair-plugin-builds.cjs` (Issue #382)**: `npm run install-plugins` (`cd quartz && npx quartz plugin install --from-config`) can leave a plugin permanently stuck. Quartz's own installer (`quartz/quartz/cli/plugin-git-handlers.js`, `handlePluginInstallUnified`) writes a plugin's `quartz.lock.json` entry as soon as `git clone` succeeds, before that plugin's own `npm install --ignore-scripts && npm run build` (run inside the plugin's own directory, independent of this repo's root `package.json`/`node_modules`) runs; if that build step fails, Quartz swallows the exception and never corrects the lockfile entry it already wrote. The next run's "already installed?" check (`lockfile.plugins[name] && fs.existsSync(pluginDir)`) is still true — only the build failed, not the clone — so the broken plugin is silently skipped forever, unlike a clone failure (which never writes a lockfile entry and so retries automatically). `npx quartz plugin install` also never surfaces this as a non-zero exit code (the CLI command handler just awaits the installer and returns), so a plain `&&`-chained npm script can't detect it from the exit status either. `repair-plugin-builds.cjs` (appended to the `install-plugins` npm script, after the existing `npx quartz plugin install --from-config` call) closes this without touching the Quartz submodule: it treats a plugin as stuck when its directory exists in `quartz/.quartz/plugins/` but has no `dist/` (the same completion signal Quartz's own `hasPrebuiltDist`/`needsBuild` use internally), deletes that plugin's directory and lockfile entry so it looks "never installed" again, and re-runs `npx quartz plugin install --from-config` so Quartz retries clone+build for it exactly as it already does for clone failures (bounded to 3 attempts, then a clear, actionable error naming the still-stuck plugin and the exact command to run inside its directory to see the underlying error). Confirmed via a from-scratch clone of Quartz's `plugin-git-handlers.js`/`plugin-data.js` (`v5` branch) and a real 48-plugin, 16-way-parallel reproduction — not merely inferred from symptoms. Root `package.json`'s own `shiki` (a dependency some third-party plugins need) was considered and rejected as a fix: each plugin's build runs with that plugin's own directory as `cwd`, never touching this repo's root `node_modules`, so adding `shiki` there has no effect on a plugin's own build failure
