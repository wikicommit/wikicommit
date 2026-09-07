"""Tests that the three places describing what to do about a retracted source
agree with each other, and with what Regeneration Mode actually does
(Issues #737 / #744).

`status: retracted` is written by a human and never by a Skill, so nothing in
the pipeline enforces the routes out of it — the routes live entirely in prose,
in three copies that ship independently:

- `wikicommit-generate` SKILL.md — the Skill that performs the rebuild
- `wikicommit-status` SKILL.md Step 12 — where a human is told which route to take
- `check_retracted_sources.py`'s docstring — the same advice next to the code

plus the design record those three are written from (`docs/DesignDoc-data.md`
and `docs/DesignDoc-ScriptSpec.md`), which does not ship but is where the next
editor looks first.

These three drifted apart once already, within a single pull request: Issue
#737 landed with `--regenerate` re-acquiring every source, so all three
correctly said `--regenerate` was *not* the way to rebuild from what was left.
Issue #744 then made `--regenerate` drop the retracted source, which inverted
that advice. Nothing but these tests notices if one copy keeps the old answer,
and the failure mode is a user following documented advice into the exact
re-ingestion the retraction exists to prevent.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"
DOCS = REPO_ROOT / "docs"
CHECK_SCRIPT = (
    SKILLS / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_retracted_sources.py"
)

# Each source of advice, and how to read it.
ADVICE_SOURCES = [
    pytest.param(SKILLS / "wikicommit-generate" / "SKILL.md", id="generate-skill"),
    pytest.param(SKILLS / "wikicommit-status" / "SKILL.md", id="status-skill"),
    pytest.param(CHECK_SCRIPT, id="check-script-docstring"),
    # The design record is a fourth copy. It does not ship, so it is not one of
    # the three above, but it is where the other three are written from: leave
    # it out and reverting it is invisible to every test here.
    pytest.param(DOCS / "DesignDoc-data.md", id="design-doc-data"),
    pytest.param(DOCS / "DesignDoc-ScriptSpec.md", id="design-doc-scriptspec"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ADVICE_SOURCES)
def test_no_copy_still_says_regenerate_is_not_the_route(path):
    """The pre-Issue #744 wording must not survive anywhere.

    Its exact phrasings are matched rather than a keyword, because the same
    words appear legitimately in the corrected text; what must be gone is the
    claim that `--regenerate` does not work for this.
    """
    text = read(path)
    stale_claims = [
        # wikicommit-status SKILL.md Step 12
        "is not by itself the fix",
        # check_retracted_sources.py's docstring
        "is **not** on its own the way",
        # docs/DesignDoc-data.md — Japanese, and so unmatchable in the three
        # English copies; it is listed because the file carrying it is now
        # scanned, not as a check on the others.
        "はそれ単体では",
        # wikicommit-generate SKILL.md — its own pre-Issue #744 wording, which
        # none of the phrasings above ever appeared in. Without this entry the
        # parametrized case for the file that performs the rebuild cannot fail.
        "disqualifies the page the same way",
    ]
    for claim in stale_claims:
        assert claim not in text, (
            f"{path} still carries the pre-Issue #744 advice ({claim!r}), which "
            "sends a user to /wikicommit-fix for a rebuild that --regenerate now "
            "performs correctly."
        )


def test_regeneration_mode_drops_the_retracted_source_rather_than_the_page():
    """A retracted source is the one acquisition failure that must NOT skip the
    page. The changed / unavailable / manual cases skip because the content is
    still wanted and cannot be had; a retraction says the content is not wanted,
    so removing what rested on it is the point (Issue #744)."""
    text = read(SKILLS / "wikicommit-generate" / "SKILL.md")
    assert "A retracted source is dropped, not fetched, and not carried forward" in text
    assert "drop the retracted entry from the rebuilt page's `sources:`" in text
    # The asymmetry has to be stated, not just implemented: without it the next
    # editor reads the three neighbouring "skip the page" rules and makes this
    # one match them.
    assert "This is the opposite treatment from the changed/unavailable/`manual` cases" in text


def test_a_page_with_no_surviving_source_is_excluded_up_front():
    """Dropping every source would rebuild a page from nothing, so the
    all-retracted page is an eligibility exclusion — which also keeps it from
    consuming one of the five slots in the count guard."""
    text = read(SKILLS / "wikicommit-generate" / "SKILL.md")
    assert "A page **every** one of whose sources is `status: retracted`" in text
    assert "/wikicommit-remove" in text


def test_sources_copy_through_rule_names_its_one_exception():
    """Step 2 says `sources:` is copied through untouched. Left unqualified it
    contradicts step 1's drop, and a reader following step 2 alone would write
    the retracted entry back."""
    text = read(SKILLS / "wikicommit-generate" / "SKILL.md")
    assert "The single exception is a `status: retracted` entry" in text


def test_the_unchanged_output_valve_is_documented_as_unreachable_here():
    """`sources:` is inside the valve's comparison, so a dropped entry always
    counts as a difference. That is the correct outcome — what the page rests
    on changed — but it has to be written down, or a later reader tries to make
    the valve fire for these pages."""
    text = read(SKILLS / "wikicommit-generate" / "SKILL.md")
    assert "can never compare identical and always lands on `pending`" in text
