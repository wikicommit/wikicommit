"""Tests for the view tree — second-order pages grounded in this wiki's own
pages rather than in an external document (Issue #675).

Two things are pinned here. First, that the scripts listed as *including* the
tree actually walk it: a view page has to be validated, linked to, searched,
indexed and published like any other page, and each of those is a separate
opt-in because `collect_entity_pages()` is scoped to one tree by design.

Second — and this is the half that would rot silently — that the scripts listed
as *excluding* it stay excluded. Those four are excluded for reasons that hold
regardless of what the tree contains: three read fields a view page does not
have (`properties:`, `type:`, `sources[].hash`), and `check_orphans.py` would
report every view page as an orphan, since one is unlinked the moment it is
written. If a later change swaps a `collect_entity_pages()` call for a
both-trees walk, nothing errors — the reports just gain findings nobody can act
on, which is exactly how a report gets ignored.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / ".wikicommit" / "scripts"

ENTITY_PAGE = """\
---
title: "山田太郎"
lang: ja
type: "schema:Person"
review_status: reviewed
sources:
  - type: manual
    author: tester
    created_at: "2026-09-01"
---

本文です。[[View/agent-loops]] を参照。
"""

VIEW_PAGE = """\
---
title: "エージェントループの実践"
lang: ja
kind: practice
review_status: pending
derived_from:
  - path: .wikicommit/entity/ja/Person/yamada-taro.md
    source_commit: ""
---

