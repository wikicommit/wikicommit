"""Tests for .wikicommit/scripts/check_retracted_sources.py (Issue #737)"""

import re
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_retracted_sources.py"


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_path_mgmt(root: Path, rel: str, *, path: str, status: str) -> Path:
    mgmt = root / ".wikicommit" / "source" / "path" / rel
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        textwrap.dedent(f"""\
            ---
            source:
              type: path
              path: {path}
              hash: sha256:abc123
            status: {status}
            ---
            """),
        encoding="utf-8",
    )
    return mgmt


def write_mgmt(root: Path, rel: str, *, url: str, status: str, reason: str = "") -> Path:
    mgmt = root / ".wikicommit" / "source" / "url" / rel
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    body = f"\n## Retraction Reason\n\n{reason}\n" if reason else ""
    mgmt.write_text(
        textwrap.dedent(f"""\
            ---
            source:
              type: url
              url: {url}
              hash: sha256:abc123
            status: {status}
            ---
            """) + body,
        encoding="utf-8",
    )
    return mgmt


def write_page(root: Path, rel: str, urls: list[str], *, extra: str = "") -> Path:
    page = root / ".wikicommit" / "entity" / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    sources = "".join(
        f"  - type: url\n    url: {u}\n    hash: sha256:abc123\n" for u in urls
    )
    page.write_text(
        f'---\ntitle: "T"\nlang: ja\ntype: "schema:Place"\n{extra}sources:\n{sources}---\n\nbody\n',
        encoding="utf-8",
    )
    return page


def test_no_source_dir_reports_zero_of_both(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: retracted_sources=0, affected_pages=0" in result.stdout


def test_nothing_retracted_is_distinguishable_from_no_affected_pages(tmp_path):
    """`retracted_sources=0` and `affected_pages=0` are different facts, and
    the summary reports both so a reader can tell them apart."""
    write_mgmt(tmp_path, "example.com/a.md", url="https://example.com/a", status="generated")
    write_page(tmp_path, "ja/Place/x.md", ["https://example.com/a"])

    result = run(tmp_path)
    assert "RETRACTED_SOURCE:" not in result.stdout
    assert "SUMMARY: retracted_sources=0, affected_pages=0" in result.stdout


def test_page_on_a_retracted_source_is_reported_with_remaining_count(tmp_path):
    write_mgmt(
        tmp_path, "example.com/bad.md",
        url="https://example.com/bad", status="retracted", reason="Figures never corrected.",
    )
    write_mgmt(tmp_path, "example.com/ok.md", url="https://example.com/ok", status="generated")
    write_page(tmp_path, "ja/Place/x.md", ["https://example.com/bad", "https://example.com/ok"])

    result = run(tmp_path)
    assert result.returncode == 0
    out = result.stdout
    assert "RETRACTED_SOURCE:" in out
    assert "https://example.com/bad" in out
    # The remaining-source count is what decides remove vs. regenerate vs. fix.
    assert "1 other source(s) remain on this page" in out
    assert "page: .wikicommit/entity/ja/Place/x.md" in out
    assert "SUMMARY: retracted_sources=1, affected_pages=1" in out


def test_page_left_with_no_other_source_says_zero_remain(tmp_path):
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    write_page(tmp_path, "ja/Place/x.md", ["https://example.com/bad"])

    result = run(tmp_path)
    assert "0 other source(s) remain on this page" in result.stdout


def test_a_surviving_manual_source_is_counted_as_remaining(tmp_path):
    """A `type: manual` entry names neither a path nor a url, so counting
    identities instead of entries would make it invisible — and Step 12 reads
    "0 other source(s) remain" as "usually a /wikicommit-remove", which would
    push a human toward deleting a page that still rests on their own
    assertion."""
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    page = tmp_path / ".wikicommit" / "entity" / "ja" / "Place" / "x.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        '---\ntitle: "T"\nlang: ja\ntype: "schema:Place"\nsources:\n'
        "  - type: url\n    url: https://example.com/bad\n    hash: sha256:abc123\n"
        "  - type: manual\n    author: taro\n    created_at: 2026-01-01\n---\n\nbody\n",
        encoding="utf-8",
    )

    result = run(tmp_path)
    assert "1 other source(s) remain on this page" in result.stdout


def test_a_source_listed_twice_is_reported_once(tmp_path):
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    write_page(
        tmp_path, "ja/Place/x.md", ["https://example.com/bad", "https://example.com/bad"]
    )

    result = run(tmp_path)
    assert result.stdout.count("RETRACTED_SOURCE:") == 1
    assert "0 other source(s) remain on this page" in result.stdout


def test_unaffected_page_is_not_reported(tmp_path):
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    write_page(tmp_path, "ja/Place/x.md", ["https://example.com/other"])

    result = run(tmp_path)
    assert "RETRACTED_SOURCE:" not in result.stdout
    assert "SUMMARY: retracted_sources=1, affected_pages=0" in result.stdout


def test_removed_pages_are_excluded(tmp_path):
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    write_page(tmp_path, "ja/Place/x.md", ["https://example.com/bad"], extra="status: removed\n")

    result = run(tmp_path)
    assert "SUMMARY: retracted_sources=1, affected_pages=0" in result.stdout


