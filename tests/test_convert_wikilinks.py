"""Tests for .wikicommit/scripts/convert_wikilinks.py"""

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "convert_wikilinks.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "convert_wikilinks.py"
)

# load_primary_lang() is exercised directly (rather than only via subprocess) so its
# fallback default (#376) can be asserted without needing a full wikilink-resolution
# fixture — _frontmatter/_wikilink are sibling-imported by convert_wikilinks.py, so the
# script's own directory must be on sys.path before exec_module() runs it.
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("convert_wikilinks", SCRIPT)
_convert_wikilinks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_convert_wikilinks)


def run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run convert_wikilinks.py with args in cwd and return the result.

    GITHUB_REPOSITORY is stripped from the inherited environment by default so
    convert_wikilinks.py's CI-only rendering branch (path_href()) can't leak into
    tests that don't explicitly opt in via `env` — this ambient leak was the root
    cause of the CI-only test failures fixed in Issue #469.
    """
    run_env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=run_env,
        check=False,
    )


def write_page(root: Path, lang: str, type_name: str, slug: str, body: str) -> Path:
    page_dir = root / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(body, encoding="utf-8")
    return page


def write_source(root: Path, rel_path: str, body: str) -> Path:
    """Write an source management file at .wikicommit/source/<rel_path>
    (mirroring add_source.py's layout, Issue #476's rename target)."""
    mgmt_path = root / ".wikicommit" / "source" / rel_path
    mgmt_path.parent.mkdir(parents=True, exist_ok=True)
    mgmt_path.write_text(body, encoding="utf-8")
    return mgmt_path


def write_config(
    root: Path,
    primary_lang: str = "ja",
    theme: str = "",
    targets: list[str] | None = None,
    extra: str = "",
) -> None:
    """Write a minimal config.yml.

    `extra` is appended verbatim after the generated keys, so a test can supply
    a top-level block in shapes a typed parameter could not express (a mapping,
    a bare string where a mapping is expected, a nested value where a string is
    expected) — see the site_description tests below.
    """
    config_dir = root / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    theme_line = f"theme: {yaml.safe_dump(theme).strip()}\n" if theme else ""
    (config_dir / "config.yml").write_text(
        f"translation:\n  primary_lang: {primary_lang}\n  targets: {targets or []}\n"
        f"{theme_line}{extra}",
        encoding="utf-8",
    )


# ── load_primary_lang() fallback default (#376) ─────────────────────────────────

def test_load_primary_lang_fallback_is_en_when_config_missing(tmp_path):
    assert _convert_wikilinks.load_primary_lang(tmp_path) == "en"


def test_load_primary_lang_fallback_is_en_when_field_missing(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yml").write_text("translation:\n  targets: []\n", encoding="utf-8")
    assert _convert_wikilinks.load_primary_lang(tmp_path) == "en"


def test_load_primary_lang_still_honors_explicit_value(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    assert _convert_wikilinks.load_primary_lang(tmp_path) == "ja"


# ── Same-language, different type: ../Type/slug.md ─────────────────────────────

def test_same_lang_different_type(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[Place/tokyo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[Tokyo](../Place/tokyo.md)" in out
    assert "SUMMARY: converted=2, unresolved_links=0" in result.stdout


# ── Same-language, same type: ./slug.md ─────────────────────────────────────────

def test_same_lang_same_type(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "yamada-jiro", "---\ntitle: Jiro\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Taro\n---\n\nBrother: [[Person/yamada-jiro]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[Jiro](./yamada-jiro.md)" in out


# ── Cross-language fallback: ../../<primary_lang>/Type/slug.md ─────────────────

def test_cross_lang_fallback(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "en", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nLives in [[Place/tokyo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "en" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[Tokyo](../../ja/Place/tokyo.md)" in out


# ── Same slug exists in both langs: same-language match wins over cross-lang ────
# #76 was actually a Quartz-side bug: the `crawl-links` plugin's `shortest`
# resolution re-matched already-correct hrefs against allSlugs and hit both
# ja/en copies of the same slug, dropping the language directory. That is
# fixed by the markdownLinkResolution: relative change in quartz.config.yaml
# and can only be verified by an actual Quartz build (see the checklist item
# in Issues/p2-015-e2e-verification.md). This test does not exercise that
# code path; it only guards convert_wikilinks.py's pre-existing (unchanged by
# #76) same-language-first precedence, which the relative-mode fix depends on
# staying correct.

def test_same_slug_both_languages_resolves_same_lang(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Person", "sato-minori", "---\ntitle: Sato\n---\n\nBody.\n")
    write_page(tmp_path, "en", "Person", "sato-minori", "---\ntitle: Sato\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Organization", "midori-no-hiroba-network",
        "---\ntitle: Midori\n---\n\nContact: [[Person/sato-minori]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Organization" / "midori-no-hiroba-network.md").read_text(
        encoding="utf-8"
    )
    assert "[Sato](../Person/sato-minori.md)" in out


# ── Link text uses the target page's title, not the raw Type/slug (Issue #354) ──

def test_link_text_falls_back_to_type_slug_when_title_missing(tmp_path):
    """A target page with no `title` frontmatter (or an empty one) must still
    resolve — the link text falls back to the pre-#354 `Type/slug` form
    rather than rendering an empty link label."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", "---\nlang: ja\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[Place/tokyo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[Place/tokyo](../Place/tokyo.md)" in out


def test_link_text_escapes_brackets_in_title(tmp_path):
    """A title containing `[`/`]` must not prematurely terminate the
    generated Markdown link's text span (same escaping already used by
    generate_sources_index() for other free-text link labels)."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", '---\ntitle: "Tokyo [1868]"\n---\n\nBody.\n')
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[Place/tokyo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert r"[Tokyo \[1868\]](../Place/tokyo.md)" in out


def test_link_text_escapes_quotes_in_frontmatter_wikilink(tmp_path):
    """A WikiLink embedded inside a double-quoted frontmatter value (e.g.
    `affiliation: "[[Organization/companya]]"`) must not break out of the
    enclosing YAML string if the resolved title contains a literal `"`."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Organization", "companya", '---\ntitle: "He said \\"Hi\\""\n---\n\nBody.\n')
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            ---
            title: "Yamada"
            affiliation: "[[Organization/companya]]"
            ---

            Body.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert 'affiliation: "[He said \\"Hi\\"](../Organization/companya.md)"' in out
    fm_text = out.split("---")[1]
    parsed = yaml.safe_load(fm_text)
    assert parsed["affiliation"] == '[He said "Hi"](../Organization/companya.md)'


# ── Unresolved link rendered as plain text (no raw [[...]] leaks to readers) ─────
# Issue #431: an unresolved WikiLink used to be left as the raw `m.group(0)` match
# (the literal `[[Type/slug]]` bracket syntax), which meant readers of the published
# site would see internal notation instead of either a working link or a dead link.
# The fix strips the brackets and renders `Type/slug` as plain text.

