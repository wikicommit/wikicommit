---
pass_token: "9c3e71a5"
---

# Steps 1–3: what changed, how it is classified, and the quality checks (`link-and-style-checks`)

The workflow engine hands you this step once its own steps have run: the version-skew check, the default branch, change detection (Step 1), the refusal of another run's unfinished work, **the classification of the changes (Step 2) and the fast quality checks (the first part of Step 3)**. So there **are** changes when you get here, none of them belongs to a run that is still open, and no frontmatter, WikiLink, raw-HTML or duplicate-page check found anything blocking — a blocking finding halts the run before this step, with that finding as `halted_reason`, and nothing is branched or committed.

What is left for you is the two checks that never block and do not fit one synchronous command: **lychee** (external links) and **markdownlint-cli2** (style). Report `checked` when both are recorded. The workflow engine's check confirms it on disk; the next step collects every tool's warnings into the run record's `warnings` list, and the PR body is built from what the tools recorded — you do not copy any finding by hand.

### Step 1: Detect Changes (the workflow engine's `detect` step)

The workflow engine has already run the equivalent of:

```bash
git -c core.quotePath=false status --porcelain -- ".wikicommit/entity/**/*.md" ".wikicommit/view/**/*.md" ".wikicommit/source/**/*.md" ".wikicommit/review/**/*.md" ".wikicommit/entity/assets/**" ".wikicommit/source-policy.md" ".wikicommit/entity-policy.md" ".wikicommit/relations.yml"
```

> The `.wikicommit/entity/assets/**` pathspec covers assets — images and attachments under `.wikicommit/entity/assets/`. Without it, a run that only adds an image stops at "No changes to merge" and the asset is never committed, even though Step 5's `git add` (which takes directories, not `*.md`) would have staged it had some other `.md` change carried the run that far. Note this is detection only: assets must **not** enter the `changed_md` list (Step 2), whose pathspecs stay `*.md`-only — every quality check it feeds (`validate_frontmatter.py`, `check_wikilinks.py`, `check_raw_html.py`, `markdownlint-cli2`) parses frontmatter and would fail on a PNG. Because of that, an assets-only run reaches Step 3 with an **empty** `changed_md`, and the per-file checks are skipped (Step 3).
>
> The `.wikicommit/view/**/*.md` pathspec covers the view tree — second-order pages grounded in this wiki's own pages (`derived_from`) rather than in an external document, which `/wikicommit-synthesize` writes there. Unlike assets and the policy files below, these **are** wiki pages and do belong in `changed_md`: every per-file check handles them (`validate_frontmatter.py` applies the view-page rules, `check_wikilinks.py` resolves `[[View/<slug>]]`, `check_raw_html.py` and `markdownlint-cli2` are content checks that do not care which tree a page came from). A wiki that has never run `/wikicommit-synthesize` has no such directory, and the pathspec simply matches nothing.
>
> The two policy-file pathspecs cover `.wikicommit/source-policy.md` and `.wikicommit/entity-policy.md`. `wikicommit-collect`'s Step 8 appends a declined candidate to that file's `rejected:` list, and neither `.wikicommit/entity/` nor `.wikicommit/source/` contains it (`.wikicommit/source/` is a directory pathspec and does not match the sibling file `source-policy.md`). Without this pathspec a collect run in which the user declines every candidate stops at "No changes to merge" and the record of that decision is never committed — which defeats the whole point of the list, since the next free exploration re-proposes the source it was meant to remember. Like assets, this is a `.md` file that must **not** enter the `changed_md` list (Step 2): it is not a wiki page, and `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` would all fail on it. Step 2 classifies them as `policy_files`. The entity policy is there for the same reason one axis over — it is hand-edited prose deciding whether an entity may be written about at all, and `wikicommit-generate` acts on it, so a run in which the human edits only that file must not stop at "No changes to merge".
>
> The `.wikicommit/review/**/*.md` pathspec covers the review records — one immutable file per review, written by `record_review.py` under `.wikicommit/review/`. They are what makes "every page was reviewed" a checkable statement rather than an assertion, so a run whose records are never committed is indistinguishable from one where no review happened. Like assets and the policy files, these are `.md` files that must **not** enter the `changed_md` list (Step 2): they are not wiki pages, and `validate_frontmatter.py` / `check_wikilinks.py` would fail on them. Step 5's `git add` takes the directory.
>
> The `.wikicommit/relations.yml` pathspec covers the decisions `/wikicommit-relate` records about how two or more pages relate. A run that only records "these two are distinct" changes nothing else, and without this pathspec it would stop at "No changes to merge" — the decision would never be committed and the same pair would be raised again. It is not a wiki page and never enters `changed_md`; it is classified as `relations_file`.
>
> Note also that `lychee` is invoked with an explicit path argument (Step 3) — the changed pages only — so it does not walk this tree: a record's `source_file` can hold a URL, and an unscoped run would re-fetch every one of them on every merge.
>
> `git diff --name-only HEAD` does not detect untracked files. Wiki pages and management files newly generated by `wikicommit-generate` are untracked (not yet `git add`-ed), so use `git status --porcelain` instead (it lists untracked files too, in `?? path` form).
>
> The scripts read `git status --porcelain -z`. By default, paths containing non-ASCII characters (e.g. Japanese filenames), spaces or quotes are quoted and escaped in the output, and naively extracting them as `rest = line[3:]` yields a path string that doesn't actually exist; `-z` (which `core.quotePath=false` alone does not replace — it covers only non-ASCII) prints every path as it is.

