#!/usr/bin/env python3
"""Determine Quartz v5 setup status for wikicommit-init step 3.d (#229).

Runs `npm install` when needed and reports a single status via JSON on stdout.
The caller (SKILL.md) maps the status to the appropriate next-steps message —
this script only makes the (previously agent-read) state-machine decision so it
can't be misread by the agent walking a multi-branch prose description.

Statuses:
  fully_set_up                        - node_modules/ and quartz/node_modules/ already exist; npm install skipped
  npm_install_completed_fully_set_up  - npm install succeeded and quartz/ already exists (submodule deps now installed)
  npm_install_completed_submodule_pending - npm install succeeded but quartz/ does not exist yet (first-time init)
  npm_install_failed_submodule_exists - npm install failed but quartz/ already exists (submodule already added)
  npm_install_failed_no_submodule     - npm install failed and quartz/ does not exist

Whenever quartz/ already exists (fully_set_up, npm_install_completed_fully_set_up,
npm_install_failed_submodule_exists), `npm run install-plugins` is also attempted
best-effort and its outcome reported as the `install_plugins_ok` field (Issue #380 —
without this, a `--no-overwrite --quartz` re-init that finds Quartz already set up
silently drops the `npm run install-plugins` guidance entirely, since the
"Set up Quartz v5" next-steps step that normally carries it is omitted in that case).
It cannot run when quartz/ does not exist yet (first-time init, before the user has
run `git submodule add`) — `install_plugins_ok` is absent from the JSON in that case.
"""

import json
import subprocess
import sys
from pathlib import Path


def _is_dir(path: str) -> bool:
    return Path(path).is_dir()


def _run_install_plugins() -> bool:
    """Best-effort `npm run install-plugins`. Returns True iff it exits 0."""
    try:
        result = subprocess.run(["npm", "run", "install-plugins"], check=False)
        return result.returncode == 0
    except OSError:
        return False


def main() -> int:
    if _is_dir("node_modules") and _is_dir("quartz/node_modules"):
        print(json.dumps({"status": "fully_set_up", "install_plugins_ok": _run_install_plugins()}))
        return 0

    try:
        result = subprocess.run(["npm", "install"], check=False)
        npm_install_ok = result.returncode == 0
    except OSError:
        # npm/Node.js not installed, or otherwise unable to launch the command.
        npm_install_ok = False
    quartz_exists = _is_dir("quartz")

    if not npm_install_ok:
        status = "npm_install_failed_submodule_exists" if quartz_exists else "npm_install_failed_no_submodule"
    else:
        status = "npm_install_completed_fully_set_up" if quartz_exists else "npm_install_completed_submodule_pending"

    output = {"status": status}
    if quartz_exists:
        output["install_plugins_ok"] = _run_install_plugins()
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
