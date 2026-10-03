"""Tests for record_relation.py and check_name_collisions.py (Issue #1095).

The relation files are only worth writing if something reads them: the
collision detector must stop raising a pair a person has already decided
about, in any relation.
"""

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
RECORD = REPO_ROOT / ".wikicommit" / "scripts" / "record_relation.py"
COLLISIONS = REPO_ROOT / ".wikicommit" / "scripts" / "check_name_collisions.py"


def page(root: Path, lang: str, type_name: str, slug: str, fm: str) -> None:
    path = root / ".wikicommit" / "entity" / lang / type_name / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm}---\n\nBody.\n", encoding="utf-8")


def run(root: Path, script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, cwd=root)


def relations(root: Path) -> list:
    return yaml.safe_load((root / ".wikicommit" / "relations.yml").read_text(encoding="utf-8"))


def test_records_append_to_one_file(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "a", 'title: "A"\n')
    page(tmp_path, "en", "DefinedTerm", "b", 'title: "B"\n')
    page(tmp_path, "en", "DefinedTerm", "c", 'title: "C"\n')
    r1 = run(tmp_path, RECORD, "--relation", "same", "--page", "DefinedTerm/a", "--page", "DefinedTerm/b",
             "--today", "2026-10-01")
    assert r1.returncode == 0, r1.stdout
    path = tmp_path / ".wikicommit" / "relations.yml"
    path.write_text(path.read_text() + "# a person's comment\n", encoding="utf-8")
    r2 = run(tmp_path, RECORD, "--relation", "broader", "--broader", "DefinedTerm/a", "--page", "DefinedTerm/c",
             "--note", "C is a kind of A", "--today", "2026-10-01")
    assert r2.returncode == 0, r2.stdout
    assert "# a person's comment" in path.read_text()
    assert relations(tmp_path) == [
        {"relation": "same", "pages": ["DefinedTerm/a", "DefinedTerm/b"], "decided_at": "2026-10-01"},
        {"relation": "broader", "broader": "DefinedTerm/a", "pages": ["DefinedTerm/c"],
         "decided_at": "2026-10-01", "note": "C is a kind of A"},
    ]


def test_refuses_an_unknown_page_and_writes_nothing(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "a", 'title: "A"\n')
    result = run(tmp_path, RECORD, "--relation", "distinct", "--page", "DefinedTerm/a", "--page", "DefinedTerm/zz")
    assert result.returncode == 1
    assert not (tmp_path / ".wikicommit" / "relations.yml").exists()


def test_refuses_broader_without_the_containing_page(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "a", 'title: "A"\n')
    page(tmp_path, "en", "DefinedTerm", "b", 'title: "B"\n')
    result = run(tmp_path, RECORD, "--relation", "broader", "--page", "DefinedTerm/a", "--page", "DefinedTerm/b")
    assert result.returncode == 1


def test_refuses_to_append_to_a_broken_file(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "a", 'title: "A"\n')
    page(tmp_path, "en", "DefinedTerm", "b", 'title: "B"\n')
    path = tmp_path / ".wikicommit" / "relations.yml"
    path.write_text("relation: same\n", encoding="utf-8")
    result = run(tmp_path, RECORD, "--relation", "related", "--page", "DefinedTerm/a", "--page", "DefinedTerm/b")
    assert result.returncode == 1
    assert path.read_text() == "relation: same\n"


def test_collision_between_a_title_and_an_alias(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "function-calling", 'title: "Function calling"\n')
    page(tmp_path, "en", "DefinedTerm", "tool-use-design-pattern",
         'title: "Tool use design pattern"\naliases: ["function  CALLING"]\n')
    out = run(tmp_path, COLLISIONS).stdout.splitlines()
    assert out[0] == ('COLLISION: "Function calling" (en) — DefinedTerm/function-calling (title), '
                      "DefinedTerm/tool-use-design-pattern (alias)")
    assert out[-1] == "SUMMARY: collisions=1, judged_pairs_skipped=0, relations=0"


def test_a_broken_relations_file_raises_everything(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "agent", 'title: "Agent"\n')
    page(tmp_path, "en", "Concept", "user-agent", 'title: "User agent"\naliases: ["Agent"]\n')
    (tmp_path / ".wikicommit" / "relations.yml").write_text("{bad", encoding="utf-8")
    result = run(tmp_path, COLLISIONS)
    assert "COLLISION" in result.stdout and "WARNING" in result.stderr


def test_a_decided_pair_is_not_raised_again(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "agent", 'title: "Agent"\n')
    page(tmp_path, "en", "Concept", "user-agent", 'title: "User agent"\naliases: ["Agent"]\n')
    assert "COLLISION" in run(tmp_path, COLLISIONS).stdout
    run(tmp_path, RECORD, "--relation", "distinct", "--page", "DefinedTerm/agent", "--page", "Concept/user-agent")
    out = run(tmp_path, COLLISIONS).stdout.splitlines()
    assert out == ["SUMMARY: collisions=0, judged_pairs_skipped=1, relations=1"]


def test_same_type_title_clash_is_left_to_check_orphans(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "a", 'title: "Same"\n')
    page(tmp_path, "en", "DefinedTerm", "b", 'title: "Same"\n')
    assert run(tmp_path, COLLISIONS).stdout.startswith("SUMMARY: collisions=0")


def test_removed_pages_and_other_languages_do_not_collide(tmp_path):
    page(tmp_path, "en", "DefinedTerm", "a", 'title: "Name"\n')
    page(tmp_path, "en", "Person", "b", 'title: "Name"\nstatus: removed\n')
    page(tmp_path, "ja", "Person", "c", 'title: "Name"\n')
    assert run(tmp_path, COLLISIONS).stdout.startswith("SUMMARY: collisions=0")
