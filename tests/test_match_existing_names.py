"""Tests for .wikicommit/scripts/match_existing_names.py (Issue #1096).

Pass 2c used to set `action: update` only on a same-type, same-slug page, so a
source that called a concept by a name an existing page carried as an alias
got a second page. These tests pin the matching side: exact (normalized)
string equality against title and aliases, same type only for SAME, and the
two cases that must not become an update — a match on another type, and a
name several same-type pages answer to.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".wikicommit" / "scripts" / "match_existing_names.py"


def write_page(root: Path, lang: str, type_name: str, slug: str, frontmatter: str) -> None:
    path = root / ".wikicommit" / "entity" / lang / type_name / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\nBody.\n", encoding="utf-8")


def write_config(root: Path, primary_lang: str = "en") -> None:
    (root / ".wikicommit").mkdir(parents=True, exist_ok=True)
    (root / ".wikicommit" / "config.yml").write_text(
        f"translation:\n  primary_lang: {primary_lang}\n  targets: []\n", encoding="utf-8"
    )


def run(root: Path, entities: list, *args: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=json.dumps(entities, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.splitlines()


def test_an_alias_of_a_same_type_page_is_same(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "en", "DefinedTerm", "tool-use-design-pattern",
        'title: "Tool use design pattern"\naliases: ["Function calling"]\n',
    )
    lines = run(tmp_path, [{"title": "function  CALLING", "type": "schema:DefinedTerm"}])
    assert lines[0] == (
        'SAME: 0 "function  CALLING" -> .wikicommit/entity/en/DefinedTerm/tool-use-design-pattern.md '
        '(matched alias "Function calling")'
    )
    assert lines[-1] == "SUMMARY: entities=1, same=1, ambiguous=0, other_type=0"


def test_a_title_match_is_same(tmp_path):
    write_config(tmp_path, "ja")
    write_page(tmp_path, "ja", "Person", "yamada-taro", 'title: "山田太郎"\n')
    lines = run(tmp_path, [{"title": "山田太郎", "type": "schema:Person"}])
    assert lines[0].startswith('SAME: 0 "山田太郎" -> .wikicommit/entity/ja/Person/yamada-taro.md (matched title')


def test_a_match_on_another_type_is_not_same(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "en", "SoftwareApplication", "claude-code", 'title: "Claude Code"\n')
    lines = run(tmp_path, [{"title": "Claude Code", "type": "schema:DefinedTerm"}])
    assert lines[0] == (
        'OTHER_TYPE: 0 "Claude Code" -> .wikicommit/entity/en/SoftwareApplication/claude-code.md '
        "(type SoftwareApplication, not DefinedTerm)"
    )
    assert not any(line.startswith("SAME:") for line in lines)


def test_a_name_two_same_type_pages_answer_to_is_ambiguous(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "en", "DefinedTerm", "function-calling", 'title: "Function calling"\n')
    write_page(
        tmp_path, "en", "DefinedTerm", "tool-use-design-pattern",
        'title: "Tool use design pattern"\naliases: ["Function calling"]\n',
    )
    lines = run(tmp_path, [{"title": "Function calling", "type": "schema:DefinedTerm"}])
    assert lines[0].startswith("AMBIGUOUS: 0 ")
    assert "function-calling.md" in lines[0] and "tool-use-design-pattern.md" in lines[0]
    assert not any(line.startswith("SAME:") for line in lines)


def test_meaning_alone_is_not_a_match(tmp_path):
    """Synonyms are a person's call (/wikicommit-relate), not this script's."""
    write_config(tmp_path)
    write_page(tmp_path, "en", "DefinedTerm", "function-calling", 'title: "Function calling"\n')
    lines = run(tmp_path, [{"title": "Tool calling", "type": "schema:DefinedTerm"}])
    assert lines[0] == 'NONE: 0 "Tool calling"'


def test_only_primary_lang_and_live_pages_are_read(tmp_path):
    write_config(tmp_path, "ja")
    write_page(tmp_path, "en", "Person", "yamada-taro", 'title: "Taro Yamada"\n')
    write_page(tmp_path, "ja", "Person", "gone", 'title: "Taro Yamada"\nstatus: removed\n')
    lines = run(tmp_path, [{"title": "Taro Yamada", "type": "schema:Person"}])
    assert lines[0] == 'NONE: 0 "Taro Yamada"'


def test_an_entitys_own_aliases_are_matched_too(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "en", "DefinedTerm", "function-calling", 'title: "Function calling"\n')
    lines = run(
        tmp_path,
        [{"title": "Tool use", "type": "schema:DefinedTerm", "aliases": ["Function calling"]}],
    )
    assert lines[0].startswith('SAME: 0 "Tool use" -> .wikicommit/entity/en/DefinedTerm/function-calling.md')


def test_an_alias_given_as_a_single_string_is_one_alias(tmp_path):
    """A bare string must not be iterated character by character."""
    write_config(tmp_path)
    write_page(tmp_path, "en", "DefinedTerm", "function-calling", 'title: "Function calling"\n')
    write_page(tmp_path, "en", "DefinedTerm", "c", 'title: "C"\n')
    lines = run(
        tmp_path,
        [{"title": "Tool use", "type": "schema:DefinedTerm", "aliases": "Function calling"}],
    )
    assert lines[0].startswith('SAME: 0 "Tool use" -> .wikicommit/entity/en/DefinedTerm/function-calling.md')
    assert not any("DefinedTerm/c.md" in line for line in lines)


def test_stdin_that_is_not_a_list_is_an_error(tmp_path):
    write_config(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input="{}", capture_output=True, text=True, cwd=tmp_path
    )
    assert result.returncode == 2