def test_path_sources_are_matched_on_source_path(tmp_path):
    mgmt = tmp_path / ".wikicommit" / "source" / "path" / "raw" / "paper.pdf.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper.pdf
              hash: sha256:abc123
            status: retracted
            ---
            """),
        encoding="utf-8",
    )
    page = tmp_path / ".wikicommit" / "entity" / "ja" / "Place" / "x.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        '---\ntitle: "T"\nlang: ja\ntype: "schema:Place"\n'
        "sources:\n  - type: path\n    path: raw/paper.pdf\n    hash: sha256:abc123\n---\n\nbody\n",
        encoding="utf-8",
    )

    result = run(tmp_path)
    assert "raw/paper.pdf" in result.stdout
    assert "SUMMARY: retracted_sources=1, affected_pages=1" in result.stdout


def test_view_pages_are_scanned_but_never_match(tmp_path):
    """A view page carries `derived_from`, not `sources[]`, so it can never
    match here — but it is scanned rather than excluded, so "view pages were
    not looked at" is not a silent property of the check."""
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    view = tmp_path / ".wikicommit" / "view" / "ja" / "topic.md"
    view.parent.mkdir(parents=True, exist_ok=True)
    view.write_text(
        '---\ntitle: "V"\nlang: ja\nderived_from:\n  - path: .wikicommit/entity/ja/Place/x.md\n'
        "    source_commit: abc\n---\n\nbody\n",
        encoding="utf-8",
    )

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: retracted_sources=1, affected_pages=0" in result.stdout


# --- `--list` (Issue #928) ---------------------------------------------------
#
# The second caller of this script. `/wikicommit-review` and `/wikicommit-fix`
# both re-fetch a page's `sources[]` and read the documents, neither goes
# through `resolve_source_cache_path.py`, and so neither saw a retraction at
# all: review was measuring pages against a document a person had withdrawn and
# passing them for being faithful to it.


def test_list_names_each_retracted_source_and_its_management_file(tmp_path):
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    write_mgmt(tmp_path, "example.com/ok.md", url="https://example.com/ok", status="generated")

    result = run(tmp_path, "--list")
    assert result.returncode == 0
    assert (
        "RETRACTED: https://example.com/bad "
        "(.wikicommit/source/url/example.com/bad.md)" in result.stdout
    )
    # A source that was not withdrawn must not appear: the callers drop exactly
    # what this prints, so a false line silently removes real ground truth.
    assert "https://example.com/ok" not in result.stdout
    assert "SUMMARY: retracted_sources=1" in result.stdout


def test_list_matches_the_line_shape_the_resolver_already_uses(tmp_path):
    """`RETRACTED: <identity> (<management file>)` is a shared contract.

    `resolve_source_cache_path.py` prints the same shape for the third
    reference-side path (`/wikicommit-ask --include-source`), so all three read
    one form. The management file is part of it and not decoration: it is where
    the human wrote `## Retraction Reason`, the only place the *why* exists.
    """
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")

    line = next(
        line
        for line in run(tmp_path, "--list").stdout.splitlines()
        if line.startswith("RETRACTED:")
    )
    assert re.fullmatch(r"RETRACTED: \S+ \(\.wikicommit/source/.+\.md\)", line), line


def test_list_omits_the_affected_pages_count(tmp_path):
    """This mode reads no page, and a zero would read as a scan that found none."""
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")

    result = run(tmp_path, "--list")
    assert "SUMMARY: retracted_sources=1" in result.stdout
    assert "affected_pages" not in result.stdout


def test_list_does_not_scan_pages(tmp_path):
    """The callers run this before fetching, once per run — it must not pay for
    a full page walk, and must not report page-level findings they did not ask
    for."""
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    write_page(tmp_path, "ja/Place/x.md", ["https://example.com/bad"])

    result = run(tmp_path, "--list")
    assert "RETRACTED_SOURCE:" not in result.stdout
    assert "page:" not in result.stdout


def test_list_reports_zero_rather_than_nothing_when_none_are_retracted(tmp_path):
    write_mgmt(tmp_path, "example.com/ok.md", url="https://example.com/ok", status="generated")

    result = run(tmp_path, "--list")
    assert result.returncode == 0
    assert result.stdout.strip() == "SUMMARY: retracted_sources=0"


def test_list_covers_path_sources_too(tmp_path):
    """The identity key is `source.path` for these, the same value a page's
    `sources[]` entry carries — so the callers can match on it directly."""
    write_path_mgmt(tmp_path, "raw/paper.pdf.md", path="raw/paper.pdf", status="retracted")

    result = run(tmp_path, "--list")
    assert (
        "RETRACTED: raw/paper.pdf (.wikicommit/source/path/raw/paper.pdf.md)" in result.stdout
    )


def test_list_exits_zero_even_with_retractions(tmp_path):
    """A retraction existing is not an error. Signalling one through the exit
    code is `resolve_source_cache_path.py`'s job (exit 2), and it can do that
    because it answers about a single identifier; a listing cannot.
    """
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    assert run(tmp_path, "--list").returncode == 0


def test_list_and_the_default_mode_agree_on_what_is_retracted(tmp_path):
    """One table, two readings. If these ever disagree, the callers' guard and
    the health check would be naming different sets."""
    write_mgmt(tmp_path, "example.com/bad.md", url="https://example.com/bad", status="retracted")
    write_path_mgmt(tmp_path, "raw/paper.pdf.md", path="raw/paper.pdf", status="retracted")
    write_page(tmp_path, "ja/Place/x.md", ["https://example.com/bad"])

    listed = {
        line.split("RETRACTED: ", 1)[1].rsplit(" (", 1)[0]
        for line in run(tmp_path, "--list").stdout.splitlines()
        if line.startswith("RETRACTED:")
    }
    assert listed == {"https://example.com/bad", "raw/paper.pdf"}
    assert "SUMMARY: retracted_sources=2, affected_pages=1" in run(tmp_path).stdout
