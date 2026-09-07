"""Tests for .wikicommit/scripts/search_index.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "search_index.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "search_index.py"
)
DB_RELATIVE_PATH = Path(".wikicommit") / ".cache" / "search_index.sqlite3"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(
    root: Path, lang: str, type_name: str, slug: str, frontmatter: str, body: str = "Body.\n"
) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return page


# ── build ────────────────────────────────────────────────────────────────────

def test_build_no_wiki_dir(tmp_path):
    result = run(["build"], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert not (tmp_path / DB_RELATIVE_PATH).exists()


def test_build_creates_index_file(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
        body="CompanyAのシニアエンジニア。機械学習システムの開発に携わる。\n",
    )

    result = run(["build"], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: indexed 1 pages" in result.stdout
    assert (tmp_path / DB_RELATIVE_PATH).is_file()


def test_build_excludes_index_md(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "index",
        textwrap.dedent("""\
            title: "Person index"
            lang: ja
            type: "schema:Person"
            """),
    )

    result = run(["build"], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: indexed 0 pages" in result.stdout


def test_build_excludes_removed_pages(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            status: removed
            removed_at: "2026-01-01"
            """),
    )

    result = run(["build"], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: indexed 0 pages" in result.stdout

    query_result = run(["query", "山田太郎"], cwd=tmp_path)
    assert query_result.returncode == 0
    assert "MATCH:" not in query_result.stdout
    assert 'hits=0' in query_result.stdout


def test_build_skips_pages_with_non_mapping_frontmatter(tmp_path):
    """YAML that parses successfully but isn't a mapping (e.g. a bare scalar)
    must not crash the whole build — the page is skipped instead."""
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    page_dir.mkdir(parents=True)
    (page_dir / "broken.md").write_text("---\njust a plain scalar\n---\n\nBody.\n", encoding="utf-8")

    result = run(["build"], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: indexed 0 pages" in result.stdout


def test_build_skips_removed_pages_with_malformed_yaml(tmp_path):
    """A page whose frontmatter fails to parse can't be confirmed as *not*
    `status: removed`, so it must be excluded rather than indexed."""
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    page_dir.mkdir(parents=True)
    (page_dir / "broken.md").write_text(
        "---\ntitle: [unterminated\nstatus: removed\n---\n\nSecret body text.\n",
        encoding="utf-8",
    )

    result = run(["build"], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: indexed 0 pages" in result.stdout


def test_build_rebuilds_from_scratch(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )
    assert run(["build"], cwd=tmp_path).returncode == 0

    # Remove the page and rebuild — the stale row must not survive.
    (tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "yamada-taro.md").unlink()
    result = run(["build"], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: indexed 0 pages" in result.stdout

    query_result = run(["query", "山田太郎"], cwd=tmp_path)
    assert 'hits=0' in query_result.stdout


# ── query ────────────────────────────────────────────────────────────────────

def test_query_auto_builds_when_index_missing(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
        body="CompanyAのシニアエンジニアです。\n",
    )

    assert not (tmp_path / DB_RELATIVE_PATH).exists()
    result = run(["query", "エンジニア"], cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / DB_RELATIVE_PATH).exists()
    assert "MATCH:" in result.stdout


def test_query_exact_title_match(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "山田太郎"], cwd=tmp_path)
    assert result.returncode == 0
    assert "MATCH: " in result.stdout
    assert "yamada-taro.md" in result.stdout
    assert "title=山田太郎" in result.stdout
    assert "type=schema:Person" in result.stdout
    assert "lang=ja" in result.stdout
    assert 'hits=1' in result.stdout


def test_query_partial_body_match_cjk_without_segmentation(tmp_path):
    """Trigram tokenization must find a CJK substring inside a longer word
    without any word-boundary segmentation (Issue #126 completion criteria)."""
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
        body="CompanyAのシニアエンジニア。機械学習システムの開発に携わる。\n",
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "エンジニア"], cwd=tmp_path)
    assert result.returncode == 0
    assert "yamada-taro.md" in result.stdout
    assert 'hits=1' in result.stdout


def test_query_no_hits(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "存在しない単語です"], cwd=tmp_path)
    assert result.returncode == 0
    assert "MATCH:" not in result.stdout
    assert 'hits=0' in result.stdout


