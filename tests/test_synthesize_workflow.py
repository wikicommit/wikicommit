"""wikicommit-synthesize driven by skill_workflow.py (Issue #1195).

The fourth Skill on the engine, and the first one with no item loop: a run writes
at most one view page. The values one step hands to the next (topic, kind,
grounding pages, page path) travel in the run record's lists, and the run ends in
two writes that are easy to lose at the tail — the page with a `derived_from`
naming exactly the pages read, and its `synthesize-step5.5` review record. These
run the real `workflow.yaml` and `workflow_checks.py` in a scratch wiki.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".claude/skills/wikicommit-init/scripts/templates/scripts"
RULES = REPO / ".claude/skills/wikicommit-init/scripts/templates/review-rules.md"
SYNTHESIZE = REPO / ".claude/skills/wikicommit-synthesize"
WORKFLOW = ".claude/skills/wikicommit-synthesize/workflow.yaml"
VIEW = ".wikicommit/view/ja/loop.md"
A = ".wikicommit/entity/ja/Person/a.md"
B = ".wikicommit/entity/ja/Person/b.md"

sys.path.insert(0, str(SCRIPTS))


def _steps(workflow: dict):
    for step in workflow["steps"]:
        yield from step.get("steps", [step])


def _token(name: str) -> str:
    from record_run import read_pass_token

    return read_pass_token(SYNTHESIZE / "references" / name)


def page_text(title: str, lang: str = "ja", body: str = "body\n", **extra) -> str:
    front = {"title": title, "lang": lang, "review_status": "pending", **extra}
    return "---\n" + yaml.safe_dump(front, allow_unicode=True) + "---\n\n" + body


@pytest.fixture
def wiki(tmp_path: Path):
    work = tmp_path / "wiki"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    })
    shutil.copytree(SCRIPTS, work / ".wikicommit" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(SYNTHESIZE, work / ".claude" / "skills" / "wikicommit-synthesize",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(RULES, work / ".wikicommit" / "review-rules.md")
    (work / ".wikicommit" / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n", encoding="utf-8")
    (work / ".gitignore").write_text(".wikicommit/run/\n", encoding="utf-8")

    def git(*args):
        return subprocess.run(["git", *args], cwd=work, env=env, check=True,
                              capture_output=True, text=True)

    def write(rel: str, text: str):
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    write(A, page_text("A", type="schema:Person"))
    write(B, page_text("B", type="schema:Person"))
    git("add", ".")
    git("commit", "-q", "-m", "init")
    return {"dir": work, "env": env, "git": git, "write": write}


def drive(wiki, *args: str) -> tuple[dict, int]:
    result = subprocess.run(
        [sys.executable, ".wikicommit/scripts/skill_workflow.py", *args],
        cwd=wiki["dir"], env=wiki["env"], capture_output=True, text=True, check=False,
    )
    return json.loads(result.stdout), result.returncode


def front(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---\n", 2)[1])


def start(wiki, *extra: str) -> tuple[dict, str]:
    resp, code = drive(wiki, "start", "--workflow", WORKFLOW, "--model", "m", *extra)
    assert code == 0, resp
    return resp, resp["run"]


def head(wiki, rel: str) -> str:
    return wiki["git"]("log", "-1", "--format=%H", "--", rel).stdout.strip()


def done(wiki, run: str, step: str, outcome: str, token: str, *extra: str):
    return drive(wiki, "done", run, "--step", step, "--outcome", outcome,
                 "--token", _token(token), *extra)


def ground(wiki, run: str, *pages: str):
    adds = [a for p in pages for a in ("--add", f"grounding={p}")]
    return done(wiki, run, "ground", "grounded", "ground.md", *adds)


def synthesize(wiki, *, grounding=(A, B), commits=None, result="pass", write=True,
               body="## 概要\n\n本文\n", **extra):
    """Do what references/write-page.md asks, on disk."""
    if write:
        derived = [{"path": p, "source_commit": head(wiki, p) if commits is None else commits[i]}
                   for i, p in enumerate(grounding)]
        wiki["write"](VIEW, page_text("ループ", body=body, generated_at="2026-10-06",
                                      generated_by="m", derived_from=derived, **extra))
    out = subprocess.run(
        [sys.executable, ".wikicommit/scripts/record_review.py", VIEW, "--kind", "ai",
         "--stage", "synthesize-step5.5", "--model", "m", "--result", result],
        cwd=wiki["dir"], env=wiki["env"], capture_output=True, text=True, check=False,
    )
    assert out.returncode == 0, out.stderr


# --- the definition -----------------------------------------------------------


def test_the_synthesize_workflow_points_at_files_that_exist_and_checks_each_token():
    from skill_workflow import load_workflow

    workflow = load_workflow(SYNTHESIZE / "workflow.yaml")
    assert workflow["skill"] == "wikicommit-synthesize"
    tokens = []
    for step in _steps(workflow):
        if step.get("instructions"):
            assert (SYNTHESIZE / step["instructions"]).is_file(), step["id"]
            tokens.append(_token(Path(step["instructions"]).name))
            assert tokens[-1], step["id"]
    assert len(set(tokens)) == len(tokens), "two instruction files share a pass_token"
    for sid in ("ground", "write"):
        step = next(s for s in _steps(workflow) if s["id"] == sid)
        assert step.get("check"), f"{sid} must not be completed on the agent's word alone"


def test_the_skill_md_is_the_workflow_loop():
    text = (SYNTHESIZE / "SKILL.md").read_text(encoding="utf-8")
    assert "skill_workflow.py start --workflow workflow.yaml" in text
    assert "skill_workflow.py next <run>" in text
    assert "--arg=" in text and '--arg "' not in text, (
        "a value starting with -- after a space is read as an option of its own"
    )
    assert "record_run.py start" not in text, "the workflow engine opens the run record now"
    assert "record_run.py end" not in text, "the workflow engine closes the run record now"


# --- preflight and survey -----------------------------------------------------


def test_a_missing_rules_file_halts_before_any_search(wiki):
    (wiki["dir"] / ".wikicommit/review-rules.md").unlink()
    resp, run = start(wiki, "--arg=loop")
    assert resp["step"] is None and resp["state"] == "halted"
    assert "--no-overwrite" in front(wiki["dir"] / run)["halted_reason"]


def test_a_bad_max_grounding_halts(wiki):
    resp, run = start(wiki, "--arg=loop", "--arg=--max-grounding", "--arg=many")
    assert resp["state"] == "halted"
    assert "--max-grounding" in front(wiki["dir"] / run)["halted_reason"]


def test_a_topic_skips_the_survey(wiki):
    resp, _ = start(wiki, "--arg=loop")
    assert resp["step"] == "ground"


def test_no_topic_surveys_and_nothing_chosen_finishes_the_run(wiki):
    resp, run = start(wiki, "--non-interactive")
    assert resp["step"] == "survey"
    assert "never pick one" in resp["when_nobody_can_answer"]
    resp, code = done(wiki, run, "survey", "chosen", "survey.md")
    assert code == 1 and "topic" in resp["reason"], "chosen needs a topic"
    resp, code = done(wiki, run, "survey", "none", "survey.md")
    assert code == 0 and resp["finished"] is True
    assert front(wiki["dir"] / run)["ended_at"]


def test_a_chosen_angle_carries_its_topic_kind_and_cap(wiki):
    _, run = start(wiki)
    resp, code = done(wiki, run, "survey", "chosen", "survey.md",
                      "--add", "topic=ループ", "--add", "kind=ranking")
    assert code == 1 and "kind" in resp["reason"], "only the six kinds"
    resp, code = done(wiki, run, "survey", "chosen", "survey.md", "--add", "topic=ループ",
                      "--add", "kind=comparison", "--add", "max_grounding=1")
    assert code == 0 and resp["step"] == "ground"
    lists = front(wiki["dir"] / run)["workflow"]["lists"]
    assert lists["topic"] == ["ループ"] and lists["kind"] == ["comparison"]
    resp, code = ground(wiki, run, A, B)
    assert code == 1 and "cap of 1" in resp["reason"], "the cap named at the survey holds"


# --- grounding ----------------------------------------------------------------


def test_grounding_must_be_originals_in_primary_lang(wiki):
    wiki["write"](".wikicommit/entity/en/Person/a.md",
                  page_text("A", lang="en", translated_from=A))
    wiki["write"](".wikicommit/entity/ja/Person/syn.md",
                  page_text("S", derived_from=[{"path": A, "source_commit": ""}]))
    wiki["write"](".wikicommit/view/ja/other.md", page_text("O"))
    _, run = start(wiki, "--arg=loop")

    resp, code = done(wiki, run, "ground", "grounded", "ground.md")
    assert code == 1 and "no grounding page" in resp["reason"]
    for bad, why in ((".wikicommit/entity/en/Person/a.md", "not a page under"),
                     (".wikicommit/entity/ja/Person/syn.md", "itself a synthesis"),
                     (".wikicommit/view/ja/other.md", "not a page under"),
                     (".wikicommit/entity/ja/Person/gone.md", "does not exist")):
        resp, code = ground(wiki, run, A, bad)
        assert code == 1 and why in resp["reason"], (bad, resp)
    assert "grounding" not in front(wiki["dir"] / run)["workflow"].get("lists", {}), (
        "a refused step's additions are rolled back"
    )
    resp, code = ground(wiki, run, A, B)
    assert code == 0 and resp["step"] == "write"


def test_no_grounding_page_finishes_the_run(wiki):
    _, run = start(wiki, "--arg=loop")
    resp, code = done(wiki, run, "ground", "nothing", "ground.md")
    assert code == 0 and resp["finished"] is True
    assert front(wiki["dir"] / run)["halted_reason"] == ""


# --- the page -----------------------------------------------------------------


def test_the_page_is_not_complete_until_derived_from_and_review_record_are_right(wiki):
    _, run = start(wiki, "--arg=loop")
    ground(wiki, run, A, B)
    add = ("--add", f"page={VIEW}")

    resp, code = done(wiki, run, "write", "written", "write-page.md", *add)
    assert code == 1 and "review record" in resp["reason"], "nothing was done yet"

    synthesize(wiki, grounding=(A,))
    resp, code = done(wiki, run, "write", "written", "write-page.md", *add)
    assert code == 1 and "missing: " + B in resp["reason"]

    synthesize(wiki, commits=["", head(wiki, B)])
    resp, code = done(wiki, run, "write", "written", "write-page.md", *add)
    assert code == 1 and "source_commit" in resp["reason"]

    synthesize(wiki, type="schema:Thing", body="# ループ\n\n本文\n")
    resp, code = done(wiki, run, "write", "written", "write-page.md", *add)
    assert code == 1 and "no type:" in resp["reason"] and "H1" in resp["reason"]

    synthesize(wiki, kind="comparison")
    resp, code = done(wiki, run, "write", "written", "write-page.md", *add)
    assert code == 0 and resp["step"] == "report", resp
    assert (wiki["dir"] / ".wikicommit/view/ja/index.md").exists(), (
        "rebuild-index ran before the report"
    )
    touched = front(wiki["dir"] / run)["workflow"]["touched"]
    assert VIEW in touched and ".wikicommit/view/ja/index.md" in touched
    assert any(p.startswith(".wikicommit/review/view/ja/loop/") for p in touched)


def test_a_page_outside_the_view_tree_is_refused(wiki):
    _, run = start(wiki, "--arg=loop")
    ground(wiki, run, A)
    resp, code = done(wiki, run, "write", "written", "write-page.md",
                      "--add", "page=.wikicommit/view/en/loop.md")
    assert code == 1 and ".wikicommit/view/ja/<slug>.md" in resp["reason"]


def test_a_discarded_synthesis_writes_nothing_skips_the_index_and_is_reported(wiki):
    _, run = start(wiki, "--arg=loop")
    ground(wiki, run, A)
    add = ("--add", f"page={VIEW}")
    resp, code = done(wiki, run, "write", "discarded", "write-page.md", *add)
    assert code == 1 and "result: discarded" in resp["reason"]
    synthesize(wiki, result="discarded", write=False)
    resp, code = done(wiki, run, "write", "discarded", "write-page.md", *add)
    assert code == 0 and resp["step"] == "report"
    assert not (wiki["dir"] / ".wikicommit/view/ja/index.md").exists()
    log = front(wiki["dir"] / run)["workflow"]["log"]
    assert {"step": "rebuild-index", "outcome": "skipped"}.items() <= next(
        e for e in log if e["step"] == "rebuild-index").items()

    resp, code = done(wiki, run, "report", "reported", "completion-report.md",
                      "--count", "synthesized=0", "--count", "failed=1")
    assert code == 0 and resp["finished"] is True
    assert front(wiki["dir"] / run)["outcome"] == {"synthesized": 0, "failed": 1}


def test_declining_to_overwrite_finishes_the_run_untouched(wiki):
    wiki["write"](VIEW, page_text("old"))
    wiki["git"]("add", ".")
    wiki["git"]("commit", "-q", "-m", "view")
    # Written before the run, not in the same second it started (the check
    # compares at whole-second resolution and counts that second as the run's).
    os.utime(wiki["dir"] / VIEW, (1_000_000_000, 1_000_000_000))
    resp, run = start(wiki, "--arg=loop", "--non-interactive")
    ground(wiki, run, A)
    resp, _ = drive(wiki, "next", run)
    assert "declined" in resp["when_nobody_can_answer"]
    resp, code = done(wiki, run, "write", "declined", "write-page.md", "--add", f"page={VIEW}")
    assert code == 0 and resp["finished"] is True
    assert front(wiki["dir"] / VIEW)["title"] == "old"


def test_a_stopped_run_resumes_from_the_step_it_stopped_at(wiki):
    """Interrupted between steps: each resumption is a fresh `next` with nothing
    but the run path, and what earlier steps chose is still in the record."""
    _, run = start(wiki, "--arg=ループ", "--arg=--max-grounding", "--arg=2")
    resp, code = ground(wiki, run, A, B)
    assert code == 0 and resp["step"] == "write"

    # A new session: only the run path survives.
    resp, _ = drive(wiki, "next", run)
    assert resp["step"] == "write"
    assert front(wiki["dir"] / run)["workflow"]["lists"]["grounding"] == [A, B]
    resp, code = ground(wiki, run, A)
    assert code == 1 and resp["accepted"] is False, "a finished step cannot be done again"

    synthesize(wiki)
    resp, code = done(wiki, run, "write", "written", "write-page.md", "--add", f"page={VIEW}")
    assert code == 0 and resp["step"] == "report"

    resp, _ = drive(wiki, "next", run)
    assert resp["step"] == "report"
    resp, code = done(wiki, run, "report", "reported", "completion-report.md",
                      "--page", VIEW, "--count", "synthesized=1", "--count", "failed=0")
    assert code == 0 and resp["finished"] is True
    record = front(wiki["dir"] / run)
    assert record["skill"] == "wikicommit-synthesize"
    assert record["args"] == ["ループ", "--max-grounding", "2"]
    assert record["ended_at"] and record["halted_reason"] == ""
    assert record["pages"] == [VIEW]


def test_a_rules_version_mismatch_halts_the_run(wiki):
    _, run = start(wiki, "--arg=loop")
    ground(wiki, run, A)
    resp, code = done(wiki, run, "write", "halted", "write-page.md",
                      "--reason", "rules_version mismatch")
    assert code == 0 and resp["state"] == "halted"
    assert front(wiki["dir"] / run)["halted_reason"] == "write: rules_version mismatch"


def test_a_dangling_or_unknown_option_halts(wiki):
    resp, run = start(wiki, "--arg=loop", "--arg=--max-grounding")
    assert resp["state"] == "halted"
    assert "--max-grounding" in front(wiki["dir"] / run)["halted_reason"]
    resp, run = start(wiki, "--arg=loop", "--arg=--max-groundng=5")
    assert resp["state"] == "halted"
    assert "--max-groundng=5" in front(wiki["dir"] / run)["halted_reason"]


def test_an_existing_page_left_unwritten_is_not_written(wiki):
    """A pass record from this run on a page already on disk from an earlier run
    does not make `written` true: the page itself has to be written in this run."""
    _, run = start(wiki, "--arg=loop")
    ground(wiki, run, A, B)
    synthesize(wiki)
    os.utime(wiki["dir"] / VIEW, (1_000_000_000, 1_000_000_000))
    resp, code = done(wiki, run, "write", "written", "write-page.md", "--add", f"page={VIEW}")
    assert code == 1 and "not written during this run" in resp["reason"]


def test_a_page_changed_after_its_pass_record_is_refused(wiki):
    _, run = start(wiki, "--arg=loop")
    ground(wiki, run, A, B)
    synthesize(wiki)
    later = time.time() + 120
    os.utime(wiki["dir"] / VIEW, (later, later))
    resp, code = done(wiki, run, "write", "written", "write-page.md", "--add", f"page={VIEW}")
    assert code == 1 and "changed after its newest" in resp["reason"]


@pytest.mark.parametrize("outcome", ["written", "discarded", "declined"])
def test_an_unreadable_started_at_fails_the_page_check(wiki, outcome):
    """Without the run's start an earlier run's record or write would pass for
    this one, so every outcome fails instead (the same direction as written_since)."""
    _, run = start(wiki, "--arg=loop")
    ground(wiki, run, A, B)
    synthesize(wiki, result="discarded" if outcome == "discarded" else "pass",
               write=outcome != "discarded")
    record = wiki["dir"] / run
    text = record.read_text(encoding="utf-8")
    started = next(line for line in text.splitlines() if line.startswith("started_at:"))
    record.write_text(text.replace(started, "started_at: not-a-time", 1), encoding="utf-8")
    resp, code = done(wiki, run, "write", outcome, "write-page.md", "--add", f"page={VIEW}")
    assert code == 1 and "started_at" in resp["reason"], resp
