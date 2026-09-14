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


# --- checkpoints (Issue #797) -------------------------------------------------
#
# `ended_at` says whether the run finished; these lines say where it got to and
# what it skipped. The class they exist for is Issues #406 / #452 / #474 — a step
# at the tail of a long flow silently not running — all three of which were found
# only by a human auditing a published repository afterwards.


def _stamps(*names: str) -> list[dict]:
    return [{"pass": n, "at": "2026-09-07T10:44:02+09:00", "token": "unchecked"} for n in names]


def test_a_record_predating_checkpoints_says_nothing_about_passes(tmp_path):
    """Records written before checkpoints existed have no `passes` key at all,
    and there is nothing honest to report for them.

    The work fields are populated here on purpose: this must stay silent because
    the key is absent, not because the run looks like a no-op — that is the whole
    distinction the gate rests on (Issue #864).
    """
    path = _record(tmp_path, "20260907-104233-generate.md",
                   ended_at="2026-09-07T11:05:12+09:00",
                   sources=["a.md"], pages=["p.md"], outcome={"generated": 1})
    assert "passes:" not in path.read_text(encoding="utf-8")
    result = _run(tmp_path)
    assert "pass(es)" not in result.stdout
    assert "MISSING_PASS:" not in result.stdout
    assert "SUMMARY: runs=1, incomplete=0, missing_pass=0" in result.stdout


def test_a_run_that_did_work_and_stamped_nothing_is_reported(tmp_path):
    """The worst case, and the one the gate used to hide (Issue #864).

    `passes: []` is not "predates stamping": `start` writes the key empty on
    purpose, so a run that lost *every* stamping instruction is distinguishable
    from one that could not have stamped. Reporting only partial gaps had the
    line fall silent exactly where the failure was total.
    """
    _record(tmp_path, "20260907-104233-generate.md",
            ended_at="2026-09-07T11:05:12+09:00", passes=[],
            sources=["a.md"], pages=["p.md"], outcome={"generated": 1})
    result = _run(tmp_path)
    assert "MISSING_PASS:" in result.stdout
    assert "stamped no pass at all" in result.stdout
    # The evidence is on the line: it is why this is reported rather than taken
    # for a run that had nothing to do.
    assert "1 source(s), 1 page(s)" in result.stdout
    assert "pass1-extract, pass2b-type, pass2c-entities, pass3-generate, pass4-review " \
        "never ran" in result.stdout
    assert "missing_pass=1" in result.stdout


def test_a_run_that_stamped_nothing_and_did_nothing_is_silent(tmp_path):
    """A bare `/wikicommit-generate` on a current wiki finds no management file,
    says so and exits — a legitimate finish with no stamp, and the usual one.

    Reporting it would put the line on most runs, and a line that is always on
    stops being read (Issue #562's force). An all-zero outcome is not work.
    """
    _record(tmp_path, "20260907-104233-generate.md",
            ended_at="2026-09-07T11:05:12+09:00", passes=[], outcome={"generated": 0})
    result = _run(tmp_path)
    assert "MISSING_PASS:" not in result.stdout
    assert "missing_pass=0" in result.stdout


def test_last_run_reports_how_many_passes_were_stamped(tmp_path):
    _record(tmp_path, "20260907-104233-generate.md", ended_at="2026-09-07T11:05:12+09:00",
            outcome={"generated": 12}, passes=_stamps(
                "pass1-extract", "pass2b-type", "pass2c-entities",
                "pass3-generate", "pass4-review"))
    result = _run(tmp_path)
    assert "LAST_RUN: 2026-09-07 10:42 wikicommit-generate (22m39s, 5 pass(es), generated=12)" \
        in result.stdout


def test_an_unfinished_run_says_where_it_got_to(tmp_path):
    """The two halt paths change no file, so this is the only trace — and without
    a stamp that trace has no position."""
    _record(tmp_path, "20260905-140300-generate.md", started_at="2026-09-05T14:03:00+09:00",
            halted_reason="rules_version mismatch",
            passes=_stamps("pass1-extract", "pass2b-type"))
    result = _run(tmp_path)
    assert "halted: rules_version mismatch" in result.stdout
    assert "reached pass2b-type" in result.stdout
    assert "pass2c-entities, pass3-generate, pass4-review never ran" in result.stdout


def test_a_finished_run_with_a_gap_is_reported_as_missing_pass(tmp_path):
    """This is the #406 / #452 / #474 shape: the run completed, and a step in it
    simply did not happen."""
    _record(tmp_path, "20260907-104233-generate.md", ended_at="2026-09-07T11:05:12+09:00",
            passes=_stamps("pass1-extract", "pass2b-type", "pass2c-entities", "pass3-generate"))
    result = _run(tmp_path)
    assert "MISSING_PASS: 2026-09-07 10:42 wikicommit-generate " \
        "(finished, but pass4-review left no stamp)" in result.stdout
    assert "missing_pass=1" in result.stdout


