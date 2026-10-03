"""driver.py — the order of a Skill's steps held by a script (Issue #1085).

Most of these run a small generic workflow, because the engine's claims are about
the engine: order is enforced, completion is decided by a check on disk, the log is
the state (so a fresh process resumes where the last one stopped), and a run that
is still open blocks a merge that carries its files while every other change
passes. The last group runs `wikicommit-generate`'s real workflow, which is where
those claims have to hold in practice.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".claude/skills/wikicommit-init/scripts/templates/scripts"
DRIVER = SCRIPTS / "driver.py"
GENERATE = REPO / ".claude/skills/wikicommit-generate"

sys.path.insert(0, str(SCRIPTS))


def drive(cwd: Path, *args: str, stdin: str = "") -> tuple[dict, int]:
    result = subprocess.run(
        [sys.executable, str(DRIVER), *args],
        cwd=cwd, capture_output=True, text=True, input=stdin, check=False,
    )
    out = result.stdout.strip()
    return (json.loads(out) if out else {}), result.returncode


def front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---\n", 2)[1])


# --- a small generic workflow -------------------------------------------------

HELPER = '''
import sys
from pathlib import Path
cmd = sys.argv[1]
if cmd == "items":
    for name in ("a", "b"):
        print(f"ITEM: {name}")
elif cmd == "none":
    pass
elif cmd == "check":
    item, outcome = sys.argv[2], sys.argv[3]
    marker = Path(f"work-{item}")
    if outcome == "wrote" and not marker.is_file():
        print(f"work-{item} was not written")
        sys.exit(1)
    print(f"TOUCHED: work-{item}")
elif cmd == "fail":
    print("preflight says no")
    sys.exit(1)
'''

WORKFLOW = {
    "skill": "wikicommit-generate",
    "record_sources": "things",
    "steps": [
        {"id": "list", "type": "script",
         "run": ["{python}", "{skill_dir}/helper.py", "items"], "produces": "things"},
        {"id": "confirm", "type": "human", "ask": "go?",
         "choices": {"yes": "", "no": ""}, "non_interactive": "yes"},
        {"id": "each", "for_each": "things", "steps": [
            {"id": "work", "type": "agent", "instructions": "work.md", "stamp": True,
             "outcomes": {"wrote": "", "skip": "", "halted": ""},
             "ends_item_on": ["skip"], "halts_on": ["halted"],
             "check": ["{python}", "{skill_dir}/helper.py", "check", "{item}", "{outcome}"]},
            {"id": "after", "type": "agent", "outcomes": {"ok": ""}},
        ]},
        {"id": "wrap", "type": "agent", "outcomes": {"reported": ""}},
    ],
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "helper.py").write_text(HELPER, encoding="utf-8")
    (skill / "work.md").write_text('---\npass_token: "tok123"\n---\n# work\n', encoding="utf-8")
    (skill / "workflow.yaml").write_text(yaml.safe_dump(WORKFLOW), encoding="utf-8")
    return tmp_path


def start(repo: Path, *extra: str) -> tuple[dict, str]:
    resp, code = drive(repo, "start", "--workflow", "skill/workflow.yaml", "--model", "m", *extra)
    assert code == 0, resp
    return resp, resp["run"]


def work(repo: Path, run: str, item: str, outcome: str = "wrote", token: str = "tok123"):
    if outcome == "wrote":
        (repo / f"work-{item}").write_text("x", encoding="utf-8")
    return drive(repo, "done", run, "--step", "work", "--item", item,
                 "--outcome", outcome, "--token", token)


def test_start_runs_scripts_and_stops_at_the_first_step_needing_someone(repo):
    resp, run = start(repo)
    assert resp["step"] == "confirm" and resp["type"] == "human"
    record = front(repo / run)
    assert record["driver"]["lists"]["things"] == ["a", "b"]
    assert record["ended_at"] == ""


def test_a_fresh_process_resumes_where_the_last_one_stopped(repo):
    """What compaction or a new session looks like to the driver: nothing but the
    run path. The log on disk is the whole state."""
    _, run = start(repo)
    drive(repo, "done", run, "--step", "confirm", "--answer", "yes")
    work(repo, run, "a")
    resp, code = drive(repo, "next", run)
    assert code == 0
    assert (resp["step"], resp["item"]) == ("after", "a")
    again, _ = drive(repo, "next", run)
    assert (again["step"], again["item"]) == ("after", "a"), "next must not advance"


def test_a_step_other_than_the_current_one_is_refused(repo):
    _, run = start(repo)
    resp, code = drive(repo, "done", run, "--step", "wrap", "--outcome", "reported")
    assert code == 1 and resp["accepted"] is False
    assert resp["step"] == "confirm", "the refusal hands back the current step"


def test_a_human_step_needs_one_of_its_choices(repo):
    _, run = start(repo)
    resp, code = drive(repo, "done", run, "--step", "confirm", "--answer", "maybe")
    assert code == 1 and "yes" in resp["reason"]
    resp, code = drive(repo, "done", run, "--step", "confirm", "--answer", "yes")
    assert code == 0 and resp["step"] == "work"


def test_a_non_interactive_run_takes_the_defined_default(repo):
    resp, run = start(repo, "--non-interactive")
    assert resp["step"] == "work", "nobody to ask, so the human step answered itself"
    log = front(repo / run)["driver"]["log"]
    confirm = next(e for e in log if e["step"] == "confirm")
    assert confirm["answer"] == "yes" and confirm["answered_by"] == "non-interactive default"


def test_the_token_is_checked_against_the_file_the_driver_opens(repo):
    resp, run = start(repo, "--non-interactive")
    missing, code = drive(repo, "done", run, "--step", "work", "--item", "a", "--outcome", "wrote")
    assert code == 1 and "pass_token" in missing["reason"]
    wrong, code = work(repo, run, "a", token="nope")
    assert code == 1 and "does not match" in wrong["reason"]
    ok, code = work(repo, run, "a")
    assert code == 0 and ok["accepted"] is True
    stamps = front(repo / run)["passes"]
    assert stamps == [{**stamps[0], "pass": "work", "token": "ok", "source": "a"}]


def test_completion_is_decided_by_the_check_not_the_report(repo):
    _, run = start(repo, "--non-interactive")
    resp, code = drive(repo, "done", run, "--step", "work", "--item", "a",
                       "--outcome", "wrote", "--token", "tok123")
    assert code == 1 and "work-a was not written" in resp["reason"]
    assert resp["step"] == "work", "a failed check leaves the step current"
    assert front(repo / run)["passes"] == [], "an unaccepted step is not stamped"


def test_repeated_check_failures_tell_the_agent_to_stop(repo):
    _, run = start(repo, "--non-interactive")
    for _ in range(3):
        resp, _ = drive(repo, "done", run, "--step", "work", "--item", "a",
                        "--outcome", "wrote", "--token", "tok123")
    assert resp.get("blocked") is True


def test_an_item_can_end_early_and_the_next_item_follows(repo):
    _, run = start(repo, "--non-interactive")
    resp, code = work(repo, run, "a", outcome="skip")
    assert code == 0
    assert (resp["step"], resp["item"]) == ("work", "b"), "`after` is skipped for a"


def test_a_halt_closes_the_run_as_not_finished(repo):
    _, run = start(repo, "--non-interactive")
    no_reason, code = drive(repo, "done", run, "--step", "work", "--item", "a",
                            "--outcome", "halted", "--token", "tok123")
    assert code == 1 and "--reason" in no_reason["reason"]
    resp, code = drive(repo, "done", run, "--step", "work", "--item", "a",
                       "--outcome", "halted", "--token", "tok123", "--reason", "no network")
    assert code == 0 and resp["step"] is None and resp["state"] == "halted"
    record = front(repo / run)
    assert record["ended_at"] and record["halted_reason"] == "work: no network"


def finish(repo: Path, run: str) -> dict:
    for item in ("a", "b"):
        work(repo, run, item)
        drive(repo, "done", run, "--step", "after", "--item", item, "--outcome", "ok")
    resp, code = drive(repo, "done", run, "--step", "wrap", "--outcome", "reported",
                       "--count", "generated=2", "--page", "work-a")
    assert code == 0
    return resp


def test_the_last_step_closes_the_record_in_the_shape_check_run_records_reads(repo):
    _, run = start(repo, "--non-interactive")
    resp = finish(repo, run)
    assert resp["step"] is None and resp["finished"] is True
    record = front(repo / run)
    assert record["ended_at"] and record["halted_reason"] == ""
    assert record["sources"] == ["a", "b"]
    assert record["outcome"] == {"generated": 2}
    assert record["pages"] == ["work-a"]
    report = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_run_records.py")],
        cwd=repo, capture_output=True, text=True, check=False,
    ).stdout
    assert "INCOMPLETE_RUN" not in report


# --- the exit: /wikicommit-merge ---------------------------------------------


def test_merge_is_refused_while_an_open_run_touched_a_changed_file(repo):
    _, run = start(repo, "--non-interactive")
    work(repo, run, "a")
    resp, code = drive(repo, "check-merge")
    assert code == 1 and resp["blocked"] is True
    blocking = resp["open_runs"][0]
    assert blocking["files"] == ["work-a"]
    assert (blocking["step"], blocking["item"]) == ("after", "a")


def test_changes_no_run_touched_pass(repo):
    """fix, remove, review and hand edits use no driver; they must still merge."""
    _, run = start(repo, "--non-interactive")
    work(repo, run, "a")
    resp, code = drive(repo, "check-merge", "hand-edited.md")
    assert code == 0 and resp["blocked"] is False


@pytest.mark.parametrize("ending", ["finished", "halted", "abandoned"])
def test_a_run_that_ended_does_not_block(repo, ending):
    _, run = start(repo, "--non-interactive")
    if ending == "finished":
        finish(repo, run)
    elif ending == "halted":
        work(repo, run, "a")
        drive(repo, "done", run, "--step", "after", "--item", "a", "--outcome", "ok")
        drive(repo, "done", run, "--step", "work", "--item", "b", "--outcome", "halted",
              "--token", "tok123", "--reason", "stop")
    else:
        work(repo, run, "a")
        resp, code = drive(repo, "abandon", run, "--reason", "session gone")
        assert code == 0 and resp["left_behind"] == ["work-a"], (
            "abandoning names what the run left rather than passing or deleting it"
        )
    resp, code = drive(repo, "check-merge")
    assert code == 0 and resp["blocked"] is False


def test_the_stop_hook_blocks_once_while_a_run_is_open(repo):
    _, run = start(repo, "--non-interactive")
    resp, code = drive(repo, "status", "--stop-hook", stdin="{}")
    assert code == 0 and resp["decision"] == "block" and run in resp["reason"]
    again, _ = drive(repo, "status", "--stop-hook", stdin='{"stop_hook_active": true}')
    assert again == {}, "a second stop in the same attempt is let through"
    finish(repo, run)
    after, _ = drive(repo, "status", "--stop-hook", stdin="{}")
    assert after == {}


def test_the_engine_carries_no_wikicommit_knowledge():
    """Paths, status values and pass names belong to each Skill's workflow file and
    check scripts; the engine has to stay usable by a Skill that shares none."""
    code = "\n".join(
        line for line in DRIVER.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    body = code.split('"""', 2)[2]  # past the module docstring
    for word in (".wikicommit/", "pass1", "pass4", "generated_pages", "status: ",
                 "management file", "wikicommit-generate"):
        assert word not in body, word


