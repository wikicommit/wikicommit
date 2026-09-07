"""Build-generated navigation pages opt out of the comment box (Issue #741).

giscus renders into `afterBody`, which means *every* page — including the kinds
of page nobody wrote: Type indexes, the view-tree index, the root index, the
mirrored `content/sources/` tree, and `content/overview/`. Those are navigation
and aggregation; a comment box under one has nothing to receive.

For those, the opt-out is a `comments: false` key in the page's own frontmatter,
which the comments plugin honours. It goes in the same place, and for the same
reason, as the `review_status: reviewed` stamp they already carry (Issue #580):
the side that writes the page decides, rather than the renderer guessing from a
slug. So the risk here is not that someone argues with the decision — it is
that a further kind of generated page gets added later and the key is forgotten,
which nothing would otherwise notice until a comment box appeared under it.

Two kinds of navigation page cannot be reached that way at all: Quartz builds
folder pages and tag pages itself, and no `.md` is written for them — notably
`content/<lang>/index.md` is never written, so every language top is a synthesised
folder page. Those are excluded in `layout.byPageType`, next to `wikicommit-banner`,
which sits there for exactly the same reason (Issue #648). Both mechanisms are
required; neither covers the other's pages.

These tests run the real scripts and read the real output, rather than grepping
the source for the literal string: what matters is the key reaching the file.
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".wikicommit" / "scripts"


def _run(script: str, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"
    return result


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    return yaml.safe_load(text.split("---\n")[1]) or {}


def _wiki(tmp_path: Path) -> Path:
    page = tmp_path / ".wikicommit/entity/ja/Person/yamada-taro.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        'title: "山田太郎"\n'
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
    view = tmp_path / ".wikicommit/view/ja/agent-loop.md"
    view.parent.mkdir(parents=True, exist_ok=True)
    view.write_text(
        "---\n"
        'title: "エージェントループ"\n'
        "lang: ja\n"
        "derived_from:\n"
        "  - path: .wikicommit/entity/ja/Person/yamada-taro.md\n"
        "    source_commit: abc123\n"
        "---\n"
        "\n"
        "body\n",
        encoding="utf-8",
    )
    mgmt = tmp_path / ".wikicommit/source/url/example.com/a.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        "---\n"
        "source:\n"
        "  type: url\n"
        "  url: https://example.com/a\n"
        "  hash: sha256:cd34\n"
        "status: generated\n"
        "generated_pages:\n"
        "  - .wikicommit/entity/ja/Person/yamada-taro.md\n"
        "---\n"
        "\n## Summary\n\nSummary text.\n",
        encoding="utf-8",
    )
    (tmp_path / ".wikicommit" / "config.yml").write_text(
        "translation:\n  targets: []\n  primary_lang: ja\n", encoding="utf-8"
    )
    return tmp_path


def test_type_and_view_indexes_opt_out(tmp_path):
    _wiki(tmp_path)
    _run("rebuild_index.py", tmp_path)
    for rel in (".wikicommit/entity/ja/Person/index.md", ".wikicommit/view/ja/index.md"):
        fm = _frontmatter(tmp_path / rel)
        assert fm.get("comments") is False, f"{rel} would render a comment box"
        # The sibling stamp this one rides along with must still be there.
        assert fm.get("review_status") == "reviewed", rel


def test_every_build_generated_page_under_content_opts_out(tmp_path):
    """Root index, the mirrored sources tree, and the overview page.

    Asserted by walking the output rather than by naming the four writers, so a
    fifth generated page added later has to answer this question too.
    """
    _wiki(tmp_path)
    _run("rebuild_index.py", tmp_path)
    _run("convert_wikilinks.py", tmp_path, "--source", ".wikicommit/entity", "--output", "content")

    content = tmp_path / "content"
    authored = {
        # The two pages a human or an LLM wrote; everything else under content/
        # is build-generated and must opt out.
        content / "ja" / "Person" / "yamada-taro.md",
        content / "ja" / "View" / "agent-loop.md",
    }
    generated = [p for p in sorted(content.rglob("*.md")) if p not in authored]
    assert generated, "no build-generated pages were produced; the fixture is wrong"

    for page in generated:
        fm = _frontmatter(page)
        assert fm.get("comments") is False, (
            f"{page.relative_to(content)} is build-generated but would render a "
            f"comment box. Add `comments: false` where it is written, next to the "
            f"`review_status: reviewed` stamp it already carries."
        )


def test_authored_pages_keep_comments(tmp_path):
    """The opt-out must not leak onto the pages the box is actually for."""
    _wiki(tmp_path)
    _run("rebuild_index.py", tmp_path)
    _run("convert_wikilinks.py", tmp_path, "--source", ".wikicommit/entity", "--output", "content")
    for rel in ("ja/Person/yamada-taro.md", "ja/View/agent-loop.md"):
        fm = _frontmatter(tmp_path / "content" / rel)
        assert "comments" not in fm, f"{rel} was silently opted out of comments"


def test_the_shipped_config_does_not_carry_empty_giscus_keys():
    """Issue #553: a receptacle nobody fills is worse than an absent one."""
    template = (
        REPO / ".claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml"
    ).read_text(encoding="utf-8")
    block = template[template.index("github:quartz-community/comments"):]
    block = block[: block.index("- source:", 10)]
    for key in ("repo:", "repoId:", "category:", "categoryId:"):
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith(key):
                raise AssertionError(
                    f"{key} is shipped as a real key; it would sit empty in every "
                    f"repository that never enables comments (Issue #553). Keep it "
                    f"in the commented-out example only."
                )
    assert "enabled: false" in block, "comments must ship disabled"