def test_an_unfinished_run_is_not_also_reported_as_missing_pass(tmp_path):
    """It is already on INCOMPLETE_RUN: with the obvious reason for the gap, and
    "finished, but" would be false of it."""
    _record(tmp_path, "20260905-140300-generate.md", started_at="2026-09-05T14:03:00+09:00",
            passes=_stamps("pass1-extract"))
    result = _run(tmp_path)
    assert "INCOMPLETE_RUN:" in result.stdout
    assert "MISSING_PASS:" not in result.stdout
    assert "missing_pass=0" in result.stdout


def test_a_regenerate_run_is_not_faulted_for_skipping_pass_2(tmp_path):
    """That mode takes a page rather than a source, so Pass 2 does not run by
    design — and the narrowing is read off the record's own args."""
    _record(tmp_path, "20260907-104233-generate.md", ended_at="2026-09-07T11:05:12+09:00",
            args=["--regenerate", "--all"],
            passes=_stamps("pass1-extract", "pass3-generate", "pass4-review"))
    result = _run(tmp_path)
    assert "MISSING_PASS:" not in result.stdout
    assert "missing_pass=0" in result.stdout


def test_a_repeated_pass_name_is_not_a_gap(tmp_path):
    """generate walks the passes once per source; five `pass1-extract` stamps are
    five sources."""
    _record(tmp_path, "20260907-104233-generate.md", ended_at="2026-09-07T11:05:12+09:00",
            passes=_stamps("pass1-extract", "pass2b-type", "pass2c-entities",
                           "pass3-generate", "pass4-review",
                           "pass1-extract", "pass2b-type", "pass2c-entities",
                           "pass3-generate", "pass4-review"))
    result = _run(tmp_path)
    assert "MISSING_PASS:" not in result.stdout
    assert "10 pass(es)" in result.stdout


def test_a_malformed_passes_value_does_not_take_down_the_report(tmp_path):
    """A hand-edited record must not cost the caller the incomplete count, which
    is the one number here that has to err high."""
    _record(tmp_path, "20260907-104233-generate.md",
            ended_at="2026-09-07T11:05:12+09:00", passes="not a list")
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert "SUMMARY: runs=1, incomplete=0, missing_pass=0" in result.stdout


def test_every_record_reported_for_zero_stamps_states_its_evidence():
    """`work_recorded()` and `_work_summary()` must agree on what counts as work.

    The zero-stamp line is printed *because* the record shows work, and the
    summary is the only place that reason appears. `work_recorded()` accepts the
    loose shapes a hand-edited record can hold on purpose (a bare scalar where a
    list belongs, a non-mapping `outcome`), so a summary that counted only
    well-formed lists and mappings would print the strongest finding this line
    produces with no stated basis at all.

    Checked as an invariant over combinations rather than through one record,
    because the two functions are separate and nothing else ties them together.
    """
    sys.path.insert(0, str(SCRIPTS))
    import check_run_records as c

    values = [None, [], {}, "", 0, False, "s.md", ["a"], ["a", "b"], [""],
              {"g": 0}, {"g": 1}, {"g": "x"}, {"g": 0, "f": 2}, {"g": []}, 5]
    unexplained = [
        {"sources": s, "pages": p, "outcome": o}
        for s in values for p in values for o in values
        if c.work_recorded({"sources": s, "pages": p, "outcome": o})
        and not c._work_summary({"sources": s, "pages": p, "outcome": o})
    ]
    assert unexplained == []


# --- halt して閉じた実行（Issue #872）------------------------------------------
#
# halt は `record_run.py end --halted-reason` で記録を閉じるため `ended_at` を
# 持つ。`ended_at` を「完走したか」の代理指標にしていた間、halt は完走側に落ち、
# `MISSING_PASS:` に "finished, but" として出るか、1 行も出ないかのどちらかだった
# （後者は `missing_passes()` が空になる場合 — とくに `EXPECTED_PASSES` を持たない
# Skill では原理的にそうなる）。下の 3 件は Issue #872 の実測 3 件に対応する。


