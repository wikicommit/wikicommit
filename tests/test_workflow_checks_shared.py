"""The helpers the Skills' `workflow_checks.py` share live in one module (Issue #1219).

`.wikicommit/scripts/_workflow_checks.py` holds what every Skill's checks read the
same way — the run record and its state, a recorded answer, the run's start, the
review records written since — and `skill_workflow.run_state()` is the one place the
state key (and the old `driver:` key) is read. These tests pin five things:

- no Skill's `workflow_checks.py` carries its own copy of a shared helper, or its own
  reading of the state key;
- the shared module reads a record written under the old key;
- a wiki whose `.wikicommit/scripts/` predates the module stops every Skill at its
  first step with a pointer to `/wikicommit-update`, and a `when:` condition does not
  read the missing module as "skip this step";
- the bootstrap that loads the module has one shape in all four (Issue #1233), and a
  missing PyYAML stops it with exit 2 and a pointer to the dependency, not to
  `/wikicommit-update`;
- run directly, each sets its streams to UTF-8 before the bootstrap (Issue #1264),
  with the same streams, error handlers, encoding and swallowed exceptions as the
  engine's `use_utf8_streams()` (Issue #1273).
"""

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SKILLS = REPO / ".claude" / "skills"
SCRIPTS = SKILLS / "wikicommit-init" / "scripts" / "templates" / "scripts"
SHARED = SCRIPTS / "_workflow_checks.py"
SKILLS_WITH_CHECKS = ("wikicommit-generate", "wikicommit-merge",
                      "wikicommit-translate", "wikicommit-synthesize")

SHARED_HELPERS = ("read_run", "read_state", "listed", "list_of", "answer_of", "run_started",
                  "written_since", "git", "records_since", "review_records_since",
                  "review_record_dir", "cmd_select", "run")


def checks_path(skill: str) -> Path:
    return SKILLS / skill / "scripts" / "workflow_checks.py"


def defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_no_skill_keeps_its_own_copy_of_a_shared_helper(skill):
    # `read_state` in merge is a one-line projection of the shared `read_run`, kept
    # for its call sites; anything longer is a copy.
    own = defined_functions(checks_path(skill)) & set(SHARED_HELPERS)
    allowed = {"read_state"} if skill == "wikicommit-merge" else set()
    assert own <= allowed, f"{skill} defines {sorted(own - allowed)} itself"


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_the_state_key_is_not_read_outside_the_engine(skill):
    code = checks_path(skill).read_text(encoding="utf-8")
    assert '"driver"' not in code and "'driver'" not in code
    assert '("workflow"' not in code


def test_the_shared_module_reads_the_state_through_the_engine():
    code = SHARED.read_text(encoding="utf-8")
    assert "from skill_workflow import parse_porcelain_z, run_command, run_state" in code
    assert '"driver"' not in code and '"workflow"' not in code


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_no_skill_runs_a_child_without_the_shared_utf8_run(skill):
    """A child's output is read as UTF-8 through the engine's `run_command` (shared
    as `run`), whatever the locale says (Issue #1256); a Skill calling
    `subprocess` itself reads it with the locale's codec again."""
    tree = ast.parse(checks_path(skill).read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names} | {node.module for node in ast.walk(tree)
                                            if isinstance(node, ast.ImportFrom)}
    assert "subprocess" not in imported


