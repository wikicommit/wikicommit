---
name: wikicommit-update
description: Bring an initialized wiki repository in step with the installed WikiCommit distribution — refresh WikiCommit's own payload, show what changed in files you may have edited, restamp the synced version, verify, and open a PR for review
disable-model-invocation: true
---

# wikicommit-update

Brings this repository in step with the WikiCommit distribution currently installed under `.claude/skills/`, and opens a pull request with the result.

A wiki repository holds three kinds of thing, and only the first is yours:

- **What you wrote** — pages, `config.yml`, the type templates in `.wikicommit/schema/`
- **WikiCommit's own payload** — `.wikicommit/scripts/`, `quartz-plugins/`, the two workflows, the `*.cjs` build scripts. You never edit these, so they can simply be refreshed
- **Generated elsewhere** — `quartz/`, `package-lock.json`. Not this Skill's business

This Skill refreshes the second, shows you the first so you can decide, and never touches the third. It always ends in a pull request — nothing is merged automatically, because the whole point of the middle part is that a person looks at it.

## Update the Skills first

**This Skill does not update `.claude/skills/` itself.** Do that before running it:

```bash
npx skills add wikicommit/wikicommit --skill '*' --agent claude-code -y --copy
```

The reason is not caution: a Skill that rewrites its own `SKILL.md` mid-run leaves the agent executing the instructions it loaded at the start, which are now the old ones. So the order is: update the Skills, then run this.

## Usage

```
/wikicommit-update
```

No arguments. Everything it needs is on disk.

## Processing Flow

### Step 1: Compare Versions

Read `wikicommit_version` from `.wikicommit/config.yml` — the version this repository was last brought in step with — and the `VERSION` in `.claude/skills/wikicommit-init/scripts/templates/scripts/_version.py`, which is what is installed now.

- **Equal** → tell the user there is nothing to update and stop. Do not run the rest.
- **Different** → record both. The pair bounds which changelog entries are new.
- **`wikicommit_version` absent** → this repository predates the stamp. Treat every entry in the changelog as new, and say so: the report will be long, and that is expected once.

If `.wikicommit/config.yml` does not exist, stop and tell the user to run `/wikicommit-init` first. If `.claude/skills/wikicommit-init/` does not exist, stop and tell them to install the Skills (the command above).

### Step 2: Detect Drift

```bash
python .wikicommit/scripts/check_distribution_freshness.py
```

**If that file does not exist, use the copy in the Skill tree instead** — it resolves everything from `--repo-root`, so it reports the same thing:

```bash
python .claude/skills/wikicommit-init/scripts/templates/scripts/check_distribution_freshness.py
```

A repository initialized before this script shipped does not have it under `.wikicommit/scripts/`, and that is exactly the repository this Skill exists for. The installed copy only arrives with Step 3, which runs after this.

Read its `OUTDATED:` / `MISSING:` / `ORPHAN:` lines and the `SUMMARY:` counts. Each line names a path and says what is wrong with it. Nothing at all, together with equal versions in Step 1, means there is genuinely nothing to do.

Note what a quiet result on a file you may have edited does **and does not** mean: those are compared only for things the template has *gained* — a new setting, a new frontmatter key, a new ignore pattern. Silence means nothing was added upstream that is missing here, not that your file matches the template.

### Step 3: Refresh WikiCommit's Own Payload

```bash
python .claude/skills/wikicommit-init/scripts/init.py --no-overwrite \
  --primary-lang "<translation.primary_lang from config.yml>"
```

**Pass `--primary-lang`, taken from this repository's `config.yml`.** It defaults to `en`, and the flag decides which language directories get created — omit it on a `ja` wiki and the refresh creates an empty `.wikicommit/entity/en/` and `.wikicommit/view/en/`, which Step 8 then commits. `config.yml` itself is not rewritten either way (it is the user's).

Add `--quartz` and `--quartz-pages` to match how this repository was set up (`quartz.config.yaml` present → `--quartz`; `.github/workflows/deploy.yml` present → also `--quartz-pages`). Omitting a flag the repository was initialized with does not damage anything, but it leaves that half of the distribution un-refreshed.

This refreshes the payload listed above and leaves everything else alone. **Keep `--no-overwrite`.** It is no longer the only thing protecting your files — each path now declares whether it is WikiCommit's or yours — but there is no reason to drop it, and older installations of the Skills still rely on it.

