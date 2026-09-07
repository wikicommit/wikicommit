"""Tests for .claude/skills/wikicommit-init/scripts/init.py (#88)"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts" / "init.py"


def _load_init_module():
    """Import init.py as a module so its tables can be asserted directly.

    Same pattern as tests/test_add_source.py; loaded lazily rather than at import
    time because every other test in this file drives the script as a subprocess.
    """
    import importlib.util

    # init.py imports its sibling _root_outputs by bare name, which only resolves
    # when the script's own directory is on sys.path (as it is when run directly).
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("wikicommit_init", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return module


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


# ── Directory generation (no --quartz) ────────────────────────────────────────

def test_main_generates_wikicommit_structure(tmp_path):
    result = run([], cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".wikicommit" / "config.yml").is_file()
    assert (tmp_path / ".wikicommit" / "schema").is_dir()
    assert any((tmp_path / ".wikicommit" / "schema").iterdir())
    assert (tmp_path / ".wikicommit" / "scripts").is_dir()
    assert any((tmp_path / ".wikicommit" / "scripts").iterdir())
    assert (tmp_path / ".wikicommit" / "source" / "path").is_dir()
    assert (tmp_path / ".wikicommit" / "source" / "url").is_dir()
    assert (tmp_path / ".wikicommit" / "entity" / "assets").is_dir()
    assert (tmp_path / ".wikicommit" / "entity" / "en").is_dir()  # default --primary-lang
    # .wikicommit/exports/ is no longer generated (Issue #283 — the exports/ concept
    # was abolished when wikicommit-synthesize started writing directly to wiki/)
    assert not (tmp_path / ".wikicommit" / "exports").exists()


# ── --theme option (#160) ───────────────────────────────────────────────────

def test_theme_defaults_to_empty_string(tmp_path):
    result = run([], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / ".wikicommit" / "config.yml").read_text(encoding="utf-8")
    assert 'theme: ""' in config


def test_theme_is_written_to_config(tmp_path):
    result = run(["--theme", "Internal engineering knowledge base"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / ".wikicommit" / "config.yml").read_text(encoding="utf-8")
    assert 'theme: "Internal engineering knowledge base"' in config


def test_theme_with_quotes_and_backslashes_is_escaped_and_round_trips(tmp_path):
    import yaml

    raw_theme = 'A "quoted" theme with a \\backslash'
    result = run(["--theme", raw_theme], cwd=tmp_path)

    assert result.returncode == 0
    config_path = tmp_path / ".wikicommit" / "config.yml"
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert parsed["theme"] == raw_theme


def test_theme_with_embedded_newline_round_trips(tmp_path):
    import yaml

    raw_theme = "First line\nSecond line"
    result = run(["--theme", raw_theme], cwd=tmp_path)

    assert result.returncode == 0
    config_path = tmp_path / ".wikicommit" / "config.yml"
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert parsed["theme"] == raw_theme


def test_theme_with_control_character_round_trips(tmp_path):
    import yaml

    raw_theme = "before\x07after"
    result = run(["--theme", raw_theme], cwd=tmp_path)

    assert result.returncode == 0
    config_path = tmp_path / ".wikicommit" / "config.yml"
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert parsed["theme"] == raw_theme


def test_theme_starting_with_dash_works_with_equals_form(tmp_path):
    # SKILL.md instructs callers to always use the `--theme=<text>` (`=`-joined) form;
    # a space-separated `--theme <text>` breaks argparse when <text> starts with `-`.
    result = run(["--theme=--looks-like-a-flag"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / ".wikicommit" / "config.yml").read_text(encoding="utf-8")
    assert 'theme: "--looks-like-a-flag"' in config


# ── --update-theme flag (#374) ──────────────────────────────────────────────

def test_update_theme_rewrites_existing_blank_theme(tmp_path):
    run([], cwd=tmp_path)  # first init: theme defaults to ""

    result = run(["--update-theme", "Internal engineering knowledge base"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / ".wikicommit" / "config.yml").read_text(encoding="utf-8")
    assert 'theme: "Internal engineering knowledge base"' in config


def test_update_theme_overwrites_existing_non_blank_theme(tmp_path):
    run(["--theme", "Old theme"], cwd=tmp_path)

    result = run(["--update-theme", "New theme"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / ".wikicommit" / "config.yml").read_text(encoding="utf-8")
    assert 'theme: "New theme"' in config
    assert "Old theme" not in config


def test_update_theme_only_touches_theme_line(tmp_path):
    run(["--primary-lang", "ja", "--targets", "en", "zh"], cwd=tmp_path)
    before = (tmp_path / ".wikicommit" / "config.yml").read_text(encoding="utf-8")

    result = run(["--update-theme", "New theme"], cwd=tmp_path)

    assert result.returncode == 0
    after = (tmp_path / ".wikicommit" / "config.yml").read_text(encoding="utf-8")
    before_without_theme = "\n".join(
        line for line in before.splitlines() if not line.startswith("theme:")
    )
    after_without_theme = "\n".join(
        line for line in after.splitlines() if not line.startswith("theme:")
    )
    assert before_without_theme == after_without_theme


def test_update_theme_round_trips_special_characters(tmp_path):
    import yaml

    run([], cwd=tmp_path)
    raw_theme = 'A "quoted" theme with a \\backslash and \nnewline'

    result = run(["--update-theme", raw_theme], cwd=tmp_path)

    assert result.returncode == 0
    config_path = tmp_path / ".wikicommit" / "config.yml"
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert parsed["theme"] == raw_theme


def test_update_theme_fails_when_config_does_not_exist(tmp_path):
    result = run(["--update-theme", "New theme"], cwd=tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stderr
    assert not (tmp_path / ".wikicommit").exists()


def test_update_theme_inserts_field_when_missing_from_legacy_config(tmp_path):
    config_dir = tmp_path / ".wikicommit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yml").write_text(
        "translation:\n  targets: []\n  primary_lang: en\n", encoding="utf-8"
    )

    result = run(["--update-theme", "Retrofitted theme"], cwd=tmp_path)

    assert result.returncode == 0
    config = (config_dir / "config.yml").read_text(encoding="utf-8")
    assert 'theme: "Retrofitted theme"' in config
    assert "primary_lang: en" in config  # untouched


def test_main_without_quartz_does_not_generate_quartz_files(tmp_path):
    run([], cwd=tmp_path)

    assert not (tmp_path / "quartz.config.yaml").exists()
    assert not (tmp_path / "package.json").exists()
    assert not (tmp_path / ".github" / "workflows" / "deploy.yml").exists()
    assert not (tmp_path / "quartz-plugins").exists()
    assert not (tmp_path / ".github" / "ISSUE_TEMPLATE" / "report.md").exists()


# ── review-issue-close-sync.yml (#313) ──────────────────────────────────────

def test_review_issue_close_sync_workflow_generated_without_quartz(tmp_path):
    """Unlike deploy.yml (Quartz-only), this workflow backs the review
    pipeline and must be generated regardless of the --quartz choice."""
    result = run([], cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml").is_file()


def test_review_issue_close_sync_workflow_records_the_reviewer(tmp_path):
    """Issue #663: the published banner names the reviewer by reading the page's
    own `reviewed_by` frontmatter, and this workflow is the only thing that ever
    writes it. Nothing else in the pipeline notices if that step disappears — the
    page still merges as `reviewed`, the banner just silently stops naming anyone
    — so the step's presence and its position after the closer is resolved are
    pinned here (same kind of guard test_workflow_template_dispatch.py provides
    for the deploy.yml dispatch)."""
    import yaml

    run([], cwd=tmp_path)
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    steps = yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"]["sync"]["steps"]

    names = [step.get("name") for step in steps]
    ids = [step.get("id") for step in steps]
    assert "Record the reviewer on the page" in names, (
        "review-issue-close-sync.yml no longer records the reviewer, so every page it "
        "marks as reviewed will publish without a reviewer name (Issue #663)."
    )

    index = names.index("Record the reviewer on the page")
    # closed_by is resolved by the `closer` step; writing before it would stamp an
    # empty login, which validate_frontmatter.py rejects in the quality gate below.
    assert index > ids.index("closer")
    # Must land in the same commit as review_status, i.e. before `git add`.
    assert index < ids.index("pr")

    step = steps[index]
    assert "set_frontmatter_field.py" in step["run"]
    assert "reviewed_by=" in step["run"]
    assert step["env"]["REVIEWER_LOGIN"] == "${{ steps.closer.outputs.login }}"


def test_review_issue_close_sync_workflow_is_refreshed(tmp_path):
    """Reversed by Issue #712. This workflow backs WikiCommit's own review pipeline and
    the user never authors it, so leaving it untouched meant every repository kept
    running whatever version it was initialized with — which is exactly what all three
    pilots were found doing, with no way to notice. A repository that wants CI of its
    own adds it in another file; this name belongs to WikiCommit."""
    workflow = tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("SENTINEL\n", encoding="utf-8")

    run([], cwd=tmp_path)

    assert workflow.read_text(encoding="utf-8") != "SENTINEL\n"
    assert "issues" in workflow.read_text(encoding="utf-8")


# ── --quartz option ────────────────────────────────────────────────────────────

def test_main_with_quartz_generates_publishing_setup(tmp_path):
    result = run(["--quartz"], cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / "quartz.config.yaml").is_file()
    assert (tmp_path / "package.json").is_file()
    assert (tmp_path / "prebuild-symlinks.cjs").is_file()
    assert (tmp_path / "repair-plugin-builds.cjs").is_file()
    assert (tmp_path / "install-local-plugins.cjs").is_file()
    assert (tmp_path / "quartz-plugins").is_dir()
    assert any((tmp_path / "quartz-plugins").iterdir())
    assert (tmp_path / ".github" / "ISSUE_TEMPLATE" / "report.md").is_file()


# ── --quartz-pages option (#335) ────────────────────────────────────────────
# --quartz alone sets up local build/preview only; --quartz-pages additionally
# opts the repository into automatic GitHub Pages publishing (deploy.yml).

def test_quartz_alone_does_not_generate_deploy_workflow(tmp_path):
    result = run(["--quartz"], cwd=tmp_path)

    assert result.returncode == 0
    assert not (tmp_path / ".github" / "workflows" / "deploy.yml").exists()


def test_quartz_pages_generates_deploy_workflow(tmp_path):
    result = run(["--quartz", "--quartz-pages"], cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".github" / "workflows" / "deploy.yml").is_file()


def test_quartz_pages_without_quartz_is_rejected(tmp_path):
    result = run(["--quartz-pages"], cwd=tmp_path)

    assert result.returncode == 1
    assert "--quartz-pages requires --quartz" in result.stderr
    assert not (tmp_path / ".github" / "workflows" / "deploy.yml").exists()
    assert not (tmp_path / "quartz.config.yaml").exists()


def test_existing_deploy_workflow_is_refreshed(tmp_path):
    """Reversed by Issue #712, for the same reason as the review workflow above: this is
    WikiCommit's Quartz build, not the repository's own CI."""
    deploy = tmp_path / ".github" / "workflows" / "deploy.yml"
    deploy.parent.mkdir(parents=True)
    deploy.write_text("SENTINEL\n", encoding="utf-8")

    result = run(["--quartz", "--quartz-pages"], cwd=tmp_path)

    assert result.returncode == 0
    assert deploy.read_text(encoding="utf-8") != "SENTINEL\n"


# ── .github/ISSUE_TEMPLATE/report.md (#339) ─────────────────────────────────

def test_report_issue_template_not_overwritten(tmp_path):
    """wikicommit-banner's report link (#245/#313) points at ?template=report.md;
    #339 fixes the file never having been distributed. Like deploy.yml, an
    existing repo's own template must never be clobbered on re-init."""
    template = tmp_path / ".github" / "ISSUE_TEMPLATE" / "report.md"
    template.parent.mkdir(parents=True)
    template.write_text("SENTINEL\n", encoding="utf-8")

    run(["--quartz"], cwd=tmp_path)

    assert template.read_text(encoding="utf-8") == "SENTINEL\n"


