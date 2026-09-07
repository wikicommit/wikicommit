"""Tests for .wikicommit/scripts/check_orphans.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_orphans.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_orphans.py"
)


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(root: Path, lang: str, type_name: str, slug: str, frontmatter: str, body: str = "Body.\n") -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return page


# ── No wiki dir ───────────────────────────────────────────────────────────────

def test_no_wiki_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: orphans=0, duplicates=0" in result.stdout


# ── Orphan detection ──────────────────────────────────────────────────────────

def test_orphan_page_detected(tmp_path):
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        textwrap.dedent("""\
            title: "Tokyo"
            lang: ja
            type: "schema:Place"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "ORPHAN:" in result.stdout
    assert "tokyo.md" in result.stdout
    assert "SUMMARY: orphans=1, duplicates=0" in result.stdout


def test_linked_page_is_not_orphan(tmp_path):
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        textwrap.dedent("""\
            title: "Tokyo"
            lang: ja
            type: "schema:Place"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="Lives in [[Place/tokyo]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    orphan_lines = [line for line in result.stdout.splitlines() if line.startswith("ORPHAN:")]
    assert not any("tokyo.md" in line for line in orphan_lines)
    assert "SUMMARY: orphans=1, duplicates=0" in result.stdout  # yamada itself has no backlink


def test_wikilink_embedded_in_frontmatter_property_counts_as_backlink(tmp_path):
    """A `[[Type/slug]]` written as a `properties:` value (Issue #496 — e.g.
    `affiliation: "[[Organization/companya]]"`) must count the same as one
    in the body: this script reads the whole file as raw text and regex-
    scans it for WIKILINK_RE, never distinguishing frontmatter from body."""
    write_page(
        tmp_path, "ja", "Organization", "companya",
        textwrap.dedent("""\
            title: "CompanyA"
            lang: ja
            type: "schema:Organization"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"

            properties:
              affiliation: "[[Organization/companya]]"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    orphan_lines = [line for line in result.stdout.splitlines() if line.startswith("ORPHAN:")]
    assert not any("companya.md" in line for line in orphan_lines)


def test_cross_language_backlink_counts(tmp_path):
    """A ja page linked only from an en page should not be orphan (slug-based cross-lang match)."""
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        textwrap.dedent("""\
            title: "Tokyo"
            lang: ja
            type: "schema:Place"
            """),
    )
    write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: en
            type: "schema:Person"
            """),
        body="Lives in [[Place/tokyo]].\n",
    )

    result = run(cwd=tmp_path)
    orphan_lines = [line for line in result.stdout.splitlines() if line.startswith("ORPHAN:")]
    assert not any("tokyo" in line for line in orphan_lines)


def test_index_md_excluded_from_orphan_check(tmp_path):
    write_page(
        tmp_path, "ja", "Place", "index",
        textwrap.dedent("""\
            title: "Place index"
            lang: ja
            type: "schema:Place"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "ORPHAN:" not in result.stdout
    assert "SUMMARY: orphans=0, duplicates=0" in result.stdout


