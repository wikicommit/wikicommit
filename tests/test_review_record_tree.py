"""The review record tree must stay invisible to the entity-tree scans (Issue #750).

`.wikicommit/review/` holds `.md` files that are not wiki pages: they have no
`type:`, no `sources:`, no body to speak of, and their frontmatter carries a
`source_file` that can be a URL. Several scripts walk `**/*.md`, and the whole
design rests on the claim that every one of those walks is scoped to a tree
that is not this one.

That claim was checked once by hand when the tree was introduced. This file
keeps it checked, because the ways it can break are all silent:

- `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` would
  report every record as a malformed page, and `wikicommit-merge` would block
  on records that are exactly what they should be.
- `collect_entity_pages()` widening to include them would make every record a
  page in `check_orphans.py`, `search_index.py` and `convert_wikilinks.py` —
  and `convert_wikilinks.py` would publish the review records to the site.
- `lychee` losing its path argument would re-fetch every `source_file` URL in
  the whole accumulated history on every single merge.

The last one is the reason this file also asserts on the Skill instructions
rather than on Python alone: that scoping lives in a `wikicommit-merge` command
line, and nothing else would notice it being dropped.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".wikicommit" / "scripts"

sys.path.insert(0, str(SCRIPTS))

from _wikilink import collect_entity_pages, collect_view_pages  # noqa: E402


def _wiki(tmp_path: Path) -> Path:
    """A repository with one real page and one review record."""
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
    record = tmp_path / ".wikicommit/review/entity/ja/Person/yamada-taro/20260905-142233-ai.md"
    record.parent.mkdir(parents=True, exist_ok=True)
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
    record.write_text(
        "---\n"
        "page: .wikicommit/entity/ja/Person/yamada-taro.md\n"
        "kind: ai\n"
        "stage: generate-pass4\n"
        "model: claude-opus-5[1m]\n"
        "result: pass\n"
        "findings:\n"
        "  - round: 1\n"
        "    type: MISSING_SOURCE\n"
        "    source_file: https://example.invalid/never-fetch-me\n"
        "---\n",
        encoding="utf-8",
    )
    return tmp_path


def _run(script: str, tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=tmp_path, check=False,
    )


def test_collect_entity_pages_does_not_see_records(tmp_path, monkeypatch):
    _wiki(tmp_path)
    monkeypatch.chdir(tmp_path)
    pages = collect_entity_pages() + collect_view_pages()
    assert [p.as_posix() for p in pages] == [".wikicommit/entity/ja/Person/yamada-taro.md"]


def test_argumentless_page_checks_ignore_the_record_tree(tmp_path):
    """Each of these walks **/*.md when given no arguments."""
    _wiki(tmp_path)
    for script in ("validate_frontmatter.py", "check_raw_html.py", "check_wikilinks.py"):
        result = _run(script, tmp_path)
        assert "review/" not in result.stdout, f"{script} reported a review record"
        assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"


def test_orphan_and_wanted_checks_ignore_the_record_tree(tmp_path):
    _wiki(tmp_path)
    for script in ("check_orphans.py", "check_wanted_pages.py"):
        result = _run(script, tmp_path)
        assert "review/" not in result.stdout, f"{script} reported a review record"


def test_search_index_does_not_index_records(tmp_path):
    """A record's findings quote the page's defects; they must not be searchable content."""
    _wiki(tmp_path)
    build = _run("search_index.py", tmp_path, "build")
    if build.returncode != 0:
        import pytest
        pytest.skip(f"search index unavailable: {build.stdout} {build.stderr}")
    result = _run("search_index.py", tmp_path, "query", "MISSING_SOURCE")
    assert "review/" not in result.stdout


def test_convert_wikilinks_does_not_publish_records(tmp_path):
    """Records are visible in the repository, but never on the published site."""
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
    assert not any("review" in p for p in published), published


def test_lychee_stays_scoped_in_the_merge_skill():
    """An unscoped run would re-fetch every recorded source_file URL on every merge."""
    skill = (REPO / ".claude/skills/wikicommit-merge/SKILL.md").read_text(encoding="utf-8")
    for line in skill.splitlines():
        if "lychee" in line and "--config" in line and line.strip().startswith("lychee"):
            assert ".wikicommit/entity/" in line, (
                "lychee must keep an explicit path argument; without one it would walk "
                "the review records and re-fetch their source_file URLs. Line: " + line
            )
            break
    else:
        raise AssertionError("no lychee invocation found in wikicommit-merge SKILL.md")


def test_merge_stages_the_record_tree():
    """Records that are never committed are indistinguishable from reviews that never ran."""
    skill = (REPO / ".claude/skills/wikicommit-merge/SKILL.md").read_text(encoding="utf-8")
    assert '".wikicommit/review/**/*.md"' in skill, "review records are not detected as changes"
    assert "git add -- " in skill
    add_line = next(line for line in skill.splitlines() if line.startswith("git add -- "))
    assert ".wikicommit/review/" in add_line, add_line


def test_records_are_not_wiki_pages_in_the_changed_md_list():
    """They would fail every per-file quality check if they were."""
    skill = (REPO / ".claude/skills/wikicommit-merge/SKILL.md").read_text(encoding="utf-8")
    marker = "1. Obtain **`<changed .md files>`**:"
    body = skill[skill.index(marker): skill.index(marker) + 400]
    assert ".wikicommit/review/" not in body, (
        "review records must not enter <changed .md files>"
    )
