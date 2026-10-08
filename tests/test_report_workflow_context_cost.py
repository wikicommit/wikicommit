"""Tests for tools/report_workflow_context_cost.py (Issue #1267)."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "tools" / "report_workflow_context_cost.py"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)] + args, capture_output=True,
                          text=True, cwd=cwd, check=False)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


WORKFLOW = """\
skill: demo
steps:
  - id: preflight
    type: script
    run: [python, x.py]
  - id: register
    type: agent
    when: [python, y.py]
    instructions: references/register.md
  - id: cap
    type: human
    ask: "ask?"
    choices: {a: "", b: ""}
  - id: per-source
    for_each: sources
    steps:
      - id: pass1
        type: agent
        instructions: references/pass1.md
        also_read: references/routing.md
      - id: pass2
        type: agent
        instructions: references/pass2.md
  - id: report
    type: agent
    instructions: references/report.md
"""


# what the engine hands over for the `cap` human step: its ask and its choices
CAP_INLINE = len("ask?") + len(json.dumps({"a": "", "b": ""}))


def make_tree(root: Path) -> Path:
    skills = root / ".claude" / "skills"
    demo = skills / "demo"
    write(demo / "workflow.yaml", WORKFLOW)
    write(demo / "SKILL.md", "s" * 100)
    write(demo / "references" / "register.md", "r" * 10)
    write(demo / "references" / "pass1.md",
          "Read `.wikicommit/rules.md` and follow it.\n"
          "This is used by Pass 2 (`references/pass2.md`).\n"
          "Read `.wikicommit/schema/<Type>.md` for the type.\n")
    write(demo / "references" / "pass2.md", "p" * 40)
    write(demo / "references" / "routing.md", "t" * 20)
    write(demo / "references" / "report.md", "e" * 30)
    write(skills / "wikicommit-init" / "scripts" / "templates" / "rules.md", "u" * 50)
    return skills


def report(root: Path) -> dict:
    result = run(["--json"], cwd=root)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    (skill,) = [s for s in data["skills"] if s["skill"] == "demo"]
    return skill


def test_one_row_per_step_with_loop_and_condition(tmp_path):
    make_tree(tmp_path)
    skill = report(tmp_path)
    rows = {r["id"]: r for r in skill["steps"]}
    assert list(rows) == ["preflight", "register", "cap", "pass1", "pass2", "report"]
    assert rows["register"]["conditional"] is True
    assert rows["pass1"]["loop"] == "sources"
    assert rows["preflight"]["bytes"] == 0
    assert rows["cap"]["bytes"] == CAP_INLINE


def test_read_references_are_followed_and_mentions_are_not(tmp_path):
    make_tree(tmp_path)
    skill = report(tmp_path)
    pass1 = next(r for r in skill["steps"] if r["id"] == "pass1")
    files = {f["file"]: f["bytes"] for f in pass1["files"]}
    pass1_size = (tmp_path / ".claude/skills/demo/references/pass1.md").stat().st_size
    assert files == {"references/pass1.md": pass1_size, ".wikicommit/rules.md": 50,
                     "references/routing.md": 20}
    assert not any(f.endswith("pass2.md") for f in files)
    assert ".wikicommit/schema/<Type>.md" in skill["unresolved"]


def test_totals(tmp_path):
    make_tree(tmp_path)
    skill = report(tmp_path)
    pass1_size = (tmp_path / ".claude/skills/demo/references/pass1.md").stat().st_size
    # SKILL.md + cap's ask and choices + report (register is conditional)
    assert skill["always_bytes"] == 100 + CAP_INLINE + 30
    assert skill["conditional_bytes"] == 10
    assert skill["per_item_bytes"] == {"sources": pass1_size + 50 + 20 + 40}


def test_every_human_step_counts_its_own_ask(tmp_path):
    skills = make_tree(tmp_path)
    workflow = skills / "demo" / "workflow.yaml"
    workflow.write_text(WORKFLOW.replace(
        "  - id: report\n",
        "  - id: confirm\n    type: human\n    ask: \"another question\"\n"
        "    choices: {a: \"\", b: \"\"}\n  - id: report\n"), encoding="utf-8")
    skill = report(tmp_path)
    confirm = len("another question") + len(json.dumps({"a": "", "b": ""}))
    assert skill["always_bytes"] == 100 + CAP_INLINE + confirm + 30


def test_a_step_file_is_not_listed_as_only_mentioned(tmp_path):
    make_tree(tmp_path)
    skill = report(tmp_path)
    # pass1.md names pass2.md in passing, but pass2 hands it over as instructions
    assert "references/pass2.md" not in skill["mentioned"]


def test_text_output_states_the_assumption(tmp_path):
    make_tree(tmp_path)
    result = run(["--bytes-per-token", "3"], cwd=tmp_path)
    assert result.returncode == 0
    assert "1 token ~ 3 bytes" in result.stdout
    assert "TOTAL per item of `sources`" in result.stdout


def test_unknown_skill_is_a_usage_error(tmp_path):
    make_tree(tmp_path)
    assert run(["--skill", "nope"], cwd=tmp_path).returncode == 2


def test_runs_on_this_repository():
    result = run(["--json"], cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    names = {s["skill"] for s in json.loads(result.stdout)["skills"]}
    assert "wikicommit-generate" in names
