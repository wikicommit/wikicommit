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

   It follows every `merged_into` and rewrites `[[Type/old]]` to `[[Type/new]]` in every live page, frontmatter included (`properties:` values carry WikiLinks too). Without it the next `/wikicommit-merge` is blocked: a link to a `status: removed` page is an error there. The pages it rewrites keep their `review_status` — only the link changed, and it now names the page a person decided is the same concept. `/wikicommit-status` does not list them under `STALE_REVIEW:` either: `check_review_coverage.py` undoes each merge recorded in `relations.yml` before deciding a page changed. A page that already linked to both the kept and the absorbed page before the merge is the exception — it is listed, and a re-review clears it.

If any step fails, stop and report `halted` with what failed; do not undo the steps before it. The person can finish by hand: the check names what is still missing.

## What to tell the person (in the run's report)

- Which pages were merged into which, the names the kept page took over, and how many links were rewritten.
- **Open review-tracking Issues for the absorbed pages are not closed by this Skill** (it runs no Git or GitHub commands). After `/wikicommit-merge`, close each one, noting that the page was merged into the kept page. The kept page is back at `review_status: pending`, so `/wikicommit-merge` opens a fresh tracking Issue for it.
- **The absorbed pages' URLs on the published site stop working.** Removed pages are not built, and nothing redirects them; the merged names are on the kept page as aliases, and an alias becomes a redirect to it — so the old **name** still leads there, but the old **slug** does not.
- The kept page's translations are now out of date; `/wikicommit-status` lists them as stale, and `/wikicommit-translate` brings them up to date.
