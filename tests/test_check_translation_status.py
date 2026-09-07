"""Tests for .wikicommit/scripts/check_translation_status.py"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_translation_status.py"

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


def write_parent_page(root: Path, lang: str, type_name: str, slug: str, title: str) -> Path:
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


def write_translation_page(root: Path, lang: str, type_name: str, slug: str, translated_from: str, source_commit: str) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(
        textwrap.dedent(f"""\
            ---
            title: "{slug}"
            lang: {lang}
            type: "schema:{type_name}"
            translated_from: {translated_from}
            source_commit: "{source_commit}"
            ---

            Body.
            """),
        encoding="utf-8",
    )
    return page


def write_config(root: Path, targets: list[str], primary_lang: str = "ja") -> None:
    config_dir = root / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    targets_yaml = "[" + ", ".join(targets) + "]"
    (config_dir / "config.yml").write_text(
        textwrap.dedent(f"""\
            translation:
              targets: {targets_yaml}
              primary_lang: {primary_lang}
            """),
        encoding="utf-8",
    )


def test_no_wiki_dir(tmp_path):
    init_git_repo(tmp_path)
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: stale=0, missing_source=0, untranslated=0" in result.stdout


def test_fresh_translation_matches_head(tmp_path):
    init_git_repo(tmp_path)
    parent = write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    head = git_commit_all(tmp_path, "add parent page")

    parent_rel = str(parent.relative_to(tmp_path))
    write_translation_page(tmp_path, "en", "Person", "yamada", parent_rel, head)

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" not in result.stdout
    assert "SUMMARY: stale=0, missing_source=0, untranslated=0" in result.stdout


def test_stale_translation_when_parent_updated(tmp_path):
    init_git_repo(tmp_path)
    parent = write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    old_head = git_commit_all(tmp_path, "add parent page")

    parent_rel = str(parent.relative_to(tmp_path))
    write_translation_page(tmp_path, "en", "Person", "yamada", parent_rel, old_head)
    git_commit_all(tmp_path, "add translation page")

    # Update the parent page and commit again, moving HEAD forward.
    parent.write_text(parent.read_text(encoding="utf-8") + "\nMore content.\n", encoding="utf-8")
    git_commit_all(tmp_path, "update parent page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" in result.stdout
    en_page = tmp_path / ".wikicommit" / "entity" / "en" / "Person" / "yamada.md"
    assert f"page: {en_page.relative_to(tmp_path)}" in result.stdout
    assert "SUMMARY: stale=1, missing_source=0, untranslated=0" in result.stdout


def test_missing_source_when_parent_deleted(tmp_path):
    init_git_repo(tmp_path)
    write_translation_page(
        tmp_path, "en", "Person", "yamada",
        ".wikicommit/entity/ja/Person/nonexistent.md",
        "0123456789abcdef0123456789abcdef01234567",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "MISSING_SOURCE:" in result.stdout
    assert "SUMMARY: stale=0, missing_source=1, untranslated=0" in result.stdout


def test_non_translation_page_ignored(tmp_path):
    init_git_repo(tmp_path)
    write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    git_commit_all(tmp_path, "add page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: stale=0, missing_source=0, untranslated=0" in result.stdout


def test_stale_when_parent_exists_but_has_no_git_history(tmp_path):
    """A parent page present on disk but never committed has no git log entry
    (`git log` succeeds with empty output once HEAD exists); the script must
    treat this as stale rather than silently matching."""
    init_git_repo(tmp_path)
    (tmp_path / "placeholder.txt").write_text("x", encoding="utf-8")
    git_commit_all(tmp_path, "unrelated initial commit")

    parent = write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    parent_rel = str(parent.relative_to(tmp_path))
    write_translation_page(
        tmp_path, "en", "Person", "yamada", parent_rel,
        "0123456789abcdef0123456789abcdef01234567",
    )

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" in result.stdout
    assert "SUMMARY: stale=1, missing_source=0, untranslated=0" in result.stdout


def test_stale_when_source_commit_is_empty_string(tmp_path):
    """Issue #409 regression: wikicommit-translate writes source_commit as "" when the
    source page has no commits yet (now allowed through by validate_frontmatter.py's
    quality gate); this script must still flag it as STALE, not silently pass it as fresh."""
    init_git_repo(tmp_path)
    (tmp_path / "placeholder.txt").write_text("x", encoding="utf-8")
    git_commit_all(tmp_path, "unrelated initial commit")

    parent = write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    parent_rel = str(parent.relative_to(tmp_path))
    git_commit_all(tmp_path, "add parent page")
    write_translation_page(tmp_path, "en", "Person", "yamada", parent_rel, "")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" in result.stdout
    assert "SUMMARY: stale=1, missing_source=0, untranslated=0" in result.stdout


def test_translated_from_glob_metachar_path_does_not_false_match(tmp_path):
    """Issue #369: a `translated_from` path containing glob metacharacters
    (e.g. `report[2024].md`) must not be confused with an unrelated file that
    happens to match the bracket expression as a character class (e.g.
    `report2.md`) when `_git_head_commit` passes it to `git log` as a
    pathspec. Without the `:(literal)` prefix (same fix as Issue #115), `git
    log -1 --format=%H -- "report[2024].md"` can return the commit hash of
    the unrelated `report2.md` instead of the real parent page's own commit
    — verified experimentally to reproduce when the decoy file's last commit
    is more recent than the real parent page's. If that wrong hash is then
    compared against `source_commit`, a translation that is actually fresh
    gets misreported as STALE."""
    init_git_repo(tmp_path)
    parent = write_parent_page(tmp_path, "ja", "Person", "report[2024]", "Report 2024")
    parent_rel = str(parent.relative_to(tmp_path))
    real_head = git_commit_all(tmp_path, "add parent page (older)")

    # Decoy page in the same directory that a naive (non-literal) pathspec
    # interpretation of "report[2024].md" would falsely match, committed
    # afterwards so its HEAD is more recent than the real parent page's.
    write_parent_page(tmp_path, "ja", "Person", "report2", "Decoy")
    git_commit_all(tmp_path, "add decoy page (newer)")

    write_translation_page(tmp_path, "en", "Person", "report-2024", parent_rel, real_head)
    git_commit_all(tmp_path, "add translation page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "STALE:" not in result.stdout
    assert "SUMMARY: stale=0, missing_source=0, untranslated=0" in result.stdout


def test_untranslated_when_target_missing(tmp_path):
    init_git_repo(tmp_path)
    write_config(tmp_path, ["en"])
    source = write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    git_commit_all(tmp_path, "add source page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert f"UNTRANSLATED: {source.relative_to(tmp_path)} (target: en)" in result.stdout
    assert f"page: {source.relative_to(tmp_path)}" in result.stdout
    assert "SUMMARY: stale=0, missing_source=0, untranslated=1" in result.stdout


def test_no_untranslated_when_translation_exists(tmp_path):
    init_git_repo(tmp_path)
    write_config(tmp_path, ["en"])
    source = write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    head = git_commit_all(tmp_path, "add source page")

    parent_rel = str(source.relative_to(tmp_path))
    write_translation_page(tmp_path, "en", "Person", "yamada", parent_rel, head)

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNTRANSLATED:" not in result.stdout
    assert "SUMMARY: stale=0, missing_source=0, untranslated=0" in result.stdout


def test_no_untranslated_when_targets_empty(tmp_path):
    init_git_repo(tmp_path)
    write_config(tmp_path, [])
    write_parent_page(tmp_path, "ja", "Person", "yamada", "Yamada")
    git_commit_all(tmp_path, "add source page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNTRANSLATED:" not in result.stdout
    assert "SUMMARY: stale=0, missing_source=0, untranslated=0" in result.stdout


def test_removed_page_not_counted_as_untranslated(tmp_path):
    init_git_repo(tmp_path)
    write_config(tmp_path, ["en"])
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / "yamada.md"
    page.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            status: removed
            removed_at: "2026-01-01"
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            Body.
            """),
        encoding="utf-8",
    )
    git_commit_all(tmp_path, "add removed page")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "UNTRANSLATED:" not in result.stdout
    assert "SUMMARY: stale=0, missing_source=0, untranslated=0" in result.stdout