def test_a_halt_is_not_reported_as_finished(tmp_path):
    """実測 1 件目: ガード C の halt（打点は pass1-extract のみ）。

    以前は `MISSING_PASS: ... (finished, but ...)` に出ていた。halt に対して
    "finished" は偽であり、Pass 2c 以降に到達しないのは halt の意味そのもので
    あって「飛ばした」ではない。
    """
    _record(tmp_path, "20260910-100000-generate.md",
            started_at="2026-09-10T10:00:00+09:00", ended_at="2026-09-10T10:00:20+09:00",
            halted_reason="missing package: youtube-transcript-api",
            passes=_stamps("pass1-extract"))
    result = _run(tmp_path)
    assert "finished" not in result.stdout
    assert "MISSING_PASS:" not in result.stdout
    assert "INCOMPLETE_RUN:" in result.stdout
    assert "halted: missing package: youtube-transcript-api" in result.stdout
    assert "SUMMARY: runs=1, incomplete=1, missing_pass=0" in result.stdout


def test_a_halt_that_stamped_every_pass_is_still_reported(tmp_path):
    """実測 2 件目: Pass 4 の `rules_version` 不一致で halt（5 種すべて打点済み）。

    `missing_passes()` が空になるため `MISSING_PASS:` 側をどう直しても届かず、
    以前は 1 行も出なかった。
    """
    _record(tmp_path, "20260910-110000-generate.md",
            started_at="2026-09-10T11:00:00+09:00", ended_at="2026-09-10T11:03:00+09:00",
            halted_reason="rules_version mismatch",
            passes=_stamps("pass1-extract", "pass2b-type", "pass2c-entities",
                           "pass3-generate", "pass4-review"))
    result = _run(tmp_path)
    assert "INCOMPLETE_RUN: 2026-09-10 11:00 wikicommit-generate " \
        "(halted: rules_version mismatch (3m00s) — reached pass4-review)" in result.stdout
    assert "SUMMARY: runs=1, incomplete=1, missing_pass=0" in result.stdout


def test_a_halt_in_a_skill_with_no_expected_passes_is_reported(tmp_path):
    """実測 3 件目: `wikicommit-synthesize` の halt。

    `EXPECTED_PASSES` は `wikicommit-generate` の 1 エントリしか持たないため、
    この Skill の期待パスは空・欠落も空になり、`MISSING_PASS:` に出る余地が
    原理的に無い。判定を `halted_reason` に移したことで同じ 1 行が覆う。
    """
    _record(tmp_path, "20260910-120000-synthesize.md", skill="wikicommit-synthesize",
            started_at="2026-09-10T12:00:00+09:00", ended_at="2026-09-10T12:05:00+09:00",
            halted_reason="rules_version mismatch", passes=[])
    result = _run(tmp_path)
    assert "INCOMPLETE_RUN: 2026-09-10 12:00 wikicommit-synthesize " \
        "(halted: rules_version mismatch (5m00s))" in result.stdout
    assert "SUMMARY: runs=1, incomplete=1, missing_pass=0" in result.stdout


def test_last_run_names_a_halt(tmp_path):
    """`LAST_RUN:` は 1 件しか出ないため、そこに halt が来たときに
    「5 分かかった実行」としか読めないままにしない。"""
    _record(tmp_path, "20260910-120000-synthesize.md", skill="wikicommit-synthesize",
            started_at="2026-09-10T12:00:00+09:00", ended_at="2026-09-10T12:05:00+09:00",
            halted_reason="rules_version mismatch", passes=[])
    result = _run(tmp_path)
    assert "LAST_RUN: 2026-09-10 12:00 wikicommit-synthesize " \
        "(halted: rules_version mismatch, 5m00s)" in result.stdout


def test_a_run_that_was_never_closed_still_says_no_ended_at(tmp_path):
    """halt 側の文面へ寄せた結果、打刻忘れの側が失われていないこと。

    両者を分ける値は `halted_reason` だけであり、行はそれぞれ自分がどちらかを
    述べる（Step 17 の 1 行がこの 2 つを同時に数えるため）。
    """
    _record(tmp_path, "20260905-140300-generate.md",
            started_at="2026-09-05T14:03:00+09:00", passes=_stamps("pass1-extract"))
    result = _run(tmp_path)
    assert "INCOMPLETE_RUN: 2026-09-05 14:03 wikicommit-generate (no ended_at" in result.stdout
    assert "halted:" not in result.stdout


def test_a_record_that_is_both_halted_and_unclosed_says_both(tmp_path):
    """手編集の記録はこの組み合わせを持ちうる。どちらかを落とすと記録を
    誤って説明することになるため両方を出す。"""
    _record(tmp_path, "20260905-140300-generate.md",
            started_at="2026-09-05T14:03:00+09:00", halted_reason="rules_version mismatch")
    result = _run(tmp_path)
    assert "(no ended_at — halted: rules_version mismatch)" in result.stdout
