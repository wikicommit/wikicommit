#!/usr/bin/env python3
"""Detect fixed `.claude/skills/<name>/…` paths in the distributed Skills' instructions.

The Skills are installed under `.claude/skills/` for Claude Code but under
`.agents/skills/` for Codex (`npx skills add --agent codex` creates no `.claude/skills/`
at all). An instruction that names `.claude/skills/wikicommit-generate/references/…`
from the repository root therefore resolves in one install and not the other — and
since Issue #911 moved every Pass of `/wikicommit-generate` behind such a pointer, a
Codex-only install could not enter Pass 1 (Issue #1021). The fix writes those paths
relative to the Skill's own directory (`references/…`, `scripts/…`) or to its siblings
(`../wikicommit-init/…`), which both runtimes resolve because both tell the agent where
the Skill it loaded lives.

Nothing stopped the count from growing: 22 places when Issue #732 first counted them,
57 when Issue #1021 did. This check is what stops it now.

Scope: every `.md` under the distributed Skills (the list is imported from
`check_distributed_path_refs.py`, which `tests/test_skill_distribution_list_sync.py`
already keeps in step with `install.sh`, so no third copy is made). Two exclusions:

- `CHANGELOG.md` and `changelog/` — records of what changed, not instructions.
- `scripts/templates/guides/` — hand-run guides a *person* follows from the repository
  root after init copies them into `.wikicommit/guides/`. A Skill-relative path means
  nothing there; they name `.claude/skills/` and say where the Codex copy is instead.

A line that names `.agents/skills` alongside `.claude/skills/<name>` is also allowed: it
is describing the two locations, not assuming one of them. A generic mention of the
directory (`.claude/skills/` with nothing after it, or `.claude/skills/<name>` with a
placeholder) is not a path into a Skill and is not matched.

Usage:
    python tools/check_skill_tree_paths.py

Exit code: 1 if any ERROR, else 0.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_distributed_path_refs import DISTRIBUTED_SKILLS, SKILLS_DIR  # noqa: E402

FIXED_SKILL_PATH_RE = re.compile(r"\.claude/skills/[A-Za-z0-9_-]")


def collect_files() -> list[Path]:
    files: list[Path] = []
    for name in DISTRIBUTED_SKILLS:
        root = SKILLS_DIR / name
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            rel_parts = path.relative_to(root).parts
            if path.name == "CHANGELOG.md" or "node_modules" in rel_parts:
                continue
            if "changelog" in rel_parts:
                continue
            if rel_parts[:3] == ("scripts", "templates", "guides"):
                continue
            files.append(path)
    return sorted(files)


def main() -> int:
    errors = 0
    files = collect_files()
    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if ".agents/skills" in line:
                continue
            for match in FIXED_SKILL_PATH_RE.finditer(line):
                start = match.start()
                snippet = line[start:start + 60].split("`")[0].split()[0]
                print(
                    f"ERROR: {path}:{lineno}: fixed Skill-tree path {snippet!r} — write it "
                    "relative to this Skill's directory (references/…, scripts/…) or to a "
                    "sibling Skill (../wikicommit-…/…), since the Skills may be installed "
                    "under .agents/skills/ (Issue #1021)"
                )
                errors += 1
    print(f"SUMMARY: checked={len(files)}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
