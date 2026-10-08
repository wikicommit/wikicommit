"""wikicommit-merge driven by skill_workflow.py (Issue #1094; Step 2 and 3 as script
steps, Issue #1196).

The second Skill on the engine, and a different shape from the first: no loop over
items, but Git operations, a wait on GitHub, one question to a person and Issues
filed after the merge. These run the real `workflow.yaml` and `workflow_checks.py`
in a scratch repository with a local bare `origin` and a stand-in `gh`, because what
has to hold is the claim the Skill makes — a merge stopped partway resumes from the
step it stopped at, and a step is not complete until the disk (or GitHub) says so.
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
MERGE = REPO / ".claude/skills/wikicommit-merge"
WORKFLOW = ".claude/skills/wikicommit-merge/workflow.yaml"
TEMPLATES = REPO / ".claude/skills/wikicommit-init/scripts/templates"
PAGE = ".wikicommit/entity/ja/Person/a.md"
PAGE_TEXT = """---
title: "A"
lang: ja
type: "schema:Person"
sources:
  - type: manual
    author: t
    created_at: "2026-10-07"
review_status: pending
---

A is a person.
"""

sys.path.insert(0, str(SCRIPTS))

FAKE_GH = '''#!{python}
import sys
args = sys.argv[1:]
if args[:2] == ["repo", "view"]:
    print("main")
elif args[:2] == ["pr", "view"]:
    print(open("{state}").read().strip())
else:
    sys.exit(1)
'''

# Records each call (argv and working directory) and prints the JSON in `out`.
FAKE_LYCHEE = '''#!{python}
import json, os, sys
with open("{calls}", "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
print(open("{out}").read())
'''


def _steps(workflow: dict):
    for step in workflow["steps"]:
        yield from step.get("steps", [step])


def _token(name: str) -> str:
    from record_run import read_pass_token

    return read_pass_token(MERGE / "references" / name)


@pytest.fixture
def wiki(tmp_path: Path):
    origin = tmp_path / "origin.git"
    work = tmp_path / "wiki"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state = tmp_path / "pr-state"
    state.write_text("OPEN\n", encoding="utf-8")
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH.format(python=sys.executable, state=state), encoding="utf-8")
    gh.chmod(0o755)
    lychee_out = tmp_path / "lychee-out"
    lychee_out.write_text('{"fail_map": {}}', encoding="utf-8")
    lychee_calls = tmp_path / "lychee-calls"
    lychee = bin_dir / "lychee"
    lychee.write_text(FAKE_LYCHEE.format(python=sys.executable, calls=lychee_calls,
                                         out=lychee_out), encoding="utf-8")
    lychee.chmod(0o755)
    env = dict(os.environ)
    env.update({
        "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    })
    shutil.copytree(SCRIPTS, work / ".wikicommit" / "scripts")
    shutil.copytree(TEMPLATES / "schema", work / ".wikicommit" / "schema")
    shutil.copytree(MERGE, work / ".claude" / "skills" / "wikicommit-merge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (work / ".gitignore").write_text(".wikicommit/run/\n.wikicommit/.cache/\nignored/\n",
                                     encoding="utf-8")

    def git(*args):
        return subprocess.run(["git", *args], cwd=work, env=env, check=True,
                              capture_output=True, text=True)

    git("add", ".")
    git("commit", "-q", "-m", "init")
    git("remote", "add", "origin", str(origin))
    git("push", "-q", "origin", "main")
    page = work / PAGE
    page.parent.mkdir(parents=True)
    page.write_text(PAGE_TEXT, encoding="utf-8")
    return {"dir": work, "env": env, "git": git, "pr_state": state,
            "lychee_out": lychee_out, "lychee_calls": lychee_calls}


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


def checks(wiki, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(Path(".claude/skills/wikicommit-merge/scripts/workflow_checks.py")),
         *args],
        cwd=wiki["dir"], env=wiki["env"], capture_output=True, text=True, check=False,
        input=stdin,
    )


def quiet_orphans(wiki) -> None:
    """A lone page is an orphan; tests that want no warning at all stub the check."""
    (wiki["dir"] / ".wikicommit/scripts/check_orphans.py").write_text(
        "print('SUMMARY: orphans=0, duplicates=0')\n", encoding="utf-8")


def passed(wiki, run: str) -> dict:
    """The agent's part of Step 3: lychee until done, markdownlint piped in."""
    for _ in range(10):
        out = checks(wiki, "links", "--run", run).stdout
        if "LINKS: done" in out:
            break
    checks(wiki, "style", "--run", run, stdin="Summary: 0 error(s)\n")
    resp, code = drive(wiki, "done", run, "--step", "link-and-style-checks",
                       "--outcome", "checked", "--token", _token("quality-checks.md"))
    assert code == 0, resp
    return resp


