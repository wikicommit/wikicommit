"""Tests for qualifying a page's name by year (Issue #1120): rename_page.py and the
`series` relation.

Editions of one series share a name; before `/wikicommit-relate` records them as a
series, each is qualified the same way — slug `-<year>`, title `（<year>）` — and a
rename carries its translations, the links to it and the source files along.
"""

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS = REPO_ROOT / ".wikicommit" / "scripts"
RENAME = SCRIPTS / "rename_page.py"
RECORD = SCRIPTS / "record_relation.py"
COLLISIONS = SCRIPTS / "check_name_collisions.py"
VALIDATE = SCRIPTS / "validate_frontmatter.py"
WIKILINKS = SCRIPTS / "check_wikilinks.py"

V3 = ".wikicommit/entity/ja/CreativeWork/ilo-report-v.md"
V3_NEW = ".wikicommit/entity/ja/CreativeWork/ilo-report-v-2025.md"
V3_EN = ".wikicommit/entity/en/CreativeWork/ilo-report-v.md"
V3_EN_NEW = ".wikicommit/entity/en/CreativeWork/ilo-report-v-2025.md"
V4 = ".wikicommit/entity/ja/CreativeWork/ilo-report-v-2026.md"


def write(root: Path, rel: str, fm: str, body: str = "本文。\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm}---\n\n{body}", encoding="utf-8")


def run(root: Path, script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, cwd=root)


