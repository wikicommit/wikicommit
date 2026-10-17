"""Closing the tracking Issue of a removed page records no review (Issue #1131).

A page taken down by `/wikicommit-remove` or by a merge stays on disk at
`status: removed`. `review-issue-close-sync.yml` skipped only a page whose file
was gone, so closing a removed page's Issue — which the merge's report asked the
person to do — marked it `reviewed` and wrote a human review record for a page
nobody read. Seen in a pilot wiki, where the close-sync pull requests merged on
their own. The `Resolve target page` step's embedded Python is run as written.
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

SYNC_YML = (Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts"
            / "templates" / "workflows" / "review-issue-close-sync.yml")
PAGE = ".wikicommit/entity/en/DefinedTerm/old.md"


def _resolver() -> str:
    steps = list(yaml.safe_load(SYNC_YML.read_text(encoding="utf-8"))["jobs"].values())[0]["steps"]
    run = next(s["run"] for s in steps if s.get("name") == "Resolve target page")
    match = re.search(r"<<'PY'\n(.*?)\n\s*PY\n", run, re.DOTALL)
    assert match, "the embedded Python heredoc is missing"
    return match.group(1)


def _resolve(tmp_path: Path, front: str) -> dict:
    page = tmp_path / PAGE
    page.parent.mkdir(parents=True)
    page.write_text(f"---\n{front}---\n\nBody.\n", encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-"], input=_resolver(), capture_output=True, text=True, cwd=tmp_path,
        env={"ISSUE_BODY": f"<!-- wikicommit-page: {PAGE} -->", "GITHUB_OUTPUT": str(out),
             "STATE_REASON": "completed", "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())


def test_a_removed_page_is_skipped(tmp_path):
    outputs = _resolve(tmp_path, 'title: "Old"\nstatus: removed\nremoved_reason: merged\n'
                                 "merged_into: .wikicommit/entity/en/DefinedTerm/new.md\n"
                                 "review_status: pending\n")
    assert outputs == {"proceed": "false"}


def test_a_live_page_still_proceeds(tmp_path):
    outputs = _resolve(tmp_path, 'title: "Old"\nreview_status: pending\n')
    assert outputs["proceed"] == "true"
    assert outputs["path"] == PAGE