def test_unresolved_link_rendered_as_plain_text(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[Organization/unknown]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[[" not in out and "]]" not in out
    assert "Organization/unknown" in out
    assert "not resolved" in result.stdout
    assert "SUMMARY: converted=1, unresolved_links=1" in result.stdout


# ── Link to a status: removed page is also rendered as plain text ────────────────

def test_removed_target_rendered_as_plain_text(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        "---\ntitle: Tokyo\nstatus: removed\nremoved_at: \"2026-01-01\"\n---\n\nBody.\n",
    )
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[Place/tokyo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[[" not in out and "]]" not in out
    assert "Place/tokyo" in out
    assert "not resolved" in result.stdout
    assert "SUMMARY: converted=1, unresolved_links=1, skipped_removed=1, removed_stale=0" in result.stdout


def test_unresolved_link_in_unparseable_path_rendered_as_plain_text(tmp_path):
    """A .md file directly under wiki/ (not under <lang>/<type>/) can't have its
    own (lang, type) determined by parse_wiki_path(), so every WikiLink in it
    goes through the `lang is None or current_type is None` branch of
    replace() rather than the same-lang/primary-lang lookup branch exercised
    above. Both branches must render plain text, not raw [[...]] (Issue #431)."""
    write_config(tmp_path)
    entity_dir = tmp_path / "entity"
    entity_dir.mkdir(parents=True, exist_ok=True)
    (entity_dir / "orphan.md").write_text(
        "---\ntitle: Orphan\n---\n\nSee [[Organization/unknown]].\n", encoding="utf-8"
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "orphan.md").read_text(encoding="utf-8")
    assert "[[" not in out and "]]" not in out
    assert "Organization/unknown" in out
    assert "not resolved" in result.stdout


def test_removed_page_not_built(tmp_path):
    """status: removed pages must not be mirrored into content/ at all (Issue
    #271): the page itself was previously still written (only inbound links
    to it were left unresolved), leaving it reachable by direct URL on the
    published site."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        "---\ntitle: Tokyo\nstatus: removed\nremoved_at: \"2026-01-01\"\n---\n\nBody.\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert not (tmp_path / "content" / "ja" / "Place" / "tokyo.md").exists()


def test_stale_output_from_previous_run_removed(tmp_path):
    """A page removed from --source since the previous run (status: removed,
    or the source file deleted outright) must not leave its old content/
    output lingering across repeated invocations (e.g. `npm run preview`
    locally), which would keep it reachable by direct URL (Issue #271)."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        "---\ntitle: Tokyo\n---\n\nBody.\n",
    )
    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    out_path = tmp_path / "content" / "ja" / "Place" / "tokyo.md"
    assert out_path.exists()

    (tmp_path / "entity" / "ja" / "Place" / "tokyo.md").unlink()

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert not out_path.exists()
    assert "Removing stale build output" in result.stdout
    assert "SUMMARY: converted=0, unresolved_links=0, skipped_removed=0, removed_stale=1" in result.stdout


# ── Malformed / disallowed Type segments are left untouched ────────────────────

def test_double_slash_malformed_wikilink_left_unchanged(tmp_path):
    """A malformed [[Person//foo]] (double slash) must not match WIKILINK_RE
    at all (Issue #109/#114 regression: convert_wikilinks.py previously had a
    looser regex than check_wikilinks.py / check_orphans.py that could match
    type="Person/")."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[Person//foo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[[Person//foo]]" in out
    assert "SUMMARY: converted=1, unresolved_links=0" in result.stdout


def test_hyphenated_custom_type_wikilink_left_unchanged(tmp_path):
    """A [[custom/Multi-Word/slug]] link must not match WIKILINK_RE: custom
    type directory names are PascalCase without hyphens (docs/DesignDoc-data.md
    §5.3, Issue #114), so the hyphenated Type segment is left untouched rather
    than counted as an unresolved link."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[custom/Multi-Word/foo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[[custom/Multi-Word/foo]]" in out
    assert "SUMMARY: converted=1, unresolved_links=0" in result.stdout


# ── Frontmatter WikiLinks are also converted ─────────────────────────────────────

def test_frontmatter_wikilink_converted(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Organization", "companya", "---\ntitle: CompanyA\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        textwrap.dedent("""\
            ---
            title: "Yamada"
            affiliation: "[[Organization/companya]]"
            ---

            Body.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert 'affiliation: "[CompanyA](../Organization/companya.md)"' in out


# ── --primary-lang overrides config.yml ──────────────────────────────────────────

def test_primary_lang_cli_override(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "zh", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "en", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nLives in [[Place/tokyo]].\n",
    )

    result = run(
        ["--source", "entity/", "--output", "content/", "--primary-lang", "zh"],
        cwd=tmp_path,
    )
    assert result.returncode == 0

    out = (tmp_path / "content" / "en" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[Tokyo](../../zh/Place/tokyo.md)" in out


# ── Directory structure is mirrored ──────────────────────────────────────────────

def test_mirrors_directory_structure(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "DefinedTerm", "wikicommit", "---\ntitle: WikiCommit\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "content" / "ja" / "DefinedTerm" / "wikicommit.md").exists()


# ── Root content/index.md is generated to link to the primary_lang wiki top ─────

def test_root_index_generated_single_lang(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "[Wiki トップ (ja)](./ja/)" in out
    assert "review_status: reviewed" in out
    assert "言語を選択" not in out


# ── Root content/index.md lists a language selector when targets is non-empty ───

def test_root_index_language_selector(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en, zh]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(tmp_path, "zh", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "- [ja](./ja/)" in out
    assert "- [en](./en/)" in out
    assert "- [zh](./zh/)" in out


# ── Root content/index.md excludes targets with zero generated pages (#190) ─────
# Phase 1-3 has no translation pipeline (DesignDoc-pipeline.md §6.4), so a
# manually configured `targets` language commonly has no pages at all. Passing
# it through used to produce a dead link in the language selector.

def test_root_index_excludes_targets_without_pages(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en, zh]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(tmp_path, "zh", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    # "en" has no pages at all: no wiki/en/ directory exists.

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "- [ja](./ja/)" in out
    assert "- [zh](./zh/)" in out
    # The *link* must be absent, not the two letters: a bare substring test on a
    # two-letter code matches anything containing them (Issue #741 added a
    # `comm**en**ts: false` line to this very frontmatter).
    assert "- [en](./en/)" not in out


def test_root_index_no_selector_when_all_targets_have_no_pages(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en, zh]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    # Neither "en" nor "zh" has any pages.

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "[Wiki トップ (ja)](./ja/)" in out
    assert "言語を選択" not in out


def test_root_index_empty_target_lang_dir_treated_as_no_pages(tmp_path):
    """An existing but empty wiki/<lang>/ directory (e.g. leftover from a removed
    page) must not count as having pages."""
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    (tmp_path / "entity" / "en").mkdir(parents=True, exist_ok=True)

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "言語を選択" not in out
    # The *link* must be absent, not the two letters: a bare substring test on a
    # two-letter code matches anything containing them (Issue #741 added a
    # `comm**en**ts: false` line to this very frontmatter).
    assert "- [en](./en/)" not in out


def test_root_index_excludes_target_with_only_removed_or_index_pages(tmp_path):
    """A target lang dir containing only status: removed pages or an auto-generated
    Type/index.md (no live content) must not count as having pages."""
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "en", "Place", "tokyo",
        "---\ntitle: Tokyo\nstatus: removed\n---\n\nBody.\n",
    )
    write_page(tmp_path, "en", "Place", "index", "---\ntitle: Place\n---\n\nIndex.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "言語を選択" not in out
    # The *link* must be absent, not the two letters: a bare substring test on a
    # two-letter code matches anything containing them (Issue #741 added a
    # `comm**en**ts: false` line to this very frontmatter).
    assert "- [en](./en/)" not in out


def test_root_index_primary_lang_with_no_pages_does_not_crash(tmp_path):
    """primary_lang having zero pages (e.g. a brand-new repo's first build) must
    not break root index generation; the top link is still emitted unconditionally."""
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    # "ja" (primary_lang) has no wiki/ja/ directory at all.

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "[Wiki トップ (ja)](./ja/)" in out
    assert "- [en](./en/)" in out


# ── Non-list `targets` in config.yml is ignored rather than iterated as chars ───

def test_root_index_ignores_non_list_targets(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: en\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "言語を選択" not in out
    assert "- [e]" not in out


# ── Duplicate entries in `targets` produce one selector link each ───────────────

def test_root_index_dedupes_targets(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en, en]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert out.count("- [en](./en/)") == 1


# ── Root content/index.md uses non-Japanese chrome text for other primary_lang ──

def test_root_index_labels_follow_primary_lang(tmp_path):
    write_config(tmp_path, primary_lang="en")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "[Wiki Home (en)](./en/)" in out
    assert "トップ" not in out


# ── Root content/index.md is always regenerated, even if already present in
# --output from a previous local build (Issue #358: an earlier clobber guard
# here caused this page to freeze at its first-ever build content forever
# under repeated `npm run build`/`npm run preview` runs, since package.json's
# prebuild script never clears content/ between runs) ───────────────────────

def test_root_index_regenerated_when_stale(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    output_dir = tmp_path / "content"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.md").write_text("---\ntitle: Custom\n---\n\nCustom root page.\n", encoding="utf-8")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (output_dir / "index.md").read_text(encoding="utf-8")
    assert out != "---\ntitle: Custom\n---\n\nCustom root page.\n"
    assert "Wiki トップ" in out


# ── Site-wide page/reviewed count + theme embedded on content/index.md (Issue #407) ──

def test_root_index_embeds_page_and_reviewed_counts(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\nreview_status: reviewed\n---\n\nBody.\n")
    write_page(tmp_path, "ja", "Place", "osaka", "---\ntitle: Osaka\nreview_status: pending\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    fm = yaml.safe_load((tmp_path / "content" / "index.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["wikicommit_page_count"] == 2
    assert fm["wikicommit_reviewed_count"] == 1


def test_root_index_page_count_excludes_type_index_and_removed_pages(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\nreview_status: reviewed\n---\n\nBody.\n")
    write_page(tmp_path, "ja", "Place", "index", "---\ntitle: Place\n---\n\nIndex.\n")
    write_page(
        tmp_path, "ja", "Place", "removed-place",
        "---\ntitle: Removed\nstatus: removed\nreview_status: reviewed\n---\n\nBody.\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    fm = yaml.safe_load((tmp_path / "content" / "index.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["wikicommit_page_count"] == 1
    assert fm["wikicommit_reviewed_count"] == 1


def test_root_index_counts_pages_across_all_languages(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\nreview_status: reviewed\n---\n\nBody.\n")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\nreview_status: pending\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    # Issue #730: a multilingual wiki reports one pair of counts per language in
    # the body and omits the two frontmatter fields entirely, which is what stops
    # the banner from drawing a site-wide total (it renders only when both are
    # numbers). The single 2/1 total was nobody's view: each language's wiki is
    # one page, and the reviewed ratio was diluted by the untouched translation.
    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "wikicommit_page_count" not in out
    assert "wikicommit_reviewed_count" not in out
    body = root_index_body(tmp_path)
    assert "- [ja](./ja/)（1 ページ / 人が読んだ 1）" in body
    assert "- [en](./en/)（1 ページ / 人が読んだ 0）" in body


def test_root_index_never_embeds_theme_even_when_configured(tmp_path):
    """Issue #670: config.yml's `theme` is an LLM-facing scope instruction, not
    reader-facing copy, so generate_root_index() no longer emits it. Configuring
    a theme must therefore change nothing about content/index.md's frontmatter —
    this guards against the field being re-introduced."""
    write_config(tmp_path, theme='A "quoted" theme: with a colon')
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    fm = yaml.safe_load((tmp_path / "content" / "index.md").read_text(encoding="utf-8").split("---")[1])
    assert "wikicommit_theme" not in fm
    # The counts stay — they are language-independent (Issue #670 removed only the theme line).
    assert fm["wikicommit_page_count"] == 1


# ── site_description on the root index (#671) ──────────────────────────────────
#
# The reader-facing counterpart to `theme` (which Issue #670 removed from the
# published page precisely because it was written for the LLM, not for readers).
# It goes in the body, one line per language under that language's own link, so
# it never needs a caption and is never limited to the banner's two locales.

def root_index_body(root: Path) -> str:
    return (root / "content" / "index.md").read_text(encoding="utf-8").split("---", 2)[2]


def test_root_index_shows_site_description_for_every_language(tmp_path):
    write_config(
        tmp_path,
        primary_lang="it",
        targets=["en", "ja"],
        extra='site_description:\n  it: "Base di conoscenza sul Decameron."\n'
        '  en: "A knowledge base on the Decameron."\n'
        "  ja: 「デカメロン」の知識ベース。\n",
    )
    for lang in ("it", "en", "ja"):
        write_page(tmp_path, lang, "Book", "decameron", "---\ntitle: Decameron\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [it](./it/) (1 page / 0 read by a person) — Base di conoscenza sul Decameron." in body
    assert "- [en](./en/) (1 page / 0 read by a person) — A knowledge base on the Decameron." in body
    assert "- [ja](./ja/) (1 page / 0 read by a person) — 「デカメロン」の知識ベース。" in body


def test_root_index_omits_description_only_for_languages_without_one(tmp_path):
    write_config(
        tmp_path,
        primary_lang="it",
        targets=["en"],
        extra='site_description:\n  it: "Base di conoscenza sul Decameron."\n',
    )
    for lang in ("it", "en"):
        write_page(tmp_path, lang, "Book", "decameron", "---\ntitle: Decameron\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [it](./it/) (1 page / 0 read by a person) — Base di conoscenza sul Decameron." in body
    # The language without an entry keeps the counts but no dash — not an empty dash.
    assert "- [en](./en/) (1 page / 0 read by a person)\n" in body
    assert "- [en](./en/) (1 page / 0 read by a person) —" not in body


def test_root_index_without_site_description_is_unchanged(tmp_path):
    """An absent field must reproduce the previous output exactly, so existing
    repositories keep working (no retroactive migration — Issue #671)."""
    write_config(tmp_path, targets=["en"])
    for lang in ("ja", "en"):
        write_page(tmp_path, lang, "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    # Issue #730 adds the per-language counts; the em-dash description slot the
    # absent site_description would have filled stays empty either way.
    assert "- [ja](./ja/)（1 ページ / 人が読んだ 0）\n" in body
    assert "- [en](./en/)（1 ページ / 人が読んだ 0）\n" in body
    assert "—" not in body.split("## ")[1]


def test_root_index_single_language_puts_description_under_the_top_link(tmp_path):
    """With one language there is no language list to hang the line off, so it
    goes under the top link instead."""
    write_config(
        tmp_path, extra='site_description:\n  ja: 社内エンジニア組織の技術ナレッジベース。\n'
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "[Wiki トップ (ja)](./ja/)\n\n社内エンジニア組織の技術ナレッジベース。\n" in body
    # No language list is emitted for a single-language wiki.
    assert "## 言語を選択" not in body


def test_root_index_ignores_malformed_site_description(tmp_path):
    """A broken description must not take the build down — it is dropped, which
    is also what an unset field does (same tolerance load_theme() had)."""
    write_config(
        tmp_path,
        targets=["en"],
        # A bare string instead of a mapping, which yaml parses fine but is the
        # wrong shape entirely.
        extra="site_description: just a string\n",
    )
    for lang in ("ja", "en"):
        write_page(tmp_path, lang, "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert "- [ja](./ja/)（1 ページ / 人が読んだ 0）\n" in root_index_body(tmp_path)


def test_root_index_drops_only_the_non_string_site_description_entries(tmp_path):
    write_config(
        tmp_path,
        targets=["en"],
        extra="site_description:\n  ja: 技術ナレッジベース。\n  en:\n    nested: not a string\n",
    )
    for lang in ("ja", "en"):
        write_page(tmp_path, lang, "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [ja](./ja/)（1 ページ / 人が読んだ 0） — 技術ナレッジベース。" in body
    assert "- [en](./en/)（1 ページ / 人が読んだ 0）\n" in body


def test_root_index_collapses_newlines_inside_a_site_description(tmp_path):
    """A multi-line value (a YAML `|` block is a natural way to write three
    sentences) must still come out as one list item. Pasted verbatim, its blank
    line would end the language list and strand the remaining languages in a
    second one."""
    write_config(
        tmp_path,
        targets=["en"],
        extra="site_description:\n  ja: |\n    一行目です。\n\n    二行目です。\n  en: \"One. Two.\"\n",
    )
    for lang in ("ja", "en"):
        write_page(tmp_path, lang, "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [ja](./ja/)（1 ページ / 人が読んだ 0） — 一行目です。 二行目です。\n" in body
    # The list is still one list: the en row directly follows the ja row.
    assert "一行目です。 二行目です。\n- [en](./en/)（1 ページ / 人が読んだ 0） — One. Two.\n" in body


def test_root_index_skips_description_for_a_language_with_no_pages(tmp_path):
    """existing_lang_targets() already filters `langs` down to languages that
    have real pages (Issue #190). A description must not resurrect a dead link."""
    write_config(
        tmp_path,
        targets=["en"],
        extra='site_description:\n  ja: 技術ナレッジベース。\n  en: "A knowledge base."\n',
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "A knowledge base." not in body
    assert "(./en/)" not in body


# ── Root index also lists languages that have pages but are not in `targets` ───
# Issue #731: existing_lang_targets() only narrows `targets`, so the reverse gap
# (real pages, no `targets` entry) left those languages out of the one page whose
# whole job is choosing a language.

def test_root_index_lists_language_with_pages_missing_from_targets(tmp_path):
    write_config(tmp_path, primary_lang="ja", targets=[])
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "言語を選択" in out
    assert "- [ja](./ja/)" in out
    assert "- [en](./en/)" in out


def test_root_index_orders_primary_then_targets_then_discovered(tmp_path):
    """`targets` is written by a person, so its order is kept; discovered
    languages follow it in sorted order, leaving existing sites unchanged."""
    write_config(tmp_path, primary_lang="ja", targets=["zh", "en"])
    for lang in ("ja", "zh", "en", "fr", "de"):
        write_page(tmp_path, lang, "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    listed = [line[3:5] for line in out.splitlines() if line.startswith("- [")]
    assert listed == ["ja", "zh", "en", "de", "fr"]


def test_root_index_discovered_language_ignores_assets_directory(tmp_path):
    """.wikicommit/entity/assets/ is the language-neutral asset store
    (DesignDoc-data.md §3.1), not a language. Deriving from page_stats rather
    than a directory listing keeps it out structurally."""
    write_config(tmp_path, primary_lang="ja", targets=[])
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    assets_dir = tmp_path / "entity" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "diagram.png").write_bytes(b"\x89PNG\r\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "assets" not in out
    assert "言語を選択" not in out


def test_root_index_discovered_language_ignores_type_index_only_language(tmp_path):
    """A language left with nothing but a Type index.md (rebuild_index.py keeps
    one after the last page of a type is removed) must not get a front-door
    link into an empty tree — the same exclusion existing_lang_targets() makes."""
    write_config(tmp_path, primary_lang="ja", targets=[])
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "en", "Place", "index",
        "---\ntitle: Place\nlang: en\ntype: \"schema:Place\"\nreview_status: reviewed\n---\n\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "(./en/)" not in out
    assert "言語を選択" not in out


def test_root_index_shows_site_description_for_a_discovered_language(tmp_path):
    """A site_description entry for a language outside `targets` now renders,
    because that language finally has a link to hang it off."""
    write_config(
        tmp_path,
        primary_lang="ja",
        targets=[],
        extra='site_description:\n  ja: 技術ナレッジベース。\n  en: "A knowledge base."\n',
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [en](./en/)（1 ページ / 人が読んだ 0） — A knowledge base.\n" in body


def test_root_index_skips_discovered_language_whose_only_page_failed_to_write(tmp_path):
    """A page whose source cannot be read is still keyed into page_stats (the
    overview tallies it), but convert_file() writes nothing for it — so the
    language must not reach the front door, or the link points at a
    content/<lang>/ directory this build never created."""
    write_config(tmp_path, primary_lang="ja", targets=[])
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    # A directory named *.md: rglob lists it and parse_wiki_path() resolves it,
    # but read_text() raises IsADirectoryError.
    (tmp_path / "entity" / "de" / "Place" / "berlin.md").mkdir(parents=True)

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "(./de/)" not in out
    assert not (tmp_path / "content" / "de").exists()


def test_compute_langs_unions_targets_and_published_langs():
    assert _convert_wikilinks.compute_langs("ja", ["en"], ["ja", "en", "fr"]) == ["ja", "en", "fr"]
    # A targets language with no published pages is still kept: the caller has
    # already filtered it through existing_lang_targets(), which also sees the
    # view tree and files page_stats cannot resolve.
    assert _convert_wikilinks.compute_langs("ja", ["en"], ["ja"]) == ["ja", "en"]
    # Omitting published_langs reproduces the pre-#731 behaviour exactly.
    assert _convert_wikilinks.compute_langs("ja", ["en", "ja"]) == ["ja", "en"]


# ── Per-language counts on a multilingual root index (Issue #730) ─────────────
# The single site-wide total was nobody's view — the wiki behind each language
# link is that language's pages — and it diluted the reviewed ratio, which
# Issue #664 reframed as a statement about the trust ladder.

def test_root_index_reports_counts_per_language_and_drops_the_site_total(tmp_path):
    write_config(tmp_path, primary_lang="ja", targets=["en"])
    for slug in ("tokyo", "osaka"):
        write_page(
            tmp_path, "ja", "Place", slug,
            f"---\ntitle: {slug}\nreview_status: reviewed\n---\n\nBody.\n",
        )
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    # Omitting both fields is what suppresses the banner's site summary: it
    # renders only when both are numbers, so WikiCommitBanner.tsx needs no change.
    assert "wikicommit_page_count" not in out
    assert "wikicommit_reviewed_count" not in out
    body = root_index_body(tmp_path)
    assert "- [ja](./ja/)（2 ページ / 人が読んだ 2）" in body
    assert "- [en](./en/)（1 ページ / 人が読んだ 0）" in body


def test_root_index_keeps_the_site_total_on_a_single_language_wiki(tmp_path):
    """No language list to hang per-language counts off, so the banner keeps
    rendering exactly as before."""
    write_config(tmp_path, primary_lang="ja", targets=[])
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\nreview_status: reviewed\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    fm = yaml.safe_load((tmp_path / "content" / "index.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["wikicommit_page_count"] == 1
    assert fm["wikicommit_reviewed_count"] == 1


def test_root_index_keeps_issue_664_note_when_the_banner_stops_rendering(tmp_path):
    """The note explaining what "reviewed" counts lives in the same banner block
    as the numbers, so omitting the frontmatter would take it away too — and a
    bare "reviewed 0" reads as "nobody cares about this project", which is what
    Issue #664 fixed."""
    write_config(tmp_path, primary_lang="ja", targets=["en"])
    for lang in ("ja", "en"):
        write_page(tmp_path, lang, "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "ページは LLM が生成した時点で公開されます。" in body
    assert "Wiki の完成度でも、内容の正しさの保証でもありません。" in body
    # Under the language list, not above it.
    assert body.index("- [en](./en/)") < body.index("ページは LLM が生成した時点で")


def test_root_index_counts_view_pages_but_not_type_indexes(tmp_path):
    """View pages are published pages of their language like any other, so they
    count — matching the overview page's per-language tally. Type index.md is
    build-generated navigation and is excluded there too."""
    write_config(tmp_path, primary_lang="ja", targets=["en"])
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Place", "index",
        "---\ntitle: Place\nlang: ja\ntype: \"schema:Place\"\nreview_status: reviewed\n---\n\n",
    )
    view_dir = tmp_path / ".wikicommit" / "view" / "ja"
    view_dir.mkdir(parents=True, exist_ok=True)
    (view_dir / "agent-loop.md").write_text(
        "---\ntitle: Agent loop\nlang: ja\nkind: practice\n"
        "derived_from:\n  - path: .wikicommit/entity/ja/Place/tokyo.md\n    source_commit: \"\"\n---\n\nBody.\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(
        ["--source", "entity/", "--output", "content/", "--view-source", ".wikicommit/view"],
        cwd=tmp_path,
    )
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [ja](./ja/)（2 ページ / 人が読んだ 0）" in body


def test_root_index_reports_zero_for_a_language_with_no_resolvable_page(tmp_path):
    """existing_lang_targets() admits a language on any non-removed .md under
    it, including files that never resolve to <lang>/<Type>/<slug>.md. Such a
    language reaches the list with nothing page_stats can count."""
    write_config(tmp_path, primary_lang="ja", targets=["en"])
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    stray = tmp_path / "entity" / "en" / "loose.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("---\ntitle: Loose\n---\n\nBody.\n", encoding="utf-8")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [en](./en/)（0 ページ / 人が読んだ 0）" in body


def test_root_index_counts_use_english_singular_for_one_page(tmp_path):
    """`1 pages` in the default label set would be the one place this chrome
    reads as machine output."""
    write_config(tmp_path, primary_lang="en", targets=["fr"])
    for lang in ("en", "fr"):
        write_page(tmp_path, lang, "Place", "paris", "---\ntitle: Paris\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = root_index_body(tmp_path)
    assert "- [en](./en/) (1 page / 0 read by a person)" in body
    assert "1 pages" not in body


def test_root_index_zero_pages_still_embeds_zero_counts(tmp_path):
    write_config(tmp_path)

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    fm = yaml.safe_load((tmp_path / "content" / "index.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["wikicommit_page_count"] == 0
    assert fm["wikicommit_reviewed_count"] == 0


# ── content/sources/ mirrors .wikicommit/source/ (Issue #476) ──────────────────

def test_source_page_written_with_type_original_status_summary(tmp_path):
    write_config(tmp_path)
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc123
            status: generated
            generated_pages: []
            ---

            ## Summary

            Introduces the paper.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "paper-2024.md").read_text(encoding="utf-8")
    assert 'title: "raw/paper-2024.pdf"' in out
    assert "review_status: reviewed" in out
    assert "**種別**: path" in out
    assert "`raw/paper-2024.pdf`" in out
    assert "**ステータス**: generated" in out
    assert "Introduces the paper." in out
    assert "生成されたページはまだありません。" in out


def test_retracted_source_page_is_kept_and_says_so(tmp_path):
    """Issue #737: a retracted source keeps its public page rather than losing it.

    This is the opposite requirement from a `status: removed` page, which is
    never written into content/ at all (Issue #271) precisely so it stops being
    reachable. Here nothing needs to become unreachable — "this wiki used this
    source and then withdrew it" is a record worth publishing — so what is
    needed is a statement on the page, not its deletion.
    """
    write_config(tmp_path)
    write_source(
        tmp_path, "url/example.com/listing.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/listing
              hash: sha256:abc123
            status: retracted
            generated_pages: []
            ---

            ## Summary

            A city-wide company listing.

            ## Retraction Reason

            The 2019 figures contradict the city's own published statistics.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    page = tmp_path / "content" / "sources" / "url" / "example.com" / "listing.md"
    assert page.is_file()
    out = page.read_text(encoding="utf-8")
    assert "**ステータス**: retracted" in out
    # The bare status value is a field; on its own it does not tell a reader
    # what it means for the pages this source produced.
    assert "この情報源は取り下げられました" in out
    assert "## 取り下げの理由" in out
    assert "The 2019 figures contradict the city's own published statistics." in out


def test_non_retracted_source_page_has_no_retraction_block(tmp_path):
    write_config(tmp_path)
    write_source(
        tmp_path, "url/example.com/ok.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/ok
              hash: sha256:abc123
            status: generated
            generated_pages: []
            ---

            ## Summary

            Fine.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "url" / "example.com" / "ok.md").read_text(encoding="utf-8")
    assert "取り下げ" not in out


def test_retracted_source_page_without_a_reason_says_none_recorded(tmp_path):
    write_config(tmp_path)
    write_source(
        tmp_path, "url/example.com/listing.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/listing
              hash: sha256:abc123
            status: retracted
            generated_pages: []
            ---

            ## Summary

            A city-wide company listing.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "url" / "example.com" / "listing.md").read_text(encoding="utf-8")
    assert "## 取り下げの理由" in out
    assert "（理由の記載がありません）" in out


def test_source_page_renders_source_license_when_recorded(tmp_path):
    """Issue #558: the public source page states the same terms the per-page
    sources box does."""
    write_config(tmp_path)
    write_source(
        tmp_path, "url/it.wikipedia.org/Decameron.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://it.wikipedia.org/wiki/Decameron
              hash: sha256:abc123
              license: CC-BY-SA-4.0
            status: generated
            generated_pages: []
            ---

            ## Summary

            Boccaccio's Decameron.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "url" / "it.wikipedia.org" / "Decameron.md").read_text(encoding="utf-8")
    assert "**ライセンス**: CC-BY-SA-4.0" in out


def test_source_page_omits_license_line_when_blank_or_absent(tmp_path):
    """Blank means "unknown", not "unrestricted" — rendering an empty License
    line would read as a recorded license."""
    write_config(tmp_path)
    write_source(
        tmp_path, "url/example.com/article.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/article
              hash: sha256:abc123
              license:
            status: pending
            generated_pages: []
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "url" / "example.com" / "article.md").read_text(encoding="utf-8")
    assert "ライセンス" not in out


def test_source_page_url_type_renders_link_and_pending_status(tmp_path):
    write_config(tmp_path)
    write_source(
        tmp_path, "url/example.com/article.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/article
              hash: ""
            status: pending
            generated_pages: []
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "url" / "example.com" / "article.md").read_text(encoding="utf-8")
    assert "**種別**: url" in out
    assert "[https://example.com/article](https://example.com/article)" in out
    assert "**ステータス**: pending" in out
    assert "（まだ生成されていません）" in out


def test_source_page_generated_pages_link_to_content_pages_with_titles(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        '---\ntitle: "山田太郎"\n---\n\nBody.\n',
    )
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc123
            status: generated
            generated_pages:
              - .wikicommit/entity/ja/Person/yamada-taro.md
            ---

            ## Summary

            About Yamada.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "paper-2024.md").read_text(encoding="utf-8")
    assert "[山田太郎](../../../ja/Person/yamada-taro.md)" in out


def test_source_page_generated_pages_skips_removed_and_missing_targets(tmp_path):
    """A generated_pages[] entry pointing at a page later set to status:
    removed, or one that was deleted outright, must not render as a link —
    main()'s stale-cleanup sweeps such pages out of content/, so linking to
    one here would be a dead link on the published site."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nBody.\n",
    )
    write_page(
        tmp_path, "ja", "Person", "removed-person",
        '---\ntitle: Removed\nstatus: removed\nremoved_at: "2026-01-01"\n---\n\nBody.\n',
    )
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc123
            status: generated
            generated_pages:
              - .wikicommit/entity/ja/Person/yamada-taro.md
              - .wikicommit/entity/ja/Person/removed-person.md
              - .wikicommit/entity/ja/Person/deleted-person.md
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "paper-2024.md").read_text(encoding="utf-8")
    assert "[Yamada](../../../ja/Person/yamada-taro.md)" in out
    assert "removed-person" not in out
    assert "deleted-person" not in out


def test_source_page_generated_pages_rejects_path_escaping_entry(tmp_path):
    """A generated_pages[] entry that doesn't resolve to a same-tree relative
    path (absolute-looking, or escaping entity_dir via "..") must be dropped
    rather than fed into a filesystem path join (Path.__truediv__ silently
    discards the left side of a join when the right side looks absolute)."""
    write_config(tmp_path)
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc123
            status: generated
            generated_pages:
              - /etc/passwd
              - ../../../etc/passwd
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "paper-2024.md").read_text(encoding="utf-8")
    assert "passwd" not in out
    assert "生成されたページはまだありません。" in out


def test_source_page_generated_pages_legacy_wiki_prefix_still_resolves(tmp_path):
    """A generated_pages[] entry written before the Issue #477
    .wikicommit/wiki/ -> entity/ rename keeps its old prefix verbatim (no
    auto-migration, docs/DesignDoc-data.md §4.3's coexistence precedent) —
    normalize_wiki_rel() must still resolve it."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        '---\ntitle: "山田太郎"\n---\n\nBody.\n',
    )
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc123
            status: generated
            generated_pages:
              - .wikicommit/wiki/ja/Person/yamada-taro.md
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "paper-2024.md").read_text(encoding="utf-8")
    assert "[山田太郎](../../../ja/Person/yamada-taro.md)" in out


def test_source_page_generated_pages_rejects_double_prefixed_entry(tmp_path):
    """A hand-edited generated_pages[] entry with both prefixes stacked
    (`.wikicommit/entity/.wikicommit/wiki/...`) must not be silently
    normalized down to a plausible-looking relative path — normalize_wiki_rel()
    strips at most one prefix occurrence, so the malformed remainder still
    contains a literal `.wikicommit/` segment and can never resolve to a real
    page on disk."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        '---\ntitle: "山田太郎"\n---\n\nBody.\n',
    )
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc123
            status: generated
            generated_pages:
              - .wikicommit/entity/.wikicommit/wiki/ja/Person/yamada-taro.md
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "paper-2024.md").read_text(encoding="utf-8")
    assert "山田太郎" not in out
    assert "生成されたページはまだありません。" in out


def test_source_page_legacy_japanese_summary_heading_still_renders(tmp_path):
    """Pre-Issue-#405 management files used a `## サマリ` heading (no
    automatic migration, docs/DesignDoc-data.md §4.3) — the page must still
    surface that text instead of falling back to the placeholder."""
    write_config(tmp_path)
    write_source(
        tmp_path, "path/raw/legacy.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/legacy.pdf
              hash: sha256:abc123
            status: generated
            generated_pages: []
            ---

            ## サマリ

            旧形式の要約。
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "legacy.md").read_text(encoding="utf-8")
    assert "旧形式の要約。" in out
    assert "（まだ生成されていません）" not in out


def test_source_page_file_link_uses_github_repository_env(tmp_path):
    write_config(tmp_path)
    write_source(
        tmp_path, "path/raw/paper 2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper 2024.pdf
              hash: sha256:abc
            status: pending
            generated_pages: []
            ---
            """),
    )

    result = run(
        ["--source", "entity/", "--output", "content/"],
        cwd=tmp_path,
        env={"GITHUB_REPOSITORY": "wikicommit-dev/example-wiki"},
    )
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "path" / "raw" / "paper 2024.md").read_text(encoding="utf-8")
    assert (
        "[raw/paper 2024.pdf](https://github.com/wikicommit-dev/example-wiki/blob/main/raw/paper%202024.pdf)"
        in out
    )


def test_source_page_skips_malformed_frontmatter(tmp_path):
    write_config(tmp_path)
    write_source(tmp_path, "path/broken.md", "---\nsource: [this is not a mapping\n---\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert not (tmp_path / "content" / "sources" / "path" / "broken.md").exists()
    assert "WARNING" in result.stdout


def test_source_page_regenerated_when_stale(tmp_path):
    """content/sources/ pages are always regenerated, even if already present
    in --output from a previous local build (same Issue #358 freeze-bug
    class as generate_root_index()'s content/index.md)."""
    write_config(tmp_path)
    stale_path = tmp_path / "content" / "sources" / "path" / "raw" / "paper-2024.md"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("---\ntitle: Custom\n---\n\nCustom stale page.\n", encoding="utf-8")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert not stale_path.exists()


def test_sources_index_groups_entries_by_type(tmp_path):
    write_config(tmp_path)
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc
            status: pending
            generated_pages: []
            ---
            """),
    )
    write_source(
        tmp_path, "url/example.com/article.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/article
              hash: ""
            status: pending
            generated_pages: []
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "index.md").read_text(encoding="utf-8")
    assert "review_status: reviewed" in out
    assert "## ファイル" in out
    assert "[raw/paper-2024.pdf](./path/raw/paper-2024.md)" in out
    assert "## URL" in out
    assert "[https://example.com/article](./url/example.com/article.md)" in out


def test_sources_index_empty_when_no_management_files(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "index.md").read_text(encoding="utf-8")
    assert "登録されている情報源はありません。" in out


def test_sources_index_ignores_management_file_missing_source_type(tmp_path):
    write_config(tmp_path)
    write_source(tmp_path, "path/no-source-block.md", "---\nstatus: pending\n---\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "index.md").read_text(encoding="utf-8")
    assert "登録されている情報源はありません。" in out
    assert not (tmp_path / "content" / "sources" / "path" / "no-source-block.md").exists()


# ── Intermediate directory index.md pages (Issue #493) ──────────────────────

def test_source_dir_index_written_for_url_and_host_directories(tmp_path):
    """content/sources/url/ and content/sources/url/<host>/ each get their own
    index.md so Explorer navigation into them doesn't 404 — Quartz's
    folder-page plugin is enabled but does not auto-generate one for this
    tree."""
    write_config(tmp_path)
    write_source(
        tmp_path, "url/example.com/article.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/article
              hash: ""
            status: pending
            generated_pages: []
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    type_index = (tmp_path / "content" / "sources" / "url" / "index.md").read_text(encoding="utf-8")
    assert 'title: "URL"' in type_index
    assert "review_status: reviewed" in type_index
    assert "- [example.com](./example.com/)" in type_index

    host_index = (tmp_path / "content" / "sources" / "url" / "example.com" / "index.md").read_text(encoding="utf-8")
    assert 'title: "example.com"' in host_index
    assert "review_status: reviewed" in host_index
    assert "- [https://example.com/article](./article.md)" in host_index


def test_source_dir_index_written_for_nested_path_directories(tmp_path):
    """The same fix applies to `type: path` sources, which mirror the
    ingested file's own repo-relative path and can be nested just as deeply
    (docs/DesignDoc-data.md §4.3) — not hardcoded to `url` only."""
    write_config(tmp_path)
    write_source(
        tmp_path, "path/raw/paper-2024.md",
        textwrap.dedent("""\
            ---
            source:
              type: path
              path: raw/paper-2024.pdf
              hash: sha256:abc123
            status: pending
            generated_pages: []
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    type_index = (tmp_path / "content" / "sources" / "path" / "index.md").read_text(encoding="utf-8")
    assert 'title: "ファイル"' in type_index
    assert "- [raw](./raw/)" in type_index

    raw_index = (tmp_path / "content" / "sources" / "path" / "raw" / "index.md").read_text(encoding="utf-8")
    assert 'title: "raw"' in raw_index
    assert "- [raw/paper-2024.pdf](./paper-2024.md)" in raw_index


def test_source_dir_index_stale_cleanup_removes_now_empty_directory(tmp_path):
    """When a source is removed between runs, main()'s stale-cleanup pass
    must also remove the intermediate directory index.md pages it previously
    wrote — they're returned in generate_source_pages()'s `written` set like
    any other page, so this exercises that they aren't forgotten there."""
    write_config(tmp_path)
    url_source = write_source(
        tmp_path, "url/example.com/article.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/article
              hash: ""
            status: pending
            generated_pages: []
            ---
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    type_index = tmp_path / "content" / "sources" / "url" / "index.md"
    host_index = tmp_path / "content" / "sources" / "url" / "example.com" / "index.md"
    assert type_index.exists()
    assert host_index.exists()

    url_source.unlink()
    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert not type_index.exists()
    assert not host_index.exists()


def test_source_dir_index_does_not_clobber_source_page_named_index(tmp_path):
    """A management file whose own mirrored path happens to end in
    `index.md` — e.g. a `type: url` source sanitized from a URL whose path
    is `/index` (docs/DesignDoc-data.md §4.3 documents this exact collision
    class, previously solved once already at the bare-domain-vs-path layer
    for Issue #213) — must not have its real source page (Original link/
    Status/Summary/Generated pages) silently overwritten by the generic
    directory listing _write_source_dir_indexes() writes for its parent
    directory, since both resolve to the identical output path."""
    write_config(tmp_path)
    write_source(
        tmp_path, "url/example.com/index.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/index
              hash: ""
            status: pending
            generated_pages: []
            ---

            ## Summary

            The real summary that must survive.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out_path = tmp_path / "content" / "sources" / "url" / "example.com" / "index.md"
    content = out_path.read_text(encoding="utf-8")
    assert "The real summary that must survive." in content
    assert "https://example.com/index" in content

    # A second run (main()'s stale-cleanup pass runs every invocation) must
    # not sweep the real page away either, since it has to be present in the
    # returned `written` set even though _write_source_dir_indexes() skipped
    # writing to its path.
    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert out_path.exists()
    assert "The real summary that must survive." in out_path.read_text(encoding="utf-8")

    # The sibling directory index (url/index.md, a distinct path) is still
    # written normally.
    type_index = (tmp_path / "content" / "sources" / "url" / "index.md").read_text(encoding="utf-8")
    assert 'title: "URL"' in type_index
    assert "- [example.com](./example.com/)" in type_index


# ── Root content/index.md links to the single content/sources/ tree (Issue #476) ──

def test_root_index_links_to_single_sources_entry_point(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "[情報源一覧](./sources/)" in out
    assert (tmp_path / "content" / "sources" / "index.md").exists()


def test_root_index_single_sources_link_even_with_language_selector(tmp_path):
    """Unlike the language selector (one bullet per lang), the sources link
    is single and language-independent — the source tree has no `lang` concept."""
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "- [ja](./ja/)" in out
    assert "- [en](./en/)" in out
    assert out.count("./sources/") == 1
    assert "[情報源一覧](./sources/)" in out


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")


# ── Source tree is left untouched ────────────────────────────────────────────────

def test_source_not_modified(tmp_path):
    write_config(tmp_path)
    src = write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\nSee [[Place/tokyo]].\n",
    )
    person = tmp_path / "entity" / "ja" / "Person" / "yamada-taro.md"
    before = person.read_text(encoding="utf-8")

    run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert person.read_text(encoding="utf-8") == before
    assert src.read_text(encoding="utf-8") == "---\ntitle: Tokyo\n---\n\nBody.\n"


# ── assets/ mirroring into content/assets/ (#589) ───────────────────────────────

def write_asset(root: Path, rel_path: str, data: bytes = b"\x89PNG\r\n\x1a\n") -> Path:
    asset = root / "entity" / "assets" / rel_path
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(data)
    return asset


def test_assets_are_copied_to_content(tmp_path):
    """Before #589 nothing carried entity/assets/ into content/, so the relative
    path docs/DesignDoc-publish.md §8.6 recommends for local images 404'd."""
    write_config(tmp_path)
    write_asset(tmp_path, "diagram.png")
    write_asset(tmp_path, "sub/photo.jpg", b"\xff\xd8\xff")
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Yamada\n---\n\n![diagram](../../assets/diagram.png)\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    copied = tmp_path / "content" / "assets" / "diagram.png"
    assert copied.is_file()
    assert copied.read_bytes() == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "content" / "assets" / "sub" / "photo.jpg").is_file()
    assert "assets=2" in result.stdout
    # The relative path in the page body is left alone (it is plain Markdown,
    # not a WikiLink) and now resolves against the copied file.
    page = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "![diagram](../../assets/diagram.png)" in page


def test_assets_are_not_deleted_by_the_page_stale_cleanup(tmp_path):
    """The page cleanup walks content/**/*.md against a write set that assets are
    never in; assets carry their own set, so the two must not cross."""
    write_config(tmp_path)
    write_asset(tmp_path, "diagram.png")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")

    run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert (tmp_path / "content" / "assets" / "diagram.png").is_file()
    assert "removed_stale=0" in result.stdout
    assert "removed_stale_assets=0" in result.stdout


def test_deleted_asset_is_removed_from_content_on_next_run(tmp_path):
    """Same contract as Issue #271's page cleanup — no orphan residue that stays
    reachable by direct URL after the source file is gone."""
    write_config(tmp_path)
    write_asset(tmp_path, "diagram.png")
    write_asset(tmp_path, "old.png")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")
    run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert (tmp_path / "content" / "assets" / "old.png").is_file()

    (tmp_path / "entity" / "assets" / "old.png").unlink()
    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert not (tmp_path / "content" / "assets" / "old.png").exists()
    assert (tmp_path / "content" / "assets" / "diagram.png").is_file()
    assert "removed_stale_assets=1" in result.stdout


def test_asset_cleanup_does_not_touch_pages_outside_assets(tmp_path):
    """The asset cleanup is scoped to content/assets/ so it can never delete
    something another tool wrote elsewhere under content/."""
    write_config(tmp_path)
    write_asset(tmp_path, "diagram.png")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")
    run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    foreign = tmp_path / "content" / "assets-like" / "keep.png"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_bytes(b"keep")

    run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert foreign.is_file()


def test_markdown_under_assets_is_copied_not_converted(tmp_path):
    """A .md under assets/ must be treated as an attachment only — converting it
    as well would write two different files from one source."""
    write_config(tmp_path)
    write_asset(tmp_path, "notes.md", b"---\ntitle: Attachment\n---\n\n[[Person/yamada-taro]]\n")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    copied = tmp_path / "content" / "assets" / "notes.md"
    assert copied.is_file()
    # Copied verbatim: the WikiLink is untouched, i.e. it did not go through
    # convert_file().
    assert "[[Person/yamada-taro]]" in copied.read_text(encoding="utf-8")
    assert "converted=1" in result.stdout  # the page only, not the attachment
    assert "assets=1" in result.stdout


def test_asset_with_slugified_name_warns(tmp_path):
    """Quartz renames some filenames on the way to public/, which silently breaks
    the relative path a page body has to write."""
    write_config(tmp_path)
    write_asset(tmp_path, "My Diagram.png")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert "assets/my-diagram.png" in result.stdout
    # Still copied — the warning is advisory, not a gate.
    assert (tmp_path / "content" / "assets" / "My Diagram.png").is_file()


def test_asset_named_after_the_assets_dir_warns(tmp_path):
    """Quartz slugifies the content/-relative path, so a top-level asset whose
    stem repeats its parent directory (assets/assets.png) becomes index.png."""
    write_config(tmp_path)
    write_asset(tmp_path, "assets.png")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert "WARNING:" in result.stdout
    assert "assets/index.png" in result.stdout


def test_markdown_attachment_warning_does_not_suggest_a_rename(tmp_path):
    """Every .md loses its extension, so "rename it to match" is unachievable."""
    write_config(tmp_path)
    write_asset(tmp_path, "notes.md", b"---\ntitle: Attachment\n---\n\nBody.\n")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert "assets/notes" in result.stdout
    assert "Rename it to match" not in result.stdout


def test_uppercase_markdown_extension_is_not_reported_as_renamed(tmp_path):
    """Quartz's .md/.html check is case-sensitive, so a .MD attachment keeps its
    extension and must not be reported as renamed."""
    write_config(tmp_path)
    write_asset(tmp_path, "notes.MD", b"body\n")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert "WARNING:" not in result.stdout


def test_conforming_asset_names_do_not_warn(tmp_path):
    write_config(tmp_path)
    write_asset(tmp_path, "diagram-01.png")
    write_asset(tmp_path, "under_score.png")
    write_asset(tmp_path, "図表.png")
    write_asset(tmp_path, "dot.name.png")
    write_page(tmp_path, "ja", "Person", "yamada-taro", "---\ntitle: Yamada\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)

    assert "WARNING:" not in result.stdout


# Ground truth captured by running the real slugifyFilePath from
# @quartz-community/utils 0.1.1 (the function Quartz's builtin Assets emitter
# applies to every file it copies out of content/). Pinning these keeps the
# Python port honest if either side changes.
QUARTZ_SLUG_CASES = [
    ("diagram.png", "diagram.png"),
    ("My Diagram.PNG", "my-diagram.PNG"),   # stem lowercased, extension is not
    ("a&b.png", "a-and-b.png"),
    ("50%.png", "50-percent.png"),
    ("q?x.png", "qx.png"),
    ("a<b>c.png", "abc.png"),
    ("x#y.png", "xy.png"),
    ("a b  c.png", "a-b--c.png"),
    ("UPPER.png", "upper.png"),
    ("foo/foo.png", "foo/index.png"),        # name repeating its parent directory
    ("_index.png", "index.png"),
    ("sub/dir/x.jpg", "sub/dir/x.jpg"),
    ("under_score.png", "under_score.png"),
    ("dot.name.png", "dot.name.png"),
    ("図表.png", "図表.png"),                  # non-ASCII survives untouched
    ("notes.MD", "notes.MD"),                # .md/.html check is case-sensitive
    # Slugified as sync_assets() calls it: on the content/-relative path.
    ("assets/diagram.png", "assets/diagram.png"),
    ("assets/assets.png", "assets/index.png"),
    ("assets/notes.md", "assets/notes"),
]


def test_quartz_asset_slug_matches_quartz():
    for given, expected in QUARTZ_SLUG_CASES:
        assert _convert_wikilinks.quartz_asset_slug(given) == expected, given


# ── custom/ flattening on publish (Issue #576) ─────────────────────────────────

def test_custom_type_page_publishes_without_the_custom_segment(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        "---\ntitle: Quartz\n---\n\nBody.\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    assert (tmp_path / "content" / "ja" / "Decision" / "adopt-quartz.md").is_file()
    assert not (tmp_path / "content" / "ja" / "custom").exists()


def test_custom_type_page_survives_the_same_run_stale_cleanup(tmp_path):
    """The write set and the output path have to be the same value: computing
    the flattened path in only one of the two makes the cleanup pass delete
    the file the run just wrote (Issue #271's sweep, Issue #576's move)."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "custom/Decision", "x", "---\ntitle: X\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "content" / "ja" / "Decision" / "x.md").is_file()
    assert "removed_stale=0" in result.stdout

    # A second run over unchanged input must be a no-op too.
    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert (tmp_path / "content" / "ja" / "Decision" / "x.md").is_file()
    assert "removed_stale=0" in result.stdout


def test_wikilink_to_a_custom_type_page_uses_the_flattened_path(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "custom/Decision", "adopt-quartz", "---\ntitle: Quartz\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Taro\n---\n\nSee [[custom/Decision/adopt-quartz]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert "unresolved_links=0" in result.stdout

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "[Quartz](../Decision/adopt-quartz.md)" in out


def test_wikilink_from_a_custom_type_page_uses_the_flattened_source_dir(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        "---\ntitle: Quartz\n---\n\nSee [[Place/tokyo]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert "unresolved_links=0" in result.stdout

    out = (tmp_path / "content" / "ja" / "Decision" / "adopt-quartz.md").read_text(encoding="utf-8")
    # One level up from ja/Decision/, not the two ja/custom/Decision/ would need.
    assert "[Tokyo](../Place/tokyo.md)" in out


def test_cross_lang_fallback_from_a_custom_type_page_is_flattened_on_both_ends(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "custom/Decision", "adopt-quartz", "---\ntitle: Quartz\n---\n\nBody.\n")
    write_page(
        tmp_path, "en", "custom/Decision", "other",
        "---\ntitle: Other\nlang: en\n---\n\nSee [[custom/Decision/adopt-quartz]].\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert "unresolved_links=0" in result.stdout

    out = (tmp_path / "content" / "en" / "Decision" / "other.md").read_text(encoding="utf-8")
    assert "[Quartz](../../ja/Decision/adopt-quartz.md)" in out


def test_body_relative_asset_link_is_rewritten_when_the_page_is_flattened(tmp_path):
    """A body written against the entity tree reaches entity/assets/ with
    ../../../ from <lang>/custom/<Type>/. Publishing moves the page up one
    level, so the link needs one fewer (Issue #576 / #589)."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "custom/Decision", "adopt-quartz",
        "---\ntitle: Quartz\n---\n\n![diagram](../../../assets/diagram.png)\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Decision" / "adopt-quartz.md").read_text(encoding="utf-8")
    assert "![diagram](../../assets/diagram.png)" in out


def test_body_relative_links_are_untouched_for_a_standard_type_page(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "yamada-taro",
        "---\ntitle: Taro\n---\n\n![d](../../assets/d.png) and [x](https://example.com/a)\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "![d](../../assets/d.png)" in out
    assert "[x](https://example.com/a)" in out


def test_absolute_and_anchor_link_targets_survive_flattening_unchanged(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "custom/Decision", "x",
        "---\ntitle: X\n---\n\n"
        "[a](https://example.com/p) [b](/root.png) [c](#section) [d](mailto:a@example.com)\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Decision" / "x.md").read_text(encoding="utf-8")
    assert "[a](https://example.com/p)" in out
    assert "[b](/root.png)" in out
    assert "[c](#section)" in out
    assert "[d](mailto:a@example.com)" in out


def test_flatten_custom_type_strips_only_the_first_segment():
    assert _convert_wikilinks.flatten_custom_type("custom/Decision") == "Decision"
    assert _convert_wikilinks.flatten_custom_type("custom/custom/Decision") == "custom/Decision"
    assert _convert_wikilinks.flatten_custom_type("Person") == "Person"
    assert _convert_wikilinks.flatten_custom_type("Customer") == "Customer"


def test_flatten_entity_rel_leaves_non_custom_paths_alone():
    assert _convert_wikilinks.flatten_entity_rel(Path("ja/custom/Decision/x.md")) == Path("ja/Decision/x.md")
    assert _convert_wikilinks.flatten_entity_rel(Path("ja/Person/x.md")) == Path("ja/Person/x.md")
    # Too short to be a page: leave it be rather than mangling it.
    assert _convert_wikilinks.flatten_entity_rel(Path("ja/custom.md")) == Path("ja/custom.md")


def test_output_path_collision_warns_and_keeps_the_unflattened_page(tmp_path):
    """Impossible today (a custom type is Schema.org-absent by definition), but
    a name Schema.org adds later could collide. The standard type keeps its
    path; the custom one is skipped with a WARNING rather than overwriting it."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Decision", "x", "---\ntitle: Standard\n---\n\nBody.\n")
    write_page(tmp_path, "ja", "custom/Decision", "x", "---\ntitle: Custom\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Decision" / "x.md").read_text(encoding="utf-8")
    assert "title: Standard" in out
    assert "WARNING:" in result.stdout
    assert "already claimed by" in result.stdout
    assert "SUMMARY: converted=1" in result.stdout


def test_generated_pages_link_from_a_source_page_uses_the_flattened_path(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "custom/Decision", "adopt-quartz", "---\ntitle: Quartz\n---\n\nBody.\n")
    write_source(
        tmp_path, "url/example.com/article.md",
        textwrap.dedent("""\
            ---
            source:
              type: url
              url: https://example.com/article
              hash: "sha256:abc"
            status: generated
            generated_pages:
              - .wikicommit/entity/ja/custom/Decision/adopt-quartz.md
            ---

            ## Summary

            Summary text.
            """),
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "url" / "example.com" / "article.md").read_text(encoding="utf-8")
    assert "(../../../ja/Decision/adopt-quartz.md)" in out


def test_relative_link_between_two_pages_of_the_same_custom_type_stays_resolvable(tmp_path):
    """`resolved` names the target in the entity tree, so it needs the same
    flattening the target page itself gets. Without it a sibling link is
    re-aimed at content/ja/custom/Decision/, a directory publishing no longer
    creates (Issue #576)."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "custom/Decision", "a",
        "---\ntitle: A\n---\n\nSee [b](./b.md).\n",
    )
    write_page(tmp_path, "ja", "custom/Decision", "b", "---\ntitle: B\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Decision" / "a.md").read_text(encoding="utf-8")
    assert "[b](./b.md)" in out


def test_relative_link_into_a_custom_type_page_is_rewritten_from_an_unmoved_page(tmp_path):
    """The linking page does not move, but its target does — skipping every
    page whose own directory is unchanged would leave this link dangling
    (Issue #576)."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "custom/Decision", "a", "---\ntitle: A\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "taro",
        "---\ntitle: Taro\n---\n\nSee [a](../custom/Decision/a.md).\n",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "ja" / "Person" / "taro.md").read_text(encoding="utf-8")
    assert "[a](../Decision/a.md)" in out


# ── Wiki-wide overview page: content/overview/index.md (Issue #585) ────────────

OVERVIEW_REL = ("content", "overview", "index.md")


def read_overview(root: Path) -> str:
    return root.joinpath(*OVERVIEW_REL).read_text(encoding="utf-8")


def build_overview_fixture(root: Path) -> None:
    """A small wiki exercising every overview section: two languages, two
    types, a hub page, an orphan, a wanted link, a manual source and a url
    management file with generated_pages."""
    write_config(root, primary_lang="ja")
    write_page(
        root, "ja", "Person", "yamada-taro",
        "---\ntitle: 山田太郎\nlang: ja\ntype: schema:Person\ntags: [engineer, ml]\n"
        "review_status: reviewed\n---\n\n[[Place/tokyo]] と [[DefinedTerm/nashi]]。\n",
    )
    write_page(
        root, "ja", "Place", "tokyo",
        "---\ntitle: 東京\nlang: ja\ntype: schema:Place\ntags: [city]\nreview_status: pending\n"
        "sources:\n  - type: manual\n    author: taro\n    created_at: \"2026-01-01\"\n---\n\nBody.\n",
    )
    write_page(
        root, "en", "Person", "yamada-taro",
        "---\ntitle: Taro Yamada\nlang: en\ntype: schema:Person\n"
        "translated_from: .wikicommit/entity/ja/Person/yamada-taro.md\nreview_status: pending\n---\n\nBody.\n",
    )
    write_source(
        root, "url/example.com/article.md",
        "---\nsource:\n  type: url\n  url: https://www.example.com/article\n  hash: sha256:abc\n"
        "status: generated\ngenerated_pages:\n"
        "  - .wikicommit/entity/ja/Person/yamada-taro.md\n"
        "  - .wikicommit/entity/ja/Place/tokyo.md\n---\n\n## Summary\n\nSummary text.\n",
    )


def test_overview_page_generated_and_linked_from_root_index(tmp_path):
    build_overview_fixture(tmp_path)

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    assert tmp_path.joinpath(*OVERVIEW_REL).is_file()
    out = read_overview(tmp_path)
    # Build-generated navigation, so it must not carry the unreviewed banner.
    assert "review_status: reviewed" in out
    assert 'title: "Wiki 全体の俯瞰"' in out

    root_index = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "[Wiki 全体の俯瞰](./overview/)" in root_index


def test_overview_totals_count_pages_reviewed_langs_and_translation_coverage(tmp_path):
    build_overview_fixture(tmp_path)
    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "**総ページ数**: 3" in out
    assert "**人が読んだページ**: 1 / 3 (33%)" in out
    # Issue #664: the bare count reads as "nobody cares about this project";
    # the number stays and a caption below the totals says what it counts.
    assert "人が最後まで読んだ件数です" in out
    assert "**型数**: 2" in out
    assert "**言語別ページ数**: en 1, ja 2" in out
    # One of the two ja keys also exists in en.
    assert "**翻訳カバレッジ**: en 1 / 2 (50%)" in out
    # The caption sits after the whole list, not between two of its bullets:
    # the translation-coverage bullet is appended conditionally, so a caption
    # emitted with the other totals splits the list on every multi-language
    # wiki and reads as an introduction to the coverage line.
    note_at = out.index("ページは LLM が生成した時点で公開されます")
    assert out.index("**翻訳カバレッジ**") < note_at
    assert note_at < out.index("## 知識の中心")


def test_overview_hub_section_ranks_pages_by_backlink_count(tmp_path):
    build_overview_fixture(tmp_path)
    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "- [東京](../ja/Place/tokyo.md) — 被リンク数: 1" in out
    # Only the primary-language page represents a key, so the en translation of
    # an unreferenced page never shows up as a hub either.
    assert "被リンク数: 0" not in out


def test_overview_by_type_table_reports_counts_reviewed_avg_backlinks_and_orphans(tmp_path):
    build_overview_fixture(tmp_path)
    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "| `Person` | 2 | 1 (50%) | 0.0 | 2 |" in out
    assert "| `Place` | 1 | 0 (0%) | 1.0 | 0 |" in out


def test_overview_lists_wanted_pages_as_referrer_links_not_wikilinks(tmp_path):
    build_overview_fixture(tmp_path)
    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "- `DefinedTerm/nashi` — 参照元: [山田太郎](../ja/Person/yamada-taro.md)" in out
    # A wanted key has no page by definition, so emitting it as a WikiLink
    # would leave an unresolved link on the published page.
    assert "[[" not in out


def test_overview_lists_orphan_pages(tmp_path):
    build_overview_fixture(tmp_path)
    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "- [Taro Yamada](../en/Person/yamada-taro.md)" in out
    assert "- [山田太郎](../ja/Person/yamada-taro.md)" in out


def test_overview_source_breakdown_counts_type_status_host_and_cross_tab(tmp_path):
    build_overview_fixture(tmp_path)
    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "| `url` | 1 |" in out
    # manual only ever appears on a page's own sources[], never as a management
    # file, so it is counted in pages and labelled to say so.
    assert "| manual（ページの sources[] のみ。管理ファイルを持たない） | 1 |" in out
    assert "| `generated` | 1 |" in out
    # www. is stripped so one publisher cannot split into two rows.
    assert "| `example.com` | 1 |" in out
    assert "| `url` | 1 | 1 | 2 |" in out


def test_overview_tag_ranking(tmp_path):
    build_overview_fixture(tmp_path)
    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "| `city` | 1 |" in out
    assert "| `engineer` | 1 |" in out
    assert "| `ml` | 1 |" in out


def test_overview_labels_follow_primary_lang(tmp_path):
    write_config(tmp_path, primary_lang="en")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert 'title: "Overview"' in out
    assert "## At a glance" in out
    assert "俯瞰" not in out
    # Issue #664: both label dicts carry the reframed count and its caption, and
    # the two must say the same thing — a reader following the root index's link
    # sees both surfaces in a row.
    assert "**Read by a person**:" in out
    assert "how many a person has since read all the way through" in out


def test_overview_written_with_no_pages_at_all(tmp_path):
    """The root index always links to ./overview/, so the page has to exist
    even for a wiki with nothing in it — same invariant content/sources/index.md
    upholds (Issue #476)."""
    write_config(tmp_path)
    (tmp_path / "entity").mkdir(parents=True, exist_ok=True)

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "まだページがありません。" in out


def test_overview_not_deleted_by_stale_cleanup(tmp_path):
    """The overview's output path must be registered in written_rel_paths, or
    the stale-cleanup pass deletes it in the same run that wrote it (the Issue
    #271 failure mode)."""
    build_overview_fixture(tmp_path)

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert tmp_path.joinpath(*OVERVIEW_REL).is_file()
    assert "Removing stale build output" not in result.stdout

    # And it survives a second, incremental build over the same content/ dir,
    # which is where the stale-cleanup pass actually has something to sweep.
    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0
    assert tmp_path.joinpath(*OVERVIEW_REL).is_file()
    assert "Removing stale build output" not in result.stdout


def test_overview_excludes_removed_pages_from_gaps_and_totals(tmp_path):
    """A link at a removed page is check_wikilinks.py's ERROR, not a page
    nobody has written yet — listing it under "referenced but not written"
    would tell the reader to write a page that was deliberately taken down."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "taro",
        "---\ntitle: Taro\n---\n\n[[Place/tokyo]]\n",
    )
    write_page(
        tmp_path, "ja", "Place", "tokyo",
        "---\ntitle: 東京\nstatus: removed\nremoved_at: \"2026-01-01\"\n---\n\nBody.\n",
    )

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "**総ページ数**: 1" in out
    assert "Place/tokyo" not in out


def test_overview_omits_type_mismatched_links_from_wanted(tmp_path):
    """A link whose slug exists under another Type is a Type typo (Issue #563),
    not a missing page. check_wanted_pages.py reports it as TYPE_MISMATCH for
    the operator; telling a reader to write a page that already exists is
    worse than saying nothing."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "taro",
        "---\ntitle: Taro\n---\n\n[[Organization/tokyo]]\n",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: 東京\n---\n\nBody.\n")

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "Organization/tokyo" not in out


def test_overview_type_index_pages_are_not_counted_and_do_not_hide_orphans(tmp_path):
    """rebuild_index.py's per-Type index.md links to every page of its type, so
    counting it as a referrer would make every page look referenced — the same
    exclusion check_orphans.py applies."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "taro", "---\ntitle: Taro\n---\n\nBody.\n")
    write_page(
        tmp_path, "ja", "Person", "index",
        "---\ntitle: Person\nreview_status: reviewed\n---\n\n[[Person/taro]] — Taro\n",
    )

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "**総ページ数**: 1" in out
    assert "- [Taro](../ja/Person/taro.md)" in out


def test_overview_custom_type_shown_flattened(tmp_path):
    """Publishing drops a custom type's `custom/` segment (Issue #576), and the
    overview is a published page, so its type column has to match."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "custom/Decision", "adopt", "---\ntitle: Adopt\n---\n\nBody.\n")

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "| `Decision` |" in out
    assert "custom/Decision" not in out
    assert "(../ja/Decision/adopt.md)" in out


def test_overview_does_not_rewrite_source_management_files(tmp_path):
    """The overview deliberately leaves check_ingest_freshness.py to
    /wikicommit-status: it writes `status: outdated` back into management
    files, and a build must never modify the repository it is building."""
    build_overview_fixture(tmp_path)
    mgmt = tmp_path / ".wikicommit" / "source" / "url" / "example.com" / "article.md"
    before = mgmt.read_text(encoding="utf-8")

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    assert mgmt.read_text(encoding="utf-8") == before


def test_url_host_normalizes_www_and_case():
    assert _convert_wikilinks.url_host("https://WWW.Example.COM/a?b=c") == "example.com"
    assert _convert_wikilinks.url_host("https://ja.wikipedia.org/wiki/X") == "ja.wikipedia.org"
    assert _convert_wikilinks.url_host("not a url") is None
    assert _convert_wikilinks.url_host("") is None
    assert _convert_wikilinks.url_host(None) is None


def test_overview_table_cells_escape_pipes(tmp_path):
    """A `|` in a tag would otherwise split the row into extra columns and
    shift every value after it."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "taro",
        '---\ntitle: Taro\ntags: ["a|b"]\n---\n\nBody.\n',
    )

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "| `a\\|b` | 1 |" in out


def test_overview_ignores_scalar_tags_value(tmp_path):
    """`tags: engineer` (a string, not a list) must not iterate character by
    character and register one tag per letter."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "taro", "---\ntitle: Taro\ntags: engineer\n---\n\nBody.\n")

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "| `e` |" not in out
    assert "| `engineer` |" not in out


def test_overview_counts_backlinks_per_key_not_per_language(tmp_path):
    """A WikiLink carries no language, so a page and its translations are one
    node. Counting per page would double every number the moment a wiki gains a
    second language, with no new link written."""
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: 東京\n---\n\nBody.\n")
    write_page(tmp_path, "ja", "Person", "taro", "---\ntitle: Taro\n---\n\n[[Place/tokyo]]\n")
    write_page(
        tmp_path, "en", "Person", "taro",
        "---\ntitle: Taro\ntranslated_from: .wikicommit/entity/ja/Person/taro.md\n---\n\n[[Place/tokyo]]\n",
    )

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "- [東京](../ja/Place/tokyo.md) — 被リンク数: 1" in out


def test_overview_self_link_is_not_a_backlink(tmp_path):
    """A page's only inbound link being its own makes it an orphan here, even
    though check_orphans.py counts it as referenced."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "taro", "---\ntitle: Taro\n---\n\n[[Person/taro]]\n")

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "被リンク数" not in out.split("## 型別の傾向")[0].split("## 知識の中心")[1]
    assert "- [Taro](../ja/Person/taro.md)" in out


def test_overview_wanted_referrers_deduped_across_languages(tmp_path):
    """Referrers are counted in the same unit as the hub ranking — one entry
    per referring key, represented by its primary-language page."""
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Person", "taro", "---\ntitle: 太郎\n---\n\n[[Place/nashi]]\n")
    write_page(
        tmp_path, "en", "Person", "taro",
        "---\ntitle: Taro\ntranslated_from: .wikicommit/entity/ja/Person/taro.md\n---\n\n[[Place/nashi]]\n",
    )

    assert run(["--source", "entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    out = read_overview(tmp_path)
    assert "- `Place/nashi` — 参照元: [太郎](../ja/Person/taro.md)\n" in out
    assert "Taro](../en/" not in out.split("### 参照されているが存在しないページ")[1].split("###")[0]


# ── Site-wide licensing notice (Issue #645, layer 2 of §8.10's four layers) ────
# The per-page notice WikiCommitSources renders (Issue #558, layer 1) never
# reaches a reader looking at the site as a whole; these two build-generated
# entry points are where that reader arrives.

def test_root_index_carries_site_wide_licensing_notice(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "サイト全体に単一のライセンスはありません" in out
    # Placed after both entry-point links: it qualifies the site rather than
    # offering somewhere else to go.
    assert out.index("(./overview/)") < out.index("サイト全体に単一のライセンスはありません")


def test_root_index_licensing_notice_follows_primary_lang(tmp_path):
    write_config(tmp_path, primary_lang="en")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "no single license covering the whole site" in out
    assert "単一のライセンス" not in out


def test_sources_index_carries_licensing_section(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")
    mgmt = tmp_path / ".wikicommit" / "source" / "url" / "example.com"
    mgmt.mkdir(parents=True, exist_ok=True)
    (mgmt / "article.md").write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/article\n"
        "  license: CC-BY-SA-4.0\nstatus: generated\n---\n\n## Summary\n\nBody.\n",
        encoding="utf-8",
    )

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "index.md").read_text(encoding="utf-8")
    # Assert the entry actually landed, so this test cannot silently degrade into a
    # second copy of the no-sources case below if management-file parsing regresses.
    assert "[https://example.com/article](./url/example.com/article.md)" in out
    assert "## 利用条件について" in out
    assert "サイト全体に適用される単一のライセンスはありません" in out
    # "not recorded" must not read as "unrestricted".
    assert "「制約が無い」という意味ではありません" in out


def test_sources_index_licensing_section_shown_when_no_sources_registered(tmp_path):
    """The statement is about how this wiki works, not about current contents."""
    write_config(tmp_path, primary_lang="en")
    write_page(tmp_path, "en", "Place", "tokyo", "---\ntitle: Tokyo\n---\n\nBody.\n")

    result = run(["--source", "entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    out = (tmp_path / "content" / "sources" / "index.md").read_text(encoding="utf-8")
    assert "No sources have been registered yet." in out
    assert "## About terms of use" in out
    assert "no single license applies to the site as a whole" in out


# ── AI review verdicts published to content/ only (Issue #751) ───────────────
#
# The build reads .wikicommit/review/ as a second input and stamps the verdict
# onto the published copy of a page. Nothing is written back into
# .wikicommit/entity/, which is what keeps the record tree the single place a
# verdict lives — and what lets a verdict be withheld the moment it goes stale,
# the failure a copy in the page's own frontmatter could not notice (Issue #705).

RECORD_SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "record_review.py"


def write_wikicommit_page(root: Path, lang: str, type_name: str, slug: str, body: str) -> Path:
    """Write a page under `.wikicommit/entity/`, the real --source root.

    Distinct from write_page() above, which uses a bare `entity/`: review
    records are addressed by a repository-relative page path, so this feature
    only engages under the prefix record_review.py accepts.
    """
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(body, encoding="utf-8")
    return page


def record_review(root: Path, page_rel: str, *, model: str, reviewed_at: str,
                  findings: str | None = None,
                  result: str = "pass") -> subprocess.CompletedProcess:
    """Write one `kind: ai` record via record_review.py itself.

    Deliberately the real writer rather than a hand-built file: what this test
    ultimately asserts is that the two scripts agree on the record's shape and
    on how `page_content_hash` is computed, and a fixture would assert only that
    the reader agrees with the fixture.
    """
    args = [
        sys.executable, str(RECORD_SCRIPT), page_rel,
        "--kind", "ai", "--stage", "generate-pass4", "--result", result,
        "--model", model, "--reviewed-at", reviewed_at,
    ]
    if findings is not None:
        args += ["--json", "-"]
    return subprocess.run(
        args, capture_output=True, text=True, cwd=root, check=True,
        input=findings if findings is not None else None,
    )


PAGE_WITH_STAMPS = (
    "---\n"
    'title: "山田太郎"\n'
    "lang: ja\n"
    'type: "schema:Person"\n'
    "review_status: pending\n"
    'generated_at: "2026-06-17"\n'
    'generated_by: "claude-opus-5"\n'
    "---\n"
    "\n"
    "本文。\n"
)


def test_standing_ai_verdict_is_stamped_on_the_published_copy_only(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    page = write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert 'ai_review_model: "claude-opus-5[1m]"' in published
    assert 'ai_review_at: "2026-09-05"' in published
    # The body and every original frontmatter key survive: the stamp is a textual
    # insertion, not a YAML round-trip, so nothing else in the page is reformatted.
    assert "本文。" in published
    assert 'generated_by: "claude-opus-5"' in published

    # The entity page is the point of the whole design: it must not gain a field.
    assert "ai_review" not in page.read_text(encoding="utf-8")


def test_stale_ai_verdict_is_withheld_after_the_page_changes(tmp_path):
    """A verdict made against text that is no longer there says nothing about
    the page being published now — this is why the hash, not a copied flag."""
    write_config(tmp_path, primary_lang="ja")
    page = write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )
    page.write_text(PAGE_WITH_STAMPS + "\n後から書き足された一文。\n", encoding="utf-8")

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "ai_review_model" not in published
    assert "ai_review_at" not in published


def test_page_with_no_record_publishes_exactly_as_before(tmp_path):
    """Pages predating the record tree keep their old rendering — the blank is
    permanent (a record cannot be made retroactively) and must stay silent."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "ai_review" not in published
    overview = (tmp_path / "content" / "overview" / "index.md").read_text(encoding="utf-8")
    # Not "0 / 1", which would read as a check that ran and failed.
    assert "出典と照合済み（AI）" not in overview


def test_overview_reports_ai_review_separately_from_human_review(tmp_path):
    """The machine's count never shares Issue #664's `reviewed` label, which was
    made to say 人による out loud."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    overview = (tmp_path / "content" / "overview" / "index.md").read_text(encoding="utf-8")
    assert "**出典と照合済み（AI）**: 1 / 1 (100%) (claude-opus-5[1m])" in overview
    assert "**人が読んだページ**: 0 / 1 (0%)" in overview
    # Says what was compared, and says what it did not look at. Reading this as
    # "verified" is the over-claim Issue #740 is fixing on the human side.
    assert "照合しているのは出典との一致だけで" in overview
    assert "網羅性" in overview


def test_root_index_reports_the_ai_review_count_single_language(tmp_path):
    """Issue #769 — the AI count reached the per-page banner and the overview but
    not the front page, so "N pages / M read by a person" read as "nothing has
    been done to the other N-M"."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    write_wikicommit_page(tmp_path, "ja", "Person", "suzuki-hanako", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    index = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(index.split("---")[1])
    assert fm["wikicommit_page_count"] == 2
    assert fm["wikicommit_ai_reviewed_count"] == 1


def test_root_index_reports_the_ai_review_count_per_language(tmp_path):
    """Issue #769 — counted per language for the same reason Issue #730 split the
    other two, and the reason holds harder: a translation page carries no record
    at all, so a site-wide figure would be diluted by however many exist."""
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  primary_lang: ja\n  targets: [en]\n", encoding="utf-8"
    )
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    write_wikicommit_page(tmp_path, "en", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    body = (tmp_path / "content" / "index.md").read_text(encoding="utf-8").split("---", 2)[2]
    # The language with a record gets three numbers, in full-coverage-then-sample
    # order; the one without keeps the two-number form.
    assert "- [ja](./ja/)（1 ページ / 出典と照合 1 / 人が読んだ 0）" in body
    assert "- [en](./en/)（1 ページ / 人が読んだ 0）" in body
    assert "照合しているのは出典との一致だけで" in body


def test_root_index_ai_count_covers_the_same_pages_as_the_page_count(tmp_path):
    """Issue #769 — the three site-wide numbers must count one set of pages.

    A page whose path never resolves to <lang>/<Type>/<slug>.md is published and
    stamped with its verdict, and total_pages counts it, but it never reaches
    page_stats. Tallying the AI count there reported "1 of 2 checked" for a wiki
    where both pages carry a standing verdict — the misreading this count exists
    to remove, pointed the other way.
    """
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    unkeyed = tmp_path / ".wikicommit" / "entity" / "ja" / "notes.md"
    unkeyed.write_text(PAGE_WITH_STAMPS, encoding="utf-8")
    for rel in (".wikicommit/entity/ja/Person/yamada-taro.md", ".wikicommit/entity/ja/notes.md"):
        record_review(tmp_path, rel, model="claude-opus-5[1m]", reviewed_at="2026-09-05")

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    # The unkeyed page really is published and really does carry the stamp, so
    # leaving it out of the tally would contradict the page it just wrote.
    published = (tmp_path / "content" / "ja" / "notes.md").read_text(encoding="utf-8")
    assert "ai_review_model:" in published

    index = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(index.split("---")[1])
    assert fm["wikicommit_page_count"] == 2
    assert fm["wikicommit_ai_reviewed_count"] == 2


def test_root_index_omits_the_ai_review_count_when_there_are_no_records(tmp_path):
    """Issue #769 — omitted rather than written as 0. A wiki generated before
    review records existed has none (they are not created retroactively), and
    `checked against sources: 0` would report that as "nothing was checked"."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    index = (tmp_path / "content" / "index.md").read_text(encoding="utf-8")
    assert "wikicommit_ai_reviewed_count" not in index
    assert "出典と照合" not in index


def test_root_index_note_names_the_label_rather_than_pointing_at_a_number(tmp_path):
    """Issue #769 — with a third number on the page, "the count above" no longer
    identifies which one it explains. The per-language note already named its
    label (Issue #730); the banner's and the overview's did not."""
    write_config(tmp_path, primary_lang="en")
    write_wikicommit_page(
        tmp_path, "en", "Person", "yamada-taro",
        PAGE_WITH_STAMPS.replace("lang: ja", "lang: en"),
    )
    record_review(
        tmp_path, ".wikicommit/entity/en/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    overview = (tmp_path / "content" / "overview" / "index.md").read_text(encoding="utf-8")
    assert '"Read by a person" is how many' in overview
    assert "The count above" not in overview


def test_overview_counts_findings_but_the_page_banner_does_not(tmp_path):
    """Per-page a finding count reads as "this page is bad" when it means the
    opposite, so the number is aggregated here and nowhere else."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
        findings=(
            '{"result": "PASS", "issues": [{"round": 1, "type": "MISSING_SOURCE",'
            ' "claim": "c", "instruction": "i"}, {"round": 2, "type": "HALLUCINATION",'
            ' "claim": "d", "instruction": "j"}]}'
        ),
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    overview = (tmp_path / "content" / "overview" / "index.md").read_text(encoding="utf-8")
    assert "**うち指摘を受けて書き直された箇所**: 2" in overview

    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert 'ai_review_model: "claude-opus-5[1m]"' in published
    assert "MISSING_SOURCE" not in published
    assert "findings" not in published


def test_index_pages_are_never_stamped(tmp_path):
    """rebuild_index.py's navigation pages are not model-written; stamping one
    would claim a source check that never happened."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    write_wikicommit_page(
        tmp_path, "ja", "Person", "index",
        "---\ntitle: Person\nlang: ja\ntype: \"schema:Person\"\nreview_status: reviewed\n---\n\n"
        "- [[Person/yamada-taro]]\n",
    )
    # A record for the index page exists but must be ignored regardless.
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/index.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    published_index = (tmp_path / "content" / "ja" / "Person" / "index.md").read_text(encoding="utf-8")
    assert "ai_review" not in published_index


def test_inject_frontmatter_lines_leaves_a_page_without_frontmatter_alone(tmp_path):
    """A malformed page is validate_frontmatter.py's to report. A publish step
    inventing a frontmatter block for it would be a larger change than the
    annotation is worth."""
    inject = _convert_wikilinks.inject_frontmatter_lines
    assert inject("Body only.\n", ["ai_review_at: x"]) == "Body only.\n"
    assert inject("---\ntitle: t\n", ["ai_review_at: x"]) == "---\ntitle: t\n"
    assert inject("---\ntitle: t\n---\n\nBody.\n", []) == "---\ntitle: t\n---\n\nBody.\n"
    assert (
        inject("---\ntitle: t\n---\n\nBody.\n", ["ai_review_at: x"])
        == "---\ntitle: t\nai_review_at: x\n---\n\nBody.\n"
    )


def test_a_newline_in_a_record_value_cannot_inject_frontmatter(tmp_path):
    """_yaml_quote() escapes quotes and backslashes but cannot escape a line
    break, so a value carrying one would end the frontmatter line and write what
    followed as further keys — on every page that record covers."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5", reviewed_at="2026-09-05",
    )
    # Rewrite the record's model with an embedded newline, the way a malformed
    # or hostile writer could.
    record = next((tmp_path / ".wikicommit" / "review").rglob("*.md"))
    record.write_text(
        record.read_text(encoding="utf-8").replace(
            "model: claude-opus-5", 'model: "bad\\nreview_status: reviewed"'
        ),
        encoding="utf-8",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "ai_review_model" not in published
    # The page keeps the review_status it actually has.
    assert "review_status: pending" in published
    assert "review_status: reviewed" not in published


def test_a_failed_verdict_is_not_published_as_a_passing_one(tmp_path):
    """`wikicommit-review` records `--result fail` when its fact-check found
    something, against a page that stays on disk. Standing is not the same as
    passing: publishing that record would put "checked against sources" on the
    one page whose latest check failed, and count its unfixed findings among
    those "raised and fixed before publishing"."""
    write_config(tmp_path, primary_lang="ja")
    write_wikicommit_page(tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_STAMPS)
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05", result="fail",
    )

    result = run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path)
    assert result.returncode == 0

    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "ai_review_model" not in published
    assert "ai_review_at" not in published
    overview = (tmp_path / "content" / "overview" / "index.md").read_text(encoding="utf-8")
    assert "出典と照合済み（AI）" not in overview


PAGE_WITH_SOURCE = (
    "---\n"
    'title: "山田太郎"\n'
    "lang: ja\n"
    'type: "schema:Person"\n'
    "review_status: pending\n"
    "sources:\n"
    "  - type: url\n"
    "    url: https://example.com/a\n"
    "    hash: sha256:{digest}\n"
    "---\n"
    "\n"
    "本文。\n"
)


def test_verdict_is_withheld_when_a_source_it_rested_on_changed(tmp_path):
    """The other half of staleness. `sources` is one of the bookkeeping fields
    the content hash ignores, so re-ingesting a source leaves the page's text —
    and therefore its hash — untouched while the evidence the reviewer saw has
    moved. Withholding here is what keeps the banner from contradicting
    `/wikicommit-status`, which reports the same record as STALE_REVIEW."""
    write_config(tmp_path, primary_lang="ja")
    page = write_wikicommit_page(
        tmp_path, "ja", "Person", "yamada-taro", PAGE_WITH_SOURCE.format(digest="a" * 64)
    )
    record_review(
        tmp_path, ".wikicommit/entity/ja/Person/yamada-taro.md",
        model="claude-opus-5[1m]", reviewed_at="2026-09-05",
    )

    # Sanity: unchanged, the verdict publishes.
    assert run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path).returncode == 0
    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "ai_review_at" in published

    # The source document changed under it; the page's own prose did not.
    page.write_text(PAGE_WITH_SOURCE.format(digest="b" * 64), encoding="utf-8")
    assert run(["--source", ".wikicommit/entity/", "--output", "content/"], cwd=tmp_path).returncode == 0

    published = (tmp_path / "content" / "ja" / "Person" / "yamada-taro.md").read_text(encoding="utf-8")
    assert "ai_review_model" not in published
    assert "ai_review_at" not in published
