#!/usr/bin/env python3
"""Surface .claude/skills/*/SKILL.md that don't set disable-model-invocation (#234).

**What the flag stops is wider than "automatic trigger judgment" (Issue #945).**
The official documentation names three things: a description-matched autoload,
preloading into subagents, and a scheduled task firing with the Skill as its
prompt. It does *not* say the flag blocks an explicit invocation through the
Skill tool — but that is blocked too, by a separate mechanism: a flagged Skill is
not listed to the model at all, so its name is not among the ones the Skill tool
accepts. Keep those two apart when describing the flag. The accurate summary is
that setting it leaves exactly one path open — a person typing `/name`.

Whether a Skill should set it is therefore a judgment call with two halves, and
this script does not attempt to make either. The first is the original one: does
it have side effects — git/gh writes, filesystem mutations outside a sandbox —
that shouldn't fire from an agent's own automatic trigger judgment? The second
stayed invisible while only the first was being asked: does this Skill ever need
to run with no person at the keyboard? If it does, the flag is the wrong
instrument for the first half, because it closes the unattended path as well. The
narrower one is `skillOverrides` in `.claude/settings.json`, which the operator of
a given repository holds rather than the distribution (docs/DesignDoc-skills.md
§11.1).

This script only lists every Skill currently without the field set, as a
non-blocking reminder for reviewers to consciously confirm that omission is
still correct — most relevant when a PR adds a new
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