# --- wikicommit-generate's own workflow --------------------------------------


def _steps(workflow: dict):
    for step in workflow["steps"]:
        yield from step.get("steps", [step])


@pytest.mark.parametrize("name", ["workflow.yaml", "workflow-regenerate.yaml"])
def test_the_generate_workflows_point_at_files_that_exist(name):
    from driver import load_workflow

    workflow = load_workflow(GENERATE / name)
    for step in _steps(workflow):
        for key in ("instructions", "also_read"):
            if step.get(key):
                assert (GENERATE / step[key]).is_file(), f"{name}: {step['id']}: {step[key]}"


def test_every_generate_pass_file_is_token_checked():
    """A pass file without a pass_token is completed on the agent's word alone."""
    from record_run import read_pass_token

    workflow = yaml.safe_load((GENERATE / "workflow.yaml").read_text(encoding="utf-8"))
    for step in _steps(workflow):
        if step.get("stamp") or step["id"] == "register":
            assert read_pass_token(GENERATE / step["instructions"]), step["id"]


def test_generate_human_steps_have_the_non_interactive_answer_the_skill_documents():
    """Issue #910's rule, held by the definition: with nobody to ask, the batch cap
    takes the first five — never everything."""
    for name in ("workflow.yaml", "workflow-regenerate.yaml"):
        workflow = yaml.safe_load((GENERATE / name).read_text(encoding="utf-8"))
        humans = [s for s in _steps(workflow) if s.get("type") == "human"]
        assert humans, name
        for step in humans:
            assert step["non_interactive"] == "first-five", name


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shutil.copytree(SCRIPTS, tmp_path / ".wikicommit" / "scripts")
    shutil.copytree(GENERATE, tmp_path / ".claude" / "skills" / "wikicommit-generate",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / ".wikicommit" / "config.yml").write_text("theme: ''\n", encoding="utf-8")
    (tmp_path / ".wikicommit" / "review-rules.md").write_text("---\n---\n", encoding="utf-8")
    source = tmp_path / ".wikicommit" / "source" / "path" / "raw" / "a.txt.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nsource:\n  type: path\n  path: raw/a.txt\nstatus: pending\n---\n",
        encoding="utf-8",
    )
    return tmp_path


