"""Tests for the shared .wikicommit/scripts/_schemaorg_vocab.py module (Issue #495).

Consolidates Schema.org vocabulary loading/caching and domainIncludes/
rdfs:subClassOf ancestry logic shared by check_schema_org_type.py and
validate_frontmatter.py. All tests point WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD at
a local fixture (or leave it unset with an isolated cwd) instead of the real
https://schema.org/ endpoint, so the suite stays network-free and
deterministic.
"""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "_schemaorg_vocab.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "_schemaorg_vocab.py"
)

# _schemaorg_vocab.py sibling-imports _frontmatter (installed_standard_types()
# reads each schema file's `type:`), so the scripts directory has to be on
# sys.path before exec_module() runs it — same setup test_wikilink_shared.py
# already does for the same reason.
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("_schemaorg_vocab", SCRIPT)
_schemaorg_vocab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schemaorg_vocab)

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
        # Text is directly tagged schema:DataType; URL is a DataType only via
        # its rdfs:subClassOf chain (subClassOf Text) — mirrors the real
        # Schema.org vocabulary's "URL has no direct tag" case (Issue #496).
        {"@id": "schema:Text", "@type": ["rdfs:Class", "schema:DataType"]},
        {
            "@id": "schema:URL",
            "@type": "rdfs:Class",
            "rdfs:subClassOf": {"@id": "schema:Text"},
        },
        {
            "@id": "schema:name",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:typicalAgeRange",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Game"},
        },
        {
            "@id": "schema:gameItem",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Game"},
            "schema:rangeIncludes": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:sameAs",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": {"@id": "schema:URL"},
        },
        {
            "@id": "schema:about",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": [{"@id": "schema:Thing"}, {"@id": "schema:Text"}],
        },
        {
            "@id": "schema:noRange",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Thing"},
        },
        # Sibling of Game (both subClassOf Thing directly, not each other's
        # ancestor) plus an Organization-only property, for
        # properties_available_to()'s exclusion test (Issue #497).
        {"@id": "schema:Organization", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {
            "@id": "schema:numberOfEmployees",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Organization"},
        },
    ]
}


# ── property_in_domain() ─────────────────────────────────────────────────────

def test_property_in_domain_true_for_direct_match():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    ancestry = _schemaorg_vocab.ancestors("Game", index["types"])
    assert _schemaorg_vocab.property_in_domain("typicalAgeRange", ancestry, index["properties"]) is True


def test_property_in_domain_true_via_ancestor():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    ancestry = _schemaorg_vocab.ancestors("Game", index["types"])
    assert _schemaorg_vocab.property_in_domain("name", ancestry, index["properties"]) is True


def test_property_in_domain_false_when_wrong_domain():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    ancestry = _schemaorg_vocab.ancestors("CreativeWork", index["types"])
    assert _schemaorg_vocab.property_in_domain("typicalAgeRange", ancestry, index["properties"]) is False


def test_property_in_domain_none_when_not_in_vocab():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    ancestry = _schemaorg_vocab.ancestors("Game", index["types"])
    assert _schemaorg_vocab.property_in_domain("notARealProperty", ancestry, index["properties"]) is None


# ── is_in_datatype_lineage() / entity_range_candidates() (Issue #496) ───────

def test_is_in_datatype_lineage_true_for_direct_tag():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    assert _schemaorg_vocab.is_in_datatype_lineage("Text", index["types"]) is True


def test_is_in_datatype_lineage_true_via_ancestor():
    """URL carries no schema:DataType tag of its own — only its
    rdfs:subClassOf ancestor (Text) does. This is the exact case that
    motivated walking the whole ancestor chain rather than checking the
    type itself only."""
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    assert _schemaorg_vocab.is_in_datatype_lineage("URL", index["types"]) is True


def test_is_in_datatype_lineage_false_for_entity_type():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    assert _schemaorg_vocab.is_in_datatype_lineage("Game", index["types"]) is False


def test_entity_range_candidates_none_when_not_in_vocab():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    assert _schemaorg_vocab.entity_range_candidates("notARealProperty", index["properties"], index["types"]) is None


