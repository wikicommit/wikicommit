"""tools/check_designdoc_issue_refs.py (Issue #1138)."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import check_designdoc_issue_refs as guard  # noqa: E402


def run(cwd):
    return subprocess.run([sys.executable, str(REPO / "tools/check_designdoc_issue_refs.py")],
                          cwd=cwd, capture_output=True, text=True)


def test_the_repository_passes():
    result = run(REPO)
    assert result.returncode == 0, result.stdout


def test_every_split_doc_has_its_history():
    for rel in guard.CAPS:
        assert (REPO / "docs/history" / Path(rel).name).exists(), rel


def _layout(tmp_path, refs):
    # Every split doc is laid out (with no references) so that only the pipeline
    # entry, which each test varies, can produce a finding.
    (tmp_path / "docs/history").mkdir(parents=True)
    for rel in guard.CAPS:
        (tmp_path / "docs/history" / Path(rel).name).write_text("history\n", encoding="utf-8")
        (tmp_path / rel).write_text("body\n", encoding="utf-8")
    (tmp_path / "docs/DesignDoc-pipeline.md").write_text(
        "".join(f"x (Issue #{i})\n" for i in range(refs)), encoding="utf-8")


def test_a_growing_count_fails(tmp_path):
    _layout(tmp_path, guard.CAPS["docs/DesignDoc-pipeline.md"] + 1)
    result = run(tmp_path)
    assert result.returncode == 1
    assert "ERROR: docs/DesignDoc-pipeline.md" in result.stdout


def test_a_shrinking_count_asks_to_lower_the_cap(tmp_path, monkeypatch, capsys):
    # Patch the cap in-process so this keeps working once the real cap reaches 0.
    _layout(tmp_path, 0)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(guard.CAPS, "docs/DesignDoc-pipeline.md", 1)
    assert guard.main() == 0
    assert "NOTE: docs/DesignDoc-pipeline.md" in capsys.readouterr().out


def test_a_missing_history_file_fails(tmp_path):
    _layout(tmp_path, 0)
    (tmp_path / "docs/history/DesignDoc-pipeline.md").unlink()
    assert run(tmp_path).returncode == 1
