---
pass_token: "a5ebc134"
---

# Step 8: post-review tracking Issues (`tracking-issues`)

The workflow engine hands you this step only after `merge-pr` was confirmed merged, so the default branch you are on already holds this batch. It hands it over only when there is something to file — or when it could not tell, because the open tracking Issues could not be read.

Report `filed` when every page the targets command lists has been handled — given a new Issue, or skipped and recorded for the report. **There is no completion check on this step, on purpose**: a page whose Issue could not be created is skipped by design and picked up by the next run's full scan, and a check that insisted on an Issue for every pending page would turn a tolerated API failure into a run that cannot finish.

### Step 8: Generate Post-Review Tracking Issues

> **Why a tracking Issue instead of a post-review PR**: GitHub does not let a PR author approve their own PR, so a solo operator could never approve a review PR opened under their own account. Closing an Issue has no such self-approval restriction (any repo write-access holder can close it), and lets someone who only reads the published wiki — with no Claude Code session at all — mark a page reviewed straight from GitHub.

#### The Target Pages

Get them by running the scan again, now — not from the run record's `review_targets` list, which was read before this step started:

```bash
python <this Skill's directory>/scripts/workflow_checks.py targets --kind review --run <run>
```

Each `ITEM:` line is a page to file an Issue for, in the order to file them. The command scans the whole `.wikicommit/entity/` and `.wikicommit/view/` trees on the default branch (not only this batch, so a page whose Issue could not be filed in an earlier run is picked up), keeps the pages whose `review_status` is `pending` or missing, leaves out `index.md`, the attachments under `.wikicommit/entity/assets/` and `status: removed`, and drops every page an open `wikicommit-review` Issue already names. Running it afresh is what makes a resumed step safe: an Issue created before the interruption is open now, so its page is no longer listed and nothing is filed twice.

- **No `ITEM:` line and a `WARNING:` that the open Issues could not be read** → file nothing. Without that match every page would get a duplicate Issue. Keep the `WARNING:` for the Step 10 report and report `filed`; the next `/wikicommit-merge` picks the pages up.
- **No `ITEM:` line otherwise** → display "No pages require post-review" and report `filed`.
- Keep every other `WARNING:` line (a page whose frontmatter YAML could not be parsed is skipped) for the Step 10 report as well.

Process **every** listed page in this same run; there is no cap. A cap only staggers when Issues appear and strands the pages beyond it. The only real constraint is GitHub's secondary rate limit on rapid successive mutations, so pause 2 seconds after each page's `gh issue create` (step 1 of Issue Generation below) before starting the next page.

#### Per Target Page

Obtain `<lang>` and `<slug>` from the target page's frontmatter `lang` field and its filename (without extension). `<Type>` is the value of the frontmatter `type` field with the `schema:` prefix stripped (e.g. `schema:Person` → `Person`, `schema:custom/Decision` → `custom/Decision`); always use this `<Type>` (including the `/`) in Issue titles. **A page under `.wikicommit/view/` has no `type:` field at all**, so for one of those `<Type>` is the reserved constant `View` — the same segment `[[View/<slug>]]` and the published `content/<lang>/View/` path use. Do not leave it empty; an Issue titled `Review: /<slug> (<lang>)` names nothing. While reading this frontmatter, also check for `translated_from` and `derived_from` — which one is present (if either) selects the Issue Body Template variant used below.

**Also determine `<Pass-2b type?>` for a `sources`-based page** (only listed pages reach here, so this read is spent only on pages that get an Issue). Read `.wikicommit/schema/<Type>.md` (`<Type>` as derived just above, i.e. with the `schema:` prefix already stripped) and check whether its `wikicommit.provenance` is `generate-interactive` or `generate-auto` — the two values `wikicommit-generate` Pass 2b has stamped when adding a type on the fly (it writes only `generate-interactive` now, since a non-interactive run defers a type candidate instead of approving it, but type files already stamped `generate-auto` remain and still get the item). If it is, the `sources` variant's checklist below gains one extra item; otherwise that item is omitted. Treat a missing or unreadable schema file, a missing `provenance`, or any other value (`default`, `init-theme`, `collect`, `schema-propose`, `manual`) as "no" — every one of those means a human either installed the type deliberately or approved it through a path that already had its own confirmation. Skip this read entirely for translation and synthesized pages: neither variant carries the item.

