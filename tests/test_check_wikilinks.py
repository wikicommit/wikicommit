"""Tests for .wikicommit/scripts/check_wikilinks.py"""

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_wikilinks.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_wikilinks.py"
)

# load_primary_lang() is exercised directly (rather than only via subprocess) so its
# fallback default (#376) can be asserted without needing a full wikilink-resolution
# fixture — _frontmatter/_wikilink are sibling-imported by check_wikilinks.py, so the
# script's own directory must be on sys.path before exec_module() runs it.
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("check_wikilinks", SCRIPT)
_check_wikilinks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_check_wikilinks)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run check_wikilinks.py with args in cwd and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(
    root: Path, lang: str, type_name: str, slug: str,
    extra: dict | None = None,
) -> Path:
    """Write a minimal wiki page and return its path (creates parent dirs)."""
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    fm: dict = {
        "title": slug,
        "lang": lang,
        "type": f"schema:{type_name}",
        "review_status": "pending",
        "sources": [{"type": "manual", "author": "test", "created_at": "2026-01-01"}],
    }
    if extra:
        fm.update(extra)
    page.write_text(
        f"---\n{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---\n\nBody text.\n",
        encoding="utf-8",
    )
    return page


def write_config(root: Path, primary_lang: str = "ja") -> None:
    config_dir = root / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        f"translation:\n  primary_lang: {primary_lang}\n  targets: []\n",
        encoding="utf-8",
    )


# ── load_primary_lang() fallback default (#376) ─────────────────────────────────

def test_load_primary_lang_fallback_is_en_when_config_missing(tmp_path):
    assert _check_wikilinks.load_primary_lang(tmp_path) == "en"


