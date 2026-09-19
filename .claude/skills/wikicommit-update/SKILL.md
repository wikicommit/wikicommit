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

Then record whether the wiki's own content was already modified before this run started:

```bash
git status --porcelain -- .wikicommit/entity .wikicommit/view .wikicommit/schema
```

**Do this here and nowhere later.** Step 7 needs to know whether these paths were clean when the run began, and from Step 3 onward this Skill writes to them itself — after that, nothing can separate the user's edits from its own. Anything listed here: tell the user now that their uncommitted page edits make Step 7's judgment unreliable, and carry the list forward to Step 7.

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

Run these in order:

```bash
python .wikicommit/scripts/rebuild_index.py
python .wikicommit/scripts/validate_frontmatter.py
python .wikicommit/scripts/check_wikilinks.py
python .wikicommit/scripts/check_raw_html.py
python .wikicommit/scripts/check_orphans.py
python .wikicommit/scripts/check_distribution_freshness.py
```

The last one is the confirmation that this run did what it set out to do: what remains should be only what the user declined in Step 5, plus orphans they chose to keep. Anything else means a step did not take.

**A blocking failure in the middle four is not automatically this update's doing.** Those four read the wiki's own pages, and this update does not write pages — so a failure there is often a deviation that was already on the default branch and is only surfacing now, because a check grew stricter or started looking at every page instead of the changed ones. Which of the two it is decides the right response, and the output alone does not tell them apart. Work it out rather than guessing, and do not stop on a finding this update did not create.

#### Deciding whether a blocking failure is this update's

Only `validate_frontmatter.py`, `check_wikilinks.py`, `check_raw_html.py` and `check_orphans.py` need this. `rebuild_index.py` and `check_distribution_freshness.py` always exit 0, and the second of those measures the update itself, so "pre-existing" is not even defined for it. Warnings are out of scope — plenty of those are normal.

**Stage 1 — did this run write anything those checks read?**

```bash
git status --porcelain -- .wikicommit/entity .wikicommit/view .wikicommit/schema
```

- **Empty** → this run did not write a byte of what they read, so the finding is pre-existing by definition. No stash, no stage 2.
- **Non-empty** → go to stage 2, passing **whichever of those three directories exist** — not the individual file paths this printed. Why directories is the next section.

**`.wikicommit/config.yml` is deliberately not in that list**, even though `check_wikilinks.py` reads it. Step 6 rewrites its `wikicommit_version:` line on every run, so including it would make stage 1 non-empty every single time and the cheap branch above unreachable. The only thing the four checks read out of that file is `translation.primary_lang`, which no step of this Skill touches.

A path that does not exist is fine *here*: `git status` accepts a pathspec matching nothing, so a repository with no `.wikicommit/view/` still exits 0. **Stage 2 is not so forgiving** — drop any of the three that does not exist before passing them on.

**Stage 2 — the new checker against the old content**

```bash
before=$(git rev-parse -q --verify refs/stash || true)
git stash push -u -- <the directories from stage 1 that exist>
after=$(git rev-parse -q --verify refs/stash || true)

<re-run just the one check that failed>

# Pop only if this push actually created an entry
[ -n "$after" ] && [ "$after" != "$before" ] && git stash pop
```

**Narrowing the pathspec is the whole point.** `.wikicommit/scripts/` and `.claude/skills/` stay refreshed, so the *new* checker examines the *old* pages — which is the actual question being asked. A bare `git stash` rolls the checker back as well, and then a check that has merely grown stricter finds nothing, and you conclude the update broke something it never touched.

Same error → pre-existing. Error gone → this update caused it.

**`-u` and the `refs/stash` comparison are both load-bearing.** Step 3 adds files as well as changing them — `.gitkeep` under a language directory it had to create, a base type new upstream — and those arrive untracked. Four things follow, all of them observed:

| What happens | Why the shape above handles it |
|---|---|
| `git stash push` **aborts entirely** (`did not match any file(s) known to git`, exit 1, nothing stashed) when a pathspec matches nothing *known to git* — which includes a path that exists on disk but is untracked | `-u` takes untracked content too, so a tree whose only change under one of these directories is a file this run created no longer aborts. Passing the individual paths stage 1 printed is what walks into this: one `??` entry among them is enough |
| Without `-u`, a directory pathspec stashes the tracked modifications and **leaves untracked files in place** | Then the file this run added is still there for the re-run, the same error comes back, and it reads as pre-existing — the verdict inverted, in the direction that opens a PR |
| A push that creates **no entry** still leaves a following `pop` to open whatever unrelated stash the user already had | The `before`/`after` comparison, not the stage-1 emptiness test alone: a non-empty stage 1 can still end in no entry. `-u` also **stashes and then exits 1** on a directory that does not exist, keeping the entry — so never key the pop off the exit code either |
| A conflicting `pop` leaves the working tree broken mid-update | **Stop there.** Show `git stash list` and how to recover. Do not open a PR |