> **Why `provenance` rather than this batch's diff.** This step scans the whole default branch so that a page whose Issue creation failed in an earlier run is still picked up; a batch-scoped condition would give that rescued page a different checklist purely as a function of when the API failed. `provenance` is a permanent stamp, so it answers identically on every run. The cost — every page of a Pass 2b-added type carries the item from then on — is accepted, since Pass 2b adding a type at all is uncommon.

**`<page path>`** is the target page's own repo-relative path, exactly as the targets command printed it — `.wikicommit/entity/<lang>/<Type>/<slug>.md` for an entity page, `.wikicommit/view/<lang>/<slug>.md` for a view page. Use that value verbatim in the "Review Target" line and the marker below; do not rebuild it from `<lang>`/`<Type>`/`<slug>`, because a view page's path contains no Type segment and reconstructing one produces `.wikicommit/entity/<lang>//<slug>.md`, a path nothing on disk matches.

Each tracking Issue embeds an exact machine-readable marker in its body: `<!-- wikicommit-page: <page path> -->`. This is the marker `review-issue-close-sync.yml` resolves on close, and the one the targets command matches open Issues by; a marker naming a path that does not exist makes that workflow exit quietly at its "page already removed" branch, leaving the page `pending` with nothing to show for the close.

#### Issue Generation (repeat per target page)

```bash
# 1. Create the tracking Issue
gh issue create \
  --title "$(cat <<'EOF'
Review: <Type>/<slug> (<lang>)
EOF
)" \
  --label wikicommit-review \
  --body "$(the Issue body template below — selected per the translated_from/derived_from check above — with the relevant fields and the marker filled in)"

# 2. Brief pause before the next page's issue create, to stay clear of GitHub's secondary rate limit
sleep 2
```

Pass `--title` through a quote-delimited heredoc, not a plain `--title "Review: <Type>/<slug> (<lang>)"` double-quote embedding. `<Type>` and `<slug>` are not upstream-validated constrained identifiers, so they do not qualify for the exemption this rule grants to values a script or command has already validated deterministically: `validate_frontmatter.py` only checks that `type` starts with the `schema:` prefix (no constraint on the characters after it), and `<slug>` is simply the page's filename with no character-class enforcement anywhere in the pipeline. A page whose `type`/filename contains shell metacharacters (via a hand-edited page, Route B, or a future ingest bug) would otherwise be interpolated verbatim into this `gh issue create` command.

Skip step 2 after the last target page (no next iteration to protect).

If `gh issue create` fails because the `wikicommit-review` label does not exist yet in this repository (`could not add label: 'wikicommit-review' not found` or similar), create it once — `gh label create wikicommit-review --description "WikiCommit page review tracking" --color <any color>` — then retry the same `gh issue create`. This only happens the first time this step ever runs in a given repository; the label persists afterward.

Obtain `<Issue number>` from the `gh issue create` output (the Issue URL) or via `gh issue view --json number -q .number`, and record it for use in the Step 10 completion report.