def test_entity_range_candidates_entity_only():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    entity_types, datatype_types = _schemaorg_vocab.entity_range_candidates(
        "gameItem", index["properties"], index["types"]
    )
    assert entity_types == ["Thing"]
    assert datatype_types == []


def test_entity_range_candidates_datatype_only_via_lineage():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    entity_types, datatype_types = _schemaorg_vocab.entity_range_candidates(
        "sameAs", index["properties"], index["types"]
    )
    assert entity_types == []
    assert datatype_types == ["URL"]


def test_entity_range_candidates_mixed():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    entity_types, datatype_types = _schemaorg_vocab.entity_range_candidates(
        "about", index["properties"], index["types"]
    )
    assert entity_types == ["Thing"]
    assert datatype_types == ["Text"]


def test_entity_range_candidates_empty_when_no_range_declared():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    entity_types, datatype_types = _schemaorg_vocab.entity_range_candidates(
        "noRange", index["properties"], index["types"]
    )
    assert entity_types == []
    assert datatype_types == []


# ── _build_index() populates is_datatype/range (Issue #496) ─────────────────

def test_build_index_populates_is_datatype_and_range():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    assert index["types"]["Text"]["is_datatype"] is True
    assert index["types"]["Game"]["is_datatype"] is False
    assert index["properties"]["gameItem"]["range"] == ["Thing"]


# ── properties_available_to() (Issue #497) ───────────────────────────────────

def test_properties_available_to_includes_own_and_inherited():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    available = _schemaorg_vocab.properties_available_to("Game", index["types"], index["properties"])
    assert set(available.keys()) == {"gameItem", "typicalAgeRange", "name", "sameAs", "about", "noRange"}


def test_properties_available_to_excludes_unrelated_sibling_type():
    """numberOfEmployees is Organization-only — Organization is a sibling of
    Game (both subClassOf Thing directly), not an ancestor, so it must not
    appear for Game."""
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    available = _schemaorg_vocab.properties_available_to("Game", index["types"], index["properties"])
    assert "numberOfEmployees" not in available

    org_available = _schemaorg_vocab.properties_available_to("Organization", index["types"], index["properties"])
    assert org_available["numberOfEmployees"] == ["Organization"]


def test_properties_available_to_reports_declaring_ancestor():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    available = _schemaorg_vocab.properties_available_to("Game", index["types"], index["properties"])
    assert available["name"] == ["Thing"]
    assert available["gameItem"] == ["Game"]


def test_properties_available_to_empty_for_unknown_type():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    assert _schemaorg_vocab.properties_available_to("NotARealType", index["types"], index["properties"]) == {}


# ── _build_index() robustness against malformed @graph entries ──────────────

def test_build_index_skips_non_dict_graph_entries():
    """A malformed dump entry (e.g. a bare string) must be skipped, not
    crash the whole build with an AttributeError."""
    vocab = {"@graph": ["not-a-dict", *FIXTURE_VOCAB["@graph"]]}
    index = _schemaorg_vocab._build_index(vocab)
    assert "Game" in index["types"]
    assert "typicalAgeRange" in index["properties"]


# ── load_or_build_index() cache/fetch robustness ─────────────────────────────

def write_fixture(tmp_path: Path, content: dict | str) -> Path:
    fixture_path = tmp_path / "vocab.jsonld"
    if isinstance(content, str):
        fixture_path.write_text(content, encoding="utf-8")
    else:
        fixture_path.write_text(json.dumps(content), encoding="utf-8")
    return fixture_path


def test_load_or_build_index_uses_test_override(tmp_path, monkeypatch):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    monkeypatch.setenv(_schemaorg_vocab.TEST_VOCAB_PATH_ENV, str(fixture))
    index, err = _schemaorg_vocab.load_or_build_index()
    assert err == ""
    assert "Game" in index["types"]


def test_load_or_build_index_reports_missing_override_as_error(tmp_path, monkeypatch):
    monkeypatch.setenv(_schemaorg_vocab.TEST_VOCAB_PATH_ENV, str(tmp_path / "does-not-exist.jsonld"))
    index, err = _schemaorg_vocab.load_or_build_index()
    assert index is None
    assert err != ""


