"""An excluded entity's existing page has to be named (Issue #876).

Generation never removes a page — `/wikicommit-remove` is the only path that does —
so an entity excluded today can have a page from an earlier run still standing and
published, and before this nothing in the run's output pointed at it. The exclusion
notes recorded *which entity*, by title, and the file name is a language-neutral
English slug whose derivation does not run backwards (a common noun is translated, an
established spelling kept, otherwise romanized; Issue #193). On the two wikis where
this policy actually fired — `saitama-city-wiki` (ja) and `decameron-wiki` (it) —
going from the title to the page meant grepping `title:` across the tree, for an
answer Pass 2c already had as a by-product of naming the entity.

Every assertion here is about instruction prose, which is all there is to assert:
the resolution happens inside an LLM pass. So these pin the two things that make the
change safe rather than merely present — that the report is a statement of fact and
not a verdict, and that nothing deletes anything — because both are exactly the kind
of qualifier a later edit trims as redundant.
"""

import re
from pathlib import Path

REPO = Path(__file__).parent.parent
GENERATE = REPO / ".claude/skills/wikicommit-generate"
# Pass 2c, which is what these assertions are about, moved out of SKILL.md into
# references/pass2c-entities.md (Issue #911). SKILL.md now holds the pointer.
SKILL = GENERATE / "references" / "pass2c-entities.md"
NOTICE = GENERATE / "references" / "completion-notice.md"
GUIDE = (
    REPO
    / ".claude/skills/wikicommit-init/scripts/templates/guides"
    / "applying-entity-policy-to-existing-pages.md"
)


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_pass_2c_resolves_existing_path_for_excluded_entities():
    text = _flat(SKILL.read_text(encoding="utf-8"))
    assert _flat(
        "Set `existing_path` on an `action: exclude` entity too, when that entity "
        "already has a page"
    ) in text, (
        "Pass 2c no longer resolves existing_path for excluded entities, so an "
        "excluded entity's standing page goes unnamed again"
    )


def test_the_field_is_documented_as_driving_nothing_for_excluded_entities():
    """On a create/update entity this field makes Pass 3 read the page. Pass 3 handles
    only those two actions, so there is no read here — but an unwritten premise drifts,
    which is the failure this repository keeps re-encountering."""
    text = _flat(SKILL.read_text(encoding="utf-8"))
    assert _flat("This field is information here and drives nothing.") in text
    assert _flat(
        "nothing about an excluded entity's page is opened, rewritten, or removed"
    ) in text


def test_the_analysis_json_example_shows_a_resolved_path_on_an_exclude_entry():
    """Prose alone would leave the shape to inference, and the examples are what a
    reader copies. One of the two exclude entries carries a path in each copy."""
    for path in (SKILL, REPO / "docs/DesignDoc-skills.md"):
        text = path.read_text(encoding="utf-8")
        block = re.search(
            r'"action": "exclude",\s*\n\s*"existing_path": "\.wikicommit/entity/[^"]+"',
            text,
        )
        assert block, f"{path.name} has no exclude entry with a resolved existing_path"


def test_both_report_sinks_carry_the_path():
    """Two existing lines, not a new block: the notice is where a person decides what
    to do, and `## Generation Notes` is the copy that outlives the run's output."""
    skill = _flat(SKILL.read_text(encoding="utf-8"))
    assert _flat(
        "and — when the entity turned out to have one — its `existing_path`"
    ) in skill, "## Generation Notes no longer records the page path"

    notice = _flat(NOTICE.read_text(encoding="utf-8"))
    assert _flat(
        "Where an excluded entity's `existing_path` is set, name that page on its line"
    ) in notice, "the completion notice no longer names the page"


def test_the_report_states_a_fact_rather_than_a_verdict():
    """The qualifier is the substance. A page can rest on three sources, and one of
    them ruling the entity out today says nothing about the other two — so "exists and
    was not touched" is the whole of what an exclusion establishes."""
    notice = _flat(NOTICE.read_text(encoding="utf-8"))
    assert _flat("State what is true of the page, not what to do about it.") in notice
    assert _flat("It is not evidence the page should go") in notice
    assert _flat(
        "A page for this already exists and this run neither created nor updated it"
    ) in notice, "the rendered line no longer states the fact in those terms"


def test_only_the_privacy_group_points_at_removal():
    notice = _flat(NOTICE.read_text(encoding="utf-8"))
    assert _flat("Only the `privacy` group points at `/wikicommit-remove`") in notice
    assert _flat(
        "Under `theme_mismatch`, name the page and stop there"
    ) in notice, "theme_mismatch is no longer held back from suggesting removal"


def test_nothing_removes_a_page_automatically():
    """Removal is irreversible and `removed_reason` is a judgment. A policy decides
    what to create, not what to destroy."""
    notice = _flat(NOTICE.read_text(encoding="utf-8"))
    assert _flat("Never call `/wikicommit-remove` yourself.") in notice


def test_the_guide_no_longer_tells_the_reader_to_match_titles_by_hand():
    """Issue #867's guide predates this and said the matching was manual. Left as it
    was, it sends a reader looking for something the run now prints — and it is the
    only document written for the person applying a policy change."""
    text = GUIDE.read_text(encoding="utf-8")
    assert "### Working out which pages those are is still by hand" not in text, (
        "the guide still claims the page paths must be worked out by hand"
    )
    assert "### The run names the pages for you" in text
    # And it must keep the recovery route for runs from before this change.
    assert "git show HEAD:<management" in text


def test_the_trailing_note_scopes_itself_to_the_privacy_group():
    """Both groups can name pages, and the note prints under only one of them.

    "the pages named above" swept in the off-subject ones — the very pages the
    paragraph beside it says must not be pointed at removal. The grouping exists to
    keep the two reasons distinct; a note that reaches across it undoes that.
    """
    notice = NOTICE.read_text(encoding="utf-8")
    assert "the pages named\nin this group are the ones this applies to." in notice, (
        "the trailing note no longer scopes itself to its own group, so it points "
        "theme_mismatch pages at /wikicommit-remove"
    )
    assert "the pages named\nabove are the ones" not in notice
