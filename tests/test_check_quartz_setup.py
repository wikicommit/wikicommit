"""Tests for .claude/skills/wikicommit-init/scripts/check_quartz_setup.py (#229)"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts" / "check_quartz_setup.py"


def _write_fake_npm(bin_dir: Path, exit_code: int) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    npm = bin_dir / "npm"
    npm.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    npm.chmod(npm.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _write_fake_npm_dispatch(bin_dir: Path, install_exit: int, install_plugins_exit: int) -> None:
    """Fake npm that exits differently for `npm install` vs `npm run install-plugins`."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    npm = bin_dir / "npm"
    npm.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "run" ] && [ "$2" = "install-plugins" ]; then\n'
        f"  exit {install_plugins_exit}\n"
        "fi\n"
        f"exit {install_exit}\n",
        encoding="utf-8",
    )
    npm.chmod(npm.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def run(cwd: Path, path: str | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


def status_of(result: subprocess.CompletedProcess) -> str:
    return json.loads(result.stdout)["status"]


def test_fully_set_up_skips_npm_install(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "quartz" / "node_modules").mkdir(parents=True)

    # No npm on PATH — if the script wrongly invoked it, this would crash instead of
    # returning the fully_set_up status, proving npm install was actually skipped.
    result = run(tmp_path, path="")

    assert result.returncode == 0
    assert status_of(result) == "fully_set_up"


def test_npm_install_completed_fully_set_up(tmp_path):
    (tmp_path / "quartz").mkdir()
    bin_dir = tmp_path / "bin"
    _write_fake_npm(bin_dir, exit_code=0)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert status_of(result) == "npm_install_completed_fully_set_up"


def test_npm_install_completed_submodule_pending(tmp_path):
    bin_dir = tmp_path / "bin"
    _write_fake_npm(bin_dir, exit_code=0)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert status_of(result) == "npm_install_completed_submodule_pending"


def test_npm_install_failed_submodule_exists(tmp_path):
    (tmp_path / "quartz").mkdir()
    bin_dir = tmp_path / "bin"
    _write_fake_npm(bin_dir, exit_code=1)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    # The script itself always exits 0 (best-effort, non-blocking) even when npm install fails.
    assert result.returncode == 0
    assert status_of(result) == "npm_install_failed_submodule_exists"


def test_npm_install_failed_no_submodule(tmp_path):
    bin_dir = tmp_path / "bin"
    _write_fake_npm(bin_dir, exit_code=1)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert status_of(result) == "npm_install_failed_no_submodule"


def test_npm_not_installed_reports_failure_status_instead_of_crashing(tmp_path):
    # No npm_install_needed pre-check shortcut here (no node_modules/), and no npm
    # binary anywhere on PATH — simulates npm/Node.js not being installed at all.
    result = run(tmp_path, path="")

    assert result.returncode == 0
    assert status_of(result) == "npm_install_failed_no_submodule"


def test_partial_setup_top_level_only_still_triggers_npm_install(tmp_path):
    # Only top-level node_modules/ exists (no quartz/node_modules/) — the pre-check must
    # require both directories, not just one, otherwise quartz/node_modules would wrongly
    # stay uninstalled forever on repeat runs.
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "quartz").mkdir()
    bin_dir = tmp_path / "bin"
    _write_fake_npm(bin_dir, exit_code=0)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert status_of(result) == "npm_install_completed_fully_set_up"


# Issue #380: whenever quartz/ already exists, `npm run install-plugins` is auto-attempted too
# (previously this guidance was silently dropped entirely on a `--no-overwrite --quartz` re-init
# that found Quartz already fully set up, since the "Set up Quartz v5" next-steps step that used
# to be the only place carrying it was omitted in that case).


def test_fully_set_up_attempts_install_plugins_and_reports_success(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "quartz" / "node_modules").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    _write_fake_npm_dispatch(bin_dir, install_exit=0, install_plugins_exit=0)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    data = json.loads(result.stdout)
    assert data["status"] == "fully_set_up"
    assert data["install_plugins_ok"] is True


def test_fully_set_up_reports_install_plugins_failure(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "quartz" / "node_modules").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    _write_fake_npm_dispatch(bin_dir, install_exit=0, install_plugins_exit=1)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    data = json.loads(result.stdout)
    assert data["status"] == "fully_set_up"
    assert data["install_plugins_ok"] is False


def test_npm_install_completed_fully_set_up_reports_install_plugins_outcome(tmp_path):
    (tmp_path / "quartz").mkdir()
    bin_dir = tmp_path / "bin"
    _write_fake_npm_dispatch(bin_dir, install_exit=0, install_plugins_exit=0)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    data = json.loads(result.stdout)
    assert data["status"] == "npm_install_completed_fully_set_up"
    assert data["install_plugins_ok"] is True


def test_npm_install_failed_submodule_exists_still_attempts_install_plugins(tmp_path):
    # Top-level `npm install` failing doesn't preclude `npm run install-plugins` from
    # working independently inside the already-added quartz/ submodule.
    (tmp_path / "quartz").mkdir()
    bin_dir = tmp_path / "bin"
    _write_fake_npm_dispatch(bin_dir, install_exit=1, install_plugins_exit=0)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    data = json.loads(result.stdout)
    assert data["status"] == "npm_install_failed_submodule_exists"
    assert data["install_plugins_ok"] is True


def test_no_quartz_dir_never_attempts_install_plugins(tmp_path):
    # quartz/ doesn't exist yet (first-time init, before `git submodule add`) — there is
    # nothing for `npx quartz plugin install` to operate on, so the field must be absent
    # rather than reporting a spurious failure.
    bin_dir = tmp_path / "bin"
    _write_fake_npm_dispatch(bin_dir, install_exit=0, install_plugins_exit=0)

    result = run(tmp_path, path=f"{bin_dir}:{os.environ['PATH']}")

    data = json.loads(result.stdout)
    assert data["status"] == "npm_install_completed_submodule_pending"
    assert "install_plugins_ok" not in data
