#!/usr/bin/env python3
"""Check whether "Allow GitHub Actions to create and approve pull requests"
(Settings -> Actions -> General -> Workflow permissions) is enabled.

review-issue-close-sync.yml's `Commit and open PR` step depends on this
repository setting (Issue #313). wikicommit-init attempts to enable it
automatically at repository initialization time (best-effort, Issue #403),
but that attempt can silently fail for reasons that leave no trace in normal
operation — the failure only surfaces days later, when a reviewer closes a
tracking Issue and the workflow run fails deep in GitHub Actions logs nobody
routinely checks (Issue #478). This script re-checks the setting on each
wikicommit-status run so drift is caught proactively instead of by accident.

Usage:
    python .wikicommit/scripts/check_actions_pr_permission.py

Exit code: always 0 (warning-only, non-blocking, matching every other
check_*.py script).

Read-only: unlike wikicommit-init's Step 3, this script never attempts to
enable the setting itself. wikicommit-init writes to the repository setting
only after the user's Y/n Prerequisites confirmation; a periodic health
check should not make that same write unprompted.

This is the only check_*.py script that calls `gh` — every other script
in this directory only ever reads `.wikicommit/`.
"""

import json
import subprocess
import sys
from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/review-issue-close-sync.yml")
SETTING_NAME = '"Allow GitHub Actions to create and approve pull requests"'


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def resolve_repo() -> str | None:
    """Return "<owner>/<repo>" via `gh repo view`, or None if unresolvable."""
    result = _run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if result.returncode != 0:
        return None
    repo = result.stdout.strip()
    return repo or None


def evaluate_permission_json(raw: str, repo: str) -> tuple[str, str, str]:
    """Parse `gh api repos/{repo}/actions/permissions/workflow`'s JSON
    response and return (status, message, enabled), status one of
    "OK"/"WARNING" and enabled one of "true"/"false"/"unknown" (the last
    for a response that couldn't even be parsed — genuinely undetermined,
    distinct from a parsed response that confirms the setting is off)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "WARNING", f"{repo}: gh api のレスポンスを解析できませんでした（設定を確認できません）", "unknown"

    if not isinstance(data, dict):
        return "WARNING", f"{repo}: gh api のレスポンスを解析できませんでした（設定を確認できません）", "unknown"

    if data.get("can_approve_pull_request_reviews"):
        return "OK", f"{repo}: {SETTING_NAME} は有効です", "true"

    default_permissions = data.get("default_workflow_permissions", "read")
    enable_cmd = (
        f"gh api -X PUT repos/{repo}/actions/permissions/workflow "
        f"-F can_approve_pull_request_reviews=true "
        f"-f default_workflow_permissions={default_permissions}"
    )
    return "WARNING", (
        f"{repo}: {SETTING_NAME} が無効です。review-issue-close-sync.yml が"
        f"レビュー追跡Issue Close後の自動マージに失敗します（Issue #403）。"
        f"有効化: {enable_cmd}"
    ), "false"


def main() -> int:
    if not WORKFLOW_PATH.is_file():
        print("OK: review-issue-close-sync.yml が存在しないためこのチェックは対象外です")
        print("SUMMARY: enabled=n/a")
        return 0

    auth = _run(["gh", "auth", "status"])
    if auth.returncode != 0:
        print(f"WARNING: gh が未認証のため {SETTING_NAME} の状態を確認できません")
        print("SUMMARY: enabled=unknown")
        return 0

    repo = resolve_repo()
    if repo is None:
        print(f"WARNING: リポジトリを特定できないため {SETTING_NAME} の状態を確認できません")
        print("SUMMARY: enabled=unknown")
        return 0

    result = _run(["gh", "api", f"repos/{repo}/actions/permissions/workflow"])
    if result.returncode != 0:
        print(f"WARNING: {repo}: gh api repos/{repo}/actions/permissions/workflow の呼び出しに失敗しました（権限不足等の可能性）")
        print("SUMMARY: enabled=unknown")
        return 0

    status, message, enabled = evaluate_permission_json(result.stdout, repo)
    print(f"{status}: {message}")
    print(f"SUMMARY: enabled={enabled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
