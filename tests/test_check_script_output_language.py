"""Tests for tools/check_script_output_language.py (#770)"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "tools" / "check_script_output_language.py"
REPO_ROOT = Path(__file__).parent.parent


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_script(root: Path, skill_name: str, file_name: str, body: str) -> Path:
    scripts_dir = root / ".claude" / "skills" / skill_name / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    path = scripts_dir / file_name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_no_skills_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, errors=0" in result.stdout


def test_english_output_passes(tmp_path):
    write_script(tmp_path, "wikicommit-demo", "ok.py", '''
        print("ERROR: file does not exist")
    ''')
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_japanese_print_literal_is_an_error(tmp_path):
    write_script(tmp_path, "wikicommit-demo", "bad.py", '''
        print("ERROR: ファイルが存在しません")
    ''')
    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert "bad.py:2" in result.stdout
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_japanese_in_fstring_constant_part_is_an_error(tmp_path):
    write_script(tmp_path, "wikicommit-demo", "bad.py", '''
        path = "x"
        print(f"ERROR: {path}: ファイルが存在しません")
    ''')
    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_japanese_in_interpolated_value_is_not_an_error(tmp_path):
    # Only literal parts are output the script itself authored; what a variable
    # happens to hold at run time (a page title, an error from another module)
    # is data, not a message.
    write_script(tmp_path, "wikicommit-demo", "ok.py", '''
        title = "山田太郎"
        print(f"OK: {title}")
    ''')
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_comments_and_docstrings_are_not_scanned(tmp_path):
    write_script(tmp_path, "wikicommit-demo", "ok.py", '''
        """このスクリプトの説明。開発者向けなので日本語のまま据え置く。"""

        def f():
            """関数の説明。"""
            # 日本語のコメント
            print("OK: done")
    ''')
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_non_print_japanese_literal_is_not_scanned(tmp_path):
    # The known limitation, pinned so it is not mistaken for coverage: reader-facing
    # label tables (convert_wikilinks.py) and returned messages (_frontmatter.py)
    # are both invisible here.
    write_script(tmp_path, "wikicommit-demo", "ok.py", '''
        LABELS = {"ja": "情報源一覧"}


        def parse():
            return None, "frontmatter がマッピング形式ではありません"
    ''')
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_only_scripts_directories_are_walked(tmp_path):
    skill_dir = tmp_path / ".claude" / "skills" / "wikicommit-demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "helper.py").write_text('print("ERROR: 日本語")\n', encoding="utf-8")
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, errors=0" in result.stdout


def test_real_repository_is_clean():
    result = run(cwd=REPO_ROOT)
    assert result.returncode == 0, result.stdout
    assert ", errors=0" in result.stdout