def gen(wiki: Path, *args: str):
    return subprocess.run(
        [sys.executable, ".wikicommit/scripts/driver.py", *args],
        cwd=wiki, capture_output=True, text=True, check=False,
    )


WORKFLOW_PATH = ".claude/skills/wikicommit-generate/workflow.yaml"
SOURCE = ".wikicommit/source/path/raw/a.txt.md"


def test_generate_hands_out_the_queued_source(wiki):
    result = gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m")
    resp = json.loads(result.stdout)
    assert (resp["step"], resp["item"]) == ("pass1-extract", SOURCE)
    assert resp["instructions"] == "references/pass1-extract.md"


def test_generate_halts_at_the_start_without_review_rules(wiki):
    (wiki / ".wikicommit" / "review-rules.md").unlink()
    resp = json.loads(gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m").stdout)
    assert resp["step"] is None and resp["state"] == "halted"
    assert "--no-overwrite" in resp["halted_reason"]


def test_generate_with_nothing_queued_finishes_as_a_no_op(wiki):
    (wiki / SOURCE).unlink()
    resp = json.loads(gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m").stdout)
    assert resp["finished"] is True
    assert resp["finished_because"] == "No management files to process"


def test_pass4_refuses_a_write_back_left_undone(wiki):
    """The check that used to be a clean-up after the run: a page listed in
    generated_pages with no review record is refused at the step."""
    run = json.loads(gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m",
                         "--non-interactive").stdout)["run"]
    tokens = {"pass1-extract": "a3f1c07d", "pass2b-type": "5e9b2d84",
              "pass2c-entities": "c41a7f6b", "pass3-generate": "9d8e35a2"}
    source = wiki / SOURCE
    source.write_text(
        "---\nsource:\n  type: path\n  path: raw/a.txt\nstatus: pending\n"
        "extracted_tokens: 10\n---\n\n## Summary\n\nx\n", encoding="utf-8",
    )
    outcomes = {"pass1-extract": "extracted", "pass2b-type": "ok",
                "pass2c-entities": "ok", "pass3-generate": "ok"}
    for step, token in tokens.items():
        result = gen(wiki, "done", run, "--step", step, "--item", SOURCE,
                     "--outcome", outcomes[step], "--token", token)
        assert result.returncode == 0, result.stdout

    page = wiki / ".wikicommit/entity/en/Person/x.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\ntitle: x\n---\n", encoding="utf-8")
    source.write_text(
        "---\nsource:\n  type: path\n  path: raw/a.txt\nstatus: generated\n"
        "extracted_tokens: 10\nlast_generated_at: '2026-09-29'\n"
        "generated_pages: [.wikicommit/entity/en/Person/x.md]\n---\n\n## Summary\n\nx\n",
        encoding="utf-8",
    )
    refused = json.loads(gen(wiki, "done", run, "--step", "pass4-review", "--item", SOURCE,
                             "--outcome", "ok", "--token", "7b06f4ce").stdout)
    assert refused["accepted"] is False and "no review record" in refused["reason"]

    record = wiki / ".wikicommit/review/entity/en/Person/x/20260929-000000-ai.md"
    record.parent.mkdir(parents=True)
    record.write_text("---\n---\n", encoding="utf-8")
    accepted = json.loads(gen(wiki, "done", run, "--step", "pass4-review", "--item", SOURCE,
                              "--outcome", "ok", "--token", "7b06f4ce").stdout)
    assert accepted["accepted"] is True and accepted["step"] == "completion"
    touched = front(wiki / run)["driver"]["touched"]
    assert ".wikicommit/entity/en/Person/x.md" in touched


