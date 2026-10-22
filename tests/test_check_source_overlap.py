"""Tests for .wikicommit/scripts/check_source_overlap.py (Issue #1380)"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / ".wikicommit" / "scripts"
SCRIPT = SCRIPTS / "check_source_overlap.py"
sys.path.insert(0, str(SCRIPTS))

import check_source_overlap as cso  # noqa: E402

URL = "https://example.com/post"
CACHE = Path(".wikicommit/.cache/ingest-fetch/example.com/post.md")

# 120 distinct words, so a run of six is shared only where text was copied.
SOURCE = " ".join(f"w{i}" for i in range(120))


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          cwd=cwd, check=False)


def write_url_mgmt(root: Path, *, url: str = URL, rel: str = "example.com/post.md",
                   lang: str = "en", status: str = "generated") -> None:
    mgmt = root / ".wikicommit/source/url" / rel
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(textwrap.dedent(f"""\
        ---
        source:
          type: url
          url: '{url}'
          hash: sha256:abc
          lang: {lang}
        status: {status}
        ---
        """), encoding="utf-8")


def write_cache(root: Path, text: str = SOURCE, rel: Path = CACHE) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


def write_page(root: Path, body: str, *, lang: str = "en", sources: str | None = None,
               extra: str = "", name: str = "post.md") -> Path:
    if sources is None:
        sources = f"  - type: url\n    url: '{URL}'\n"
    page = root / ".wikicommit/entity" / lang / "BlogPosting" / name
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\ntitle: T\nlang: {lang}\ntype: \"schema:BlogPosting\"\n"
                    f"sources:\n{sources}{extra}---\n\n{body}\n", encoding="utf-8")
    return page


def own(count: int, start: int = 0) -> str:
    return " ".join(f"own{i}" for i in range(start, start + count))


def copied(start: int, count: int) -> str:
    return " ".join(f"w{i}" for i in range(start, start + count))


# --- counting -------------------------------------------------------------------


def test_share_counts_words_inside_runs_of_n_or_more():
    grams = cso.source_grams([SOURCE], 6)
    # 10 copied words among 90 of the page's own: 10%.
    result = cso.measure(f"{own(45)} {copied(0, 10)} {own(45, 45)}", grams, 6)
    assert result.words == 100
    assert result.share == pytest.approx(0.10)
    assert result.longest == [f"w{i}" for i in range(10)]


def test_a_run_shorter_than_n_is_not_counted():
    grams = cso.source_grams([SOURCE], 6)
    result = cso.measure(f"{own(10)} {copied(0, 5)} {own(10, 10)}", grams, 6)
    assert result.share == 0


def test_case_and_punctuation_do_not_hide_a_copy():
    grams = cso.source_grams(["The quick brown fox jumps over the lazy dog."], 6)
    result = cso.measure("THE QUICK, brown fox — jumps over!", grams, 6)
    assert result.share == 1


def test_no_run_is_counted_across_an_excluded_span():
    # The six words are contiguous in the source, but the page splits them
    # with a quotation, which is dropped and breaks the run.
    grams = cso.source_grams([SOURCE], 6)
    prose = cso.page_prose(f'{copied(0, 3)} "a quoted remark" {copied(3, 3)}')
    assert cso.measure(prose, grams, 6).share == 0


# --- what the page body loses before counting -------------------------------------


@pytest.mark.parametrize("wrapped", [
    '"{}"', "“{}”", "「{}」", "『{}』", "`{}`", "> {}", "| {} | x |",
    "```\n{}\n```",
])
def test_quotations_code_blockquotes_and_tables_are_excluded(wrapped):
    prose = cso.page_prose(wrapped.format(copied(0, 10)))
    assert cso.measure(prose, cso.source_grams([SOURCE], 6), 6).words == 0


def test_generation_notes_and_everything_after_are_excluded():
    prose = cso.page_prose(f"{own(5)}\n\n## Generation Notes\n\n{copied(0, 10)}\n\n## Later\n\nx")
    assert cso.tokens(prose) == own(5).split()


def test_wikilinks_become_their_display_text_or_slug_words():
    prose = cso.page_prose("[[DefinedTerm/context-window|the window]] and [[Person/ada-lovelace]]")
    assert cso.tokens(prose) == ["the", "window", "and", "ada", "lovelace"]


def test_markdown_links_keep_their_text_and_drop_the_url():
    prose = cso.page_prose("see [the post](https://example.com/a-b-c-d-e-f) and https://x.y/z")
    assert cso.tokens(prose) == ["see", "the", "post", "and"]


def test_cjk_text_is_counted_by_character():
    assert cso.tokens("大宮公園は1885年に開設") == ["大", "宮", "公", "園", "は", "1885", "年", "に",
                                                  "開", "設"]
    assert cso.tokens("Claude Code の設定") == ["claude", "code", "の", "設", "定"]


# --- the CLI ----------------------------------------------------------------------


def test_a_page_over_the_threshold_is_reported(tmp_path):
    write_url_mgmt(tmp_path)
    write_cache(tmp_path)
    page = write_page(tmp_path, f"{own(70)} {copied(0, 30)}")
    out = run(tmp_path).stdout
    assert f"OVERLAP: {page.relative_to(tmp_path)} 30% (100 words; longest: 30 words" in out
    assert "SUMMARY: measured=1, overlap=1" in out


def test_a_page_under_the_threshold_prints_ok(tmp_path):
    write_url_mgmt(tmp_path)
    write_cache(tmp_path)
    write_page(tmp_path, f"{own(90)} {copied(0, 10)}")
    result = run(tmp_path)
    assert result.returncode == 0
    assert "OVERLAP:" not in result.stdout
    assert "OK: no page over the threshold" in result.stdout
    assert "SHARE:" in run(tmp_path, "--all-shares").stdout


def test_a_short_page_is_measured_but_not_reported(tmp_path):
    write_url_mgmt(tmp_path)
    write_cache(tmp_path)
    write_page(tmp_path, copied(0, 50))
    out = run(tmp_path).stdout
    assert "OVERLAP:" not in out
    assert "under_min_words=1" in out
    assert "OVERLAP:" in run(tmp_path, "--min-words", "10").stdout


def test_a_page_whose_sources_have_no_cache_is_not_passed_silently(tmp_path):
    write_url_mgmt(tmp_path)
    page = write_page(tmp_path, own(200))
    result = run(tmp_path)
    assert result.returncode == 0
    assert f"NO_SOURCE_TEXT: {page.relative_to(tmp_path)}" in result.stdout
    assert "no_source_text=1" in result.stdout


def test_an_unregistered_source_counts_as_no_source_text(tmp_path):
    page = write_page(tmp_path, own(200))
    assert f"NO_SOURCE_TEXT: {page.relative_to(tmp_path)}" in run(tmp_path).stdout


def test_summarize_missing_prints_one_count(tmp_path):
    write_url_mgmt(tmp_path)
    write_page(tmp_path, own(200), name="a.md")
    write_page(tmp_path, own(200), name="b.md")
    out = run(tmp_path, "--summarize-missing").stdout
    assert out.count("NO_SOURCE_TEXT:") == 1
    assert "NO_SOURCE_TEXT: 2 page(s) not measured" in out


def test_a_partly_cached_page_is_measured_against_what_is_there(tmp_path):
    write_url_mgmt(tmp_path)
    write_cache(tmp_path)
    write_url_mgmt(tmp_path, url="https://example.com/other", rel="example.com/other.md")
    sources = (f"  - type: url\n    url: '{URL}'\n"
               "  - type: url\n    url: 'https://example.com/other'\n")
    write_page(tmp_path, f"{own(70)} {copied(0, 30)}", sources=sources)
    out = run(tmp_path).stdout
    assert "OVERLAP:" in out and "NO_SOURCE_TEXT:" not in out


def test_a_source_in_another_language_is_skipped(tmp_path):
    write_url_mgmt(tmp_path, lang="en")
    write_cache(tmp_path)
    page = write_page(tmp_path, copied(0, 120), lang="ja")
    out = run(tmp_path).stdout
    assert f"SKIPPED_CROSS_LANG: {page.relative_to(tmp_path)} (ja page; sources in en)" in out
    assert "OVERLAP:" not in out and "cross_lang=1" in out


def test_a_source_with_no_recorded_language_is_compared(tmp_path):
    write_url_mgmt(tmp_path, lang="")
    write_cache(tmp_path)
    write_page(tmp_path, f"{own(70)} {copied(0, 30)}")
    assert "OVERLAP:" in run(tmp_path).stdout


def test_a_region_subtag_on_source_lang_still_matches(tmp_path):
    write_url_mgmt(tmp_path, lang="en-US")
    write_cache(tmp_path)
    write_page(tmp_path, f"{own(70)} {copied(0, 30)}")
    assert "OVERLAP:" in run(tmp_path).stdout


def test_a_translated_page_is_skipped_as_cross_language(tmp_path):
    page = write_page(tmp_path, own(200), sources="",
                      extra="translated_from: .wikicommit/entity/ja/BlogPosting/post.md\n")
    assert f"SKIPPED_CROSS_LANG: {page.relative_to(tmp_path)} (translated page)" in run(
        tmp_path).stdout


def test_an_uncached_same_language_source_outranks_a_cross_language_one(tmp_path):
    write_url_mgmt(tmp_path, lang="ja")
    write_url_mgmt(tmp_path, url="https://example.com/other", rel="example.com/other.md",
                   lang="en")
    write_cache(tmp_path, rel=Path(".wikicommit/.cache/ingest-fetch/example.com/other.md"))
    sources = (f"  - type: url\n    url: '{URL}'\n"
               "  - type: url\n    url: 'https://example.com/other'\n")
    page = write_page(tmp_path, own(200), lang="ja", sources=sources)
    assert f"NO_SOURCE_TEXT: {page.relative_to(tmp_path)}" in run(tmp_path).stdout


def test_manual_and_retracted_sources_are_not_measured_and_not_missing(tmp_path):
    write_url_mgmt(tmp_path, status="retracted")
    write_cache(tmp_path)
    sources = (f"  - type: url\n    url: '{URL}'\n"
               "  - type: manual\n    author: someone\n")
    write_page(tmp_path, copied(0, 120), sources=sources)
    out = run(tmp_path).stdout
    assert "OVERLAP:" not in out and "NO_SOURCE_TEXT:" not in out
    assert "SUMMARY: measured=0" in out


def test_a_path_source_reads_its_extraction_cache(tmp_path):
    mgmt = tmp_path / ".wikicommit/source/path/raw/paper.pdf.md"
    mgmt.parent.mkdir(parents=True)
    mgmt.write_text("---\nsource:\n  type: path\n  path: raw/paper.pdf\n  lang: en\n---\n",
                    encoding="utf-8")
    write_cache(tmp_path, rel=Path(".wikicommit/.cache/extract-path/raw/paper.pdf.md"))
    write_page(tmp_path, f"{own(70)} {copied(0, 30)}",
               sources="  - type: path\n    path: raw/paper.pdf\n")
    assert "OVERLAP:" in run(tmp_path).stdout


def test_a_markdown_path_source_is_read_as_it_is(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/notes.md").write_text(SOURCE, encoding="utf-8")
    write_page(tmp_path, f"{own(70)} {copied(0, 30)}",
               sources="  - type: path\n    path: raw/notes.md\n")
    assert "OVERLAP:" in run(tmp_path).stdout


def test_a_japanese_page_uses_the_character_run_length(tmp_path):
    source = "大宮公園は埼玉県さいたま市大宮区にある県営の公園で明治時代に開設された。"
    write_url_mgmt(tmp_path, lang="ja")
    write_cache(tmp_path, source)
    # 24 copied characters, then 240 of the page's own: 9% of 264. A run must
    # be 12 characters (not 6 words) long, so --cjk-n 30 finds nothing.
    own_ja = "".join(chr(0x30A2 + i % 80) for i in range(240))
    write_page(tmp_path, "大宮公園は埼玉県さいたま市大宮区にある県営の公園" + own_ja, lang="ja")
    out = run(tmp_path, "--all-shares").stdout
    assert "9% (264 characters; longest: 24 characters" in out
    assert "0% (264 characters" in run(tmp_path, "--all-shares", "--cjk-n", "30").stdout


def test_a_short_japanese_page_needs_twice_min_words_characters(tmp_path):
    write_url_mgmt(tmp_path, lang="ja")
    write_cache(tmp_path, "大宮公園は埼玉県さいたま市大宮区にある県営の公園で明治時代に開設された。")
    write_page(tmp_path, "大宮公園は埼玉県さいたま市大宮区にある県営の公園" * 6, lang="ja")
    out = run(tmp_path, "--min-words", "100").stdout
    assert "OVERLAP:" not in out and "under_min_words=1" in out
    assert "OVERLAP:" in run(tmp_path, "--min-words", "70").stdout


def test_removed_pages_and_named_pages_only(tmp_path):
    write_url_mgmt(tmp_path)
    write_cache(tmp_path)
    write_page(tmp_path, copied(0, 120), name="gone.md", extra="status: removed\n")
    kept = write_page(tmp_path, copied(0, 120), name="kept.md")
    other = write_page(tmp_path, copied(0, 120), name="other.md")
    out = run(tmp_path, str(kept.relative_to(tmp_path))).stdout
    assert "kept.md" in out and "other.md" not in out and "gone.md" not in out
    assert "gone.md" not in run(tmp_path).stdout and other.name in run(tmp_path).stdout


def test_a_fence_closed_by_a_longer_run_does_not_swallow_the_rest_of_the_page():
    prose = cso.page_prose("before\n```\ncode\n````\nafter the fence")
    assert "code" not in prose and "after the fence" in prose