If `gh issue create` fails for any other reason (API error, etc., after the label-retry above), skip this page, record the error to the console, and move to the next page (do not abort all of Step 8 due to a single page's failure).

If `generated_at`/`generated_by` (`sources`-based and synthesized pages) or `translated_at`/`translated_by` (translation pages, see below) is missing from the target page's frontmatter, write "unknown" in the Issue body for that field.

#### Issue Body Template

##### Language of the Issue body

**Render the chosen template in the wiki's `primary_lang`** — `translation.primary_lang` from `.wikicommit/config.yml`, the same value `/wikicommit-init` set. When it is `en`, or when the file is missing, unreadable, or has no `primary_lang`, emit the English template verbatim as before.

The English templates below stay canonical: translate at write time rather than keeping one template per language. Three variants times two languages would double this Skill's instruction area, and a SKILL.md is loaded in full on every invocation.

**Why this Issue is translated when the scripts' console output is fixed English**: the language follows the reader. Console output is read by an operator and an agent, so it stays in one language; this Issue is read by whoever closes it, which by design includes someone who only reads the published wiki and has no Claude Code session at all — and every other reader-facing surface (the banner, the sources box, the build-generated pages) already switches.

**`.github/ISSUE_TEMPLATE/report.md` is not the same case and stays English.** It says why in its own words: there is one of it per repository, so it has no language of its own. A tracking Issue is one per page, and that page has a `lang`, so the same reasoning lands the other way.

**`primary_lang`, not the page's own `lang`.** A tracking Issue follows one page, which makes the page's language the intuitive choice, but the person who reads it is whoever holds write access to close it — a property of the repository, not of the page. On a wiki with `targets`, using the page's `lang` would send that one operator Issues in two languages.

Leave these untranslated wherever they appear:

- The marker line `<!-- wikicommit-page: <page path> -->`. `review-issue-close-sync.yml` matches it exactly, and it is the only part of the body any machine reads.
- The Issue title (`Review: <Type>/<slug> (<lang>)`). It is an identifier, and listing and searching depend on its shape.
- Anything anyone is expected to type or look at: command names (`/wikicommit-fix`, `/wikicommit-generate <url>`, `/wikicommit-merge`, `/wikicommit-status`), file paths, frontmatter keys and values (`sources:`, `properties:`, `review_status`, `status: retracted`), and the `wikicommit-review` label.
- The field values themselves — the page path, the dates, and the model IDs — and the literal `unknown` this step writes in place of a missing one (it stands in a field-value slot, and Step 9's Issues use the same literal).

The section headings and the prose are translated, since they are what the reader is there to read. **This includes the shared "How to Proceed" section**: "insert this verbatim" below means the three variants all get the same text, not that this one section stays English. Leaving it untranslated would hand the reader this change is for — someone closing the Issue with no Claude Code session — the write-access requirement, the warning that a comment asking for a change does not make the change, and the two comment exceptions in a language they may not read, inside a body that is otherwise in their own.

Three variants exist, selected by which provenance field the target page's frontmatter has:

- **`sources`-based pages** (no `translated_from`, no `derived_from`) — a normal `wikicommit-generate` output.
- **Translation pages** (`translated_from` present) — a `wikicommit-translate` output. Carries `translated_from`/`translated_at`/`translated_by` instead of `generated_at`/`generated_by`, and its `sources` is inherited from the original page rather than set directly — so "does the content match the source document?" does not translate meaningfully to it, and its checklist below is a distinct set of translation-quality questions rather than a reworded copy of the `sources`-based checklist.
- **Synthesized pages** (`derived_from` present) — a `wikicommit-synthesize` output. Carries `derived_from` (an array of `{path, source_commit}`) instead of `sources`, but — unlike a translation page — does carry `generated_at`/`generated_by` the same as a `sources`-based page; only its "Review Target"/"Once You Have Read It" content differs, not the at/by fields.

These three provenance fields are mutually exclusive per page, so exactly one variant applies to any given target page. All three share the same "How to Proceed" text below — it only describes `review-issue-close-sync.yml`'s reaction to the Issue closing, which is identical regardless of page provenance — and the same `wikicommit-review` label / `<!-- wikicommit-page: ... -->` marker format, so no change to that workflow is required for any of the three.

**Why the checklists read as they do.** Do not bring back questions Pass 4 already answers (does the page match its sources, are there hallucinations): asking them on every page, and having them pass every time, is what stops a checklist from being read. Ask instead for what only a person can supply. Pass 4 may judge only on the literal source text, so **outside knowledge** is by construction something only a human brings; and nothing anywhere checks **harm** — whether a sentence inside a page that legitimately exists treats a real person or organization unfairly (`.wikicommit/entity-policy.md` decides only whether the page is written).

- **The knowledge item says "tell us if you know", never "go and find out"** — research would make each review an open-ended search; reporting what you already know costs nothing.
- **The knowledge item and the source item go in the `sources` variant only.** On a translation a stale fact or a bad source belongs to the original page, and on a synthesized page to whichever grounding page states it — the same redirect `wikicommit-fix` makes. **Harm goes in all three**, because a harmful sentence is harmful whatever produced it.
- **No checkboxes.** `review_status` is two-valued: it records an *event* — someone read the page — not an attestation about it. So the Issue asks for **one line on what the reader took away**, and anything they noticed goes in the same comment, as prompts rather than boxes to tick. Keep the list short anyway — one of these Issues is generated per page.
- **"This is not a test" has to be written down.** Without it, the request for a line reads as something the reader will be marked on. There is no correct answer, so nothing can be marked or faked.
- **Do not write "this is not a review" anywhere.** All three products come from one reading. Change only the reader-facing strings; leave `review_status`, `reviewed_by`, the `wikicommit-review` label, the workflow filenames, the Skill names and the commit trailers alone.
- **Say the machine's half out loud.** The banner states that the page was checked against its sources, so introduce the prompts as what that check does *not* cover — otherwise the reader infers nothing was checked at all.
- **The source itself is a separate question.** Every automated check measures the page *against* its sources, so a page faithfully repeating a source's error passes all of them; only a person can doubt a source. The answer lands as `status: retracted` plus a `## Retraction Reason`, written by hand, so it travels as a comment — the second exception to "a comment does not carry through", alongside a source URL. Both exist because `/wikicommit-fix` edits a page's text and cannot touch its sources.
- **Keep this text different from the report link's.** The report link addresses any reader; this Issue addresses whoever can close it. Copying one into the other makes each look like a worse copy of the other. The distinct part here is the ask for a line; one sentence naming the difference keeps it legible.

##### Shared "How to Proceed" section (all variants)

Insert this verbatim into every Issue body, between "## Once You Have Read It" and the marker line — "verbatim" meaning identical across all three variants, not exempt from "Language of the Issue body" above; render it in `primary_lang` along with the variant it is inserted into:

```markdown
## How to Proceed

Closing this Issue takes write access to this repository (or triage access, if it is owned by an organization) — GitHub only lets you close an Issue you did not open yourself if you have one of those, and hides the button otherwise. If you are reading this without that access, open a new Issue of your own describing what is wrong instead: that needs no special access, and `/wikicommit-fix` reads it. On a published wiki, the report link in the banner at the top of the page does this for you with the page already filled in (that link is worded in the page's own language, so its exact label differs from page to page).
Read the page (locally, or on the published wiki once it's live) and, if everything looks good, simply close this Issue — that alone is enough. A GitHub Actions workflow (`.github/workflows/review-issue-close-sync.yml`) detects the close, flips this page's `review_status` from `pending` to `reviewed`, and auto-merges that change once quality checks pass. There is no PR to Approve here — closing this Issue is the entire action, and it works the same whether you use Claude Code or just the GitHub web/mobile UI. **Close it as "completed"** (GitHub's default close button): only that reason marks the page `reviewed`. Closing as "not planned" or "duplicate" leaves the page `pending` and records no review.
If changes are needed, write what you found in a comment and leave this Issue open. **You do not have to make the fix yourself** — `/wikicommit-fix <this Issue's URL>` reads this body and its comments. It is closed once the fix has landed.
**A comment saying what you took away, or what you noticed, is exactly what this Issue is for** — that needs nothing further from you, and nothing else has to happen to it.
**A comment asking for a change does not make the change**: the workflow that runs on close only reads the marker line at the bottom of this Issue's body and flips `review_status` from `pending` to `reviewed` — it never reads comments. Closing after only asking for a fix merges the page with that fix unmade. To have it applied, run `/wikicommit-fix <this Issue's URL>` explicitly (it reads both this Issue's body and its comments and proposes a fix), and close this Issue only after that fix has landed.
**Two kinds of comment are the exception, because both are about a page's sources rather than its text, and `/wikicommit-fix` cannot touch sources at all.**
**A URL naming a document a page should have been written from** needs `/wikicommit-generate <url>` followed by `/wikicommit-merge` — that folds what the document says into the page written from it, which comes back for review once it lands (if this Issue tracks a translated or a synthesized page, that is the page this one derives from, not this one). If you cannot run those, leaving the URL in a comment hands it to someone who can — but leave this Issue open until they have, because closing it still merges this page as reviewed.
**Saying that one of the sources itself is wrong** is the other. Nothing automated can reach that judgment — every check this wiki runs treats the sources as the standard the page is measured against, so a page faithfully repeating a source's error passes all of them. Name the source and say what is wrong with it in a comment; someone with write access marks it `status: retracted` with the reason in its management file, and `/wikicommit-status` then lists every page still standing on it. Name only a document this page itself was written from — if this Issue tracks a translated or a synthesized page, it has no sources of its own and the documents belong to the page it derives from, so raise it there rather than here. Leave this Issue open until that has happened, for the same reason as above.
Commands here are written the way Claude Code invokes them (`/wikicommit-fix`); in Codex, type `$wikicommit-fix` and so on instead.
```

##### `sources`-based pages (no `translated_from`, no `derived_from`)

```markdown
## Review Target

- Page: `<page path>`
- Generated at: <generated_at> (write "unknown" if not set)
- Generated by: <generated_by> (write "unknown" if not set)

## Once You Have Read It

When you have read this page, put **one line on what you took away from it** in a comment and close
this Issue (the box you type into when you close is the same one). It does not have to be a summary
— "that surprised me" or "nothing here was new to me" is enough.

**This is not a test of your understanding.** It is the record that this page's knowledge actually
reached a person. Closing this Issue states two things — that this page's knowledge reached a
person, and that **nothing struck you as obviously wrong while reading**. It is not a guarantee
that the content is correct.

This page was already checked against the documents it was written from, by machine, when it was
generated — where the published page shows it, the banner at the top names the model and the date. Nothing below was
checked by any automation, so if you noticed any of it while reading, put that in the same comment.
**You are not being asked to go looking.**

- Anything about a real person or organization that reads as overstated, or as settled when it is
  disputed, or as a private detail this page has no reason to hold. Whether this page should exist
  at all was judged against `.wikicommit/entity-policy.md` when it was generated; the sentences
  inside it were not.
- Anything that conflicts with what you already know, or an important fact about this subject that
  none of its sources carry. **If you have a URL for it, put the URL in the comment** — that one is
  carried onward even though nothing else in a comment is (see "How to Proceed"). `/wikicommit-generate <url>`
  folds what it says into this page, and the page comes back here to be read again; run it yourself
  if you have write access, or leave the URL for someone who does.
- Anything another page on this wiki says differently. The machine can only compare a page against
  ones written before it in the same batch, so a contradiction across batches is visible to nobody
  but a person reading several pages over time.
- **Anything wrong with a source this page was written from**, rather than with the page. This is a
  separate thing to say, and saying the page looks fine does not cover it: every automated check
  measures the page *against* its sources, so a page that faithfully repeats a source's error passes
  all of them. If you know one of the documents this page lists under `sources:` to be unreliable,
  say which and why — a comment carries this one onward (see "How to Proceed").
- Is `<Type>` the right type for this subject, and do the `properties:` keys listed in `.wikicommit/schema/<Type>.md` fit it? This type was added automatically while this page was being written, and no automated check judges whether it *fits* — only that it exists in the Schema.org vocabulary.

**If something did stick out, a comment is all that is asked of you — and in that case do not close
this Issue.** The fix is not yours to make; whoever has access closes this once it has landed.

On a published wiki, the report link on the page collects the same kinds of thing from any reader
who happens to notice one. This Issue is the step above it: closing it is how this wiki records that someone
read the page, which is why it takes write access.

<the shared "How to Proceed" section above, inserted verbatim>

<!-- wikicommit-page: <page path> -->
```

**The last bullet is conditional: emit it only when `<Pass-2b type?>` (determined above) is yes, and drop the whole line otherwise**, leaving the bullets that always apply. Do not emit it commented out or with the condition written into it — what a reader sees must contain only what they are actually being asked, and an HTML comment placed inside the body would travel into the Issue verbatim the way the `wikicommit-page` marker does. It appears only on pages whose type was added on the fly, which is the uncommon case, and it is the only place the tracking Issue surfaces a type decision that may have been taken with no human confirmation at all.

##### Translation pages (`translated_from` present)

```markdown
## Review Target

- Page: `<page path>`
- Translated from: `<translated_from>` (the original-language page; this Issue tracks only the translation's own `review_status`, not the original's — the original may already be `reviewed`, or may never have been through this review flow at all, so it will not always have a tracking Issue of its own)
- Translated at: <translated_at> (write "unknown" if not set)
- Translated by: <translated_by> (write "unknown" if not set)

## Once You Have Read It

When you have read this page, put **one line on what you took away from it** in a comment and close
this Issue (the box you type into when you close is the same one). It does not have to be a summary
— "that surprised me" or "nothing here was new to me" is enough.

**This is not a test of your understanding.** It is the record that this page's knowledge actually
reached a person. Closing this Issue states two things — that this page's knowledge reached a
person, and that **nothing struck you as obviously wrong while reading**. It is not a guarantee
that the content is correct.

This page was already checked against the original it was translated from, by a machine translation-quality
pass, when it was generated. Nothing
below was checked by any automation, so if you noticed any of it while reading, put that in the same
comment. **You are not being asked to go looking.**

- Anywhere the translation does not carry the original's meaning, reads awkwardly or too literally,
  or uses a term differently from the `DefinedTerm/` glossary.
- Anything about a real person or organization that reads as overstated, or as settled when it is
  disputed, or as a private detail this page has no reason to hold. Whether this page should exist
  at all was judged against `.wikicommit/entity-policy.md` when it was generated; the sentences
  inside it were not.

If a fact here is out of date or wrong on the substance rather than the wording, the page to fix is the original this was translated from, not this one — a fix written here is overwritten the next time the original changes and the translation is regenerated. The same goes for a source: this page has none of its own, and anything wrong with the documents behind it belongs to the original's own sources.

**If something did stick out, a comment is all that is asked of you — and in that case do not close
this Issue.** The fix is not yours to make; whoever has access closes this once it has landed.

On a published wiki, the report link on the page collects the same kinds of thing from any reader
who happens to notice one. This Issue is the step above it: closing it is how this wiki records that someone
read the page, which is why it takes write access.

<the shared "How to Proceed" section above, inserted verbatim>

<!-- wikicommit-page: <page path> -->
```

##### Synthesized pages (`derived_from` present)

```markdown
## Review Target

- Page: `<page path>`
- Derived from: `<derived_from[0].path>`, `<derived_from[1].path>`, ... (one entry per `derived_from` array element)
- Generated at: <generated_at> (write "unknown" if not set)
- Generated by: <generated_by> (write "unknown" if not set)

## Once You Have Read It

When you have read this page, put **one line on what you took away from it** in a comment and close
this Issue (the box you type into when you close is the same one). It does not have to be a summary
— "that surprised me" or "nothing here was new to me" is enough.

**This is not a test of your understanding.** It is the record that this page's knowledge actually
reached a person. Closing this Issue states two things — that this page's knowledge reached a
person, and that **nothing struck you as obviously wrong while reading**. It is not a guarantee
that the content is correct.

Every claim on this page was already checked, by machine, against the pages listed under "Derived
from". Nothing below was checked by any automation, so if you noticed any of it while reading, put
that in the same comment. **You are not being asked to go looking.**

- Anything about a real person or organization that reads as overstated, or as settled when it is
  disputed, or as a private detail this page has no reason to hold. Whether this page should exist
  at all was judged against `.wikicommit/entity-policy.md` when it was generated; the sentences
  inside it were not.

This is the page where that one earns the most. Every automated check here compares a single claim against the pages under "Derived from"; an implication that arises only from putting several of their statements side by side is visible to no check at all — and putting statements side by side is exactly what this page does.

If a fact here is wrong rather than badly combined, the page to fix is the one under "Derived from" that states it, not this one. The same goes for a source: this page has none of its own, and anything wrong with the documents behind it belongs to whichever page under "Derived from" was written from them.

**If something did stick out, a comment is all that is asked of you — and in that case do not close
this Issue.** The fix is not yours to make; whoever has access closes this once it has landed.

On a published wiki, the report link on the page collects the same kinds of thing from any reader
who happens to notice one. This Issue is the step above it: closing it is how this wiki records that someone
read the page, which is why it takes write access.

<the shared "How to Proceed" section above, inserted verbatim>

<!-- wikicommit-page: <page path> -->
```

The marker line is an HTML comment: GitHub does not render it in the Issue view, so it stays invisible to the human reviewer while still being retrievable via `gh issue view --json body` for the targets command above and for `review-issue-close-sync.yml`.

GitHub has no native way to require a comment before an Issue is closed ("Require conversation resolution" applies to PRs, not Issues). The ask for a line, and the prompts under it, are guidance for the human reviewer, not an enforced gate — which is why the wording has to earn the line rather than demand it.
