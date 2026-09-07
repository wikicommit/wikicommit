"""Tests for .claude/skills/wikicommit-init/scripts/templates/repair-plugin-builds.cjs (#382)

Quartz's own installer (quartz/quartz/cli/plugin-git-handlers.js) writes a plugin's
quartz.lock.json entry as soon as `git clone` succeeds, before that plugin's own
`npm install --ignore-scripts && npm run build` runs. If that build step fails, the
lockfile entry is never corrected, so the next `npx quartz plugin install --from-config`
run's "already installed?" check (`lockfile.plugins[name] && fs.existsSync(pluginDir)`)
stays true forever. repair-plugin-builds.cjs detects this (plugin directory exists but
has no dist/ — the same completion signal Quartz's own hasPrebuiltDist/needsBuild use)
and retries by deleting the stuck plugin's directory and lockfile entry, then re-running
`npx quartz plugin install --from-config` (bounded retries).

These tests fake `npx` on PATH rather than using the real Quartz CLI (no network, no
real plugin repositories) — the fake mirrors the exact clone-then-build-then-lockfile
sequencing described above: on each invocation it always (re)creates the plugin
directory and (re)writes its lockfile entry (mirroring a clone that always succeeds),
and only creates dist/ once a controllable "recovers at attempt N" threshold is met
(mirroring a build that may or may not succeed on a given retry).
"""

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

NODE = shutil.which("node")

SCRIPT = (
    Path(__file__).parent.parent
    / ".claude"
    / "skills"
    / "wikicommit-init"
    / "scripts"
    / "templates"
    / "repair-plugin-builds.cjs"
)

_FAKE_NPX = """#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const name = process.env.NPX_FAKE_PLUGIN_NAME;
const recoverAtAttempt = process.env.NPX_FAKE_RECOVER_AT_ATTEMPT
  ? parseInt(process.env.NPX_FAKE_RECOVER_AT_ATTEMPT, 10)
  : null;
const vanish = process.env.NPX_FAKE_VANISH === "1";

const cwd = process.cwd();
const lockfilePath = path.join(cwd, "quartz.lock.json");
const pluginsDir = path.join(cwd, ".quartz", "plugins");
const countFile = path.join(cwd, ".npx-fake-invocations");

let count = fs.existsSync(countFile) ? parseInt(fs.readFileSync(countFile, "utf-8"), 10) : 0;
count += 1;
fs.writeFileSync(countFile, String(count));

if (vanish) {
  // Simulates a total re-clone failure (e.g. network down): unlike a build
  // failure, Quartz's own clone catch block writes nothing to the lockfile and
  // leaves no directory behind, so the plugin is left completely absent.
  process.exit(0);
}

const lockfile = fs.existsSync(lockfilePath)
  ? JSON.parse(fs.readFileSync(lockfilePath, "utf-8"))
  : { version: "1.0.0", plugins: {} };

const pluginDir = path.join(pluginsDir, name);
fs.mkdirSync(pluginDir, { recursive: true });
lockfile.plugins[name] = {
  source: "github:test/test",
  resolved: "https://example.com/test/test",
  commit: "deadbeef",
  installedAt: new Date().toISOString(),
};
fs.mkdirSync(path.dirname(lockfilePath), { recursive: true });
fs.writeFileSync(lockfilePath, JSON.stringify(lockfile, null, 2) + "\\n");

if (recoverAtAttempt !== null && count >= recoverAtAttempt) {
  fs.mkdirSync(path.join(pluginDir, "dist"), { recursive: true });
}
process.exit(0);
"""


