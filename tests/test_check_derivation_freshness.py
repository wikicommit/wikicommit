"""Tests for .wikicommit/scripts/check_derivation_freshness.py"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_derivation_freshness.py"

# Isolate test git repos from the developer's/CI runner's global and system git
# config (gpgsign, hooksPath, commit templates, credential helpers, etc.), which
# could otherwise make `git commit` hang or fail nondeterministically depending
# on the environment it runs in.
_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=_GIT_ENV)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True, env=_GIT_ENV)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, env=_GIT_ENV)


def git_commit_all(root: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=_GIT_ENV)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=root, check=True, env=_GIT_ENV)
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H"], cwd=root, capture_output=True, text=True, check=True, env=_GIT_ENV
    )
    return result.stdout.strip()


def write_source_page(root: Path, lang: str, type_name: str, slug: str, title: str) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(
        textwrap.dedent(f"""\
            ---
            title: "{title}"
            lang: {lang}
            type: "schema:{type_name}"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            Body.
            """),
        encoding="utf-8",
    )
    return page


def write_synthesized_page(
    root: Path, lang: str, type_name: str, slug: str, derived_from: list[tuple[str, str]]
) -> Path:
    # Built without textwrap.dedent: the interpolated `entries` block has its
    # own fixed 2/4-space indentation, which would throw off dedent()'s
    # common-leading-whitespace calculation for the rest of the template
    # (dedent runs on the final string, after f-string substitution).
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    entries = "\n".join(
        f'  - path: {path}\n    source_commit: "{commit}"' for path, commit in derived_from
    )
    content = (
        "---\n"
        f'title: "{slug}"\n'
        f"lang: {lang}\n"
        f'type: "schema:{type_name}"\n'
        "derived_from:\n"
        f"{entries}\n"
        "---\n"
        "\n"
        "Body.\n"
    )
    page.write_text(content, encoding="utf-8")
    return page


def test_no_wiki_dir(tmp_path):
    init_git_repo(tmp_path)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: stale=0, missing_source=0" in result.stdout


def test_fresh_derivation_matches_head(tmp_path):
    init_git_repo(tmp_path)
    source = write_source_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    head = git_commit_all(tmp_path, "add source page")

    source_rel = str(source.relative_to(tmp_path))
    write_synthesized_page(tmp_path, "ja", "DefinedTerm", "topic", [(source_rel, head)])

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" not in result.stdout
    assert "SUMMARY: stale=0, missing_source=0" in result.stdout


def test_stale_when_source_updated(tmp_path):
    init_git_repo(tmp_path)
    source = write_source_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    old_head = git_commit_all(tmp_path, "add source page")

    source_rel = str(source.relative_to(tmp_path))
    synthesized = write_synthesized_page(tmp_path, "ja", "DefinedTerm", "topic", [(source_rel, old_head)])
    git_commit_all(tmp_path, "add synthesized page")

    # Update the source page and commit again, moving HEAD forward.
    source.write_text(source.read_text(encoding="utf-8") + "\nMore content.\n", encoding="utf-8")
    git_commit_all(tmp_path, "update source page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" in result.stdout
    assert f"page: {synthesized.relative_to(tmp_path)}" in result.stdout
    assert "SUMMARY: stale=1, missing_source=0" in result.stdout


def test_stale_when_source_commit_is_empty_string(tmp_path):
    """Issue #409 regression: wikicommit-synthesize writes source_commit as "" when the
    grounding page has no commits yet (now allowed through by validate_frontmatter.py's
    quality gate, same convention as wikicommit-translate); this script must still flag
    it as STALE, not silently pass it as fresh."""
    init_git_repo(tmp_path)
    source = write_source_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    source_rel = str(source.relative_to(tmp_path))
    git_commit_all(tmp_path, "add source page")
    write_synthesized_page(tmp_path, "ja", "DefinedTerm", "topic", [(source_rel, "")])

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" in result.stdout
    assert "SUMMARY: stale=1, missing_source=0" in result.stdout


def test_derived_from_glob_metachar_path_does_not_false_match(tmp_path):
    """Issue #369: a `derived_from[].path` containing glob metacharacters
    (e.g. `report[2024].md`) must not be confused with an unrelated file
    that happens to match the bracket expression as a character class (e.g.
    `report2.md`) when `_git_head_commit` passes it to `git log` as a
    pathspec — the same false-match risk `check_translation_status.py`'s
    identical helper has for `translated_from` (fixed with `:(literal)`,
    same as Issue #115). Verified experimentally to reproduce when the
    decoy file's last commit is more recent than the real source page's."""
    init_git_repo(tmp_path)
    source = write_source_page(tmp_path, "ja", "Person", "report[2024]", "Report 2024")
    source_rel = str(source.relative_to(tmp_path))
    real_head = git_commit_all(tmp_path, "add source page (older)")

    # Decoy page in the same directory that a naive (non-literal) pathspec
    # interpretation of "report[2024].md" would falsely match, committed
    # afterwards so its HEAD is more recent than the real source page's.
    write_source_page(tmp_path, "ja", "Person", "report2", "Decoy")
    git_commit_all(tmp_path, "add decoy page (newer)")

    write_synthesized_page(tmp_path, "ja", "DefinedTerm", "topic", [(source_rel, real_head)])
    git_commit_all(tmp_path, "add synthesized page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" not in result.stdout
    assert "SUMMARY: stale=0, missing_source=0" in result.stdout


def test_missing_source_when_source_deleted(tmp_path):
    init_git_repo(tmp_path)
    write_synthesized_page(
        tmp_path, "ja", "DefinedTerm", "topic",
        [(".wikicommit/entity/ja/Person/nonexistent.md", "0123456789abcdef0123456789abcdef01234567")],
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "MISSING_SOURCE:" in result.stdout
    assert "SUMMARY: stale=0, missing_source=1" in result.stdout


def test_multiple_entries_one_stale_one_fresh(tmp_path):
    init_git_repo(tmp_path)
    source1 = write_source_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    source2 = write_source_page(tmp_path, "ja", "Organization", "companya", "CompanyA")
    head1 = git_commit_all(tmp_path, "add both source pages")

    source1_rel = str(source1.relative_to(tmp_path))
    source2_rel = str(source2.relative_to(tmp_path))
    synthesized = write_synthesized_page(
        tmp_path, "ja", "DefinedTerm", "topic",
        [(source1_rel, head1), (source2_rel, head1)],
    )
    git_commit_all(tmp_path, "add synthesized page")

    # Only source1 is updated afterward.
    source1.write_text(source1.read_text(encoding="utf-8") + "\nMore.\n", encoding="utf-8")
    git_commit_all(tmp_path, "update source1")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    stale_lines = [line for line in result.stdout.splitlines() if line.startswith("STALE:")]
    assert len(stale_lines) == 1
    assert source1_rel in stale_lines[0]
    page_lines = [
        line for line in result.stdout.splitlines()
        if line == f"page: {synthesized.relative_to(tmp_path)}"
    ]
    assert len(page_lines) == 1
    assert "SUMMARY: stale=1, missing_source=0" in result.stdout


def test_non_synthesized_page_ignored(tmp_path):
    init_git_repo(tmp_path)
    write_source_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    git_commit_all(tmp_path, "add page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: stale=0, missing_source=0" in result.stdout


def test_stale_when_source_exists_but_has_no_git_history(tmp_path):
    """A source page present on disk but never committed has no git log entry
    (`git log` succeeds with empty output once HEAD exists); the script must
    treat this as stale rather than silently matching."""
    init_git_repo(tmp_path)
    (tmp_path / "placeholder.txt").write_text("x", encoding="utf-8")
    git_commit_all(tmp_path, "unrelated initial commit")

    source = write_source_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    source_rel = str(source.relative_to(tmp_path))
    write_synthesized_page(
        tmp_path, "ja", "DefinedTerm", "topic",
        [(source_rel, "0123456789abcdef0123456789abcdef01234567")],
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" in result.stdout
    assert "SUMMARY: stale=1, missing_source=0" in result.stdout
