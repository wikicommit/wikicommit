"""Tests for .wikicommit/scripts/check_schema_files.py (Issue #889).

Uses a local JSON-LD vocabulary fixture via WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD,
the same network-free hook check_schema_org_type.py's own tests use.

Two of the cases here are the ones that motivated the script, and both were
measured on a real repository rather than imagined: a `granularity` bullet
truncated by an unquoted ` #` (one pilot lost ~280 characters off the end of a
rule and nothing anywhere said so), and a bullet turned into a one-key mapping
by an unquoted `": "`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".wikicommit" / "scripts" / "check_schema_files.py"
TEMPLATE_SCRIPT = (
    REPO_ROOT
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts"
    / "check_schema_files.py"
)
ENV_VAR = "WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD"

# Thing <- Person, with `affiliation` on Person and `name` on Thing.
FIXTURE_VOCAB = {
    "@graph": [
        {"@id": "schema:Thing", "@type": "rdfs:Class"},
        {"@id": "schema:Person", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:Place", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {
            "@id": "schema:affiliation",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Person"},
        },
        {
            "@id": "schema:name",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
        },
    ]
}


def run(cwd: Path) -> subprocess.CompletedProcess:
    vocab = cwd / "vocab.jsonld"
    if not vocab.exists():
        vocab.write_text(json.dumps(FIXTURE_VOCAB), encoding="utf-8")
    env = {**os.environ, ENV_VAR: str(vocab)}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, cwd=cwd, env=env, check=False,
    )


def write(root: Path, rel: str, text: str) -> Path:
    path = root / ".wikicommit" / "schema" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


GOOD_PERSON = """---
wikicommit:
  base: https://schema.org/Person
  provenance: collect
  granularity:
    - Create a page for any person named in full
    - Boundary — a Person is an individual, not the organization they work for
title: ""
type: "schema:Person"
lang: ""
sources: []
tags: []

properties:
  affiliation: ""
---