複数ページを突き合わせた読み。[[Person/yamada-taro]] を参照。
"""


def run(script: str, root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=root, check=False,
    )


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    (tmp_path / ".wikicommit").mkdir()
    (tmp_path / ".wikicommit" / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: []\n", encoding="utf-8"
    )
    schema = tmp_path / ".wikicommit" / "schema"
    schema.mkdir()
    (schema / "default.md").write_text(
        "---\nwikicommit:\n  frontmatter:\n    required: [title, lang, type, sources]\n---\n",
        encoding="utf-8",
    )
    (schema / "Person.md").write_text(
        '---\nwikicommit:\n  base: https://schema.org/Person\ntype: "schema:Person"\n---\n',
        encoding="utf-8",
    )
    entity = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    entity.mkdir(parents=True)
    (entity / "yamada-taro.md").write_text(ENTITY_PAGE, encoding="utf-8")
    view = tmp_path / ".wikicommit" / "view" / "ja"
    view.mkdir(parents=True)
    (view / "agent-loops.md").write_text(VIEW_PAGE, encoding="utf-8")
    return tmp_path


# ── Scripts that include the view tree ────────────────────────────────────────

def test_validate_frontmatter_accepts_a_view_page(wiki):
    result = run("validate_frontmatter.py", wiki)
    assert result.returncode == 0, result.stdout
    assert "2 files validated" in result.stdout


def test_validate_frontmatter_rejects_type_on_a_view_page(wiki):
    page = wiki / ".wikicommit" / "view" / "ja" / "agent-loops.md"
    page.write_text(VIEW_PAGE.replace("kind: practice", 'type: "schema:Person"'), encoding="utf-8")
    result = run("validate_frontmatter.py", wiki)
    assert result.returncode == 1
    assert "type" in result.stdout and "view" in result.stdout


def test_validate_frontmatter_rejects_sources_on_a_view_page(wiki):
    page = wiki / ".wikicommit" / "view" / "ja" / "agent-loops.md"
    page.write_text(
        VIEW_PAGE.replace("kind: practice", "sources:\n  - type: manual\n    author: t\n    created_at: \"2026-09-01\""),
        encoding="utf-8",
    )
    result = run("validate_frontmatter.py", wiki)
    assert result.returncode == 1
    assert "sources" in result.stdout


def test_validate_frontmatter_rejects_an_unknown_kind(wiki):
    page = wiki / ".wikicommit" / "view" / "ja" / "agent-loops.md"
    page.write_text(VIEW_PAGE.replace("kind: practice", "kind: essay"), encoding="utf-8")
    result = run("validate_frontmatter.py", wiki)
    assert result.returncode == 1
    assert "kind" in result.stdout


def test_validate_frontmatter_accepts_a_view_page_without_a_kind(wiki):
    """`kind` is optional on purpose: pages accumulating without one is the
    evidence that a kind is missing, so an absent field must not be an error."""
    page = wiki / ".wikicommit" / "view" / "ja" / "agent-loops.md"
    page.write_text(VIEW_PAGE.replace("kind: practice\n", ""), encoding="utf-8")
    result = run("validate_frontmatter.py", wiki)
    assert result.returncode == 0, result.stdout


def test_validate_frontmatter_rejects_a_nested_view_page(wiki):
    """A view page has no Type directory, so a nested path is not a view page
    whose type could not be read — it is misplaced."""
    nested = wiki / ".wikicommit" / "view" / "ja" / "Practice"
    nested.mkdir()
    (nested / "agent-loops.md").write_text(VIEW_PAGE, encoding="utf-8")
    result = run("validate_frontmatter.py", wiki)
    assert result.returncode == 1
    assert "<lang>/<slug>.md" in result.stdout


def test_check_wikilinks_resolves_links_in_both_directions(wiki):
    result = run("check_wikilinks.py", wiki)
    assert result.returncode == 0, result.stdout
    assert "0 errors" in result.stdout
    # Both pages were walked: the entity page links to the view page and back.
    assert "2 files checked" in result.stdout


def test_check_wanted_pages_does_not_report_an_existing_view_page(wiki):
    result = run("check_wanted_pages.py", wiki)
    assert "wanted=0" in result.stdout, result.stdout


def test_check_wanted_pages_reports_a_missing_view_page(wiki):
    page = wiki / ".wikicommit" / "entity" / "ja" / "Person" / "yamada-taro.md"
    page.write_text(ENTITY_PAGE.replace("View/agent-loops", "View/not-written"), encoding="utf-8")
    result = run("check_wanted_pages.py", wiki)
    assert "WANTED: View/not-written" in result.stdout


def test_check_derivation_freshness_walks_the_view_tree(wiki):
    result = run("check_derivation_freshness.py", wiki)
    # The fixture is not a git repository, so the per-entry git lookup fails and
    # the finding lands on stderr rather than as STALE. Either way the page was
    # named, which is the whole claim here: this tree is the script's subject
    # from Issue #675 on.
    assert "view/ja/agent-loops.md" in result.stdout + result.stderr


def test_rebuild_index_writes_a_per_language_view_index(wiki):
    result = run("rebuild_index.py", wiki)
    assert result.returncode == 0, result.stdout
    index = (wiki / ".wikicommit" / "view" / "ja" / "index.md").read_text(encoding="utf-8")
    assert "- [[View/agent-loops]]" in index
    # No `type:` — validate_frontmatter.py rejects one on a page in this tree.
    assert "type:" not in index
    assert "review_status: reviewed" in index


def test_rebuild_index_output_passes_validation(wiki):
    assert run("rebuild_index.py", wiki).returncode == 0
    result = run("validate_frontmatter.py", wiki)
    assert result.returncode == 0, result.stdout


def test_search_index_indexes_view_pages(wiki):
    assert run("search_index.py", wiki, "build").returncode == 0
    result = run("search_index.py", wiki, "query", "突き合わせ")
    assert "view/ja/agent-loops.md" in result.stdout
    assert "type=View" in result.stdout


def test_convert_wikilinks_publishes_the_view_tree_under_a_View_segment(wiki):
    result = run(
        "convert_wikilinks.py", wiki, "--source", ".wikicommit/entity/", "--output", "content/"
    )
    assert result.returncode == 0, result.stdout
    published = wiki / "content" / "ja" / "View" / "agent-loops.md"
    assert published.is_file()
    # The language stays the first segment, which is what the three Quartz
    # plugins reading it as a language depend on.
    assert published.read_text(encoding="utf-8").count("../Person/yamada-taro.md") == 1
    entity_out = (wiki / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "../View/agent-loops.md" in entity_out


def test_convert_wikilinks_skips_a_removed_view_page(wiki):
    page = wiki / ".wikicommit" / "view" / "ja" / "agent-loops.md"
    page.write_text(
        VIEW_PAGE.replace("kind: practice", 'status: removed\nremoved_at: "2026-09-01"'),
        encoding="utf-8",
    )
    run("convert_wikilinks.py", wiki, "--source", ".wikicommit/entity/", "--output", "content/")
    assert not (wiki / "content" / "ja" / "View" / "agent-loops.md").exists()


# ── Scripts that must NOT walk the view tree ─────────────────────────────────

@pytest.mark.parametrize(
    "script, reason",
    [
        # Reads `properties:`, which a view page has no notion of.
        ("check_recurring_characters.py", "properties"),
        ("check_unlinked_entity_mentions.py", "properties"),
        # Reads `type:`, which a view page deliberately does not carry.
        ("check_schema_coverage.py", "type"),
        ("check_installed_type_usage.py", "type"),
        # Matches against `sources[].hash`, which a view page does not have.
        ("reconcile_ingest_status.py", "sources"),
        # A view page is unlinked at birth, so every one would be an orphan.
        ("check_orphans.py", "orphan"),
    ],
)
def test_excluded_scripts_never_name_a_view_page(wiki, script, reason):
    result = run(script, wiki)
    assert "view/ja/agent-loops.md" not in result.stdout, (
        f"{script} walked the view tree; it is excluded because of {reason}\n{result.stdout}"
    )


def test_build_survey_view_excludes_the_view_tree_by_default(wiki):
    """Surveying a view page proposes analysing the analysis — the pages an
    angle would actually be grounded in are the entity pages underneath."""
    result = run("build_survey_view.py", wiki)
    # The view page gets no PAGE: record of its own. The entity page's outgoing
    # link to it still shows up under `links=` — a link is a link, and the graph
    # is built from every page's own body.
    assert "PAGE: View/agent-loops" not in result.stdout, result.stdout
    assert "PAGE: Person/yamada-taro" in result.stdout


def test_build_survey_view_includes_the_view_tree_on_request(wiki):
    result = run("build_survey_view.py", wiki, "--include-view")
    assert "PAGE: View/agent-loops" in result.stdout, result.stdout
