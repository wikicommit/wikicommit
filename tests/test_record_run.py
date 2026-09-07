"""Tests for .wikicommit/scripts/record_run.py (Issue #790).

The load-bearing property is the asymmetry between the two ways this can be
wrong. A run that finished but was never closed is reported as incomplete, which
costs a reader a glance; a run that did not finish but is reported as complete
would silently retire the one question the record exists to answer. Every
assertion here that looks like it is about `ended_at` is really about keeping
the error on the first side.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent
SCRIPT = REPO / ".wikicommit" / "scripts" / "record_run.py"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd, check=False,
    )


def _start(cwd: Path, skill: str = "wikicommit-generate", *extra: str) -> Path:
    result = _run(cwd, "start", "--skill", skill, *extra)
    assert result.returncode == 0, result.stderr
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("RUN_STARTED:"))
    return cwd / line.split(" ", 2)[1]


def _front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---\n")[1])


def test_start_writes_a_record_with_an_empty_ended_at(tmp_path):
    """The empty string is the signal, in the same position a timestamp will take."""
    path = _start(tmp_path, "wikicommit-generate", "--model", "claude-opus-5[1m]",
                  "--arg", "https://example.com/a")
    assert path.is_file()
    front = _front(path)
    assert front["skill"] == "wikicommit-generate"
    assert front["ended_at"] == ""
    assert front["started_at"]
    assert front["model"] == "claude-opus-5[1m]"
    assert front["args"] == ["https://example.com/a"]
    assert front["wikicommit_version"]


def test_the_body_is_empty(tmp_path):
    """Frontmatter only, by design — there is nothing a run record says in prose,
    and an empty body invites something being written there because there is room."""
    path = _start(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("---\n")
    assert text.count("---\n") == 2


def test_the_filename_carries_the_stamp_and_the_skill(tmp_path):
    path = _start(tmp_path, "wikicommit-merge")
    assert path.name.endswith("-merge.md")
    stamp = path.name.split("-merge.md")[0]
    assert len(stamp) == len("20260907-104233"), path.name


def test_end_fills_in_the_outcome(tmp_path):
    path = _start(tmp_path)
    result = _run(tmp_path, "end", str(path),
                  "--page", ".wikicommit/entity/ja/Place/minuma.md",
                  "--source", ".wikicommit/source/url/example.com/a.md",
                  "--outcome", "generated=12", "--outcome", "failed=1")
    assert result.returncode == 0, result.stderr
    front = _front(path)
    assert front["ended_at"]
    assert front["pages"] == [".wikicommit/entity/ja/Place/minuma.md"]
    assert front["sources"] == [".wikicommit/source/url/example.com/a.md"]
    assert front["outcome"] == {"generated": 12, "failed": 1}


def test_end_records_a_halt_that_changed_no_file(tmp_path):
    """The two halt paths stop before anything is written, so this line is the
    only trace such a run leaves anywhere."""
    path = _start(tmp_path)
    result = _run(tmp_path, "end", str(path), "--halted-reason", "rules_version mismatch")
    assert result.returncode == 0, result.stderr
    assert _front(path)["halted_reason"] == "rules_version mismatch"


def test_end_refuses_a_path_that_does_not_exist(tmp_path):
    """It will not guess at which record to close. Guessing would shut a genuinely
    dead run from an earlier session and erase the signal it was carrying."""
    result = _run(tmp_path, "end", ".wikicommit/run/20260101-000000-generate.md")
    assert result.returncode == 1
    assert "no such run record" in result.stderr


def test_end_does_not_disturb_the_fields_it_was_not_given(tmp_path):
    path = _start(tmp_path, "wikicommit-generate", "--model", "m", "--arg", "a")
    _run(tmp_path, "end", str(path), "--outcome", "generated=1")
    front = _front(path)
    assert front["model"] == "m"
    assert front["args"] == ["a"]
    assert front["pages"] == []


def test_a_non_integer_outcome_is_rejected(tmp_path):
    path = _start(tmp_path)
    result = _run(tmp_path, "end", str(path), "--outcome", "generated=lots")
    assert result.returncode == 1
    assert "expects an integer" in result.stderr
    # And the record is left as it was, rather than half-closed.
    assert _front(path)["ended_at"] == ""


def test_an_unknown_skill_is_rejected(tmp_path):
    """The four are the Skills whose half-finished state is otherwise unreadable."""
    result = _run(tmp_path, "start", "--skill", "wikicommit-fix")
    assert result.returncode != 0


def test_two_starts_in_the_same_second_do_not_overwrite(tmp_path):
    sys.path.insert(0, str(SCRIPT.parent))
    from record_run import allocate_run_path

    directory = tmp_path / "run"
    directory.mkdir()
    first = allocate_run_path(directory, "20260907-104233", "wikicommit-generate")
    first.write_text("---\n---\n", encoding="utf-8")
    second = allocate_run_path(directory, "20260907-104233", "wikicommit-generate")
    assert second != first
    assert not second.exists()


def test_rotation_keeps_the_newest_and_drops_the_rest(tmp_path):
    sys.path.insert(0, str(SCRIPT.parent))
    from record_run import rotate

    directory = tmp_path / "run"
    directory.mkdir()
    for day in range(1, 6):
        (directory / f"2026090{day}-104233-generate.md").write_text("---\n---\n", encoding="utf-8")
    rotate(directory, keep=2)
    assert sorted(p.name for p in directory.glob("*.md")) == [
        "20260904-104233-generate.md", "20260905-104233-generate.md",
    ]


def test_rotation_drops_the_oldest_of_a_colliding_second_not_the_newest(tmp_path):
    """The collision suffix does not sort after the unsuffixed name.

    `...-generate-2.md` sorts *before* `...-generate.md` because `-` precedes
    `.`, so ordering on the bare filename would prune the newest records of a
    second first. `record_review.py` shares `record_sort_key()` between writer
    and reader for exactly this; `run_sort_key()` is the same key here.
    """
    sys.path.insert(0, str(SCRIPT.parent))
    from record_run import allocate_run_path, rotate

    directory = tmp_path / "run"
    directory.mkdir()
    written = []
    for _ in range(3):
        path = allocate_run_path(directory, "20260907-104233", "wikicommit-generate")
        path.write_text("---\n---\n", encoding="utf-8")
        written.append(path)
    rotate(directory, keep=1)
    assert [p.name for p in directory.glob("*.md")] == [written[-1].name]


def test_rotation_ignores_files_that_are_not_records(tmp_path):
    sys.path.insert(0, str(SCRIPT.parent))
    from record_run import rotate

    directory = tmp_path / "run"
    directory.mkdir()
    stray = directory / "README.md"
    stray.write_text("not a record\n", encoding="utf-8")
    for day in range(1, 4):
        (directory / f"2026090{day}-104233-generate.md").write_text("---\n---\n", encoding="utf-8")
    rotate(directory, keep=1)
    assert stray.exists()


def test_rotation_runs_on_start(tmp_path):
    """Rotation happens at write time, so the directory stays bounded without
    anything having to remember to clean it. Exercised at the real KEEP_RECORDS
    rather than a patched one: `rotate`'s default binds at definition, so a test
    that patches the module constant would silently exercise nothing."""
    sys.path.insert(0, str(SCRIPT.parent))
    from record_run import KEEP_RECORDS

    directory = tmp_path / ".wikicommit" / "run"
    directory.mkdir(parents=True)
    for n in range(KEEP_RECORDS + 5):
        (directory / f"20260101-{n:06d}-generate.md").write_text("---\n---\n", encoding="utf-8")
    _start(tmp_path)
    assert len(list(directory.glob("*.md"))) == KEEP_RECORDS
    # The oldest went and the newest stayed, rather than the other way round.
    assert not (directory / "20260101-000000-generate.md").exists()
    assert (directory / f"20260101-{KEEP_RECORDS + 4:06d}-generate.md").exists()


def test_end_survives_a_hand_edited_naive_started_at(tmp_path):
    """A record can be read and edited by hand, and this tree is not tracked.

    Subtracting a naive stamp from an aware one raises TypeError, which is
    caught by neither `cmd_end`'s handler nor `main`'s. The record itself is
    already written by then, so the crash would report a run that closed fine
    as a failure.
    """
    path = _start(tmp_path)
    text = path.read_text(encoding="utf-8")
    started = _front(path)["started_at"]
    path.write_text(text.replace(started, started[:19]), encoding="utf-8")

    result = _run(tmp_path, "end", str(path.relative_to(tmp_path)))
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert _front(path)["ended_at"]


@pytest.mark.parametrize("skill", ["wikicommit-generate", "wikicommit-translate",
                                   "wikicommit-synthesize", "wikicommit-merge"])
def test_each_writing_skill_invokes_the_recorder(skill):
    """A script nothing calls records nothing. Both ends are asserted because a
    Skill that only opens records would report every run as incomplete."""
    text = (REPO / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert f"record_run.py start --skill {skill}" in text, skill
    assert "record_run.py end" in text, skill