def test_load_or_build_index_reports_malformed_json_as_error(tmp_path, monkeypatch):
    fixture = write_fixture(tmp_path, "not valid json{{{")
    monkeypatch.setenv(_schemaorg_vocab.TEST_VOCAB_PATH_ENV, str(fixture))
    index, err = _schemaorg_vocab.load_or_build_index()
    assert index is None
    assert err != ""


def test_load_or_build_index_reports_non_utf8_response_as_error_not_crash(tmp_path, monkeypatch):
    """A non-UTF-8 fetch response (e.g. a mangled CDN error page) must
    surface as (None, error_message), not an uncaught UnicodeDecodeError."""
    fixture = tmp_path / "vocab.jsonld"
    fixture.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    monkeypatch.setenv(_schemaorg_vocab.TEST_VOCAB_PATH_ENV, str(fixture))
    index, err = _schemaorg_vocab.load_or_build_index()
    assert index is None
    assert err != ""


def test_load_or_build_index_rejects_malformed_shape_cache_and_rebuilds(tmp_path, monkeypatch):
    """A committed .wikicommit/schemaorg-vocab.json that parses as valid JSON
    but doesn't have the expected {"types": ..., "properties": ...} shape
    (hand-edited, bad merge, stale checkout) must be discarded and rebuilt
    rather than crash every later `index["types"]` access with a KeyError."""
    monkeypatch.chdir(tmp_path)
    vocab_path = tmp_path / ".wikicommit" / "schemaorg-vocab.json"
    vocab_path.parent.mkdir(parents=True)
    vocab_path.write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")

    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    monkeypatch.setenv(_schemaorg_vocab.TEST_VOCAB_PATH_ENV, str(fixture))

    index, err = _schemaorg_vocab.load_or_build_index()
    assert err == ""
    assert "Game" in index["types"]


def test_load_or_build_index_rejects_pre_496_cache_and_rebuilds(tmp_path, monkeypatch):
    """A cache written before Issue #496 has the right top-level envelope
    ({"types": dict, "properties": dict}) but is missing the per-entry
    "is_datatype"/"range" keys _build_index() now writes. Accepting it as-is
    would silently degrade --show-range to reporting nothing (a missing
    "range" key defaults to []) or, worse, misclassify a real DataType as an
    entity type (a missing "is_datatype" key reads as falsy, same as a
    confirmed non-DataType) — so it must be detected and rebuilt, not
    silently accepted."""
    monkeypatch.chdir(tmp_path)
    vocab_path = tmp_path / ".wikicommit" / "schemaorg-vocab.json"
    vocab_path.parent.mkdir(parents=True)
    pre_496_shape = {
        "types": {"Game": {"parents": [], "comment": ""}},  # no "is_datatype"
        "properties": {"name": {"domain": ["Thing"]}},  # no "range"
    }
    vocab_path.write_text(json.dumps(pre_496_shape), encoding="utf-8")

    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    monkeypatch.setenv(_schemaorg_vocab.TEST_VOCAB_PATH_ENV, str(fixture))

    index, err = _schemaorg_vocab.load_or_build_index()
    assert err == ""
    assert "is_datatype" in index["types"]["Game"]
    assert "range" in index["properties"]["gameItem"]


def test_is_well_shaped_index_true_for_current_shape():
    index = _schemaorg_vocab._build_index(FIXTURE_VOCAB)
    assert _schemaorg_vocab._is_well_shaped_index(index) is True


def test_is_well_shaped_index_false_when_entry_missing_new_keys():
    assert _schemaorg_vocab._is_well_shaped_index(
        {"types": {"Game": {"parents": []}}, "properties": {}}
    ) is False
    assert _schemaorg_vocab._is_well_shaped_index(
        {"types": {}, "properties": {"name": {"domain": []}}}
    ) is False


def test_no_vocab_file_written_when_using_test_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    monkeypatch.setenv(_schemaorg_vocab.TEST_VOCAB_PATH_ENV, str(fixture))
    _schemaorg_vocab.load_or_build_index()
    assert not (tmp_path / ".wikicommit" / "schemaorg-vocab.json").exists()


# ── wikicommit-init template stays in sync with the canonical module ────────

def test_template_copy_matches_canonical_module():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
