"""The commit-trailer rule is one rule, written four times (Issue #1019).

`wikicommit-merge`, `-schema-propose`, `-update` and `-init` (its foundation
commit) each carry the trailer paragraph, because each commits on its own and
the paragraph is short enough to keep beside the command it governs (the
Issue #875 threshold for moving shared prose into a data file is not met).
Four copies drift, and the drift is silent — one Skill would go on naming a
vendor that did not run it while the others have stopped. So the four blocks
are held equal here, whitespace-indentation aside (the `init` copy sits inside
a numbered list item).
"""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).parent.parent / ".claude" / "skills"
COPIES = ("wikicommit-merge", "wikicommit-schema-propose", "wikicommit-update", "wikicommit-init")

BLOCK_RE = re.compile(
    r"<!-- commit-trailers:start.*?-->\n(.*?)\n\s*<!-- commit-trailers:end -->", re.DOTALL
)


def _block(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    blocks = BLOCK_RE.findall(text)
    assert len(blocks) == 1, f"{skill}: expected exactly one commit-trailers block, found {len(blocks)}"
    return "\n".join(line.strip() for line in blocks[0].splitlines())


@pytest.mark.parametrize("skill", COPIES[1:])
def test_every_copy_matches_the_merge_copy(skill):
    assert _block(skill) == _block("wikicommit-merge"), (
        f"{skill}'s commit-trailers block differs from wikicommit-merge's; "
        "change all four together (Issue #1019)"
    )


def test_the_table_maps_each_vendor_and_writes_nothing_otherwise():
    block = _block("wikicommit-merge")
    assert "`claude-`, or `claude-` after a provider prefix ending in `anthropic.` (Bedrock, e.g. `us.anthropic.claude-…`) | `Co-Authored-By: <Claude display name> <noreply@anthropic.com>`" in block
    assert "`gpt-` or `codex` | `Co-Authored-By: Codex <noreply@openai.com>`" in block
    assert "no `Co-Authored-By` line at all" in block


@pytest.mark.parametrize("skill", COPIES[:3])
def test_the_commit_template_leaves_the_co_author_line_to_the_table(skill):
    """A literal `noreply@anthropic.com` line in the heredoc would be copied
    as-is by a non-Claude model — the misattribution this Issue removes."""
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "<Co-Authored-By line>\nGenerated-By:   <current model ID>" in text
    assert "Co-Authored-By: <Claude display name> <noreply@anthropic.com>\nGenerated-By:" not in text
