"""Tests for .wikicommit/scripts/reconcile_ingest_status.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "reconcile_ingest_status.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "reconcile_ingest_status.py"
)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_ingest_file(root: Path, rel_path: str, source_hash: str, status: str, extra_frontmatter: str = "") -> Path:
    mgmt_file = root / ".wikicommit" / "source" / "path" / rel_path
    mgmt_file.parent.mkdir(parents=True, exist_ok=True)
    mgmt_file.write_text(
        textwrap.dedent(f"""\
            ---
            source:
              type: path
              path: raw/paper.txt
              hash: {source_hash}
            status: {status}
            {extra_frontmatter}---
            """),
        encoding="utf-8",
    )
    return mgmt_file


def write_page(root: Path, lang: str, type_name: str, slug: str, source_hash: str) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(
        textwrap.dedent(f"""\
            ---
            title: "Test Page"
            type: "schema:Person"
            lang: {lang}
            sources:
              - type: path
                path: raw/paper.txt
                hash: {source_hash}
            ---

            Body.
            """),
        encoding="utf-8",
    )
    return page


def test_no_ingest_dir(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=0" in result.stdout


def test_pending_with_matching_hash_reconciled(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")

    result = run(["--today=2026-08-14"], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" in result.stdout
    assert ".wikicommit/entity/ja/Person/yamada-taro.md" in result.stdout
    assert "page: .wikicommit/source/path/paper.md" in result.stdout
    assert "SUMMARY: reconciled=1" in result.stdout

    updated = mgmt_file.read_text(encoding="utf-8")
    assert "status: generated" in updated
    assert 'generated_pages: [".wikicommit/entity/ja/Person/yamada-taro.md"]' in updated
    assert 'last_generated_at: "2026-08-14"' in updated


def test_pending_with_no_match_left_alone(tmp_path):
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" not in result.stdout
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")


def test_outdated_not_touched_even_with_matching_hash(tmp_path):
    """Critical regression guard: check_ingest_freshness.py deliberately leaves the
    old (page-matching) hash in place when it flags a file outdated — a hash match
    on an outdated file means "was generated before the source changed and still
    needs reprocessing", not "already reconciled". Reconciling it here would mask
    genuine staleness (this was the most serious bug in an earlier prose-based
    version of this fix, per Issue #474's code review)."""
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "outdated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" not in result.stdout
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: outdated" in mgmt_file.read_text(encoding="utf-8")


def test_generated_status_not_touched(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "generated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: generated" in mgmt_file.read_text(encoding="utf-8")


def test_empty_hash_skipped_not_treated_as_wildcard(tmp_path):
    """A pending type:url source registered before Pass 1 fetched it has hash: "" —
    this must never be treated as a match against every page (Issue #474 review)."""
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", '""', "pending")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" not in result.stdout
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")


def test_failure_reason_section_removed_on_reconcile(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")
    content = mgmt_file.read_text(encoding="utf-8")
    content = content.rstrip("\n") + "\n\n## Failure Reason\n\nSomething went wrong previously.\n"
    mgmt_file.write_text(content, encoding="utf-8")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=1" in result.stdout
    updated = mgmt_file.read_text(encoding="utf-8")
    assert "## Failure Reason" not in updated


def test_multiple_pages_citing_same_hash_all_listed_sorted(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    write_page(tmp_path, "ja", "Organization", "companya", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=1" in result.stdout
    updated = mgmt_file.read_text(encoding="utf-8")
    assert (
        'generated_pages: [".wikicommit/entity/ja/Organization/companya.md", '
        '".wikicommit/entity/ja/Person/yamada-taro.md"]' in updated
    )


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75, #231) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
