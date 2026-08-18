---
name: wikicommit-fix
description: Fix a wiki page based on a GitHub Issue, a page path, or a published page URL, using its sources as ground truth
disable-model-invocation: true
---

# wikicommit-fix

An AI-assisted skill that fixes typos, factual errors, and missing information reported for a wiki page, cross-checking against the target page's `sources` (the original documents). Because the flow is a thin sequence of identifying the feedback and the target page → generating a fix proposal → human confirmation → calling `wikicommit-merge`, this skill has no dedicated scripts.

Feedback can be supplied three ways (Issue #454): as a GitHub Issue (the original, and still the only route with automatic traceback to an originating Issue in Step 7), as a repo-relative page path with an inline free-text instruction, or as a published-wiki page URL with an inline free-text instruction. This mirrors the two-route (Issue-driven / direct-target) pattern `wikicommit-review` already established (Issue #313), extended here to a third input form (published URL) that page-review didn't need.

## Usage

```
/wikicommit-fix <issue-url>                                    # Issue-driven: e.g. /wikicommit-fix https://github.com/owner/repo/issues/42
/wikicommit-fix <page-path> "<fix instruction>"                 # Page-path-driven: e.g. /wikicommit-fix .wikicommit/entity/ja/Person/yamada-taro.md "生年を1981年に修正して"
/wikicommit-fix <published-page-url> "<fix instruction>"        # Published-URL-driven: e.g. /wikicommit-fix https://example.github.io/ja/Person/yamada-taro "生年を1981年に修正して"
```

## Processing Flow

### Step 1: Identify the Input Route, Then Fetch Feedback Content

Determine which of the three input forms was given, in this order:

1. **Issue-driven**: the first argument matches a GitHub Issue URL (`https://github.com/<owner>/<repo>/issues/<number>`). Parse `owner/repo` and the issue number, then run:

   ```bash
   gh issue view <issue-number> --repo <owner>/<repo> --json title,body,url,comments
   ```

   If `gh` authentication fails or the issue doesn't exist, display the error as-is and stop. The feedback content for Step 4 is the Issue's `body` plus every comment's `body`, concatenated (Issue #454 — previously only `body` was fetched, so feedback left as a comment on an auto-generated review-tracking Issue, per `docs/DesignDoc-pipeline.md` §6.2's fixed-checklist template, was silently invisible to this skill; that's the most natural place a human reviewer would actually write one). If a second argument was also given, ignore it (a free-text instruction has no role here — feedback always comes from the Issue itself) and note that to the user.

2. **Page-path-driven**: the first argument starts with `.wikicommit/entity/`. If it doesn't resolve to an existing file, display "Page not found: `<page-path>`" and stop (don't fall through to the generic usage message below — a `.wikicommit/entity/`-prefixed first argument unambiguously signals page-path-driven intent, most likely a typo, not a different input form). Otherwise, a second argument (the free-text fix instruction) is required — if missing, display an error asking for it and stop. The feedback content for Step 4 is that second argument verbatim.

3. **Published-URL-driven**: the first argument is a URL that isn't a GitHub Issue URL. A second argument (the free-text fix instruction) is required — if missing, display an error asking for it and stop. The feedback content for Step 4 is that second argument verbatim. Resolving this URL to a target page happens in Step 2.

If none of the above match (unrecognized input — not an Issue URL, not a `.wikicommit/entity/`-prefixed path, not a URL), display the Usage block above and stop.

### Step 2: Identify the Target Page

