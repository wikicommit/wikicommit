"""Tests for .wikicommit/scripts/match_index_only.py (Issue #1032).

`index_only:` takes two shapes — a domain (the whole host) and a page (that one
page) — and the shape is the meaning. These tests pin the two apart, and pin the
one behavior change the Issue accepted: an entry carrying a path used to mean its
whole host and now means that page.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).parent.parent
    / ".claude"
    / "skills"
    / "wikicommit-init"
    / "scripts"
    / "templates"
    / "scripts"
    / "match_index_only.py"
)


def run(policy: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--policy", str(policy), *args],
        capture_output=True,
        text=True,
    )


def write(tmp_path: Path, entries: list[str]) -> Path:
    path = tmp_path / "source-policy.md"
    lines = "".join(f"    - {e}\n" for e in entries)
    path.write_text(f"---\nwikicommit:\n  index_only:\n{lines}---\n", encoding="utf-8")
    return path


def test_a_domain_entry_covers_the_whole_host(tmp_path):
    policy = write(tmp_path, ["en.wikipedia.org"])
    result = run(policy, "match", "https://en.wikipedia.org/wiki/Saitama")
    assert result.returncode == 0
    assert result.stdout.startswith("INDEX_ONLY:")
    assert "domain" in result.stdout


def test_a_domain_entry_ignores_scheme_and_www(tmp_path):
    policy = write(tmp_path, ["https://www.example.com/"])
    result = run(policy, "match", "http://example.com/anything")
    assert result.stdout.startswith("INDEX_ONLY:")
    assert "domain" in result.stdout


def test_a_domain_entry_does_not_cover_a_subdomain(tmp_path):
    policy = write(tmp_path, ["example.com"])
    result = run(policy, "match", "https://blog.example.com/post")
    assert result.stdout.startswith("OK:")


def test_a_page_entry_covers_that_page_only(tmp_path):
    """The case the Issue exists for: an awesome list on github.com must not
    turn every GitHub README into an index."""
    policy = write(tmp_path, ["https://github.com/example/awesome-foo"])
    hit = run(policy, "match", "https://github.com/example/awesome-foo/")
    assert hit.stdout.startswith("INDEX_ONLY:")
    assert "page" in hit.stdout
    miss = run(policy, "match", "https://github.com/example/some-tool")
    assert miss.stdout.startswith("OK:")


def test_a_page_entry_ignores_fragment_and_www(tmp_path):
    policy = write(tmp_path, ["https://github.com/example/awesome-foo"])
    result = run(policy, "match", "https://www.github.com/example/awesome-foo#tools")
    assert result.stdout.startswith("INDEX_ONLY:")


def test_a_page_entry_compares_the_path_percent_decoded(tmp_path):
    policy = write(tmp_path, ["https://ja.wikipedia.org/wiki/さいたま市"])
    encoded = "https://ja.wikipedia.org/wiki/%E3%81%95%E3%81%84%E3%81%9F%E3%81%BE%E5%B8%82"
    assert run(policy, "match", encoded).stdout.startswith("INDEX_ONLY:")


def test_a_page_entry_keeps_the_query(tmp_path):
    """Where the query names the page, dropping it would widen one page to all."""
    policy = write(tmp_path, ["https://example.org/index.php?title=A"])
    assert run(policy, "match", "https://example.org/index.php?title=A").stdout.startswith("INDEX_ONLY:")
    assert run(policy, "match", "https://example.org/index.php?title=B").stdout.startswith("OK:")


def test_list_pages_returns_only_page_entries(tmp_path):
    policy = write(tmp_path, ["en.wikipedia.org", "https://github.com/example/awesome-foo"])
    result = run(policy, "list-pages")
    assert result.returncode == 0
    assert "PAGE: https://github.com/example/awesome-foo" in result.stdout
    assert "en.wikipedia.org" not in result.stdout
    assert "SUMMARY: index_only_pages=1" in result.stdout


def test_a_missing_policy_matches_nothing(tmp_path):
    result = run(tmp_path / "absent.md", "match", "https://en.wikipedia.org/wiki/X")
    assert result.returncode == 0
    assert result.stdout.startswith("OK:")


def test_an_unparseable_policy_warns_and_matches_nothing(tmp_path):
    path = tmp_path / "source-policy.md"
    path.write_text("---\nwikicommit: [unclosed\n---\n", encoding="utf-8")
    result = run(path, "match", "https://en.wikipedia.org/wiki/X")
    assert result.returncode == 0
    assert result.stdout.startswith("OK:")
    assert "WARNING:" in result.stderr


def test_the_shipped_template_lists_nothing(tmp_path):
    template = SCRIPT.parent.parent / "source-policy.md"
    result = run(template, "list-pages")
    assert "SUMMARY: index_only_pages=0" in result.stdout


def test_a_malformed_entry_does_not_crash_the_lookup(tmp_path):
    policy = write(tmp_path, ['"https://[bad/x"', "en.wikipedia.org"])
    result = run(policy, "match", "https://en.wikipedia.org/wiki/X")
    assert result.returncode == 0
    assert result.stdout.startswith("INDEX_ONLY:")


def test_a_page_entry_compares_the_query_percent_decoded(tmp_path):
    policy = write(tmp_path, ["https://ja.wikipedia.org/w/index.php?title=さいたま市"])
    encoded = "https://ja.wikipedia.org/w/index.php?title=%E3%81%95%E3%81%84%E3%81%9F%E3%81%BE%E5%B8%82"
    assert run(policy, "match", encoded).stdout.startswith("INDEX_ONLY:")