def test_load_primary_lang_fallback_is_en_when_field_missing(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yml").write_text("translation:\n  targets: []\n", encoding="utf-8")
    assert _check_wikilinks.load_primary_lang(tmp_path) == "en"


def test_load_primary_lang_still_honors_explicit_value(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    assert _check_wikilinks.load_primary_lang(tmp_path) == "ja"


# ── Basic OK case ──────────────────────────────────────────────────────────────

def test_valid_wikilink(tmp_path):
    """A [[Type/slug]] that points to an existing page should produce no errors."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo")

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[Place/tokyo]] for details.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 0
    assert "errors, 0 warnings" in result.stdout
    assert "ERROR" not in result.stdout


# ── Missing link ───────────────────────────────────────────────────────────────

def test_missing_wikilink(tmp_path):
    """A [[Type/slug]] to a non-existent page should produce WARNING and exit code 0
    (Issue #340 — downgraded from ERROR so authors stop avoiding WikiLinks for
    not-yet-created concepts; check_wanted_pages.py now reports these instead)."""
    write_config(tmp_path)

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[Place/nonexistent]] for details.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "[[Place/nonexistent]]" in result.stdout
    assert "page does not exist" in result.stdout


# ── Type-segment mismatch (Issue #563) ────────────────────────────────────────

def _link_page(root: Path, body_link: str, *, lang: str = "ja") -> Path:
    """A page whose body carries exactly one WikiLink, used as the --changed file."""
    page = write_page(root, lang, "GovernmentService", "ward-office")
    page.write_text(
        page.read_text(encoding="utf-8").replace("Body text.", f"Provided by {body_link}."),
        encoding="utf-8",
    )
    return page


def test_wrong_type_segment_is_error_naming_the_real_type(tmp_path):
    """The page exists under another Type, so this is a one-word fix, not a
    not-yet-written concept — Issue #340's reason for not blocking does not apply."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "AdministrativeArea", "saitama-city")
    page = _link_page(tmp_path, "[[Organization/saitama-city]]")

    result = run(["--changed", str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "[[Organization/saitama-city]]" in result.stdout
    assert "AdministrativeArea/saitama-city.md" in result.stdout
    assert "1 errors, 0 warnings" in result.stdout


def test_wrong_type_segment_lists_every_candidate_type(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "AdministrativeArea", "saitama-city")
    write_page(tmp_path, "ja", "Place", "saitama-city")
    page = _link_page(tmp_path, "[[Organization/saitama-city]]")

    result = run(["--changed", str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "AdministrativeArea/saitama-city.md" in result.stdout
    assert "Place/saitama-city.md" in result.stdout


def test_wrong_type_segment_matches_across_languages(tmp_path):
    """Search is language-agnostic, matching check_orphans.py's slug-based
    matching — a Type segment is wrong regardless of the target's language."""
    write_config(tmp_path)
    write_page(tmp_path, "en", "AdministrativeArea", "saitama-city")
    page = _link_page(tmp_path, "[[Organization/saitama-city]]")

    result = run(["--changed", str(page)], cwd=tmp_path)
    assert result.returncode == 1
    assert "AdministrativeArea/saitama-city.md" in result.stdout


def test_unused_slug_stays_a_warning(tmp_path):
    """Issue #340's relaxation is untouched: a slug no Type has stays non-blocking."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "AdministrativeArea", "saitama-city")
    page = _link_page(tmp_path, "[[Organization/kawaguchi-city]]")

    result = run(["--changed", str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "page does not exist" in result.stdout
    assert "0 errors, 1 warnings" in result.stdout


def test_removed_page_under_another_type_stays_a_warning(tmp_path):
    """Pointing the link there would only swap this for the removed-page ERROR,
    so the honest report is that no usable page backs the slug."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "AdministrativeArea", "saitama-city",
        extra={"status": "removed", "removed_at": "2026-01-01"},
    )
    page = _link_page(tmp_path, "[[Organization/saitama-city]]")

    result = run(["--changed", str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "page does not exist" in result.stdout


def test_index_page_under_another_type_stays_a_warning(tmp_path):
    """Every Type has an index.md, so matching on that slug means nothing."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "index")
    page = _link_page(tmp_path, "[[Organization/index]]")

    result = run(["--changed", str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


def test_translation_fallback_is_not_reported_as_type_mismatch(tmp_path):
    """Same Type, page only in primary_lang — the existing translation WARNING
    must win over the new Type-mismatch check."""
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Organization", "saitama-city")
    page = _link_page(tmp_path, "[[Organization/saitama-city]]", lang="en")

    result = run(["--changed", str(page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "translation page not created yet" in result.stdout
    assert "the Type segment may be wrong" not in result.stdout


# ── Removed link ───────────────────────────────────────────────────────────────

def test_removed_wikilink(tmp_path):
    """A [[Type/slug]] to a removed page should produce ERROR."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo",
               extra={"status": "removed", "removed_at": "2026-01-01"})

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[Place/tokyo]].
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "[[Place/tokyo]]" in result.stdout
    assert "removed" in result.stdout


# ── Same-commit exception ──────────────────────────────────────────────────────

def test_same_commit_new_page_exception(tmp_path):
    """Linking to a page in the same --changed set should not produce an error."""
    write_config(tmp_path)

    entity_dir = tmp_path / ".wikicommit" / "entity" / "ja"

    person_dir = entity_dir / "Person"
    person_dir.mkdir(parents=True, exist_ok=True)
    source = person_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[Place/tokyo]].
            """),
        encoding="utf-8",
    )

    place_dir = entity_dir / "Place"
    place_dir.mkdir(parents=True, exist_ok=True)
    new_page = place_dir / "tokyo.md"
    new_page.write_text(
        textwrap.dedent("""\
            ---
            title: "Tokyo"
            lang: ja
            type: "schema:Place"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            Body.
            """),
        encoding="utf-8",
    )

    # Both files passed as --changed: no error expected
    result = run(["--changed", str(source), str(new_page)], cwd=tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout


# ── --deleted: remaining backlinks ─────────────────────────────────────────────

def test_deleted_with_remaining_backlinks(tmp_path):
    """--deleted file that still has backlinks should produce WARNING but exit 0."""
    write_config(tmp_path)
    tokyo = write_page(
        tmp_path, "ja", "Place", "tokyo",
        extra={"status": "removed", "removed_at": "2026-01-01"},
    )

    # A page that links to tokyo (not in --changed)
    person_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    person_dir.mkdir(parents=True, exist_ok=True)
    referring = person_dir / "yamada.md"
    referring.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[Place/tokyo]].
            """),
        encoding="utf-8",
    )

    # Another file as --changed (unrelated) so --changed is non-empty
    unrelated_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "DefinedTerm"
    unrelated_dir.mkdir(parents=True, exist_ok=True)
    unrelated = unrelated_dir / "foo.md"
    unrelated.write_text(
        textwrap.dedent("""\
            ---
            title: "Foo"
            lang: ja
            type: "schema:DefinedTerm"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            Body.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(unrelated), "--deleted", str(tokyo)], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "a backlink remains" in result.stdout
    assert "ERROR" not in result.stdout


# ── Translation fallback warning ───────────────────────────────────────────────

def test_translation_fallback_warning(tmp_path):
    """Link in en page to a page that exists only in ja (primary_lang) should produce WARNING."""
    write_config(tmp_path, primary_lang="ja")
    # ja target exists
    write_page(tmp_path, "ja", "Place", "tokyo")

    # en source with link to [[Place/tokyo]]
    en_dir = tmp_path / ".wikicommit" / "entity" / "en" / "Person"
    en_dir.mkdir(parents=True, exist_ok=True)
    source = en_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: en
            type: "schema:Person"
            review_status: pending
            translated_from: .wikicommit/entity/ja/Person/yamada.md
            source_commit: "0000000000000000000000000000000000000000"
            ---

            See [[Place/tokyo]].
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "translation page not created yet" in result.stdout
    assert "ERROR" not in result.stdout


# ── No --changed produces OK ───────────────────────────────────────────────────

def test_no_changed_files(tmp_path):
    """Invocation with no --changed arguments should exit 0 with OK summary."""
    write_config(tmp_path)
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK:" in result.stdout


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")


# ── Multiple errors counted correctly ─────────────────────────────────────────

# ── Nested custom types (Issue #105) ────────────────────────────────────────

def test_nested_type_valid_wikilink(tmp_path):
    """A [[custom/Decision/slug]] link to an existing nested-type page is recognized."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "custom/Decision", "adopt-quartz")

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[custom/Decision/adopt-quartz]] for details.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 0
    assert "errors, 0 warnings" in result.stdout
    assert "ERROR" not in result.stdout


def test_nested_type_missing_wikilink(tmp_path):
    """A [[custom/Decision/slug]] link to a non-existent nested-type page is still
    caught, now as WARNING/exit 0 (Issue #340)."""
    write_config(tmp_path)

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[custom/Decision/nonexistent]] for details.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "[[custom/Decision/nonexistent]]" in result.stdout
    assert "page does not exist" in result.stdout


def test_nested_type_removed_wikilink(tmp_path):
    """A [[custom/Decision/slug]] link to a removed nested-type page produces ERROR."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        extra={"status": "removed", "removed_at": "2026-01-01"},
    )

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[custom/Decision/adopt-quartz]].
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "[[custom/Decision/adopt-quartz]]" in result.stdout
    assert "removed" in result.stdout


def test_nested_type_deleted_with_remaining_backlinks(tmp_path):
    """--deleted nested-type file that still has backlinks should produce WARNING but exit 0."""
    write_config(tmp_path)
    decision = write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        extra={"status": "removed", "removed_at": "2026-01-01"},
    )

    person_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    person_dir.mkdir(parents=True, exist_ok=True)
    referring = person_dir / "yamada.md"
    referring.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[custom/Decision/adopt-quartz]].
            """),
        encoding="utf-8",
    )

    unrelated_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "DefinedTerm"
    unrelated_dir.mkdir(parents=True, exist_ok=True)
    unrelated = unrelated_dir / "foo.md"
    unrelated.write_text(
        textwrap.dedent("""\
            ---
            title: "Foo"
            lang: ja
            type: "schema:DefinedTerm"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            Body.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(unrelated), "--deleted", str(decision)], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "a backlink remains" in result.stdout
    assert "ERROR" not in result.stdout


def test_double_slash_malformed_wikilink_reported_as_missing(tmp_path):
    """A malformed [[Person//foo]] (double slash) must not silently resolve
    to an existing Person/foo.md page via pathlib path normalization — it
    should be treated as a broken/unmatched reference like any other typo."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "foo")

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[Person//foo]] for details.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    # The malformed link must not be silently accepted as a valid reference
    # to Person/foo.md; WIKILINK_RE simply does not match it, so no
    # ERROR/WARNING is raised for it and it is not counted as a checked link.
    assert "[[Person//foo]]" not in result.stdout
    assert "errors, 0 warnings" in result.stdout


def test_hyphenated_custom_type_wikilink_reported_as_missing(tmp_path):
    """A [[custom/Multi-Word/slug]] link must not silently resolve to an
    existing custom/Multi-Word/foo.md page: custom type directory names are
    PascalCase without hyphens (docs/DesignDoc-data.md §5.3, Issue #114), so
    the Type segment's hyphen means WIKILINK_RE simply does not match it."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "custom/Multi-Word", "foo")

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[custom/Multi-Word/foo]] for details.
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    # The malformed (hyphenated) link is not matched by WIKILINK_RE at all,
    # so it is neither reported nor counted as a checked link.
    assert "[[custom/Multi-Word/foo]]" not in result.stdout
    assert "errors, 0 warnings" in result.stdout


def test_multiple_missing_links(tmp_path):
    """Multiple broken WikiLinks should all be reported (as WARNING, Issue #340)."""
    write_config(tmp_path)

    source_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "yamada.md"
    source.write_text(
        textwrap.dedent("""\
            ---
            title: "Yamada"
            lang: ja
            type: "schema:Person"
            review_status: pending
            sources:
              - type: manual
                author: test
                created_at: "2026-01-01"
            ---

            See [[Place/a]] and [[Place/b]].
            """),
        encoding="utf-8",
    )

    result = run(["--changed", str(source)], cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.count("WARNING:") == 2


# ── No-argument whole-wiki mode (Issue #571) ─────────────────────────────────

def _write_body(root: Path, lang: str, type_name: str, slug: str, body: str, extra: dict | None = None) -> Path:
    page = write_page(root, lang, type_name, slug, extra)
    text = page.read_text(encoding="utf-8")
    page.write_text(text.replace("Body text.\n", body), encoding="utf-8")
    return page


def test_no_args_checks_every_page(tmp_path):
    """It used to print "0 files checked" and exit 0 — indistinguishable from a clean run."""
    write_page(tmp_path, "ja", "Place", "tokyo")
    _write_body(
        tmp_path, "ja", "Person", "yamada-taro",
        "Lives in [[Place/tokyo]], works at [[Organization/nope]].\n",
    )
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "2 files checked" in result.stdout
    assert "[[Organization/nope]]" in result.stdout


def test_no_args_reports_a_removed_target_as_an_error(tmp_path):
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        {"status": "removed", "removed_at": "2026-01-01"},
    )
    _write_body(tmp_path, "ja", "Person", "yamada-taro", "Lives in [[Place/tokyo]].\n")
    result = run([], cwd=tmp_path)
    assert result.returncode == 1
    assert "status: removed" in result.stdout


def test_no_args_on_an_empty_wiki_is_still_zero_files(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "OK: 0 files checked" in result.stdout


def test_no_args_skips_assets(tmp_path):
    assets = tmp_path / ".wikicommit" / "entity" / "assets"
    assets.mkdir(parents=True)
    (assets / "notes.md").write_text("[[Place/nope]]\n", encoding="utf-8")
    result = run([], cwd=tmp_path)
    assert "OK: 0 files checked" in result.stdout


def test_no_args_still_warns_about_a_missing_translation(tmp_path):
    """The same-commit exception must not swallow the cross-language WARNING.

    Whole-wiki mode feeds every page in as --changed, so leaving that exception
    armed made every existing target match it — an `en` page linking to a page
    that exists only in `ja` was accepted in silence instead of reporting
    "translation page not created", one of the two warnings the mode exists for.
    """
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Person", "yamada-taro")
    _write_body(tmp_path, "en", "Person", "hanako", "Works with [[Person/yamada-taro]].\n")
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "translation page not created yet" in result.stdout
    assert "1 warnings" in result.stdout


# ── The backlink index must not depend on where the repository sits on disk
#    (Issue #677) ───────────────────────────────────────────────────────────────
# check_wikilinks.py builds an absolute entity_dir (`Path.cwd() / ENTITY_DIR`),
# and the old `"assets" in wiki_page.parts` therefore matched any repository
# living under a directory named "assets" — skipping every page and leaving the
# backlink index empty. The --deleted WARNING then silently stopped being
# emitted, which is the one signal the removal flow has for links left dangling.

def _removal_fixture(root: Path) -> None:
    write_config(root)
    write_page(root, "ja", "Person", "a",
               extra={"status": "removed", "removed_at": "2026-01-01"})
    b = write_page(root, "ja", "Person", "b")
    b.write_text(b.read_text(encoding="utf-8").replace("Body text.", "See [[Person/a]]."),
                 encoding="utf-8")


def _run_removal(root: Path) -> subprocess.CompletedProcess:
    return run(
        ["--changed", ".wikicommit/entity/ja/Person/b.md",
         "--deleted", ".wikicommit/entity/ja/Person/a.md"],
        cwd=root,
    )


def test_backlink_warning_survives_an_assets_named_ancestor_directory(tmp_path):
    root = tmp_path / "assets" / "wiki"
    root.mkdir(parents=True)
    _removal_fixture(root)

    result = _run_removal(root)

    assert "a backlink remains" in result.stdout, result.stdout
    assert "1 warnings" in result.stdout


def test_backlink_warning_is_identical_with_and_without_such_an_ancestor(tmp_path):
    """The two runs must agree — the point is that location cannot matter."""
    under_assets = tmp_path / "assets" / "wiki"
    under_assets.mkdir(parents=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    for root in (under_assets, plain):
        _removal_fixture(root)

    assert _run_removal(under_assets).stdout == _run_removal(plain).stdout


def test_assets_directly_under_entity_is_still_excluded(tmp_path):
    """The narrowing must not lose the exclusion it replaced: a real attachment
    under `.wikicommit/entity/assets/` is not a page and must not be a referrer.

    The removed page is passed only via --deleted. Listing it in --changed too
    would make main() skip the whole backlink check for it (a --deleted path
    that is also --changed is handled by the WikiLink check instead), and the
    assertion would then hold no matter what the walk collected. The ordinary
    page linking to the same target is the positive control that proves the
    backlink walk ran at all.
    """
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "a",
               extra={"status": "removed", "removed_at": "2026-01-01"})
    b = write_page(tmp_path, "ja", "Person", "b")
    b.write_text(b.read_text(encoding="utf-8").replace("Body text.", "See [[Person/a]]."),
                 encoding="utf-8")
    assets = tmp_path / ".wikicommit" / "entity" / "assets"
    assets.mkdir(parents=True)
    (assets / "notes.md").write_text("See [[Person/a]].\n", encoding="utf-8")

    result = run(["--deleted", ".wikicommit/entity/ja/Person/a.md"], cwd=tmp_path)

    assert "a backlink remains" in result.stdout, result.stdout
    assert "Person/b.md" in result.stdout
    assert "assets/notes.md" not in result.stdout, result.stdout
    assert "1 warnings" in result.stdout
