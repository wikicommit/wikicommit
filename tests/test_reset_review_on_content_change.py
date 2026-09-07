"""Tests for .wikicommit/scripts/reset_review_on_content_change.py (Issue #724).

The trust ladder's top rung (`review_status: reviewed`, plus the real name in
`reviewed_by`) claims a human read this text. Two write paths — `action: update`
in `wikicommit-generate` Pass 3 and `wikicommit-fix` — used to rewrite the prose
without moving that claim. This script demotes the page when, and only when, its
*content* changed relative to HEAD.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".wikicommit" / "scripts" / "reset_review_on_content_change.py"

ENTITY_PAGE = """\
---
title: "山田太郎"
lang: ja
type: "schema:Person"
tags: [engineer]
review_status: reviewed
reviewed_by: "octocat"
generated_at: "2026-01-01"
generated_by: "claude-opus-5"
generated_with: "0.1.0"
expires_at: "2027-06-21"
properties:
  jobTitle: "シニアエンジニア"
sources:
  - type: path
    path: raw/paper.pdf
    hash: sha256:abc123
---

山田太郎は CompanyA のシニアエンジニア。
"""

VIEW_PAGE = """\
---
title: "エージェントループの実践"
lang: ja
kind: practice
review_status: reviewed
reviewed_by: "octocat"
derived_from:
  - path: .wikicommit/entity/ja/Person/yamada-taro.md
    source_commit: abc123
---

