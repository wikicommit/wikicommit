"""Tests for .wikicommit/scripts/check_unlinked_entity_mentions.py (Issue #561)

The script needs the Schema.org vocabulary to classify a property's range, so
each test writes a small local JSON-LD fixture and points
WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD at it — the same network-free hook
check_schema_org_type.py's and check_property_wikilink_reinforcement.py's own
tests use.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".wikicommit" / "scripts" / "check_unlinked_entity_mentions.py"
TEMPLATE_SCRIPT = (
    REPO_ROOT
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts"
    / "check_unlinked_entity_mentions.py"
)
ENV_VAR = "WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD"

# Thing <- {Person, Organization, Book, DefinedTerm}, Person <- Novelist, plus:
#   - character:  rangeIncludes Person                  (entity-only)
#   - provider:   rangeIncludes [Organization, Person]  (entity-only, two candidates)
#   - genre:      rangeIncludes [DefinedTerm, Text]     (mixed)
#   - isbn:       rangeIncludes Text                    (DataType-only)
#   - noRange:    no rangeIncludes at all
FIXTURE_VOCAB = {
    "@graph": [
        {"@id": "schema:Thing", "@type": "rdfs:Class"},
        {"@id": "schema:Person", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:Novelist", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Person"}},
        {"@id": "schema:Organization", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:Book", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:DefinedTerm", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:Text", "@type": ["rdfs:Class", "schema:DataType"]},
        {
            "@id": "schema:character",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Book"},
            "schema:rangeIncludes": {"@id": "schema:Person"},
        },
        {
            "@id": "schema:provider",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": [{"@id": "schema:Organization"}, {"@id": "schema:Person"}],
        },
        {
            "@id": "schema:genre",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Book"},
            "schema:rangeIncludes": [{"@id": "schema:DefinedTerm"}, {"@id": "schema:Text"}],
        },
        {
            "@id": "schema:isbn",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Book"},
            "schema:rangeIncludes": {"@id": "schema:Text"},
        },
        {
            "@id": "schema:noRange",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Book"},
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


def write(root: Path, lang: str, type_name: str, slug: str, frontmatter: str) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\nBody.\n", encoding="utf-8")
    return page


def write_book(root: Path, lang: str, slug: str, properties: str, type_name: str = "Book") -> Path:
    return write(
        root, lang, type_name, slug,
        f'title: "{slug}"\nlang: {lang}\ntype: "schema:{type_name}"\nproperties:\n{properties}',
    )


def write_person(root: Path, lang: str, slug: str, title: str, extra: str = "", type_name: str = "Person") -> Path:
    return write(
        root, lang, type_name, slug,
        f'title: "{title}"\nlang: {lang}\ntype: "schema:{type_name}"\n{extra}',
    )


# ── Nothing to report ────────────────────────────────────────────────────────

def test_no_wiki_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: unlinked=0" in result.stdout


def test_wikilinked_value_is_not_reported(tmp_path):
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write_book(tmp_path, "it", "decameron", '  character:\n    - "[[Person/filostrato]]"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_value_naming_no_page_is_not_reported(tmp_path):
    write_book(tmp_path, "it", "decameron", '  character:\n    - "Calandrino"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


# ── The Issue #561 case ──────────────────────────────────────────────────────

def test_plain_text_value_naming_an_existing_page_is_reported(tmp_path):
    """The decameron case: a page written by a later ingest, never linked back."""
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write_book(
        tmp_path, "it", "decameron",
        '  character:\n    - "[[Person/pampinea]]"\n    - "Filostrato"\n',
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout
    assert 'properties.character "Filostrato" exists as Person/filostrato' in result.stdout
    assert "page: .wikicommit/entity/it/Book/decameron.md" in result.stdout


def test_scalar_value_is_read(tmp_path):
    write_person(tmp_path, "ja", "saitama-city", "さいたま市", type_name="Organization")
    write_book(
        tmp_path, "ja", "child-allowance", '  provider: "さいたま市"\n', type_name="Book",
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout


def test_alias_answers_the_value(tmp_path):
    write_person(tmp_path, "it", "ser-ciappelletto", "Ser Ciappelletto", extra='aliases: ["Ciappelletto"]\n')
    write_book(tmp_path, "it", "decameron", '  character:\n    - "Ciappelletto"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout
    assert "Person/ser-ciappelletto" in result.stdout


def test_slug_answers_the_value(tmp_path):
    write_person(tmp_path, "en", "filostrato", "Some Other Title")
    write_book(tmp_path, "en", "decameron", '  character:\n    - "filostrato"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout


def test_value_is_matched_after_normalization(tmp_path):
    write_person(tmp_path, "it", "ser-ciappelletto", "Ser  Ciappelletto")
    write_book(tmp_path, "it", "decameron", '  character:\n    - "ser ciappelletto"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout


def test_subtype_of_a_range_candidate_answers_the_value(tmp_path):
    """Novelist is a Person, so it may answer a character value."""
    write_person(tmp_path, "it", "boccaccio", "Boccaccio", type_name="Novelist")
    write_book(tmp_path, "it", "decameron", '  character:\n    - "Boccaccio"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout


# ── Range gating ─────────────────────────────────────────────────────────────

def test_type_must_be_in_the_property_range(tmp_path):
    """A Person page does not answer `genre`, whose only entity range is DefinedTerm."""
    write_person(tmp_path, "it", "comedy", "Comedy")
    write_book(tmp_path, "it", "decameron", '  genre: "Comedy"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_mixed_range_still_reports_its_entity_candidate(tmp_path):
    write(tmp_path, "it", "DefinedTerm", "novella", 'title: "Novella"\nlang: it\ntype: "schema:DefinedTerm"\n')
    write_book(tmp_path, "it", "decameron", '  genre: "Novella"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout


def test_datatype_only_property_is_skipped(tmp_path):
    write(tmp_path, "it", "DefinedTerm", "x", 'title: "978-0"\nlang: it\ntype: "schema:DefinedTerm"\n')
    write_book(tmp_path, "it", "decameron", '  isbn: "978-0"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_property_absent_from_the_vocabulary_is_skipped(tmp_path):
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write_book(tmp_path, "it", "decameron", '  notAProperty: "Filostrato"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_property_without_range_includes_is_skipped(tmp_path):
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write_book(tmp_path, "it", "decameron", '  noRange: "Filostrato"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


# ── Exclusions ───────────────────────────────────────────────────────────────

def test_removed_target_page_is_not_a_match(tmp_path):
    write_person(tmp_path, "it", "filostrato", "Filostrato", extra="status: removed\n")
    write_book(tmp_path, "it", "decameron", '  character:\n    - "Filostrato"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_removed_referring_page_is_not_scanned(tmp_path):
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write_book(
        tmp_path, "it", "decameron",
        '  character:\n    - "Filostrato"\n',
    )
    page = tmp_path / ".wikicommit" / "entity" / "it" / "Book" / "decameron.md"
    page.write_text(page.read_text(encoding="utf-8").replace("properties:", "status: removed\nproperties:"), encoding="utf-8")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_self_reference_is_not_reported(tmp_path):
    """A page naming itself is not an unlinked mention of some other page."""
    write_person(
        tmp_path, "it", "boccaccio", "Boccaccio",
        extra='properties:\n  provider: "Boccaccio"\n',
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_custom_typed_referring_page_is_still_scanned(tmp_path):
    """The range classification never consults the referring page's own type.

    A custom type has no Schema.org entry, so it cannot be a *target* — but as a
    referrer its `character` value is judged exactly as a ShortStory's would be.
    """
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write(
        tmp_path, "it", "custom/Tale", "t1",
        'title: "t1"\nlang: it\ntype: "schema:custom/Tale"\n'
        'properties:\n  character:\n    - "Filostrato"\n',
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=1" in result.stdout


def test_custom_typed_target_page_is_not_a_match(tmp_path):
    """Nothing says whether a custom type satisfies a property's range."""
    write(
        tmp_path, "it", "custom/Narrator", "filostrato",
        'title: "Filostrato"\nlang: it\ntype: "schema:custom/Narrator"\n',
    )
    write_book(tmp_path, "it", "decameron", '  character:\n    - "Filostrato"\n')
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_unknown_property_on_a_custom_typed_page_is_skipped(tmp_path):
    """A custom type's keys are not machine-validated; an invented one misses the vocabulary."""
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write(
        tmp_path, "it", "custom/Tale", "t1",
        'title: "t1"\nlang: it\ntype: "schema:custom/Tale"\n'
        'properties:\n  invented: "Filostrato"\n',
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_index_pages_are_skipped(tmp_path):
    write_person(tmp_path, "it", "filostrato", "Filostrato")
    write(
        tmp_path, "it", "Book", "index",
        'title: "Book"\nlang: it\ntype: "schema:Book"\n'
        'properties:\n  character:\n    - "Filostrato"\n',
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: unlinked=0" in result.stdout


def test_page_without_properties_block_is_skipped(tmp_path):
    write(tmp_path, "it", "Book", "decameron", 'title: "d"\nlang: it\ntype: "schema:Book"\n')
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: unlinked=0" in result.stdout


def test_non_string_values_are_skipped(tmp_path):
    write_book(tmp_path, "it", "decameron", "  character:\n    - 42\n    - \"\"\n")
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: unlinked=0" in result.stdout


# ── Distribution ─────────────────────────────────────────────────────────────

def test_template_copy_matches():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