# --- the definition -----------------------------------------------------------


def test_the_merge_workflow_points_at_files_that_exist_and_checks_each_token():
    from skill_workflow import load_workflow

    workflow = load_workflow(MERGE / "workflow.yaml")
    for step in _steps(workflow):
        if step.get("instructions"):
            assert (MERGE / step["instructions"]).is_file(), step["id"]
            assert _token(Path(step["instructions"]).name), (
                f"{step['id']}: a step file without a pass_token is completed on the "
                "agent's word alone"
            )


def test_the_warnings_question_proceeds_when_nobody_can_answer():
    """Non-interactive runs record the warnings and proceed; blocking still halts."""
    workflow = yaml.safe_load((MERGE / "workflow.yaml").read_text(encoding="utf-8"))
    humans = [s for s in _steps(workflow) if s.get("type") == "human"]
    assert [s["id"] for s in humans] == ["proceed-with-warnings"]
    assert humans[0]["non_interactive"] == "proceed"
    assert humans[0]["finishes_on"] == ["stop"]
    gates = next(s for s in _steps(workflow) if s["id"] == "quality-checks")
    assert gates["type"] == "script", "the blocking checks are run by the engine"
    slow = next(s for s in _steps(workflow) if s["id"] == "link-and-style-checks")
    assert slow.get("check"), "lychee and markdownlint are confirmed on disk"


def test_the_skill_md_is_the_workflow_loop():
    text = (MERGE / "SKILL.md").read_text(encoding="utf-8")
    assert "skill_workflow.py start --workflow workflow.yaml" in text
    assert "skill_workflow.py next <run>" in text
    assert "record_run.py start" not in text, "the workflow engine opens the run record now"


# --- the run ------------------------------------------------------------------


def test_nothing_to_merge_finishes_as_a_no_op(wiki):
    (wiki["dir"] / PAGE).unlink()
    resp, run = start(wiki)
    assert resp["step"] is None and resp["finished_because"] == "No changes to merge"
    record = front(wiki["dir"] / run)
    assert record["ended_at"] and record["halted_reason"] == ""


def test_the_merge_does_not_block_itself_but_another_open_run_does(wiki):
    resp, _ = start(wiki)
    assert resp["step"] == "link-and-style-checks", (
        "the merge's own open run must not block it")
    assert "DEFAULT_BRANCH: main" in resp["notes"]

    other = wiki["dir"] / "other"
    other.mkdir()
    (other / "workflow.yaml").write_text(yaml.safe_dump({
        "skill": "wikicommit-generate",
        "steps": [
            {"id": "write", "type": "script",
             "run": ["{python}", "-c", f"print('TOUCHED: {PAGE}')"]},
            {"id": "later", "type": "agent", "outcomes": {"ok": ""}},
        ],
    }), encoding="utf-8")
    drive(wiki, "start", "--workflow", "other/workflow.yaml", "--model", "m")
    resp, run = start(wiki)
    assert resp["step"] is None and resp["state"] == "halted"
    assert any(n.startswith("OPEN_RUN:") and PAGE in n for n in resp["notes"]), resp
    assert front(wiki["dir"] / run)["halted_reason"].startswith("open-runs:")


