---
name: wikicommit-collect
description: Discover candidate sources (local files and web pages) related to the configured wiki theme, pending human approval before registration
disable-model-invocation: true
---

# wikicommit-collect

A skill that, based on `.wikicommit/config.yml`'s `theme`, searches for not-yet-ingested files in the repository and related sources on the web, and presents them as candidates. It does not implement a dedicated crawler — it's built entirely from existing file scanning, Claude Code's native web search, and internal calls to `wikicommit-generate`. This skill has no dedicated scripts of its own.

## Usage

```
/wikicommit-collect [optional guidance]
/wikicommit-collect --index <url> [--index <url>]... [optional guidance]
```

The guidance argument is free text, same as `/wikicommit-ask <question>` and other skills that take a free-text argument. It expresses research direction or preferred/excluded sources, e.g.:

```
/wikicommit-collect Prefer academic sources; avoid personal blogs
/wikicommit-collect --index https://ja.wikipedia.org/wiki/さいたま市
```

`--index <url>` names a page to **mine for references rather than register** (step 5.5, Issue #570): its citation and external-link sections are read for primary-source URLs, and the page itself never becomes a candidate. `.wikicommit/source-policy.md`'s `index_only:` does the same thing standing, by domain.

With no guidance, the run begins by surveying the wiki — what it already holds, what it links to but has not written, where it is thin — and offering a few focuses to search on. One is chosen before anything is searched for; `theme` alone is too coarse to aim a single run.

## Processing Flow

### Step 1: Check `theme`

Read `.wikicommit/config.yml` and get the `theme` field.

- If the `theme` field is absent, or its value is an empty string:

  ```
  theme is not set, so candidates cannot be narrowed down. Set theme in .wikicommit/config.yml and re-run.
  ```

  Display this and stop (do not search for candidates).

  > `/wikicommit-init` now prompts for `theme` interactively on first run. For a repository that was already initialized before this field existed (or where `theme` was left blank), re-run `/wikicommit-init` and answer the theme prompt with non-blank text — as of Issue #374, it now updates just the `theme:` line of the existing `.wikicommit/config.yml` via a dedicated `--update-theme` flag on `init.py`, instead of silently discarding the answer under `--no-overwrite` as it previously did. Editing `theme: "<free text>"` in `.wikicommit/config.yml` directly still works too, if preferred.

- If `theme` is set, proceed to step 2, using its content as the relevance criterion for steps 4–6.

### Step 2: Hold the Guidance Argument

First split the argument. Every `--index <url>` occurrence is **not guidance**: remove each flag and its URL from the string and hold the URLs separately as index pages for step 5.5. Leaving them in would make step 5 read `--index https://ja.wikipedia.org/...` as "search mainly on that site" and bias the queries toward the very page the flag exists to keep out of the candidate list (Issue #570).

If anything remains after that split, hold it as "research guidance" for the rest of this run — it narrows or steers the search on top of `theme`, it does not replace `theme`. It is used in steps 4 and 5.

If no argument was given, or nothing remains after removing the `--index` flags, there is no research guidance yet — the survey step below offers one, and whatever is chosen there is held here for the rest of the run. If nothing is chosen the run stops, so the later steps never search on `theme` alone.

### Step 2.5: Read the Source Policy (Issue #564)

Read `.wikicommit/source-policy.md`. It is this wiki's standing answer to "which sources do we take in", where `theme` answers "which entities get pages" — two questions that used to share one field because there was nowhere else to put the first. If the file is absent, or its body is empty or still the shipped comment, there is no prose policy; carry on with `theme` alone.

Hold three things for the rest of this run:

- the **body prose** — a standing filter on candidates, applied in steps 4, 5 and 6
- **`rejected:`** — sources already considered and turned down. Drop any candidate whose URL matches an entry, the same way step 3's already-registered list is applied. This is the whole point of the list: without it, free exploration has no memory of a prior decision and proposes the same source again every run
- **`exclude_domains:`** — nothing to hold; step 5 already unions it into its `check-domain` call
- **`index_only:`** — domains to read but never register (Issue #570). A candidate on one of these domains is not offered for registration; it goes to step 5.5 to be mined for the primary sources it cites. Any `--index <url>` held in step 2 is the same idea for one run, but it names a *page*, not a domain: it goes straight to step 5.5 as an index page and does not turn its whole host into an `index_only:` domain

**Precedence with step 2's guidance argument**: the policy is the standing rule, the argument steers one run within it. Where they simply differ, both apply — the argument narrows, it does not widen. Where the argument asks for something the policy rules out, **say so and ask before treating the argument as an exception for this run**; if the user confirms, it applies to this run only and nothing is written to the policy file. That direction matters: a guidance argument is typed in a moment, the policy was written deliberately, so the argument does not get to silently overrule it.

### Step 3: Inventory Already-Registered Sources

Read the frontmatter of every management file (`.md`) under `.wikicommit/source/`, and collect:

- `source.type: path` → `source.path`
- `source.type: url` / `source.type: wikicommit` → `source.url`
- `extracted_tokens`, if present — used as a size reference in step 6

Use the `source.path`/`source.url` list to exclude duplicates in steps 4 and 5.

### Step 3.5: Survey the Wiki and Choose a Focus (only when no research guidance was held)

Skip this step entirely when step 2 held research guidance. Guidance means the person already has a focus, and a survey would only talk them out of it.

**Run it when the argument was empty, and when only `--index <url>` was given.** An index page names where to start looking, not what to look for; the two are compatible, so a run with `--index` and no guidance still surveys.

With no guidance, every later step searches on `theme` alone. `theme` is this wiki's whole subject scope — it is the right criterion for "does this belong here", and far too coarse to aim a single run. So an argument-less run searches at the same width every time and keeps surfacing candidates from the areas that are already thick. The place to put a focus already exists (the guidance step 2 holds); what was missing was any way to see the wiki's current shape well enough to write one.

**This step's output is not deterministic.** The same wiki will suggest different focuses on different runs. That is expected: this is idea support, not a quality gate, and nothing is written or fetched until a person has chosen.

#### 3.5.1 Build the view

Three read-only scripts, run as-is; nothing new is computed here.

```bash
python .wikicommit/scripts/build_survey_view.py
python .wikicommit/scripts/check_wanted_pages.py
python .wikicommit/scripts/check_orphans.py
```

Read all three outputs into context. Each answers a different question:

- `build_survey_view.py` — **what is here**. Each page reduced to title, type, tags, `properties.description`, `##` headings and outgoing links, plus the `TYPE:` / `HUB:` / `TAG:` rankings. A type with one or two pages is an area barely touched.
- `check_wanted_pages.py` — the **`WANTED:`** lines are concepts the wiki links to but has no page for. This is the wiki saying, in its own words, what it wants written; it is the strongest signal here. Ignore `TYPE_MISMATCH:` lines — the page exists under another Type, so nothing is missing and the fix is a one-word link edit, not a source.
- `check_orphans.py` — `ORPHAN:` lines carry the sources each orphan came from, so a source that produced exactly one page, linked from nowhere, stands out as a thin patch. Ignore `DUPLICATE:` lines here for the same reason as `TYPE_MISMATCH:` — both pages exist, so nothing is missing and no source would fix it. **This script exits 1 whenever it reported a duplicate, and that is not a failure of this step**: read its output and carry on. (It is the one script here that can exit non-zero; `wikicommit-merge` treats that exit as blocking because a duplicate blocks a merge, which has nothing to do with surveying.) If a script is genuinely missing or errors out, say which one and continue with the views you did get — a partial view still beats searching on `theme` alone.

If `build_survey_view.py` prints a `TRUNCATED:` line, say so plainly — the view is incomplete and covers only the most-linked part of the wiki — and offer to re-run with a higher `--max-pages`.

Do not run `/wikicommit-status` to get these. It is a health check, and one of the scripts it runs rewrites source management files; there is no reason to cause a write before searching for anything.

#### 3.5.2 Propose focuses

From that view, propose **at most 5**, matching the count at which this Skill and its siblings stop and ask. Fewer is fine; a wiki with little structure in it should get few. For each, give:

- a short phrase, in `primary_lang`, in the form the later search steps can take as their direction
- one line on why it is worth searching for, naming the specific page, wanted concept, or orphan that suggested it

Propose only what the view actually supports. A focus nothing in the wiki points at sends the searches after something this wiki has shown no sign of wanting.

#### 3.5.3 Let the person choose

Present the numbered list and ask which to search on. They can type their own phrase instead, in which case use it verbatim.

Whatever is chosen becomes this run's research guidance, held exactly as step 2 would have held an argument: it **narrows the search on top of `theme`, it does not replace `theme`**, and the later search steps use it the same way.

If the answer is not a choice — no answer arrives, or nothing appeals — stop here without searching. Do not pick one: the point of this step is that the person, not the model, decides where the run is aimed. If this Skill was invoked with nobody there to answer, stopping is the correct outcome; re-run it with explicit guidance to skip the survey.

Focuses that were passed over are not recorded anywhere. The view is rebuilt from the wiki every run, so anything the wiki still points at can be proposed again. Note that the `rejected:` list this Skill writes later holds **source URLs a person turned down**, which is a different thing — do not put a passed-over focus there.

### Step 4: Search Local Candidates

Scan files in the repository, excluding:

- `.git/`, `.wikicommit/`, `.claude/`, `node_modules/`, build output directories (`dist/`, `build/`, etc.)
- Files matching a `source.path` already collected in step 3

Restrict target extensions to those `wikicommit-generate` can handle (the "Prerequisite Skills (Text Extraction)" table in `.claude/skills/wikicommit-generate/SKILL.md`): `.md` / `.txt` / `.pdf` / `.docx` / `.pptx` / `.xlsx` / `.epub` / image files (`.jpg` / `.jpeg` / `.png` / `.gif` / `.tiff`, etc.). Extensions outside this set (which fall to the `markitdown` fallback) are not included in this step's target, since they would make the scope of the in-repository scan unbounded.

For the remaining candidates, have the LLM judge relevance to `theme` from the filename and parent directory name. Do not read the full content of files (to avoid the cost blowing up when there are many files). If needed, limit yourself to skimming the first few lines. Exclude files clearly unrelated to `theme` (license files, dependency lock files, CI configuration, etc.) from the candidates. If research guidance was held in step 2, apply it here too where it plausibly applies to local files (e.g. "prefer academic sources" can inform which local documents look more relevant) — but expect limited effect, since guidance aimed at sources like Wikipedia has no local-file equivalent. Apply the source-policy prose from step 2.5 the same way — it is generally about the character of a source rather than where it lives, so most of it carries over to local files unchanged.

### Step 5: Search Web Candidates

Use Claude Code's native web search tool to search for sources related to `theme` — as the **set** of queries laid out under "Run several queries, not one" below, not as one query. Fold in the source-policy prose from step 2.5 as a filter on which results are kept — a policy saying "prefer primary sources, no personal blogs" excludes matching results here rather than merely ranking them lower, since it is a standing decision about what this wiki takes in. Drop any result whose URL appears in the policy's `rejected:` list, and say nothing about it (as with a duplicate: it was never a viable candidate). If research guidance was held in step 2, fold it into the search too: e.g. guidance like "search mainly on the city's own site" should produce queries that prioritize `site:` the site(s) named, and guidance like "prefer academic sources, avoid personal blogs" should be applied as a filter on which results are kept as candidates, not just as extra query text. **Guidance that names an encyclopedia is ambiguous and must be resolved before acting on it** (Issue #570): "search mainly on Wikipedia" can mean "register Wikipedia articles as sources" or "use Wikipedia to find out what exists here" — two different things with different consequences, the second of which is step 5.5's job. Ask which is meant rather than assuming, unless the domain is already listed under `index_only:`, which answers it. Keep the URL, title, and summary for each search result. Exclude any URL matching a `source.url` already collected in step 3.

#### Run several queries, not one

One query phrased at the abstraction level of `theme` returns the head of the distribution — large outlets, well-known articles — and returns the same head every run. The classes of source a `theme` most often names by hand (independent developer blogs, a vendor's own site, small open-source repositories) sit in the tail, and re-running that one query never reaches them. So issue a **set** of queries, drawn from the six passes below.

`theme` and the source-policy prose are read here for two separate things: the subject to search for, and the **origins named as preferred**. Passes C–F exist because those origins — and the gaps this wiki already knows it has — are things a subject-level query cannot express.

- **A — the theme, at several levels of concreteness.** The broad `theme` query is one query in this pass, not the whole of it. Also build queries out of the concrete terms `theme` contains (a named product, a named practice, a technique) rather than only its overall subject: a term-level query and a subject-level query surface different parts of the distribution. Research guidance from step 2 applies here as it always has.
- **B — `filetype:pdf`.** Append `filetype:pdf` to the theme (and guidance) terms and run it as its own query. General web search ranks news articles and blog posts above primary-source documents (government pamphlets, academic papers, technical specs), which are frequently published as PDF rather than HTML; this pass counters that bias. It supplements the other passes and never replaces them, and it runs unconditionally — not only when guidance mentions documents. Tag each result from this pass as a PDF candidate for step 6. A URL pointing straight at a PDF needs no special handling at registration (`markitdown` converts by content-type), so step 8 is unaffected.
- **C — `site:` over hosts already registered.** Step 3 read every `source.url` in order to deduplicate; take the **hosts** out of that same list and search each with `site:`. A domain this wiki has already taken something from is a publisher it has already judged worth reading, and the next article there will not outrank a large outlet on a general query. This costs no new input — it is step 3's output turned around. Prefer hosts that appear more than once; skip one-off aggregators. **The match is host-exact, not organization-wide**: a registered `code.example.com` does not cause `example.com` to be searched. That is pass D's job, and the reason it is a separate pass rather than a widening of this one.
- **D — `site:` over origins named in `theme` and the source policy.** When `theme` or the source-policy prose names organizations or sites as preferred ("prioritizes ... from practitioners and vendors (e.g. Acme, Example Corp)"), those names are instructions about where to look, and nothing was turning them into queries. Search each named origin with `site:` against its domain where the domain is unambiguous, and with the organization's name as a query term where it is not. Use only origins the prose actually names — do not supply one the wiki never mentioned — and only ones it names **as preferred**. A domain the policy names in order to keep it out is not a target for this pass: one under `exclude_domains:`, one carrying a `rejected:` entry, or an `index_only:` domain. Searching the first two spends budget on results the filters below drop anyway; searching an `index_only:` one is worse, since step 5's routing hands every hit to step 5.5, which fetches and mines each of them — turning a pass meant to find sources into a bulk crawl of the one domain the policy exists to keep out of the candidate list.
- **E — what the wiki is already missing.** `check_wanted_pages.py` computes exactly the concepts this wiki links to but has no page for. Nothing else in this Skill knows what the wiki is short of, so use that list as query terms:

  ```bash
  python .wikicommit/scripts/check_wanted_pages.py
  ```

  If step 3.5 already ran this script, reuse the output it read rather than running it again: nothing between the two points writes to `.wikicommit/entity/`, so a second scan of the whole tree returns the same lines it already has.

  Take the **`WANTED:`** lines only. Skip `TYPE_MISMATCH:` lines — those name a page that already exists under a different Type, so the wiki is not missing anything and the fix is a one-word link edit, not a new source. Turn each `Type/slug` into a term by dropping everything up to and including the **last** `/` — a custom type's key carries two segments, so `custom/Decision/some-slug` leaves `some-slug` — and replacing hyphens with spaces, then pair it with the theme terms so the query stays inside this wiki's subject. When there are more wanted pages than this pass's share of the budget, take the ones with the highest `referenced by N pages` count: the number is already on the line, and a concept several pages reach for is the one the wiki is most short of. If the script is absent, exits non-zero, or prints no `WANTED:` line, skip this pass silently: it is one input among several and must never stop the run.

  **Limitation**: a slug is a language-neutral English identifier, so on a wiki written in another language the derived term may not match how sources phrase it. Use it as-is; translating it back to the wiki's language is not attempted here.
- **F — repository hosts.** Search code-hosting sites (`site:github.com` and equivalents) for the theme's concrete terms, as a pass of its own. This is pass B's argument on a different axis: `filetype:pdf` exists because a *format* ranks systematically below articles, and a small repository ranks systematically below them for an unrelated reason — the size of whoever published it. A wiki whose theme names open-source toolkits will not otherwise see them.

**Query budget**: run **at most 5 queries in any one pass, and at most 20 across the run.** When that ceiling binds, spend at least one query on every pass that has input before spending what is left, and spend that remainder where it buys the most breadth — the 5-per-pass ceiling applies to it too, so it cannot simply be poured back into A. Breadth across passes is the whole point, and a run that spends its budget on variations of the theme query is the single-query behavior this plan replaces. A pass with no input (no registered hosts, no named origins, no wanted pages) simply does not run and costs nothing.

Queries are not the only cost this has to bound. Every surviving web result becomes a numbered row in step 6 and costs two subprocess calls on the way there — `check-domain` below, then the license lookup — so twenty queries' worth of raw results would put hundreds of shell invocations and a list no one can read in front of the user. After the filters below, keep the most relevant results (on the order of twenty) and drop the rest before running the per-candidate lookups. What the extra passes change is **where** candidates come from, not how many reach the human.

**No pass decides anything.** Every result from every pass goes through the same filters below — deduplication against step 3 **and against what an earlier pass already kept**, the source-policy prose and its `rejected:` list, `index_only:` routing, and `check-domain` — before it can become a candidate. The passes overlap by design (a broad theme query and a `site:` query over the same vendor return the same article), so a URL any pass already kept is dropped by every later one: it has to appear once in step 6, not once per pass that found it, or the user picks the same source under two numbers and step 8 registers it twice. Nor is any query history kept: each pass is re-derived from the wiki's current state, so a wiki that grows searches differently next time without a second kind of state to maintain.

**Route `index_only` domains to step 5.5, do not offer them (Issue #570)**: a result whose domain matches the policy's `index_only:` is not dropped and not presented — it is carried to step 5.5 as a page to mine. Nothing on such a domain ever becomes a registration candidate.

**Known JS-shell domain exclusion (Issue #425)**: also exclude any result whose URL fails the check below — these are domains a prior `wikicommit-generate` run has confirmed to sometimes return an empty content shell (real content only renders after JS execution) when fetched with `markitdown`, so presenting them as candidates here just reintroduces a source someone already deliberately excluded, via free-exploration guidance that has no memory of that prior exclusion (this is exactly what happened with the x.com source in the `ai-driven-dev-wiki` pilot that motivated this Issue):

```bash
python .wikicommit/scripts/check_extraction_quality.py check-domain "$(cat <<'EOF'
<candidate URL>
EOF
)"
```

The URL goes through a quote-delimited heredoc for the same reason step 6's lookup does — a candidate URL is unvalidated free text, and an unquoted one containing `&` is split by the shell. Here the consequence is worse than a wrong answer: the fragment before the `&` runs in the background, so the check returns exit 0 (read as `OK:`) while what followed the `&` is executed as a command, and a domain this wiki has decided against is kept as a candidate.

The same command also enforces the policy's `exclude_domains:` — `check_extraction_quality.py` unions that list with its own built-in one (Issue #564), so a domain this wiki has decided against is dropped here without this step needing to read the policy file itself. `BLOCKED:` (exit 1) → drop the candidate silently (no need to mention it in step 6's presentation — it was never a viable candidate in the first place, same as a duplicate already excluded above). `OK:` (exit 0) → keep it as a candidate.

### Step 5.5: Mine Index Pages for Primary Sources (Issue #570)

Skip this step when nothing was collected for it — no `--index` argument, and no result on an `index_only:` domain.

For each index page, fetch it the same way Pass 1 does — it carries the User-Agent Wikimedia hosts require, and this reads the page without registering anything. `--fetch-url` requires `--output` and writes exactly what `markitdown` produced there, so give it a scratch path under the gitignored cache (a path of your own, not one of Pass 1's `ingest-fetch/` scratch paths — those are derived from a management file, and an index page has none). Quote the URL: it is free text from the command line or a search result, and an unquoted `&` would be read by the shell.

```bash
python .claude/skills/wikicommit-generate/scripts/add_source.py --fetch-url "<index URL>" \
  --output ".wikicommit/.cache/collect-index/<host>-<slug>.md"
```

Read **only its citation, references, and external-links sections**, and take the URLs they hold. Each becomes an ordinary web candidate from step 5 onward: deduplicated against step 3's registered sources, filtered by the source policy, checked by `check-domain`, and shown in step 6 tagged with which index page cited it. **Mine one hop only** — a URL taken from an index page is never itself mined, even when it lands on an `index_only:` domain (a cited encyclopedia article is dropped there like any other candidate on that domain). Without that stop, step 5's routing rule would send each mined URL back into this step and the fetching would not terminate.

**The index page itself never becomes a candidate.** That line is the whole point of this step, and it is worth knowing why it sits exactly there rather than anywhere else:

- Reading an index page to decide **what to write** would let its wording and structure into the generated text, while the page is not in `sources:` — so Pass 4 has nothing to check the resemblance against and no attribution is emitted. A wiki that does this is in a *worse* position than one that registers the article outright and carries its license.
- Reading an index page to decide **which URLs to go and get** does not. A list of references is an enumeration of facts, and a page written from a primary source you fetched yourself owes that primary source nothing beyond its own terms.

So: **read the reference list, never the prose**. Do not summarize the article, do not carry its section headings into the candidate descriptions, and do not let its framing decide which of the cited sources look interesting — relevance is judged against `theme` and the source policy, exactly as for a search result.

Say what happened, and say it in terms of what was and was not taken in:

```
Mined https://ja.wikipedia.org/wiki/さいたま市 for cited sources (the article itself was not
registered as a source):
  12 URLs found, 3 already registered, 2 dropped by the source policy → 7 new candidates below
```

If an index page yields nothing (no reference section, or every URL already registered or filtered out), say so plainly rather than falling back to offering the page itself.

### Step 6: Present Candidates

Merge the local and web candidates and present them as a numbered list, ordered by judged relevance (highest first). For each candidate, mark it with `⚠️` and note any copyright/licensing concern (e.g. amounts to a full reprint of a commercial news article, scraping prohibited by terms of service, etc.). If a candidate closely resembles an already-registered source found in Step 3 (e.g. same site, same document series) and that source's management file has `extracted_tokens` recorded, mention that figure as a rough size reference (e.g. "similar to already-ingested X, ~1200 tokens") to help the user gauge context-budget impact before selecting many candidates at once. For `[Web]` candidates, note the file format when it is not a plain HTML page (e.g. `[PDF]`) — in particular, every result surfaced by step 5's `filetype:pdf` pass — so the user can tell primary-source documents apart from HTML pages at a glance.

**Known license (Issue #646)**: for each `[Web]` candidate, look up the license registration would record on it, and show it. This is the same deterministic table `add_source.py` consults at registration time, queried one step earlier so it informs the approval this Skill requires rather than arriving after the source is already in:

```bash
python .claude/skills/wikicommit-generate/scripts/add_source.py \
  --license-for-url "$(cat <<'EOF'
<candidate URL>
EOF
)"
```

The URL goes through a quote-delimited heredoc, as every unvalidated free-text CLI argument in these Skills does. A candidate URL is not a value some earlier script checked the shape of — it comes off a search result, or verbatim out of a third party's reference list in step 5.5 — and an unquoted one containing `&` is split by the shell: the lookup then answers for the truncated URL (an ordinary `…/w/index.php?title=X&oldid=1` permalink loses its `&oldid=…`, and with it the share-alike line this step exists to show), while whatever followed the `&` is run as a command.

Always exits 0. Three outcomes:

- `LICENSE: <id> (share-alike)` → show the identifier **and** say that a page built only from this source inherits the obligation to offer that page under the same license. This is the registration-time warning of Issue #570 moved one step earlier, where it can still change the decision
- `LICENSE: <id>` → show the identifier alone
- `UNKNOWN: <url>` → **write nothing on that candidate's line.** The table holds only the handful of sites that state a license for their own content as a whole, so most candidates land here; a "license: unknown" on nearly every row is a line the reader learns to skip, and this Skill already has a near-always-empty step it deliberately keeps folded away for that reason (step 7)

Because the silent case is the common one, say once — in the preamble below, not per candidate — what that silence means. A license is shown only where WikiCommit has a confirmed entry, and its absence means WikiCommit does not know the terms, never that there are none. This is the same line `sources[].license` draws by omitting the field rather than recording an empty string.

Do not guess a license from the domain, the page, or the search summary. This step reports a lookup; the LLM's own reading of the licensing situation belongs in the `⚠️` note above, where it is visibly an assessment rather than a recorded fact.

```
Not-yet-ingested source candidates related to theme "<theme content>":
(A license is shown only where WikiCommit has a confirmed entry for that site. No license shown
means WikiCommit does not know the terms — not that there are none. The final judgment is yours.)

[Local]
1. raw/report-2024.pdf — (brief reason for relevance)
2. docs/notes/meeting-0512.md — (brief reason for relevance)

[Web]
3. https://example.com/article — "Article Title" (brief reason for relevance)
   ⚠️ Copyright concern: may amount to a full reprint of a commercial news article
4. https://example.gov/pamphlet.pdf — [PDF] "Pamphlet Title" (brief reason for relevance)
5. https://ja.wikipedia.org/wiki/XXX — "Article Title" (brief reason for relevance)
   License: CC-BY-SA-4.0 — share-alike: a page built only from this source has to be offered
   under the same license
```

If there are zero candidates, display "No not-yet-ingested candidates related to theme were found" and stop. Otherwise, hold off on asking the user to select by number — that prompt now comes at the start of step 8, after the type proposal step below has had a chance to run against the full list.

### Step 7: Type Proposal (Issue #489)

Before asking the user to select candidates, look at the candidates just presented in step 6 (titles + web search summaries, not full content) as a group and judge whether one or more Schema.org standard types — beyond what's already in `installed schema/` — would fit several of them meaningfully better than any installed type (the same "clearer semantic fit" bar `wikicommit-generate` Pass 2b uses, not merely "also plausible"). This step exists because, at the time this Issue was written, Pass 2b's own proposal only fired in an interactive session — a batch/subagent-driven `/wikicommit-generate` run silently defaulted every Pass 2b prompt to reject, so a type that was clearly needed never got added (see this Issue's background). Pass 2b has since gained its own non-interactive auto-approval path for candidates clearing a stricter bar (Issue #507), so this step is no longer the *only* mitigation for that failure mode, but it remains valuable in its own right: step 6's candidate list is being reviewed before the user has picked anything from it — the number-selection prompt is deliberately deferred to step 8 precisely so this step's Enter-based approval always runs interactively — and the evidence available (candidate titles + search summaries across multiple candidates) is comparable in strength to what Pass 2b judges from a single source's summary.

Zero candidates is the expected common outcome — do not force one to justify running this step, and do not present anything to the user if nothing clearly qualifies (this keeps the step from becoming the kind of near-always-empty detour Issue #404 removed from `wikicommit-init`, since it stays folded into this existing step rather than becoming a standalone one). Skip any candidate type that already has a file in `.wikicommit/schema/`.

1. Load the Schema.org type names (this also builds the shared vocabulary cache lazily on first use, same as `wikicommit-generate` Pass 2b step 1): `python .wikicommit/scripts/check_schema_org_type.py --list-type-names`. Non-zero exit (vocabulary fetch failed) → skip this step entirely and proceed straight to step 8 with only `installed schema/` types available; do not block or fail the run over this. Ground the judgment below in this output — do not propose a type name from memory alone, since an unverified guess (wrong casing, a type that doesn't actually exist) would only surface as a downstream `ERROR:` in step 3 after the user has already approved it.
2. Using the `--list-type-names` output, judge which candidate types (if any) qualify per the bar above.
   Then read the descriptions of just those candidates before going further (stage two, Issue #798):

   ```bash
   python .wikicommit/scripts/check_schema_org_type.py --describe \
     "$(cat <<'EOF'
   <Candidate1>
   EOF
   )" \
     "$(cat <<'EOF'
   <Candidate2>
   EOF
   )"
   ```

   Each candidate name goes through its own quote-delimited heredoc, for the same reason step 4's
   `--property` values do — these are names this step itself just proposed, not values an earlier
   script already verified. Drop any candidate whose actual definition does not fit, and any name
   that comes back as `ERROR:` (a name not in the vocabulary was invented rather than recalled).

For each candidate type that does qualify:

3. Present it to the user and ask for approval, Enter-based (default to **N** on a blank Enter), citing which candidates from step 6 motivate it:

   ```
   Several of the above candidates (2. "Introducing Kiro", 5. "Antigravity overview") describe named
   software products — schema:SoftwareApplication may fit them better than any installed schema/ type.

   Add this type now? [y/N]
   ```

4. For each approved type, re-verify it still exists in the vocabulary and pick 2-5 candidate properties for the new type's `properties:` block, verifying each the same way `wikicommit-generate` Pass 2b / `wikicommit-schema-propose` Step 4 do:

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

   Each `--property` value goes through its own quote-delimited heredoc — these are candidate names this step itself just proposed, not values an earlier script already verified. If the script reports `<Type>` itself as `ERROR:` (not just a property), abort this candidate entirely — do not write a schema file for it, and tell the user the proposed type name did not resolve in the vocabulary (this should be rare given the `--list-type-names` grounding in step 1 and the `--describe` confirmation in step 2, but is not impossible if the LLM misread a type name from that list). Otherwise, drop any individual property the script reports as `ERROR:` — never put an unverified property into the new schema file's `properties:` block. Then write `.wikicommit/schema/<Type>.md` directly with the Write tool, in the standard-type format (Issue #495's `properties:`-nested layout), using `.wikicommit/schema/default.md` and `.wikicommit/schema/Person.md` as the fixed style references — identical process to `wikicommit-generate` Pass 2b step 4 / `wikicommit-schema-propose` Step 4. **Where another installed type is the better home for a recognizable class of subject, say so as its own `granularity` rule and name that type** — e.g. `Prefer schema:HowTo when the source's substance is an ordered set of steps the reader performs`. `granularity` is where cross-type deference lives (there is no separate field for it), and `wikicommit-generate` Pass 2c is instructed to follow such a line over its own read of the fit (Issue #569). It is not the same as the `Boundary` rule: `Boundary` says what the type is not, this says who should have it instead. Name only types that are actually installed — a line pointing at a type this wiki does not have cannot be acted on. Every `granularity` bullet has to survive YAML parsing as a plain **string**: write a boundary rule as `Boundary — …` with an em dash rather than `Boundary: …`, and keep ` #` out of the middle of an unquoted bullet. The two fail differently. A `": "` turns the bullet into a one-key mapping, which consumers that filter on `isinstance(g, str)` skip entirely — `check_property_wikilink_reinforcement.py` at least warns that it did so. A ` #` opens a YAML comment and truncates the rest of the line; the bullet is still a string, so nothing warns at all and the dropped half is simply gone. Nothing validates a schema file and no Skill can edit it afterwards, so either shape is merged and stays broken (Issue #649). Wrap the whole bullet in double quotes if the wording needs either character. Set `wikicommit.provenance: collect` in the new file's `wikicommit:` block (do not copy `Person.md`'s own `provenance: default` value — each write site stamps its own origin). This is the one narrow exception to this Skill's "no writes to `.wikicommit/schema/`" rule (see Prohibited Actions below): it only ever *adds* a file that isn't there yet, never edits or deletes an existing one. No commit or PR happens here — the new file is left on disk like any other file `wikicommit-generate` writes, and `wikicommit-merge` picks it up later in the normal batch.

5. Rejected or no-candidate types are simply not added — no persistence of a declined candidate anywhere, same reasoning as `wikicommit-generate` Pass 2b. `wikicommit-schema-propose` remains the post-hoc safety net for anything missed here.

### Step 8: Register the Selected Candidates

Make clear that the copyright/license assessment from step 6 is only a rough guide and **the final judgment is made by a human**, then ask the user to select by number from the step 6 list (multiple selections allowed; "none" is also a valid choice; `all` or `*` selects every listed candidate at once).

<!-- skill-language-exception: names the Japanese token this prompt used to accept, in the note recording why it was dropped -->
The select-all shortcut used to accept the Japanese word 「全部」 alongside `all` (Issue #808). It was dropped rather than joined by more languages: a hand-maintained list of translations has no end, and every operator whose language is not on it silently has one fewer way to answer. `*` is the language-neutral replacement — it belongs to the same vocabulary as the numbers this prompt already asks for. Nothing hard-breaks for an operator who still types 「全部」: this is a prompt read by an agent, which resolves it from context; what changed is which forms this Skill guarantees.

For each candidate the user selected — and only those — run **only** `wikicommit-generate`'s Step 0: Source Registration (`.claude/skills/wikicommit-generate/SKILL.md`) with that candidate's path/url as the argument. That step's item 0 re-reads `.wikicommit/source-policy.md` before registering; here it has nothing left to decide — steps 2.5/4/5/6 already applied the same policy to this candidate and the user then approved it explicitly — so **do not re-prompt about the policy for a candidate selected here**. Treat the approval you just collected as the answer to item 0's question, and run item 0's checks only for the one thing this Skill did not already do: a candidate whose URL is in `rejected:` should not be reachable here at all (step 2.5 drops those), so if one is, say so and stop rather than registering it silently. Do **not** proceed to Pass 1–4 (text extraction, analysis, page generation, review) here — page generation is deferred to a separate `/wikicommit-generate` run (see Step 9). Running text extraction and analysis for every selected candidate within this same conversation would accumulate each candidate's extracted text in context, risking token exhaustion and long runtimes when many candidates are selected at once.

Do not register candidates the user did not select in `.wikicommit/source/`.

**Record the ones they turned down (Issue #564)**: for each `[Web]` candidate the user explicitly declined — not the ones they simply did not get to, and never a `[Local]` one, which no future search will re-surface — ask for a one-line reason and append an entry to `wikicommit.rejected` in `.wikicommit/source-policy.md`:

```yaml
  rejected:
    - url: https://opendata.example.lg.jp/datasets/XXX
      reason: too large to be worth a page of its own
      date: "2026-08-29"
```

**Check what `rejected:` currently looks like before writing.** The shipped template leaves it with no value, so a first entry goes straight underneath it. A wiki initialized before this file existed — or one where someone wrote `rejected: []` by hand — has an empty *flow* list instead, and a block entry cannot be nested under one: writing `- url: ...` beneath a line reading `rejected: []` is a YAML syntax error. Replace that whole line with a bare `rejected:` first. This matters more than it looks: a syntax error anywhere in this frontmatter makes `check_extraction_quality.py` fall back to "no extra domains", silently switching `exclude_domains` off for every URL fetched afterwards. Read the file back after writing and confirm its frontmatter still parses before reporting success.

Skip the whole thing if the user does not want to give a reason; an entry with no reason is worse than no entry, since a later reader cannot tell whether it still applies. Ask once, per run, for all declined candidates together — not once per candidate.

This is the only write any Skill makes to this file, and it may only **append** to `rejected:` — never edit or remove an existing entry, never touch another key, never touch the prose. The prose and the maps are the human's, in the same way `.wikicommit/schema/` is (step 7's exception has the same shape). Nothing else in WikiCommit persists a rejected candidate, and this is a deliberate difference from Pass 2b's declined *type* candidates, which are dropped on purpose: reading the same source again re-derives a type judgment, but "we looked at this and decided we did not want it" is a human decision that reading the source a second time will never reproduce. Without a record, free exploration proposes it again every single run.

### Step 9: Report Results

Display a list of the outcome for each candidate's registration (`CREATED` / `SKIP` / `UPDATED`, or the failure reason — per Step 0's output). If at least one candidate was registered, guide the user through the next steps:

```
Next steps:
- Run /wikicommit-generate (no arguments) to generate wiki pages for the N registered candidates
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
```

If many candidates were registered (e.g. more than around 5), add a note suggesting the user split page generation across multiple `/wikicommit-generate` runs (no arguments; it processes all pending/outdated management files each time) rather than expecting a single run to handle all of them — each run's context resets when started fresh, which keeps token usage and per-run time manageable.

## Prohibited Actions

- Registering to `.wikicommit/source/` without user approval
- Implementing a new dedicated crawler or scraping script (must be built entirely from a combination of existing web search and extraction skills)
- Committing or creating a PR against `main` or any branch
- Writing to `.wikicommit/source-policy.md`, other than appending to its `rejected:` list in step 8 (never editing an existing entry, another key, or the prose)
- Writing to `.wikicommit/schema/`, other than the narrow exception in step 7 (adding a new, human-approved type file only — never editing or deleting an existing one, same "add-only" exception `wikicommit-generate` Pass 2b uses)
- Writing anything at all during the survey step — it runs three read-only scripts and reads their output; nothing on disk changes before a focus is chosen
- Choosing a focus for the person when they do not. With nobody answering, the run stops without searching; the model does not aim it on its own
- Recording focuses that were passed over. The `rejected:` list holds source URLs a person turned down, which is a different thing

## Notes

- The copyright assessment of web search results depends on the LLM's judgment and is not guaranteed accurate. Limit yourself to surfacing concerns — the final judgment is made by a human
- Relevance judgment for local candidates does not read the full content of files. Full-content evaluation is left to `wikicommit-generate`'s Pass 2 (analysis), which runs in a later, separate `/wikicommit-generate` invocation (not called from within this skill — see step 8)
- Setting or changing `theme` is out of scope for this skill (edit `.wikicommit/config.yml` directly)
- **Role split with `wikicommit-init`'s obvious-type judgment and `wikicommit-generate` Pass 2b (Issue #490)**: this Skill's step 7 is the middle of three type-proposal entry points, ordered by how strong the evidence behind the proposal is: `wikicommit-init` judges from the `theme` sentence alone (weakest, strictest bar), this Skill judges from candidate titles and search summaries (middle), and `wikicommit-generate` Pass 2b judges from the full source text (strongest). All three skip types that already have a file under `.wikicommit/schema/`, so they do not need to be mutually exclusive
