"""Tests for merging same pages (Issue #1119): merge_pages.py, rewrite_merged_links.py
and the merge steps of wikicommit-generate's regeneration workflow.

The merge rests on a person's `same` decision; the names the kept page takes over
are recorded in `.wikicommit/relations.yml` so Pass 4 can tell them from aliases
a source supports; links to the absorbed pages are rewritten rather than
redirected at publish time.
"""

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS = REPO_ROOT / ".wikicommit" / "scripts"
MERGE = SCRIPTS / "merge_pages.py"
REWRITE = SCRIPTS / "rewrite_merged_links.py"
RECORD = SCRIPTS / "record_relation.py"
REMOVE = REPO_ROOT / ".claude" / "skills" / "wikicommit-remove" / "scripts" / "remove_page.py"
CHECKS = REPO_ROOT / ".claude" / "skills" / "wikicommit-generate" / "scripts" / "workflow_checks.py"

KEEP = ".wikicommit/entity/en/DefinedTerm/tool-use.md"
ABSORB = ".wikicommit/entity/en/DefinedTerm/function-calling.md"


def write(root: Path, rel: str, fm: str, body: str = "Body.\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm}---\n\n{body}", encoding="utf-8")


def run(root: Path, script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, cwd=root)


def wiki(root: Path, *, decided: bool = True) -> Path:
    (root / ".wikicommit").mkdir(parents=True, exist_ok=True)
    (root / ".wikicommit" / "config.yml").write_text("translation:\n  primary_lang: en\n", encoding="utf-8")
    write(root, KEEP, 'title: "Tool use"\ntype: "schema:DefinedTerm"\nlang: en\naliases: ["Tool calling"]\n'
          "sources:\n  - type: url\n    url: https://a.example/x\n    hash: sha256:aa\n")
    write(root, ABSORB, 'title: "Function calling"\ntype: "schema:DefinedTerm"\nlang: en\n'
          'aliases: ["Function call"]\n'
          "sources:\n  - type: url\n    url: https://a.example/x\n    hash: sha256:aa\n"
          "  - type: url\n    url: https://b.example/y\n    hash: sha256:bb\n")
    write(root, ".wikicommit/entity/ja/DefinedTerm/function-calling.md",
          'title: "関数呼び出し"\ntype: "schema:DefinedTerm"\nlang: ja\n'
          f"translated_from: {ABSORB}\nsource_commit: ''\n")
    write(root, ".wikicommit/entity/en/Person/x.md",
          'title: "X"\ntype: "schema:Person"\nlang: en\nproperties:\n  knowsAbout: "[[DefinedTerm/function-calling]]"\n',
          "Uses [[DefinedTerm/function-calling]] and [[DefinedTerm/tool-use]].\n")
    if decided:
        r = run(root, RECORD, "--relation", "same", "--page", "DefinedTerm/tool-use",
                "--page", "DefinedTerm/function-calling", "--today", "2026-10-01")
        assert r.returncode == 0, r.stdout
    return root


def test_plan_refuses_a_merge_no_person_decided(tmp_path):
    wiki(tmp_path, decided=False)
    result = run(tmp_path, MERGE, "plan", "--into", KEEP, "--absorb", ABSORB)
    assert result.returncode == 1
    assert "/wikicommit-relate" in result.stdout


def test_plan_lists_the_union_of_sources_and_the_names_taken_over(tmp_path):
    wiki(tmp_path)
    result = run(tmp_path, MERGE, "plan", "--into", KEEP, "--absorb", ABSORB)
    assert result.returncode == 0, result.stdout
    lines = result.stdout.splitlines()
    assert [ln for ln in lines if ln.startswith("SOURCE:")] == [
        "SOURCE: url https://a.example/x sha256:aa",
        "SOURCE: url https://b.example/y sha256:bb",
    ]
    assert [ln for ln in lines if ln.startswith("ALIAS:")] == [
        "ALIAS: Function calling", "ALIAS: Function call", "ALIAS: 関数呼び出し",
    ]
    assert f"TRANSLATION: .wikicommit/entity/ja/DefinedTerm/function-calling.md (of {ABSORB})" in lines


