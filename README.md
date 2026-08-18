# WikiCommit

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/wikicommit/wikicommit/actions/workflows/test.yml/badge.svg)](https://github.com/wikicommit/wikicommit/actions/workflows/test.yml)
[![GitHub Stars](https://img.shields.io/github/stars/wikicommit/wikicommit?style=social)](https://github.com/wikicommit/wikicommit)

A Git-based knowledge management platform. An LLM generates wiki pages from your source documents, and after automated and human review, they're published as a static wiki. It's implemented as a set of SKILL.md files and runs as-is on whatever LLM environment you already subscribe to, such as Claude Code.

> **Status**: Actively being validated through real-world use in pilot repositories; breaking changes may occur.

## What You Can Do

- **Multi-person, asynchronous review**: After passing quality checks, pages are auto-merged and published, and review is split up per page — each reviewer just closes their Issue to finish.
- **Automated from source discovery to page generation**: Automatically discovers un-ingested related sources from local folders and the web. Register a PDF, URL, or file in your repository, and it generates wiki pages.
- **GitOps**: Every change is recorded as a commit and PR. Auditing, rollback, and backup are all handled by `git log` alone.
- **Q&A over the wiki (RAG)**: Answers questions using wiki pages as the starting point, and can trace back to the primary sources to cite them when needed.
- **Multilingual support**: End-to-end support for translation generation, automatic detection of stale translations, and WikiLink language fallback.
- **Automatic publishing to GitHub Pages**: A merge to `main` triggers a build and deploy as a static site. Local preview before publishing is also available.
- **Health checks**: Detects orphan pages, expired pages, broken links, stale translations, and more.

**Use cases**: Well suited for internal technical documentation, product knowledge bases, research notes, community wikis, and other situations where you want to continuously generate and maintain a structured wiki from scattered sources (PDFs, URLs, files in an existing repository).

## Table of Contents

- [WikiCommit](#wikicommit)
  - [What You Can Do](#what-you-can-do)
  - [Table of Contents](#table-of-contents)
  - [Basic Flow](#basic-flow)
    - [Step 1: Register a source + generate wiki pages](#step-1-register-a-source--generate-wiki-pages)
    - [Step 2: Quality checks, PR creation, merge](#step-2-quality-checks-pr-creation-merge)
    - [Step 3: Post-merge review](#step-3-post-merge-review)
  - [Tech Stack](#tech-stack)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [Skills List](#skills-list)
  - [Contributing](#contributing)
  - [License](#license)

## Basic Flow

### Step 1: Register a source + generate wiki pages

**(Optional) If you haven't decided which sources to ingest yet**: Running `/wikicommit-collect` discovers and lists candidate related sources — not yet ingested — from local folders and the web, based on the `theme` in `config.yml`. In light of copyright and license risks, only the candidates that a human reviews and selects are registered. Selected sources are then treated the same as `/wikicommit-generate`.

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

Check the review-tracking Issue (`wikicommit-review` label, automatically created for each page with `review_status: pending`):

- Does the page content align with the source?
- Are the WikiLinks (`[[Type/slug]]`) correct?

- **No problems** → Just close the Issue to finish. `review-issue-close-sync.yml` detects this, updates `review_status: reviewed`, and auto-merges.
- **Needs fixing** → First, a human leaves the points to address as comments on the Issue. `/wikicommit-fix <issue-url>` has the AI propose a fix based on the Issue body and comments; after human confirmation, `/wikicommit-merge` applies the fix, and then the Issue is closed.
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

## Installation

```bash
# Method 1: npx skills add (recommended; compliant with the agentskills.io standard; requires Node.js)
# Running it bare opens an interactive picker; it does not install everything silently.
npx skills add wikicommit/wikicommit

# To install only a specific Skill
npx skills add wikicommit/wikicommit --skill wikicommit-generate

# To install multiple specific Skills at once (repeat --skill)
npx skills add wikicommit/wikicommit --skill wikicommit-generate --skill wikicommit-merge

# To install every Skill without prompts (when in doubt, this is a safe choice)
npx skills add wikicommit/wikicommit --all

# Method 2: install.sh (simpler, no Node.js required; clone wikicommit anywhere,
# then run it from the root of your target wiki repository)
git clone --depth 1 https://github.com/wikicommit/wikicommit.git /tmp/wikicommit
cd /path/to/your-wiki-repo
bash /tmp/wikicommit/install.sh
```

After installation, run this in the repository where you want to initialize the wiki:

```
/wikicommit-init
```

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

---

## License

[Apache License 2.0](LICENSE)
