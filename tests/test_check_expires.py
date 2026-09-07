"""Tests for .wikicommit/scripts/check_expires.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_expires.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_expires.py"
)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(root: Path, lang: str, type_name: str, slug: str, frontmatter: str) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\nBody.\n", encoding="utf-8")
    return page


def test_no_wiki_dir(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: expired=0" in result.stdout


def test_expired_page_detected(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            expires_at: "2026-06-01"
            """),
    )

    result = run(["--today=2026-06-23"], cwd=tmp_path)
    assert result.returncode == 0
    assert "EXPIRED:" in result.stdout
    assert "page: .wikicommit/entity/ja/Person/yamada.md" in result.stdout
    assert "SUMMARY: expired=1" in result.stdout


def test_expires_at_equal_today_is_expired(tmp_path):
    """expires_at == today should count as expired (same-day cutoff)."""
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            expires_at: "2026-06-23"
            """),
    )

    result = run(["--today=2026-06-23"], cwd=tmp_path)
    assert result.returncode == 0
    assert "EXPIRED:" in result.stdout
    assert "SUMMARY: expired=1" in result.stdout


def test_future_expires_at_not_expired(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            expires_at: "2027-06-01"
            """),
    )

    result = run(["--today=2026-06-23"], cwd=tmp_path)
    assert result.returncode == 0
    assert "EXPIRED:" not in result.stdout
    assert "SUMMARY: expired=0" in result.stdout


def test_no_expires_at_field_ignored(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            """),
    )

    result = run(["--today=2026-06-23"], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: expired=0" in result.stdout


def test_removed_page_ignored_even_if_expired(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            expires_at: "2020-01-01"
            status: removed
            removed_at: "2026-01-01"
            """),
    )

    result = run(["--today=2026-06-23"], cwd=tmp_path)
    assert result.returncode == 0
    assert "EXPIRED:" not in result.stdout
    assert "SUMMARY: expired=0" in result.stdout


def test_invalid_expires_at_format_warns_but_does_not_crash(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            expires_at: "not-a-date"
            """),
    )

    result = run(["--today=2026-06-23"], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "SUMMARY: expired=0" in result.stdout


def test_defaults_to_system_date_when_no_today_flag(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada",
        textwrap.dedent("""\
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            expires_at: "2999-01-01"
            """),
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "EXPIRED:" not in result.stdout


def test_invalid_today_flag_warns_but_does_not_crash(tmp_path):
    result = run(["--today=2026/06/23"], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" in result.stdout
    assert "SUMMARY: expired=0" in result.stdout


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75, #231) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
