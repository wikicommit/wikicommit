"""A required review leaves the `reviewed` PR for a person (Issue #1396).

On a default branch that requires an approving review, the PR that
`review-issue-close-sync.yml` opens to mark a page `reviewed` is `BLOCKED`. The
"Auto-merge on quality pass" step used to treat `BLOCKED` as terminal and fail
the job, so the page stayed `pending` and the PR sat open with nobody told. It
now splits `BLOCKED` the way `/wikicommit-merge` does (Issue #1377): a running
check is waited for, a failed check fails, a required review — or a check left
`EXPECTED`, which never starts for a PR opened with `GITHUB_TOKEN` — leaves the
PR open and comments on the Issue. The step's `run:` body is executed as written
against a stub `gh`, and the Pages dispatch is checked to run only after a merge.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

SYNC_YML = (Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts"
            / "templates" / "workflows" / "review-issue-close-sync.yml")

GH_STUB = """#!/usr/bin/env bash
set -e
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "pr view")
    n=$(cat "$GH_COUNT" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$GH_COUNT"
    f="$GH_STATES/$n.json"; [ -f "$f" ] || f="$GH_STATES/last.json"
    cat "$f" ;;
  "issue comment") [ -z "$GH_COMMENT_FAILS" ] || exit 1 ;;
