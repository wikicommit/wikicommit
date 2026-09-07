"""Tests for tools/check_skill_user_facing_vocabulary.py (#588)"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = (
    Path(__file__).parent.parent / "tools" / "check_skill_user_facing_vocabulary.py"
)


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_skill_md(root: Path, skill_name: str, body: str) -> Path:
    skill_dir = root / ".claude" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {skill_name}\ndescription: test\n---\n\n" + textwrap.dedent(body),
        encoding="utf-8",
    )
    return skill_md


def test_no_skills_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: blocks=0, exceptions=0, errors=0" in result.stdout


def test_clean_template_passes(tmp_path):
    write_skill_md(tmp_path, "wikicommit-demo", """
        ```
        Generated 3 pages. Run /wikicommit-merge to commit them.
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: blocks=1, exceptions=0, errors=0" in result.stdout


def test_detects_pass_step_route_and_tracker_references(tmp_path):
    write_skill_md(tmp_path, "wikicommit-demo", """
        ```
        Skipped during Pass 2b (see Step 5).
        This is a Route A page (Issue #315, PR #42).
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 1
    for expected in ['"Pass 2b"', '"Step 5"', '"Route A"', '"Issue #315"', '"PR #42"']:
        assert expected in result.stdout
    assert "errors=5" in result.stdout


def test_markdown_and_text_blocks_are_scanned(tmp_path):
    write_skill_md(tmp_path, "wikicommit-demo", """
        ```markdown
        ## Done (Issue #313)
        ```

        ```text
        Finished Pass 3.
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert "errors=2" in result.stdout


def test_bash_json_yaml_blocks_are_skipped(tmp_path):
    """Commands and data formats are not user-facing prose."""
    write_skill_md(tmp_path, "wikicommit-demo", """
        ```bash
        gh issue create --label wikicommit-review  # Issue #313
        ```

        ```json
        {"note": "Pass 2b"}
        ```

        ```yaml
        note: Route A
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: blocks=0, exceptions=0, errors=0" in result.stdout


def test_prose_outside_fences_is_not_scanned(tmp_path):
    """Internal step numbers in the instructions themselves are legitimate —
    the rule is about output, not about how the Skill describes itself."""
    write_skill_md(tmp_path, "wikicommit-demo", """
        Pass 2b runs here (Issue #315), and Route A applies. See Step 4.
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "errors=0" in result.stdout


def test_exception_marker_with_reason_skips_the_block(tmp_path):
    write_skill_md(tmp_path, "wikicommit-demo", """
        <!-- skill-vocabulary-exception: PR body, read by reviewers -->
        ```markdown
        - <path from Step 1> (Issue #285)
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: blocks=1, exceptions=1, errors=0" in result.stdout


def test_exception_marker_without_reason_is_itself_an_error(tmp_path):
    """Adding an exception has to restate why the reader is not a user."""
    write_skill_md(tmp_path, "wikicommit-demo", """
        <!-- skill-vocabulary-exception: -->
        ```markdown
        See Step 1.
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert "has no reason" in result.stdout
    assert "errors=1" in result.stdout


def test_exception_marker_separated_by_blank_lines_still_applies(tmp_path):
    write_skill_md(tmp_path, "wikicommit-demo", """
        <!-- skill-vocabulary-exception: reviewer-facing -->

        ```markdown
        See Step 1.
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "exceptions=1" in result.stdout


def test_exception_marker_does_not_leak_to_the_next_block(tmp_path):
    write_skill_md(tmp_path, "wikicommit-demo", """
        <!-- skill-vocabulary-exception: reviewer-facing -->
        ```markdown
        See Step 1.
        ```

        Some prose in between.

        ```markdown
        See Step 2.
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert "errors=1" in result.stdout
    assert "exceptions=1" in result.stdout


def test_nested_fence_does_not_end_the_outer_block(tmp_path):
    """SKILL.md templates embed fenced examples; a ``` inside a ```` block is
    content, not the end of it."""
    write_skill_md(tmp_path, "wikicommit-demo", """
        ````
        Example output:

        ```bash
        echo hi
        ```

        Generated during Pass 3.
        ````
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 1
    assert '"Pass 3"' in result.stdout
    assert "SUMMARY: blocks=1, exceptions=0, errors=1" in result.stdout


def test_unterminated_fence_body_is_not_scanned(tmp_path):
    write_skill_md(tmp_path, "wikicommit-demo", """
        ```
        Generated during Pass 3.
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: blocks=0, exceptions=0, errors=0" in result.stdout


def test_non_wikicommit_skills_are_not_scanned(tmp_path):
    """implement-issue / review-and-merge are developer tools; their reader is
    the developer running them."""
    write_skill_md(tmp_path, "implement-issue", """
        ```
        Implemented Issue #123 in Step 4.
        ```
    """)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: blocks=0, exceptions=0, errors=0" in result.stdout


def test_repository_skills_are_clean():
    """The real .claude/skills/ must stay at zero — this is the regression
    guard the prose rule alone did not provide."""
    repo_root = Path(__file__).parent.parent
    result = run(cwd=repo_root)
    assert result.returncode == 0, result.stdout
    assert "errors=0" in result.stdout
