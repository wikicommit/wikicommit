"""Tests for .wikicommit/scripts/check_run_records.py (Issue #790).

The two lines this prints are the only reason the run records are worth writing:
without a consumer the tree would be a receptacle nothing reads (Issue #553).
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".wikicommit" / "scripts"


def _run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "check_run_records.py")],
        capture_output=True, text=True, cwd=cwd, check=False,
    )


def _record(cwd: Path, name: str, **fields) -> Path:
    directory = cwd / ".wikicommit" / "run"
    directory.mkdir(parents=True, exist_ok=True)
    front = {
        "skill": "wikicommit-generate",
        "started_at": "2026-09-07T10:42:33+09:00",
        "ended_at": "",
        "model": "claude-opus-5[1m]",
        "wikicommit_version": "0.3.0",
        "args": [], "sources": [], "pages": [], "outcome": {}, "halted_reason": "",
    }
    front.update(fields)
    import yaml
    path = directory / name
    path.write_text(
        "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + "---\n",
        encoding="utf-8",
    )
    return path


def test_a_missing_directory_says_so_rather_than_reporting_zeros(tmp_path):
    """"Nothing has been run since records existed" and "every run finished" are
    different states, and only the first means there was nothing to look at."""
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: runs=0, incomplete=0" in result.stdout
    assert "does not exist yet" in result.stdout


def test_an_empty_directory_says_so_too(tmp_path):
    (tmp_path / ".wikicommit" / "run").mkdir(parents=True)
    result = _run(tmp_path)
    assert "SUMMARY: runs=0, incomplete=0" in result.stdout
    assert "no run records yet" in result.stdout


def test_a_finished_run_reports_its_elapsed_time_and_outcome(tmp_path):
    """The duration exists in no other layer: generated_at is a date and a commit
    timestamp is the merge."""
    _record(tmp_path, "20260907-104233-generate.md",
            ended_at="2026-09-07T11:05:12+09:00", outcome={"generated": 12, "failed": 1})
    result = _run(tmp_path)
    assert "LAST_RUN: 2026-09-07 10:42 wikicommit-generate (22m39s, generated=12 failed=1)" in result.stdout
    assert "SUMMARY: runs=1, incomplete=0" in result.stdout
    assert "INCOMPLETE_RUN:" not in result.stdout


def test_an_unfinished_run_is_reported(tmp_path):
    """This is the whole point: the state such a run leaves behind is otherwise
    indistinguishable from a queue that has not reached those sources yet."""
    _record(tmp_path, "20260905-140300-generate.md",
            started_at="2026-09-05T14:03:00+09:00")
    result = _run(tmp_path)
    assert "INCOMPLETE_RUN: 2026-09-05 14:03 wikicommit-generate (no ended_at)" in result.stdout
    assert "SUMMARY: runs=1, incomplete=1" in result.stdout


def test_a_halt_reason_is_carried_onto_the_line(tmp_path):
    """A halt changes no file, so this is the only trace of it anywhere."""
    _record(tmp_path, "20260905-140300-generate.md", started_at="2026-09-05T14:03:00+09:00",
            halted_reason="rules_version mismatch")
    result = _run(tmp_path)
    assert "no ended_at — halted: rules_version mismatch" in result.stdout


def test_only_the_newest_run_is_reported_but_every_unfinished_one_is(tmp_path):
    """The last run answers "did what I just ran get anywhere", which is not a
    history; each unfinished record is individually actionable."""
    _record(tmp_path, "20260901-100000-generate.md", started_at="2026-09-01T10:00:00+09:00")
    _record(tmp_path, "20260902-100000-merge.md", skill="wikicommit-merge",
            started_at="2026-09-02T10:00:00+09:00")
    _record(tmp_path, "20260903-100000-generate.md", started_at="2026-09-03T10:00:00+09:00",
            ended_at="2026-09-03T10:30:00+09:00")
    result = _run(tmp_path)
    assert result.stdout.count("LAST_RUN:") == 1
    assert "LAST_RUN: 2026-09-03 10:00" in result.stdout
    assert result.stdout.count("INCOMPLETE_RUN:") == 2
    assert "SUMMARY: runs=3, incomplete=1" not in result.stdout
    assert "SUMMARY: runs=3, incomplete=2" in result.stdout


def test_the_newest_of_a_colliding_second_is_the_one_reported(tmp_path):
    """`...-generate-2.md` sorts before `...-generate.md` on the bare filename,
    so ordering on that would print the oldest record of a second as LAST_RUN:.
    Reader and writer share `run_sort_key()` to keep the two consistent."""
    _record(tmp_path, "20260907-104233-generate.md",
            started_at="2026-09-07T10:42:33+09:00", ended_at="2026-09-07T10:43:00+09:00",
            outcome={"generated": 1})
    _record(tmp_path, "20260907-104233-generate-2.md",
            started_at="2026-09-07T10:42:33+09:00", ended_at="2026-09-07T10:59:33+09:00",
            outcome={"generated": 99})
    result = _run(tmp_path)
    assert "generated=99" in result.stdout, result.stdout
    assert "generated=1" not in result.stdout, result.stdout


def test_a_mixed_naive_and_aware_stamp_does_not_take_down_the_report(tmp_path):
    """These records are hand-editable and not tracked. Subtracting a naive
    stamp from an aware one raises TypeError, which would lose LAST_RUN:, every
    INCOMPLETE_RUN: line and SUMMARY: — including the count that must err high."""
    _record(tmp_path, "20260901-100000-generate.md",
            started_at="2026-09-01T10:00:00+09:00")
    _record(tmp_path, "20260902-100000-generate.md",
            started_at="2026-09-02T10:00:00", ended_at="2026-09-02T10:30:00+09:00")
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert "LAST_RUN:" in result.stdout
    assert "SUMMARY: runs=2, incomplete=1" in result.stdout


def test_an_unreadable_record_warns_rather_than_being_dropped(tmp_path):
    """Skipping it silently would understate the incomplete count, which is the
    one number here that has to err high."""
    directory = tmp_path / ".wikicommit" / "run"
    directory.mkdir(parents=True)
    (directory / "20260907-104233-generate.md").write_text("not frontmatter\n", encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "WARNING:" in result.stderr


def test_files_that_are_not_records_are_ignored(tmp_path):
    directory = tmp_path / ".wikicommit" / "run"
    directory.mkdir(parents=True)
    (directory / "README.md").write_text("notes\n", encoding="utf-8")
    _record(tmp_path, "20260907-104233-generate.md", ended_at="2026-09-07T10:43:00+09:00")
    result = _run(tmp_path)
    assert "SUMMARY: runs=1, incomplete=0" in result.stdout
    assert not result.stderr.strip()


def test_it_never_writes_to_the_run_directory(tmp_path):
    """Rotation belongs to the writer; a health check that deleted records would
    remove the evidence it exists to report."""
    path = _record(tmp_path, "20260907-104233-generate.md")
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    _run(tmp_path)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_the_status_skill_runs_this_check():
    """A consumer nothing invokes is the receptacle this was meant not to be."""
    text = (REPO / ".claude" / "skills" / "wikicommit-status" / "SKILL.md").read_text(encoding="utf-8")
    assert "check_run_records.py" in text