def test_query_lang_filter(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "Engineer"
            lang: ja
            type: "schema:Person"
            """),
        body="Engineer body text.\n",
    )
    write_page(
        tmp_path, "en", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "Engineer"
            lang: en
            type: "schema:Person"
            """),
        body="Engineer body text.\n",
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "Engineer", "--lang", "en"], cwd=tmp_path)
    assert result.returncode == 0
    assert "lang=en" in result.stdout
    assert "lang=ja" not in result.stdout
    assert 'hits=1' in result.stdout


def test_query_limit(tmp_path):
    for i in range(3):
        write_page(
            tmp_path, "ja", "Person", f"person-{i}",
            textwrap.dedent(f"""\
                title: "Person {i}"
                lang: ja
                type: "schema:Person"
                """),
            body="Shared keyword appears here.\n",
        )
    run(["build"], cwd=tmp_path)

    result = run(["query", "keyword", "--limit", "2"], cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.count("MATCH:") == 2
    assert 'hits=2' in result.stdout


def test_query_title_ranked_above_body_only_match(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "title-match",
        textwrap.dedent("""\
            title: "Keyword"
            lang: ja
            type: "schema:Person"
            """),
        body="Unrelated body text.\n",
    )
    write_page(
        tmp_path, "ja", "Person", "body-match",
        textwrap.dedent("""\
            title: "Unrelated Title"
            lang: ja
            type: "schema:Person"
            """),
        body="Body text mentioning Keyword once.\n",
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "Keyword"], cwd=tmp_path)
    matches = [line for line in result.stdout.splitlines() if line.startswith("MATCH:")]
    assert len(matches) == 2
    assert "title-match.md" in matches[0]
    assert "body-match.md" in matches[1]


def test_query_multi_word_matches_non_adjacent_terms(tmp_path):
    """A multi-word query must behave as an AND of keywords, not an exact
    adjacent-phrase match, so a page mentioning both terms non-contiguously
    is still found."""
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
        body="機械学習を専門とするエンジニアです。\n",
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "エンジニア 機械学習"], cwd=tmp_path)
    assert result.returncode == 0
    assert "yamada-taro.md" in result.stdout
    assert 'hits=1' in result.stdout


def test_query_corrupted_db_reports_error_instead_of_crashing(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )
    run(["build"], cwd=tmp_path)
    (tmp_path / DB_RELATIVE_PATH).write_bytes(b"not a sqlite database")

    result = run(["query", "山田太郎"], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_query_short_term_warns_and_returns_zero_hits(tmp_path):
    """A trigram tokenizer can't form a token from fewer than 3 characters,
    so a short query term silently never matches — even when matching
    content exists (Issue #274). The script must surface this instead of
    leaving the caller to guess why hits=0."""
    write_page(
        tmp_path, "ja", "Person", "kodomo",
        textwrap.dedent("""\
            title: "児童手当"
            lang: ja
            type: "schema:Person"
            """),
        body="児童手当の申請手続きについて説明する。\n",
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "児童"], cwd=tmp_path)
    assert result.returncode == 0
    assert 'WARNING: query term "児童" has 2 character(s)' in result.stdout
    assert "MATCH:" not in result.stdout
    assert 'hits=0' in result.stdout


def test_query_short_term_warning_per_term(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "kodomo",
        textwrap.dedent("""\
            title: "児童手当"
            lang: ja
            type: "schema:Person"
            """),
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "児童 給付"], cwd=tmp_path)
    assert result.returncode == 0
    assert 'WARNING: query term "児童" has 2 character(s)' in result.stdout
    assert 'WARNING: query term "給付" has 2 character(s)' in result.stdout


