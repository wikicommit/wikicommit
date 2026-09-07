"""Tests for .claude/skills/wikicommit-remove/scripts/remove_page.py (#123)"""

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-remove" / "scripts" / "remove_page.py"

_spec = importlib.util.spec_from_file_location("remove_page", SCRIPT)
remove_page = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(remove_page)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(root: Path, lang: str, type_name: str, slug: str, extra: dict | None = None) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    lines = [
        "---",
        f'title: "{slug}"',
        f"lang: {lang}",
        f"type: schema:{type_name}",
        "sources: []",
    ]
    if extra:
        for key, value in extra.items():
            lines.append(f"{key}: {value}")
    lines += ["---", "", f"Body of {slug}.", ""]
    page.write_text("\n".join(lines), encoding="utf-8")
    return page


# ── add_removed_fields ───────────────────────────────────────────────────────

def test_add_removed_fields_appends_new_fields():
    content = "---\ntitle: \"foo\"\nlang: ja\n---\n\nBody text.\n"
    fields = remove_page.removed_fields("2026-07-08", "obsolete", None)

    updated = remove_page.add_removed_fields(content, fields)

    assert 'status: removed' in updated
    assert 'removed_at: "2026-07-08"' in updated
    assert 'removed_reason: obsolete' in updated
    assert "Body text.\n" in updated
    assert 'title: "foo"' in updated


def test_add_removed_fields_includes_merged_into_only_when_given():
    content = "---\ntitle: \"foo\"\n---\n\nBody.\n"
    fields = remove_page.removed_fields("2026-07-08", "merged", ".wikicommit/entity/ja/Person/other.md")

    updated = remove_page.add_removed_fields(content, fields)

    assert "merged_into: .wikicommit/entity/ja/Person/other.md" in updated


def test_add_removed_fields_overwrites_existing_status_field():
    content = "---\ntitle: \"foo\"\nstatus: draft\n---\n\nBody.\n"
    fields = remove_page.removed_fields("2026-07-08", "gdpr", None)

    updated = remove_page.add_removed_fields(content, fields)

    assert updated.count("status:") == 1
    assert "status: removed" in updated


def test_add_removed_fields_raises_when_no_frontmatter():
    try:
        remove_page.add_removed_fields("no frontmatter here", [("status", "removed")])
        assert False, "expected ValueError"
    except ValueError:
        pass


# ── parse_wiki_path ──────────────────────────────────────────────────────────

def test_parse_wiki_path_extracts_lang_type_slug(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    page = entity_dir / "ja" / "Person" / "yamada-taro.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\n---\n", encoding="utf-8")

    result = remove_page.parse_wiki_path(page, entity_dir)

    assert result == ("ja", "Person", "yamada-taro")


def test_parse_wiki_path_handles_nested_custom_type(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    page = entity_dir / "ja" / "custom" / "Decision" / "some-decision.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\n---\n", encoding="utf-8")

    result = remove_page.parse_wiki_path(page, entity_dir)

    assert result == ("ja", "custom/Decision", "some-decision")


def test_parse_wiki_path_returns_none_outside_wiki_dir(tmp_path):
    entity_dir = tmp_path / ".wikicommit" / "entity"
    outside = tmp_path / "raw" / "paper.md"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("---\n---\n", encoding="utf-8")

    assert remove_page.parse_wiki_path(outside, entity_dir) is None


# ── find_translation_pages ───────────────────────────────────────────────────

