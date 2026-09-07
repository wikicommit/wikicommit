#!/usr/bin/env python3
"""Warn when a .claude/skills/*/SKILL.md exceeds a recommended line count.

Anthropic's skill-creator guidance recommends keeping SKILL.md under ~500
lines and moving deterministic, repetitive logic into scripts/ instead
(see docs/DesignDoc-skills.md section 11.5). This script is a dev-only
early warning for that guidance; it is not part of the .wikicommit/scripts/
suite distributed to wiki repositories.

Usage:
    python tools/check_skill_md_lines.py [--limit=500]

Exit code: always 0 (warning-only, non-blocking).
"""

import argparse
import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")
DEFAULT_LIMIT = 500


def collect_skill_md_files() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Warn on oversized SKILL.md files.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, metavar="N",
                         help=f"Line count threshold (default: {DEFAULT_LIMIT}).")
    args = parser.parse_args()

    over_limit_count = 0
    checked_count = 0

    for skill_md in collect_skill_md_files():
        checked_count += 1
        line_count = len(skill_md.read_text(encoding="utf-8-sig").splitlines())

        if line_count > args.limit:
            print(f"WARNING: {skill_md}: {line_count} lines (limit: {args.limit})")
            over_limit_count += 1

    print(f"SUMMARY: checked={checked_count}, over_limit={over_limit_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
