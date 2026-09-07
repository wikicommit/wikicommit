"""Tests for .wikicommit/scripts/check_wanted_pages.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_wanted_pages.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_wanted_pages.py"
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
    assert "SUMMARY: wanted=0" in result.stdout


# ── Basic wanted-page detection ─────────────────────────────────────────────────

def test_link_to_existing_page_is_not_wanted(tmp_path):
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
    assert "WANTED" not in result.stdout
    assert "SUMMARY: wanted=0" in result.stdout


def test_link_to_nonexistent_page_is_wanted(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="See [[DefinedTerm/hotpotqa]] for details.\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "WANTED: DefinedTerm/hotpotqa" in result.stdout
    assert "referenced by 1 pages" in result.stdout
    assert "yamada.md" in result.stdout
    assert "page: DefinedTerm/hotpotqa" in result.stdout
    assert "SUMMARY: wanted=1" in result.stdout


def test_wanted_page_referenced_by_multiple_pages_counted_once_per_referrer(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="See [[DefinedTerm/hotpotqa]] and again [[DefinedTerm/hotpotqa]].\n",
    )
    write_page(
        tmp_path, "ja", "Person", "suzuki",
        textwrap.dedent("""\
            title: "Suzuki"
            lang: ja
            type: "schema:Person"
            """),
        body="Also references [[DefinedTerm/hotpotqa]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    # Same page linking twice must not double-count; two distinct referring pages should.
    assert "referenced by 2 pages" in result.stdout
    assert "SUMMARY: wanted=1" in result.stdout


# ── Cross-language existence ─────────────────────────────────────────────────────

def test_link_to_page_existing_only_in_another_language_is_not_wanted(tmp_path):
    """check_wanted_pages.py checks existence across ALL languages, not just the
    referencer's own language or primary_lang (unlike check_wikilinks.py's
    per-lang/primary_lang WARNING case) — see Issue #340 scope."""
    write_page(
        tmp_path, "en", "Place", "tokyo",
        textwrap.dedent("""\
            title: "Tokyo"
            lang: en
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
    assert "WANTED" not in result.stdout


# ── status: removed pages still count as existing ────────────────────────────────

def test_link_to_removed_page_is_not_wanted(tmp_path):
    """A removed page still has a backing file — that's check_wikilinks.py's ERROR
    case, not this script's concern."""
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
    assert "WANTED" not in result.stdout


# ── Type-segment mismatch (Issue #563) ────────────────────────────────────────

def test_slug_existing_under_another_type_is_type_mismatch_not_wanted(tmp_path):
    """Creating the "wanted" page here would duplicate one that already exists —
    the fix is to correct the link's Type segment instead."""
    write_page(
        tmp_path, "ja", "AdministrativeArea", "saitama-city",
        textwrap.dedent("""\
            title: "さいたま市"
            lang: ja
            type: "schema:AdministrativeArea"
            """),
    )
    write_page(
        tmp_path, "ja", "GovernmentService", "ward-office",
        textwrap.dedent("""\
            title: "Ward office"
            lang: ja
            type: "schema:GovernmentService"
            """),
        body="Provided by [[Organization/saitama-city]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "WANTED:" not in result.stdout
    assert "TYPE_MISMATCH: Organization/saitama-city" in result.stdout
    assert "AdministrativeArea/saitama-city.md" in result.stdout
    assert "page: Organization/saitama-city" in result.stdout
    assert "SUMMARY: wanted=0, type_mismatch=1" in result.stdout


def test_type_mismatch_lists_every_candidate_type(tmp_path):
    for type_name in ("AdministrativeArea", "Place"):
        write_page(
            tmp_path, "ja", type_name, "saitama-city",
            textwrap.dedent(f"""\
                title: "Saitama"
                lang: ja
                type: "schema:{type_name}"
                """),
        )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="Works in [[Organization/saitama-city]].\n",
    )

    result = run(cwd=tmp_path)
    assert "AdministrativeArea/saitama-city.md" in result.stdout
    assert "Place/saitama-city.md" in result.stdout
    assert "SUMMARY: wanted=0, type_mismatch=1" in result.stdout


def test_type_mismatch_matches_across_languages(tmp_path):
    """Whether the Type segment is right does not depend on which language
    directory the page happens to live in."""
    write_page(
        tmp_path, "en", "AdministrativeArea", "saitama-city",
        textwrap.dedent("""\
            title: "Saitama City"
            lang: en
            type: "schema:AdministrativeArea"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="Works in [[Organization/saitama-city]].\n",
    )

    result = run(cwd=tmp_path)
    assert "TYPE_MISMATCH: Organization/saitama-city" in result.stdout
    assert "SUMMARY: wanted=0, type_mismatch=1" in result.stdout


def test_removed_page_under_another_type_stays_wanted(tmp_path):
    """Retargeting onto a removed page just trades this report for
    check_wikilinks.py's removed-page ERROR — no usable page backs the slug."""
    write_page(
        tmp_path, "ja", "AdministrativeArea", "saitama-city",
        textwrap.dedent("""\
            title: "Saitama"
            lang: ja
            type: "schema:AdministrativeArea"
            status: removed
            removed_at: "2026-01-01"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="Works in [[Organization/saitama-city]].\n",
    )

    result = run(cwd=tmp_path)
    assert "TYPE_MISMATCH" not in result.stdout
    assert "WANTED: Organization/saitama-city" in result.stdout
    assert "SUMMARY: wanted=1, type_mismatch=0" in result.stdout


def test_index_page_under_another_type_stays_wanted(tmp_path):
    """Every Type has an index.md, so a slug match on it says nothing about
    the link's intent."""
    write_page(
        tmp_path, "ja", "Place", "index",
        textwrap.dedent("""\
            title: "Place"
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
        body="See [[Organization/index]].\n",
    )

    result = run(cwd=tmp_path)
    assert "TYPE_MISMATCH" not in result.stdout
    assert "WANTED: Organization/index" in result.stdout


# ── Nested custom types ───────────────────────────────────────────────────────────

def test_nested_type_wanted_page(tmp_path):
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
    assert "WANTED: custom/Decision/adopt-quartz" in result.stdout
    assert "page: custom/Decision/adopt-quartz" in result.stdout


# ── Deterministic ordering ────────────────────────────────────────────────────────

def test_wanted_pages_sorted_alphabetically(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="See [[DefinedTerm/zzz]] and [[DefinedTerm/aaa]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    aaa_idx = result.stdout.index("DefinedTerm/aaa")
    zzz_idx = result.stdout.index("DefinedTerm/zzz")
    assert aaa_idx < zzz_idx


# ── Exit code always 0 ─────────────────────────────────────────────────────────────

def test_always_exits_zero_even_with_wanted_pages(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
        body="See [[DefinedTerm/hotpotqa]].\n",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0


# ── Template sync (Issue #71-style drift guard) ───────────────────────────────────

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
