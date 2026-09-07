"""Tests for .wikicommit/scripts/check_recurring_characters.py (Issue #560)"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".wikicommit" / "scripts" / "check_recurring_characters.py"
TEMPLATE_SCRIPT = (
    REPO_ROOT
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts"
    / "check_recurring_characters.py"
)


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_work(root: Path, lang: str, slug: str, characters: list[str], type_name: str = "ShortStory") -> Path:
    """Write a work page whose properties.character holds the given values."""
    entries = "".join(f"    - {value}\n" for value in characters)
    return _write(
        root, lang, type_name, slug,
        f'title: "{slug}"\n'
        f"lang: {lang}\n"
        f'type: "schema:{type_name}"\n'
        "properties:\n"
        f"  character:\n{entries}",
    )


def write_person(root: Path, lang: str, slug: str, title: str, extra: str = "") -> Path:
    return _write(
        root, lang, "Person", slug,
        f'title: "{title}"\nlang: {lang}\ntype: "schema:Person"\n{extra}',
    )


def _write(root: Path, lang: str, type_name: str, slug: str, frontmatter: str) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\nBody.\n", encoding="utf-8")
    return page


# ── Nothing to report ────────────────────────────────────────────────────────

def test_no_wiki_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: recurring=0" in result.stdout


def test_single_work_appearance_is_not_recurring(tmp_path):
    """The one-work protagonist axis is Person.md's call at generation time, not this script's."""
    write_work(tmp_path, "it", "federigo-and-the-falcon", ["Federigo degli Alberighi"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout
    assert "Federigo" not in result.stdout


def test_wikilinked_value_is_not_reported(tmp_path):
    """A WikiLinked character is precisely what the rule asks for."""
    write_work(tmp_path, "it", "story-a", ["[[Person/saladin]]"])
    write_work(tmp_path, "it", "story-b", ["[[Person/saladin]]"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout


# ── RECURRING ────────────────────────────────────────────────────────────────

def test_name_in_two_works_without_a_person_page_is_recurring(tmp_path):
    for slug in ("calandrino-and-the-heliotrope", "calandrino-and-the-stolen-pig"):
        write_work(tmp_path, "it", slug, ["Calandrino", "Bruno"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=2" in result.stdout
    assert 'RECURRING: "Calandrino" appears as plain text in 2 work(s)' in result.stdout
    assert "ShortStory/calandrino-and-the-heliotrope" in result.stdout


def test_translations_of_one_work_count_once(tmp_path):
    """Three language versions of one story are one work, not three."""
    for lang in ("it", "en", "ja"):
        write_work(tmp_path, lang, "calandrino-and-the-heliotrope", ["Calandrino"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout


def test_recurrence_spans_work_types(tmp_path):
    """A character shared by a ShortStory and a Book recurs just the same."""
    write_work(tmp_path, "it", "a-tale", ["Calandrino"], type_name="ShortStory")
    write_work(tmp_path, "it", "the-collection", ["Calandrino"], type_name="Book")
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=1" in result.stdout


def test_names_are_matched_after_normalization(tmp_path):
    write_work(tmp_path, "it", "story-a", ["Ser  Ciappelletto"])
    write_work(tmp_path, "it", "story-b", ["ser ciappelletto"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=1" in result.stdout


def test_removed_work_is_not_counted(tmp_path):
    write_work(tmp_path, "it", "story-a", ["Calandrino"])
    _write(
        tmp_path, "it", "ShortStory", "story-b",
        'title: "story-b"\nlang: it\ntype: "schema:ShortStory"\n'
        "status: removed\nproperties:\n  character:\n    - Calandrino\n",
    )
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout


# ── Names that already have a page ───────────────────────────────────────────
#
# These are check_unlinked_entity_mentions.py's finding (Issue #561), not this
# script's — page existence is read here only to keep them off the promotion
# list, so the assertions are all "not reported".

def test_name_with_an_existing_person_page_is_not_reported(tmp_path):
    write_person(tmp_path, "it", "saladin", "Saladino")
    write_work(tmp_path, "it", "story-a", ["Saladino"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout
    assert "Saladino" not in result.stdout


def test_existing_page_keeps_a_recurring_name_off_the_list(tmp_path):
    """A name with a page is never reported as one to create, however often it recurs."""
    write_person(tmp_path, "it", "saladin", "Saladino")
    write_work(tmp_path, "it", "story-a", ["Saladino"])
    write_work(tmp_path, "it", "story-b", ["Saladino"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout


def test_person_page_in_another_language_still_counts_as_existing(tmp_path):
    """Slugs are language-neutral, so a page in any language answers the name."""
    write_person(tmp_path, "en", "saladin", "Saladino")
    write_work(tmp_path, "it", "story-a", ["Saladino"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout


def test_alias_answers_the_name(tmp_path):
    """A page filed under a fuller form of the name still answers the plain string.

    Matching titles only would report RECURRING here, i.e. "write a page" for a
    person who already has one — the duplicate check_wanted_pages.py's
    TYPE_MISMATCH split exists to prevent, and one check_orphans.py would not
    catch either (the two pages differ in title).
    """
    write_person(
        tmp_path, "it", "ser-ciappelletto", "Ser Ciappelletto",
        extra='aliases: ["Ciappelletto"]\n',
    )
    write_work(tmp_path, "it", "story-a", ["Ciappelletto"])
    write_work(tmp_path, "it", "story-b", ["Ciappelletto"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=0" in result.stdout
    assert "Ciappelletto" not in result.stdout


def test_non_string_aliases_are_skipped(tmp_path):
    write_person(tmp_path, "it", "saladin", "Saladino", extra="aliases: 42\n")
    write_work(tmp_path, "it", "story-a", ["Calandrino"])
    write_work(tmp_path, "it", "story-b", ["Calandrino"])
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: recurring=1" in result.stdout


def test_removed_person_page_does_not_answer_the_name(tmp_path):
    write_person(tmp_path, "it", "saladin", "Saladino", extra="status: removed\n")
    write_work(tmp_path, "it", "story-a", ["Saladino"])
    write_work(tmp_path, "it", "story-b", ["Saladino"])
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=1" in result.stdout


# ── Robustness ───────────────────────────────────────────────────────────────

def test_scalar_character_value_is_read(tmp_path):
    for slug in ("story-a", "story-b"):
        _write(
            tmp_path, "it", "ShortStory", slug,
            f'title: "{slug}"\nlang: it\ntype: "schema:ShortStory"\n'
            'properties:\n  character: "Calandrino"\n',
        )
    result = run(cwd=tmp_path)
    assert "SUMMARY: recurring=1" in result.stdout


def test_empty_and_non_string_values_are_skipped(tmp_path):
    for slug in ("story-a", "story-b"):
        _write(
            tmp_path, "it", "ShortStory", slug,
            f'title: "{slug}"\nlang: it\ntype: "schema:ShortStory"\n'
            'properties:\n  character:\n    - ""\n    - 42\n',
        )
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: recurring=0" in result.stdout


def test_page_without_properties_block_is_skipped(tmp_path):
    _write(tmp_path, "it", "ShortStory", "story-a", 'title: "a"\nlang: it\ntype: "schema:ShortStory"\n')
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: recurring=0" in result.stdout


def test_index_pages_are_skipped(tmp_path):
    _write(
        tmp_path, "it", "ShortStory", "index",
        'title: "ShortStory"\nlang: it\ntype: "schema:ShortStory"\n'
        "properties:\n  character:\n    - Calandrino\n",
    )
    write_work(tmp_path, "it", "story-a", ["Calandrino"])
    write_work(tmp_path, "it", "story-b", ["Calandrino"])
    result = run(cwd=tmp_path)
    # Only the two real works count; the index page contributes nothing.
    assert "ShortStory/index" not in result.stdout
    assert "SUMMARY: recurring=1" in result.stdout


# ── Distribution ─────────────────────────────────────────────────────────────

def test_template_copy_matches(tmp_path):
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
