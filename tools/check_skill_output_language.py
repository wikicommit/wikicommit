#!/usr/bin/env python3
"""Detect Japanese-fixed strings in a Skill's user-facing output (Issue #808).

Issues #770, #772 and #773 settled the same question three times, and the answer
is always "the language follows the reader":

    operator / agent (a diagnostic)  -> fixed English          (#770)
    reader / reporter               -> the wiki's primary_lang (#773)
    user (the distribution itself)  -> English                 (#772)

Issue #824 later narrowed the middle row for one surface: `/wikicommit-fix`
Step 7's completion comment renders in the target page's own `lang`, not
`primary_lang`, because its reader is the one reporter who read that page. That
refinement does not touch this script -- neither answer is "Japanese hard-coded
into a SKILL.md", which is the only thing scanned for here.

What none of those rules produces is Japanese hard-coded into a SKILL.md. Issue
#808 nevertheless found six such places, so the rule held only as long as
someone happened to look. This script is the guard that prose alone was not.

What it scans: every line of .claude/skills/wikicommit-*/SKILL.md -- both prose
and fenced blocks. Restricting it to fenced blocks (as
check_skill_user_facing_vocabulary.py does) would have caught one of #808's six
findings; the other five were quoted strings sitting in ordinary instruction
prose. The internal-only Skills (implement-issue, review-and-merge) are excluded
for the same reason that script excludes them: their reader is the developer
running them.

What it looks for: Japanese sentence punctuation and corner brackets
(``。、？！「」``). It deliberately does *not* flag CJK characters as such. A
SKILL.md is full of legitimate Japanese **example data** -- page titles, entity
names, search terms, source quotes -- and CJK alone cannot tell
``"生年を1981年に修正して"`` (an example argument) from
``"対象言語がありません。"`` (an error message this Skill actually prints).
Sentence punctuation can: emitted Japanese prose carries it, and a title or a
query term does not. Measured against Issue #808's own findings, this rule
flagged five of the six with zero false positives on the example data.

Known limitation, stated rather than papered over: a Japanese **label** with no
sentence punctuation is invisible here. #808's ``要確認:`` (a finding label
printed next to ``OK``) is exactly that, and nothing short of understanding the
line would separate it from the example data around it. This is the same class
of limitation check_skill_user_facing_vocabulary.py records about prose the
agent composes itself: CI narrows where the rule can silently rot, it does not
close it.

Marking an exception: put an HTML comment naming a reason either on the flagged
line itself or on the nearest preceding non-blank line.

    <!-- skill-language-exception: verbatim source text quoted as an example -->

A marker with no reason after the colon is itself an error, so adding one means
consciously restating why the Japanese belongs there.

The marker is matched per line, which leaves one sharp edge worth knowing before
you hit it: a Japanese line *inside a fenced block* cannot be excused from
outside the fence, because the nearest preceding non-blank line is another line
of the block rather than the fence opener. Putting the marker inside the fence
does silence this check, but the fenced blocks here are output templates a Skill
emits verbatim, so the comment would be printed to the user along with the rest
of the template. In that position the fix is to reword the example so it carries
no Japanese sentence punctuation (a page title or a search term is already fine
as-is) rather than to add a marker. check_skill_user_facing_vocabulary.py does
not share this edge because its markers are anchored to the line before the
fence opener and cover the whole block.

Usage:
    python tools/check_skill_output_language.py

Exit code: 0 = clean, 1 = at least one hard-coded Japanese string (blocking).
"""

import re
import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")

# Japanese sentence punctuation and corner brackets. See the module docstring
# for why this is the signal rather than "any CJK character".
JAPANESE_PROSE_RE = re.compile(r"[。、？！「」]")

EXCEPTION_RE = re.compile(r"<!--\s*skill-language-exception:\s*(.*?)\s*-->")


def collect_skill_md_files() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(SKILLS_DIR.glob("wikicommit-*/SKILL.md"))


def exception_reason(lines: list[str], index: int) -> str | None:
    """Return the reason from a marker on this line or the nearest one above it.

    Returns "" (falsy but not None) when a marker is present with no reason, so
    the caller can tell "no marker" from "marker without a reason".
    """
    m = EXCEPTION_RE.search(lines[index])
    if m:
        return m.group(1)
    for j in range(index - 1, -1, -1):
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
        checked += 1
        for index, text in enumerate(lines):
            match = JAPANESE_PROSE_RE.search(text)
            if not match:
                continue
            reason = exception_reason(lines, index)
            if reason is not None:
                if not reason:
                    print(
                        f"ERROR: {skill_md}:{index + 1}: skill-language-exception marker has no "
                        "reason. State why Japanese belongs on this line -- example data, or a "
                        "quotation -- rather than being a string this Skill prints."
                    )
                    errors += 1
                else:
                    exceptions += 1
                continue
            print(
                f"ERROR: {skill_md}:{index + 1}: Japanese prose \"{match.group(0)}\" in a Skill's "
                "output. The language follows the reader: fixed English for an operator or agent "
                "(Issue #770), the wiki's primary_lang for a reader or reporter (Issue #773). "
                "If this is example data, mark it with skill-language-exception and say why."
            )
            errors += 1

    print(f"SUMMARY: files={checked}, exceptions={exceptions}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
