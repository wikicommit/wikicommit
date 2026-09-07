"""The run record tree must stay invisible to everything else (Issue #790).

`.wikicommit/run/` holds `.md` files that are not wiki pages: no `type:`, no
`sources:`, no body at all. Several scripts walk `**/*.md`, and this tree rests
on the claim that none of those walks reaches it — the same claim
`tests/test_review_record_tree.py` fixes for `.wikicommit/review/`, checked here
because the ways it can break are silent.

Two of the assertions run the opposite way from that file, and the difference is
the point rather than an inconsistency. Review records are committed; run records
are not, and `wikicommit-merge` staging one would undo the whole storage
decision: a file would land in the PR of every run, and because deleting a file
in Git does not make it go away, retention could no longer be expressed at all.
"""

import subprocess
import sys
from pathlib import Path

from _publication import is_development_repository

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".wikicommit" / "scripts"

sys.path.insert(0, str(SCRIPTS))

from _wikilink import collect_entity_pages, collect_view_pages  # noqa: E402


def _wiki(tmp_path: Path) -> Path:
    """A repository with one real page and one run record."""
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
    record = tmp_path / ".wikicommit/run/20260907-104233-generate.md"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        "---\n"
        "skill: wikicommit-generate\n"
        "started_at: '2026-09-07T10:42:33+09:00'\n"
        "ended_at: ''\n"
        "model: claude-opus-5[1m]\n"
        "args:\n"
        "- https://example.invalid/never-fetch-me\n"
        "pages:\n"
        "- .wikicommit/entity/ja/Person/yamada-taro.md\n"
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


def test_argumentless_page_checks_ignore_the_run_tree(tmp_path):
    """Each of these walks **/*.md when given no arguments. A record has no
    `type:` and no `sources:`, so every one would be reported as a broken page
    and `wikicommit-merge` would block on files that are exactly as intended."""
    _wiki(tmp_path)
    for script in ("validate_frontmatter.py", "check_raw_html.py", "check_wikilinks.py"):
        result = _run(script, tmp_path)
        assert "run/" not in result.stdout, f"{script} reported a run record"
        assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"


def test_orphan_and_wanted_checks_ignore_the_run_tree(tmp_path):
    _wiki(tmp_path)
    for script in ("check_orphans.py", "check_wanted_pages.py"):
        result = _run(script, tmp_path)
        assert "run/" not in result.stdout, f"{script} reported a run record"


def test_convert_wikilinks_does_not_publish_records(tmp_path):
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
    assert not any("run" in Path(p).name for p in published), published


def test_the_tree_is_ignored_by_git_in_both_gitignores():
    """Both copies, and for different reasons: this repository's own runs write
    records too, and the template is what reaches a user's wiki. The template
    copy is compared line-additively (Issue #712), so an existing repository is
    told the line is missing rather than having it appear silently."""
    template = (REPO / ".claude/skills/wikicommit-init/scripts/templates/.gitignore").read_text(
        encoding="utf-8"
    )
    checked = [(template, "templates/.gitignore")]
    # The root .gitignore governs this repository's own runs, and is not part of
    # the published snapshot (dev/publication-scope.md §3). The template half is
    # the one that reaches a user's wiki, so it is checked everywhere
    # (Issue #788).
    if is_development_repository():
        checked.append(((REPO / ".gitignore").read_text(encoding="utf-8"), ".gitignore"))
    for text, name in checked:
        assert ".wikicommit/run/" in text.splitlines() or any(
            line.strip() == ".wikicommit/run/" for line in text.splitlines()
        ), f"{name} does not ignore the run record tree"


def test_merge_does_not_stage_the_run_tree():
    """The inverse of the review records, on purpose. Committing these would put
    a file in every run's PR and make retention inexpressible."""
    skill = (REPO / ".claude/skills/wikicommit-merge/SKILL.md").read_text(encoding="utf-8")
    add_line = next(line for line in skill.splitlines() if line.startswith("git add -- "))
    assert ".wikicommit/run/" not in add_line, add_line
    assert '".wikicommit/run/**/*.md"' not in skill, "run records must not be detected as changes"


def test_lychee_would_not_reach_a_recorded_argument():
    """A record's `args` can hold a URL. lychee keeps an explicit path argument
    for the review tree already; this asserts the run tree is outside it too."""
    skill = (REPO / ".claude/skills/wikicommit-merge/SKILL.md").read_text(encoding="utf-8")
    for line in skill.splitlines():
        if "lychee" in line and "--config" in line and line.strip().startswith("lychee"):
            assert ".wikicommit/run" not in line, line
            assert ".wikicommit/entity/" in line, line
            break
    else:
        raise AssertionError("no lychee invocation found in wikicommit-merge SKILL.md")
