"""Only a close as "completed" marks a page reviewed (Issue #1323).

`review-issue-close-sync.yml` used to flip a page to `reviewed` and write a human
review record whatever reason the tracking Issue was closed with. "Not planned"
and "duplicate" do not say that anyone read the page and found nothing wrong —
the two things `reviewed` asserts — and a close through the API with no reason
says nothing at all. The `Resolve target page` step's embedded Python is run as
written; the comment step and the permission are checked on the parsed workflow.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SYNC_YML = (Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts"
            / "templates" / "workflows" / "review-issue-close-sync.yml")
PAGE = ".wikicommit/entity/en/DefinedTerm/term.md"


def _workflow() -> dict:
    return yaml.safe_load(SYNC_YML.read_text(encoding="utf-8"))


def _steps() -> list:
    return list(_workflow()["jobs"].values())[0]["steps"]


def _step(name: str) -> dict:
    return next(s for s in _steps() if s.get("name") == name)


def _resolver() -> str:
    match = re.search(r"<<'PY'\n(.*?)\n\s*PY\n", _step("Resolve target page")["run"], re.DOTALL)
    assert match, "the embedded Python heredoc is missing"
    return match.group(1)


def _resolve(tmp_path: Path, state_reason: str | None, extra_front: str = "") -> dict:
    page = tmp_path / PAGE
    page.parent.mkdir(parents=True)
    page.write_text(f'---\ntitle: "Term"\nreview_status: pending\n{extra_front}---\n\nBody.\n',
                    encoding="utf-8")
    out = tmp_path / "out"
    env = {"ISSUE_BODY": f"<!-- wikicommit-page: {PAGE} -->", "GITHUB_OUTPUT": str(out),
           "PATH": "/usr/bin:/bin"}
    if state_reason is not None:
        env["STATE_REASON"] = state_reason
    result = subprocess.run(
        [sys.executable, "-"], input=_resolver(), capture_output=True, text=True, cwd=tmp_path,
        env=env, check=False,
    )
    assert result.returncode == 0, result.stderr
    outputs = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    return {"outputs": outputs, "stdout": result.stdout}


@pytest.mark.parametrize(("state_reason", "shown"), [
    ("not_planned", "not_planned"),
    ("duplicate", "duplicate"),
    ("", "none"),
    (None, "none"),
    ("reopened", "reopened"),
])
def test_a_close_that_is_not_completed_is_skipped(tmp_path, state_reason, shown):
    got = _resolve(tmp_path, state_reason)
    assert got["outputs"] == {"proceed": "false", "not_completed": "true", "state_reason": shown}
    assert f"state_reason={shown}" in got["stdout"]


def test_a_close_as_completed_proceeds(tmp_path):
    outputs = _resolve(tmp_path, "completed")["outputs"]
    assert outputs["proceed"] == "true"
    assert outputs["path"] == PAGE
    assert "not_completed" not in outputs


@pytest.mark.parametrize("state_reason", ["not_planned", "duplicate"])
def test_a_removed_page_is_skipped_quietly_whatever_the_reason(tmp_path, state_reason):
    # A merged or removed page's Issue is naturally closed as "duplicate" or "not
    # planned"; it must not get a comment telling the closer to reopen it.
    outputs = _resolve(tmp_path, state_reason, "status: removed\n")["outputs"]
    assert outputs == {"proceed": "false"}


def test_the_state_reason_is_passed_through_env():
    step = _step("Resolve target page")
    assert step["env"]["STATE_REASON"] == "${{ github.event.issue.state_reason }}"
    assert "github.event" not in step["run"]


def test_a_skipped_close_is_explained_on_the_issue():
    step = _step("Explain a skipped close")
    assert step["if"] == "steps.resolve.outputs.not_completed == 'true'"
    assert "gh issue comment" in step["run"]
    assert "pending" in step["run"] and "completed" in step["run"]
    names = [s.get("name") for s in _steps()]
    assert names.index("Explain a skipped close") < names.index("Rewrite review_status")


def test_the_workflow_can_comment_on_issues():
    assert _workflow()["permissions"]["issues"] == "write"