### Step 4: Confirm Orphan Deletions

Each `ORPHAN:` line from Step 2 is a file that exists here with no counterpart in the distribution — almost always a script renamed upstream, whose old name stayed behind because a refresh copies but never deletes.

**Never delete one without asking.** Show the list, and for each say what it is and what would break. Delete only what the user confirms, one by one — not as a batch, and not by default. An orphan is harmless where it sits; deleting one that something still calls is not.

If the user is unsure about a file, leave it. It can go in the next update.

### Step 5: Show What Changed in Files You May Have Edited

For each remaining `OUTDATED:` / `MISSING:` line, one file at a time. Never edit any of these without showing the user first and getting an answer.

**`.wikicommit/config.yml`** — the finding names settings the template has that this file lacks. Offer to add them:

```bash
python .claude/skills/wikicommit-init/scripts/init.py --add-config-keys <key> [<key> ...]
```

This appends each setting with the commented example that documents it, and never rewrites a value already there. Explain what each new setting does (the changelog entry from Step 9 usually says) and let the user pick. A setting they decline is simply not added — every one of them is optional and inert until filled in.

**`quartz.config.yaml`** — show the new keys and where they sit in the file. **Do not present the repository's own settings as differences**: `pageTitle`, `pageTitleSuffix`, `locale`, `baseUrl`, `links`, `theme` and anything under `translation` are this wiki's, and listing them as drift buries the one line that actually matters. Four of those (`pageTitle`, `pageTitleSuffix`, `locale`, `links`) are written by substituting a `{...}` placeholder at init time, so the template still holds the placeholder — copying one across would put the literal `{LOCALE}` into the config, where YAML reads it as a mapping rather than a locale string. Apply what the user accepts by hand, in place, preserving their formatting and comments.

**`.wikicommit/schema/`** — this is the one tree a person is meant to edit directly, so it is compared byte for byte and any difference shows up. For each differing type template, show the diff **together with the changelog entry that explains it** (Step 9) — a diff on a type template without the reason for it is not something anyone can act on. Apply only what the user accepts. Where they have their own edits in the same file, merging is theirs to do: point at both sides rather than choosing.

**Everything else** (`.lychee.toml`, `.markdownlint.json`, `package.json`, the issue template, `.gitignore`) — show the difference and ask. `package.json` in particular may differ because this repository had its own before WikiCommit was installed; in that case what matters is whether the template gained a script this repository needs, not that the two files differ.

### Step 6: Restamp the Synced Version

```bash
python .claude/skills/wikicommit-init/scripts/init.py --update-version <installed version>
```

Only after Steps 3–5 are done. This records what this repository is now in step with, so the next update knows where to start reading from — and it is the only thing that writes this field.

Do this even if the user declined some of Step 5. Those are optional settings and their own type-template edits; the distribution itself is in step, and leaving the stamp behind would make the next update replay the entire range.

### Step 7: Verify

Run these in order, and stop at the first real failure rather than pressing on:

```bash
python .wikicommit/scripts/rebuild_index.py
python .wikicommit/scripts/validate_frontmatter.py
python .wikicommit/scripts/check_wikilinks.py
python .wikicommit/scripts/check_raw_html.py
python .wikicommit/scripts/check_orphans.py
python .wikicommit/scripts/check_distribution_freshness.py
```

The last one is the confirmation that this run did what it set out to do: what remains should be only what the user declined in Step 5, plus orphans they chose to keep. Anything else means a step did not take.

If this repository publishes with Quartz, build it too:

```bash
npm install && npm run build
```

A failure here usually means the refreshed plugins and the local `quartz.config.yaml` disagree — worth resolving now rather than discovering it in a deploy.

### Step 8: Open a Pull Request

Find the repository's default branch first, and use it below instead of assuming `main`:

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
```

If that fails (no GitHub remote, or `gh` is not authenticated), fall back to `main` and warn the user that the branch and PR operations will fail if the real default branch differs.

If the current branch is not the default branch, say so and ask before continuing — the PR would otherwise carry that branch's other commits too. Do not switch branches here: Steps 3–6 have already changed files, and a checkout that would overwrite them fails.

```bash
# Branch from wherever HEAD already is. Steps 3-6 have already modified tracked
# files, so pulling here would abort as soon as the remote had touched any of the
# same paths, leaving the update half-applied and uncommitted.
git checkout -b "wikicommit/update-<installed version>"