@pytest.mark.parametrize("key", ["workflow", "driver"])
def test_read_run_accepts_the_current_and_the_old_state_key(tmp_path, key):
    record = tmp_path / "run.md"
    record.write_text(f"---\nskill: x\n{key}:\n  lists:\n    a: [one]\n---\n", encoding="utf-8")
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import _workflow_checks as w;"
            "r, s = w.read_run(sys.argv[2]); print(w.listed(s, 'a'))")
    result = subprocess.run([sys.executable, "-c", code, str(SCRIPTS), str(record)],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "['one']"


# --- a wiki older than the shared module ---------------------------------------


def old_wiki(tmp_path: Path, skill: str) -> tuple[Path, dict]:
    work = tmp_path / "wiki"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    shutil.copytree(SCRIPTS, work / ".wikicommit" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__", "_workflow_checks.py"))
    shutil.copytree(SKILLS / skill, work / ".claude" / "skills" / skill,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (work / ".wikicommit" / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n", encoding="utf-8")
    (work / ".wikicommit" / "review-rules.md").write_text("---\n---\n", encoding="utf-8")
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})
    return work, env


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_a_wiki_without_the_shared_module_stops_at_the_first_step(tmp_path, skill):
    work, env = old_wiki(tmp_path, skill)
    result = subprocess.run(
        [sys.executable, ".wikicommit/scripts/skill_workflow.py", "start",
         "--workflow", f".claude/skills/{skill}/workflow.yaml", "--model", "m", "--arg", "topic"],
        cwd=work, env=env, capture_output=True, text=True, check=False,
    )
    response = json.loads(result.stdout)
    assert response.get("step") is None, response
    assert "/wikicommit-update" in response.get("halted_reason", ""), response


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_a_missing_shared_module_is_not_read_as_no(tmp_path, skill):
    """Exit 1 from a `when:` condition means "skip this step"; a check that cannot run
    at all must not say that."""
    work, env = old_wiki(tmp_path, skill)
    result = subprocess.run(
        [sys.executable, str(work / ".claude" / "skills" / skill / "scripts" / "workflow_checks.py"),
         "--help"],
        cwd=work, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert "/wikicommit-update" in result.stdout


# --- the bootstrap that loads the shared module (Issue #1233) ---------------------
#
# The bootstrap cannot live in the module it loads, so each Skill carries its own; the
# names each imports differ, so the four are held to one shape rather than one string.


def bootstrap(skill: str) -> tuple[list[ast.stmt], int]:
    """The script's top-level statements and the position of the `try` importing
    `_workflow_checks`; the `sys.path.insert` statement is the one before it."""
    body = ast.parse(checks_path(skill).read_text(encoding="utf-8")).body
    for i, node in enumerate(body):
        if isinstance(node, ast.Try) and any(
            isinstance(s, ast.ImportFrom) and s.module == "_workflow_checks" for s in node.body
        ):
            assert i > 0, f"{skill} has no statement before the try importing _workflow_checks"
            return body, i
    raise AssertionError(f"{skill} has no try block importing _workflow_checks")


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_the_bootstrap_has_one_shape(skill):
    body, i = bootstrap(skill)
    path_insert, block = body[i - 1], body[i]
    reference_body, j = bootstrap(SKILLS_WITH_CHECKS[0])
    reference = reference_body[j]
    assert ast.unparse(path_insert) == \
        "sys.path.insert(0, str(Path.cwd() / '.wikicommit' / 'scripts'))"
    assert all(isinstance(s, (ast.Import, ast.ImportFrom)) for s in block.body)
    assert not block.orelse and not block.finalbody and len(block.handlers) == 1
    assert ast.unparse(block.handlers[0]) == ast.unparse(reference.handlers[0])
    assert ast.unparse(block.handlers[0].body[-1]) == "sys.exit(2)"


def utf8_streams(skill: str) -> ast.If:
    """The `if __name__ == "__main__":` before the bootstrap that sets the streams."""
    body, i = bootstrap(skill)
    for node in body[:i - 1]:
        if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'" \
                and "reconfigure" in ast.unparse(node):
            return node
    raise AssertionError(f"{skill} does not set its streams to UTF-8 before the bootstrap")


def reconfigure_shape(loop: ast.For) -> tuple:
    """What a `for stream, errors in (...): try: stream.reconfigure(...)` loop sets:
    the error handler of each stream (in any order), the encoding, the exceptions it swallows and
    what it does with them. Variable names are left out, so the four Skills' `_stream`
    and the engine's `stream` compare equal."""
    stream_var, errors_var = (t.id for t in loop.target.elts)
    pairs = {ast.unparse(pair.elts[0]): ast.literal_eval(pair.elts[1])
             for pair in loop.iter.elts}
    assert len(pairs) == len(loop.iter.elts), ast.unparse(loop.iter)
    assert not loop.orelse, ast.unparse(loop)
    (block,) = loop.body
    (statement,) = block.body
    call = statement.value
    assert ast.unparse(call.func) == f"{stream_var}.reconfigure", ast.unparse(call)
    keywords = {k.arg: k.value for k in call.keywords}
    assert set(keywords) == {"encoding", "errors"} and not call.args, ast.unparse(call)
    assert ast.unparse(keywords["errors"]) == errors_var, ast.unparse(call)
    (handler,) = block.handlers
    assert not block.orelse and not block.finalbody
    return (pairs, ast.literal_eval(keywords["encoding"]), ast.unparse(handler.type),
            [ast.unparse(s) for s in handler.body])


def engine_utf8_streams() -> ast.For:
    """The loop of `skill_workflow.use_utf8_streams()`, which the engine runs first."""
    tree = ast.parse((SCRIPTS / "skill_workflow.py").read_text(encoding="utf-8"))
    function = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "use_utf8_streams")
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # the docstring
    # Nothing but the loop: a stream set outside it would not be compared.
    (loop,) = body
    assert isinstance(loop, ast.For), ast.unparse(loop)
    return loop


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_the_streams_are_set_to_utf8_before_the_bootstrap(skill):
    """Run directly, nothing passes PYTHONIOENCODING (Issue #1264); the import's own
    error message is printed too, so the streams are set before it."""
    assert ast.unparse(utf8_streams(skill)) == ast.unparse(utf8_streams(SKILLS_WITH_CHECKS[0]))


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_the_streams_match_the_engine(skill):
    """The four blocks say they set the same streams and error handlers as
    `use_utf8_streams()` (Issue #1273): changing the engine's alone fails here rather
    than leaving the four behind. `resolve_source_cache_path.py`'s function of the same
    name differs on purpose and is not compared."""
    (loop,) = utf8_streams(skill).body
    assert reconfigure_shape(loop) == reconfigure_shape(engine_utf8_streams())


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_a_direct_run_writes_utf8_under_a_locale_that_is_not(tmp_path, skill):
    """`LC_ALL=C` without PYTHONIOENCODING: stdout would be ASCII, and a non-ASCII
    line raised UnicodeEncodeError at `print`. The bootstrap's own message, the first
    thing a script prints, carries a non-ASCII module error here."""
    scripts = tmp_path / "wiki" / ".wikicommit" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "_workflow_checks.py").write_text(
        "raise ImportError('.wikicommit/entity/ja/Person/山田.md')\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONIOENCODING"}
    env.update({"LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"})
    result = subprocess.run([sys.executable, str(checks_path(skill)), "--help"],
                            cwd=scripts.parent.parent, env=env, capture_output=True,
                            check=False)
    err = result.stderr.decode("utf-8", "replace")
    assert result.returncode == 2, err
    assert "山田.md" in result.stdout.decode("utf-8"), err


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_no_third_party_import_escapes_the_bootstrap(skill):
    """An import outside the `try` would fail with a traceback and exit 1."""
    body = ast.parse(checks_path(skill).read_text(encoding="utf-8")).body
    stdlib = set(sys.stdlib_module_names)
    for node in body:
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        for name in names:
            assert name.split(".")[0] in stdlib | {"__future__"}, f"{skill} imports {name}"


@pytest.mark.parametrize("skill", SKILLS_WITH_CHECKS)
def test_a_missing_pyyaml_points_at_the_dependency_not_at_update(tmp_path, skill):
    """Run directly (as `references/*.md` tell the agent to), with the shared module
    present but PyYAML unimportable: exit 2, and no pointer to `/wikicommit-update`,
    which would not install it."""
    work = tmp_path / "wiki"
    work.mkdir()
    shutil.copytree(SCRIPTS, work / ".wikicommit" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    script = checks_path(skill)
    code = ("import runpy, sys; sys.modules['yaml'] = None; "
            "sys.argv = [sys.argv[1], '--help']; runpy.run_path(sys.argv[0], run_name='__main__')")
    result = subprocess.run([sys.executable, "-c", code, str(script)],
                            cwd=work, capture_output=True, text=True, check=False)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "PyYAML" in result.stdout
    assert "/wikicommit-update" not in result.stdout
