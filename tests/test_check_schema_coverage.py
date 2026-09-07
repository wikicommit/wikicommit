"""Tests for .wikicommit/scripts/check_schema_coverage.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_schema_coverage.py"


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(root: Path, rel_path: str, type_value: str, status: str | None = None) -> Path:
    page = root / ".wikicommit" / "entity" / rel_path
    page.parent.mkdir(parents=True, exist_ok=True)
    status_line = f"status: {status}\n" if status else ""
    page.write_text(
        textwrap.dedent(f"""\
            ---
            title: "Test"
            lang: ja
            type: "{type_value}"
            {status_line}---

            Body.
            """),
        encoding="utf-8",
    )
    return page


def write_schema_file(root: Path, rel_path: str) -> Path:
    schema_file = root / ".wikicommit" / "schema" / rel_path
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    schema_file.write_text("---\ntitle: \"\"\n---\n", encoding="utf-8")
    return schema_file


def test_no_wiki_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: unschemaed_types=0" in result.stdout


def test_type_with_dedicated_schema_file_not_reported(tmp_path):
    write_schema_file(tmp_path, "Person.md")
    write_page(tmp_path, "ja/Person/taro.md", "schema:Person")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED:" not in result.stdout
    assert "SUMMARY: unschemaed_types=0" in result.stdout


def test_type_without_schema_file_reported(tmp_path):
    write_page(tmp_path, "ja/Game/tag.md", "schema:Game")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED: schema:Game (1 pages" in result.stdout
    assert "SUMMARY: unschemaed_types=1" in result.stdout


def test_default_md_fallback_does_not_count_as_covered(tmp_path):
    """Even though default.md exists (as it always does in a real repo), a type
    without its OWN schema file is still a coverage gap — that is the entire
    point of this script (Issue #285)."""
    write_schema_file(tmp_path, "default.md")
    write_page(tmp_path, "ja/Game/tag.md", "schema:Game")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED: schema:Game" in result.stdout
    assert "SUMMARY: unschemaed_types=1" in result.stdout


def test_removed_pages_excluded(tmp_path):
    write_page(tmp_path, "ja/Game/tag.md", "schema:Game", status="removed")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED:" not in result.stdout
    assert "SUMMARY: unschemaed_types=0" in result.stdout


def test_index_md_excluded(tmp_path):
    write_page(tmp_path, "ja/Game/index.md", "schema:Game")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED:" not in result.stdout
    assert "SUMMARY: unschemaed_types=0" in result.stdout


def test_multiple_pages_same_type_aggregated(tmp_path):
    write_page(tmp_path, "ja/Game/tag.md", "schema:Game")
    write_page(tmp_path, "ja/Game/hide-and-seek.md", "schema:Game")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED: schema:Game (2 pages" in result.stdout
    assert "SUMMARY: unschemaed_types=1" in result.stdout


def test_custom_type_resolution(tmp_path):
    write_schema_file(tmp_path, "custom/Decision.md")
    write_page(tmp_path, "ja/custom/Decision/foo.md", "schema:custom/Decision")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED:" not in result.stdout
    assert "SUMMARY: unschemaed_types=0" in result.stdout


def test_custom_type_without_schema_file_reported(tmp_path):
    write_page(tmp_path, "ja/custom/Recipe/foo.md", "schema:custom/Recipe")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED: schema:custom/Recipe (1 pages" in result.stdout
    assert "SUMMARY: unschemaed_types=1" in result.stdout


def test_non_schema_prefixed_type_ignored(tmp_path):
    write_page(tmp_path, "ja/Weird/foo.md", "NotSchemaPrefixed")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED:" not in result.stdout
    assert "SUMMARY: unschemaed_types=0" in result.stdout


def test_exact_match_only_distinct_type_strings_not_merged(tmp_path):
    write_page(tmp_path, "ja/Game/a.md", "schema:Game")
    write_page(tmp_path, "ja/Games/b.md", "schema:Games")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNCOVERED: schema:Game (1 pages" in result.stdout
    assert "UNCOVERED: schema:Games (1 pages" in result.stdout
    assert "SUMMARY: unschemaed_types=2" in result.stdout