def test_plan_refuses_one_source_recorded_with_two_hashes(tmp_path):
    wiki(tmp_path)
    path = tmp_path / ABSORB
    path.write_text(path.read_text(encoding="utf-8").replace("sha256:aa", "sha256:old"), encoding="utf-8")
    result = run(tmp_path, MERGE, "plan", "--into", KEEP, "--absorb", ABSORB)
    assert result.returncode == 1
    assert "two different hashes" in result.stdout


def test_plan_refuses_a_translation_and_a_manual_source(tmp_path):
    wiki(tmp_path)
    result = run(tmp_path, MERGE, "plan", "--into", KEEP,
                 "--absorb", ".wikicommit/entity/ja/DefinedTerm/function-calling.md")
    assert result.returncode == 1
    path = tmp_path / ABSORB
    path.write_text(path.read_text(encoding="utf-8").replace(
        "sources:\n", "sources:\n  - type: manual\n    author: me\n    created_at: '2026-01-01'\n"), encoding="utf-8")
    result = run(tmp_path, MERGE, "plan", "--into", KEEP, "--absorb", ABSORB)
    assert result.returncode == 1
    assert "manual" in result.stdout


def test_a_full_merge_passes_the_check(tmp_path):
    wiki(tmp_path)
    # Pass 3 / 4 are an agent's work; stand in for them by writing the merged page.
    keep = tmp_path / KEEP
    keep.write_text(keep.read_text(encoding="utf-8").replace(
        'aliases: ["Tool calling"]', 'aliases: ["Tool calling", "Function calling", "Function call", "関数呼び出し"]'),
        encoding="utf-8")
    before = run(tmp_path, MERGE, "check", "--into", KEEP, "--absorb", ABSORB)
    assert before.returncode == 1

    assert run(tmp_path, MERGE, "record", "--into", KEEP, "--absorb", ABSORB, "--today", "2026-10-02").returncode == 0
    item = yaml.safe_load((tmp_path / ".wikicommit/relations.yml").read_text(encoding="utf-8"))[-1]
    assert item == {
        "relation": "same", "pages": ["DefinedTerm/tool-use", "DefinedTerm/function-calling"],
        "merged_into": "DefinedTerm/tool-use",
        "merged_aliases": ["Function calling", "Function call", "関数呼び出し"], "merged_at": "2026-10-02",
    }
    assert run(tmp_path, REMOVE, ABSORB, "--reason", "merged", "--merged-into", KEEP).returncode == 0
    rewrite = run(tmp_path, REWRITE)
    assert "SUMMARY: merged=1, pages=1, links=2" in rewrite.stdout, rewrite.stdout

    person = (tmp_path / ".wikicommit/entity/en/Person/x.md").read_text(encoding="utf-8")
    assert "[[DefinedTerm/function-calling]]" not in person
    assert 'knowsAbout: "[[DefinedTerm/tool-use]]"' in person

    after = run(tmp_path, MERGE, "check", "--into", KEEP, "--absorb", ABSORB)
    assert after.returncode == 0, after.stdout
    assert f"TOUCHED: {ABSORB}" in after.stdout
    assert "TOUCHED: .wikicommit/entity/ja/DefinedTerm/function-calling.md" in after.stdout


def test_check_fails_when_the_kept_page_lacks_a_merged_alias(tmp_path):
    wiki(tmp_path)
    run(tmp_path, MERGE, "record", "--into", KEEP, "--absorb", ABSORB)
    run(tmp_path, REMOVE, ABSORB, "--reason", "merged", "--merged-into", KEEP)
    run(tmp_path, REWRITE)
    result = run(tmp_path, MERGE, "check", "--into", KEEP, "--absorb", ABSORB)
    assert result.returncode == 1
    assert "merged aliases" in result.stdout