def test_query_no_warning_for_terms_at_minimum_length(tmp_path):
    write_page(
        tmp_path, "ja", "Person", "kodomo",
        textwrap.dedent("""\
            title: "児童手当"
            lang: ja
            type: "schema:Person"
            """),
        body="児童手当の申請手続きについて説明する。\n",
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", "児童手当"], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING:" not in result.stdout
    assert 'hits=1' in result.stdout


def test_query_special_characters_do_not_error(tmp_path):
    """A raw MATCH query would choke on FTS5 syntax characters like '-' or
    '"'; user-supplied query text must be safely handled either way."""
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            title: "山田太郎"
            lang: ja
            type: "schema:Person"
            """),
    )
    run(["build"], cwd=tmp_path)

    result = run(["query", 'weird"query -AND* text'], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


# ── query expansion: group OR / group AND (Issue #581) ──────────────────────

def _write_allowance_pages(tmp_path):
    """Two pages whose vocabulary differs from what a user is likely to type."""
    write_page(
        tmp_path, "ja", "DefinedTerm", "child-allowance",
        textwrap.dedent("""\
            title: "児童手当"
            lang: ja
            type: "schema:DefinedTerm"
            """),
        body="児童手当の申請手続きについて説明する。\n",
    )
    write_page(
        tmp_path, "ja", "DefinedTerm", "nursery",
        textwrap.dedent("""\
            title: "保育所"
            lang: ja
            type: "schema:DefinedTerm"
            """),
        body="保育所の入所手続きの説明。\n",
    )
    run(["build"], cwd=tmp_path)


def test_expand_or_finds_page_written_with_a_different_word(tmp_path):
    """The point of the feature: the user's word is absent from the wiki, and a
    synonym in the same group reaches the page anyway."""
    _write_allowance_pages(tmp_path)

    missed = run(["query", "子ども手当"], cwd=tmp_path)
    assert "hits=0" in missed.stdout

    result = run(["query", "--expand", "子ども手当|児童手当"], cwd=tmp_path)
    assert result.returncode == 0
    assert "child-allowance.md" in result.stdout
    assert "hits=1" in result.stdout


def test_expand_terms_appended_to_a_flat_query_would_narrow_instead(tmp_path):
    """Why grouping is required rather than adding the synonym to the query
    string: FTS5 AND-s adjacent phrases, so the extra wording removes the hit."""
    _write_allowance_pages(tmp_path)

    flat = run(["query", "子ども手当 児童手当"], cwd=tmp_path)
    assert "hits=0" in flat.stdout

    grouped = run(["query", "--expand", "子ども手当|児童手当"], cwd=tmp_path)
    assert "hits=1" in grouped.stdout


def test_expand_groups_are_anded_together(tmp_path):
    _write_allowance_pages(tmp_path)

    both = run(["query", "--expand", "子ども手当|児童手当", "--expand", "手続き"], cwd=tmp_path)
    assert "hits=1" in both.stdout
    assert 'query=("子ども手当" OR "児童手当") AND ("手続き")' in both.stdout

    # The second group genuinely constrains: a concept absent from that page
    # removes it from the results.
    neither = run(["query", "--expand", "子ども手当|児童手当", "--expand", "入所手続き"], cwd=tmp_path)
    assert "hits=0" in neither.stdout


def test_expand_single_term_group_is_parenthesised_and_still_matches(tmp_path):
    """FTS5 rejects a parenthesised group next to a bare phrase, so every group
    is parenthesised even when it holds one term."""
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", "児童手当", "--expand", "手続き"], cwd=tmp_path)
    assert result.returncode == 0
    assert 'query=("児童手当") AND ("手続き")' in result.stdout
    assert "hits=1" in result.stdout


def test_expand_escapes_embedded_double_quote_like_the_positional_path(tmp_path):
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", 'we"ird|保育所'], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert 'query=("we""ird" OR "保育所")' in result.stdout
    assert "hits=1" in result.stdout


def test_expand_drops_blank_terms_from_a_group(tmp_path):
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", "|児童手当| |"], cwd=tmp_path)
    assert result.returncode == 0
    assert 'query=("児童手当")' in result.stdout
    assert "hits=1" in result.stdout


def test_expand_short_term_with_a_usable_sibling_is_dropped_not_fatal(tmp_path):
    """A long synonym rescues a sub-trigram original; the warning must say so
    rather than reuse the dead-query wording."""
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", "児童|児童手当"], cwd=tmp_path)
    assert result.returncode == 0
    assert 'WARNING: expand term "児童" has 2 character(s)' in result.stdout
    assert "its group still matches via: 児童手当" in result.stdout
    assert 'query=("児童手当")' in result.stdout
    assert "hits=1" in result.stdout


def test_expand_group_of_only_short_terms_is_dropped_with_its_own_warning(tmp_path):
    """No term in the group can ever match. Keeping it would zero out the whole
    query, since groups are AND-ed; it is dropped instead, and the warning is
    worded differently from the salvageable case above."""
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", "手続き", "--expand", "児童|給付"], cwd=tmp_path)
    assert result.returncode == 0
    assert 'WARNING: expand group "児童|給付" has no term of at least 3 character(s)' in result.stdout
    assert "no longer narrows the search" in result.stdout
    assert 'query=("手続き")' in result.stdout
    assert "hits=2" in result.stdout


def test_expand_every_group_short_yields_zero_hits_without_error(tmp_path):
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", "児童|給付"], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "hits=0" in result.stdout
    # The per-group message says the search stopped being narrowed, which is the
    # opposite of what happens once nothing is left to narrow: the expression is
    # the empty phrase and hits=0 is guaranteed. Say that outright.
    assert "WARNING: no usable --expand term remains" in result.stdout


def test_expand_all_blank_warns_instead_of_silently_returning_zero(tmp_path):
    """A blank --expand value drops out during parsing, before the short-term
    check ever runs, so without this warning the run is completely silent and
    hits=0 is indistinguishable from the wiki genuinely having no match."""
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", ""], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "WARNING: no usable --expand term remains" in result.stdout
    assert "hits=0" in result.stdout


def test_expand_term_containing_a_newline_keeps_summary_on_one_line(tmp_path):
    """Callers parse `SUMMARY: query=..., hits=N` line by line; a newline left
    inside a term would split that line and hide hits= from them."""
    _write_allowance_pages(tmp_path)

    result = run(["query", "--expand", "児童手当\n申請手続き"], cwd=tmp_path)
    assert result.returncode == 0
    summary_lines = [ln for ln in result.stdout.splitlines() if ln.startswith("SUMMARY:")]
    assert summary_lines == ['SUMMARY: query=("児童手当 申請手続き"), hits=0']


def test_expand_respects_lang_and_limit(tmp_path):
    _write_allowance_pages(tmp_path)
    write_page(
        tmp_path, "en", "DefinedTerm", "child-allowance",
        textwrap.dedent("""\
            title: "Child Allowance"
            lang: en
            type: "schema:DefinedTerm"
            """),
        body="児童手当 is the Japanese child allowance.\n",
    )
    run(["build"], cwd=tmp_path)

    both = run(["query", "--expand", "児童手当"], cwd=tmp_path)
    assert "hits=2" in both.stdout

    ja_only = run(["query", "--expand", "児童手当", "--lang", "ja"], cwd=tmp_path)
    assert "hits=1" in ja_only.stdout
    assert "/en/" not in ja_only.stdout

    limited = run(["query", "--expand", "児童手当", "--limit", "1"], cwd=tmp_path)
    assert "hits=1" in limited.stdout


def test_positional_query_summary_format_is_unchanged(tmp_path):
    """The positional path keeps its quoted-raw-query SUMMARY; only the
    expansion path prints the built MATCH expression instead."""
    _write_allowance_pages(tmp_path)

    result = run(["query", "児童手当"], cwd=tmp_path)
    assert 'SUMMARY: query="児童手当", hits=1' in result.stdout


def test_query_and_expand_together_is_an_error(tmp_path):
    _write_allowance_pages(tmp_path)

    result = run(["query", "児童手当", "--expand", "子ども手当"], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR:" in result.stdout
    assert "MATCH:" not in result.stdout


def test_query_with_neither_term_source_is_an_error(tmp_path):
    _write_allowance_pages(tmp_path)

    result = run(["query"], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR:" in result.stdout


# ── wikicommit-init template stays in sync with the canonical script ─────────

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
