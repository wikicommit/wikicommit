"""Tests for .wikicommit/scripts/check_installed_type_usage.py (Issue #565)

Uses a local JSON-LD vocabulary fixture via WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD,
the same network-free hook check_schema_org_type.py's own tests use.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".wikicommit" / "scripts" / "check_installed_type_usage.py"
TEMPLATE_SCRIPT = (
    REPO_ROOT
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts"
    / "check_installed_type_usage.py"
)
ENV_VAR = "WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD"

# Thing <- Place <- CivicStructure <- {Park, Museum}; Thing <- Person
FIXTURE_VOCAB = {
    "@graph": [
        {"@id": "schema:Thing", "@type": "rdfs:Class"},
        {"@id": "schema:Place", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:CivicStructure", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Place"}},
        {"@id": "schema:Park", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:CivicStructure"}},
        {"@id": "schema:Museum", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:CivicStructure"}},
        {"@id": "schema:Person", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
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


def write_schema(root: Path, type_name: str, provenance: str = "collect") -> Path:
    path = root / ".wikicommit" / "schema" / f"{type_name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nwikicommit:\n  provenance: {provenance}\n  granularity: []\n'
        f'title: ""\ntype: "schema:{type_name}"\n---\n\nTemplate body.\n',
        encoding="utf-8",
    )
    return path


def write_page(root: Path, type_name: str, slug: str, extra: str = "", lang: str = "ja") -> Path:
    path = root / ".wikicommit" / "entity" / lang / type_name / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\nlang: {lang}\ntype: "schema:{type_name}"\n{extra}---\n\nBody.\n',
        encoding="utf-8",
    )
    return path


# ── Nothing to report ────────────────────────────────────────────────────────

def test_no_schema_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: unused=0, ancestor_fallback=0" in result.stdout


def test_used_type_with_no_installed_descendant_is_quiet(tmp_path):
    write_schema(tmp_path, "Person")
    write_page(tmp_path, "Person", "yamada-taro")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=0, ancestor_fallback=0" in result.stdout


# ── UNUSED ───────────────────────────────────────────────────────────────────

def test_installed_type_with_zero_pages_is_unused(tmp_path):
    write_schema(tmp_path, "Park", provenance="collect")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout
    assert "UNUSED: schema:Park" in result.stdout
    assert "provenance: collect" in result.stdout


def test_default_provenance_type_is_exempt(tmp_path):
    """A base type ships with every wiki; zero pages says nothing about it."""
    write_schema(tmp_path, "Place", provenance="default")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=0, ancestor_fallback=0" in result.stdout


def _write_schema_without_provenance(root: Path, type_name: str) -> None:
    path = root / ".wikicommit" / "schema" / f"{type_name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nwikicommit:\n  granularity: []\ntitle: ""\ntype: "schema:{type_name}"\n---\n\nBody.\n',
        encoding="utf-8",
    )


def _write_config(root: Path, base_types: list[str]) -> None:
    path = root / ".wikicommit" / "config.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "schema:\n  base_types: [" + ", ".join(base_types) + "]\n", encoding="utf-8"
    )


def test_type_with_no_provenance_field_is_reported(tmp_path):
    """A missing provenance means "made before that field existed", not "default"."""
    _write_schema_without_provenance(tmp_path, "Park")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout


def test_config_base_types_stand_in_for_a_missing_provenance(tmp_path):
    """A wiki initialized before Issue #519 would otherwise report its whole shipped set."""
    _write_schema_without_provenance(tmp_path, "Place")
    _write_schema_without_provenance(tmp_path, "Park")
    _write_config(tmp_path, ["Place", "Person"])
    result = run(cwd=tmp_path)
    # Place is a configured base type, Park is not.
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout
    assert "schema:Park" in result.stdout
    assert "schema:Place" not in result.stdout


def test_explicit_non_default_provenance_beats_config_base_types(tmp_path):
    """A file that says where it came from is believed over the config list."""
    write_schema(tmp_path, "Place", provenance="collect")
    _write_config(tmp_path, ["Place"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout


def test_unreadable_config_only_costs_extra_lines(tmp_path):
    _write_schema_without_provenance(tmp_path, "Place")
    (tmp_path / ".wikicommit" / "config.yml").write_text("  : [\n", encoding="utf-8")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout


def test_removed_pages_do_not_count_as_usage(tmp_path):
    write_schema(tmp_path, "Park")
    write_page(tmp_path, "Park", "omiya-park", extra="status: removed\n")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout


def test_index_pages_do_not_count_as_usage(tmp_path):
    write_schema(tmp_path, "Park")
    write_page(tmp_path, "Park", "index")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout


def test_pages_in_any_language_count(tmp_path):
    write_schema(tmp_path, "Park")
    write_page(tmp_path, "Park", "omiya-park", lang="en")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=0, ancestor_fallback=0" in result.stdout


# ── ANCESTOR_FALLBACK ────────────────────────────────────────────────────────

def test_pages_on_an_ancestor_with_an_installed_descendant(tmp_path):
    """The saitama case: Park.md installed, seven parks written as Place."""
    write_schema(tmp_path, "Place", provenance="default")
    write_schema(tmp_path, "Park")
    write_page(tmp_path, "Place", "omiya-park")
    write_page(tmp_path, "Park", "akigase-park")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=0, ancestor_fallback=1" in result.stdout
    assert "ANCESTOR_FALLBACK: schema:Place has 1 page(s)" in result.stdout
    assert "schema:Park" in result.stdout


def test_indirect_descendant_counts(tmp_path):
    """Park is a Place through CivicStructure, not directly."""
    write_schema(tmp_path, "Place", provenance="default")
    write_schema(tmp_path, "Park")
    write_page(tmp_path, "Place", "somewhere")
    write_page(tmp_path, "Park", "omiya-park")
    result = run(cwd=tmp_path)
    assert "ancestor_fallback=1" in result.stdout


def test_multiple_installed_descendants_are_all_listed(tmp_path):
    write_schema(tmp_path, "Place", provenance="default")
    write_schema(tmp_path, "Park")
    write_schema(tmp_path, "Museum")
    write_page(tmp_path, "Place", "somewhere")
    write_page(tmp_path, "Park", "omiya-park")
    write_page(tmp_path, "Museum", "a-museum")
    result = run(cwd=tmp_path)
    assert "schema:Museum, schema:Park" in result.stdout


def test_unused_type_is_not_also_reported_as_a_fallback(tmp_path):
    """A type with zero pages cannot be sitting on anything."""
    write_schema(tmp_path, "Place", provenance="default")
    write_schema(tmp_path, "Park")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=1, ancestor_fallback=0" in result.stdout


def test_custom_types_are_out_of_scope(tmp_path):
    """A custom type has no vocabulary entry to place in a subClassOf chain."""
    path = tmp_path / ".wikicommit" / "schema" / "custom" / "Decision.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '---\nwikicommit:\n  provenance: schema-propose\ntitle: ""\n'
        'type: "schema:custom/Decision"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=0, ancestor_fallback=0" in result.stdout


def test_default_md_is_ignored(tmp_path):
    path = tmp_path / ".wikicommit" / "schema" / "default.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\nwikicommit:\n  frontmatter:\n    required: []\ntitle: ""\ntype: ""\n---\n\nBody.\n', encoding="utf-8")
    result = run(cwd=tmp_path)
    assert "SUMMARY: unused=0, ancestor_fallback=0" in result.stdout


# ── Distribution ─────────────────────────────────────────────────────────────

def test_template_copy_matches():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
