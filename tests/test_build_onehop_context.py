"""Tests for .wikicommit/scripts/build_onehop_context.py (Issue #947).

The first test here is the regression the script exists for: a throwaway regex
in the prose version had a character class with no `-`, so it matched none of
this wiki's kebab-case slugs (Issue #193) and the one-hop set came back quietly
smaller with no error to show for it.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "build_onehop_context.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts"
    / "build_onehop_context.py"
)


def run(cwd: Path, page_path: str, body: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--page-path", page_path, *args],
        input=body,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def make_repo(tmp_path: Path, *, primary_lang: str = "ja") -> Path:
    (tmp_path / ".wikicommit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".wikicommit" / "config.yml").write_text(
        textwrap.dedent(f"""\
            translation:
              primary_lang: {primary_lang}
              targets: [en]
            """),
        encoding="utf-8",
    )
    return tmp_path


def write_page(root: Path, rel: str, body: str = "body", **fields: str) -> Path:
    page = root / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    extra = "".join(f"{k}: {v}\n" for k, v in fields.items())
    page.write_text(f"---\ntitle: \"x\"\n{extra}---\n\n{body}\n", encoding="utf-8")
    return page


def page_lines(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.startswith("PAGE: ")]


def summary(stdout: str) -> str:
    lines = [line for line in stdout.splitlines() if line.startswith("SUMMARY: ")]
    assert len(lines) == 1, stdout
    return lines[0]


def test_kebab_case_slugs_resolve(tmp_path):
    """The defect this script was written for: a hyphen in the slug."""
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/vibe-coding.md", lang="ja")
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/context-engineering.md", lang="ja")
    body = "sees [[DefinedTerm/vibe-coding]] and [[DefinedTerm/context-engineering]]"
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/spec-driven-development.md", body)

    assert res.returncode == 0, res.stderr
    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/DefinedTerm/vibe-coding.md (outbound)",
        "PAGE: .wikicommit/entity/ja/DefinedTerm/context-engineering.md (outbound)",
    ]
    assert "outbound=2" in summary(res.stdout)


def test_nested_custom_type_resolves(tmp_path):
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/custom/Practice/agent-loop.md", lang="ja")
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/x.md", "[[custom/Practice/agent-loop]]")

    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/custom/Practice/agent-loop.md (outbound)"
    ]


def test_view_link_resolves_into_the_view_tree(tmp_path):
    """`View` is a reserved Type segment with no Type directory (Issue #675)."""
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/view/ja/agent-loop.md", lang="ja")
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/x.md", "[[View/agent-loop]]")

    assert page_lines(res.stdout) == ["PAGE: .wikicommit/view/ja/agent-loop.md (outbound)"]


def test_a_view_page_can_be_the_page_under_review(tmp_path):
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/vibe-coding.md", lang="ja")
    res = run(root, ".wikicommit/view/ja/landscape.md", "[[DefinedTerm/vibe-coding]]")

    assert res.returncode == 0, res.stderr
    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/DefinedTerm/vibe-coding.md (outbound)"
    ]


def test_cross_language_fallback_to_primary_lang(tmp_path):
    """docs/DesignDoc-pipeline.md §6.4: own language, then primary_lang."""
    root = make_repo(tmp_path, primary_lang="ja")
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/vibe-coding.md", lang="ja")
    res = run(root, ".wikicommit/entity/en/DefinedTerm/x.md", "[[DefinedTerm/vibe-coding]]")

    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/DefinedTerm/vibe-coding.md (outbound)"
    ]


def test_own_language_wins_over_primary_lang(tmp_path):
    root = make_repo(tmp_path, primary_lang="ja")
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/vibe-coding.md", lang="ja")
    write_page(root, ".wikicommit/entity/en/DefinedTerm/vibe-coding.md", lang="en")
    res = run(root, ".wikicommit/entity/en/DefinedTerm/x.md", "[[DefinedTerm/vibe-coding]]")

    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/en/DefinedTerm/vibe-coding.md (outbound)"
    ]


def test_unresolved_link_is_dropped_without_a_finding(tmp_path):
    """Issue #340: pointing at a page nobody has written yet is non-blocking."""
    root = make_repo(tmp_path)
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/x.md", "[[DefinedTerm/not-written-yet]]")

    assert res.returncode == 0
    assert page_lines(res.stdout) == []
    assert "outbound=0, inbound=0, skipped=0" in summary(res.stdout)


def test_inbound_pages_are_found(tmp_path):
    root = make_repo(tmp_path)
    write_page(
        root, ".wikicommit/entity/ja/DefinedTerm/cites-me.md",
        "refers to [[DefinedTerm/subject]]", lang="ja",
    )
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", "no links here")

    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/DefinedTerm/cites-me.md (inbound)"
    ]
    assert "inbound=1" in summary(res.stdout)


def test_index_md_is_skipped(tmp_path):
    """rebuild_index.py writes every page's own WikiLink into its Type index."""
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/index.md",
               "- [[DefinedTerm/subject]]", lang="ja")
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", "")

    assert page_lines(res.stdout) == []
    assert "skipped=1" in summary(res.stdout)


def test_removed_page_is_skipped(tmp_path):
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/gone.md", lang="ja", status="removed")
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/x.md", "[[DefinedTerm/gone]]")

    assert page_lines(res.stdout) == []
    assert "skipped=1" in summary(res.stdout)


def test_translation_of_the_page_under_review_is_skipped(tmp_path):
    """A disagreement there is staleness, which check_translation_status.py reports."""
    root = make_repo(tmp_path)
    write_page(
        root, ".wikicommit/entity/en/DefinedTerm/subject.md",
        "cites [[DefinedTerm/subject]]", lang="en",
        translated_from=".wikicommit/entity/ja/DefinedTerm/subject.md",
    )
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", "")

    assert page_lines(res.stdout) == []
    assert "skipped=1" in summary(res.stdout)


