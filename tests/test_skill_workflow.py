"""skill_workflow.py — the order of a Skill's steps held by a script (Issue #1085).

Most of these run a small generic workflow, because the engine's claims are about
the engine: order is enforced, completion is decided by a check on disk, the log is
the state (so a fresh process resumes where the last one stopped), and a run that
is still open blocks a merge that carries its files while every other change
passes. The last group runs `wikicommit-generate`'s real workflow, which is where
those claims have to hold in practice.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".claude/skills/wikicommit-init/scripts/templates/scripts"
ENGINE = SCRIPTS / "skill_workflow.py"
GENERATE = REPO / ".claude/skills/wikicommit-generate"

sys.path.insert(0, str(SCRIPTS))


def drive(cwd: Path, *args: str, stdin: str = "") -> tuple[dict, int]:
    result = subprocess.run(
        [sys.executable, str(ENGINE), *args],
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
elif cmd == "names":
    for name in Path("names.txt").read_text(encoding="utf-8").splitlines():
        print(f"ITEM: {name}")
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
    assert record["workflow"]["lists"]["things"] == ["a", "b"]
    assert record["ended_at"] == ""


def test_a_fresh_process_resumes_where_the_last_one_stopped(repo):
    """What compaction or a new session looks like to the engine: nothing but the
    run path. The log on disk is the whole state."""
    _, run = start(repo)
    drive(repo, "done", run, "--step", "confirm", "--answer", "yes")
    work(repo, run, "a")
    resp, code = drive(repo, "next", run)
    assert code == 0
    assert (resp["step"], resp["item"]) == ("after", "a")
    again, _ = drive(repo, "next", run)
    assert (again["step"], again["item"]) == ("after", "a"), "next must not advance"


def test_a_run_recorded_under_the_old_driver_key_resumes(repo):
    """A run started before the rename (Issue #1203) keeps its state under `driver:`.
    `next` still finds it, and the next write moves it to `workflow:` so the record
    carries one key, not two."""
    _, run = start(repo)
    drive(repo, "done", run, "--step", "confirm", "--answer", "yes")
    work(repo, run, "a")
    path = repo / run
    text = path.read_text(encoding="utf-8")
    _, head, body = text.split("---\n", 2)
    record = yaml.safe_load(head)
    record["driver"] = record.pop("workflow")
    path.write_text("---\n" + yaml.safe_dump(record, sort_keys=False) + "---\n" + body,
                    encoding="utf-8")

    resp, code = drive(repo, "next", run)
    assert code == 0
    assert (resp["step"], resp["item"]) == ("after", "a")
    status, _ = drive(repo, "status")
    assert [r["run"] for r in status["open_runs"]] == [run], "an old-key run is still open"
    resp, code = drive(repo, "done", run, "--step", "after", "--item", "a", "--outcome", "ok")
    assert code == 0 and (resp["step"], resp["item"]) == ("work", "b")
    record = front(path)
    assert "driver" not in record
    assert [e["step"] for e in record["workflow"]["log"]][-1] == "after"


def test_the_state_names_its_definition_file_without_repeating_the_key(repo):
    """The state lives under `workflow:`; the definition's path inside it is
    `definition`, not a second `workflow` (Issue #1209)."""
    _, run = start(repo)
    state = front(repo / run)["workflow"]
    assert state["definition"] == "skill/workflow.yaml"
    assert len(state["definition_sha256"]) == 64
    assert "workflow" not in state and "workflow_sha256" not in state


@pytest.mark.parametrize("key", ["workflow", "driver"])
def test_a_run_recorded_with_the_old_definition_fields_resumes(repo, key):
    """Records written before Issue #1209 name the definition `workflow` /
    `workflow_sha256` inside the state, under either state key. `next` resumes
    them, and the next write moves both the key and the fields to the new names."""
    _, run = start(repo)
    drive(repo, "done", run, "--step", "confirm", "--answer", "yes")
    work(repo, run, "a")
    path = repo / run
    _, head, body = path.read_text(encoding="utf-8").split("---\n", 2)
    record = yaml.safe_load(head)
    state = record.pop("workflow")
    state["workflow"] = state.pop("definition")
    state["workflow_sha256"] = state.pop("definition_sha256")
    record[key] = state
    path.write_text("---\n" + yaml.safe_dump(record, sort_keys=False) + "---\n" + body,
                    encoding="utf-8")

    resp, code = drive(repo, "next", run)
    assert code == 0, resp
    assert (resp["step"], resp["item"]) == ("after", "a")
    assert not any("changed" in n for n in resp.get("notes", [])), "the old hash is still compared"
    resp, code = drive(repo, "done", run, "--step", "after", "--item", "a", "--outcome", "ok")
    assert code == 0 and (resp["step"], resp["item"]) == ("work", "b")
    record = front(path)
    assert "driver" not in record
    state = record["workflow"]
    assert state["definition"] == "skill/workflow.yaml"
    assert "workflow" not in state and "workflow_sha256" not in state


def test_status_and_check_merge_read_the_old_definition_fields(repo):
    """`status` and `check-merge` read open runs without `load_run()`; a run
    recorded with the old field names must still name its step there."""
    _, run = start(repo, "--non-interactive")
    work(repo, run, "a")
    path = repo / run
    _, head, body = path.read_text(encoding="utf-8").split("---\n", 2)
    record = yaml.safe_load(head)
    state = record["workflow"]
    state["workflow"] = state.pop("definition")
    state["workflow_sha256"] = state.pop("definition_sha256")
    path.write_text("---\n" + yaml.safe_dump(record, sort_keys=False) + "---\n" + body,
                    encoding="utf-8")
    status, _ = drive(repo, "status")
    entry = status["open_runs"][0]
    assert "problem" not in entry, entry
    assert (entry["step"], entry["item"]) == ("after", "a")
    resp, code = drive(repo, "check-merge")
    assert code == 1 and "problem" not in resp["open_runs"][0]
    assert resp["open_runs"][0]["step"] == "after"


def test_an_old_definition_hash_still_warns_when_the_definition_changed(repo):
    _, run = start(repo)
    path = repo / run
    _, head, body = path.read_text(encoding="utf-8").split("---\n", 2)
    record = yaml.safe_load(head)
    state = record["workflow"]
    state["workflow"] = state.pop("definition")
    state.pop("definition_sha256")
    state["workflow_sha256"] = "0" * 64
    path.write_text("---\n" + yaml.safe_dump(record, sort_keys=False) + "---\n" + body,
                    encoding="utf-8")
    resp, code = drive(repo, "next", run)
    assert code == 0, resp
    assert any("definition changed" in n for n in resp["notes"])


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
    log = front(repo / run)["workflow"]["log"]
    confirm = next(e for e in log if e["step"] == "confirm")
    assert confirm["answer"] == "yes" and confirm["answered_by"] == "non-interactive default"


def test_the_token_is_checked_against_the_file_the_engine_opens(repo):
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
    """fix, remove, review and hand edits use no workflow definition; they must still merge."""
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


def test_the_run_asking_is_not_counted_as_open(repo):
    """A Skill that is itself driven (wikicommit-merge) runs `check-merge` while its
    own run is open; `--except-run` leaves that one run out and no other."""
    _, run = start(repo, "--non-interactive")
    work(repo, run, "a")
    resp, code = drive(repo, "check-merge", "--except-run", run)
    assert code == 0 and resp["blocked"] is False
    _, other = start(repo, "--non-interactive")
    resp, code = drive(repo, "check-merge", "--except-run", other)
    assert code == 1 and [r["run"] for r in resp["open_runs"]] == [run]


# --- paths that are not plain ASCII (Issue #1256) -------------------------------

# A page's slug is an English identifier, so what is not ASCII in practice is a raw
# source named in Japanese and the management file that mirrors it. A space is
# here so the `-z` reading is held to a path that is not one word.
ODD_NAMES = ["原稿.md", "a b.md"]


def list_names(repo: Path, names: list[str]) -> None:
    (repo / "names.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    workflow = yaml.safe_load((repo / "skill/workflow.yaml").read_text(encoding="utf-8"))
    workflow["steps"][0]["run"] = ["{python}", "{skill_dir}/helper.py", "names"]
    (repo / "skill/workflow.yaml").write_text(yaml.safe_dump(workflow), encoding="utf-8")


@pytest.mark.parametrize("name", ODD_NAMES)
def test_check_merge_reads_git_status_paths_as_they_are_on_disk(repo, name):
    """Without `--changed`, `check-merge` asks `git status`. Read without `-z`, git
    printed `"\\345\\216\\237..."` for a non-ASCII path, which matched nothing in the run's `touched` list, so the merge carried
    the file of an unfinished run. `abandon` named nothing left behind for the same
    reason. merge's own `check-merged` calls `check-merge` this way."""
    list_names(repo, [name])
    _, run = start(repo, "--non-interactive")
    work(repo, run, name)
    resp, code = drive(repo, "check-merge")
    assert code == 1 and resp["open_runs"][0]["files"] == [f"work-{name}"], resp
    resp, code = drive(repo, "abandon", run, "--reason", "session gone")
    assert code == 0 and resp["left_behind"] == [f"work-{name}"], resp


def test_a_renamed_file_is_read_under_its_new_path(repo):
    """Under `-z` a rename is followed by its old path; that one is not a change."""
    (repo / "old.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "old.md"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"],
                   cwd=repo, check=True)
    subprocess.run(["git", "mv", "old.md", "新しい.md"], cwd=repo, check=True)
    import skill_workflow as engine

    here = os.getcwd()
    try:
        os.chdir(repo)
        changed = engine.changed_files()
    finally:
        os.chdir(here)
    assert "新しい.md" in changed and "old.md" not in changed, changed


def test_a_listed_non_ascii_path_survives_a_locale_that_is_not_utf8(repo):
    """A `produces:` list comes from a child's `ITEM:` lines. Under a locale that
    is not UTF-8 (ASCII here, cp932 / cp1252 on Windows) the child could not print
    the path, the engine read it with the wrong codec, and the engine's own JSON
    raised at `print`. Each of the three is UTF-8 now."""
    list_names(repo, ODD_NAMES)
    env = {**os.environ, "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
    env.pop("PYTHONIOENCODING", None)
    result = subprocess.run(
        [sys.executable, str(ENGINE), "start", "--workflow", "skill/workflow.yaml",
         "--model", "m"],
        cwd=repo, env=env, capture_output=True, check=False)
    out = result.stdout.decode("utf-8")
    assert result.returncode == 0, out + result.stderr.decode("utf-8", "replace")
    resp = json.loads(out)
    assert resp["step"] == "confirm"
    assert front(repo / resp["run"])["workflow"]["lists"]["things"] == ODD_NAMES


def test_a_human_answer_can_finish_the_run(repo):
    """`finishes_on` on a human step: the person deciding not to go on ends the run
    normally, as a decision rather than a failure."""
    workflow = yaml.safe_load((repo / "skill/workflow.yaml").read_text(encoding="utf-8"))
    workflow["steps"][1]["finishes_on"] = ["no"]
    (repo / "skill/workflow.yaml").write_text(yaml.safe_dump(workflow), encoding="utf-8")
    _, run = start(repo)
    resp, code = drive(repo, "done", run, "--step", "confirm", "--answer", "no")
    assert code == 0 and resp["step"] is None and resp["finished"] is True
    assert resp["finished_because"] == "confirm: no"
    record = front(repo / run)
    assert record["ended_at"] and record["halted_reason"] == ""
    workflow["steps"][1]["non_interactive"] = "no"
    (repo / "skill/workflow.yaml").write_text(yaml.safe_dump(workflow), encoding="utf-8")
    resp, _ = start(repo, "--non-interactive")
    assert resp["step"] is None and resp["finished"] is True


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
        line for line in ENGINE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    body = code.split('"""', 2)[2]  # past the module docstring
    for word in (".wikicommit/", "pass1", "pass4", "generated_pages", "status: ",
                 "management file", "wikicommit-generate", "wikicommit-merge", "gh pr",
                 "wikicommit-translate", "translated_from", "source_commit",
                 "wikicommit-synthesize", "derived_from", "synthesize-step5.5"):
        assert word not in body, word


# --- wikicommit-generate's own workflow --------------------------------------


def _steps(workflow: dict):
    for step in workflow["steps"]:
        yield from step.get("steps", [step])


@pytest.mark.parametrize("name", ["workflow.yaml", "workflow-regenerate.yaml"])
def test_the_generate_workflows_point_at_files_that_exist(name):
    from skill_workflow import load_workflow

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
    takes the first five — never everything — and the deferred questions are left
    for later rather than answered by anyone (Issue #1116)."""
    expected = {"batch-cap": "first-five", "ask-deferred": "later"}
    for name in ("workflow.yaml", "workflow-regenerate.yaml"):
        workflow = yaml.safe_load((GENERATE / name).read_text(encoding="utf-8"))
        humans = [s for s in _steps(workflow) if s.get("type") == "human"]
        assert humans, name
        for step in humans:
            assert step["non_interactive"] == expected[step["id"]], name


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
        [sys.executable, ".wikicommit/scripts/skill_workflow.py", *args],
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
    touched = front(wiki / run)["workflow"]["touched"]
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
    # The workflow engine itself runs the check on `halted` (check_on_halt): a deferral
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


@pytest.mark.parametrize("name", ["add_source.py", "resolve_source_cache_path.py", "remove_page.py"])
def test_generate_halts_at_the_start_on_scripts_older_than_the_skill(wiki, name):
    """Issue #1210 moved these from Skill trees into `.wikicommit/scripts/`; a wiki that has
    not taken `/wikicommit-update` yet would otherwise fail on Step 0's first command."""
    (wiki / ".wikicommit" / "scripts" / name).unlink()
    resp = json.loads(gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m").stdout)
    assert resp["step"] is None and resp["state"] == "halted"
    assert name in resp["halted_reason"] and "/wikicommit-update" in resp["halted_reason"]


# --- deferred questions asked once the loop is over (Issue #1116) -------------


SECOND = ".wikicommit/source/path/raw/b.txt.md"
TOKENS = {"pass1-extract": "a3f1c07d", "pass2b-type": "5e9b2d84",
          "pass2c-entities": "c41a7f6b", "pass3-generate": "9d8e35a2",
          "pass4-review": "7b06f4ce"}
LOW = ("LOW_DENSITY: natural-language ratio 0.11 below 0.3 (non-prose breakdown: "
       "links 12%, numbers/tables 71%, other markup 17%)")


def _queue(wiki: Path, rel: str, reason: str = "") -> None:
    path = wiki / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"---\nsource:\n  type: path\n  path: raw/{Path(rel).stem}\nstatus: pending\n---\n"
    if reason:
        text += f"\n## Deferred Reason\n\n{reason}\n"
    path.write_text(text, encoding="utf-8")


def _done(wiki: Path, run: str, step: str, item: str, outcome: str) -> dict:
    base = step.removeprefix("reprocess-")
    result = gen(wiki, "done", run, "--step", step, "--item", item,
                 "--outcome", outcome, "--token", TOKENS[base])
    return json.loads(result.stdout)


def _start(wiki: Path, *extra: str) -> tuple[dict, str]:
    resp = json.loads(gen(wiki, "start", "--workflow", WORKFLOW_PATH, "--model", "m",
                          *extra).stdout)
    return resp, resp["run"]


def test_a_non_interactive_run_still_leaves_the_deferral_queued(wiki):
    """With nobody to ask, the end-of-loop question takes `later`: the source keeps
    its deferral and its status, and the run goes on to the end as before."""
    _, run = _start(wiki, "--non-interactive")
    _queue(wiki, SOURCE, LOW)
    resp = _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    assert resp["accepted"] is True and resp["step"] == "completion", resp
    state = front(wiki / run)["workflow"]
    assert state["lists"]["questions"] == [SOURCE]
    asked = [e for e in state["log"] if e["step"] == "ask-deferred"]
    assert asked and asked[0]["answer"] == "later"
    assert asked[0]["answered_by"] == "non-interactive default"
    assert "reprocess" not in state["lists"]
    source = front(wiki / SOURCE)
    assert source["status"] == "pending"
    assert "## Deferred Reason" in (wiki / SOURCE).read_text(encoding="utf-8")


def test_one_source_is_asked_where_it_would_have_been_asked(wiki):
    """With a single source the question comes straight after the pass that set it
    aside, which is where an interactive run used to ask it."""
    _, run = _start(wiki)
    _queue(wiki, SOURCE, LOW)
    resp = _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    assert resp["step"] == "ask-deferred" and resp["type"] == "human", resp
    assert resp["lists"] == {"questions": [SOURCE]}
    assert "--add" in resp["then"]


def test_a_network_deferral_is_not_a_question(wiki):
    """NETWORK_UNAVAILABLE waits for a network, so nobody is asked about it."""
    _, run = _start(wiki)
    _queue(wiki, SOURCE, "NETWORK_UNAVAILABLE: name resolution failed")
    resp = _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    assert resp["step"] == "completion", resp


def test_a_continued_low_density_source_goes_through_the_passes_again(wiki):
    _, run = _start(wiki)
    _queue(wiki, SOURCE, LOW)
    _done(wiki, run, "pass1-extract", SOURCE, "deferred")

    refused = json.loads(gen(wiki, "done", run, "--step", "ask-deferred",
                             "--answer", "answered", "--add", f"reprocess={SOURCE}").stdout)
    assert refused["accepted"] is False and "low-density question" in refused["reason"]
    assert "reprocess" not in front(wiki / run)["workflow"]["lists"], "rolled back"

    resp = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "answered",
                          "--add", f"reprocess={SOURCE}",
                          "--add", f"continue-low-density={SOURCE}").stdout)
    assert resp["accepted"] is True, resp
    assert (resp["step"], resp["item"]) == ("reprocess-pass1-extract", SOURCE)
    assert resp["instructions"] == "references/pass1-extract.md"
    assert resp["lists"] == {"continue-low-density": [SOURCE], "fail-low-density": []}

    again = _done(wiki, run, "reprocess-pass1-extract", SOURCE, "deferred")
    assert again["accepted"] is False and "continue" in again["reason"]

    _queue(wiki, SOURCE)
    text = (wiki / SOURCE).read_text(encoding="utf-8").replace(
        "status: pending\n", "status: pending\nextracted_tokens: 10\n")
    (wiki / SOURCE).write_text(text, encoding="utf-8")
    resp = _done(wiki, run, "reprocess-pass1-extract", SOURCE, "extracted")
    assert (resp["step"], resp["item"]) == ("reprocess-pass2b-type", SOURCE), resp
    stamps = [p["pass"] for p in front(wiki / run)["passes"]]
    assert stamps == ["pass1-extract", "pass1-extract"], "the second loop stamps the same pass"


def test_a_failed_low_density_answer_has_to_be_carried_out(wiki):
    _, run = _start(wiki)
    _queue(wiki, SOURCE, LOW)
    _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    resp = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "answered",
                          "--add", f"reprocess={SOURCE}",
                          "--add", f"fail-low-density={SOURCE}").stdout)
    assert resp["step"] == "reprocess-pass1-extract", resp
    refused = _done(wiki, run, "reprocess-pass1-extract", SOURCE, "deferred")
    assert refused["accepted"] is False and "failed" in refused["reason"]


def test_later_takes_no_answers(wiki):
    _, run = _start(wiki)
    _queue(wiki, SOURCE, LOW)
    _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    refused = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "later",
                             "--add", f"reprocess={SOURCE}").stdout)
    assert refused["accepted"] is False
    resp = json.loads(gen(wiki, "done", run, "--step", "ask-deferred",
                          "--answer", "later").stdout)
    assert resp["accepted"] is True and resp["step"] == "completion", resp


