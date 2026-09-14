#!/usr/bin/env python3
"""Warn when a Skill's instructions grow past what is reasonable to load on
every invocation.

Two metrics, because one number cannot answer both questions (Issue #887):

    instruction surface   every instruction `.md` the Skill can reach, in bytes
                          — what the Skill costs to follow, and the figure that
                          cannot be gamed by moving prose into a sibling file
    SKILL.md body         the entry file alone, in lines and bytes — what is
                          loaded whether or not anything else is read, and the
                          figure Anthropic's ~500-line guidance is about

Reading them as a pair is the point. `body ↓` with `surface →` means a Skill was
split; `body ↓` with `surface ↓` means prose was actually removed. Before this,
only the body was measured, so the first of those was indistinguishable from the
second — splitting a file looked like shrinking it.

## Why bytes for the surface

The line count was a proxy for token cost, and a poor one here: measured across
this repository's Skills, `.md` density runs 41–166 bytes per line, a 4.0x
spread. One Skill sat at 75% of another's byte count while passing the line
guard because its lines were longer. Bytes track the cost directly.

The threshold is **40,000 bytes**, and it is chosen from two directions that
agree:

- **Token cost.** At roughly 4 bytes per token for this kind of prose, that is
  about 10,000 tokens — a reasonable ceiling for what one Skill should claim of
  a conversation on its own.
- **The observed distribution.** Across 19 Skills the largest below this line is
  28,777 bytes and the smallest above it is 41,223, so the threshold falls in a
  1.4x gap rather than cutting through a cluster.

**The threshold is deliberately not tied to a compaction window.** A harness may
re-attach only the first N tokens of a Skill after compacting, but that number
belongs to one harness at one version; token cost is true everywhere. See
docs/DesignDoc-skills.md section 11.6, which draws the same line.

## What counts as instruction surface

Every `.md` under the Skill's directory, including `SKILL.md`. `scripts/` holds
`.py` and drops out on its own. Two exclusions are deliberate:

- **`CHANGELOG.md` and `changelog/`** (in `wikicommit-init`) — a distribution
  payload carried so that it reaches an installed wiki repository. It is never
  instructions to an agent.
- **`scripts/templates/`** — files expanded into a wiki repository, not read
  from here. Some of them (`review-rules.md`, `schema-authoring.md`) *are* read
  by Skills, but at their installed `.wikicommit/` paths and by **several**
  Skills at once, so they cannot be charged to any one of them. They are out of
  scope for this metric, and a Skill that leans on one is measured lighter than
  it runs.

## The limit this metric does not see

**It does not distinguish "moved to another file" from "moved to another
context."** A file read into the same conversation still costs what it says; a
subagent's prompt does not appear in the parent's context at all. Both look
identical here — a second `.md` in the directory — so a Skill that delegates
work to a subagent measures **higher than it actually costs**. Nothing static
can tell the two apart, and a frontmatter marker saying which is which would be
a field with no consumer, so the metric is left as is and the caveat written
down instead.

Usage:
    python tools/check_skill_md_lines.py [--limit=40000] [--body-line-limit=500]

Exit code: always 0 (warning-only, non-blocking).
"""

import argparse
import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")

# Instruction surface, in bytes. See the docstring for how this number was
# chosen; it is a proxy for token cost, not for any harness's compaction window.
DEFAULT_LIMIT = 40_000

# The entry file alone, in lines — Anthropic's skill-creator guidance, kept at
# its original value and its original unit so that it still means what that
# guidance means.
DEFAULT_BODY_LINE_LIMIT = 500

# Not instructions: a distribution payload, and files expanded elsewhere.
EXCLUDED_NAMES = {"CHANGELOG.md"}
EXCLUDED_DIRS = {"changelog", "templates"}


def collect_skill_dirs() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists())


def instruction_files(skill_dir: Path) -> list[Path]:
    """Every instruction `.md` this Skill can reach, `SKILL.md` first.

    The single definition of "which `.md` under a Skill is instructions":
    `check_skill_output_language.py` and `check_skill_user_facing_vocabulary.py`
    import this rather than restating it, so the size metric and the two
    blocking scanners cannot come to disagree about what they are looking at.
    """
    found = []
    for path in sorted(skill_dir.rglob("*.md")):
        rel = path.relative_to(skill_dir)
        if path.name in EXCLUDED_NAMES:
            continue
        if EXCLUDED_DIRS & set(rel.parts):
            continue
        found.append(path)
    entry = skill_dir / "SKILL.md"
    return [entry] + [p for p in found if p != entry]


def main() -> int:
    parser = argparse.ArgumentParser(description="Warn on oversized Skill instructions.")
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT, metavar="N",
        help=f"Instruction-surface byte threshold (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--body-line-limit", type=int, default=DEFAULT_BODY_LINE_LIMIT, metavar="N",
        help=f"SKILL.md line threshold (default: {DEFAULT_BODY_LINE_LIMIT}).",
    )
    args = parser.parse_args()

    checked = 0
    over_surface = 0
    over_body = 0

    for skill_dir in collect_skill_dirs():
        checked += 1
        files = instruction_files(skill_dir)
        surface = sum(len(p.read_text(encoding="utf-8-sig").encode("utf-8")) for p in files)
        body_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8-sig")
        body_bytes = len(body_text.encode("utf-8"))
        body_lines = len(body_text.splitlines())

        surface_over = surface > args.limit
        body_over = body_lines > args.body_line_limit
        if surface_over:
            over_surface += 1
        if body_over:
            over_body += 1

        # One line per flagged Skill carrying *both* figures, even when only one
        # of them is over. Reading them as a pair is the whole point, and printing
        # the body figure only when it trips its own threshold would hide exactly
        # the case the pair exists to show: a Skill whose body dropped below the
        # line limit while its surface did not move is a Skill that was split.
        if surface_over or body_over:
            parts = [
                f"surface {surface} B ({'over' if surface_over else 'ok'} {args.limit})",
                f"SKILL.md {body_lines} lines ({'over' if body_over else 'ok'} "
                f"{args.body_line_limit}), {body_bytes} B",
            ]
            if len(files) > 1:
                others = ", ".join(p.relative_to(skill_dir).as_posix() for p in files[1:])
                parts.append(f"{len(files)} instruction files: SKILL.md + {others}")
            print(f"WARNING: {skill_dir}: " + "; ".join(parts))

    print(
        f"SUMMARY: checked={checked}, over_surface={over_surface}, "
        f"over_body_lines={over_body}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
