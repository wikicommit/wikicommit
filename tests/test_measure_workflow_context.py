"""Tests for tools/measure_workflow_context.py (Issue #1267).

A small made-up run record and conversation log: two sources through a
two-pass loop, where the second source re-reads the first pass's instructions
and gets a short stub back.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "tools" / "measure_workflow_context.py"

RUN = """\
---
skill: wikicommit-generate
started_at: '2026-10-08T10:00:00+09:00'
workflow:
  state: finished
  log:
  - {key: preflight, step: preflight, at: '2026-10-08T10:00:05+09:00', outcome: ran}
  - {key: pass1|a.md, step: pass1, item: a.md, at: '2026-10-08T10:01:00+09:00', outcome: ok}
  - {key: pass2|a.md, step: pass2, item: a.md, at: '2026-10-08T10:02:00+09:00', outcome: ok}
  - {key: pass1|b.md, step: pass1, item: b.md, at: '2026-10-08T10:03:00+09:00', outcome: ok}
  - {key: pass2|b.md, step: pass2, item: b.md, at: '2026-10-08T10:04:00+09:00', outcome: ok}
---
"""

PASS1 = "/repo/.claude/skills/wikicommit-generate/references/pass1-extract.md"


def assistant(ts: str, msg_id: str, context: int, tools=(), sidechain=False) -> dict:
    return {
        "type": "assistant", "timestamp": ts, "isSidechain": sidechain,
        "message": {
            "id": msg_id,
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": context - 10,
                      "cache_read_input_tokens": 0, "output_tokens": 5},
            "content": [{"type": "tool_use", "id": tid, "name": name, "input": data}
                        for tid, name, data in tools],
        },
    }


def result(tool_id: str, text: str) -> dict:
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text}]}}


def make_log(path: Path) -> Path:
    rows = [
        assistant("2026-10-08T00:59:00Z", "m0", 1000),  # before the run
        assistant("2026-10-08T01:00:30Z", "m1", 2000, [("t1", "Read", {"file_path": PASS1})]),
        result("t1", "x" * 400),
        # the same message logged again for a second content block: counted once
        assistant("2026-10-08T01:00:30Z", "m1", 2000),
        assistant("2026-10-08T01:01:30Z", "m2", 3000,
                  [("t2", "Read", {"file_path": "/repo/.wikicommit/entity/ja/Person/x.md"})]),
        result("t2", "page text"),
        assistant("2026-10-08T01:02:30Z", "m3", 3500, [("t3", "Read", {"file_path": PASS1})]),
        result("t3", "unchanged"),
        assistant("2026-10-08T01:03:10Z", "s1", 99999, sidechain=True),
        assistant("2026-10-08T01:03:30Z", "m4", 4500,
                  [("t4", "Bash", {"command": "cat .wikicommit/review-rules.md"})]),
        result("t4", "y" * 50),
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)] + args, capture_output=True,
                          text=True, check=False)


def measure(tmp_path: Path) -> dict:
    record = tmp_path / "run.md"
    record.write_text(RUN, encoding="utf-8")
    log = make_log(tmp_path / "session.jsonl")
    proc = run(["--run", str(record), "--log", str(log), "--json"])
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_steps_get_the_calls_between_log_entries(tmp_path):
    data = measure(tmp_path)
    (rep,) = data["runs"]
    assert rep["context_before"] == 1000
    steps = [(s["step"], s["item"], s["calls"], s["context_end"], s["growth"]) for s in rep["steps"]]
    assert steps == [
        ("preflight", None, 0, 1000, 0),
        ("pass1", "a.md", 1, 2000, 1000),
        ("pass2", "a.md", 1, 3000, 1000),
        ("pass1", "b.md", 1, 3500, 500),
        ("pass2", "b.md", 1, 4500, 1000),
    ]
    assert rep["per_item_growth"] == {"a.md": 2000, "b.md": 1500}
    assert data["subagent_calls"] == 1


def test_instruction_reads_are_counted_with_returned_size(tmp_path):
    (rep,) = measure(tmp_path)["runs"]
    reads = rep["reads"]
    pass1 = ".claude/skills/wikicommit-generate/references/pass1-extract.md"
    assert reads[pass1] == {"count": 2, "bytes": [400, len("unchanged")]}
    assert reads[".wikicommit/review-rules.md"]["count"] == 1
    # a page read is not an instruction read, and its path is not printed
    assert not any("entity" in name for name in reads)


def test_text_output_has_no_content(tmp_path):
    record = tmp_path / "run.md"
    record.write_text(RUN, encoding="utf-8")
    log = make_log(tmp_path / "session.jsonl")
    proc = run(["--run", str(record), "--log", str(log)])
    assert proc.returncode == 0, proc.stderr
    assert "READS .claude/skills/wikicommit-generate/references/pass1-extract.md: 2 time(s)" in proc.stdout
    assert "page text" not in proc.stdout and "xxxx" not in proc.stdout


def test_a_record_without_a_workflow_log_is_refused(tmp_path):
    record = tmp_path / "run.md"
    record.write_text("---\nskill: x\nstarted_at: '2026-10-08T10:00:00+09:00'\n---\n", encoding="utf-8")
    log = make_log(tmp_path / "session.jsonl")
    assert run(["--run", str(record), "--log", str(log)]).returncode == 2


def test_a_call_in_the_same_second_as_the_step_end_stays_with_the_step(tmp_path):
    # the engine writes `at` truncated to the second; the call that reported the
    # step done is logged a fraction of a second before the engine ran
    record = tmp_path / "run.md"
    record.write_text(RUN, encoding="utf-8")
    log = make_log(tmp_path / "session.jsonl")
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(assistant("2026-10-08T01:04:00.400Z", "m5", 4800)) + "\n")
    proc = run(["--run", str(record), "--log", str(log), "--json"])
    assert proc.returncode == 0, proc.stderr
    (rep,) = json.loads(proc.stdout)["runs"]
    assert rep["steps"][-1]["calls"] == 2
    assert rep["steps"][-1]["context_end"] == 4800


def test_a_read_after_cd_is_counted(tmp_path):
    record = tmp_path / "run.md"
    record.write_text(RUN, encoding="utf-8")
    log = tmp_path / "session.jsonl"
    rows = [
        assistant("2026-10-08T01:00:30Z", "m1", 2000,
                  [("t1", "Bash", {"command": "cd /repo && cat .wikicommit/schema/Person.md"})]),
        result("t1", "z" * 30),
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    proc = run(["--run", str(record), "--log", str(log), "--json"])
    assert proc.returncode == 0, proc.stderr
    (rep,) = json.loads(proc.stdout)["runs"]
    assert rep["reads"] == {".wikicommit/schema/Person.md": {"count": 1, "bytes": [30]}}