def test_quartz_synthesised_pages_are_excluded_in_layout():
    """folder / tag pages have no .md to stamp, so frontmatter cannot reach them.

    `content/<lang>/index.md` is never written (see
    test_every_build_generated_page_under_content_opts_out's output), so the
    language top is always a folder page Quartz synthesises with default
    frontmatter — `comments` undefined, box rendered. Same for /tags/<tag>.
    """
    import yaml as _yaml

    template = (
        REPO / ".claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml"
    ).read_text(encoding="utf-8")
    config = _yaml.safe_load(re.sub(r"\{[A-Z_]+\}", "x", template))
    by_page_type = config["layout"]["byPageType"]
    for page_type in ("folder", "tag"):
        exclude = by_page_type[page_type].get("exclude", [])
        assert "comments" in exclude, (
            f"byPageType.{page_type}.exclude does not drop the comments component. "
            f"Quartz synthesises these pages with no .md behind them, so the "
            f"`comments: false` frontmatter opt-out cannot reach them and enabling "
            f"giscus puts a comment box on every language top and tag listing — "
            f"the pages this whole change exists to keep it off. `wikicommit-banner` "
            f"is already excluded here for the identical reason (Issue #648)."
        )


def test_reactions_are_not_wired_to_review_status():
    """The two axes are deliberately separate (Issue #741); nothing may join them."""
    # Anchored on the rationale itself, not on the bare string "review_status":
    # both files already contain that word for unrelated reasons (the banner
    # plugin's own entry; the folder/tag exclude comment), so a bare membership
    # test stays green even if the whole giscus rationale is deleted.
    for path, phrase in (
        (
            REPO / ".claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml",
            "deliberately NOT wired to review_status",
        ),
        (
            REPO / ".claude/skills/wikicommit-init/SKILL.md",
            "Do not wire reactions or discussions to `review_status`",
        ),
    ):
        text = path.read_text(encoding="utf-8")
        assert phrase in text, (
            f"{path.name} no longer states the separation between reactions and "
            f"review_status (looked for: {phrase!r})"
        )
    workflow = (
        REPO / ".claude/skills/wikicommit-init/scripts/templates/workflows"
        / "review-issue-close-sync.yml"
    ).read_text(encoding="utf-8")
    # The sync workflow must stay driven by issues.closed alone.
    assert "discussion" not in workflow.lower(), (
        "review-issue-close-sync.yml now reacts to Discussions. A reaction is not "
        "a review: it needs no write access, has no principled threshold, and a "
        "page nobody has reacted to has no discussion to read."
    )