def test_page_linked_only_from_index_is_still_orphan(tmp_path):
    """index.md's own outgoing WikiLinks must not count towards a page's backlinks,
    otherwise every page listed on its auto-generated type index would be
    considered referenced and orphan detection would never fire."""
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        textwrap.dedent("""\
            title: "Tokyo"
            lang: ja
            type: "schema:Place"
            """),
    )
    write_page(
        tmp_path, "ja", "Place", "index",
        textwrap.dedent("""\
            title: "Place index"
            lang: ja
            type: "schema:Place"
            """),
        body="- [[Place/tokyo]]\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    orphan_lines = [line for line in result.stdout.splitlines() if line.startswith("ORPHAN:")]
    assert any("tokyo.md" in line for line in orphan_lines)
    assert "SUMMARY: orphans=1, duplicates=0" in result.stdout


def test_removed_page_excluded_from_orphan_check(tmp_path):
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        textwrap.dedent("""\
            title: "Tokyo"
            lang: ja
            type: "schema:Place"
            status: removed
            removed_at: "2026-01-01"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "ORPHAN:" not in result.stdout


# ── Nested custom types (Issue #105) ────────────────────────────────────────

def test_nested_type_linked_page_is_not_orphan(tmp_path):
    """A [[custom/Decision/slug]] backlink must be recognized for nested Types."""
    write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        textwrap.dedent("""\
            title: "Adopt Quartz"
            lang: ja
            type: "schema:custom/Decision"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="See [[custom/Decision/adopt-quartz]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    orphan_lines = [line for line in result.stdout.splitlines() if line.startswith("ORPHAN:")]
    assert not any("adopt-quartz.md" in line for line in orphan_lines)
    assert "SUMMARY: orphans=1, duplicates=0" in result.stdout  # yamada itself has no backlink


def test_nested_type_unlinked_page_is_orphan(tmp_path):
    """A nested-type page with no backlinks is still reported as ORPHAN."""
    write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        textwrap.dedent("""\
            title: "Adopt Quartz"
            lang: ja
            type: "schema:custom/Decision"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "ORPHAN:" in result.stdout
    assert "adopt-quartz.md" in result.stdout
    assert "SUMMARY: orphans=1, duplicates=0" in result.stdout


def test_double_slash_malformed_wikilink_does_not_match(tmp_path):
    """A malformed [[Person//foo]] (double slash) must not be treated as a
    valid backlink to Person/foo — it should behave like any other unmatched
    text, not silently resolve to type="Person/" with a mismatched key."""
    write_page(
        tmp_path, "ja", "Person", "foo",
        textwrap.dedent("""\
            title: "Foo"
            lang: ja
            type: "schema:Person"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="See [[Person//foo]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    orphan_lines = [line for line in result.stdout.splitlines() if line.startswith("ORPHAN:")]
    # foo.md is not validly referenced by the malformed link, so it correctly
    # remains an orphan rather than being silently (and incorrectly) resolved.
    assert any("foo.md" in line for line in orphan_lines)


def test_hyphenated_custom_type_wikilink_does_not_match(tmp_path):
    """A [[custom/Multi-Word/slug]] link must not match the WikiLink regex:
    custom type directory names are PascalCase without hyphens (per
    docs/DesignDoc-data.md §5.3, Issue #114), so a hyphenated Type segment is
    treated as unmatched text rather than a broken/backlink reference."""
    write_page(
        tmp_path, "ja", "custom/Multi-Word", "foo",
        textwrap.dedent("""\
            title: "Foo"
            lang: ja
            type: "schema:custom/Multi-Word"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="See [[custom/Multi-Word/foo]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    orphan_lines = [line for line in result.stdout.splitlines() if line.startswith("ORPHAN:")]
    # The hyphenated Type segment is not matched by WIKILINK_RE, so foo.md
    # remains unreferenced and correctly stays an orphan.
    assert any("foo.md" in line for line in orphan_lines)


# ── Duplicate detection ───────────────────────────────────────────────────────

def test_duplicate_pages_detected(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "taro-yamada",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert "DUPLICATE:" in result.stdout
    assert "SUMMARY: orphans=2, duplicates=1" in result.stdout


def test_duplicate_title_normalization(tmp_path):
    """Titles differing only by whitespace/case/NFKC normalization should count as duplicates."""
    write_page(
        tmp_path, "ja", "Person", "yamada-a",
        textwrap.dedent("""\
            title: "Yamada  Taro"
            lang: ja
            type: "schema:Person"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada-b",
        textwrap.dedent("""\
            title: "yamada taro"
            lang: ja
            type: "schema:Person"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert "DUPLICATE:" in result.stdout


def test_different_lang_same_title_not_duplicate(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada Taro"
            lang: ja
            type: "schema:Person"
            """),
    )
    write_page(
        tmp_path, "en", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada Taro"
            lang: en
            type: "schema:Person"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "DUPLICATE:" not in result.stdout


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")


def test_removed_page_excluded_from_duplicate_check(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-a",
        textwrap.dedent("""\
            title: "Yamada Taro"
            lang: ja
            type: "schema:Person"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada-b",
        textwrap.dedent("""\
            title: "Yamada Taro"
            lang: ja
            type: "schema:Person"
            status: removed
            removed_at: "2026-01-01"
            """),
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "DUPLICATE:" not in result.stdout


# ── ORPHAN provenance (Issue #570) ───────────────────────────────────────────

def test_orphan_line_names_its_sources(tmp_path):
    write_page(
        tmp_path, "ja", "Place", "hikawa-shrine",
        'title: "氷川神社"\nlang: ja\ntype: "schema:Place"\n'
        "sources:\n"
        "  - type: url\n    url: https://ja.wikipedia.org/wiki/A\n"
        "  - type: path\n    path: raw/overview.pdf\n",
    )
    result = run(cwd=tmp_path)
    assert "sources: https://ja.wikipedia.org/wiki/A, raw/overview.pdf" in result.stdout
    assert "SUMMARY: orphans=1" in result.stdout


def test_orphan_line_says_so_when_there_are_no_sources(tmp_path):
    write_page(tmp_path, "ja", "Place", "x", 'title: "X"\nlang: ja\ntype: "schema:Place"\n')
    result = run(cwd=tmp_path)
    assert "(no sources)" in result.stdout


def test_orphan_line_survives_a_malformed_sources_entry(tmp_path):
    write_page(
        tmp_path, "ja", "Place", "x",
        'title: "X"\nlang: ja\ntype: "schema:Place"\nsources:\n  - "just a string"\n  - type: manual\n    author: Taro\n',
    )
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "sources: Taro" in result.stdout
