"""wikicommit-translate driven by skill_workflow.py (Issue #1194).

The third Skill on the engine: a loop over (source page, target language) pairs,
each ending in three writes — the translation, its `source_commit` write-back and
its `translate-check` review record. These run the real `workflow.yaml` and
`workflow_checks.py` in a scratch wiki, because what has to hold is the claim the
Skill makes: a pair is not complete until all three are on disk, and a run
stopped partway resumes from the pair it stopped at with nothing but the run path.
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
RULES = REPO / ".claude/skills/wikicommit-init/scripts/templates/review-rules.md"
TRANSLATE = REPO / ".claude/skills/wikicommit-translate"
WORKFLOW = ".claude/skills/wikicommit-translate/workflow.yaml"

sys.path.insert(0, str(SCRIPTS))


def _steps(workflow: dict):
    for step in workflow["steps"]:
        yield from step.get("steps", [step])


def _token(name: str) -> str:
    from record_run import read_pass_token

    return read_pass_token(TRANSLATE / "references" / name)


def page_text(title: str, lang: str = "ja", **extra) -> str:
    front = {"title": title, "lang": lang, "type": "schema:Thing",
             "review_status": "pending", **extra}
    return "---\n" + yaml.safe_dump(front, allow_unicode=True) + "---\n\nbody\n"


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
    shutil.copytree(TRANSLATE, work / ".claude" / "skills" / "wikicommit-translate",
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

    write(".wikicommit/entity/ja/Person/a.md", page_text("A"))
    write(".wikicommit/entity/ja/DefinedTerm/z.md", page_text("Z"))
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


def translate(wiki, source: str, lang: str, *, source_commit=None, result="pass",
              write=True) -> str:
    """Do what references/translate-page.md asks for one pair, on disk."""
    target = source.replace("/ja/", f"/{lang}/", 1)
    if write:
        commit = head(wiki, source) if source_commit is None else source_commit
        wiki["write"](target, page_text(
            "T", lang=lang, translated_from=source, source_commit=commit,
            translated_at="2026-10-06", translated_by="m"))
    out = subprocess.run(
        [sys.executable, ".wikicommit/scripts/record_review.py", target, "--kind", "ai",
         "--stage", "translate-check", "--model", "m", "--result", result],
        cwd=wiki["dir"], env=wiki["env"], capture_output=True, text=True, check=False,
    )
    assert out.returncode == 0, out.stderr
    return target


def done_pair(wiki, run: str, item: str, outcome: str = "translated", *extra: str):
    return drive(wiki, "done", run, "--step", "translate", "--item", item,
                 "--outcome", outcome, "--token", _token("translate-page.md"), *extra)


# --- the definition -----------------------------------------------------------


def test_the_translate_workflow_points_at_files_that_exist_and_checks_each_token():
    from skill_workflow import load_workflow

    workflow = load_workflow(TRANSLATE / "workflow.yaml")
    assert workflow["skill"] == "wikicommit-translate"
    for step in _steps(workflow):
        if step.get("instructions"):
            assert (TRANSLATE / step["instructions"]).is_file(), step["id"]
            assert _token(Path(step["instructions"]).name), step["id"]
    pair = next(s for s in _steps(workflow) if s["id"] == "translate")
    assert pair.get("check"), "a pair must not be completed on the agent's word alone"
    cap = next(s for s in _steps(workflow) if s["id"] == "batch-cap")
    assert cap["non_interactive"] == "first-five"


def test_the_skill_md_is_the_workflow_loop():
    text = (TRANSLATE / "SKILL.md").read_text(encoding="utf-8")
    assert "skill_workflow.py start --workflow workflow.yaml" in text
    assert "skill_workflow.py next <run>" in text
    assert "record_run.py start" not in text, "the workflow engine opens the run record now"
    assert "record_run.py end" not in text, "the workflow engine closes the run record now"


# --- preflight and collection -------------------------------------------------


def test_a_missing_rules_file_halts_before_anything_is_translated(wiki):
    (wiki["dir"] / ".wikicommit/review-rules.md").unlink()
    resp, run = start(wiki)
    assert resp["step"] is None and resp["state"] == "halted"
    assert "--no-overwrite" in front(wiki["dir"] / run)["halted_reason"]


def test_a_translation_given_as_the_page_halts(wiki):
    wiki["write"](".wikicommit/entity/en/Person/a.md",
                  page_text("A", lang="en", translated_from=".wikicommit/entity/ja/Person/a.md"))
    resp, run = start(wiki, "--arg", ".wikicommit/entity/en/Person/a.md")
    assert resp["state"] == "halted"
    assert "is itself a translation" in front(wiki["dir"] / run)["halted_reason"]


def test_no_target_language_halts(wiki):
    (wiki["dir"] / ".wikicommit/config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: []\n", encoding="utf-8")
    resp, run = start(wiki, "--arg", ".wikicommit/entity/ja/Person/a.md")
    assert resp["state"] == "halted"
    assert "No target language" in front(wiki["dir"] / run)["halted_reason"]


def test_single_page_mode_lists_the_named_targets_and_skips_its_own_language(wiki):
    resp, run = start(wiki, "--arg", ".wikicommit/entity/ja/Person/a.md",
                      "--arg=--lang", "--arg=ja")
    assert resp["step"] is None and resp["finished_because"] == "Nothing to translate"
    resp, run = start(wiki, "--arg", ".wikicommit/entity/ja/Person/a.md",
                      "--arg=--lang", "--arg=fr")
    assert resp["step"] == "translate"
    assert resp["item"] == ".wikicommit/entity/ja/Person/a.md -> fr"


def test_batch_mode_puts_the_glossary_first_and_includes_stale_pairs(wiki):
    # A stale translation: its source_commit is not the source page's HEAD.
    wiki["write"](".wikicommit/entity/en/Person/b.md", page_text(
        "B", lang="en", translated_from=".wikicommit/entity/ja/Person/b.md",
        source_commit="0" * 40))
    wiki["write"](".wikicommit/entity/ja/Person/b.md", page_text("B"))
    wiki["git"]("add", ".")
    wiki["git"]("commit", "-q", "-m", "b")
    _, run = start(wiki)
    lists = front(wiki["dir"] / run)["workflow"]["lists"]
    # Within a group the order is the path check_translation_status.py reported:
    # the translation page for a STALE line, the source page for an UNTRANSLATED one.
    assert lists["pairs"] == [
        ".wikicommit/entity/ja/DefinedTerm/z.md -> en",
        ".wikicommit/entity/ja/Person/b.md -> en",
        ".wikicommit/entity/ja/Person/a.md -> en",
    ]


def test_batch_mode_with_lang_lists_only_that_languages_pairs(wiki):
    (wiki["dir"] / ".wikicommit/config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en, zh]\n", encoding="utf-8")
    _, run = start(wiki, "--arg=--lang", "--arg=en")
    assert front(wiki["dir"] / run)["workflow"]["lists"]["pairs"] == [
        ".wikicommit/entity/ja/DefinedTerm/z.md -> en",
        ".wikicommit/entity/ja/Person/a.md -> en",
    ]
    # Without --lang, batch mode is unchanged: every target's pairs.
    _, run = start(wiki)
    pairs = front(wiki["dir"] / run)["workflow"]["lists"]["pairs"]
    assert sorted(pairs) == sorted(
        f".wikicommit/entity/ja/{p} -> {lang}"
        for p in ("DefinedTerm/z.md", "Person/a.md") for lang in ("en", "zh"))
    assert pairs[0].startswith(".wikicommit/entity/ja/DefinedTerm/")


def test_batch_mode_with_a_lang_outside_targets_halts(wiki):
    resp, run = start(wiki, "--arg=--lang", "--arg=fr")
    assert resp["step"] is None and resp["state"] == "halted"
    reason = front(wiki["dir"] / run)["halted_reason"]
    assert "fr is not in `targets`" in reason and "Name a page" in reason


def test_batch_mode_with_a_lang_outside_targets_still_refreshes_its_stale_translations(wiki):
    # A translation made in single-page mode (or under a target since removed):
    # check_translation_status.py reports it STALE whatever `targets` says.
    wiki["write"](".wikicommit/entity/fr/Person/a.md", page_text(
        "A", lang="fr", translated_from=".wikicommit/entity/ja/Person/a.md",
        source_commit="0" * 40))
    wiki["git"]("add", ".")
    wiki["git"]("commit", "-q", "-m", "fr")
    resp, run = start(wiki, "--arg=--lang", "--arg=fr")
    assert resp.get("state") != "halted", resp
    assert front(wiki["dir"] / run)["workflow"]["lists"]["pairs"] == [
        ".wikicommit/entity/ja/Person/a.md -> fr",
    ]


@pytest.mark.parametrize("interactive", [True, False])
def test_more_than_five_pairs_asks_or_takes_the_first_five(wiki, interactive):
    for i in range(6):
        wiki["write"](f".wikicommit/entity/ja/Person/p{i}.md", page_text(f"P{i}"))
    resp, run = start(wiki) if interactive else start(wiki, "--non-interactive")
    if interactive:
        assert resp["step"] == "batch-cap"
        resp, code = drive(wiki, "done", run, "--step", "batch-cap", "--answer", "first-five")
        assert code == 0
    assert resp["step"] == "translate"
    lists = front(wiki["dir"] / run)["workflow"]["lists"]
    assert len(lists["candidates"]) == 8 and lists["pairs"] == lists["candidates"][:5]
    assert lists["pairs"][0].startswith(".wikicommit/entity/ja/DefinedTerm/")


# --- the run ------------------------------------------------------------------


def test_a_pair_is_not_complete_until_page_write_back_and_review_record_are_on_disk(wiki):
    _, run = start(wiki, "--arg", ".wikicommit/entity/ja/Person/a.md")
    item = ".wikicommit/entity/ja/Person/a.md -> en"

    resp, code = done_pair(wiki, run, item)
    assert code == 1 and "review record" in resp["reason"], "nothing was done yet"

    # Written and reviewed, but source_commit not written back correctly.
    translate(wiki, ".wikicommit/entity/ja/Person/a.md", "en", source_commit="")
    resp, code = done_pair(wiki, run, item)
    assert code == 1 and "source_commit" in resp["reason"]

    target = wiki["dir"] / ".wikicommit/entity/en/Person/a.md"
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace("source_commit: ''",
                                   f"source_commit: {head(wiki, '.wikicommit/entity/ja/Person/a.md')}"),
                      encoding="utf-8")
    resp, code = done_pair(wiki, run, item)
    assert code == 0 and resp["step"] == "report", resp
    touched = front(wiki["dir"] / run)["workflow"]["touched"]
    assert ".wikicommit/entity/en/Person/a.md" in touched
    assert any(p.startswith(".wikicommit/review/entity/en/Person/a/") for p in touched)


def test_an_uncommitted_source_page_needs_an_empty_source_commit(wiki):
    wiki["write"](".wikicommit/entity/ja/Person/a.md", page_text("A2"))
    _, run = start(wiki, "--arg", ".wikicommit/entity/ja/Person/a.md")
    item = ".wikicommit/entity/ja/Person/a.md -> en"
    translate(wiki, ".wikicommit/entity/ja/Person/a.md", "en")  # writes HEAD's hash
    resp, code = done_pair(wiki, run, item)
    assert code == 1 and "uncommitted" in resp["reason"]


def test_a_stopped_batch_resumes_from_the_pair_it_stopped_at(wiki):
    """The whole run, interrupted between pairs: each resumption is a fresh `next`
    with nothing but the run path, and finished pairs are not handed out again."""
    _, run = start(wiki)
    first = ".wikicommit/entity/ja/DefinedTerm/z.md -> en"
    second = ".wikicommit/entity/ja/Person/a.md -> en"

    resp, _ = drive(wiki, "next", run)
    assert resp["step"] == "translate" and resp["item"] == first
    translate(wiki, ".wikicommit/entity/ja/DefinedTerm/z.md", "en")
    resp, code = done_pair(wiki, run, first)
    assert code == 0 and resp["item"] == second

    # A new session: only the run path survives.
    resp, _ = drive(wiki, "next", run)
    assert resp["step"] == "translate" and resp["item"] == second
    resp, code = done_pair(wiki, run, first)
    assert code == 1 and resp["accepted"] is False, "a finished pair cannot be done again"

    # The second pair fails review past the retry limit: nothing written.
    resp, code = done_pair(wiki, run, second, "discarded")
    assert code == 1, "no discarded record yet"
    translate(wiki, ".wikicommit/entity/ja/Person/a.md", "en", result="discarded", write=False)
    resp, code = done_pair(wiki, run, second, "discarded")
    assert code == 0 and resp["step"] == "report"
    assert not (wiki["dir"] / ".wikicommit/entity/en/Person/a.md").exists()
    assert (wiki["dir"] / ".wikicommit/entity/en/DefinedTerm/index.md").exists(), (
        "rebuild-index ran before the report"
    )

    resp, code = drive(wiki, "done", run, "--step", "report", "--outcome", "reported",
                       "--token", _token("completion-report.md"),
                       "--page", ".wikicommit/entity/en/DefinedTerm/z.md",
                       "--count", "translated=1", "--count", "failed=1")
    assert code == 0 and resp["finished"] is True
    record = front(wiki["dir"] / run)
    assert record["skill"] == "wikicommit-translate"
    assert record["ended_at"] and record["halted_reason"] == ""
    assert record["outcome"] == {"translated": 1, "failed": 1}
    assert record["pages"] == [".wikicommit/entity/en/DefinedTerm/z.md"]


def test_a_rules_version_mismatch_halts_the_run(wiki):
    _, run = start(wiki, "--arg", ".wikicommit/entity/ja/Person/a.md")
    resp, code = done_pair(wiki, run, ".wikicommit/entity/ja/Person/a.md -> en", "halted",
                           "--reason", "rules_version mismatch")
    assert code == 0 and resp["state"] == "halted"
    assert front(wiki["dir"] / run)["halted_reason"] == "translate: rules_version mismatch"


def test_an_unreadable_started_at_fails_the_pair_even_with_an_earlier_pass_record(wiki):
    """Without the run's start the check cannot tell this run's records from an
    earlier run's, so it fails instead of accepting every record on disk."""
    translate(wiki, ".wikicommit/entity/ja/Person/a.md", "en")  # an earlier run's pass
    _, run = start(wiki, "--arg", ".wikicommit/entity/ja/Person/a.md")
    record = wiki["dir"] / run
    text = record.read_text(encoding="utf-8")
    started = next(line for line in text.splitlines() if line.startswith("started_at:"))
    record.write_text(text.replace(started, "started_at: not-a-time", 1), encoding="utf-8")
    resp, code = done_pair(wiki, run, ".wikicommit/entity/ja/Person/a.md -> en")
    assert code == 1 and "started_at" in resp["reason"], resp
