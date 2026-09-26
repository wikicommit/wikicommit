"""Where the installed WikiCommit Skill tree lives (Issue #1021).

The Skills are not always under `.claude/skills/`. Claude Code reads that directory, but
Codex reads `.agents/skills/` instead, and `npx skills add --agent codex` installs there
and nowhere else. Two scripts here read the Skill tree at run time — `record_run.py`
opens a pass file to check `--token`, and `check_distribution_freshness.py` compares
against the templates `wikicommit-init` ships — and both used to hard-code
`.claude/skills/`. With a Codex-only install the first recorded a correctly-read pass as
`token: missing` (the direction Issue #925 had just fixed for version skew), and the
second printed "wikicommit-init is not installed" and a clean all-zero summary, so the
version-skew check Issue #930 placed at the start of a run went silently blank.

The search order lives here, once, so the two scripts cannot drift apart. It is also
the only place a script needs it: instructions (`SKILL.md` and `references/`) are
written relative to the Skill's own directory, which every runtime hands the agent, and
a script inside a Skill finds its siblings through its own `__file__`. Only these
scripts — which run from `.wikicommit/scripts/` and look *into* the Skill tree — have no
such anchor.

`.claude/skills` is searched first. With `npx skills add --copy` for both agents the
two trees are copies from the same install and hold the same bytes, so the order does
not change the answer; when they do differ, the `.claude/skills` copy is the one Claude
Code runs, and preferring it keeps this script's answer the same as it was before
Issue #1021 for every repository that already worked.
"""

from pathlib import Path

SKILL_TREE_ROOTS = (Path(".claude") / "skills", Path(".agents") / "skills")


def skill_dirs(skill: str, repo_root: Path = Path(".")) -> list[Path]:
    """Every installed copy of `skill`, in search order (possibly empty)."""
    return [
        repo_root / root / skill
        for root in SKILL_TREE_ROOTS
        if (repo_root / root / skill).is_dir()
    ]


def find_skill_dir(skill: str, repo_root: Path = Path(".")) -> Path | None:
    """The first installed copy of `skill` in search order, or None."""
    found = skill_dirs(skill, repo_root)
    return found[0] if found else None
