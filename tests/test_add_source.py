"""Tests for .claude/skills/wikicommit-generate/scripts/add_source.py (#88)"""

import hashlib
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-generate" / "scripts" / "add_source.py"

_spec = importlib.util.spec_from_file_location("add_source", SCRIPT)
add_source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(add_source)


# ── sha256_file ──────────────────────────────────────────────────────────────

def test_sha256_file_matches_known_content(tmp_path):
    content = b"hello wikicommit\n"
    source = tmp_path / "sample.txt"
    source.write_bytes(content)

    expected = f"sha256:{hashlib.sha256(content).hexdigest()}"
    assert add_source.sha256_file(str(source)) == expected


# ── mgmt_path_for_file / mgmt_path_for_url ────────────────────────────────

def test_mgmt_path_for_file_mirrors_source_path(tmp_path):
    # The original extension is kept and ".md" appended (#573) — replacing the
    # extension made "paper-2024.pdf" and "paper-2024.docx" collide.
    result = add_source.mgmt_path_for_file("raw/paper-2024.pdf", tmp_path)
    assert result == tmp_path / ".wikicommit" / "source" / "path" / "raw" / "paper-2024.pdf.md"


def test_mgmt_path_for_file_nested_path(tmp_path):
    result = add_source.mgmt_path_for_file("src/auth.py", tmp_path)
    assert result == tmp_path / ".wikicommit" / "source" / "path" / "src" / "auth.py.md"


def test_mgmt_path_for_url(tmp_path):
    result = add_source.mgmt_path_for_url("https://example.com/path/to/page", tmp_path)
    assert result == tmp_path / ".wikicommit" / "source" / "url" / "example.com" / "path-to-page.md"


def test_mgmt_path_for_url_bare_domain_uses_host_as_filename(tmp_path):
    # #213: a fixed "index" fallback would collide with a real "/index" path
    # (see test_url_to_filename_bare_domain_does_not_collide_with_index_path).
    result = add_source.mgmt_path_for_url("https://example.com", tmp_path)
    assert result == tmp_path / ".wikicommit" / "source" / "url" / "example.com.md"


# ── url_to_filename (#191: host directory + path filename, #192: percent-encoded Japanese URLs) ──

@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://ja.wikipedia.org/wiki/%E3%82%B7%E3%82%A2%E3%83%88%E3%83%AB%E7%B3%BB%E3%82%B3%E3%83%BC%E3%83%92%E3%83%BC",
            "ja.wikipedia.org/wiki-シアトル系コーヒー",
        ),
        ("https://zh.wikipedia.org/wiki/%E5%92%96%E5%95%A1", "zh.wikipedia.org/wiki-咖啡"),
        ("https://example.com/100%-done", "example.com/100--done"),
        ("https://example.com/%zz/page", "example.com/-zz-page"),
        ("https://example.com", "example.com"),
    ],
)
def test_url_to_filename_percent_encoding(url, expected):
    assert add_source.url_to_filename(url) == expected


def test_url_to_filename_bare_domain_does_not_collide_with_index_path():
    # #213: "https://example.com" and "https://example.com/index" are
    # different sources and must resolve to different management file paths.
    bare = add_source.url_to_filename("https://example.com")
    index_path = add_source.url_to_filename("https://example.com/index")
    assert bare != index_path
    assert bare == "example.com"
    assert index_path == "example.com/index"


def test_url_to_filename_encoded_slash_does_not_collide_with_literal_slash():
    # %2F is an ASCII percent-encoding (not decoded, see #192 fix), so it must
    # not collapse onto the "-" produced by a literal "/" path separator.
    encoded = add_source.url_to_filename("https://example.com/foo%2Fbar")
    literal = add_source.url_to_filename("https://example.com/foo/bar")
    assert encoded != literal
    assert literal == "example.com/foo-bar"


def test_url_to_filename_groups_different_paths_under_same_host_directory():
    # #191: two pages on the same site should share a host directory instead
    # of flattening into indistinguishable sibling files.
    a = add_source.url_to_filename("https://www.keycoffee.co.jp/experience/knowledge/detail/coffee-production-area")
    b = add_source.url_to_filename("https://www.keycoffee.co.jp/experience/knowledge/detail/coffee-roasting")
    host_a, _, _ = a.partition("/")
    host_b, _, _ = b.partition("/")
    assert host_a == host_b == "www.keycoffee.co.jp"
    assert a != b


@pytest.mark.parametrize("url", ["https://", "https:///foo", "http://"])
def test_url_to_filename_rejects_hostless_url(url):
    # A hostless URL would otherwise produce a filename starting with "/",
    # which Path.__truediv__ treats as absolute and silently escapes
    # repo_root (see mgmt_path_for_url).
    with pytest.raises(ValueError):
        add_source.url_to_filename(url)


def test_process_url_hostless_url_returns_error(tmp_path):
    result, path, _msg = add_source.process_url("https:///foo", tmp_path)
    assert result == "ERROR"
    assert path == "https:///foo"
    assert not (tmp_path / "foo.md").exists()
    assert not (tmp_path.parent / "foo.md").exists()


# ── parse_frontmatter_status / update_frontmatter_status ──────────────────────

def test_parse_frontmatter_status_reads_field():
    content = add_source.build_frontmatter_file("raw/paper-2024.pdf", "sha256:abc123")
    assert add_source.parse_frontmatter_status(content) == "pending"


def test_update_frontmatter_status_changes_status_only():
    content = add_source.build_frontmatter_file("raw/paper-2024.pdf", "sha256:abc123")
    updated = add_source.update_frontmatter_status(content, "outdated")

    assert add_source.parse_frontmatter_status(updated) == "outdated"
    assert add_source.parse_frontmatter_hash(updated) == "sha256:abc123"


# ── process_file ───────────────────────────────────────────────────────────

def _write_source(tmp_path: Path, rel_path: str, content: bytes) -> None:
    source = tmp_path / rel_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)


def test_process_file_new_registration_creates_pending(tmp_path):
    _write_source(tmp_path, "raw/paper-2024.pdf", b"original content\n")

    result, path, _msg = add_source.process_file("raw/paper-2024.pdf", tmp_path)

    assert result == "CREATED"
    mgmt_file = tmp_path / path
    content = mgmt_file.read_text(encoding="utf-8")
    assert add_source.parse_frontmatter_status(content) == "pending"


def test_process_file_hash_match_non_outdated_skips(tmp_path):
    _write_source(tmp_path, "raw/paper-2024.pdf", b"original content\n")
    file_hash = add_source.sha256_file(str(tmp_path / "raw" / "paper-2024.pdf"))
    mgmt_file = add_source.mgmt_path_for_file("raw/paper-2024.pdf", tmp_path)
    mgmt_file.parent.mkdir(parents=True, exist_ok=True)
    original = add_source.update_frontmatter_status(
        add_source.build_frontmatter_file("raw/paper-2024.pdf", file_hash), "generated"
    )
    mgmt_file.write_text(original, encoding="utf-8")

    result, path, _msg = add_source.process_file("raw/paper-2024.pdf", tmp_path)

    assert result == "SKIP"
    content = mgmt_file.read_text(encoding="utf-8")
    assert content == original
    assert add_source.parse_frontmatter_status(content) == "generated"


