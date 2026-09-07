"""Guards /wikicommit-synthesize's index.md rebuild step (Issue #547).

A synthesized page has no source of its own (only `derived_from`), so nothing
schedules a later /wikicommit-generate run to pick it up — before Issue #547
the page simply stayed out of its type index, and being unlinked at birth it
was reachable only by direct URL. The rebuild is one call to the shared
rebuild_index.py (Issue #406), so the only way it regresses is the Step
disappearing from SKILL.md.
"""

from pathlib import Path

import pytest

SKILL_MD = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-synthesize" / "SKILL.md"
)


@pytest.fixture(scope="module")
def skill_md() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def test_synthesize_calls_rebuild_index(skill_md):
    assert "rebuild_index.py" in skill_md


def test_rebuild_is_scoped_to_the_written_directory(skill_md):
    """Unlike generate/translate, this Skill writes exactly one page and knows
    where it went, so it passes that directory instead of rebuilding the whole
    tree. Since Issue #675 the page goes to the view tree, whose index is
    per-language — a view page has no Type directory to scope to."""
    assert ".wikicommit/view/<lang>\n" in skill_md


def test_stale_out_of_scope_note_is_gone(skill_md):
    """The Issue #283-era Notes line saying the index is not updated."""
    assert "does not update the affected" not in skill_md
