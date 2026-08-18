---
name: wikicommit-search
description: Search wiki pages by keyword using FTS5 trigram full-text search
---

# wikicommit-search

A keyword-search skill that performs FTS5 trigram full-text search over `.wikicommit/entity/`. All index-building and query logic is delegated to the shared script `.wikicommit/scripts/search_index.py` (p3-005); this skill is only responsible for formatting and displaying results (`docs/DesignDoc-skills.md` §11.5).

## Usage

```
/wikicommit-search <query> [--lang <lang>]
```

- `<query>`: search keywords (multiple words separated by spaces are allowed)
- `--lang <lang>`: restrict to pages in the given language (ISO 639-1) (optional)

## Processing Flow

### Step 1: Run the Query

```bash
python .wikicommit/scripts/search_index.py query "$(cat <<'EOF'
<query>
EOF
)" [--lang <lang>] --limit 10
```

Pass the query through a quote-delimited heredoc (`docs/DesignDoc-skills.md` §11.7), not a plain double-quote embedding — `<query>` is free-form user text with no upstream validation, and command substitution (`` ` ``, `$(...)`) is evaluated by the shell at the point this command line is assembled regardless of which program the resulting argument is ultimately handed to; scoping the downstream program to a local read-only script does not by itself contain that (Issue #398 — this reverses the narrower carve-out `docs/DesignDoc-skills.md` §11.7 previously documented for search queries).

Pass `--lang` through to `search_index.py` as-is if given. Always pass `--limit 10`.

On exit code `1` (failure, with an `ERROR:` line printed), display that error message as-is to the user and stop (e.g. SQLite doesn't support trigram, or `.wikicommit/entity/` doesn't exist).

### Step 2: Parse the Output

Parse stdout:

- `MATCH: <path> | title=<title> | type=<type> | lang=<lang> | review_status=<review_status>` line → information for one hit
- The indented line immediately after (`  <snippet>`) → that hit's snippet
- `SUMMARY: query="...", hits=<N>` line → the total hit count
- `WARNING: query term "<term>" has <N> character(s); trigram search requires at least 3 and this term cannot match anything` line(s) (zero or more, one per short term) → `search_index.py` itself detects query terms too short for the trigram tokenizer to ever match (Issue #274); collect these to explain an unexpected `hits=0` in Step 3

### Step 2.5: Look Up Each Hit's `sources`

For each hit's `<path>` (skip this step entirely if `hits=0`), read the page with the Read tool and extract its frontmatter. `search_index.py`'s own index doesn't carry `sources` — it isn't full-text-searchable structured data, so extending the FTS5 schema for it isn't worth it when each hit's `path` is already in hand (Issue #458). Format a `sources` line per hit:

- Ordinary page with a non-empty `sources` list: format each entry and join with `, `:
  - `type: path` → the `path` value as-is (e.g., `raw/paper-2024.pdf`)
  - `type: url` / `type: wikicommit` → the `url` value with a leading `https://` or `http://` stripped (e.g., `simonwillison.net/2025/May/1/not-vibe-coding/` — full URLs would dominate the result listing's width; the scheme carries no information the reader needs to recognize the source)
  - `type: manual` → `manual (author: <author>)`
- Translation page (`translated_from` present, per `docs/DesignDoc-data.md` §4.2 these have no `sources` of their own): read the parent page at `translated_from` and format *its* `sources` the same way as above, prefixed with `translated from <translated_from>: ` — this is more informative than a bare "this is a translation" note, and the parent page's `sources` are exactly what a reader chasing provenance actually wants. If the parent page itself is missing (already a `check_translation_status.py` `MISSING_SOURCE` case elsewhere), fall back to `translated from <translated_from> (parent page not found)`.
- Synthesized page (`derived_from` present, per `docs/DesignDoc-data.md` §4.2 these also have no `sources` of their own): format as `derived from: <path1>, <path2>, ...` using each entry's `path`.
- Anything else with an empty or missing `sources` (a malformed page that isn't a translation/synthesis/index page — `index.md` pages don't reach this step at all, since `search_index.py`'s `build` already excludes them from the index): `sources: (none)`.

### Step 3: Display Results

If `hits=0`:

```
No matching pages
```

If any `WARNING:` lines were parsed in Step 2, append a supplementary note naming the offending term(s) (translate the explanation into the query's language if it isn't English):

```
No matching pages

⚠️ The query term(s) "<term1>", "<term2>" are shorter than 3 characters. Trigram search can't match terms under 3 characters — try a more specific term (e.g. 児童手当 instead of 児童).
```

Display this and stop.

If `hits` is 1 or more, number the hits 1, 2, 3, ... in hit order (already ranked by bm25 in `search_index.py`) and format them, appending the `sources` line from Step 2.5. Append `⚠️ Unreviewed` at the end of the line for any hit with `review_status: pending` (omit it for `reviewed`):

```
Search results: "<query>" (<hits> hits)

1. <title> (<type>, <lang>) ⚠️ Unreviewed
   <path>
   <snippet>
   sources: simonwillison.net/2025/May/1/not-vibe-coding/, arxiv.org/html/2510.17842v1

2. <title> (<type>, <lang>)
   <path>
   <snippet>
   sources: translated from .wikicommit/entity/ja/DefinedTerm/vibe-coding.md: raw/paper-2024.pdf
```

## Notes

- Do not commit or create a PR against `main` or any branch
- Do not write to `.wikicommit/schema/`
- This skill itself has no side effects. However, `search_index.py` automatically runs `build` if the index file (`.wikicommit/.cache/search_index.sqlite3`, not tracked by Git) doesn't exist
