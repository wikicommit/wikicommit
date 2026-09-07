"""Tests for .wikicommit/scripts/check_retracted_sources.py (Issue #737)"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_retracted_sources.py"


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


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