def test_warnings_ask_a_person_and_stop_ends_the_run_untouched(wiki):
    _, run = start(wiki)
    resp = passed(wiki, run)
    assert resp["step"] == "proceed-with-warnings"
    assert resp["lists"]["warnings"] == ["check_orphans.py (1)"]
    resp, code = drive(wiki, "done", run, "--step", "proceed-with-warnings", "--answer", "stop")
    assert code == 0 and resp["finished"] is True
    assert wiki["git"]("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"


def test_a_non_interactive_run_proceeds_past_warnings(wiki):
    _, run = start(wiki, "--non-interactive")
    resp = passed(wiki, run)
    assert resp["step"] == "commit"
    assert front(wiki["dir"] / run)["workflow"]["lists"]["warnings"] == [
        "check_orphans.py (1)"
    ], "the warnings reach the run record"
    body = checks(wiki, "pr-body", "--run", run).stdout
    assert "Warnings: 1." in body and "### check_orphans.py (1)" in body
    assert f"- ORPHAN: {PAGE}" in body, "the PR body carries the finding verbatim"


def test_a_blocking_check_halts_before_any_branch(wiki):
    """A blocking finding halts the run in the engine's own step, with the finding
    as the reason and every finding in the notes; no branch is made."""
    (wiki["dir"] / PAGE).write_text("---\ntitle: A\n---\nbody\n", encoding="utf-8")
    resp, run = start(wiki)
    assert resp["step"] is None and resp["state"] == "halted"
    reason = front(wiki["dir"] / run)["halted_reason"]
    assert reason.startswith("quality-checks: BLOCKED: validate_frontmatter.py: ERROR:"), reason
    assert any(n.startswith("ERROR:") and PAGE in n for n in resp["notes"]), resp["notes"]
    assert wiki["git"]("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"


def test_a_check_that_crashes_does_not_pass_silently(wiki):
    (wiki["dir"] / ".wikicommit/scripts/check_raw_html.py").write_text(
        "import sys\nsys.exit(2)\n", encoding="utf-8")
    resp, run = start(wiki)
    assert resp["state"] == "halted"
    assert "check_raw_html.py: could not run" in front(wiki["dir"] / run)["halted_reason"]


def test_a_stopped_merge_resumes_from_where_it_stopped(wiki):
    """The whole run, interrupted after each step that has an effect outside the
    agent: every resumption is a fresh `next` with nothing but the run path, and each
    step is refused until the disk or GitHub agrees it happened."""
    git = wiki["git"]
    quiet_orphans(wiki)
    _, run = start(wiki)
    assert passed(wiki, run)["step"] == "commit", "no warnings: the question is skipped"

    def done(step: str, token_file: str, *extra: str):
        return drive(wiki, "done", run, "--step", step, "--outcome",
                     {"commit": "committed", "open-pr": "opened", "merge-pr": "merged",
                      "tracking-issues": "filed", "failure-issues": "filed",
                      "report": "reported"}[step],
                     "--token", _token(token_file), *extra)

    resp, code = done("commit", "commit.md")
    assert code == 1 and resp["accepted"] is False, "nothing was committed yet"
    git("checkout", "-q", "-b", "wikicommit/merge-20261006-120000")
    git("add", ".wikicommit/entity/")
    git("commit", "-q", "-m", "wiki: bulk update")
    resp, code = done("commit", "commit.md")
    assert code == 0 and resp["step"] == "open-pr"

    # A new session: only the run path survives.
    resp, _ = drive(wiki, "next", run)
    assert resp["step"] == "open-pr"
    resp, code = done("open-pr", "open-pr.md", "--add", "pr=7")
    assert code == 1 and "origin" in resp["reason"], "the branch was never pushed"
    git("push", "-q", "origin", "wikicommit/merge-20261006-120000")
    resp, code = done("open-pr", "open-pr.md", "--add", "pr=7")
    assert code == 0 and resp["step"] == "merge-pr"

    resp, _ = drive(wiki, "next", run)
    assert resp["step"] == "merge-pr"
    resp, code = done("merge-pr", "merge-pr.md")
    assert code == 1 and "OPEN" in resp["reason"], "GitHub has not merged it"
    wiki["pr_state"].write_text("MERGED\n", encoding="utf-8")
    resp, code = done("merge-pr", "merge-pr.md")
    assert code == 1 and "main" in resp["reason"], "still on the merge branch"
    git("checkout", "-q", "main")
    resp, code = done("merge-pr", "merge-pr.md")
    assert code == 0 and resp["step"] == "tracking-issues"

    resp, _ = drive(wiki, "next", run)
    assert resp["step"] == "tracking-issues"
    assert done("tracking-issues", "tracking-issues.md")[0]["step"] == "failure-issues"
    assert done("failure-issues", "failure-issues.md")[0]["step"] == "report"
    resp, code = done("report", "completion-report.md", "--count", "pr=7",
                      "--count", "tracking_issues=1", "--count", "failure_issues=0")
    assert code == 0 and resp["finished"] is True
    record = front(wiki["dir"] / run)
    assert record["skill"] == "wikicommit-merge"
    assert record["ended_at"] and record["halted_reason"] == ""
    assert record["outcome"] == {"pr": 7, "tracking_issues": 1, "failure_issues": 0}
    assert record["workflow"]["lists"]["pr"] == ["7"]


def test_a_merge_that_fails_halts_with_its_reason(wiki):
    quiet_orphans(wiki)
    _, run = start(wiki)
    passed(wiki, run)
    wiki["git"]("checkout", "-q", "-b", "wikicommit/merge-20261006-120000")
    wiki["git"]("add", ".wikicommit/entity/")
    wiki["git"]("commit", "-q", "-m", "wiki: bulk update")
    wiki["git"]("push", "-q", "origin", "wikicommit/merge-20261006-120000")
    for step, name, extra in (("commit", "commit.md", ["--outcome", "committed"]),
                              ("open-pr", "open-pr.md", ["--outcome", "opened", "--add", "pr=7"])):
        _, code = drive(wiki, "done", run, "--step", step, "--token", _token(name), *extra)
        assert code == 0
    resp, code = drive(wiki, "done", run, "--step", "merge-pr", "--outcome", "failed",
                       "--token", _token("merge-pr.md"), "--reason", "DIRTY")
    assert code == 0 and resp["state"] == "halted"
    assert front(wiki["dir"] / run)["halted_reason"] == "merge-pr: DIRTY"


# --- Step 2: classification ---------------------------------------------------


def _classify(wiki, kind: str) -> tuple[list[str], list[str]]:
    result = checks(wiki, "classify", "--kind", kind)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    return ([line[len("ITEM: "):] for line in lines if line.startswith("ITEM: ")],
            [line for line in lines if not line.startswith("ITEM: ")])


def _manager(wiki, name: str, path: str) -> None:
    manager = wiki["dir"] / ".wikicommit/source/path" / f"{name}.md"
    manager.parent.mkdir(parents=True, exist_ok=True)
    manager.write_text(f"---\nsource:\n  type: path\n  path: \"{path}\"\n---\n",
                       encoding="utf-8")


def test_classify_pages_and_removals(wiki):
    work, git = wiki["dir"], wiki["git"]
    removed = ".wikicommit/entity/ja/Person/b.md"
    gone = ".wikicommit/entity/ja/Person/c.md"
    for path in (removed, gone):
        (work / path).write_text(PAGE_TEXT, encoding="utf-8")
    git("add", removed, gone)
    git("commit", "-q", "-m", "pages")
    (work / removed).write_text(PAGE_TEXT.replace("review_status: pending",
                                                  "review_status: pending\nstatus: removed"),
                                encoding="utf-8")
    (work / gone).unlink()
    asset = work / ".wikicommit/entity/assets/x.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"png")

    pages, _ = _classify(wiki, "pages")
    assert sorted(pages) == sorted([PAGE, removed]), "deleted files and assets are not pages"
    assert _classify(wiki, "removing")[0] == [removed], "a new page is not being removed"


def test_classify_new_sources(wiki):
    work = wiki["dir"]
    (work / "raw").mkdir()
    (work / "raw/report[2024].pdf").write_bytes(b"%PDF")
    (work / "raw/report2.pdf").write_bytes(b"%PDF")  # what `[2024]` would match as a class
    (work / "ignored").mkdir()
    (work / "ignored/secret.pdf").write_bytes(b"%PDF")
    _manager(wiki, "a", "raw/report[2024].pdf")
    _manager(wiki, "b", "ignored/secret.pdf")
    _manager(wiki, "c", "raw/missing.pdf")

    items, notes = _classify(wiki, "sources")
    assert items == ["raw/report[2024].pdf"]
    assert any("raw/missing.pdf" in n and "does not exist" in n for n in notes), notes
    assert any("ignored/secret.pdf" in n and ".gitignore" in n for n in notes), notes


def test_classify_new_sources_in_a_directory_takes_only_its_untracked_files(wiki):
    """A hand-written management file can name a directory. Each file in it is
    judged on its own, whichever git happens to list first: the untracked ones are
    carried, a tracked file's uncommitted edit never is (Issue #1237)."""
    work, git = wiki["dir"], wiki["git"]
    for name, tracked, new in (("first", "z-tracked.txt", "a-new.txt"),
                               ("second", "a-tracked.txt", "z-new.txt")):
        directory = work / "raw" / name
        directory.mkdir(parents=True)
        (directory / tracked).write_text("v1\n", encoding="utf-8")
        git("add", f"raw/{name}/{tracked}")
        git("commit", "-q", "-m", name)
        (directory / tracked).write_text("v2, an unrelated edit\n", encoding="utf-8")
        (directory / new).write_text("new\n", encoding="utf-8")
        _manager(wiki, name, f"raw/{name}")

    items, notes = _classify(wiki, "sources")
    assert sorted(items) == ["raw/first/a-new.txt", "raw/second/z-new.txt"], (items, notes)
    assert not any(".gitignore" in n for n in notes), notes


def test_an_ignored_source_path_is_named_once_however_it_is_written(wiki):
    """git prints `ignored/secret.pdf` for `./ignored/secret.pdf`; the warning names
    the path once, not once as written and again as git printed it (Issue #1258)."""
    work = wiki["dir"]
    (work / "ignored").mkdir()
    (work / "ignored/secret.pdf").write_bytes(b"%PDF")
    _manager(wiki, "a", "./ignored/secret.pdf")
    _, notes = _classify(wiki, "sources")
    warning = [n for n in notes if ".gitignore" in n]
    assert warning and "(./ignored/secret.pdf)" in warning[0], notes


def _undecodable(directory: Path) -> str:
    """Create a file whose name is not valid UTF-8; skip where the file system
    refuses one (macOS, Windows)."""
    name = b"\xff\xfe.md"
    try:
        fd = os.open(os.fsencode(directory) + b"/" + name, os.O_WRONLY | os.O_CREAT, 0o644)
    except (OSError, UnicodeError) as e:
        pytest.skip(f"the file system refuses a name that is not valid UTF-8: {e}")
    os.write(fd, PAGE_TEXT.encode("utf-8"))
    os.close(fd)
    return name.decode("utf-8", "replace")


def test_a_page_whose_name_is_not_utf8_halts_the_classification(wiki):
    """It used to fall out of `changed_md` without a word, and the commit step, which
    stages by pathspec, would have committed it unchecked (Issue #1258)."""
    _undecodable((wiki["dir"] / PAGE).parent)
    for kind in ("pages", "removing"):
        result = checks(wiki, "classify", "--kind", kind)
        assert result.returncode == 1, (kind, result.stdout)
        assert "not valid UTF-8" in result.stdout and "Rename" in result.stdout, result.stdout
        assert "\ufffd" not in result.stdout, "the path is shown printable"


def test_a_deleted_page_whose_name_is_not_utf8_does_not_halt(wiki):
    """A tracked page renamed with a plain `mv` leaves ` D <old name>` behind; that
    entry needs no check, so it must not keep the merge halted (Issue #1258)."""
    directory = (wiki["dir"] / PAGE).parent
    _undecodable(directory)
    wiki["git"]("add", "-A")
    wiki["git"]("commit", "-q", "-m", "bad name")
    os.remove(os.fsencode(directory) + b"/\xff\xfe.md")
    result = checks(wiki, "classify", "--kind", "pages")
    assert result.returncode == 0, result.stdout


def test_a_source_file_whose_name_is_not_utf8_is_warned_and_left_out(wiki):
    work = wiki["dir"]
    directory = work / "raw/zip"
    directory.mkdir(parents=True)
    (directory / "ok.txt").write_text("ok\n", encoding="utf-8")
    _undecodable(directory)
    _manager(wiki, "z", "raw/zip")
    items, notes = _classify(wiki, "sources")
    assert items == ["raw/zip/ok.txt"], (items, notes)
    assert any("not valid UTF-8" in n for n in notes), notes


def test_classify_schema_vocab_policy_and_relations(wiki):
    work, git = wiki["dir"], wiki["git"]
    (work / ".wikicommit/schema/Recipe2.md").write_text("---\n---\n", encoding="utf-8")
    custom = work / ".wikicommit/schema/custom/Thing.md"
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("---\n---\n", encoding="utf-8")
    with (work / ".wikicommit/schema/Person.md").open("a", encoding="utf-8") as f:
        f.write("\nedited\n")
    (work / ".wikicommit/schemaorg-vocab.json").write_text("{}", encoding="utf-8")
    (work / ".wikicommit/source-policy.md").write_text("x\n", encoding="utf-8")
    (work / ".wikicommit/relations.yml").write_text("[]\n", encoding="utf-8")

    items, notes = _classify(wiki, "schema")
    assert sorted(items) == [".wikicommit/schema/Recipe2.md", ".wikicommit/schema/custom/Thing.md"]
    assert any("Person.md" in n for n in notes), "an edited committed type file is reported"
    assert _classify(wiki, "vocab")[0] == [".wikicommit/schemaorg-vocab.json"]
    assert _classify(wiki, "policy")[0] == [".wikicommit/source-policy.md"]
    assert _classify(wiki, "relations")[0] == [".wikicommit/relations.yml"]
    git("add", ".wikicommit/schemaorg-vocab.json")
    git("commit", "-q", "-m", "vocab")
    (work / ".wikicommit/schemaorg-vocab.json").write_text('{"a": 1}', encoding="utf-8")
    assert _classify(wiki, "vocab")[0] == [], "a rebuilt tracked vocab is a person's to commit"


def test_the_commit_step_is_handed_the_lists(wiki):
    quiet_orphans(wiki)
    (wiki["dir"] / ".wikicommit/relations.yml").write_text("[]\n", encoding="utf-8")
    _, run = start(wiki)
    resp = passed(wiki, run)
    assert resp["step"] == "commit"
    assert resp["lists"]["relations_file"] == [".wikicommit/relations.yml"]
    assert resp["lists"]["new_sources"] == []
    resp, _ = drive(wiki, "next", run)
    assert resp["lists"]["relations_file"] == [".wikicommit/relations.yml"], (
        "a resumed commit step reads the lists instead of working them out again")


# --- Step 3: the fast checks' edges (Issue #1237) ------------------------------


def _module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "merge_workflow_checks", MERGE / "scripts" / "workflow_checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_non_ascii_page_survives_a_locale_that_is_not_utf8(wiki):
    """git prints paths as UTF-8 bytes whatever the locale says. Read with the
    locale's encoding (ASCII here, cp932/cp1252 on Windows) the page either became a
    path that does not exist or raised UnicodeDecodeError out of the step.

    `detect` rather than `classify --kind pages`: the latter also asks the file
    system whether the page exists, and under an ASCII locale on POSIX the file
    system encoding is ASCII too. On Windows it is UTF-8 whatever the locale."""
    page = ".wikicommit/entity/ja/Person/山田.md"
    (wiki["dir"] / page).write_text(PAGE_TEXT, encoding="utf-8")
    # No PYTHONIOENCODING: run directly, as `references/*.md` tell the agent to, the
    # script writes its own stdout as UTF-8 (Issue #1264).
    env = {**wiki["env"], "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
    env.pop("PYTHONIOENCODING", None)
    result = subprocess.run(
        [sys.executable, str(Path(".claude/skills/wikicommit-merge/scripts/workflow_checks.py")),
         "detect"],
        cwd=wiki["dir"], env=env, capture_output=True, check=False)
    out = result.stdout.decode("utf-8")
    assert result.returncode == 0, out + result.stderr.decode("utf-8", "replace")
    assert f"ITEM: {page}" in out.splitlines(), out


def test_a_python_check_writes_and_is_read_as_utf8(monkeypatch):
    """A child check prints a Japanese finding; under a locale that cannot encode it
    (cp1252 on Windows, ASCII here) it raised UnicodeEncodeError in the child."""
    module = _module()
    monkeypatch.setenv("PYTHONIOENCODING", "ascii")
    result = module.run([sys.executable, "-c", "print('WARNING: 山田.md: 日本語')"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "WARNING: 山田.md: 日本語"
    undecodable = module.run([sys.executable, "-c",
                              "import sys; sys.stdout.buffer.write(b'ok \\xff')"])
    assert undecodable.stdout.startswith("ok "), "an undecodable byte is shown, not raised"


def test_check_wikilinks_calls_fit_however_many_pages_are_removed():
    """Outgoing links per group of changed pages, backlinks per group of removed
    pages: m + k calls, each page in exactly one call of each kind (Issue #1257)."""
    module = _module()
    prefix = ["python", ".wikicommit/scripts/check_wikilinks.py"]
    changed = [f".wikicommit/entity/ja/Person/page-{i:04d}-{'x' * 40}.md" for i in range(800)]
    for removed in ([], changed[:5], changed[:400], changed):
        argvs = module.wikilink_argvs(prefix, changed, removed)
        checked, deleted = [], []
        for argv in argvs:
            flag, *paths = argv[len(prefix):]
            assert module.argv_length(argv) <= module.ARGV_CHARS
            assert not any(p.startswith("--") for p in paths), "one kind of check per call"
            (checked if flag == "--changed" else deleted).extend(paths)
        assert checked == changed, "every changed page is checked once"
        assert deleted == removed, "every removed page's backlinks are checked once"
        assert len(argvs) == (len(module.path_argvs([*prefix, "--changed"], changed))
                              + len(module.path_argvs([*prefix, "--deleted"], removed)))


def test_each_whole_command_line_fits_with_a_long_prefix(monkeypatch, tmp_path):
    """The interpreter, the script path and the flag count against ARGV_CHARS, not
    only the page paths: with long paths packed to the limit, the whole argv of
    every call still fits — for all three per-file checks (Issue #1263)."""
    module = _module()
    python = "/" + "/".join(["very-long-virtualenv-directory"] * 40) + "/bin/python"
    changed = [f".wikicommit/entity/ja/Person/page-{i:05d}-{'y' * 150}.md"
               for i in range(600)]
    for name in ("validate_frontmatter.py", "check_raw_html.py"):
        prefix = [python, str(module.SCRIPTS_DIR / name)]
        argvs = module.path_argvs(prefix, changed)
        assert len(argvs) > 1
        assert all(module.argv_length(argv) <= module.ARGV_CHARS for argv in argvs)
        assert [p for argv in argvs for p in argv[len(prefix):]] == changed
    prefix = [python, str(module.SCRIPTS_DIR / "check_wikilinks.py")]
    argvs = module.wikilink_argvs(prefix, changed, changed)
    assert all(module.argv_length(argv) <= module.ARGV_CHARS for argv in argvs)
    # cmd_checks itself builds its calls through the same function.
    seen = []
    monkeypatch.setattr(module.sys, "executable", python)
    monkeypatch.setattr(module, "read_state", lambda run: {})
    monkeypatch.setattr(module, "listed",
                        lambda state, key: changed if key == "changed_md" else [])
    monkeypatch.setattr(module, "run_script",
                        lambda argvs, blocking, warning: (seen.extend(argvs), ([], [], ""))[1])
    monkeypatch.setattr(module, "write_findings", lambda *a: None)
    assert module.cmd_checks(type("Args", (), {"run": "r.md"})()) == 0
    per_file = [argv for argv in seen if len(argv) > 2]
    assert len(per_file) > 3
    assert all(module.argv_length(argv) <= module.ARGV_CHARS for argv in seen)


def test_a_backlink_to_a_removed_page_is_warned_once_however_the_calls_split(
        tmp_path, monkeypatch):
    """The page being removed is among the changed pages as well; the warning must
    appear, and the same once, whether the change fits one call or many."""
    module = _module()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".wikicommit").mkdir()
    (tmp_path / ".wikicommit/config.yml").write_text("primary_lang: ja\n", encoding="utf-8")
    person = tmp_path / ".wikicommit/entity/ja/Person"
    person.mkdir(parents=True)
    removed = ".wikicommit/entity/ja/Person/a.md"
    (tmp_path / removed).write_text(
        PAGE_TEXT.replace("review_status: pending", "review_status: pending\nstatus: removed"),
        encoding="utf-8")
    changed = [removed]
    for name in ("b", "c", "d"):
        (person / f"{name}.md").write_text(PAGE_TEXT, encoding="utf-8")
        changed.append(f".wikicommit/entity/ja/Person/{name}.md")
    (person / "e.md").write_text(PAGE_TEXT + "\nSee [[Person/a]].\n", encoding="utf-8")
    prefix = [sys.executable, str(SCRIPTS / "check_wikilinks.py")]

    results = []
    for limit in (module.ARGV_CHARS, len(changed[0]) + 1):
        argvs = module.wikilink_argvs(prefix, changed, [removed], limit)
        blocked, warned, crash = module.run_script(argvs, ("ERROR:",), ("WARNING:",))
        assert not blocked and not crash, (blocked, crash)
        results.append((len(argvs), warned))
    (one_call, single), (many_calls, split) = results
    assert one_call == 2 and many_calls == 5
    assert single == [f"WARNING: {removed} (being changed to status: removed): "
                      "a backlink remains (.wikicommit/entity/ja/Person/e.md)"]
    assert split == single


def test_a_run_with_no_changed_page_skips_the_link_and_style_step(wiki):
    quiet_orphans(wiki)
    (wiki["dir"] / PAGE).unlink()
    (wiki["dir"] / ".wikicommit/relations.yml").write_text("[]\n", encoding="utf-8")
    resp, run = start(wiki)
    assert resp["step"] == "commit", resp
    assert front(wiki["dir"] / run)["workflow"]["lists"]["changed_md"] == []


# --- Step 3: lychee, markdownlint and the PR body ------------------------------


def test_lychee_sees_only_the_changed_pages_a_few_per_call(wiki):
    work = wiki["dir"]
    second = ".wikicommit/entity/ja/Person/b.md"
    (work / second).write_text(PAGE_TEXT, encoding="utf-8")
    quiet_orphans(wiki)
    resp, run = start(wiki)
    assert resp["step"] == "link-and-style-checks"
    resp, code = drive(wiki, "done", run, "--step", "link-and-style-checks",
                       "--outcome", "checked", "--token", _token("quality-checks.md"))
    assert code == 1 and "LINKS: done" in resp["reason"], "nothing was checked yet"

    first = checks(wiki, "links", "--run", run, "--batch", "1", "--budget", "0").stdout
    assert "LINKS: 1/2" in first and "LINKS: more" in first
    second_call = checks(wiki, "links", "--run", run, "--batch", "1", "--budget", "0").stdout
    assert "LINKS: 2/2" in second_call and "LINKS: done" in second_call

    calls = [json.loads(line) for line in
             wiki["lychee_calls"].read_text(encoding="utf-8").splitlines()]
    assert len(calls) == 2, "one batch per call, and the second call continued the first"
    checked = [Path(arg).resolve() for call in calls for arg in call["argv"]
               if arg.endswith(".md")]
    assert sorted(checked) == sorted((work / p).resolve() for p in (PAGE, second)), (
        "lychee must see the changed pages only, never a whole tree — review and run "
        "records hold URLs that would all be fetched again")
    for call in calls:
        assert "--cache" in call["argv"]
        assert Path(call["cwd"]) == (work / ".wikicommit/.cache/lychee").resolve(), (
            "the .lycheecache file lands in the ignored cache directory")

    resp, code = drive(wiki, "done", run, "--step", "link-and-style-checks",
                       "--outcome", "checked", "--token", _token("quality-checks.md"))
    assert code == 1 and "markdownlint" in resp["reason"]


def test_lychee_findings_and_markdownlint_reach_the_pr_body(wiki):
    quiet_orphans(wiki)
    url_fail = {"fail_map": {str((wiki["dir"] / PAGE).resolve()): [
        {"url": f"https://example.com/{i}?a=1&b=2", "status": {"text": "404 Not Found"}}
        for i in range(7)]}}
    wiki["lychee_out"].write_text(json.dumps(url_fail), encoding="utf-8")
    _, run = start(wiki, "--non-interactive")
    checks(wiki, "links", "--run", run)
    checks(wiki, "style", "--run", run,
           stdin=f"markdownlint-cli2 v0.13.0\n{PAGE}:3 MD012/no-multiple-blanks Multiple\n"
                 "Summary: 1 error(s)\n")
    resp, code = drive(wiki, "done", run, "--step", "link-and-style-checks",
                       "--outcome", "checked", "--token", _token("quality-checks.md"))
    assert code == 0 and resp["step"] == "commit", resp
    assert front(wiki["dir"] / run)["workflow"]["lists"]["warnings"] == [
        "lychee (7)", "markdownlint-cli2 (1)"]
    body = checks(wiki, "pr-body", "--run", run).stdout
    assert "Warnings: 8." in body
    assert f"- {PAGE}: https://example.com/0?a=1&b=2 (404 Not Found)" in body
    assert "- (+2 more)" in body, "five findings per tool, then the count of the rest"
    assert "MD012" in body


def test_lychee_progress_from_before_structured_findings_starts_over(wiki):
    """A run's `lychee-progress.json` holding plain-string findings (written before
    Issue #1243) is discarded, and `lychee.json` keeps the findings' text only."""
    quiet_orphans(wiki)
    url_fail = {"fail_map": {str((wiki["dir"] / PAGE).resolve()): [
        {"url": "https://example.com/new", "status": {"text": "404 Not Found"}}]}}
    wiki["lychee_out"].write_text(json.dumps(url_fail), encoding="utf-8")
    _, run = start(wiki)
    cache = wiki["dir"] / ".wikicommit/.cache/merge" / Path(run).stem
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "lychee-progress.json").write_text(json.dumps(
        {"checked": [PAGE], "findings": [f"{PAGE}: https://example.com/old (404)"]}),
        encoding="utf-8")
    assert "LINKS: done, 1 warning(s)" in checks(wiki, "links", "--run", run).stdout
    assert wiki["lychee_calls"].exists(), "the old progress was discarded, not continued"
    data = json.loads((cache / "lychee.json").read_text(encoding="utf-8"))
    assert data["findings"] == [f"{PAGE}: https://example.com/new (404 Not Found)"]


def test_lychee_or_markdownlint_that_never_ran_is_a_warning_not_a_pass(wiki):
    quiet_orphans(wiki)
    (wiki["dir"].parent / "bin" / "lychee").unlink()
    _, run = start(wiki)
    assert "LINKS: done" in checks(wiki, "links", "--run", run).stdout
    checks(wiki, "style", "--run", run, stdin="npx: command not found\n")
    resp, code = drive(wiki, "done", run, "--step", "link-and-style-checks",
                       "--outcome", "checked", "--token", _token("quality-checks.md"))
    assert code == 0, resp
    assert resp["lists"]["warnings"] == ["lychee (1)", "markdownlint-cli2 (1)"]
    body = checks(wiki, "pr-body", "--run", run).stdout
    assert "lychee is not installed" in body
    assert "markdownlint-cli2 did not run: npx: command not found" in body


def test_no_warnings_body(wiki):
    quiet_orphans(wiki)
    _, run = start(wiki)
    passed(wiki, run)
    body = checks(wiki, "pr-body", "--run", run).stdout
    assert "Quality checks ran with no blocking errors and no warnings." in body
    assert "## Warnings" not in body