def test_process_file_hash_match_outdated_returns_to_pending(tmp_path):
    _write_source(tmp_path, "raw/paper-2024.pdf", b"original content\n")
    file_hash = add_source.sha256_file(str(tmp_path / "raw" / "paper-2024.pdf"))
    mgmt_file = add_source.mgmt_path_for_file("raw/paper-2024.pdf", tmp_path)
    mgmt_file.parent.mkdir(parents=True, exist_ok=True)
    original = add_source.update_frontmatter_status(
        add_source.build_frontmatter_file("raw/paper-2024.pdf", file_hash), "outdated"
    )
    mgmt_file.write_text(original, encoding="utf-8")

    result, path, _msg = add_source.process_file("raw/paper-2024.pdf", tmp_path)

    assert result == "UPDATED"
    content = mgmt_file.read_text(encoding="utf-8")
    assert add_source.parse_frontmatter_status(content) == "pending"
    assert add_source.parse_frontmatter_hash(content) == file_hash


def test_process_file_hash_mismatch_non_outdated_becomes_outdated_without_hash_update(tmp_path):
    _write_source(tmp_path, "raw/paper-2024.pdf", b"changed content\n")
    old_hash = "sha256:" + "0" * 64
    mgmt_file = add_source.mgmt_path_for_file("raw/paper-2024.pdf", tmp_path)
    mgmt_file.parent.mkdir(parents=True, exist_ok=True)
    original = add_source.update_frontmatter_status(
        add_source.build_frontmatter_file("raw/paper-2024.pdf", old_hash), "generated"
    )
    mgmt_file.write_text(original, encoding="utf-8")

    result, path, _msg = add_source.process_file("raw/paper-2024.pdf", tmp_path)

    assert result == "UPDATED"
    content = mgmt_file.read_text(encoding="utf-8")
    assert add_source.parse_frontmatter_status(content) == "outdated"
    # hash は更新されない（前回生成時の参照点を保持する設計）
    assert add_source.parse_frontmatter_hash(content) == old_hash


def test_process_file_hash_mismatch_already_outdated_skips(tmp_path):
    _write_source(tmp_path, "raw/paper-2024.pdf", b"changed again\n")
    old_hash = "sha256:" + "1" * 64
    mgmt_file = add_source.mgmt_path_for_file("raw/paper-2024.pdf", tmp_path)
    mgmt_file.parent.mkdir(parents=True, exist_ok=True)
    original = add_source.update_frontmatter_status(
        add_source.build_frontmatter_file("raw/paper-2024.pdf", old_hash), "outdated"
    )
    mgmt_file.write_text(original, encoding="utf-8")

    result, path, _msg = add_source.process_file("raw/paper-2024.pdf", tmp_path)

    assert result == "SKIP"
    content = mgmt_file.read_text(encoding="utf-8")
    assert content == original
    assert add_source.parse_frontmatter_status(content) == "outdated"
    assert add_source.parse_frontmatter_hash(content) == old_hash


# ── process_file: Windows backslash path normalization (#269) ────────────────

def test_process_file_normalizes_backslash_path_separators(tmp_path):
    # A Windows-native caller may pass a backslash-separated relative path
    # (e.g. from copy-pasting a Windows Explorer path). Written verbatim into
    # a double-quoted YAML string, "\0" is parsed as a NUL escape and
    # corrupts the path (#269). process_file() must normalize it up front.
    _write_source(tmp_path, "pdfs/04_hitorioya-katei-shien.pdf", b"pdf content\n")

    result, path, _msg = add_source.process_file("pdfs\\04_hitorioya-katei-shien.pdf", tmp_path)

    assert result == "CREATED"
    # The management file itself must land under a real "pdfs/" subdirectory,
    # not a single file literally named "pdfs\04_....md".
    assert path == ".wikicommit/source/path/pdfs/04_hitorioya-katei-shien.pdf.md"
    mgmt_file = tmp_path / path
    assert mgmt_file.exists()

    content = mgmt_file.read_text(encoding="utf-8")
    assert "\\" not in content
    assert "path: 'pdfs/04_hitorioya-katei-shien.pdf'" in content

    fm = yaml.safe_load(content.split("---")[1])
    assert fm["source"]["path"] == "pdfs/04_hitorioya-katei-shien.pdf"


