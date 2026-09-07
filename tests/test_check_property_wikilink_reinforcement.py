"""Tests for .wikicommit/scripts/check_property_wikilink_reinforcement.py

All tests point WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD at a small local JSON-LD
fixture instead of the real https://schema.org/ endpoint, so the suite stays
network-free and deterministic (same hook check_schema_org_type.py's own
tests use).
"""

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_property_wikilink_reinforcement.py"
ENV_VAR = "WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD"

TEMPLATE_SCHEMA_DIR = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "schema"
)

# Most tests drive the script as a subprocess; the "distributed templates" ones
# at the bottom call is_reinforced() directly, so the module is also imported
# here (same pattern as test_check_wikilinks.py — the script imports its sibling
# helper modules by bare name, hence the sys.path entry).
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("check_property_wikilink_reinforcement", SCRIPT)
_checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checker)

# Thing <- {Person, Organization, Place}, plus:
#   - affiliation: domainIncludes Person, rangeIncludes Organization (entity-only)
#   - foundingLocation: domainIncludes Organization, rangeIncludes Place (entity-only)
#   - description: domainIncludes Thing, rangeIncludes [TextObject, Text] (mixed —
#     TextObject is a plain rdfs:Class, not tagged schema:DataType, matching the
#     real Schema.org shape check_schema_org_type.py's own fixture documents)
#   - name: domainIncludes Thing, rangeIncludes Text (DataType-only via direct tag)
#   - noRange: domainIncludes Thing, no rangeIncludes at all
FIXTURE_VOCAB = {
    "@graph": [
        {"@id": "schema:Thing", "@type": "rdfs:Class"},
        {"@id": "schema:Person", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:Organization", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:Place", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:Text", "@type": ["rdfs:Class", "schema:DataType"]},
        {"@id": "schema:TextObject", "@type": "rdfs:Class"},
        {
            "@id": "schema:affiliation",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Person"},
            "schema:rangeIncludes": {"@id": "schema:Organization"},
        },
        {
            "@id": "schema:foundingLocation",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Organization"},
            "schema:rangeIncludes": {"@id": "schema:Place"},
        },
        {
            "@id": "schema:description",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": [{"@id": "schema:TextObject"}, {"@id": "schema:Text"}],
        },
        {
            "@id": "schema:name",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": {"@id": "schema:Text"},
        },
        {
            "@id": "schema:noRange",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
        },
    ]
}


def write_fixture(tmp_path: Path, content: dict) -> Path:
    fixture_path = tmp_path / "vocab.jsonld"
    fixture_path.write_text(json.dumps(content), encoding="utf-8")
    return fixture_path


def run(cwd: Path, fixture_path: Path | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if fixture_path is not None:
        env[ENV_VAR] = str(fixture_path)
    else:
        env.pop(ENV_VAR, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


def write_schema_file(root: Path, rel_path: str, body: str) -> Path:
    schema_file = root / ".wikicommit" / "schema" / rel_path
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    schema_file.write_text(textwrap.dedent(body), encoding="utf-8")
    return schema_file


def test_no_schema_dir(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_entity_only_property_without_reinforcement_reported(tmp_path):
    write_schema_file(
        tmp_path, "Organization.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Organization"
            properties:
              foundingLocation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED: Organization.foundingLocation" in result.stdout
    assert "SUMMARY: unreinforced=1" in result.stdout


def test_entity_only_property_reinforced_via_placeholder_not_reported(tmp_path):
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Person"
            properties:
              affiliation: "[[Organization/slug]]"
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_entity_only_property_reinforced_via_granularity_not_reported(tmp_path):
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity:
                - affiliation names an organization; link it with a WikiLink
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_list_value_reinforced_via_wikilink_placeholder(tmp_path):
    write_schema_file(
        tmp_path, "Organization.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Organization"
            properties:
              foundingLocation: ["[[Place/slug]]"]
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout


def test_mixed_property_without_reinforcement_reported(tmp_path):
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Person"
            properties:
              description: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED: Person.description" in result.stdout
    assert "SUMMARY: unreinforced=1" in result.stdout


def test_datatype_only_property_never_reported(tmp_path):
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Person"
            properties:
              name: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_property_with_no_range_declared_not_reported(tmp_path):
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Person"
            properties:
              noRange: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_property_not_in_vocab_not_reported(tmp_path):
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Person"
            properties:
              notARealSchemaOrgProperty: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_custom_type_skipped(tmp_path):
    write_schema_file(
        tmp_path, "custom/Decision.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:custom/Decision"
            properties:
              decidedBy: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_default_md_skipped(tmp_path):
    write_schema_file(
        tmp_path, "default.md",
        """\
            ---
            wikicommit:
              granularity: []
            title: ""
            type: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_no_properties_block_skipped(tmp_path):
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Person"
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_multiple_files_aggregated(tmp_path):
    write_schema_file(
        tmp_path, "Organization.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Organization"
            properties:
              foundingLocation: ""
            ---
            body
            """,
    )
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: []
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED: Organization.foundingLocation" in result.stdout
    assert "UNREINFORCED: Person.affiliation" in result.stdout
    assert "SUMMARY: unreinforced=2" in result.stdout


def test_vocab_fetch_failure_warns_and_returns_zero(tmp_path):
    """No fixture at all and no real network access in the test sandbox —
    load_or_build_index() should fail, and this script degrades to a
    non-blocking WARNING (same pattern validate_frontmatter.py's
    `properties:` check uses), never a hard failure."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    env = dict(os.environ)
    env[ENV_VAR] = str(tmp_path / "does-not-exist.jsonld")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert "WARNING: the Schema.org vocabulary could not be loaded" in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_null_wikicommit_block_does_not_crash(tmp_path):
    """A `wikicommit:` key present but with no nested content parses as
    `None`, not `{}` — `fm.get("wikicommit", {})` only substitutes the
    default when the key is *absent*, so a naive `.get("wikicommit", {}).get(...)`
    chain would raise AttributeError on this input instead of degrading
    gracefully like every other malformed-input case this script handles."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED: Person.affiliation" in result.stdout
    assert "SUMMARY: unreinforced=1" in result.stdout


def test_mapping_granularity_bullet_warns_and_is_still_skipped(tmp_path):
    """#649 — an unquoted bullet containing `key: value` parses as a one-key
    mapping, so the reinforcement search never sees the prose in it. The entry
    stays skipped (the fix belongs in the schema file, which nothing else
    validates), but it no longer disappears without a word: the WARNING is what
    explains the otherwise inexplicable UNREINFORCED line right below it."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity:
                - Boundary with Organization: link each affiliation as a WikiLink
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "wikicommit.granularity[0]" in result.stdout
    assert "dict" in result.stdout
    assert "UNREINFORCED: Person.affiliation" in result.stdout
    assert "SUMMARY: unreinforced=1" in result.stdout


def test_string_granularity_bullets_produce_no_warning(tmp_path):
    """The warning must stay quiet on well-formed templates — otherwise every
    run of /wikicommit-status carries noise that trains readers to ignore it."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity:
                - Boundary — a Person page is not a role description
                - Link each affiliation as [[Organization/slug]]
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "wikicommit.granularity" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_non_list_granularity_warns(tmp_path):
    """`granularity:` written as a bare string (rather than a list) was also
    coerced to [] silently. Same class of silent skip, same remedy."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity: Link each affiliation as a WikiLink
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "wikicommit.granularity is not a list" in result.stdout
    assert "UNREINFORCED: Person.affiliation" in result.stdout
    assert "SUMMARY: unreinforced=1" in result.stdout


def test_granularity_mention_without_link_cue_is_not_reinforcement(tmp_path):
    """#650 — a bullet that names the property in order to say the *opposite*
    used to count as reinforcement. This is the shape that actually silenced
    HowTo.tool/supply twice (Issues #550 and #551), and it could not be fixed
    by rewording the second time because naming those properties was the whole
    point of the bullet."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity:
                - The affiliation property is frequently empty; leave it out rather than
                  treating its emptiness as a signal that the subject does not fit
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED: Person.affiliation" in result.stdout
    assert "SUMMARY: unreinforced=1" in result.stdout


def test_granularity_wikilink_token_alone_counts_as_link_cue(tmp_path):
    """`[[` is the other accepted cue — a bullet can point at linking by
    showing the target form rather than by using the word "link"."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity:
                - Write affiliation as [[Organization/slug]] when the employer has its own page
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED:" not in result.stdout
    assert "SUMMARY: unreinforced=0" in result.stdout


def test_property_name_cannot_supply_its_own_link_cue():
    """#650 — the cue has to come from the prose *around* the property name.
    `schema:originalMediaLink` is in scope here (its range includes MediaObject
    and WebPage), and its own name contains "link", so matching the cue against
    the whole bullet would let any bullet that merely names it count as
    reinforcement — reinstating exactly the mention-only behaviour this
    requirement exists to remove."""
    bullet = "Do not record originalMediaLink; it duplicates the source entry"
    assert not _checker.is_reinforced("originalMediaLink", "", [bullet])
    assert _checker.is_reinforced(
        "originalMediaLink", "", ["Write originalMediaLink as [[MediaObject/slug]]"]
    )


def test_link_cue_must_be_in_the_same_bullet_as_the_property_name(tmp_path):
    """The two halves have to co-occur: a template whose linking advice is about
    some *other* property does not reinforce this one."""
    write_schema_file(
        tmp_path, "Person.md",
        """\
            ---
            wikicommit:
              granularity:
                - The affiliation property is frequently empty; leave it out
                - Link a birthPlace with a WikiLink when the place has its own page
            type: "schema:Person"
            properties:
              affiliation: ""
            ---
            body
            """,
    )
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "UNREINFORCED: Person.affiliation" in result.stdout
    assert "SUMMARY: unreinforced=1" in result.stdout


# ── Distributed templates: Issue #523's reinforcements must not regress ──────
#
# Issue #650's completion condition asks explicitly that narrowing the prose
# test does not silently un-reinforce any of the reinforcements Issue #523
# actually wrote. Asserting it here (against the real templates, through the
# real predicate) keeps the answer true as templates get reworded, which a
# one-off check at implementation time would not.

# (template file, property) pairs Issue #523 (and its /code-review --fix pass)
# reinforced in granularity prose rather than via a [[Type/slug]] placeholder.
ISSUE_523_PROSE_REINFORCEMENTS = [
    ("BlogPosting.md", "author"), ("BlogPosting.md", "publisher"),
    ("NewsArticle.md", "author"), ("NewsArticle.md", "publisher"),
    ("ScholarlyArticle.md", "author"), ("ShortStory.md", "author"),
    ("Book.md", "author"), ("Book.md", "character"), ("ShortStory.md", "character"),
    ("Event.md", "organizer"), ("Event.md", "performer"),
]


def template_granularity(template: str) -> list[str]:
    """The usable `granularity` bullets of a distributed template, read through
    the same frontmatter parser and the same filter the script itself uses."""
    path = TEMPLATE_SCHEMA_DIR / template
    fm = _checker.parse_frontmatter_or_warn(path)
    return _checker.granularity_strings(path, fm.get("wikicommit"))


@pytest.mark.parametrize("template,prop", ISSUE_523_PROSE_REINFORCEMENTS)
def test_existing_prose_reinforcements_survive_the_link_cue_requirement(template, prop):
    """#650 — every reinforcement Issue #523 wrote names the property *and*
    points toward linking, so requiring both must not report any of them."""
    granularity = template_granularity(template)
    assert _checker.is_reinforced(prop, "", granularity), (
        f"{template} の {prop} が granularity 補強として認識されなくなりました"
        "（Issue #523 が書いた補強の回帰）"
    )


def test_howto_tool_and_supply_are_not_prose_reinforced():
    """#650 — the two properties the mention-only test wrongly silenced. Their
    granularity bullet names them in order to say they are often empty, which
    is the opposite of pointing at a WikiLink."""
    granularity = template_granularity("HowTo.md")
    assert not _checker.is_reinforced("tool", "", granularity)
    assert not _checker.is_reinforced("supply", "", granularity)
