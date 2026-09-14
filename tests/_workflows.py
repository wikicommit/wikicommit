"""Where the workflow files live, for the guards that check them.

Two directories, and **the publication boundary runs between them**: the
distributed templates under `.claude/skills/` are in the published subset, while
`.github/` is on the permanent-exclusion list (`dev/scripts/snapshot_push.sh`'s
`FORBIDDEN_PATHS`). A guard that walks both therefore sees a different set in
the published snapshot, and that is correct rather than a hole — but the absence
of a file must not itself be the signal. `test_workflow_template_expressions.py`
carries that half for everyone: its two "were found" tests pair
`_publication.skip_unless_development_repository()` with an assertion that the
inputs of each directory are present, so a path constant that breaks turns those
red rather than quietly emptying every parametrize built on this module
(see `_publication.py`). Guards added here do not need to restate it.

Shared rather than copied because two guards now walk the same set
(`test_workflow_template_expressions.py` — the dependency-free check for empty
expressions, Issue #830 — and `test_workflow_actionlint.py` — the broader
upstream linter, Issue #862) and the two are explicitly meant to cover the same
files at different depths. Two copies of the discovery would drift, and the way
that drift shows up is the worst one available here: the narrower guard keeps
passing while the broader one silently stops looking at a file.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

TEMPLATE_WORKFLOWS = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "workflows"
)
REPO_WORKFLOWS = REPO_ROOT / ".github" / "workflows"

WORKFLOW_DIRECTORIES = (TEMPLATE_WORKFLOWS, REPO_WORKFLOWS)


def workflow_files() -> list[Path]:
    """Every workflow file in both directories, sorted, skipping missing dirs."""
    paths: list[Path] = []
    for directory in WORKFLOW_DIRECTORIES:
        if directory.is_dir():
            paths.extend(sorted(directory.glob("*.yml")))
            paths.extend(sorted(directory.glob("*.yaml")))
    return paths


def names_in(directory: Path) -> set[str]:
    """Names of the workflow files found directly in `directory`."""
    return {path.name for path in workflow_files() if path.parent == directory}
