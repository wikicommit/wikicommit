"""The `summary` field description must not ask for exclusion reasons (Issue #943).

Issue #831 moved exclusion reasons (`exclude_note`/`coverage_gap_note`) out of
`## Summary` and into the non-public `## Generation Notes` section, because
`## Summary` is the one prose section `_write_source_page()` publishes to
`content/sources/` — an exclusion note there named real living people
alongside the reason they were dropped.

That fix only touched the write-back instructions (what to do with the JSON's
`summary` value once it comes back). It missed the field description the LLM
actually reads when filling the JSON in: `references/pass2c-entities.md`
told the model, in the same breath as asking for a summary, to "briefly note
the reason" for any exclusion right there in `summary` — so a model that
followed the field description to the letter would fold the reason back into
the very string that ends up in the public section, no matter how strict the
write-back instructions downstream were.

The reason belongs in `entities[].exclude_note`, which the JSON schema already
carries. This test pins two things: the field description itself stays free of
exclusion language (so the string a model copies verbatim cannot smuggle a
reason back in), and the surrounding prose still points at `exclude_note` as
the right place — a bare prohibition with no redirect would read like the same
"container rule" the write-back step already states, without explaining that
`summary`'s own field description is where the leak actually happened.
"""

import re
from pathlib import Path

SKILLS = Path(__file__).parent.parent / ".claude" / "skills"
PASS2C = (SKILLS / "wikicommit-generate" / "references" / "pass2c-entities.md").read_text(
    encoding="utf-8"
)
DESIGN_DOC = (Path(__file__).parent.parent / "docs" / "DesignDoc-skills.md").read_text(
    encoding="utf-8"
)

# Matches the `"summary": "..."` field description inside the JSON code block
# that `references/pass2c-entities.md` gives the LLM to fill in.
SUMMARY_FIELD_RE = re.compile(r'"summary":\s*"((?:[^"\\]|\\.)*)"')


def _summary_field_description(text: str) -> str:
    match = SUMMARY_FIELD_RE.search(text)
    assert match, "could not find a \"summary\": \"...\" field in the JSON block"
    return match.group(1)


def _prose_before_json_block(text: str) -> str:
    """The paragraph introducing the JSON block, before the ```json fence."""
    marker = "Ask the LLM to analyze the extracted text"
    start = text.index(marker)
    end = text.index("```json", start)
    return text[start:end]


def test_pass2c_summary_field_does_not_ask_for_exclusion_reasons():
    description = _summary_field_description(PASS2C)
    lowered = description.lower()
    assert "exclud" not in lowered, (
        "the `summary` field description in references/pass2c-entities.md asks the "
        "LLM to fold exclusion reasons into `summary` — that belongs in "
        "`entities[].exclude_note` instead (Issue #943): " + description
    )


def test_pass2c_intro_prose_redirects_to_exclude_note():
    intro = _prose_before_json_block(PASS2C)
    assert "exclude_note" in intro, (
        "the prose introducing the JSON block should name `exclude_note` as "
        "the place exclusion reasons go, so the prohibition on `summary` reads "
        "as a redirection rather than a bare ban (Issue #943)"
    )


def test_design_doc_example_summary_has_no_exclusion_reason():
    description = _summary_field_description(DESIGN_DOC)
    assert "除外" not in description, (
        "the example analysis JSON in docs/DesignDoc-skills.md folds an "
        "exclusion reason into the `summary` value — the example's entities[] "
        "already carries exclude_reason/exclude_note, so the summary value "
        "should not repeat it (Issue #943): " + description
    )
