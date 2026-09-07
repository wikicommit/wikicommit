"""Tests for .wikicommit/scripts/rebuild_index.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "rebuild_index.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "rebuild_index.py"
)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(root: Path, lang: str, type_name: str, slug: str, frontmatter: str, body: str = "Body.\n") -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return page


# ── No wiki dir / no args ────────────────────────────────────────────────────

def test_no_wiki_dir(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: rebuilt=0" in result.stdout


# ── Basic rebuild ─────────────────────────────────────────────────────────────

def test_rebuild_single_type_dir(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )

    result = run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: .wikicommit/entity/ja/Person/index.md rebuilt (1 pages)" in result.stdout
    assert "SUMMARY: rebuilt=1" in result.stdout

    index = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(encoding="utf-8")
    assert 'title: "Person"' in index
    assert "lang: ja" in index
    assert 'type: "schema:Person"' in index
    # A Type index is a build-generated navigation page, not LLM-authored
    # content. Without the field, WikiCommitBanner.tsx falls back to `pending`
    # and shows readers an "unreviewed" warning on a machine-written table of
    # contents — for which no review-tracking Issue can ever exist, since
    # wikicommit-merge excludes index.md (Issue #580). Same stamp
    # convert_wikilinks.py already applies to the root index and source pages.
    assert "review_status: reviewed" in index
    # A list item holding the WikiLink alone, with no trailing title (Issue
    # #678): convert_wikilinks.py renders a WikiLink as the target page's own
    # title, so a `— {title}` suffix published as "山田太郎 — 山田太郎". The
    # `- ` marker keeps the rows from folding into one run-on paragraph.
    assert "\n- [[Person/yamada-taro]]\n" in index
    assert "山田太郎" not in index.split("---")[2]


def test_bare_type_name_not_type_index(tmp_path):
    """Issue #320: title must be the bare Type name, not '<Type> Index'."""
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "Taro"
            lang: ja
            type: "schema:Person"
            """),
    )
    run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    index = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(encoding="utf-8")
    assert 'title: "Person"' in index
    assert "Index" not in index


# ── status: removed pages are excluded ───────────────────────────────────────

def test_removed_page_excluded(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "Taro"
            lang: ja
            type: "schema:Person"
            """),
    )
    write_page(
        tmp_path, "ja", "Person", "removed-person",
        textwrap.dedent("""\
            title: "Gone"
            lang: ja
            type: "schema:Person"
            status: removed
            removed_at: "2026-01-01"
            """),
    )

    run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    index = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(encoding="utf-8")
    assert "yamada-taro" in index
    assert "removed-person" not in index


# ── Existing index.md is fully regenerated, not appended to ─────────────────