**Issue-driven** (unchanged from before Issue #454):

1. If the Issue body explicitly states a path starting with `.wikicommit/entity/`, use it as the target page.
2. If not explicitly stated, extract keywords from the Issue title/body and search under `.wikicommit/entity/` (use the `wikicommit-search` skill if it's installed; otherwise fall back to the Grep tool).
3. If the search returns multiple results, present the candidate list (path + title + `type`) to the user and let them choose. If there are zero results, display an error and stop.

**Page-path-driven**: the target page is the path from Step 1 directly — no search needed.

**Published-URL-driven**: reverse-resolve the URL to a `.wikicommit/entity/` path. The build pipeline mirrors `.wikicommit/entity/<lang>/<Type>/<slug>.md` to `content/<lang>/<Type>/<slug>.md` verbatim (`.wikicommit/scripts/convert_wikilinks.py`), but Quartz's own slug transformation of the `<Type>` path segment beyond that point isn't something this repo can verify (its Quartz submodule was removed in Issue #81) — so **do not** try to reconstruct `<Type>` from the URL. Instead, extract only `<lang>` (the URL path's first segment) and `<slug>` (its last segment, stripping a trailing `.html` if present) and resolve using those two alone, which are far less likely to have been case-transformed by the build than a multi-word `<Type>` segment:

```bash
python3 -c "
import sys, os, glob
from urllib.parse import urlparse

url = sys.argv[1]
segments = [s for s in urlparse(url).path.strip('/').split('/') if s]
if len(segments) < 2:
    print('ERROR: could not extract both <lang> and <slug> from the URL path')
    sys.exit(1)
lang = segments[0].lower()
slug = segments[-1]
if slug.lower().endswith('.html'):
    slug = slug[:-5]

root = f'.wikicommit/entity/{lang}'
if not os.path.isdir(root):
    print(f'ERROR: no .wikicommit/entity/{lang}/ directory (unrecognized <lang> segment \"{lang}\")')
    sys.exit(1)

all_pages = glob.glob(f'{root}/**/*.md', recursive=True)
matches = sorted(p for p in all_pages if os.path.splitext(os.path.basename(p))[0].lower() == slug.lower())

if not matches:
    print(f'NOT_FOUND: no page under {root}/ with slug \"{slug}\"')
elif len(matches) == 1:
    print(f'MATCH: {matches[0]}')
else:
    for m in matches:
        print(f'CANDIDATE: {m}')
" "$(cat <<'EOF'
<published-page-url>
EOF
)"
```

The free-text-in-shell-argument rule (`docs/DesignDoc-skills.md` §11.7) applies here even though the value looks like a URL — it is unvalidated text from the user, and the heredoc-via-command-substitution form is what keeps a URL containing shell metacharacters from being evaluated by the shell during command assembly.

Matching is deliberately by `<slug>` alone across every `<Type>` directory under that `<lang>`, not `<lang>/<Type>/<slug>` — this is what makes the lookup independent of Quartz's `<Type>`-segment casing. Handle the three possible outcomes:

- `MATCH: <path>` → use it as the target page.
- `CANDIDATE: <path>` (one or more lines) → the slug exists under more than one `<Type>` for this `<lang>` (e.g. both `Person/tokyo.md` and `Place/tokyo.md`). Present the candidate list (path + title + `type`, same presentation as the Issue-driven multi-result case above) and let the user choose.
- `NOT_FOUND:` / `ERROR:` → display the message as-is and stop.

**All routes**: once the target page is determined, read its frontmatter. If the page has `status: removed`, tell the user and confirm whether to proceed.

### Step 3: Fetch the Source Document

1. Check the target page's frontmatter `sources`.
2. If `sources` is empty and the page is a translated page with `translated_from`, read the parent page pointed to by `translated_from` and use the parent page's `sources` instead (per `DesignDoc-data.md §4.2`, translated pages inherit source information from the parent page).
3. For each element of `sources`, fetch the source document according to `source.type` (reuse the text extraction routing from `wikicommit-generate` Pass 1):
   - `type: path` and `.md` / `.txt` → read directly with the Read tool
   - `type: path` with any other extension → call the corresponding extraction skill per the "Prerequisite Skills (Text Extraction)" table in `.claude/skills/wikicommit-generate/SKILL.md`. If the required skill is not installed, guide the user through the install command and stop
   - `type: url` / `type: wikicommit` → fetch `source.url` with the WebFetch tool
   - `type: manual` → no source document. Treat only `sources`' `author` / `created_at` as provenance information, and use the page body itself as the basis for the fix
4. If no source document could be obtained at all (fetch failure, or `sources` is empty and there's no parent page either), warn the user and confirm whether to proceed. Since producing a fix proposal without a source raises the risk of hallucination, whether to proceed must always be the user's call.

### Step 4: Generate a Fix Proposal

**Translation-page redirect check** (Issue #529 — only when the target page identified in Step 2 has `translated_from`): before generating anything, classify **each distinct point** in the feedback identified in Step 1 (the Issue's body plus every comment, per Step 1, can raise more than one) as either **translation-specific** (a mistranslation, terminology inconsistency against the `DefinedTerm/` glossary, or unnatural/overly-literal phrasing — a property of this translation alone, not of the original page's content) or **content-derived** (a factual error, missing information, or structural issue that would equally apply to the original page). Classify per point, not the feedback as a whole — feedback often mixes both kinds (e.g. one comment asks for a phrasing fix, another flags a wrong birth year), and collapsing it into a single verdict risks sending a translation-only fix to the original page, or losing a content fix on the translation page where a future re-translation would silently discard it. This is the same original-vs-translation-specific split already established for the tracking-Issue checklists (`docs/DesignDoc-pipeline.md` §6.2, Issue #525) and `wikicommit-review` Step 4's fact-check.

If one or more points are content-derived, ask the user once, scoped to those points: "この指摘は原文ページ（`<translated_from>`）にも影響する可能性があります。原文ページを修正対象にしますか？" If they agree, those points' fix proposal targets the `translated_from` path instead of the translation page — Step 5's write and Step 6's report for that proposal then apply to the original page instead of the translation. Step 3's source fetch does not need to be redone for this proposal **if** the translation page's `sources` was empty when Step 3 ran (the ordinary case — `docs/DesignDoc-data.md` §4.2 — since Step 3 already fell back to the parent's `sources` then, so the documents fetched are already the original page's own ground truth). If the translation page instead carried its own non-empty `sources` (uncommon, but permitted — that section only says a translation page "can omit" `sources`, not that it must), re-run Step 3 against the `translated_from` page's own `sources` before generating this proposal, since the documents already fetched reflect the translation page's `sources`, not necessarily the parent's. Once the fix lands on the original page, the existing STALE-detection path (`source_commit` mismatch → `check_translation_status.py`, `docs/DesignDoc-pipeline.md` §6.4) picks up the translation for re-translation on its own — this Skill does not also need to edit the translation page for these points.

If one or more points are translation-specific, their fix proposal always targets the translation page from Step 2 (never redirected), regardless of what happens with any content-derived points above.

If the user declines the redirect for the content-derived points, fold those points into the same proposal as the translation-specific ones, targeting the translation page from Step 2 unchanged — proceed exactly as if no redirect had been offered.

Pass each proposal's points, the current body of whichever page that proposal targets (per the classification above), and the source document obtained (or re-fetched, per above) into the LLM's context, and generate that proposal. When every point in the feedback classifies the same way (or the redirect is declined), this collapses back to the single fix proposal this Skill produced before Issue #529.

Rules:

- Include only claims grounded in the source document. Do not add new claims absent from the source document (hallucination prevention, per the policy in `DesignDoc-data.md §4.6`)
- If the feedback cannot be corroborated by the source document, do not make a fix — report to the user that "the feedback could not be corroborated in the source document" (never make an ungrounded fix)
- Do not change structural frontmatter fields (`type`, `lang`, `sources`, etc.). The main focus of the fix is the body text, but if a type-specific property (nested under `properties:` — e.g. `properties.description`, `properties.birthDate`, Issue #495) has a clear factual error, that may also be included in the fix. When editing one, preserve the `properties:` nesting exactly as already present in the page — do not flatten it to the top level

### Step 5: User Confirmation → Write

If Step 4 produced two separate fix proposals (one redirected to the original page, one remaining on the translation page), repeat the numbered steps below once per proposal, in either order — each is its own confirmation-and-write cycle.

1. Present the fix proposal to the user in diff form (the relevant sections before/after).
2. Only after getting the user's confirmation, write to the target page with the Edit tool. **Do not write before confirmation.**
3. If the user rejects the proposal or gives fix instructions, regenerate based on the instructions and repeat step 5.
4. **Translator Notes** (Issue #524): if the target page has `translated_from` (i.e. it is a translation page) **and** the fix just written is translation-specific — a mistranslation, terminology inconsistency, or unnatural phrasing that is a property of this translation, not of the original page's content (the original does not need the same fix, since the original is correct as-is) — also append an entry to its `translator_notes` frontmatter field (a list of strings; add the field with an empty list if it doesn't exist yet — `docs/DesignDoc-data.md` §4.2). Format the entry as `"YYYY-MM-DD: <one- or two-sentence summary of what changed and why>"` using today's date, and always append (never remove or rewrite prior entries — if a new entry supersedes an older one on the same point, leave the old entry in place; the newer, later-dated entry is understood to take precedence). Write the entry in the target page's own `lang` (the translation's language, not `primary_lang` — a translator note is written for whoever next edits or re-translates this specific language variant). This exists because `/wikicommit-translate` always fully re-translates from the original page with no memory of the current translation (`docs/DesignDoc-pipeline.md` §6.4) — without this note, the fix just written would silently disappear the next time the original page changes and triggers a re-translation. Do **not** add an entry for a fix that is a genuine factual correction potentially also relevant to the original page (e.g. a wrong `properties.birthDate` value copied through from a stale source) — `translator_notes` is scoped to translation-quality issues only. Skip this step entirely for a page without `translated_from`.

### Step 6: Report Results

Briefly report to the user how the written fix (or fixes, if Step 4 produced separate proposals for the original and translation pages) addresses each point raised in the feedback (the Issue, or the free-text instruction) — and which page each point's fix was written to, so a point redirected to the original page is clearly distinguished from one that stayed on the translation page.

### Guidance After Completion

```
Next steps:
- Run /wikicommit-merge to perform quality checks, PR creation, and merge
```

If the user wants to proceed all the way through PR creation automatically, you may continue on to call `wikicommit-merge` after confirming with the user, but the default is to stop at guidance only (never proceed to a PR without the user confirming the fix content).

### Step 7: Link Back to the Originating Issue

This step only applies to the **Issue-driven** route (Step 1). Page-path-driven and published-URL-driven fixes have no originating Issue to link back to — skip this step entirely for them, the same way `wikicommit-review`'s Route B (Issue #313) skips its equivalent Issue-closing step. As noted in that Skill's design, this does trade away the GitHub-visible traceability an Issue comment provides, but the underlying fix reasoning still lands in the commit message (CLAUDE.md's GitOps principle), so it isn't a new trade-off introduced by Issue #454 — it's the same one `wikicommit-review` already made for its own direct-target route.

If Step 4's translation-page redirect check (Issue #529) sent a point's fix to the original page instead of the translation page the Issue nominally targeted, this step is unaffected as far as *whether or how it runs*: the `<issue-number>`/`<owner>/<repo>` this step comments on come from Step 1, not from whichever page the fix was ultimately written to. It does change what the comment must say, though: if any point was redirected, the `<one-line summary of the fix>` below must say so explicitly (name the original page path, and note that the translation page itself is unchanged until a future re-translation picks up the fix) — otherwise the reporter, who filed feedback against the translation page's tracking Issue, would reasonably read "merged" and assume the translation page itself was directly corrected.

For the Issue-driven route, this step only applies once `wikicommit-merge` has actually run to completion and reported a successful merge (its Step 7 confirmed the merge completed, and its Step 10 completion report gives the bulk-update PR number) — whether that happened as a direct continuation of this same conversation or because the user (or you, resumed with this conversation's context) ran `/wikicommit-merge` separately afterward. If `wikicommit-merge` was never run, or it aborted, or its PR was closed without merging, skip this step entirely — do not comment.

Comment on the originating Issue (`<issue-number>`/`<owner>/<repo>` from Step 1) to close the loop with the reporter:

```bash
gh issue comment <issue-number> --repo <owner>/<repo> --body "$(cat <<'EOF'
この Issue の内容を確認し、修正を PR #<bulk-update PR number> でマージしました（<one-line summary of the fix>）。

内容に問題がなければご自身でこの Issue をクローズしてください。
EOF
)"
```

Do not run `gh issue close`. Landing the fix on `main` does not by itself confirm the reporter is satisfied with the result, so closing the Issue is left to the reporter's judgement — the comment above only asks them to do so once they're happy.

Only comment after the merge is confirmed, never before. Commenting (or closing) as soon as the fix is written in Step 5 — before `wikicommit-merge`'s quality gates and merge have actually succeeded — would leave a stale, misleading comment on the Issue if the PR later gets blocked by a `check_wikilinks.py`/`validate_frontmatter.py` error, fails to auto-merge, or times out during Step 7's polling.

## Notes

- Never write to a page without user confirmation (step 5)
- Do not commit or create a PR against `main` or any branch (that is `wikicommit-merge`'s responsibility)
- Do not add claims that don't exist in the source document (hallucination)
- Do not write to `.wikicommit/schema/` (read-only)
- Never close the originating Issue yourself (step 7) — comment only, and let the reporter close it