def test_report_issue_template_has_distinct_label(tmp_path):
    """The label must differ from wikicommit-review (Issue #313's tracking-Issue
    label) so reader-reported issues and review-tracking Issues never collide."""
    run(["--quartz"], cwd=tmp_path)

    template = (tmp_path / ".github" / "ISSUE_TEMPLATE" / "report.md").read_text(encoding="utf-8")
    assert "labels: wikicommit-report" in template
    assert "wikicommit-review" not in template.split("---", 2)[1]


def test_quartz_page_title_defaults_to_repo_dir_name(tmp_path):
    """#317 — pageTitle previously stayed the literal template value "WikiCommit
    Wiki" for every generated wiki since quartz.config.yaml was plain-copied
    without any placeholder substitution."""
    result = run(["--quartz"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / "quartz.config.yaml").read_text(encoding="utf-8")
    assert f'pageTitle: "{tmp_path.name}"' in config
    assert "WikiCommit Wiki" not in config


def test_quartz_page_title_suffix_defaults_to_the_same_name(tmp_path):
    """#679 — Quartz's Head.tsx builds <title> from the page's own frontmatter
    title plus pageTitleSuffix and nothing else, so an empty suffix left the
    site's name off every tab, og:title and twitter:title. pageTitle does not
    reach any of the three, which is why both fields carry the same name."""
    import yaml

    result = run(["--quartz"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / "quartz.config.yaml").read_text(encoding="utf-8")
    # Assert the parsed value rather than the serialization. The leading space is
    # what keeps the tab from reading "Wiki- my-wiki", and it is the parsed value
    # that reaches Quartz: matching the double-quoted text instead would still
    # pass if a future change emitted a single-quoted scalar, and a leftover
    # `{PAGE_TITLE_SUFFIX}` is valid YAML (a one-key mapping), so only comparing
    # the value catches that too.
    assert yaml.safe_load(config)["configuration"]["pageTitleSuffix"] == f" - {tmp_path.name}"


def test_quartz_config_leaves_no_unsubstituted_placeholder(tmp_path):
    """Every `{...}` in the template is a substitution site; one left behind is
    a config Quartz cannot read, and the two title fields are now two of them.

    Matching the placeholder *shape* rather than a hardcoded list of names is what
    makes this a guard instead of a third copy of the assertions above: a list has
    to be edited alongside every new placeholder, and the one that is forgotten is
    exactly the one this test exists to catch (the second-list drift of Issue
    #556/#642). The empty mappings the config legitimately contains (`links: {}`,
    `options: {}`) do not match, since the pattern requires a name. Both footer
    branches are exercised because `{REPO_URL}` is resolved by substitution with a
    URL and by deletion without one."""
    for extra_args in ([], ["--repo-url=https://github.com/acme/example-wiki"]):
        target = tmp_path / f"repo{len(extra_args)}"
        target.mkdir()
        result = run(["--quartz", *extra_args], cwd=target)

        assert result.returncode == 0
        config = (target / "quartz.config.yaml").read_text(encoding="utf-8")
        assert re.findall(r"\{[A-Z][A-Z0-9_]*\}", config) == []


def test_quartz_locale_follows_primary_lang(tmp_path):
    """#771 — the template carried a hard-coded `locale: en-US` that init never
    substituted, so a Japanese wiki published its body text and banner in Japanese
    while the sidebar, search and graph stayed English. The ja-JP translations
    existed in all three community plugins; they were simply never reached."""
    import yaml

    result = run(["--quartz", "--primary-lang=ja"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / "quartz.config.yaml").read_text(encoding="utf-8")
    assert yaml.safe_load(config)["configuration"]["locale"] == "ja-JP"


def test_quartz_locale_falls_back_to_en_us_for_an_unmapped_language(tmp_path):
    """#771 — a language none of the chrome plugins translate stays en-US rather
    than getting an invented tag. The chrome would be English either way; an
    invented tag would only make the config claim otherwise."""
    import yaml

    # Swahili: a valid ISO 639-1 code with no locale in explorer/graph/search.
    result = run(["--quartz", "--primary-lang=sw"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / "quartz.config.yaml").read_text(encoding="utf-8")
    assert yaml.safe_load(config)["configuration"]["locale"] == "en-US"


def test_every_mapped_locale_exists_in_all_three_chrome_plugins():
    """#771 — the mapping's values are only useful if the locales behind them are
    actually reachable: the file has to exist, be registered in the plugin's
    `locales` record, and survive into the built dist/ that Quartz loads. A locale
    dropped, unregistered or left out of a stale build has to fail here, because at
    build time it degrades silently to English chrome — the exact failure this Issue
    fixed, reintroduced from the other end."""
    init = _load_init_module()
    plugins_dir = (
        Path(__file__).parent.parent
        / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "quartz-plugins"
    )
    chrome_plugins = ["wikicommit-explorer", "wikicommit-graph", "wikicommit-search"]

    missing = []
    for lang, locale in sorted(init.QUARTZ_LOCALE_BY_PRIMARY_LANG.items()):
        for plugin in chrome_plugins:
            plugin_dir = plugins_dir / plugin
            # Three separate things have to hold, and only the first is a file
            # existing. `i18n()` resolves out of the `locales` record in
            # src/i18n/index.ts, and what Quartz actually loads is the built
            # dist/index.js (package.json's `main`/`exports` point there, and
            # quartz.config.yaml references the plugin directory). A locale file
            # left unregistered, or a dist/ that has gone stale relative to src/,
            # falls back to enUS at build time without any error — the same silent
            # English chrome this Issue removed.
            locale_file = plugin_dir / "src" / "i18n" / "locales" / f"{locale}.ts"
            if not locale_file.is_file():
                missing.append(f"{lang} -> {locale} ({plugin}: no locale file)")
                continue
            index_ts = (plugin_dir / "src" / "i18n" / "index.ts").read_text(encoding="utf-8")
            if f'"{locale}"' not in index_ts:
                missing.append(f"{lang} -> {locale} ({plugin}: not in src/i18n/index.ts)")
            built = (plugin_dir / "dist" / "index.js").read_text(encoding="utf-8")
            if f'"{locale}"' not in built:
                missing.append(f"{lang} -> {locale} ({plugin}: not in dist/index.js)")

    assert not missing, (
        "QUARTZ_LOCALE_BY_PRIMARY_LANG names locales that do not resolve: "
        + ", ".join(missing)
    )
    assert init.DEFAULT_QUARTZ_LOCALE == "en-US"


def _footer_links(config_text: str) -> dict:
    """Return the footer plugin's `options.links` mapping from a generated config."""
    import yaml

    parsed = yaml.safe_load(config_text)
    footer = next(p for p in parsed["plugins"] if str(p.get("source", "")).endswith("/footer"))
    return footer["options"]["links"]


def test_quartz_footer_github_link_points_at_this_repository(tmp_path):
    """#557 — the footer shipped with Quartz's own repository as its GitHub link, so
    every generated wiki's most prominent link pointed at the upstream SSG instead of
    at the wiki being read (the entry point for the read → open an Issue → close the
    review-tracking Issue path)."""
    result = run(["--quartz", "--repo-url=https://github.com/acme/example-wiki"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / "quartz.config.yaml").read_text(encoding="utf-8")
    assert _footer_links(config) == {"GitHub": "https://github.com/acme/example-wiki"}
    assert "no --repo-url resolved" not in result.stdout
    # The Quartz Discord invite that shipped alongside the upstream GitHub link has no
    # counterpart on the WikiCommit side, so it is dropped outright rather than
    # retargeted. (jackyzha0/quartz still appears once at the top of the file, in the
    # `git submodule add` instruction — that one is correct and stays.)
    assert "discord.gg" not in config
    assert "{REPO_URL}" not in config


def test_quartz_footer_drops_github_link_without_repo_url(tmp_path):
    """#557 — with no GitHub remote the entry is dropped, not left pointing at
    upstream Quartz and not left as a literal placeholder. `links: {}` is what the
    footer plugin already treats as "no links", so the footer still renders."""
    result = run(["--quartz"], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / "quartz.config.yaml").read_text(encoding="utf-8")
    assert _footer_links(config) == {}
    assert "{REPO_URL}" not in config
    # SKILL.md requires the agent to tell the user the entry was dropped, so the drop
    # must not be silent — the flag is passed as a `$(gh ...)` substitution, whose
    # failure is otherwise only visible as gh's own stderr.
    assert "NOTE: quartz.config.yaml: no --repo-url resolved" in result.stdout


def test_quartz_footer_treats_empty_repo_url_as_absent(tmp_path):
    """#557 — SKILL.md passes `--repo-url="$(gh repo view --json url -q .url)"`, which
    expands to the empty string when `gh` fails (no GitHub remote). That must behave
    exactly like omitting the flag rather than writing `GitHub: ""`."""
    result = run(["--quartz", "--repo-url="], cwd=tmp_path)

    assert result.returncode == 0
    config = (tmp_path / "quartz.config.yaml").read_text(encoding="utf-8")
    assert _footer_links(config) == {}
    assert "{REPO_URL}" not in config
    assert "NOTE: quartz.config.yaml: no --repo-url resolved" in result.stdout


def test_repo_url_without_quartz_generates_no_quartz_config(tmp_path):
    """#557 — --repo-url only feeds quartz.config.yaml, which --quartz alone creates.
    Passing it on its own must be a harmless no-op, not an error."""
    result = run(["--repo-url=https://github.com/acme/example-wiki"], cwd=tmp_path)

    assert result.returncode == 0
    assert not (tmp_path / "quartz.config.yaml").exists()


def test_main_without_quartz_does_not_generate_prebuild_symlinks_script(tmp_path):
    run([], cwd=tmp_path)

    assert not (tmp_path / "prebuild-symlinks.cjs").exists()
    assert not (tmp_path / "repair-plugin-builds.cjs").exists()
    assert not (tmp_path / "install-local-plugins.cjs").exists()


def test_main_with_quartz_excludes_test_artifacts_and_node_modules(tmp_path):
    """#93 added vitest suites and #94 added eslint config to the quartz-plugins
    templates; a generated user repo must not receive dev-only test/lint
    scaffolding or a stray node_modules/ (present if `npm ci` was ever run
    inside the source template directory)."""
    templates_src = SCRIPT.parent / "templates" / "quartz-plugins" / "wikicommit-banner"
    stray_node_modules = templates_src / "node_modules" / "some-dep" / "package.json"
    stray_node_modules.parent.mkdir(parents=True, exist_ok=True)
    stray_node_modules.write_text("{}", encoding="utf-8")
    try:
        result = run(["--quartz"], cwd=tmp_path)
        assert result.returncode == 0

        quartz_plugins = tmp_path / "quartz-plugins"
        copied_names = {p.name for p in quartz_plugins.rglob("*")}
        assert not any(name.endswith((".test.ts", ".test.tsx")) for name in copied_names)
        assert "vitest.config.ts" not in copied_names
        assert "eslint.config.js" not in copied_names
        assert "node_modules" not in copied_names
        assert (quartz_plugins / "wikicommit-banner" / "dist" / "index.js").is_file()
    finally:
        shutil.rmtree(templates_src / "node_modules")


# ── source-policy.md (Issue #564) ─────────────────────────────────────────────

def test_source_policy_is_written(tmp_path):
    import yaml

    result = run([], cwd=tmp_path)
    assert result.returncode == 0

    policy = tmp_path / ".wikicommit" / "source-policy.md"
    assert policy.is_file()
    text = policy.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    # `rejected` ships with no value, not as `[]`: /wikicommit-collect appends block
    # entries under it and the two YAML styles cannot be mixed (Issue #564).
    assert frontmatter["wikicommit"] == {"exclude_domains": [], "index_only": [], "rejected": None}
    # The body ships as a comment so an unedited file reads as "no prose policy".
    body = text.split("---", 2)[2].strip()
    assert body.startswith("<!--") and body.endswith("-->")


def test_existing_source_policy_never_overwritten(tmp_path):
    """The prose is written by hand and the Skills only append to `rejected:`."""
    policy = tmp_path / ".wikicommit" / "source-policy.md"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text("SENTINEL\n", encoding="utf-8")

    for extra_args in ([], ["--no-overwrite"]):
        result = run(extra_args, cwd=tmp_path)
        assert result.returncode == 0
        assert policy.read_text(encoding="utf-8") == "SENTINEL\n"


# ── entity-policy.md (Issue #667) ─────────────────────────────────────────────

def test_entity_policy_is_written(tmp_path):
    import yaml

    result = run([], cwd=tmp_path)
    assert result.returncode == 0

    policy = tmp_path / ".wikicommit" / "entity-policy.md"
    assert policy.is_file()
    text = policy.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    # One key only, shipped inert: a wiki that never edits this file behaves exactly
    # as it did before the file existed (Issue #667). Adding a second switch here is
    # a deliberate no — an exception belongs in the prose, not in a new key.
    assert frontmatter["wikicommit"] == {"exclude_living_persons": False}
    # The body ships as a comment so an unedited file reads as "no prose policy",
    # the same contract source-policy.md has.
    body = text.split("---", 2)[2].strip()
    assert body.startswith("<!--") and body.endswith("-->")


def test_existing_entity_policy_never_overwritten(tmp_path):
    """Hand-written prose: a re-run must not touch it, with or without --no-overwrite."""
    policy = tmp_path / ".wikicommit" / "entity-policy.md"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text("SENTINEL\n", encoding="utf-8")

    for extra_args in ([], ["--no-overwrite"]):
        result = run(extra_args, cwd=tmp_path)
        assert result.returncode == 0
        assert policy.read_text(encoding="utf-8") == "SENTINEL\n"


# ── Root-level existing files are always skipped ──────────────────────────────

def test_existing_root_file_never_overwritten_without_no_overwrite(tmp_path):
    lychee = tmp_path / ".lychee.toml"
    lychee.write_text("SENTINEL\n", encoding="utf-8")

    result = run([], cwd=tmp_path)

    assert result.returncode == 0
    assert lychee.read_text(encoding="utf-8") == "SENTINEL\n"
    assert "SKIPPED: .lychee.toml (already exists)" in result.stdout


def test_existing_root_file_never_overwritten_with_no_overwrite(tmp_path):
    lychee = tmp_path / ".lychee.toml"
    lychee.write_text("SENTINEL\n", encoding="utf-8")

    result = run(["--no-overwrite"], cwd=tmp_path)

    assert result.returncode == 0
    assert lychee.read_text(encoding="utf-8") == "SENTINEL\n"
    assert "SKIPPED: .lychee.toml (already exists)" in result.stdout


def test_existing_quartz_root_file_never_overwritten(tmp_path):
    quartz_config = tmp_path / "quartz.config.yaml"
    quartz_config.write_text("SENTINEL\n", encoding="utf-8")

    result = run(["--quartz"], cwd=tmp_path)

    assert result.returncode == 0
    assert quartz_config.read_text(encoding="utf-8") == "SENTINEL\n"
    assert "SKIPPED: quartz.config.yaml (already exists)" in result.stdout


# ── --no-overwrite for non-root files ──────────────────────────────────────────

def test_no_overwrite_skips_existing_non_root_file(tmp_path):
    schema_dir = tmp_path / ".wikicommit" / "schema"
    schema_dir.mkdir(parents=True)
    person_schema = schema_dir / "Person.md"
    person_schema.write_text("SENTINEL\n", encoding="utf-8")

    result = run(["--no-overwrite"], cwd=tmp_path)

    assert result.returncode == 0
    assert person_schema.read_text(encoding="utf-8") == "SENTINEL\n"
    # The reason changed with Issue #712 — schema/ is now protected by its own update
    # policy rather than by this flag — but the protection itself is unchanged.
    assert "SKIPPED: .wikicommit/schema/Person.md (already exists)" in result.stdout


def test_schema_is_protected_even_without_no_overwrite(tmp_path):
    """Reversed by Issue #712, and the reversal is the point. `.wikicommit/schema/` is
    the one tree humans are meant to edit directly, yet it carried no copy flag at all,
    so --no-overwrite was the single thing standing between a re-init and every
    hand-edited type template. The pilot update procedure had to warn in bold never to
    drop that flag; the update policy now makes the warning unnecessary."""
    schema_dir = tmp_path / ".wikicommit" / "schema"
    schema_dir.mkdir(parents=True)
    person_schema = schema_dir / "Person.md"
    person_schema.write_text("SENTINEL\n", encoding="utf-8")

    result = run([], cwd=tmp_path)

    assert result.returncode == 0
    assert person_schema.read_text(encoding="utf-8") == "SENTINEL\n"


# ── .wikicommit/scripts/ is refreshed even under --no-overwrite (Issue #647) ──

def _template_version() -> str:
    """The version string templates/scripts/_version.py currently ships."""
    version_py = (
        SCRIPT.parent / "templates" / "scripts" / "_version.py"
    ).read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', version_py, re.MULTILINE)
    assert match, "VERSION not found in templates/scripts/_version.py"
    return match.group(1)


def test_no_overwrite_still_refreshes_version_py(tmp_path):
    """A re-init picks up the newly installed Skills' version.

    Without this, `generated_with` / `translated_with` stamp pages built under
    the NEW Skills with the OLD version — actively wrong, and wrong in exactly
    the way that defeats the field's only use (Issue #647).
    """
    run([], cwd=tmp_path)
    version_py = tmp_path / ".wikicommit" / "scripts" / "_version.py"
    version_py.write_text('VERSION = "0.0.1-STALE"\n', encoding="utf-8")

    result = run(["--no-overwrite"], cwd=tmp_path)

    assert result.returncode == 0
    assert f'VERSION = "{_template_version()}"' in version_py.read_text(encoding="utf-8")
    assert "CREATED: .wikicommit/scripts/_version.py" in result.stdout


def test_no_overwrite_refreshes_whole_scripts_tree(tmp_path):
    """The whole tree, not just _version.py — a version claiming to be new
    while the scripts beside it stayed old is its own inconsistency."""
    run([], cwd=tmp_path)
    other_script = tmp_path / ".wikicommit" / "scripts" / "check_orphans.py"
    assert other_script.is_file()
    other_script.write_text("SENTINEL\n", encoding="utf-8")

    result = run(["--no-overwrite"], cwd=tmp_path)

    assert result.returncode == 0
    assert other_script.read_text(encoding="utf-8") != "SENTINEL\n"


def test_no_overwrite_keeps_wikicommit_version_in_config(tmp_path):
    """config.yml records the version the repository was initialized at and
    must NOT move — the opposite of what generated_with needs (Issue #577)."""
    run([], cwd=tmp_path)
    config = tmp_path / ".wikicommit" / "config.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            f'wikicommit_version: "{_template_version()}"',
            'wikicommit_version: "0.0.1-INITIAL"',
        ),
        encoding="utf-8",
    )

    result = run(["--no-overwrite"], cwd=tmp_path)

    assert result.returncode == 0
    assert 'wikicommit_version: "0.0.1-INITIAL"' in config.read_text(encoding="utf-8")
    # As with schema/ above, Issue #712 moved the protection from this flag to the
    # file's own update policy, so the skip reason changed while the guarantee did not.
    assert "SKIPPED: .wikicommit/config.yml (already exists)" in result.stdout


def test_scripts_symlinked_to_the_templates_is_a_no_op_not_an_error(tmp_path):
    """A destination that already IS the source must be skipped, not copied.

    This repository symlinks `.wikicommit/scripts` into `templates/scripts`
    so dogfooding cannot drift from the distributed copy
    (tests/test_template_mirror_sync.py). Refreshing scripts/ under
    --no-overwrite (Issue #647) walks straight into shutil.SameFileError there,
    which main() turns into an ERROR that aborts before any root-level output
    (.gitignore, .lychee.toml, review-issue-close-sync.yml) is written.
    """
    templates_scripts = SCRIPT.parent / "templates" / "scripts"
    (tmp_path / ".wikicommit").mkdir()
    (tmp_path / ".wikicommit" / "scripts").symlink_to(templates_scripts)

    result = run(["--no-overwrite"], cwd=tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "are the same file" not in result.stderr
    assert "SKIPPED: .wikicommit/scripts/_version.py (already the same file as the template)" in result.stdout
    # The run got past scripts/ and still produced the root-level outputs.
    assert (tmp_path / ".gitignore").is_file()
    assert (tmp_path / ".github" / "workflows" / "review-issue-close-sync.yml").is_file()


def test_no_overwrite_still_protects_user_owned_files(tmp_path):
    """Refreshing scripts/ must not widen into the user's own content."""
    run([], cwd=tmp_path)
    person_schema = tmp_path / ".wikicommit" / "schema" / "Person.md"
    person_schema.write_text("SENTINEL\n", encoding="utf-8")

    result = run(["--no-overwrite"], cwd=tmp_path)

    assert result.returncode == 0
    assert person_schema.read_text(encoding="utf-8") == "SENTINEL\n"


# ── Re-init: what gets refreshed and what is protected (Issue #712) ──────────
#
# Ownership used to be restated as a literal flag at each call site, and two paths
# carried no flag at all — so --no-overwrite was the only thing standing between a
# re-init and the user's theme, targets and hand-edited type templates. The update
# column in _root_outputs.py now decides it; these pin both halves of that decision.


def _reinit_over_a_customized_repo(tmp_path, *, no_overwrite: bool) -> Path:
    """Initialize, let the user customize and the payload go stale, then re-init."""
    repo = tmp_path / "repo"
    repo.mkdir()
    assert run(["--quartz", "--quartz-pages", "--primary-lang", "ja"], cwd=repo).returncode == 0

    config = repo / ".wikicommit" / "config.yml"
    config.write_text(
        config.read_text(encoding="utf-8")
        .replace('theme: ""', 'theme: "私の Wiki"')
        .replace("targets: []", "targets: [en]"),
        encoding="utf-8",
    )
    (repo / ".wikicommit" / "schema" / "Person.md").write_text("# hand-edited\n", encoding="utf-8")
    (repo / "quartz.config.yaml").write_text("pageTitle: mine\n", encoding="utf-8")

    for stale in (".github/workflows/review-issue-close-sync.yml",
                  ".github/workflows/deploy.yml",
                  "install-local-plugins.cjs",
                  "prebuild-symlinks.cjs",
                  "repair-plugin-builds.cjs",
                  "quartz-plugins/wikicommit-banner/dist/index.js"):
        (repo / stale).write_text("STALE\n", encoding="utf-8")

    args = ["--quartz", "--quartz-pages", "--primary-lang", "ja"]
    if no_overwrite:
        args.append("--no-overwrite")
    assert run(args, cwd=repo).returncode == 0
    return repo


@pytest.mark.parametrize("no_overwrite", [True, False])
def test_reinit_refreshes_wikicommit_owned_payload(tmp_path, no_overwrite):
    """All three pilots were running the same stale workflow, plugin dist and build
    scripts. None of it is user-editable, so a re-init has to bring it current — and
    --no-overwrite must not hold it back, since that flag exists to protect the user's
    own files, not WikiCommit's."""
    repo = _reinit_over_a_customized_repo(tmp_path, no_overwrite=no_overwrite)
    for refreshed in (".github/workflows/review-issue-close-sync.yml",
                      ".github/workflows/deploy.yml",
                      "install-local-plugins.cjs",
                      "prebuild-symlinks.cjs",
                      "repair-plugin-builds.cjs",
                      "quartz-plugins/wikicommit-banner/dist/index.js"):
        assert "STALE" not in (repo / refreshed).read_text(encoding="utf-8"), refreshed


@pytest.mark.parametrize("no_overwrite", [True, False])
def test_reinit_never_touches_what_the_user_owns(tmp_path, no_overwrite):
    """The no_overwrite=False half is the hole the pilot update procedure warned about
    in bold: config.yml and schema/ carried no copy flag at all, so dropping the flag
    wiped the wiki's theme, reset targets to [] and reverted every hand-edited type
    template. The update column closes it structurally, so the warning is no longer
    load-bearing."""
    repo = _reinit_over_a_customized_repo(tmp_path, no_overwrite=no_overwrite)
    config = (repo / ".wikicommit" / "config.yml").read_text(encoding="utf-8")
    assert "私の Wiki" in config
    assert "targets: [en]" in config
    assert (repo / ".wikicommit" / "schema" / "Person.md").read_text(encoding="utf-8") == "# hand-edited\n"
    assert (repo / "quartz.config.yaml").read_text(encoding="utf-8") == "pageTitle: mine\n"


def test_reinit_leaves_the_users_own_files_alone(tmp_path):
    """Anything outside the distribution is untouched, flags or no flags."""
    repo = tmp_path / "repo"
    repo.mkdir()
    assert run(["--quartz", "--primary-lang", "ja"], cwd=repo).returncode == 0
    page = repo / ".wikicommit" / "entity" / "ja" / "note.md"
    page.write_text("mine\n", encoding="utf-8")
    (repo / ".lychee.toml").write_text("# tuned by hand\n", encoding="utf-8")
    assert run(["--quartz", "--primary-lang", "ja"], cwd=repo).returncode == 0
    assert page.read_text(encoding="utf-8") == "mine\n"
    assert (repo / ".lychee.toml").read_text(encoding="utf-8") == "# tuned by hand\n"


# ── config.yml edits stay at the text level (Issue #713) ─────────────────────
#
# /wikicommit-update restamps wikicommit_version and offers to add settings the template
# has gained. Both go through init.py, and both must edit the file as *text*.
# config.yml ships commented-out worked examples that are the only documentation for the
# fields they describe — site_description (Issue #671) is a key the template deliberately
# does not ship at all, so the comment is the only thing showing its shape. A YAML
# round-trip (safe_load + dump) discards every one of them, which would mean a repository
# silently loses the instructions for the fields it has not filled in yet, on every update.


def _comment_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.lstrip().startswith("#")]


def _init_repo(tmp_path, *extra: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert run(["--primary-lang", "ja", *extra], cwd=repo).returncode == 0
    return repo


def test_update_version_rewrites_only_that_line(tmp_path):
    repo = _init_repo(tmp_path, "--theme", "私の Wiki")
    config = repo / ".wikicommit" / "config.yml"
    before = config.read_text(encoding="utf-8")

    assert run(["--update-version", "9.9.9"], cwd=repo).returncode == 0

    after = config.read_text(encoding="utf-8")
    assert 'wikicommit_version: "9.9.9"' in after
    assert _comment_lines(after) == _comment_lines(before), "コメント記入例が失われています"
    # Every other line is byte-identical.
    changed = [
        (a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b
    ]
    assert len(changed) == 1 and changed[0][1].startswith("wikicommit_version:")


def test_update_version_stamps_a_config_that_never_had_one(tmp_path):
    """A repository initialized before the stamp existed has no such line."""
    repo = _init_repo(tmp_path)
    config = repo / ".wikicommit" / "config.yml"
    stripped = "\n".join(
        ln for ln in config.read_text(encoding="utf-8").splitlines()
        if not ln.startswith("wikicommit_version")
    ) + "\n"
    config.write_text(stripped, encoding="utf-8")

    assert run(["--update-version", "1.2.3"], cwd=repo).returncode == 0

    after = config.read_text(encoding="utf-8")
    assert after.startswith('wikicommit_version: "1.2.3"\n')
    assert _comment_lines(after) == _comment_lines(stripped)
    assert yaml.safe_load(after)["wikicommit_version"] == "1.2.3"


def test_update_version_preserves_a_theme_the_user_set(tmp_path):
    repo = _init_repo(tmp_path, "--theme", "私の Wiki")
    config = repo / ".wikicommit" / "config.yml"
    assert run(["--update-version", "9.9.9"], cwd=repo).returncode == 0
    assert yaml.safe_load(config.read_text(encoding="utf-8"))["theme"] == "私の Wiki"


def test_update_version_fails_when_config_does_not_exist(tmp_path):
    result = run(["--update-version", "1.0.0"], cwd=tmp_path)
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_add_config_keys_carries_the_commented_example_with_the_key(tmp_path):
    """The key without its comment delivers a setting nobody can use."""
    repo = _init_repo(tmp_path)
    config = repo / ".wikicommit" / "config.yml"
    without_theme = re.sub(
        r"(?m)^theme:.*$\n?", "", config.read_text(encoding="utf-8")
    )
    config.write_text(without_theme, encoding="utf-8")

    result = run(["--add-config-keys", "theme"], cwd=repo)

    assert result.returncode == 0
    after = config.read_text(encoding="utf-8")
    assert yaml.safe_load(after)["theme"] == ""
    assert len(_comment_lines(after)) > len(_comment_lines(without_theme)), (
        "キーだけが追加され、その説明であるコメントが運ばれていません"
    )


def test_add_config_keys_substitutes_placeholders_rather_than_copying_them(tmp_path):
    """`theme: {THEME}` is valid YAML and parses as a *mapping*, so copying the template
    block verbatim would leave the wiki's theme as {"THEME": None} instead of a string —
    wrong in a way nothing reports."""
    repo = _init_repo(tmp_path)
    config = repo / ".wikicommit" / "config.yml"
    config.write_text(
        re.sub(r"(?m)^theme:.*$\n?", "", config.read_text(encoding="utf-8")), encoding="utf-8"
    )

    assert run(["--add-config-keys", "theme"], cwd=repo).returncode == 0

    after = config.read_text(encoding="utf-8")
    assert "{THEME}" not in after
    assert isinstance(yaml.safe_load(after)["theme"], str)


def test_add_config_keys_never_overwrites_a_value_already_there(tmp_path):
    repo = _init_repo(tmp_path, "--theme", "私の Wiki")
    config = repo / ".wikicommit" / "config.yml"
    before = config.read_text(encoding="utf-8")

    result = run(["--add-config-keys", "theme", "generate"], cwd=repo)

    assert result.returncode == 0
    assert "SUMMARY: added=0" in result.stdout
    assert config.read_text(encoding="utf-8") == before


def test_add_config_keys_skips_a_key_the_template_only_documents_in_a_comment(tmp_path):
    """site_description ships as a commented example with no key of its own (Issue #671 —
    receptacles are not shipped ahead of their consumers). There is nothing to add."""
    repo = _init_repo(tmp_path)
    config = repo / ".wikicommit" / "config.yml"
    before = config.read_text(encoding="utf-8")

    result = run(["--add-config-keys", "site_description"], cwd=repo)

    assert result.returncode == 0
    assert "SUMMARY: added=0" in result.stdout
    assert config.read_text(encoding="utf-8") == before


def test_add_config_keys_stamps_the_version_without_doubling_its_quotes(tmp_path):
    """`wikicommit_version: "{VERSION}"` is the one template line that already quotes its
    placeholder, so substituting a quoted value produced `""0.1.0""` — invalid YAML that
    took the *whole* config.yml down, not just that key. A repository predating the stamp
    is reported as missing it by check_distribution_freshness.py, which is exactly what
    /wikicommit-update feeds to --add-config-keys."""
    repo = _init_repo(tmp_path, "--theme", "私の Wiki")
    config = repo / ".wikicommit" / "config.yml"
    config.write_text(
        re.sub(r"(?m)^wikicommit_version:.*$\n?", "", config.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    assert run(["--add-config-keys", "wikicommit_version"], cwd=repo).returncode == 0

    parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert isinstance(parsed["wikicommit_version"], str)
    assert '"' not in parsed["wikicommit_version"]
    assert parsed["theme"] == "私の Wiki", "他のキーが道連れで失われています"


def test_add_config_keys_adds_a_repeated_key_only_once(tmp_path):
    """A duplicate YAML key parses silently (last wins) while _update_theme() rewrites the
    first, so the two would disagree with nothing reporting it."""
    repo = _init_repo(tmp_path)
    config = repo / ".wikicommit" / "config.yml"
    config.write_text(
        re.sub(r"(?m)^theme:.*$\n?", "", config.read_text(encoding="utf-8")), encoding="utf-8"
    )

    result = run(["--add-config-keys", "theme", "theme"], cwd=repo)

    assert result.returncode == 0
    assert "SUMMARY: added=1" in result.stdout
    after = config.read_text(encoding="utf-8")
    assert len([ln for ln in after.splitlines() if ln.startswith("theme:")]) == 1


def test_add_config_keys_leaves_the_file_parseable(tmp_path):
    repo = _init_repo(tmp_path)
    config = repo / ".wikicommit" / "config.yml"
    config.write_text(
        re.sub(r"(?m)^theme:.*$\n?", "", config.read_text(encoding="utf-8")), encoding="utf-8"
    )
    assert run(["--add-config-keys", "theme"], cwd=repo).returncode == 0
    parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert {"wikicommit_version", "translation", "theme", "generate", "schema"} <= set(parsed)
