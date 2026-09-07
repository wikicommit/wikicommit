"""Tests for dev/scripts/check_issue_registration.py

The script under test is dev-only (`dev/` is permanently excluded from the
published snapshot), so every test here is skipped there. The skip is keyed on
the repository kind rather than on the script file being absent — see
`tests/_publication.py` for why the missing file cannot itself be the signal —
and `test_the_script_under_test_exists` asserts the input is present whenever
the suite does run, so a rename still fails loudly (Issue #788).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from _publication import is_development_repository

SCRIPT = Path(__file__).parent.parent / "dev" / "scripts" / "check_issue_registration.py"

pytestmark = pytest.mark.skipif(
    not is_development_repository(),
    reason="published snapshot: dev/scripts/check_issue_registration.py is intentionally not published",
)


def test_the_script_under_test_exists():
    assert SCRIPT.is_file(), (
        f"{SCRIPT} is missing from the development repository. If it moved, follow "
        "it here rather than letting these tests skip themselves away (Issue #788)."
    )


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_issue(path: Path, github_issue) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = "null" if github_issue is None else str(github_issue)
    path.write_text(
        f"---\ngithub_issue: {value}\n---\n\n# [Phase 3] Example issue draft\n\nBody text.\n",
        encoding="utf-8",
    )
    return path


def write_issues_json(tmp_path: Path, issues: list[dict]) -> Path:
    issues_json = tmp_path / "issues.json"
    issues_json.write_text(json.dumps(issues), encoding="utf-8")
    return issues_json


def test_no_issues_dir(tmp_path):
    result = run(["--issues-json", str(write_issues_json(tmp_path, []))], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, errors=0" in result.stdout


def test_draft_with_null_github_issue_ok(tmp_path):
    write_issue(tmp_path / "Issues" / "p3-999-example.md", None)
    issues_json = write_issues_json(tmp_path, [])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_registered_with_matching_number_ok(tmp_path):
    write_issue(tmp_path / "Issues" / "registered" / "p3-999-example.md", 42)
    issues_json = write_issues_json(tmp_path, [{"number": 42, "state": "CLOSED", "title": "x"}])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_registered_with_null_github_issue_errors(tmp_path):
    """This is exactly the bug found in production: a draft sitting in
    Issues/registered/ that was never actually `gh issue create`d."""
    write_issue(tmp_path / "Issues" / "registered" / "p3-999-example.md", None)
    issues_json = write_issues_json(tmp_path, [])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR: Issues/registered/p3-999-example.md: in Issues/registered/ but github_issue is null" in result.stdout
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_registered_with_nonexistent_number_errors(tmp_path):
    write_issue(tmp_path / "Issues" / "registered" / "p3-999-example.md", 999)
    issues_json = write_issues_json(tmp_path, [{"number": 42, "state": "CLOSED", "title": "x"}])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR: Issues/registered/p3-999-example.md: github_issue: 999 does not exist on GitHub" in result.stdout
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_draft_with_nonnull_github_issue_errors(tmp_path):
    write_issue(tmp_path / "Issues" / "p3-999-example.md", 42)
    issues_json = write_issues_json(tmp_path, [{"number": 42, "state": "CLOSED", "title": "x"}])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR: Issues/p3-999-example.md: in Issues/draft/ but github_issue: 42 is set" in result.stdout
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_rejected_with_nonnull_github_issue_errors(tmp_path):
    write_issue(tmp_path / "Issues" / "rejected" / "p3-999-example.md", 42)
    issues_json = write_issues_json(tmp_path, [{"number": 42, "state": "CLOSED", "title": "x"}])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR: Issues/rejected/p3-999-example.md: in Issues/rejected/ but github_issue: 42 is set" in result.stdout


def test_missing_frontmatter_errors(tmp_path):
    path = tmp_path / "Issues" / "p3-999-example.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# [Phase 3] No frontmatter here\n\nBody text.\n", encoding="utf-8")
    issues_json = write_issues_json(tmp_path, [])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR: Issues/p3-999-example.md: frontmatter missing" in result.stdout
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_readme_and_milestones_skipped(tmp_path):
    (tmp_path / "Issues").mkdir()
    (tmp_path / "Issues" / "README.md").write_text("no frontmatter\n", encoding="utf-8")
    (tmp_path / "Issues" / "milestones.md").write_text("no frontmatter\n", encoding="utf-8")
    issues_json = write_issues_json(tmp_path, [])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, errors=0" in result.stdout


def test_multiple_files_mixed(tmp_path):
    write_issue(tmp_path / "Issues" / "p3-100-draft.md", None)
    write_issue(tmp_path / "Issues" / "registered" / "p3-101-registered.md", 42)
    write_issue(tmp_path / "Issues" / "registered" / "p3-102-misplaced.md", None)
    issues_json = write_issues_json(tmp_path, [{"number": 42, "state": "CLOSED", "title": "x"}])

    result = run(["--issues-json", str(issues_json)], cwd=tmp_path)
    assert result.returncode == 1
    assert "p3-100-draft.md" not in result.stdout.split("SUMMARY")[0].replace("SUMMARY", "")
    assert "ERROR: Issues/registered/p3-102-misplaced.md" in result.stdout
    assert "SUMMARY: checked=3, errors=1" in result.stdout