def _write_fake_npx(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    npx = bin_dir / "npx"
    npx.write_text(_FAKE_NPX, encoding="utf-8")
    npx.chmod(npx.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _seed_stuck_plugin(repo_root: Path, name: str) -> Path:
    """Seeds a plugin cloned-but-never-built: lockfile entry + directory, no dist/."""
    quartz_dir = repo_root / "quartz"
    plugin_dir = quartz_dir / ".quartz" / "plugins" / name
    plugin_dir.mkdir(parents=True)
    lockfile = {
        "version": "1.0.0",
        "plugins": {
            name: {
                "source": "github:test/test",
                "resolved": "https://example.com/test/test",
                "commit": "cafebabe",
                "installedAt": "2026-01-01T00:00:00.000Z",
            }
        },
    }
    (quartz_dir / "quartz.lock.json").write_text(json.dumps(lockfile, indent=2) + "\n", encoding="utf-8")
    return plugin_dir


def run(repo_root: Path, env_extra: dict, path: str | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [NODE, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
        check=False,
    )


def _lockfile_plugins(repo_root: Path) -> dict:
    return json.loads((repo_root / "quartz" / "quartz.lock.json").read_text(encoding="utf-8"))["plugins"]


def test_no_stuck_plugins_is_a_fast_noop(tmp_path):
    # Plugin already has dist/ — nothing to repair. No npx anywhere on PATH: if the
    # script wrongly invoked it, this would crash instead of exiting cleanly, proving
    # the repair loop was actually skipped.
    quartz_dir = tmp_path / "quartz"
    plugin_dir = quartz_dir / ".quartz" / "plugins" / "healthy-plugin"
    (plugin_dir / "dist").mkdir(parents=True)
    lockfile = {"version": "1.0.0", "plugins": {"healthy-plugin": {"source": "github:test/test"}}}
    (quartz_dir / "quartz.lock.json").write_text(json.dumps(lockfile), encoding="utf-8")

    result = run(tmp_path, {}, path="")

    assert result.returncode == 0
    assert (plugin_dir / "dist").is_dir()


def test_no_lockfile_is_a_fast_noop(tmp_path):
    (tmp_path / "quartz").mkdir()

    result = run(tmp_path, {}, path="")

    assert result.returncode == 0


def test_stuck_plugin_not_yet_cloned_is_left_alone(tmp_path):
    # Lockfile entry with no matching directory at all is a clone failure, which
    # Quartz's own installer already retries on its own next run — not our concern.
    quartz_dir = tmp_path / "quartz"
    quartz_dir.mkdir()
    lockfile = {"version": "1.0.0", "plugins": {"never-cloned": {"source": "github:test/test"}}}
    (quartz_dir / "quartz.lock.json").write_text(json.dumps(lockfile), encoding="utf-8")

    result = run(tmp_path, {}, path="")

    assert result.returncode == 0
    assert _lockfile_plugins(tmp_path) == lockfile["plugins"]


def test_stuck_plugin_recovers_on_first_retry(tmp_path):
    plugin_dir = _seed_stuck_plugin(tmp_path, "flaky-plugin")
    assert not (plugin_dir / "dist").exists()
    bin_dir = tmp_path / "bin"
    _write_fake_npx(bin_dir)

    result = run(
        tmp_path,
        {"NPX_FAKE_PLUGIN_NAME": "flaky-plugin", "NPX_FAKE_RECOVER_AT_ATTEMPT": "1"},
        path=f"{bin_dir}:{os.environ['PATH']}",
    )

    assert result.returncode == 0
    assert (plugin_dir / "dist").is_dir()
    assert "flaky-plugin" in _lockfile_plugins(tmp_path)
    assert (tmp_path / "quartz" / ".npx-fake-invocations").read_text(encoding="utf-8") == "1"


def test_stuck_plugin_recovers_after_transient_retries(tmp_path):
    plugin_dir = _seed_stuck_plugin(tmp_path, "eventually-fine")
    bin_dir = tmp_path / "bin"
    _write_fake_npx(bin_dir)

    result = run(
        tmp_path,
        {"NPX_FAKE_PLUGIN_NAME": "eventually-fine", "NPX_FAKE_RECOVER_AT_ATTEMPT": "2"},
        path=f"{bin_dir}:{os.environ['PATH']}",
    )

    assert result.returncode == 0
    assert (plugin_dir / "dist").is_dir()
    assert (tmp_path / "quartz" / ".npx-fake-invocations").read_text(encoding="utf-8") == "2"


def test_stuck_plugin_reports_failure_after_max_attempts(tmp_path):
    plugin_dir = _seed_stuck_plugin(tmp_path, "permanently-broken")
    bin_dir = tmp_path / "bin"
    _write_fake_npx(bin_dir)

    result = run(
        tmp_path,
        {"NPX_FAKE_PLUGIN_NAME": "permanently-broken"},  # NPX_FAKE_RECOVER_AT_ATTEMPT unset: never recovers
        path=f"{bin_dir}:{os.environ['PATH']}",
    )

    assert result.returncode == 1
    assert "permanently-broken" in result.stderr
    assert not (plugin_dir / "dist").exists()
    # Bounded retries, not an infinite loop: exactly 3 attempts.
    assert (tmp_path / "quartz" / ".npx-fake-invocations").read_text(encoding="utf-8") == "3"


def test_plugin_that_vanishes_entirely_on_retry_is_still_reported_as_failed(tmp_path):
    # A plugin cleared for retry can fail its re-clone completely (no directory at
    # all left behind) rather than just failing its build again. Directory-less is
    # exactly what findStuckPlugins treats as "not our concern" (ordinarily a
    # self-healing clone failure) — the script must still remember this plugin was
    # stuck to begin with and report it, not silently exit 0 because nothing
    # currently looks stuck.
    plugin_dir = _seed_stuck_plugin(tmp_path, "vanishes-on-retry")
    bin_dir = tmp_path / "bin"
    _write_fake_npx(bin_dir)

    result = run(
        tmp_path,
        {"NPX_FAKE_PLUGIN_NAME": "vanishes-on-retry", "NPX_FAKE_VANISH": "1"},
        path=f"{bin_dir}:{os.environ['PATH']}",
    )

    assert result.returncode == 1
    assert "vanishes-on-retry" in result.stderr
    assert not plugin_dir.exists()
    assert "vanishes-on-retry" not in _lockfile_plugins(tmp_path)
