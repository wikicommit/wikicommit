#!/usr/bin/env python3
"""Surface .claude/skills/*/SKILL.md that don't set disable-model-invocation (#234).

Whether a Skill should set `disable-model-invocation: true` is a judgment call
(does it have side effects — git/gh writes, filesystem mutations outside a
sandbox — that shouldn't fire from an agent's own automatic trigger judgment?)
that this script does not attempt to make. It only lists every Skill currently
without the field set, as a non-blocking reminder for reviewers to consciously
confirm that omission is still correct — most relevant when a PR adds a new
SKILL.md (see docs/DesignDoc-skills.md §11.5, CONTRIBUTING.md "SKILL.md を
変更する場合の追加手順").

Usage:
    python tools/check_skill_invocation_mode.py

Exit code: always 0 (informational only, non-blocking).
"""

import sys
from pathlib import Path

import yaml

SKILLS_DIR = Path(".claude/skills")


def collect_skill_md_files() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def has_disable_model_invocation(skill_md: Path) -> bool:
    text = skill_md.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    frontmatter = yaml.safe_load(text[3:end])
    if not isinstance(frontmatter, dict):
        return False
    return frontmatter.get("disable-model-invocation") is True


def main() -> int:
    unset_count = 0
    checked_count = 0

    for skill_md in collect_skill_md_files():
        checked_count += 1
        if not has_disable_model_invocation(skill_md):
            print(f"INFO: {skill_md}: disable-model-invocation not set (auto-invocation enabled)")
            unset_count += 1

    print(f"SUMMARY: checked={checked_count}, unset={unset_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