Body.
"""


def test_no_schema_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: files=0, findings=0" in result.stdout
    assert "NOTE:" in result.stdout


def test_a_well_formed_file_is_quiet(tmp_path):
    write(tmp_path, "Person.md", GOOD_PERSON)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: files=1, findings=0, in_distributed_templates=0" in result.stdout


def test_default_md_is_not_asked_for_a_base_or_a_type(tmp_path):
    """`default.md` is the fallback rather than a type, and carries neither by design."""
    write(
        tmp_path, "default.md",
        '---\nwikicommit:\n  frontmatter:\n    required: [title, lang, type, sources]\n'
        '  granularity: []\ntitle: ""\ntype: ""\nlang: ""\nsources: []\n---\n\nBody.\n',
    )
    result = run(cwd=tmp_path)
    assert "NO_BASE" not in result.stdout
    assert "TYPE_PATH_MISMATCH" not in result.stdout
    assert "findings=0" in result.stdout


def test_a_property_outside_the_types_domain_is_reported(tmp_path):
    write(tmp_path, "Place.md", GOOD_PERSON.replace("Person", "Place"))
    result = run(cwd=tmp_path)
    assert "BAD_PROPERTY: .wikicommit/schema/Place.md" in result.stdout
    assert "affiliation is not in the domain of schema:Place" in result.stdout


def test_a_property_that_is_not_in_the_vocabulary_at_all_is_reported(tmp_path):
    write(tmp_path, "Person.md", GOOD_PERSON.replace("affiliation:", "notAThing:"))
    result = run(cwd=tmp_path)
    assert "BAD_PROPERTY" in result.stdout
    assert "notAThing is not in the Schema.org vocabulary" in result.stdout


def test_a_mapping_bullet_is_reported(tmp_path):
    """An unquoted `": "` makes the bullet a one-key mapping (Issue #649)."""
    write(
        tmp_path, "Person.md",
        GOOD_PERSON.replace(
            "    - Boundary — a Person is an individual, not the organization they work for",
            "    - Boundary with Organization: a Person is an individual",
        ),
    )
    result = run(cwd=tmp_path)
    assert "MAPPING_BULLET: .wikicommit/schema/Person.md" in result.stdout
    assert "granularity[1] parsed as dict" in result.stdout


def test_a_truncated_bullet_is_reported_even_though_yaml_is_happy(tmp_path):
    """The failure mode nothing else notices: the value is a string, just shorter.

    Measured on a real pilot repository before this script existed — a rule ran
    ~1000 characters and reached its consumers at 723, with no warning anywhere.
    """
    write(
        tmp_path, "Person.md",
        GOOD_PERSON.replace(
            "    - Create a page for any person named in full",
            "    - Create a page for any person named in full (Issue #275) and not otherwise",
        ),
    )
    result = run(cwd=tmp_path)
    assert "TRUNCATED_BULLET: .wikicommit/schema/Person.md" in result.stdout
    # And the premise: YAML really did drop the tail without complaining.
    assert "MAPPING_BULLET" not in result.stdout


def test_a_quoted_bullet_holding_a_hash_is_not_reported(tmp_path):
    """Quoting is the documented fix, so it must not read as the defect."""
    write(
        tmp_path, "Person.md",
        GOOD_PERSON.replace(
            "    - Create a page for any person named in full",
            '    - "Create a page for any person named in full (Issue #275) and not otherwise"',
        ),
    )
    result = run(cwd=tmp_path)
    assert "TRUNCATED_BULLET" not in result.stdout


def test_a_boundary_bullet_that_parsed_as_a_mapping_still_counts_as_one(tmp_path):
    """`Boundary with X: ...` is the shape three templates carried before Issue #550
    replaced the colon with an em dash. The mapping is worth reporting; saying on top
    of it that no bullet begins with `Boundary` is simply false."""
    write(
        tmp_path, "Person.md",
        GOOD_PERSON.replace(
            "    - Boundary — a Person is an individual, not the organization they work for",
            "    - Boundary with Organization: a Person is an individual",
        ),
    )
    result = run(cwd=tmp_path)
    assert "MAPPING_BULLET" in result.stdout
    assert "NO_BOUNDARY" not in result.stdout


def test_a_missing_boundary_rule_is_reported(tmp_path):
    write(
        tmp_path, "Person.md",
        GOOD_PERSON.replace(
            "    - Boundary — a Person is an individual, not the organization they work for\n", ""
        ),
    )
    result = run(cwd=tmp_path)
    assert "NO_BOUNDARY: .wikicommit/schema/Person.md" in result.stdout


def test_an_empty_granularity_is_not_asked_for_a_boundary_rule(tmp_path):
    """`default.md` ships with `granularity: []`, and a type file may legitimately
    have written none yet — the absence of rules is a different thing from a set
    of rules with no boundary among them."""
    write(
        tmp_path, "Person.md",
        GOOD_PERSON.replace(
            "  granularity:\n"
            "    - Create a page for any person named in full\n"
            "    - Boundary — a Person is an individual, not the organization they work for\n",
            "  granularity: []\n",
        ),
    )
    result = run(cwd=tmp_path)
    assert "NO_BOUNDARY" not in result.stdout


def test_an_unknown_provenance_value_is_reported(tmp_path):
    write(tmp_path, "Person.md", GOOD_PERSON.replace("provenance: collect", "provenance: invented"))
    result = run(cwd=tmp_path)
    assert "BAD_PROVENANCE: .wikicommit/schema/Person.md" in result.stdout
    assert "'invented'" in result.stdout


def test_a_missing_provenance_is_not_reported(tmp_path):
    """Its absence means "written before that field existed" (Issue #519), which is
    a correct state for an older repository rather than something to fix."""
    write(tmp_path, "Person.md", GOOD_PERSON.replace("  provenance: collect\n", ""))
    result = run(cwd=tmp_path)
    assert "BAD_PROVENANCE" not in result.stdout
    assert "findings=0" in result.stdout


def test_the_body_of_the_page_template_is_not_read_as_granularity(tmp_path):
    """The closing `---` is itself a line beginning with `-`, so a scan that ends the
    list at "the first line that is not a bullet" steps over it. With `wikicommit:`
    written last — YAML key order is free — the page template's own Markdown list
    would otherwise be reported as truncated granularity bullets."""
    write(
        tmp_path, "Person.md",
        '---\ntitle: ""\ntype: "schema:Person"\nlang: ""\nsources: []\n'
        "wikicommit:\n  base: https://schema.org/Person\n  provenance: manual\n"
        "  granularity:\n    - Boundary — a Person is an individual\n---\n\n"
        "- a body bullet mentioning Issue #275 and more text after it\n"
        "- another body bullet\n",
    )
    result = run(cwd=tmp_path)
    assert "TRUNCATED_BULLET" not in result.stdout
    assert "findings=0" in result.stdout


def test_a_type_outside_the_vocabulary_is_reported_without_a_properties_block(tmp_path):
    """A misspelled type name is what makes a file define nothing, and it is exactly
    as silent whether or not the file also happens to carry `properties:`."""
    write(
        tmp_path, "Pracitce.md",
        '---\nwikicommit:\n  base: https://schema.org/Thing\n  provenance: manual\n'
        "  granularity:\n    - Boundary — x\n"
        'title: ""\ntype: "schema:Pracitce"\nlang: ""\nsources: []\n---\n\nBody.\n',
    )
    result = run(cwd=tmp_path)
    assert "UNKNOWN_TYPE: .wikicommit/schema/Pracitce.md" in result.stdout


def test_a_type_that_disagrees_with_its_path_is_not_also_called_unknown(tmp_path):
    """A standard type moved into a subdirectory of the maintainer's own invention
    (Issue #575): the path-derived name is not in the vocabulary, but reporting that
    would quote a `type:` the file does not contain and point at custom/."""
    path = tmp_path / ".wikicommit" / "schema" / "standard"
    path.mkdir(parents=True, exist_ok=True)
    (path / "Person.md").write_text(GOOD_PERSON, encoding="utf-8")
    result = run(cwd=tmp_path)
    assert "TYPE_PATH_MISMATCH" in result.stdout
    assert "UNKNOWN_TYPE" not in result.stdout
    assert "standard/Person, which is not in the Schema.org vocabulary" not in result.stdout


def test_a_missing_base_is_reported(tmp_path):
    write(tmp_path, "Person.md", GOOD_PERSON.replace("  base: https://schema.org/Person\n", ""))
    result = run(cwd=tmp_path)
    assert "NO_BASE: .wikicommit/schema/Person.md" in result.stdout


def test_a_type_that_disagrees_with_its_path_is_reported(tmp_path):
    """Only the path decides which type a file defines, so a mismatch means the
    file is silently defining nothing (docs/DesignDoc-data.md §5.1)."""
    write(tmp_path, "Place.md", GOOD_PERSON)
    result = run(cwd=tmp_path)
    assert "TYPE_PATH_MISMATCH: .wikicommit/schema/Place.md" in result.stdout
    assert "the file sits at Place.md" in result.stdout


def test_a_custom_type_without_a_rationale_is_reported(tmp_path):
    write(
        tmp_path, "custom/Decision.md",
        '---\nwikicommit:\n  base: https://schema.org/CreativeWork\n  provenance: schema-propose\n'
        '  granularity:\n    - Boundary — a Decision is not the meeting that made it\n'
        'title: ""\ntype: "schema:custom/Decision"\nlang: ""\nsources: []\n---\n\nBody.\n',
    )
    result = run(cwd=tmp_path)
    assert "NO_RATIONALE: .wikicommit/schema/custom/Decision.md" in result.stdout


def test_a_custom_types_properties_are_not_resolved_against_the_vocabulary(tmp_path):
    """A custom type is by definition outside it, so there is nothing to check."""
    write(
        tmp_path, "custom/Decision.md",
        '---\nwikicommit:\n  base: https://schema.org/CreativeWork\n  provenance: schema-propose\n'
        '  rationale: "No standard type carries a decision record."\n'
        '  granularity:\n    - Boundary — a Decision is not the meeting that made it\n'
        'title: ""\ntype: "schema:custom/Decision"\nlang: ""\nsources: []\n\n'
        'properties:\n  decidedAt: ""\n---\n\nBody.\n',
    )
    result = run(cwd=tmp_path)
    assert "BAD_PROPERTY" not in result.stdout
    assert "findings=0" in result.stdout


def test_findings_in_a_distributed_template_are_counted_separately(tmp_path):
    """A `provenance: default` file failing a convention means the repository holds
    an older copy of a template, not that someone wrote it wrong — several of these
    conventions were retrofitted. Measured: one pilot had 16 of 18 findings here."""
    write(
        tmp_path, "Person.md",
        GOOD_PERSON.replace("provenance: collect", "provenance: default").replace(
            "    - Boundary — a Person is an individual, not the organization they work for\n", ""
        ),
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: files=1, findings=1, in_distributed_templates=1" in result.stdout
    assert "older copy of a distributed template" in result.stdout


def test_a_file_with_no_frontmatter_is_one_finding_not_several(tmp_path):
    """The shared parser calls "no frontmatter" a non-error, because most `.md`
    files have none. A type schema file is the exception — its frontmatter is the
    definition — and every other check would otherwise fire off one cause."""
    write(tmp_path, "Person.md", "no frontmatter here at all\n")
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "NO_FRONTMATTER: .wikicommit/schema/Person.md" in result.stdout
    assert "SUMMARY: files=1, findings=1" in result.stdout


def test_malformed_yaml_is_a_finding_not_a_crash(tmp_path):
    write(tmp_path, "Person.md", '---\nwikicommit:\n  granularity: [unclosed\n---\n\nBody.\n')
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNPARSEABLE: .wikicommit/schema/Person.md" in result.stdout


def test_the_vocabulary_being_unavailable_skips_only_the_property_checks(tmp_path):
    # GOOD_PERSON at Place.md: the type/path mismatch needs no vocabulary, while
    # resolving `affiliation` against schema:Place does.
    write(tmp_path, "Place.md", GOOD_PERSON)
    env = {**os.environ, ENV_VAR: str(tmp_path / "missing.jsonld")}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, cwd=tmp_path, env=env, check=False,
    )
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "BAD_PROPERTY" not in result.stdout
    # The checks that need no vocabulary still ran.
    assert "TYPE_PATH_MISMATCH" in result.stdout


def test_the_script_is_the_distributed_template(tmp_path):
    """`.wikicommit/scripts/` is a symlink to the template tree in this repository,
    so the two are the same bytes by construction — asserted so a future change that
    replaces the symlink with a copy cannot let them drift."""
    assert SCRIPT.read_text(encoding="utf-8") == TEMPLATE_SCRIPT.read_text(encoding="utf-8")