and kept the paths as the run record's `changes` list. When it was empty the workflow engine finished the run with "No changes to merge" and you never reached this step: that is the Skill finding nothing to do and saying so, which is a run that finished, so it is not left open to fill `check_run_records.py`'s `INCOMPLETE_RUN:` list with runs that had no problem. The pathspecs above are the reason each kind of file is in or out of the lists below.

### Step 2: Classify Changed Files (the workflow engine's `classify-*` steps)

`workflow_checks.py classify` has put each list in the run record, under its own name. Read them from there (`python <this Skill's directory>/scripts/workflow_checks.py list --run <run> --list <name>`), never by running `git status` again:

| List | What it holds |
|---|---|
| `changed_md` | changed wiki pages (`.wikicommit/entity/**/*.md`, `.wikicommit/view/**/*.md`) that are on disk — deleted files (`D`) are left out. The only list the per-file checks read |
| `removing` | pages in `changed_md` that say `status: removed` now and did not at `HEAD` |
| `new_sources` | the actual source files behind changed source management files (`source.type: path`), only when untracked (for a directory `source.path`, the untracked files in it, never the directory itself). A missing or gitignored `source.path` is reported in `notes` as a `WARNING:` and left out |
| `new_schema` | untracked type files under `.wikicommit/schema/`. An edit to a committed one is reported and left out |
| `new_vocab` | `.wikicommit/schemaorg-vocab.json`, only when it was built for the first time |
| `policy_files` | `.wikicommit/source-policy.md` / `.wikicommit/entity-policy.md` when changed at all |
| `relations_file` | `.wikicommit/relations.yml` when changed at all |

### Step 3: Quality Checks

The workflow engine's `quality-checks` step has already run, in this order, `validate_frontmatter.py`, `check_wikilinks.py --changed …` and `check_raw_html.py` over `changed_md`, `check_wikilinks.py --deleted …` over `removing` (links other pages still make to a page being removed), then `check_orphans.py`. With an empty `changed_md` (an assets-only run, or one that only rewrote management files) it skipped the three per-file checks, because each reads "no paths" as "every page in the wiki". A script printing `ERROR:` (or `DUPLICATE:` for `check_orphans.py`) blocks; `WARNING:` and `ORPHAN:` are warnings, recorded for the PR body.