def test_a_type_is_asked_once_for_every_source_that_proposed_it(wiki):
    """Two sources set aside on the same candidate: one answer covers both, and
    both go through the passes again in the order they were deferred."""
    _queue(wiki, SECOND)
    _, run = _start(wiki)
    reason = ('schema:GovernmentService was considered for "児童手当の申請手続き"; '
              "it fits better than schema:HowTo")
    for item in (SOURCE, SECOND):
        path = wiki / item
        path.write_text(
            f"---\nsource:\n  type: path\n  path: raw/{Path(item).stem}\nstatus: pending\n"
            "extracted_tokens: 10\n---\n", encoding="utf-8")
        assert _done(wiki, run, "pass1-extract", item, "extracted")["accepted"] is True
        _queue(wiki, item, reason)
        resp = _done(wiki, run, "pass2b-type", item, "deferred")
        assert resp["accepted"] is True, resp
    assert resp["step"] == "ask-deferred" and resp["lists"]["questions"] == [SOURCE, SECOND]

    refused = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "answered",
                             "--add", f"reprocess={SOURCE}",
                             "--add", "approved-types=schema:VideoGame").stdout)
    assert refused["accepted"] is False and "schema:VideoGame" in refused["reason"]

    resp = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "answered",
                          "--add", f"reprocess={SOURCE}", "--add", f"reprocess={SECOND}",
                          "--add", "approved-types=schema:GovernmentService").stdout)
    assert resp["accepted"] is True, resp
    assert (resp["step"], resp["item"]) == ("reprocess-pass1-extract", SOURCE)
    state = front(wiki / run)["workflow"]
    assert state["lists"]["reprocess"] == [SOURCE, SECOND]


