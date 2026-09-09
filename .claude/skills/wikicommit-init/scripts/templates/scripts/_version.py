"""WikiCommit's own version string — the one source of truth that reaches an
installed wiki repository (Issue #577).

WikiCommit is distributed across three repositories: this development
repository, the public distribution repository (a single squashed commit per
sync, carrying no development history), and the user's wiki repository. Two
consequences shape where the version can live:

- `git tag` is not usable. The distribution repository is built with
  `git archive` and never inherits this repository's history, so a tag would
  have to be re-applied by hand on the distribution side and could drift from
  the version this repository believes it shipped.
- `.claude-plugin/plugin.json` never reaches the user's wiki repository.
  `install.sh` copies only the `SKILLS` directories, and `npx skills add`
  installs per Skill directory; the manifest sits at the distribution
  repository's root and is left behind. So `init.py` cannot read the version
  from it when stamping `.wikicommit/config.yml`.

That leaves the Skill tree itself. This module lives under
`wikicommit-init/scripts/templates/scripts/`, which `init.py` expands into
`.wikicommit/scripts/`, so the version travels all the way to the installed
repository. It follows the same "shared module several scripts import"
convention as `_frontmatter.py` / `_wikilink.py` / `_schemaorg_vocab.py`.

`.claude-plugin/plugin.json`'s `version` field carries the same number for
Claude Code's plugin machinery, which cannot see this file.
`tests/test_version_sync.py` fails when the two drift apart — the same
"enforce content equality in CI rather than generating one from the other"
pattern used by `tests/test_skill_distribution_list_sync.py`.

This version is unrelated to `pyproject.toml`'s `version`, which declares the
development repository's own Python package for its test/lint dependencies.
Nothing keeps them equal and nothing should: `pyproject.toml` sets
`packages = []` so it is not a distributed package, nothing in the repository
reads its `version`, and what bumps *this* version — a change to a type template
or a page generation rule — has no bearing on a test/lint dependency
declaration. They have in fact diverged (this file has moved on while
`pyproject.toml` stayed at its initial number), which is the expected outcome
rather than drift to repair.

Consumers:
- `init.py` — stamps `wikicommit_version` into `.wikicommit/config.yml`
- `wikicommit-generate` Pass 3 — writes `generated_with` on generated pages
- `wikicommit-synthesize` — writes `generated_with` on synthesized pages
- `wikicommit-translate` — writes `translated_with` on translation pages
- `record_review.py` — stamps `wikicommit_version` on each review record
  (imports `get_version()` directly rather than shelling out, being a
  sibling module in the same directory)

Skills read it by running this file directly:

    python .wikicommit/scripts/_version.py
"""

# Semantic version of WikiCommit itself (the Skills and the templates they
# expand). Bump this together with `.claude-plugin/plugin.json`'s `version`
# and a new `CHANGELOG.md` entry; the CHANGELOG entry is what tells a user
# which pages are worth regenerating, since the version alone is coarser than
# the per-type template changes it stands for.
VERSION = "0.5.0"


def get_version() -> str:
    """Return WikiCommit's version string."""
    return VERSION


if __name__ == "__main__":
    print(VERSION)
