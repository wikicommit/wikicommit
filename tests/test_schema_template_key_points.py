"""Guards the shared `## Key Points` section on the article-shaped types (Issue #673).

The three templates that carry "what this document claims" used to disagree on
both halves of it: ScholarlyArticle called the section `## Key Contributions`
while the other two called it `## Key Points`, and all three ended their
instruction with "in list or prose form". Neither half is separately harmless —
a section written as prose cannot have one claim lifted out of it, and a
section whose name varies by type cannot be found across types at all. Together
they meant the claims a wiki holds were not comparable, by a human reading two
pages or by anything mechanical.

Both halves are now fixed in the templates, and this test holds them there. The
mechanical consumer already exists and needed no new code:
`build_survey_view.py` extracts each page's `##` headings for
`/wikicommit-synthesize`'s survey mode (Issue #586), so a single heading name
becomes a cross-page signal the moment it is single.

Scope is deliberately these three types and no others. ShortStory and Book are
works rather than arguments, and Person / Place / Organization / Event / HowTo /
DefinedTerm have no notion of "what this document claims" at all — adding the
section to them would leave the empty placeholder Issue #553 named when it
removed `inDefinedTermSet`.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_SCHEMA_DIR = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "schema"
)

sys.path.insert(0, str(REPO_ROOT / ".wikicommit" / "scripts"))
from _frontmatter import parse_frontmatter_and_body_text  # noqa: E402

HEADING = "## Key Points"

# The article-shaped types: a document that argues or reports something, whose
# claims are the thing a reader compares against another page's. Kept as an
# explicit list rather than derived, so adding a type here is a decision someone
# makes on purpose — the same "confirmed entries only" shape as
# check_extraction_quality.py's KNOWN_JS_SHELL_DOMAINS.
ARTICLE_TYPES = {
    "ScholarlyArticle.md": "a paper: its findings, taxonomy and stated contribution",
    "NewsArticle.md": "a report: the facts, figures and claims it carries",
    "BlogPosting.md": "a post: the argument or technique it advances",
}

# Types that must NOT grow the section, and why. ShortStory/Book are works, not
# arguments; the rest describe a subject rather than a document about one.
NON_ARTICLE_TYPES = {
    "ShortStory.md", "Book.md", "Person.md", "Place.md", "Organization.md",
    "Event.md", "HowTo.md", "DefinedTerm.md", "default.md",
}


def _body_of(path: Path) -> str:
    """Return the Markdown body, dropping the leading YAML frontmatter block.

    Delegates to the shared production parser rather than splitting here: four
    tests in this directory read the same template set, and each carrying its
    own split is how `.wikicommit/scripts/_frontmatter.py` came to exist in the
    first place (Issue #704 — its module docstring lists the real bugs the
    divergent copies produced). The body variant is text-based, so the file is
    read with utf-8-sig to match that module's own `parse_frontmatter()`:
    otherwise a BOM-prefixed template looks like one with no frontmatter, and
    the whole file — frontmatter included — comes back as the body.
    """
    frontmatter, error, body = parse_frontmatter_and_body_text(
        path.read_text(encoding="utf-8-sig")
    )
    assert not error, f"{path}: {error}"
    assert frontmatter, f"{path}: frontmatter block is missing or empty"
    return body


def test_expected_templates_exist():
    """A rename or move must not turn the checks below into vacuous passes."""
    for name in ARTICLE_TYPES:
        assert (TEMPLATE_SCHEMA_DIR / name).is_file(), f"{name} が見つかりません"
    for name in NON_ARTICLE_TYPES:
        assert (TEMPLATE_SCHEMA_DIR / name).is_file(), f"{name} が見つかりません"


def test_every_distributed_template_is_classified():
    """Neither list may silently miss a template — an unlisted one is unguarded.

    The two lists above are the whole of this file's scope, and a template in
    neither is checked in neither direction: nothing asks it for the shared
    heading and nothing forbids it one. A newly distributed article-shaped type
    could then reintroduce exactly the split Issue #673 removed — its own
    heading name, its own "in list or prose form" — while this file stayed
    green. Only the literal string `## Key Contributions` would still be
    caught, and a third name is not that string.

    Classifying a new type is therefore a decision someone has to make here on
    purpose, which is the same intent the explicit lists were written for.
    `custom/` is excluded deliberately: it ships empty and its contents are
    each wiki's own, not distributed types.
    """
    on_disk = {path.name for path in TEMPLATE_SCHEMA_DIR.glob("*.md")}
    classified = set(ARTICLE_TYPES) | NON_ARTICLE_TYPES
    assert on_disk == classified, (
        "配布テンプレートと本ファイルの分類が食い違っています（Issue #673）。"
        f"未分類: {sorted(on_disk - classified)} / 実体なし: {sorted(classified - on_disk)}。"
        f"記事系なら ARTICLE_TYPES に、それ以外なら NON_ARTICLE_TYPES に理由付きで加えてください"
    )


@pytest.mark.parametrize("name", sorted(ARTICLE_TYPES))
def test_article_template_has_key_points(name):
    body = _body_of(TEMPLATE_SCHEMA_DIR / name)
    assert f"\n{HEADING}\n" in body, (
        f"{name}（{ARTICLE_TYPES[name]}）の本文に `{HEADING}` がありません。"
        f"記事系 3 型は同じ見出し名を共有する規約です（Issue #673）"
    )


@pytest.mark.parametrize("name", sorted(ARTICLE_TYPES))
def test_article_template_asks_for_one_claim_per_bullet(name):
    """The heading alone is not the convention — a prose section under it is still
    not liftable claim by claim, which is what made the old wording unusable."""
    body = _body_of(TEMPLATE_SCHEMA_DIR / name)
    sections = body.split(f"\n{HEADING}\n", 1)
    assert len(sections) == 2, (
        f"{name} の本文に `{HEADING}` がないため指示を検査できません（Issue #673）。"
        f"見出し自体の欠落は test_article_template_has_key_points を参照してください"
    )
    instruction = sections[1].split("\n## ", 1)[0]
    assert "one claim per bullet" in instruction, (
        f"{name} の `{HEADING}` の指示が「1 主張 1 箇条書き」を求めていません（Issue #673）"
    )
    assert "prose form" not in instruction, (
        f"{name} の `{HEADING}` の指示に `in list or prose form` が残っています。"
        f"散文を許すと主張が 1 件ずつ取り出せません（Issue #673）"
    )


@pytest.mark.parametrize("name", sorted(NON_ARTICLE_TYPES))
def test_non_article_template_has_no_key_points(name):
    """Adding it everywhere would leave a section nothing fills (Issue #553)."""
    body = _body_of(TEMPLATE_SCHEMA_DIR / name)
    assert HEADING not in body, (
        f"{name} に `{HEADING}` があります。この節は記事系 3 型に限る規約です（Issue #673）"
    )


def test_old_heading_is_gone_from_every_template():
    """`## Key Contributions` was ScholarlyArticle's name for the same section;
    keeping both names anywhere would restore exactly the split this removed."""
    for path in sorted(TEMPLATE_SCHEMA_DIR.rglob("*.md")):
        assert "## Key Contributions" not in _body_of(path), (
            f"{path.name} に旧見出し `## Key Contributions` が残っています（Issue #673）"
        )
