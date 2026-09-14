"""The guides tree must stay invisible to the page scans (Issue #846).

`.wikicommit/guides/` holds `.md` files that are not wiki pages: no frontmatter
at all, no `type:`, no `sources:`, and links out to github.com. Several scripts
walk `**/*.md`, and putting a new tree of `.md` under `.wikicommit/` rests on the
claim that every one of those walks is scoped to a tree that is not this one.

That claim was checked by hand when the tree was introduced. This file keeps it
checked, for the same reason `test_review_record_tree.py` exists: every way it
can break is silent.

- `validate_frontmatter.py` / `check_raw_html.py` / `check_wikilinks.py` would
  report a guide as a malformed page, and `wikicommit-merge` would block on a
  file that is exactly what it should be.
- `collect_entity_pages()` widening to include them would make every guide an
  orphan page in `check_orphans.py`, index them in `search_index.py`, and — the
  worst of the three — have `convert_wikilinks.py` publish WikiCommit's own
  setup instructions to the reader-facing site.

A guide is also the first distributed `.md` under `.wikicommit/` whose body is
mostly prose with external links, so a `lychee` invocation that lost its path
argument would start fetching github.com on every merge. That scoping lives in a
`wikicommit-merge` command line rather than in Python, so it is asserted here
against the Skill instructions — the same exception the review-record test makes.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".wikicommit" / "scripts"
TEMPLATE_GUIDES = REPO / ".claude/skills/wikicommit-init/scripts/templates/guides"

sys.path.insert(0, str(SCRIPTS))

from _wikilink import collect_entity_pages, collect_view_pages  # noqa: E402


def _wiki(tmp_path: Path) -> Path:
    """A repository with one real page and the guides tree as init would write it."""
    page = tmp_path / ".wikicommit/entity/ja/Person/yamada-taro.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        'title: "T"\n'
        "lang: ja\n"
        'type: "schema:Person"\n'
        "review_status: pending\n"
        "sources:\n"
        "  - type: url\n"
        "    url: https://example.com/a\n"
        "    hash: sha256:cd34\n"
        "---\n"
        "\n"
        "本文。\n",
        encoding="utf-8",
    )
    schema = tmp_path / ".wikicommit/schema/default.md"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text(
        "---\n"
        "wikicommit:\n"
        "  frontmatter:\n"
        "    required: [title, lang, type, sources]\n"
        "  granularity: []\n"
        "---\n",
        encoding="utf-8",
    )
    guides = tmp_path / ".wikicommit/guides"
    guides.mkdir(parents=True, exist_ok=True)
    for template in sorted(TEMPLATE_GUIDES.glob("*.md")):
        (guides / template.name).write_text(
            template.read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _run(script: str, tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=tmp_path, check=False,
    )


def test_the_shelf_is_stocked_and_prose_names_what_is_on_it():
    """An empty shelf is the failure mode Issue #553 names; this one started stocked.

    Exact equality rather than "at least one" is deliberate. Three places name the
    guides in prose and none of them is generated from this directory, so adding or
    renaming one has to be a deliberate edit that walks past them; the message says
    where. Without that, the tree grows and the prose keeps advertising one file.
    """
    assert sorted(p.name for p in TEMPLATE_GUIDES.glob("*.md")) == [
        "applying-entity-policy-to-existing-pages.md",
        "enabling-comments.md",
    ], (
        "adding or renaming a guide? three places name them in prose and none is "
        "generated from this directory: _GUIDES_STEP in "
        ".claude/skills/wikicommit-init/scripts/print_next_steps.py, the 'Guides' "
        "section of README.md, and the '手順書（Guides）' section of README_ja.md."
    )


def test_collect_entity_pages_does_not_see_guides(tmp_path, monkeypatch):
    _wiki(tmp_path)
    monkeypatch.chdir(tmp_path)
    pages = collect_entity_pages() + collect_view_pages()
    assert [p.as_posix() for p in pages] == [".wikicommit/entity/ja/Person/yamada-taro.md"]


def test_argumentless_page_checks_ignore_the_guides_tree(tmp_path):
    """Each of these walks **/*.md when given no arguments."""
    _wiki(tmp_path)
    for script in ("validate_frontmatter.py", "check_raw_html.py", "check_wikilinks.py"):
        result = _run(script, tmp_path)
        assert "guides/" not in result.stdout, f"{script} reported a guide"
        assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"


def test_orphan_and_wanted_checks_ignore_the_guides_tree(tmp_path):
    _wiki(tmp_path)
    for script in ("check_orphans.py", "check_wanted_pages.py"):
        result = _run(script, tmp_path)
        assert "guides/" not in result.stdout, f"{script} reported a guide"


def test_convert_wikilinks_does_not_publish_guides(tmp_path):
    """Guides are WikiCommit's instructions to the operator, never reader-facing content."""
    _wiki(tmp_path)
    (tmp_path / ".wikicommit" / "config.yml").write_text(
        "translation:\n  targets: []\n  primary_lang: ja\n", encoding="utf-8"
    )
    result = _run(
        "convert_wikilinks.py", tmp_path,
        "--source", ".wikicommit/entity", "--output", "content",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    published = sorted(p.as_posix() for p in (tmp_path / "content").rglob("*.md"))
    assert not any("guides" in p for p in published), published


def test_merge_skill_keeps_lychee_scoped_to_a_path():
    """A bare `lychee --config .lychee.toml` would crawl the guides' external links."""
    skill = (REPO / ".claude/skills/wikicommit-merge/SKILL.md").read_text(encoding="utf-8")
    for line in skill.splitlines():
        if "lychee" not in line or "--config" not in line:
            continue
        after = line.split("--config", 1)[1]
        assert ".wikicommit/" in after, f"lychee invoked without a path argument: {line}"
        break
    else:
        # Without this, rewording or removing the invocation makes the loop body never
        # run and the test pass having checked nothing — the same for/else guard
        # test_review_record_tree.py uses on the very same line.
        raise AssertionError("no lychee invocation found in wikicommit-merge SKILL.md")
