"""Tests for .wikicommit/scripts/validate_frontmatter.py"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "validate_frontmatter.py"
VOCAB_ENV_VAR = "WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD"

DEFAULT_SCHEMA = textwrap.dedent("""\
    ---
    wikicommit:
      frontmatter:
        required: [title, lang, type, sources]
      granularity: []
    title: ""
    type: ""
    lang: ""
    sources: []
    review_status: pending
    ---

    (2-3 paragraph overview of the subject)
    """)

PERSON_SCHEMA = textwrap.dedent("""\
    ---
    wikicommit:
      base: https://schema.org/Person
      granularity: []
    title: ""
    type: "schema:Person"
    lang: ""
    sources: []
    tags: []

    properties:
      description: ""
    ---

    (2-3 paragraph overview of the person)
    """)


def run(args: list[str], cwd: Path, vocab_fixture: Path | None = None) -> subprocess.CompletedProcess:
    """vocab_fixture, when given, points _schemaorg_vocab.py's TEST_VOCAB_PATH_ENV
    hook at a local JSON-LD file instead of the real https://schema.org/
    endpoint or the repo's committed .wikicommit/schemaorg-vocab.json cache
    (which doesn't exist under tmp_path anyway), keeping properties: tests
    network-free and deterministic."""
    env = dict(os.environ)
    if vocab_fixture is not None:
        env[VOCAB_ENV_VAR] = str(vocab_fixture)
    else:
        env.pop(VOCAB_ENV_VAR, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


# A small hand-built slice of the real schema.org JSON-LD shape (same shape as
# test_check_schema_org_type.py's FIXTURE_VOCAB): Thing <- CreativeWork <- Game,
# with "name" domainIncludes Thing (inherited by everything), "genre"
# domainIncludes CreativeWork, and "typicalAgeRange" domainIncludes Game directly.
# Also includes Person/description so PERSON_SCHEMA's own properties: block
# (description) validates against this same fixture in tests that mix the two.
FIXTURE_VOCAB = {
    "@graph": [
        {"@id": "schema:Thing", "@type": "rdfs:Class"},
        {
            "@id": "schema:CreativeWork",
            "@type": "rdfs:Class",
            "rdfs:subClassOf": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:Game",
            "@type": "rdfs:Class",
            "rdfs:subClassOf": {"@id": "schema:CreativeWork"},
        },
        {
            "@id": "schema:Person",
            "@type": "rdfs:Class",
            "rdfs:subClassOf": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:name",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:genre",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:CreativeWork"},
        },
        {
            "@id": "schema:typicalAgeRange",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Game"},
        },
        {
            "@id": "schema:description",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
        },
    ]
}


def write_vocab_fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "vocab.jsonld"
    fixture_path.write_text(json.dumps(FIXTURE_VOCAB), encoding="utf-8")
    return fixture_path


def write_schema(root: Path, name: str, content: str) -> None:
    schema_path = root / ".wikicommit" / "schema" / name
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(content, encoding="utf-8")


def write_page(root: Path, lang: str, type_name: str, slug: str, frontmatter: str, body: str = "Body text.\n") -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return page


def setup_schemas(tmp_path: Path) -> None:
    write_schema(tmp_path, "default.md", DEFAULT_SCHEMA)
    write_schema(tmp_path, "Person.md", PERSON_SCHEMA)


# ── Valid page ──────────────────────────────────────────────────────────────

def test_valid_page_no_errors(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "1 files validated, 0 errors, 0 warnings" in result.stdout


# ── Missing required field ──────────────────────────────────────────────────

def test_missing_required_field(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            lang: ja
            type: "schema:Person"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "title" in result.stdout
    assert "required field is missing" in result.stdout


# ── review_status missing → warning only ────────────────────────────────────

def test_missing_review_status_is_warning(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "review_status" in result.stdout


# ── review_status invalid value → error ─────────────────────────────────────

def test_invalid_review_status(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: bogus
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "review_status" in result.stdout


# ── review_status: curated → error (Issue #370: removed as an undocumented,
#    never-written value; only pending/reviewed are defined) ─────────────────

def test_review_status_curated_is_rejected(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: curated
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "review_status" in result.stdout


# ── Translation page: sources exempt, requires translated_from/source_commit ──

def test_translation_page_exempts_sources_but_requires_translation_fields(tmp_path):
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)

    page = write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent(f"""\
            title: "Yamada"
            lang: en
            type: "schema:Person"
            review_status: pending
            translated_from: {parent_rel}
            source_commit: "0123456789abcdef0123456789abcdef01234567"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "sources" not in result.stdout


def test_translation_page_missing_source_commit(tmp_path):
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)

    page = write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent(f"""\
            title: "Yamada"
            lang: en
            type: "schema:Person"
            review_status: pending
            translated_from: {parent_rel}
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "source_commit" in result.stdout


def test_translation_page_empty_source_commit_is_allowed(tmp_path):
    """Issue #409: wikicommit-translate writes source_commit as "" when the source page
    has no commits yet; validate_frontmatter.py must not block this (check_translation_status.py
    already flags it as STALE)."""
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)

    page = write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent(f"""\
            title: "Yamada"
            lang: en
            type: "schema:Person"
            review_status: pending
            translated_from: {parent_rel}
            source_commit: ""
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_translation_page_accepts_translated_by(tmp_path):
    """Issue #453: translated_by (mirrors generated_by, but for the model that ran
    /wikicommit-translate) is optional and must not be empty when present."""
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)

    page = write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent(f"""\
            title: "Yamada"
            lang: en
            type: "schema:Person"
            review_status: pending
            translated_from: {parent_rel}
            source_commit: "0123456789abcdef0123456789abcdef01234567"
            translated_by: "claude-sonnet-4-6"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_translation_page_empty_translated_by_is_rejected(tmp_path):
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)

    page = write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent(f"""\
            title: "Yamada"
            lang: en
            type: "schema:Person"
            review_status: pending
            translated_from: {parent_rel}
            source_commit: "0123456789abcdef0123456789abcdef01234567"
            translated_by: ""
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "translated_by" in result.stdout


# ── generated_with / translated_with (WikiCommit's own version, Issue #577) ──

def test_page_accepts_generated_with(tmp_path):
    """generated_with records which version of WikiCommit generated the page.
    Optional; its absence means the page predates the field (no back-fill)."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            generated_at: "2026-08-29"
            generated_by: "claude-opus-5"
            generated_with: "0.1.0"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_page_without_generated_with_is_accepted(tmp_path):
    """Pages generated before Issue #577 carry no generated_with and stay valid."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            generated_by: "claude-opus-5"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_page_empty_generated_with_is_rejected(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            generated_with: ""
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "generated_with" in result.stdout


# ── reviewed_by (who the `reviewed` badge belongs to, Issue #663) ─────────────

def test_page_accepts_reviewed_by(tmp_path):
    """review-issue-close-sync.yml writes the closer's GitHub login in the same
    commit that flips review_status, so the published banner can say whose
    judgment `reviewed` represents."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: reviewed
            reviewed_by: "octocat"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_page_without_reviewed_by_is_accepted(tmp_path):
    """Absence is the normal state, not a gap: pages reviewed before the field
    existed are not back-filled, and a wiki that never runs the workflow never
    gets one."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: reviewed
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_page_empty_reviewed_by_is_rejected(tmp_path):
    """Same contract as generated_by: absent means "not recorded", and an empty
    string would make the two indistinguishable."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: reviewed
            reviewed_by: ""
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "reviewed_by" in result.stdout


def test_reviewed_by_is_not_read_as_a_misplaced_schema_property(tmp_path):
    """It is a WikiCommit bookkeeping field, so it belongs at the top level and
    must not trip validate_schema_properties()'s flat-field scan (Issue #495)."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: reviewed
            reviewed_by: "octocat"
            properties:
              jobTitle: "Engineer"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "reviewed_by" not in result.stdout


def _translation_page_with(tmp_path, extra_lines: str):
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)
    return write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent(f"""\
            title: "Yamada"
            lang: en
            type: "schema:Person"
            review_status: pending
            translated_from: {parent_rel}
            source_commit: "0123456789abcdef0123456789abcdef01234567"
            """) + extra_lines,
    )