def test_pass4_accepts_an_all_excluded_source(wiki):
    """`excluded` writes no last_generated_at and no pages; the check must not demand them."""
    source = wiki / SOURCE
    source.write_text(
        "---\nsource:\n  type: path\n  path: raw/a.txt\nstatus: excluded\n---\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(GENERATE / "scripts" / "workflow_checks.py"),
         "check-pass4", "--item", SOURCE],
        cwd=wiki, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout


def _check_pass2c(wiki, outcome: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GENERATE / "scripts" / "workflow_checks.py"),
         "check-pass2c", "--item", SOURCE, "--outcome", outcome],
        cwd=wiki, capture_output=True, text=True, check=False,
    )


def test_pass2c_deferred_needs_a_reason_and_a_queued_status(wiki):
    """Issue #1068: an update page's existing source that cannot be fetched defers
    the source before Pass 3. The deferral has to say why, and has to leave the
    source where the queue collects it — a forced recheck arrives as `generated`
    with a new hash already written, and leaving it there loses the update."""
    source = wiki / SOURCE
    source.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/a\nstatus: generated\n---\n\n"
        "## Summary\n\nx\n", encoding="utf-8",
    )
    assert "Deferred Reason" in _check_pass2c(wiki, "deferred").stdout

    source.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/a\nstatus: generated\n---\n\n"
        "## Summary\n\nx\n\n## Deferred Reason\n\nERROR: 403\n", encoding="utf-8",
    )
    refused = _check_pass2c(wiki, "deferred")
    assert refused.returncode == 1 and "status: pending" in refused.stdout

    source.write_text(source.read_text(encoding="utf-8").replace("status: generated", "status: pending"),
                      encoding="utf-8")
    assert _check_pass2c(wiki, "deferred").returncode == 0
    assert _check_pass2c(wiki, "ok").returncode == 0


