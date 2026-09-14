"""Tests for tools/check_skill_output_language.py (Issue #808)"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "tools" / "check_skill_output_language.py"
REPO_ROOT = Path(__file__).parent.parent


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_skill(root: Path, skill_name: str, body: str) -> Path:
    skill_dir = root / ".claude" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_no_skills_dir(tmp_path):
    """走査対象が無いこと自体はエラーではない（他のガードと同じ扱い）。"""
    result = run(tmp_path)
    assert result.returncode == 0
    assert "errors=0" in result.stdout


def test_japanese_sentence_in_prose_is_flagged(tmp_path):
    """散文中の引用された日本語メッセージを検出する。

    Issue #808 の 6 件のうち 5 件はフェンスの中ではなく通常の指示散文にあった。
    フェンスだけを見るガードでは 1 件しか拾えない。
    """
    write_skill(
        tmp_path,
        "wikicommit-translate",
        """\
        # wikicommit-translate

        If `targets` is empty, stop with: "対象言語がありません。"
        """,
    )
    result = run(tmp_path)
    assert result.returncode == 1
    assert "SKILL.md:3" in result.stdout
    assert "errors=1" in result.stdout


def test_japanese_inside_fenced_block_is_flagged(tmp_path):
    """フェンスの中（bash の heredoc 等）も走査対象である。"""
    write_skill(
        tmp_path,
        "wikicommit-fix",
        """\
        # wikicommit-fix

        ```bash
        gh issue comment 1 --body "この Issue の内容を確認しました。"
        ```
        """,
    )
    result = run(tmp_path)
    assert result.returncode == 1
    assert "errors=1" in result.stdout


def test_corner_brackets_are_flagged(tmp_path):
    """句点を持たない日本語トークンでも、「」で囲まれていれば拾える。"""
    write_skill(
        tmp_path,
        "wikicommit-collect",
        """\
        # wikicommit-collect

        "all"/「全部」selects every listed candidate at once.
        """,
    )
    result = run(tmp_path)
    assert result.returncode == 1
    assert "errors=1" in result.stdout


def test_japanese_example_data_without_sentence_punctuation_is_not_flagged(tmp_path):
    """例示としての日本語（タイトル・検索語・引数）は誤検出しない。

    これが本ガードの設計の中心である。CJK の有無で判定すると、Issue #808 が
    明示的にスコープ外とした例示が全部エラーになり、ガードそのものが読まれなくなる。
    """
    write_skill(
        tmp_path,
        "wikicommit-fix",
        """\
        # wikicommit-fix

        /wikicommit-fix <page-path> "生年を1981年に修正して"
        Also searched: 子ども手当 (ja), child allowance (en)
        - schema:Book — "ドグラ・マグラ"
        try a more specific term (e.g. 児童手当 instead of 児童)
        """,
    )
    result = run(tmp_path)
    assert result.returncode == 0
    assert "errors=0" in result.stdout


def test_exception_marker_on_the_same_line(tmp_path):
    write_skill(
        tmp_path,
        "wikicommit-generate",
        """\
        # wikicommit-generate

        Quoted source text: "8月支給分は7月1日、12月支給分は11月1日" <!-- skill-language-exception: verbatim source quote -->
        """,
    )
    result = run(tmp_path)
    assert result.returncode == 0
    assert "exceptions=1" in result.stdout


def test_exception_marker_on_the_preceding_line(tmp_path):
    write_skill(
        tmp_path,
        "wikicommit-generate",
        """\
        # wikicommit-generate

        <!-- skill-language-exception: verbatim source quote -->
        Quoted source text: "8月支給分は7月1日、12月支給分は11月1日"
        """,
    )
    result = run(tmp_path)
    assert result.returncode == 0
    assert "exceptions=1" in result.stdout


def test_exception_marker_without_a_reason_is_an_error(tmp_path):
    """理由の無いマーカーはそれ自体をエラーとする（語彙ガードと同じ規約）。"""
    write_skill(
        tmp_path,
        "wikicommit-generate",
        """\
        # wikicommit-generate

        <!-- skill-language-exception: -->
        Quoted source text: "8月支給分は7月1日、12月支給分は11月1日"
        """,
    )
    result = run(tmp_path)
    assert result.returncode == 1
    assert "has no reason" in result.stdout


def test_non_wikicommit_skills_are_not_scanned(tmp_path):
    """走査対象は wikicommit-* の前方一致に限る（除外リストではない）。

    語彙ガード（Issue #588）と同じ線引きを共有する。接頭辞の外にある Skill は
    開発用の道具であり、読み手は実行している開発者本人である。
    """
    skill_dir = tmp_path / ".claude" / "skills" / "not-a-wikicommit-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("実装してください。\n", encoding="utf-8")
    result = run(tmp_path)
    assert result.returncode == 0
    assert "files=0" in result.stdout


def test_real_skills_are_clean():
    """実際の .claude/skills/ が検出 0 件であること。

    他の 2 つのガード（#588・#770）と同じく、スクリプトの単体挙動だけでなく
    リポジトリの現状も検証する — ガード自体が正しくても対象が汚れていれば
    このチェックは目的を果たしていない。
    """
    result = run(REPO_ROOT)
    assert result.returncode == 0, result.stdout
    assert "errors=0" in result.stdout


# ── SKILL.md の兄弟ファイル（Issue #887） ────────────────────────────────────

def write_instruction_md(root: Path, skill_name: str, rel: str, body: str) -> Path:
    path = root / ".claude" / "skills" / skill_name / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_a_sibling_instruction_file_is_scanned(tmp_path):
    """SKILL.md から出した手順がこのチェックの対象から外れないこと。

    Issue #887 が Regeneration Mode を `references/regenerate.md` へ移した。SKILL.md しか
    見ない形だと、移した瞬間にその散文が黙って対象外になる — サイズガードが
    分割を「改善」と報告したのと同じ形である。
    """
    write_skill(tmp_path, "wikicommit-generate", """
        Nothing to flag here.
    """)
    write_instruction_md(tmp_path, "wikicommit-generate", "regenerate.md", """
        Report: "対象ページがありません。"
    """)
    result = run(tmp_path)
    assert result.returncode == 1
    assert "regenerate.md:" in result.stdout
    assert "files=2" in result.stdout


def test_payload_and_template_md_are_not_scanned(tmp_path):
    """`CHANGELOG.md` / `changelog/` は配布ペイロード、`scripts/templates/` は
    配布先で展開されるファイルであり、どちらもここから読まれる指示ではない。"""
    write_skill(tmp_path, "wikicommit-init", """
        Nothing to flag here.
    """)
    japanese = '        Report: "対象言語がありません。"\n'
    write_instruction_md(tmp_path, "wikicommit-init", "CHANGELOG.md", japanese)
    write_instruction_md(tmp_path, "wikicommit-init", "changelog/0.4.0.md", japanese)
    write_instruction_md(
        tmp_path, "wikicommit-init", "scripts/templates/source-policy.md", japanese
    )
    result = run(tmp_path)
    assert result.returncode == 0
    assert "files=1" in result.stdout
    assert "errors=0" in result.stdout