複数の記述を突き合わせた読み。
"""


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    """A committed wiki holding one entity page and one view page."""
    entity = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    entity.mkdir(parents=True)
    (entity / "yamada-taro.md").write_text(ENTITY_PAGE, encoding="utf-8")

    view = tmp_path / ".wikicommit" / "view" / "ja"
    view.mkdir(parents=True)
    (view / "agent-loop.md").write_text(VIEW_PAGE, encoding="utf-8")

    for cmd in (
        ["git", "init", "-q", "."],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "T"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "init"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


ENTITY_REL = ".wikicommit/entity/ja/Person/yamada-taro.md"
VIEW_REL = ".wikicommit/view/ja/agent-loop.md"


# ── content changed → demote ────────────────────────────────────────────────

def test_body_change_resets_review_status_and_drops_reviewer(wiki):
    page = wiki / ENTITY_REL
    page.write_text(page.read_text(encoding="utf-8") + "\n追記した一文。\n", encoding="utf-8")

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "RESET:" in result.stdout
    assert "body" in result.stdout
    content = page.read_text(encoding="utf-8")
    assert "review_status: pending" in content
    assert "reviewed_by" not in content


@pytest.mark.parametrize(
    "old,new,field",
    [
        ('title: "山田太郎"', 'title: "山田 太郎"', "title"),
        ("tags: [engineer]", "tags: [engineer, ml]", "tags"),
        ('  jobTitle: "シニアエンジニア"', '  jobTitle: "エンジニア"', "properties"),
        ('expires_at: "2027-06-21"', 'expires_at: "2026-12-31"', "expires_at"),
    ],
)
def test_content_field_change_resets(wiki, old, new, field):
    """`expires_at` is content, not bookkeeping: Pass 4 checks it against the
    source like any other claim (Issue #279)."""
    page = wiki / ENTITY_REL
    page.write_text(page.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "RESET:" in result.stdout
    assert field in result.stdout
    assert "review_status: pending" in page.read_text(encoding="utf-8")


def test_a_view_page_is_handled_too(wiki):
    """wikicommit-fix takes both trees (Issue #675); looking only at the entity
    tree would let half its targets through silently."""
    page = wiki / VIEW_REL
    page.write_text(page.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")

    result = run([VIEW_REL], cwd=wiki)

    assert result.returncode == 0
    assert "RESET:" in result.stdout
    content = page.read_text(encoding="utf-8")
    assert "review_status: pending" in content
    assert "reviewed_by" not in content


# ── bookkeeping-only change → keep the sign-off ─────────────────────────────

def test_appending_a_source_alone_does_not_reset(wiki):
    """`sources[]` is bookkeeping. `action: update` almost always appends one —
    treating that as content would collapse this rule into "always reset"."""
    page = wiki / ENTITY_REL
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "    hash: sha256:abc123\n",
            "    hash: sha256:abc123\n  - type: url\n    url: https://example.com\n    hash: sha256:def456\n",
        ),
        encoding="utf-8",
    )

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "UNCHANGED:" in result.stdout
    content = page.read_text(encoding="utf-8")
    assert "review_status: reviewed" in content
    assert 'reviewed_by: "octocat"' in content


@pytest.mark.parametrize(
    "old,new",
    [
        ('generated_at: "2026-01-01"', 'generated_at: "2026-09-02"'),
        ('generated_by: "claude-opus-5"', 'generated_by: "claude-fable-5-1"'),
        ('generated_with: "0.1.0"', 'generated_with: "0.2.0"'),
    ],
)
def test_generated_field_change_alone_does_not_reset(wiki, old, new):
    page = wiki / ENTITY_REL
    page.write_text(page.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "UNCHANGED:" in result.stdout
    assert "review_status: reviewed" in page.read_text(encoding="utf-8")


def test_identical_page_does_not_reset(wiki):
    result = run([ENTITY_REL, VIEW_REL], cwd=wiki)

    assert result.returncode == 0
    assert result.stdout.count("UNCHANGED:") == 2
    assert "SUMMARY: reset=0, unchanged=2, skipped=0, errors=0" in result.stdout


def test_trailing_newline_difference_alone_does_not_reset(wiki):
    """Whitespace at the ends of the body is not a claim anyone reviewed."""
    page = wiki / ENTITY_REL
    page.write_text(page.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "UNCHANGED:" in result.stdout


def test_a_bom_prefixed_page_is_compared_on_equal_terms(wiki):
    """The work-tree read strips a BOM (`utf-8-sig`); the HEAD read must too.

    Without that, `_split_frontmatter()` does not recognise `\ufeff---` as the
    start of a frontmatter block, so the HEAD side parses as "no frontmatter,
    body = whole file" and an untouched page reports every field as changed.
    """
    page = wiki / ENTITY_REL
    page.write_bytes(b"\xef\xbb\xbf" + page.read_bytes())
    subprocess.run(["git", "commit", "-qam", "bom"], cwd=wiki, check=True, capture_output=True)

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "UNCHANGED:" in result.stdout
    assert 'reviewed_by: "octocat"' in page.read_text(encoding="utf-8-sig")


def test_a_bom_prefixed_page_still_resets_on_a_real_change(wiki):
    page = wiki / ENTITY_REL
    page.write_bytes(b"\xef\xbb\xbf" + page.read_bytes())
    subprocess.run(["git", "commit", "-qam", "bom"], cwd=wiki, check=True, capture_output=True)
    page.write_text(page.read_text(encoding="utf-8-sig") + "\n追記。\n", encoding="utf-8")

    result = run([ENTITY_REL], cwd=wiki)

    assert "RESET:" in result.stdout
    assert "body" in result.stdout


def test_a_non_utf8_locale_does_not_break_the_comparison(wiki):
    """`git show` output is decoded as UTF-8 explicitly, not via the locale.

    Leaving it to `text=True` raises UnicodeDecodeError on a non-ASCII page
    under an ASCII/cp932/cp1252 locale — which aborts the whole run, leaving
    every later page in the same call unchecked.
    """
    page = wiki / ENTITY_REL
    page.write_text(page.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONUTF8": "0",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), ENTITY_REL],
        capture_output=True, text=True, cwd=wiki, check=False, env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "RESET:" in result.stdout
    assert "review_status: pending" in page.read_text(encoding="utf-8")


def test_crlf_line_endings_alone_do_not_reset(wiki):
    """The HEAD side gets the same newline normalisation `Path.read_text` applies."""
    page = wiki / ENTITY_REL
    page.write_bytes(page.read_bytes().replace(b"\n", b"\r\n"))
    subprocess.run(["git", "commit", "-qam", "crlf"], cwd=wiki, check=True, capture_output=True)

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "UNCHANGED:" in result.stdout


# ── nothing to demote ──────────────────────────────────────────────────────

def test_a_pending_page_is_skipped(wiki):
    page = wiki / ENTITY_REL
    page.write_text(
        page.read_text(encoding="utf-8").replace("review_status: reviewed", "review_status: pending"),
        encoding="utf-8",
    )

    result = run([ENTITY_REL], cwd=wiki)

    assert result.returncode == 0
    assert "SKIP:" in result.stdout
    assert "review_status: pending" in page.read_text(encoding="utf-8")


def test_an_index_page_is_skipped(wiki):
    """`rebuild_index.py` stamps `reviewed` on build-generated index pages
    (Issue #580) and `wikicommit-merge` excludes them from tracking Issues, so
    demoting one leaves an unreviewed banner nobody can clear."""
    index = wiki / ".wikicommit" / "entity" / "ja" / "Person" / "index.md"
    index.write_text(
        '---\ntitle: "Person"\nlang: ja\ntype: "schema:Person"\n'
        "review_status: reviewed\n---\n\n- [[Person/yamada-taro]]\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=wiki, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "index"], cwd=wiki, check=True, capture_output=True)
    index.write_text(
        index.read_text(encoding="utf-8") + "- [[Person/suzuki]]\n", encoding="utf-8"
    )

    result = run([".wikicommit/entity/ja/Person/index.md"], cwd=wiki)

    assert result.returncode == 0
    assert "SKIP:" in result.stdout
    assert "review_status: reviewed" in index.read_text(encoding="utf-8")


def test_a_page_untracked_at_head_is_skipped(wiki):
    """A newly created page is `pending` to begin with and has no earlier
    version to compare against."""
    new_page = wiki / ".wikicommit" / "entity" / "ja" / "Person" / "suzuki.md"
    new_page.write_text(ENTITY_PAGE, encoding="utf-8")

    result = run([".wikicommit/entity/ja/Person/suzuki.md"], cwd=wiki)

    assert result.returncode == 0
    assert "SKIP:" in result.stdout
    assert "not tracked at HEAD" in result.stdout
    assert "review_status: reviewed" in new_page.read_text(encoding="utf-8")


# ── argument errors ────────────────────────────────────────────────────────

def test_a_path_outside_both_trees_is_an_error(wiki):
    (wiki / "README.md").write_text("---\nreview_status: reviewed\n---\n\nx\n", encoding="utf-8")

    result = run(["README.md"], cwd=wiki)

    assert result.returncode == 1
    assert "ERROR:" in result.stderr


def test_a_missing_page_is_an_error(wiki):
    result = run([".wikicommit/entity/ja/Person/nope.md"], cwd=wiki)

    assert result.returncode == 1
    assert "ERROR:" in result.stderr


def test_no_arguments_is_an_error(wiki):
    result = run([], cwd=wiki)

    assert result.returncode == 1
    assert "ERROR:" in result.stderr


def test_one_bad_page_does_not_stop_the_others(wiki):
    page = wiki / ENTITY_REL
    page.write_text(page.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")

    result = run([".wikicommit/entity/ja/Person/nope.md", ENTITY_REL], cwd=wiki)

    assert result.returncode == 1
    assert "RESET:" in result.stdout
    assert "review_status: pending" in page.read_text(encoding="utf-8")