def test_translation_skip_tolerates_the_legacy_wiki_prefix(tmp_path):
    """Issue #477's old `.wikicommit/wiki/` prefix survives in stored paths."""
    root = make_repo(tmp_path)
    write_page(
        root, ".wikicommit/entity/en/DefinedTerm/subject.md",
        "cites [[DefinedTerm/subject]]", lang="en",
        translated_from=".wikicommit/wiki/ja/DefinedTerm/subject.md",
    )
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", "")

    assert page_lines(res.stdout) == []
    assert "skipped=1" in summary(res.stdout)


def test_a_page_in_both_directions_is_reported_once_as_outbound(tmp_path):
    root = make_repo(tmp_path)
    write_page(
        root, ".wikicommit/entity/ja/DefinedTerm/mutual.md",
        "cites [[DefinedTerm/subject]]", lang="ja",
    )
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", "[[DefinedTerm/mutual]]")

    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/DefinedTerm/mutual.md (outbound)"
    ]
    assert "outbound=1, inbound=0" in summary(res.stdout)


def test_the_page_under_review_is_never_its_own_neighbour(tmp_path):
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", lang="ja")
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", "[[DefinedTerm/subject]]")

    assert page_lines(res.stdout) == []


def test_cap_keeps_outbound_first_and_reports_capped(tmp_path):
    root = make_repo(tmp_path)
    outbound = [f"o-{i}" for i in range(6)]
    for slug in outbound:
        write_page(root, f".wikicommit/entity/ja/DefinedTerm/{slug}.md", lang="ja")
    write_page(
        root, ".wikicommit/entity/ja/DefinedTerm/inbound.md",
        "cites [[DefinedTerm/subject]]", lang="ja",
    )
    body = " ".join(f"[[DefinedTerm/{slug}]]" for slug in outbound)
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", body)

    lines = page_lines(res.stdout)
    assert len(lines) == 5
    assert all("(outbound)" in line for line in lines)
    assert "outbound=5, inbound=0" in summary(res.stdout)
    assert "capped=true" in summary(res.stdout)


def test_a_page_skipped_in_both_directions_is_counted_once(tmp_path):
    """`skipped` counts pages, not hits — a doubled number stops being read."""
    root = make_repo(tmp_path)
    write_page(
        root, ".wikicommit/entity/ja/DefinedTerm/gone.md",
        "cites [[DefinedTerm/subject]]", lang="ja", status="removed",
    )
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/subject.md", "[[DefinedTerm/gone]]")

    assert page_lines(res.stdout) == []
    assert "skipped=1" in summary(res.stdout)


def test_a_negative_max_pages_keeps_nothing_rather_than_dropping_the_tail(tmp_path):
    """`ordered[:-1]` would quietly lose one neighbour and still report a cap."""
    root = make_repo(tmp_path)
    for slug in ("a-one", "b-two"):
        write_page(root, f".wikicommit/entity/ja/DefinedTerm/{slug}.md", lang="ja")
    body = "[[DefinedTerm/a-one]] [[DefinedTerm/b-two]]"
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/x.md", body, "--max-pages", "-1")

    assert res.returncode == 0, res.stderr
    assert page_lines(res.stdout) == []
    assert "outbound=0, inbound=0" in summary(res.stdout)
    assert "capped=true" in summary(res.stdout)


def test_summary_is_printed_even_for_an_empty_neighbourhood(tmp_path):
    """"The neighbourhood is empty" must not look like "extraction found nothing"."""
    root = make_repo(tmp_path)
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/lonely.md", "no links at all")

    assert res.returncode == 0
    assert page_lines(res.stdout) == []
    assert summary(res.stdout) == "SUMMARY: outbound=0, inbound=0, skipped=0, capped=false"


def test_the_page_under_review_need_not_exist_on_disk(tmp_path):
    """Pass 4 runs before the write (references/pass3-generate.md item 6)."""
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/vibe-coding.md", lang="ja")
    res = run(root, ".wikicommit/entity/ja/DefinedTerm/brand-new.md", "[[DefinedTerm/vibe-coding]]")

    assert res.returncode == 0, res.stderr
    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/DefinedTerm/vibe-coding.md (outbound)"
    ]


def test_stdin_body_wins_over_the_stale_copy_on_disk(tmp_path):
    """`action: update`: the file still holds the *previous* version's links."""
    root = make_repo(tmp_path)
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/old-target.md", lang="ja")
    write_page(root, ".wikicommit/entity/ja/DefinedTerm/new-target.md", lang="ja")
    write_page(
        root, ".wikicommit/entity/ja/DefinedTerm/subject.md",
        "cites [[DefinedTerm/old-target]]", lang="ja",
    )
    res = run(
        root, ".wikicommit/entity/ja/DefinedTerm/subject.md",
        "---\nlang: ja\n---\n\ncites [[DefinedTerm/new-target]]\n",
    )

    assert page_lines(res.stdout) == [
        "PAGE: .wikicommit/entity/ja/DefinedTerm/new-target.md (outbound)"
    ]


def test_a_path_outside_both_trees_is_an_error(tmp_path):
    root = make_repo(tmp_path)
    res = run(root, "docs/DesignDoc-data.md", "body")

    assert res.returncode == 1
    assert "does not resolve to a page" in res.stderr


def test_template_mirror_is_the_same_file(tmp_path):
    """.wikicommit/scripts/ is a symlink to templates/scripts/ in this repo."""
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
