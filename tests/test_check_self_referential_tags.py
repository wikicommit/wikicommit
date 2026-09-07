"""Tests for .wikicommit/scripts/check_self_referential_tags.py (Issue #571)"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".wikicommit" / "scripts" / "check_self_referential_tags.py"
TEMPLATE_SCRIPT = (
    REPO_ROOT
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts"
    / "check_self_referential_tags.py"
)


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=cwd, check=False
    )


def write_page(
    root: Path, type_name: str, slug: str, title: str, tags: list[str],
    lang: str = "ja", extra: str = "",
) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    listed = "".join(f'  - "{tag}"\n' for tag in tags)
    page.write_text(
        f'---\ntitle: "{title}"\nlang: {lang}\ntype: "schema:{type_name}"\n'
        f"{extra}tags:\n{listed}---\n\nBody.\n",
        encoding="utf-8",
    )
    return page


# ── Nothing to report ────────────────────────────────────────────────────────

def test_no_wiki_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


def test_cross_cutting_tags_are_quiet(tmp_path):
    write_page(tmp_path, "Place", "minuma-tanbo", "見沼田んぼ", ["緑地", "治水"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


def test_partial_overlap_with_the_title_is_not_reported(tmp_path):
    """`見沼` on a page titled `見沼田んぼ` groups it with the rest of that area."""
    write_page(tmp_path, "Place", "minuma-tanbo", "見沼田んぼ", ["見沼"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


def test_page_without_tags_is_skipped(tmp_path):
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Place"
    page_dir.mkdir(parents=True)
    (page_dir / "x.md").write_text(
        '---\ntitle: "X"\nlang: ja\ntype: "schema:Place"\n---\n\nBody.\n', encoding="utf-8"
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


# ── TITLE_ECHO ───────────────────────────────────────────────────────────────

def test_tag_equal_to_the_title_is_reported(tmp_path):
    write_page(tmp_path, "Place", "minuma-tanbo", "見沼田んぼ", ["見沼田んぼ", "緑地"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=1, type_echo=0" in result.stdout
    assert 'TITLE_ECHO:' in result.stdout and "見沼田んぼ" in result.stdout
    assert "page: " in result.stdout


def test_title_match_is_normalized(tmp_path):
    write_page(tmp_path, "Person", "yamada", "Taro  Yamada", ["taro yamada"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=1, type_echo=0" in result.stdout


# ── TYPE_ECHO ────────────────────────────────────────────────────────────────

def test_tag_equal_to_the_type_is_reported(tmp_path):
    write_page(tmp_path, "Person", "yamada", "山田太郎", ["person"], lang="en")
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=1" in result.stdout
    assert "TYPE_ECHO:" in result.stdout


def test_prefixed_type_string_is_matched(tmp_path):
    write_page(tmp_path, "Person", "yamada", "山田太郎", ["schema:Person"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=1" in result.stdout


def test_hyphenated_spelling_of_a_type_is_matched(tmp_path):
    write_page(tmp_path, "GovernmentService", "x", "窓口", ["government-service"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=1" in result.stdout


def test_custom_type_matches_both_spellings(tmp_path):
    for tag, expected in (("Decision", 1), ("custom/Decision", 1)):
        root = tmp_path / tag.replace("/", "_")
        write_page(root, "custom/Decision", "d1", "ある決定", [tag])
        result = run(cwd=root)
        assert f"SUMMARY: title_echo=0, type_echo={expected}" in result.stdout, tag


def test_a_translated_type_name_is_a_known_miss(tmp_path):
    """No translation of the Schema.org vocabulary exists here, by design."""
    write_page(tmp_path, "Museum", "x", "岩槻人形博物館", ["博物館"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


# ── Exclusions ───────────────────────────────────────────────────────────────

def test_removed_pages_are_skipped(tmp_path):
    write_page(
        tmp_path, "Place", "minuma-tanbo", "見沼田んぼ", ["見沼田んぼ"],
        extra="status: removed\n",
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


def test_index_pages_are_skipped(tmp_path):
    write_page(tmp_path, "Place", "index", "Place", ["Place"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


def test_non_string_and_empty_tags_are_skipped(tmp_path):
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Place"
    page_dir.mkdir(parents=True)
    (page_dir / "x.md").write_text(
        '---\ntitle: "X"\nlang: ja\ntype: "schema:Place"\ntags:\n  - 42\n  - ""\n---\n\nBody.\n',
        encoding="utf-8",
    )
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: title_echo=0, type_echo=0" in result.stdout


def test_title_echo_wins_over_type_echo(tmp_path):
    """A page titled after its own type reports once, not twice."""
    write_page(tmp_path, "Person", "person", "Person", ["Person"], lang="en")
    result = run(cwd=tmp_path)
    assert "SUMMARY: title_echo=1, type_echo=0" in result.stdout


# ── Distribution ─────────────────────────────────────────────────────────────

def test_template_copy_matches():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
