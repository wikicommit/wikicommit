# Updating the Quartz submodule

`quartz/` is someone else's repository — Quartz itself, pulled in with `git submodule add`. Your
repository does not hold a copy of it; it holds one line saying *which commit of it to use*. This
guide is about moving that line forward, which no Skill does for you: `/wikicommit-update` syncs
WikiCommit's own files and never touches the submodule.

**This one applies only to a wiki published with Quartz** (`/wikicommit-init --quartz`). The
guides tree ships with every initialization, so if your repository has no `quartz/` directory
there is nothing here to do.

> **These guides are written in English only, and that is a deliberate exception.** Everything
> else WikiCommit shows a human follows the reader: a review-tracking Issue is rendered in the
> wiki's `primary_lang`, while a script's diagnostics stay in English because their reader is the
> operator or an agent. A guide's reader is a human operator, so that rule would put it in
> `primary_lang` — but a guide is a *distributed file*, not text an agent renders on the spot, so
> honouring it would mean carrying one template per language. `.wikicommit/review-rules.md` is
> already distributed in English for the same practical reason. Written here so the next person to
> touch this does not reopen the question as a bug.

> **This directory is WikiCommit's, not yours.** Every later `/wikicommit-init` and
> `/wikicommit-update` overwrites what is here, so an edit you make to a guide is lost on the next
> refresh, and a file of your own added alongside them is reported as an orphan by
> `/wikicommit-status` and offered for deletion by `/wikicommit-update`. Keep your own notes
> somewhere else in the repository.

## You do not have to do this

Updating is optional and there is no hurry. The published site is built by
`.github/workflows/deploy.yml`, which checks out the submodule at the commit your repository
recorded — not whatever is in your local `quartz/` — so the site keeps building on the same Quartz
until you deliberately move it. Update when you want something a newer Quartz has, not because
the submodule is "behind".

## Why `quartz/` looks modified

WikiCommit's own build writes into `quartz/`. None of this is your editing, and deleting it does
not help — the next build puts it back:

| What appears | What writes it | What git sees |
|---|---|---|
| `quartz/package-lock.json` | the root `package.json`'s `postinstall`, which runs `npm install` inside `quartz/` | **a change to a tracked file** |
| `quartz/content`, `quartz/quartz.config.yaml` | `prebuild-symlinks.cjs` | untracked |
| `quartz/quartz.lock.json`, `quartz/.quartz/plugins/*` | `npm run install-plugins` | untracked |

None of it reaches your repository's history: `git add quartz` records only the submodule's
commit pointer. The untracked files also never get in the way. **The one tracked change does** —
`git pull` inside `quartz/` stops with:

```text
error: Your local changes to the following files would be overwritten by merge:
        package-lock.json
```

That is the only thing the first step below is for.

## Steps

Note the commit you are on first, so you can come back to it:

```bash
git -C quartz rev-parse HEAD
```

Then:

```bash
git -C quartz checkout -- package-lock.json   # drop the build's side effect
git -C quartz pull origin v5                   # the branch the Quartz v5 line is published on
(cd quartz && npm install)                     # a newer Quartz may need different dependencies
npm run build                                  # the real test — see below
git add quartz                                 # move your repository's pointer
git commit -m "chore: bump quartz submodule to $(git -C quartz rev-parse --short HEAD)"
```

**Install inside `quartz/`, not with a root `npm install`.** The root `postinstall` begins with
`git submodule update --init --recursive`, which checks the submodule out at the commit your
repository has recorded — before `git add quartz`, that is the *old* commit, and it silently
undoes the pull.

## Do not skip the build

`npm run build` is the step that tells you whether the update is safe, and it is the one worth
the most. Quartz releases can change what a plugin must look like: `quartz.config.yaml` pulls in
many `github:quartz-community/*` plugins as well as WikiCommit's own `quartz-plugins/*`, and a
breaking release (one pilot saw `feat!: adopt 1.0.0 ecosystem` among seven new commits) can leave
some of them unable to load. The build prints a warning for a plugin that fails to install and
carries on, so read its output rather than only its exit status, and preview the result
(`/wikicommit-serve`) before you commit.

## Going back

If the build fails or the preview looks wrong, return to the commit you noted:

```bash
git -C quartz checkout -- package-lock.json   # the install above may have changed it again
git -C quartz checkout <the SHA you noted>
(cd quartz && npm install)
```

Nothing needs undoing in your repository if you had not yet run `git add quartz`. If you had
already committed the new pointer, check out the old SHA as above, then `git add quartz` and
commit again.