def wiki(root: Path) -> Path:
    (root / ".wikicommit").mkdir(parents=True, exist_ok=True)
    (root / ".wikicommit" / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n", encoding="utf-8")
    src = "sources:\n  - type: url\n    url: https://ilo.example/v3\n    hash: sha256:aa\n"
    write(root, V3, 'title: "仕事の未来報告書"\ntype: "schema:CreativeWork"\nlang: ja\n'
          f"review_status: reviewed\nreviewed_by: someone\n{src}")
    write(root, V3_EN, 'title: "Future of Work Report"\ntype: "schema:CreativeWork"\nlang: en\n'
          f"review_status: pending\ntranslated_from: {V3}\nsource_commit: ''\n")
    write(root, V4, 'title: "仕事の未来報告書 V(4)"\ntype: "schema:CreativeWork"\nlang: ja\n'
          "review_status: pending\nsources:\n  - type: url\n    url: https://ilo.example/v4\n    hash: sha256:bb\n",
          "前年の[[CreativeWork/ilo-report-v]]を受ける。\n")
    write(root, ".wikicommit/source/url/ilo.example/v3.md",
          f"source:\n  type: url\n  url: https://ilo.example/v3\nstatus: generated\ngenerated_pages:\n  - {V3}\n")
    return root


def test_plan_qualifies_slug_and_title_and_writes_nothing(tmp_path):
    wiki(tmp_path)
    result = run(tmp_path, RENAME, "plan", "--page", V3, "--year", "2025")
    assert result.returncode == 0, result.stdout
    lines = result.stdout.splitlines()
    assert f"RENAME: {V3} -> {V3_NEW}" in lines
    assert f"RENAME: {V3_EN} -> {V3_EN_NEW}" in lines
    assert 'TITLE: ja "仕事の未来報告書" -> "仕事の未来報告書（2025）"' in lines
    assert 'TITLE: en "Future of Work Report" -> "Future of Work Report (2025)"' in lines
    assert not (tmp_path / V3_NEW).exists()


def test_apply_renames_with_translations_links_and_source_files(tmp_path):
    wiki(tmp_path)
    result = run(tmp_path, RENAME, "apply", "--page", V3, "--year", "2025", "--today", "2026-10-02")
    assert result.returncode == 0, result.stdout + result.stderr

    new = yaml.safe_load((tmp_path / V3_NEW).read_text(encoding="utf-8").split("---")[1])
    assert new["title"] == "仕事の未来報告書（2025）"
    assert new["review_status"] == "pending" and "reviewed_by" not in new
    new_en = yaml.safe_load((tmp_path / V3_EN_NEW).read_text(encoding="utf-8").split("---")[1])
    assert new_en["title"] == "Future of Work Report (2025)"
    assert new_en["translated_from"] == V3_NEW

    old = yaml.safe_load((tmp_path / V3).read_text(encoding="utf-8").split("---")[1])
    assert old["status"] == "removed" and old["removed_reason"] == "merged" and old["merged_into"] == V3_NEW
    old_en = yaml.safe_load((tmp_path / V3_EN).read_text(encoding="utf-8").split("---")[1])
    assert old_en["merged_into"] == V3_EN_NEW

    assert "[[CreativeWork/ilo-report-v-2025]]" in (tmp_path / V4).read_text(encoding="utf-8")
    assert f"  - {V3_NEW}\n" in (tmp_path / ".wikicommit/source/url/ilo.example/v3.md").read_text(encoding="utf-8")
    item = yaml.safe_load((tmp_path / ".wikicommit/relations.yml").read_text(encoding="utf-8"))[-1]
    assert item == {"relation": "same", "pages": ["CreativeWork/ilo-report-v", "CreativeWork/ilo-report-v-2025"],
                    "merged_into": "CreativeWork/ilo-report-v-2025", "renamed_at": "2026-10-02"}
    assert "[[CreativeWork/ilo-report-v-2025]]" in (
        tmp_path / ".wikicommit/entity/ja/CreativeWork/index.md").read_text(encoding="utf-8")

    for script in (VALIDATE, WIKILINKS):
        check = run(tmp_path, script)
        assert "ERROR" not in check.stdout, check.stdout


def test_a_title_already_qualified_keeps_the_review_status_when_only_the_slug_changes(tmp_path):
    """Issue #1246: a slug is a file name, not text a person read."""
    wiki(tmp_path)
    for path, old, new in ((V3, "仕事の未来報告書", "仕事の未来報告書（2025）"),
                           (V3_EN, "Future of Work Report", "Future of Work Report (2025)")):
        page = tmp_path / path
        page.write_text(page.read_text(encoding="utf-8").replace(f'"{old}"', f'"{new}"'), encoding="utf-8")
    result = run(tmp_path, RENAME, "apply", "--page", V3, "--year", "2025", "--today", "2026-10-02")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TITLE:" not in result.stdout
    new = yaml.safe_load((tmp_path / V3_NEW).read_text(encoding="utf-8").split("---")[1])
    assert new["title"] == "仕事の未来報告書（2025）"
    assert new["review_status"] == "reviewed" and new["reviewed_by"] == "someone"
    new_en = yaml.safe_load((tmp_path / V3_EN_NEW).read_text(encoding="utf-8").split("---")[1])
    assert new_en["title"] == "Future of Work Report (2025)"
    assert new_en["translated_from"] == V3_NEW


def test_a_slug_already_qualified_only_changes_the_title(tmp_path):
    wiki(tmp_path)
    result = run(tmp_path, RENAME, "apply", "--page", V4, "--year", "2026",
                 "--base-title", "ja=仕事の未来報告書")
    assert result.returncode == 0, result.stdout
    assert "RENAME:" not in result.stdout
    fm = yaml.safe_load((tmp_path / V4).read_text(encoding="utf-8").split("---")[1])
    assert fm["title"] == "仕事の未来報告書（2026）"
    again = run(tmp_path, RENAME, "apply", "--page", V4, "--year", "2026")
    assert "UNCHANGED:" in again.stdout


def test_refuses_a_translation_a_bad_year_and_a_taken_slug(tmp_path):
    wiki(tmp_path)
    assert run(tmp_path, RENAME, "plan", "--page", V3_EN, "--year", "2025").returncode == 1
    assert run(tmp_path, RENAME, "plan", "--page", V3, "--year", "25").returncode == 1
    write(tmp_path, ".wikicommit/entity/en/CreativeWork/ilo-report-v-2025.md",
          'title: "Taken"\ntype: "schema:CreativeWork"\nlang: en\n')
    taken = run(tmp_path, RENAME, "plan", "--page", V3, "--year", "2025")
    assert taken.returncode == 1 and "already exists" in taken.stdout


def test_a_series_is_recorded_and_no_longer_raised_as_a_collision(tmp_path):
    wiki(tmp_path)
    # Two editions answering to the same name: the newer one carries it as an alias.
    path = tmp_path / V4
    path.write_text(path.read_text(encoding="utf-8").replace(
        "lang: ja\n", 'lang: ja\naliases: ["仕事の未来報告書"]\n', 1), encoding="utf-8")
    before = run(tmp_path, COLLISIONS)
    assert "COLLISION:" in before.stdout
    recorded = run(tmp_path, RECORD, "--relation", "series", "--page", "CreativeWork/ilo-report-v",
                   "--page", "CreativeWork/ilo-report-v-2026", "--today", "2026-10-02")
    assert recorded.returncode == 0, recorded.stdout
    after = run(tmp_path, COLLISIONS)
    assert "COLLISION:" not in after.stdout
    assert "judged_pairs_skipped=1" in after.stdout
