# WikiCommit

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/wikicommit/wikicommit?style=social)](https://github.com/wikicommit/wikicommit)

A Git-based knowledge management platform. An LLM generates wiki pages from your source documents, and after automated and human review, they're published as a static wiki. It's implemented as a set of SKILL.md files and runs as-is on whatever LLM environment you already subscribe to, such as Claude Code.

**An LLM writes faster than one person can read, so review has to be splittable.** WikiCommit makes a single page the unit of review: one page is one tracking Issue, closed on its own. A reviewer reads that page and nothing else — not the rest of the knowledge base — and never has to wait on anyone else's review. That is what keeps a growing wiki from piling up behind one reader.

> **Status**: Actively being validated through real-world use in pilot repositories; breaking changes may occur.

## What You Can Do

- **Multi-person, asynchronous review**: Pages are auto-merged and published once they pass the quality checks, so review never blocks publishing; each reviewer finishes by closing their page's Issue.
- **Automated from source discovery to page generation**: Automatically discovers un-ingested related sources from local folders and the web. Register a PDF, URL, or file in your repository, and it generates wiki pages.
- **GitOps**: Every change is recorded as a commit and PR. Auditing, rollback, and backup are all handled by `git log` alone.
- **Q&A over the wiki (RAG)**: Answers questions using wiki pages as the starting point, and can trace back to the primary sources to cite them when needed.
- **Multilingual support**: End-to-end support for translation generation, automatic detection of stale translations, and WikiLink language fallback.
- **Automatic publishing to GitHub Pages**: A merge to `main` triggers a build and deploy as a static site. Local preview before publishing is also available.
- **Health checks**: Detects orphan pages, expired pages, broken links, stale translations, and more.

**Use cases**: Well suited for internal technical documentation, product knowledge bases, research notes, community wikis, and other situations where you want to continuously generate and maintain a structured wiki from scattered sources (PDFs, URLs, files in an existing repository).

## Examples

Wikis that are actually running in production:

- **[decameron-wiki](https://wikicommit.github.io/decameron-wiki/)** — A wiki about Giovanni Boccaccio's *The Decameron*, written in Italian and translated into English and Japanese.

## Table of Contents

- [WikiCommit](#wikicommit)
  - [What You Can Do](#what-you-can-do)
  - [Examples](#examples)
  - [Table of Contents](#table-of-contents)
  - [Basic Flow](#basic-flow)
    - [Step 1: Register a source + generate wiki pages](#step-1-register-a-source--generate-wiki-pages)
    - [Step 2: Quality checks, PR creation, merge](#step-2-quality-checks-pr-creation-merge)
    - [Step 3: Post-merge review](#step-3-post-merge-review)
  - [Tech Stack](#tech-stack)
  - [Requirements](#requirements)
    - [Context window](#context-window)
  - [Installation](#installation)
  - [Changelog](#changelog)
  - [Skills List](#skills-list)
  - [Design Docs](#design-docs)
  - [Contributing](#contributing)
  - [License](#license)

## Basic Flow

### Step 1: Register a source + generate wiki pages

**(Optional) If you haven't decided which sources to ingest yet**: Running `/wikicommit-collect` discovers and lists candidate related sources — not yet ingested — from local folders and the web, based on the `theme` in `config.yml`. In light of copyright and license risks, only the candidates that a human reviews and selects are registered. Selected sources are then treated the same as `/wikicommit-generate`.

**Which sources to take in** is written in `.wikicommit/source-policy.md`, created by `/wikicommit-init`. It holds the rules in prose (`prefer primary sources`, `no promotional material`) plus a few lists: domains never to fetch, sources already turned down, and domains to read but never register.

**Whether a relevant subject may be written about at all** is a separate question, and lives in `.wikicommit/entity-policy.md` (also created by `/wikicommit-init`). `theme` decides relevance; this file decides permissibility — a living person at the centre of your subject scores highest on relevance and may still be someone you do not want a page about. It ships inert, with one switch (`exclude_living_persons`, off by default) and room for prose covering anything else you want kept out (private individuals, minors, matters under dispute, your own unreleased information). It applies when a page is generated and does not reach back; use `/wikicommit-remove` for a page that already exists.

That last one matters when an encyclopedia covers your subject. A page written from one encyclopedia article and nothing else tends to be a shorter version of that article, without its footnotes — and if the article is share-alike licensed, your page inherits that obligation. Listing the domain under `index_only:`, or passing `--index <url>`, makes `/wikicommit-collect` read the article's **citations** and offer those primary sources instead; the article itself is never registered. Take the structural overview from a primary source, use the encyclopedia to find out what exists, and register an encyclopedia article outright only where no primary source does — which keeps the pages carrying a share-alike obligation few and deliberate.

```
/wikicommit-collect --index https://en.wikipedia.org/wiki/<subject>
```

```
/wikicommit-generate <path|url>
```

- Generates a tracking file in `.wikicommit/source/` (`status: pending`)
- Automatically computes and records a hash
- Runs automatically in order: text extraction → content analysis → page generation → source-consistency review
- On completion → generated files are written to the working directory (no Git operations)

### Step 2: Quality checks, PR creation, merge

```
/wikicommit-merge
```

- Quality checks (frontmatter validation, WikiLink checks, raw HTML detection, external link validation, orphan page detection)
- Branch creation, PR creation, auto-merge (implemented without relying on GitHub's built-in auto-merge feature, so it works even on GitHub Free private repositories)
- Creates review-tracking Issues (`wikicommit-review` label) and generation-failure tracking Issues (`wikicommit-generation-failure` label)

**(Optional) To check how things look locally before or after merging**: `/wikicommit-serve [--build]` starts a local Quartz v5 build and preview server (no need to wait for the GitHub Pages deployment to complete).

### Step 3: Post-merge review

**The machine checks every page; a person reads some of them.** Each page is compared against the documents it was written from when it is generated, and the WikiLinks are validated before the merge — so the reading is not a re-run of either. What it adds is what no automated check reaches: whether a sentence is unfair to a real person or organization, whether the page conflicts with what you already know, and whether it contradicts another page written in a different batch. Reading every page is not the goal; `/wikicommit-status` lists the ones most worth a second look.

Check the review-tracking Issue (`wikicommit-review` label, automatically created for each page with `review_status: pending`). Closing it states two things: that this page's knowledge reached a person, and that nothing struck them as obviously wrong while reading. It is not a guarantee that the content is correct.

- **Nothing stood out** → Just close the Issue to finish. `review-issue-close-sync.yml` detects this, updates `review_status: reviewed`, and auto-merges.
- **Something stood out** → Leave it in a comment and keep the Issue open — the fix is not the reader's to make. `/wikicommit-fix <issue-url>` has the AI propose a fix based on the Issue body and comments; after human confirmation, `/wikicommit-merge` applies the fix, and then the Issue is closed.
- **Page created or edited directly by a human without going through an Issue** → `/wikicommit-review <page>` completes the frontmatter, runs a source-consistency check, and records review completion, then `/wikicommit-merge`.

Merging to `main` triggers a static wiki build via Quartz v5 and automatic deployment to GitHub Pages.

## Tech Stack

| Purpose | Technology |
| --- | --- |
| Static site generation | [Quartz v5](https://quartz.jzhao.xyz/) |
| Structured data | [Schema.org](https://schema.org/) |
| Knowledge representation spec | [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) (Open Knowledge Format) |
| Full-text search | SQLite FTS5 (trigram) |
| Link validation | [lychee](https://github.com/lycheeverse/lychee) |
| Markdown style | markdownlint-cli2 |

## Requirements

- [Claude Code](https://www.npmjs.com/package/@anthropic-ai/claude-code) (latest version recommended)
- Python 3.11+ (for the quality-check scripts)
- [`gh` CLI](https://cli.github.com/) (authenticated; used for PR creation and merging)
- Node.js 20+ (for `markdownlint-cli2`)
- [lychee](https://github.com/lycheeverse/lychee) (for external link validation; if not installed, `/wikicommit-init` makes a best-effort attempt to auto-install it)

> Because the Skills are a set of SKILL.md files compliant with the [agentskills.io](https://agentskills.io) standard, they should in principle work with other compatible coding agents such as Codex, but Claude Code is currently the only environment we've verified.

### Context window

WikiCommit does not provide LLM inference — you bring your own Claude Code, GitHub Copilot or API contract. That contract has a context requirement, and `/wikicommit-generate` is the command that sets it: it loads a fixed overhead before it reads a single source, then adds the extracted text of each source on top.

```text
context needed  ≈  51K (fixed)  +  ~15K x (sources processed in one run)

  the fixed part:
    wikicommit-generate/SKILL.md, loaded in full        ~47K
    the Schema.org type names (--list-type-names)       ~3.4K
```

| Context window | Sources per run |
|---|---|
| 200K | up to 5 (the guard's own limit) |
| 1M | up to 5 (the same limit) |

`/wikicommit-generate` already asks before processing more than 5 sources in one run, so both rows are that existing guard rather than a new one. The fixed part used to be ~84K, because the full Schema.org type list — every one of the 933 types *with its description* — was loaded on every run; it now loads the names alone and reads the descriptions of only the handful of types actually being considered. That put a 200K window below the guard's own limit; it no longer does.

**The 15K per source is an estimate, and you can measure your own.** `/wikicommit-generate` writes `extracted_tokens` into every source management file under `.wikicommit/source/`, so after one run `grep extracted_tokens .wikicommit/source/**/*.md` gives you the real figure for the kind of source you actually feed it. 15K is what a Japanese Wikipedia article came to; a short blog post is far less, a PDF report far more.

**Where 200K comes from.** In Claude Code, Opus 5 / Opus 4.8 / Opus 4.6 / Sonnet 4.6 default to a 200K window; Sonnet 5 and Fable 5 / 5.1 are natively 1M. Opus reaches 1M with the `[1m]` suffix (`/model opus[1m]`) or an environment variable, and whether that is available depends on your plan — Max, Team and Enterprise get it automatically, Pro needs usage credits, and metered API access can use it. These are the figures as of 2026-09; see [Claude Code's model configuration docs](https://code.claude.com/docs/en/model-config) for the current ones.

**What happens if you exceed it.** Claude Code compacts the conversation rather than failing, and re-attaches only the **first 5,000 tokens** of each skill afterwards — roughly the first 110 lines of `wikicommit-generate/SKILL.md`, which is Step 0 and nothing else. Passes 1 through 4 are outside it. The run continues without them and produces output that looks normal, so treat the table above as a real limit rather than a suggestion.

`/wikicommit-collect` and `/wikicommit-init` also load the type names, but neither accumulates per-source text the way generate does, so neither approaches the same total.

## Installation

```bash
# Method 1: npx skills add (recommended; compliant with the agentskills.io standard; requires Node.js)
# Running it bare opens an interactive picker; it does not install everything silently.
# --copy is recommended -- see the note below.
npx skills add wikicommit/wikicommit --copy

# To install only a specific Skill
npx skills add wikicommit/wikicommit --skill wikicommit-generate --copy

# To install multiple specific Skills at once (repeat --skill)
npx skills add wikicommit/wikicommit --skill wikicommit-generate --skill wikicommit-merge --copy

# To install every Skill without prompts (when in doubt, this is a safe choice)
# Note: do not combine bare --all with --copy. --all is shorthand for
# --skill '*' --agent '*' -y, so with --copy it writes a full copy of every Skill
# into all ~50 supported agent directories; pin the agent instead.
npx skills add wikicommit/wikicommit --skill '*' --agent claude-code -y --copy

# Method 2: install.sh (simpler, no Node.js required; clone wikicommit anywhere,
# then run it from the root of your target wiki repository)
git clone --depth 1 https://github.com/wikicommit/wikicommit.git /tmp/wikicommit
cd /path/to/your-wiki-repo
bash /tmp/wikicommit/install.sh
```

> **Why `--copy`?** Whenever you install to two or more agents at once, `npx skills add` writes the real
> files to `.agents/skills/<name>/` and makes each agent's entry — including `.claude/skills/<name>` — a
> relative symlink pointing at them. That causes two problems for WikiCommit: (1) the symlinks do not
> survive being carried across a host → container filesystem boundary (observed with a devcontainer built
> after installing on the host — the Skills were simply not visible inside the container), and (2)
> WikiCommit expects `.claude/skills/` to be committed to your wiki repository, and a committed symlink
> breaks on clone unless you also commit `.agents/skills/`. `--copy` gives you real files under
> `.claude/skills/`, matching what Method 2 does. (If you pick Claude Code alone in the picker the CLI
> already copies, so `--copy` simply makes that outcome explicit — keep it either way.)
>
> **Devcontainers and GitHub Codespaces**: install from *inside* the container, not on the host before
> building it. Doing so removes the boundary the symlinks cannot cross, and is worth doing even with
> `--copy` since the CLI's default placement may change.

After installation, run this in the repository where you want to initialize the wiki:

```
/wikicommit-init
```

## Changelog

[CHANGELOG.md](CHANGELOG.md) records what changed in each version of WikiCommit itself — the Skills and the template tree they expand. The distribution repository carries no development history, so this file is the only way to learn what changed since the version you last installed, and it is what `/wikicommit-update` reads when it syncs a repository with a newer release.

## Skills List

| # | Category | Command | Description |
| --- | --- | --- | --- |
| 1 | Initialization | `/wikicommit-init` | Initialize a wiki in a repository |
| 2 | Generate/Register | `/wikicommit-generate <path\|url>` | Register a source + generate wiki pages |
| 3 | Generate/Register | `/wikicommit-collect` | Discover candidate related sources (requires human approval) |
| 4 | Generate/Register | `/wikicommit-synthesize <topic>` | Synthesize a new page from existing wiki pages (writes to `entity/`) |
| 5 | Generate/Register | `/wikicommit-translate <page> [--lang <target>]` \| `/wikicommit-translate` (batch) | Translate a page (local write-out only) |
| 6 | Review/Quality | `/wikicommit-merge` | Quality checks, PR creation, and merge |
| 7 | Review/Quality | `/wikicommit-review <page>` | Validate and review a page |
| 8 | Review/Quality | `/wikicommit-fix <issue-url>` \| `/wikicommit-fix <page-path\|published-url> "<instruction>"` | AI-assisted page fix (from an Issue / page path / published URL) |
| 9 | Review/Quality | `/wikicommit-remove <page>` | Remove a page (creates a PR) |
| 10 | Review/Quality | `/wikicommit-schema-propose` | Detect uncovered types and propose schema files (PR, not auto-merged) |
| 11 | Reference/Search | `/wikicommit-ask <question>` | Ask the wiki a RAG-style question |
| 12 | Reference/Search | `/wikicommit-search <query>` | Keyword search |
| 13 | Reference/Search | `/wikicommit-quiz [--difficulty=easy\|medium\|hard]` | Generate a quiz from wiki content |
| 14 | Operations/Preview | `/wikicommit-status` | Health check (orphans, unreviewed, expired) |
| 15 | Operations/Preview | `/wikicommit-serve [--build]` | Build and preview the wiki locally |
| 16 | Operations/Preview | `/wikicommit-update` | Bring the repository in step with the installed distribution (PR, not auto-merged) |

---

## Design Docs

`docs/` holds the design record this project was built from. It is written in Japanese, and it is a record kept while building rather than a polished specification — its purpose is to preserve *why* something works the way it does, and what was considered and rejected. Start with [docs/DesignDoc-architecture.md](docs/DesignDoc-architecture.md) — the design principles, the overall architecture, and the major decisions. After that, read by the unit of a single decision — for example `docs/DesignDoc-data.md` §4.8 on how review records are stored — rather than front to back; the set is roughly 1 MB in total. [docs/README.md](docs/README.md) explains how to read it, including what the `Issue #NNN` references mean and which referenced paths are not part of this repository.

## Contributing

[docs/README.md](docs/README.md) explains how to read the design record — what is published here, what the `Issue #NNN` references mean, and which referenced paths are not part of this repository. [tests/README.md](tests/README.md) covers the test suite: how to run it, why much of it is written in Japanese, and which tests are skipped outside the development repository.

## License

[Apache License 2.0](LICENSE)
