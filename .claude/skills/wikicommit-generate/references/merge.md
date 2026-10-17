---
pass_token: "4c7e1b93"
---

# Merging same pages — taking the absorbed pages down (`--regenerate --merge`)

> **Paths in this file.** `references/…`, `scripts/…` and `../<other-skill>/…` are relative to the Skill's directory (the parent of this `references/` directory), not to the repository root — the Skills may be installed under `.claude/skills/` or `.agents/skills/`. Commands still run from the repository root, so spell the path out from there. Paths starting with `.wikicommit/` are repository-root paths as before.

The workflow engine hands you this file as the `merge-absorb` step, and only when the run merges pages (`/wikicommit-generate --regenerate <kept page> --merge <absorbed page> [...]`) and the kept page has passed Pass 4 and been written. `references/regenerate.md` says how the kept page was rebuilt; this file finishes the merge. **When it is done, report it to the workflow engine** with `--token 4c7e1b93` (this file's `pass_token`) and the outcome `absorbed`, or `halted` with `--reason` when a step below fails. The workflow engine then runs `merge_pages.py check`, which refuses the step until every part below is on disk.

Work in this order — the record first, because `merge_pages.py` reads the absorbed pages, and it refuses pages already taken down.

1. **Record the merge** in `.wikicommit/relations.yml`:

   ```bash
   python .wikicommit/scripts/merge_pages.py record --into <kept page> --absorb <absorbed page> [--absorb ...]
   ```

   It appends a `same` item with `merged_into` and `merged_aliases` — the names the kept page took over. That item is where the merged aliases are told apart from aliases a source supports: they rest on a person's decision, so they are not reviewed as added aliases and the one-alias-per-language limit does not hold for them.

2. **Take each absorbed page down**, with its translations:

   ```bash
   python .wikicommit/scripts/remove_page.py <absorbed page> --reason merged --merged-into <kept page>
   ```

   One call per absorbed page. The script finds the page's translations by `translated_from` and gives them the same `status: removed` and `merged_into`, and removes their lines from the type indexes.

3. **Rewrite the links** to the absorbed pages:

   ```bash
   python .wikicommit/scripts/rewrite_merged_links.py
   ```

   It follows every `merged_into` and rewrites `[[Type/old]]` to `[[Type/new]]` in every live page, frontmatter included (`properties:` values carry WikiLinks too). Without it the next `/wikicommit-merge` is blocked: a link to a `status: removed` page is an error there. The pages it rewrites keep their `review_status` — only the link changed, and it now names the page a person decided is the same concept. `/wikicommit-status` does not list them under `STALE_REVIEW:` either: `check_review_coverage.py` undoes each merge recorded in `relations.yml` before deciding a page changed. A page that already linked to both the kept and the absorbed page before the merge is the exception — it is listed, and a re-review clears it. It changes only the link, so two results are left for the person, and it names each: `SELF_LINK:` — a page that now links to itself (in practice the kept page's translation, written before the merge) — and `ALSO_LINKED:` — a page that now names the kept page where it named two different pages, often two items of one list. Keep both kinds of line for the report; do not edit those pages here.

If any step fails, stop and report `halted` with what failed; do not undo the steps before it. The person can finish by hand: the check names what is still missing.

## What to tell the person (in the run's report)

- Which pages were merged into which, the names the kept page took over, and how many links were rewritten.
- Every `SELF_LINK:` and `ALSO_LINKED:` page, with what to do: a self-link in the kept page's translation goes away when `/wikicommit-translate` rebuilds it (below); any other is removed with `/wikicommit-fix <page>`. An `ALSO_LINKED:` page that had a review record is also listed under `STALE_REVIEW:` by `/wikicommit-status` until it is reviewed again.
- **Other items in `.wikicommit/relations.yml` that name an absorbed page are left as they are** — the file is only appended to, and a person's decision is edited only by a person. They stay correct: the merge item says where the absorbed page went, and a reader follows `merged_into` as links do. Name those items so the person can edit them if they want the file to read in the kept page's name.
- **Open review-tracking Issues for the absorbed pages are not closed by this Skill** (it runs no Git or GitHub commands). After `/wikicommit-merge`, the person closes each one, noting that the page was merged into the kept page. Closing it records no review: `review-issue-close-sync.yml` skips a page at `status: removed`. A wiki whose copy of that workflow predates this rule records the absorbed page as `reviewed` by the person who closed the Issue — if `.github/workflows/review-issue-close-sync.yml` has no `status: removed` check, point the person at `/wikicommit-update` before closing. The kept page is back at `review_status: pending`, so `/wikicommit-merge` opens a fresh tracking Issue for it.
- **The absorbed pages' URLs on the published site stop working.** Removed pages are not built, and nothing redirects them; the merged names are on the kept page as aliases, and an alias becomes a redirect to it — so the old **name** still leads there, but the old **slug** does not.
- The kept page's translations are now out of date; `/wikicommit-status` lists them as stale, and `/wikicommit-translate` brings them up to date.
