"""Tests for the shared .wikicommit/scripts/_wikilink.py module (Issue #114).

Consolidates WIKILINK_RE and path->(lang, type, slug) parsing that used to be
duplicated (and drifting) across check_orphans.py, check_wikilinks.py, and
convert_wikilinks.py.
"""

import importlib.util
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "_wikilink.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "_wikilink.py"
)

# _wikilink.py sibling-imports _frontmatter (build_slug_type_index needs a page's
# status:), so the scripts directory has to be on sys.path before exec_module()
# runs it — same setup test_check_wikilinks.py already does for the same reason.
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("_wikilink", SCRIPT)
_wikilink = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wikilink)


# ── WIKILINK_RE ──────────────────────────────────────────────────────────────

def test_wikilink_re_matches_simple_type():
    m = _wikilink.WIKILINK_RE.search("See [[Person/yamada-taro]] for details.")
    assert m is not None
    assert m.group(1) == "Person"
    assert m.group(2) == "yamada-taro"


def test_wikilink_re_matches_nested_custom_type():
    m = _wikilink.WIKILINK_RE.search("See [[custom/Decision/adopt-quartz]].")
    assert m is not None
    assert m.group(1) == "custom/Decision"
    assert m.group(2) == "adopt-quartz"


def test_wikilink_re_rejects_double_slash():
    """[[Person//foo]] must not be parsed as type="Person/" (Issue #109 regression)."""
    assert _wikilink.WIKILINK_RE.search("[[Person//foo]]") is None


def test_wikilink_re_rejects_hyphenated_type_segment():
    """Custom type directory names must not contain hyphens (docs/DesignDoc-data.md
    §5.3 naming convention, Issue #114). [[custom/Multi-Word/slug]] is not
    recognized as a nested type; the Type character class only allows
    [A-Za-z0-9_]."""
    assert _wikilink.WIKILINK_RE.search("[[custom/Multi-Word/slug]]") is None


# ── parse_wiki_path ──────────────────────────────────────────────────────────

