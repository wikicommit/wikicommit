"""Tests for the shared .wikicommit/scripts/_frontmatter.py module (Issue #212).

Consolidates YAML frontmatter parsing that used to be duplicated (and
drifting) across convert_wikilinks.py, check_wikilinks.py, check_orphans.py,
check_translation_status.py, and validate_frontmatter.py.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "_frontmatter.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "_frontmatter.py"
)

_spec = importlib.util.spec_from_file_location("_frontmatter", SCRIPT)
_frontmatter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_frontmatter)


# ── parse_frontmatter_text ───────────────────────────────────────────────────

def test_parse_frontmatter_text_returns_dict_on_success():
    fm, err = _frontmatter.parse_frontmatter_text('---\ntitle: "Yamada Taro"\nlang: ja\n---\n\nBody.\n')
    assert err == ""
    assert fm == {"title": "Yamada Taro", "lang": "ja"}


def test_parse_frontmatter_text_no_block_is_not_an_error():
    fm, err = _frontmatter.parse_frontmatter_text("Just a plain markdown file.\n")
    assert (fm, err) == ({}, "")


def test_parse_frontmatter_text_empty_block_returns_empty_dict():
    fm, err = _frontmatter.parse_frontmatter_text("---\n---\n\nBody.\n")
    assert (fm, err) == ({}, "")


def test_parse_frontmatter_text_unterminated_block_is_an_error():
    fm, err = _frontmatter.parse_frontmatter_text("---\ntitle: Unterminated\n\nBody with no closing marker.\n")
    assert fm is None
    assert "no closing `---`" in err


def test_parse_frontmatter_text_malformed_yaml_is_an_error():
    fm, err = _frontmatter.parse_frontmatter_text("---\ntitle: [unclosed\n---\n\nBody.\n")
    assert fm is None
    assert err != ""


def test_parse_frontmatter_text_non_mapping_yaml_is_an_error():
    """A frontmatter block that parses to a YAML list (not a mapping) must be
    reported as an error rather than returned as-is: callers do fm.get(...)
    and would crash on a list (the pre-consolidation `yaml.safe_load(...) or
    {}` pattern in check_wikilinks.py / check_orphans.py had this bug)."""
    fm, err = _frontmatter.parse_frontmatter_text("---\n- a\n- b\n---\n\nBody.\n")
    assert fm is None
    assert err != ""


def test_parse_frontmatter_text_handles_crlf_line_endings():
    """The old per-script FRONTMATTER_RE explicitly handled CRLF via `\\r?`;
    the line-scan replacement must preserve that (Windows-authored pages)."""
    fm, err = _frontmatter.parse_frontmatter_text('---\r\ntitle: "CRLF Test"\r\n---\r\n\r\nBody.\r\n')
    assert err == ""
    assert fm == {"title": "CRLF Test"}


# ── parse_frontmatter (file-based) ──────────────────────────────────────────

def test_parse_frontmatter_reads_bom_prefixed_file(tmp_path):
    """A BOM-prefixed page (as some Windows editors write) must not silently
    fail frontmatter detection (Issue #212: some scripts read with
    utf-8-sig, others with plain utf-8, before consolidation)."""
    page = tmp_path / "page.md"
    page.write_bytes("---\ntitle: BOM Test\n---\n\nBody.\n".encode("utf-8-sig"))

    fm, err = _frontmatter.parse_frontmatter(page)
    assert err == ""
    assert fm == {"title": "BOM Test"}


def test_parse_frontmatter_missing_file_is_an_error(tmp_path):
    fm, err = _frontmatter.parse_frontmatter(tmp_path / "does-not-exist.md")
    assert fm is None
    assert err != ""


# ── parse_frontmatter_or_warn ───────────────────────────────────────────────
# Shared by check_wikilinks.py and check_translation_status.py, which both
# only need a best-effort dict and treat any parse failure as "no frontmatter".

def test_parse_frontmatter_or_warn_returns_dict_on_success(tmp_path):
    page = tmp_path / "page.md"
    page.write_text('---\ntitle: "Yamada Taro"\n---\n\nBody.\n', encoding="utf-8")

    assert _frontmatter.parse_frontmatter_or_warn(page) == {"title": "Yamada Taro"}


def test_parse_frontmatter_or_warn_falls_back_to_empty_dict_on_error(tmp_path, capsys):
    page = tmp_path / "page.md"
    page.write_text("---\ntitle: Unterminated\n\nBody with no closing marker.\n", encoding="utf-8")

    assert _frontmatter.parse_frontmatter_or_warn(page) == {}
    assert "WARNING:" in capsys.readouterr().out


# ── parse_frontmatter_and_body_text ─────────────────────────────────────────
# Used by search_index.py (Issue #231), which needs the body text separately
# from the frontmatter fields to build the FTS5 index.

def test_parse_frontmatter_and_body_text_splits_fm_and_body():
    fm, err, body = _frontmatter.parse_frontmatter_and_body_text(
        '---\ntitle: "Yamada Taro"\nlang: ja\n---\n\nBody text here.\n'
    )
    assert err == ""
    assert fm == {"title": "Yamada Taro", "lang": "ja"}
    assert body == "\nBody text here.\n"


def test_parse_frontmatter_and_body_text_no_block_returns_whole_content_as_body():
    fm, err, body = _frontmatter.parse_frontmatter_and_body_text("Just a plain markdown file.\n")
    assert (fm, err) == ({}, "")
    assert body == "Just a plain markdown file.\n"


def test_parse_frontmatter_and_body_text_unterminated_block_falls_back_to_full_content():
    content = "---\ntitle: Unterminated\n\nBody with no closing marker.\n"
    fm, err, body = _frontmatter.parse_frontmatter_and_body_text(content)
    assert fm is None
    assert "no closing `---`" in err
    assert body == content


def test_parse_frontmatter_and_body_text_non_mapping_yaml_still_returns_body():
    """Even when the frontmatter itself is invalid, the body must still be
    isolated from it (search_index.py needs it to decide what NOT to index,
    but must not accidentally index the frontmatter block as body text)."""
    fm, err, body = _frontmatter.parse_frontmatter_and_body_text("---\n- a\n- b\n---\n\nBody.\n")
    assert fm is None
    assert err != ""
    assert body == "\nBody.\n"


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75, #231) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
