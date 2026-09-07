"""Tests for .wikicommit/scripts/check_ingest_freshness.py"""

import hashlib
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_ingest_freshness.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_ingest_freshness.py"
)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_ingest_file(root: Path, rel_path: str, source_path: str, source_hash: str, status: str) -> Path:
    mgmt_dir = root / ".wikicommit" / "source" / "path"
    mgmt_file = mgmt_dir / rel_path
    mgmt_file.parent.mkdir(parents=True, exist_ok=True)
    mgmt_file.write_text(
        textwrap.dedent(f"""\
            ---
            source:
              type: path
              path: {source_path}
              hash: sha256:{source_hash}
            status: {status}
            ---
            """),
        encoding="utf-8",
    )
    return mgmt_file


def test_no_ingest_dir(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: outdated=0, ok=0" in result.stdout


def test_matching_hash_is_ok(tmp_path):
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"hello world")
    digest = sha256_of(b"hello world")

    write_ingest_file(tmp_path, "raw/paper.md", "raw/paper.txt", digest, "generated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OUTDATED:" not in result.stdout
    assert "SUMMARY: outdated=0, ok=1" in result.stdout


def test_hash_mismatch_detected_and_status_rewritten(tmp_path):
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"updated content")

    mgmt_file = write_ingest_file(tmp_path, "raw/paper.md", "raw/paper.txt", sha256_of(b"original content"), "generated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OUTDATED:" in result.stdout
    assert "page: .wikicommit/source/path/raw/paper.md" in result.stdout
    assert "SUMMARY: outdated=1, ok=0" in result.stdout

    updated_content = mgmt_file.read_text(encoding="utf-8")
    assert "status: outdated" in updated_content


def test_url_source_type_skipped(tmp_path):
    mgmt_dir = tmp_path / ".wikicommit" / "source" / "url"
    mgmt_dir.mkdir(parents=True, exist_ok=True)
    mgmt_file = mgmt_dir / "example.md"
    mgmt_file.write_text(
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/article
              hash: sha256:deadbeef
            status: generated
            ---
            """),
        encoding="utf-8",
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OUTDATED:" not in result.stdout
    assert "SUMMARY: outdated=0, ok=0" in result.stdout


def test_pending_status_skipped(tmp_path):
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"content")

    write_ingest_file(tmp_path, "raw/paper.md", "raw/paper.txt", sha256_of(b"different"), "pending")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OUTDATED:" not in result.stdout
    assert "SUMMARY: outdated=0, ok=0" in result.stdout


def test_already_outdated_status_still_reported(tmp_path):
    """status: outdated is checkable (CHECKABLE_STATUSES includes it); a still-mismatched
    hash must keep being reported without needing an unnecessary rewrite."""
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"updated content")

    write_ingest_file(tmp_path, "raw/paper.md", "raw/paper.txt", sha256_of(b"original content"), "outdated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OUTDATED:" in result.stdout
    assert "SUMMARY: outdated=1, ok=0" in result.stdout


def test_outdated_status_not_reset_when_hash_now_matches(tmp_path):
    """Only wikicommit-generate resets status back to generated; this script must
    leave an outdated management file's status untouched even if the hash now
    matches again (e.g. the source file was reverted)."""
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"hello world")
    digest = sha256_of(b"hello world")

    mgmt_file = write_ingest_file(tmp_path, "raw/paper.md", "raw/paper.txt", digest, "outdated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OUTDATED:" not in result.stdout
    assert "SUMMARY: outdated=0, ok=1" in result.stdout
    assert "status: outdated" in mgmt_file.read_text(encoding="utf-8")


def test_specific_files_argument(tmp_path):
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"content a")
    mgmt_a = write_ingest_file(tmp_path, "raw/paper-a.md", "raw/paper.txt", sha256_of(b"content a"), "generated")
    write_ingest_file(tmp_path, "raw/paper-b.md", "raw/paper.txt", sha256_of(b"different"), "generated")

    result = run([str(mgmt_a.relative_to(tmp_path))], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: outdated=0, ok=1" in result.stdout
    assert "paper-b.md" not in result.stdout


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75, #231) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")


def test_retracted_status_is_never_rewritten_to_outdated(tmp_path):
    """A human's retraction must survive an edit to the source file (Issue #737).

    The failure this guards against is silent: `retracted` says a human read
    the source and judged it unreliable, and rewriting it to `outdated` on a
    hash mismatch would put it straight back into Pass 1's collection list.
    Touching the source file by a single byte would then lift the retraction
    with nothing reported.
    """
    source = tmp_path / "raw" / "paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"content changed since retraction")

    mgmt_file = write_ingest_file(
        tmp_path, "raw/paper.md", "raw/paper.txt", sha256_of(b"content at retraction time"), "retracted"
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OUTDATED:" not in result.stdout
    # Not counted as ok either — it is not checked at all.
    assert "SUMMARY: outdated=0, ok=0" in result.stdout
    assert "status: retracted" in mgmt_file.read_text(encoding="utf-8")