def test_translation_page_accepts_translated_with(tmp_path):
    page = _translation_page_with(tmp_path, 'translated_with: "0.1.0"\n')

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_translation_page_empty_translated_with_is_rejected(tmp_path):
    page = _translation_page_with(tmp_path, 'translated_with: ""\n')

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "translated_with" in result.stdout


# ── Synthesized page: sources exempt, requires valid derived_from ───────────

def test_synthesized_page_exempts_sources_but_requires_derived_from_fields(tmp_path):
    setup_schemas(tmp_path)
    parent1 = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent2 = write_page(
        tmp_path, "ja", "Person", "suzuki",
        textwrap.dedent("""\
            title: "Suzuki"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent1_rel = parent1.relative_to(tmp_path)
    parent2_rel = parent2.relative_to(tmp_path)

    page = write_page(
        tmp_path, "ja", "DefinedTerm", "synthesized-topic",
        textwrap.dedent(f"""\
            title: "Synthesized Topic"
            lang: ja
            type: "schema:DefinedTerm"
            review_status: pending
            derived_from:
              - path: {parent1_rel}
                source_commit: "0123456789abcdef0123456789abcdef01234567"
              - path: {parent2_rel}
                source_commit: "abcdef0123456789abcdef0123456789abcdef01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "sources" not in result.stdout


def test_synthesized_page_empty_derived_from_is_error(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "DefinedTerm", "synthesized-topic",
        textwrap.dedent("""\
            title: "Synthesized Topic"
            lang: ja
            type: "schema:DefinedTerm"
            review_status: pending
            derived_from: []
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "derived_from" in result.stdout


def test_synthesized_page_derived_from_nonexistent_path(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "DefinedTerm", "synthesized-topic",
        textwrap.dedent("""\
            title: "Synthesized Topic"
            lang: ja
            type: "schema:DefinedTerm"
            review_status: pending
            derived_from:
              - path: .wikicommit/entity/ja/Person/nonexistent.md
                source_commit: "0123456789abcdef0123456789abcdef01234567"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "derived_from[0].path" in result.stdout


def test_synthesized_page_derived_from_invalid_source_commit(tmp_path):
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)

    page = write_page(
        tmp_path, "ja", "DefinedTerm", "synthesized-topic",
        textwrap.dedent(f"""\
            title: "Synthesized Topic"
            lang: ja
            type: "schema:DefinedTerm"
            review_status: pending
            derived_from:
              - path: {parent_rel}
                source_commit: "too-short"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "derived_from[0].source_commit" in result.stdout


def test_synthesized_page_empty_derived_from_source_commit_is_allowed(tmp_path):
    """Issue #409: same empty-string-means-uncommitted convention as translated_from/
    source_commit, applied to derived_from[].source_commit (wikicommit-synthesize)."""
    setup_schemas(tmp_path)
    parent = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )
    parent_rel = parent.relative_to(tmp_path)

    page = write_page(
        tmp_path, "ja", "DefinedTerm", "synthesized-topic",
        textwrap.dedent(f"""\
            title: "Synthesized Topic"
            lang: ja
            type: "schema:DefinedTerm"
            review_status: pending
            derived_from:
              - path: {parent_rel}
                source_commit: ""
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


# ── index.md: sources exempt ─────────────────────────────────────────────────

def test_index_page_exempts_sources(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "index",
        textwrap.dedent("""\
            title: "Person index"
            lang: ja
            type: "schema:Person"
            review_status: pending
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


# ── sources item validation ──────────────────────────────────────────────────

def test_sources_file_missing_hash_prefix(tmp_path):
    setup_schemas(tmp_path)
    (tmp_path / "raw.pdf").write_text("dummy", encoding="utf-8")
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: path
                path: raw.pdf
                hash: abc123
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "sha256:" in result.stdout


def test_sources_file_nonexistent_path(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: path
                path: nonexistent.pdf
                hash: sha256:abc123
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "file does not exist" in result.stdout


def test_sources_invalid_type(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: bogus
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "invalid type" in result.stdout


def test_sources_url_valid(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: url
                url: "https://example.com/article"
                hash: "sha256:abc123"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_sources_url_missing_https_prefix(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: url
                url: "http://example.com/article"
                hash: "sha256:abc123"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "https://" in result.stdout


def test_sources_url_missing_hash_prefix(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: url
                url: "https://example.com/article"
                hash: "abc123"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "sha256:" in result.stdout


def test_sources_license_is_optional_and_accepted_verbatim(tmp_path):
    """Issue #558: `license` is an optional free-form field on any source type.
    WikiCommit records what the operator wrote and does not judge whether the
    value is a correct or applicable license, so no vocabulary check applies."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: url
                url: "https://it.wikipedia.org/wiki/Decameron"
                hash: "sha256:abc123"
                license: "CC-BY-SA-4.0"
              - type: url
                url: "https://example.com/terms"
                hash: "sha256:def456"
                license: "Saitama City website terms of use"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_sources_blank_license_is_error(tmp_path):
    """An empty string would render as "a license is recorded" on the published
    page while carrying no information; "unknown" is expressed by omitting the
    field entirely."""
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: url
                url: "https://example.com/article"
                hash: "sha256:abc123"
                license: ""
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "sources[0].license" in result.stdout


def test_sources_empty_list_is_error(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources: []
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "at least one source is required" in result.stdout


# ── Format validations ───────────────────────────────────────────────────────

def test_invalid_lang_format(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: JPN
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "lang" in result.stdout


def test_type_missing_schema_prefix(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "schema:" in result.stdout


def test_invalid_expires_at_format(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            expires_at: "2026/06/01"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "expires_at" in result.stdout


def test_invalid_wikidata_prefix(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            wikidata: "Q12345"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "wikidata" in result.stdout


# ── Missing schema file falls back to default.md ─────────────────────────────

def test_unknown_type_falls_back_to_default_with_warning(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Place", "tokyo",
        textwrap.dedent("""\
            title: "Tokyo"
            lang: ja
            type: "schema:Place"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "schema file not found" in result.stdout


# ── type: not in Schema.org vocabulary → error (Issue #512) ──────────────────

def test_nonexistent_type_with_local_schema_file_is_error(tmp_path):
    """A typo'd/non-standard `type:` (not in Schema.org's vocabulary) must be
    flagged even when a local .wikicommit/schema/<Type>.md happens to exist
    for it — resolve_type_schema()'s WARNING only fires when the local file
    is *missing*, so without this check the page passes silently and
    properties: is never machine-verified against anything (Issue #512)."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    write_schema(
        tmp_path, "Xyzzy.md",
        textwrap.dedent("""\
            ---
            wikicommit:
              base: https://schema.org/Xyzzy
              granularity: []
            title: ""
            type: "schema:Xyzzy"
            lang: ""
            sources: []
            tags: []

            properties:
              description: ""
            ---

            (2-3 paragraph overview)
            """),
    )
    page = write_page(
        tmp_path, "ja", "Xyzzy", "example",
        textwrap.dedent("""\
            title: "Example"
            lang: ja
            type: "schema:Xyzzy"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "type" in result.stdout
    assert "schema:Xyzzy" in result.stdout
    assert "does not exist in the Schema.org vocabulary" in result.stdout


def test_nonexistent_type_with_no_local_schema_file_reports_both(tmp_path):
    """The far more common real-world trigger for Issue #512: a plain typo
    with no matching local schema file built for it at all (unlike the
    previous test, which pre-creates one to isolate the new check). This
    must now fire *both* diagnostics for the same `type:` value — the new
    ERROR (not in Schema.org's vocabulary) and the pre-existing
    resolve_type_schema() WARNING (no local schema file, falling back to
    default.md) — since they check different things (vocabulary membership
    vs. local file presence) and can legitimately both be true at once. This
    locks in that co-occurrence as intended, rather than leaving it as an
    untested code path."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = write_page(
        tmp_path, "ja", "Preson", "example",
        textwrap.dedent("""\
            title: "Example"
            lang: ja
            type: "schema:Preson"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "schema:Preson does not exist in the Schema.org vocabulary" in result.stdout
    assert "WARNING" in result.stdout
    assert "schema file not found: .wikicommit/schema/Preson.md" in result.stdout


def test_nonexistent_type_properties_not_flagged_individually(tmp_path):
    """Once type: itself is reported as an error, properties: keys under it
    should not also be individually flagged — there's no vocabulary entry to
    check them against, so validate_schema_properties() must stop at the
    type-level error instead of falling through to the per-key loop."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    write_schema(
        tmp_path, "Xyzzy.md",
        textwrap.dedent("""\
            ---
            wikicommit:
              base: https://schema.org/Xyzzy
              granularity: []
            title: ""
            type: "schema:Xyzzy"
            lang: ""
            sources: []
            tags: []

            properties:
              anything: ""
            ---

            (2-3 paragraph overview)
            """),
    )
    page = write_page(
        tmp_path, "ja", "Xyzzy", "example",
        textwrap.dedent("""\
            title: "Example"
            lang: ja
            type: "schema:Xyzzy"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"

            properties:
              anything: "value"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 1
    assert "properties.anything" not in result.stdout


def test_custom_type_still_unaffected_by_vocabulary_check(tmp_path):
    """schema:custom/... types must keep bypassing the Issue #512 check —
    they intentionally have no Schema.org vocabulary entry at all (validated
    separately, by a human, via wikicommit-schema-propose)."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    write_schema(
        tmp_path, "custom/Decision.md",
        textwrap.dedent("""\
            ---
            wikicommit:
              base: https://schema.org/CreativeWork
              granularity: []
            title: ""
            type: "schema:custom/Decision"
            sources: []
            tags: []

            properties:
              description: ""
            ---

            (summary of the decision)
            """),
    )
    page = write_page(
        tmp_path, "ja", "custom/Decision", "adopt-x",
        textwrap.dedent("""\
            title: "Adopt X"
            lang: ja
            type: "schema:custom/Decision"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


# ── properties: field validation (Issue #495) ────────────────────────────────

def _person_properties_page(tmp_path: Path, properties_yaml: str) -> Path:
    return write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent(f"""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"

            properties:
            {properties_yaml}
            """),
    )


def test_properties_valid_key_passes(tmp_path):
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = _person_properties_page(tmp_path, '  description: "A senior engineer."')

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_properties_unknown_key_is_error(tmp_path):
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = _person_properties_page(tmp_path, '  notAProperty: "value"')

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "properties.notAProperty" in result.stdout
    assert "does not exist in the Schema.org vocabulary" in result.stdout


def test_properties_key_outside_type_domain_is_error(tmp_path):
    """typicalAgeRange domainIncludes Game, not Person (or any of Person's
    ancestors) in FIXTURE_VOCAB — using it on a Person page must fail."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = _person_properties_page(tmp_path, '  typicalAgeRange: "adult"')

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "properties.typicalAgeRange" in result.stdout
    assert "belongs to neither" in result.stdout


def test_properties_key_inherited_from_ancestor_passes(tmp_path):
    """`name` domainIncludes Thing, an ancestor of Person via rdfs:subClassOf
    in FIXTURE_VOCAB — must be accepted through the ancestry walk, not just
    an exact domainIncludes match on Person itself."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = _person_properties_page(tmp_path, '  name: "Yamada Taro"')

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_properties_not_a_dict_is_error(tmp_path):
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            properties: "not a dict"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "properties" in result.stdout
    assert "must be a dict" in result.stdout


def test_properties_custom_type_skips_vocabulary_validation(tmp_path):
    """schema:custom/... types have no Schema.org vocabulary entry — their
    properties are documented in prose in the schema file and reviewed by a
    human, not machine-verified here (docs/DesignDoc-data.md §5.3)."""
    setup_schemas(tmp_path)
    write_schema(
        tmp_path, "custom/Decision.md",
        textwrap.dedent("""\
            ---
            wikicommit:
              base: https://schema.org/CreativeWork
              granularity: []
            title: ""
            type: "schema:custom/Decision"
            lang: ""
            sources: []

            properties:
              decidedAt: ""
            ---

            (summary of the decision)
            """),
    )
    vocab = write_vocab_fixture(tmp_path)
    page = write_page(
        tmp_path, "ja", "custom/Decision", "adopt-x",
        textwrap.dedent("""\
            title: "Adopt X"
            lang: ja
            type: "schema:custom/Decision"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"

            properties:
              decidedAt: "2026-01-01"
              notInSchemaOrgEither: "still fine"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_properties_vocabulary_unavailable_degrades_to_warning(tmp_path):
    """When the Schema.org vocabulary can't be obtained at all (no committed
    cache under tmp_path, and here a deliberately nonexistent override path
    standing in for a network failure), properties: validation must degrade
    to a WARNING rather than an ERROR that blocks the quality gate — a
    missing/stale schemaorg-vocab.json is an expected, non-blocking state
    (docs/DesignDoc-ScriptSpec.md)."""
    setup_schemas(tmp_path)
    missing_vocab = tmp_path / "does-not-exist.jsonld"
    page = _person_properties_page(tmp_path, '  description: "A senior engineer."')

    result = run([str(page)], cwd=tmp_path, vocab_fixture=missing_vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "WARNING" in result.stdout
    assert "properties" in result.stdout
    assert "validation was skipped because the Schema.org vocabulary could not be loaded" in result.stdout


def test_properties_empty_block_is_not_an_error(tmp_path):
    """`properties:` with nothing indented under it parses as YAML null, not
    a dict — this must be treated as "no type-specific properties," not a
    `dict 型でなければなりません` false positive."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            properties:
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_flat_schema_property_is_error(tmp_path):
    """A Schema.org property left flat at the top level instead of nested
    under `properties:` (e.g. an LLM reverting to the pre-Issue-#495 shape)
    must be caught — nothing else in this script inspects unrecognized
    top-level keys."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            description: "A senior engineer."
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert ": description:" in result.stdout
    assert "nest it under properties:" in result.stdout


def test_flat_field_outside_type_domain_is_not_flagged(tmp_path):
    """A flat top-level key that happens to share a name with a real
    Schema.org property, but one that doesn't belong to this page's type
    (e.g. `typicalAgeRange` domainIncludes Game, not Person in
    FIXTURE_VOCAB), must not be flagged — only properties that actually
    belong to *this* type trigger the nesting requirement."""
    setup_schemas(tmp_path)
    vocab = write_vocab_fixture(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            typicalAgeRange: "adult"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_custom_type_flat_field_is_not_flagged(tmp_path):
    """Custom types have no Schema.org vocabulary entry, so the flat-field
    scan (which only fires for keys that resolve as real properties of the
    page's type) never applies to them."""
    setup_schemas(tmp_path)
    write_schema(
        tmp_path, "custom/Decision.md",
        textwrap.dedent("""\
            ---
            wikicommit:
              base: https://schema.org/CreativeWork
              granularity: []
            title: ""
            type: "schema:custom/Decision"
            lang: ""
            sources: []

            properties:
              decidedAt: ""
            ---

            (summary of the decision)
            """),
    )
    vocab = write_vocab_fixture(tmp_path)
    page = write_page(
        tmp_path, "ja", "custom/Decision", "adopt-x",
        textwrap.dedent("""\
            title: "Adopt X"
            lang: ja
            type: "schema:custom/Decision"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            decidedAt: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path, vocab_fixture=vocab)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


# ── Removed page fields ──────────────────────────────────────────────────────

def test_removed_page_requires_removed_at(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            status: removed
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "removed_at" in result.stdout


def test_removed_page_merged_requires_merged_into(tmp_path):
    setup_schemas(tmp_path)
    page = write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            status: removed
            removed_at: "2026-01-01"
            removed_reason: merged
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            """),
    )

    result = run([str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "merged_into" in result.stdout


# ── No target files ───────────────────────────────────────────────────────────

def test_no_target_files(tmp_path):
    setup_schemas(tmp_path)
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: 0 files validated, 0 errors, 0 warnings" in result.stdout


# ── Path <-> type consistency (Issue #545) ──────────────────────────────────

CUSTOM_PRACTICE_SCHEMA = textwrap.dedent("""\
    ---
    wikicommit:
      base: https://schema.org/CreativeWork
      provenance: schema-propose
      granularity: []
    title: ""
    type: "schema:custom/Practice"
    sources: []
    tags: []
    ---

    (summary of the practice)
    """)

MANUAL_SOURCE_FM = textwrap.dedent("""\
    review_status: pending
    sources:
      - type: manual
        author: test
        created_at: "2026-01-01"
    """)


def test_custom_type_page_outside_custom_dir_is_error(tmp_path):
    """The exact round5 shape: type says schema:custom/Practice but the page
    sits in <lang>/Practice/, so [[custom/Practice/<slug>]] can never resolve."""
    setup_schemas(tmp_path)
    write_schema(tmp_path, "custom/Practice.md", CUSTOM_PRACTICE_SCHEMA)
    write_page(
        tmp_path, "en", "Practice", "parallel-coding-agents",
        'title: "Parallel coding agents"\nlang: en\ntype: "schema:custom/Practice"\n'
        + MANUAL_SOURCE_FM,
    )
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "schema:custom/Practice" in result.stdout
    assert "Practice/" in result.stdout
    # The suggested move target names the custom/ location.
    assert ".wikicommit/entity/en/custom/Practice/parallel-coding-agents.md" in result.stdout


def test_custom_type_page_inside_custom_dir_is_ok(tmp_path):
    setup_schemas(tmp_path)
    write_schema(tmp_path, "custom/Practice.md", CUSTOM_PRACTICE_SCHEMA)
    write_page(
        tmp_path, "en", "custom/Practice", "parallel-coding-agents",
        'title: "Parallel coding agents"\nlang: en\ntype: "schema:custom/Practice"\n'
        + MANUAL_SOURCE_FM,
    )
    result = run([], tmp_path)
    assert result.returncode == 0
    assert "does not match the directory" not in result.stdout


def test_standard_type_page_in_wrong_type_dir_is_error(tmp_path):
    """Not custom-specific: a Person page filed under Place/ is the same defect."""
    setup_schemas(tmp_path)
    write_page(
        tmp_path, "ja", "Place", "yamada",
        'title: "Yamada"\nlang: ja\ntype: "schema:Person"\n' + MANUAL_SOURCE_FM,
    )
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "does not match the directory" in result.stdout


def test_index_page_type_matches_its_directory(tmp_path):
    """rebuild_index.py writes type: schema:<type_name> including the custom/
    sub-path, so index.md pages must pass unchanged."""
    setup_schemas(tmp_path)
    write_schema(tmp_path, "custom/Practice.md", CUSTOM_PRACTICE_SCHEMA)
    index = tmp_path / ".wikicommit" / "entity" / "en" / "custom" / "Practice" / "index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        '---\ntitle: "Practice"\nlang: en\ntype: "schema:custom/Practice"\n---\n\n',
        encoding="utf-8",
    )
    result = run([], tmp_path)
    assert result.returncode == 0
    assert "does not match the directory" not in result.stdout


def test_page_directly_under_entity_dir_is_skipped(tmp_path):
    """A page that doesn't resolve to <lang>/<Type>/<slug>.md predates this
    layout — old/new coexistence, so report nothing rather than blocking."""
    setup_schemas(tmp_path)
    stray = tmp_path / ".wikicommit" / "entity" / "stray.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text(
        '---\ntitle: "Stray"\nlang: ja\ntype: "schema:Person"\n' + MANUAL_SOURCE_FM + "---\n\nBody.\n",
        encoding="utf-8",
    )
    result = run([str(stray.relative_to(tmp_path))], tmp_path)
    assert "does not match the directory" not in result.stdout


def test_type_without_schema_prefix_reports_only_the_prefix_error(tmp_path):
    """The prefix error is already reported on its own; don't pile a second,
    derived complaint about the directory on top of it."""
    setup_schemas(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada",
        'title: "Yamada"\nlang: ja\ntype: "Person"\n' + MANUAL_SOURCE_FM,
    )
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "does not start with the `schema:` prefix" in result.stdout
    assert "does not match the directory" not in result.stdout