esac
"""


def _steps() -> list:
    workflow = yaml.safe_load(SYNC_YML.read_text(encoding="utf-8"))
    return workflow["jobs"]["sync"]["steps"]


def _step(name: str) -> dict:
    return next(s for s in _steps() if s.get("name") == name)


def _pr(merge_state: str, review: str = "", checks: list | None = None, state: str = "OPEN") -> dict:
    return {"state": state, "mergeStateStatus": merge_state, "reviewDecision": review,
            "statusCheckRollup": checks or []}


def _run(tmp_path: Path, states: list[dict], comment_fails: bool = False) -> dict:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text(GH_STUB, encoding="utf-8")
    (bindir / "sleep").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    for exe in bindir.iterdir():
        exe.chmod(0o755)
    state_dir = tmp_path / "states"
    state_dir.mkdir()
    for i, pr in enumerate(states, start=1):
        (state_dir / f"{i}.json").write_text(json.dumps(pr), encoding="utf-8")
    (state_dir / "last.json").write_text(json.dumps(states[-1]), encoding="utf-8")
    log = tmp_path / "gh.log"
    out = tmp_path / "out"
    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "GH_LOG": str(log), "GH_COUNT": str(tmp_path / "count"), "GH_STATES": str(state_dir),
        "GITHUB_OUTPUT": str(out),
        "PR_NUMBER": "42", "PR_URL": "https://github.com/o/r/pull/42",
        "LANG": "en", "TYPE": "DefinedTerm", "SLUG": "term", "ISSUE_NUMBER": "7",
        "REVIEWER_NAME": "Rev", "REVIEWER_LOGIN": "rev",
    }
    if comment_fails:
        env["GH_COMMENT_FAILS"] = "1"
    result = subprocess.run(
        ["bash", "-e", "-c", _step("Auto-merge on quality pass")["run"]],
        capture_output=True, text=True, env=env, cwd=tmp_path, check=False,
    )
    outputs = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return {"code": result.returncode, "outputs": outputs, "calls": calls,
            "stdout": result.stdout + result.stderr}


def _commented(calls: list[str]) -> bool:
    return any(c.startswith("issue comment 7") for c in calls)


def _merged(calls: list[str]) -> bool:
    return any(c.startswith("pr merge 42") for c in calls)


def test_a_required_review_leaves_the_pr_and_comments(tmp_path):
    got = _run(tmp_path, [_pr("UNKNOWN"), _pr("BLOCKED", "REVIEW_REQUIRED")])
    assert got["code"] == 0, got["stdout"]
    assert got["outputs"]["merged"] == "false"
    assert not _merged(got["calls"])
    comment = next(c for c in got["calls"] if c.startswith("issue comment 7"))
    assert "https://github.com/o/r/pull/42" in comment
    assert "github-actions[bot]" in comment
    assert "Required checks" not in comment


def test_changes_requested_also_waits_for_a_person(tmp_path):
    got = _run(tmp_path, [_pr("BLOCKED", "CHANGES_REQUESTED")])
    assert got["code"] == 0
    assert _commented(got["calls"]) and not _merged(got["calls"])


def test_a_running_check_is_waited_for_before_deciding(tmp_path):
    running = {"__typename": "CheckRun", "name": "lint", "status": "IN_PROGRESS", "conclusion": ""}
    passed = {"__typename": "CheckRun", "name": "lint", "status": "COMPLETED", "conclusion": "SUCCESS"}
    got = _run(tmp_path, [_pr("BLOCKED", "REVIEW_REQUIRED", [running]),
                          _pr("BLOCKED", "REVIEW_REQUIRED", [passed])])
    assert got["code"] == 0
    assert sum(c.startswith("pr view") for c in got["calls"]) == 2
    assert _commented(got["calls"])


def test_a_review_behind_checks_still_running_at_timeout_is_left_for_a_person(tmp_path):
    running = {"__typename": "StatusContext", "context": "ci", "state": "PENDING"}
    got = _run(tmp_path, [_pr("BLOCKED", "REVIEW_REQUIRED", [running])])
    assert got["code"] == 0
    assert sum(c.startswith("pr view") for c in got["calls"]) == 30
    assert _commented(got["calls"]) and not _merged(got["calls"])


def test_an_expected_check_is_not_waited_for_and_is_named(tmp_path):
    expected = {"__typename": "StatusContext", "context": "ci/test", "state": "EXPECTED"}
    got = _run(tmp_path, [_pr("BLOCKED", "", [expected])])
    assert got["code"] == 0
    assert sum(c.startswith("pr view") for c in got["calls"]) == 1
    comment = next(c for c in got["calls"] if c.startswith("issue comment 7"))
    assert "ci/test" in comment
    assert "Close and reopen" in comment


def test_a_failed_check_still_fails(tmp_path):
    failed = {"__typename": "CheckRun", "name": "lint", "status": "COMPLETED", "conclusion": "FAILURE"}
    got = _run(tmp_path, [_pr("BLOCKED", "REVIEW_REQUIRED", [failed])])
    assert got["code"] == 1
    assert not _commented(got["calls"]) and not _merged(got["calls"])


@pytest.mark.parametrize("pr", [_pr("BLOCKED"), _pr("DIRTY"), _pr("CLEAN", state="CLOSED")])
def test_other_terminal_states_still_fail(tmp_path, pr):
    got = _run(tmp_path, [pr])
    assert got["code"] == 1
    assert not _commented(got["calls"]) and not _merged(got["calls"])


def test_clean_merges_and_reports_it(tmp_path):
    got = _run(tmp_path, [_pr("UNKNOWN"), _pr("CLEAN")])
    assert got["code"] == 0, got["stdout"]
    assert _merged(got["calls"])
    assert got["outputs"]["merged"] == "true"
    assert not _commented(got["calls"])


def test_a_comment_that_cannot_be_posted_fails_the_job(tmp_path):
    got = _run(tmp_path, [_pr("BLOCKED", "REVIEW_REQUIRED")], comment_fails=True)
    assert got["code"] == 1
    assert "could not be posted" in got["stdout"]


def test_the_pages_dispatch_waits_for_an_actual_merge():
    dispatch = next(s for s in _steps() if "gh workflow run deploy.yml" in (s.get("run") or ""))
    assert "steps.merge.outputs.merged == 'true'" in dispatch["if"]
    assert _step("Auto-merge on quality pass")["id"] == "merge"


def test_a_pr_merged_by_someone_else_while_waiting_succeeds_without_merging(tmp_path):
    got = _run(tmp_path, [_pr("UNKNOWN"), _pr("UNKNOWN", state="MERGED")])
    assert got["code"] == 0, got["stdout"]
    assert got["outputs"]["merged"] == "false"
    assert not _merged(got["calls"]) and not _commented(got["calls"])


def test_the_comment_hints_at_unreported_required_checks(tmp_path):
    # A required check that never reported is absent from statusCheckRollup, so
    # it cannot be named — the comment still says how to start it.
    got = _run(tmp_path, [_pr("BLOCKED", "REVIEW_REQUIRED")])
    comment = next(c for c in got["calls"] if c.startswith("issue comment 7"))
    assert "close and reopen the pull request" in comment
    assert "published site" not in comment  # no deploy.yml in this repository


def test_the_comment_mentions_the_rebuild_only_with_deploy_yml(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "deploy.yml").write_text("on: push\n", encoding="utf-8")
    got = _run(tmp_path, [_pr("BLOCKED", "REVIEW_REQUIRED")])
    comment = next(c for c in got["calls"] if c.startswith("issue comment 7"))
    assert "published site is rebuilt" in comment


def test_the_pr_body_carries_the_reviewed_by_trailer():
    # A person who squash-merges with "pull request title and description" as
    # the default message keeps the trailer only if the PR body carries it.
    run = _step("Commit and open PR")["run"]
    assert "Reviewed-by: %s <%s@users.noreply.github.com>" in run
