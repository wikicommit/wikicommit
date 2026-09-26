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
