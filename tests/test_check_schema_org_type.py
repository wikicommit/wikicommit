"""Tests for .wikicommit/scripts/check_schema_org_type.py

All tests point WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD at a small local JSON-LD
fixture instead of the real https://schema.org/ endpoint, so the suite stays
network-free and deterministic (see the script's TEST_VOCAB_PATH_ENV hook).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_schema_org_type.py"
ENV_VAR = "WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD"

# A small hand-built slice of the real schema.org JSON-LD shape:
# Thing <- CreativeWork <- Game, with:
#   - "name" domainIncludes Thing (available to everything via inheritance)
#   - "genre" domainIncludes CreativeWork (available to Game via ancestry)
#   - "typicalAgeRange" / "gameItem" domainIncludes Game directly
# Plus, for --show-range (Issue #496):
#   - Text is directly tagged schema:DataType; URL is a DataType only via its
#     rdfs:subClassOf chain (subClassOf Text) — the same "URL has no direct
#     tag" case the real Schema.org vocabulary has and this feature exists to
#     handle (see is_in_datatype_lineage() in _schemaorg_vocab.py)
#   - "gameItem" rangeIncludes Thing (entity-only)
#   - "sameAs" rangeIncludes URL (DataType-only, via lineage not a direct tag)
#   - "about" rangeIncludes [Thing, Text] (mixed entity + DataType)
#   - "noRange" has no rangeIncludes at all (nothing to report)
# Plus, for --list-properties (Issue #497):
#   - "typicalAgeRange"/"gameItem" carry an rdfs:comment, to test that
#     --list-properties surfaces it
#   - Organization (a sibling of Game, both subClassOf Thing) and its
#     Organization-only property "numberOfEmployees", to test that
#     --list-properties for Game correctly excludes properties declared on
#     an unrelated type outside Game's own ancestry
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
            "@id": "schema:genre",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:CreativeWork"},
        },
        {
            "@id": "schema:typicalAgeRange",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Game"},
            "rdfs:comment": "The typical expected age range, e.g. '7-9', '11-'.",
        },
        {
            "@id": "schema:gameItem",
            "@type": "rdf:Property",
            "schema:domainIncludes": [{"@id": "schema:Game"}],
            "schema:rangeIncludes": {"@id": "schema:Thing"},
            "rdfs:comment": "An item is an object within the game world.",
        },
        {"@id": "schema:Organization", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {
            "@id": "schema:numberOfEmployees",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Organization"},
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
    ]
}


def write_fixture(tmp_path: Path, content: dict | str) -> Path:
    fixture_path = tmp_path / "vocab.jsonld"
    if isinstance(content, str):
        fixture_path.write_text(content, encoding="utf-8")
    else:
        fixture_path.write_text(json.dumps(content), encoding="utf-8")
    return fixture_path


def run(args: list[str], cwd: Path, fixture_path: Path | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if fixture_path is not None:
        env[ENV_VAR] = str(fixture_path)
    else:
        env.pop(ENV_VAR, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


def test_type_exists_no_properties(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "OK: schema:Game exists in the Schema.org vocabulary" in result.stdout
    assert "SUMMARY: type=schema:Game, checked=1, errors=0" in result.stdout


def test_type_accepts_bare_name_without_prefix(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "Game"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "OK: schema:Game exists in the Schema.org vocabulary" in result.stdout


def test_type_does_not_exist(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:FooBarNonexistent"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: schema:FooBarNonexistent does not exist in the Schema.org vocabulary" in result.stdout
    assert "SUMMARY: type=schema:FooBarNonexistent, checked=1, errors=1" in result.stdout


def test_property_belongs_directly(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--property", "typicalAgeRange"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "OK: typicalAgeRange belongs to schema:Game (or one of its ancestor types)" in result.stdout
    assert "SUMMARY: type=schema:Game, checked=2, errors=0" in result.stdout


def test_multiple_properties_belonging_directly(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Game", "--property", "typicalAgeRange", "--property", "gameItem"],
        cwd=tmp_path,
        fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "SUMMARY: type=schema:Game, checked=3, errors=0" in result.stdout


def test_property_belongs_via_ancestor(tmp_path):
    """'genre' is only declared on CreativeWork, Game's parent — this exercises
    the ancestor-chain traversal, not just a direct domainIncludes hit."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--property", "genre"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "OK: genre belongs to schema:Game (or one of its ancestor types)" in result.stdout