def test_find_translation_pages_matches_translated_from(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro")
    translation = write_page(
        tmp_path, "en", "Person", "taro-yamada",
        extra={"translated_from": ".wikicommit/entity/ja/Person/yamada-taro.md"},
    )
    unrelated = write_page(tmp_path, "en", "Person", "someone-else")

    entity_dir = tmp_path / ".wikicommit" / "entity"
    exclude = entity_dir / "ja" / "Person" / "yamada-taro.md"

    result = remove_page.find_translation_pages(
        entity_dir, "Person", ".wikicommit/entity/ja/Person/yamada-taro.md", exclude
    )

    assert result == [translation]
    assert unrelated not in result


def test_find_translation_pages_returns_empty_when_no_match(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro")
    entity_dir = tmp_path / ".wikicommit" / "entity"
    exclude = entity_dir / "ja" / "Person" / "yamada-taro.md"

    result = remove_page.find_translation_pages(
        entity_dir, "Person", ".wikicommit/entity/ja/Person/yamada-taro.md", exclude
    )

    assert result == []


# ── remove_index_entry ───────────────────────────────────────────────────────

def test_remove_index_entry_deletes_matching_line(tmp_path):
    """The format rebuild_index.py writes today: `- [[Type/slug]]` (Issue #678)."""
    index_path = tmp_path / "index.md"
    index_path.write_text(
        "---\ntitle: \"Person\"\n---\n\n"
        "- [[Person/yamada-taro]]\n"
        "- [[Person/suzuki-jiro]]\n",
        encoding="utf-8",
    )

    changed = remove_page.remove_index_entry(index_path, "Person", "yamada-taro")

    assert changed is True
    content = index_path.read_text(encoding="utf-8")
    assert "yamada-taro" not in content
    assert "- [[Person/suzuki-jiro]]\n" in content


def test_remove_index_entry_handles_pre_issue_678_formats(tmp_path):
    """Existing repos are not migrated, so both older row formats — bare
    `[[Type/slug]]`, and the `[[Type/slug]] — Title` form before that — stay on
    disk until rebuild_index.py next runs over that Type directory."""
    index_path = tmp_path / "index.md"
    index_path.write_text(
        "---\ntitle: \"Person Index\"\n---\n\n"
        "[[Person/yamada-taro]] — Taro Yamada\n"
        "[[Person/suzuki-jiro]]\n"
        "[[Person/tanaka-saburo]] — Saburo Tanaka\n",
        encoding="utf-8",
    )

    assert remove_page.remove_index_entry(index_path, "Person", "yamada-taro") is True
    assert remove_page.remove_index_entry(index_path, "Person", "suzuki-jiro") is True

    content = index_path.read_text(encoding="utf-8")
    assert "yamada-taro" not in content
    assert "suzuki-jiro" not in content
    assert "[[Person/tanaka-saburo]] — Saburo Tanaka" in content


def test_remove_index_entry_returns_false_when_no_match(tmp_path):
    index_path = tmp_path / "index.md"
    index_path.write_text("- [[Person/suzuki-jiro]]\n", encoding="utf-8")

    changed = remove_page.remove_index_entry(index_path, "Person", "yamada-taro")

    assert changed is False


# ── CLI (main) ───────────────────────────────────────────────────────────────

def test_cli_marks_page_removed_and_updates_index(tmp_path):
    page = write_page(tmp_path, "ja", "Person", "yamada-taro")
    index_path = tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "index.md"
    index_path.write_text("- [[Person/yamada-taro]]\n", encoding="utf-8")

    result = run([str(page.relative_to(tmp_path)), "--reason", "obsolete", "--today", "2026-07-08"], tmp_path)

    assert result.returncode == 0
    assert "REMOVED: .wikicommit/entity/ja/Person/yamada-taro.md" in result.stdout
    content = page.read_text(encoding="utf-8")
    assert "status: removed" in content
    assert 'removed_at: "2026-07-08"' in content
    assert "removed_reason: obsolete" in content
    assert "yamada-taro" not in index_path.read_text(encoding="utf-8")


def test_cli_also_removes_translation_pages(tmp_path):
    page = write_page(tmp_path, "ja", "Person", "yamada-taro")
    translation = write_page(
        tmp_path, "en", "Person", "taro-yamada",
        extra={"translated_from": ".wikicommit/entity/ja/Person/yamada-taro.md"},
    )

    result = run([str(page.relative_to(tmp_path)), "--reason", "obsolete", "--today", "2026-07-08"], tmp_path)

    assert result.returncode == 0
    assert "REMOVED: .wikicommit/entity/ja/Person/yamada-taro.md" in result.stdout
    assert "REMOVED: .wikicommit/entity/en/Person/taro-yamada.md" in result.stdout
    assert "status: removed" in translation.read_text(encoding="utf-8")


def test_cli_also_removes_translation_pages_with_legacy_wiki_prefix(tmp_path):
    """A translation page written before the Issue #477 .wikicommit/wiki/ ->
    entity/ rename keeps its old translated_from verbatim (no auto-migration,
    docs/DesignDoc-data.md §4.3's coexistence precedent) — the cascade must
    still find and remove it."""
    page = write_page(tmp_path, "ja", "Person", "yamada-taro")
    translation = write_page(
        tmp_path, "en", "Person", "taro-yamada",
        extra={"translated_from": ".wikicommit/wiki/ja/Person/yamada-taro.md"},
    )

    result = run([str(page.relative_to(tmp_path)), "--reason", "obsolete", "--today", "2026-07-08"], tmp_path)

    assert result.returncode == 0
    assert "REMOVED: .wikicommit/entity/en/Person/taro-yamada.md" in result.stdout
    assert "status: removed" in translation.read_text(encoding="utf-8")


def test_cli_errors_when_page_missing(tmp_path):
    result = run([".wikicommit/entity/ja/Person/nonexistent.md", "--reason", "obsolete"], tmp_path)

    assert result.returncode == 1
    assert "file does not exist" in result.stderr


def test_cli_errors_when_already_removed(tmp_path):
    page = write_page(tmp_path, "ja", "Person", "yamada-taro", extra={"status": "removed"})

    result = run([str(page.relative_to(tmp_path)), "--reason", "obsolete"], tmp_path)

    assert result.returncode == 1
    assert "already has status: removed" in result.stderr


def test_cli_errors_when_merged_without_merged_into(tmp_path):
    page = write_page(tmp_path, "ja", "Person", "yamada-taro")

    result = run([str(page.relative_to(tmp_path)), "--reason", "merged"], tmp_path)

    assert result.returncode == 1
    assert "--merged-into" in result.stderr


def test_cli_errors_when_merged_into_target_missing(tmp_path):
    page = write_page(tmp_path, "ja", "Person", "yamada-taro")

    result = run(
        [str(page.relative_to(tmp_path)), "--reason", "merged", "--merged-into", ".wikicommit/entity/ja/Person/ghost.md"],
        tmp_path,
    )

    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_cli_succeeds_with_valid_merged_into(tmp_path):
    page = write_page(tmp_path, "ja", "Person", "yamada-taro")
    target = write_page(tmp_path, "ja", "Person", "new-page")

    result = run(
        [
            str(page.relative_to(tmp_path)), "--reason", "merged",
            "--merged-into", str(target.relative_to(tmp_path)), "--today", "2026-07-08",
        ],
        tmp_path,
    )

    assert result.returncode == 0
    content = page.read_text(encoding="utf-8")
    assert "merged_into:" in content
    assert "new-page.md" in content


def test_cli_rejects_page_outside_repo_root(tmp_path):
    other_root = tmp_path / "elsewhere"
    other_root.mkdir()
    outside_page = write_page(other_root, "ja", "Person", "yamada-taro")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = run(
        [str(outside_page), "--reason", "obsolete", "--today", "2026-07-08"],
        repo_root,
    )

    assert result.returncode == 1
    assert "path is outside the repository" in result.stderr
    assert "status: removed" not in outside_page.read_text(encoding="utf-8")


def test_add_removed_fields_handles_backslash_in_value():
    content = "---\ntitle: \"foo\"\n---\n\nBody.\n"
    fields = remove_page.removed_fields(
        "2026-07-08", "merged", ".wikicommit/entity/ja/Person/weird\\1target.md"
    )

    updated = remove_page.add_removed_fields(content, fields)

    assert "merged_into: .wikicommit/entity/ja/Person/weird\\1target.md" in updated
