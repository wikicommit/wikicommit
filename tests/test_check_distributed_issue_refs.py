"""tools/check_distributed_issue_refs.py (Issue #1054)."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import check_distributed_issue_refs as guard  # noqa: E402


def test_the_repository_passes():
    result = subprocess.run([sys.executable, "tools/check_distributed_issue_refs.py"],
                            cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_a_printed_string_is_caught_but_comments_and_docstrings_are_not(tmp_path):
    script = tmp_path / "x.py"
    script.write_text(
        '"""Module docstring (Issue #1)."""\n'
        "# comment (Issue #2)\n"
        'FIELD: str = "x"\n'
        '"""Attribute docstring (Issue #3)."""\n'
        "def f():\n"
        '    """Function docstring (Issue #4)."""\n'
        '    print("WARNING: something (Issue #5)")\n',
        encoding="utf-8",
    )
    assert guard.script_output_refs(script) == [(7, "Issue #5")]


def test_every_distributed_skill_has_a_cap():
    from check_distributed_path_refs import DISTRIBUTED_SKILLS
    assert set(guard.CAPS) == set(DISTRIBUTED_SKILLS)


def test_comments_and_docstrings_are_counted_but_printed_strings_are_not(tmp_path):
    script = tmp_path / "x.py"
    script.write_text(
        '"""Module docstring (Issue #1)."""\n'
        "# comment (Issue #2)\n"
        'FIELD: str = "x"\n'
        '"""Attribute docstring (Issue #3)."""\n'
        "def f():\n"
        '    """Function docstring (Issue #4)."""\n'
        '    print("WARNING: something (Issue #5)")  # trailing (Issue #6)\n',
        encoding="utf-8",
    )
    assert [ref for _, ref in guard.script_comment_refs(script)] == [
        "Issue #1", "Issue #2", "Issue #3", "Issue #4", "Issue #6"]


def test_a_reference_in_a_comment_of_a_distributed_script_fails(tmp_path, monkeypatch, capsys):
    script = tmp_path / "x.py"
    script.write_text('"""Docstring."""\n# kept for now (Issue #1)\n', encoding="utf-8")
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(guard, "distributed_scripts", lambda: [script])
    assert guard.main() == 1
    assert f"ERROR: {script}:2: 'Issue #1' in a comment or docstring" in capsys.readouterr().out


def test_a_reference_wrapped_across_lines_is_counted(tmp_path):
    script = tmp_path / "x.py"
    script.write_text(
        '"""Decided the same way Issue\n#566 decided it."""\n'
        "# declared in _root_outputs.py per Issue\n"
        "# #647, as before.\n",
        encoding="utf-8",
    )
    assert guard.script_comment_refs(script) == [(1, "Issue #566"), (3, "Issue #647")]


def test_a_bare_or_hyphenated_number_in_a_printed_string_is_caught(tmp_path):
    script = tmp_path / "x.py"
    script.write_text(
        'print("help (#374 — no effect on a repeat run)")\n'
        'print("ERROR: a pre-Issue-#476 tree is never migrated")\n'
        'print("avoids the 403s, #527) and writes")\n',
        encoding="utf-8",
    )
    assert guard.script_output_refs(script) == [
        (1, "#374"), (2, "Issue-#476"), (3, "#527")]


def test_hash_forms_that_are_not_issue_numbers_pass(tmp_path):
    script = tmp_path / "x.py"
    script.write_text(
        'COLOURS = ["#123abc", "#000000ff"]\n'
        'print("## 12 heading", "##12", "item #1", "&#123;", "page.html#42", "#a1")\n'
        "# noqa: E402 — see step #3\n",
        encoding="utf-8",
    )
    assert guard.script_output_refs(script) == []
    assert guard.script_comment_refs(script) == []


def test_a_bare_number_in_a_comment_or_docstring_is_caught(tmp_path):
    script = tmp_path / "x.py"
    script.write_text('"""Kept since #1343."""\n# see Issue-#476\n', encoding="utf-8")
    assert guard.script_comment_refs(script) == [(1, "#1343"), (2, "Issue-#476")]


def test_a_bare_number_next_to_cjk_text_is_caught(tmp_path):
    script = tmp_path / "x.py"
    script.write_text('print("参照#374で直した")\n', encoding="utf-8")
    assert guard.script_output_refs(script) == [(1, "#374")]