**If Step 2's probe already listed changes under those paths, the verdict is unreliable** — the user's own uncommitted page edits are rolled back in stage 2 too, so an error they introduced reads as this update's. That errs toward stopping, which is the safe direction, but say so rather than leaving it implicit.

#### What to do with the verdict

- **This update's** → stop, as before. Something in Steps 3–6 did not take, and a PR should not go out on it.
- **Pre-existing** → say so and carry on to Step 8. The update itself is sound, and holding it hostage to a deviation it did not create fixes nothing — it just turns one problem into two. Carry the finding into the report (Step 8 and Step 9) together with its consequence.

The consequence differs by check, and that is the part worth writing down:

- **`check_orphans.py` `DUPLICATE:`** → this is the one that actually blocks. `/wikicommit-merge` runs this check unscoped, so **this wiki cannot merge anything until it is fixed.** Say that plainly, and say it before the user writes their next page.
- **`check_wikilinks.py`, a wrong Type segment** → `/wikicommit-merge` only looks at changed files, so it does not stop there today. `/wikicommit-status` reports it as `TYPE_MISMATCH:` and will keep doing so.
- **Everything else** — `validate_frontmatter.py` and `check_raw_html.py` errors, and links to a `status: removed` page → merge passes over them and **no standing check reports them**. Nobody sees them again until that page is next written.

If this repository publishes with Quartz, build it too:

```bash
npm install && npm run build
```

A failure here usually means the refreshed plugins and the local `quartz.config.yaml` disagree — worth resolving now rather than discovering it in a deploy. **Treat it as this update's and stop**, without attempting the judgment above. Not because a build cannot have been broken beforehand — it can — but because the judgment is not available here: a pre-update build runs on un-refreshed plugins, and stage 2 deliberately does not roll `quartz-plugins/` back. Rolling it back would reproduce the old-checker mistake exactly.

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
git add .wikicommit .claude .agents skills-lock.json .github quartz-plugins .gitignore \
  .lychee.toml .markdownlint.json package.json quartz.config.yaml \
  prebuild-symlinks.cjs repair-plugin-builds.cjs install-local-plugins.cjs
# (drop any path this repository does not have; `git add` fails on a missing pathspec)
#
# `.agents` looks like a build directory but holds the Skills themselves. When `npx skills
# add` targets two or more agents it writes each Skill's real files to .agents/skills/<name>/
# and makes .claude/skills/<name> a relative symlink into it (Issue #555), so staging .claude
# without .agents commits a tree of links with nothing to point at — every clone gets a broken
# .claude/skills/. skills-lock.json records what was installed and plays no part in resolving
# those links, so it is a separate path rather than a substitute for either. A repository
# installed with install.sh has no skills-lock.json and one placed by copy has no .agents; the
# line above already drops whichever is absent, so neither needs a branch of its own here.

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

**Any pre-existing finding from Step 7 goes in too, under its own heading, kept apart from what this update changed.** Quote the finding verbatim and give its consequence — `DUPLICATE:` means this wiki cannot merge anything until it is fixed; a wrong Type segment means `/wikicommit-status` will keep reporting it; the rest means no standing check watches it at all. This is where such a finding gets read: the Skill does not auto-merge, so a person is already looking at this page.

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

**List the pre-existing findings from Step 7 here as well, each with its consequence**, and say plainly that they were not caused by this update and are not fixed by it. Put a `DUPLICATE:` first if there is one: until it is resolved, `/wikicommit-merge` fails on every batch, so it is the one item that blocks the next thing the user does.

## Notes

- **Nothing here merges.** This Skill opens a PR and stops.
- **Steps 4 and 5 always ask.** Deleting a file and changing a setting are the user's calls; this Skill's job is to make them answerable, not to make them.
- **Type templates are not auto-merged.** `.wikicommit/schema/` is the one tree humans edit directly, so a difference is shown, never applied silently.
- **Page rebuilds are out of scope.** Reported, not run.
- **The Skills themselves are updated outside this Skill** (see the top).