def test_an_item_ended_in_one_loop_is_walked_again_in_the_next(wiki):
    """The engine keys an early end by loop, so the second loop does not skip a
    source the first one deferred."""
    _, run = _start(wiki)
    _queue(wiki, SOURCE, LOW)
    _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    resp = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "answered",
                          "--add", f"reprocess={SOURCE}",
                          "--add", f"fail-low-density={SOURCE}").stdout)
    assert resp["step"] == "reprocess-pass1-extract"
    text = (wiki / SOURCE).read_text(encoding="utf-8").replace("status: pending", "status: failed")
    (wiki / SOURCE).write_text(text.replace("## Deferred Reason", "## Failure Reason"),
                               encoding="utf-8")
    resp = _done(wiki, run, "reprocess-pass1-extract", SOURCE, "failed")
    assert resp["accepted"] is True and resp["step"] == "completion", resp


def test_a_type_answer_must_name_a_candidate_whole(wiki):
    """`schema:Government` is a substring of the deferred `schema:GovernmentService`,
    but Pass 2b looks its candidate up by name, so it would never match."""
    _, run = _start(wiki)
    path = wiki / SOURCE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nsource:\n  type: path\n  path: raw/a\nstatus: pending\n"
                    "extracted_tokens: 10\n---\n", encoding="utf-8")
    _done(wiki, run, "pass1-extract", SOURCE, "extracted")
    _queue(wiki, SOURCE, "schema:GovernmentService was considered; it fits better than schema:HowTo")
    _done(wiki, run, "pass2b-type", SOURCE, "deferred")
    refused = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "answered",
                             "--add", f"reprocess={SOURCE}",
                             "--add", "approved-types=schema:Government").stdout)
    assert refused["accepted"] is False and "schema:Government " in refused["reason"]


def test_a_source_named_twice_in_reprocess_is_refused(wiki):
    _, run = _start(wiki)
    _queue(wiki, SOURCE, LOW)
    _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    refused = json.loads(gen(wiki, "done", run, "--step", "ask-deferred", "--answer", "answered",
                             "--add", f"reprocess={SOURCE}", "--add", f"reprocess=./{SOURCE}",
                             "--add", f"continue-low-density={SOURCE}").stdout)
    assert refused["accepted"] is False and "more than once" in refused["reason"]


def test_a_pass1_deferral_reason_has_to_be_the_scripts_line(wiki):
    """The end-of-loop question finds a low-density deferral by its prefix."""
    _, run = _start(wiki)
    _queue(wiki, SOURCE, f"- {LOW}")
    refused = _done(wiki, run, "pass1-extract", SOURCE, "deferred")
    assert refused["accepted"] is False and "verbatim" in refused["reason"]
