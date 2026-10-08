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


# ── source.path resolving outside the repository (Issue #1207) ──────────────

def _outside_cases(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """A repo under tmp_path/repo, a secret file beside it, and the three ways a
    hand-written management file can point at it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"secret")
    (repo / "link").symlink_to(secret)
    return repo, secret, {
        "dotdot": "../secret.txt",
        "absolute": str(secret),
        "symlink": "link",
    }


def test_outside_source_path_is_not_hashed_or_rewritten(tmp_path):
    repo, secret, cases = _outside_cases(tmp_path)
    for name, source_path in cases.items():
        # A mismatched hash: if the file were hashed, this would be OUTDATED.
        mgmt = write_ingest_file(repo, f"{name}.md", source_path, "0" * 64, "generated")
        result = run([str(mgmt.relative_to(repo))], cwd=repo)
        assert result.returncode == 0
        assert "OUTDATED:" not in result.stdout, name
        assert "resolves outside the repository" in result.stderr, name
        assert "SUMMARY: outdated=0, ok=0" in result.stdout, name
        assert "status: generated" in mgmt.read_text(encoding="utf-8"), name


def test_outside_source_path_does_not_reveal_whether_the_file_exists(tmp_path):
    repo, secret, _cases = _outside_cases(tmp_path)
    present = write_ingest_file(repo, "present.md", "../secret.txt", "0" * 64, "generated")
    absent = write_ingest_file(repo, "absent.md", "../no-such-file.txt", "0" * 64, "generated")

    r_present = run([str(present.relative_to(repo))], cwd=repo)
    r_absent = run([str(absent.relative_to(repo))], cwd=repo)
    assert "not found" not in r_absent.stderr
    assert r_present.stdout == r_absent.stdout
    assert r_present.stderr.replace("present", "X").replace("secret.txt", "Y") == \
        r_absent.stderr.replace("absent", "X").replace("no-such-file.txt", "Y")


def test_outside_source_path_never_opens_the_file(tmp_path, monkeypatch):
    """In-process: the existence check and the hash are both unreachable."""
    import importlib.util

    repo, _secret, cases = _outside_cases(tmp_path)
    for name, source_path in cases.items():
        write_ingest_file(repo, f"{name}.md", source_path, "0" * 64, "generated")

    monkeypatch.syspath_prepend(str(TEMPLATE_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("check_ingest_freshness_1207", TEMPLATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def _boom(*_a, **_k):
        raise AssertionError("an outside source.path was hashed")

    monkeypatch.setattr(mod, "_sha256_of_file", _boom)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["check_ingest_freshness.py"])
    assert mod.main() == 0