def test_existing_index_is_overwritten(tmp_path):
    person_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    person_dir.mkdir(parents=True)
    (person_dir / "index.md").write_text(
        '---\ntitle: "Person Index"\nlang: ja\ntype: "schema:Person"\n---\n\n[[Person/stale]] — Stale\n',
        encoding="utf-8",
    )
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "Taro"
            lang: ja
            type: "schema:Person"
            """),
    )

    run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    index = (person_dir / "index.md").read_text(encoding="utf-8")
    assert "stale" not in index
    assert "yamada-taro" in index
    assert 'title: "Person"' in index


# ── Sorted, deterministic ordering ───────────────────────────────────────────

def test_entries_sorted_by_slug(tmp_path):
    write_page(tmp_path, "ja", "Person", "zzz", textwrap.dedent("""\
        title: "Z"
        lang: ja
        type: "schema:Person"
        """))
    write_page(tmp_path, "ja", "Person", "aaa", textwrap.dedent("""\
        title: "A"
        lang: ja
        type: "schema:Person"
        """))

    run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    index = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(encoding="utf-8")
    assert index.index("aaa") < index.index("zzz")


# ── Nested custom types ───────────────────────────────────────────────────────

def test_nested_custom_type(tmp_path):
    write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        textwrap.dedent("""\
            title: "Adopt Quartz"
            lang: ja
            type: "schema:custom/Decision"
            """),
    )

    result = run([".wikicommit/entity/ja/custom/Decision"], cwd=tmp_path)
    assert result.returncode == 0
    assert "rebuilt (1 pages)" in result.stdout

    index = (tmp_path / ".wikicommit" / "entity" / "ja" / "custom" / "Decision" / "index.md").read_text(encoding="utf-8")
    assert 'title: "Decision"' in index
    assert 'type: "schema:custom/Decision"' in index
    assert "review_status: reviewed" in index
    assert "\n- [[custom/Decision/adopt-quartz]]\n" in index
    assert "Adopt Quartz" not in index.split("---")[2]


# ── No-args mode discovers every Type directory ──────────────────────────────

def test_no_args_discovers_all_type_dirs(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", textwrap.dedent("""\
        title: "Taro"
        lang: ja
        type: "schema:Person"
        """))
    write_page(tmp_path, "en", "Place", "tokyo", textwrap.dedent("""\
        title: "Tokyo"
        lang: en
        type: "schema:Place"
        """))

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: rebuilt=2" in result.stdout
    assert (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").exists()
    assert (tmp_path / ".wikicommit" / "entity" / "en" / "Place" / "index.md").exists()


def test_no_args_rebuilds_type_dir_left_with_only_an_index(tmp_path):
    """A Type directory whose last page was removed keeps its index.md but holds
    no page for a later run to rediscover it by. Keying discovery on pages alone
    would strand that index at whatever the last rebuild wrote — including, for
    an index written before Issue #580, frontmatter with no `review_status`,
    which WikiCommitBanner renders as an "unreviewed" warning forever."""
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    page_dir.mkdir(parents=True)
    (page_dir / "index.md").write_text(
        '---\ntitle: "Person"\nlang: ja\ntype: "schema:Person"\n---\n\n'
        "[[Person/gone]] — Gone\n",
        encoding="utf-8",
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: rebuilt=1" in result.stdout
    index = (page_dir / "index.md").read_text(encoding="utf-8")
    assert "review_status: reviewed" in index
    assert "[[" not in index


def test_no_args_skips_assets_dir(tmp_path):
    assets_dir = tmp_path / ".wikicommit" / "entity" / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "photo.md").write_text("not a page\n", encoding="utf-8")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: rebuilt=0" in result.stdout


# ── Missing / malformed input is a warning, not a failure ───────────────────

def test_nonexistent_dir_is_warning_not_error(tmp_path):
    result = run([".wikicommit/entity/ja/Nonexistent"], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING: .wikicommit/entity/ja/Nonexistent: directory not found, skipped" in result.stdout
    assert "SUMMARY: rebuilt=0" in result.stdout


def test_page_missing_title_is_warning_and_omitted(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "no-title",
        textwrap.dedent("""\
            lang: ja
            type: "schema:Person"
            """),
    )
    result = run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "no-title" not in result.stdout.split("SUMMARY")[0].replace("WARNING: .wikicommit/entity/ja/Person/no-title.md", "")
    index = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(encoding="utf-8")
    assert "[[Person/no-title]]" not in index


def test_page_with_unparseable_frontmatter_is_warning_and_omitted(tmp_path):
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    page_dir.mkdir(parents=True)
    (page_dir / "broken.md").write_text("---\ntitle: [unterminated\n", encoding="utf-8")
    write_page(
        tmp_path, "ja", "Person", "ok-page",
        textwrap.dedent("""\
            title: "OK"
            lang: ja
            type: "schema:Person"
            """),
    )

    result = run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    assert result.returncode == 0
    index = (page_dir / "index.md").read_text(encoding="utf-8")
    assert "ok-page" in index
    assert "broken" not in index


# ── Empty directory produces an index.md with no entries ────────────────────

def test_type_dir_with_only_removed_pages_produces_empty_index(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "removed-person",
        textwrap.dedent("""\
            title: "Gone"
            lang: ja
            type: "schema:Person"
            status: removed
            removed_at: "2026-01-01"
            """),
    )

    result = run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    assert result.returncode == 0
    assert "rebuilt (0 pages)" in result.stdout
    index = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(encoding="utf-8")
    assert 'title: "Person"' in index
    # An index with no entries is still a navigation page — a Type directory
    # emptied by removals must not start warning readers about itself.
    assert "review_status: reviewed" in index
    assert "[[" not in index


# ── Title with special YAML characters is safely quoted ─────────────────────

def test_title_with_quote_is_escaped(tmp_path):
    write_page(
        tmp_path, "ja", "DefinedTerm", "quoted",
        'title: "Say \\"hi\\""\nlang: ja\ntype: "schema:DefinedTerm"\n',
    )
    result = run([".wikicommit/entity/ja/DefinedTerm"], cwd=tmp_path)
    assert result.returncode == 0
    index_path = tmp_path / ".wikicommit" / "entity" / "ja" / "DefinedTerm" / "index.md"
    index = index_path.read_text(encoding="utf-8")
    # Re-parse the generated index.md's own frontmatter to prove it's valid YAML.
    import yaml
    fm = yaml.safe_load(index.split("---")[1])
    assert fm["title"] == "DefinedTerm"


# ── Multiple directories in one invocation ───────────────────────────────────

def test_multiple_dirs_in_one_call(tmp_path):
    write_page(tmp_path, "ja", "Person", "a", textwrap.dedent("""\
        title: "A"
        lang: ja
        type: "schema:Person"
        """))
    write_page(tmp_path, "ja", "Place", "b", textwrap.dedent("""\
        title: "B"
        lang: ja
        type: "schema:Place"
        """))

    result = run([".wikicommit/entity/ja/Person", ".wikicommit/entity/ja/Place"], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: rebuilt=2" in result.stdout


# ── Template sync (Issue #71-style drift guard) ───────────────────────────────────

# ── The row format itself (Issue #678) ───────────────────────────────────────

def test_index_rows_carry_no_title_suffix(tmp_path):
    """A row is a list item holding exactly one WikiLink. The published page
    renders the link as the target's own `title`, so anything appended repeats
    that title verbatim; and without the `- ` marker the rows are consecutive
    non-blank lines, which CommonMark folds into a single run-on paragraph
    (Quartz ships `hard-line-breaks` disabled, so soft breaks stay soft)."""
    for slug, title in (("aaa", "Alpha"), ("bbb", "Beta")):
        write_page(tmp_path, "ja", "Person", slug, textwrap.dedent(f"""\
            title: "{title}"
            lang: ja
            type: "schema:Person"
            """))

    run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    body = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(
        encoding="utf-8"
    ).split("---")[2]

    assert [ln for ln in body.splitlines() if ln] == ["- [[Person/aaa]]", "- [[Person/bbb]]"]


def test_dropping_the_suffix_did_not_change_ordering_or_exclusions(tmp_path):
    """Only the row format moved: slug-ascending order, the `status: removed`
    exclusion, and the missing-title WARNING all stay as they were."""
    write_page(tmp_path, "ja", "Person", "zzz", 'title: "Z"\nlang: ja\ntype: "schema:Person"\n')
    write_page(tmp_path, "ja", "Person", "aaa", 'title: "A"\nlang: ja\ntype: "schema:Person"\n')
    write_page(tmp_path, "ja", "Person", "mmm",
               'title: "M"\nlang: ja\ntype: "schema:Person"\n'
               'status: removed\nremoved_at: "2026-01-01"\n')
    write_page(tmp_path, "ja", "Person", "untitled", 'lang: ja\ntype: "schema:Person"\n')

    result = run([".wikicommit/entity/ja/Person"], cwd=tmp_path)
    body = (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md").read_text(
        encoding="utf-8"
    ).split("---")[2]

    assert [ln for ln in body.splitlines() if ln] == ["- [[Person/aaa]]", "- [[Person/zzz]]"]
    assert "has no title field" in result.stdout
    assert "untitled" not in body
    assert "mmm" not in body


def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