def test_main_from_args_include_normalizes_to_forward_slashes(tmp_path, capsys):
    _write_source(tmp_path, "src/nested/auth.py", b"# auth\n")

    exit_code = add_source.main_from_args(
        ["src", "--include", "**/*.py", "--repo-root", str(tmp_path)]
    )

    assert exit_code == 0
    mgmt_file = tmp_path / ".wikicommit" / "source" / "path" / "src" / "nested" / "auth.py.md"
    assert mgmt_file.exists()
    fm = yaml.safe_load(mgmt_file.read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["path"] == "src/nested/auth.py"


# ── build_frontmatter_file / build_frontmatter_url: single-quoted path/url (#269) ──

def test_yaml_single_quote_escapes_embedded_single_quotes():
    assert add_source._yaml_single_quote("it's") == "'it''s'"


def test_build_frontmatter_file_path_survives_stray_backslash_as_yaml():
    # Defense-in-depth: even if a backslash slipped past normalization
    # elsewhere, a single-quoted YAML scalar has no escape processing, so it
    # must still round-trip through yaml.safe_load unchanged.
    content = add_source.build_frontmatter_file("pdfs/04_foo.pdf", "sha256:abc123")
    fm = yaml.safe_load(content.split("---")[1])
    assert fm["source"]["path"] == "pdfs/04_foo.pdf"


# ── process_url ──────────────────────────────────────────────────────────────

def test_process_url_new_registration_creates_pending(tmp_path):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "CREATED"
    content = (tmp_path / path).read_text(encoding="utf-8")
    assert add_source.parse_frontmatter_status(content) == "pending"


def test_process_url_existing_skips(tmp_path):
    add_source.process_url("https://example.com/article", tmp_path)

    result, path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "SKIP"
    assert "already registered" in msg


# ── process_url: RECHECK for settled statuses (#310) ──────────────────────────

@pytest.mark.parametrize("status", ["generated", "failed", "excluded"])
def test_process_url_settled_status_returns_recheck(tmp_path, status):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    mgmt_file = tmp_path / path
    updated = add_source.update_frontmatter_status(
        mgmt_file.read_text(encoding="utf-8"), status
    )
    mgmt_file.write_text(updated, encoding="utf-8")

    result, out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "RECHECK"
    assert out_path == path
    assert status in msg
    # RECHECK must not touch the management file — Pass 1 decides via a real
    # re-fetch, and an unchanged HASH_MATCH must leave status/hash as-is.
    assert mgmt_file.read_text(encoding="utf-8") == updated


@pytest.mark.parametrize("status", ["pending", "outdated"])
def test_process_url_queued_status_still_skips(tmp_path, status):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    mgmt_file = tmp_path / path
    mgmt_file.write_text(
        add_source.update_frontmatter_status(
            mgmt_file.read_text(encoding="utf-8"), status
        ),
        encoding="utf-8",
    )

    result, out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "SKIP"
    assert "already registered" in msg


# ── partial splits on failed_pages (Issue #567) ──────────────────────────────
#
# A `partial` with pages that failed can still make progress, so Pass 1 keeps
# collecting it and SKIP is right. A `partial` that only excluded off-theme
# entities never progresses again, so Pass 1 stopped collecting it — leaving
# SKIP in place would give that URL no freshness path at all.

def _register_partial(tmp_path, failed_pages_line: str) -> str:
    _result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    mgmt_file = tmp_path / path
    content = add_source.update_frontmatter_status(
        mgmt_file.read_text(encoding="utf-8"), "partial"
    )
    content = re.sub(r"^failed_pages:.*$", failed_pages_line, content, count=1, flags=re.MULTILINE)
    mgmt_file.write_text(content, encoding="utf-8")
    return path


def test_process_url_partial_without_failed_pages_rechecks(tmp_path):
    _register_partial(tmp_path, "failed_pages: []")

    result, _out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "RECHECK"
    assert "no failed pages" in msg


def test_process_url_partial_with_failed_pages_skips(tmp_path):
    _register_partial(tmp_path, "failed_pages: [.wikicommit/entity/ja/Person/a.md]")

    result, _out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "SKIP"
    assert "already registered" in msg


def test_process_url_partial_with_block_style_failed_pages_skips(tmp_path):
    """A human editing the file by hand writes the block form, not the flow form."""
    _register_partial(tmp_path, "failed_pages:\n  - .wikicommit/entity/ja/Person/a.md")

    result, _out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "SKIP"


@pytest.mark.parametrize("failed_pages_line", ["failed_pages:", "failed_pages: ~"])
def test_process_url_partial_with_unreadable_failed_pages_rechecks(tmp_path, failed_pages_line):
    """Unreadable means "no evidence of retryable work" — the safe side is not to queue it."""
    _register_partial(tmp_path, failed_pages_line)

    result, _out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "RECHECK"


def test_main_from_args_recheck_reported_in_summary(tmp_path, capsys):
    add_source.main_from_args(["https://example.com/article", "--repo-root", str(tmp_path)])
    mgmt_file = tmp_path / ".wikicommit" / "source" / "url" / "example.com" / "article.md"
    mgmt_file.write_text(
        add_source.update_frontmatter_status(
            mgmt_file.read_text(encoding="utf-8"), "generated"
        ),
        encoding="utf-8",
    )
    capsys.readouterr()  # discard first-run output

    exit_code = add_source.main_from_args(
        ["https://example.com/article", "--repo-root", str(tmp_path)]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "RECHECK: " in captured.out
    assert "rechecked=1" in captured.out


# ── update_frontmatter_hash ────────────────────────────────────────────────

def test_update_frontmatter_hash_changes_hash_only():
    content = add_source.build_frontmatter_url("https://example.com/article")
    updated = add_source.update_frontmatter_hash(content, "sha256:abc123")

    assert add_source.parse_frontmatter_hash(updated) == "sha256:abc123"
    assert add_source.parse_frontmatter_status(updated) == "pending"


def test_update_frontmatter_hash_preserves_other_fields():
    content = add_source.build_frontmatter_file("raw/paper-2024.pdf", "sha256:old")
    updated = add_source.update_frontmatter_hash(content, "sha256:new")

    assert add_source.parse_frontmatter_hash(updated) == "sha256:new"
    assert "path: 'raw/paper-2024.pdf'" in updated


# ── write_hash ──────────────────────────────────────────────────────────────

def test_write_hash_fills_in_empty_hash_for_url_source(tmp_path):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    assert result == "CREATED"
    assert add_source.parse_frontmatter_hash((tmp_path / path).read_text(encoding="utf-8")) == '""'

    content_file = tmp_path / "fetched.txt"
    content_bytes = b"fetched page content\n"
    content_file.write_bytes(content_bytes)
    expected_hash = f"sha256:{hashlib.sha256(content_bytes).hexdigest()}"

    result, out_path, new_hash = add_source.write_hash(path, "fetched.txt", tmp_path)

    assert result == "HASH_WRITTEN"
    assert out_path == path
    assert new_hash == expected_hash
    assert add_source.parse_frontmatter_hash((tmp_path / path).read_text(encoding="utf-8")) == expected_hash


def test_write_hash_missing_mgmt_file_errors(tmp_path):
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")

    result, path, msg = add_source.write_hash(
        ".wikicommit/source/url/nonexistent.md", "fetched.txt", tmp_path
    )

    assert result == "ERROR"
    assert "does not exist" in msg


def test_write_hash_missing_content_file_errors(tmp_path):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)

    result, out_path, msg = add_source.write_hash(path, "does-not-exist.txt", tmp_path)

    assert result == "ERROR"
    assert "the content file does not exist" in msg


def test_write_hash_rejects_file_type_source(tmp_path):
    # Register a type: path source (not url/wikicommit) and confirm --write-hash refuses it.
    mgmt_file = tmp_path / ".wikicommit" / "source" / "path" / "raw" / "paper-2024.md"
    mgmt_file.parent.mkdir(parents=True)
    mgmt_file.write_text(
        add_source.build_frontmatter_file("raw/paper-2024.pdf", "sha256:abc123"), encoding="utf-8"
    )
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")

    result, out_path, msg = add_source.write_hash(
        str(mgmt_file.relative_to(tmp_path)), "fetched.txt", tmp_path
    )

    assert result == "ERROR"
    assert "source.type" in msg
    assert add_source.parse_frontmatter_hash(mgmt_file.read_text(encoding="utf-8")) == "sha256:abc123"


def test_write_hash_detects_unwritten_hash_field(tmp_path):
    # Simulate a management file whose hash line isn't indented the way the
    # regex expects (e.g. hand-edited or produced by a different code path) —
    # the substitution silently no-ops, so write_hash must not report success.
    mgmt_file = tmp_path / ".wikicommit" / "source" / "url" / "example.md"
    mgmt_file.parent.mkdir(parents=True)
    mgmt_file.write_text(
        '---\nsource:\n  type: url\n  url: "https://example.com"\nhash: ""\n\nschema:\nstatus: pending\n---\n',
        encoding="utf-8",
    )
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")

    result, out_path, msg = add_source.write_hash(
        str(mgmt_file.relative_to(tmp_path)), "fetched.txt", tmp_path
    )

    assert result == "ERROR"
    assert "was not found" in msg


def test_main_write_hash_cli_writes_hash(tmp_path, capsys):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    assert result == "CREATED"
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"cli fetched content\n")

    exit_code = add_source.main_from_args(
        ["--write-hash", path, "--content-file", "fetched.txt", "--repo-root", str(tmp_path)]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "HASH_WRITTEN:" in captured.out
    updated_content = (tmp_path / path).read_text(encoding="utf-8")
    assert add_source.parse_frontmatter_hash(updated_content) != '""'


def test_main_write_hash_without_content_file_errors(tmp_path, capsys):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)

    exit_code = add_source.main_from_args(
        ["--write-hash", path, "--repo-root", str(tmp_path)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "--content-file" in captured.err


# ── check_hash ─────────────────────────────────────────────────────────────

def test_check_hash_matches_cached_scratch_file(tmp_path):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    content_file = tmp_path / "fetched.txt"
    content_bytes = b"fetched page content\n"
    content_file.write_bytes(content_bytes)
    add_source.write_hash(path, "fetched.txt", tmp_path)

    result, out_path, msg = add_source.check_hash(path, "fetched.txt", tmp_path)

    assert result == "HASH_MATCH"
    assert out_path == path
    assert msg == f"sha256:{hashlib.sha256(content_bytes).hexdigest()}"


def test_check_hash_mismatch_when_source_changed(tmp_path):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"original content\n")
    add_source.write_hash(path, "fetched.txt", tmp_path)

    # Source was refetched with different content (e.g. after an outdated -> pending reset)
    # without the scratch file being refreshed yet.
    content_file.write_bytes(b"changed content\n")

    result, out_path, msg = add_source.check_hash(path, "fetched.txt", tmp_path)

    assert result == "HASH_MISMATCH"


def test_check_hash_mismatch_when_scratch_file_missing(tmp_path):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")
    add_source.write_hash(path, "fetched.txt", tmp_path)

    result, out_path, msg = add_source.check_hash(path, "does-not-exist.txt", tmp_path)

    assert result == "HASH_MISMATCH"
    assert "does not exist" in msg


def test_check_hash_mismatch_when_hash_still_empty(tmp_path):
    # Freshly registered url source: hash is still "" (not yet fetched at all).
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")

    result, out_path, msg = add_source.check_hash(path, "fetched.txt", tmp_path)

    assert result == "HASH_MISMATCH"
    assert "source.hash" in msg


def test_check_hash_missing_mgmt_file_errors(tmp_path):
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")

    result, path, msg = add_source.check_hash(
        ".wikicommit/source/url/nonexistent.md", "fetched.txt", tmp_path
    )

    assert result == "ERROR"
    assert "does not exist" in msg


def test_check_hash_rejects_file_type_source(tmp_path):
    mgmt_file = tmp_path / ".wikicommit" / "source" / "path" / "raw" / "paper-2024.md"
    mgmt_file.parent.mkdir(parents=True)
    mgmt_file.write_text(
        add_source.build_frontmatter_file("raw/paper-2024.pdf", "sha256:abc123"), encoding="utf-8"
    )
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")

    result, out_path, msg = add_source.check_hash(
        str(mgmt_file.relative_to(tmp_path)), "fetched.txt", tmp_path
    )

    assert result == "ERROR"
    assert "source.type" in msg


def test_main_check_hash_cli_reports_match(tmp_path, capsys):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"cli fetched content\n")
    add_source.main_from_args(
        ["--write-hash", path, "--content-file", "fetched.txt", "--repo-root", str(tmp_path)]
    )
    capsys.readouterr()  # discard write-hash output

    exit_code = add_source.main_from_args(
        ["--check-hash", path, "--content-file", "fetched.txt", "--repo-root", str(tmp_path)]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "HASH_MATCH:" in captured.out


def test_main_check_hash_cli_reports_mismatch(tmp_path, capsys):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    content_file = tmp_path / "fetched.txt"
    content_file.write_bytes(b"content\n")

    exit_code = add_source.main_from_args(
        ["--check-hash", path, "--content-file", "fetched.txt", "--repo-root", str(tmp_path)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "HASH_MISMATCH:" in captured.out


def test_main_check_hash_without_content_file_errors(tmp_path, capsys):
    result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)

    exit_code = add_source.main_from_args(
        ["--check-hash", path, "--repo-root", str(tmp_path)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "--content-file" in captured.err


# ── fetch_url (#527) ──────────────────────────────────────────────────────────

class _FakeConvertResult:
    def __init__(self, text_content):
        self.text_content = text_content


def _install_fake_markitdown(monkeypatch, *, text_content=None, raises=None, capture=None):
    """markitdown.MarkItDown を差し替え、実ネットワークアクセスなしで fetch_url() を検証する。

    add_source.fetch_url() は `from markitdown import MarkItDown` を関数内部で
    遅延importしているため（Issue #527 — .wikicommit/scripts/ のスクリプトと同様、
    markitdown 未インストールの環境でも他のCLIモードが壊れないようにする設計）、
    markitdown モジュールの MarkItDown 属性そのものを差し替えれば、fetch_url() 側の
    遅延importにも反映される。

    `markitdown`/`requests` は pyproject.toml の project dependencies ではなく、
    wiki リポジトリ側が用意する外部ツール（Prerequisite Skills テーブル参照）という
    位置づけのため、wikicommit-dev 自身の CI 環境にはインストールされていない
    （lychee 等の他の外部ツールと同じ扱い）。未インストールの環境ではこの一群の
    テストごとスキップする。
    """
    pytest.importorskip("markitdown")
    import markitdown as markitdown_module

    class FakeMarkItDown:
        def __init__(self, **kwargs):
            if capture is not None:
                capture["requests_session"] = kwargs.get("requests_session")

        def convert_url(self, url):
            if capture is not None:
                capture["url"] = url
            if raises is not None:
                raise raises
            return _FakeConvertResult(text_content)

    monkeypatch.setattr(markitdown_module, "MarkItDown", FakeMarkItDown)


def test_fetch_url_writes_converted_content(tmp_path, monkeypatch):
    _install_fake_markitdown(monkeypatch, text_content="# Fake Page\n\nHello.")

    result, path, _msg = add_source.fetch_url(
        "https://example.com/page", "scratch/page.md", tmp_path
    )

    assert result == "FETCHED"
    assert path == str(tmp_path / "scratch" / "page.md")
    assert (tmp_path / "scratch" / "page.md").read_text(encoding="utf-8") == "# Fake Page\n\nHello."


def test_fetch_url_sends_wikicommit_user_agent(tmp_path, monkeypatch):
    captured: dict = {}
    _install_fake_markitdown(monkeypatch, text_content="content", capture=captured)

    add_source.fetch_url("https://example.com/page", "out.md", tmp_path)

    assert captured["url"] == "https://example.com/page"
    assert captured["requests_session"].headers["User-Agent"] == add_source.USER_AGENT


def test_fetch_url_creates_parent_directories(tmp_path, monkeypatch):
    _install_fake_markitdown(monkeypatch, text_content="content")

    add_source.fetch_url("https://example.com/page", "a/b/c/out.md", tmp_path)

    assert (tmp_path / "a" / "b" / "c" / "out.md").exists()


def test_fetch_url_reports_error_on_exception_without_writing_file(tmp_path, monkeypatch):
    _install_fake_markitdown(monkeypatch, raises=RuntimeError("403 Client Error: Forbidden"))

    result, _path, msg = add_source.fetch_url("https://example.com/blocked", "out.md", tmp_path)

    assert result == "ERROR"
    assert "403 Client Error: Forbidden" in msg
    assert not (tmp_path / "out.md").exists()


def test_main_fetch_url_cli_writes_file(tmp_path, monkeypatch, capsys):
    _install_fake_markitdown(monkeypatch, text_content="cli content")

    exit_code = add_source.main_from_args(
        [
            "--fetch-url",
            "https://example.com/page",
            "--output",
            "out.md",
            "--repo-root",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "FETCHED:" in captured.out
    assert (tmp_path / "out.md").read_text(encoding="utf-8") == "cli content"


def test_main_fetch_url_cli_reports_error(tmp_path, monkeypatch, capsys):
    _install_fake_markitdown(monkeypatch, raises=RuntimeError("boom"))

    exit_code = add_source.main_from_args(
        [
            "--fetch-url",
            "https://example.com/broken",
            "--output",
            "out.md",
            "--repo-root",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ERROR:" in captured.err
    assert "boom" in captured.err


def test_main_fetch_url_without_output_errors(tmp_path, capsys):
    exit_code = add_source.main_from_args(
        ["--fetch-url", "https://example.com/page", "--repo-root", str(tmp_path)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "--output" in captured.err


# ── URL identity: query strings and source.url-based lookup (#572) ────────────

def test_url_to_filename_keeps_query_so_videos_do_not_collide():
    """Every "watch?v=<id>" used to derive the same "watch" stem, so the second
    video registered against the first video's management file."""
    names = {
        add_source.url_to_filename(f"https://www.youtube.com/watch?v={vid}")
        for vid in ("96jN2OCOfLs", "shZgedW15vg", "AAA")
    }
    assert len(names) == 3
    assert "www.youtube.com/watch-v-96jN2OCOfLs" in names


def test_url_to_filename_query_less_url_is_unchanged():
    """Backward compatibility: URLs without a query derive the same name as before."""
    assert add_source.url_to_filename("https://example.com/path/to/page") == "example.com/path-to-page"
    assert add_source.url_to_filename("https://example.com") == "example.com"


def test_url_to_filename_drops_tracking_params_but_keeps_identifying_ones():
    plain = add_source.url_to_filename("https://example.com/article")
    assert add_source.url_to_filename("https://example.com/article?utm_source=x") == plain
    assert add_source.url_to_filename("https://example.com/article?fbclid=abc123") == plain
    assert add_source.url_to_filename("https://example.com/article?p=7") != plain


def test_url_to_filename_is_stable_across_query_param_order():
    assert add_source.url_to_filename("https://example.com/p?b=2&a=1") == add_source.url_to_filename(
        "https://example.com/p?a=1&b=2"
    )


def test_url_to_filename_truncates_overlong_stem_with_hash_suffix():
    """A long signed/tokenized query would otherwise push the name past the
    filesystem's 255-byte limit and surface as an OSError."""
    base = "https://example.com/download?token=" + "z" * 500
    name = add_source.url_to_filename(base)
    stem = name.split("/", 1)[1]
    assert len(stem.encode("utf-8")) <= add_source._MAX_STEM_BYTES
    # Two long URLs sharing a truncated prefix must still land on distinct names.
    other = add_source.url_to_filename(base + "&page=2")
    assert name != other


def test_url_to_filename_truncates_overlong_bare_domain_query_stem():
    """A bare domain carrying only a query folds the query into the host half,
    which must get the same length guard as the path branch — otherwise the
    name blows past the filesystem's 255-byte limit and surfaces as an OSError."""
    name = add_source.url_to_filename("https://example.com?token=" + "z" * 600)
    assert "/" not in name  # still a "<host>.md" sibling, not a nested path
    assert len(name.encode("utf-8")) <= add_source._MAX_STEM_BYTES
    other = add_source.url_to_filename("https://example.com?token=" + "z" * 600 + "&page=2")
    assert name != other


def test_process_url_registers_bare_domain_with_overlong_query(tmp_path):
    result, path, _msg = add_source.process_url(
        "https://example.com?token=" + "z" * 600, tmp_path
    )
    assert result == "CREATED"
    assert (tmp_path / path).is_file()


def test_url_to_filename_truncation_does_not_split_multibyte_characters():
    name = add_source.url_to_filename("https://example.com/" + "日本語" * 200)
    stem = name.split("/", 1)[1]
    assert len(stem.encode("utf-8")) <= add_source._MAX_STEM_BYTES
    stem.encode("utf-8").decode("utf-8")  # would raise if a character were split


def test_normalize_url_for_identity_drops_fragment_and_trailing_slash():
    n = add_source.normalize_url_for_identity
    assert n("https://example.com/a#section") == n("https://example.com/a")
    assert n("https://example.com/a/") == n("https://example.com/a")


def test_process_url_registers_each_video_separately(tmp_path):
    """The originating #572 repro: three videos, one management file each."""
    paths = []
    for vid in ("AAA", "BBB", "CCC"):
        result, path, _msg = add_source.process_url(
            f"https://www.youtube.com/watch?v={vid}", tmp_path
        )
        assert result == "CREATED", (vid, result)
        paths.append(path)

    assert len(set(paths)) == 3
    for vid, path in zip(("AAA", "BBB", "CCC"), paths):
        fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
        assert fm["source"]["url"] == f"https://www.youtube.com/watch?v={vid}"


def test_process_url_settled_collision_no_longer_rechecks_a_different_url(tmp_path):
    """The dangerous variant: once the first video reached a settled status, a
    *different* video's URL returned RECHECK against it, and Pass 1 would then
    re-fetch the wrong source and report success."""
    _r, first_path, _m = add_source.process_url("https://www.youtube.com/watch?v=AAA", tmp_path)
    mgmt_file = tmp_path / first_path
    mgmt_file.write_text(
        add_source.update_frontmatter_status(mgmt_file.read_text(encoding="utf-8"), "generated"),
        encoding="utf-8",
    )

    result, path, _msg = add_source.process_url("https://www.youtube.com/watch?v=BBB", tmp_path)

    assert result == "CREATED"
    assert path != first_path


def test_process_url_tracking_param_variant_resolves_to_same_source(tmp_path):
    _r, path, _m = add_source.process_url("https://example.com/article", tmp_path)

    result, out_path, _msg = add_source.process_url(
        "https://example.com/article?utm_source=newsletter", tmp_path
    )

    assert result == "SKIP"
    assert out_path == path


def test_process_url_finds_legacy_flat_named_management_file(tmp_path):
    """Pre-#191 flat naming is never auto-migrated, so identity must come from
    source.url rather than from recomputing the filename."""
    legacy = tmp_path / ".wikicommit" / "source" / "url" / "example-com-article.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        add_source.build_frontmatter_url("https://example.com/article"), encoding="utf-8"
    )

    result, path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "SKIP", msg
    assert path == ".wikicommit/source/url/example-com-article.md"


def test_process_url_finds_pre_572_query_dropped_management_file(tmp_path):
    """A file created before this fix has the full URL in source.url even though
    its filename lost the query — re-registering it must not create a duplicate."""
    old = tmp_path / ".wikicommit" / "source" / "url" / "vimeo.com" / "video.md"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text(
        add_source.build_frontmatter_url("https://vimeo.com/video?id=1"), encoding="utf-8"
    )

    same, same_path, _m = add_source.process_url("https://vimeo.com/video?id=1", tmp_path)
    other, other_path, _m2 = add_source.process_url("https://vimeo.com/video?id=2", tmp_path)

    assert same == "SKIP"
    assert same_path == ".wikicommit/source/url/vimeo.com/video.md"
    assert other == "CREATED"
    assert other_path != same_path


def test_process_url_falls_back_to_hash_suffixed_path_on_name_collision(tmp_path):
    """Sanitization can still collapse two distinct URLs onto one stem. That must
    produce a distinct file with an explicit message, never a silent share."""
    first, first_path, _m = add_source.process_url("https://site.test/a-b", tmp_path)
    result, path, msg = add_source.process_url("https://site.test/a b", tmp_path)

    assert first == "CREATED"
    assert result == "CREATED"
    assert path != first_path
    assert "already taken by a different URL" in msg
    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["url"] == "https://site.test/a b"


def test_main_from_args_reports_collision_fallback(tmp_path, capsys):
    add_source.main_from_args(["https://site.test/a-b", "--repo-root", str(tmp_path)])
    capsys.readouterr()

    add_source.main_from_args(["https://site.test/a b", "--repo-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert "already taken by a different URL" in captured.out


def test_process_url_source_url_frontmatter_keeps_the_url_verbatim(tmp_path):
    """Normalization is internal only — provenance must record what was passed."""
    raw = "https://example.com/article?utm_source=x&b=2&a=1#frag"
    _r, path, _m = add_source.process_url(raw, tmp_path)

    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["url"] == raw


# ── path identity: extension collisions and source.path-based lookup (#573) ──

def test_mgmt_path_for_file_keeps_extension_so_siblings_do_not_collide():
    """"paper.pdf" and "paper.docx" used to derive the same "paper.md"."""
    root = Path("/repo")
    pdf = add_source.mgmt_path_for_file("raw/paper.pdf", root)
    docx = add_source.mgmt_path_for_file("raw/paper.docx", root)
    assert pdf != docx
    assert pdf.name == "paper.pdf.md"
    assert docx.name == "paper.docx.md"


def test_process_file_registers_same_stem_different_extensions_separately(tmp_path):
    _write_source(tmp_path, "raw/paper.pdf", b"pdf content\n")
    _write_source(tmp_path, "raw/paper.docx", b"docx content\n")

    pdf_result, pdf_path, _m = add_source.process_file("raw/paper.pdf", tmp_path)
    docx_result, docx_path, _m2 = add_source.process_file("raw/paper.docx", tmp_path)

    assert pdf_result == "CREATED"
    assert docx_result == "CREATED"
    assert pdf_path != docx_path
    for path, expected in ((pdf_path, "raw/paper.pdf"), (docx_path, "raw/paper.docx")):
        fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
        assert fm["source"]["path"] == expected


def test_process_file_sibling_registration_does_not_disturb_existing_source(tmp_path):
    """The core of #573: registering paper.docx used to rewrite paper.pdf's
    management file to status: outdated, so the unchanged PDF got reprocessed."""
    _write_source(tmp_path, "raw/paper.pdf", b"pdf content\n")
    _write_source(tmp_path, "raw/paper.docx", b"docx content\n")
    _r, pdf_path, _m = add_source.process_file("raw/paper.pdf", tmp_path)
    before = (tmp_path / pdf_path).read_text(encoding="utf-8")

    add_source.process_file("raw/paper.docx", tmp_path)

    assert (tmp_path / pdf_path).read_text(encoding="utf-8") == before
    assert add_source.parse_frontmatter_status(before) == "pending"


def test_process_file_finds_legacy_extension_stripped_management_file(tmp_path):
    """Pre-#573 management files are never auto-migrated, so identity must come
    from source.path rather than from recomputing the filename."""
    _write_source(tmp_path, "src/auth.py", b"# auth\n")
    legacy = tmp_path / ".wikicommit" / "source" / "path" / "src" / "auth.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        add_source.build_frontmatter_file(
            "src/auth.py", add_source.sha256_file(str(tmp_path / "src" / "auth.py"))
        ),
        encoding="utf-8",
    )

    result, path, msg = add_source.process_file("src/auth.py", tmp_path)

    assert result == "SKIP", msg
    assert path == ".wikicommit/source/path/src/auth.md"
    # No second management file under the new naming.
    assert not (tmp_path / ".wikicommit" / "source" / "path" / "src" / "auth.py.md").exists()


def test_process_file_legacy_management_file_still_transitions_to_outdated(tmp_path):
    """The scan must return the legacy file itself, so the normal hash-mismatch
    path keeps working against it rather than creating a duplicate."""
    _write_source(tmp_path, "src/auth.py", b"# auth\n")
    legacy = tmp_path / ".wikicommit" / "source" / "path" / "src" / "auth.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        add_source.build_frontmatter_file(
            "src/auth.py", add_source.sha256_file(str(tmp_path / "src" / "auth.py"))
        ),
        encoding="utf-8",
    )
    _write_source(tmp_path, "src/auth.py", b"# auth changed\n")

    result, path, msg = add_source.process_file("src/auth.py", tmp_path)

    assert result == "UPDATED"
    assert path == ".wikicommit/source/path/src/auth.md"
    assert "outdated" in msg
    assert add_source.parse_frontmatter_status(legacy.read_text(encoding="utf-8")) == "outdated"


def test_process_file_falls_back_when_derived_name_taken_by_another_source(tmp_path):
    """An extensionless real file can still land on a legacy management file's
    name. That must not share or overwrite it."""
    _write_source(tmp_path, "src/auth.py", b"# auth\n")
    legacy = tmp_path / ".wikicommit" / "source" / "path" / "src" / "auth.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        add_source.build_frontmatter_file(
            "src/auth.py", add_source.sha256_file(str(tmp_path / "src" / "auth.py"))
        ),
        encoding="utf-8",
    )
    legacy_before = legacy.read_text(encoding="utf-8")
    _write_source(tmp_path, "src/auth", b"different file\n")

    result, path, msg = add_source.process_file("src/auth", tmp_path)

    assert result == "CREATED"
    assert path != ".wikicommit/source/path/src/auth.md"
    assert "already taken by a different source path" in msg
    assert legacy.read_text(encoding="utf-8") == legacy_before
    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["path"] == "src/auth"


def test_normalize_source_path_absorbs_backslashes_and_dot_prefix():
    n = add_source.normalize_source_path
    assert n("pdfs\\a.pdf") == "pdfs/a.pdf"
    assert n("./raw/paper.pdf") == "raw/paper.pdf"
    assert n("raw/paper.pdf") == "raw/paper.pdf"


def test_process_file_matches_existing_source_across_dot_prefix(tmp_path):
    _write_source(tmp_path, "raw/paper.pdf", b"pdf content\n")
    _r, path, _m = add_source.process_file("raw/paper.pdf", tmp_path)

    result, out_path, _msg = add_source.process_file("./raw/paper.pdf", tmp_path)

    assert result == "SKIP"
    assert out_path == path


def test_process_file_matches_bom_prefixed_management_file(tmp_path):
    """A management file rewritten with a UTF-8 BOM (some Windows editors do
    this) must still be found by the source.path scan — reading it as plain
    utf-8 hides the frontmatter, which used to make process_file() think the
    derived name belonged to a different source and write a second management
    file for the same source."""
    _write_source(tmp_path, "raw/paper.pdf", b"pdf content\n")
    _r, path, _m = add_source.process_file("raw/paper.pdf", tmp_path)
    mgmt = tmp_path / path
    mgmt.write_text(mgmt.read_text(encoding="utf-8"), encoding="utf-8-sig")

    result, out_path, msg = add_source.process_file("raw/paper.pdf", tmp_path)

    assert (result, out_path) == ("SKIP", path), msg
    assert sorted(p.name for p in mgmt.parent.iterdir()) == [mgmt.name]


def test_process_file_truncates_management_name_that_would_exceed_name_limit(tmp_path):
    """Appending ".md" makes the derived name longer than the source filename,
    so a name already near the filesystem's 255-byte limit must be truncated
    with a hash suffix instead of failing the write with a bare OSError."""
    long_name = "x" * 250 + ".pdf"
    _write_source(tmp_path, f"raw/{long_name}", b"content\n")

    result, path, _msg = add_source.process_file(f"raw/{long_name}", tmp_path)

    assert result == "CREATED"
    assert len(Path(path).name.encode("utf-8")) <= 255
    assert (tmp_path / path).is_file()
    # The same source still resolves to that management file on re-registration.
    assert add_source.process_file(f"raw/{long_name}", tmp_path)[:2] == ("SKIP", path)


def test_process_file_stores_normalized_source_path(tmp_path):
    """Identity comparison strips a leading "./", so the stored source.path
    must be stripped too — otherwise the recorded value depends on how the
    source happened to be spelled on its first registration."""
    _write_source(tmp_path, "raw/paper.pdf", b"pdf content\n")

    _result, path, _msg = add_source.process_file("./raw/paper.pdf", tmp_path)

    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["path"] == "raw/paper.pdf"


def test_main_from_args_include_reuses_one_scan_across_the_batch(tmp_path):
    """Bulk registration must not rescan .wikicommit/source/path/ per source
    (that is O(N^2) reads), yet must still see files created earlier in the
    same batch."""
    for i in range(3):
        _write_source(tmp_path, f"src/f{i}.py", f"# {i}\n".encode())

    assert add_source.main_from_args(["src", "--include", "**/*.py", "--repo-root", str(tmp_path)]) == 0
    mgmt_dir = tmp_path / ".wikicommit" / "source" / "path" / "src"
    assert sorted(p.name for p in mgmt_dir.iterdir()) == ["f0.py.md", "f1.py.md", "f2.py.md"]

    # Re-running must reuse those management files rather than create more.
    assert add_source.main_from_args(["src", "--include", "**/*.py", "--repo-root", str(tmp_path)]) == 0
    assert len(list(mgmt_dir.iterdir())) == 3


# ── source.license (#558) ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://it.wikipedia.org/wiki/Decameron", "CC-BY-SA-4.0"),
        ("https://ja.wikipedia.org/wiki/X", "CC-BY-SA-4.0"),
        ("https://wikipedia.org/wiki/X", "CC-BY-SA-4.0"),
        ("https://it.wikisource.org/wiki/X", "CC-BY-SA-4.0"),
        ("https://www.wikidata.org/wiki/Q1", "CC0-1.0"),
        ("https://www.city.saitama.lg.jp/page.html", ""),
        ("https://example.com/wikipedia.org", ""),
        ("https://notwikipedia.org/x", ""),
        ("not a url", ""),
    ],
)
def test_license_for_url_matches_the_registrable_domain_only(url, expected):
    assert add_source.license_for_url(url) == expected


def test_process_url_records_the_known_domain_license(tmp_path):
    _result, path, msg = add_source.process_url("https://it.wikipedia.org/wiki/Decameron", tmp_path)

    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["license"] == "CC-BY-SA-4.0"
    assert "CC-BY-SA-4.0" in msg


def test_process_url_leaves_license_blank_for_an_unknown_domain(tmp_path):
    """Blank means "unknown", not "unrestricted" — the field is present so a
    human can fill it in, and validate_frontmatter.py rejects an empty string
    on a page rather than letting it look like a recorded license."""
    _result, path, msg = add_source.process_url("https://example.com/article", tmp_path)

    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["license"] is None
    assert "license" not in msg


def test_explicit_license_overrides_the_known_domain_table(tmp_path):
    _result, path, _msg = add_source.process_url(
        "https://it.wikipedia.org/wiki/Decameron", tmp_path, "all-rights-reserved"
    )

    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["license"] == "all-rights-reserved"


def test_process_file_records_an_explicit_license(tmp_path):
    _write_source(tmp_path, "raw/paper.pdf", b"pdf content\n")

    _result, path, _msg = add_source.process_file("raw/paper.pdf", tmp_path, None, "CC-BY-4.0")

    fm = yaml.safe_load((tmp_path / path).read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["license"] == "CC-BY-4.0"


def test_main_from_args_passes_license_through(tmp_path):
    _write_source(tmp_path, "raw/paper.pdf", b"pdf content\n")

    assert (
        add_source.main_from_args(
            ["raw/paper.pdf", "--license", "PDL-1.0", "--repo-root", str(tmp_path)]
        )
        == 0
    )

    mgmt = tmp_path / ".wikicommit" / "source" / "path" / "raw" / "paper.pdf.md"
    fm = yaml.safe_load(mgmt.read_text(encoding="utf-8").split("---")[1])
    assert fm["source"]["license"] == "PDL-1.0"


# ── share-alike notice (Issue #570) ──────────────────────────────────────────

@pytest.mark.parametrize(
    "value,expected",
    [
        ("CC-BY-SA-4.0", True),
        ("cc-by-sa-3.0", True),
        ("  CC-BY-SA-4.0  ", True),
        ("GFDL-1.3", True),
        ("ODbL-1.0", True),
        ("CC-BY-NC-SA-4.0", True),
        ("CC0-1.0", False),
        ("CC-BY-2.5", False),
        ("all-rights-reserved", False),
        ("Saitama City website terms of use", False),
        ("", False),
    ],
)
def test_is_share_alike(value, expected):
    assert add_source.is_share_alike(value) is expected


def test_created_note_warns_on_a_share_alike_source(tmp_path):
    result, _path, msg = add_source.process_url("https://ja.wikipedia.org/wiki/X", tmp_path)
    assert result == "CREATED"
    assert "CC-BY-SA-4.0" in msg
    assert "share-alike license" in msg


def test_created_note_is_silent_for_a_non_share_alike_license(tmp_path):
    result, _path, msg = add_source.process_url("https://www.wikidata.org/wiki/Q1", tmp_path)
    assert result == "CREATED"
    assert "CC0-1.0" in msg
    assert "share-alike" not in msg


def test_created_note_warns_for_an_explicit_share_alike_override(tmp_path):
    result, _path, msg = add_source.process_url(
        "https://example.com/a", tmp_path, license_override="CC-BY-SA-4.0"
    )
    assert result == "CREATED"
    assert "share-alike license" in msg


def test_created_note_warns_for_a_share_alike_file_source(tmp_path):
    # The known-domain table cannot reach a type: path source, so --license is the
    # only entry point — but the obligation is the same one, so the notice must fire.
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "article.html").write_text("x", encoding="utf-8")
    result, _path, msg = add_source.process_file(
        "raw/article.html", tmp_path, None, "CC-BY-SA-4.0"
    )
    assert result == "CREATED"
    assert "share-alike license" in msg


def test_created_note_is_silent_for_a_non_share_alike_file_source(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "article.html").write_text("x", encoding="utf-8")
    result, _path, msg = add_source.process_file(
        "raw/article.html", tmp_path, None, "CC-BY-4.0"
    )
    assert result == "CREATED"
    assert "share-alike" not in msg


# ── --license-for-url: the known-domain table, queried one step before
#    registration so wikicommit-collect can show it on a candidate (Issue #646) ─

def test_license_for_url_cli_reports_share_alike(capsys):
    exit_code = add_source.main_from_args(
        ["--license-for-url", "https://ja.wikipedia.org/wiki/Tokyo"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "LICENSE: CC-BY-SA-4.0 (share-alike)"


def test_license_for_url_cli_omits_marker_for_non_share_alike(capsys):
    exit_code = add_source.main_from_args(
        ["--license-for-url", "https://www.wikidata.org/wiki/Q1"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "LICENSE: CC0-1.0"
    assert "share-alike" not in captured.out


def test_license_for_url_cli_reports_unknown_without_failing(capsys):
    """Not in the table is not an error, and must not read as 'unrestricted'."""
    exit_code = add_source.main_from_args(
        ["--license-for-url", "https://example.com/article"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "UNKNOWN: https://example.com/article"
    assert "LICENSE:" not in captured.out


def test_license_for_url_cli_reports_unknown_for_an_unparseable_url(capsys):
    """A URL urlsplit() refuses to parse still has to leave via UNKNOWN/exit 0 —
    the caller's three documented outcomes have no branch for a traceback."""
    exit_code = add_source.main_from_args(["--license-for-url", "https://[abc/x"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "UNKNOWN: https://[abc/x"


def test_license_for_url_cli_matches_registration_table(tmp_path, capsys):
    """The lookup and the value registration records must not drift apart —
    showing a candidate one license and then recording another would be worse
    than showing nothing."""
    add_source.main_from_args(
        ["--license-for-url", "https://it.wikisource.org/wiki/Decameron"]
    )
    looked_up = capsys.readouterr().out.strip().removeprefix("LICENSE: ").split(" ")[0]

    _result, path, _msg = add_source.process_url(
        "https://it.wikisource.org/wiki/Decameron", tmp_path
    )
    mgmt = (tmp_path / path).read_text(encoding="utf-8")
    front = yaml.safe_load(mgmt.split("---", 2)[1])

    assert front["source"]["license"] == looked_up


def test_license_for_url_cli_does_not_register_anything(tmp_path, capsys):
    add_source.main_from_args(
        ["--license-for-url", "https://ja.wikipedia.org/wiki/Tokyo",
         "--repo-root", str(tmp_path)]
    )

    assert not (tmp_path / ".wikicommit" / "source").exists()


def test_no_source_error_mentions_license_for_url(capsys):
    exit_code = add_source.main_from_args([])

    assert exit_code == 1
    assert "--license-for-url" in capsys.readouterr().err


# ── partial-extraction notice (Issue #715) ───────────────────────────────────
#
# A GitHub issue/PR URL fetches successfully and yields the thread's *body*,
# but every comment on it is dropped with no error at all — the management file
# still records status: generated with a non-zero extracted_tokens. That is the
# same failure class Issue #574 named for YouTube transcripts, so it is handled
# the same way the ShareAlike notice is: told once at registration, never
# blocking. See docs/DesignDoc-pipeline.md §6.1.


@pytest.mark.parametrize(
    "url,expected",
    [
        # Confirmed directly in Issue #715 (three public issues, zero comments
        # extracted from any of them while all three bodies came through).
        ("https://github.com/vercel-labs/skills/issues/851", True),
        ("https://github.com/o/r/issues/1", True),
        # Same comment timeline; included on that basis (see the callout).
        ("https://github.com/astral-sh/ruff/pull/20522", True),
        ("https://github.com/o/r/pull/12/files", True),
        # Host matching follows license_for_url(): leading www. is ignored.
        ("https://www.github.com/o/r/issues/1", True),
        # Not github.com — a path that merely looks like one must not match.
        ("https://example.com/o/r/issues/1", False),
        ("https://gist.github.com/someone/abc123", False),
        # github.com URLs whose fetch really is complete: flagging these would
        # put a wrong notice on the most common shapes of GitHub URL.
        ("https://github.com/o/r", False),
        ("https://github.com/o/r/blob/main/README.md", False),
        ("https://github.com/o/r/releases/tag/v1.0.0", False),
        # Deliberately out of the table: same product family, but a different
        # surface nobody has confirmed (see the callout).
        ("https://github.com/o/r/discussions/5", False),
        # Not an issue/PR number.
        ("https://github.com/o/r/issues", False),
        ("https://github.com/o/r/pull/abc", False),
    ],
)
def test_partial_extraction_note_matches_only_confirmed_url_shapes(url, expected):
    assert bool(add_source.partial_extraction_note(url)) is expected


def test_created_note_warns_on_a_github_issue_url(tmp_path):
    result, _path, msg = add_source.process_url(
        "https://github.com/o/r/issues/851", tmp_path
    )
    assert result == "CREATED"
    assert "partial extraction" in msg
    assert "comment" in msg


def test_created_note_is_silent_for_an_ordinary_github_url(tmp_path):
    result, _path, msg = add_source.process_url(
        "https://github.com/o/r/blob/main/README.md", tmp_path
    )
    assert result == "CREATED"
    assert "partial extraction" not in msg


def test_partial_extraction_notice_does_not_block_or_fail_registration(tmp_path):
    """The notice is not a guard: the source registers exactly as any other URL
    would, with the same status. An issue whose body is the whole point is a
    perfectly good source, so stopping here would kill a legitimate use."""
    result, path, _msg = add_source.process_url(
        "https://github.com/o/r/issues/851", tmp_path
    )

    assert result == "CREATED"
    mgmt = (tmp_path / path).read_text(encoding="utf-8")
    front = yaml.safe_load(mgmt.split("---", 2)[1])
    assert front["status"] == "pending"
    assert front["source"]["url"] == "https://github.com/o/r/issues/851"


def test_partial_extraction_notice_coexists_with_the_share_alike_notice(tmp_path):
    """Both notices ride on the same created_note, so a source that triggers
    both must not have one silently overwrite the other."""
    result, _path, msg = add_source.process_url(
        "https://github.com/o/r/issues/851", tmp_path, license_override="CC-BY-SA-4.0"
    )

    assert result == "CREATED"
    assert "share-alike license" in msg
    assert "partial extraction" in msg


# ── retracted sources (Issue #737) ────────────────────────────────────────────

RETRACTION_SECTION = (
    "\n## Retraction Reason\n\n"
    "The 2019 figures contradict the city's own published statistics;\n"
    "the publisher confirmed the page was never corrected.\n"
)


def _retract(mgmt_file: Path, *, with_reason: bool = True) -> None:
    content = add_source.update_frontmatter_status(
        mgmt_file.read_text(encoding="utf-8"), "retracted"
    )
    if with_reason:
        content = content.rstrip("\n") + "\n" + RETRACTION_SECTION
    mgmt_file.write_text(content, encoding="utf-8")


def test_process_url_retracted_returns_retracted_not_skip(tmp_path):
    """`SKIP: already registered` says nothing about *why* the source is unusable.

    That message is the whole defect Issue #737's hole (2) names: a human
    re-registering the same URL learns only that it is on file already, never
    that someone withdrew it.
    """
    _result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    mgmt_file = tmp_path / path
    _retract(mgmt_file)
    before = mgmt_file.read_text(encoding="utf-8")

    result, out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "RETRACTED"
    assert out_path == path
    assert "contradict the city's own published statistics" in msg
    # A retraction is never lifted by re-registering; nothing is written back.
    assert mgmt_file.read_text(encoding="utf-8") == before


def test_process_url_retracted_without_reason_says_so(tmp_path):
    _result, path, _msg = add_source.process_url("https://example.com/article", tmp_path)
    _retract(tmp_path / path, with_reason=False)

    result, _out_path, msg = add_source.process_url("https://example.com/article", tmp_path)

    assert result == "RETRACTED"
    assert "no ## Retraction Reason recorded" in msg


def test_process_file_retracted_survives_a_source_edit(tmp_path):
    """The `type: path` mirror of the same hole, plus the one in Issue #737's
    hole (1): a changed hash must not walk the file back to `outdated`, which
    would re-queue it for Pass 1 and lift the retraction silently."""
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("original", encoding="utf-8")

    _result, path, _msg = add_source.process_file("raw/paper.txt", tmp_path)
    mgmt_file = tmp_path / path
    _retract(mgmt_file)
    before = mgmt_file.read_text(encoding="utf-8")

    source.write_text("edited after the retraction", encoding="utf-8")
    result, out_path, msg = add_source.process_file("raw/paper.txt", tmp_path)

    assert result == "RETRACTED"
    assert out_path == path
    assert "contradict the city's own published statistics" in msg
    assert mgmt_file.read_text(encoding="utf-8") == before


def test_parse_retraction_reason_collapses_and_truncates():
    long_reason = "word " * 100
    content = f"---\nstatus: retracted\n---\n\n## Retraction Reason\n\n{long_reason}\n"
    parsed = add_source.parse_retraction_reason(content)
    assert "\n" not in parsed
    assert len(parsed) <= 200
    assert parsed.endswith("...")


def test_parse_retraction_reason_stops_at_the_next_heading():
    content = (
        "---\nstatus: retracted\n---\n\n"
        "## Retraction Reason\n\nWithdrawn by the editor.\n\n"
        "## User Notes\n\nUnrelated note that must not leak into the reason.\n"
    )
    assert add_source.parse_retraction_reason(content) == "Withdrawn by the editor."


def test_parse_retraction_reason_absent_returns_empty_string():
    assert add_source.parse_retraction_reason("---\nstatus: retracted\n---\n") == ""
