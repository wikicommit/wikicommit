"""Tests for .wikicommit/scripts/check_actions_pr_permission.py (#478)"""

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_actions_pr_permission.py"

_spec = importlib.util.spec_from_file_location("check_actions_pr_permission", SCRIPT)
check_actions_pr_permission = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_actions_pr_permission)


def write_fake_gh(bin_dir: Path, script_body: str) -> None:
    """Write an executable `gh` shim to bin_dir, for prepending to PATH so
    the script under test never hits the real GitHub API/CLI."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f"#!/bin/sh\n{script_body}\n", encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def run(cwd: Path, bin_dir: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if bin_dir is not None:
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


# ── No workflow file: not applicable, gh is never invoked ──────────────────

def test_no_workflow_file_is_ok_without_calling_gh(tmp_path):
    # No gh shim on PATH at all — if the script tried to call gh here, the
    # subprocess would fail with a nonzero/garbled result instead of a clean
    # early-exit OK.
    result = run(tmp_path)

    assert result.returncode == 0
    assert "OK:" in result.stdout
    assert "does not apply" in result.stdout
    assert "SUMMARY: enabled=n/a" in result.stdout


# ── gh unavailable/unauthenticated ──────────────────────────────────────────

def test_gh_auth_failure_reports_unknown(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: x\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    write_fake_gh(bin_dir, 'if [ "$1" = "auth" ]; then exit 1; fi\nexit 0')

    result = run(tmp_path, bin_dir)

    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert "cannot be checked" in result.stdout
    assert "SUMMARY: enabled=unknown" in result.stdout


def test_repo_unresolvable_reports_unknown(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: x\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    write_fake_gh(
        bin_dir,
        'if [ "$1" = "auth" ]; then exit 0; fi\n'
        'if [ "$1" = "repo" ]; then exit 1; fi\n'
        "exit 0",
    )

    result = run(tmp_path, bin_dir)

    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert "could not be resolved" in result.stdout
    assert "SUMMARY: enabled=unknown" in result.stdout


def test_gh_api_failure_reports_unknown(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: x\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    write_fake_gh(
        bin_dir,
        'if [ "$1" = "auth" ]; then exit 0; fi\n'
        'if [ "$1" = "repo" ]; then echo "acme/example-wiki"; exit 0; fi\n'
        'if [ "$1" = "api" ]; then exit 1; fi\n'
        "exit 0",
    )

    result = run(tmp_path, bin_dir)

    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert "acme/example-wiki" in result.stdout
    assert "failed" in result.stdout
    assert "SUMMARY: enabled=unknown" in result.stdout


# ── gh api succeeds: enabled / disabled ─────────────────────────────────────

def test_permission_enabled_reports_ok(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: x\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    write_fake_gh(
        bin_dir,
        'if [ "$1" = "auth" ]; then exit 0; fi\n'
        'if [ "$1" = "repo" ]; then echo "acme/example-wiki"; exit 0; fi\n'
        'if [ "$1" = "api" ]; then echo \'{"can_approve_pull_request_reviews": true}\'; exit 0; fi\n'
        "exit 0",
    )

    result = run(tmp_path, bin_dir)

    assert result.returncode == 0
    assert "OK:" in result.stdout
    assert "acme/example-wiki" in result.stdout
    assert "SUMMARY: enabled=true" in result.stdout


def test_permission_disabled_reports_warning_with_enable_command(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: x\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    write_fake_gh(
        bin_dir,
        'if [ "$1" = "auth" ]; then exit 0; fi\n'
        'if [ "$1" = "repo" ]; then echo "acme/example-wiki"; exit 0; fi\n'
        'if [ "$1" = "api" ]; then echo \'{"can_approve_pull_request_reviews": false, '
        '"default_workflow_permissions": "write"}\'; exit 0; fi\n'
        "exit 0",
    )

    result = run(tmp_path, bin_dir)

    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert "acme/example-wiki" in result.stdout
    assert "Issue #403" in result.stdout
    assert (
        "gh api -X PUT repos/acme/example-wiki/actions/permissions/workflow "
        "-F can_approve_pull_request_reviews=true -f default_workflow_permissions=write"
    ) in result.stdout
    assert "SUMMARY: enabled=false" in result.stdout


def test_malformed_json_reports_unknown(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: x\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    write_fake_gh(
        bin_dir,
        'if [ "$1" = "auth" ]; then exit 0; fi\n'
        'if [ "$1" = "repo" ]; then echo "acme/example-wiki"; exit 0; fi\n'
        'if [ "$1" = "api" ]; then echo "not json"; exit 0; fi\n'
        "exit 0",
    )

    result = run(tmp_path, bin_dir)

    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert "could not be parsed" in result.stdout
    assert "SUMMARY: enabled=unknown" in result.stdout


# ── evaluate_permission_json() unit tests ───────────────────────────────────

def test_evaluate_permission_json_defaults_missing_default_permissions_to_read():
    status, message, enabled = check_actions_pr_permission.evaluate_permission_json(
        '{"can_approve_pull_request_reviews": false}', "acme/example-wiki"
    )
    assert status == "WARNING"
    assert enabled == "false"
    assert "default_workflow_permissions=read" in message

# Sync between this canonical script and its wikicommit-init template copy is
# already covered generically by tests/test_template_mirror_sync.py (which
# byte-compares every git-tracked file under .wikicommit/scripts/ against its
# .claude/skills/wikicommit-init/scripts/templates/scripts/ counterpart), so
# no file-specific duplicate of that check is needed here.
