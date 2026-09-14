# Enabling comments (giscus)

Comments are off by default. Turning them on is a one-time setup you do by hand — no Skill does
it for you, and re-running `/wikicommit-init` does not do it either.

**This one applies only to a wiki published with Quartz** (`/wikicommit-init --quartz`). The
guides tree ships with every initialization, so if your repository has no `quartz.config.yaml`
there is nothing here to do yet.

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

## What it is for

It gives a reader somewhere to put a thought they are not yet sure enough about to open an Issue
over. Three layers, and they do not overlap:

| Layer | Where | What it takes |
|---|---|---|
| **Noticing** | comments (this guide) | nothing — anyone, any number of times |
| **Reporting** | the banner's report link, which opens an Issue | confidence that something should be fixed |
| **Declaring** | closing a review-tracking Issue | write access to the repository |

The gap the first layer fills is real rather than decorative: a contradiction between two pages
generated in *different* batches is out of reach of every automated check by design, so the only
thing in the system holding both pages at once is a person who read one last week and the other
today. That thought arrives as "these don't quite agree" — which is not an Issue.

## Before you start

Three prerequisites, all of them giscus's own. **Check all three before touching the config**: a
missed one fails at read time, not at build time, so the site builds fine and the comment box
simply does not work.

1. **The repository is public.** Otherwise visitors cannot see the discussion at all. A wiki
   published on GitHub Pages under a free plan already satisfies this.
2. **The giscus GitHub App is installed on it** — <https://github.com/apps/giscus>. Without it,
   visitors can see comments but cannot post or react. **This is the one step that fails
   silently**, and the one you cannot check from the command line, so confirm it in the browser.
3. **Discussions is turned on** (Settings → General → Features → Discussions), with a category to
   hold the threads. Use an **Announcements**-type category — giscus recommends it because only
   maintainers and giscus itself can then open new discussions there.

## Collect the four values

```bash
gh api "repos/<owner>/<repo>" --jq .node_id          # repoId

gh api graphql -f query='
  query { repository(owner: "<owner>", name: "<repo>") {
    discussionCategories(first: 20) { nodes { id name } } } }'   # categoryId
```

The second call lists every category with its id; take the one you created in step 3 above.

## Edit `quartz.config.yaml`

Find the `github:quartz-community/comments` entry, flip `enabled` to `true`, and fill in the
options:

```yaml
  - source: github:quartz-community/comments
    enabled: true
    options:
      provider: giscus
      options:
        repo: <owner>/<repo>
        repoId: <node_id from above>
        category: <the category's name>
        categoryId: <that category's id from above>
        lang: <your primary_lang>
```

`lang` is one static value for the whole site — it does **not** follow a page's own `lang`
frontmatter — so on a multilingual wiki it will not match every reader. Your `primary_lang` is the
sensible choice.

## Check the two exclude lists

Build-generated navigation pages are kept out of the comment box two different ways, and a wiki
needs both:

- The pages **WikiCommit** writes (Type indexes, the view-tree index, the root index,
  `content/sources/`, `content/overview/`) carry `comments: false` in their own frontmatter, and
  the plugin skips them.
- The pages **Quartz** synthesises have no `.md` behind them to stamp. No `index.md` is written at
  `content/<lang>/`, so each language top (`/ja/` and the like) is a folder page Quartz builds
  itself, and every `/tags/<tag>` page is the same. These are excluded by listing `comments` in
  `layout.byPageType.folder.exclude` and `layout.byPageType.tag.exclude`, next to
  `wikicommit-banner`, which is there for exactly this reason.

Confirm both entries are present before enabling. A `quartz.config.yaml` written before this
plugin existed predates the `comments` entry in those two lists.

## If your wiki predates this plugin entry

`quartz.config.yaml` is never overwritten once it exists — it holds your own `pageTitle`,
`baseUrl` and links — so the `comments` plugin entry reaches a repository only on its *first*
init. It is not commented out there: it is a live entry carrying `enabled: false`, which is what
the section above has you flip. On an older wiki, copy that entry by hand out of the template
that ships with the `wikicommit-init` Skill:

```bash
sed -n '/quartz-community\/comments/,/priority:/p' \
  .claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml
```

Add the `comments` entry to the two exclude lists above by hand as well.

## Two costs, both accepted

- It adds a dependency on a `github:quartz-community/*` plugin.
- An empty comment box looks empty on every page, in a way a report link does not.