# Stage the update, not the build. `git add -A` would also sweep in package-lock.json
# (rewritten by Step 7's npm install) and any unrelated untracked file — both of which
# this Skill declares out of scope at the top.
git add .wikicommit .claude .github quartz-plugins .gitignore \
  .lychee.toml .markdownlint.json package.json quartz.config.yaml \
  prebuild-symlinks.cjs repair-plugin-builds.cjs install-local-plugins.cjs
# (drop any path this repository does not have; `git add` fails on a missing pathspec)

git commit -m "$(cat <<'EOF'
chore: sync distribution to <installed version>

Co-Authored-By: <Claude display name> <noreply@anthropic.com>
Generated-By:   <current model ID>
EOF
)"
git push -u origin "wikicommit/update-<installed version>"
gh pr create --base "<default branch>" --title "..." --body "..."
```

**The trailer's model fields are placeholders, not literals.** Write the ID of the model actually running this Skill, exactly as the runtime reports it (keep any suffix; do not shorten or normalize it), and its human-readable display name — or just `Claude` when that name is not known with confidence. `<noreply@anthropic.com>` is a fixed literal. Never hardcode a model ID.

Pass the title and body through a heredoc with a quoted delimiter (`"$(cat <<'EOF' ... EOF)"`), the way the other Skills do — the changelog text going into the body is free-form and may contain characters a shell would otherwise act on.

If the default branch has moved on since this branch was cut, rebase it (`git fetch origin && git rebase "origin/<default branch>"`) **after** the commit exists, not before — at that point a conflict is something the user can look at, rather than an abort that leaves nothing recorded.

**Do not merge, and do not enable auto-merge.** Everything in Steps 4 and 5 was a judgment call, and the PR is where someone checks it. If the branch already exists, this update is already in flight — say so rather than force-pushing over it.

The body should carry: the version range, what was refreshed, what the user declined and why, orphans deleted and kept, and the regeneration candidates from Step 9.

### Step 9: Report

**Read only the versions between the two from Step 1** (Issue #801). The changelog is one file per release, so this is a matter of opening the right files rather than filtering a large one:

- `.claude/skills/wikicommit-init/CHANGELOG.md` holds `[Unreleased]`, the latest released version, and an index of every earlier one
- `.claude/skills/wikicommit-init/changelog/<version>.md` holds each earlier version, one per file

Take the index, pick the versions above the synced one, and open those files and no others. A user one version behind should read one entry — do not read the whole set and then filter, which costs the same as before the split. Pasting everything you read is likewise the same as reporting nothing.

When Step 1 found no stamp the range is unknown: say so, and summarize from the latest version and the index rather than opening every file.

Then count the pages worth rebuilding:

```bash
grep -rl "generated_with" .wikicommit/entity/ .wikicommit/view/ 2>/dev/null \
  | xargs -r grep -L "generated_with: \"<installed version>\""
```

`grep -rl` alone lists every page that carries the field at all, including ones already written at the installed version; the second pass drops those. Pages with no `generated_with` at all predate the field and are not listed by either pass — mention them separately if the wiki has any. `.wikicommit/view/` does not exist on a repository initialized before it was introduced, hence the `2>/dev/null`.

Pages whose `generated_with` is older than the installed version were written under rules that have since changed. **Report the count and the changelog entries that explain why; do not rebuild anything.** Which pages are worth redoing is a judgment call — the version is coarser than the change (a release that touched one type template makes every page look equally old), so the count is a starting point and the changelog entries are what narrow it. `/wikicommit-generate --regenerate` is how they get rebuilt, when the user decides to.

Close with: the version this repository is now in step with, the PR link, and anything left for the user to do.

## Notes

- **Nothing here merges.** This Skill opens a PR and stops.
- **Steps 4 and 5 always ask.** Deleting a file and changing a setting are the user's calls; this Skill's job is to make them answerable, not to make them.
- **Type templates are not auto-merged.** `.wikicommit/schema/` is the one tree humans edit directly, so a difference is shown, never applied silently.
- **Page rebuilds are out of scope.** Reported, not run.
- **The Skills themselves are updated outside this Skill** (see the top).