@pytest.mark.parametrize("outcome", ["deferred", "halted"])
def test_pass2c_partial_with_no_failed_pages_is_not_queued(wiki, outcome):
    """A forced recheck also arrives as `partial` with an empty `failed_pages`,
    which the queue does not collect — it has to be set back to pending too."""
    source = wiki / SOURCE
    source.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/a\nstatus: partial\n"
        "failed_pages: []\n---\n\n## Summary\n\nx\n\n## Deferred Reason\n\nERROR: 403\n",
        encoding="utf-8",
    )
    refused = _check_pass2c(wiki, outcome)
    assert refused.returncode == 1 and "status: pending" in refused.stdout


def test_pass2c_halted_is_held_to_the_deferral_conditions(wiki):
    """A second NETWORK_UNAVAILABLE in a row defers this source and then stops
    the run; the deferral it writes is checked like any other."""
    source = wiki / SOURCE
    source.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/a\nstatus: generated\n---\n\n"
        "## Summary\n\nx\n", encoding="utf-8",
    )
    assert "Deferred Reason" in _check_pass2c(wiki, "halted").stdout

    source.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/a\nstatus: pending\n---\n\n"
        "## Summary\n\nx\n\n## Deferred Reason\n\nNETWORK_UNAVAILABLE: x\n", encoding="utf-8",
    )
    assert _check_pass2c(wiki, "halted").returncode == 0