| Script / tool | Blocking condition | Warning only |
|---|---|---|
| `validate_frontmatter.py` | Any `ERROR:` output | Any `WARNING:` output |
| `check_wikilinks.py` | Any `ERROR:` output | Any `WARNING:` output |
| `check_raw_html.py` | Any `ERROR:` output (raw HTML tag detected in page body) | Any `WARNING:` output |
| `lychee` | None (always warning only) | HTTP 4xx, timeouts, connection errors |
| `markdownlint-cli2` | None (always warning only) | All violations |
| `check_orphans.py` | Any `DUPLICATE:` output (duplicate pages) | Any `ORPHAN:` output |

You only get here when `changed_md` has at least one page: with an empty `changed_md` there is nothing for lychee or markdownlint to read, and the workflow engine skips this step itself (its `when:` condition).

Run the two remaining checks from the repository root.

**1. lychee — the external links of the changed pages only.** Run this, and **run it again while it prints `LINKS: more`**, until it prints `LINKS: done`:

```bash
python <this Skill's directory>/scripts/workflow_checks.py links --run <run>
```

Each call checks a few pages at a time and returns within about 100 seconds, however many pages changed, so it stays inside the shell's time limit; what it has checked is kept beside the run, so the next call continues where the last stopped (also after a compaction). Do not run `lychee` yourself, and do not put the call in the background: the wrapper scopes lychee to the changed pages — never the whole of `.wikicommit/`, where review and run records hold URLs that would all be fetched again — runs it with `--cache`, and records its findings for the PR body. A missing `lychee` is recorded as a warning, not an error.

**2. markdownlint-cli2 — piped into the recorder:**

```bash
python <this Skill's directory>/scripts/workflow_checks.py list --run <run> --list changed_md -0 \
  | xargs -0 -- npx markdownlint-cli2 --config .markdownlint.json 2>&1 \
  | python <this Skill's directory>/scripts/workflow_checks.py style --run <run>
```

Run it as a direct shell pipeline exactly as shown. `-0` and `xargs -0` keep a path with a space in one piece, and `xargs` keeps a long list under the command-line length limit. Do not write a Python `subprocess` wrapper around `npx` instead: on Windows `npx` is `npx.cmd`, which `subprocess.run(['npx', ...])` cannot start without a shell (`FileNotFoundError`). `2>&1` matters — markdownlint-cli2 prints its findings and its `Summary:` line on stderr, and output with neither is recorded as "did not run" rather than as a clean pass.

Then report `checked`. If the check refuses it, its reason names which of the two is not recorded yet.

The findings stay beside the run, where `workflow_checks.py pr-body` reads them. Carry the warning list forward to Step 6 that way, never in memory: it survives a compaction, and the next step reads it from there.

**Warnings never stop the run here.** When any tool recorded one, the workflow engine's next step asks the user whether to proceed (a `human` step), and if they choose not to, the run finishes with no branch created and the working tree as it is. **In a non-interactive run, where no answer will arrive, do not abort — record the warnings and proceed**: the workflow engine answers `proceed` itself, and that is the right default for warnings specifically:

- **The confirmation is not the gate on whether this may merge.** Every warning this step can produce — orphan, unresolved WikiLink, lychee, markdownlint — is mergeable by design (see the table above); the confirmation only shows a person the warnings, it does not decide the outcome.
- **Little is lost by no one seeing them at this moment.** `ORPHAN:` and unresolved WikiLinks are standing state that `/wikicommit-status` reports until fixed, and lychee and markdownlint findings come back the moment the same checks run again. The PR body makes them durable rather than transient; it does not make anyone read them (Step 7 auto-merges seconds later).

**Blocking is untouched.** `ERROR:` and `DUPLICATE:` still abort the run (it halts), interactive or not — and they halt it before a branch exists, so the working tree is left as-is for a later run.