def test_parse_wiki_path_simple_type(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    page = entity_dir / "ja" / "Person" / "yamada-taro.md"
    page.parent.mkdir(parents=True)
    page.write_text("dummy", encoding="utf-8")

    assert _wikilink.parse_wiki_path(page, entity_dir) == ("ja", "Person", "yamada-taro")


def test_parse_wiki_path_nested_custom_type(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    page = entity_dir / "ja" / "custom" / "Decision" / "adopt-quartz.md"
    page.parent.mkdir(parents=True)
    page.write_text("dummy", encoding="utf-8")

    assert _wikilink.parse_wiki_path(page, entity_dir) == ("ja", "custom/Decision", "adopt-quartz")


def test_parse_wiki_path_outside_wiki_dir_returns_none(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    entity_dir.mkdir(parents=True)
    outside = tmp_path / "elsewhere" / "note.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("dummy", encoding="utf-8")

    assert _wikilink.parse_wiki_path(outside, entity_dir) is None


def test_parse_wiki_path_too_few_components_returns_none(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    page = entity_dir / "ja" / "index.md"
    page.parent.mkdir(parents=True)
    page.write_text("dummy", encoding="utf-8")

    # <lang>/<slug>.md has no Type component (fewer than 3 path parts).
    assert _wikilink.parse_wiki_path(page, entity_dir) is None


def test_parse_wiki_path_robust_to_relative_entity_dir(tmp_path, monkeypatch):
    """resolve()-based implementation must work regardless of cwd (Issue #114 §2:
    the pre-consolidation _path_to_wikilink_key lacked resolve() and could
    silently return an empty key when called from a different cwd)."""
    entity_dir_abs = tmp_path / ".wikicommit" / "entity"
    page = entity_dir_abs / "ja" / "Place" / "tokyo.md"
    page.parent.mkdir(parents=True)
    page.write_text("dummy", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = _wikilink.parse_wiki_path(
        Path(".wikicommit/entity/ja/Place/tokyo.md"), Path(".wikicommit/entity")
    )
    assert result == ("ja", "Place", "tokyo")


# ── wikicommit-init template stays in sync with the canonical module ────────

# ── build_slug_type_index() / other_types_for_slug() (Issue #563) ────────────

def _page(entity_dir: Path, lang: str, type_name: str, slug: str, extra: str = "") -> None:
    d = entity_dir / lang / type_name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        textwrap.dedent(f"""\
            ---
            title: "{slug}"
            lang: {lang}
            type: "schema:{type_name}"
            {extra}
            ---

            Body.
            """),
        encoding="utf-8",
    )


def test_build_slug_type_index_groups_types_by_slug_across_languages(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    _page(entity_dir, "ja", "AdministrativeArea", "saitama-city")
    _page(entity_dir, "en", "Place", "saitama-city")
    _page(entity_dir, "ja", "Person", "yamada")

    index = _wikilink.build_slug_type_index(entity_dir)
    assert index["saitama-city"] == {"AdministrativeArea", "Place"}
    assert index["yamada"] == {"Person"}


def test_build_slug_type_index_skips_index_and_removed_pages(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    _page(entity_dir, "ja", "Place", "index")
    _page(entity_dir, "ja", "Place", "tokyo", extra='status: removed\n            removed_at: "2026-01-01"')

    index = _wikilink.build_slug_type_index(entity_dir)
    assert "index" not in index
    assert "tokyo" not in index


def test_build_slug_type_index_on_missing_dir_is_empty(tmp_path):
    assert _wikilink.build_slug_type_index(tmp_path / "nope") == {}


def test_build_slug_type_index_ignores_assets_above_entity_dir(tmp_path):
    """check_wikilinks.py passes an absolute entity_dir, so the assets filter
    must be anchored at entity_dir — otherwise a repository that merely lives
    under a directory named "assets" indexes nothing and every Type-segment
    mismatch silently degrades back to the generic missing-page WARNING."""
    entity_dir = tmp_path / "assets" / "my-wiki" / ".wikicommit" / "entity"
    _page(entity_dir, "ja", "AdministrativeArea", "saitama-city")

    index = _wikilink.build_slug_type_index(entity_dir.resolve())
    assert index == {"saitama-city": {"AdministrativeArea"}}


def test_build_slug_type_index_still_skips_entity_assets_dir(tmp_path):
    """.wikicommit/entity/assets/ holds attachments, not pages."""
    entity_dir = tmp_path / ".wikicommit" / "entity"
    _page(entity_dir, "assets", "notes", "diagram")
    _page(entity_dir, "ja", "Person", "yamada")

    assert _wikilink.build_slug_type_index(entity_dir) == {"yamada": {"Person"}}


def test_other_types_for_slug_excludes_the_type_that_was_linked():
    index = {"saitama-city": {"AdministrativeArea", "Organization", "Place"}}
    assert _wikilink.other_types_for_slug("Organization", "saitama-city", index) == [
        "AdministrativeArea", "Place",
    ]


def test_other_types_for_slug_empty_when_slug_is_unused():
    assert _wikilink.other_types_for_slug("Organization", "nobody", {}) == []


def test_other_types_for_slug_empty_when_only_the_linked_type_has_it():
    index = {"tokyo": {"Place"}}
    assert _wikilink.other_types_for_slug("Place", "tokyo", index) == []


# ── collect_entity_pages() (Issue #677) ──────────────────────────────────────

def _entity_tree(root: Path) -> Path:
    entity = root / ".wikicommit" / "entity"
    (entity / "ja" / "Person").mkdir(parents=True)
    (entity / "ja" / "Person" / "yamada-taro.md").write_text("x\n", encoding="utf-8")
    (entity / "ja" / "Person" / "index.md").write_text("x\n", encoding="utf-8")
    (entity / "assets").mkdir(parents=True)
    (entity / "assets" / "notes.md").write_text("x\n", encoding="utf-8")
    return entity


def test_collect_entity_pages_drops_assets_and_index(tmp_path):
    entity = _entity_tree(tmp_path)

    names = [p.name for p in _wikilink.collect_entity_pages(entity)]

    assert names == ["yamada-taro.md"]


def test_collect_entity_pages_can_keep_index(tmp_path):
    entity = _entity_tree(tmp_path)

    names = sorted(p.name for p in _wikilink.collect_entity_pages(entity, include_index=True))

    assert names == ["index.md", "yamada-taro.md"]


def test_collect_entity_pages_agrees_for_relative_and_absolute_entity_dir(tmp_path, monkeypatch):
    """The bug this helper exists to retire (Issue #677) was exactly a
    disagreement between the two forms."""
    entity = _entity_tree(tmp_path)
    monkeypatch.chdir(tmp_path)

    relative = [p.name for p in _wikilink.collect_entity_pages(Path(".wikicommit/entity"))]
    absolute = [p.name for p in _wikilink.collect_entity_pages(entity.resolve())]

    assert relative == absolute == ["yamada-taro.md"]


def test_collect_entity_pages_ignores_an_assets_named_ancestor(tmp_path):
    root = tmp_path / "assets" / "wiki"
    root.mkdir(parents=True)
    entity = _entity_tree(root)

    assert [p.name for p in _wikilink.collect_entity_pages(entity.resolve())] == ["yamada-taro.md"]


def test_collect_entity_pages_keeps_a_type_or_slug_named_assets(tmp_path):
    """`assets` is only meaningful as the first segment below entity_dir — a
    Type or slug that happens to carry the name is an ordinary page."""
    entity = tmp_path / ".wikicommit" / "entity"
    (entity / "ja" / "assets").mkdir(parents=True)
    (entity / "ja" / "assets" / "page.md").write_text("x\n", encoding="utf-8")
    (entity / "ja" / "Person").mkdir(parents=True)
    (entity / "ja" / "Person" / "assets.md").write_text("x\n", encoding="utf-8")

    names = sorted(p.name for p in _wikilink.collect_entity_pages(entity))

    assert names == ["assets.md", "page.md"]


def test_collect_entity_pages_returns_empty_for_a_missing_tree(tmp_path):
    assert _wikilink.collect_entity_pages(tmp_path / "nope") == []


def test_template_copy_matches_canonical_module():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
