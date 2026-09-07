#!/usr/bin/env python3
"""Detect internal vocabulary leaking into a Skill's user-facing output templates (#588).

docs/DesignDoc-skills.md §11.8 says a Skill's confirmation prompts and
completion messages must not expose its own internal step numbers (`Step N` /
`Pass N`), design vocabulary (`Route A` / `Route B`), or internal tracker
references (`Issue #NNN` / `PR #NNN`). None of those reach the user: `docs/`
is not part of the distribution snapshot, and an Issue number points into a
repository the user cannot open at all.

§11.8 existed as prose only, and prose alone did not hold — the rule was added
in one Issue and a later one introduced a fresh violation into
wikicommit-status's result template. This script is the regression guard the
prose could not be.

What it scans: fenced code blocks in .claude/skills/wikicommit-*/SKILL.md whose
info string is absent or `markdown` — those are the blocks a Skill prints to
the user verbatim. Blocks tagged `bash`/`json`/`yaml` (and any other language)
are commands and data formats, not user-facing prose, and are skipped.

Known limitation, deliberately not addressed here: this only sees text that
lives in a template. The leak that prompted §11.8 in the first place was an
agent composing its own confirmation question and pulling "Step 5" out of the
surrounding instruction prose — wording that appears in no template and that
this script therefore cannot see. Guardrails in the prose instructions remain
necessary; CI complements them rather than replacing them.

Marking an exception: put an HTML comment on the line immediately before the
fence, naming a reason.

    <!-- skill-vocabulary-exception: PR body, read by developers and reviewers -->

A marker with no reason after the colon is itself an error, so adding one means
consciously restating why §11.8's exception applies.

Usage:
    python tools/check_skill_user_facing_vocabulary.py

Exit code: 0 = clean, 1 = at least one leak (blocking).
"""

import re
import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")

# Info strings whose blocks are user-facing prose. Everything else (bash, json,
# yaml, ...) is a command or a data format.
USER_FACING_INFO_STRINGS = {"", "markdown", "md", "text"}

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")

PATTERNS = [
    ("internal step number", re.compile(r"\bPass ?\d[a-c]?\b")),
    ("internal step number", re.compile(r"\bStep \d+\b")),
    ("internal design vocabulary", re.compile(r"\bRoute [AB]\b")),
    ("internal tracker reference", re.compile(r"\bIssue #\d+\b")),
    ("internal tracker reference", re.compile(r"\bPR #\d+\b")),
]

EXCEPTION_RE = re.compile(r"<!--\s*skill-vocabulary-exception:\s*(.*?)\s*-->")


def collect_skill_md_files() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    # wikicommit-* only: the internal-only Skills (implement-issue,
    # review-and-merge) are developer tools, and their reader is the developer
    # running them.
    return sorted(SKILLS_DIR.glob("wikicommit-*/SKILL.md"))


def iter_user_facing_blocks(lines: list[str]):
    """Yield (start_line_number, [(line_number, text), ...]) per user-facing block.

    Closing a fence requires a marker at least as long as the opening one and of
    the same character, so a ```` ``` ```` nested inside a ```` ```` ```` block
    does not end it — SKILL.md templates do embed fenced examples.
    """
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        fence, info = m.group(2), m.group(3).strip()
        start = i
        i += 1
        body: list[tuple[int, str]] = []
        closed = False
        while i < len(lines):
            close = FENCE_RE.match(lines[i])
            if (
                close
                and close.group(3).strip() == ""
                and close.group(2)[0] == fence[0]
                and len(close.group(2)) >= len(fence)
            ):
                closed = True
                i += 1
                break
            body.append((i + 1, lines[i]))
            i += 1
        # An unterminated fence is not this script's problem to report, but its
        # body should not be scanned as if it were a block either.
        if not closed:
            continue
        first_word = info.split()[0].lower() if info else ""
        if first_word in USER_FACING_INFO_STRINGS:
            yield start, body


def preceding_exception_reason(lines: list[str], fence_index: int) -> str | None:
    """Return the reason from a marker on the line just before the fence.

    Returns "" (falsy but not None) when the marker is present with no reason,
    so the caller can tell "no marker" from "marker without a reason".
    """
    for j in range(fence_index - 1, -1, -1):
        if lines[j].strip() == "":
            continue
        m = EXCEPTION_RE.search(lines[j])
        return m.group(1) if m else None
    return None


def main() -> int:
    errors = 0
    checked = 0
    exceptions = 0

    for skill_md in collect_skill_md_files():
        lines = skill_md.read_text(encoding="utf-8-sig").splitlines()
        for fence_index, body in iter_user_facing_blocks(lines):
            checked += 1
            reason = preceding_exception_reason(lines, fence_index)
            if reason is not None:
                if not reason:
                    print(
                        f"ERROR: {skill_md}:{fence_index + 1}: skill-vocabulary-exception marker has no "
                        "reason. State why this block's reader is a developer or reviewer rather than a "
                        "user (docs/DesignDoc-skills.md §11.8)."
                    )
                    errors += 1
                else:
                    exceptions += 1
                continue
            for line_no, text in body:
                for label, pattern in PATTERNS:
                    for match in pattern.finditer(text):
                        print(
                            f"ERROR: {skill_md}:{line_no}: {label} \"{match.group(0)}\" in a user-facing "
                            "output template. Describe the state and the next action in plain words "
                            "instead (docs/DesignDoc-skills.md §11.8)."
                        )
                        errors += 1

    print(f"SUMMARY: blocks={checked}, exceptions={exceptions}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
