---
pass_token: "2c1afb95"
---

# Steps 4–5: branch and commit (`commit`)

Make the branch and the one commit that carries this run's changes. The workflow engine's check then confirms, on disk, that you are on a `wikicommit/merge-*` branch with a commit beyond `<default branch>` (the run record's `default_branch` list) and that **none of the changes `detect` found is still uncommitted** — so a `git add` that silently staged nothing is caught here, before anything is pushed. Report `committed`; report `halted` with `--reason` only if the branch or the commit could not be made at all.

Step 2's lists are in the run record: the workflow engine handed them over with this step (`lists`: `new_sources`, `new_schema`, `new_vocab`, `policy_files`, `relations_file`), and `python <this Skill's directory>/scripts/workflow_checks.py list --run <run> --list <name>` prints any of them again — after a compaction or in a resumed session too. Use them as they are; do not work them out again from `git status`.

If a resumed run finds the branch already made (the current branch is a `wikicommit/merge-*` branch), do not make a second one: commit on it if nothing is committed yet, or report `committed` if the commit is already there.

### Step 4: Create Branch

```bash
git checkout -b wikicommit/merge-$(date +%Y%m%d-%H%M%S)
```

Branch naming rule (exception): use the form `wikicommit/merge-<YYYYMMDD>-<HHMMSS>`. CLAUDE.md's `issue-NNN` convention is for issue-driven development branches and does not apply to the temporary branches this skill auto-generates.

### Step 5: Commit

```bash
git add -- .wikicommit/entity/ .wikicommit/view/ .wikicommit/source/ .wikicommit/review/ <new source files...> <new schema files...> <new vocab file> <policy files...> <relations file>
git commit -m "$(cat <<'EOF'
wiki: bulk update <YYYY-MM-DD>

<Co-Authored-By line>
Generated-By:   <current model ID>
EOF
)"
```

<!-- commit-trailers:start (this block is identical in wikicommit-merge, -schema-propose, -update, -init and -organize; tests/test_commit_trailer_vendor_table.py holds them together) -->
**Commit trailers.** Always write `Generated-By:   <current model ID>`: the ID of the model actually running this Skill, exactly as the runtime reports it — the same self-reported value `wikicommit-generate` writes into a page's `generated_by` (keep any suffix; do not shorten or normalize it; never hardcode one). Then choose `<Co-Authored-By line>` from the start of that same ID, so the two lines can never name different vendors:

| `<current model ID>` starts with | `<Co-Authored-By line>` |
|---|---|
| `claude-`, or `claude-` after a provider prefix ending in `anthropic.` (Bedrock, e.g. `us.anthropic.claude-…`) | `Co-Authored-By: <Claude display name> <noreply@anthropic.com>` — the model's human-readable name, or just `Claude` when it is not known with confidence |
| `gpt-` or `codex` | `Co-Authored-By: Codex <noreply@openai.com>` |
| anything else | **no `Co-Authored-By` line at all** — `Generated-By` already records the model |

GitHub resolves a co-author by the email address and shows that vendor's avatar on the commit, so a line naming a vendor that did not run this Skill misattributes it; writing none is the correct answer for a model not in the table. Decide by the model, not by the harness running it — one harness can run models from more than one vendor. If the harness appends its own co-author line after this message, leave it; an identical duplicate does no harm.
<!-- commit-trailers:end -->

Replace `<YYYY-MM-DD>` with the output of `date +%Y-%m-%d` (use the same date in both the commit message title and body). Pass each path in `new_sources` as a separate argument prefixed with `:(literal)` for `<new source files...>` (e.g. `:(literal)raw/report[2024].pdf`; omit if there are none): without the prefix, a path containing glob metacharacters can accidentally stage an unrelated file (`[2024]` is read as a character class). Pass each path in `new_schema` for `<new schema files...>` the same way (omit if there are none) — these are always plain `.wikicommit/schema/<Type>.md` paths, but using `:(literal)` uniformly costs nothing. Pass `new_vocab` for `<new vocab file>`, each path in `policy_files` for `<policy files...>`, and `relations_file` for `<relations file>` verbatim, each as its own argument (omit any that is empty) — these are fixed literal paths (`.wikicommit/schemaorg-vocab.json`, `.wikicommit/source-policy.md`, `.wikicommit/entity-policy.md`, `.wikicommit/relations.yml`).

**Drop any of the four `.wikicommit/` directories that does not exist on disk.** `git add` treats a pathspec matching nothing as fatal and aborts the *whole* invocation — nothing is staged, and the commit that follows has no content — so listing them unconditionally would break every merge on a wiki that has one of them missing. That is not a hypothetical: `.wikicommit/review/` is created by `/wikicommit-init`, so a repository that updated its Skills (`npx skills add`) without re-running init does not have it, and a repository initialized by an older version may lack `.wikicommit/view/`. Check each with a plain directory test and pass only the ones present — or, for one that is gone from disk, still tracked (`git ls-files -- <dir>` prints something), since its deletions are changes `detect` found and the check below refuses a commit that leaves them unstaged. The ones you drop are, by definition, directories with nothing to stage.