def test_rewrite_follows_chains_and_leaves_a_still_live_page_alone(tmp_path):
    write(tmp_path, ".wikicommit/entity/en/DefinedTerm/a.md", "title: A\nstatus: removed\n"
          "merged_into: .wikicommit/entity/en/DefinedTerm/b.md\n")
    write(tmp_path, ".wikicommit/entity/en/DefinedTerm/b.md", "title: B\nstatus: removed\n"
          "merged_into: .wikicommit/entity/en/DefinedTerm/c.md\n")
    write(tmp_path, ".wikicommit/entity/en/DefinedTerm/c.md", "title: C\n")
    # d is merged in en but still live in ja: links to it still resolve there.
    write(tmp_path, ".wikicommit/entity/en/DefinedTerm/d.md", "title: D\nstatus: removed\n"
          "merged_into: .wikicommit/entity/en/DefinedTerm/c.md\n")
    write(tmp_path, ".wikicommit/entity/ja/DefinedTerm/d.md", "title: D\n")
    write(tmp_path, ".wikicommit/entity/en/Person/p.md", "title: P\n",
          "[[DefinedTerm/a]] [[DefinedTerm/b]] [[DefinedTerm/d]]\n")
    result = run(tmp_path, REWRITE)
    text = (tmp_path / ".wikicommit/entity/en/Person/p.md").read_text(encoding="utf-8")
    assert "[[DefinedTerm/c]] [[DefinedTerm/c]] [[DefinedTerm/d]]" in text
    assert "still live" in result.stderr


def test_rewrite_dry_run_writes_nothing(tmp_path):
    write(tmp_path, ".wikicommit/entity/en/DefinedTerm/a.md", "title: A\nstatus: removed\n"
          "merged_into: .wikicommit/entity/en/DefinedTerm/c.md\n")
    write(tmp_path, ".wikicommit/entity/en/DefinedTerm/c.md", "title: C\n")
    write(tmp_path, ".wikicommit/entity/en/Person/p.md", "title: P\n", "[[DefinedTerm/a]]\n")
    result = run(tmp_path, REWRITE, "--dry-run")
    assert "REWRITTEN:" in result.stdout
    assert "[[DefinedTerm/a]]" in (tmp_path / ".wikicommit/entity/en/Person/p.md").read_text(encoding="utf-8")


def _run_record(root: Path, args: list[str], log: list[dict]) -> Path:
    path = root / "run.md"
    path.write_text("---\n" + yaml.safe_dump({"args": args, "driver": {"log": log}}) + "---\n", encoding="utf-8")
    return path


def test_merge_ready_only_after_the_kept_page_was_rebuilt(tmp_path):
    args = ["--regenerate", KEEP, "--merge", ABSORB]
    rebuilt = [{"step": "pass4-review", "item": KEEP, "outcome": "rebuilt"}]
    failed = [{"step": "pass4-review", "item": KEEP, "outcome": "failed"}]
    assert run(tmp_path, CHECKS, "merge-ready", "--run", str(_run_record(tmp_path, args, rebuilt))).returncode == 0
    assert run(tmp_path, CHECKS, "merge-ready", "--run", str(_run_record(tmp_path, args, failed))).returncode == 1
    plain = _run_record(tmp_path, ["--regenerate", KEEP], rebuilt)
    assert run(tmp_path, CHECKS, "merge-ready", "--run", str(plain)).returncode == 1


def test_check_merge_delegates_to_merge_pages(tmp_path):
    wiki(tmp_path)
    shutil_tree = tmp_path / ".wikicommit" / "scripts"
    shutil_tree.symlink_to(SCRIPTS.resolve(), target_is_directory=True)
    record = _run_record(tmp_path, ["--regenerate", KEEP, "--merge", ABSORB], [])
    result = run(tmp_path, CHECKS, "check-merge", "--run", str(record))
    assert result.returncode == 1
    assert "no merge record" in result.stdout
