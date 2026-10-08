---
pass_token: "5cd0ed36"
---

# Step 9: generation-failure tracking Issues (`failure-issues`)

The workflow engine hands you this step only after `merge-pr` was confirmed merged.

Report `filed` when every target management file has been handled — given a new Issue, found to have an open one already, or skipped and recorded for the report. As with Step 8 there is no completion check, for the same reason, and a resumed run simply runs this step again from the start: the marker match below keeps it from filing anything twice.

### Step 9: Generate Generation-Failure Tracking Issues

Only run this step if Step 7 confirmed the merge completed (`gh pr merge` exited 0).

> **Why this step exists**: when a `wikicommit-generate` entity fails source-integrity review (Pass 4) after exhausting `generate.max_retries`, it is recorded only inside the source management file's `failed_pages` list and `## Failure Reason` section — invisible from the page itself (for `action: update`, the pre-existing page is simply left unchanged, with no sign anything was attempted) and invisible from any later session unless someone happens to re-open that exact management file. This mirrors Step 8's tracking-Issue mechanism but for a different failure class: Step 8 surfaces successfully-generated pages awaiting human review; this step surfaces generation attempts that did *not* produce a page at all. It intentionally does not trigger any automation on close (unlike Step 8's `review_status` flip via `review-issue-close-sync.yml`) — closing this Issue is purely a human record-keeping action, since there is no single well-defined "fixed" state analogous to `review_status: reviewed` for a page that was never written. To actually retry, re-run `/wikicommit-generate` on the source.

#### Extracting Target Management Files

Scan the **entire `.wikicommit/source/` tree on the default branch** (`<default branch>` — the run record's `default_branch` list) — not just this batch's changes — for the same reason as Step 8's full-tree scan: a management file whose tracking-Issue creation failed in a *previous* run, or one that picked up `failed_pages` through a batch other than the immediately preceding one, must still be caught on every run regardless of which run originally introduced it.

```bash
python -c "
import re, sys
from pathlib import Path
import yaml
FRONTMATTER_RE = re.compile(r'^---\r?\n(.*?)\r?\n---\r?\n?', re.DOTALL)
for path in sorted(Path('.wikicommit/source').rglob('*.md')):
    content = path.read_text(encoding='utf-8-sig')
    m = FRONTMATTER_RE.match(content)
    try:
        fm = (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError as e:
        print(f'WARNING: {path}: frontmatter YAML parse failed, skipping ({e})', file=sys.stderr)
        continue
    if not isinstance(fm, dict):
        continue
    failed = fm.get('failed_pages') or []
    if isinstance(failed, list) and failed:
        print(path)
    elif fm.get('status') == 'failed':
        print(path)
"
```

**`status: failed` is a second target condition, not a redundant one.** `failed_pages` is written by Pass 4, so it is only ever non-empty when page generation was actually attempted. A source that fails in Pass 1 — a known JS-shell domain, an empty or unreadable extraction — never reaches Pass 4, so its `failed_pages` is empty; and nothing else reports it (Pass 1 does not collect `failed`, and `check_ingest_freshness.py`'s `CHECKABLE_STATUSES` does not include it), so without this condition it would drop out of the pipeline with no report anywhere. The two conditions do not overlap in practice — Pass 4 step 7 writes `status: failed` only on a branch where every entity was attempted and failed, and that branch fills `failed_pages` — but the `elif` makes one Issue per management file regardless.

Same `FRONTMATTER_RE` and `try`/`except` resilience as Step 8's extraction script, for the same reason: one management file anywhere in the tree with malformed frontmatter must not abort the scan before every other target file is found. Relay any `WARNING:` lines to the user in the Step 10 completion report, same as Step 8.

If there are zero target management files, display "No generation failures require tracking" and proceed to Step 10.

Process every target management file found in this same run — same no-cap, sleep-2-seconds-between-creates rate-limit approach as Step 8's "No Cap — Rate Limit Safety Margin Instead" section, for the same reasons.

#### Checking for Existing Tracking Issues (per target management file)

Each tracking Issue embeds an exact machine-readable marker in its body: `<!-- wikicommit-ingest: <source management file path> -->`. Fetch open `wikicommit-generation-failure`-labeled issues and scan their `body` for that exact marker locally (same rationale as Step 8 — do not rely on `gh issue list --search`):

```bash
gh api "repos/{owner}/{repo}/issues?labels=wikicommit-generation-failure&state=open&per_page=100" \
  --paginate --jq '.[] | select(.pull_request | not) | {number, body}'
```

Same fetch as Step 8 — type `{owner}/{repo}` literally, and do not swap it for a label-filtered `gh issue list`, which stops at 1000.

- If any returned issue's `body` contains the exact marker for this management file → skip it and move to the next
- If none do → create a new tracking Issue

#### Issue Generation (repeat per target management file)

Read the management file's `source.type`, `source.path`/`source.url`, `failed_pages`, and `last_generated_at` fields, and its `## Failure Reason` section body (write "unknown" in the Issue body for `last_generated_at` if unset — same "unknown" fallback Step 8 uses for missing `generated_at`/`generated_by`). For a source caught by `status: failed` with an empty `failed_pages`, say so where the list would go — the failure happened before any page was attempted, and an empty list with no explanation reads as data that went missing.

**Then get the reason for each failed page from the review records**. Skip this command when `failed_pages` is empty — the `status: failed` source caught before any page was attempted has no page to ask about:

```bash
python .wikicommit/scripts/check_review_coverage.py --discarded-reason "$(cat <<'EOF'
<failed_pages[0]>
EOF
)" "$(cat <<'EOF'
<failed_pages[1]>
EOF
)"
```

Repeat the `"$(cat <<'EOF' … EOF)"` argument once per entry. It is the free-text-in-shell-argument form rather than a bare path for the same reason `--title` below is, and for the same reason Pass 4 uses it when it hands these very paths to `reset_review_on_content_change.py`: `<Type>` and `<slug>` are not validated anywhere in the pipeline, and both come out of Pass 2's reading of a source document.

**This is not a second-best source for the reason — on most of these Issues it is the only one.** Pass 4 writes `## Failure Reason` only on the `status: failed` branch, and deletes it on `partial`; `partial` is what a source reaches when some of its entities succeeded, which is the ordinary shape of a generation failure. So on the Issues this step creates most often, that section is structurally absent and the reason reads `unknown` — while the run that discarded the page wrote a full account of why into `.wikicommit/review/`, the only trace a page that was never written leaves behind.

Take the reason per failed page, in this order:

1. `REASON:` lines from the command above — the finding type, where it was found, and the instruction the review gave, quoted as recorded
2. the management file's `## Failure Reason` section, when present **and that page has no record of its own**. `status: failed` is written on two different paths and only one of them lands here: a Pass 1 failure leaves `failed_pages` empty, so there is nothing per-page to report and this section is the whole reason; a Pass 4 run in which every entity was attempted and failed fills `failed_pages` *and* leaves a record per page, so (1) still wins there even though the section is present
3. `NO_RECORD:` or neither — write that no reason was recorded, **not `unknown`**. A failure predating the review-record tree, or a repository without `.wikicommit/review/`, genuinely has nothing to show; saying so is different from saying the reason is unknowable, and it tells the reader not to go looking

**If that script does not exist or does not accept `--discarded-reason`, carry on without it** and fall back to (2) and (3). A repository whose `.wikicommit/scripts/` predates this mode is the normal case for a wiki that has not been updated recently, and a missing reason is not a reason to withhold the Issue.

The instruction text is quoted **verbatim**. It was written to steer a regeneration rather than to be read by an operator, and it shows — it is phrased as a command. Summarizing it would mean rewriting a judgment this step did not make, at exactly the point where the record's value is its specificity; the record tree was designed to be read by people, and this text is the most specific thing that exists about why the page is missing. **The one field never quoted is `source_file`**: for a source document it holds a path under `.wikicommit/.cache/`, which is gitignored and machine-local, so it names nothing in another clone or after the cache is cleared. The script already drops it and says instead which *kind* of file the line numbers count into.

```bash
# 1. Create the tracking Issue
gh issue create \
  --title "$(cat <<'EOF'
Generation failure: <source management file path>
EOF
)" \
  --label wikicommit-generation-failure \
  --body "$(the Issue body template below, with source, failed_pages, last_generated_at, and the failure reason filled in)"

# 2. Brief pause before the next management file's issue create, to stay clear of GitHub's secondary rate limit
sleep 2
```

Pass `--title` through the same quote-delimited heredoc pattern as Step 8, for the same reason — the source management file path is deterministic but not itself upstream-validated against a constrained character set, so it is not exempt from this rule.

Skip step 2 after the last target management file (no next iteration to protect).

If `gh issue create` fails because the `wikicommit-generation-failure` label does not exist yet in this repository, create it once — `gh label create wikicommit-generation-failure --description "WikiCommit generate-pass failure tracking" --color <any color>` — then retry the same `gh issue create`. This only happens the first time this step ever runs in a given repository; the label persists afterward.

Obtain `<Issue number>` from the `gh issue create` output (the Issue URL) or via `gh issue view --json number -q .number`, and record it for use in the Step 10 completion report.

If `gh issue create` fails for any other reason (API error, etc., after the label-retry above), skip this management file, record the error to the console, and move to the next one (do not abort all of Step 9 due to a single file's failure).

#### Issue Body Template

```markdown
## Generation Failure

- Source: `<source.type>` — `<source.path or source.url>`
- Ingest management file: `<source management file path>`
- Last attempted: <last_generated_at> (write "unknown" if not set)
- Failed pages (intended `create`/`update` targets that were not written; any existing page among these was left unchanged):
  - `<failed_pages[0]>`
  - `<failed_pages[1]>`
  - ...

## Failure Reason

<One block per failed page, in the same order as the list above:>

### `<failed_pages[0]>`

<The review's findings for that page, one per line, as `<TYPE> <where>: <instruction verbatim>`.
 Where no record exists, write: No reason was recorded for this page. — and nothing else.>

<Only where `failed_pages` is empty — the `status: failed` source caught before any page was
 attempted — there are no per-page blocks: drop the headings and quote the management file's
 `## Failure Reason` section body here instead. When `failed_pages` is non-empty the per-page
 blocks above are the reason, even if that section is also present.>

## How to Proceed

This Issue is a visibility record, not an automation trigger — closing it does not change anything on its own (unlike a `wikicommit-review` tracking Issue, whose close is detected by `review-issue-close-sync.yml`).

<Write exactly one of the two blocks below, chosen by `failed_pages`, and drop the other along with
 this note. The two failures retire in different ways, and the steps of one cannot be carried out on
 the other: the first block is about entities, and a source caught before any page was attempted has none.>

<Block A — only where `failed_pages` is non-empty:>

Read the failure reason above, then either fix the underlying issue (adjust the source content, or add guidance to the management file's `## User Notes`) and re-run `/wikicommit-generate` on this source to retry.

**Closing it while `failed_pages` is still non-empty does not keep it closed** — the duplicate check above looks only at *open* Issues, so the next `/wikicommit-merge` creates this Issue again. To retire it for good, the underlying entry has to leave `failed_pages`.

**If the gap is acceptable as it is** — the page should simply not exist, for example because the source only mentions that subject in passing — accept it this way instead of closing the Issue as it stands:

1. In the management file's `## User Notes` section, write that this source should not produce a page for that entity, and why. The step that decides what to extract from a source reads that section, and an entity it does not extract cannot land in `failed_pages` again.
2. If the management file's `status` is `failed` (every entity it produced failed), first change it to `pending` — a named run otherwise stops at "no changes" without reading the source again. Then run `/wikicommit-generate <this source's path or URL>` naming this source explicitly — a run without arguments may not reach it.
3. Check that the management file's `failed_pages` is now empty. If the entity you wrote about is still listed, the note was not followed; this Issue stays useful as it is.
4. Run `/wikicommit-merge`, then close this Issue. With `failed_pages` empty, it is not created again.

That one named run also rewrites this source's pages that did succeed; any of them whose content changes goes back to waiting for a read and gets a review tracking Issue of its own. That is expected, not a fault.

<Block B — only where `failed_pages` is empty (the source failed before any page was attempted, so its `status` is `failed`):>

No page was attempted in the run that failed, so there is no entity to accept or to retry — only the source itself. **Closing this Issue as it is does not keep it closed**: the duplicate check above looks only at *open* Issues, and the next `/wikicommit-merge` finds `status: failed` again and creates this Issue anew. Retire it one of these two ways, depending on what the failure reason says:

1. **If the failure was temporary** — a network or server problem — wait, then change the management file's `status` to `pending` and run `/wikicommit-generate <this source's path or URL>` naming this source explicitly. A fetch that now succeeds moves the source off `status: failed`, and the next merge leaves this Issue alone. If it fails the same way again, it was not temporary: take the second route.
   **Except** when the management file lists `generated_pages` (an earlier run built pages from it and only this re-check failed): leave `status` as `failed` and just run `/wikicommit-generate <this source's path or URL>` by name — that re-fetches the URL and compares it with the content the pages were built from. Setting `pending` instead would rebuild every one of those pages from the cached copy without fetching anything, sending any whose wording changes back to waiting for a read. If that run reports no changes, change `status` back to `generated` and delete the `## Failure Reason` section; if the content changed, the run regenerates the pages and sets `status` itself.
2. **If this URL source cannot be fetched at all** — for example the site refuses automated requests (HTTP 403) — take the source out of the wiki:
   - Delete the management file. `/wikicommit-merge` creates this Issue from the management file, so without one it never creates it again. **Except** when that file lists `generated_pages` (an earlier run built pages from it and only this re-check failed): then do not delete it — change `status` back to `generated` and delete its `## Failure Reason` section instead. Nothing was fetched, so `source.hash` still describes the content those pages were built from.
   - Add the URL to `rejected:` in `.wikicommit/source-policy.md` with a `reason` that says it could not be fetched (the status code) and a `date`. The next attempt to register it then stops to ask, quoting that reason, and the record of what was tried survives the deleted file. If other documents on the same site are refused too, add the host to `exclude_domains:` instead — that is a decision about the whole site, and it also stops any URL on it from being fetched.
   - Run `/wikicommit-merge`, then close this Issue.

   For a repository file (`source.type: path`) that cannot be extracted, these steps do not apply — there is no URL to record, and its `source.hash` was already updated to the new file when it was registered. Repair or replace the file and take the first route, or remove the file from the repository together with its management file.

   Do not mark this source `status: retracted` for this. That value says the source *was* fetched in full and its content is not trustworthy, and the published source page shows it as withdrawn — neither is true of a document the wiki never managed to read.

Commands here are written the way Claude Code invokes them (`/wikicommit-generate`); in Codex, type `$wikicommit-generate` and so on instead.

<!-- wikicommit-ingest: <source management file path> -->
```

The marker line is an HTML comment, same as Step 8's — invisible in the Issue view, retrievable via `gh issue view --json body`.