def test_property_exists_but_does_not_belong(tmp_path):
    """'name' exists but only on Thing... wait, Thing is an ancestor of Game too,
    so use a property scoped to an unrelated type instead."""
    vocab = dict(FIXTURE_VOCAB)
    vocab["@graph"] = FIXTURE_VOCAB["@graph"] + [
        {"@id": "schema:Person", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {
            "@id": "schema:jobTitle",
            "@type": "rdf:Property",
            "schema:domainIncludes": {"@id": "schema:Person"},
        },
    ]
    fixture = write_fixture(tmp_path, vocab)
    result = run(["--type", "schema:Game", "--property", "jobTitle"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: jobTitle belongs to neither schema:Game nor any of its ancestor types" in result.stdout


def test_property_not_in_vocab_at_all(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--property", "totallyMadeUpProperty"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: totallyMadeUpProperty does not exist in the Schema.org vocabulary" in result.stdout


def test_missing_type_makes_property_checks_fail_too(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:FooBarNonexistent", "--property", "name"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: schema:FooBarNonexistent does not exist in the Schema.org vocabulary" in result.stdout
    assert "ERROR: schema:FooBarNonexistent does not exist, so the domain of name cannot be verified" in result.stdout
    assert "SUMMARY: type=schema:FooBarNonexistent, checked=2, errors=2" in result.stdout


def test_vocab_fetch_failure_reported_as_error(tmp_path):
    """Pointing the override at a nonexistent file exercises the same failure
    path a real network error would take (OSError), without touching the
    network."""
    missing_fixture = tmp_path / "does-not-exist.jsonld"
    result = run(["--type", "schema:Game"], cwd=tmp_path, fixture_path=missing_fixture)
    assert result.returncode == 1
    assert "ERROR: the Schema.org vocabulary could not be loaded" in result.stdout


def test_malformed_vocab_json_reported_as_error(tmp_path):
    fixture = write_fixture(tmp_path, "not valid json{{{")
    result = run(["--type", "schema:Game"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: the Schema.org vocabulary could not be loaded" in result.stdout


def test_no_vocab_file_written_when_using_test_override(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    run(["--type", "schema:Game"], cwd=tmp_path, fixture_path=fixture)
    assert not (tmp_path / ".wikicommit" / "schemaorg-vocab.json").exists()


# ── --show-range (Issue #496) ────────────────────────────────────────────────

def test_show_range_entity_only(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Game", "--property", "gameItem", "--show-range"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "RANGE: gameItem references entity types only (candidates: Thing)" in result.stdout
    assert "[[Type/slug]]" in result.stdout


def test_show_range_datatype_only_via_lineage(tmp_path):
    """URL carries no direct schema:DataType tag — it's only reachable via
    its rdfs:subClassOf chain (subClassOf Text), the exact case
    is_in_datatype_lineage() exists to handle."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Thing", "--property", "sameAs", "--show-range"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "RANGE: sameAs references data types only (candidates: URL)" in result.stdout
    assert "No WikiLink is needed" in result.stdout


def test_show_range_mixed(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Thing", "--property", "about", "--show-range"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "RANGE: about mixes entity types and data types" in result.stdout
    assert "entity candidates: Thing" in result.stdout
    assert "data type candidates: Text" in result.stdout


def test_show_range_no_range_declared_prints_nothing(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Thing", "--property", "noRange", "--show-range"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "RANGE:" not in result.stdout


def test_show_range_omitted_without_flag(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Game", "--property", "gameItem"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "RANGE:" not in result.stdout


def test_show_range_not_printed_for_failed_property(tmp_path):
    """A property that fails domainIncludes verification (here, one that
    doesn't exist in the vocabulary at all) has no OK: line and thus no
    RANGE: line either — nothing worth reporting range info for."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Game", "--property", "doesNotExistAtAll", "--show-range"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 1
    assert "RANGE:" not in result.stdout


# ── --list-properties (Issue #497) ───────────────────────────────────────────

def test_list_properties_includes_own_and_inherited(tmp_path):
    """Game's own properties (typicalAgeRange, gameItem) plus everything
    inherited via its rdfs:subClassOf ancestry (genre from CreativeWork,
    name/sameAs/about/noRange from Thing) must all be listed."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--list-properties"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    names = [line.split("\t")[0] for line in lines if "\t" in line]
    assert names == sorted(names)  # alphabetical
    assert set(names) == {"about", "gameItem", "genre", "name", "noRange", "sameAs", "typicalAgeRange"}
    assert "SUMMARY: type=schema:Game, properties=7" in result.stdout


def test_list_properties_excludes_unrelated_type_property(tmp_path):
    """numberOfEmployees is Organization-only — Organization is a sibling of
    Game (both subClassOf Thing directly), not an ancestor of Game, so it
    must not appear in Game's --list-properties output."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--list-properties"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "numberOfEmployees" not in result.stdout

    result_org = run(["--type", "schema:Organization", "--list-properties"], cwd=tmp_path, fixture_path=fixture)
    assert "numberOfEmployees\tOrganization" in result_org.stdout


def test_list_properties_declaring_type_shows_inherited_ancestor(tmp_path):
    """`name` is declared on Thing, not Game — the declaring-type column for
    a Game query must show the actual declaring ancestor (Thing), not Game
    itself."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--list-properties"], cwd=tmp_path, fixture_path=fixture)
    name_line = next(line for line in result.stdout.splitlines() if line.startswith("name\t"))
    assert name_line.split("\t")[1] == "Thing"

    game_item_line = next(line for line in result.stdout.splitlines() if line.startswith("gameItem\t"))
    assert game_item_line.split("\t")[1] == "Game"


def test_list_properties_entity_range_column(tmp_path):
    """The third column reports entity-type WikiLink candidates (Issue #496
    integration): gameItem's is Thing, sameAs's is "-" (URL is DataType-only
    via lineage), about's is Thing (mixed — Text is dropped), noRange's is
    "-" (no rangeIncludes declared at all)."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--list-properties"], cwd=tmp_path, fixture_path=fixture)
    columns = {line.split("\t")[0]: line.split("\t")[2] for line in result.stdout.splitlines() if "\t" in line}
    assert columns["gameItem"] == "Thing"
    assert columns["sameAs"] == "-"
    assert columns["about"] == "Thing"
    assert columns["noRange"] == "-"


def test_list_properties_includes_comment(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:Game", "--list-properties"], cwd=tmp_path, fixture_path=fixture)
    assert "typicalAgeRange\tGame\t-\tThe typical expected age range, e.g. '7-9', '11-'." in result.stdout


def test_list_properties_requires_type(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--list-properties"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "--type" in result.stdout


def test_list_properties_nonexistent_type_is_error(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--type", "schema:FooBarNonexistent", "--list-properties"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: schema:FooBarNonexistent does not exist in the Schema.org vocabulary" in result.stdout


def test_list_properties_takes_priority_over_property_verification(tmp_path):
    """When --type, --list-properties, and --property are all given,
    --list-properties wins — --property is ignored, not processed."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Game", "--property", "doesNotExistAtAll", "--list-properties"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "doesNotExistAtAll" not in result.stdout
    assert "SUMMARY: type=schema:Game, properties=" in result.stdout


def test_list_type_names_takes_priority_over_list_properties(tmp_path):
    """--list-type-names alongside --type/--list-properties still wins, same as
    it already does over --property (existing behavior, unchanged)."""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(
        ["--type", "schema:Game", "--list-properties", "--list-type-names"],
        cwd=tmp_path, fixture_path=fixture,
    )
    assert result.returncode == 0
    assert "SUMMARY: types=" in result.stdout
    assert "SUMMARY: type=schema:Game" not in result.stdout


def test_list_type_names_prints_names_without_descriptions(tmp_path):
    """段階 1 は名前だけを返す（Issue #798）。

    説明文まで毎回積んでいたことが 147 KB の正体であり、そこを落とすのが
    この 2 段階化の全部である。名前の行に説明文が混ざっていないことは、
    削減が実際に効いていることの唯一の直接的な検証になる。
    """
    vocab = {
        "@graph": FIXTURE_VOCAB["@graph"] + [
            {
                "@id": "schema:Game",  # duplicate id with a comment this time — last write wins in _build_index
                "@type": "rdfs:Class",
                "rdfs:subClassOf": {"@id": "schema:CreativeWork"},
                "rdfs:comment": "The Game type covers ... typical use is board games etc.",
            },
        ]
    }
    fixture = write_fixture(tmp_path, vocab)
    result = run(["--list-type-names"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "Game" in result.stdout.splitlines()
    assert "The Game type covers" not in result.stdout
    assert "\t" not in result.stdout
    assert "SUMMARY: types=" in result.stdout


def test_list_type_names_ignores_type_and_property_args(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--list-type-names", "--type", "schema:FooBarNonexistent"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "ERROR:" not in result.stdout


def test_describe_prints_names_and_comments(tmp_path):
    """段階 2 は指名された型の説明文だけを返す。"""
    vocab = {
        "@graph": FIXTURE_VOCAB["@graph"] + [
            {
                "@id": "schema:Game",
                "@type": "rdfs:Class",
                "rdfs:subClassOf": {"@id": "schema:CreativeWork"},
                "rdfs:comment": "The Game type covers ... typical use is board games etc.",
            },
        ]
    }
    fixture = write_fixture(tmp_path, vocab)
    result = run(["--describe", "schema:Game"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "Game\tThe Game type covers ... typical use is board games etc." in result.stdout
    assert "SUMMARY: described=1, errors=0" in result.stdout
    # 指名していない型は出さない — それが段階 2 の存在理由である
    assert "Thing" not in result.stdout


def test_describe_accepts_a_bare_name_without_the_schema_prefix(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--describe", "Thing"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "SUMMARY: described=1, errors=0" in result.stdout


def test_describe_errors_on_a_name_not_in_the_vocabulary(tmp_path):
    """語彙に無い名前は黙って落とさず ERROR にする（Issue #798 の検討事項 6）。

    段階 1 が 933 件の実在する名前を渡している以上、戻ってこなかった名前は
    モデルの創作である。黙って省くとそれが承認ステップまで伝わらない。
    """
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--describe", "schema:FooBarNonexistent"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: schema:FooBarNonexistent does not exist" in result.stdout
    assert "SUMMARY: described=0, errors=1" in result.stdout


def test_describe_still_prints_the_valid_names_alongside_an_invalid_one(tmp_path):
    """1 件不正でも実在した分は出す — 呼び出し側が有効な候補だけで進めるため。"""
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--describe", "schema:Thing", "schema:FooBarNonexistent"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "Thing\t" in result.stdout
    assert "SUMMARY: described=1, errors=1" in result.stdout


def test_describe_collapses_embedded_newlines_in_comment(tmp_path):
    """~6% of real Schema.org type comments (e.g. '3DModel') span multiple
    lines — verified against the live vocab dump while implementing this
    (Issue #285). --describe's one-line-per-type contract must hold even
    for those, or a multi-line comment would look like extra bare entries
    to whatever parses this output."""
    vocab = {
        "@graph": [
            {
                "@id": "schema:3DModel",
                "@type": "rdfs:Class",
                "rdfs:comment": "A 3D model represents some kind of 3D content.\nSpans multiple lines in the source dump.",
            },
        ]
    }
    fixture = write_fixture(tmp_path, vocab)
    result = run(["--describe", "schema:3DModel"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert "3DModel\tA 3D model represents some kind of 3D content. Spans multiple lines in the source dump." in lines


def test_describe_handles_language_tagged_comment_object(tmp_path):
    vocab = {
        "@graph": [
            {
                "@id": "schema:Thing",
                "@type": "rdfs:Class",
                "rdfs:comment": {"@value": "The most generic type of item.", "@language": "en"},
            },
        ]
    }
    fixture = write_fixture(tmp_path, vocab)
    result = run(["--describe", "schema:Thing"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 0
    assert "Thing\tThe most generic type of item." in result.stdout


def test_list_types_is_gone(tmp_path):
    """`--list-types` は残さず削除した（Issue #798 の検討事項 5）。

    3 Skill が 2 段階へ移った時点で呼び出し元が 0 になり、消費者のいない
    受け皿を配らないという既定（Issue #553）がそのまま当たる。しかも残せば、
    プリロードすべきでないと決めたばかりの高価な経路を配布物が持ち続ける。
    """
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run(["--list-types"], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr


def test_missing_type_and_list_modes_all_absent_is_an_error(tmp_path):
    fixture = write_fixture(tmp_path, FIXTURE_VOCAB)
    result = run([], cwd=tmp_path, fixture_path=fixture)
    assert result.returncode == 1
    assert "ERROR: specify one of --type / --list-type-names / --describe / --list-installed-hierarchy" in result.stdout


# ── --list-installed-hierarchy (Issue #565) ──────────────────────────────────

# Thing <- Place <- CivicStructure <- Park; Thing <- Person
HIERARCHY_VOCAB = {
    "@graph": [
        {"@id": "schema:Thing", "@type": "rdfs:Class"},
        {"@id": "schema:Place", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
        {"@id": "schema:CivicStructure", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Place"}},
        {"@id": "schema:Park", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:CivicStructure"}},
        {"@id": "schema:Person", "@type": "rdfs:Class", "rdfs:subClassOf": {"@id": "schema:Thing"}},
    ]
}


def _write_schema_file(root: Path, type_name: str) -> None:
    path = root / ".wikicommit" / "schema" / f"{type_name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nwikicommit:\n  provenance: default\ntitle: ""\ntype: "schema:{type_name}"\n---\n\nBody.\n',
        encoding="utf-8",
    )


def _hierarchy(tmp_path: Path) -> tuple[subprocess.CompletedProcess, dict[str, str]]:
    fixture = write_fixture(tmp_path, HIERARCHY_VOCAB)
    result = run(["--list-installed-hierarchy"], tmp_path, fixture)
    rows = {
        line.split("\t")[0]: line.split("\t")[1]
        for line in result.stdout.splitlines()
        if "\t" in line
    }
    return result, rows


def test_list_installed_hierarchy_reports_installed_ancestors(tmp_path):
    for name in ("Place", "Park", "Person"):
        _write_schema_file(tmp_path, name)
    result, rows = _hierarchy(tmp_path)
    assert result.returncode == 0
    assert rows["Park"] == "Place"
    assert rows["Place"] == "-"
    assert rows["Person"] == "-"
    assert "SUMMARY: installed_types=3" in result.stdout


def test_list_installed_hierarchy_orders_ancestors_nearest_first(tmp_path):
    for name in ("Place", "CivicStructure", "Park"):
        _write_schema_file(tmp_path, name)
    _result, rows = _hierarchy(tmp_path)
    assert rows["Park"] == "CivicStructure, Place"


def test_list_installed_hierarchy_only_reports_installed_ancestors(tmp_path):
    """CivicStructure sits between the two but is not installed, so it is not named."""
    for name in ("Place", "Park"):
        _write_schema_file(tmp_path, name)
    _result, rows = _hierarchy(tmp_path)
    assert rows["Park"] == "Place"


def test_list_installed_hierarchy_skips_custom_types(tmp_path):
    _write_schema_file(tmp_path, "Place")
    path = tmp_path / ".wikicommit" / "schema" / "custom" / "Decision.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\ntitle: ""\ntype: "schema:custom/Decision"\n---\n\nBody.\n', encoding="utf-8")
    result, _rows = _hierarchy(tmp_path)
    assert "SUMMARY: installed_types=1" in result.stdout
    assert "custom" not in result.stdout


def test_list_installed_hierarchy_with_no_schema_dir(tmp_path):
    result, _rows = _hierarchy(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: installed_types=0" in result.stdout