def test_pass2c_halted_stops_the_run(wiki):
    run = json.loads(gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m",
                         "--non-interactive").stdout)["run"]
    source = wiki / SOURCE
    source.write_text(
        "---\nsource:\n  type: path\n  path: raw/a.txt\nstatus: pending\n"
        "extracted_tokens: 10\n---\n\n## Summary\n\nx\n\n## Deferred Reason\n\nNETWORK_UNAVAILABLE: x\n",
        encoding="utf-8",
    )
    for step, token, outcome in (("pass1-extract", "a3f1c07d", "extracted"),
                                 ("pass2b-type", "5e9b2d84", "ok")):
        assert gen(wiki, "done", run, "--step", step, "--item", SOURCE,
                   "--outcome", outcome, "--token", token).returncode == 0
    no_reason = gen(wiki, "done", run, "--step", "pass2c-entities", "--item", SOURCE,
                    "--outcome", "halted", "--token", "c41a7f6b")
    assert no_reason.returncode == 1
    # The driver itself runs the check on `halted` (check_on_halt): a deferral
    # left out of the queue is refused, not just when the check is called directly.
    text = source.read_text(encoding="utf-8")
    source.write_text(text.replace("status: pending", "status: generated"), encoding="utf-8")
    unqueued = gen(wiki, "done", run, "--step", "pass2c-entities", "--item", SOURCE,
                   "--outcome", "halted", "--token", "c41a7f6b",
                   "--reason", "network unavailable")
    assert unqueued.returncode == 1 and "status: pending" in unqueued.stdout, unqueued.stdout
    source.write_text(text, encoding="utf-8")
    result = json.loads(gen(wiki, "done", run, "--step", "pass2c-entities", "--item", SOURCE,
                            "--outcome", "halted", "--token", "c41a7f6b",
                            "--reason", "network unavailable").stdout)
    assert result["step"] is None and "network unavailable" in (result.get("halted_reason") or ""), result


def test_pass2c_deferred_skips_the_rest_of_the_source(wiki):
    run = json.loads(gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m",
                         "--non-interactive").stdout)["run"]
    source = wiki / SOURCE
    source.write_text(
        "---\nsource:\n  type: path\n  path: raw/a.txt\nstatus: pending\n"
        "extracted_tokens: 10\n---\n\n## Summary\n\nx\n\n## Deferred Reason\n\nERROR: 403\n",
        encoding="utf-8",
    )
    for step, token, outcome in (("pass1-extract", "a3f1c07d", "extracted"),
                                 ("pass2b-type", "5e9b2d84", "ok")):
        assert gen(wiki, "done", run, "--step", step, "--item", SOURCE,
                   "--outcome", outcome, "--token", token).returncode == 0
    result = json.loads(gen(wiki, "done", run, "--step", "pass2c-entities", "--item", SOURCE,
                            "--outcome", "deferred", "--token", "c41a7f6b").stdout)
    assert result["accepted"] is True
    assert result["step"] == "completion", result
